#!/usr/bin/env python3
"""Calibrate the Nerra Network pronunciation pipeline against raw Grok TTS.

For each candidate word, generate audio via Grok TTS **both** with the raw
word AND with each candidate respelling. Transcribe the audio with
faster-whisper. Compare the transcript against the target word and score the
result.

The output tells the operator, per word:

  * Whether Grok pronounces the raw word correctly (→ respelling is
    redundant and should be removed).
  * Whether any respelling produces a worse result than the raw word
    (→ respelling is actively harmful, like ``plan it TAIR ee uhn``
    transcribed as ``Planet Terra EE and Daily``).
  * Which respelling among a candidate set lands closest to the target.

Costs: ~$0.02 per audio generation × N candidates × M words. A typical
sweep (15 words × 3 candidates) is ~$0.90.

Usage:

    # Test a single word with the respellings currently in the maps
    BUTTONDOWN_API_KEY=... GROK_API_KEY=... python scripts/test_pronunciation.py \\
        --word Planetterrian

    # Test all baked-in candidates and write a markdown report
    python scripts/test_pronunciation.py --all --report calibration.md

    # Full sweep: load every entry currently in the production maps
    # (shows/pronunciation_map.yaml + assets/pronunciation.py) and
    # score each respelling vs. raw Grok rendering.
    python scripts/test_pronunciation.py --from-pipeline --report sweep.md

    # Try a custom respelling alongside the existing ones
    python scripts/test_pronunciation.py --word Alnylam \\
        --respelling "al-NEE-lum"

Requirements: GROK_API_KEY (or XAI_API_KEY) in env. faster-whisper installed
(``pip install faster-whisper`` — already a project dep).

This script is intentionally NOT part of the test suite — it spends money
on real API calls and shouldn't run on every CI invocation. Run it manually
when:

  * A new respelling is proposed (test it before shipping).
  * An operator hears a mispronunciation in production.
  * The Grok TTS voice model changes (re-baseline everything).
"""

from __future__ import annotations

import argparse
import difflib
import logging
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("test_pronunciation")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


# ---------------------------------------------------------------------------
# Candidates to test by default
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """One word + the respellings to compare against its raw form."""
    target: str
    respellings: List[str] = field(default_factory=list)


# Curated list of words flagged in production. Each entry pairs the canonical
# spelling with the respellings currently/previously used in the pipeline.
# Add new entries when the operator reports a mispronunciation.
DEFAULT_CANDIDATES: List[Candidate] = [
    Candidate(
        target="Planetterrian",
        respellings=[
            "Planet-terry-an",        # legacy WORD_PRONUNCIATIONS (PR-#355-)
            "plan it TAIR ee uhn",    # PR #355 (also wrong per May 11 daily)
        ],
    ),
    Candidate(
        target="tissue",
        respellings=["tish-oo"],
    ),
    Candidate(
        target="neurodegenerative",
        respellings=["newro-de-JEN-er-uh-tiv"],
    ),
    Candidate(
        target="Alnylam",
        respellings=["Al-nye-lam", "al-NEE-lum"],
    ),
    Candidate(
        target="Roscosmos",
        respellings=["Ross-cosmos", "ross-KOZ-mos"],
    ),
    Candidate(
        target="Teslarati",
        respellings=["Tesla-rah-tee"],
    ),
]


# ---------------------------------------------------------------------------
# Pipeline-map loader (--from-pipeline)
# ---------------------------------------------------------------------------


PRONUNCIATION_MAP_YAML = PROJECT_ROOT / "shows" / "pronunciation_map.yaml"


def _load_pipeline_candidates() -> List[Candidate]:
    """Load every entry currently in the two production pronunciation maps.

    Sources:
      * ``shows/pronunciation_map.yaml`` (``corrections`` dict) — applied at
        TTS-call time by ``engine.tts.prepare_text_for_tts``.
      * ``assets/pronunciation.py:WORD_PRONUNCIATIONS`` — applied at
        script-save time by ``assets.pronunciation.prepare_text_for_tts``.

    Entries are deduplicated by lowercased target — the two maps often
    carry case-variants of the same word (``tissue`` + ``Tissue`` +
    ``tissues`` + ``Tissues``); since Grok TTS pronunciation is case-
    insensitive, testing one representative covers all four. When the
    same target appears in both maps with different respellings, both
    respellings are kept so the sweep compares all options against raw.
    """
    import yaml  # local import; only needed for --from-pipeline

    seen: dict[str, Candidate] = {}

    # Layer 1: YAML map (TTS-call-time overrides)
    if PRONUNCIATION_MAP_YAML.is_file():
        data = yaml.safe_load(PRONUNCIATION_MAP_YAML.read_text(encoding="utf-8")) or {}
        corrections = data.get("corrections") or {}
        for target, respelling in corrections.items():
            key = str(target).strip().lower()
            if not key:
                continue
            c = seen.get(key)
            if c is None:
                seen[key] = Candidate(target=str(target), respellings=[str(respelling)])
            elif str(respelling) not in c.respellings:
                c.respellings.append(str(respelling))

    # Layer 2: WORD_PRONUNCIATIONS dict (script-save-time overrides)
    try:
        from assets.pronunciation import WORD_PRONUNCIATIONS
    except Exception:  # pragma: no cover — defensive
        WORD_PRONUNCIATIONS = {}
    for target, respelling in WORD_PRONUNCIATIONS.items():
        key = str(target).strip().lower()
        if not key:
            continue
        c = seen.get(key)
        if c is None:
            seen[key] = Candidate(target=str(target), respellings=[str(respelling)])
        elif str(respelling) not in c.respellings:
            c.respellings.append(str(respelling))

    return list(seen.values())


