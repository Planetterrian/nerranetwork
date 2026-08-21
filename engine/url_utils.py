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

import json
import logging
import re
import unicodedata
from typing import Optional
from urllib.parse import quote, urlparse

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


# Google News stopped embedding the publisher URL in the article id.
# The modern ``CBMi…`` id base64-decodes to a protobuf whose payload is an
# opaque ``AU_yqL…`` token, and the article page is a JS interstitial — so
# neither decoding nor redirect-following reaches the publisher. The only
# route is the same internal RPC the page's own JavaScript calls: post the
# article id plus the page's signature/timestamp pair to
# ``DotsSplashUi/data/batchexecute`` with rpc id ``Fbv4je``.
_GN_BATCHEXECUTE = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
_GN_RPC_ID = "Fbv4je"
_GN_SIGNATURE_RE = re.compile(r'data-n-a-sg="([^"]+)"')
_GN_TIMESTAMP_RE = re.compile(r'data-n-a-ts="([^"]+)"')

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

# Resolution costs two network round-trips, and the same URL is seen by the
# fetcher, the digest post-pass and the show-notes builder within one run.
# Process-local memo — deliberately not persisted: Google rotates the
# signature, so a stale cache would be worse than no cache.
_GN_RESOLVE_CACHE: dict[str, str] = {}


def _gn_article_id(url: str) -> str:
    """Return the opaque article id (last path segment) of a GN URL."""
    try:
        path = urlparse(url).path or ""
    except Exception:  # noqa: BLE001
        return ""
    return path.rstrip("/").rsplit("/", 1)[-1]


def _gn_resolve_via_batchexecute(
    url: str,
    *,
    timeout: float,
    session: Optional["requests.Session"] = None,
) -> Optional[str]:
    """Ask Google News' own RPC for the publisher URL behind *url*.

    Returns the publisher URL, or ``None`` when any step fails (no page,
    no signature pair, RPC error, unparseable response, or a result that
    is somehow still a Google News URL).
    """
    article_id = _gn_article_id(url)
    if not article_id:
        return None

    get = (session or requests).get
    post = (session or requests).post
    headers = {"User-Agent": _BROWSER_UA}

    try:
        page = get(url, headers=headers, allow_redirects=True, timeout=timeout)
        html = page.text or ""
    except (requests.RequestException, requests.Timeout) as exc:
        logger.debug("Google News page fetch failed for %s: %s", url, exc)
        return None

    sig = _GN_SIGNATURE_RE.search(html)
    ts = _GN_TIMESTAMP_RE.search(html)
    if not sig or not ts:
        # Google changed the page shape — do not guess, just give up.
        logger.debug("Google News signature pair not found for %s", url)
        return None

    try:
        timestamp = int(ts.group(1))
    except (TypeError, ValueError):
        return None

    # Payload shape mirrors what the page's JS sends. The "X" placeholders
    # are literal in Google's own request; only the id/timestamp/signature
    # triple is meaningful.
    inner = [
        "garturlreq",
        [
            ["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1,
             None, None, None, None, None, 0, 1],
            "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0,
        ],
        article_id,
        timestamp,
        sig.group(1),
    ]
    payload = "f.req=" + quote(
        json.dumps([[[_GN_RPC_ID, json.dumps(inner), None, "generic"]]])
    )

    try:
        resp = post(
            _GN_BATCHEXECUTE,
            headers={
                "User-Agent": _BROWSER_UA,
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            },
            data=payload,
            timeout=timeout,
        )
        body = resp.text or ""
    except (requests.RequestException, requests.Timeout) as exc:
        logger.debug("Google News batchexecute failed for %s: %s", url, exc)
        return None

    # Response is Google's anti-JSON-hijacking envelope: a `)]}'` prelude,
    # then length-prefixed JSON chunks. The payload we want is a nested
    # JSON string `["garturlres","<url>",1]`.
    match = re.search(r'\\"garturlres\\",\\"(https?://[^\\"]+)', body)
    if not match:
        match = re.search(r'"garturlres","(https?://[^"]+)"', body)
    if not match:
        logger.debug("Google News RPC returned no publisher URL for %s", url)
        return None

    resolved = match.group(1).encode().decode("unicode_escape")
    resolved = sanitize_url(resolved)
    if not resolved or is_google_news_url(resolved):
        return None
    return resolved


def resolve_google_news_url(
    url: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    session: Optional["requests.Session"] = None,
) -> str:
    """Follow a Google News redirect to its canonical publisher URL.

    Returns the canonical URL on success. Returns *url* unchanged when:
      - it isn't a Google News URL (cheap short-circuit)
      - the network request fails / times out
      - Google's RPC does not hand back a publisher URL

    Two strategies, cheapest first: a plain redirect follow (which still
    works for legacy-format ids), then the ``batchexecute`` RPC that the
    Google News page itself uses for the modern opaque ids.
    """
    if not is_google_news_url(url):
        return url

    cached = _GN_RESOLVE_CACHE.get(url)
    if cached is not None:
        return cached

    headers = {"User-Agent": _BROWSER_UA}
    get = (session or requests).get
    head = (session or requests).head
    try:
        resp = head(url, headers=headers, allow_redirects=True, timeout=timeout)
        final = str(resp.url or "").strip()
        if not final or is_google_news_url(final):
            # Some Google News URLs return 405 on HEAD or redirect
            # in-place. Fall back to GET, but cap the response with
            # stream=True so we don't actually download a 5 MB news page.
            with get(
                url, headers=headers,
                allow_redirects=True, timeout=timeout, stream=True,
            ) as get_resp:
                final = str(get_resp.url or "").strip()
        if final and not is_google_news_url(final):
            _GN_RESOLVE_CACHE[url] = final
            return final
    except (requests.RequestException, requests.Timeout) as exc:
        logger.debug(
            "Google News redirect resolve failed for %s: %s",
            url, exc,
        )

    resolved = _gn_resolve_via_batchexecute(url, timeout=timeout, session=session)
    if resolved:
        _GN_RESOLVE_CACHE[url] = resolved
        return resolved

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


