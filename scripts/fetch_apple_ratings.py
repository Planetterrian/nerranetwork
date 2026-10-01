#!/usr/bin/env python3
"""Fetch Apple Podcasts ratings for every show with an Apple show page.

Every English outro has asked listeners to "rate us on Apple Podcasts"
since the network launched, and nothing ever read the result back: Apple
Reporter is gated behind the Podcasters Program agreement
(docs/analytics.md) and the cookie scrape reports plays, not stars. The
PUBLIC show page, however, carries the rating in two places and needs no
auth at all:

* the ``<script type="application/ld+json">`` block — ``CreativeWorkSeries``
  with an ``aggregateRating`` of ``ratingValue`` + ``reviewCount``
  (Apple's ``reviewCount`` IS the ratings count: on 2026-10-01 The Daily's
  JSON-LD read ``reviewCount: 105794`` beside the page metadata's
  ``totalNumberOfRatings: 105794`` and ``totalNumberOfReviews: 0``);
* the serialised page metadata — ``"ratings":{"ratingAverage":…,
  "totalNumberOfRatings":…,"totalNumberOfReviews":…}`` — which is present
  even when the JSON-LD carries NO ``aggregateRating`` (a show with zero
  ratings has none; Tesla Shorts Time's page read ``totalNumberOfRatings:
  0`` with no JSON-LD block the same day).

Honesty contract (the one ``fetch_op3_stats.py`` and docs/analytics.md
follow): a show whose page returned NO rating block at all reads
``null``, never 0 — "unmeasured" and "zero" are different facts. A page
that says zero ratings is a measured zero and records ``rating_count: 0``
with ``rating_value: null`` (an average of nothing is not 0.0). A fetch
that fails keeps the previous reading tagged ``not_refreshed_this_run``.
Every show keeps a dated ``history`` (one entry per day, newest last,
capped at :data:`HISTORY_MAX`) so the dashboard can compute a 7-day
ratings delta — the only number the on-air ask can be scored against.

Polite by construction: a browser-like User-Agent, a 20 s timeout, and a
pause between shows. Never raises on a bad page.

Usage::

    python scripts/fetch_apple_ratings.py                 # api/apple_ratings.json
    python scripts/fetch_apple_ratings.py --dry-run       # print, write nothing
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
log = logging.getLogger("apple_ratings")

#: Seconds to wait between show pages (politeness — Apple is not an API).
PAUSE_SECONDS = 1.5
#: Per-request timeout.
HTTP_TIMEOUT = 20
#: Dated history entries kept per show (≈ one quarter of nightlies).
HISTORY_MAX = 90
#: Apple serves a reduced page (no JSON-LD) to a bare python-requests UA.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
#: Sentinel note for a page that carried no rating block of either shape.
NO_RATING_BLOCK_NOTE = (
    "page returned no rating block (JSON-LD aggregateRating and the "
    "ratings metadata both absent) — unmeasured, not zero"
)

_LD_JSON_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_META_RATINGS_RE = re.compile(r'"ratings"\s*:\s*(\{[^{}]*\})')


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> Optional[int]:
    n = _num(value)
    return int(n) if n is not None else None


def parse_apple_ratings(html: str) -> Dict[str, Any]:
    """Read the rating block out of a public Apple Podcasts show page.

    Returns ``rating_value`` / ``rating_count`` / ``review_count`` /
    ``source`` with ``None`` for anything the page did not state.
    ``source`` is ``"ld_json"`` when the JSON-LD ``aggregateRating`` was
    read, ``"page_metadata"`` when only the serialised ratings metadata
    was, and ``None`` when neither block existed.
    """
    out: Dict[str, Any] = {
        "rating_value": None, "rating_count": None,
        "review_count": None, "source": None,
    }
    if not html:
        return out

    # Primary: schema.org aggregateRating in the JSON-LD block(s).
    for raw in _LD_JSON_RE.findall(html):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            agg = node.get("aggregateRating")
            if not isinstance(agg, dict):
                continue
            value = _num(agg.get("ratingValue"))
            count = _int(agg.get("ratingCount"))
            if count is None:
                # Apple labels the ratings count ``reviewCount``.
                count = _int(agg.get("reviewCount"))
            if value is None and count is None:
                continue
            out.update({
                "rating_value": value, "rating_count": count,
                "source": "ld_json",
            })
            break
        if out["source"]:
            break

    # Secondary: the page's own serialised ratings metadata. It states
    # zero explicitly (totalNumberOfRatings: 0) where the JSON-LD simply
    # omits the block, and it is the only place the REVIEW count lives.
    m = _META_RATINGS_RE.search(html)
    if m:
        try:
            meta = json.loads(m.group(1))
        except (ValueError, TypeError):
            meta = {}
        if isinstance(meta, dict) and "totalNumberOfRatings" in meta:
            total = _int(meta.get("totalNumberOfRatings"))
            out["review_count"] = _int(meta.get("totalNumberOfReviews"))
            if out["source"] is None:
                out["source"] = "page_metadata"
                out["rating_count"] = total
                avg = _num(meta.get("ratingAverage"))
                # ratingAverage is 0 on an unrated show — a placeholder,
                # not a measured average. Only a rated show has one.
                out["rating_value"] = avg if (total or 0) > 0 and avg else None
            elif out["rating_count"] is None:
                out["rating_count"] = total
    return out


def fetch_page(url: str) -> Optional[str]:
    """GET the public show page. Returns the HTML, or ``None`` on any
    failure (non-200, timeout, transport error) — never raises."""
    import requests

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT,
                                          "Accept-Language": "en-US,en;q=0.9"},
                            timeout=HTTP_TIMEOUT)
    except Exception as exc:  # noqa: BLE001 — one page must not kill the run
        log.warning("apple_ratings: %s request failed: %s", url, exc)
        return None
    if resp.status_code != 200:
        log.warning("apple_ratings: %s returned HTTP %s", url, resp.status_code)
        return None
    return resp.text


def rating_targets() -> List[Dict[str, str]]:
    """Every registry show with an Apple show page, resolved the way the
    site resolves it: the registry's ``apple_podcasts_url`` string when
    set, else the URL derived from the show YAML's ``apple_show_id``
    (``generate_html._apple_links_for``). A show on neither has no page to
    read and is simply absent from the output."""
    from generate_html import NETWORK_SHOWS, _apple_links_for

    targets: List[Dict[str, str]] = []
    for slug, entry in NETWORK_SHOWS.items():
        url = _apple_links_for(slug, (entry or {}).get("apple_podcasts_url"))[
            "apple_podcasts_url"]
        if url:
            targets.append({"slug": slug, "apple_url": url})
    return sorted(targets, key=lambda t: t["slug"])


def _append_history(previous: List[Any], today: str,
                    rating_value: Optional[float],
                    rating_count: Optional[int]) -> List[Dict[str, Any]]:
    """One entry per date (a rerun on the same day replaces that day's
    entry), newest last, capped at :data:`HISTORY_MAX`."""
    history = [h for h in (previous or [])
               if isinstance(h, dict) and h.get("date") and h["date"] != today]
    history.append({"date": today, "rating_value": rating_value,
                    "rating_count": rating_count})
    history.sort(key=lambda h: str(h.get("date")))
    return history[-HISTORY_MAX:]


def build_ratings(targets: List[Dict[str, str]],
                  previous: Optional[Dict[str, Any]],
                  *,
                  fetch: Optional[Callable[[str], Optional[str]]] = None,
                  sleep: Callable[[float], None] = time.sleep,
                  pause: float = PAUSE_SECONDS,
                  now: Optional[_dt.datetime] = None) -> Dict[str, Any]:
    """Fetch every target and merge with the previous file's readings.

    ``fetch`` is resolved at CALL time (never as a default bound at import)
    so a test that patches ``fetch_page`` on the module actually stops the
    request — the first draft bound it as a default and the test suite made
    a live request to podcasts.apple.com.
    """
    fetch = fetch or fetch_page
    now = now or _dt.datetime.now(_dt.timezone.utc)
    today = now.date().isoformat()
    fetched_at = now.isoformat()
    prev_shows = (previous or {}).get("shows") or {}

    shows: Dict[str, Any] = {}
    for i, target in enumerate(targets):
        slug, url = target["slug"], target["apple_url"]
        if i and pause:
            sleep(pause)
        html = fetch(url)
        prev = prev_shows.get(slug) or {}
        if html is None:
            if prev:
                shows[slug] = {**prev, "apple_url": url,
                               "not_refreshed_this_run": True}
                log.warning("apple_ratings: %s fetch failed — keeping the "
                            "previous reading (not_refreshed_this_run)", slug)
            else:
                shows[slug] = {
                    "apple_url": url, "rating_value": None,
                    "rating_count": None, "review_count": None,
                    "source": None, "fetched_at": None, "history": [],
                    "not_refreshed_this_run": True,
                    "note": "fetch failed and no previous reading exists",
                }
            continue
        parsed = parse_apple_ratings(html)
        entry: Dict[str, Any] = {
            "apple_url": url,
            "rating_value": parsed["rating_value"],
            "rating_count": parsed["rating_count"],
            "review_count": parsed["review_count"],
            "source": parsed["source"],
            "fetched_at": fetched_at,
            "history": _append_history(prev.get("history") or [], today,
                                       parsed["rating_value"],
                                       parsed["rating_count"]),
        }
        if parsed["source"] is None:
            entry["note"] = NO_RATING_BLOCK_NOTE
            log.warning("apple_ratings: %s — %s", slug, NO_RATING_BLOCK_NOTE)
        shows[slug] = entry
        log.info("apple_ratings: %s rating=%s count=%s (%s)", slug,
                 entry["rating_value"], entry["rating_count"], entry["source"])

    return {"fetched_at": fetched_at, "shows": shows}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default="api/apple_ratings.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="print JSON to stdout, write nothing")
    parser.add_argument("--pause", type=float, default=PAUSE_SECONDS,
                        help="seconds between show pages")
    args = parser.parse_args(argv)

    out_path = Path(args.out)
    previous: Dict[str, Any] = {}
    if out_path.exists():
        try:
            previous = json.loads(out_path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001 — a corrupt file is "no previous"
            previous = {}

    targets = rating_targets()
    if not targets:
        log.info("apple_ratings: no show carries an Apple URL — nothing to fetch")
        return 0
    stats = build_ratings(targets, previous, pause=args.pause)

    if args.dry_run:
        print(json.dumps(stats, indent=2)[:4000])
        return 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    refreshed = sum(1 for s in stats["shows"].values()
                    if not s.get("not_refreshed_this_run"))
    log.info("apple_ratings: wrote %s (%d shows, %d refreshed)",
             out_path, len(stats["shows"]), refreshed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
