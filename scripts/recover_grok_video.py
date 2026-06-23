#!/usr/bin/env python3
"""Recover Grok Video clips that were generated but not (fully) used.

When the per-episode pipeline submits its Grok Video clips but dies before
downloading them (e.g. the 2026-06-23 Tesla Ep519 pipeline timeout), the
clips may still be retrievable server-side. Each clip was submitted and has a
``request_id``; the status endpoint ``GET https://api.x.ai/v1/videos/{id}``
returns the finished clip's (temporary) URL once it has rendered.

Three modes:

  1. --list-all       Enumerate EVERY video on the account via the xAI list
                      endpoint (best-effort) and download each into --out-dir.
                      This is the "get all clips that ran so far, across all
                      shows" path — it doesn't need any request IDs.

  2. --requests FILE  Retrieve a specific set of clips. FILE has one
                      "clip_id request_id" (or bare "request_id") per line;
                      "#" comments allowed. Harvest these from a run's logs —
                      see HARVESTING below.

  3. (default)        Retrieve the embedded Tesla Ep519 (2026-06-23) clips.

By default every retrieved clip is KEPT as an individual .mp4 in the output
dir. Pass --stitch (+ optional --audio) to also concatenate an ordered set
into one episode video.

IMPORTANT — clip result URLs are TEMPORARY. Clips from runs more than a day
or so old are likely already gone; the script reports per-clip status so you
can see how many survived. Nothing here is destructive.

HARVESTING request IDs from a run's logs (you have `gh`; this sandbox agent
does not have an xAI key, so run this yourself):

    gh run view <RUN_ID> --repo Planetterrian/nerranetwork --log \
      | grep -oE 'ep[0-9]+_clip[0-9]+ \(request_id=[0-9a-f-]+' \
      | sed -E 's/ \(request_id=/ /' > ep_requests.txt
    GROK_API_KEY=... python scripts/recover_grok_video.py \
      --requests ep_requests.txt --out-dir recovered/

Usage examples:
    # Everything the account still has:
    GROK_API_KEY=... python scripts/recover_grok_video.py --list-all --out-dir recovered/

    # The embedded Ep519 set, stitched with the published audio:
    GROK_API_KEY=... python scripts/recover_grok_video.py \
        --stitch --audio https://audio.nerranetwork.com/tesla/Tesla_Shorts_Time_Pod_Ep519_20260623.mp3 \
        --out Ep519_video.mp4 --out-dir recovered_ep519/

Requires: GROK_API_KEY (or XAI_API_KEY) in the environment. --stitch needs ffmpeg.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.grok_video import (  # noqa: E402 (after sys.path bootstrap)
    GROK_VIDEO_STATUS_ENDPOINT,
    GrokVideoError,
    _check_video_status_once,
    _composite_video_with_audio,
    _download_video,
    _extract_video_url,
    _is_terminal_failure,
    _is_terminal_success,
    _stitch_videos_ffmpeg,
)

# Tesla Shorts Time Ep519 (2026-06-23) — the 46 clips submitted before the
# pipeline timed out, in script order (clip_id, request_id). From the run log.
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

# SpaceX Daily Ep12 (2026-06-23) — the 12 clips submitted before that
# pipeline timed out, in script order. From the run log.
SPACEX_EP12_REQUESTS = [
    ("ep012_clip00", "6b2e91d5-07e0-9133-97a2-e6f8c631f4eb"),
    ("ep012_clip01", "e99f058c-781d-9b64-95fa-3390d9d9f307"),
    ("ep012_clip02", "4feefd20-2a7a-9b45-933e-a176c09512c6"),
    ("ep012_clip03", "b62a5624-e3c4-9d12-809d-5a5860a4c44b"),
    ("ep012_clip04", "0050ff95-a20e-9508-86f9-b7623f471966"),
    ("ep012_clip05", "53ba2b36-8d4c-9dd6-b56d-5732f239eebb"),
    ("ep012_clip06", "bfa19b55-03c7-9e0b-8edc-9e240bd0a2a8"),
    ("ep012_clip07", "6c552b94-f917-9217-8bf7-92a09a0db864"),
    ("ep012_clip08", "645d6892-8e9c-9293-9204-e9236764a545"),
    ("ep012_clip09", "757a0c39-1c31-91d6-a0ed-84196b3c490e"),
    ("ep012_clip10", "def29b63-bdb3-93bf-b09e-ca38ab121812"),
    ("ep012_clip11", "468520d4-b54c-9aa2-9f75-e24b52c259b6"),
]

# Episode audio (R2) for the embedded sets, for --stitch convenience.
EMBEDDED_SETS = {
    "tesla_ep519": (
        EP519_REQUESTS,
        "https://audio.nerranetwork.com/tesla/Tesla_Shorts_Time_Pod_Ep519_20260623.mp3",
    ),
    "spacex_ep12": (
        SPACEX_EP12_REQUESTS,
        "https://audio.nerranetwork.com/spacex/SpaceX_Daily_Ep012_20260623.mp3",
    ),
}


def _load_requests(path: Path) -> list[tuple[str, str]]:
    """Parse a 'clip_id request_id' (or bare 'request_id') per-line file."""
    out: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) == 1:
            out.append((f"clip{len(out):03d}", parts[0]))
        else:
            out.append((parts[0], parts[1]))
    return out


def _resolve_audio(audio: str, work_dir: Path) -> Path | None:
    if not audio:
        return None
    if audio.startswith(("http://", "https://")):
        dest = work_dir / "episode_audio.mp3"
        print(f"Downloading episode audio: {audio}")
        # Use requests (bundles certifi CAs) — urllib on macOS python.org
        # builds has no trust store unless Install Certificates.command was run.
        resp = requests.get(audio, timeout=180, stream=True)
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)
        return dest
    p = Path(audio)
    return p if p.exists() else None


def _list_all_videos(api_key: str) -> list[dict]:
    """Best-effort enumerate every video on the account.

    The xAI video API is documented only for POST .../generations and
    GET .../{id}; a list endpoint is not guaranteed. We try GET on the
    collection with simple pagination and accept the common response shapes
    ({"data": [...]}, {"videos": [...]}, or a bare list). Returns [] (with a
    clear message) if the endpoint isn't available.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    items: list[dict] = []
    url: str | None = GROK_VIDEO_STATUS_ENDPOINT
    params = {"limit": 100}
    seen_pages = 0
    while url and seen_pages < 100:
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=60)
        except requests.RequestException as exc:
            print(f"List endpoint unreachable: {exc}", file=sys.stderr)
            break
        if resp.status_code == 404:
            print(
                "The account-level list endpoint (GET /v1/videos) is not "
                "available on this API. Use --requests with IDs harvested from "
                "the run logs instead (see the script header).",
                file=sys.stderr,
            )
            break
        if resp.status_code >= 400:
            print(f"List endpoint HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
            break
        try:
            body = resp.json()
        except ValueError:
            print("List endpoint returned non-JSON; cannot enumerate.", file=sys.stderr)
            break

        page = body.get("data") or body.get("videos") if isinstance(body, dict) else body
        if not page:
            break
        items.extend(page)
        seen_pages += 1

        # Cursor pagination, if present.
        nxt = body.get("next_cursor") or body.get("next") if isinstance(body, dict) else None
        if not nxt:
            break
        params = {"limit": 100, "cursor": nxt}
        url = GROK_VIDEO_STATUS_ENDPOINT

    return items


def _run_list_all(api_key: str, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    items = _list_all_videos(api_key)
    if not items:
        print("No videos enumerated (endpoint unavailable or account empty).")
        return 1

    manifest = []
    got = 0
    for i, item in enumerate(items):
        vid = str(item.get("id") or item.get("request_id") or f"video{i:04d}")
        url = _extract_video_url(item)
        status = item.get("status", "unknown")
        if not url and not _is_terminal_success(status):
            # Re-poll by id to get a fresh temporary URL.
            try:
                body = _check_video_status_once(vid, api_key=api_key)
                url, status = _extract_video_url(body), body.get("status", status)
            except GrokVideoError as exc:
                print(f"  {vid}: {exc}")
        if url:
            dest = out_dir / f"{vid}.mp4"
            if _download_video(url, dest):
                got += 1
                manifest.append({"id": vid, "status": status, "file": dest.name})
                print(f"  {vid}: downloaded ✓")
                continue
        print(f"  {vid}: not downloadable (status={status})")
        manifest.append({"id": vid, "status": status, "file": None})

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nDownloaded {got}/{len(items)} videos → {out_dir} (manifest.json written)")
    return 0 if got else 1


def _retrieve(requests_list, api_key, out_dir, retries, retry_wait):
    """Poll + download a list of (clip_id, request_id). Returns ordered paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    pending = failed = 0
    dumped = False
    for clip_id, request_id in requests_list:
        body = None
        for attempt in range(max(1, retries)):
            try:
                body = _check_video_status_once(request_id, api_key=api_key)
            except GrokVideoError as exc:
                print(f"  {clip_id} [{request_id}]: status error — {exc}")
                body = None
                break
            if _is_terminal_success(body.get("status")):
                break
            if _is_terminal_failure(body.get("status")):
                break
            if attempt < retries - 1:
                print(f"  {clip_id}: status={body.get('status')} — retry in {retry_wait:.0f}s")
                time.sleep(retry_wait)

        status = (body or {}).get("status", "unreachable")
        if not body or not _is_terminal_success(status):
            print(f"  {clip_id} [{request_id}]: NOT available (status={status})")
            if _is_terminal_failure(status) or status == "unreachable":
                failed += 1
            else:
                pending += 1
            continue

        url = _extract_video_url(body)
        if not url:
            failed += 1
            print(f"  {clip_id}: finished (status={status}) but no URL field found")
            if not dumped:
                # Dump one raw response so the URL field can be pinned if the
                # shape is unexpected.
                print("  --- raw response (for diagnosis) ---")
                print(json.dumps(body, indent=2)[:2000])
                print("  --- end raw response ---")
                dumped = True
            continue
        dest = out_dir / f"{clip_id}.mp4"
        if _download_video(url, dest):
            downloaded.append(dest)
            print(f"  {clip_id}: downloaded ✓")
        else:
            failed += 1
            print(f"  {clip_id}: download failed")

    print(
        f"\nRecovered {len(downloaded)}/{len(requests_list)} clips "
        f"({pending} still pending, {failed} failed) → {out_dir}"
    )
    return downloaded


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list-all", action="store_true", help="Enumerate + download every video on the account")
    ap.add_argument("--set", dest="embedded_set", choices=sorted(EMBEDDED_SETS),
                    default="tesla_ep519", help="Which embedded clip set to recover (default: tesla_ep519)")
    ap.add_argument("--requests", type=Path, help="File of 'clip_id request_id' lines (overrides --set)")
    ap.add_argument("--out-dir", type=Path, default=None, help="Directory to keep the individual clips")
    ap.add_argument("--stitch", action="store_true", help="Also concatenate the clips into one episode video")
    ap.add_argument("--audio", default="", help="Episode audio (path or URL) to composite when --stitch")
    ap.add_argument("--out", type=Path, help="Stitched output MP4 (required with --stitch)")
    ap.add_argument("--retries", type=int, default=3, help="Status-poll retries per clip if still pending")
    ap.add_argument("--retry-wait", type=float, default=10.0, help="Seconds between status retries")
    args = ap.parse_args()

    api_key = os.getenv("GROK_API_KEY", "").strip() or os.getenv("XAI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: set GROK_API_KEY (or XAI_API_KEY) in the environment.", file=sys.stderr)
        return 2

    if args.list_all:
        out_dir = args.out_dir or Path("recovered_videos")
        return _run_list_all(api_key, out_dir)

    if args.requests:
        requests_list = _load_requests(args.requests)
        default_audio = ""
    else:
        requests_list, default_audio = EMBEDDED_SETS[args.embedded_set]
        requests_list = list(requests_list)
    if not requests_list:
        print("ERROR: no request IDs to recover.", file=sys.stderr)
        return 2

    out_dir = args.out_dir or Path(tempfile.mkdtemp(prefix="grok_video_recover_"))
    print(f"Recovering {len(requests_list)} clip(s) into {out_dir}")
    downloaded = _retrieve(requests_list, api_key, out_dir, args.retries, args.retry_wait)

    if not downloaded:
        print("Nothing downloaded — the clips are no longer retrievable.", file=sys.stderr)
        return 1

    if not args.stitch:
        print(f"Individual clips kept in {out_dir}. Pass --stitch to assemble a video.")
        return 0

    if not args.out:
        print("ERROR: --stitch requires --out <file.mp4>.", file=sys.stderr)
        return 2

    stitched = out_dir / "stitched.mp4"
    if not _stitch_videos_ffmpeg(downloaded, stitched, cleanup=True):
        print("ERROR: stitching failed (is ffmpeg installed?).", file=sys.stderr)
        return 1

    audio_path = _resolve_audio(args.audio or default_audio, out_dir)
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

    if len(downloaded) < len(requests_list):
        print(
            "NOTE: PARTIAL recovery — some clips were missing, so the stitched "
            "video is shorter than the audio (the composite uses -shortest)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
