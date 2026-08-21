"""Nerra Daily — the network's combined daily edition.

One episode a day that splices the ALREADY-PUBLISHED English episodes into
a single feed, with short new host links spoken by Mira (the Age of AI
host, Grok voice ``ara``) between segments. Nothing here regenerates show
content: the segments are the exact MP3s the standalone feeds shipped,
downloaded back from R2, so the marginal cost of an edition episode is a
few cents of link TTS plus one small Grok call to write the links.

Design rules that bind:

* **The per-show cross-promo outro is CUT from edition segments only.**
  Every English episode's spoken tail is sign-off -> network sibling plug
  (``engine.network_promo``) -> website-surface plug -> AI disclosure, all
  baked into the voice audio. Inside a combined network episode those
  plugs are noise (the sibling show often plays two segments later), so
  each segment is trimmed at the plug using the episode's committed
  Whisper word-timestamp transcript, and Mira speaks ONE network-level AI
  disclosure at the end of the combined episode. The standalone feeds are
  untouched — this module only ever writes under its own edition paths.
* **Detection is transcript-evidence based, never guesswork.** Whisper
  renders the brand many ways ("Nerra network", "Nera network", "Narrow
  Network", "NERANetwork.com" — all observed in committed transcripts),
  so the matchers are fuzzy on the brand token but anchored on the four
  promo frame shapes from ``engine.network_promo``. No match = no trim:
  the segment ships whole (plug included) rather than risk cutting real
  content. A cut is also refused in the first half of an episode.
* **Editions are language-parameterized from day one** (the ru_dub ->
  lang_dub lesson): everything show-specific lives in an
  :class:`EditionSpec`, so a Russian or French edition is a new spec +
  prompt file, not a fork.

The orchestrator that runs this end to end is
``scripts/build_daily_edition.py``; the workflow is
``.github/workflows/nerra-daily.yml``. Docs: ``docs/nerra_daily.md``.
Drift guards: ``tests/test_daily_edition.py``.
"""

from __future__ import annotations

import bisect
import datetime as _dt
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Mira's sanctioned Grok voice (same preset the Age of AI narration uses).
MIRA_VOICE_ID = "ara"

#: Spoken once by Mira at the very end of the combined episode, replacing
#: the 11-13 per-segment disclosures the trim removes. Keep it one
#: sentence-pair (the May 2026 disclosure-tightening rule) and keep it
#: honest about BOTH layers: her links are AI-voiced AND the segments come
#: from the network's AI-voiced shows.
MIRA_AI_DISCLOSURE = (
    "Nerra Daily is assembled from the Nerra Network's shows, which use AI "
    "voice synthesis, and my own voice is AI generated too — the editorial "
    "selection and analysis across the network are our own."
)

#: Uniform re-encode for every spliced piece (segments + Mira links) so the
#: final stream-copy concat joins identical streams. ``-q:a 2`` (~190 kbps
#: VBR) is one small step below the shows' archival ``-q:a 0`` master —
#: inaudible for speech, and it keeps a ~2 h daily file near ~150 MB.
SEGMENT_ENCODE_ARGS = ["-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-q:a", "2"]

PROMO_FADE_SECONDS = 0.5
PROMO_CUT_PAD_SECONDS = 0.15
#: Only the last stretch of a transcript is searched for the plug.
PROMO_SEARCH_WINDOW_SECONDS = 150.0
#: A candidate cut before this fraction of the episode is refused outright.
PROMO_MIN_FRACTION = 0.5
#: "Rather watch than listen" YouTube CTA directly before the plug — when it
#: sits within this many seconds of the plug cut, the cut moves earlier to
#: include it (it reads as part of the outro block, and repeating it 11x in
#: one combined episode is the exact fatigue the trim exists to remove).
YOUTUBE_LEAD_WINDOW_SECONDS = 25.0