# ---------------------------------------------------------------------------
# TTS + Whisper helpers
# ---------------------------------------------------------------------------


def _synthesize(text: str, out_path: Path) -> None:
    """Generate audio via Grok TTS using the same defaults as production.

    Uses the project's ``grok_speak_chunk`` so behavior matches what listeners
    hear. WAV @ 48 kHz, text_normalization=True (matching production).
    """
    from engine.tts import grok_speak_chunk

    api_key = (
        os.getenv("GROK_API_KEY")
        or os.getenv("XAI_API_KEY", "")
    ).strip()
    if not api_key:
        raise RuntimeError(
            "GROK_API_KEY (or XAI_API_KEY) must be set in env to run pronunciation calibration."
        )

    # Wrap the test word in a short carrier phrase so Grok generates a
    # natural-prosody sample (a bare one-word utterance can produce odd
    # results because there's no surrounding context). The transcript
    # comparison then strips the carrier.
    sample = f"The word is {text}, that's correct."

    grok_speak_chunk(
        sample,
        voice_id="kdif6sqjcyiq",  # English custom voice (production default)
        out_path=out_path,
        api_key=api_key,
        language_code="en",
        output_codec="wav",
        output_sample_rate=48000,
        text_normalization=True,
    )


def _transcribe(audio_path: Path) -> str:
    """Run faster-whisper over the audio and return the joined transcript."""
    from faster_whisper import WhisperModel

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(audio_path), language="en")
    text = " ".join(s.text.strip() for s in segments).strip()
    return text


def _extract_word_under_test(transcript: str) -> str:
    """Pull the word from the ``The word is X, that's correct.`` carrier.

    Falls back to the full transcript if the carrier pattern is missing
    (Whisper occasionally drops or reorders the framing words).
    """
    m = re.search(
        r"(?:[Tt]he word is)\s+(.*?)[,\.\s]+(?:that['’]?s|correct)",
        transcript,
    )
    if m:
        return m.group(1).strip().rstrip(",.").strip()
    return transcript


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _normalize(s: str) -> str:
    """Lowercase + strip non-alnum so we compare phoneme-shape, not casing."""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _similarity(a: str, b: str) -> float:
    """Return a 0..1 similarity score between two normalized strings."""
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


# ---------------------------------------------------------------------------
# Top-level evaluate
# ---------------------------------------------------------------------------


@dataclass
class Result:
    target: str
    sent_text: str       # raw or respelling
    is_raw: bool
    transcript_full: str
    transcript_word: str
    score: float


