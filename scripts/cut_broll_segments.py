#!/usr/bin/env python3
"""Auto-cut the interesting moments out of long source footage.

Source archives are long: NASA's "Isolated Launch Views" masters run
4-40 minutes each, and a render only wants a handful of ~7 s accents.
Reviewing that by hand every time is the thing this script exists to
avoid — it finds the moments mechanically, so the operator's job drops
to a quick sanity-watch of short candidates instead of scrubbing hours
of tape.

**How a moment is judged interesting.** One cheap ffmpeg pass samples
the video at 2 fps and reports each sampled frame's *scene score* — how
different it is from the previous sample. That single signal separates
the three things we care about:

* near-zero across a stretch → a locked-off hold or a slate (boring),
* a lone spike → a hard cut between shots (never cut ACROSS one: a
  b-roll accent containing an edit reads as a mistake),
* sustained mid-range → something is actually moving in frame, which
  for launch footage is the rocket. That is the signal we rank on.

No LLM, no per-episode cost, no API. The whole selection
(:func:`pick_segments`) is a pure function over the sampled scores, so
it is unit-tested against real measured shapes rather than by
eyeballing renders.

Segments are spread across the source (``--min-gap``) so five clips
from one launch aren't five near-identical seconds of the same ascent,
and the head of the file is skipped by default because that is
reliably a countdown slate or a title card.

Usage::

    # Cut ~5 candidates from every clip already downloaded:
    python scripts/cut_broll_segments.py nasa_broll/*.mp4 \\
        --out-dir broll_cuts --per-source 5

    # Watch the (short!) candidates, delete the duds, then publish:
    python scripts/build_broll_pool.py --show spacex broll_cuts/*.mp4

Attribution rides along: each cut inherits its source's credit line
from the fetch script's ``_provenance.json`` and writes a new one beside
the cuts, so ``build_broll_pool.py`` still finds it and the CC BY /
NASA credit reaches the YouTube description.

Requires ffmpeg + ffprobe on PATH.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("cut_broll_segments")

# Sampling rate for the motion probe. 2 fps is enough to characterise
# camera/subject motion and keeps the probe cheap on a 40-minute master.
SAMPLE_FPS = 2.0

# A sampled frame this different from the previous one is a hard cut,
# not motion. Segments never span one.
CUT_SCORE = 0.35

# Below this mean score a window is a static hold — a locked-off pad
# shot or a slate.
MIN_MOTION_SCORE = 0.008

DEFAULT_SEGMENT_SECONDS = 7.0
DEFAULT_PER_SOURCE = 5
DEFAULT_MIN_GAP_SECONDS = 20.0
DEFAULT_SKIP_HEAD_SECONDS = 8.0

_PTS_RE = re.compile(r"pts_time:(?P<t>[0-9]+(?:\.[0-9]+)?)")
_SCORE_RE = re.compile(r"lavfi\.scene_score=(?P<s>[0-9]+(?:\.[0-9]+)?)")


def parse_motion_output(text: str) -> List[Tuple[float, float]]:
    """Parse ``metadata=print`` output into ``[(time_s, score), …]``.

    ffmpeg emits a frame header line then the metadata line::

        frame:1    pts:1024   pts_time:0.5
        lavfi.scene_score=0.123456

    Pairs are matched in order; an unpaired trailing header is dropped.
    """
    times: List[float] = []
    scores: List[float] = []
    for line in (text or "").splitlines():
        m = _PTS_RE.search(line)
        if m:
            times.append(float(m.group("t")))
            continue
        m = _SCORE_RE.search(line)
        if m:
            scores.append(float(m.group("s")))
    return list(zip(times, scores))


def pick_segments(
    samples: Sequence[Tuple[float, float]],
    *,
    segment_s: float = DEFAULT_SEGMENT_SECONDS,
    max_segments: int = DEFAULT_PER_SOURCE,
    min_gap_s: float = DEFAULT_MIN_GAP_SECONDS,
    skip_head_s: float = DEFAULT_SKIP_HEAD_SECONDS,
    cut_score: float = CUT_SCORE,
    min_motion: float = MIN_MOTION_SCORE,
) -> List[Tuple[float, float, float]]:
    """Choose the most interesting non-overlapping windows.

    Pure function over ``(time, scene_score)`` samples. Returns
    ``[(start_s, end_s, mean_score), …]`` ordered best-first, with:

    * no window spanning a hard cut (score ≥ *cut_score*),
    * nothing inside the first *skip_head_s* (slates / countdown cards),
    * at least *min_gap_s* between chosen starts, so the picks come from
      different parts of the source instead of clustering on the single
      most energetic moment,
    * static windows (mean < *min_motion*) rejected outright — better to
      return three good clips than five padded with locked-off holds.
    """
    if not samples or segment_s <= 0 or max_segments <= 0:
        return []
    ordered = sorted(samples, key=lambda p: p[0])
    cuts = [t for t, s in ordered if s >= cut_score]
    last_t = ordered[-1][0]

    candidates: List[Tuple[float, float, float]] = []
    for start, _score in ordered:
        if start < skip_head_s:
            continue
        end = start + segment_s
        if end > last_t:
            break
        # Never cut across an edit.
        if any(start < c < end for c in cuts):
            continue
        inside = [s for t, s in ordered if start <= t < end and s < cut_score]
        if not inside:
            continue
        mean = sum(inside) / len(inside)
        if mean < min_motion:
            continue
        candidates.append((start, end, mean))

    # Greedy best-first with a spacing constraint.
    chosen: List[Tuple[float, float, float]] = []
    for cand in sorted(candidates, key=lambda c: -c[2]):
        if len(chosen) >= max_segments:
            break
        if any(abs(cand[0] - c[0]) < min_gap_s for c in chosen):
            continue
        chosen.append(cand)
    return chosen


def sample_motion(path: Path, *, fps: float = SAMPLE_FPS) -> List[Tuple[float, float]]:
    """Run the ffmpeg motion probe over *path*."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found on PATH")
    cmd = [
        "ffmpeg", "-nostats", "-i", str(path),
        "-vf", f"fps={fps},select='gte(scene,0)',metadata=print:file=-",
        "-an", "-f", "null", "-",
    ]
    proc = subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, timeout=1800,
    )
    # metadata=print writes to stdout; ffmpeg's own log goes to stderr.
    samples = parse_motion_output(proc.stdout)
    if not samples:
        samples = parse_motion_output(proc.stderr)
    return samples


