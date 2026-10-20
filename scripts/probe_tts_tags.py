#!/usr/bin/env python3
"""Probe Grok TTS speech tags at a story boundary (Oct 20 2026). Read-only.

Why: the network marks a story change with the voice now (engine/story_tags.py)
instead of a longer pause or a music swell. The opener tag ``[breath]`` is in
the sanctioned set; which LANDING tag to wrap around a story's last sentence
is not known for this voice — xAI's own tag tables did not render for us, the
code's list (from the docs as read in May) says ``<low>``, Telnyx's reference
says ``<lower-pitch>``, and an unknown tag is spoken aloud (M&A Ep045 "Fast.",
UC Ep001 "Build intensity."). So this asks the voice directly.

For one fixed two-story snippet it synthesises each variant below through the
production request (the custom voice, the ``<fast>`` wrap, text
normalisation on), then prints for each: the pause at the boundary, the
pitch of the last 0.4 s of story one against the 2 s before it (the landing),
the pitch of the first 1.2 s of story two against the 1.2 s before the gap
(the lift), and the Whisper transcript of the boundary region so a spoken
tag word is visible. The WAVs are left in ``probe_out/`` for the workflow to
attach as artifacts — the listen is the decision, the numbers say where to
listen. Nothing is published. Needs GROK_API_KEY (or XAI_API_KEY).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

VOICE = os.getenv("PROBE_VOICE_ID", "kdif6sqjcyiq")
OUT = Path(os.getenv("PROBE_OUT_DIR", "probe_out"))
WRAP_OPEN, WRAP_CLOSE = "<fast>", "</fast>"

STORY_ONE = (
    "The city council voted seven to two to extend the pilot for another year. "
    "Ridership on the two routes rose by a third after the fares were dropped, "
    "and the transit agency says the lost fare revenue was smaller than the "
    "cost of collecting it. The extension runs through next September."
)
STORY_TWO = (
    "A regional airline will add direct flights between the two cities from "
    "January. The route was last served nine years ago, and the airline says it "
    "will start with four flights a week on a seventy-six seat aircraft."
)

LAST_SENTENCE = "The extension runs through next September."


def _variant(close_tag: str = "", open_tag: str = "") -> str:
    """Story one, optionally with its last sentence wrapped in *close_tag*
    (a bare tag name), a paragraph break, then story two optionally opened
    by *open_tag* — the exact shape engine/story_tags.py produces."""
    one = STORY_ONE
    if close_tag:
        one = one.replace(LAST_SENTENCE, f"<{close_tag}>{LAST_SENTENCE}</{close_tag}>")
    two = f"{open_tag} {STORY_TWO}" if open_tag else STORY_TWO
    return f"{one}\n\n{two}"


VARIANTS = {
    "A_plain": _variant(),
    "B_breath": _variant(open_tag="[breath]"),
    "C_low_breath": _variant("low", "[breath]"),
    "D_lowerpitch_breath": _variant("lower-pitch", "[breath]"),
    "E_soft_breath": _variant("soft", "[breath]"),
    "F_longpause": _variant(open_tag="[long-pause]"),
}


def _load(path: Path, sr: int = 16000):
    import numpy as np
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32), sr


def _f0_track(x, sr, fmin=70, fmax=320, win=0.04, hop=0.01):
    import numpy as np
    n = int(win * sr)
    h = int(hop * sr)
    lo = int(sr / fmax)
    hi = int(sr / fmin)
    out = []
    for s in range(0, len(x) - n, h):
        fr = x[s:s + n]
        if float(np.sqrt(np.mean(fr ** 2))) < 0.01:
            out.append(0.0)
            continue
        fr = fr - fr.mean()
        ac = np.correlate(fr, fr, "full")[n - 1:]
        ac = ac / (ac[0] + 1e-9)
        seg = ac[lo:hi]
        k = int(np.argmax(seg)) + lo
        out.append(sr / k if float(seg.max()) > 0.5 else 0.0)
    return np.array(out), hop


def _median_f0(f0, hop, t0, dur):
    import numpy as np
    v = f0[int(max(t0, 0) / hop): int((t0 + dur) / hop)]
    v = v[v > 0]
    return float(np.median(v)) if len(v) else None


def _pauses(x, sr, min_s=0.25):
    import numpy as np
    h = int(0.01 * sr)
    env = np.array([np.sqrt(np.mean(x[i:i + h] ** 2)) for i in range(0, len(x) - h, h)])
    db = 20 * np.log10(env + 1e-9)
    thr = float(np.percentile(db[db > -80], 50)) - 25
    quiet = db < thr
    out = []
    i = 0
    while i < len(quiet):
        if quiet[i]:
            j = i
            while j < len(quiet) and quiet[j]:
                j += 1
            if (j - i) * 0.01 >= min_s:
                out.append((i * 0.01, (j - i) * 0.01))
            i = j
        else:
            i += 1
    return out


def _transcribe(path: Path) -> str:
    try:
        from faster_whisper import WhisperModel
        from engine.transcripts import load_whisper_audio
    except Exception as exc:  # noqa: BLE001
        return f"(no whisper: {exc})"
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(load_whisper_audio(path), beam_size=1)
    return " ".join(s.text.strip() for s in segments)


def main() -> int:
    key = os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
    if not key:
        print("::error::GROK_API_KEY / XAI_API_KEY not set")
        return 2
    from engine.tts import grok_speak_chunk
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    # The boundary is the gap after "September." — find it from the longest pause
    # in the middle third, which is where the only paragraph break sits.
    for name, text in VARIANTS.items():
        wav = OUT / f"{name}.wav"
        grok_speak_chunk(f"{WRAP_OPEN}{text}{WRAP_CLOSE}", VOICE, wav, api_key=key,
                         language_code="en", text_normalization=True)
        x, sr = _load(wav)
        dur = len(x) / sr
        f0, hop = _f0_track(x, sr)
        mid = [p for p in _pauses(x, sr) if dur * 0.3 < p[0] < dur * 0.8]
        if not mid:
            report[name] = {"error": "no pause found", "duration_s": round(dur, 2)}
            print(f"{name}: no boundary pause found in {dur:.1f}s")
            continue
        p0, plen = max(mid, key=lambda p: p[1])
        land = _median_f0(f0, hop, p0 - 0.4, 0.4)
        prior = _median_f0(f0, hop, p0 - 2.4, 2.0)
        lift = _median_f0(f0, hop, p0 + plen, 1.2)
        pre = _median_f0(f0, hop, p0 - 1.2, 1.2)
        clip = OUT / f"{name}_boundary.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(p0 - 4, 0):.2f}", "-t", "9",
                        "-i", str(wav), str(clip)], check=True)
        words = _transcribe(clip)
        spoken_tag = bool(re.search(r"\b(low|lower pitch|higher pitch|soft|breath|long pause|fast)\b[.,]?\s*(?:[A-Z]|$)", words))
        row = {
            "duration_s": round(dur, 2), "boundary_pause_s": round(plen, 2),
            "landing_hz": None if land is None or prior is None else round(land - prior, 1),
            "lift_hz": None if lift is None or pre is None else round(lift - pre, 1),
            "boundary_transcript": words, "tag_word_suspected": spoken_tag,
        }
        report[name] = row
        print(f"{name}: pause {plen:.2f}s | landing {row['landing_hz']} Hz | lift {row['lift_hz']} Hz | "
              f"tag spoken? {spoken_tag}\n    {words}")
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nReading rule: a variant whose boundary transcript carries the tag word is OUT. Among the "
          "rest, the one with the most negative landing and the largest lift is the candidate for "
          "tts.story_tag_close — and the listen decides.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
