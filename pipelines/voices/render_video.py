#!/usr/bin/env python3
"""The video version of an interview: the guest beside Mira (Oct 28 2026).

Patrick wants the interviews on video for YouTube, X and the episode's page,
with the guest's camera beside Mira's picture ("side by side", his choice of
Oct 28). The guest's camera is recorded in their browser and placed on the
guest leg's clock by post_interview (``video_take.py``); the edit records,
in ``tracks.edit.clock``, every stretch of the room it kept and where that
stretch starts in the published file. So the picture is cut exactly as the
sound was: the same takes, the same closed pauses, the same running order,
frame for frame.

    python pipelines/voices/render_video.py --run <interview_run id>

Layout, 1920x1080 at 30 fps: two 16:9 tiles on the show's dark ground, the
guest on the left and Mira's studio illustration on the right, a border in
the show's colour on whoever is speaking (from the transcript of the edit),
names under the tiles, the show's name over them. While the edit plays
something the camera did not see (Mira's narration, a pause between pieces,
a stretch the camera was off) the guest's tile shows their name card.

What it will not do: render for a guest who asked for audio only on the
review page (``editorial_packages.guest_video_ok`` false), or for an edit
the video was not cut against. The result goes to R2 and is recorded as
``tracks.edit.video_url`` with the edit URL it follows; publish_episode
uploads it to YouTube and puts it on the episode's page only when that edit
is still the one being published.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROOT = Path(__file__).resolve().parents[2]
FPS = 30
W, H = 1920, 1080
TILE_W, TILE_H = 880, 496
GUEST_X, MIRA_X, TILE_Y = 48, 992, 250
BORDER = 6
MIRA_IMAGE = ROOT / "assets" / "mira" / "mira-studio.mp4"
FONT_BOLD = ROOT / "assets" / "fonts" / "DMSans-Bold.ttf"
FONT_MEDIUM = ROOT / "assets" / "fonts" / "DMSans-Medium.ttf"
GROUND = "0x0B1020"
TILE_GROUND = "0x161D33"


# ---------------------------------------------------------------------------
# Planning (pure)
# ---------------------------------------------------------------------------

def frames(seconds: float, fps: int = FPS) -> int:
    return int(round(float(seconds) * fps))


def plan_guest_track(clock: Sequence[Sequence[float]], room_offset: float,
                     takes: List[dict], total_sec: float,
                     fps: int = FPS) -> List[dict]:
    """The guest tile as a list of runs covering ``[0, total frames)``:
    ``{"start", "end"}`` in edit frames, and either ``{"take", "at"}`` (show
    that take from ``at`` seconds) or ``{"card": True}``.

    ``clock`` rows are ``[room_from, room_to, edit_from(, scale)]`` (see
    edit_transcript.edit_clock); room times carry ``room_offset``, which is
    taken off to reach the guest leg's clock the takes are placed on. A
    stretch with a scale had its pauses closed without a record of where,
    so no single picture matches it; it gets the card. Frame numbers come
    from the edit's own clock, never from summing durations, so nothing can
    drift however many pieces there are."""
    from video_take import video_time

    total = frames(total_sec, fps)
    runs: List[dict] = []
    for seg in sorted(clock or [], key=lambda r: float(r[2])):
        ra, rb, ea = float(seg[0]), float(seg[1]), float(seg[2])
        scale = float(seg[3]) if len(seg) > 3 else 1.0
        if rb <= ra or scale < 0.999:
            continue
        leg_a, leg_b = ra - room_offset, rb - room_offset
        t = leg_a
        while t < leg_b - 1e-6:
            where = video_time(takes, t)
            if where is None:
                # Not on camera here: skip to the next moment a take covers.
                nxt = _next_covered(takes, t, leg_b)
                t = nxt if nxt is not None else leg_b
                continue
            i, vt = where
            piece_end = _piece_end(takes[i], vt)
            run_end = min(leg_b, t + (piece_end - vt))
            f0 = frames(ea + (t - leg_a), fps)
            f1 = frames(ea + (run_end - leg_a), fps)
            if f1 > f0:
                runs.append({"start": f0, "end": min(f1, total), "take": i,
                             "at": round(vt, 3)})
            t = run_end
    runs = _non_overlapping(sorted(runs, key=lambda r: r["start"]), fps)
    return _fill_cards(runs, total)


def _piece_end(take: dict, vt: float) -> float:
    for piece in take.get("pieces") or []:
        if float(piece["from"]) <= vt < float(piece["to"]):
            return float(piece["to"])
    return vt


def _next_covered(takes: List[dict], t: float, limit: float) -> Optional[float]:
    starts = [float(p["from"]) + float(p["delay"])
              for take in takes for p in take.get("pieces") or []]
    later = [s for s in starts if t < s < limit]
    return min(later) if later else None


def _non_overlapping(runs: List[dict], fps: int = FPS) -> List[dict]:
    """Later runs give way to earlier ones; a trimmed run starts its picture
    as much later as its start moved."""
    out: List[dict] = []
    for r in runs:
        if r["end"] <= r["start"]:
            continue
        if out and r["start"] < out[-1]["end"]:
            moved = out[-1]["end"] - r["start"]
            r = {**r, "start": out[-1]["end"]}
            if r["end"] <= r["start"]:
                continue
            if "at" in r:
                r["at"] = round(r["at"] + moved / fps, 3)
        out.append(r)
    return out


def _fill_cards(runs: List[dict], total: int) -> List[dict]:
    out: List[dict] = []
    at = 0
    for r in runs:
        if r["start"] > at:
            out.append({"start": at, "end": r["start"], "card": True})
        out.append(r)
        at = r["end"]
    if at < total:
        out.append({"start": at, "end": total, "card": True})
    # Neighbouring cards are one card.
    merged: List[dict] = []
    for r in out:
        if merged and r.get("card") and merged[-1].get("card") and merged[-1]["end"] == r["start"]:
            merged[-1] = {**merged[-1], "end": r["end"]}
        else:
            merged.append(r)
    return merged


def speaker_spans(edit_transcript: str, total_sec: float) -> Dict[str, List[Tuple[float, float]]]:
    """``{"mira": [(from, to)], "guest": [...]}`` on the edit's clock, from
    the transcript of the edit: each line holds the floor until the next.
    Anyone but Mira (the guest, a co-host) lights the guest's tile."""
    from edit_transcript import parse_lines
    lines = parse_lines(edit_transcript or "")
    spans: Dict[str, List[Tuple[float, float]]] = {"mira": [], "guest": []}
    for k, (at, who, _text) in enumerate(lines):
        end = lines[k + 1][0] if k + 1 < len(lines) else total_sec
        if end <= at:
            continue
        side = "mira" if who.lower().startswith("mira") else "guest"
        if spans[side] and abs(spans[side][-1][1] - at) < 1e-6:
            spans[side][-1] = (spans[side][-1][0], min(end, total_sec))
        else:
            spans[side].append((at, min(end, total_sec)))
    return spans


