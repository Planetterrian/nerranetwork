"""Article dating: one module decides what an article's date IS and how far
it can be trusted (Sep 30 2026 network review).

The operator heard months-old stories aired as today's news. The audit found
the reason was not one bug but a shared assumption: every path that could
not date an article stamped it with the RUN CLOCK. Undated feed entries,
every xAI ``web_search`` result, every X post and every Google News item
(whose feed date is the INDEX date, not the article's) all arrived carrying
today's date, sorted to the top of the digest prompt, and printed
``(2026-09-30)`` beside a headline the prompt then told the model was
"FRESH (within last 48 hours)". Nothing downstream could tell them from a
genuinely fresh story, because by then they looked identical.

Contract:

* ``published_date`` is the article's date as an ISO string, or ``""`` when
  nothing dated it. An empty string sorts LAST under every existing
  newest-first sort and renders NO date in the prompt (``prompt_pub_date``
  already returns ``""`` for it) — an unknown date is never shown as today.
* ``date_source`` names where the date came from (the constants below).
  ``feed`` / ``url_path`` / ``page`` are trusted; ``index`` (a Google News
  feed date), ``model`` (a date the search model claimed), ``x_post`` (a
  post date the model reported) and ``unknown`` are not, and are the
  articles :func:`probe_page_dates` opens to read the publisher's own date.
* ``page_published_date`` is set only by reading the page. It outranks
  ``published_date`` in :func:`engine.article_text.article_age_days`, which
  is what the ``stale_article_days`` gate reads.

Nothing here drops an article on its own. The gate is
:func:`engine.article_text.drop_stale_articles`; this module only makes
sure it has a real date to read.
"""
from __future__ import annotations

import datetime as _dt
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

DATE_SOURCE_FEED = "feed"          # the feed's own pubDate / updated
DATE_SOURCE_INDEX = "index"        # an aggregator's index date (Google News)
DATE_SOURCE_URL_PATH = "url_path"  # /YYYY/MM/DD/ in the publisher URL
DATE_SOURCE_PAGE = "page"          # read from the page's meta / JSON-LD
DATE_SOURCE_MODEL = "model"        # a date the search model reported
DATE_SOURCE_X_POST = "x_post"      # a post date the search model reported
DATE_SOURCE_UNKNOWN = "unknown"    # nothing dated it

TRUSTED_DATE_SOURCES = frozenset({
    DATE_SOURCE_FEED, DATE_SOURCE_URL_PATH, DATE_SOURCE_PAGE,
})

# Sep 30 2026: the default number of pages a run may open to date the
# articles nothing else dated. The prompt list is capped at 40; on a clean
# feed day the probe opens nothing at all.
DEFAULT_MAX_PROBES = 12

_DATE_TOKEN_RE = re.compile(r"(20[0-9]{2})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])")
_X_HOST_RE = re.compile(r"^https?://(?:www\.|mobile\.)?(?:x\.com|twitter\.com|t\.co)/", re.I)


def parse_date_token(raw: Optional[str]) -> Optional[_dt.datetime]:
    """``YYYY-MM-DD`` (anywhere in *raw*) as an aware UTC datetime at the END
    of that day, or ``None``. ``unknown`` / ``none`` / blank are ``None``.

    End of day, not midnight: a date can only ever say "no later than
    this" (the same rule ``engine.fetcher._url_path_date`` follows), so a
    freshness check can never call today's article stale for being dated
    at 00:00.
    """
    text = (raw or "").strip()
    if not text or text.lower() in {"unknown", "none", "n/a", "null"}:
        return None
    m = _DATE_TOKEN_RE.search(text)
    if not m:
        return None
    try:
        day = _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                           tzinfo=_dt.timezone.utc)
    except ValueError:
        return None
    return day + _dt.timedelta(days=1) - _dt.timedelta(seconds=1)


_MONTHS = ("january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december")
_SLUG_WORD_DATE_RE = re.compile(
    r"(?:^|[-_])(" + "|".join(_MONTHS) + r")-([0-3]?[0-9])-(20[0-9]{2})(?=$|[-_.])",
    re.I,
)
_SLUG_ISO_DATE_RE = re.compile(
    r"(?:^|[-_])(20[0-9]{2})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])(?=$|[-_.])"
)
_PATH_DATE_RE = re.compile(r"/20[0-9]{2}/(?:0[1-9]|1[0-2])(?:/|$)")
_URL_PATH_DATE_RE = re.compile(
    r"/(20[0-9]{2})/(0[1-9]|1[0-2])(?:/(0[1-9]|[12][0-9]|3[01]))?(?=/|$)")