def cut_segment(src: Path, start: float, end: float, dest: Path) -> None:
    """Extract ``[start, end)`` from *src* into *dest*."""
    cmd = [
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
        "-i", str(src),
        # Re-encode: a keyframe-aligned stream copy can drift several
        # seconds, which at accent length is the whole clip.
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-an", str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=900)  # noqa: S603


def _source_attribution(src: Path) -> str:
    """Credit line for *src* from a sibling ``_provenance.json``."""
    prov = src.parent / "_provenance.json"
    if not prov.exists():
        return ""
    try:
        rows = json.loads(prov.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    if not isinstance(rows, list):
        return ""
    for row in rows:
        if isinstance(row, dict) and row.get("file") == src.name:
            return str(row.get("attribution") or "").strip()
    return ""


def _write_provenance(out_dir: Path, rows: List[dict]) -> None:
    path = out_dir / "_provenance.json"
    existing: List[dict] = []
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = loaded
        except Exception:  # noqa: BLE001
            pass
    by_file = {r.get("file"): r for r in existing if isinstance(r, dict)}
    for row in rows:
        by_file[row["file"]] = row
    path.write_text(json.dumps(list(by_file.values()), indent=2),
                    encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="+", type=Path,
                    help="Long source videos to mine")
    ap.add_argument("--out-dir", default="broll_cuts", type=Path)
    ap.add_argument("--per-source", type=int, default=DEFAULT_PER_SOURCE,
                    help="max segments per source video")
    ap.add_argument("--segment-seconds", type=float,
                    default=DEFAULT_SEGMENT_SECONDS)
    ap.add_argument("--min-gap-seconds", type=float,
                    default=DEFAULT_MIN_GAP_SECONDS,
                    help="minimum spacing between picks within one source")
    ap.add_argument("--skip-head-seconds", type=float,
                    default=DEFAULT_SKIP_HEAD_SECONDS,
                    help="ignore the first N seconds (slates/countdowns)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report the chosen timecodes without cutting")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    total = 0
    for src in args.sources:
        if not src.exists():
            logger.error("%s: not found — skipped", src)
            continue
        if src.name == "_provenance.json":
            continue
        try:
            samples = sample_motion(src)
        except Exception as exc:  # noqa: BLE001
            logger.error("%s: motion probe failed (%s) — skipped", src, exc)
            continue
        if not samples:
            logger.warning("%s: no motion data (unreadable?) — skipped",
                           src.name)
            continue
        picks = pick_segments(
            samples,
            segment_s=args.segment_seconds,
            max_segments=args.per_source,
            min_gap_s=args.min_gap_seconds,
            skip_head_s=args.skip_head_seconds,
        )
        if not picks:
            logger.warning("%s: nothing above the motion floor — skipped "
                           "(a locked-off or slate-heavy source)", src.name)
            continue
        credit = _source_attribution(src)
        logger.info("%s: %d segment(s) from %.0f min of source",
                    src.name, len(picks), samples[-1][0] / 60)
        for idx, (start, end, score) in enumerate(picks, 1):
            stamp = f"{int(start // 60):02d}m{int(start % 60):02d}s"
            dest = out_dir / f"{src.stem[:48]}__{stamp}.mp4"
            logger.info("  %5.1fs → %5.1fs  motion=%.4f  %s",
                        start, end, score, dest.name)
            if args.dry_run:
                continue
            if dest.exists():
                logger.info("    skip (exists)")
                continue
            try:
                cut_segment(src, start, end, dest)
            except Exception as exc:  # noqa: BLE001
                logger.error("    cut failed: %s", exc)
                dest.unlink(missing_ok=True)
                continue
            total += 1
            row = {"file": dest.name, "source_file": src.name,
                   "start_s": round(start, 2), "end_s": round(end, 2),
                   "motion_score": round(score, 5)}
            if credit:
                row["attribution"] = credit
            rows.append(row)

    if rows:
        _write_provenance(out_dir, rows)
    if args.dry_run:
        logger.info("dry run — nothing written")
        return 0
    logger.info("cut %d segment(s) into %s — watch them (they're short), "
                "delete the duds, then publish the keepers with "
                "scripts/build_broll_pool.py", total, out_dir)
    return 0 if total else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logger.warning("interrupted")
        raise SystemExit(130)
