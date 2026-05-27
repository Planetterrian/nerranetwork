#!/usr/bin/env python3
"""Build the static client search index from the Content Lake (Item 2, May 2026 review).

Server-side FTS + metadata export powers a richer, always-up-to-date global
search experience (replaces the limited multi-fetch proto in base.html.j2).

Writes site/data/search-index.json (or custom --out).

Schema (v1)::

    {
      "schema_version": 1,
      "generated_at": "2026-05-...",
      "episode_count": 1234,
      "shows": ["tesla", ...],
      "episodes": [
        {
          "show_slug": "tesla",
          "episode_num": 461,
          "date": "2026-05-20",
          "title": "...",
          "hook": "...",
          "summary": "...",
          "url": "/tesla.html",
          "entities": ["Tesla", "Cybercab"],
          "topics": ["autonomous-vehicles"],
          "show_name": "Tesla Shorts Time",
          "language": "en"
        },
        ...
      ]
    }

The index is intentionally compact (no full scripts/digests) so the client
can download it once and perform fast interactive ranking/filtering.
FTS ranking happens at build time for any future pre-computed "top results"
features; the current v1 ships the full doc list for client-side flexibility.

Safe/idempotent:
- Missing lake DB or no episodes → writes minimal valid index (no crash).
- Only rewrites the file when content actually changed (timestamp-only
  changes are suppressed so CI stays clean).
- Dry-run supported.

Run:
    python scripts/build_search_index.py
    python scripts/build_search_index.py --dry-run
    python scripts/build_search_index.py --out /tmp/search.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Make engine importable
_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.content_lake import get_all_search_docs  # type: ignore


DEFAULT_OUT = _ROOT / "site" / "data" / "search-index.json"


def build_index(docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    shows = sorted({d.get("show_slug") for d in docs if d.get("show_slug")})
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "episode_count": len(docs),
        "shows": shows,
        "episodes": docs,
    }


def write_if_changed(new_content: str, out_path: Path, dry_run: bool) -> bool:
    """Write only if different from existing (ignore timestamp-only for cleanliness)."""
    if dry_run:
        print(f"[dry-run] Would write {len(new_content)} bytes to {out_path}")
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        try:
            existing = out_path.read_text(encoding="utf-8")
            existing_obj = json.loads(existing)
            new_obj = json.loads(new_content)
            # Compare ignoring generated_at
            existing_obj.pop("generated_at", None)
            new_obj.pop("generated_at", None)
            if json.dumps(existing_obj, sort_keys=True) == json.dumps(new_obj, sort_keys=True):
                print(f"No content change; leaving {out_path} untouched (CI friendly).")
                return False
        except Exception:
            pass  # fall through and overwrite on parse error

    out_path.write_text(new_content, encoding="utf-8")
    print(f"Wrote search index ({len(new_content)} bytes) → {out_path}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Nerra Network global search index from content lake")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output JSON path")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen; do not write")
    args = parser.parse_args()

    try:
        raw_docs = get_all_search_docs()
    except Exception as e:
        print(f"Warning: could not read content lake ({e}). Writing empty index.", file=sys.stderr)
        raw_docs = []

    # Normalise to the exact fields we want in the public index (strip internals)
    clean_docs: List[Dict[str, Any]] = []
    for d in raw_docs:
        clean_docs.append({
            "show_slug": d.get("show_slug"),
            "episode_num": d.get("episode_num"),
            "date": d.get("date"),
            "title": d.get("title") or "",
            "hook": d.get("hook") or "",
            "summary": d.get("summary") or "",
            "url": f"/{str(d.get('show_slug', '')).replace('_', '-')}.html",
            "entities": d.get("entities") or [],
            "topics": d.get("topics") or [],
            "show_name": d.get("show_name") or d.get("show_slug", ""),
            "language": d.get("language") or "en",
        })

    index = build_index(clean_docs)
    content = json.dumps(index, indent=2, ensure_ascii=False) + "\n"

    wrote = write_if_changed(content, args.out, args.dry_run)
    if wrote or args.dry_run:
        print(f"Index covers {index['episode_count']} episodes across {len(index['shows'])} shows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
