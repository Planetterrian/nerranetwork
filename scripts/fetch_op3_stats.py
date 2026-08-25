#!/usr/bin/env python3
"""Fetch OP3 (op3.dev) download statistics for every show.

The network has wrapped every RSS enclosure URL with the OP3 analytics
prefix since launch (``engine/publisher.py:apply_op3_prefix``) but never
read the resulting data back. This script closes that loop:

* ``api/op3_stats.json`` — full per-show + per-episode download counts
  for the operator dashboard (``scripts/generate_dashboard.py`` reads it).
* ``site/data/popular_episodes.json`` — public, display-fields-only feed
  of the network's most-downloaded recent episodes, rendered as the
  "Most played" rail on the homepage. (``/api/`` is robots-disallowed,
  ``site/data/`` is the public spot, next to ``search-index.json``.)

Clean no-op when ``OP3_API_TOKEN`` is unset: logs one line, exits 0, and
leaves any previously committed output untouched — same convention as
every other optional integration in this repo.

OP3 API (https://op3.dev/api/docs): base ``https://op3.dev/api/1``,
``Authorization: Bearer <token>``. Shows are resolved from the feed URL
via ``GET /shows/<urlsafe-base64-of-feed-url>``; counts come from
``/queries/show-download-counts`` and ``/queries/episode-download-counts``
(``format=json-o``). OP3 only has data from the date the prefix went
live; there is no backfill for earlier listens.

Usage::

    python scripts/fetch_op3_stats.py                  # write both files
    python scripts/fetch_op3_stats.py --dry-run        # print, write nothing
    python scripts/fetch_op3_stats.py --out /tmp/o.json --popular-out /tmp/p.json
"""

from __future__ import annotations

import argparse
import base64
import datetime as _dt
import json
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make `engine` / `generate_html` importable when run from anywhere.
_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests  # noqa: E402  (after sys.path fix)
from tenacity import (  # noqa: E402  (after sys.path fix)
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
log = logging.getLogger("op3_stats")

OP3_API_BASE = "https://op3.dev/api/1"
SITE_BASE_URL = "https://nerranetwork.com"
HTTP_TIMEOUT = 15
# Public popular-episodes feed size (homepage rail shows fewer).
POPULAR_LIMIT = 12
# Only display fields may reach the public file — never tokens/uuids.
_PUBLIC_EPISODE_FIELDS = (
    "title", "show_slug", "show_name", "brand_color", "show_page",
    "audio_url", "downloads_7d", "rank", "blog_url",
)

_NON_SHOW_YAMLS = {
    "_defaults", "_blocked_sources", "pronunciation_map",
    "network_meta", "scaffold_pending", "translation_overrides",
}


def _list_show_yaml_paths(shows_dir: Path) -> List[Path]:
    return sorted(
        p for p in shows_dir.glob("*.yaml")
        if p.stem not in _NON_SHOW_YAMLS
        and not p.stem.endswith("_template")
        and not p.stem.startswith("_")
    )


def _virtual_show_targets(root: Path, covered: set) -> List[Dict[str, str]]:
    """Registry-only virtual shows (``shows/network_meta.yaml`` entries with
    no ``shows/<slug>.yaml`` — Nerra Daily is the first) whose feeds carry
    the OP3 prefix like any other. Without this the combined edition's
    audience was measured NOWHERE: absent from this file, a show with no
    listeners looks exactly like one that was never fetched — the same
    hole the July 2026 language-feed fix closed for multilingual."""
    import yaml

    meta_path = root / "shows" / "network_meta.yaml"
    try:
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 — registry damage must not kill the run
        log.warning("op3: cannot parse network_meta.yaml: %s", exc)
        return []
    targets: List[Dict[str, str]] = []
    for slug, entry in meta.items():
        if not isinstance(entry, dict) or slug in covered:
            continue
        rss_file = str(entry.get("rss_file") or "").strip()
        if not rss_file or not (root / rss_file).is_file():
            continue
        targets.append({"slug": slug, "rss_file": rss_file})
    return sorted(targets, key=lambda t: t["slug"])


def _blog_url_for_title(slug: str, title: str) -> str:
    """Relative blog URL when the episode HTML exists (underscored dirs)."""
    import re

    m = re.search(r"(?i)\bep(?:isode)?\s*(\d+)\b", title or "")
    if not m:
        return ""
    ep = int(m.group(1))
    rel = f"blog/{slug}/ep{ep:03d}.html"
    return rel if (_ROOT / rel).exists() else ""


class _RateLimited(requests.exceptions.RequestException):
    """HTTP 429 from OP3 — retried with backoff like a transient error."""


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=5, max=40),
    retry=retry_if_exception_type((
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        _RateLimited,
    )),
    reraise=True,
)
def _get(url: str, token: str, params: Optional[Dict[str, str]] = None) -> Any:
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=HTTP_TIMEOUT,
    )
    if resp.status_code == 429:
        raise _RateLimited(f"429 Too Many Requests: {url}")
    resp.raise_for_status()
    return resp.json()


