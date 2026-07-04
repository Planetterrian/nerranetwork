#!/usr/bin/env python3
"""
Operator tooling for The DP Pod's Dispatch Wall.

Appends a REAL listener dispatch to ``digests/dp_pod/dispatches.json`` — the
operator-curated file the club page's Dispatch Wall renders from — without
hand-editing JSON. Per the club charter the wall is never generated or
fabricated: this script exists so curating real listener mail is a one-liner,
and it validates the entry shape the page collector expects
(``generate_html._collect_dp_dispatches``).

Usage examples:
    # Minimal — what they did is the only required field
    python scripts/add_dp_dispatch.py --did "Sealed the three worst drafts in my house."

    # Full entry, as read on air
    python scripts/add_dp_dispatch.py \
        --name "Sarah, Calgary" \
        --did "Sealed the three worst drafts in my house before the cold snap." \
        --numbers "\$14 in foam tape, about 2 hours, roughly \$90 a year saved" \
        --shoutout "My dad held the ladder." \
        --episode 3

    # View the current wall
    python scripts/add_dp_dispatch.py --show

Then commit the file and the wall updates on the next site regen (nightly, or
``python generate_html.py --show dp_pod``).
"""

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISPATCHES_PATH = ROOT / "digests" / "dp_pod" / "dispatches.json"


def _load() -> dict:
    if not DISPATCHES_PATH.exists():
        return {"dispatches": []}
    data = json.loads(DISPATCHES_PATH.read_text(encoding="utf-8"))
    if isinstance(data, list):  # tolerate a bare-list file
        data = {"dispatches": data}
    data.setdefault("dispatches", [])
    return data


def _show(data: dict) -> None:
    entries = data.get("dispatches", [])
    if not entries:
        print("Dispatch Wall is empty — the page renders its how-to-send state.")
        return
    print(f"{len(entries)} dispatch(es) on the wall (newest first on the page):\n")
    for e in sorted(entries, key=lambda d: d.get("date") or "", reverse=True):
        name = e.get("name") or "A club member"
        when = f"  ({e['date']})" if e.get("date") else ""
        print(f"- {name}{when}: {e.get('did', '')}")
        if e.get("numbers"):
            print(f"    numbers: {e['numbers']}")
        if e.get("shoutout"):
            print(f"    shoutout: {e['shoutout']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--did", help="What they did (required to add; plain sentence)")
    ap.add_argument("--name", default="", help='How to credit them, e.g. "Sarah, Calgary"')
    ap.add_argument("--numbers", default="", help="The honest numbers line (cost/hours/impact)")
    ap.add_argument("--shoutout", default="", help="Who helped, or who should try it next")
    ap.add_argument("--episode", type=int, default=None,
                    help="Episode number whose Lever this answers (optional)")
    ap.add_argument("--date", default=None,
                    help="YYYY-MM-DD received date (default: today)")
    ap.add_argument("--show", action="store_true", help="Print the current wall and exit")
    args = ap.parse_args()

    data = _load()

    if args.show:
        _show(data)
        return

    if not args.did or not args.did.strip():
        ap.error("--did is required (or pass --show to view the wall)")

    when = args.date or date.today().isoformat()
    try:
        date.fromisoformat(when)
    except ValueError:
        raise SystemExit(f"--date must be YYYY-MM-DD, got: {when!r}")

    entry = {"date": when, "did": args.did.strip()}
    if args.name.strip():
        entry["name"] = args.name.strip()
    if args.numbers.strip():
        entry["numbers"] = args.numbers.strip()
    if args.shoutout.strip():
        entry["shoutout"] = args.shoutout.strip()
    if args.episode is not None:
        entry["episode_num"] = args.episode

    # Guard against accidental double-adds of the same mail.
    for existing in data["dispatches"]:
        if existing.get("did") == entry["did"] and existing.get("name", "") == entry.get("name", ""):
            raise SystemExit(
                "An identical dispatch (same name + did) is already on the wall — not adding."
            )

    data["dispatches"].append(entry)
    DISPATCHES_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    who = entry.get("name", "A club member")
    print(f"Added dispatch from {who} ({when}). Wall now has {len(data['dispatches'])} entry(ies).")
    print("Commit digests/dp_pod/dispatches.json — the wall updates on the next site regen.")


if __name__ == "__main__":
    main()