def enable_expr(spans: List[Tuple[float, float]]) -> str:
    """An ffmpeg ``enable`` expression true inside any span (0 when none)."""
    if not spans:
        return "0"
    return "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in spans)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _run(cmd: list, timeout: int = 3600) -> None:
    subprocess.run([str(c) for c in cmd], check=True, capture_output=True,
                   text=True, timeout=timeout)


ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
          "-r", str(FPS)]


def name_card(guest: str, subtitle: str, out: Path) -> Path:
    """The guest's tile while the camera has nothing to show."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (TILE_W, TILE_H), (22, 29, 51))
    draw = ImageDraw.Draw(img)

    def font(path: Path, size: int):
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            return ImageFont.load_default()

    big, small = font(FONT_BOLD, 54), font(FONT_MEDIUM, 30)
    y = TILE_H // 2 - (40 if subtitle else 20)
    for text, f, fill, dy in ((guest, big, (241, 245, 249), 0),
                              (subtitle, small, (148, 163, 184), 78)):
        if not text:
            continue
        w = draw.textlength(text, font=f)
        draw.text(((TILE_W - w) / 2, y + dy - 27), text, font=f, fill=fill)
    img.save(out)
    return out


def render_guest_tile(runs: List[dict], take_paths: List[Path], card: Path,
                      workdir: Path, fps: int = FPS) -> Path:
    """One clip per run at the tile's size, joined without re-encoding."""
    workdir.mkdir(parents=True, exist_ok=True)
    scale = (f"scale={TILE_W}:{TILE_H}:force_original_aspect_ratio=increase,"
             f"crop={TILE_W}:{TILE_H},setsar=1,fps={fps}")
    listing = workdir / "list.txt"
    with listing.open("w") as fh:
        for k, r in enumerate(runs):
            n = r["end"] - r["start"]
            out = workdir / f"r{k:05d}.mp4"
            if r.get("card"):
                cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", fps,
                       "-i", card, "-vf", f"scale={TILE_W}:{TILE_H},setsar=1"]
            else:
                cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{r['at']:.3f}",
                       "-i", take_paths[r["take"]], "-an", "-vf", scale]
            _run(cmd + ["-frames:v", n, *ENCODE, out])
            fh.write(f"file '{out.name}'\n")
    tile = workdir / "guest_tile.mp4"
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", listing,
          "-c", "copy", tile])
    return tile