# ---------------------------------------------------------------------------
# Edition registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EditionSpec:
    """Everything one combined edition needs to know about itself."""

    edition_id: str
    slug: str
    name: str
    host: str
    language: str
    voice_id: str
    #: Fixed rundown order (operator decision 2026-08-21: flagships first
    #: by audience — Tesla / M&A / SpaceX are 53% of network downloads —
    #: with The DP Pod's good-news show as the deliberate warm close).
    lineup: Tuple[str, ...]
    #: Lineup members that only publish on Mondays. Discovery is purely
    #: date-driven (a late Monday episode found on Tuesday still splices);
    #: this set only shapes the *expected* roster used by the ready gate.
    monday_only: frozenset
    feed_file: str
    guid_prefix: str
    episode_prefix: str
    r2_prefix: str
    digest_dir: str
    show_page: str
    prompt_file: str
    channel_description: str
    channel_category: str = "News"
    channel_subcategory: str = "Daily News"
    channel_keywords: str = ""
    cover_url: str = ""
    #: Below this many available segments the build refuses to publish —
    #: a two-show "network edition" misrepresents the product.
    min_segments: int = 4


EDITIONS: Dict[str, EditionSpec] = {
    "en": EditionSpec(
        edition_id="en",
        slug="nerra_daily",
        name="Nerra Daily",
        host="Mira",
        language="en",
        voice_id=MIRA_VOICE_ID,
        lineup=(
            "tesla",
            "models_agents",
            "spacex",
            "modern_investing",
            "omni_view",
            "fascinating_frontiers",
            "planetterrian",
            "unintended_consequences",
            "first_principles",
            "models_agents_beginners",
            "env_intel",
            "offshore_north",
            "dp_pod",
        ),
        monday_only=frozenset({"env_intel", "offshore_north"}),
        feed_file="nerra_daily_podcast.rss",
        guid_prefix="nerra-daily",
        episode_prefix="Nerra_Daily",
        r2_prefix="nerra_daily",
        digest_dir="digests/nerra_daily",
        show_page="nerra-daily.html",
        prompt_file="shows/prompts/nerra_daily_links.txt",
        channel_description=(
            "The whole Nerra Network in one daily listen. Mira — the AI "
            "documentarian who hosts The Age of AI — anchors every English "
            "show the network published today: Tesla, SpaceX, AI, markets, "
            "world news, science, big ideas, and a good-news close. Each "
            "segment is the full episode; Mira adds the through-line."
        ),
        channel_keywords=(
            "daily news, tech news, Tesla, SpaceX, AI, investing, science, "
            "podcast network, daily briefing, Nerra Network"
        ),
        cover_url="https://nerranetwork.com/assets/covers/nerra-daily.jpg",
    ),
}


def edition(edition_id: str) -> EditionSpec:
    try:
        return EDITIONS[edition_id]
    except KeyError:
        raise KeyError(
            f"unknown edition '{edition_id}' — known: {', '.join(sorted(EDITIONS))}"
        )


# ---------------------------------------------------------------------------
# Segment discovery
# ---------------------------------------------------------------------------

_OP3_RE = re.compile(r"^https?://op3\.dev/e/", re.IGNORECASE)
_EP_TITLE_RE = re.compile(r"^\s*(?:Ep|Episode|Выпуск)\s*\d+\s*[:—-]\s*", re.IGNORECASE)


def strip_op3(url: str) -> str:
    """Return the bare enclosure URL (OP3 redirector prefix removed)."""
    if not url:
        return url
    stripped = _OP3_RE.sub("", url)
    if stripped != url and not stripped.startswith("http"):
        stripped = "https://" + stripped
    return stripped


def hook_from_title(episode_title: str) -> str:
    """``"Ep 578: <hook>"`` -> ``"<hook>"`` (title unchanged when unlabeled)."""
    return _EP_TITLE_RE.sub("", episode_title or "").strip()


@dataclass
class Segment:
    """One show's already-published episode, as the edition sees it."""

    slug: str
    show_name: str
    episode_num: int
    episode_title: str
    hook: str
    date: str
    audio_url: str
    content: str
    digest_dir: Path
    transcript_path: Optional[Path]
    music_intro_offset: float
    #: Filled in during assembly:
    cut_final_seconds: Optional[float] = None
    cut_kind: str = ""
    duration_seconds: Optional[float] = None


