#!/usr/bin/env python3
"""Probe the network's audio chain on fresh Grok audio. Read-only.

Two modes, one script:

**The fixture passage (Oct 29 2026; no arguments).** The operator heard hiss
and clicks on Nerra Daily, on Mira's links and on the first show. Measured
on Ep070: every join of the edition was an MP3 stream copy (~39 ms of
encoder padding and a hard step: a click per handoff); Mira's pieces were
loudness-normalized only (11 clicks in a 35 s intro, a hissier pause floor
than any show's); and a spliced story pause was digital zero, so a show's
hiss switched off and on at every story change. Those three are fixed in
code. This mode runs each stage, old and new, on one fixed passage
synthesized here (not on published files that already carry the old
processing), prints the numbers, and leaves the files in ``probe_out/`` for
the workflow to attach, because the listen is the decision.

**A real minute of a committed script (Nov 3 2026, listen before the
slate).** The fixture passage is 900 characters of made-up council news; it
cannot tell the operator what a chain change does to Tesla's numbers, to
Mira's pace or to a DP Pod exchange. ::

    python scripts/probe_audio_chain.py --script digests/<dir>/<ep>_tts.txt \\
        --seconds 75 --variants legacy,glue [--voice <id>] [--dialogue] [--dry-run]

synthesizes the FIRST ``--seconds`` of a committed ``*_tts.txt`` — the exact
text the episode spoke — on the show's voice (about 1,200 characters for
75 s, a couple of cents of TTS), then renders every named chain variant
through the REAL builders: ``engine.audio.master_voice_track`` for the
voice-only finish and ``engine.audio.mix_with_music`` with the show's own
theme and the show's own ``audio:`` settings, exactly as ``run_show`` calls
them. Nothing here hand-rolls a filter string: a variant is a set of
keyword arguments for those builders, and a name the builders on this tree
do not accept is reported and skipped, never approximated. ``--dialogue``
(automatic for a ``tts.dialogue_mode`` show) renders the exchange through
``engine.tts_dialogue.synthesize_dialogue`` at every speed in
``DIALOGUE_SPEEDS`` — the DP Pod's open question. ``--dry-run`` needs no
API key: it records the ffmpeg commands the builders would issue for the
show's theme and prints them.

Per output file: clicks (isolated impulses), pause floor and pause hiss
(4-16 kHz), digital-silence frames, peak, and since Nov 3 integrated
loudness / range / true peak from ``engine.audio.measure_loudness``.
Nothing is published and nothing is written under ``digests/`` or the
feeds: every file lands in ``--out`` (``probe_out/`` by default). Needs
GROK_API_KEY (or XAI_API_KEY) unless ``--dry-run``.
"""
from __future__ import annotations

import argparse
import contextlib
import inspect
import json
import os
import shlex
import subprocess
import sys
import types
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

import yaml

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

#: Characters of a committed ``*_tts.txt`` per second of the shipped audio,
#: measured Nov 3 2026 on the last three episodes of six shows
#: (``len(_tts.txt) / counters.audio_duration_s``): Patrick's voice 15.3-16.0
#: (Tesla, SpaceX, Models & Agents), Mira 16.5-18.1 (Vancouver, Top World),
#: the DP Pod at speed 1.05 17.8. The lower figure, so ``--seconds`` buys at
#: least that much voice on the slowest reader.
CHARS_PER_SECOND = 16.0

#: The speeds a ``--dialogue`` probe renders: the documented default and the
#: DP Pod's shipped ``tts.speed`` (shows/dp_pod.yaml), the operator's open
#: question from the Oct 2026 listens.
DIALOGUE_SPEEDS = (1.0, 1.05)

#: Named chain variants: each is keyword arguments for the real builders
#: (``voice_chain_filters`` / ``master_voice_track`` / ``mix_with_music``),
#: layered over the show's own ``audio.voice_denoise`` / ``voice_declick``.
#: ``legacy`` is the chain as it ships. A name whose arguments the builders
#: on this tree do not accept (``glue`` until the dynamics change lands in
#: ``engine/audio.py``) is reported as unavailable and skipped — the probe
#: never approximates a chain the engine does not own.
VARIANTS: Dict[str, Dict[str, object]] = {
    "legacy": {},
    "no_denoise": {"denoise": False},
    "strong_declick": {"declick": "strong"},
    "glue": {"dynamics": "glue"},
}


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


