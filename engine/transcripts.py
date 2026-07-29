"""Episode transcript generation using faster-whisper.

Generates timestamped transcripts from podcast audio files for:
  - Searchable episode text on web players
  - RSS <podcast:transcript> tags
  - SEO indexing
  - Accessibility

May 12 2026: now returns a ``TranscriptResult`` carrying both file
paths AND the in-memory plain text so callers (specifically the
TTS-validation step) can reuse the Whisper output without a second
transcribe call. Saves one Whisper pass per episode (~$0.03-0.10).

July 28 2026 — brand-name repair (P0). Whisper had never been given
the show vocabulary, so it rendered "Nerra" as "NARA" / "Naran" and
"nerranetwork.com" as "naranetwork.com" in **790 committed transcript
files** across 13 shows. That is not a cosmetic bug: SRT/ASS captions
are built from this data, so the wrong brand name is burned into
published Shorts, and the same files are served as
``<podcast:transcript>`` on the audio and video feeds. Two layers fix
it here (a third — :mod:`scripts.fix_transcript_brand` — backfills the
existing files):

  1. ``initial_prompt`` biases faster-whisper's decoder toward the
     real vocabulary. Prevention, but probabilistic — never trusted
     on its own.
  2. :func:`correct_brand_text` / :func:`correct_brand_words` are a
     deterministic post-pass over segment text AND the per-word
     arrays. The word arrays matter as much as the text: the Shorts
     ASS captions read ``segment["words"][i]["word"]`` directly
     (``engine/captions.py``), so text-only repair would leave the
     misspelling burned into video.

Every correction is anchored on following brand context ("Network",
"network.com", "-RU"), never on the bare token, so a legitimate
"Nara" (the Japanese city — plausible on a world-news show like Omni
View) is never rewritten. All 559 observed occurrences carry that
context; the anchor is what keeps the rule safe as coverage grows.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Brand-name repair
# ---------------------------------------------------------------------------

# Vocabulary handed to faster-whisper as ``initial_prompt``. Whisper
# biases decoding toward tokens seen in the prompt, which is the
# supported mechanism for domain vocabulary. Keep it SHORT — the
# prompt competes with the audio for the decoder's attention, and a
# long list degrades general accuracy.
_BASE_VOCABULARY: tuple[str, ...] = (
    "Nerra Network",
    "nerranetwork.com",
)

# The misspelling stem, as Whisper actually produced it: "nara" or
# "naran" (it hears the doubled-R brand as a single R). Anchored with
# \b on both sides so it never fires inside a longer word — the
# observed "dinarag" (a real transcript token) must not match.
_STEM = r"naran?"

# 1. The RU channel: "NARA-RU", "www.nara.ru" → "@NerraRU".
_RU_CHANNEL_RE = re.compile(rf"\b(?:www\.)?{_STEM}[-.]ru\b", re.I)

# 2. Joined domain form: "naranetwork", "NARANetwork", "narannetwork".
_JOINED_RE = re.compile(rf"\b{_STEM}networks?\b", re.I)

# 2b. The stem torn in half around a stray syllable — Whisper heard
#     "nerranetwork.com" and wrote "NARA RENnetwork.com" (MIT Ep074).
#     Requiring the "ren" to sit immediately before "network" keeps
#     this from firing on ordinary prose.
_TORN_RE = re.compile(rf"\b{_STEM}\b[\s\-]{{1,3}}ren(?=networks?\b)", re.I)

# 3. Separated form: "NARA Network", "Naran Network", "nara-network".
#    Only the stem is rewritten; the separator and the "network" token
#    keep whatever casing Whisper emitted.
#
#    The optional "at"/"a" prefix catches the handle being read aloud:
#    "@NerraNetwork" is spoken "at Nerra Network", and Whisper glues
#    the preposition onto the brand — "find us on YouTube at Atnara
#    Network" (FF Ep061, MAB Ep027/032). The preposition is already
#    present in the surrounding text in every observed case, so the
#    whole glued token collapses to the brand.
#
#    ``networks?`` catches the plural the show reads in its own
#    cross-promo ("one of the Nerra Network's daily briefings" heard
#    as "NARA networks"); ``\s`` in the separator lets the anchor
#    reach across the NEWLINE that joins two transcript segments,
#    which is where 41 of the occurrences lived.
_SEPARATED_RE = re.compile(
    rf"\b(?:at?)?{_STEM}\b(?=[\s\-]{{1,3}}networks?\b)", re.I
)


def _match_case(replacement: str, original: str) -> str:
    """Return *replacement* cased to match *original*.

    Lowercase stays lowercase (mid-sentence "nara network dot com");
    anything else becomes the canonical brand capitalisation. ALL-CAPS
    is deliberately NOT preserved — "NERRA Network" would be a new
    misspelling, and the all-caps form is a Whisper artefact of the
    acronym it thought it heard, not an authorial choice.
    """
    return replacement.lower() if original.islower() else replacement


def correct_brand_text(text: str) -> str:
    """Repair Whisper's "Nerra" misspellings in a chunk of transcript text.

    Deterministic and idempotent — running it twice is a no-op, which
    matters because the backfill script may be re-run over files that
    were already corrected.
    """
    if not text:
        return text

    # Cheap bail-out: the stem is absent from the overwhelming
    # majority of segments, and this runs per-segment per-episode.
    if "nara" not in text.lower():
        return text

    text = _RU_CHANNEL_RE.sub("NerraRU", text)
    text = _TORN_RE.sub(lambda m: _match_case("Nerra", m.group(0)), text)
    text = _JOINED_RE.sub(
        lambda m: _match_case("NerraNetwork", m.group(0)), text
    )
    text = _SEPARATED_RE.sub(lambda m: _match_case("Nerra", m.group(0)), text)
    return text


# Stem match with no context requirement. Only ever applied to a word
# token whose FOLLOWING token has already been confirmed as a brand
# anchor — never to free text.
_STEM_ONLY_RE = re.compile(rf"\b(?:at?)?{_STEM}\b", re.I)

# What counts as a brand anchor in the next word token: "network..." /
# "rennetwork..." prefixes, or a standalone "ru". Whisper splits the
# separator unpredictably — "nara" + "-network", "NARA" + "-RU.",
# ".nara" + ".ru." — so leading punctuation is stripped before the test.


# The stem sitting at the very end of a segment, where the anchoring
# "Network" has landed in the next segment.
_TRAILING_STEM_RE = re.compile(rf"\b(?:at?)?{_STEM}\b\s*$", re.I)


def _next_token_anchors(token: str) -> bool:
    """True when *token* is the trailing half of a split brand name."""
    stripped = (token or "").strip().lstrip(".-–—/ ").lower()
    if stripped.startswith(("network", "rennetwork")):
        return True
    # "ru" must stand alone (bar trailing punctuation): "ruins", "rules"
    # and "Russia" begin with the same two letters, and treating them as
    # anchors would rewrite a legitimate preceding "Nara" ("we visited
    # Nara ruins" must never become "Nerra ruins").
    return stripped.startswith("ru") and not stripped[2:3].isalpha()


def _repair_with_external_anchor(token: str) -> str:
    """Repair a token whose anchor lives in the neighbouring token."""
    return _STEM_ONLY_RE.sub(lambda m: _match_case("Nerra", m.group(0)), token)


def correct_brand_words(
    words: Sequence[dict], *, next_token: str = "",
) -> list[dict]:
    """Repair the per-word array, where each token lacks its own context.

    A word entry is often the bare token ``"NARA"`` with the anchoring
    ``"Network"`` sitting in the NEXT entry, so the text-level regex
    cannot see enough to fire. This walks the sequence and supplies the
    missing context from the following word, preserving every timestamp
    and probability untouched.

    *next_token* is the first word of the FOLLOWING segment, so a brand
    split across a segment boundary is repaired too.
    """
    out: list[dict] = []
    for i, entry in enumerate(words):
        token = entry.get("word")
        if not token or "nara" not in token.lower():
            out.append(entry)
            continue

        # Self-contained forms ("naranetwork.com", "NARA-RU") first.
        fixed = correct_brand_text(token)
        if fixed == token:
            following = (
                words[i + 1].get("word", "") if i + 1 < len(words) else next_token
            )
            if _next_token_anchors(following):
                fixed = _repair_with_external_anchor(token)

        if fixed != token:
            entry = {**entry, "word": fixed}
        out.append(entry)
    return out


def correct_brand_segments(segments: Sequence[dict]) -> list[dict]:
    """Repair a whole segment list, including brands split across segments.

    Whisper often ends a segment on the bare stem and opens the next
    one with "Network", so neither segment carries enough context on
    its own — the same blind spot the per-word pass solves, one level
    up. Handles ``text`` and the nested ``words`` array together.
    """
    out: list[dict] = []
    for i, segment in enumerate(segments):
        updated = dict(segment)

        text = updated.get("text") or ""
        fixed = correct_brand_text(text)
        if fixed == text and "nara" in text.lower():
            # Borrow the anchor from the start of the next segment. Only
            # the TRAILING stem is rewritten — a legitimate "Nara" earlier
            # in the same segment keeps its own (absent) context.
            nxt = (segments[i + 1].get("text") or "") if i + 1 < len(segments) else ""
            first = nxt.strip().split(" ", 1)[0] if nxt.strip() else ""
            if _next_token_anchors(first):
                fixed = _TRAILING_STEM_RE.sub(
                    lambda m: _match_case("Nerra", m.group(0)), text
                )
        if fixed != text:
            updated["text"] = fixed

        words = updated.get("words")
        if words:
            # Hand the next segment's opening word across the boundary so
            # a brand split between segments still finds its anchor.
            nxt_words = (
                segments[i + 1].get("words") or [] if i + 1 < len(segments) else []
            )
            head = nxt_words[0].get("word", "") if nxt_words else ""
            updated["words"] = correct_brand_words(words, next_token=head)

        out.append(updated)
    return out


# Whisper conditions on roughly the last 224 TOKENS of the prompt; stay
# comfortably under that so nothing is silently dropped.
_MAX_PROMPT_CHARS = 600


def build_initial_prompt(vocabulary: Optional[Iterable[str]] = None) -> str:
    """Compose the faster-whisper ``initial_prompt`` for a show.

    *vocabulary* carries per-show proper nouns (the show name and its
    YAML ``keywords:``); the network brand is always included — and goes
    LAST, because Whisper keeps the *tail* of an oversized prompt: put
    first, the brand terms are exactly what truncation removes on
    keyword-heavy shows (planetterrian's list alone overflows the
    window). Excess show keywords are dropped instead, never the brand.
    """
    brand = list(_BASE_VOCABULARY)
    seen = {t.lower() for t in brand}
    extras: list[str] = []
    for term in vocabulary or ():
        term = (term or "").strip()
        if term and term.lower() not in seen:
            seen.add(term.lower())
            extras.append(term)

    budget = _MAX_PROMPT_CHARS - (len(", ".join(brand)) + 1)
    kept: list[str] = []
    used = 0
    for term in extras:
        cost = len(term) + 2  # ", " separator
        if used + cost > budget:
            break
        kept.append(term)
        used += cost
    return ", ".join(kept + brand) + "."


@dataclass(frozen=True)
class TranscriptResult:
    """Output of a successful ``generate_transcript()`` call.

    ``txt_path`` and ``json_path`` are written to disk; ``text`` is
    the same plain-text content as ``txt_path.read_text()`` but
    available without a second disk round-trip (and lets the
    TTS-validation stage skip its own Whisper call entirely).
    """

    txt_path: Path
    json_path: Path
    text: str


def generate_transcript(
    audio_path: Path,
    output_dir: Path,
    episode_prefix: str,
    *,
    model_size: str = "base",
    language: Optional[str] = None,
    vocabulary: Optional[Iterable[str]] = None,
) -> Optional[TranscriptResult]:
    """Generate a transcript from an MP3 file using faster-whisper.

    Parameters
    ----------
    audio_path:
        Path to the MP3 file.
    output_dir:
        Directory to write transcript files into.
    episode_prefix:
        Filename prefix (e.g. ``"TST_Ep042_20260316"``).
    model_size:
        Whisper model size (``"tiny"``, ``"base"``, ``"small"``).
    language:
        Language code (e.g. ``"en"``, ``"ru"``). None = auto-detect.
    vocabulary:
        Show-specific proper nouns (show name + YAML ``keywords:``)
        added to the decoder's ``initial_prompt`` alongside the
        network brand. Optional — the brand terms are always sent.

    Returns
    -------
    TranscriptResult or None
        On success, a ``TranscriptResult`` with ``txt_path``,
        ``json_path``, and ``text`` (plain-text transcript). On
        failure (faster-whisper missing, audio missing, transcribe
        raised), returns None — caller treats as non-fatal.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.info("faster-whisper not installed — skipping transcript generation")
        return None

    if not audio_path.exists():
        logger.warning("Audio file not found for transcript: %s", audio_path)
        return None

    # Ensure the destination exists — callers pass fresh subdirs (e.g. the
    # Nerra Voices post-interview workdir), and losing a 4-minute Whisper
    # run to a missing mkdir is silly (first Age of AI dry run, July 2026).
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Generating transcript from %s (model=%s) ...", audio_path.name, model_size)

    # Pass through ``HF_TOKEN`` if present so the faster-whisper model
    # download uses authenticated requests to Hugging Face Hub. Without
    # it every run logs ``Warning: You are sending unauthenticated
    # requests to the HF Hub. Please set a HF_TOKEN to enable higher
    # rate limits and faster downloads.`` (TST Ep465 log, May 6 2026
    # — recurring on every show). Optional — anonymous still works,
    # just slower and rate-limited.
    import os
    hf_token = os.getenv("HF_TOKEN", "").strip()

    try:
        # ``faster-whisper`` reads ``HF_TOKEN`` directly from the env via
        # huggingface_hub. We export it explicitly here so the value
        # picked up matches whatever the operator sets — and so the
        # absence is logged once per run instead of once per HTTP call.
        if hf_token:
            os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=5,
            word_timestamps=True,
            # Bias the decoder toward the real brand vocabulary. This
            # is prevention only — the deterministic repair below is
            # what we actually rely on (July 28 2026).
            initial_prompt=build_initial_prompt(vocabulary),
        )

        transcript_segments = []
        full_text_parts = []

        for segment in segments:
            seg_text = correct_brand_text(segment.text.strip())
            seg_data = {
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": seg_text,
            }
            if segment.words:
                seg_data["words"] = correct_brand_words([
                    {
                        "word": w.word.strip(),
                        "start": round(w.start, 2),
                        "end": round(w.end, 2),
                        "probability": round(w.probability, 3),
                    }
                    for w in segment.words
                ])
            transcript_segments.append(seg_data)

        # Second pass: repair brands that straddle a segment boundary
        # (Whisper ends a segment on "NARA" and opens the next with
        # "Network" — neither half has enough context alone).
        transcript_segments = correct_brand_segments(transcript_segments)
        full_text_parts = [s["text"] for s in transcript_segments]

        # Write JSON transcript (timestamped segments + word-level data)
        json_path = output_dir / f"{episode_prefix}_transcript.json"
        json_data = {
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration": round(info.duration, 2),
            "segments": transcript_segments,
        }
        json_path.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Write plain-text transcript
        # Joined last so a brand spanning the newline between two
        # segments is caught even if the segment pass could not see it.
        plain_text = correct_brand_text("\n".join(full_text_parts))
        txt_path = output_dir / f"{episode_prefix}_transcript.txt"
        txt_path.write_text(plain_text, encoding="utf-8")

        logger.info(
            "Transcript generated: %s (%d segments, %s detected)",
            txt_path.name, len(transcript_segments), info.language,
        )
        return TranscriptResult(
            txt_path=txt_path, json_path=json_path, text=plain_text,
        )

    except Exception as exc:
        logger.warning("Transcript generation failed (non-fatal): %s", exc)
        return None
