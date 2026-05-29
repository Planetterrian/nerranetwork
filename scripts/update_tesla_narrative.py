#!/usr/bin/env python3
"""
Operator tooling for the Tesla Narrative Tracker.

Usage examples:
    python scripts/update_tesla_narrative.py optimus "Factory construction now 35% complete. First cell production line installation has begun."
    python scripts/update_tesla_narrative.py fsd_unsupervised --claim "Unsupervised approval in Texas expected before end of 2026" --episode 490

This script makes it easy to keep the narrative tracker up to date without hand-editing JSON.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

TRACKER_PATH = Path("digests/tesla_shorts_time/tesla_narrative_tracker.json")

PROGRAM_KEYS = [
    "optimus",
    "cybercab_robotaxi",
    "fsd_unsupervised",
    "hw5_ai5",
    "next_gen_vehicle",
    "4680_structural_pack",
]


def load_tracker():
    if not TRACKER_PATH.exists():
        print("Tracker file not found. Creating from defaults...")
        return {"version": 1, "programs": {}}
    with TRACKER_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_tracker(data):
    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACKER_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Updated {TRACKER_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Update Tesla Narrative Tracker")
    parser.add_argument("program", choices=PROGRAM_KEYS, help="Which program to update")
    parser.add_argument("status", nargs="?", help="New status text for the program")
    parser.add_argument("--episode", type=int, help="Episode number of this update")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Date of update (YYYY-MM-DD)")
    parser.add_argument("--claim", help="Add a notable claim made on this episode")
    parser.add_argument("--claim-status", default="new", help="Status of the claim (new, on_track, delayed, etc.)")

    args = parser.parse_args()

    tracker = load_tracker()
    prog = tracker.setdefault("programs", {}).setdefault(args.program, {})

    if args.status:
        prog["status"] = args.status
        if args.episode:
            prog["last_major_update_episode"] = args.episode
            prog["last_major_update_date"] = args.date
        print(f"Updated status for {args.program}")

    if args.claim and args.episode:
        claims = prog.setdefault("notable_claims", [])
        claims.append({
            "episode": args.episode,
            "date": args.date,
            "claim": args.claim,
            "status": args.claim_status
        })
        print(f"Added claim from Ep {args.episode}")

    tracker["last_updated"] = datetime.now().isoformat()
    save_tracker(tracker)


if __name__ == "__main__":
    main()