def url_path_date(url: str) -> Optional[_dt.datetime]:
    """Publication date implied by a ``/YYYY/MM[/DD]/`` URL path, as a UTC
    datetime, or ``None`` when the URL carries no such path.

    A day-dated path is the END of that day; a month-only path is the LAST
    second of that month — a path date can only ever say "no later than
    this", so a freshness check never calls a recent article stale.
    ``engine.fetcher._url_path_date`` delegates here.

    Oct 17 2026 readout (freshness-dating-2026-09-30): Planetterrian
    2026-10-07 cited ``bjo.bmj.com/content/early/2026/09/18/…`` — nineteen
    days old on a ``stale_article_days: 3`` show — because the stale gate
    read only the page and feed dates (a journal feed dates an online-first
    paper by its issue) and the URL path was checked only against the
    fetch window. :func:`engine.article_text.article_age_days` now reads
    this date too, older-only, like :func:`url_slug_date`.
    """
    if not url:
        return None
    m = _URL_PATH_DATE_RE.search(url)
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    day = int(m.group(3)) if m.group(3) else None
    try:
        if day is None:
            nxt = _dt.datetime(year + (month == 12), (month % 12) + 1, 1,
                               tzinfo=_dt.timezone.utc)
            return nxt - _dt.timedelta(seconds=1)
        return (_dt.datetime(year, month, day, tzinfo=_dt.timezone.utc)
                + _dt.timedelta(days=1) - _dt.timedelta(seconds=1))
    except ValueError:
        return None


#: ``S0092-8674(08)01317-2`` / ``S0092867408013172`` / percent-encoded.
_PII_YEAR_RE = re.compile(r"/S\d{4}-?\d{3}[\dX](?:\(|%28)?(\d{2})(?:\)|%29)?\d{5}-?[\dX]",
                          re.IGNORECASE)


def url_slug_date(url: str) -> Optional[_dt.datetime]:
    """The EARLIEST date written into a URL's path words, end of that day.

    Oct 17 2026, Omni View Ep208: The Hindu's
    ``…/panama-earthquake-toll-injuries-damage-update-october-10-2026/…``
    aired as that morning's news a week late, and as a less accurate story
    than the show had told on Oct 11. Its feed date was fresh and the URL
    has no ``/YYYY/MM/`` path, so nothing read the date the publisher wrote
    into the slug. A slug date is a date the story already existed on, so
    it can only make an article OLDER; a deadline or event date ahead of
    the run ("…-by-march-31-2027", "…-results-on-november-10-2026") never
    makes anything stale. A URL with a ``/YYYY/MM/`` path is left to that
    path (a slug there names a period, e.g. "…period-ending-september-30").
    Calibrated on every content tracker (732 slug-dated URLs): four were
    used more than three days after their slug date, all four re-surfaced
    stories.
    """
    from urllib.parse import urlsplit

    try:
        path = urlsplit(url or "").path
    except ValueError:
        return None
    if not path or _PATH_DATE_RE.search(path):
        return None
    found: List[_dt.datetime] = []
    for seg in path.split("/"):
        for m in _SLUG_WORD_DATE_RE.finditer(seg):
            try:
                found.append(_dt.datetime(int(m.group(3)), _MONTHS.index(m.group(1).lower()) + 1,
                                          int(m.group(2)), tzinfo=_dt.timezone.utc))
            except ValueError:
                pass
        for m in _SLUG_ISO_DATE_RE.finditer(seg):
            try:
                found.append(_dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                          tzinfo=_dt.timezone.utc))
            except ValueError:
                pass
    # Oct 22 2026: an Elsevier PII carries its year — S0092-8674(08)01317-2
    # is a 2008 Cell paper, which Planetterrian Ep221 aired as news under a
    # fresh feed date. The two digits in the parentheses are the year the
    # manuscript was registered; a paper registered in December can publish
    # in January, so the article counts as published by the last day of the
    # FOLLOWING year — a decade-old paper is still stale, a fresh one never.
    for m in _PII_YEAR_RE.finditer(url or ""):
        yy = int(m.group(1))
        year = 1900 + yy if yy >= 80 else 2000 + yy
        found.append(_dt.datetime(year + 1, 12, 31, tzinfo=_dt.timezone.utc))
    if not found:
        return None
    return min(found) + _dt.timedelta(days=1) - _dt.timedelta(seconds=1)


def stamp(article: Dict, when: Optional[_dt.datetime], source: str) -> Dict:
    """Write *when* (or ``""``) and *source* onto *article* in place."""
    article["published_date"] = when.isoformat() if when is not None else ""
    article["date_source"] = source if when is not None else DATE_SOURCE_UNKNOWN
    return article


