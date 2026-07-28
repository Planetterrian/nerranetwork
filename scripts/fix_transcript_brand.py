#!/usr/bin/env python3
"""One-shot backfill: repair the "Nerra" brand misspelling in committed transcripts.

Whisper was never given the show vocabulary (fixed July 28 2026 in
``engine/transcripts.py``), so it rendered the network brand as "NARA",
"Naran Network" and "naranetwork.com" across the back catalogue. Those
files are not scratch data — they are served live as
``<podcast:transcript>`` on every audio and video feed, so correcting
them in place fixes the published artefact the moment the commit lands.

What this touches:
  * ``*_transcript.txt`` — plain text, rewritten line for line.
  * ``*_transcript.json`` — ``segments[].text`` and
    ``segments[].words[].word`` ONLY. Timestamps, probabilities,
    language detection and duration are never modified.

What this deliberately does NOT do: regenerate audio or re-render
video for the back catalogue. Forward episodes get clean captions
automatically; re-rendering years of video to fix burned-in captions
is not worth the spend.

Usage::

    python scripts/fix_transcript_brand.py            # dry run (default)
    python scripts/fix_transcript_brand.py --apply    # write the files
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.transcripts import correct_brand_segments, correct_brand_text  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def fix_txt(path: Path, *, apply: bool) -> int:
    """Repair a plain-text transcript. Returns the number of changed lines.

    The correction runs over the WHOLE file, not line by line: one
    transcript line is one Whisper segment, and 41 of the occurrences
    had the brand split across that newline ("...the NARA\\nnetworks
    daily briefings"). Correcting per line hides exactly those.
    """
    original = path.read_text(encoding="utf-8")
    fixed = correct_brand_text(original)
    if fixed == original:
        return 0
    changed = sum(
        1 for a, b in zip(original.split("\n"), fixed.split("\n")) if a != b
    )
    if apply:
        path.write_text(fixed, encoding="utf-8")
    return changed


def fix_json(path: Path, *, apply: bool) -> int:
    """Repair a JSON transcript. Returns the number of changed fields."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"  !! skipping unreadable {path.name}: {exc}")
        return 0

    segments = data.get("segments", [])
    repaired = correct_brand_segments(segments)

    changed = 0
    for before, after in zip(segments, repaired):
        if before.get("text") != after.get("text"):
            changed += 1
        changed += sum(
            1 for a, b in zip(before.get("words") or [], after.get("words") or [])
            if a.get("word") != b.get("word")
        )

    if changed:
        data["segments"] = repaired

    if changed and apply:
        # ``indent=2`` + ``ensure_ascii=False`` matches how
        # engine/transcripts.py writes these files, so the diff shows
        # only the corrected words and never a reformat of the file.
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="write the corrected files (default is a dry run)",
    )
    parser.add_argument(
        "--digests-dir", default=str(REPO_ROOT / "digests"),
        help="root directory to scan (default: ./digests)",
    )
    args = parser.parse_args()

    root = Path(args.digests_dir)
    if not root.is_dir():
        print(f"No such directory: {root}")
        return 1

    per_show: dict[str, dict[str, int]] = {}
    total_files = 0
    total_fields = 0

    paths = sorted(root.glob("*/*_transcript.txt")) + sorted(
        root.glob("*/*_transcript.json")
    )
    for path in paths:
        changed = (
            fix_txt(path, apply=args.apply)
            if path.suffix == ".txt"
            else fix_json(path, apply=args.apply)
        )
        if not changed:
            continue
        show = path.parent.name
        bucket = per_show.setdefault(show, {"files": 0, "fields": 0})
        bucket["files"] += 1
        bucket["fields"] += changed
        total_files += 1
        total_fields += changed

    mode = "Rewrote" if args.apply else "Would rewrite"
    print(f"{mode} {total_files} file(s), {total_fields} corrected field(s)\n")
    for show in sorted(per_show, key=lambda s: -per_show[s]["files"]):
        stats = per_show[show]
        print(f"  {show:32s} {stats['files']:4d} files  {stats['fields']:5d} fields")

    if not args.apply and total_files:
        print("\nDry run — re-run with --apply to write these changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
