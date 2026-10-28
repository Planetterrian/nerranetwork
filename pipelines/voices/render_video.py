#!/usr/bin/env python3
"""The video versions of an interview: the guest beside Mira (Oct 28 2026).

Patrick wants the interviews on video for YouTube, X and the episode's page.
Two shapes come out of one edit:

* **Long form**, 1920x1080: the guest's camera and Mira's studio picture
  side by side, a border in the show's colour on whoever is speaking, names
  under the tiles, the show's name over them. YouTube and the episode page.
* **Shorts**, 1080x1920: the guest stacked over Mira, the show's name on top
  and the words burned in at the bottom, one clip per suggested moment (up to
  three, each under a minute and a half). YouTube Shorts, X, Reels, TikTok:
  most of these are watched on a phone with the sound off, so the captions
  are not decoration.

The guest's camera is recorded in their browser and placed on the guest
leg's clock by post_interview (``video_take.py``); the edit records, in
``tracks.edit.clock``, every stretch of the room it kept and where that
stretch starts in the published file. So the picture is cut exactly as the
sound was, frame for frame. While the edit plays something the camera did
not see (Mira's narration, a pause between pieces, a stretch the camera was
off) the guest's tile shows their name card.

**Mira moves only when she is speaking** (Patrick, on the first preview: "it
had her talking when she was not, and that looks really bad"). Who is
speaking, and when, is measured from the audio, never from the transcript:
her own processed track for the room (moved onto the edit's clock), the
edit itself where it plays her narration. While she speaks her picture plays
the talking loop from its first frame (which is the still she rests on), and
when she stops it rests on the still. The speaker's border follows the same
measurement.

    python pipelines/voices/render_video.py --run <interview_run id>
    python pipelines/voices/render_video.py --run <test room run> --preview

What it will not do: render for a guest who asked for audio only on the
review page (``editorial_packages.guest_video_ok`` false), or for an edit
the video was not cut against. The results go to R2 and are recorded as
``tracks.edit.video_url`` / ``tracks.edit.shorts`` with the edit URL they
follow; publish_episode uses them only while that edit is still the one
being published.
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
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROOT = Path(__file__).resolve().parents[2]
FPS = 30
W, H = 1920, 1080
TILE_W, TILE_H = 880, 496
GUEST_X, MIRA_X, TILE_Y = 48, 992, 250
BORDER = 6
MIRA_LOOP = ROOT / "assets" / "mira" / "mira-studio.mp4"
MIRA_STILL = ROOT / "assets" / "mira" / "mira-studio.jpg"
MIRA_IMAGE = MIRA_LOOP          # kept for anything that imported the old name
FONT_BOLD = ROOT / "assets" / "fonts" / "DMSans-Bold.ttf"
FONT_MEDIUM = ROOT / "assets" / "fonts" / "DMSans-Medium.ttf"
GROUND = "0x0B1020"
TILE_GROUND = "0x161D33"
#: Mira's picture is a 480x730 portrait of her at the desk. A tile shows her
#: the way the guest's camera shows them: head and shoulders, cropped from
#: this many pixels down the source.
MIRA_SRC_W, MIRA_SRC_H = 480, 730
MIRA_FACE_Y = 56

# The vertical (Shorts) layout, 1080x1920.
VW, VH = 1080, 1920
# Everything a viewer needs sits between the phone apps' own furniture: the
# top 180 px and the bottom ~360 px carry search, title and channel overlays.
V_GUEST = (40, 200, 1000, 620)          # x, y, w, h
V_MIRA = (40, 850, 1000, 560)
V_BORDER = 8
#: A Short is one moment, not a chapter.
SHORT_MAX_SEC = 90.0          # the clip pass picks 20-90 s moments
SHORT_MIN_SEC = 15.0
SHORTS_PER_EPISODE = 3

#: Mira's mouth closes on a pause longer than this; shorter gaps are breaths
#: inside a sentence.
MIRA_GAP_SEC = 0.45
#: A speaker keeps the border across a pause shorter than this.
FLOOR_GAP_SEC = 1.0
#: Speech shorter than this is a click, a breath or a cough, not talking.
MIN_TALK_SEC = 0.25


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


def slice_runs(runs: List[dict], f0: int, f1: int, fps: int = FPS) -> List[dict]:
    """The guest tile's runs for frames ``[f0, f1)``, renumbered from 0."""
    out: List[dict] = []
    for r in runs:
        a, b = max(r["start"], f0), min(r["end"], f1)
        if b <= a:
            continue
        piece = {"start": a - f0, "end": b - f0}
        if r.get("card"):
            piece["card"] = True
        else:
            piece.update(take=r["take"], at=round(r["at"] + (a - r["start"]) / fps, 3))
        out.append(piece)
    return out


