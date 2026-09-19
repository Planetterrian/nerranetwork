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
* ``fleet`` — one record per Route du Rhum IMOCA entry from the class
  register (architect, yard, launch date, foils, dated highlights), for
  the "Know the fleet" panel; a failed page keeps the previous record.
* ``press`` — recent press coverage OF the campaign (a Google News query
  resolved to publisher URLs), for the "In the press" rail.
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

#: Press coverage OF the campaign (Sep 19 2026): the same Google News
#: query the show reads, resolved to publisher URLs at fetch time so the
#: page never links a news.google.com redirect. Headlines only — the
#: dashboard's "In the press" rail is a reading list, not a source of fact.
_PRESS_QUERY_URL = (
    "https://news.google.com/rss/search?q=%22Canada+Ocean+Racing%22+OR+%22Scott+Shawyer%22"
    "+OR+%22Emira+IV%22&hl=en-US&gl=US&ceid=US:en"
)
MAX_PRESS = 10

#: The IMOCA class register (Sep 19 2026): each Route du Rhum entry's boat
#: page on imoca.org carries the architect, the yard, the launch date, the
#: foil flag and a dated "Sailing Highlights" list — the fleet guide the
#: dashboard renders. Slugs live on the curated entries (``imoca_slug``).
_IMOCA_BOAT_URL = "https://www.imoca.org/en/boats/{slug}"
MAX_HIGHLIGHTS = 5

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


_LABEL_RE = re.compile(
    r'<span class="ProfileCard-label">([^<]+)</span></th><td>(.*?)</td>', re.S
)
_SPEC_RE = re.compile(r"<tr><th>([^<]+)</th><td>(.*?)</td></tr>", re.S)
_SAIL_NO_RE = re.compile(r"<h2[^>]*>\s*([A-Z]{2,3}\s?\d{1,4})\s*</h2>")
_HIGHLIGHT_RE = re.compile(r"<strong>\s*(\d{4})\s*:\s*</strong>\s*(.*?)(?:<br\s*/?>|</p>|</div>)", re.S)


def parse_imoca_boat_page(html: str) -> Dict[str, Any]:
    """Facts from one imoca.org boat page: the ProfileCard tables (Baptismal
    name / Architect / Construction / Launch date / Skipper), the spec
    table (Foils, Weight, …), the sail number and the dated highlights."""
    out: Dict[str, Any] = {}
    for label, value in _LABEL_RE.findall(html):
        out[label.strip().lower().replace(" ", "_")] = _strip(value)
    for label, value in _SPEC_RE.findall(html):
        key = label.strip().lower().replace(" ", "_").replace(".", "")
        if key in ("foils", "weight", "mast_type", "length", "draught", "beam") and _strip(value):
            out[key] = _strip(value)
    m = _SAIL_NO_RE.search(html)
    if m:
        out["sail_number"] = m.group(1).replace("  ", " ")
    highlights = []
    tail = html.split("Sailing Highlights", 1)[1] if "Sailing Highlights" in html else ""
    for year, text in _HIGHLIGHT_RE.findall(tail):
        text = _strip(text)
        if text:
            highlights.append(f"{year}: {text}")
        if len(highlights) >= MAX_HIGHLIGHTS:
            break
    if highlights:
        out["highlights"] = highlights
    return out


def _rdr_entries() -> List[Dict[str, Any]]:
    try:
        data = json.loads((_ROOT / "site" / "data" / "offshore_north_dashboard.json").read_text(encoding="utf-8"))
        return [e for e in (data.get("rdr_imoca_entries") or {}).get("entries") or [] if e.get("imoca_slug")]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read the Rhum entries from the curated record: %s", exc)
        return []


