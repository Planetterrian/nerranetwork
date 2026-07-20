"""Interview-audio polish for episode production (July 2026).

Born from the first produced episode's operator notes: guest bass-heavy and
level-mismatched vs Mira, background noise audible while Mira speaks,
audible filler words and long silences, and Mira's spoken time checks.

Two stages, both applied to the interview track before assembly:

1. ``polish_audio`` — deterministic ffmpeg chain: de-bass + presence EQ,
   gentle noise gate (background between phrases), and program-wide
   dynamic normalization so both speakers sit at comparable levels.
2. ``build_word_cuts`` — Whisper word-timestamp pass (runs in CI where
   compute is free) producing cut windows for: filler words (um/uh/ah…),
   long silences (collapsed, not removed), and spoken time-check phrases
   ("17 minutes elapsed, about 28 minutes remain") that predate the
   silent-time-checks prompt fix.

Cuts are returned in apply_redactions' {start, end, reason} format so the
assembly stage applies guest redactions and polish cuts in one pass.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

FILLERS = {"um", "uh", "uhm", "umm", "ah", "ahh", "er", "erm",
           "hmm", "mhm", "mm", "hm"}
_NUMBERISH = re.compile(
    r"^(\d+|about|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
    r"twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty)$", re.I)

SILENCE_GAP_SEC = 1.8       # gaps longer than this get collapsed…
SILENCE_KEEP_SEC = 0.9      # …down to roughly this much breathing room
MAX_FILLER_SEC = 1.0
MERGE_SLOP_SEC = 0.12


_RNNOISE_MODEL = (Path(__file__).resolve().parents[3]
                  / "assets" / "audio" / "rnnoise_sh.rnnn")


def polish_audio(in_path: Path, out_path: Path) -> Path:
    """Mastering-order chain (v3, first-episode sound-engineering pass).

    July 20 2026: the v1 chain's noise gate produced audible open/close
    ticks and its aggressive dynaudnorm pumped the noise floor up during
    quiet speech — the operator heard both on the produced episode. v3 is
    a proper order: RNN speech denoiser (removes compression hiss RIDING
    the voice, artifact-free — far better than afftdn), declicker for
    impulsive transport ticks, de-esser for harsh call-path sibilance,
    corrective EQ, then gentle 2.5:1 compression for leveling. No gate,
    no dynaudnorm — ever again.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    denoise = (f"arnndn=m={_RNNOISE_MODEL}," if _RNNOISE_MODEL.exists()
               else "afftdn=nf=-24:tn=1,")
    if not _RNNOISE_MODEL.exists():
        logger.warning("rnnoise model missing (%s) — falling back to afftdn",
                       _RNNOISE_MODEL)
    chain = (
        "highpass=f=85,"
        + denoise +
        "adeclick,"
        "deesser,"
        "equalizer=f=130:t=q:w=1.1:g=-3.5,"    # tame boomy guest bass
        "equalizer=f=2800:t=q:w=1.2:g=2.5,"    # vocal presence / clarity
        "acompressor=threshold=-24dB:ratio=2.5:attack=15:release=250:makeup=5,"
        "alimiter=limit=0.95"
    )
    cmd = ["ffmpeg", "-y", "-i", str(in_path), "-af", chain,
           "-ar", "48000", "-ac", "1", str(out_path)]
    logger.info("Polishing interview audio (v3 chain) → %s", out_path.name)
    proc = subprocess.run(cmd, capture_output=True, timeout=3600, text=True)
    if proc.returncode != 0:
        logger.error("polish_audio ffmpeg failed:\n%s", (proc.stderr or "")[-1500:])
        raise RuntimeError("polish_audio failed")
    return out_path


def _transcribe_words(audio: Path, workdir: Path) -> list[dict]:
    from engine.transcripts import generate_transcript
    result = generate_transcript(audio, workdir / "polish_stt", "polish",
                                 model_size="small", language="en")
    if result is None:
        return []
    import json
    data = json.loads(result.json_path.read_text(encoding="utf-8"))
    words: list[dict] = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []) or []:
            token = re.sub(r"[^\w']", "", (w.get("word") or "").lower())
            if token:
                words.append({"w": token, "s": float(w["start"]),
                              "e": float(w["end"])})
    return words


def _time_phrase_cuts(words: list[dict]) -> List[dict]:
    """Cut spoken '[N] minutes elapsed[, about M minutes remain]' phrases."""
    cuts = []
    i = 0
    while i < len(words) - 1:
        if words[i]["w"] in ("minutes", "minute") and \
           words[i + 1]["w"] in ("elapsed", "remain", "remained", "remaining"):
            start_idx = i
            # pull in the leading count ("17", "about", "seventeen")
            while start_idx > 0 and _NUMBERISH.match(words[start_idx - 1]["w"]):
                start_idx -= 1
            end_idx = i + 1
            # swallow a following "about M minutes remain" clause
            j = end_idx + 1
            grabbed = 0
            while j < len(words) and grabbed < 5:
                w = words[j]["w"]
                if _NUMBERISH.match(w) or w in ("minutes", "minute", "remain",
                                                "remained", "remaining"):
                    end_idx = j
                    j += 1
                    grabbed += 1
                else:
                    break
            cuts.append({"start": max(0.0, words[start_idx]["s"] - 0.05),
                         "end": words[end_idx]["e"] + 0.10,
                         "reason": "spoken time check"})
            i = end_idx + 1
        else:
            i += 1
    return cuts


def build_word_cuts(audio: Path, workdir: Path) -> List[dict]:
    words = _transcribe_words(audio, workdir)
    if not words:
        logger.warning("No word timestamps — polish cuts skipped")
        return []

    cuts: List[dict] = []
    for w in words:
        if w["w"] in FILLERS and (w["e"] - w["s"]) <= MAX_FILLER_SEC:
            cuts.append({"start": max(0.0, w["s"] - 0.02),
                         "end": w["e"] + 0.02, "reason": "filler"})
    for a, b in zip(words, words[1:]):
        gap = b["s"] - a["e"]
        if gap > SILENCE_GAP_SEC:
            cuts.append({"start": a["e"] + SILENCE_KEEP_SEC * 0.6,
                         "end": b["s"] - SILENCE_KEEP_SEC * 0.4,
                         "reason": "long silence"})
    cuts += _time_phrase_cuts(words)

    cuts.sort(key=lambda c: c["start"])
    merged: List[dict] = []
    for c in cuts:
        if merged and c["start"] <= merged[-1]["end"] + MERGE_SLOP_SEC:
            merged[-1]["end"] = max(merged[-1]["end"], c["end"])
            merged[-1]["reason"] += "+" + c["reason"]
        else:
            merged.append(dict(c))

    total = sum(c["end"] - c["start"] for c in merged)
    fillers = sum(1 for c in merged if "filler" in c["reason"])
    silences = sum(1 for c in merged if "silence" in c["reason"])
    timechk = sum(1 for c in merged if "time check" in c["reason"])
    logger.info("Polish cuts: %d windows (%.1fs total) — %d filler, "
                "%d silence, %d time-check", len(merged), total,
                fillers, silences, timechk)
    return merged