def _summaries_entries(summaries_path: Path) -> List[dict]:
    if not summaries_path.exists():
        return []
    try:
        data = json.loads(summaries_path.read_text(encoding="utf-8")) or {}
    except (json.JSONDecodeError, OSError):
        logger.warning("unreadable summaries file: %s", summaries_path)
        return []
    if isinstance(data, dict):
        return [e for e in data.get("summaries", []) if isinstance(e, dict)]
    if isinstance(data, list):
        return [e for e in data if isinstance(e, dict)]
    return []


def _transcript_path_for(digest_dir: Path, audio_url: str) -> Optional[Path]:
    """The committed Whisper transcript sits beside the digest, named after
    the MP3: ``<basename>_transcript.json``."""
    basename = strip_op3(audio_url).rsplit("/", 1)[-1]
    if not basename.endswith(".mp3"):
        return None
    candidate = digest_dir / (basename[: -len(".mp3")] + "_transcript.json")
    return candidate if candidate.exists() else None


def discover_segments(
    spec: EditionSpec,
    root: Path,
    target_date: _dt.date,
    *,
    config_loader=None,
) -> Tuple[List[Segment], List[str]]:
    """Find every lineup show with an episode dated *target_date*.

    Returns ``(segments_in_lineup_order, missing_slugs)`` where missing
    covers only shows *expected* that day (weekday-aware) — a Monday-only
    show absent on a Wednesday is not missing, but its episode IS spliced
    if one happens to carry today's date (late publish).
    """
    if config_loader is None:
        from engine.config import load_config as config_loader  # noqa: PLC0415

    date_str = target_date.isoformat()
    expected = set(expected_slugs(spec, target_date))
    segments: List[Segment] = []
    missing: List[str] = []

    for slug in spec.lineup:
        try:
            cfg = config_loader(str(root / "shows" / f"{slug}.yaml"))
        except Exception as exc:  # noqa: BLE001 — one bad YAML must not sink the edition
            logger.warning("could not load config for %s: %s", slug, exc)
            if slug in expected:
                missing.append(slug)
            continue
        summaries_path = root / cfg.publishing.summaries_json
        entry = next(
            (e for e in _summaries_entries(summaries_path) if e.get("date") == date_str),
            None,
        )
        if entry is None or not entry.get("audio_url"):
            if slug in expected:
                missing.append(slug)
            continue
        digest_dir = summaries_path.parent
        audio_url = strip_op3(str(entry["audio_url"]))
        title = str(entry.get("episode_title") or "")
        segments.append(
            Segment(
                slug=slug,
                show_name=cfg.name or slug,
                episode_num=int(entry.get("episode_num") or 0),
                episode_title=title,
                hook=hook_from_title(title),
                date=date_str,
                audio_url=audio_url,
                content=str(entry.get("content") or ""),
                digest_dir=digest_dir,
                transcript_path=_transcript_path_for(digest_dir, audio_url),
                music_intro_offset=float(
                    (cfg.audio.voice_intro_delay or 0.0) + (cfg.audio.intro_duration or 0.0)
                ),
            )
        )
    return segments, missing


def expected_slugs(spec: EditionSpec, target_date: _dt.date) -> List[str]:
    """The roster the ready gate waits for on *target_date* (Monday adds
    the weeklies; every other lineup show is daily)."""
    is_monday = target_date.weekday() == 0
    return [
        s for s in spec.lineup if is_monday or s not in spec.monday_only
    ]


# ---------------------------------------------------------------------------
# Promo-cut detection (transcript word timestamps)
# ---------------------------------------------------------------------------

# Anchored on the four rotating frames in engine.network_promo, with the
# brand token fuzzy (Whisper spellings observed in committed transcripts:
# Nerra / Nera / Narra / Narrow / NERA). Order does not imply priority —
# the earliest match in the tail window wins.
_PRIMARY_PROMO_PATTERNS = [
    re.compile(r"\b(?:and\s+)?before you go\s+this show is part of the \w+ network\b"),
    re.compile(r"\bthis show is part of the \w+ network\b"),
    re.compile(r"\bone more thing\b(?:\s+\w+){0,14}?\s+sister show\b"),
    re.compile(r"\bquick tip from the network\b"),
    re.compile(r"\bthis show comes to you from the \w+ network\b"),
]
#: The YouTube CTA that immediately precedes the plug on most shows.
_YOUTUBE_LEAD_PATTERN = re.compile(
    r"\b(?:and\s+)?if you(?:\s+\w+){0,2}\s+rather watch than listen\b"
)
#: Weaker evidence, used only when no frame matched.
_NETWORK_MENTION_PATTERN = re.compile(r"\b(?:nerra|nera|narra|narrow)\s*network\b")
_DISCLOSURE_PATTERN = re.compile(r"\bthis episode used ai voice synthesis\b")

