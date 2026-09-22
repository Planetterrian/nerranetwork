"""Full article text for the digest prompt (Sep 14 2026, Offshore North review).

The fetch layer hands the model a headline, the feed's ``description`` and a
URL — never the article. On a show whose whole premise is reading what a
campaign actually said, that is fatal: Offshore North Ep004 (2026-09-07)
knew that Canada Ocean Racing's site was "last updated 2 September with a
summary of summer training" and nothing else, so it told listeners the
boat's position was "unconfirmed" while the post it never opened said the
boat "is now leaving Canada and heading back to Europe". Ep005 then read a
team-malizia.com headline about the START of The Ocean Race Atlantic
("first across the line as the race begins"), re-surfaced by Google News
ten days later, and aired it as the result of a race that had already
finished — with a different winner.

Two layers, both opt-in per show (``fetch_full_text: N`` in the show YAML —
the number of articles to open; every other show is byte-identical):

1. **Feed bodies.** WordPress-class feeds carry the whole post in
   ``content:encoded``; ``engine.fetcher`` now stores it on the article as
   ``content_text`` (plain text). No HTTP, no risk.
2. **Page fetch.** For articles without a feed body, fetch the page and
   extract the main prose — ``<article>`` / ``<main>`` paragraphs, boilerplate
   stripped. Best-effort by contract: any failure leaves the article as it
   was and the run continues.

Either way the text lands on ``article["full_text"]`` (capped at
``max_chars``), and run_show renders it under the headline in the digest
prompt's article list. The digest prompt then has something to read.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: Per-article cap on the text handed to the prompt. ~2,500 characters is
#: 400-450 words — the substance of a campaign blog post or a race report,
#: without letting one long feature swallow the whole article budget.
DEFAULT_MAX_CHARS = 2500

#: Below this many characters a feed ``description`` is a teaser, not a
#: body, and the page is worth opening.
_DESCRIPTION_IS_A_BODY_CHARS = 1200

_BOILERPLATE_TAGS = (
    "script", "style", "noscript", "nav", "header", "footer", "aside",
    "form", "iframe", "svg", "button", "figure", "figcaption",
)

#: Class/id fragments that mark chrome, not prose (cookie banners, share
#: rows, related-post rails, comment threads).
_BOILERPLATE_HINTS = re.compile(
    r"(cookie|share|social|related|comment|sidebar|newsletter|subscribe|"
    r"breadcrumb|menu|nav-|-nav|footer|promo|advert)",
    re.IGNORECASE,
)

_WS_RE = re.compile(r"\s+")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)


def _clean(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def _tag_strip_fallback(html: str) -> str:
    """No-bs4 fallback: drop script/style BLOCKS (a JSON-LD blob is not
    prose), then strip tags."""
    import html as _html

    body = _SCRIPT_STYLE_RE.sub(" ", html or "")
    return _clean(_html.unescape(re.sub(r"<[^>]+>", " ", body)))


def extract_article_text(html: str) -> str:
    """Return the main prose of an HTML page as plain text.

    Preference order: the first ``<article>``, then ``<main>``, then the
    body. Within the chosen container, paragraph-level elements are joined
    with blank lines; boilerplate tags and chrome-flavoured containers are
    dropped first. Falls back to the container's flattened text when it
    holds no paragraphs. Never raises — an unparsable page yields ``""``.
    """
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup  # beautifulsoup4 is in requirements
    except Exception:  # noqa: BLE001 — bs4 missing: degrade to a tag strip
        return _tag_strip_fallback(html)
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:  # noqa: BLE001
        return _tag_strip_fallback(html)

    for tag in soup.find_all(_BOILERPLATE_TAGS):
        tag.decompose()

    container = soup.find("article") or soup.find("main") or soup.body or soup
    # Chrome-flavoured blocks are dropped only when they are SMALL relative
    # to the container: page builders (Elementor, Divi) wrap the whole post
    # in "widget" / "header"-named divs, and the first cut of this function
    # decomposed the article itself down to "Skip to content".
    total = len(_clean(container.get_text(" "))) or 1
    for tag in list(container.find_all(["div", "section", "ul", "ol", "aside"])):
        attrs = getattr(tag, "attrs", None)
        if not attrs:  # already decomposed inside a removed ancestor
            continue
        marker = " ".join([str(attrs.get("id") or "")] + list(attrs.get("class") or []))
        if marker and _BOILERPLATE_HINTS.search(marker):
            if len(_clean(tag.get_text(" "))) < 0.3 * total:
                tag.decompose()

    paragraphs: List[str] = []
    for node in container.find_all(["p", "h2", "h3", "li", "blockquote"]):
        text = _clean(node.get_text(" "))
        # Skip nav crumbs and captions — a real sentence has some length.
        if len(text) < 40 and not text.endswith((".", "!", "?")):
            continue
        paragraphs.append(text)
    if paragraphs:
        return "\n\n".join(paragraphs)
    return _clean(container.get_text(" "))


def default_fetch(url: str, timeout: int = 20) -> Tuple[int, str]:
    """Fetch *url* and return ``(status, html)``; non-HTML bodies are ``""``."""
    import requests

    resp = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; NerraNetwork/1.0; "
                "+https://nerranetwork.com)"
            ),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
        },
        allow_redirects=True,
    )
    ctype = (resp.headers.get("content-type") or "").lower()
    if "html" in ctype or "xml" in ctype or ctype.startswith("text/"):
        return resp.status_code, resp.text
    return resp.status_code, ""


#: Where a page states its own publish date, in the order they are
#: trusted. The OpenGraph/article meta is what publishers set for social
#: cards; JSON-LD ``datePublished`` is what Google reads; ``<time
#: datetime>`` is the visible byline. A page with none yields ``None``.
_META_DATE_RE = re.compile(
    r'<meta\s+(?:property|name)=["\'](?:article:published_time|og:published_time|'
    r'datePublished|pubdate|publish-date|date)["\']\s+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_META_DATE_RE_REV = re.compile(
    r'<meta\s+content=["\']([^"\']+)["\']\s+(?:property|name)=["\'](?:article:published_time|'
    r'og:published_time|datePublished|pubdate|publish-date|date)["\']',
    re.IGNORECASE,
)
_JSONLD_DATE_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
_TIME_TAG_RE = re.compile(r'<time[^>]+datetime=["\']([^"\']+)["\']', re.IGNORECASE)


def _parse_iso_date(value: str):
    """Best-effort ISO-8601 → aware UTC datetime, else ``None``."""
    import datetime as _dt

    raw = (value or "").strip()
    if not raw:
        return None
    raw = raw.replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        raw += "T00:00:00+00:00"
    try:
        parsed = _dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed.astimezone(_dt.timezone.utc)


def extract_published_date(html: str):
    """The page's own publish date as an aware UTC datetime, or ``None``.

    Read during the full-text fetch so a story an aggregator re-surfaced
    under a fresh index date carries its REAL date (Sep 18 2026 review,
    fix 8: Ep005 reported the 1 September race start on 14 September)."""
    if not html:
        return None
    head = html[:200_000]
    for pattern in (_META_DATE_RE, _META_DATE_RE_REV, _JSONLD_DATE_RE, _TIME_TAG_RE):
        m = pattern.search(head)
        if m:
            parsed = _parse_iso_date(m.group(1))
            if parsed is not None:
                return parsed
    return None


def fetch_article(
    url: str,
    *,
    fetch: Optional[Callable[[str], Tuple[int, str]]] = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> Tuple[str, Optional[object]]:
    """Open *url* → ``(text, published)``: the main text clipped to
    *max_chars* and the page's own publish date (or ``None``).

    ``("", None)`` on any failure (transport error, non-200, empty page)."""
    if not url:
        return "", None
    fetcher = fetch or default_fetch
    try:
        status, html = fetcher(url)
    except Exception as exc:  # noqa: BLE001 — never break a run
        logger.info("Full-text fetch failed for %s: %s", url[:100], exc)
        return "", None
    if status != 200 or not html:
        logger.info("Full-text fetch skipped for %s (status %s)", url[:100], status)
        return "", None
    return clip_text(extract_article_text(html), max_chars), extract_published_date(html)


def fetch_article_text(
    url: str,
    *,
    fetch: Optional[Callable[[str], Tuple[int, str]]] = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> str:
    """Open *url* and return its main text, clipped to *max_chars*.

    ``""`` on any failure (transport error, non-200, empty extraction)."""
    return fetch_article(url, fetch=fetch, max_chars=max_chars)[0]


def clip_text(text: str, max_chars: int) -> str:
    """Clip at a sentence/paragraph boundary near *max_chars*."""
    text = (text or "").strip()
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    head = text[:max_chars]
    cut = max(head.rfind("\n\n"), head.rfind(". "), head.rfind("! "), head.rfind("? "))
    if cut > max_chars * 0.5:
        head = head[: cut + 1]
    return head.rstrip() + " […]"


def _needs_page_fetch(article: Dict) -> bool:
    desc = article.get("description") or ""
    return len(desc) < _DESCRIPTION_IS_A_BODY_CHARS


def enrich_articles_with_full_text(
    articles: List[Dict],
    *,
    max_articles: int,
    max_chars: int = DEFAULT_MAX_CHARS,
    priority_sources: Optional[Iterable[str]] = None,
    fetch: Optional[Callable[[str], Tuple[int, str]]] = None,
    workers: int = 6,
) -> int:
    """Attach ``full_text`` to up to *max_articles* articles, in place.

    Selection order: articles from *priority_sources* (the campaign's own
    channels) first, then the list order run_show already sorted (newest
    first). An article whose feed carried a body (``content_text``) is
    served from that with no HTTP; the rest are fetched in parallel.
    Returns the number of articles that gained text. Never raises.
    """
    if not articles or max_articles <= 0:
        return 0
    prio = {s.strip().lower() for s in (priority_sources or []) if s}

    def _rank(item: Tuple[int, Dict]) -> Tuple[int, int]:
        idx, art = item
        src = (art.get("source_name") or "").strip().lower()
        return (0 if src in prio else 1, idx)

    ordered = sorted(enumerate(articles), key=_rank)
    chosen = [art for _, art in ordered[:max_articles]]

    gained = 0
    to_fetch: List[Dict] = []
    for art in chosen:
        body = (art.get("content_text") or "").strip()
        if body:
            art["full_text"] = clip_text(body, max_chars)
            art["full_text_source"] = "feed"
            gained += 1
        elif _needs_page_fetch(art) and art.get("url"):
            to_fetch.append(art)
        else:
            # The description already is the body (some feeds ship it in
            # <description>); promote it so the prompt renders one block.
            art["full_text"] = clip_text(art.get("description") or "", max_chars)
            art["full_text_source"] = "description"
            gained += 1

    if to_fetch:
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(to_fetch)))) as pool:
            futures = {
                pool.submit(fetch_article, a["url"], fetch=fetch, max_chars=max_chars): a
                for a in to_fetch
            }
            for fut in as_completed(futures):
                art = futures[fut]
                try:
                    text, published = fut.result()
                except Exception as exc:  # noqa: BLE001
                    logger.info("Full-text worker failed: %s", exc)
                    text, published = "", None
                if published is not None:
                    art["page_published_date"] = published.isoformat()
                if text:
                    art["full_text"] = text
                    art["full_text_source"] = "page"
                    gained += 1
    logger.info(
        "Full-text enrichment: %d of %d selected articles carry text "
        "(%d served from feed bodies)",
        gained, len(chosen), sum(1 for a in chosen if a.get("full_text_source") == "feed"),
    )
    return gained


def render_full_text_block(article: Dict, indent: str = "   ") -> str:
    """The prompt-side rendering of an article's full text (``""`` if none)."""
    text = (article.get("full_text") or "").strip()
    if not text:
        return ""
    body = text.replace("\n\n", "\n" + indent)
    return f"{indent}FULL TEXT: {body}"



