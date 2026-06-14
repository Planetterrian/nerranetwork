"""
Unit tests for engine/fetcher.py — RSS feed fetching pipeline.

Covers:
  - _get_source_name(): URL-to-source-name mapping
  - _parse_entry_date(): feedparser date extraction
  - _fetch_single_feed(): single-feed fetch with mocked HTTP + feedparser
  - fetch_rss_articles(): end-to-end orchestration (parallelism, dedup, sorting)
  - Keyword filtering edge cases
  - Deduplication behaviour

All network calls are mocked — no real HTTP requests are made.
"""

import datetime
import sys
import time
from threading import Lock
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

from engine.fetcher import (
    _get_source_name,
    _parse_entry_date,
    _publisher_from_entry,
    _fetch_single_feed,
    fetch_rss_articles,
    _SOURCE_MAP,
)


class TestPublisherFromEntry:
    """Transparent sourcing: recover the real outlet from a Google News item
    so digests/blogs cite the publisher, not the opaque 'Google News' redirect
    (June 14 2026)."""

    def test_prefers_source_element(self):
        entry = {"source": {"title": "Space.com", "href": "https://www.space.com"},
                 "title": "A black hole at the dawn of time - Space.com"}
        assert _publisher_from_entry(entry) == "Space.com"

    def test_falls_back_to_title_suffix(self):
        entry = {"title": "Japan's H3 rocket returns to flight successfully - Ars Technica"}
        assert _publisher_from_entry(entry) == "Ars Technica"

    def test_guards_against_headline_clause(self):
        # Short head before the dash must NOT be mistaken for a headline.
        assert _publisher_from_entry({"title": "AI - the future"}) is None

    def test_none_when_no_publisher(self):
        assert _publisher_from_entry({"title": "A plain headline with no dash"}) is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UTC = datetime.timezone.utc


def _utc_now():
    return datetime.datetime.now(UTC)


def _make_entry(
    title="Test Article",
    link="https://example.com/article",
    description="A test description",
    summary=None,
    published_parsed=None,
    updated_parsed=None,
    author="",
):
    """Build a mock feedparser entry (SimpleNamespace with dict-style .get())."""
    data = {
        "title": title,
        "link": link,
        "description": description,
        "author": author,
    }
    if summary is not None:
        data["summary"] = summary

    entry = SimpleNamespace(**data)
    # feedparser entries support both attribute and .get() access
    entry.get = lambda key, default="": data.get(key, default)

    if published_parsed is not None:
        entry.published_parsed = published_parsed
    if updated_parsed is not None:
        entry.updated_parsed = updated_parsed
    return entry


def _dt_to_timetuple(dt):
    """Convert a datetime to a time.struct_time (feedparser style)."""
    return dt.timetuple()


def _make_feed(entries, title="Test Feed", bozo=False, bozo_exception=None):
    """Build a mock feedparser result object."""
    feed_info = {"title": title}
    feed_ns = SimpleNamespace()
    feed_ns.get = lambda key, default="": feed_info.get(key, default)
    return SimpleNamespace(
        feed=feed_ns,
        entries=entries,
        bozo=bozo,
        bozo_exception=bozo_exception,
    )


@pytest.fixture()
def mock_feedparser():
    """Inject a mock feedparser module into sys.modules for the duration of
    each test, so that the local ``import feedparser`` inside
    ``_fetch_single_feed`` resolves to our mock."""
    mock_fp = MagicMock()
    with patch.dict(sys.modules, {"feedparser": mock_fp}):
        yield mock_fp


# ===================================================================
# TestGetSourceName
# ===================================================================