def speaker_spans(edit_transcript: str, total_sec: float) -> Dict[str, List[Tuple[float, float]]]:
    """``{"mira": [(from, to)], "guest": [...]}`` on the edit's clock, from
    the transcript of the edit: each line holds the floor until the next.
    The fallback when the per-speaker audio cannot be read: a line holds the
    floor through its pauses, so it is only good enough for the border."""
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


def merge_spans(runs: Sequence[Tuple[float, float]], gap: float = 1.0,
                min_len: float = 0.0) -> List[Tuple[float, float]]:
    """Speech runs joined across pauses shorter than ``gap``, and runs
    shorter than ``min_len`` (after joining) dropped."""
    out: List[List[float]] = []
    for a, b in sorted(runs):
        if out and a - out[-1][1] < gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(round(a, 2), round(b, 2)) for a, b in out if b - a >= min_len]


def clock_spans(clock: Sequence[Sequence[float]]) -> List[Tuple[float, float]]:
    """Where the room plays in the edit."""
    out = []
    for seg in clock or []:
        ra, rb, ea = float(seg[0]), float(seg[1]), float(seg[2])
        sc = float(seg[3]) if len(seg) > 3 else 1.0
        if rb > ra:
            out.append((ea, ea + (rb - ra) * sc))
    return sorted(out)


def runs_to_edit(runs: Sequence[Tuple[float, float]], clock: Sequence[Sequence[float]],
                 room_offset: float = 0.0) -> List[Tuple[float, float]]:
    """Speech runs on a processed track (the guest leg's clock) moved onto
    the edit's clock: every part of a run the edit kept, where it plays."""
    out: List[Tuple[float, float]] = []
    for a, b in runs:
        ra_, rb_ = a + room_offset, b + room_offset
        for seg in clock or []:
            ra, rb, ea = float(seg[0]), float(seg[1]), float(seg[2])
            sc = float(seg[3]) if len(seg) > 3 else 1.0
            lo, hi = max(ra_, ra), min(rb_, rb)
            if hi > lo:
                out.append((ea + (lo - ra) * sc, ea + (hi - ra) * sc))
    return sorted(out)