def article_age_days(article: Dict, now) -> Optional[float]:
    """Age in days of the article's most trustworthy date: the page's own
    publish date when the full-text fetch found one, else the feed date.
    ``None`` when neither parses."""
    for key in ("page_published_date", "published_date"):
        parsed = _parse_iso_date(str(article.get(key) or ""))
        if parsed is not None:
            return (now - parsed).total_seconds() / 86400.0
    return None


def drop_stale_articles(
    articles: List[Dict],
    *,
    max_age_days: int,
    now=None,
    exempt_sources: Optional[Iterable[str]] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """Nothing older than *max_age_days* is news.

    Returns ``(kept, dropped)``. An article is dropped when its page publish
    date — or, failing that, its feed date — is older than the limit.
    Undated articles are kept (the guard exists for re-surfaced old
    stories, never to lose a story the page did not date). Sources named
    in *exempt_sources* (the campaign's own channels, which are read on a
    deliberately wider window) are never dropped. ``max_age_days <= 0``
    is a no-op.
    """
    if max_age_days <= 0 or not articles:
        return list(articles), []
    import datetime as _dt

    now = now or _dt.datetime.now(_dt.timezone.utc)
    exempt = {s.strip().lower() for s in (exempt_sources or []) if s}
    kept: List[Dict] = []
    dropped: List[Dict] = []
    for art in articles:
        src = (art.get("source_name") or "").strip().lower()
        # Hook-supplied articles may opt out (engine.hook_articles): a
        # week's merged PRs are dated in the past by construction.
        if src in exempt or art.get("exempt_stale"):
            kept.append(art)
            continue
        age = article_age_days(art, now)
        if age is not None and age > max_age_days:
            dropped.append(art)
            logger.info(
                "Dropping stale article (%.0f days, page-dated=%s): %s",
                age, bool(art.get("page_published_date")),
                (art.get("title") or "")[:80],
            )
        else:
            kept.append(art)
    return kept, dropped