def evaluate_candidate(c: Candidate, work_dir: Path) -> List[Result]:
    results: List[Result] = []

    # Always test the raw target first — gives us the baseline.
    inputs: List[Tuple[str, bool]] = [(c.target, True)]
    for r in c.respellings:
        inputs.append((r, False))

    for idx, (sent, is_raw) in enumerate(inputs):
        slug = re.sub(r"[^a-z0-9]+", "_", sent.lower()).strip("_")[:40]
        audio = work_dir / f"{_normalize(c.target)}__{idx:02d}_{slug}.wav"
        logger.info("  generating audio for %r ...", sent)
        _synthesize(sent, audio)
        transcript = _transcribe(audio)
        word = _extract_word_under_test(transcript)
        score = _similarity(c.target, word)
        results.append(Result(
            target=c.target,
            sent_text=sent,
            is_raw=is_raw,
            transcript_full=transcript,
            transcript_word=word,
            score=score,
        ))
    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _format_table(results: List[Result]) -> str:
    if not results:
        return "(no results)"
    headers = ["TARGET", "INPUT", "TRANSCRIBED-AS", "SCORE", "VERDICT"]
    rows: List[List[str]] = []
    # Group by target so we can compare raw vs. respellings within each block.
    by_target: dict[str, List[Result]] = {}
    for r in results:
        by_target.setdefault(r.target, []).append(r)

    for target, group in by_target.items():
        # Sort: raw first, then respellings in original order
        group.sort(key=lambda r: (not r.is_raw,))
        raw_score = next((r.score for r in group if r.is_raw), 0.0)
        for r in group:
            tag = "raw" if r.is_raw else "respell"
            if r.is_raw:
                verdict = "baseline" if r.score >= 0.85 else "BAD"
            else:
                delta = r.score - raw_score
                if abs(delta) < 0.05:
                    verdict = "≈ raw"
                elif delta > 0:
                    verdict = f"+{delta:.2f} better"
                else:
                    verdict = f"{delta:.2f} WORSE"
            rows.append([
                target,
                f"[{tag}] {r.sent_text!r}",
                r.transcript_word[:50],
                f"{r.score:.2f}",
                verdict,
            ])
        rows.append(["", "", "", "", ""])  # blank separator

    # Column widths
    widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    lines: List[str] = []
    lines.append("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    lines.append("  ".join("-" * widths[i] for i in range(len(headers))))
    for r in rows:
        lines.append("  ".join(r[i].ljust(widths[i]) for i in range(len(headers))))
    return "\n".join(lines)


def _format_markdown(results: List[Result]) -> str:
    by_target: dict[str, List[Result]] = {}
    for r in results:
        by_target.setdefault(r.target, []).append(r)

    md: List[str] = []
    md.append("# Pronunciation calibration")
    md.append("")
    md.append("Per-word comparison of Grok TTS rendering with the raw spelling vs. each respelling.")
    md.append("Higher score = Whisper transcribed the audio closer to the target word.")
    md.append("")
    md.append("| Target | Input | Transcribed as | Score | Verdict |")
    md.append("|---|---|---|---|---|")
    for target, group in by_target.items():
        group.sort(key=lambda r: (not r.is_raw,))
        raw_score = next((r.score for r in group if r.is_raw), 0.0)
        for r in group:
            tag = "raw" if r.is_raw else "respell"
            if r.is_raw:
                verdict = "baseline" if r.score >= 0.85 else "**BAD**"
            else:
                delta = r.score - raw_score
                if abs(delta) < 0.05:
                    verdict = "≈ raw"
                elif delta > 0:
                    verdict = f"+{delta:.2f} **better**"
                else:
                    verdict = f"{delta:.2f} **WORSE**"
            md.append(
                f"| `{target}` | [{tag}] `{r.sent_text}` "
                f"| `{r.transcript_word[:60]}` | {r.score:.2f} | {verdict} |"
            )
    return "\n".join(md)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--word",
        help="Test a specific word (defaults to the baked-in candidate list).",
    )
    parser.add_argument(
        "--respelling",
        action="append",
        default=[],
        help="Extra respelling to test alongside the existing ones. Use multiple times for multiple candidates.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Test every candidate in the baked-in list.",
    )
    parser.add_argument(
        "--from-pipeline",
        action="store_true",
        help=(
            "Sweep every entry currently in shows/pronunciation_map.yaml "
            "+ assets/pronunciation.py:WORD_PRONUNCIATIONS. Use to "
            "calibrate which overrides still earn their keep."
        ),
    )
    parser.add_argument(
        "--report",
        help="Write a markdown report to this path (in addition to the table on stdout).",
    )
    args = parser.parse_args(argv)

    if not args.word and not args.all and not args.from_pipeline:
        print(
            "Pass --word <name>, --all, or --from-pipeline.",
            file=sys.stderr,
        )
        return 2

    if args.word:
        existing = next(
            (c for c in DEFAULT_CANDIDATES if c.target.lower() == args.word.lower()),
            None,
        )
        if existing is None:
            existing = Candidate(target=args.word, respellings=[])
        if args.respelling:
            existing = Candidate(
                target=existing.target,
                respellings=existing.respellings + args.respelling,
            )
        targets = [existing]
    elif args.from_pipeline:
        targets = _load_pipeline_candidates()
        logger.info(
            "Loaded %d candidates from production pronunciation maps.",
            len(targets),
        )
    else:
        targets = DEFAULT_CANDIDATES

    with tempfile.TemporaryDirectory(prefix="pronunciation_test_") as tmp_str:
        work_dir = Path(tmp_str)
        all_results: List[Result] = []
        for c in targets:
            logger.info("Testing %s (raw + %d respelling(s))",
                        c.target, len(c.respellings))
            all_results.extend(evaluate_candidate(c, work_dir))

    print()
    print(_format_table(all_results))
    print()

    if args.report:
        Path(args.report).write_text(_format_markdown(all_results), encoding="utf-8")
        print(f"Markdown report written to {args.report}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
