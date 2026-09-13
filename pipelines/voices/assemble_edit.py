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

from common import (  # noqa: E402
    OPERATOR_EMAIL, logger, package_review_token, r2_upload, sb_select,
    sb_update, send_email,
)
from shows import get_show  # noqa: E402

EDL_DIR = Path(__file__).parent / "edl"
GENTLE = ("highpass=f=60,"
          "acompressor=threshold=-21dB:ratio=3:attack=20:release=250,"
          "dynaudnorm=f=250:g=15")
LOUDNESS = "loudnorm=I=-16:TP=-1.5:LRA=11"
# Narration does not get dynaudnorm. Mira's takes already arrive at one
# level, and Sept 13 2026 measured what levelling them costs: her intro came
# out of the assembler with a noise floor of -51.8 dB against -62.3 in the
# approved edit, and her outro -48.2 against -74.1, while the conversation
# either side of them matched to a tenth of a decibel. Nothing had been added
# to the narration — dynaudnorm had simply lifted its quiet frames, hiss
# included, by up to 15 dB. Speech level is unaffected: the master loudnorm
# sets that, and both builds put her at -12.9 dB.
NARRATION_GENTLE = ("highpass=f=60,"
                    "acompressor=threshold=-21dB:ratio=2:attack=20:release=250")
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

# Restoration (Sept 13 2026). Two faults, measured rather than assumed:
#
#  * Ticks. Mira's Speech-to-Speech audio reaches the recorder over a
#    websocket, and her narration carried roughly 40 click-like events a
#    minute against 18 in the conversation. adeclick removes about 90% of
#    them and leaves band energy from 100 Hz to 16 kHz unchanged to a tenth
#    of a decibel, so nothing is dulled.
#  * Hiss. It lives in the conference mixer's output, not in anyone's
#    microphone: in a real pause a guest's own leg recording is digital
#    silence while the room mix has real energy above 8 kHz. anlmdn takes
#    another 6 dB off the floor.
RESTORE = "adeclick=w=75:t=2,anlmdn=s=0.0005:p=0.002"

# Narration gets one filter the conversation does not. Her takes come out of
# the websocket with a floor around -66 dB, and everything downstream — the
# compressor, then the master loudnorm — adds roughly 13 dB of gain, which
# puts that floor at -53 in the finished episode where it is audible under a
# voice with no room tone behind it. afftdn takes it to -63 with the noise
# estimate parked at the measured floor (nf=-45); at nf=-50 it sits below the
# noise and does almost nothing. Band energy from 100 Hz to 8 kHz moves by at
# most 0.2 dB, so she is not dulled. A conversation has its own room tone and
# does not need or want this.
NARRATION_RESTORE = "adeclick=w=75:t=2,afftdn=nf=-45:nr=12,anlmdn=s=0.0005:p=0.002"