class TestGetSourceName:
    """Tests for _get_source_name: URL -> human-readable name mapping."""

    def test_nasa_mapping(self):
        assert _get_source_name("https://www.nasa.gov/feed") == "NASA"

    def test_reuters_mapping(self):
        assert _get_source_name("https://feeds.reuters.com/news") == "Reuters"

    def test_bbc_mapping(self):
        assert _get_source_name("https://feeds.bbc.com/news/rss.xml") == "BBC"

    def test_spacex_mapping(self):
        assert _get_source_name("https://www.spacex.com/rss") == "SpaceX"

    def test_electrek_mapping(self):
        assert _get_source_name("https://electrek.co/feed/") == "Electrek"

    def test_case_insensitive_url(self):
        """URL matching should be case-insensitive."""
        assert _get_source_name("https://WWW.NASA.GOV/RSS") == "NASA"

    def test_unknown_domain_returns_feed_title(self):
        """When URL matches nothing, the feed title is used as fallback."""
        result = _get_source_name(
            "https://unknownsite.org/feed", "My Custom Feed"
        )
        assert result == "My Custom Feed"

    def test_unknown_domain_default_title(self):
        """When URL matches nothing and title is 'Unknown', return 'Unknown'."""
        result = _get_source_name("https://unknownsite.org/feed", "Unknown")
        assert result == "Unknown"

    def test_unknown_domain_no_title_argument(self):
        """Omitting the feed_title argument should default to 'Unknown'."""
        result = _get_source_name("https://unknownsite.org/feed")
        assert result == "Unknown"

    def test_first_match_wins(self):
        """When multiple patterns could match, the first one in _SOURCE_MAP wins."""
        # "nature.com" appears before any other nature-containing pattern
        assert _get_source_name("https://www.nature.com/rss") == "Nature"

    def test_all_source_map_entries_work(self):
        """Every entry in _SOURCE_MAP should resolve correctly."""
        for pattern, expected_name in _SOURCE_MAP:
            url = f"https://www.{pattern}/feed"
            assert _get_source_name(url) == expected_name, (
                f"Expected '{expected_name}' for pattern '{pattern}'"
            )


# ===================================================================
# TestParseEntryDate
# ===================================================================

class TestParseEntryDate:
    """Tests for _parse_entry_date: extracting UTC datetime from entries."""

    def test_published_parsed(self):
        dt = datetime.datetime(2026, 2, 15, 10, 30, 0, tzinfo=UTC)
        entry = _make_entry(published_parsed=_dt_to_timetuple(dt))
        result = _parse_entry_date(entry)
        assert result is not None
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.tzinfo == UTC

    def test_updated_parsed_fallback(self):
        """When published_parsed is absent, updated_parsed is used."""
        dt = datetime.datetime(2026, 1, 20, 8, 0, 0, tzinfo=UTC)
        entry = _make_entry(updated_parsed=_dt_to_timetuple(dt))
        result = _parse_entry_date(entry)
        assert result is not None
        assert result.year == 2026
        assert result.month == 1

    def test_published_takes_priority(self):
        """published_parsed is preferred over updated_parsed."""
        dt_pub = datetime.datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
        dt_upd = datetime.datetime(2026, 3, 2, 12, 0, 0, tzinfo=UTC)
        entry = _make_entry(
            published_parsed=_dt_to_timetuple(dt_pub),
            updated_parsed=_dt_to_timetuple(dt_upd),
        )
        result = _parse_entry_date(entry)
        assert result.day == 1  # published, not updated

    def test_no_date_returns_none(self):
        """When neither date attribute exists, return None."""
        entry = _make_entry()
        result = _parse_entry_date(entry)
        assert result is None

    def test_invalid_date_tuple_returns_none(self):
        """A malformed date tuple should not crash — returns None."""
        entry = _make_entry()
        entry.published_parsed = ("not", "a", "date")
        result = _parse_entry_date(entry)
        assert result is None

    def test_none_date_value(self):
        """Explicitly None date attributes should return None."""
        entry = _make_entry()
        entry.published_parsed = None
        entry.updated_parsed = None
        result = _parse_entry_date(entry)
        assert result is None


# ===================================================================
# TestFetchSingleFeed
# ===================================================================

