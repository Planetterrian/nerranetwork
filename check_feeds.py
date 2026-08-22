#!/usr/bin/env python3
"""RSS FEED health auditor for Nerra Network.

Renamed from check_sources.py (Aug 2026): this tool grades whether a FEED
is healthy — reachability, parse quality, freshness, volume. It has no view
on whether anything written FROM a feed is true; that is
scripts/verify_claims.py + engine/claims.py (the source-integrity gate).
The old name implied a guarantee this file never provided.

Checks every RSS source across all show configs for:
  1. Reachability — can we fetch the feed at all?
  2. Parse quality — does feedparser produce valid entries?
  3. Freshness — when was the most recent article published?
  4. Volume — how many articles in the last 24h / 7d?
  5. Content quality — average title length, description richness
  6. Blocked sources — flags any feed matching _blocked_sources.yaml
  7. Candidate discovery — optionally suggests new high-quality sources

Usage:
    python check_feeds.py                  # Audit all shows
    python check_feeds.py tesla            # Audit one show
    python check_feeds.py --suggest tesla  # Suggest new sources for a show
    python check_feeds.py --report         # Generate full JSON report
    python check_feeds.py --grade          # Show letter grades per source
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SHOWS_DIR = Path(__file__).parent / "shows"
BLOCKED_FILE = SHOWS_DIR / "_blocked_sources.yaml"
REPORT_DIR = Path(__file__).parent / "reports"

HEADERS = {
    "User-Agent": "NerraNetwork-SourceAuditor/1.0 (podcast feed checker)"
}
TIMEOUT = 15


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SourceScore:
    """Quality score for a single RSS source."""
    url: str
    label: str
    show: str
    reachable: bool = False
    parse_ok: bool = False
    http_status: int = 0
    response_time_ms: int = 0
    total_entries: int = 0
    entries_24h: int = 0
    entries_7d: int = 0
    newest_article_age_hours: float = -1
    avg_title_length: float = 0
    avg_desc_length: float = 0
    has_descriptions: bool = False
    is_blocked: bool = False
    blocked_reason: str = ""
    error: str = ""
    grade: str = "F"
    score: float = 0.0
    details: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Blocked source checking
# ---------------------------------------------------------------------------

def _load_blocked_sources() -> list[dict]:
    """Load blocked sources from _blocked_sources.yaml."""
    if not BLOCKED_FILE.exists():
        return []
    try:
        import yaml
        with open(BLOCKED_FILE) as f:
            data = yaml.safe_load(f) or {}
        return data.get("blocked", [])
    except Exception as e:
        logger.warning("Could not load blocked sources: %s", e)
        return []


def _extract_domain(url: str) -> str:
    """Extract the registrable domain from a URL or pattern."""
    clean = url.lower().replace("https://", "").replace("http://", "")
    domain = clean.split("/")[0].replace("www.", "")
    return domain


def _is_blocked(url: str, blocked: list[dict]) -> tuple[bool, str]:
    """Check if a URL matches any blocked source using domain-level matching.

    Matches on domain boundaries to avoid false positives like
    'rt.com' matching inside 'breitbart.com'.
    """
    url_domain = _extract_domain(url)
    for entry in blocked:
        pattern = entry.get("url", "").lower().replace("www.", "")
        if not pattern:
            continue
        # Domain-level match: pattern must match the domain or a parent domain
        if url_domain == pattern or url_domain.endswith("." + pattern):
            return True, entry.get("reason", "blocked")
    return False, ""


# ---------------------------------------------------------------------------
# Feed auditing
# ---------------------------------------------------------------------------

def _parse_date(entry) -> Optional[datetime.datetime]:
    """Extract a UTC datetime from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime.datetime(*parsed[:6], tzinfo=datetime.timezone.utc)
            except (ValueError, TypeError):
                pass
    return None


