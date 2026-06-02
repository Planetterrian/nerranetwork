"""RSS feed fetching for the podcast generation pipeline.

Provides:
  - fetch_rss_articles(): fetch, filter, and deduplicate articles from RSS feeds
"""

import datetime
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Dict, List, Optional

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from engine.utils import (
    DEFAULT_HEADERS,
    HTTP_TIMEOUT_SECONDS,
    remove_similar_items,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTML stripping helper
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace to produce plain text.

    Google News RSS feeds (and some Reddit feeds) return HTML in the
    description field. This cleans it to plain text.
    """
    if not text or "<" not in text:
        return text
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"&amp;", "&", clean)
    clean = re.sub(r"&lt;", "<", clean)
    clean = re.sub(r"&gt;", ">", clean)
    clean = re.sub(r"&nbsp;", " ", clean)
    clean = re.sub(r"&#\d+;", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


# ---------------------------------------------------------------------------
# Source name mapping
# ---------------------------------------------------------------------------

_SOURCE_MAP: List[tuple] = [
    # Google News (must precede generic patterns)
    ("news.google.com", "Google News"),
    # Reddit — specific subreddits first, then generic fallback
    # (must precede generic patterns like "longevity", "science", etc.)
    ("reddit.com/r/teslamotors", "r/teslamotors"),
    ("reddit.com/r/electricvehicles", "r/electricvehicles"),
    ("reddit.com/r/teslainvestorsclub", "r/teslainvestorsclub"),
    ("reddit.com/r/environment", "r/environment"),
    ("reddit.com/r/climate", "r/climate"),
    ("reddit.com/r/britishcolumbia", "r/britishcolumbia"),
    ("reddit.com/r/spacex", "r/spacex"),
    ("reddit.com/r/space", "r/space"),
    ("reddit.com/r/astronomy", "r/astronomy"),
    ("reddit.com/r/longevity", "r/longevity"),
    ("reddit.com/r/science", "r/science"),
    ("reddit.com/r/biotech", "r/biotech"),
    ("reddit.com/r/worldnews", "r/worldnews"),
    ("reddit.com/r/news", "r/news"),
    ("reddit.com/r/geopolitics", "r/geopolitics"),
    ("reddit.com/r/machinelearning", "r/MachineLearning"),
    ("reddit.com/r/localllama", "r/LocalLLaMA"),
    ("reddit.com/r/artificial", "r/artificial"),
    ("reddit.com/r/chatgpt", "r/ChatGPT"),
    ("reddit.com/r/canadianinvestor", "r/CanadianInvestor"),
    ("reddit.com/r/investing", "r/investing"),
    ("reddit.com/r/stocks", "r/stocks"),
    ("reddit.com/r/personalfinancecanada", "r/PersonalFinanceCanada"),
    ("reddit.com", "Reddit"),
    # Space / Astronomy
    ("nasa.gov", "NASA"),
    ("space.com", "Space.com"),
    ("spaceflightnow", "Spaceflight Now"),
    ("spacenews.com", "SpaceNews"),
    ("astronomy.com", "Astronomy Magazine"),
    ("skyandtelescope", "Sky & Telescope"),
    ("universetoday", "Universe Today"),
    ("esa.int", "European Space Agency"),
    ("roscosmos", "Roscosmos"),
    ("jaxa.jp", "JAXA"),
    ("spacex.com", "SpaceX"),
    ("blueorigin", "Blue Origin"),
    # Science / Medicine
    ("nature.com", "Nature"),
    ("science.org", "Science"),
    ("cell.com", "Cell"),
    ("newscientist", "New Scientist"),
    ("scientificamerican", "Scientific American"),
    ("sciencedaily", "Science Daily"),
    ("sciencenews", "Science News"),
    ("quantamagazine", "Quanta Magazine"),
    ("technologyreview", "MIT Technology Review"),
    ("the-scientist", "The Scientist"),
    # Health / Longevity
    ("longevity", "Longevity Technology"),
    ("lifespan.io", "Lifespan.io"),
    ("healthline", "Healthline"),
    ("medicalnewstoday", "Medical News Today"),
    ("statnews", "STAT News"),
    ("nih.gov", "NIH"),
    ("cdc.gov", "CDC"),
    ("who.int", "WHO"),
    ("fda.gov", "FDA"),
    ("thelancet", "The Lancet"),
    ("jamanetwork", "JAMA"),
    ("nejm", "New England Journal of Medicine"),
    ("bmj.com", "BMJ"),
    ("harvard", "Harvard"),
    ("mayo", "Mayo Clinic"),
    # Finance / Investing
    ("financialpost.com", "Financial Post"),
    ("bnnbloomberg.ca", "BNN Bloomberg"),
    ("theglobeandmail.com", "Globe and Mail"),
    ("moneysense.ca", "MoneySense"),
    ("wealthsimple.com", "Wealthsimple"),
    ("youngandthrifty.ca", "Young and Thrifty"),
    ("finance.yahoo.com", "Yahoo Finance"),
    ("investopedia.com", "Investopedia"),
    ("fool.com", "Motley Fool"),
    ("marketwatch.com", "MarketWatch"),
    ("bankofcanada.ca", "Bank of Canada"),
    ("benzinga.com", "Benzinga"),
    ("finextra.com", "Finextra"),
    ("etfdb.com", "ETF Database"),
    ("etf.com", "ETF.com"),
    ("cointelegraph.com", "CoinTelegraph"),
    ("seekingalpha.com", "Seeking Alpha"),
    ("morningstar.com", "Morningstar"),
    # News / General
    ("reuters.com", "Reuters"),
    ("apnews.com", "AP News"),
    ("bbc.com", "BBC"),
    ("npr.org", "NPR"),
    ("cnbc.com", "CNBC"),
    ("bloomberg.com", "Bloomberg"),
    ("nytimes.com", "New York Times"),
    ("washingtonpost.com", "Washington Post"),
    ("theguardian.com", "The Guardian"),
    ("aljazeera.com", "Al Jazeera"),
    ("foxnews.com", "Fox News"),
    # Tesla-specific
    ("electrek.co", "Electrek"),
    ("teslarati.com", "Teslarati"),
    ("insideevs.com", "InsideEVs"),
    ("tesmanian.com", "Tesmanian"),
    ("notateslaapp.com", "Not a Tesla App"),
    ("torquenews.com", "Torque News"),
    ("cleantechnica.com", "CleanTechnica"),
]


def _get_source_name(feed_url: str, feed_title: str = "Unknown") -> str:
    """Map a feed URL to a human-readable source name."""
    url_lower = feed_url.lower()
    for pattern, name in _SOURCE_MAP:
        if pattern in url_lower:
            return name
    return feed_title if feed_title != "Unknown" else "Unknown"


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def _parse_entry_date(entry) -> Optional[datetime.datetime]:
    """Extract a UTC datetime from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime.datetime(
                    *parsed[:6], tzinfo=datetime.timezone.utc
                )
            except (ValueError, TypeError):
                pass
    return None


# ---------------------------------------------------------------------------
# Retry-wrapped HTTP helper
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    )),
    reraise=True,
)
def _fetch_url_with_retry(url: str) -> requests.Response:
    """GET a URL with automatic retry on transient network errors."""
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response