def measure_with_loudness(path: Path) -> dict:
    """``measure`` plus the Nov 3 loudness reader (I / LRA / TP), or nulls."""
    from engine.audio import measure_loudness

    row = measure(path)
    loud = measure_loudness(path) or {}
    row["integrated_lufs"] = loud.get("I")
    row["loudness_range_lu"] = loud.get("LRA")
    row["true_peak_dbtp"] = loud.get("TP")
    return row


# --------------------------------------------------------- script mode --
def clip_script(text: str, seconds: float) -> str:
    """The first ``seconds`` of a committed TTS script, cut at a boundary.

    The budget is ``seconds * CHARS_PER_SECOND`` characters. The cut lands on
    the last paragraph boundary inside the budget (for a dialogue script a
    paragraph is a turn, so no speaker is cut mid-line); with no paragraph
    boundary inside it, on the last sentence end; never mid-word. The first
    paragraph always ships whole, so a short budget never yields nothing.
    """
    text = text.strip()
    budget = max(1, int(seconds * CHARS_PER_SECOND))
    if len(text) <= budget:
        return text
    head = text[:budget]
    cut = head.rfind("\n\n")
    if cut <= 0:
        for mark in (". ", "? ", "! ", ".\n", "?\n", "!\n"):
            cut = max(cut, head.rfind(mark) + len(mark) - 1)
    if cut <= 0:
        cut = head.rfind(" ")
    if cut <= 0:
        cut = text.find("\n\n")
        if cut <= 0:
            cut = len(text)
    return text[:cut].rstrip()


def show_for_script(script: Path):
    """The show whose ``episode.output_dir`` holds ``script`` — slug and
    its loaded ``ShowConfig`` (so the probe renders with the show's own
    voice, theme and ``audio:`` values, never a guessed set).
    """
    from engine.config import load_config

    script = script.resolve()
    try:
        rel_dir = script.parent.relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise SystemExit(f"--script must point inside the repository: {script}") from exc
    for yaml_path in sorted((ROOT / "shows").glob("*.yaml")):
        if yaml_path.name.startswith("_"):
            continue
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        out_dir = str(((raw.get("episode") or {}).get("output_dir")) or "").strip("/")
        if out_dir and out_dir == rel_dir:
            return yaml_path.stem, load_config(yaml_path)
    raise SystemExit(f"No show in shows/*.yaml owns {rel_dir} (episode.output_dir)")


def mix_kwargs(config) -> dict:
    """The keyword arguments ``run_show`` hands ``mix_with_music`` for this
    show, read from the same config object (one set of values, two callers)."""
    a = config.audio
    bg = None
    if a.background_music_file:
        bg = ROOT / a.background_music_file
    return {
        "intro_duration": int(a.intro_duration),
        "overlap_duration": int(a.overlap_duration),
        "fade_duration": int(a.fade_duration),
        "outro_duration": int(a.outro_duration),
        "intro_volume": a.intro_volume,
        "overlap_volume": a.overlap_volume,
        "fade_volume": a.fade_volume,
        "outro_volume": a.outro_volume,
        "voice_intro_delay": a.voice_intro_delay,
        "background_music_path": bg,
        "outro_crossfade": a.outro_crossfade,
        "outro_fade_out_duration": getattr(a, "outro_fade_out_duration", 6.0),
    }