def _text_file(workdir: Path, name: str, text: str) -> Path:
    p = workdir / name
    p.write_text(text, encoding="utf-8")
    return p


def compose(guest_tile: Path, audio: Path, out: Path, *, total_sec: float,
            spans: Dict[str, List[Tuple[float, float]]], guest_name: str,
            show_name: str, brand: str, workdir: Path) -> Path:
    """The final 1920x1080 picture with the episode's audio."""
    color = "0x" + brand.lstrip("#") if brand else "0x7C3AED"
    gname = _text_file(workdir, "guest_name.txt", guest_name)
    mname = _text_file(workdir, "mira_name.txt", "Mira · AI host")
    title = _text_file(workdir, "title.txt", show_name)
    site = _text_file(workdir, "site.txt", "nerranetwork.com")
    font_b, font_m = str(FONT_BOLD), str(FONT_MEDIUM)
    label_y = TILE_Y + TILE_H + 28

    def box(x: int, side: str) -> str:
        return (f"drawbox=x={x - BORDER}:y={TILE_Y - BORDER}:w={TILE_W + 2 * BORDER}:"
                f"h={TILE_H + 2 * BORDER}:color={color}:t={BORDER}:"
                f"enable='{enable_expr(spans.get(side) or [])}'")

    graph = ";".join([
        f"color=c={GROUND}:s={W}x{H}:r={FPS}:d={total_sec:.3f}[bg]",
        f"[0:v]setpts=PTS-STARTPTS,fps={FPS}[g]",
        # Mira's picture is portrait: centred on a tile of its own colour.
        f"color=c={TILE_GROUND}:s={TILE_W}x{TILE_H}:r={FPS}:d={total_sec:.3f}[mt]",
        f"[1:v]scale=-2:{TILE_H},fps={FPS},setsar=1[mi]",
        "[mt][mi]overlay=x=(W-w)/2:y=0:shortest=1[m]",
        f"[bg][g]overlay=x={GUEST_X}:y={TILE_Y}:eof_action=pass[a]",
        f"[a][m]overlay=x={MIRA_X}:y={TILE_Y}:shortest=1[b]",
        "[b]" + ",".join([
            box(GUEST_X, "guest"),
            box(MIRA_X, "mira"),
            f"drawtext=fontfile='{font_b}':textfile='{gname}':x={GUEST_X}:y={label_y}:"
            "fontsize=40:fontcolor=0xF1F5F9",
            f"drawtext=fontfile='{font_b}':textfile='{mname}':x={MIRA_X}:y={label_y}:"
            "fontsize=40:fontcolor=0xF1F5F9",
            f"drawtext=fontfile='{font_b}':textfile='{title}':x=(w-tw)/2:y=110:"
            "fontsize=54:fontcolor=0xF8FAFC",
            f"drawtext=fontfile='{font_m}':textfile='{site}':x=(w-tw)/2:y={H - 110}:"
            "fontsize=32:fontcolor=0x94A3B8",
        ]) + "[v]",
    ])
    # The graph goes on the command line: -filter_complex_script is
    # deprecated from ffmpeg 7 and the runners carry 8.1. Even an hour of
    # speaker changes is a few tens of kilobytes, far under ARG_MAX.
    _text_file(workdir, "graph.txt", graph)  # kept beside the job for a look
    _run(["ffmpeg", "-y", "-v", "error",
          "-i", guest_tile,
          "-stream_loop", "-1", "-i", MIRA_IMAGE,
          "-i", audio,
          "-filter_complex", graph,
          "-map", "[v]", "-map", "2:a",
          *ENCODE, "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
          "-t", f"{total_sec:.3f}", "-movflags", "+faststart", out], timeout=7200)
    return out