def _feed_url_for(rss_file: str) -> str:
    return f"{SITE_BASE_URL}/{rss_file}"


def _show_uuid_for_feed(feed_url: str, token: str) -> Optional[str]:
    """Resolve the OP3 showUuid from the feed URL (urlsafe base64)."""
    encoded = base64.urlsafe_b64encode(feed_url.encode("utf-8")).decode("ascii")
    data = _get(f"{OP3_API_BASE}/shows/{encoded}", token)
    uuid = (data or {}).get("showUuid")
    return uuid or None


def _fetch_show_stats(slug: str, feed_url: str, token: str,
                      cached_uuid: Optional[str]) -> Optional[Dict[str, Any]]:
    """Fetch per-show + per-episode download counts. Best-effort per show."""
    try:
        uuid = cached_uuid or _show_uuid_for_feed(feed_url, token)
        if not uuid:
            log.warning("op3: no showUuid for %s (%s) — prefix may be too new",
                        slug, feed_url)
            return None

        show_counts = _get(
            f"{OP3_API_BASE}/queries/show-download-counts",
            token, {"showUuid": uuid, "format": "json-o"},
        )
        episode_counts = _get(
            f"{OP3_API_BASE}/queries/episode-download-counts",
            token, {"showUuid": uuid, "format": "json-o"},
        )

        # show-download-counts → {"asof": "YYYY-MM-DD",
        #   "showDownloadCounts": {uuid: {"monthlyDownloads": N,
        #   "weeklyDownloads": [w-3, w-2, w-1, w0], "weeklyAvgDownloads": N,
        #   "numWeeks": N, "days": "0101…"}}} (verified live 2026-06).
        per_show = ((show_counts or {}).get("showDownloadCounts") or {}).get(uuid) or {}
        weekly = per_show.get("weeklyDownloads") or []
        # episode-download-counts → {"showUuid":…, "episodes": [{"itemGuid",
        #   "title", "pubdate", "downloads1", "downloads3", "downloads7",
        #   "downloads30", "downloadsAll"}]}; window keys are OMITTED when
        # OP3's data span doesn't cover them yet (verified live 2026-06).
        raw_eps = (episode_counts or {}).get("episodes") or []

        episodes = []
        for ep in raw_eps:
            downloads_all = ep.get("downloadsAll") or 0
            episodes.append({
                "title": ep.get("title") or "",
                "item_guid": ep.get("itemGuid") or "",
                "pubdate": ep.get("pubdate") or "",
                "downloads_3d": ep.get("downloads3") or 0,
                # Fall back through wider windows so young feeds (data span
                # < 7 days) still rank sensibly on the popular rail.
                "downloads_7d": ep.get("downloads7") or ep.get("downloads3")
                or ep.get("downloads1") or 0,
                "downloads_30d": ep.get("downloads30") or downloads_all,
                "downloads_all_time": downloads_all,
            })
        episodes.sort(key=lambda e: e["downloads_7d"], reverse=True)

        return {
            "show_uuid": uuid,
            "feed_url": feed_url,
            "asof": (show_counts or {}).get("asof") or "",
            "downloads_7d": (weekly[-1] if weekly else 0),
            "downloads_30d": per_show.get("monthlyDownloads") or 0,
            "weekly_avg": per_show.get("weeklyAvgDownloads") or 0,
            "weekly_downloads": weekly,
            "episodes": episodes,
        }
    except Exception as exc:  # noqa: BLE001 — one show must not kill the run
        log.warning("op3: %s fetch failed: %s", slug, exc)
        return None