def _intersect(runs: Sequence[Tuple[float, float]],
               regions: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
    out = []
    for a, b in runs:
        for lo, hi in regions:
            x, y = max(a, lo), min(b, hi)
            if y > x:
                out.append((x, y))
    return sorted(out)


def _complement(regions: Sequence[Tuple[float, float]], total: float) -> List[Tuple[float, float]]:
    out, at = [], 0.0
    for a, b in merge_spans(regions, gap=0.0):
        if a > at:
            out.append((at, a))
        at = max(at, b)
    if at < total:
        out.append((at, total))
    return out


def narration_regions(edit: dict, total_sec: float) -> List[Tuple[float, float]]:
    """Where the edit plays Mira alone (her narration, or a cut of her own
    track): the pieces the assembler marked, or, for an edit built before it
    marked them, everything the room's clock does not cover."""
    pieces = edit.get("pieces") or []
    if pieces:
        return [(float(p["from"]), float(p["to"])) for p in pieces
                if p.get("kind") in ("narration", "mira")]
    return _complement(clock_spans(edit.get("clock") or []), total_sec)


def guest_only_regions(edit: dict) -> List[Tuple[float, float]]:
    """Pieces cut from the guest's own track (a cold open): Mira is not heard."""
    return [(float(p["from"]), float(p["to"])) for p in edit.get("pieces") or []
            if p.get("kind") == "guest"]


def mira_only_regions(edit: dict) -> List[Tuple[float, float]]:
    """Pieces of Mira's narration or her own track: the guest is not heard."""
    return [(float(p["from"]), float(p["to"])) for p in edit.get("pieces") or []
            if p.get("kind") in ("narration", "mira")]


def _subtract(runs: Sequence[Tuple[float, float]],
              cut: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
    out = list(runs)
    for lo, hi in cut:
        nxt = []
        for a, b in out:
            if hi <= a or lo >= b:
                nxt.append((a, b))
                continue
            if a < lo:
                nxt.append((a, lo))
            if hi < b:
                nxt.append((hi, b))
        out = nxt
    return sorted(out)


def speech_on_edit(edit: dict, edit_runs: Sequence[Tuple[float, float]],
                   mira_runs: Sequence[Tuple[float, float]],
                   guest_runs: Sequence[Tuple[float, float]],
                   total_sec: float) -> Dict[str, List[Tuple[float, float]]]:
    """Who is speaking when, on the edit's clock.

    ``edit_runs`` is speech found in the edit file itself; ``mira_runs`` and
    ``guest_runs`` are speech on the processed tracks (the guest leg's
    clock). Mira speaks where her track does (moved onto the edit) and
    where the edit plays her narration and has speech; the guest where their
    track does. Returns ``{"mira_talk": ..., "mira": ..., "guest": ...}``:
    ``mira_talk`` closes on her pauses (her picture), the other two hold the
    floor across them (the border)."""
    clock = edit.get("clock") or []
    offset = float(edit.get("room_offset_sec") or 0.0)
    mira = runs_to_edit(mira_runs, clock, offset)
    mira = _subtract(mira, guest_only_regions(edit))
    mira += _intersect(edit_runs, narration_regions(edit, total_sec))
    guest = _subtract(runs_to_edit(guest_runs, clock, offset), mira_only_regions(edit))
    return {"mira_talk": merge_spans(mira, MIRA_GAP_SEC, MIN_TALK_SEC),
            "mira": merge_spans(mira, FLOOR_GAP_SEC, MIN_TALK_SEC),
            "guest": merge_spans(guest, FLOOR_GAP_SEC, MIN_TALK_SEC)}


def shift_spans(spans: Sequence[Tuple[float, float]], start: float, end: float
                ) -> List[Tuple[float, float]]:
    """``spans`` inside ``[start, end)``, on a clock that starts at ``start``."""
    out = []
    for a, b in spans:
        x, y = max(a, start), min(b, end)
        if y > x:
            out.append((round(x - start, 2), round(y - start, 2)))
    return out


def enable_expr(spans: List[Tuple[float, float]]) -> str:
    """An ffmpeg ``enable`` expression true inside any span (0 when none)."""
    if not spans:
        return "0"
    return "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in spans)


def mira_segments(talk: Sequence[Tuple[float, float]], total_frames: int,
                  fps: int = FPS) -> List[dict]:
    """Mira's picture as runs of frames: ``{"start", "end", "talk"}``. Each
    talking run starts the loop from its first frame."""
    out: List[dict] = []
    at = 0
    for a, b in sorted(talk):
        f0, f1 = max(at, frames(a, fps)), min(total_frames, frames(b, fps))
        if f1 <= f0:
            continue
        if f0 > at:
            out.append({"start": at, "end": f0, "talk": False})
        out.append({"start": f0, "end": f1, "talk": True})
        at = f1
    if at < total_frames:
        out.append({"start": at, "end": total_frames, "talk": False})
    return out


#: When she stops, her face eases back to rest over this many frames instead
#: of snapping from wherever the loop was (a sixth of a second).
SETTLE_FRAMES = 5


def mira_plan(talk: Sequence[Tuple[float, float]], total_frames: int, loop_frames: int,
              fps: int = FPS) -> List[dict]:
    """The parts Mira's track is joined from, in order: ``{"part": "talk",
    "at", "n"}`` (the loop from frame ``at``), ``{"part": "settle", "from",
    "n"}`` (easing from loop frame ``from`` to rest) and ``{"part": "rest",
    "n"}``. Exactly ``total_frames`` frames; a part never runs past the end of
    the loop (a long answer is the loop again, from its first frame)."""
    out: List[dict] = []
    last = None
    for seg in mira_segments(talk, total_frames, fps):
        n = seg["end"] - seg["start"]
        if seg["talk"]:
            at = 0
            while n > 0:
                take = min(n, loop_frames - at)
                out.append({"part": "talk", "at": at, "n": take})
                n -= take
                last = at + take - 1
                at = 0
            continue
        if last is not None and n > SETTLE_FRAMES:
            out.append({"part": "settle", "from": last, "n": SETTLE_FRAMES})
            n -= SETTLE_FRAMES
        last = None
        while n > 0:
            take = min(n, loop_frames)
            out.append({"part": "rest", "n": take})
            n -= take
    return out


def clip_windows(pkg: Optional[dict], run: Optional[dict], n: int = SHORTS_PER_EPISODE,
                 total_sec: Optional[float] = None) -> List[dict]:
    """The moments to cut as Shorts: the editorial pass's clip suggestions,
    moved from the room's clock to the edit's, each at most
    ``SHORT_MAX_SEC`` and at least ``SHORT_MIN_SEC``, none overlapping.
    ``[{"start", "seconds", "title"}]``."""
    from edit_transcript import room_to_edit
    edit = ((((run or {}).get("grok_session_log") or {}).get("tracks") or {})
            .get("edit") or {})
    clock = edit.get("clock") or []
    out: List[dict] = []
    for clip in (pkg or {}).get("clip_suggestions") or []:
        if len(out) >= n:
            break
        if not isinstance(clip, dict) or clip.get("start") is None:
            continue
        try:
            start, end = float(clip["start"]), clip.get("end")
            moved = room_to_edit(clock, start) if clock else start
            moved_end = (room_to_edit(clock, float(end)) if clock else float(end)) \
                if end is not None else None
        except (TypeError, ValueError):
            continue
        if moved is None:
            continue
        seconds = (moved_end - moved) if moved_end and moved_end > moved else 45.0
        seconds = min(SHORT_MAX_SEC, max(SHORT_MIN_SEC, seconds))
        if total_sec is not None:
            seconds = min(seconds, max(0.0, total_sec - moved))
            if seconds < SHORT_MIN_SEC:
                continue
        if any(moved < o["start"] + o["seconds"] and o["start"] < moved + seconds for o in out):
            continue
        title = str(clip.get("title") or clip.get("hook") or clip.get("label")
                    or clip.get("quote") or "").strip()
        out.append({"start": round(moved, 2), "seconds": round(seconds, 2), "title": title[:90]})
    return out


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _run(cmd: list, timeout: int = 3600) -> None:
    subprocess.run([str(c) for c in cmd], check=True, capture_output=True,
                   text=True, timeout=timeout)


ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
          "-r", str(FPS)]


def name_card(guest: str, subtitle: str, out: Path, size: Tuple[int, int] = (TILE_W, TILE_H)) -> Path:
    """The guest's tile while the camera has nothing to show."""
    from PIL import Image, ImageDraw, ImageFont
    w, h = size
    img = Image.new("RGB", (w, h), (22, 29, 51))
    draw = ImageDraw.Draw(img)

    def font(path: Path, px: int):
        try:
            return ImageFont.truetype(str(path), px)
        except OSError:
            return ImageFont.load_default()

    big, small = font(FONT_BOLD, 54), font(FONT_MEDIUM, 30)
    y = h // 2 - (40 if subtitle else 20)
    for text, f, fill, dy in ((guest, big, (241, 245, 249), 0),
                              (subtitle, small, (148, 163, 184), 78)):
        if not text:
            continue
        tw = draw.textlength(text, font=f)
        draw.text(((w - tw) / 2, y + dy - 27), text, font=f, fill=fill)
    img.save(out)
    return out


def render_guest_tile(runs: List[dict], take_paths: List[Path], card: Path,
                      workdir: Path, fps: int = FPS,
                      size: Tuple[int, int] = (TILE_W, TILE_H)) -> Path:
    """One clip per run at the tile's size (the camera cropped to fill it),
    joined without re-encoding."""
    w, h = size
    workdir.mkdir(parents=True, exist_ok=True)
    scale = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
             f"crop={w}:{h},setsar=1,fps={fps}")
    listing = workdir / "list.txt"
    with listing.open("w") as fh:
        for k, r in enumerate(runs):
            n = r["end"] - r["start"]
            out = workdir / f"r{k:05d}.mp4"
            if r.get("card"):
                cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", fps,
                       "-i", card, "-vf", f"scale={w}:{h},setsar=1"]
            else:
                cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{r['at']:.3f}",
                       "-i", take_paths[r["take"]], "-an", "-vf", scale]
            _run(cmd + ["-frames:v", n, *ENCODE, out])
            fh.write(f"file '{out.name}'\n")
    tile = workdir / "guest_tile.mp4"
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", listing,
          "-c", "copy", tile])
    return tile


