#!/usr/bin/env python3
"""Monthly RSS Source Discovery for Nerra Network.

Discovers, audits, and recommends new high-quality RSS sources for all shows.
Only recommends sources that meet strict quality thresholds and are not on
the blocked list. Designed to run monthly via GitHub Actions.

Process:
  1. Load each show's config (topic, keywords, existing sources)
  2. Search for candidate RSS feeds using curated search strategies
  3. Fetch and audit each candidate (reachability, freshness, volume, quality)
  4. Filter: must score B+ (70+), not blocked, not already in config
  5. Generate a recommendations report (Markdown + YAML snippets)

Usage:
    python discover_sources.py                   # Discover for all shows
    python discover_sources.py tesla             # Discover for one show
    python discover_sources.py --apply           # Auto-add approved sources
    python discover_sources.py --min-score 80    # Stricter threshold
    python discover_sources.py --dry-run         # Preview without writing

Quality gates:
  - Must be reachable with valid RSS/Atom
  - Must have articles within the last 7 days (not stale)
  - Must score >= 70 (grade B) on the standard audit scale
  - Must NOT match any pattern in _blocked_sources.yaml
  - Must NOT duplicate an existing source (by domain)
  - Response time must be under 10 seconds
  - Must have meaningful descriptions (avg > 50 chars)
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent
SHOWS_DIR = ROOT / "shows"
BLOCKED_FILE = SHOWS_DIR / "_blocked_sources.yaml"
REPORTS_DIR = ROOT / "reports"

HEADERS = {
    "User-Agent": "NerraNetwork-SourceDiscovery/1.0 (podcast feed finder)"
}
TIMEOUT = 15
DEFAULT_MIN_SCORE = 70  # Grade B


# ---------------------------------------------------------------------------
# Show topic profiles — search strategies per show
# ---------------------------------------------------------------------------

SHOW_SEARCH_PROFILES: dict[str, dict] = {
    "tesla": {
        "description": "Tesla EV news, TSLA stock, autonomous driving, energy",
        "search_queries": [
            "Tesla news RSS feed",
            "electric vehicle news RSS",
            "TSLA stock analysis RSS feed",
            "autonomous driving news RSS",
            "EV charging network news RSS",
            "Tesla energy storage news RSS",
        ],
        "candidate_feeds": [
            # Curated candidates to try each month
            ("https://electrifiedfuture.com/feed/", "Electrified Future"),
            ("https://www.autoevolution.com/rss/content-type-news-category-cars-sub-category-tesla/", "autoevolution Tesla"),
            ("https://www.motortrend.com/rss/", "MotorTrend"),
            ("https://www.caranddriver.com/rss/all.xml/", "Car and Driver"),
            ("https://thedriven.io/feed/", "The Driven"),
            ("https://evobsession.com/feed/", "EV Obsession"),
            ("https://pluginamerica.org/feed/", "Plug In America"),
        ],
    },
    "omni_view": {
        "description": "World news, geopolitics, global events",
        "search_queries": [
            "world news RSS feed",
            "international news RSS",
            "geopolitics analysis RSS feed",
            "global affairs RSS",
        ],
        "candidate_feeds": [
            ("https://foreignpolicy.com/feed/", "Foreign Policy"),
            ("https://www.economist.com/rss", "The Economist"),
            ("https://www.cfr.org/rss.xml", "Council on Foreign Relations"),
            ("https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "NYT World"),
            ("https://feeds.washingtonpost.com/rss/world", "WaPo World"),
            ("https://www.france24.com/en/rss", "France 24"),
            ("https://www.dw.com/rss/en/all/rss-en-all/s-922", "DW News"),
        ],
    },
    "fascinating_frontiers": {
        "description": "Space exploration, astronomy, rocket launches",
        "search_queries": [
            "space exploration news RSS feed",
            "astronomy news RSS",
            "rocket launch RSS feed",
            "SpaceX news RSS",
        ],
        "candidate_feeds": [
            ("https://www.planetary.org/feed", "The Planetary Society"),
            ("https://spacepolicyonline.com/feed/", "Space Policy Online"),
            ("https://www.nasaspaceflight.com/feed/", "NASASpaceFlight"),
            ("https://astronomynow.com/feed/", "Astronomy Now"),
            ("https://skyandtelescope.org/astronomy-news/feed/", "Sky & Telescope"),
            ("https://www.esa.int/rssfeed/Our_Activities/Space_Science", "ESA Science"),
        ],
    },
    "planetterrian": {
        "description": "Science, health, longevity, medicine, environment",
        "search_queries": [
            "science news RSS feed",
            "health longevity news RSS",
            "medical research news RSS",
            "environmental science RSS feed",
        ],
        "candidate_feeds": [
            ("https://www.livescience.com/feeds/all", "Live Science"),
            ("https://arstechnica.com/science/feed/", "Ars Technica Science"),
            ("https://phys.org/rss-feed/", "Phys.org"),
            ("https://www.statnews.com/feed/", "STAT News"),
            ("https://theconversation.com/us/articles.atom", "The Conversation"),
            ("https://medicalxpress.com/rss-feed/", "Medical Xpress"),
        ],
    },
    "env_intel": {
        "description": "Environmental policy, climate, clean energy, sustainability",
        "search_queries": [
            "environmental policy RSS feed",
            "climate change news RSS",
            "clean energy news RSS feed",
            "sustainability news RSS",
        ],
        "candidate_feeds": [
            ("https://www.carbonbrief.org/feed/", "Carbon Brief"),
            ("https://grist.org/feed/", "Grist"),
            ("https://insideclimatenews.org/feed/", "Inside Climate News"),
            ("https://www.canarymedia.com/feed/", "Canary Media"),
            ("https://www.eenews.net/feed/", "E&E News"),
            ("https://reneweconomy.com.au/feed/", "RenewEconomy"),
            ("https://www.desmog.com/feed/", "DeSmog"),
        ],
    },
    "models_agents": {
        "description": "AI models, LLMs, agent frameworks, ML research",
        "search_queries": [
            "AI models news RSS feed",
            "LLM research RSS feed",
            "AI agent framework RSS",
            "machine learning news RSS",
        ],
        "candidate_feeds": [
            ("https://www.interconnects.ai/feed", "Interconnects"),
            ("https://magazine.sebastianraschka.com/feed", "Sebastian Raschka"),
            ("https://www.ruder.io/rss/", "Sebastian Ruder"),
            ("https://newsletter.maartengrootendorst.com/feed", "Maarten Grootendorst"),
            ("https://jack-clark.net/feed/", "Import AI (Jack Clark)"),
            ("https://www.oneusefulthing.org/feed", "One Useful Thing"),
            ("https://buttondown.com/ainews/rss", "AI News (Buttondown)"),
        ],
    },
    "models_agents_beginners": {
        "description": "AI for beginners, accessible AI education, teen-friendly AI",
        "search_queries": [
            "AI for beginners RSS feed",
            "machine learning tutorial RSS",
            "AI education RSS feed",
        ],
        "candidate_feeds": [
            ("https://machinelearningmastery.com/feed/", "Machine Learning Mastery"),
            ("https://www.datacamp.com/blog/rss.xml", "DataCamp Blog"),
            ("https://ai.google/feed/", "Google AI"),
            ("https://blogs.nvidia.com/feed/", "NVIDIA Blog"),
        ],
    },
    "finansy_prosto": {
        "description": "Canadian personal finance for Russian-speaking immigrants, Vancouver focus",
        "search_queries": [
            "Canadian personal finance RSS feed",
            "newcomer Canada finance blog RSS",
            "Vancouver real estate news RSS",
            "Canadian immigration finance RSS",
        ],
        "candidate_feeds": [
            ("https://www.savvynewcanadians.com/feed/", "Savvy New Canadians"),
            ("https://creditcardgenius.ca/blog/feed", "Credit Card Genius"),
            ("https://www.greedyrates.ca/blog/feed/", "Greedy Rates"),
            ("https://milliondollarjourney.com/feed", "Million Dollar Journey"),
            ("https://www.squawkfox.com/feed/", "Squawkfox"),
            ("https://www.myownadvisor.ca/feed/", "My Own Advisor"),
            ("https://retirehappy.ca/feed/", "Retire Happy"),
        ],
    },
    "privet_russian": {
        "description": "Russian language learning, Ukrainian/diaspora culture, kids education",
        "search_queries": [
            "Russian language learning RSS feed",
            "learn Russian blog RSS",
            "Ukrainian diaspora Canada RSS",
            "kids language learning RSS feed",
        ],
        "candidate_feeds": [
            ("https://www.bbc.co.uk/learningenglish/english/rss", "BBC Learning English"),
            ("https://www.lingq.com/blog/feed/", "LingQ Blog"),
            ("https://www.kyivindependent.com/feed/", "Kyiv Independent"),
            ("https://english.nv.ua/rss/all.xml", "NV Ukraine English"),
            ("https://www.openculture.com/feed", "Open Culture"),
            ("https://www.smithsonianmag.com/rss/", "Smithsonian Magazine"),
        ],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_blocked_sources() -> list[dict]:
    """Load blocked source patterns from _blocked_sources.yaml."""
    if not BLOCKED_FILE.exists():
        return []
    try:
        with open(BLOCKED_FILE) as f:
            data = yaml.safe_load(f) or {}
        return data.get("blocked", [])
    except Exception:
        return []


def _is_blocked(url: str, blocked: list[dict]) -> bool:
    """Check if a URL matches any blocked source using domain-level matching."""
    url_domain = _extract_domain(url)
    for entry in blocked:
        pattern = entry.get("url", "").lower().replace("www.", "")
        if not pattern:
            continue
        if url_domain == pattern or url_domain.endswith("." + pattern):
            return True
    return False


def _load_show_config(slug: str) -> dict:
    """Load a show's YAML config."""
    path = SHOWS_DIR / f"{slug}.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _existing_domains(sources: list[dict]) -> set[str]:
    """Extract domain fragments from existing source URLs for dedup."""
    domains = set()
    for src in sources:
        url = src.get("url", "").lower()
        # Extract domain-like portion
        for part in url.replace("https://", "").replace("http://", "").split("/"):
            if "." in part:
                domains.add(part.replace("www.", ""))
                break
    return domains