def relabel_aggregator_links(text: str, articles) -> tuple[str, int]:
    """Replace "Google News" link labels with the outlet that reported the story.

    Digests cite aggregated stories as ``Source: [Google News](https://
    news.google.com/rss/articles/CBMi...)``. The label names the
    redirector, so the reader never learns who did the reporting, and the
    blog's Sources card renders Google's favicon as if Google were the
    publisher.

    The real outlet is already known: ``fetcher._publisher_from_entry``
    reads it from the feed's per-item ``<source>`` element and stores it
    on the article as ``source_name``. This is the wire that carries it
    into the digest — a deterministic post-pass keyed on the exact URL,
    with no prompt change (so nothing about the generated prose moves)
    and no network call.

    The href is left as-is here: this pass only names the publisher.
    Turning a Google News href INTO the publisher URL is
    ``repair_aggregator_urls`` (deterministic, from the article record)
    and ``resolve_google_news_url`` (at fetch time, via Google's own RPC —
    plain redirect-following does not penetrate the JS interstitial the
    modern opaque ids serve).

    Returns ``(text, relabelled_count)``.
    """
    if not text or not articles:
        return text, 0

    by_url = {}
    for article in articles:
        url = (article.get("url") or "").strip()
        name = (article.get("source_name") or "").strip()
        aggregator = (article.get("aggregator_url") or "").strip()
        if not url or not name:
            continue
        # An item is aggregated either because its URL is still a Google
        # News redirect, or because we resolved one away — and after
        # `repair_aggregator_urls` runs, the second case is the normal
        # one. Keying on the redirect alone silently stopped relabelling
        # exactly the links the repair had just fixed.
        if is_google_news_url(url):
            by_url[url] = name
        elif aggregator:
            by_url[url] = name
            by_url[aggregator] = name

    if not by_url:
        return text, 0

    count = 0

    def _replace(match: re.Match) -> str:
        nonlocal count
        label, url = match.group(1), match.group(2)
        publisher = by_url.get(url.strip())
        # Only rewrite the aggregator placeholder. A label the digest
        # already made specific is left exactly as written.
        if publisher and label.strip().lower() in ("google news", "news.google.com"):
            count += 1
            return f"[{publisher}]({url})"
        return match.group(0)

    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", _replace, text)
    return text, count


# A Google News article id is ~400 opaque base64 characters. Two different
# articles diverge within the first few dozen; a retyped one diverges at a
# single position anywhere. So a generous shared prefix identifies the
# article without requiring the stray to be byte-correct.
_GN_ID_PREFIX_MATCH = 48


def repair_aggregator_urls(text: str, articles) -> tuple[str, int]:
    """Replace Google News URLs in *text* with the publisher URLs we resolved.

    The fetcher resolves each aggregated item to its publisher URL before
    the article ever reaches the prompt, but the digest prompt still shows
    the model an article list, and the model writes its own Sources
    section. Offshore North Ep001 shipped two 468-character
    ``news.google.com/rss/articles/CBMi…`` URLs there — and RETYPED them,
    so each differed from the real link by one character and resolved to
    nothing at all.

    This maps every Google News URL in *text* back to a fetched article —
    exact match first, then a shared-id-prefix match that survives the
    model's transcription errors — and substitutes the publisher URL the
    fetcher already resolved. A stray with no match is left alone (the
    reader gets a working, if ugly, Google link rather than a dead one).

    Deterministic, no network calls. Returns ``(text, repaired_count)``.
    """
    if not text or not articles:
        return text, 0

    exact: dict[str, str] = {}
    by_prefix: dict[str, str] = {}
    for article in articles:
        canonical = (article.get("url") or "").strip()
        aggregator = (article.get("aggregator_url") or "").strip()
        if not canonical or not aggregator:
            continue
        if is_google_news_url(canonical) or not is_google_news_url(aggregator):
            continue
        exact[aggregator] = canonical
        article_id = _gn_article_id(aggregator)
        if len(article_id) >= _GN_ID_PREFIX_MATCH:
            by_prefix[article_id[:_GN_ID_PREFIX_MATCH]] = canonical

    if not exact:
        return text, 0

    count = 0

    def _replace(match: re.Match) -> str:
        nonlocal count
        stray = match.group(0)
        # Trailing punctuation is the writer's, not the URL's.
        trailing = ""
        while stray and stray[-1] in ".,);:":
            trailing = stray[-1] + trailing
            stray = stray[:-1]
        canonical = exact.get(stray)
        if not canonical:
            article_id = _gn_article_id(stray)
            canonical = by_prefix.get(article_id[:_GN_ID_PREFIX_MATCH])
        if not canonical:
            return match.group(0)
        count += 1
        return canonical + trailing

    text = re.sub(r"https?://news\.google\.[^\s)\]>\"']+", _replace, text)
    return text, count