def _even(x: float) -> int:
    return int(round(x / 2.0)) * 2


def mira_crop(size: Tuple[int, int]) -> str:
    """The crop of her portrait that fills a ``size`` tile, head and
    shoulders, scaled to it."""
    w, h = size
    ch = min(MIRA_SRC_H, _even(MIRA_SRC_W * h / w))
    cw = MIRA_SRC_W if ch < MIRA_SRC_H else _even(MIRA_SRC_H * w / h)
    y = max(0, min(MIRA_FACE_Y, MIRA_SRC_H - ch))
    x = (MIRA_SRC_W - cw) // 2
    return f"crop={cw}:{ch}:{x}:{y},scale={w}:{h}:flags=lanczos,unsharp=5:5:0.6"


def render_mira_track(talk: Sequence[Tuple[float, float]], total_sec: float,
                      size: Tuple[int, int], workdir: Path, fps: int = FPS) -> Path:
    """Mira's tile for the whole clip: the still while she is quiet, the
    talking loop (from its first frame, which is the still) while she
    speaks, easing back to rest when she stops. The parts are rendered once
    as every-frame-a-keyframe clips, so the joins are exact."""
    workdir.mkdir(parents=True, exist_ok=True)
    vf = f"{mira_crop(size)},setsar=1,fps={fps}"
    intra = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
             "-g", "1", "-keyint_min", "1", "-r", str(fps)]
    loop_frames = frames(10.0, fps)
    talk_clip, still_clip = workdir / "talk.mp4", workdir / "still.mp4"
    _run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", MIRA_LOOP, "-an",
          "-vf", vf, "-frames:v", loop_frames, *intra, talk_clip])
    # The still is the loop's own first frame, taken through the same scale,
    # so the cut into speech is seamless (the published jpg is a different
    # encode of that frame and its colours sit a shade apart).
    rest = workdir / "rest.png"
    _run(["ffmpeg", "-y", "-v", "error", "-i", MIRA_LOOP, "-vf", vf, "-frames:v", 1, rest])
    _run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", fps, "-i", rest,
          "-vf", "setsar=1,format=yuv420p", "-frames:v", loop_frames, *intra, still_clip])
    total = frames(total_sec, fps)
    listing = workdir / "mira.txt"
    settles: Dict[int, Path] = {}

    def settle(at: int) -> Path:
        # One short clip per loop frame she can stop on, made when first needed.
        if at not in settles:
            last = workdir / f"stop_{at:04d}.png"
            _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at / fps:.4f}", "-i", talk_clip,
                  "-frames:v", 1, last])
            clip = workdir / f"settle_{at:04d}.mp4"
            w = f"min(1,(N+1)/{SETTLE_FRAMES + 1})"
            _run(["ffmpeg", "-y", "-v", "error",
                  "-loop", "1", "-framerate", fps, "-i", last,
                  "-loop", "1", "-framerate", fps, "-i", rest,
                  "-filter_complex", f"[0:v][1:v]blend=all_expr='A*(1-{w})+B*{w}',"
                                     "setsar=1,format=yuv420p[v]",
                  "-map", "[v]", "-frames:v", SETTLE_FRAMES, *intra, clip])
            settles[at] = clip
        return settles[at]

    with listing.open("w") as fh:
        for part in mira_plan(talk, total, loop_frames, fps):
            if part["part"] == "talk":
                src, start = talk_clip, part["at"]
            elif part["part"] == "settle":
                src, start = settle(part["from"]), 0
            else:
                src, start = still_clip, 0
            fh.write(f"file '{src.name}'\ninpoint {start / fps:.6f}\n"
                     f"outpoint {(start + part['n']) / fps:.6f}\n")
    out = workdir / "mira_track.mp4"
    # Joined exactly (every part is all keyframes) and encoded once more at a
    # quality the final picture cannot tell from the source: a still face at
    # normal quality pulses on every keyframe.
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", listing,
          "-frames:v", total, "-c:v", "libx264", "-preset", "veryfast", "-crf", "10",
          "-pix_fmt", "yuv420p", "-r", str(fps), out])
    return out