def _language_feed_targets(root: Path) -> List[Dict[str, str]]:
    """Every per-language feed the network actually pays to produce.

    The multilingual stage is roughly a third of network spend (~$38/mo)
    and its audience was measured NOWHERE: the per-language enclosures
    carry the OP3 prefix like any other, but this fetcher only ever
    resolved the English feed, so ``api/op3_stats.json`` had zero
    language-track entries. Whether a language earns its cost was
    therefore unanswerable — which is the only reason the ZH/FR tracks
    on channel-less shows kept renewing.

    Scoped to the languages each show actually generates
    (``multilingual.languages`` with ``enabled``), so the request count
    tracks real spend rather than the 44 feed files on disk (most of
    which are stubs from a one-off backfill).
    """
    import yaml

    targets: List[Dict[str, str]] = []
    for yaml_path in _list_show_yaml_paths(root / "shows"):
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001 — one bad YAML must not kill the run
            continue
        ml = data.get("multilingual") or {}
        if not ml.get("enabled"):
            continue
        rss_file = ((data.get("publishing") or {}).get("rss_file") or "").strip()
        if not rss_file:
            continue
        for lang in (ml.get("languages") or []):
            lang = str(lang).strip().lower()
            if not lang:
                continue
            from engine.language_feeds import feed_filename
            fname = feed_filename(rss_file, lang)
            if not (root / fname).is_file():
                continue
            targets.append({
                "key": f"{yaml_path.stem}:{lang}",
                "slug": yaml_path.stem,
                "lang": lang,
                "rss_file": fname,
            })
    return targets


def _episode_audio_urls(rss_path: Path) -> Dict[str, str]:
    """Map episode title AND guid → enclosure URL from a committed feed."""
    mapping: Dict[str, str] = {}
    try:
        root = ET.parse(rss_path).getroot()
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            guid = (item.findtext("guid") or "").strip()
            enclosure = item.find("enclosure")
            url = enclosure.get("url") if enclosure is not None else ""
            if url:
                if title:
                    mapping[title] = url
                if guid:
                    mapping[guid] = url
    except Exception as exc:  # noqa: BLE001
        log.warning("op3: could not parse %s: %s", rss_path, exc)
    return mapping