def resolve_variants(names: List[str], config) -> List[Tuple[str, Optional[dict], str]]:
    """Each requested name as ``(name, builder_kwargs | None, note)``.

    ``builder_kwargs`` is the show's own denoise / declick with the variant's
    arguments layered on top, and it is ``None`` when any of those arguments
    is not a parameter of EVERY real builder on this tree (the note says
    which) — a chain the engine does not own is never rendered.
    """
    from engine import audio as _audio

    builders = {
        "voice_chain_filters": _audio.voice_chain_filters,
        "master_voice_track": _audio.master_voice_track,
        "mix_with_music": _audio.mix_with_music,
    }
    base = {"denoise": config.audio.voice_denoise, "declick": config.audio.voice_declick}
    out = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        if name not in VARIANTS:
            out.append((name, None, f"unknown variant; known: {', '.join(VARIANTS)}"))
            continue
        kwargs = {**base, **VARIANTS[name]}
        missing = []
        for builder_name, fn in builders.items():
            params = inspect.signature(fn).parameters
            for key in VARIANTS[name]:
                if key not in params:
                    missing.append(f"{builder_name} has no `{key}`")
        if missing:
            out.append((name, None, "not a chain engine.audio offers on this tree: "
                        + "; ".join(missing)))
            continue
        out.append((name, kwargs, _audio.voice_chain_filters(**kwargs)))
    return out


@contextlib.contextmanager
def recording_builders(seconds: float) -> Iterator[List[list]]:
    """Run the real builders without ffmpeg: ``engine.audio``'s subprocess
    is swapped for a recorder for the duration (nothing outside that module
    sees it) and the duration reader answers ``seconds``. Yields the list
    the recorded commands land in."""
    from engine import audio as _audio

    recorded: List[list] = []

    def _record(cmd, *args, **kwargs):
        recorded.append([str(c) for c in cmd])
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    shim = types.SimpleNamespace(run=_record, CalledProcessError=subprocess.CalledProcessError,
                                 TimeoutExpired=subprocess.TimeoutExpired)
    real_subprocess, real_duration = _audio.subprocess, _audio.get_audio_duration
    _audio.subprocess = shim
    _audio.get_audio_duration = lambda p, *a, **k: float(seconds)
    try:
        yield recorded
    finally:
        _audio.subprocess = real_subprocess
        _audio.get_audio_duration = real_duration


def render_variant(raw: Path, label: str, kwargs: dict, config, out: Path) -> List[Path]:
    """One variant through the real builders, as ``run_show`` mixes an
    episode: the voice-only finish (PCM, the translated tracks' and the
    no-music shows' path) and, when the show has a theme, the full mix."""
    from engine.audio import master_voice_track, mix_with_music

    produced = [master_voice_track(raw, out / f"{label}_voice.wav", **kwargs)]
    theme = ROOT / config.audio.music_file if config.audio.music_file else None
    if theme is not None and theme.exists():
        produced.append(mix_with_music(raw, theme, out / f"{label}_mix.mp3",
                                       **mix_kwargs(config), **kwargs))
    return produced


def _synthesize_clip(clip: str, config, voice: str, label: str, out: Path, key: str,
                     *, speed: float) -> Path:
    from engine.tts import synthesize

    raw = out / f"{label}_raw.mp3"
    synthesize(
        clip, voice, raw, api_key=key, provider=config.tts.provider,
        max_chars=config.tts.max_chars, language_code=config.tts.language_code,
        speed=speed, apply_text_normalization=config.tts.apply_text_normalization,
        speech_wrap_open=config.tts.speech_wrap_open,
        speech_wrap_close=config.tts.speech_wrap_close,
    )
    return raw


def _synthesize_dialogue_clip(clip: str, config, label: str, out: Path, key: str,
                              *, speed: float) -> Path:
    from engine.tts_dialogue import synthesize_dialogue

    raw = out / f"{label}_raw.mp3"
    synthesize_dialogue(
        clip, dict(config.tts.dialogue_voices), raw, api_key=key,
        max_chars=config.tts.max_chars, language_code=config.tts.language_code,
        pause_ms=config.tts.dialogue_pause_ms, speed=speed,
    )
    return raw


