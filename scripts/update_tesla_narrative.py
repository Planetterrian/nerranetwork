#!/usr/bin/env python3
"""
Operator tooling for the Tesla Narrative Tracker.

This tool makes it easy to keep the long-term narrative memory up to date
without hand-editing JSON. It supports updating status, adding notable claims,
and managing key open questions.

Usage examples:
    # Update status for a program
    python scripts/update_tesla_narrative.py optimus "Factory construction now 35% complete. First cell production line installation has begun." --episode 491

    # Add a notable claim
    python scripts/update_tesla_narrative.py fsd_unsupervised --claim "Unsupervised approval in Texas expected before end of 2026" --episode 490 --claim-status "on_track"

    # Update open questions for a program
    python scripts/update_tesla_narrative.py cybercab_robotaxi --questions "Regulatory path in California" "Production timeline for unsupervised version" --episode 491

    # View current state
    python scripts/update_tesla_narrative.py --show
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


def show_tracker(tracker):
    print("\n=== Current Tesla Narrative Tracker ===\n")
    for key, prog in tracker.get("programs", {}).items():
        name = prog.get("display_name", key)
        status = prog.get("status", "No status")
        last = ""
        if prog.get("last_major_update_episode"):
            last = f" (Ep{prog['last_major_update_episode']}, {prog.get('last_major_update_date', '')})"
        print(f"**{name}**{last}")
        print(f"  Status: {status}")
        questions = prog.get("key_open_questions", [])
        if questions:
            print("  Open questions:")
            for q in questions:
                print(f"    - {q}")
        claims = prog.get("notable_claims", [])
        if claims:
            print(f"  Notable claims: {len(claims)} recorded")
        print()
    print("Last updated:", tracker.get("last_updated", "unknown"))


def main():
    parser = argparse.ArgumentParser(description="Update Tesla Narrative Tracker")
    parser.add_argument("program", nargs="?", choices=PROGRAM_KEYS + [None], default=None, help="Which program to update")
    parser.add_argument("status", nargs="?", default=None, help="New status text for the program")
    parser.add_argument("--show", action="store_true", help="Show current tracker state")
    parser.add_argument("--episode", type=int, help="Episode number of this update")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Date of update (YYYY-MM-DD)")
    parser.add_argument("--claim", help="Add a notable claim made on this episode")
    parser.add_argument("--claim-status", default="new", help="Status of the claim")
    parser.add_argument("--questions", nargs="+", help="Replace the list of key open questions for this program")

    args = parser.parse_args()

    tracker = load_tracker()

    if args.show or (not args.program and not args.status and not args.claim and not args.questions):
        show_tracker(tracker)
        return

    if not args.program:
        print("Error: program is required unless using --show")
        return

    prog = tracker.setdefault("programs", {}).setdefault(args.program, {})

    updated = False

    if args.status:
        prog["status"] = args.status
        if args.episode:
            prog["last_major_update_episode"] = args.episode
            prog["last_major_update_date"] = args.date
        print(f"Updated status for {args.program}")
        updated = True

    if args.questions:
        prog["key_open_questions"] = list(args.questions)
        print(f"Updated key open questions for {args.program}")
        updated = True

    if args.claim and args.episode:
        claims = prog.setdefault("notable_claims", [])
        claims.append({
            "episode": args.episode,
            "date": args.date,
            "claim": args.claim,
            "status": args.claim_status
        })
        print(f"Added claim from Ep {args.episode}")
        updated = True

    if updated:
        tracker["last_updated"] = datetime.now().isoformat()
        save_tracker(tracker)
    else:
        print("No changes made. Use --show to view current state or provide status/claim/questions.")


if __name__ == "__main__":
    main()