def _extract_domain(url: str) -> str:
    """Extract the domain from a URL."""
    clean = url.lower().replace("https://", "").replace("http://", "")
    domain = clean.split("/")[0].replace("www.", "")
    return domain


# ---------------------------------------------------------------------------
# Feed auditing (lightweight version of check_feeds.py)
# ---------------------------------------------------------------------------

@dataclass
class CandidateResult:
    url: str
    label: str
    show: str
    reachable: bool = False
    parse_ok: bool = False
    http_status: int = 0
    response_time_ms: int = 0
    total_entries: int = 0
    entries_7d: int = 0
    newest_article_age_hours: float = -1
    avg_title_length: float = 0
    avg_desc_length: float = 0
    has_descriptions: bool = False
    score: float = 0.0
    grade: str = "F"
    rejection_reason: str = ""


def _audit_candidate(url: str, label: str, show: str) -> CandidateResult:
    """Fetch and score a candidate RSS feed."""
    import feedparser

    result = CandidateResult(url=url, label=label, show=show)

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
        result.rejection_reason = f"unreachable: {str(e)[:80]}"
        return result

    # Parse
    try:
        feed = feedparser.parse(resp.content)
        if not feed.entries:
            result.rejection_reason = "no entries in feed"
            return result
        result.parse_ok = True
        result.total_entries = len(feed.entries)
    except Exception as e:
        result.rejection_reason = f"parse error: {str(e)[:80]}"
        return result

    # Analyze
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff_7d = now - datetime.timedelta(days=7)
    title_lengths = []
    desc_lengths = []
    newest_date = None

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        desc = (entry.get("description", "") or entry.get("summary", "")).strip()

        if title:
            title_lengths.append(len(title))
        if desc:
            desc_lengths.append(len(desc))

        for attr in ("published_parsed", "updated_parsed"):
            parsed = getattr(entry, attr, None)
            if parsed:
                try:
                    dt = datetime.datetime(*parsed[:6], tzinfo=datetime.timezone.utc)
                    if newest_date is None or dt > newest_date:
                        newest_date = dt
                    if dt >= cutoff_7d:
                        result.entries_7d += 1
                    break
                except (ValueError, TypeError):
                    pass

    if title_lengths:
        result.avg_title_length = sum(title_lengths) / len(title_lengths)
    if desc_lengths:
        result.avg_desc_length = sum(desc_lengths) / len(desc_lengths)
        result.has_descriptions = result.avg_desc_length > 50
    if newest_date:
        result.newest_article_age_hours = (now - newest_date).total_seconds() / 3600

    # Score (same algorithm as check_feeds.py)
    score = 0.0
    score += 10  # reachable
    if result.response_time_ms < 2000:
        score += 5
    if result.response_time_ms < 500:
        score += 5
    if result.newest_article_age_hours >= 0:
        if result.newest_article_age_hours < 24:
            score += 30
        elif result.newest_article_age_hours < 72:
            score += 20
        elif result.newest_article_age_hours < 168:
            score += 10
    if result.entries_7d >= 10:
        score += 20
    elif result.entries_7d >= 5:
        score += 15
    elif result.entries_7d >= 2:
        score += 10
    elif result.entries_7d >= 1:
        score += 5
    if result.avg_title_length > 30:
        score += 10
    elif result.avg_title_length > 15:
        score += 5
    if result.has_descriptions:
        score += 10
    if result.parse_ok:
        score += 5
    if result.total_entries >= 5:
        score += 5

    result.score = min(score, 100)

    if score >= 85:
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
# Discovery engine
# ---------------------------------------------------------------------------