# ---------------------------------------------------------------------------
# Single-feed fetcher
# ---------------------------------------------------------------------------

def _fetch_single_feed(
    feed_url: str,
    cutoff_time: datetime.datetime,
    keywords: Optional[List[str]],
    problematic_feeds: set,
    problematic_feeds_lock: Lock,
    max_articles: int = 0,
) -> Optional[tuple]:
    """Fetch and parse a single RSS feed.

    Returns ``(feed_url, articles, source_name)`` on success, ``None`` on
    error or if the feed produced no usable articles.
    """
    import feedparser

    try:
        response = _fetch_url_with_retry(feed_url)
        feed = feedparser.parse(response.content)

        if feed.bozo and feed.bozo_exception:
            # Only skip if the feed produced zero entries — many valid feeds
            # trigger bozo on minor XML issues but still have usable entries.
            if not feed.entries:
                with problematic_feeds_lock:
                    if feed_url not in problematic_feeds:
                        problematic_feeds.add(feed_url)
                        logger.warning(
                            "RSS feed parsing failed (no entries): %s — %s",
                            feed_url,
                            str(feed.bozo_exception)[:100],
                        )
                return None
            else:
                logger.debug(
                    "RSS feed has minor XML issues but %d entries parsed OK: %s",
                    len(feed.entries), feed_url,
                )

        feed_title = feed.feed.get("title", "Unknown")
        source_name = _get_source_name(feed_url, feed_title)

        articles: List[Dict] = []
        for entry in feed.entries:
            published_time = _parse_entry_date(entry)

            # Skip articles older than the cutoff
            if published_time and published_time < cutoff_time:
                continue

            title = entry.get("title", "").strip()
            description = (
                entry.get("description", "").strip()
                or entry.get("summary", "").strip()
            )
            link = entry.get("link", "").strip()

            # Strip HTML from descriptions (Google News, Reddit, etc.)
            if description and "<" in description:
                description = _strip_html(description)
            if title and "<" in title:
                title = _strip_html(title)

            if not title or not link:
                continue

            # Sanitize the URL: strip C0/C1 control characters that have
            # leaked from RSS scrapes (the May 2 Omni View daily had
            # `?ito\x14...` literals in href attributes), and resolve
            # Google News redirect URLs to their canonical publisher
            # form so the email body stays under Gmail's 102 KB clip
            # threshold. Both ops are best-effort — `sanitize_url`
            # returns None on malformed URLs so we drop the article;
            # `resolve_google_news_url` returns the input unchanged on
            # network failure so we ship the redirect rather than
            # nothing.
            from engine.url_utils import (
                resolve_google_news_url,
                sanitize_url,
            )
            link_clean = sanitize_url(link)
            if not link_clean:
                logger.debug(
                    "Dropping article with malformed URL: %s — %s",
                    title[:60], link[:120],
                )
                continue
            link = resolve_google_news_url(link_clean)

            # Keyword filtering (if keywords provided)
            if keywords:
                text_lower = (title + " " + description).lower()
                if not any(kw in text_lower for kw in keywords):
                    continue

            articles.append(
                {
                    "title": title,
                    "description": description,
                    "url": link,
                    "source_name": source_name,
                    "published_date": (
                        published_time.isoformat()
                        if published_time
                        else datetime.datetime.now(
                            datetime.timezone.utc
                        ).isoformat()
                    ),
                    "relevance_score": 0.0,
                    "author": entry.get("author", ""),
                }
            )

        # Cap per-feed articles to prevent high-volume feeds (e.g. arXiv)
        # from flooding the pipeline with hundreds of entries.
        if max_articles and len(articles) > max_articles:
            logger.info(
                "Capping %s from %d to %d articles",
                source_name, len(articles), max_articles,
            )
            articles = articles[:max_articles]

        # Visibility: a feed that yields 0 usable articles is ambiguous —
        # it could be blocked/empty (0 entries parsed) or simply filtered
        # out (entries parsed but none matched the recency/keyword filters).
        # The old "Fetched 0 articles" log hid the difference, so a feed
        # silently going dark (Cloudflare block returning an empty body)
        # looked identical to a quiet news day. Surface the parsed count.
        if not articles:
            n_entries = len(feed.entries)
            if n_entries == 0:
                logger.warning(
                    "Feed yielded 0 entries (likely blocked/empty/stale URL): %s",
                    source_name,
                )
            else:
                logger.info(
                    "Feed %s: parsed %d entries but 0 passed recency/keyword "
                    "filters", source_name, n_entries,
                )

        return (feed_url, articles, source_name)

    except requests.RequestException as exc:
        with problematic_feeds_lock:
            if feed_url not in problematic_feeds:
                problematic_feeds.add(feed_url)
                logger.warning(
                    "Network error fetching RSS feed: %s — %s", feed_url, exc
                )
        return None
    except Exception as exc:
        with problematic_feeds_lock:
            if feed_url not in problematic_feeds:
                problematic_feeds.add(feed_url)
                logger.warning(
                    "RSS feed error: %s — %s", feed_url, exc
                )
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_rss_articles(
    feed_urls: List[Dict[str, str]],
    cutoff_hours: int = 24,
    keywords: Optional[List[str]] = None,
    *,
    max_workers: int = 10,
    similarity_threshold: float = 0.85,
    max_articles_per_feed: int = 50,
) -> List[Dict]:
    """Fetch, filter, and deduplicate articles from RSS feeds.

    Parameters
    ----------
    feed_urls:
        List of ``{"url": "...", "label": "..."}`` dicts.
    cutoff_hours:
        Only include articles published within the last *cutoff_hours*.
    keywords:
        If provided, only include articles whose title+description
        contain at least one keyword (case-insensitive).
    max_workers:
        Maximum number of concurrent feed fetches.
    similarity_threshold:
        Threshold for deduplication (0.0–1.0).  Articles above this
        similarity are considered duplicates.
    max_articles_per_feed:
        Maximum number of articles to keep from any single feed.
        Prevents high-volume feeds (e.g. arXiv) from flooding the
        pipeline.  Set to 0 to disable the cap.

    Returns
    -------
    list[dict]
        Deduplicated articles sorted newest-first.  Each dict has keys:
        ``title``, ``description``, ``url``, ``source_name``,
        ``published_date``, ``relevance_score``, ``author``.
    """
    cutoff_time = datetime.datetime.now(
        datetime.timezone.utc
    ) - datetime.timedelta(hours=cutoff_hours)

    urls = [fd["url"] for fd in feed_urls]
    logger.info("Fetching news from %d RSS feeds...", len(urls))

    all_articles: List[Dict] = []
    problematic_feeds: set = set()
    problematic_feeds_lock = Lock()
    successful_feeds = 0

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_url = {
            pool.submit(
                _fetch_single_feed,
                url,
                cutoff_time,
                keywords,
                problematic_feeds,
                problematic_feeds_lock,
                max_articles_per_feed,
            ): url
            for url in urls
        }
        for future in as_completed(future_to_url):
            result = future.result()
            if result:
                _feed_url, feed_articles, source_name = result
                successful_feeds += 1
                logger.info(
                    "Fetched %d articles from %s",
                    len(feed_articles),
                    source_name,
                )
                all_articles.extend(feed_articles)

    raw_count = len(all_articles)
    failed_feeds = len(problematic_feeds)
    logger.info("Fetched %d total articles from RSS feeds", raw_count)
    if problematic_feeds:
        logger.warning(
            "Skipped %d problematic feed(s): %s",
            len(problematic_feeds),
            ", ".join(sorted(problematic_feeds)),
        )

    if not all_articles:
        logger.warning("No articles found from RSS feeds")
        logger.info(
            "RSS fetch summary: %d feeds attempted, %d succeeded, %d failed, "
            "%d raw articles, 0 after dedup",
            len(urls), successful_feeds, failed_feeds, raw_count,
        )
        return []

    # Deduplicate
    before = len(all_articles)
    articles = remove_similar_items(
        all_articles,
        similarity_threshold=similarity_threshold,
        get_text_func=lambda x: f"{x.get('title', '')} {x.get('description', '')}",
    )
    after = len(articles)
    if before != after:
        logger.info(
            "Removed %d similar/duplicate articles", before - after
        )
    logger.info(
        "RSS fetch summary: %d feeds attempted, %d succeeded, %d failed, "
        "%d raw articles, %d after dedup",
        len(urls), successful_feeds, failed_feeds, raw_count, after,
    )

    # Sort newest first
    articles.sort(key=lambda x: x.get("published_date", ""), reverse=True)

    logger.info("Returning %d unique articles", len(articles))
    return articles