# ---------------------------------------------------------------------------
# The job
# ---------------------------------------------------------------------------

def video_allowed(pkg: Optional[dict]) -> bool:
    """A guest who asked for audio only gets no video, anywhere."""
    return not (pkg and pkg.get("guest_video_ok") is False)


def render_for_run(run_id: str) -> Optional[str]:
    from common import logger, r2_upload, sb_select, sb_update, show_for
    import requests

    rows = sb_select("interview_runs", f"id=eq.{run_id}")
    if not rows:
        raise SystemExit(f"no interview_runs row {run_id}")
    run = rows[0]
    log = run.get("grok_session_log") or {}
    tracks = log.get("tracks") or {}
    edit = tracks.get("edit") or {}
    video = tracks.get("video") or {}
    if not edit.get("url") or not edit.get("clock"):
        logger.info("run %s has no assembled edit with a clock — nothing to cut "
                    "a video against", run_id)
        return None
    if not video.get("takes"):
        logger.info("run %s has no guest video — the episode stays audio", run_id)
        return None
    interview = (sb_select("interviews", f"id=eq.{run['interview_id']}") or [{}])[0]
    app = (sb_select("guest_applications",
                     f"id=eq.{interview.get('application_id')}") or [{}])[0]
    pkgs = sb_select("editorial_packages",
                     f"interview_run_id=eq.{run_id}&status=neq.killed&order=created_at.desc&limit=1")
    pkg = pkgs[0] if pkgs else None
    if not video_allowed(pkg):
        logger.info("the guest asked for audio only — no video for run %s", run_id)
        return None
    show = show_for(interview, app)
    total = float(edit.get("duration_sec") or 0.0)
    guest = str(app.get("name") or "Guest")
    subtitle = " · ".join(x for x in (app.get("title"), app.get("organization")) if x)

    with tempfile.TemporaryDirectory(prefix="render_video_") as tmp:
        work = Path(tmp)
        audio = work / "edit.mp3"
        with requests.get(edit["url"], stream=True, timeout=900) as resp:
            resp.raise_for_status()
            with audio.open("wb") as fh:
                for chunk in resp.iter_content(1 << 16):
                    fh.write(chunk)
        takes = video["takes"]
        take_paths: List[Path] = []
        for i, take in enumerate(takes):
            dest = work / f"take_{i}{Path(take['url'].split('?')[0]).suffix or '.mkv'}"
            with requests.get(take["url"], stream=True, timeout=1800) as resp:
                resp.raise_for_status()
                with dest.open("wb") as fh:
                    for chunk in resp.iter_content(1 << 16):
                        fh.write(chunk)
            take_paths.append(dest)
        runs = plan_guest_track(edit["clock"], float(edit.get("room_offset_sec") or 0.0),
                                takes, total)
        on_camera = sum(r["end"] - r["start"] for r in runs if not r.get("card"))
        logger.info("guest tile: %d runs, %.0f%% of the episode on camera", len(runs),
                    100.0 * on_camera / max(1, frames(total)))
        card = name_card(guest, subtitle, work / "card.png")
        tile = render_guest_tile(runs, take_paths, card, work / "tile")
        spans = speaker_spans((pkg or {}).get("edit_transcript") or "", total)
        name = Path(edit["url"].split("?")[0]).stem + "_video.mp4"
        out = compose(tile, audio, work / name, total_sec=total, spans=spans,
                      guest_name=guest, show_name=show.name, brand=show.brand_color,
                      workdir=work)
        url = r2_upload(out, show.r2_key("video", name))

    fresh = (sb_select("interview_runs", f"id=eq.{run_id}") or [run])[0]
    log = dict(fresh.get("grok_session_log") or {})
    tracks = dict(log.get("tracks") or {})
    edit_now = dict(tracks.get("edit") or {})
    edit_now.update({"video_url": url, "video_of": edit["url"],
                     "video_built_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                     "video_on_camera": round(on_camera / max(1, frames(total)), 3)})
    tracks["edit"] = edit_now
    log["tracks"] = tracks
    sb_update("interview_runs", f"id=eq.{run_id}", {"grok_session_log": log})
    logger.info("video version of run %s -> %s", run_id, url)
    return url


def merge_spans(runs: Sequence[Tuple[float, float]], gap: float = 1.0
                ) -> List[Tuple[float, float]]:
    """Speech runs joined across pauses shorter than ``gap``: who holds the
    floor, for the border, when there is no transcript of an edit."""
    out: List[List[float]] = []
    for a, b in sorted(runs):
        if out and a - out[-1][1] < gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(round(a, 2), round(b, 2)) for a, b in out]


def preview_for_run(run_id: str) -> Optional[str]:
    """A test room's picture, uncut: the room's own stereo recording (guest
    left, Mira right) with the guest's camera placed against the left side,
    so the operator can watch what the camera gave before guests get it. A
    test room is never post-processed, so there is no edit to follow; the
    whole room is the clock. Uploaded beside the room's raw files, never
    published anywhere."""
    from common import logger, r2_upload, sb_select, show_for
    import requests
    from video_take import build_video_track, video_takes
    import turn_cues

    run = (sb_select("interview_runs", f"id=eq.{run_id}") or [None])[0]
    if not run:
        raise SystemExit(f"no interview_runs row {run_id}")
    stereo = str(run.get("recording_guest_url") or "")
    if not stereo:
        logger.info("run %s has no room recording to preview", run_id)
        return None
    if not (((run.get("grok_session_log") or {}).get("tracks") or {}).get("video")
            or video_takes(run)):
        logger.info("run %s recorded no camera — nothing to preview", run_id)
        return None
    interview = (sb_select("interviews", f"id=eq.{run.get('interview_id')}") or [{}])[0]
    app = (sb_select("guest_applications",
                     f"id=eq.{interview.get('application_id')}") or [{}])[0]
    show = show_for(interview, app)
    with tempfile.TemporaryDirectory(prefix="render_preview_") as tmp:
        work = Path(tmp)
        room = work / "room.mp3"
        with requests.get(stereo, stream=True, timeout=900) as resp:
            resp.raise_for_status()
            with room.open("wb") as fh:
                for chunk in resp.iter_content(1 << 16):
                    fh.write(chunk)
        guest = turn_cues.load_audio((str(room), 0), sr=16000)
        mira = turn_cues.load_audio((str(room), 1), sr=16000)
        ref = work / "guest_ref.wav"
        _run(["ffmpeg", "-y", "-v", "error", "-i", room, "-af", "pan=mono|c0=c0",
              "-ar", 16000, ref])
        video = (((run.get("grok_session_log") or {}).get("tracks") or {}).get("video")
                 or build_video_track(run, ref, work / "takes",
                                      upload=lambda path, _key: str(path),
                                      key_for=lambda name: name))
        if not video or not video.get("takes"):
            logger.info("run %s: the camera could not be placed on the room", run_id)
            return None
        takes = video["takes"]
        take_paths = [Path(t["url"]) if not str(t["url"]).startswith("http")
                      else _fetch(t["url"], work / f"take_{i}.mkv") for i, t in enumerate(takes)]
        total = len(guest) / 16000.0
        runs = plan_guest_track([[0.0, total, 0.0]], 0.0, takes, total)
        on_camera = sum(r["end"] - r["start"] for r in runs if not r.get("card"))
        logger.info("preview: %.0f%% of the room on camera", 100.0 * on_camera / max(1, frames(total)))
        spans = {"guest": merge_spans(turn_cues.speech_runs(turn_cues.frame_db(guest[::2]))),
                 "mira": merge_spans(turn_cues.speech_runs(turn_cues.frame_db(mira[::2])))}
        name = str(app.get("name") or "Guest")
        card = name_card(name, "test room", work / "card.png")
        tile = render_guest_tile(runs, take_paths, card, work / "tile")
        out = compose(tile, room, work / f"{run_id}_preview_video.mp4", total_sec=total,
                      spans=spans, guest_name=name, show_name=show.name,
                      brand=show.brand_color, workdir=work)
        url = r2_upload(out, show.r2_key("raw", f"{run_id}_preview_video.mp4"))
    logger.info("preview of test room %s -> %s", run_id, url)
    return url


def _fetch(url: str, dest: Path) -> Path:
    import requests
    with requests.get(url, stream=True, timeout=1800) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_content(1 << 16):
                fh.write(chunk)
    return dest


def run_id_for_edl(slug: str) -> str:
    """The run an EDL cuts (the file in the repo, else the stored one)."""
    path = Path(__file__).parent / "edl" / f"{slug}.json"
    spec = None
    if path.exists():
        spec = json.loads(path.read_text(encoding="utf-8"))
    else:
        from narrate import _stored_spec
        spec = _stored_spec(slug, "edl")
    return str((spec or {}).get("run_id") or "")


def tell_patrick(url: str, run_id: str, preview: bool = False) -> None:
    from common import OPERATOR_EMAIL, logger, send_email
    if preview:
        subject = "The test room's video is ready to watch"
        body = (f"<p>Hi Patrick,</p><p>The camera from test room <code>{run_id}</code>, "
                f"beside my picture, uncut: <a href=\"{url}\">watch it here</a>. It is "
                "published nowhere. If it looks right, the shows can record guests' "
                "cameras (<code>local_video: true</code>).</p><p>— Mira</p>")
    else:
        subject = "The video version is ready to watch"
        body = (f"<p>Hi Patrick,</p><p>The video version of run <code>{run_id}</code> "
                f"is cut: <a href=\"{url}\">watch it here</a>. It follows the edit "
                "you reviewed, frame for frame. It goes to YouTube and the episode's "
                "page when you publish, unless the guest asked for audio only.</p>"
                "<p>— Mira</p>")
    try:
        send_email(OPERATOR_EMAIL, subject, body)
    except Exception:  # noqa: BLE001 — the video exists either way
        logger.exception("could not email the video link (it is at %s)", url)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", default=os.environ.get("RUN_ID", ""))
    ap.add_argument("--edl", default=os.environ.get("EDL_SLUG", ""))
    ap.add_argument("--preview", action="store_true",
                    default=os.environ.get("PREVIEW", "").lower() in ("1", "true"),
                    help="a test room's picture, uncut, for the operator to watch")
    args = ap.parse_args(argv)
    run_id = (args.run or "").strip() or (run_id_for_edl(args.edl.strip()) if args.edl.strip() else "")
    if not run_id:
        raise SystemExit("--run <interview_run id> or --edl <slug> is required")
    url = preview_for_run(run_id) if args.preview else render_for_run(run_id)
    if url:
        tell_patrick(url, run_id, preview=args.preview)
    print(json.dumps({"video_url": url}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
