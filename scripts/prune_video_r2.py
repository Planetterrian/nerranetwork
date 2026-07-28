#!/usr/bin/env python3
"""Delete episode MP4s that nothing points at any more.

The problem
-----------
Each rendered episode is about 174 MB. Five shows publish daily, so the
``video/`` keyspace grows roughly **318 GB per year** and never shrinks.
Nothing expires it. R2 storage is cheap per gigabyte and merciless in
aggregate: a year of this is a recurring bill for objects no listener
can reach, because each video feed lists only ``max_episodes`` (30)
items. Episode 31 and older are already invisible to Apple — the MP4
just stays in the bucket forever.

Why a script rather than a bucket lifecycle rule
------------------------------------------------
A lifecycle rule expires by age, which is the wrong predicate. The feed
window is a *count*, and a show that pauses for two months would have
its still-listed episodes deleted out from under it. This script deletes
by reachability instead: an object is a candidate only if no feed and no
durable index references it.

Safety
------
* **Dry run by default.** Nothing is deleted without ``--apply``.
* Reads the live ``*.video.rss`` files AND every
  ``digests/<slug>/video_assets.json``, so an object referenced by
  either is kept. The index outlives the 30-record summaries truncation
  and is what lets ``max_episodes`` exceed 30 at all.
* ``--keep-newest N`` (default 60) retains that many objects per show
  regardless of references, so a bug in feed generation cannot cascade
  into deleting a show's whole back catalogue on the next run.
* Never touches the ``art/`` prefix. Episode artwork is a few hundred
  kilobytes and stays reachable from older index rows.

Usage::

    python scripts/prune_video_r2.py                  # report only
    python scripts/prune_video_r2.py --apply          # actually delete
    python scripts/prune_video_r2.py --show spacex    # one show
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_KEEP_NEWEST = 60
_ENCLOSURE_RE = re.compile(rb'<enclosure[^>]+url="([^"]+\.mp4)"')


def _referenced_keys() -> Set[str]:
    """Every ``video/<slug>/<file>.mp4`` key the repo still points at."""
    keys: Set[str] = set()

    for feed in ROOT.glob("*.video.rss"):
        for url in _ENCLOSURE_RE.findall(feed.read_bytes()):
            keys.add(_key_from_url(url.decode("utf-8")))

    for index in ROOT.glob("digests/*/video_assets.json"):
        try:
            data = json.loads(index.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — a corrupt index must not delete
            print(f"WARNING: unreadable {index} — treating its shows as fully "
                  f"referenced", file=sys.stderr)
            return set()
        for row in data.get("videos", []):
            url = row.get("url")
            if url:
                keys.add(_key_from_url(str(url)))

    keys.discard("")
    return keys


def _key_from_url(url: str) -> str:
    """``https://audio.../video/spacex/A.mp4`` -> ``video/spacex/A.mp4``."""
    marker = "/video/"
    idx = url.find(marker)
    return f"video/{url[idx + len(marker):]}" if idx >= 0 else ""


def _client():
    import boto3

    endpoint = os.getenv("R2_ENDPOINT_URL", "")
    access_key = os.getenv("R2_ACCESS_KEY_ID", "")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY", "")
    if not (endpoint and access_key and secret_key):
        raise SystemExit("R2_ENDPOINT_URL / R2_ACCESS_KEY_ID / "
                         "R2_SECRET_ACCESS_KEY must be set")
    return boto3.client("s3", endpoint_url=endpoint,
                        aws_access_key_id=access_key,
                        aws_secret_access_key=secret_key)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="Actually delete. Without this, report only.")
    ap.add_argument("--bucket", default=os.getenv("R2_BUCKET", "nerra-audio"))
    ap.add_argument("--show", default="", help="Limit to one show slug")
    ap.add_argument("--keep-newest", type=int, default=DEFAULT_KEEP_NEWEST,
                    help=f"Per-show floor, default {DEFAULT_KEEP_NEWEST}")
    args = ap.parse_args()

    referenced = _referenced_keys()
    if not referenced:
        print("No referenced keys found — refusing to delete anything.",
              file=sys.stderr)
        return 1
    print(f"{len(referenced)} referenced video objects across the repo")

    client = _client()
    prefix = f"video/{args.show}/" if args.show else "video/"

    by_show: Dict[str, List[dict]] = {}
    token = None
    total = 0
    while True:
        kwargs = {"Bucket": args.bucket, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token
        page = client.list_objects_v2(**kwargs)
        for obj in page.get("Contents", []):
            parts = obj["Key"].split("/")
            if len(parts) < 3:
                continue
            by_show.setdefault(parts[1], []).append(obj)
            total += 1
        if not page.get("IsTruncated"):
            break
        token = page.get("NextContinuationToken")

    print(f"{total} objects under {prefix} in {args.bucket}\n")

    doomed: List[dict] = []
    for show, objects in sorted(by_show.items()):
        objects.sort(key=lambda o: o["LastModified"], reverse=True)
        protected = {o["Key"] for o in objects[:args.keep_newest]}
        stale = [o for o in objects
                 if o["Key"] not in referenced and o["Key"] not in protected]
        live_bytes = sum(o["Size"] for o in objects)
        free_bytes = sum(o["Size"] for o in stale)
        print(f"{show:<28} {len(objects):>4} objects  "
              f"{live_bytes / 1e9:>6.1f} GB   "
              f"unreferenced: {len(stale):>4} ({free_bytes / 1e9:.1f} GB)")
        doomed.extend(stale)

    if not doomed:
        print("\nNothing to prune.")
        return 0

    freed = sum(o["Size"] for o in doomed)
    print(f"\n{len(doomed)} objects, {freed / 1e9:.1f} GB reclaimable")

    if not args.apply:
        print("Dry run — pass --apply to delete. Sample:")
        for obj in doomed[:10]:
            print(f"  {obj['Key']}")
        return 0

    for i in range(0, len(doomed), 1000):
        batch = [{"Key": o["Key"]} for o in doomed[i:i + 1000]]
        client.delete_objects(Bucket=args.bucket, Delete={"Objects": batch})
        print(f"  deleted {i + len(batch)}/{len(doomed)}")
    print(f"Freed {freed / 1e9:.1f} GB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
