"""URL sanitization and canonicalization helpers for the fetch pipeline.

Two issues this addresses:

1. **Control-character bleed.** Some RSS scrapes leave bytes like
   ``\\x14`` (DEVICE CONTROL FOUR) inside URLs — the May 2 Omni View
   daily contained ``?ito\\u001490`` literals in href attributes,
   producing dead links. ``sanitize_url`` strips C0/C1 controls before
   the URL is persisted.

2. **Google News redirect bloat.** The fetcher returns
   ``https://news.google.com/rss/articles/CBMi...`` URLs which can be
   200–600 chars long. Stacked across 19 stories × 3-source-list-each
   in Omni View, this pushed the email past Gmail's 102 KB clip
   threshold and the body got truncated mid-sentence.
   ``resolve_google_news_url`` follows the redirect once at fetch time
   and persists the canonical publisher URL (typically <100 chars).

Both helpers are best-effort: a failure returns the input unchanged
rather than raising — the fetch pipeline must never fail because of a
malformed URL.
"""

from __future__ import annotations

import logging
import unicodedata
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

GOOGLE_NEWS_HOSTS = (
    "news.google.com",
    "news.google.co.uk",
    "news.google.ca",
)

# Conservative timeout — the fetcher already runs N parallel resolves
# and we don't want one slow Google News redirect to stall the batch.
_DEFAULT_TIMEOUT = 8


def sanitize_url(url: Optional[str]) -> Optional[str]:
    """Strip C0/C1 control characters; return ``None`` for malformed.

    Returns the cleaned URL on success. Returns ``None`` when:
      - input is empty / None
      - input has no scheme or no netloc after cleaning (caller can
        then drop the source)
      - cleaning produces something with whitespace (a sign the URL
        was concatenated to garbage downstream)

    Idempotent: a clean URL passes through unchanged.
    """
    if not url:
        return None
    cleaned = "".join(
        c for c in url
        if unicodedata.category(c) not in ("Cc", "Cf")
    )
    cleaned = cleaned.strip()
    if not cleaned or any(c.isspace() for c in cleaned):
        return None
    try:
        parsed = urlparse(cleaned)
    except Exception:  # noqa: BLE001 — malformed URLs raise various errors
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    return cleaned


def is_google_news_url(url: str) -> bool:
    """Return True if *url* is a Google News redirect (vs a publisher URL).

    Catches the common patterns: ``/rss/articles/`` and ``/articles/``
    paths under any of the Google News hostnames.
    """
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return False
    host = (parsed.netloc or "").lower()
    if not any(host.endswith(g) for g in GOOGLE_NEWS_HOSTS):
        return False
    path = parsed.path or ""
    return "/articles/" in path


def resolve_google_news_url(
    url: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
) -> str:
    """Follow a Google News redirect to its canonical publisher URL.

    Returns the canonical URL on success. Returns *url* unchanged when:
      - it isn't a Google News URL (cheap short-circuit)
      - the network request fails / times out
      - the response chain doesn't move off Google News (some articles
        wrap the publisher URL in a JS-only interstitial; we don't
        execute JS)

    Uses ``HEAD`` first, falls back to ``GET`` if HEAD is rejected
    (some publishers refuse HEAD with a 405).
    """
    if not is_google_news_url(url):
        return url
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
    }
    try:
        resp = requests.head(
            url, headers=headers,
            allow_redirects=True, timeout=timeout,
        )
        final = str(resp.url or "").strip()
        if not final or is_google_news_url(final):
            # Some Google News URLs return 405 on HEAD or redirect
            # in-place. Fall back to GET, but cap the response with
            # stream=True so we don't actually download a 5 MB news page.
            with requests.get(
                url, headers=headers,
                allow_redirects=True, timeout=timeout, stream=True,
            ) as get_resp:
                final = str(get_resp.url or "").strip()
        if final and not is_google_news_url(final):
            return final
    except (requests.RequestException, requests.Timeout) as exc:
        logger.debug(
            "Google News redirect resolve failed for %s: %s",
            url, exc,
        )
    return url


def shorten_for_email(url: str, *, max_len: int = 200) -> str:
    """Strip noisy query parameters when the URL is dead-set on staying long.

    Conservative: only strips known-noise tracking params
    (``utm_source``, ``utm_medium``, ``utm_campaign``, ``utm_term``,
    ``utm_content``, ``ito``, ``ico``, ``ns_mchannel``, ``CMP``,
    ``fbclid``, ``gclid``, ``mc_cid``, ``mc_eid``). Doesn't touch
    article-id parameters or anything we don't recognize. Returns the
    URL unchanged if it's already under *max_len*.
    """
    if not url or len(url) <= max_len:
        return url
    try:
        from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
        parsed = urlparse(url)
        params = parse_qsl(parsed.query, keep_blank_values=False)
        noise = {
            "utm_source", "utm_medium", "utm_campaign", "utm_term",
            "utm_content", "ito", "ico", "ns_mchannel", "cmp",
            "fbclid", "gclid", "mc_cid", "mc_eid", "_branch_match_id",
            "ref", "ref_src",
        }
        kept = [(k, v) for k, v in params if k.lower() not in noise]
        cleaned = urlunparse(parsed._replace(query=urlencode(kept)))
        return cleaned if cleaned else url
    except Exception:  # noqa: BLE001 — never fail on URL ops
        return url