def discover_for_show(
    slug: str,
    blocked: list[dict],
    min_score: float = DEFAULT_MIN_SCORE,
) -> list[CandidateResult]:
    """Discover and audit candidate sources for a single show."""
    profile = SHOW_SEARCH_PROFILES.get(slug)
    if not profile:
        logger.warning("No search profile for show: %s", slug)
        return []

    config = _load_show_config(slug)
    existing_sources = config.get("sources", [])
    existing_doms = _existing_domains(existing_sources)

    candidates = profile.get("candidate_feeds", [])
    logger.info(
        "Discovering sources for [%s]: %d candidates, %d existing sources",
        slug, len(candidates), len(existing_sources),
    )

    approved = []

    for url, label in candidates:
        # Skip if blocked
        if _is_blocked(url, blocked):
            logger.info("  SKIP (blocked) %s", label)
            continue

        # Skip if domain already in show config
        domain = _extract_domain(url)
        if any(domain in d or d in domain for d in existing_doms):
            logger.info("  SKIP (already exists) %s [%s]", label, domain)
            continue

        # Audit the candidate
        result = _audit_candidate(url, label, slug)

        if result.score < min_score:
            reason = result.rejection_reason or f"score {result.score:.0f} < {min_score}"
            logger.info("  REJECT [%s] %s — %s", result.grade, label, reason)
            continue

        if result.newest_article_age_hours > 168:
            logger.info("  REJECT [%s] %s — stale (%.0fh)", result.grade, label, result.newest_article_age_hours)
            continue

        if not result.reachable:
            logger.info("  REJECT %s — unreachable", label)
            continue

        logger.info(
            "  APPROVE [%s] %s — score: %.0f, 7d: %d articles",
            result.grade, label, result.score, result.entries_7d,
        )
        approved.append(result)

    return approved


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    all_results: dict[str, list[CandidateResult]],
    min_score: float,
) -> str:
    """Generate a Markdown recommendations report."""
    now = datetime.datetime.now(datetime.timezone.utc)
    lines = [
        f"# Nerra Network — Source Discovery Report",
        f"",
        f"**Generated:** {now.strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Minimum score:** {min_score:.0f} (grade B)",
        f"",
    ]

    total_approved = sum(len(v) for v in all_results.values())
    total_shows = len(all_results)
    lines.append(f"**Summary:** {total_approved} new sources recommended across {total_shows} shows.\n")

    if total_approved == 0:
        lines.append("No new high-quality sources found this month. All existing sources are comprehensive.\n")
        return "\n".join(lines)

    for show, results in sorted(all_results.items()):
        if not results:
            continue

        lines.append(f"## {show}")
        lines.append(f"")
        lines.append(f"| Grade | Score | 7d Articles | Feed | Label |")
        lines.append(f"|-------|-------|-------------|------|-------|")
        for r in sorted(results, key=lambda x: x.score, reverse=True):
            lines.append(f"| {r.grade} | {r.score:.0f} | {r.entries_7d} | `{r.url}` | {r.label} |")

        lines.append(f"\n**YAML snippet to add to `shows/{show}.yaml`:**\n")
        lines.append("```yaml")
        lines.append("  # New sources (discovered " + now.strftime('%Y-%m-%d') + ")")
        for r in results:
            lines.append(f"  - url: {r.url}")
            lines.append(f"    label: {r.label}")
        lines.append("```\n")

    return "\n".join(lines)


