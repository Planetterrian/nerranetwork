"""Assemble a finished episode from an edit decision list, and put it up for review.

Why this exists (Sept 12 2026): the Matt Davis and Hogan Shrum episodes both
needed a real edit — a reconnect to bridge, an opening performed to an empty
chair to remove, a host talking over the guest's closing answer to replace
with the guest's own isolated track. Those edits were made by hand outside
the pipeline, which means they could not be reproduced, reviewed, or undone.

An EDL puts the edit in the repo as data:

    pipelines/voices/edl/<slug>.json
      {
        "show": "age_of_ai",
        "interview_id": "...",
        "run_id": "...",
        "narration": "matt_davis_2026_09_10",
        "cuts": [
          {"from": "narration:intro"},
          {"gap": 0.6},
          {"from": "run:guest",  "channel": "mono", "start": 109.7, "end": 1558},
          {"from": "run:mix",    "start": 196,      "end": 1271.6},
          {"gap": 0.6},
          {"from": "narration:outro"}
        ]
      }

``from`` is ``narration:<segment>`` (an R2 narration take), ``run:<name>``
(guest | host | mira | mix | extra_guest:N | extra_host:N, resolved from the
run row) or a literal URL. ``channel`` picks left, right or a mono fold of a
stereo source — the Voximplant per-person recordings are L = that person's
microphone, R = what they heard.

The result is uploaded to R2 and pointed at by the review pages, so gate 1
and gate 2 play the EDITED episode rather than the raw mix.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import requests  # noqa: E402

from common import logger, r2_upload, sb_select, sb_update  # noqa: E402
from shows import get_show  # noqa: E402

EDL_DIR = Path(__file__).parent / "edl"
GENTLE = ("highpass=f=60,"
          "acompressor=threshold=-21dB:ratio=3:attack=20:release=250,"
          "dynaudnorm=f=250:g=15")
LOUDNESS = "loudnorm=I=-16:TP=-1.5:LRA=11"
# Trimming dead air off a narration take belongs in narrate.py, but an EDL
# resolves takes that may have been recorded before that existed (Matt Davis:
# the assembled episode came back 106 seconds longer than the approved edit,
# all of it silence between Mira's paragraphs). Trimming a tight file is a
# no-op, so the assembler does it too rather than trusting its sources.
TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:"
        "start_silence=0.35:detection=rms,"
        "silenceremove=stop_periods=-1:stop_duration=0.35:"
        "stop_threshold=-45dB:detection=rms")
CHANNEL_FILTERS = {
    "left": "pan=mono|c0=c0",
    "right": "pan=mono|c0=c1",
    "mono": "pan=mono|c0=0.5*c0+0.5*c1",
}


def _run_sources(run: dict, show) -> Dict[str, str]:
    log = run.get("grok_session_log") or {}
    out = {
        "guest": run.get("recording_guest_url") or log.get("voximplant_record_url"),
        "host": run.get("recording_host_url"),
        "mira": run.get("recording_mira_url"),
        "mix": log.get("voximplant_mix_record_url"),
    }
    for i, url in enumerate(log.get("extra_guest_record_urls") or []):
        out[f"extra_guest:{i}"] = url
    for i, url in enumerate(log.get("extra_host_record_urls") or []):
        out[f"extra_host:{i}"] = url
    return {k: v for k, v in out.items() if v}


def _resolve(ref: str, run: dict, show, narration_slug: str) -> str:
    if ref.startswith("narration:"):
        if not narration_slug:
            raise SystemExit(f"{ref} needs a top-level \"narration\" slug")
        seg = ref.split(":", 1)[1]
        base = (os.environ.get("R2_PUBLIC_BASE_URL", "")
                or "https://audio.nerranetwork.com").rstrip("/")
        return f"{base}/{show.r2_key('narration', narration_slug, seg + '.mp3')}"
    if ref.startswith("run:"):
        name = ref.split(":", 1)[1]
        sources = _run_sources(run, show)
        if name not in sources:
            raise SystemExit(f"{ref} not on the run row (have: {sorted(sources)})")
        return sources[name]
    if ref.startswith(("http://", "https://")):
        return ref
    raise SystemExit(f"unrecognised source {ref!r}")


def _fetch(url: str, dest: Path, cache: Dict[str, Path]) -> Path:
    if url in cache:
        return cache[url]
    logger.info("fetching %s", url.split("?")[0])
    resp = requests.get(url, timeout=600)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    cache[url] = dest
    return dest


def _piece(cut: dict, src: Path, out: Path) -> Path:
    chain = []
    channel = cut.get("channel")
    if channel:
        if channel not in CHANNEL_FILTERS:
            raise SystemExit(f"channel must be one of {sorted(CHANNEL_FILTERS)}")
        chain.append(CHANNEL_FILTERS[channel])
    # Narration is trimmed by default; a conversation never is, because the
    # pauses in it are the conversation.
    trim = cut.get("trim")
    if trim is None:
        trim = str(cut.get("from", "")).startswith("narration:")
    if trim:
        chain.append(TRIM)
    chain.append(GENTLE)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if cut.get("start") is not None:
        cmd += ["-ss", str(cut["start"])]
    if cut.get("end") is not None:
        cmd += ["-to", str(cut["end"])]
    cmd += ["-i", str(src), "-af", ",".join(chain),
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(out)]
    subprocess.run(cmd, check=True)
    return out


def _silence(seconds: float, out: Path) -> Path:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-t", str(seconds), "-i", "anullsrc=r=48000:cl=mono",
                    "-c:a", "pcm_s16le", str(out)], check=True)
    return out


def _duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def assemble(slug: str) -> dict:
    spec_path = EDL_DIR / f"{slug}.json"
    if not spec_path.exists():
        raise SystemExit(f"no EDL at {spec_path}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    show = get_show(spec.get("show") or "age_of_ai")
    run_id = spec["run_id"]
    runs = sb_select("interview_runs", f"id=eq.{run_id}")
    if not runs:
        raise SystemExit(f"no interview_runs row {run_id}")
    run = runs[0]
    cuts = spec.get("cuts") or []
    if not cuts:
        raise SystemExit("EDL has no cuts")

    cache: Dict[str, Path] = {}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        pieces: List[Path] = []
        for i, cut in enumerate(cuts):
            out = work / f"{i:03d}.wav"
            if cut.get("gap") is not None:
                pieces.append(_silence(float(cut["gap"]), out))
                continue
            url = _resolve(str(cut["from"]), run, show, spec.get("narration", ""))
            src = _fetch(url, work / f"src_{abs(hash(url))}.bin", cache)
            pieces.append(_piece(cut, src, out))
            logger.info("cut %d: %s -> %.1fs", i, cut["from"], _duration(out))

        episode = work / "episode.mp3"
        inputs: List[str] = []
        labels: List[str] = []
        for i, piece in enumerate(pieces):
            inputs += ["-i", str(piece)]
            labels.append(f"[{i}:a]")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex",
             "".join(labels) + f"concat=n={len(pieces)}:v=0:a=1,{LOUDNESS}[out]",
             "-map", "[out]", "-ar", "48000", "-ac", "1",
             "-c:a", "libmp3lame", "-b:a", "128k", str(episode)],
            check=True)
        seconds = _duration(episode)
        url = r2_upload(episode, show.r2_key("raw", f"{run_id}_edit.mp3"))

    # Both review pages prefer this over the raw mix, so Patrick and the guest
    # hear the edit rather than the unedited room.
    log = dict(run.get("grok_session_log") or {})
    tracks = dict(log.get("tracks") or {})
    tracks["preview"] = url
    tracks["edit"] = {"slug": slug, "url": url, "duration_sec": round(seconds, 1)}
    log["tracks"] = tracks
    sb_update("interview_runs", f"id=eq.{run_id}", {"grok_session_log": log})
    logger.info("episode %s (%.0f min) -> %s", slug, seconds / 60, url)
    return {"url": url, "duration_sec": seconds}


if __name__ == "__main__":
    slug = os.environ.get("EDL_SLUG") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not slug:
        raise SystemExit("EDL_SLUG (or argv[1]) required")
    result = assemble(slug)
    print(f"{result['duration_sec']:.0f}s\t{result['url']}")