def _text_file(workdir: Path, name: str, text: str) -> Path:
    p = workdir / name
    p.write_text(text, encoding="utf-8")
    return p


def _color(brand: str) -> str:
    return "0x" + brand.lstrip("#") if brand else "0x7C3AED"


def compose(guest_tile: Path, audio: Path, out: Path, *, total_sec: float,
            spans: Dict[str, List[Tuple[float, float]]], guest_name: str,
            show_name: str, brand: str, workdir: Path,
            mira_track: Optional[Path] = None) -> Path:
    """The long-form 1920x1080 picture with the episode's audio. Mira's tile
    is ``mira_track`` (rendered from ``spans["mira_talk"]`` when not given)."""
    color = _color(brand)
    if mira_track is None:
        mira_track = render_mira_track(spans.get("mira_talk") or spans.get("mira") or [],
                                       total_sec, (TILE_W, TILE_H), workdir / "mira")
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
        f"[1:v]setpts=PTS-STARTPTS,fps={FPS},setsar=1[m]",
        f"[bg][g]overlay=x={GUEST_X}:y={TILE_Y}:eof_action=pass[a]",
        f"[a][m]overlay=x={MIRA_X}:y={TILE_Y}[b]",
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
          "-i", mira_track,
          "-i", audio,
          "-filter_complex", graph,
          "-map", "[v]", "-map", "2:a",
          *ENCODE, "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
          "-t", f"{total_sec:.3f}", "-movflags", "+faststart", out], timeout=7200)
    return out


#: Captions sit in the band under Mira's tile, clear of both pictures.
SHORT_CAPTION_STYLE = ("FontName=DejaVu Sans,FontSize=54,Bold=-1,PrimaryColour=&H00FFFFFF,"
                       "OutlineColour=&H00000000,BackColour=&H99000000,BorderStyle=3,"
                       "Outline=4,Shadow=0,Alignment=2,MarginV=350")


