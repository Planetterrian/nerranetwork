#!/usr/bin/env python3
"""Aggregate paid-member counts into ``api/member_metrics.json``.

Nerra Personal has been sellable since Aug 2026 — real Stripe Payment Links,
a Worker that mints and revokes feed tokens, a working sample edition — and
paid conversion has been measured NOWHERE. There is no committed Stripe,
member or MRR artifact anywhere in the repo, so "is anyone paying for this"
could not be answered from the record, which also means no change to the
Personal funnel could be scored. That is what this closes.

**Counts only, never a record.** The Worker's ``/api/admin/personal-specs``
returns each active member's ``first_name``, ``city`` and chosen shows. With
a handful of members a name plus a city identifies a person, and this file is
committed to a public repository, so nothing here writes a name, a city, an
email or a feed token. The output is integers and histograms of SHOW SLUGS.
Same rule as ``scripts/build_personal_feeds.py``: PII-light by construction,
not by reviewer vigilance.

**What it can and cannot see.** The admin endpoint lists only records with
``status == "active"`` and a feed token — i.e. paying members. Free Nerra
accounts (every newsletter signup creates one) are NOT in that list, so
``free_accounts`` stays ``null`` here and the newsletter subscriber count in
``api/audience_headline.json`` remains the measure for the free tier. Null
means unmeasured; it is never written as ``0``.

Clean no-op without ``PERSONAL_ADMIN_TOKEN``: an existing file is left
untouched rather than overwritten with nulls, because a host that cannot
authenticate must not look like a network with no members — the failure mode
``build_personal_feeds`` documents at its own fetch path.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(message)s",
                    stream=sys.stdout)
log = logging.getLogger("build_member_metrics")

API_BASE = os.environ.get("PERSONAL_API_BASE", "https://api.nerranetwork.com")
DEFAULT_OUT = REPO_ROOT / "api" / "member_metrics.json"
HTTP_TIMEOUT = 60


def fetch_specs(token: str) -> Optional[list]:
    """Return the admin endpoint's ``specs`` list, or None on any failure."""
    import requests

    try:
        resp = requests.get(
            f"{API_BASE}/api/admin/personal-specs",
            headers={"Authorization": f"Bearer {token}"},
            timeout=HTTP_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 — never break the nightly job
        log.warning("member metrics: request failed: %s", exc)
        return None
    if resp.status_code == 503:
        # The Worker answers 503 until the operator provisions KV and the
        # bucket. That is "not set up yet", not "nobody subscribed".
        log.info("member metrics: Worker reports not configured (503)")
        return None
    if resp.status_code != 200:
        log.warning("member metrics: HTTP %s from /api/admin/personal-specs",
                    resp.status_code)
        return None
    try:
        payload = resp.json() or {}
    except Exception as exc:  # noqa: BLE001
        log.warning("member metrics: unreadable JSON: %s", exc)
        return None
    specs = payload.get("specs")
    if not isinstance(specs, list):
        log.warning("member metrics: no 'specs' list in response")
        return None
    return specs


def summarise(specs: list) -> Dict[str, Any]:
    """Counts and show histograms — no field that could name a person."""
    tiers: Counter = Counter()
    shows: Counter = Counter()
    addons: Counter = Counter()
    with_city_brief = 0
    on_default_lineup = 0

    for rec in specs:
        if not isinstance(rec, dict):
            continue
        tiers[str(rec.get("tier") or "unknown")] += 1
        for slug in (rec.get("shows") or []):
            if isinstance(slug, str) and slug:
                shows[slug] += 1
        for name in (rec.get("addons") or []):
            if isinstance(name, str) and name:
                addons[name] += 1
        # The COUNT of members who have a city brief, never which city:
        # a city plus a first name identifies someone at this scale.
        if rec.get("city") or (rec.get("cities") or []):
            with_city_brief += 1
        if rec.get("default_lineup"):
            on_default_lineup += 1

    return {
        "paid_active_total": len(specs),
        "by_tier": dict(sorted(tiers.items())),
        "by_addon": dict(sorted(addons.items())),
        "with_city_brief": with_city_brief,
        # Members who never chose 2+ shows and are being served the starter
        # lineup. A product signal: high here means the picker is not landing.
        "on_default_lineup": on_default_lineup,
        "shows_chosen": dict(shows.most_common()),
        # Not derivable from this endpoint — every newsletter signup creates a
        # free account, but the admin list only returns ACTIVE PAID records.
        "free_accounts": None,
        # Stripe is the only source for revenue and trial state and nothing in
        # this repo reads it. Explicitly null so a dashboard tile says
        # "unmeasured" rather than implying zero revenue.
        "mrr_usd": None,
        "trialing": None,
    }


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--specs", default="",
                        help="Read a local specs JSON instead of the Worker "
                             "(testing only; must not contain real members).")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    out_path = Path(args.out)

    if args.specs:
        raw = json.loads(Path(args.specs).read_text(encoding="utf-8"))
        specs = raw.get("specs", raw) if isinstance(raw, dict) else raw
    else:
        token = os.environ.get("PERSONAL_ADMIN_TOKEN", "").strip()
        if not token:
            log.info("PERSONAL_ADMIN_TOKEN unset — skipping member metrics "
                     "(clean no-op)")
            if out_path.exists():
                # Never replace real counts with nulls.
                return 0
            payload = {
                "generated_at": datetime.now(timezone.utc).isoformat(
                    timespec="seconds"),
                "configured": False,
                "note": "PERSONAL_ADMIN_TOKEN not set — membership is "
                        "unmeasured, which is not the same as zero members",
            }
            if args.dry_run:
                print(json.dumps(payload, indent=2))
                return 0
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(payload, indent=2) + "\n",
                                encoding="utf-8")
            log.info("wrote %s (unconfigured placeholder)", out_path)
            return 0
        specs = fetch_specs(token)
        if specs is None:
            log.warning("member metrics: no data this run — leaving %s as is",
                        out_path)
            return 0

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "configured": True,
        **summarise(specs),
    }

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    log.info("wrote %s (paid_active=%s, tiers=%s)", out_path,
             payload["paid_active_total"], payload["by_tier"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
