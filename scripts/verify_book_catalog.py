#!/usr/bin/env python3
"""Verify that book builds actually shipped: catalog entries carry files
and the R2 objects answer 200.

    python scripts/verify_book_catalog.py --volume <id>   # one volume
    python scripts/verify_book_catalog.py --require-all   # every volume yaml

Exists because the workflow's original "Verify book integrity" step only
ran the compiler tests — it passed in 2 s on a run that had built
nothing (2026-08-22, Build Book run #1: green in 70 s, zero artifacts).
This script is the assertion that step was missing: what the catalog
claims to have built must be reachable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


PAID_KINDS = ("epub", "m4b")


def _check_private(kind: str, ref: str) -> list:
    """Verify an ``r2://bucket/key`` master exists, with credentials.

    Soft-passes when no R2 credentials are present (a fork, or a local
    run) — an unverifiable master is not the same as a missing one, and
    failing here would make the check useless everywhere but CI.
    """
    import os

    bucket, _, key = ref[len("r2://"):].partition("/")
    if not all(os.getenv(k, "").strip() for k in
               ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID",
                "R2_SECRET_ACCESS_KEY")):
        return []
    try:
        import boto3
        from botocore.config import Config as BotoConfig

        boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT_URL"].strip(),
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"].strip(),
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"].strip(),
            config=BotoConfig(signature_version="s3v4"),
        ).head_object(Bucket=bucket, Key=key)
    except Exception as exc:  # noqa: BLE001
        return [f"{kind}: private master missing ({exc}) at {ref}"]
    return []


def check_volume(entry: dict, *, expect_audio: bool) -> list:
    problems = []
    files = entry.get("files") or {}
    if not files.get("epub"):
        problems.append("no epub in catalog files")
        return problems
    # The regression that matters more than reachability: a paid master
    # that carries an https URL is a paid master anyone can download.
    for kind in PAID_KINDS:
        ref = files.get(kind)
        if ref and not ref.startswith("r2://"):
            problems.append(
                f"{kind}: paid master is published at a public URL "
                f"({ref}) — it belongs in the private bucket")
    for kind, ref in sorted(files.items()):
        if ref.startswith("r2://"):
            # The paid masters (epub, m4b) live in a private bucket and
            # MUST NOT answer to an anonymous HTTP request — that was the
            # 2026-08-26 exposure. Reachability for these means "the
            # object exists to a credentialed client", so check it the
            # only way that is true: head_object.
            problems.extend(_check_private(kind, ref))
            continue
        try:
            r = requests.head(ref, timeout=30, allow_redirects=True)
            if r.status_code != 200:
                problems.append(f"{kind}: HTTP {r.status_code} at {ref}")
        except requests.RequestException as exc:
            problems.append(f"{kind}: unreachable ({exc}) at {ref}")
    if expect_audio and not entry.get("audiobook"):
        problems.append("catalog entry has no audiobook block")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--volume", help="verify this volume id only")
    g.add_argument("--require-all", action="store_true",
                   help="every books/volumes/*.yaml must be built + live")
    ap.add_argument("--no-audio", action="store_true",
                    help="don't require an audiobook block (ebook-only run)")
    args = ap.parse_args()

    catalog_path = ROOT / "books" / "catalog.json"
    entries = {}
    if catalog_path.exists():
        for v in json.loads(catalog_path.read_text(encoding="utf-8")).get(
                "volumes", []):
            entries[v.get("volume_id")] = v

    targets = ([args.volume] if args.volume else
               sorted(p.stem for p in
                      (ROOT / "books" / "volumes").glob("*.yaml")))

    failures = 0
    for vid in targets:
        entry = entries.get(vid)
        if not entry:
            print(f"::error::{vid}: not in books/catalog.json")
            failures += 1
            continue
        problems = check_volume(entry, expect_audio=not args.no_audio)
        if problems:
            failures += 1
            for p in problems:
                print(f"::error::{vid}: {p}")
        else:
            print(f"OK {vid}: {len(entry.get('files', {}))} artifacts live")

    if failures:
        print(f"::error::book verification failed for {failures} volume(s)")
        return 1
    print(f"verified {len(targets)} volume(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