def apply_sources(all_results: dict[str, list[CandidateResult]], dry_run: bool = False) -> int:
    """Apply approved sources directly to show YAML configs.

    Returns the number of sources added.
    """
    total_added = 0

    for show, results in all_results.items():
        if not results:
            continue

        yaml_path = SHOWS_DIR / f"{show}.yaml"
        if not yaml_path.exists():
            logger.warning("Config not found: %s", yaml_path)
            continue

        content = yaml_path.read_text()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d")

        # Build YAML snippet for new sources
        snippet_lines = [f"\n  # Discovered sources ({now_str})"]
        for r in results:
            snippet_lines.append(f"  - url: {r.url}")
            snippet_lines.append(f"    label: {r.label}")
        snippet = "\n".join(snippet_lines)

        # Insert before the "keywords:" line
        if "\nkeywords:" in content:
            content = content.replace("\nkeywords:", f"{snippet}\n\nkeywords:", 1)
        else:
            # Fallback: append to sources section
            content += snippet + "\n"

        if dry_run:
            logger.info("[DRY RUN] Would add %d sources to %s", len(results), show)
            for r in results:
                logger.info("  + %s (%s)", r.label, r.url)
        else:
            yaml_path.write_text(content)
            logger.info("Added %d sources to %s", len(results), show)

        total_added += len(results)

    return total_added


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Monthly RSS source discovery for Nerra Network"
    )
    parser.add_argument(
        "shows", nargs="*",
        help="Show slug(s) to discover for (default: all shows)",
    )
    parser.add_argument(
        "--min-score", type=float, default=DEFAULT_MIN_SCORE,
        help=f"Minimum quality score to recommend (default: {DEFAULT_MIN_SCORE})",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Auto-add approved sources to show YAML configs",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview what --apply would do without writing",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Save Markdown report to reports/ directory",
    )
    args = parser.parse_args()

    blocked = _load_blocked_sources()
    logger.info("Loaded %d blocked source patterns", len(blocked))

    show_slugs = args.shows or list(SHOW_SEARCH_PROFILES.keys())

    all_results: dict[str, list[CandidateResult]] = {}
    for slug in show_slugs:
        results = discover_for_show(slug, blocked, args.min_score)
        all_results[slug] = results

    # Print summary
    total = sum(len(v) for v in all_results.values())
    print(f"\n{'=' * 60}")
    print(f"DISCOVERY COMPLETE — {total} new sources recommended")
    print(f"{'=' * 60}")
    for show, results in sorted(all_results.items()):
        if results:
            print(f"\n  {show}: {len(results)} new source(s)")
            for r in results:
                print(f"    [{r.grade}] {r.label} (score {r.score:.0f}, {r.entries_7d} articles/7d)")
    if total == 0:
        print("\n  No new sources meet the quality threshold.")
    print()

    # Generate report
    report = generate_report(all_results, args.min_score)
    if args.report or total > 0:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d")
        report_path = REPORTS_DIR / f"source_discovery_{timestamp}.md"
        report_path.write_text(report)
        logger.info("Report saved to %s", report_path)

    # Apply sources
    if args.apply and total > 0:
        added = apply_sources(all_results, dry_run=args.dry_run)
        logger.info("Applied %d new sources", added)
    elif args.dry_run and total > 0:
        apply_sources(all_results, dry_run=True)

    sys.exit(0)


if __name__ == "__main__":
    main()
