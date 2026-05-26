#!/usr/bin/env python3
"""Audit all RSS feed URLs across show YAML configs.

Reports feed health (HTTP status, entry count, freshness) and outputs
both a human-readable summary and a JSON report.

Usage:
    python scripts/audit_feeds.py              # audit all shows
    python scripts/audit_feeds.py --show tesla # audit a single show
"""
import argparse
import datetime
import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import feedparser
import requests
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOWS_DIR = ROOT / "shows"
DATA_DIR = ROOT / "data"
SKIP_FILES = {"_defaults.yaml", "_blocked_sources.yaml"}

HEADERS = {
    "User-Agent": "PodcastBot/1.0 (+https://github.com/Planetterrian/nerranetwork)"
}
TIMEOUT = 15


def _parse_date(entry) -> datetime.datetime | None:
    """Extract a UTC datetime from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        tp = getattr(entry, attr, None) or entry.get(attr)
        if tp:
            try:
                from calendar import timegm
                return datetime.datetime.fromtimestamp(
                    timegm(tp), tz=datetime.timezone.utc
                )
            except Exception:
                pass
    return None


def audit_feed(url: str) -> dict:
    """Fetch and analyse a single RSS feed URL."""
    result = {
        "url": url,
        "status": None,
        "error": None,
        "entry_count": 0,
        "latest_entry_date": None,
        "latest_age_hours": None,
        "fresh": False,
    }
    now = datetime.datetime.now(datetime.timezone.utc)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        result["status"] = resp.status_code
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        result["error"] = "TIMEOUT"
        return result
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"CONNECTION_ERROR: {str(e)[:80]}"
        return result
    except requests.exceptions.HTTPError:
        result["error"] = f"HTTP {result['status']}"
        return result
    except Exception as e:
        result["error"] = str(e)[:120]
        return result

    feed = feedparser.parse(resp.content)
    result["entry_count"] = len(feed.entries)

    if not feed.entries:
        return result

    dates = []
    for entry in feed.entries:
        d = _parse_date(entry)
        if d:
            dates.append(d)

    if dates:
        latest = max(dates)
        result["latest_entry_date"] = latest.isoformat()
        age = now - latest
        result["latest_age_hours"] = round(age.total_seconds() / 3600, 1)
        result["fresh"] = result["latest_age_hours"] <= 72

    return result


def _format_age(hours: float | None) -> str:
    if hours is None:
        return "no dates"
    if hours < 1:
        return f"{int(hours * 60)}m ago"
    if hours < 48:
        return f"{hours:.0f}h ago"
    return f"{hours / 24:.1f}d ago"


def _status_icon(result: dict) -> str:
    if result["error"]:
        return "\u274c"  # red X
    if not result["fresh"] and result["entry_count"] > 0:
        return "\u26a0\ufe0f"  # warning
    if result["entry_count"] == 0:
        return "\u26a0\ufe0f"
    return "\u2705"  # green check


def main():
    parser = argparse.ArgumentParser(description="Audit RSS feed health")
    parser.add_argument("--show", help="Audit a single show (slug)")
    args = parser.parse_args()

    # Collect feeds from YAML configs
    show_feeds: dict[str, list[dict]] = {}
    for cfg_path in sorted(SHOWS_DIR.glob("*.yaml")):
        if cfg_path.name in SKIP_FILES:
            continue
        slug = cfg_path.stem
        if args.show and args.show not in slug:
            continue
        cfg = yaml.safe_load(cfg_path.read_text())
        sources = cfg.get("sources", [])
        feeds = []
        for s in sources:
            if isinstance(s, dict) and s.get("url"):
                feeds.append({"url": s["url"], "label": s.get("label", "")})
            elif isinstance(s, str):
                feeds.append({"url": s, "label": ""})
        if feeds:
            show_feeds[slug] = feeds

    if not show_feeds:
        print("No shows found to audit.")
        return

    # Flatten all unique URLs for concurrent fetching
    all_urls = {}
    for slug, feeds in show_feeds.items():
        for f in feeds:
            all_urls[f["url"]] = f.get("label", "")

    print(f"Auditing {len(all_urls)} unique feed URLs across {len(show_feeds)} show(s)...\n")

    # Fetch all feeds concurrently
    results_map: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        future_to_url = {pool.submit(audit_feed, url): url for url in all_urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results_map[url] = future.result()
            except Exception as e:
                results_map[url] = {"url": url, "error": str(e), "status": None,
                                     "entry_count": 0, "latest_entry_date": None,
                                     "latest_age_hours": None, "fresh": False}

    # Print per-show summary
    any_issues = False
    report = {"date": datetime.date.today().isoformat(), "shows": {}}

    for slug, feeds in sorted(show_feeds.items()):
        print(f"Show: {slug}")
        show_results = []
        for f in feeds:
            r = results_map.get(f["url"], {})
            show_results.append(r)
            icon = _status_icon(r)
            status_str = str(r.get("status", "")) or r.get("error", "ERR")
            entries = r.get("entry_count", 0)
            age = _format_age(r.get("latest_age_hours"))
            freshness = "FRESH" if r.get("fresh") else ("DEAD" if r.get("error") else "STALE")
            label = f["label"] or f["url"][:50]

            if freshness != "FRESH":
                any_issues = True

            entry_str = f"{entries} entries" if entries else "0 entries"
            print(f"  {icon} {f['url']:<60} {status_str:<6} {entry_str:<14} Latest: {age:<12} {freshness}")

        report["shows"][slug] = show_results
        print()

    # Write JSON report
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    report_path = DATA_DIR / f"feed_audit_{datetime.date.today().isoformat()}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"JSON report saved to {report_path}")

    # Summary
    total = len(all_urls)
    fresh = sum(1 for r in results_map.values() if r.get("fresh"))
    dead = sum(1 for r in results_map.values() if r.get("error"))
    stale = total - fresh - dead
    print(f"\nSummary: {fresh} fresh, {stale} stale, {dead} dead out of {total} feeds")

    sys.exit(1 if any_issues else 0)


if __name__ == "__main__":
    main()
