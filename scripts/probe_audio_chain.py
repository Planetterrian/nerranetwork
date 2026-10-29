#!/usr/bin/env python3
"""Probe the network's audio chain on fresh Grok audio (Oct 29 2026). Read-only.

Why: the operator heard hiss and clicks on Nerra Daily, on Mira's links and on
the first show. Measured on Ep070: every join of the edition was an MP3
stream copy (~39 ms of encoder padding and a hard step: a click per
handoff); Mira's pieces were loudness-normalized only (11 clicks in a 35 s
intro, a hissier pause floor than any show's); and a spliced story pause
was digital zero, so a show's hiss switched off and on at every story
change. Those three are fixed in code. This probe runs each stage, old and
new, on audio synthesized here (not on published files that already carry
the old processing), prints the numbers, and leaves the files in
``probe_out/`` for the workflow to attach, because the listen is the
decision.

For one fixed passage it synthesizes the show voice (the custom voice with
the production ``<fast>`` wrap) and Mira (``ara``) as WAV, then:

* ``mira_old`` / ``mira_new`` — her piece before and after
  (``mira_piece_cmd``: the shows' voice chain, lossless);
* ``show_chain`` and ``show_chain_strong`` — the show voice through the
  network chain, and through a stronger denoise for comparison (NOT
  shipped: it is here so the operator can hear whether it is wanted);
* ``break_zeros`` / ``break_room_tone`` — a story pause spliced as digital
  silence and as the voice's own room tone, each through the chain;
* ``join_old`` / ``join_new`` — Mira, the show, Mira, joined by stream copy
  and by ``engine.audio.concatenate_audio``.

Per file: clicks (isolated impulses), pause floor and pause hiss (4-16 kHz),
digital-silence frames, peak. Nothing is published. Needs GROK_API_KEY (or
XAI_API_KEY).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SHOW_VOICE = os.getenv("PROBE_VOICE_ID", "kdif6sqjcyiq")
MIRA_VOICE = "ara"
OUT = Path(os.getenv("PROBE_OUT_DIR", "probe_out"))
SR = 44100

SHOW_TEXT = (
    "The city council voted seven to two to extend the pilot for another year. "
    "Ridership on the two routes rose by a third after the fares were dropped, "
    "and the transit agency says the lost fare revenue was smaller than the "
    "cost of collecting it. The extension runs through next September.\n\n"
    "A regional airline will add direct flights between the two cities from "
    "January. The route was last served nine years ago, and the airline says it "
    "will start with four flights a week on a seventy-six seat aircraft."
)
MIRA_TEXT = (
    "Good morning. It's Thursday, and this is Nerra Daily. Today we start in "
    "orbit, with a launch that slipped a day and a booster that flew for the "
    "thirtieth time, then we come back down to a city council vote and a new "
    "airline route. Here's the first show."
)

STRONG_DENOISE = "afftdn=nr=14:nf=-50:tn=1"


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def _load(path: Path):
    import numpy as np

    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le",
                          "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)


def measure(path: Path) -> dict:
    """The numbers the Oct 29 review read off Nerra Daily Ep070."""
    import numpy as np

    x = _load(path)
    m = x.mean(axis=1).astype(np.float64)
    e = np.abs(m[2:] - 2 * m[1:-1] + m[:-2])
    blk = int(0.02 * SR)
    nb = len(e) // blk
    clicks = 0
    times: list = []
    if nb >= 3:
        med = np.median(e[: nb * blk].reshape(nb, blk), axis=1) + 1e-6
        nbr = np.maximum(np.r_[med[0], med[:-1]], np.r_[med[1:], med[-1]])
        lvl = np.repeat(np.maximum(med, nbr), blk)
        hit = np.where((e[: nb * blk] > 60 * lvl) & (e[: nb * blk] > 0.02))[0]
        last = -10 ** 9
        for i in hit:
            if i - last > int(0.005 * SR):
                clicks += 1
                times.append(round((i + 1) / SR, 3))
            last = i
    n = int(0.02 * SR)
    k = len(m) // n
    frames = m[: k * n].reshape(k, n)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-12)
    speech = db[db > -45]
    ref = float(np.median(speech)) if len(speech) else -20.0
    pause = (db < ref - 30) & (db > -100)
    hiss = None
    if pause.any():
        spec = np.abs(np.fft.rfft(frames[pause] * np.hanning(n), axis=1)) ** 2
        freqs = np.fft.rfftfreq(n, 1 / SR)
        sel = (freqs >= 4000) & (freqs < 16000)
        hiss = round(float(np.median(10 * np.log10(spec[:, sel].sum(axis=1) / n + 1e-20))), 1)
    return {
        "file": path.name,
        "seconds": round(len(m) / SR, 2),
        "clicks": clicks,
        "click_times": times[:20],
        "pause_floor_db": round(float(np.median(db[pause])), 1) if pause.any() else None,
        "pause_hiss_4_16k_db": hiss,
        "digital_silence_frames": int((db <= -100).sum()),
        "peak": round(float(np.abs(x).max()), 3),
    }


def main() -> int:
    from engine import story_breaks as sb
    from engine.audio import concatenate_audio, voice_chain_filters
    from engine.daily_edition import EDITION_ENCODE_ARGS, mira_piece_cmd
    from engine.tts import synthesize

    key = os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or ""
    if not key:
        print("GROK_API_KEY / XAI_API_KEY required", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    show_raw, mira_raw = OUT / "show_raw.wav", OUT / "mira_raw.wav"
    synthesize(SHOW_TEXT, SHOW_VOICE, show_raw, api_key=key, provider="grok",
               language_code="en", speech_wrap_open="<fast>", speech_wrap_close="</fast>")
    synthesize(MIRA_TEXT, MIRA_VOICE, mira_raw, api_key=key, provider="grok",
               language_code="en")

    q2 = ["-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-q:a", "2"]
    # Mira, before and after.
    _run(["ffmpeg", "-y", "-i", str(mira_raw), "-c:a", "libmp3lame", "-q:a", "0",
          str(OUT / "mira_raw.mp3")])
    _run(["ffmpeg", "-y", "-i", str(OUT / "mira_raw.mp3"), "-af",
          "loudnorm=I=-16:TP=-1.5:LRA=11,adelay=350:all=1,apad=pad_dur=0.45"]
         + q2 + [str(OUT / "mira_old.mp3")])
    _run(mira_piece_cmd(mira_raw, OUT / "mira_new.flac"))
    # Mira stage by stage, to find where a click comes from.
    chain_all = voice_chain_filters()
    for name, af in (
        ("mira_stage_chain", chain_all),
        ("mira_stage_nodenoise", voice_chain_filters(denoise=False)),
        ("mira_stage_chain_loudnorm", chain_all + ",loudnorm=I=-16:TP=-1.5:LRA=11"),
        ("mira_stage_loudnorm_only", "loudnorm=I=-16:TP=-1.5:LRA=11"),
    ):
        _run(["ffmpeg", "-y", "-i", str(mira_raw), "-af", af, str(OUT / f"{name}.wav")])

    # The show voice through the chain, and a stronger denoise to compare.
    chain = voice_chain_filters()
    _run(["ffmpeg", "-y", "-i", str(show_raw), "-af", chain, str(OUT / "show_chain.wav")])
    _run(["ffmpeg", "-y", "-i", str(show_raw), "-af",
          chain.replace("afftdn=nr=9:nf=-42:tn=1", STRONG_DENOISE),
          str(OUT / "show_chain_strong.wav")])

    # A story pause at the paragraph change: zeros vs room tone.
    silences = [s for s in sb.detect_silences(show_raw) if s[1] - s[0] > 0.2]
    if silences:
        widest = max(silences, key=lambda s: s[1] - s[0])
        brk = sb.Break(cut=round(sum(widest) / 2, 3), insert=0.6,
                       gap_start=widest[0], gap_end=widest[1])
        tones = sb.room_tone_spans(show_raw, [brk])
        for name, tone in (("break_zeros", None), ("break_room_tone", tones)):
            spliced = OUT / f"{name}_raw.wav"
            _run(sb.insert_silences_cmd(show_raw, spliced, [brk.cut], [brk.insert],
                                        room_tone=tone))
            _run(["ffmpeg", "-y", "-i", str(spliced), "-af", chain, str(OUT / f"{name}.wav")])
            spliced.unlink(missing_ok=True)

    # Joins: Mira, show, Mira — stream copy of q2 pieces vs the decoded join.
    _run(["ffmpeg", "-y", "-i", str(OUT / "show_chain.wav")] + q2 + [str(OUT / "show_q2.mp3")])
    lst = OUT / "join.txt"
    lst.write_text("".join(f"file '{(OUT / n).resolve()}'\n"
                           for n in ("mira_old.mp3", "show_q2.mp3", "mira_old.mp3")))
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
          str(OUT / "join_old.mp3")])
    lst.unlink(missing_ok=True)
    _run(["ffmpeg", "-y", "-i", str(OUT / "show_chain.wav"), "-ar", "44100", "-ac", "2",
          "-c:a", "flac", str(OUT / "show_piece.flac")])
    concatenate_audio([OUT / "mira_new.flac", OUT / "show_piece.flac", OUT / "mira_new.flac"],
                      OUT / "join_new.mp3", encode_args=EDITION_ENCODE_ARGS)

    rows = [measure(p) for p in sorted(OUT.iterdir())
            if p.suffix in (".wav", ".mp3", ".flac")]
    for row in rows:
        print(json.dumps(row))
    (OUT / "measurements.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