def is_trusted(article: Dict) -> bool:
    return bool(article.get("page_published_date")) or (
        article.get("date_source") in TRUSTED_DATE_SOURCES
    )


def needs_probe(article: Dict) -> bool:
    """An article whose date nothing trustworthy supplied, with a page that
    can be opened. X posts themselves are never probed (x.com serves no
    article to a plain GET); a post that linked an article carries the
    ARTICLE url and is probed like any other."""
    if is_trusted(article):
        return False
    if article.get("source_kind") == "hook" or article.get("exempt_stale"):
        return False
    url = str(article.get("url") or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return False
    if _X_HOST_RE.match(url):
        return False
    return True


def too_old(when: Optional[_dt.datetime], *, max_age_hours: int, now=None,
            slack_hours: int = 24) -> bool:
    """True when *when* is older than the window plus a day of slack. An
    unknown date is never "too old" — that is the probe's question, not
    this one's."""
    if when is None or max_age_hours <= 0:
        return False
    now = now or _dt.datetime.now(_dt.timezone.utc)
    return when < now - _dt.timedelta(hours=max_age_hours + slack_hours)


def probe_page_dates(
    articles: Iterable[Dict],
    *,
    max_probes: int = DEFAULT_MAX_PROBES,
    fetch: Optional[Callable[[str], Tuple[int, str]]] = None,
    workers: int = 4,
) -> Dict[str, int]:
    """Open the pages of the articles nothing trustworthy dated and read the
    publisher's own date. In-place, best-effort, bounded by *max_probes*.

    A page date found sets ``page_published_date`` AND replaces
    ``published_date`` / ``date_source`` (the page outranks an index date,
    a model's claim and the run clock alike), so the prompt's newest-first
    order and the ``(YYYY-MM-DD)`` beside the headline both tell the truth.
    A page that carries no date leaves the article as it was: undated,
    sorted last, never printed as today.

    Returns counters for the metrics file: ``candidates`` (articles that
    needed a date), ``probed`` (pages opened), ``dated`` (dates found).
    """
    from engine.article_text import default_fetch, extract_published_date

    todo = [a for a in articles if needs_probe(a)]
    counters = {"candidates": len(todo), "probed": 0, "dated": 0}
    if not todo or max_probes <= 0:
        return counters
    todo = todo[:max_probes]
    fetcher = fetch or default_fetch

    def _one(art: Dict) -> Optional[_dt.datetime]:
        try:
            status, html = fetcher(art["url"])
        except Exception as exc:  # noqa: BLE001 — never break a run
            logger.info("Date probe failed for %s: %s", art["url"][:100], exc)
            return None
        if status != 200 or not html:
            return None
        return extract_published_date(html, art.get("url", ""))

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(todo)))) as pool:
        futures = {pool.submit(_one, a): a for a in todo}
        for fut in as_completed(futures):
            art = futures[fut]
            counters["probed"] += 1
            try:
                found = fut.result()
            except Exception:  # noqa: BLE001
                found = None
            if found is None:
                continue
            art["page_published_date"] = found.isoformat()
            stamp(art, found, DATE_SOURCE_PAGE)
            counters["dated"] += 1
    logger.info(
        "Date probe: %d article(s) carried no trusted date; opened %d page(s), "
        "dated %d", counters["candidates"], counters["probed"], counters["dated"],
    )
    return counters


def count_undated(articles: Iterable[Dict]) -> int:
    """Articles that will reach the prompt with no date at all."""
    return sum(1 for a in articles if not (a.get("published_date") or "").strip())


def summarize_date_sources(articles: Iterable[Dict]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for a in articles:
        key = a.get("date_source") or (
            DATE_SOURCE_FEED if a.get("published_date") else DATE_SOURCE_UNKNOWN
        )
        out[key] = out.get(key, 0) + 1
    return out


__all__: List[str] = [
    "DATE_SOURCE_FEED", "DATE_SOURCE_INDEX", "DATE_SOURCE_URL_PATH",
    "DATE_SOURCE_PAGE", "DATE_SOURCE_MODEL", "DATE_SOURCE_X_POST",
    "DATE_SOURCE_UNKNOWN", "TRUSTED_DATE_SOURCES", "DEFAULT_MAX_PROBES",
    "parse_date_token", "url_path_date", "url_slug_date",
    "stamp", "is_trusted", "needs_probe", "too_old",
    "probe_page_dates", "count_undated", "summarize_date_sources",
]