_TOKEN_CLEAN_RE = re.compile(r"[^a-z0-9]+")


def _word_stream(transcript: dict, min_start: float) -> List[Tuple[str, float, float]]:
    """Flatten transcript words at/after *min_start* into normalized
    ``(token, start, end)`` triples. A word like ``"NERANetwork.com"``
    expands to multiple tokens sharing one timing. Segments without word
    data fall back to segment-granularity timing."""
    stream: List[Tuple[str, float, float]] = []
    for seg in transcript.get("segments", []):
        seg_start = float(seg.get("start", 0.0) or 0.0)
        seg_end = float(seg.get("end", 0.0) or 0.0)
        if seg_end < min_start:
            continue
        words = seg.get("words") or []
        if words:
            source = [
                (
                    str(w.get("word", "")),
                    float(w.get("start", seg_start) or 0.0),
                    float(w.get("end", seg_end) or 0.0),
                )
                for w in words
            ]
        else:
            source = [(t, seg_start, seg_end) for t in str(seg.get("text", "")).split()]
        for raw, start, end in source:
            if start < min_start:
                continue
            for token in _TOKEN_CLEAN_RE.sub(" ", raw.lower()).split():
                stream.append((token, start, end))
    return stream


def _search_stream(
    stream: List[Tuple[str, float, float]], pattern: re.Pattern
) -> Optional[int]:
    """Index into *stream* of the earliest *pattern* match, or None."""
    if not stream:
        return None
    joined_parts: List[str] = []
    offsets: List[int] = []
    pos = 0
    for token, _start, _end in stream:
        offsets.append(pos)
        joined_parts.append(token)
        pos += len(token) + 1
    joined = " ".join(joined_parts)
    m = pattern.search(joined)
    if not m:
        return None
    return max(bisect.bisect_right(offsets, m.start()) - 1, 0)


def _cut_before(stream: List[Tuple[str, float, float]], idx: int) -> float:
    """The cut point just before token *idx*: padded back from the match
    but never into the previous word — a sign-off's final syllable must
    survive the trim intact."""
    start = stream[idx][1]
    cut = start - PROMO_CUT_PAD_SECONDS
    if idx > 0:
        prev_end = stream[idx - 1][2]
        cut = max(cut, min(prev_end + 0.03, start - 0.02))
    return max(0.0, cut)