def compose_vertical(guest_tile: Path, mira_track: Path, audio: Path, out: Path, *,
                     total_sec: float, spans: Dict[str, List[Tuple[float, float]]],
                     guest_name: str, show_name: str, brand: str, workdir: Path,
                     captions: Optional[Path] = None) -> Path:
    """The 1080x1920 picture: the show's name over the guest, the guest
    stacked over Mira, the words at the bottom."""
    color = _color(brand)
    gx, gy, gw, gh = V_GUEST
    mx, my, mw, mh = V_MIRA
    title = _text_file(workdir, "v_title.txt", show_name)
    sub = _text_file(workdir, "v_sub.txt", f"with {guest_name} · nerranetwork.com")
    gname = _text_file(workdir, "v_guest.txt", guest_name)
    mname = _text_file(workdir, "v_mira.txt", "Mira · AI host")
    font_b, font_m = str(FONT_BOLD), str(FONT_MEDIUM)

    def box(x: int, y: int, w: int, h: int, side: str) -> str:
        return (f"drawbox=x={x - V_BORDER}:y={y - V_BORDER}:w={w + 2 * V_BORDER}:"
                f"h={h + 2 * V_BORDER}:color={color}:t={V_BORDER}:"
                f"enable='{enable_expr(spans.get(side) or [])}'")

    def label(textfile: Path, x: int, y: int) -> str:
        return (f"drawtext=fontfile='{font_b}':textfile='{textfile}':x={x + 24}:y={y - 64}:"
                "fontsize=36:fontcolor=0xF8FAFC:box=1:boxcolor=0x0B1020@0.65:boxborderw=12")

    chain = [box(gx, gy, gw, gh, "guest"), box(mx, my, mw, mh, "mira"),
             f"drawtext=fontfile='{font_b}':textfile='{title}':x=(w-tw)/2:y=56:"
             "fontsize=58:fontcolor=0xF8FAFC",
             f"drawtext=fontfile='{font_m}':textfile='{sub}':x=(w-tw)/2:y=128:"
             "fontsize=34:fontcolor=0x94A3B8",
             label(gname, gx, gy + gh), label(mname, mx, my + mh)]
    if captions is not None and captions.exists() and captions.stat().st_size > 0:
        escaped = str(captions).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        chain.append(f"subtitles='{escaped}':force_style='{SHORT_CAPTION_STYLE}'")
    graph = ";".join([
        f"color=c={GROUND}:s={VW}x{VH}:r={FPS}:d={total_sec:.3f}[bg]",
        f"[0:v]setpts=PTS-STARTPTS,fps={FPS}[g]",
        f"[1:v]setpts=PTS-STARTPTS,fps={FPS},setsar=1[m]",
        f"[bg][g]overlay=x={gx}:y={gy}:eof_action=pass[a]",
        f"[a][m]overlay=x={mx}:y={my}[b]",
        "[b]" + ",".join(chain) + "[v]",
    ])
    _text_file(workdir, "v_graph.txt", graph)
    _run(["ffmpeg", "-y", "-v", "error",
          "-i", guest_tile, "-i", mira_track, "-i", audio,
          "-filter_complex", graph, "-map", "[v]", "-map", "2:a",
          *ENCODE, "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
          "-t", f"{total_sec:.3f}", "-movflags", "+faststart", out], timeout=3600)
    return out


def short_captions(audio: Path, workdir: Path, seconds: float,
                   vocabulary: Sequence[str] = ()) -> Optional[Path]:
    """Word-by-word captions for a Short, from the clip's own audio (the
    network's Shorts style: the spoken word lit as it is said)."""
    try:
        from engine.captions import transcript_to_ass_window
        from engine.transcripts import generate_transcript
        result = generate_transcript(audio, workdir, "short", model_size="base",
                                     language="en", vocabulary=list(vocabulary))
        if result is None:
            return None
        ass = workdir / "short.ass"
        transcript_to_ass_window(Path(result.json_path), ass, window_start_seconds=0.0,
                                 window_duration_seconds=max(0.1, seconds))
        return ass
    except Exception as exc:  # noqa: BLE001 — a Short without captions is still a Short
        print(f"captions failed (non-fatal): {exc}", file=sys.stderr)
        return None


def render_short(*, window: dict, runs: List[dict], take_paths: List[Path],
                 spans: Dict[str, List[Tuple[float, float]]], audio: Path,
                 guest_name: str, subtitle: str, show_name: str, brand: str,
                 workdir: Path, out: Path, vocabulary: Sequence[str] = ()) -> Path:
    """One vertical Short for ``window`` (``start``/``seconds`` on the edit's
    clock) of an edit whose guest tile is planned as ``runs``."""
    workdir.mkdir(parents=True, exist_ok=True)
    start, seconds = float(window["start"]), float(window["seconds"])
    f0, f1 = frames(start), frames(start) + frames(seconds)
    clip_audio = workdir / "clip.wav"
    _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-i", audio,
          "-t", f"{seconds:.3f}", "-ac", "2", "-ar", "48000", clip_audio])
    local = {k: shift_spans(v, start, start + seconds) for k, v in spans.items()}
    card = name_card(guest_name, subtitle, workdir / "card.png", size=V_GUEST[2:])
    tile = render_guest_tile(slice_runs(runs, f0, f1), take_paths, card, workdir / "tile",
                             size=V_GUEST[2:])
    mira = render_mira_track(local.get("mira_talk") or [], seconds, V_MIRA[2:], workdir / "mira")
    captions = short_captions(clip_audio, workdir / "captions", seconds, vocabulary)
    return compose_vertical(tile, mira, clip_audio, out, total_sec=seconds, spans=local,
                            guest_name=guest_name, show_name=show_name, brand=brand,
                            workdir=workdir, captions=captions)


# ---------------------------------------------------------------------------
# The job
# ---------------------------------------------------------------------------

def video_allowed(pkg: Optional[dict]) -> bool:
    """A guest who asked for audio only gets no video, anywhere."""
    return not (pkg and pkg.get("guest_video_ok") is False)


