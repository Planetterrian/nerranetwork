"""Public Instagram posts as dated, text-only sources (Oct 4 2026).

Offshore racing breaks on Instagram before it reaches any feed: the
campaign posts there far more often than on its site, and the class and
race organisers do the same. This module reads those posts through Meta's
**Business Discovery** API — the supported way for one Instagram
professional account to read another professional account's public posts
— and returns them as caption + permalink + timestamp. Nothing is
scraped from instagram.com (its terms forbid it and the pages sit behind
a login wall).

TEXT AND LINKS ONLY, by design. The module never requests or stores a
media URL: being able to read a post is not a licence to republish its
photograph, and the network's gallery is CC BY-SA, so a third-party image
must never enter it. A post's picture reaches a reader only as Instagram's
own embed on a resource page, rendered by Instagram, credited and linked.

Credentials (repository secrets, read-only use):

* ``INSTAGRAM_GRAPH_TOKEN`` — a long-lived user access token from a Meta
  app with Facebook Login, granted ``instagram_basic`` and
  ``pages_show_list`` (``pages_read_engagement`` where Meta asks for it);
* ``INSTAGRAM_GRAPH_USER_ID`` — the numeric id of the network's own
  Instagram professional account (the one linked to a Facebook Page).

They are deliberately NOT ``IG_ACCESS_TOKEN`` / ``IG_USER_ID``, the names
the Shorts publisher (``engine.social_publisher``) posts with: a read
token added for this must never be able to switch on posting.

Unset credentials are a clean no-op (``[]``), like every other optional
source in this pipeline.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import re
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.facebook.com/v21.0"
TOKEN_ENV = "INSTAGRAM_GRAPH_TOKEN"
USER_ID_ENV = "INSTAGRAM_GRAPH_USER_ID"
_TIMEOUT = 20

#: Fields requested per post. ``media_url`` is deliberately absent — see
#: the module docstring.
MEDIA_FIELDS = "caption,permalink,timestamp,media_type"

DEFAULT_PER_ACCOUNT = 6
TITLE_MAX = 110

_HANDLE_RE = re.compile(r"instagram\.com/([A-Za-z0-9_.]+)/?", re.IGNORECASE)


def credentials() -> Optional[Dict[str, str]]:
    token = os.getenv(TOKEN_ENV, "").strip()
    user_id = os.getenv(USER_ID_ENV, "").strip()
    if not token or not user_id:
        return None
    return {"token": token, "user_id": user_id}


def handle_from_url(url: str) -> str:
    m = _HANDLE_RE.search(url or "")
    return m.group(1) if m else ""


def handles_from_follow(follow: Any) -> List[str]:
    """Instagram handles from the dashboard record's ``follow`` groups
    (entries with ``kind: instagram``), in record order, de-duplicated —
    so the accounts the page lists and the accounts the show reads are one
    list."""
    out: List[str] = []
    groups = follow if isinstance(follow, list) else []
    for g in groups:
        for link in (g.get("links") or []) if isinstance(g, dict) else []:
            if isinstance(link, dict) and link.get("kind") == "instagram":
                h = handle_from_url(str(link.get("url", "")))
                if h and h.lower() not in {x.lower() for x in out}:
                    out.append(h)
    return out


def _parse_ts(value: Any) -> Optional[_dt.datetime]:
    try:
        text = str(value).replace("+0000", "+00:00")
        dt = _dt.datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=_dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def parse_business_discovery(handle: str, payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Graph API response → ``[{account, caption, permalink, timestamp, media_type}]``."""
    bd = (payload or {}).get("business_discovery") or {}
    username = bd.get("username") or handle
    out: List[Dict[str, Any]] = []
    for m in ((bd.get("media") or {}).get("data") or []):
        permalink = str(m.get("permalink") or "").strip()
        ts = _parse_ts(m.get("timestamp"))
        if not permalink or ts is None:
            continue
        out.append({
            "account": username,
            "caption": str(m.get("caption") or "").strip(),
            "permalink": permalink,
            "timestamp": ts.isoformat(),
            "date": ts.date().isoformat(),
            "media_type": str(m.get("media_type") or ""),
        })
    return out


def fetch_account(handle: str, *, creds: Dict[str, str], limit: int = DEFAULT_PER_ACCOUNT,
                  session=None) -> List[Dict[str, Any]]:
    fields = (f"business_discovery.username({handle})"
              f"{{username,media.limit({int(limit)}){{{MEDIA_FIELDS}}}}}")
    try:
        import requests

        http = session or requests
        resp = http.get(f"{GRAPH_BASE}/{creds['user_id']}",
                        params={"fields": fields, "access_token": creds["token"]},
                        timeout=_TIMEOUT)
        if resp.status_code != 200:
            # Never log the response body — it can echo the request URL.
            logger.warning("Instagram @%s: HTTP %s", handle, resp.status_code)
            return []
        return parse_business_discovery(handle, resp.json())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Instagram @%s failed: %s", handle, type(exc).__name__)
        return []


def fetch_recent(handles: Iterable[str], *, since_days: int = 30,
                 limit: int = DEFAULT_PER_ACCOUNT,
                 now: Optional[_dt.datetime] = None, session=None) -> List[Dict[str, Any]]:
    """Recent posts from each handle, newest first. ``[]`` without credentials."""
    creds = credentials()
    if creds is None:
        logger.info("Instagram source: %s / %s not set — skipped", TOKEN_ENV, USER_ID_ENV)
        return []
    now = now or _dt.datetime.now(_dt.timezone.utc)
    cutoff = now - _dt.timedelta(days=since_days)
    posts: List[Dict[str, Any]] = []
    for handle in handles:
        for post in fetch_account(handle, creds=creds, limit=limit, session=session):
            ts = _parse_ts(post["timestamp"])
            if ts and ts >= cutoff:
                posts.append(post)
    posts.sort(key=lambda p: p["timestamp"], reverse=True)
    return posts


def _title_from_caption(caption: str, account: str) -> str:
    first = re.split(r"(?<=[.!?])\s+|\n", caption.strip(), maxsplit=1)[0].strip()
    first = re.sub(r"(?:\s*#\w+)+\s*$", "", first).strip()
    if not first:
        return f"Instagram post by @{account}"
    if len(first) > TITLE_MAX:
        first = first[:TITLE_MAX].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
    return first


def post_articles(posts: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Posts as hook articles (``engine.hook_articles`` contract): the
    caption is the article text, the permalink is the citation, the post
    time is the date. A post with no caption carries nothing to report and
    is skipped."""
    out: List[Dict[str, Any]] = []
    for p in posts:
        caption = (p.get("caption") or "").strip()
        if not caption:
            continue
        out.append({
            "title": _title_from_caption(caption, p.get("account", "")),
            "url": p["permalink"],
            "description": caption[:400],
            "content_text": caption,
            "source_name": f"Instagram @{p.get('account', '')}",
            "published_date": p.get("timestamp", ""),
        })
    return out