def find_promo_cut(transcript: dict) -> Optional[dict]:
    """Locate where the appended network-outro block begins on the RAW
    voice track. Returns ``{"raw_seconds", "kind"}`` or ``None``.

    ``kind`` is ``"promo"`` (a frame matched — plug + surface plug + AI
    disclosure all fall after the cut), ``"network_mention"`` (fuzzy brand
    mention only — cut at the containing sentence's segment start), or
    ``"disclosure"`` (only the AI-disclosure line found — the mildest trim).
    """
    duration = float(transcript.get("duration") or 0.0)
    if duration <= 0:
        return None
    window_start = max(0.0, duration - PROMO_SEARCH_WINDOW_SECONDS)
    stream = _word_stream(transcript, window_start)
    if not stream:
        return None

    cut: Optional[float] = None
    kind = ""
    primary_hits = [
        i for i in (
            _search_stream(stream, pat) for pat in _PRIMARY_PROMO_PATTERNS
        ) if i is not None
    ]
    if primary_hits:
        idx = min(primary_hits)
        kind = "promo"
        lead_idx = _search_stream(stream, _YOUTUBE_LEAD_PATTERN)
        if (
            lead_idx is not None
            and 0 < stream[idx][1] - stream[lead_idx][1] <= YOUTUBE_LEAD_WINDOW_SECONDS
        ):
            idx = lead_idx
        cut = _cut_before(stream, idx)
    else:
        mention_idx = _search_stream(stream, _NETWORK_MENTION_PATTERN)
        if mention_idx is not None:
            # Back up to the start of the transcript segment containing the
            # mention so the cut lands on a sentence boundary, not mid-plug.
            mention = stream[mention_idx][1]
            seg_start = mention
            for seg in transcript.get("segments", []):
                s = float(seg.get("start", 0.0) or 0.0)
                e = float(seg.get("end", 0.0) or 0.0)
                if s <= mention <= e:
                    seg_start = s
                    break
            cut, kind = max(0.0, seg_start - PROMO_CUT_PAD_SECONDS), "network_mention"
        else:
            disclosure_idx = _search_stream(stream, _DISCLOSURE_PATTERN)
            if disclosure_idx is not None:
                cut, kind = _cut_before(stream, disclosure_idx), "disclosure"

    if cut is None:
        return None
    if cut < duration * PROMO_MIN_FRACTION:
        logger.warning(
            "refusing promo cut at %.1fs of %.1fs (before the %d%% floor)",
            cut, duration, int(PROMO_MIN_FRACTION * 100),
        )
        return None
    return {"raw_seconds": round(cut, 2), "kind": kind}


def load_transcript(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("unreadable transcript %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# ffmpeg command builders (pure — executed by the orchestrator)
# ---------------------------------------------------------------------------

def segment_trim_cmd(
    in_path: Path, out_path: Path, cut_final_seconds: Optional[float]
) -> List[str]:
    """Re-encode one published episode into a splice-ready segment,
    optionally trimmed at *cut_final_seconds* (final-MP3 timeline) with a
    short fade so the ducked music bed never hard-cuts."""
    cmd = ["ffmpeg", "-y", "-i", str(in_path)]
    if cut_final_seconds is not None:
        fade_start = max(0.0, cut_final_seconds - PROMO_FADE_SECONDS)
        cmd += [
            "-t", f"{cut_final_seconds:.2f}",
            "-af", f"afade=t=out:st={fade_start:.2f}:d={PROMO_FADE_SECONDS}",
        ]
    return cmd + SEGMENT_ENCODE_ARGS + [str(out_path)]


def mira_piece_cmd(in_path: Path, out_path: Path) -> List[str]:
    """Process one raw Mira TTS piece to match the segments: loudness to
    the network's -16 LUFS spec, breathing room either side, 44.1 kHz
    stereo at the shared VBR setting."""
    filters = (
        "loudnorm=I=-16:TP=-1.5:LRA=11,"
        "adelay=350:all=1,apad=pad_dur=0.45"
    )
    return (
        ["ffmpeg", "-y", "-i", str(in_path), "-af", filters]
        + SEGMENT_ENCODE_ARGS
        + [str(out_path)]
    )


# ---------------------------------------------------------------------------
# Chapters
# ---------------------------------------------------------------------------

def build_chapters(
    pieces: List[Tuple[str, float]], episode_title: str
) -> dict:
    """Podcasting 2.0 JSON Chapters from ``(title, duration_seconds)``
    pieces in splice order. Boundaries are exact (we performed the splice),
    unlike the per-show proportional estimates."""
    chapters = []
    cursor = 0.0
    for title, dur in pieces:
        start = round(cursor, 1)
        cursor += max(0.0, float(dur))
        chapters.append(
            {"startTime": start, "title": title, "endTime": round(cursor, 1)}
        )
    return {"version": "1.2.0", "chapters": chapters, "title": episode_title}


# ---------------------------------------------------------------------------
# Mira's links — prompt build, response parse, deterministic fallback
# ---------------------------------------------------------------------------

_MD_NOISE_RE = re.compile(r"[#*_`>\[\]]|\(https?://[^)]*\)")
_WS_RE = re.compile(r"\s+")


def sanitize_spoken(text: str) -> str:
    """Make LLM output safe to hand to TTS: strip markdown residue, URLs
    (the spoken form 'nerranetwork.com' survives; bracketed link syntax
    does not) and collapse whitespace."""
    from engine.utils import strip_speech_tags  # noqa: PLC0415

    text = strip_speech_tags(text or "")
    text = _MD_NOISE_RE.sub("", text)
    return _WS_RE.sub(" ", text).strip()


def digest_excerpt(content_md: str, limit: int = 550) -> str:
    """A compact plain-text taste of a show's digest for the link prompt —
    headers/formatting stripped, first substantive prose kept."""
    lines = []
    for raw in (content_md or "").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "|", "---", "![", "**REAL-TIME")):
            continue
        line = _MD_NOISE_RE.sub("", line)
        lines.append(line)
        if sum(len(x) for x in lines) > limit:
            break
    text = _WS_RE.sub(" ", " ".join(lines)).strip()
    return text[:limit].rsplit(" ", 1)[0] if len(text) > limit else text