def probe_script(args) -> int:
    from engine.tracking import GROK_TTS_COST_PER_1K_CHARS

    script = Path(args.script)
    if not script.exists():
        print(f"--script not found: {script}", file=sys.stderr)
        return 1
    slug, config = show_for_script(script)
    dialogue = bool(args.dialogue or config.tts.dialogue_mode)
    clip = clip_script(script.read_text(encoding="utf-8"), args.seconds)
    voice = args.voice or config.tts.voice_id
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    variants = resolve_variants(args.variants.split(","), config)
    theme = ROOT / config.audio.music_file if config.audio.music_file else None

    plan = {
        "show": slug,
        "script": script.resolve().relative_to(ROOT).as_posix(),
        "seconds_requested": args.seconds,
        "clip_chars": len(clip),
        "clip_estimated_seconds": round(len(clip) / CHARS_PER_SECOND, 1),
        "tts_cost_usd_estimate": round(len(clip) / 1000 * GROK_TTS_COST_PER_1K_CHARS
                                       * (len(DIALOGUE_SPEEDS) if dialogue else 1), 4),
        "voice": "dialogue:" + ",".join(f"{k}={v}" for k, v in config.tts.dialogue_voices.items())
                 if dialogue else voice,
        "dialogue_speeds": list(DIALOGUE_SPEEDS) if dialogue else [config.tts.speed],
        "theme": theme.relative_to(ROOT).as_posix() if theme and theme.exists() else None,
        "out": str(out),
        "variants": [{"name": n, "available": kw is not None, "chain": note if kw else None,
                      "note": None if kw else note} for n, kw, note in variants],
        "dry_run": bool(args.dry_run),
    }
    print(json.dumps(plan, indent=2))
    (out / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    (out / "clip.txt").write_text(clip, encoding="utf-8")
    available = [(n, kw) for n, kw, _ in variants if kw is not None]
    if not available:
        print("No requested variant is available on this tree — nothing to render.",
              file=sys.stderr)
        return 1

    speeds = DIALOGUE_SPEEDS if dialogue else (config.tts.speed,)
    if args.dry_run:
        placeholder = out / "dry_run_voice.mp3"
        placeholder.write_bytes(b"\0")
        try:
            for speed in speeds:
                for name, kwargs in available:
                    label = f"s{int(round(speed * 100)):03d}_{name}" if dialogue else name
                    with recording_builders(plan["clip_estimated_seconds"]) as recorded:
                        render_variant(placeholder, label, kwargs, config, out)
                    print(f"\n# {label}: {len(recorded)} ffmpeg command(s) the real builders "
                          f"would issue")
                    for cmd in recorded:
                        print(shlex.join(cmd))
        finally:
            placeholder.unlink(missing_ok=True)
        print("\nDry run: nothing synthesized, nothing rendered.")
        return 0

    key = os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or ""
    if not key:
        print("GROK_API_KEY / XAI_API_KEY required (or --dry-run)", file=sys.stderr)
        return 1
    rendered: List[Path] = []
    for speed in speeds:
        base_label = f"s{int(round(speed * 100)):03d}" if dialogue else "voice"
        if dialogue:
            raw = _synthesize_dialogue_clip(clip, config, base_label, out, key, speed=speed)
        else:
            raw = _synthesize_clip(clip, config, voice, base_label, out, key, speed=speed)
        rendered.append(raw)
        for name, kwargs in available:
            label = f"{base_label}_{name}" if dialogue else name
            rendered.extend(render_variant(raw, label, kwargs, config, out))
    rows = [measure_with_loudness(p) for p in rendered]
    for row in rows:
        print(json.dumps(row))
    (out / "measurements.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return 0


# -------------------------------------------------------- fixture mode --
def probe_fixture() -> int:
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--script", default="",
                   help="a committed digests/<dir>/<ep>_tts.txt; without it the Oct 29 "
                        "fixture passage runs")
    p.add_argument("--seconds", type=float, default=75.0,
                   help="how much of the script to voice (default 75)")
    p.add_argument("--variants", default="legacy",
                   help=f"comma-separated chain variants; known: {', '.join(VARIANTS)}")
    p.add_argument("--voice", default="", help="Grok voice id (default: the show's tts.voice_id)")
    p.add_argument("--dialogue", action="store_true",
                   help="render through synthesize_dialogue at every DIALOGUE_SPEEDS "
                        "(automatic for a tts.dialogue_mode show)")
    p.add_argument("--dry-run", action="store_true",
                   help="no API key, no ffmpeg: print the commands the real builders would issue")
    p.add_argument("--out", default=str(OUT), help="output directory (default probe_out/)")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.script:
        return probe_script(args)
    return probe_fixture()


if __name__ == "__main__":
    raise SystemExit(main())