def measured_speech(edit: dict, tracks: dict, edit_audio: Path,
                    total_sec: float) -> Optional[Dict[str, List[Tuple[float, float]]]]:
    """Who speaks when, measured from the audio (``speech_on_edit``), or
    None when the processed tracks cannot be read."""
    import turn_cues
    processed = tracks.get("processed") or {}
    if not processed.get("mira"):
        return None
    try:
        edit_runs = turn_cues.speech_runs(turn_cues.frame_db(turn_cues.load_audio(str(edit_audio))))
        mira_runs = turn_cues.speech_runs(turn_cues.frame_db(turn_cues.load_audio(processed["mira"])))
        guest_runs: List[Tuple[float, float]] = []
        for role in ("guest", "host"):
            if processed.get(role):
                guest_runs += turn_cues.speech_runs(
                    turn_cues.frame_db(turn_cues.load_audio(processed[role])))
    except Exception as exc:  # noqa: BLE001 — the transcript is the fallback
        print(f"speech could not be measured from the tracks: {exc}", file=sys.stderr)
        return None
    return speech_on_edit(edit, edit_runs, mira_runs, sorted(guest_runs), total_sec)


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
    shorts: List[dict] = []

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
        spans = measured_speech(edit, tracks, audio, total)
        if spans is None:
            logger.warning("speaker timing from the transcript (the tracks could not be read)")
            spans = speaker_spans((pkg or {}).get("edit_transcript") or "", total)
            spans["mira_talk"] = spans.get("mira") or []
        card = name_card(guest, subtitle, work / "card.png")
        tile = render_guest_tile(runs, take_paths, card, work / "tile")
        name = Path(edit["url"].split("?")[0]).stem + "_video.mp4"
        out = compose(tile, audio, work / name, total_sec=total, spans=spans,
                      guest_name=guest, show_name=show.name, brand=show.brand_color,
                      workdir=work)
        url = r2_upload(out, show.r2_key("video", name))
        for k, window in enumerate(clip_windows(pkg, run, total_sec=total)):
            try:
                sname = Path(edit["url"].split("?")[0]).stem + f"_short{k + 1}.mp4"
                short = render_short(window=window, runs=runs, take_paths=take_paths,
                                     spans=spans, audio=audio, guest_name=guest,
                                     subtitle=subtitle, show_name=show.name,
                                     brand=show.brand_color, workdir=work / f"short{k}",
                                     out=work / sname, vocabulary=[guest, show.name, "Mira"])
                shorts.append({**window, "url": r2_upload(short, show.r2_key("video", sname))})
                logger.info("short %d: %.0fs at %.0fs -> %s", k + 1, window["seconds"],
                            window["start"], shorts[-1]["url"])
            except Exception:  # noqa: BLE001 — the long form stands without it
                logger.exception("short %d not rendered (non-fatal)", k + 1)

    fresh = (sb_select("interview_runs", f"id=eq.{run_id}") or [run])[0]
    log = dict(fresh.get("grok_session_log") or {})
    tracks = dict(log.get("tracks") or {})
    edit_now = dict(tracks.get("edit") or {})
    edit_now.update({"video_url": url, "video_of": edit["url"],
                     "video_built_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                     "video_on_camera": round(on_camera / max(1, frames(total)), 3),
                     "shorts": shorts, "shorts_of": edit["url"]})
    tracks["edit"] = edit_now
    log["tracks"] = tracks
    sb_update("interview_runs", f"id=eq.{run_id}", {"grok_session_log": log})
    logger.info("video version of run %s -> %s (+%d shorts)", run_id, url, len(shorts))
    return url