# ---------------------------------------------------------------------------
# X / Twitter account fetcher (via xAI Grok x_search)
# ---------------------------------------------------------------------------

def x_fetch_allowed(
    x_accounts: list,
    x_enabled: bool,
    x_fetch_enabled: Optional[bool] = None,
) -> bool:
    """Whether to fetch X posts as a *content source* for this show.

    Decouples X *sourcing* from X *posting*. A show with curated
    ``x_accounts`` can read them for content even when it never posts to X
    (``x_enabled: false``) — set ``x_fetch_enabled: true`` in its YAML.

    Resolution:
      - no ``x_accounts`` → never fetch.
      - ``x_fetch_enabled`` explicitly set (True/False) → honour it.
      - otherwise default to ``x_enabled`` (preserves the pre-existing
        behaviour where X fetch piggy-backed on the X-posting flag, so
        every other show is byte-for-byte unchanged).
    """
    if not x_accounts:
        return False
    if x_fetch_enabled is not None:
        return bool(x_fetch_enabled)
    return bool(x_enabled)


def fetch_x_posts(
    x_accounts: list,
    keywords: Optional[List[str]] = None,
) -> List[Dict]:
    """Fetch recent posts from X accounts via per-account parallel API calls.

    Each account gets its own Responses API call with
    ``x_search(allowed_x_handles=[handle])``.  Calls run in parallel via
    ThreadPoolExecutor so total wall-clock time ≈ one call.  Results are
    deduped across accounts (same story from two sources → keep first).
    """
    import datetime as _dt
    import os
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not x_accounts:
        return []

    api_key = (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()
    if not api_key:
        logger.warning("No GROK_API_KEY — skipping X account fetch")
        return []

    handle_list = ", ".join(f"@{a.handle.lstrip('@')}" for a in x_accounts)
    logger.info("Fetching X posts from %d accounts (%s) via parallel per-account calls ...", len(x_accounts), handle_list)

    from digests.xai_grok import grok_generate_text

    def _fetch_one(account) -> List[Dict]:
        handle = account.handle.lstrip("@")
        label = account.label or f"@{handle}"
        max_posts = getattr(account, "max_posts", 10) or 10

        prompt = (
            f"Search X/Twitter for the most recent posts from @{handle} "
            f"in the last 24 hours.\n\n"
            f"Return ONLY a structured list of their posts, formatted exactly like this "
            f"(one block per post, separated by blank lines):\n\n"
            f"POST_TITLE: [A short headline summarizing the post, max 100 chars]\n"
            f"POST_TEXT: [The full text of the post]\n"
            f"POST_URL: [The URL, e.g. https://x.com/{handle}/status/...]\n\n"
            f"Rules:\n"
            f"- Up to {max_posts} posts maximum\n"
            f"- Only posts from the last 24 hours\n"
            f"- Skip retweets — only original posts and quote tweets\n"
            f"- If no recent posts, return exactly: NO_RECENT_POSTS\n"
            f"- No commentary — just the structured list\n"
        )

        try:
            text, meta = grok_generate_text(
                prompt=prompt,
                enable_x_search=True,
                x_handles=[handle],
                max_turns=5,
            )
        except Exception as exc:
            logger.error("X fetch @%s failed: %s — %s", handle, type(exc).__name__, exc)
            return []

        if not text or "NO_RECENT_POSTS" in text:
            logger.info("No recent posts from @%s", handle)
            return []

        now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()
        labels_map = {handle.lower(): label}
        posts = _parse_x_posts_multi(text, [handle], labels_map, now_iso)

        if not posts:
            logger.warning(
                "X @%s returned %d chars but parser extracted 0 posts. First 300: %s",
                handle, len(text), text[:300].replace("\n", " | "),
            )
            return []

        posts = posts[:max_posts]
        logger.info("X @%s: %d posts fetched", handle, len(posts))
        return posts

    # Run all account fetches in parallel
    all_posts: List[Dict] = []
    with ThreadPoolExecutor(max_workers=min(len(x_accounts), 5)) as pool:
        futures = {pool.submit(_fetch_one, acc): acc for acc in x_accounts}
        for future in as_completed(futures):
            try:
                posts = future.result(timeout=60)
                all_posts.extend(posts)
            except Exception as exc:
                acc = futures[future]
                logger.error("X fetch @%s timed out or crashed: %s", acc.handle, exc)

    # X-to-X dedup: if two accounts post about the same story, keep the first
    from engine.utils import calculate_similarity
    deduped: List[Dict] = []
    for p in all_posts:
        p_title = (p.get("title") or "")[:200]
        is_dup = any(
            calculate_similarity(p_title, d.get("title", "")[:200]) >= 0.65
            for d in deduped
        ) if p_title else False
        if is_dup:
            logger.info("X-to-X dedup: dropped '%s' (dup of earlier X post)", p_title[:60])
        else:
            deduped.append(p)
    all_posts = deduped

    if all_posts:
        by_author: Dict[str, list] = {}
        for p in all_posts:
            by_author.setdefault(p.get("author", "?"), []).append(p)
        breakdown = ", ".join(f"{a}: {len(ps)}" for a, ps in sorted(by_author.items()))
        logger.info("X fetch: %d posts total (%s)", len(all_posts), breakdown)
    else:
        logger.error("X fetch produced 0 posts from %d account(s)", len(x_accounts))

    return all_posts


def _parse_x_posts_multi(
    text: str,
    handles: List[str],
    labels: Dict[str, str],
    now_iso: str,
) -> List[Dict]:
    """Parse X posts from LLM response — handles multiple output formats.

    Tries structured POST_AUTHOR/POST_TITLE/POST_URL blocks first, then
    falls back to extracting any x.com/*/status/* URLs with surrounding text.
    """

    # --- Attempt 1: structured POST_TITLE/POST_URL blocks ---
    posts = _parse_structured_blocks(text, handles, labels, now_iso)
    if posts:
        return posts

    # --- Attempt 2: extract any x.com status URLs with context ---
    posts = _parse_url_extraction(text, handles, labels, now_iso)
    if posts:
        logger.info("Fallback URL parser extracted %d posts from response", len(posts))
    return posts


def _parse_structured_blocks(
    text: str,
    handles: List[str],
    labels: Dict[str, str],
    now_iso: str,
) -> List[Dict]:
    """Parse POST_AUTHOR/POST_TITLE/POST_TEXT/POST_URL blocks."""
    import re

    posts: List[Dict] = []
    blocks = re.split(r"(?=POST_(?:AUTHOR|TITLE)\s*:)", text.strip())
    current_author = handles[0] if handles else "unknown"

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        author_m = re.search(r"POST_AUTHOR\s*:\s*@?(\S+)", block)
        if author_m:
            current_author = author_m.group(1).strip().lower()
            if "POST_TITLE" not in block:
                continue

        title_m = re.search(r"POST_TITLE\s*:\s*(.+?)(?:\n|$)", block)
        text_m = re.search(r"POST_TEXT\s*:\s*(.+?)(?=POST_URL|POST_AUTHOR|\Z)", block, re.DOTALL)
        url_m = re.search(r"POST_URL\s*:\s*(https?://\S+)", block)

        title = title_m.group(1).strip() if title_m else ""
        desc = text_m.group(1).strip() if text_m else ""

        if not url_m:
            continue
        url = url_m.group(1).strip()

        if not title and not desc:
            continue

        label = labels.get(current_author, f"@{current_author}")
        posts.append({
            "title": title or desc[:100],
            "description": desc,
            "url": url,
            "source_name": f"{label} (X)",
            "published_date": now_iso,
            "relevance_score": 0.7,
            "author": f"@{current_author}",
        })

    return posts


def _parse_url_extraction(
    text: str,
    handles: List[str],
    labels: Dict[str, str],
    now_iso: str,
) -> List[Dict]:
    """Fallback: extract x.com/*/status/* URLs and nearby text as posts."""
    import re

    posts: List[Dict] = []
    seen_urls: set = set()

    for m in re.finditer(r"https?://(?:x\.com|twitter\.com)/(\w+)/status(?:es)?/(\d+)\S*", text):
        url = m.group(0).split(")")[0].rstrip(".,;")
        if url in seen_urls:
            continue
        seen_urls.add(url)

        author_handle = m.group(1).lower()

        # Extract surrounding text as description (100 chars before, 200 after)
        start = max(0, m.start() - 150)
        end = min(len(text), m.end() + 300)
        context = text[start:end]

        # Try to extract a meaningful line near the URL
        lines = context.split("\n")
        desc_parts = []
        for line in lines:
            stripped = line.strip().strip("-*•#>").strip()
            if stripped and "http" not in stripped and len(stripped) > 15:
                desc_parts.append(stripped)
        desc = " ".join(desc_parts[:3])[:300] if desc_parts else ""
        title = desc[:100] if desc else f"Post by @{author_handle}"

        label = labels.get(author_handle, f"@{author_handle}")
        posts.append({
            "title": title,
            "description": desc,
            "url": url,
            "source_name": f"{label} (X)",
            "published_date": now_iso,
            "relevance_score": 0.7,
            "author": f"@{author_handle}",
        })

    return posts


def _parse_x_posts(
    text: str,
    handle: str,
    label: str,
    now_iso: str,
) -> List[Dict]:
    """Parse structured POST_TITLE/POST_TEXT/POST_URL blocks from Grok output."""
    import re

    posts: List[Dict] = []
    # Split on POST_TITLE to find individual post blocks
    blocks = re.split(r"(?=POST_TITLE\s*:)", text.strip())

    for block in blocks:
        block = block.strip()
        if not block.startswith("POST_TITLE"):
            continue

        title_m = re.search(r"POST_TITLE\s*:\s*(.+?)(?:\n|$)", block)
        text_m = re.search(r"POST_TEXT\s*:\s*(.+?)(?=POST_URL|\Z)", block, re.DOTALL)
        url_m = re.search(r"POST_URL\s*:\s*(https?://\S+)", block)

        title = title_m.group(1).strip() if title_m else ""
        desc = text_m.group(1).strip() if text_m else ""

        if not url_m:
            logger.debug(
                "Dropping X post with no real URL from @%s: %s",
                handle, (title or desc)[:60],
            )
            continue
        url = url_m.group(1).strip()

        if not title and not desc:
            continue

        posts.append({
            "title": title or desc[:100],
            "description": desc,
            "url": url,
            "source_name": f"{label} (X)",
            "published_date": now_iso,
            "relevance_score": 0.7,
            "author": f"@{handle}",
        })

    return posts


# ---------------------------------------------------------------------------
# Web search fetcher (via xAI Grok web_search)
# ---------------------------------------------------------------------------

def fetch_web_search_articles(
    queries: List[str],
    keywords: Optional[List[str]] = None,
    max_results_per_query: int = 10,
) -> List[Dict]:
    """Fetch recent news articles using xAI's web_search tool.

    Supplements RSS feeds on slow news days by searching the web for
    articles matching the provided queries.

    Parameters
    ----------
    queries:
        List of search query strings (e.g. ``["Tesla news today"]``).
    keywords:
        Optional keyword filter applied after retrieval.
    max_results_per_query:
        Maximum articles to extract per query.

    Returns
    -------
    list[dict]
        Articles with standard keys: ``title``, ``description``, ``url``,
        ``source_name``, ``published_date``, ``relevance_score``, ``author``.
    """
    import datetime as _dt
    import os
    import re

    if not queries:
        return []

    api_key = (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()
    if not api_key:
        logger.warning("No GROK_API_KEY — skipping web search fetch")
        return []

    all_articles: List[Dict] = []
    now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()

    for query in queries:
        logger.info("Web search: querying '%s' ...", query)
        try:
            from digests.xai_grok import grok_generate_text

            extraction_prompt = (
                f"Search the web for recent news articles (last 24 hours) about: {query}\n\n"
                f"Return ONLY a structured list of articles, formatted exactly like this "
                f"(one block per article, separated by blank lines):\n\n"
                f"ARTICLE_TITLE: [exact headline]\n"
                f"ARTICLE_URL: [full URL]\n"
                f"ARTICLE_DESCRIPTION: [2-3 sentence summary]\n"
                f"ARTICLE_SOURCE: [publication name]\n\n"
                f"Rules:\n"
                f"- Include up to {max_results_per_query} articles maximum\n"
                f"- Only include articles from the last 24 hours\n"
                f"- Skip opinion pieces, editorials, and social media posts\n"
                f"- If no recent articles found, return exactly: NO_RECENT_ARTICLES\n"
                f"- Do NOT add any commentary — just the structured list\n"
            )

            text, _meta = grok_generate_text(
                prompt=extraction_prompt,
                enable_web_search=True,
                max_turns=5,
            )

            if not text or "NO_RECENT_ARTICLES" in text:
                logger.info("Web search: no recent articles for '%s'", query)
                continue

            # Parse structured response
            blocks = re.split(r"(?=ARTICLE_TITLE\s*:)", text.strip())
            query_articles = 0
            for block in blocks:
                block = block.strip()
                if not block.startswith("ARTICLE_TITLE"):
                    continue

                title_m = re.search(r"ARTICLE_TITLE\s*:\s*(.+?)(?:\n|$)", block)
                url_m = re.search(r"ARTICLE_URL\s*:\s*(https?://\S+)", block)
                desc_m = re.search(
                    r"ARTICLE_DESCRIPTION\s*:\s*(.+?)(?=ARTICLE_SOURCE|\Z)",
                    block, re.DOTALL,
                )
                source_m = re.search(r"ARTICLE_SOURCE\s*:\s*(.+?)(?:\n|$)", block)

                title = title_m.group(1).strip() if title_m else ""
                url = url_m.group(1).strip() if url_m else ""
                desc = desc_m.group(1).strip() if desc_m else ""
                source = source_m.group(1).strip() if source_m else "Web"

                if not title or not url:
                    continue

                all_articles.append({
                    "title": title,
                    "description": desc,
                    "url": url,
                    "source_name": f"{source} (web)",
                    "published_date": now_iso,
                    "relevance_score": 0.0,
                    "author": "",
                })
                query_articles += 1

            logger.info("Web search: %d articles from '%s'", query_articles, query)

        except Exception as exc:
            logger.warning("Web search failed for '%s': %s", query, exc)
            continue

    # Keyword filter
    if keywords and all_articles:
        kw_lower = [k.lower() for k in keywords]
        before = len(all_articles)
        all_articles = [
            a for a in all_articles
            if any(
                kw in (a.get("title", "") + " " + a.get("description", "")).lower()
                for kw in kw_lower
            )
        ]
        if before != len(all_articles):
            logger.info("Web search keyword filter: %d → %d articles", before, len(all_articles))

    # Dedup
    if all_articles:
        all_articles = remove_similar_items(
            all_articles,
            similarity_threshold=0.80,
            get_text_func=lambda x: f"{x.get('title', '')} {x.get('description', '')}",
        )

    # Escalate to ERROR when we tried N queries and got zero results — a
    # clean zero on a non-empty query list is almost always a Grok/API issue.
    if queries and not all_articles:
        logger.error(
            "Web search produced 0 articles from %d quer(y|ies) — Grok "
            "web_search may be down or credentials rejected",
            len(queries),
        )
    else:
        logger.info("Web search summary: %d queries, %d articles returned", len(queries), len(all_articles))
    return all_articles