def build_links_prompt(
    spec: EditionSpec,
    root: Path,
    segments: List[Segment],
    target_date: _dt.date,
    aoai_today: Optional[dict],
) -> str:
    template = (root / spec.prompt_file).read_text(encoding="utf-8")
    lineup_lines = []
    for i, seg in enumerate(segments, 1):
        lineup_lines.append(
            f"{i}. {seg.show_name} — \"{seg.hook or seg.episode_title}\"\n"
            f"   Today's episode covers: {digest_excerpt(seg.content)}"
        )
    # Rotate how much of herself Mira brings, deterministically by date, so
    # a daily listener does not hear the identical self-framing every day.
    reflection = (
        "In the OPENING, briefly mention that you also host The Age of AI — "
        "the network's interview show where you, an AI, phone real people — "
        "and one specific thing you hope that show achieves.",
        "In the SIGN-OFF, one short reflective line connecting something "
        "from today's episodes to your work hosting The Age of AI.",
        "Do not talk about The Age of AI today unless it published a new "
        "episode; just anchor the day.",
    )[target_date.toordinal() % 3]
    if aoai_today:
        aoai_block = (
            "A NEW episode of your own show, The Age of AI, published today: "
            f"\"{aoai_today.get('title', '')}\" with guest "
            f"{aoai_today.get('guest', '')}. Plug it warmly in the opening — "
            "it is your own interview, so genuine enthusiasm is honest — and "
            "tell listeners to find The Age of AI in their podcast app or at "
            "nerranetwork.com. Do not splice or summarize the interview."
        )
    else:
        aoai_block = "No new Age of AI episode today. " + reflection
    return template.format(
        date_spoken=target_date.strftime("%A, %B %-d, %Y"),
        weekday=target_date.strftime("%A"),
        segment_count=len(segments),
        handoff_count=max(0, len(segments) - 1),
        lineup_block="\n".join(lineup_lines),
        aoai_block=aoai_block,
    )