def preview_for_run(run_id: str) -> Optional[Dict[str, str]]:
    """A test room's pictures, uncut: the room's own stereo recording (guest
    left, Mira right) with the guest's camera placed against the left side,
    so the operator can watch what the camera gave before guests get it: the
    long form of the whole room, and a vertical Short of its first minute. A
    test room is never post-processed, so there is no edit to follow; the
    whole room is the clock. Uploaded beside the room's raw files, never
    published anywhere."""
    from common import logger, r2_upload, sb_select, show_for
    import requests
    from video_take import build_video_track, video_takes

    run = (sb_select("interview_runs", f"id=eq.{run_id}") or [None])[0]
    if not run:
        raise SystemExit(f"no interview_runs row {run_id}")
    stereo = str(run.get("recording_guest_url") or "")
    if not stereo:
        logger.info("run %s has no room recording to preview", run_id)
        return None
    interview = (sb_select("interviews", f"id=eq.{run.get('interview_id')}") or [{}])[0]
    app = (sb_select("guest_applications",
                     f"id=eq.{interview.get('application_id')}") or [{}])[0]
    show = show_for(interview, app)
    from common import r2_list, r2_put_json, r2_read_json
    from video_take import discover_takes

    def discover():
        return discover_takes(r2_list(show.r2_key("local", run_id, "guest-video") + "/"),
                              r2_read_json, put_json=r2_put_json)
    if not (((run.get("grok_session_log") or {}).get("tracks") or {}).get("video")
            or video_takes(run) or discover()):
        logger.info("run %s recorded no camera — nothing to preview", run_id)
        return None
    with tempfile.TemporaryDirectory(prefix="render_preview_") as tmp:
        work = Path(tmp)
        room = work / "room.mp3"
        with requests.get(stereo, stream=True, timeout=900) as resp:
            resp.raise_for_status()
            with room.open("wb") as fh:
                for chunk in resp.iter_content(1 << 16):
                    fh.write(chunk)
        ref = work / "guest_ref.wav"
        _run(["ffmpeg", "-y", "-v", "error", "-i", room, "-af", "pan=mono|c0=c0",
              "-ar", 16000, ref])
        video = (((run.get("grok_session_log") or {}).get("tracks") or {}).get("video")
                 or build_video_track(run, ref, work / "takes",
                                      upload=lambda path, _key: str(path),
                                      key_for=lambda name: name, discover=discover))
        if not video or not video.get("takes"):
            logger.info("run %s: the camera could not be placed on the room", run_id)
            return None
        takes = video["takes"]
        take_paths = [Path(t["url"]) if not str(t["url"]).startswith("http")
                      else _fetch(t["url"], work / f"take_{i}.mkv") for i, t in enumerate(takes)]
        out = preview_render(room, takes, take_paths, work,
                             guest_name=str(app.get("name") or "Guest"),
                             show_name=show.name, brand=show.brand_color,
                             name=f"{run_id}_preview")
        urls = {kind: r2_upload(path, show.r2_key("raw", path.name)) for kind, path in out.items()}
    logger.info("preview of test room %s -> %s", run_id, urls)
    return urls


def preview_render(room: Path, takes: List[dict], take_paths: List[Path], work: Path, *,
                   guest_name: str, show_name: str, brand: str, name: str,
                   short_seconds: float = 60.0) -> Dict[str, Path]:
    """The long form and a first-minute Short of a test room (no edit: the
    room is the clock, its left side the guest and its right side Mira)."""
    import turn_cues
    guest = turn_cues.load_audio((str(room), 0))
    mira = turn_cues.load_audio((str(room), 1))
    total = len(guest) / float(turn_cues.SR)
    edit = {"clock": [[0.0, total, 0.0]], "room_offset_sec": 0.0}
    spans = speech_on_edit(edit, [], turn_cues.speech_runs(turn_cues.frame_db(mira)),
                           turn_cues.speech_runs(turn_cues.frame_db(guest)), total)
    runs = plan_guest_track(edit["clock"], 0.0, takes, total)
    # The room's recording keeps each side on its own channel; a viewer
    # hears both voices in both ears.
    heard = work / "room_heard.wav"
    _run(["ffmpeg", "-y", "-v", "error", "-i", room, "-af", "pan=mono|c0=c0+c1",
          "-ar", 48000, heard])
    card = name_card(guest_name, "test room", work / "card.png")
    tile = render_guest_tile(runs, take_paths, card, work / "tile")
    long_form = compose(tile, heard, work / f"{name}_video.mp4", total_sec=total, spans=spans,
                        guest_name=guest_name, show_name=show_name, brand=brand, workdir=work)
    window = {"start": 0.0, "seconds": min(short_seconds, total)}
    short = render_short(window=window, runs=runs, take_paths=take_paths, spans=spans,
                         audio=heard, guest_name=guest_name, subtitle="test room",
                         show_name=show_name, brand=brand, workdir=work / "short",
                         out=work / f"{name}_short.mp4", vocabulary=[guest_name, show_name, "Mira"])
    return {"long": long_form, "short": short}


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


def tell_patrick(url: Any, run_id: str, preview: bool = False) -> None:
    from common import OPERATOR_EMAIL, logger, send_email
    if preview:
        links = url if isinstance(url, dict) else {"long": url}
        subject = "The test room's video is ready to watch"
        body = (f"<p>Hi Patrick,</p><p>The camera from test room <code>{run_id}</code>, "
                f"beside my picture, uncut: <a href=\"{links.get('long')}\">the long version</a>"
                + (f" and <a href=\"{links['short']}\">a vertical Short of its first minute</a>"
                   if links.get("short") else "")
                + ". They are published nowhere. If they look right, the shows can record "
                "guests' cameras (<code>local_video: true</code>).</p><p>— Mira</p>")
    else:
        subject = "The video version is ready to watch"
        body = (f"<p>Hi Patrick,</p><p>The video version of run <code>{run_id}</code> "
                f"is cut: <a href=\"{url}\">watch it here</a>. It follows the edit "
                "you reviewed, frame for frame, with the Shorts cut from its suggested "
                "moments. They go to YouTube, X and the episode's page when you publish, "
                "unless the guest asked for audio only.</p><p>— Mira</p>")
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
