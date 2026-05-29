#!/usr/bin/env python3
"""Post a daily network health summary to a webhook.

The pipeline already notifies on *failure* (run-show.yml), but there is no
positive heartbeat: the operator can't tell a healthy day from a silent
outage without opening the dashboard.  This script composes a compact
all-clear / cost / quota / RSS-freshness summary from ``api/dashboard.json``
(plus a live YouTube-quota estimate) and POSTs it to ``NOTIFICATION_WEBHOOK_URL``.

It is a clean no-op when the webhook is unset, so it is safe to wire into the
finalize job unconditionally.  The text builder is pure and unit-tested.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_PATH = PROJECT_ROOT / "api" / "dashboard.json"


def _count(value) -> int:
    """Coerce a dashboard field to a count.

    Dashboard fields vary in shape across versions: a list of items, an
    integer count, or a bool flag.  Normalize all of them to an int so the
    summary is robust to schema drift.
    """
    if value is None or value is False:
        return 0
    if value is True:
        return 1
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def build_summary_text(dashboard: dict, quota: dict | None = None) -> str:
    """Compose a short, human-readable status line from dashboard data.

    Pure function (no I/O) so it can be unit-tested.  Tolerates the dashboard
    expressing list-like fields as either lists, counts, or bool flags.
    """
    network = dashboard.get("network", {}) or {}
    rss = dashboard.get("rss_audit", {}) or {}

    shows_count = network.get("shows_count", "?")
    cost_7d = network.get("total_cost_last_7_days_usd")

    n_alerts = _count(dashboard.get("alerts"))
    n_stale = _count(network.get("stale_shows"))
    n_offline = _count(rss.get("offline"))
    n_raw_gh = _count(rss.get("raw_github_hits"))

    healthy = (n_alerts + n_stale + n_offline) == 0
    icon = "✅" if healthy else "⚠️"
    lines = [f"{icon} Nerra Network daily summary — {dashboard.get('generated_at', 'unknown time')}"]
    lines.append(f"Shows tracked: {shows_count}")
    if isinstance(cost_7d, (int, float)):
        lines.append(f"7-day spend: ${cost_7d:.2f}")

    if quota:
        lines.append(
            f"YouTube quota: {quota.get('total_units', 0)}/{quota.get('daily_quota', 0)} units "
            f"(headroom {quota.get('headroom_units', 0)})"
            + ("  ‼ OVER QUOTA" if quota.get("over_quota") else "")
        )

    if n_stale:
        lines.append(f"⚠️ Stale shows: {n_stale}")
    if n_offline:
        lines.append(f"⚠️ Offline RSS feeds: {n_offline}")
    if n_raw_gh:
        lines.append(f"⚠️ Feeds still using raw.githubusercontent: {n_raw_gh}")
    if n_alerts:
        lines.append(f"⚠️ Alerts: {n_alerts}")

    if healthy:
        lines.append("All feeds fresh, no alerts.")
    return "\n".join(lines)


def _load_dashboard(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"generated_at": "n/a", "_load_error": str(exc), "network": {}}


def _quota_summary() -> dict | None:
    try:
        from engine.youtube_quota import estimate_network_daily_units
        return estimate_network_daily_units(PROJECT_ROOT / "shows")
    except Exception:  # noqa: BLE001
        return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Post a daily network health summary.")
    parser.add_argument("--dashboard", type=Path, default=DASHBOARD_PATH)
    parser.add_argument("--print-only", action="store_true", help="Print the summary; never POST.")
    args = parser.parse_args(argv)

    dashboard = _load_dashboard(args.dashboard)
    text = build_summary_text(dashboard, _quota_summary())
    print(text, flush=True)

    webhook = (os.getenv("NOTIFICATION_WEBHOOK_URL") or "").strip()
    if args.print_only or not webhook:
        if not webhook:
            print("(NOTIFICATION_WEBHOOK_URL unset — summary not posted)", flush=True)
        return 0

    try:
        import requests
        resp = requests.post(webhook, json={"text": text}, timeout=15)
        if resp.status_code >= 300:
            print(f"::warning::Summary webhook returned {resp.status_code} (non-blocking)", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::Summary webhook failed: {exc} (non-blocking)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