def build_popular_episodes(stats: Dict[str, Any], root: Path) -> List[Dict[str, Any]]:
    """Derive the public top-N list. Display fields only — no uuids/tokens."""
    from generate_html import NETWORK_SHOWS  # canonical show registry

    candidates: List[Dict[str, Any]] = []
    for slug, show_stats in (stats.get("shows") or {}).items():
        meta = NETWORK_SHOWS.get(slug) or {}
        rss_file = meta.get("rss_file") or ""
        audio_urls = _episode_audio_urls(root / rss_file) if rss_file else {}
        for ep in (show_stats.get("episodes") or []):
            if not ep.get("downloads_7d"):
                continue
            audio = audio_urls.get(ep.get("title", "")) or audio_urls.get(
                ep.get("item_guid", ""))
            candidates.append({
                "title": ep.get("title") or "",
                "show_slug": slug,
                "show_name": meta.get("name") or slug,
                "brand_color": meta.get("brand_color") or "#00D4FF",
                "show_page": meta.get("show_page") or "",
                "audio_url": audio or "",
                "downloads_7d": ep.get("downloads_7d") or 0,
                "blog_url": _blog_url_for_title(slug, ep.get("title") or ""),
            })

    candidates.sort(key=lambda e: e["downloads_7d"], reverse=True)
    top = candidates[:POPULAR_LIMIT]
    for rank, ep in enumerate(top, start=1):
        ep["rank"] = rank
    # Defense-in-depth: strip anything outside the public whitelist.
    return [
        {k: v for k, v in ep.items() if k in _PUBLIC_EPISODE_FIELDS}
        for ep in top
    ]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="api/op3_stats.json")
    parser.add_argument("--popular-out", default="site/data/popular_episodes.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="print JSON to stdout, write nothing")
    args = parser.parse_args(argv)

    token = (os.getenv("OP3_API_TOKEN") or "").strip()
    if not token:
        log.info("op3: OP3_API_TOKEN unset — skipping (clean no-op)")
        return 0

    root = _ROOT
    out_path = Path(args.out)
    popular_path = Path(args.popular_out)

    # Reuse previously resolved showUuids so reruns skip the lookup.
    previous: Dict[str, Any] = {}
    if out_path.exists():
        try:
            previous = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            previous = {}
    prev_shows = previous.get("shows") or {}

    import yaml
    shows: Dict[str, Any] = {}
    for yaml_path in _list_show_yaml_paths(root / "shows"):
        slug = yaml_path.stem
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # noqa: BLE001
            log.warning("op3: cannot parse %s: %s", yaml_path, exc)
            continue
        rss_file = ((data.get("publishing") or {}).get("rss_file") or "").strip()
        if not rss_file:
            continue
        cached_uuid = (prev_shows.get(slug) or {}).get("show_uuid")
        if shows:
            time.sleep(2)  # politeness — OP3 rate-limits bursts (429)
        result = _fetch_show_stats(
            slug, _feed_url_for(rss_file), token, cached_uuid,
        )
        if result is not None:
            shows[slug] = result

    # Registry-only virtual shows (no shows/<slug>.yaml): Nerra Daily etc.
    covered = {p.stem for p in _list_show_yaml_paths(root / "shows")}
    for target in _virtual_show_targets(root, covered):
        slug = target["slug"]
        if shows:
            time.sleep(2)  # politeness — OP3 rate-limits bursts (429)
        result = _fetch_show_stats(
            slug, _feed_url_for(target["rss_file"]), token,
            (prev_shows.get(slug) or {}).get("show_uuid"),
        )
        if result is not None:
            shows[slug] = result

    # Per-language feeds live in their OWN top-level section, never mixed
    # into ``shows``: every consumer (dashboard rollups, popular-episode
    # rail, performance trackers) iterates ``shows`` keyed by slug, and a
    # "tesla:fr" key in there would be read as an unknown show.
    prev_langs = previous.get("language_feeds") or {}
    language_feeds: Dict[str, Any] = {}
    for target in _language_feed_targets(root):
        time.sleep(2)  # politeness — OP3 rate-limits bursts (429)
        result = _fetch_show_stats(
            target["key"], _feed_url_for(target["rss_file"]), token,
            (prev_langs.get(target["key"]) or {}).get("show_uuid"),
        )
        if result is None:
            # Keep the previous reading rather than dropping the language
            # from the file — an absent entry reads as "no audience" and
            # that is exactly the conclusion this data must not fake.
            if target["key"] in prev_langs:
                language_feeds[target["key"]] = {
                    **prev_langs[target["key"]],
                    "not_refreshed_this_run": True,
                }
            else:
                # Aug 15 2026: a language that never resolved ONCE was
                # invisible forever — ZH is translated daily on both
                # flagships (30/30 episodes, OP3-prefixed enclosures) yet
                # had no entry at all, so the July-29 "zero across several
                # weeks = switch-off candidate" rule could never even see
                # it. Emit an explicit unresolved marker instead: paid-for
                # and unmeasured must be distinguishable from unpaid.
                language_feeds[target["key"]] = {
                    "show_slug": target["slug"],
                    "language": target["lang"],
                    "resolved": False,
                    "downloads_7d": None,
                    "downloads_30d": None,
                    "note": "OP3 has not indexed this feed (404) — "
                            "downloads attach retroactively once it does; "
                            "a 404 persisting for weeks means check the "
                            "prefix (docs/analytics.md)",
                }
            continue
        result["show_slug"] = target["slug"]
        result["language"] = target["lang"]
        language_feeds[target["key"]] = result

    stats = {
        "fetched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "shows": shows,
        "language_feeds": language_feeds,
    }
    popular = build_popular_episodes(stats, root)

    if args.dry_run:
        print(json.dumps(stats, indent=2)[:2000])
        print(json.dumps(popular, indent=2)[:2000])
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    log.info("op3: wrote %s (%d shows, %d language feeds)",
             out_path, len(shows), len(language_feeds))

    popular_path.parent.mkdir(parents=True, exist_ok=True)
    popular_path.write_text(json.dumps(popular, indent=2) + "\n", encoding="utf-8")
    log.info("op3: wrote %s (%d episodes)", popular_path, len(popular))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
