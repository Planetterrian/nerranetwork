#!/usr/bin/env python3
"""Report site URLs that receive real traffic but have no file behind them.

A static site cannot 404 quietly: GitHub Pages serves ``404.html`` (which
carries the GA4 tag), so a dead URL that is still linked or still indexed
shows up in ``api/ga4_stats.json`` as a landing page with a 100% bounce rate.
Checked on 2026-09-18, **49 of 188 listed landing sessions — 26% — landed on a
path with no file**: the thirteen DP Pod blog posts removed in the Aug-10
catalogue purge, plus a cluster of ``blog/dp_pod/<nav target>`` paths left over
from a crawl of posts whose chrome links were relative before ``path_prefix``
was fixed.

Nothing in the pipeline noticed, because every check the site has asks whether
the pages it GENERATES are sound — never whether the pages people ASK for
exist. This script closes that gap from the other end: it reads the measured
landing pages and checks them against the working tree.

A path that belongs to the past is answered with a stub from
``site/redirects.yaml`` (see ``generate_redirect_stubs`` in
``generate_html.py``). This script is the instrument that says which paths
need one; it never writes anything.

Loud but non-blocking by default, like the other preflights. ``--strict``
exits non-zero so a guard job can hard-fail.

    python scripts/audit_dead_urls.py
    python scripts/audit_dead_urls.py --strict
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
GA4_STATS = ROOT / "api" / "ga4_stats.json"
REDIRECTS_FILE = ROOT / "site" / "redirects.yaml"

# Paths GA4 reports that are not site pages at all.
_NON_PATHS = {"", "/", "(not set)", "(none)"}


def _normalise(raw: str) -> str:
    """GA4's landing path -> a repo-relative file path, or "" to skip.

    ``landingPagePlusQueryString`` is free text: it carries query strings,
    occasionally a fragment, and — when a page's own copy leaked into the
    URL — trailing prose after a semicolon (a real row reads
    ``/age-of-ai-apply.html; it takes a couple of minutes``).
    """
    value = (raw or "").strip()
    if value in _NON_PATHS:
        return ""
    value = value.split(";", 1)[0].strip()
    path = urlparse(value).path or value
    path = unquote(path).strip().lstrip("/")
    if not path or path in _NON_PATHS:
        return ""
    # A directory URL is served by its index.html.
    if path.endswith("/"):
        path += "index.html"
    return path


def accepted_404_paths(redirects_file: Path = REDIRECTS_FILE) -> set:
    """Paths ``site/redirects.yaml`` says should stay 404 (feed URLs that
    never existed, for instance). Reported as accepted, never as a hole, so
    the audit's output is only ever news."""
    try:
        import yaml
        data = yaml.safe_load(redirects_file.read_text(encoding="utf-8")) or {}
    except Exception:
        return set()
    return {
        str(entry["path"]).strip().lstrip("/")
        for entry in (data.get("accepted_404") or [])
        if isinstance(entry, dict) and entry.get("path")
    }


def find_dead_landing_paths(
    stats: dict, root: Path = ROOT, accepted: set = None
) -> list:
    """[(path, sessions, bounce_rate)] for measured landings with no file.

    Sorted by sessions descending: the first row is the most expensive hole.
    Paths in *accepted* are left out — they are 404 on purpose.
    """
    accepted = accepted if accepted is not None else accepted_404_paths()
    dead = []
    for row in stats.get("landing_pages") or []:
        path = _normalise(row.get("landingPagePlusQueryString", ""))
        if not path or path in accepted:
            continue
        if (root / path).exists():
            continue
        dead.append((
            path,
            int(row.get("sessions") or 0),
            float(row.get("bounceRate") or 0.0),
        ))
    dead.sort(key=lambda r: (-r[1], r[0]))
    return dead


def total_landing_sessions(stats: dict) -> int:
    return sum(
        int(row.get("sessions") or 0)
        for row in stats.get("landing_pages") or []
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--strict", action="store_true",
        help="exit non-zero when any measured landing path is missing",
    )
    ap.add_argument(
        "--stats", default=str(GA4_STATS),
        help=f"GA4 stats file to read (default: {GA4_STATS})",
    )
    args = ap.parse_args(argv)

    stats_path = Path(args.stats)
    if not stats_path.exists():
        print(
            "::warning title=Dead-URL audit::"
            f"{stats_path} not found — run scripts/fetch_ga4_stats.py first. "
            "No audit performed."
        )
        return 0

    try:
        stats = json.loads(stats_path.read_text())
    except Exception as exc:  # malformed file is worth saying out loud
        print(f"::warning title=Dead-URL audit::could not read {stats_path}: {exc}")
        return 0

    dead = find_dead_landing_paths(stats)
    total = total_landing_sessions(stats)
    lost = sum(sessions for _, sessions, _ in dead)

    if not dead:
        print(
            f"Dead-URL audit: clean — every measured landing path exists "
            f"({total} landing sessions over {stats.get('days', '?')} days)."
        )
        return 0

    share = (lost / total * 100) if total else 0.0
    print(
        f"::warning title=Dead-URL audit::{len(dead)} measured landing "
        f"path(s) have no file: {lost} of {total} landing sessions "
        f"({share:.0f}%) hit a 404. Add a stub to site/redirects.yaml or "
        f"restore the page."
    )
    for path, sessions, bounce in dead:
        print(f"  {sessions:>4} sessions  bounce {bounce:.2f}  /{path}")

    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