class TestFetchSingleFeed:
    """Tests for _fetch_single_feed with mocked requests + feedparser."""

    def _cutoff(self, hours_ago=24):
        return _utc_now() - datetime.timedelta(hours=hours_ago)

    def _make_lock_and_set(self):
        return set(), Lock()

    @patch("engine.fetcher.requests")
    def test_successful_fetch(self, mock_requests, mock_feedparser):
        """Successful fetch returns (url, articles, source_name) tuple."""
        now = _utc_now()
        entry = _make_entry(
            title="NASA Discovers Water",
            link="https://nasa.gov/article/1",
            description="Water found on Mars.",
            published_parsed=_dt_to_timetuple(now),
        )
        mock_response = MagicMock()
        mock_response.content = b"<rss>...</rss>"
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception

        mock_feedparser.parse.return_value = _make_feed(
            [entry], title="NASA Feed", bozo=False
        )

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://www.nasa.gov/rss",
            self._cutoff(),
            None,
            probs,
            lock,
        )

        assert result is not None
        url, articles, source_name = result
        assert url == "https://www.nasa.gov/rss"
        assert source_name == "NASA"
        assert len(articles) == 1
        assert articles[0]["title"] == "NASA Discovers Water"
        assert articles[0]["description"] == "Water found on Mars."
        assert articles[0]["url"] == "https://nasa.gov/article/1"

    @patch("engine.fetcher.requests")
    def test_network_error_returns_none(self, mock_requests, mock_feedparser):
        """A requests.RequestException causes None return."""
        mock_requests.RequestException = Exception
        mock_requests.get.side_effect = Exception("Connection refused")

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            None,
            probs,
            lock,
        )
        assert result is None
        assert "https://example.com/feed" in probs

    @patch("engine.fetcher.requests")
    def test_bozo_feed_returns_none(self, mock_requests, mock_feedparser):
        """A feed with bozo=True and a bozo_exception is skipped."""
        mock_response = MagicMock()
        mock_response.content = b"<bad xml"
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception

        mock_feedparser.parse.return_value = _make_feed(
            [], bozo=True, bozo_exception=Exception("Not well-formed")
        )

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://example.com/bad",
            self._cutoff(),
            None,
            probs,
            lock,
        )
        assert result is None
        assert "https://example.com/bad" in probs

    @patch("engine.fetcher.requests")
    def test_date_filtering_old_articles(self, mock_requests, mock_feedparser):
        """Articles older than cutoff_time are excluded."""
        old_date = _utc_now() - datetime.timedelta(hours=48)
        entry = _make_entry(
            title="Old News",
            link="https://example.com/old",
            published_parsed=_dt_to_timetuple(old_date),
        )

        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception

        mock_feedparser.parse.return_value = _make_feed([entry])

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(hours_ago=24),
            None,
            probs,
            lock,
        )
        assert result is not None
        _, articles, _ = result
        assert len(articles) == 0

    @patch("engine.fetcher.requests")
    def test_date_filtering_keeps_recent(self, mock_requests, mock_feedparser):
        """Articles within cutoff window are kept."""
        recent_date = _utc_now() - datetime.timedelta(hours=1)
        entry = _make_entry(
            title="Fresh News",
            link="https://example.com/new",
            published_parsed=_dt_to_timetuple(recent_date),
        )

        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception

        mock_feedparser.parse.return_value = _make_feed([entry])

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(hours_ago=24),
            None,
            probs,
            lock,
        )
        _, articles, _ = result
        assert len(articles) == 1
        assert articles[0]["title"] == "Fresh News"

    @patch("engine.fetcher.requests")
    def test_entry_without_title_skipped(self, mock_requests, mock_feedparser):
        """Entries with empty title are skipped."""
        entry = _make_entry(
            title="",
            link="https://example.com/notitle",
            published_parsed=_dt_to_timetuple(_utc_now()),
        )

        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception

        mock_feedparser.parse.return_value = _make_feed([entry])

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            None,
            probs,
            lock,
        )
        _, articles, _ = result
        assert len(articles) == 0

    @patch("engine.fetcher.requests")
    def test_entry_without_link_skipped(self, mock_requests, mock_feedparser):
        """Entries with empty link are skipped."""
        entry = _make_entry(
            title="Has Title",
            link="",
            published_parsed=_dt_to_timetuple(_utc_now()),
        )

        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception

        mock_feedparser.parse.return_value = _make_feed([entry])

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            None,
            probs,
            lock,
        )
        _, articles, _ = result
        assert len(articles) == 0

    @patch("engine.fetcher.requests")
    def test_article_dict_keys(self, mock_requests, mock_feedparser):
        """Returned article dicts contain all expected keys."""
        now = _utc_now()
        entry = _make_entry(
            title="Key Check",
            link="https://example.com/keys",
            description="Testing keys",
            author="John Doe",
            published_parsed=_dt_to_timetuple(now),
        )

        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception

        mock_feedparser.parse.return_value = _make_feed([entry])

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            None,
            probs,
            lock,
        )
        _, articles, _ = result
        assert len(articles) == 1
        article = articles[0]
        expected_keys = {
            "title", "description", "url", "source_name",
            "published_date", "relevance_score", "author",
        }
        assert set(article.keys()) == expected_keys
        assert article["author"] == "John Doe"
        assert article["relevance_score"] == 0.0

    @patch("engine.fetcher.requests")
    def test_no_date_uses_current_time(self, mock_requests, mock_feedparser):
        """Entry with no date gets assigned current time as published_date."""
        entry = _make_entry(
            title="No Date Article",
            link="https://example.com/nodate",
        )

        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception

        mock_feedparser.parse.return_value = _make_feed([entry])

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            None,
            probs,
            lock,
        )
        _, articles, _ = result
        assert len(articles) == 1
        # Should be a valid ISO timestamp
        pd = articles[0]["published_date"]
        parsed = datetime.datetime.fromisoformat(pd)
        assert parsed.tzinfo is not None

    @patch("engine.fetcher.requests")
    def test_http_status_error(self, mock_requests, mock_feedparser):
        """HTTP 4xx/5xx causes raise_for_status to raise, returning None."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://example.com/404",
            self._cutoff(),
            None,
            probs,
            lock,
        )
        assert result is None

    @patch("engine.fetcher.requests")
    def test_summary_fallback_for_description(self, mock_requests, mock_feedparser):
        """When description is empty, summary is used as fallback."""
        now = _utc_now()
        entry = _make_entry(
            title="Summary Fallback",
            link="https://example.com/summary",
            description="",
            summary="Fallback summary text",
            published_parsed=_dt_to_timetuple(now),
        )

        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception

        mock_feedparser.parse.return_value = _make_feed([entry])

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            None,
            probs,
            lock,
        )
        _, articles, _ = result
        assert articles[0]["description"] == "Fallback summary text"

    @patch("engine.fetcher.requests")
    def test_problematic_feed_not_added_twice(self, mock_requests, mock_feedparser):
        """A feed URL already in problematic_feeds is not added again."""
        mock_requests.RequestException = Exception
        mock_requests.get.side_effect = Exception("Timeout")

        probs = {"https://example.com/feed"}
        lock = Lock()
        _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            None,
            probs,
            lock,
        )
        # Should still be exactly one entry (not duplicated)
        assert len(probs) == 1

    @patch("engine.fetcher.requests")
    def test_max_articles_caps_high_volume_feed(self, mock_requests, mock_feedparser):
        """Per-feed cap limits articles from high-volume feeds like arXiv."""
        now = _utc_now()
        entries = [
            _make_entry(
                title=f"Paper {i}: Novel Approach to AI Problem {i}",
                link=f"https://arxiv.org/abs/2602.{i:05d}",
                description=f"We present a novel method for problem {i}.",
                published_parsed=_dt_to_timetuple(now),
            )
            for i in range(100)
        ]

        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception

        mock_feedparser.parse.return_value = _make_feed(entries, title="arXiv AI")

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://arxiv.org/rss/cs.AI",
            self._cutoff(),
            None,
            probs,
            lock,
            max_articles=10,
        )
        assert result is not None
        _, articles, _ = result
        assert len(articles) == 10

    @patch("engine.fetcher.requests")
    def test_max_articles_zero_disables_cap(self, mock_requests, mock_feedparser):
        """max_articles=0 disables the per-feed cap."""
        now = _utc_now()
        entries = [
            _make_entry(
                title=f"Article {i}",
                link=f"https://example.com/{i}",
                published_parsed=_dt_to_timetuple(now),
            )
            for i in range(60)
        ]

        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception

        mock_feedparser.parse.return_value = _make_feed(entries)

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            None,
            probs,
            lock,
            max_articles=0,
        )
        _, articles, _ = result
        assert len(articles) == 60

    @patch("engine.fetcher.requests")
    def test_multiple_entries_mixed_dates(self, mock_requests, mock_feedparser):
        """Mix of old and recent entries: only recent ones are returned."""
        now = _utc_now()
        old = now - datetime.timedelta(hours=48)
        recent = now - datetime.timedelta(hours=2)

        entries = [
            _make_entry(
                title="Old Article",
                link="https://example.com/old",
                published_parsed=_dt_to_timetuple(old),
            ),
            _make_entry(
                title="Recent Article",
                link="https://example.com/recent",
                published_parsed=_dt_to_timetuple(recent),
            ),
        ]

        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception

        mock_feedparser.parse.return_value = _make_feed(entries)

        probs, lock = self._make_lock_and_set()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(hours_ago=24),
            None,
            probs,
            lock,
        )
        _, articles, _ = result
        assert len(articles) == 1
        assert articles[0]["title"] == "Recent Article"


# ===================================================================
# TestKeywordFiltering
# ===================================================================

class TestKeywordFiltering:
    """Keyword matching edge cases in _fetch_single_feed."""

    def _cutoff(self):
        return _utc_now() - datetime.timedelta(hours=24)

    def _setup_feed(self, mock_requests, mock_feedparser, entries):
        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_requests.get.return_value = mock_response
        mock_requests.RequestException = Exception
        mock_feedparser.parse.return_value = _make_feed(entries)

    @patch("engine.fetcher.requests")
    def test_keyword_match_in_title(self, mock_requests, mock_feedparser):
        """Article matches when keyword appears in title."""
        entry = _make_entry(
            title="Tesla Stock Surges",
            link="https://example.com/1",
            description="No match here.",
            published_parsed=_dt_to_timetuple(_utc_now()),
        )
        self._setup_feed(mock_requests, mock_feedparser, [entry])

        probs, lock = set(), Lock()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            ["tesla"],
            probs,
            lock,
        )
        _, articles, _ = result
        assert len(articles) == 1

    @patch("engine.fetcher.requests")
    def test_keyword_match_in_description(self, mock_requests, mock_feedparser):
        """Article matches when keyword appears in description."""
        entry = _make_entry(
            title="Stock Market Update",
            link="https://example.com/1",
            description="Tesla reports record deliveries.",
            published_parsed=_dt_to_timetuple(_utc_now()),
        )
        self._setup_feed(mock_requests, mock_feedparser, [entry])

        probs, lock = set(), Lock()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            ["tesla"],
            probs,
            lock,
        )
        _, articles, _ = result
        assert len(articles) == 1

    @patch("engine.fetcher.requests")
    def test_keyword_case_insensitive(self, mock_requests, mock_feedparser):
        """Keyword matching is case-insensitive."""
        entry = _make_entry(
            title="SPACEX Launches Starship",
            link="https://example.com/1",
            description="",
            published_parsed=_dt_to_timetuple(_utc_now()),
        )
        self._setup_feed(mock_requests, mock_feedparser, [entry])

        probs, lock = set(), Lock()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            ["spacex"],
            probs,
            lock,
        )
        _, articles, _ = result
        assert len(articles) == 1

    @patch("engine.fetcher.requests")
    def test_no_keyword_match_excluded(self, mock_requests, mock_feedparser):
        """Article without any keyword match is excluded."""
        entry = _make_entry(
            title="Weather Update",
            link="https://example.com/1",
            description="Sunny skies expected.",
            published_parsed=_dt_to_timetuple(_utc_now()),
        )
        self._setup_feed(mock_requests, mock_feedparser, [entry])

        probs, lock = set(), Lock()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            ["tesla", "spacex"],
            probs,
            lock,
        )
        _, articles, _ = result
        assert len(articles) == 0

    @patch("engine.fetcher.requests")
    def test_any_keyword_matches(self, mock_requests, mock_feedparser):
        """A match on ANY keyword is sufficient for inclusion."""
        entry = _make_entry(
            title="SpaceX Dragon Returns",
            link="https://example.com/1",
            description="Crew returned safely.",
            published_parsed=_dt_to_timetuple(_utc_now()),
        )
        self._setup_feed(mock_requests, mock_feedparser, [entry])

        probs, lock = set(), Lock()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            ["tesla", "spacex", "rocket"],
            probs,
            lock,
        )
        _, articles, _ = result
        assert len(articles) == 1

    @patch("engine.fetcher.requests")
    def test_no_keywords_returns_all(self, mock_requests, mock_feedparser):
        """When keywords is None, all articles (meeting other criteria) pass."""
        entries = [
            _make_entry(
                title=f"Article {i}",
                link=f"https://example.com/{i}",
                published_parsed=_dt_to_timetuple(_utc_now()),
            )
            for i in range(3)
        ]
        self._setup_feed(mock_requests, mock_feedparser, entries)

        probs, lock = set(), Lock()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            None,
            probs,
            lock,
        )
        _, articles, _ = result
        assert len(articles) == 3

    @patch("engine.fetcher.requests")
    def test_keyword_partial_word_match(self, mock_requests, mock_feedparser):
        """Keywords match as substrings (e.g., 'tesla' in 'teslarati')."""
        entry = _make_entry(
            title="Teslarati Reports New Model",
            link="https://example.com/1",
            description="",
            published_parsed=_dt_to_timetuple(_utc_now()),
        )
        self._setup_feed(mock_requests, mock_feedparser, [entry])

        probs, lock = set(), Lock()
        result = _fetch_single_feed(
            "https://example.com/feed",
            self._cutoff(),
            ["tesla"],
            probs,
            lock,
        )
        _, articles, _ = result
        assert len(articles) == 1


# ===================================================================
# TestFetchRssArticles
# ===================================================================

class TestFetchRssArticles:
    """Tests for the public fetch_rss_articles orchestration function."""

    def _make_article(self, title, published_date, description=None, url=None):
        if description is None:
            description = f"Full unique description for article titled {title}"
        return {
            "title": title,
            "description": description,
            "url": url or f"https://example.com/{title.replace(' ', '-').lower()}",
            "source_name": "Test Source",
            "published_date": published_date,
            "relevance_score": 0.0,
            "author": "",
        }

    @patch("engine.fetcher._fetch_single_feed")
    def test_aggregates_multiple_feeds(self, mock_fetch):
        """Articles from multiple feeds are aggregated."""
        t1 = _utc_now().isoformat()
        t2 = (_utc_now() - datetime.timedelta(hours=1)).isoformat()

        mock_fetch.side_effect = [
            (
                "url1",
                [self._make_article("SpaceX launches Falcon Heavy rocket to orbit", t1)],
                "Source A",
            ),
            (
                "url2",
                [self._make_article("Federal Reserve raises interest rates by quarter point", t2)],
                "Source B",
            ),
        ]

        feeds = [
            {"url": "https://feed1.com/rss", "label": "Feed 1"},
            {"url": "https://feed2.com/rss", "label": "Feed 2"},
        ]
        result = fetch_rss_articles(feeds)
        assert len(result) == 2

    @patch("engine.fetcher._fetch_single_feed")
    def test_sorts_newest_first(self, mock_fetch):
        """Results are sorted with the newest article first."""
        t_old = "2026-02-15T08:00:00+00:00"
        t_new = "2026-02-16T12:00:00+00:00"
        t_mid = "2026-02-15T18:00:00+00:00"

        mock_fetch.side_effect = [
            ("url1", [
                self._make_article("Ancient ruins discovered in Peru by archaeologists", t_old),
                self._make_article("NASA successfully lands rover on Jupiter moon Europa", t_new),
                self._make_article("Olympic committee announces host city for 2036 games", t_mid),
            ], "Source"),
        ]

        feeds = [{"url": "https://feed.com/rss", "label": "Feed"}]
        result = fetch_rss_articles(feeds)
        assert len(result) == 3
        titles = [a["title"] for a in result]
        assert titles[0] == "NASA successfully lands rover on Jupiter moon Europa"
        assert titles[1] == "Olympic committee announces host city for 2036 games"
        assert titles[2] == "Ancient ruins discovered in Peru by archaeologists"

    @patch("engine.fetcher._fetch_single_feed")
    def test_empty_feeds_return_empty(self, mock_fetch):
        """When all feeds return None, result is empty list."""
        mock_fetch.return_value = None

        feeds = [
            {"url": "https://bad1.com/rss", "label": "Bad 1"},
            {"url": "https://bad2.com/rss", "label": "Bad 2"},
        ]
        result = fetch_rss_articles(feeds)
        assert result == []

    @patch("engine.fetcher._fetch_single_feed")
    def test_no_feeds_returns_empty(self, mock_fetch):
        """Passing an empty feed list returns an empty result."""
        result = fetch_rss_articles([])
        assert result == []
        mock_fetch.assert_not_called()

    @patch("engine.fetcher._fetch_single_feed")
    def test_deduplication_removes_similar(self, mock_fetch):
        """Highly similar articles are deduplicated."""
        t = _utc_now().isoformat()
        mock_fetch.side_effect = [
            ("url1", [
                self._make_article(
                    "Tesla Stock Surges on Strong Q4 Earnings",
                    t,
                    description="Tesla stock rose sharply after Q4 earnings beat expectations",
                ),
            ], "Source A"),
            ("url2", [
                self._make_article(
                    "Tesla Stock Surges on Strong Q4 Earnings Report",
                    t,
                    description="Tesla stock rose sharply after Q4 earnings report beat expectations",
                ),
            ], "Source B"),
        ]

        feeds = [
            {"url": "https://feed1.com/rss", "label": "Feed 1"},
            {"url": "https://feed2.com/rss", "label": "Feed 2"},
        ]
        result = fetch_rss_articles(feeds, similarity_threshold=0.85)
        # These are very similar and should be deduplicated to 1
        assert len(result) == 1

    @patch("engine.fetcher._fetch_single_feed")
    def test_deduplication_keeps_different(self, mock_fetch):
        """Clearly different articles are not removed by deduplication."""
        t = _utc_now().isoformat()
        mock_fetch.side_effect = [
            ("url1", [
                self._make_article("Tesla Stock Surges After Record Deliveries", t),
                self._make_article("NASA Launches New Mars Rover Mission", t),
            ], "Source"),
        ]

        feeds = [{"url": "https://feed.com/rss", "label": "Feed"}]
        result = fetch_rss_articles(feeds, similarity_threshold=0.85)
        assert len(result) == 2

    @patch("engine.fetcher._fetch_single_feed")
    def test_keyword_passthrough(self, mock_fetch):
        """Keywords are passed to _fetch_single_feed."""
        mock_fetch.return_value = None

        feeds = [{"url": "https://feed.com/rss", "label": "Feed"}]
        fetch_rss_articles(feeds, keywords=["tesla", "spacex"])

        # Verify keywords were passed through
        call_args = mock_fetch.call_args
        assert call_args is not None
        # keywords is the 3rd positional argument (index 2)
        assert call_args[0][2] == ["tesla", "spacex"]

    @patch("engine.fetcher._fetch_single_feed")
    def test_cutoff_hours_passthrough(self, mock_fetch):
        """cutoff_hours is used to compute cutoff_time passed to _fetch_single_feed."""
        mock_fetch.return_value = None

        feeds = [{"url": "https://feed.com/rss", "label": "Feed"}]
        fetch_rss_articles(feeds, cutoff_hours=48)

        call_args = mock_fetch.call_args
        cutoff_time = call_args[0][1]
        expected_approx = _utc_now() - datetime.timedelta(hours=48)
        # Allow 5 seconds tolerance
        diff = abs((cutoff_time - expected_approx).total_seconds())
        assert diff < 5

    @patch("engine.fetcher._fetch_single_feed")
    def test_feed_returning_none_is_skipped(self, mock_fetch):
        """Feeds that return None are silently skipped."""
        t = _utc_now().isoformat()
        mock_fetch.side_effect = [
            None,
            ("url2", [self._make_article("Good Article", t)], "Source"),
            None,
        ]

        feeds = [
            {"url": "https://bad.com/rss", "label": "Bad"},
            {"url": "https://good.com/rss", "label": "Good"},
            {"url": "https://bad2.com/rss", "label": "Bad2"},
        ]
        result = fetch_rss_articles(feeds)
        assert len(result) == 1
        assert result[0]["title"] == "Good Article"

    @patch("engine.fetcher._fetch_single_feed")
    def test_max_workers_parameter(self, mock_fetch):
        """max_workers is respected (function accepts keyword-only arg)."""
        mock_fetch.return_value = None
        feeds = [{"url": "https://feed.com/rss", "label": "Feed"}]
        # Should not raise
        fetch_rss_articles(feeds, max_workers=2)

    @patch("engine.fetcher._fetch_single_feed")
    def test_similarity_threshold_parameter(self, mock_fetch):
        """similarity_threshold is passed through to remove_similar_items."""
        t = _utc_now().isoformat()
        mock_fetch.return_value = (
            "url",
            [self._make_article("Unique article about quantum computing breakthroughs", t)],
            "Source",
        )

        feeds = [{"url": "https://feed.com/rss", "label": "Feed"}]
        # Should not raise with custom threshold
        result = fetch_rss_articles(feeds, similarity_threshold=0.50)
        assert len(result) == 1


# ===================================================================
# TestDeduplication
# ===================================================================

class TestDeduplication:
    """Focused tests on deduplication behavior through fetch_rss_articles."""

    def _make_article(self, title, description="", published_date=None):
        if published_date is None:
            published_date = _utc_now().isoformat()
        if not description:
            description = f"Unique description content for article: {title}"
        return {
            "title": title,
            "description": description,
            "url": f"https://example.com/{abs(hash(title))}",
            "source_name": "Test",
            "published_date": published_date,
            "relevance_score": 0.0,
            "author": "",
        }

    @patch("engine.fetcher._fetch_single_feed")
    def test_exact_duplicate_removed(self, mock_fetch):
        """Identical titles and descriptions are deduplicated."""
        t = _utc_now().isoformat()
        art1 = self._make_article("Exact Same Title", published_date=t)
        art2 = {**art1, "url": "https://other-site.com/same-article"}
        mock_fetch.side_effect = [
            ("url1", [art1], "A"),
            ("url2", [art2], "B"),
        ]

        feeds = [
            {"url": "https://a.com/rss", "label": "A"},
            {"url": "https://b.com/rss", "label": "B"},
        ]
        result = fetch_rss_articles(feeds, similarity_threshold=0.85)
        assert len(result) == 1

    @patch("engine.fetcher._fetch_single_feed")
    def test_low_threshold_removes_more(self, mock_fetch):
        """A lower similarity threshold removes more articles."""
        t = _utc_now().isoformat()
        articles = [
            self._make_article(
                "Tesla earnings report shows growth",
                description="Tesla reported strong earnings and revenue growth in Q4",
                published_date=t,
            ),
            self._make_article(
                "Tesla earnings show solid growth",
                description="Tesla showed solid earnings and revenue growth in Q4",
                published_date=t,
            ),
            self._make_article(
                "NASA launches new satellite mission to study dark matter in deep space",
                description="NASA launched a groundbreaking satellite mission",
                published_date=t,
            ),
        ]
        mock_fetch.return_value = ("url", list(articles), "Source")

        feeds = [{"url": "https://feed.com/rss", "label": "Feed"}]

        # High threshold: more articles survive
        result_high = fetch_rss_articles(feeds, similarity_threshold=0.99)

        mock_fetch.return_value = ("url", list(articles), "Source")
        # Low threshold: fewer articles survive
        result_low = fetch_rss_articles(feeds, similarity_threshold=0.50)

        assert len(result_low) <= len(result_high)

    @patch("engine.fetcher._fetch_single_feed")
    def test_completely_different_articles_all_kept(self, mock_fetch):
        """Articles with no similarity are all kept."""
        t = _utc_now().isoformat()
        articles = [
            self._make_article(
                "Tesla Stock Price Reaches All-Time High",
                published_date=t,
            ),
            self._make_article(
                "NASA Mars Rover Discovers Ancient Microbial Fossils",
                published_date=t,
            ),
            self._make_article(
                "Federal Reserve Announces Interest Rate Decision",
                published_date=t,
            ),
            self._make_article(
                "Olympic Games Medal Count Shows China in Lead",
                published_date=t,
            ),
        ]
        mock_fetch.return_value = ("url", articles, "Source")

        feeds = [{"url": "https://feed.com/rss", "label": "Feed"}]
        result = fetch_rss_articles(feeds, similarity_threshold=0.85)
        assert len(result) == 4

    @patch("engine.fetcher._fetch_single_feed")
    def test_max_articles_per_feed_passthrough(self, mock_fetch):
        """max_articles_per_feed is passed to _fetch_single_feed."""
        mock_fetch.return_value = None

        feeds = [{"url": "https://feed.com/rss", "label": "Feed"}]
        fetch_rss_articles(feeds, max_articles_per_feed=10)

        call_args = mock_fetch.call_args
        # max_articles is the 6th positional argument (index 5)
        assert call_args[0][5] == 10

    @patch("engine.fetcher._fetch_single_feed")
    def test_max_articles_per_feed_default(self, mock_fetch):
        """Default max_articles_per_feed (50) is passed to _fetch_single_feed."""
        mock_fetch.return_value = None

        feeds = [{"url": "https://feed.com/rss", "label": "Feed"}]
        fetch_rss_articles(feeds)

        call_args = mock_fetch.call_args
        assert call_args[0][5] == 50

    @patch("engine.fetcher._fetch_single_feed")
    def test_three_duplicates_reduced_to_one(self, mock_fetch):
        """Three near-identical articles from different sources collapse to one."""
        t = _utc_now().isoformat()
        desc = "SpaceX successfully launched Starship on its maiden orbital flight"
        mock_fetch.side_effect = [
            ("u1", [{
                "title": "SpaceX Starship completes first orbital flight",
                "description": desc,
                "url": "https://a.com/1", "source_name": "A",
                "published_date": t, "relevance_score": 0.0, "author": "",
            }], "A"),
            ("u2", [{
                "title": "SpaceX Starship completes first orbital flight successfully",
                "description": desc,
                "url": "https://b.com/1", "source_name": "B",
                "published_date": t, "relevance_score": 0.0, "author": "",
            }], "B"),
            ("u3", [{
                "title": "SpaceX Starship completes its first orbital flight",
                "description": desc,
                "url": "https://c.com/1", "source_name": "C",
                "published_date": t, "relevance_score": 0.0, "author": "",
            }], "C"),
        ]

        feeds = [
            {"url": "https://a.com/rss", "label": "A"},
            {"url": "https://b.com/rss", "label": "B"},
            {"url": "https://c.com/rss", "label": "C"},
        ]
        result = fetch_rss_articles(feeds, similarity_threshold=0.85)
        assert len(result) == 1