# A stereo per-person recording is L = their microphone, R = everyone they
# heard, and those two sides arrive at different levels — on the Hogan Shrum
# tape the guest sat 6 dB over the host and Mira. Levelling each SIDE before
# folding fixes that; levelling after the fold cannot, because by then it is
# one signal. "balance" on a cut turns this on.
SIDE_CHAIN = ("highpass=f=70,{restore},dynaudnorm=f=200:g=9:p=0.9:m=12")
BALANCE_GLUE = "acompressor=threshold=-20dB:ratio=2.5:attack=20:release=250"


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
    restore = RESTORE if cut.get("restore", True) else None
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if cut.get("start") is not None:
        cmd += ["-ss", str(cut["start"])]
    if cut.get("end") is not None:
        cmd += ["-to", str(cut["end"])]
    cmd += ["-i", str(src)]

    if cut.get("balance"):
        # Level the two sides of a stereo per-person recording separately,
        # then fold. Anything else here would be levelling a mixture.
        side = SIDE_CHAIN.format(restore=restore or "anull")
        cmd += ["-filter_complex",
                f"[0:a]channelsplit=channel_layout=stereo[l][r];"
                f"[l]{side}[lg];[r]{side}[rg];"
                f"[lg][rg]amix=inputs=2:normalize=0,{BALANCE_GLUE}[o]",
                "-map", "[o]"]
    else:
        chain = []
        channel = cut.get("channel")
        if channel:
            if channel not in CHANNEL_FILTERS:
                raise SystemExit(f"channel must be one of {sorted(CHANNEL_FILTERS)}")
            chain.append(CHANNEL_FILTERS[channel])
        # Narration is trimmed by default; a conversation never is, because
        # the pauses in it are the conversation.
        trim = cut.get("trim")
        if trim is None:
            trim = str(cut.get("from", "")).startswith("narration:")
        if trim:
            chain.append(TRIM)
        narration = str(cut.get("from", "")).startswith("narration:")
        if restore:
            chain.append(NARRATION_RESTORE if narration else restore)
        chain.append(NARRATION_GENTLE if narration else GENTLE)
        cmd += ["-af", ",".join(chain)]

    cmd += ["-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(out)]
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
    show = get_show(spec.get("show"))
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

    # A transcript beside the EDL is the transcript OF THE EDIT: same cuts,
    # same running order, everyone on one clock. The pipeline's own transcript
    # describes the unedited room, which is not what a guest is asked to
    # approve, so this replaces it on the editorial package when present.
    transcript_path = EDL_DIR / f"{slug}.transcript.txt"
    if transcript_path.exists():
        text = transcript_path.read_text(encoding="utf-8")
        pkgs = sb_select("editorial_packages",
                         f"interview_id=eq.{spec['interview_id']}&select=id")
        if pkgs:
            sb_update("editorial_packages", f"id=eq.{pkgs[0]['id']}",
                      {"transcript_cleaned": text})
            logger.info("transcript of the edit written to package %s (%d chars)",
                        pkgs[0]["id"], len(text))
        else:
            logger.warning("no editorial package for %s — transcript not written",
                           spec["interview_id"])

    # Both review pages prefer this over the raw mix, so Patrick and the guest
    # hear the edit rather than the unedited room.
    log = dict(run.get("grok_session_log") or {})
    tracks = dict(log.get("tracks") or {})
    tracks["preview"] = url
    tracks["edit"] = {"slug": slug, "url": url, "duration_sec": round(seconds, 1)}
    log["tracks"] = tracks
    sb_update("interview_runs", f"id=eq.{run_id}", {"grok_session_log": log})
    logger.info("episode %s (%.0f min) -> %s", slug, seconds / 60, url)
    _tell_patrick(spec, show, slug, url, seconds)
    return {"url": url, "duration_sec": seconds}


def _tell_patrick(spec: dict, show, slug: str, url: str, seconds: float) -> None:
    """Email the finished episode to the operator for gate 1.

    Sept 13 2026: a finished episode used to sit in R2 until someone thought
    to look. The point of assembling it is that a person hears it and says
    yes, so the assembler hands it to them.
    """
    pkgs = sb_select("editorial_packages",
                     f"interview_id=eq.{spec['interview_id']}&select=id,status")
    pkg = pkgs[0] if pkgs else None
    apps = []
    ivs = sb_select("interviews", f"id=eq.{spec['interview_id']}&select=application_id")
    if ivs and ivs[0].get("application_id"):
        apps = sb_select("guest_applications", f"id=eq.{ivs[0]['application_id']}")
    guest = (apps[0].get("name") if apps else None) or "the guest"
    review = ""
    if pkg:
        try:
            review = (f"https://api.nerranetwork.com/voices/admin/review/{pkg['id']}"
                      f"?token={package_review_token(pkg['id'])}")
        except Exception:  # noqa: BLE001
            logger.exception("review token unavailable")
    try:
        send_email(
            OPERATOR_EMAIL,
            f"{show.short_label}: {guest} is cut and ready for your ear",
            f"<p>Hi Patrick,</p>"
            f"<p>The {guest} episode is assembled — introduction, conversation and "
            f"close, {int(seconds // 60)} minutes {int(seconds % 60):02d}.</p>"
            f'<p><a href="{url}">Listen to the episode</a></p>'
            + (f'<p>When it passes your ear, approve it here and the guest is asked '
               f'to review it: <a href="{review}">gate 1</a>.</p>' if review else "")
            + f"<p>Nothing reaches {guest} until you do.</p>"
              f"<p>Edit: <code>{slug}</code>. To change a cut, edit "
              f"<code>pipelines/voices/edl/{slug}.json</code> and run the assemble "
              f"workflow again.</p><p>— Mira</p>")
        if pkg:
            sb_update("editorial_packages", f"id=eq.{pkg['id']}",
                      {"operator_preview_sent_at": __import__("datetime")
                       .datetime.now(__import__("datetime").timezone.utc).isoformat()})
        logger.info("episode emailed to %s", OPERATOR_EMAIL)
    except Exception:  # noqa: BLE001 — the episode exists either way
        logger.exception("operator preview email failed (non-fatal)")


if __name__ == "__main__":
    slug = os.environ.get("EDL_SLUG") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not slug:
        raise SystemExit("EDL_SLUG (or argv[1]) required")
    result = assemble(slug)
    print(f"{result['duration_sec']:.0f}s\t{result['url']}")
