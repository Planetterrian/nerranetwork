#!/usr/bin/env python3
"""
Operator tooling for narrative trackers (Tesla + Phase 3 memory shows).

Keeps a show's long-term narrative memory up to date without hand-editing JSON:
update a program's status, add notable claims, or replace its open questions.

Defaults to Tesla so existing invocations keep working; pass ``--slug`` to
target another memory-enabled show (models_agents, fascinating_frontiers,
planetterrian — anything in engine.show_memory.SHOW_MEMORY_CONFIGS).

Usage examples:
    # Tesla (default slug) — update a program's status
    python scripts/update_tesla_narrative.py optimus "Factory construction now 35% complete." --episode 491

    # Another show — list valid program keys, then update one
    python scripts/update_tesla_narrative.py --slug models_agents --show
    python scripts/update_tesla_narrative.py --slug models_agents frontier_llms "GPT-6 and Claude 5 traded the lead this week." --episode 70

    # Add a notable claim
    python scripts/update_tesla_narrative.py fsd_unsupervised --claim "Unsupervised approval in Texas expected before end of 2026" --episode 490 --claim-status on_track

    # Replace open questions
    python scripts/update_tesla_narrative.py cybercab_robotaxi --questions "Regulatory path in California" "Unsupervised production timeline" --episode 491

    # View current state
    python scripts/update_tesla_narrative.py --slug fascinating_frontiers --show
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _resolve(slug):
    """Return (tracker_path, default_programs) for a show slug."""
    yaml_path = Path("shows") / f"{slug}.yaml"
    if not yaml_path.exists():
        raise SystemExit(
            f"Unknown show '{slug}'. Valid memory shows: tesla, " + ", ".join(_memory_slugs())
        )
    from engine.config import load_config
    cfg = load_config(yaml_path)
    out_dir = Path(cfg.episode.output_dir)

    if slug == "tesla":
        # Tesla keeps its bespoke module + committed tracker.
        from engine import tesla_memory as tm
        return out_dir / tm.NARRATIVE_TRACKER_FILENAME, tm.DEFAULT_NARRATIVE_TRACKER["programs"]

    from engine.show_memory import get_config
    mcfg = get_config(slug)
    if mcfg is None:
        raise SystemExit(
            f"No narrative-memory config for '{slug}'. "
            "Valid memory shows: tesla, " + ", ".join(_memory_slugs())
        )
    return out_dir / mcfg.narrative_filename, mcfg.default_programs


def _memory_slugs():
    from engine.show_memory import SHOW_MEMORY_CONFIGS
    return list(SHOW_MEMORY_CONFIGS)


def load_tracker(path, default_programs):
    if not path.exists():
        print(f"Tracker file {path} not found. Creating from defaults...")
        import copy
        return {"version": 1, "programs": copy.deepcopy(default_programs)}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_tracker(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Updated {path}")


def show_tracker(tracker, slug):
    print(f"\n=== Current Narrative Tracker: {slug} ===\n")
    for key, prog in tracker.get("programs", {}).items():
        name = prog.get("display_name", key)
        status = prog.get("status", "No status")
        last = ""
        if prog.get("last_major_update_episode"):
            last = f" (Ep{prog['last_major_update_episode']}, {prog.get('last_major_update_date', '')})"
        print(f"[{key}] **{name}**{last}")
        print(f"  Status: {status}")
        for q in prog.get("key_open_questions", []):
            print(f"    - {q}")
        claims = prog.get("notable_claims", [])
        if claims:
            print(f"  Notable claims: {len(claims)} recorded")
        print()
    print("Last updated:", tracker.get("last_updated", "unknown"))


def main():
    parser = argparse.ArgumentParser(description="Update a show's narrative tracker")
    parser.add_argument("program", nargs="?", default=None, help="Program key to update")
    parser.add_argument("status", nargs="?", default=None, help="New status text for the program")
    parser.add_argument("--slug", default="tesla", help="Show slug (default: tesla)")
    parser.add_argument("--show", action="store_true", help="Show current tracker state")
    parser.add_argument("--episode", type=int, help="Episode number of this update")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Date (YYYY-MM-DD)")
    parser.add_argument("--claim", help="Add a notable claim made on this episode")
    parser.add_argument("--claim-status", default="new", help="Status of the claim")
    parser.add_argument("--questions", nargs="+", help="Replace the key open questions for this program")

    args = parser.parse_args()

    tracker_path, default_programs = _resolve(args.slug)
    tracker = load_tracker(tracker_path, default_programs)

    if args.show or (not args.program and not args.status and not args.claim and not args.questions):
        show_tracker(tracker, args.slug)
        return

    if not args.program:
        print("Error: program is required unless using --show")
        return

    programs = tracker.setdefault("programs", {})
    if args.program not in programs:
        valid = ", ".join(programs.keys()) or "(none)"
        print(f"Error: unknown program '{args.program}' for {args.slug}. Valid keys: {valid}")
        return

    prog = programs[args.program]
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
        prog.setdefault("notable_claims", []).append({
            "episode": args.episode,
            "date": args.date,
            "claim": args.claim,
            "status": args.claim_status,
        })
        print(f"Added claim from Ep {args.episode}")
        updated = True

    if updated:
        tracker["last_updated"] = datetime.now().isoformat()
        save_tracker(tracker_path, tracker)
    else:
        print("No changes made. Use --show to view, or provide status/claim/questions.")


if __name__ == "__main__":
    main()