def parse_links_json(text: str, handoff_count: int) -> Optional[dict]:
    """Extract ``{"intro", "handoffs", "signoff"}`` from an LLM reply.
    Returns None on any shape problem (caller falls back)."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    intro = sanitize_spoken(str(data.get("intro", "")))
    signoff = sanitize_spoken(str(data.get("signoff", "")))
    handoffs = [sanitize_spoken(str(h)) for h in data.get("handoffs", []) if str(h).strip()]
    if not intro or not signoff or len(handoffs) < handoff_count:
        return None
    return {"intro": intro, "handoffs": handoffs[:handoff_count], "signoff": signoff}


def fallback_links(
    spec: EditionSpec, segments: List[Segment], target_date: _dt.date
) -> dict:
    """Deterministic minimal-announcer links used ONLY when the LLM call
    fails — every line still carries that day's real titles, so even the
    fallback is never two days identical."""
    date_spoken = target_date.strftime("%A, %B %-d")
    names = ", ".join(s.show_name for s in segments[:-1])
    intro = (
        f"This is {spec.name} for {date_spoken}. I'm {spec.host}, and this "
        f"is every English show the Nerra Network published today, in one "
        f"listen: {names}, and {segments[-1].show_name}. First up, "
        f"{segments[0].show_name}: {segments[0].hook or segments[0].episode_title}"
    )
    handoffs = [
        f"Next on {spec.name}: {seg.show_name}. Today — "
        f"{seg.hook or seg.episode_title}"
        for seg in segments[1:]
    ]
    signoff = (
        f"And that was the network's day. Every one of these shows has its "
        f"own feed, notes and archive at nerranetwork.com. I'm {spec.host} — "
        f"back tomorrow."
    )
    return {"intro": intro, "handoffs": handoffs, "signoff": signoff}


def aoai_new_episode(root: Path, target_date: _dt.date) -> Optional[dict]:
    """A new Age of AI interview published on *target_date*, if any."""
    path = root / "digests" / "age_of_ai" / "summaries_age_of_ai.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        return None
    for ep in data.get("episodes", []):
        if isinstance(ep, dict) and ep.get("date") == target_date.isoformat():
            return ep
    return None


# ---------------------------------------------------------------------------
# Titles, descriptions, digest markdown
# ---------------------------------------------------------------------------

def daily_title(episode_num: int, target_date: _dt.date, segments: List[Segment]) -> str:
    """``"Ep N: <Weekday> edition — <lead hook>"``, clipped by the one
    module that owns title limits (engine.titles)."""
    from engine.titles import episode_title  # noqa: PLC0415

    lead = segments[0].hook or segments[0].episode_title if segments else ""
    hook = f"{target_date.strftime('%A')} edition — {lead}"
    return episode_title(hook, episode_num, fallback=f"Nerra Daily — {target_date.isoformat()}")


def feed_description(
    spec: EditionSpec, segments: List[Segment], target_date: _dt.date
) -> str:
    lines = [
        f"{spec.name} — {target_date.strftime('%A, %B %-d, %Y')}. The whole "
        f"Nerra Network in one listen, anchored by {spec.host}.",
        "",
        "In this edition:",
    ]
    lines += [f"• {seg.show_name}: {seg.hook or seg.episode_title}" for seg in segments]
    lines += [
        "",
        "Every show has its own feed and full notes at https://nerranetwork.com",
    ]
    return "\n".join(lines)


def build_digest_md(
    spec: EditionSpec,
    root: Path,
    episode_num: int,
    target_date: _dt.date,
    segments: List[Segment],
    links: dict,
    aoai_today: Optional[dict],
) -> str:
    """The committed daily digest markdown — the blog post's source. It is
    deliberately a RUNDOWN (Mira's words + titles + links into each show's
    own post), never a copy of the shows' digests, so the network's blog
    does not compete with itself for the same text."""
    title = f"{spec.name} — {target_date.strftime('%A, %B %-d, %Y')}"
    parts = [
        f"# {title}",
        "",
        f"**Date:** {target_date.strftime('%B %d, %Y')}",
        "",
        f"*Hosted by {spec.host} · Episode {episode_num} · every English "
        f"show the Nerra Network published today, in one listen.*",
        "",
        links["intro"],
        "",
        "## Today's rundown",
        "",
    ]
    try:
        from generate_html import NETWORK_SHOWS as _ns  # noqa: PLC0415 — canonical page names
    except Exception:  # noqa: BLE001 — page links degrade to the slug convention
        _ns = {}
    for seg in segments:
        blog_link = root / "blog" / seg.slug / f"ep{seg.episode_num:03d}.html"
        link_bits = []
        if blog_link.exists():
            link_bits.append(
                f"[Full episode notes](/blog/{seg.slug}/ep{seg.episode_num:03d}.html)"
            )
        page = _ns.get(seg.slug, {}).get("show_page") or seg.slug.replace("_", "-") + ".html"
        link_bits.append(f"[{seg.show_name}](/{page})")
        parts += [
            f"### {seg.show_name} — {seg.hook or seg.episode_title}",
            "",
            " · ".join(link_bits),
            "",
        ]
    if aoai_today:
        parts += [
            f"### New on The Age of AI — {aoai_today.get('title', '')}",
            "",
            "Mira's own interview show published a new episode today. "
            "[Listen on The Age of AI](/age-of-ai.html)",
            "",
        ]
    parts += ["## Sign-off", "", links["signoff"], ""]
    return "\n".join(parts)