def audit_source(
    url: str,
    label: str,
    show: str,
    blocked: list[dict],
) -> SourceScore:
    """Audit a single RSS source and return a quality score."""
    import feedparser

    result = SourceScore(url=url, label=label, show=show)

    # Check blocked list first
    is_blk, reason = _is_blocked(url, blocked)
    if is_blk:
        result.is_blocked = True
        result.blocked_reason = reason
        result.grade = "X"
        result.details.append(f"BLOCKED: {reason}")

    # Fetch
    start = time.monotonic()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        result.response_time_ms = int((time.monotonic() - start) * 1000)
        result.http_status = resp.status_code
        resp.raise_for_status()
        result.reachable = True
    except requests.RequestException as e:
        result.response_time_ms = int((time.monotonic() - start) * 1000)
        result.error = str(e)[:200]
        result.details.append(f"UNREACHABLE: {result.error}")
        result.grade = "F"
        return result

    # Parse
    try:
        feed = feedparser.parse(resp.content)
        if not feed.entries:
            result.error = "No entries found"
            result.details.append("EMPTY: Feed returned zero entries")
            result.grade = "D"
            return result
        result.parse_ok = True
        result.total_entries = len(feed.entries)
    except Exception as e:
        result.error = str(e)[:200]
        result.details.append(f"PARSE ERROR: {result.error}")
        result.grade = "F"
        return result

    # Analyze entries
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff_24h = now - datetime.timedelta(hours=24)
    cutoff_7d = now - datetime.timedelta(days=7)

    title_lengths = []
    desc_lengths = []
    newest_date = None

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        desc = (entry.get("description", "") or entry.get("summary", "")).strip()
        pub_date = _parse_date(entry)

        if title:
            title_lengths.append(len(title))
        if desc:
            desc_lengths.append(len(desc))

        if pub_date:
            if newest_date is None or pub_date > newest_date:
                newest_date = pub_date
            if pub_date >= cutoff_24h:
                result.entries_24h += 1
            if pub_date >= cutoff_7d:
                result.entries_7d += 1

    if title_lengths:
        result.avg_title_length = sum(title_lengths) / len(title_lengths)
    if desc_lengths:
        result.avg_desc_length = sum(desc_lengths) / len(desc_lengths)
        result.has_descriptions = result.avg_desc_length > 50

    if newest_date:
        age = now - newest_date
        result.newest_article_age_hours = age.total_seconds() / 3600

    # Score calculation (0-100)
    score = 0.0

    # Reachability & speed (20 points)
    score += 10  # reachable
    if result.response_time_ms < 2000:
        score += 5
    if result.response_time_ms < 500:
        score += 5

    # Freshness (30 points)
    if result.newest_article_age_hours >= 0:
        if result.newest_article_age_hours < 24:
            score += 30
        elif result.newest_article_age_hours < 72:
            score += 20
        elif result.newest_article_age_hours < 168:
            score += 10
        else:
            result.details.append(
                f"STALE: Newest article is {result.newest_article_age_hours:.0f}h old"
            )

    # Volume (20 points)
    if result.entries_7d >= 10:
        score += 20
    elif result.entries_7d >= 5:
        score += 15
    elif result.entries_7d >= 2:
        score += 10
    elif result.entries_7d >= 1:
        score += 5

    # Content richness (20 points)
    if result.avg_title_length > 30:
        score += 10
    elif result.avg_title_length > 15:
        score += 5
    if result.has_descriptions:
        score += 10

    # Parse quality (10 points)
    if result.parse_ok:
        score += 5
    if result.total_entries >= 5:
        score += 5

    # Penalties
    if result.is_blocked:
        score = 0

    result.score = min(score, 100)

    # Letter grade
    if result.is_blocked:
        result.grade = "X"
    elif score >= 85:
        result.grade = "A"
    elif score >= 70:
        result.grade = "B"
    elif score >= 55:
        result.grade = "C"
    elif score >= 40:
        result.grade = "D"
    else:
        result.grade = "F"

    return result


# ---------------------------------------------------------------------------
# Show config loading
# ---------------------------------------------------------------------------

