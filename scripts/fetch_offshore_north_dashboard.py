#!/usr/bin/env python3
"""Refresh the live half of the Offshore North dashboard.

Writes ``api/offshore_north_dashboard.json`` — the same-origin file that
``offshore-north-dashboard.html`` reads client-side (the SpaceX / Tesla
dashboard pattern: the page carries no live data of its own, so it is
cheap to regenerate and never rate-limits an upstream per visitor).

What it collects, all best-effort:

* ``campaign_posts`` — the newest items on Canada Ocean Racing's own feeds
  (site, News, Scott's Notes, YouTube) with a clipped excerpt of each
  post's BODY, so the page can show what the team said, not just when.
* ``headlines`` — recent items from the wider offshore press feeds the
  show itself reads (Vendée Globe wall, Sailorz EN, Scuttlebutt, …),
  keyword-filtered to offshore racing.
* ``position`` — the newest dated campaign post that reads like a
  position fix (departure, arrival, transit, "heading to …"), so the
  "last known position" card always carries a date and a source.

Reliability contract (mirrors ``fetch_spacex_launches.py``): a failed or
empty fetch NEVER overwrites a previous-good cache; the page renders an
honest "not refreshed" state if the file is missing or stale.

Usage:
    python scripts/fetch_offshore_north_dashboard.py [--out api/offshore_north_dashboard.json]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger("fetch_offshore_north_dashboard")

_UA = {"User-Agent": "NerraNetwork/1.0 (+https://nerranetwork.com)"}
_TIMEOUT = 25

#: The campaign's own channels — the same URLs shows/offshore_north.yaml
#: flags ``freshness_report`` — read here from the YAML so the dashboard
#: can never drift from the show's source list.
_SHOW_YAML = _ROOT / "shows" / "offshore_north.yaml"

#: Wider-press feeds shown as "latest offshore headlines". Kept short and
#: English-first; the show YAML remains the authority for what the SHOW
#: reads — this is a reader's digest for the page.
_HEADLINE_FEEDS = [
    ("Vendée Globe", "https://www.vendeeglobe.org/en/wall/rss.xml"),
    ("Sailorz (Tip & Shaft)", "https://sailorz.com/en/feed/"),
    ("Scuttlebutt", "https://www.sailingscuttlebutt.com/feed/"),
    ("Sail-World Europe", "https://www.sail-world.com/Europe/rss/"),
    ("Yachting World", "https://www.yachtingworld.com/news/feed"),
]

#: Offshore-racing filter for the headline rail. Whole words, so "ultim"
#: cannot match "ultimate" (the Maxi Yacht Rolex Cup slipped in that way).
_HEADLINE_KEYWORDS_RE = re.compile(
    r"\b(?:imoca|vend[ée]e|route du rhum|ocean race|azimut|class ?40|ultims?|"
    r"ocean fifty|transat\w*|les sables|lorient|saint-malo|canada ocean racing|"
    r"shawyer|golden globe|jacques vabre|caf[ée] l'or|solo sail\w*|"
    r"single-?handed|double-?handed|mini 6\.50|figaro)\b",
    re.IGNORECASE,
)

_POSITION_HINTS = re.compile(
    r"\b(depart|departed|departs|leaving|left|arriv|heading|transit|"
    r"crossing|en route|underway|under way|docked|moored|tow|lock|canal|"
    r"seaway|delivery)\b",
    re.IGNORECASE,
)

MAX_POSTS_PER_FEED = 4
MAX_HEADLINES = 14
EXCERPT_CHARS = 420


def _campaign_feeds() -> List[Dict[str, str]]:
    try:
        import yaml

        data = yaml.safe_load(_SHOW_YAML.read_text(encoding="utf-8")) or {}
        out = []
        for src in data.get("sources") or []:
            if isinstance(src, dict) and src.get("freshness_report"):
                out.append({"label": src.get("label", ""), "url": src.get("url", "")})
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read campaign feeds from show YAML: %s", exc)
        return []


def _strip(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    import html as _html

    return re.sub(r"\s+", " ", _html.unescape(text)).strip()


def _body_text(entry) -> str:
    """Full plain text of the entry's body (``content:encoded``), else its
    teaser. The position probe reads this; the page shows ``_excerpt``."""
    body = ""
    try:
        for item in entry.get("content") or []:
            val = item.get("value") if isinstance(item, dict) else getattr(item, "value", "")
            if val and len(val) > len(body):
                body = val
    except Exception:  # noqa: BLE001
        body = ""
    return _strip(body) or _strip(entry.get("description", "") or entry.get("summary", ""))


def _excerpt(entry) -> str:
    text = _body_text(entry)
    if len(text) > EXCERPT_CHARS:
        head = text[:EXCERPT_CHARS]
        cut = head.rfind(". ")
        text = (head[: cut + 1] if cut > EXCERPT_CHARS // 2 else head).rstrip() + " …"
    return text


def _entry_date(entry) -> Optional[str]:
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return _dt.datetime(*val[:6], tzinfo=_dt.timezone.utc).date().isoformat()
            except Exception:  # noqa: BLE001
                continue
    return None


def _parse_feed(url: str):
    import feedparser
    import requests

    resp = requests.get(url, headers=_UA, timeout=_TIMEOUT)
    resp.raise_for_status()
    return feedparser.parse(resp.content)


def collect_campaign_posts(feeds: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    posts: List[Dict[str, Any]] = []
    seen = set()
    # The skipper's own channel first, so a post syndicated to the site
    # feed as well keeps the more specific attribution.
    ordered = sorted(feeds, key=lambda f: 0 if "scott" in (f.get("label") or "").lower() else 1)
    for feed in ordered:
        try:
            parsed = _parse_feed(feed["url"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Campaign feed failed (%s): %s", feed.get("label"), exc)
            continue
        for entry in (parsed.entries or [])[:MAX_POSTS_PER_FEED]:
            link = (entry.get("link") or "").strip()
            title = _strip(entry.get("title") or "")
            if not link or not title or link in seen:
                continue
            seen.add(link)
            body = _body_text(entry)
            posts.append({
                "channel": feed.get("label", ""),
                "title": title,
                "url": link,
                "date": _entry_date(entry),
                "excerpt": _excerpt(entry),
                # Not written to the file — used by derive_position only.
                "_body": body[:4000],
            })
    posts.sort(key=lambda p: p.get("date") or "", reverse=True)
    return posts


def collect_headlines() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    seen = set()
    for label, url in _HEADLINE_FEEDS:
        try:
            parsed = _parse_feed(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Headline feed failed (%s): %s", label, exc)
            continue
        for entry in (parsed.entries or [])[:25]:
            link = (entry.get("link") or "").strip()
            title = _strip(entry.get("title") or "")
            if not link or not title or link in seen:
                continue
            probe = title + " " + _strip(entry.get("summary", ""))[:300]
            if not _HEADLINE_KEYWORDS_RE.search(probe):
                continue
            seen.add(link)
            items.append({
                "outlet": label,
                "title": title,
                "url": link,
                "date": _entry_date(entry),
            })
    items.sort(key=lambda p: p.get("date") or "", reverse=True)
    return items[:MAX_HEADLINES]


def derive_position(posts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The newest campaign post whose title/excerpt reads like a movement
    or position fix — reported WITH its date and URL, never inferred."""
    for post in posts:  # already newest-first
        body = post.get("_body") or post.get("excerpt", "")
        blob = f"{post.get('title', '')} {body}"
        if _POSITION_HINTS.search(blob):
            sentence = ""
            for cand in re.split(r"(?<=[.!?])\s+", body):
                if _POSITION_HINTS.search(cand):
                    sentence = cand.strip()
                    break
            return {
                "date": post.get("date"),
                "text": sentence or post.get("title", ""),
                "title": post.get("title", ""),
                "url": post.get("url", ""),
                "channel": post.get("channel", ""),
            }
    return None