def collect_fleet(previous: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """One record per Route du Rhum IMOCA entry, from the class register.
    A page that fails keeps the previous run's record for that boat."""
    import requests

    prev = {f.get("slug"): f for f in ((previous or {}).get("fleet") or []) if isinstance(f, dict)}
    fleet: List[Dict[str, Any]] = []
    for entry in _rdr_entries():
        slug = entry["imoca_slug"]
        url = _IMOCA_BOAT_URL.format(slug=slug)
        record = {"skipper": entry.get("skipper", ""), "entry": entry.get("boat", ""), "slug": slug,
                  "url": url, "canada": bool(entry.get("canada"))}
        try:
            resp = requests.get(url, headers=_UA, timeout=_TIMEOUT)
            resp.raise_for_status()
            facts = parse_imoca_boat_page(resp.text)
            if not facts.get("architect") and not facts.get("launch_date"):
                raise ValueError("page carried no ProfileCard facts")
            if "skipper" in facts:
                facts["register_skipper"] = facts.pop("skipper")
            record.update(facts)
            record["fetched"] = _dt.date.today().isoformat()
        except Exception as exc:  # noqa: BLE001
            logger.warning("IMOCA boat page failed (%s): %s", slug, exc)
            if slug in prev:
                record = {**prev[slug], "stale": True}
        fleet.append(record)
    return fleet


def collect_press() -> List[Dict[str, Any]]:
    """Recent press about the campaign, newest first, publisher URLs."""
    try:
        parsed = _parse_feed(_PRESS_QUERY_URL)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Press query failed: %s", exc)
        return []
    try:
        from engine.url_utils import resolve_google_news_url
    except Exception:  # noqa: BLE001
        resolve_google_news_url = None  # type: ignore[assignment]
    items: List[Dict[str, Any]] = []
    seen = set()
    for entry in (parsed.entries or [])[:30]:
        link = (entry.get("link") or "").strip()
        title = _strip(entry.get("title") or "")
        if not link or not title:
            continue
        # Google News titles end " - Outlet"; keep the outlet, trim the title.
        outlet = ""
        src = entry.get("source")
        if isinstance(src, dict):
            outlet = _strip(src.get("title") or "")
        if " - " in title:
            head, _, tail = title.rpartition(" - ")
            if tail and len(tail) < 60:
                title, outlet = head.strip(), outlet or tail.strip()
        # The campaign's own site is the "Latest from the campaign" rail.
        if resolve_google_news_url is not None:
            try:
                link = resolve_google_news_url(link) or link
            except Exception:  # noqa: BLE001
                pass
        if "canadaoceanracing.com" in link or link in seen:
            continue
        seen.add(link)
        items.append({"outlet": outlet, "title": title, "url": link, "date": _entry_date(entry)})
    items.sort(key=lambda p: p.get("date") or "", reverse=True)
    return items[:MAX_PRESS]


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


def build(*, now: Optional[_dt.datetime] = None, previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    now = now or _dt.datetime.now(_dt.timezone.utc)
    posts = collect_campaign_posts(_campaign_feeds())
    headlines = collect_headlines()
    press = collect_press()
    fleet = collect_fleet(previous)
    position = derive_position(posts)
    public_posts = [{k: v for k, v in p.items() if not k.startswith("_")} for p in posts[:12]]
    return {
        "fetched_at": now.replace(microsecond=0).isoformat(),
        "campaign_posts": public_posts,
        "position": position,
        "headlines": headlines,
        "press": press,
        "fleet": fleet,
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

    previous = _load_previous(out)
    data = build(previous=previous)
    if not data["campaign_posts"] and not data["headlines"]:
        logger.warning("Nothing fetched — keeping the previous-good cache at %s", out)
        return 0 if previous else 1
    if previous and not data["campaign_posts"]:
        # Campaign feeds dark, press fine: keep yesterday's campaign block.
        data["campaign_posts"] = previous.get("campaign_posts", [])
        data["position"] = previous.get("position")
        data["campaign_posts_stale"] = True
    if previous and not data.get("press"):
        data["press"] = previous.get("press", [])
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
