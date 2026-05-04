#!/usr/bin/env python3
"""Tag (or untag) a Buttondown subscriber across all Nerra Network show tags.

Used to:

  - Bootstrap Patrick's own subscription so newsletters reach his inbox
    even though the website signup form didn't tag him.
  - Add an existing subscriber to a new show's mailing list without
    asking them to re-subscribe.
  - Audit which shows a subscriber is on, by passing ``--list``.

Reads ``BUTTONDOWN_API_KEY`` from the environment. Tag values come from
each show's ``newsletter.tag`` in ``shows/<slug>.yaml``.

Usage::

    # Tag the user across all 11 shows
    python scripts/buttondown_tag_subscriber.py user@example.com --all

    # Tag for specific shows
    python scripts/buttondown_tag_subscriber.py user@example.com \\
        --show tesla --show fascinating_frontiers

    # Print what tags they have today
    python scripts/buttondown_tag_subscriber.py user@example.com --list

    # Remove the user from a show's mailing list
    python scripts/buttondown_tag_subscriber.py user@example.com \\
        --show tesla --remove

The Buttondown API key needs ``subscribers:read`` and
``subscribers:write`` permissions (the default API key has both).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHOWS_DIR = PROJECT_ROOT / "shows"
BUTTONDOWN_API_BASE = "https://api.buttondown.email/v1"


def _load_show_tags() -> Dict[str, str]:
    """Return ``{slug: tag}`` for every show that has a newsletter tag."""
    tags: Dict[str, str] = {}
    for yaml_path in sorted(SHOWS_DIR.glob("*.yaml")):
        if yaml_path.stem.startswith("_") or yaml_path.stem == "pronunciation_map":
            continue
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        nl = data.get("newsletter") or {}
        tag = (nl.get("tag") or "").strip()
        if tag:
            tags[yaml_path.stem] = tag
    return tags


def _is_valid_buttondown_tag(tag: str) -> bool:
    """Buttondown rejects tags that contain no ASCII letter or digit
    (HTTP 400 ``tag_invalid``). Mirror that rule client-side so we
    can drop stale invalid tags from a subscriber's record without
    triggering the same error in our PATCH payload."""
    if not tag:
        return False
    return any(c.isascii() and c.isalnum() for c in tag)


def _get_subscriber(email: str, api_key: str) -> Optional[dict]:
    """Look up a subscriber by email. Returns the JSON record or None."""
    resp = requests.get(
        f"{BUTTONDOWN_API_BASE}/subscribers",
        headers={"Authorization": f"Token {api_key}"},
        params={"email": email},
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json() or {}
    results = payload.get("results") or []
    if not results:
        return None
    return results[0]


def _create_subscriber(email: str, tags: List[str], api_key: str) -> dict:
    """Create a new subscriber with the given tags."""
    resp = requests.post(
        f"{BUTTONDOWN_API_BASE}/subscribers",
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        },
        json={"email": email, "tags": tags, "type": "regular"},
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to create subscriber {email}: HTTP {resp.status_code} {resp.text[:300]}"
        )
    return resp.json() or {}


def _patch_subscriber_tags(sub_id: str, tags: List[str], api_key: str) -> dict:
    """Replace a subscriber's tag list."""
    resp = requests.patch(
        f"{BUTTONDOWN_API_BASE}/subscribers/{sub_id}",
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        },
        json={"tags": tags},
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Failed to update subscriber {sub_id}: HTTP {resp.status_code} {resp.text[:300]}"
        )
    return resp.json() or {}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("email", help="Subscriber email address")
    parser.add_argument(
        "--show",
        action="append",
        default=[],
        help="Show slug to tag (can pass multiple). Conflicts with --all.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Tag the subscriber for every Nerra Network show.",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove the listed shows' tags instead of adding them.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the subscriber's current tags and exit.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("BUTTONDOWN_API_KEY", "").strip(),
        help="Buttondown API key (defaults to BUTTONDOWN_API_KEY env var).",
    )
    args = parser.parse_args(argv)

    if not args.api_key:
        print("Error: BUTTONDOWN_API_KEY is not set.", file=sys.stderr)
        return 2

    show_tags = _load_show_tags()

    # Resolve which tags the operator wants to mutate.
    if args.list:
        target_tags: Set[str] = set()
    elif args.all:
        target_tags = set(show_tags.values())
    elif args.show:
        unknown = [s for s in args.show if s not in show_tags]
        if unknown:
            print(f"Unknown show slug(s): {unknown}", file=sys.stderr)
            print(f"Known: {sorted(show_tags)}", file=sys.stderr)
            return 2
        target_tags = {show_tags[s] for s in args.show}
    else:
        print("Error: pass --all, --show <slug> (one or more), or --list.",
              file=sys.stderr)
        return 2

    sub = _get_subscriber(args.email, args.api_key)
    if args.list:
        if sub is None:
            print(f"{args.email} is not a subscriber.")
        else:
            existing = sub.get("tags") or []
            print(f"{args.email} (id={sub.get('id')}, type={sub.get('type')})")
            print(f"  tags: {sorted(existing) if existing else '(none)'}")
        return 0

    if sub is None:
        if args.remove:
            print(f"{args.email} is not a subscriber — nothing to remove.")
            return 0
        # Create with the requested tags.
        new_tags = sorted(target_tags)
        created = _create_subscriber(args.email, new_tags, args.api_key)
        print(f"Created subscriber {args.email} (id={created.get('id')}) "
              f"with tags: {new_tags}")
        return 0

    raw_existing = set(sub.get("tags") or [])
    # Filter out tags Buttondown would reject in a PATCH body — these
    # are stale entries from before the YAML migration to ASCII tags
    # (e.g. "Привет, Русский!" / "Финансы Просто"). Including them in
    # the PATCH request triggers HTTP 400 tag_invalid and aborts the
    # whole update, even when the new tag is valid. Logging the
    # dropped names so the operator sees what got cleaned up.
    existing = {t for t in raw_existing if _is_valid_buttondown_tag(t)}
    dropped = raw_existing - existing
    if dropped:
        print(f"Dropping {len(dropped)} stale invalid tag(s) from "
              f"{args.email} that Buttondown would now reject: "
              f"{sorted(dropped)}")
    if args.remove:
        new = existing - target_tags
        action = "Removed"
    else:
        new = existing | target_tags
        action = "Added"
    if new == existing and not dropped:
        print(f"No-op: {args.email} already has the requested tags "
              f"({sorted(existing)}).")
        return 0

    _patch_subscriber_tags(sub.get("id"), sorted(new), args.api_key)
    delta = sorted(target_tags & (new - existing) if action == "Added"
                   else target_tags & (existing - new))
    print(f"{action} tag(s) {delta} on {args.email}. "
          f"Now tagged for {len(new)} show(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