def build(*, now: Optional[_dt.datetime] = None) -> Dict[str, Any]:
    now = now or _dt.datetime.now(_dt.timezone.utc)
    posts = collect_campaign_posts(_campaign_feeds())
    headlines = collect_headlines()
    position = derive_position(posts)
    public_posts = [{k: v for k, v in p.items() if not k.startswith("_")} for p in posts[:12]]
    return {
        "fetched_at": now.replace(microsecond=0).isoformat(),
        "campaign_posts": public_posts,
        "position": position,
        "headlines": headlines,
    }


def _load_previous(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default="api/offshore_north_dashboard.json")
    args = parser.parse_args(argv)
    out = (_ROOT / args.out) if not Path(args.out).is_absolute() else Path(args.out)

    data = build()
    previous = _load_previous(out)
    if not data["campaign_posts"] and not data["headlines"]:
        logger.warning("Nothing fetched — keeping the previous-good cache at %s", out)
        return 0 if previous else 1
    if previous and not data["campaign_posts"]:
        # Campaign feeds dark, press fine: keep yesterday's campaign block.
        data["campaign_posts"] = previous.get("campaign_posts", [])
        data["position"] = previous.get("position")
        data["campaign_posts_stale"] = True
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info(
        "Wrote %s: %d campaign posts, %d headlines, position=%s",
        out, len(data["campaign_posts"]), len(data["headlines"]),
        (data.get("position") or {}).get("date"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