def _load_show_sources(show_slug: str) -> list[dict]:
    """Load sources from a show YAML config."""
    import yaml
    yaml_path = SHOWS_DIR / f"{show_slug}.yaml"
    if not yaml_path.exists():
        logger.error("Show config not found: %s", yaml_path)
        return []
    with open(yaml_path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("sources", [])


def _get_all_show_slugs() -> list[str]:
    """Get all show slugs from YAML files in shows/."""
    slugs = []
    for p in sorted(SHOWS_DIR.glob("*.yaml")):
        if p.name.startswith("_"):
            continue
        slugs.append(p.stem)
    return slugs


# ---------------------------------------------------------------------------
# Main audit logic
# ---------------------------------------------------------------------------

def audit_show(show_slug: str, blocked: list[dict]) -> list[SourceScore]:
    """Audit all sources for a single show."""
    sources = _load_show_sources(show_slug)
    if not sources:
        logger.warning("No sources found for show: %s", show_slug)
        return []

    logger.info("Auditing %d sources for [%s]...", len(sources), show_slug)
    results = []
    for src in sources:
        url = src.get("url", "")
        label = src.get("label", "Unknown")
        if not url:
            continue
        result = audit_source(url, label, show_slug, blocked)
        results.append(result)
        # Status indicator
        icon = {"A": "+", "B": "+", "C": "~", "D": "!", "F": "X", "X": "!!"}
        logger.info(
            "  [%s] %s %s (%s) — score: %.0f, 7d: %d articles, age: %s",
            result.grade,
            icon.get(result.grade, "?"),
            label,
            f"{result.response_time_ms}ms",
            result.score,
            result.entries_7d,
            f"{result.newest_article_age_hours:.0f}h" if result.newest_article_age_hours >= 0 else "unknown",
        )
        if result.details:
            for d in result.details:
                logger.info("      %s", d)

    return results


def print_summary(all_results: list[SourceScore]) -> None:
    """Print a summary table of all audited sources."""
    if not all_results:
        print("No sources audited.")
        return

    # Group by show
    by_show: dict[str, list[SourceScore]] = {}
    for r in all_results:
        by_show.setdefault(r.show, []).append(r)

    print("\n" + "=" * 80)
    print("NERRA NETWORK — SOURCE QUALITY AUDIT")
    print("=" * 80)

    total_sources = len(all_results)
    grades = [r.grade for r in all_results]
    blocked_count = sum(1 for r in all_results if r.is_blocked)
    unreachable = sum(1 for r in all_results if not r.reachable)
    stale = sum(1 for r in all_results if r.newest_article_age_hours > 168)

    print(f"\nTotal sources: {total_sources}")
    print(f"Grade distribution: A={grades.count('A')} B={grades.count('B')} "
          f"C={grades.count('C')} D={grades.count('D')} F={grades.count('F')} "
          f"X(blocked)={grades.count('X')}")
    if blocked_count:
        print(f"  !! {blocked_count} BLOCKED source(s) found in configs!")
    if unreachable:
        print(f"  !! {unreachable} UNREACHABLE source(s)")
    if stale:
        print(f"  !! {stale} STALE source(s) (no articles in 7+ days)")

    for show, results in sorted(by_show.items()):
        show_avg = sum(r.score for r in results) / len(results) if results else 0
        print(f"\n{'─' * 80}")
        print(f"  {show.upper()} — {len(results)} sources, avg score: {show_avg:.0f}")
        print(f"{'─' * 80}")
        print(f"  {'Grade':>5}  {'Score':>5}  {'7d':>4}  {'Age':>6}  {'Ms':>5}  Source")
        print(f"  {'─'*5}  {'─'*5}  {'─'*4}  {'─'*6}  {'─'*5}  {'─'*30}")

        for r in sorted(results, key=lambda x: x.score, reverse=True):
            age_str = (
                f"{r.newest_article_age_hours:.0f}h"
                if r.newest_article_age_hours >= 0
                else "  n/a"
            )
            flag = ""
            if r.is_blocked:
                flag = " !! BLOCKED"
            elif not r.reachable:
                flag = " !! DOWN"
            elif r.newest_article_age_hours > 168:
                flag = " ! stale"
            print(
                f"  [{r.grade:>1}]    {r.score:>5.0f}  {r.entries_7d:>4}  "
                f"{age_str:>6}  {r.response_time_ms:>4}ms  {r.label}{flag}"
            )

    # Action items
    problems = [r for r in all_results if r.grade in ("D", "F", "X")]
    if problems:
        print(f"\n{'=' * 80}")
        print("ACTION ITEMS")
        print(f"{'=' * 80}")
        for r in problems:
            if r.is_blocked:
                print(f"  REMOVE [{r.show}] {r.label} — {r.blocked_reason}")
            elif not r.reachable:
                print(f"  CHECK  [{r.show}] {r.label} — unreachable ({r.error[:60]})")
            elif r.newest_article_age_hours > 168:
                print(f"  REVIEW [{r.show}] {r.label} — stale ({r.newest_article_age_hours:.0f}h since last article)")
            else:
                print(f"  REVIEW [{r.show}] {r.label} — low quality (score {r.score:.0f})")


def save_report(all_results: list[SourceScore], path: Path) -> None:
    """Save full audit report as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "audit_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_sources": len(all_results),
        "results": [asdict(r) for r in all_results],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Report saved to %s", path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Audit RSS source quality across Nerra Network shows"
    )
    parser.add_argument(
        "shows",
        nargs="*",
        help="Show slug(s) to audit (default: all shows)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Save full JSON report to reports/",
    )
    parser.add_argument(
        "--grade",
        action="store_true",
        help="Show letter grades (default behavior)",
    )
    parser.add_argument(
        "--check-blocked",
        action="store_true",
        help="Only check for blocked sources in configs (fast, no network)",
    )
    args = parser.parse_args()

    blocked = _load_blocked_sources()
    show_slugs = args.shows or _get_all_show_slugs()

    # Fast blocked-only check (no network calls)
    if args.check_blocked:
        found_blocked = False
        for slug in show_slugs:
            sources = _load_show_sources(slug)
            for src in sources:
                is_blk, reason = _is_blocked(src.get("url", ""), blocked)
                if is_blk:
                    print(f"BLOCKED [{slug}] {src.get('label', '?')}: {reason}")
                    found_blocked = True
        if not found_blocked:
            print("No blocked sources found in any config.")
        sys.exit(1 if found_blocked else 0)

    # Full audit
    all_results = []
    for slug in show_slugs:
        results = audit_show(slug, blocked)
        all_results.extend(results)

    print_summary(all_results)

    if args.report:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORT_DIR / f"source_audit_{timestamp}.json"
        save_report(all_results, report_path)

    # Exit with error if blocked sources found in configs
    if any(r.is_blocked for r in all_results):
        sys.exit(1)


if __name__ == "__main__":
    main()
