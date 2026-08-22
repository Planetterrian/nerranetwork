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
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


def check_volume(entry: dict, *, expect_audio: bool) -> list:
    problems = []
    files = entry.get("files") or {}
    if not files.get("epub"):
        problems.append("no epub in catalog files")
        return problems
    for kind, url in sorted(files.items()):
        try:
            r = requests.head(url, timeout=30, allow_redirects=True)
            if r.status_code != 200:
                problems.append(f"{kind}: HTTP {r.status_code} at {url}")
        except requests.RequestException as exc:
            problems.append(f"{kind}: unreachable ({exc}) at {url}")
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
