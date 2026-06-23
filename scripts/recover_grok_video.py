#!/usr/bin/env python3
"""Recover a Grok Video episode from already-submitted clip request IDs.

When the per-episode pipeline submits its Grok Video clips but dies before
downloading them (e.g. the 2026-06-23 Tesla Ep519 pipeline timeout), the
clips may still be retrievable server-side: each was submitted and has a
``request_id`` logged, and the status endpoint
``GET https://api.x.ai/v1/videos/{request_id}`` returns the finished clip's
(temporary) URL once it has rendered.

This script takes a list of ``clip_id request_id`` pairs, polls each status
endpoint, downloads whatever has completed, stitches them in order, and (if
given the episode audio) composites the audio onto the video — producing the
full-length MP4 the pipeline would have made.

IMPORTANT — the clip result URLs are temporary. If too much time has passed
the clips may no longer be retrievable; the script reports per-clip status so
you can see how many survived. Nothing here is destructive.

Usage:
    # Use the embedded Tesla Ep519 (2026-06-23) request IDs:
    GROK_API_KEY=... python scripts/recover_grok_video.py \
        --audio https://audio.nerranetwork.com/tesla/Tesla_Shorts_Time_Pod_Ep519_20260623.mp3 \
        --out Tesla_Shorts_Time_Pod_Ep519_20260623_video.mp4

    # Or supply your own list (one "clip_id request_id" per line, "#" comments ok):
    GROK_API_KEY=... python scripts/recover_grok_video.py \
        --requests my_request_ids.txt --audio episode.mp3 --out out.mp4

Requires: GROK_API_KEY (or XAI_API_KEY) in the environment, and ffmpeg on PATH.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.grok_video import (  # noqa: E402 (after sys.path bootstrap)
    GrokVideoError,
    _check_video_status_once,
    _composite_video_with_audio,
    _download_video,
    _stitch_videos_ffmpeg,
)

# Tesla Shorts Time Ep519 (2026-06-23) — the 46 clips submitted before the
# pipeline timed out, in script order (clip_id, request_id). Recovered from
# the failed run's logs.
EP519_REQUESTS = [
    ("ep519_clip00", "f7c995bc-ff2e-93c1-a402-dd6b29f81cf0"),
    ("ep519_clip01", "7b47df6a-a5b0-9781-affe-11212b12019d"),
    ("ep519_clip02", "e277dcef-1f14-9370-a90b-67cd14c17a08"),
    ("ep519_clip03", "0b5e3610-763f-96a9-b31e-2c1de5a44944"),
    ("ep519_clip04", "a39b9d1e-701a-928f-9e8d-798144abe48a"),
    ("ep519_clip05", "da43ccae-7cd4-9e51-82c4-f46dbd429980"),
    ("ep519_clip06", "096b6b08-c20d-950d-afaa-7a4f5f0c6c2b"),
    ("ep519_clip07", "098e05cf-9ccf-99bd-9b6e-cef8b4efb645"),
    ("ep519_clip08", "6e5e6438-50c1-9ef9-9764-598c2e641985"),
    ("ep519_clip09", "6a051bc0-5ce0-9f1f-bb83-5e2a885492f3"),
    ("ep519_clip10", "7678d0f6-59cd-94ff-84b7-c1730c591f1a"),
    ("ep519_clip11", "fd8ca420-ddf4-9e47-bdfb-393c7ab3683b"),
    ("ep519_clip12", "d66e6016-e41a-9faf-8185-1b96392c78b0"),
    ("ep519_clip13", "163ab06f-2e58-991f-a0be-5587a0069f74"),
    ("ep519_clip14", "b7efd621-309c-9da3-8deb-00f2645327bd"),
    ("ep519_clip15", "e02934c5-8b52-9dd8-ad71-6aa032369841"),
    ("ep519_clip16", "0eb1e7a4-d8e9-9639-b6af-4420d348534d"),
    ("ep519_clip17", "be7e2652-3d5a-9f6a-9f61-5684a51a4d56"),
    ("ep519_clip18", "56bc2fe9-eaa7-9961-a36f-cb6666fb4b10"),
    ("ep519_clip19", "84f67d7e-8622-9a54-a2a9-56bd3d18d668"),
    ("ep519_clip20", "f50c89f6-d3ab-983f-acf9-e5c1e868aa5d"),
    ("ep519_clip21", "a5945ebd-29ac-9c50-b364-92b28b9497ff"),
    ("ep519_clip22", "958a814e-fe44-97b7-a79e-0f029bd7b5e7"),
    ("ep519_clip23", "1920effa-326d-9eb8-b1ce-03fafad84281"),
    ("ep519_clip24", "bad1e95e-1928-973a-b581-6f1d61506a89"),
    ("ep519_clip25", "c0432406-1d97-9166-b6e5-68a44c3aaaed"),
    ("ep519_clip26", "78c991ab-56c9-9384-b8d3-be7cf20497b5"),
    ("ep519_clip27", "ce467d1e-8296-91ec-9ba8-bf96f84d54f2"),
    ("ep519_clip28", "afbcd9fd-f8d6-9e3e-84e1-37db8c4a5f20"),
    ("ep519_clip29", "4ff0c50a-d905-92f9-9a8e-9a6240a2e8ad"),
    ("ep519_clip30", "d09ffe5f-35b5-96ed-8740-1e07992a4561"),
    ("ep519_clip31", "ffa73f0c-3067-9d0a-8511-7c92f0428aeb"),
    ("ep519_clip32", "8c5d5558-aad1-97a1-a835-b04fef8e74fa"),
    ("ep519_clip33", "4ab93e72-ecf2-9498-96f7-8e15927bd907"),
    ("ep519_clip34", "c3520bfa-2dd0-92c6-9995-3c2d1a6569ea"),
    ("ep519_clip35", "8b183210-912d-984b-92d4-8b8ee26ef818"),
    ("ep519_clip36", "932bdcf4-1de1-94b8-9e75-42c1766dec3b"),
    ("ep519_clip37", "ec8fe772-02f8-9006-aed0-6f200cb6c860"),
    ("ep519_clip38", "05b98857-761c-9406-9f08-cebd6a52140c"),
    ("ep519_clip39", "0fda3cb2-3b7a-90be-9c4f-a66e659f3bee"),
    ("ep519_clip40", "5487b491-20fa-96d9-83ed-c8fd21add4c2"),
    ("ep519_clip41", "dad8bb29-b809-9890-bc21-0e57f4b768c6"),
    ("ep519_clip42", "376bf67a-2f65-9d2f-8d65-8a47dd5f52fa"),
    ("ep519_clip43", "c7032afb-dc88-9122-9704-cdec6fdec20a"),
    ("ep519_clip44", "6b7c8d3d-c4c0-94d4-a220-d9a14c31cc3b"),
    ("ep519_clip45", "03625e1c-c097-95d7-9bb9-e472eacb7715"),
]


def _load_requests(path: Path) -> list[tuple[str, str]]:
    """Parse a 'clip_id request_id' per-line file ('#' comments allowed)."""
    out: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) == 1:
            out.append((f"clip{len(out):02d}", parts[0]))
        else:
            out.append((parts[0], parts[1]))
    return out


def _resolve_audio(audio: str, work_dir: Path) -> Path | None:
    """Return a local path to the audio, downloading it if a URL was given."""
    if not audio:
        return None
    if audio.startswith(("http://", "https://")):
        dest = work_dir / "episode_audio.mp3"
        print(f"Downloading episode audio: {audio}")
        urlretrieve(audio, dest)  # noqa: S310 — operator-supplied URL
        return dest
    p = Path(audio)
    return p if p.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--requests", type=Path, help="File of 'clip_id request_id' lines (default: embedded Ep519)")
    ap.add_argument("--audio", default="", help="Episode audio (local path or URL) to composite onto the video")
    ap.add_argument("--out", type=Path, required=True, help="Output MP4 path")
    ap.add_argument("--workdir", type=Path, default=None, help="Scratch dir for clips (default: a temp dir)")
    ap.add_argument("--retries", type=int, default=3, help="Status-poll retries per clip if still pending")
    ap.add_argument("--retry-wait", type=float, default=10.0, help="Seconds between status retries")
    args = ap.parse_args()

    api_key = os.getenv("GROK_API_KEY", "").strip() or os.getenv("XAI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: set GROK_API_KEY (or XAI_API_KEY) in the environment.", file=sys.stderr)
        return 2

    requests = _load_requests(args.requests) if args.requests else list(EP519_REQUESTS)
    if not requests:
        print("ERROR: no request IDs to recover.", file=sys.stderr)
        return 2

    work_dir = args.workdir or Path(tempfile.mkdtemp(prefix="grok_video_recover_"))
    work_dir.mkdir(parents=True, exist_ok=True)
    print(f"Recovering {len(requests)} clip(s) into {work_dir}")

    downloaded: list[Path] = []
    pending: list[str] = []
    failed: list[str] = []

    for clip_id, request_id in requests:
        body = None
        for attempt in range(max(1, args.retries)):
            try:
                body = _check_video_status_once(request_id, api_key=api_key)
            except GrokVideoError as exc:
                print(f"  {clip_id} [{request_id}]: status error — {exc}")
                body = None
                break
            if body.get("status") == "completed":
                break
            if attempt < args.retries - 1:
                print(f"  {clip_id}: status={body.get('status')} — retrying in {args.retry_wait:.0f}s")
                time.sleep(args.retry_wait)

        if not body or body.get("status") != "completed":
            status = (body or {}).get("status", "unreachable")
            print(f"  {clip_id} [{request_id}]: NOT available (status={status})")
            (pending if status not in ("failed", "unreachable") else failed).append(clip_id)
            continue

        url = body.get("url")
        if not url:
            print(f"  {clip_id}: completed but no URL in response")
            failed.append(clip_id)
            continue

        local = work_dir / f"{clip_id}.mp4"
        if _download_video(url, local):
            downloaded.append(local)
            print(f"  {clip_id}: downloaded ✓")
        else:
            failed.append(clip_id)
            print(f"  {clip_id}: download failed")

    print(
        f"\nRecovered {len(downloaded)}/{len(requests)} clips "
        f"({len(pending)} still pending, {len(failed)} failed)."
    )
    if not downloaded:
        print("Nothing to stitch — the clips are no longer retrievable.", file=sys.stderr)
        return 1

    # Stitch in submission order (downloaded preserves the request order).
    stitched = work_dir / "stitched.mp4"
    if not _stitch_videos_ffmpeg(downloaded, stitched, cleanup=True):
        print("ERROR: stitching failed (is ffmpeg installed?).", file=sys.stderr)
        return 1

    audio_path = _resolve_audio(args.audio, work_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if audio_path and audio_path.exists():
        if _composite_video_with_audio(stitched, audio_path, args.out):
            print(f"\nDONE → {args.out} (video + episode audio)")
        else:
            stitched.replace(args.out)
            print(f"\nAudio composite failed; wrote video-only → {args.out}")
    else:
        if args.audio:
            print("WARNING: could not resolve --audio; writing video-only.", file=sys.stderr)
        stitched.replace(args.out)
        print(f"\nDONE → {args.out} (video only — pass --audio to add sound)")

    if len(downloaded) < len(requests):
        print(
            "NOTE: this is a PARTIAL recovery — some clips were missing, so the "
            "video is shorter than the audio (the composite uses -shortest)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
