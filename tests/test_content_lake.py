"""Tests for engine/content_lake.py — SQLite content storage with FTS5."""

import json

import pytest

from engine.content_lake import (
    EpisodeRecord,
    extract_entities_and_topics,
    get_all_search_docs,
    get_lake_stats,
    init_db,
    query_all_shows_range,
    query_by_entity,
    query_show_range,
    search_content,
    store_episode,
)


def _make_record(**overrides) -> EpisodeRecord:
    """Create a test EpisodeRecord with sensible defaults."""
    defaults = dict(
        show_slug="tesla",
        episode_num=1,
        date="2026-03-15",
        title="Tesla Episode 1",
        hook="Big news about Tesla today",
        digest_md="# Tesla Daily\n\nSome **Tesla** digest content.",
        podcast_script="Welcome to Tesla Shorts Time...",
        summary="A summary of today's Tesla news.",
        headlines=["Tesla stock soars", "FSD update released"],
        source_urls=["https://example.com/1", "https://example.com/2"],
        entities=["Tesla", "Elon Musk"],
        topics=["autonomous-vehicles", "finance"],
        word_count=500,
        show_name="Tesla Shorts Time",
        language="en",
    )
    defaults.update(overrides)
    return EpisodeRecord(**defaults)


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

class TestInitDb:
    def test_creates_tables(self, tmp_path):
        db = tmp_path / "test.db"
        init_db(db)
        assert db.exists()

        import sqlite3
        conn = sqlite3.connect(str(db))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        assert "episodes" in tables
        assert "episodes_fts" in tables

    def test_idempotent(self, tmp_path):
        db = tmp_path / "test.db"
        init_db(db)
        init_db(db)  # should not raise

    def test_creates_parent_directories(self, tmp_path):
        db = tmp_path / "nested" / "dirs" / "test.db"
        init_db(db)
        assert db.exists()


# ---------------------------------------------------------------------------
# Store and query
# ---------------------------------------------------------------------------

class TestStoreAndQuery:
    def test_store_and_query_roundtrip(self, tmp_path):
        db = tmp_path / "test.db"
        record = _make_record()
        store_episode(record, db)

        results = query_show_range("tesla", "2026-01-01", "2026-12-31", db)
        assert len(results) == 1
        r = results[0]
        assert r["show_slug"] == "tesla"
        assert r["episode_num"] == 1
        assert r["title"] == "Tesla Episode 1"
        assert r["headlines"] == ["Tesla stock soars", "FSD update released"]
        assert r["entities"] == ["Tesla", "Elon Musk"]
        assert r["topics"] == ["autonomous-vehicles", "finance"]
        assert r["word_count"] == 500
        assert r["language"] == "en"

    def test_upsert_on_duplicate(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(_make_record(title="Original"), db)
        store_episode(_make_record(title="Updated"), db)

        results = query_show_range("tesla", "2026-01-01", "2026-12-31", db)
        assert len(results) == 1
        assert results[0]["title"] == "Updated"

    def test_multiple_episodes(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(_make_record(episode_num=1, date="2026-03-01"), db)
        store_episode(_make_record(episode_num=2, date="2026-03-15"), db)
        store_episode(_make_record(episode_num=3, date="2026-04-01"), db)

        results = query_show_range("tesla", "2026-01-01", "2026-12-31", db)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# Date range filtering
# ---------------------------------------------------------------------------

class TestDateRangeFiltering:
    def test_boundary_inclusive(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(_make_record(episode_num=1, date="2026-01-01"), db)
        store_episode(_make_record(episode_num=2, date="2026-01-15"), db)
        store_episode(_make_record(episode_num=3, date="2026-02-01"), db)

        results = query_show_range("tesla", "2026-01-01", "2026-01-31", db)
        assert len(results) == 2
        assert results[0]["date"] == "2026-01-01"
        assert results[1]["date"] == "2026-01-15"

    def test_empty_range(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(_make_record(date="2026-03-15"), db)

        results = query_show_range("tesla", "2026-06-01", "2026-06-30", db)
        assert results == []


# ---------------------------------------------------------------------------
# Cross-show queries
# ---------------------------------------------------------------------------

class TestCrossShowQueries:
    def test_query_all_shows_range(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(_make_record(show_slug="tesla", episode_num=1, date="2026-03-15"), db)
        store_episode(
            _make_record(show_slug="omni_view", episode_num=1, date="2026-03-15",
                         show_name="Omni View"),
            db,
        )

        results = query_all_shows_range("2026-03-01", "2026-03-31", db)
        assert len(results) == 2
        slugs = {r["show_slug"] for r in results}
        assert slugs == {"tesla", "omni_view"}

    def test_filters_by_show_slug(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(_make_record(show_slug="tesla", episode_num=1), db)
        store_episode(
            _make_record(show_slug="omni_view", episode_num=1, show_name="Omni View"),
            db,
        )

        results = query_show_range("tesla", "2026-01-01", "2026-12-31", db)
        assert len(results) == 1
        assert results[0]["show_slug"] == "tesla"


# ---------------------------------------------------------------------------
# Entity queries
# ---------------------------------------------------------------------------

class TestEntityQueries:
    def test_query_by_entity_match(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(_make_record(entities=["Tesla", "SpaceX"]), db)

        results = query_by_entity("Tesla", db_path=db)
        assert len(results) == 1
        assert "Tesla" in results[0]["entities"]

    def test_query_by_entity_no_match(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(_make_record(entities=["Tesla", "SpaceX"]), db)

        results = query_by_entity("Nvidia", db_path=db)
        assert results == []


# ---------------------------------------------------------------------------
# Full-text search
# ---------------------------------------------------------------------------

class TestFullTextSearch:
    def test_search_content_match(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(
            _make_record(digest_md="Revolutionary battery technology breakthrough"),
            db,
        )

        results = search_content("battery technology", db_path=db)
        assert len(results) == 1

    def test_search_content_no_match(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(_make_record(), db)

        results = search_content("xyznonexistent", db_path=db)
        assert results == []


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestGetLakeStats:
    def test_stats_with_data(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(_make_record(episode_num=1, date="2026-03-01", word_count=300), db)
        store_episode(_make_record(episode_num=2, date="2026-03-15", word_count=700), db)

        stats = get_lake_stats(db)
        assert stats["total_episodes"] == 2
        assert "tesla" in stats["shows"]
        assert stats["date_range"]["earliest"] == "2026-03-01"
        assert stats["date_range"]["latest"] == "2026-03-15"
        assert stats["total_words"] == 1000
        assert stats["per_show"]["tesla"]["count"] == 2

    def test_stats_empty_db(self, tmp_path):
        db = tmp_path / "test.db"
        init_db(db)

        stats = get_lake_stats(db)
        assert stats["total_episodes"] == 0
        assert stats["shows"] == []
        assert stats["total_words"] == 0


# ---------------------------------------------------------------------------
# JSON field edge cases
# ---------------------------------------------------------------------------

class TestJsonFields:
    def test_empty_json_arrays(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(
            _make_record(headlines=[], entities=[], topics=[], source_urls=[]),
            db,
        )

        results = query_show_range("tesla", "2026-01-01", "2026-12-31", db)
        assert results[0]["headlines"] == []
        assert results[0]["entities"] == []

    def test_malformed_json_handled(self, tmp_path):
        """Manually insert malformed JSON to verify _rows_to_dicts handles it."""
        db = tmp_path / "test.db"
        init_db(db)

        import sqlite3
        conn = sqlite3.connect(str(db))
        conn.execute("""
            INSERT INTO episodes (show_slug, episode_num, date, title, headlines)
            VALUES ('tesla', 99, '2026-01-01', 'Bad JSON', 'not valid json{{{')
        """)
        conn.commit()
        conn.close()

        results = query_show_range("tesla", "2026-01-01", "2026-12-31", db)
        assert len(results) == 1
        assert results[0]["headlines"] == []  # graceful fallback


# ---------------------------------------------------------------------------
# Entity & topic extraction
# ---------------------------------------------------------------------------

class TestExtractEntitiesAndTopics:
    def test_known_entities(self):
        text = "Today Tesla announced a partnership with Nvidia for FSD chips."
        result = extract_entities_and_topics(text, "tesla")
        assert "Tesla" in result["entities"]
        assert "Nvidia" in result["entities"]

    def test_topic_patterns(self):
        text = "The new climate policy aims to reduce carbon emissions."
        result = extract_entities_and_topics(text, "env_intel")
        assert "climate" in result["topics"]

    def test_bold_entities(self):
        text = "**OpenAI** released GPT-5 and **Anthropic** launched Claude 4."
        result = extract_entities_and_topics(text, "models_agents")
        assert "OpenAI" in result["entities"]
        assert "Anthropic" in result["entities"]


# ---------------------------------------------------------------------------
# Item 2 search enhancements (server-built index + filtered FTS)
# ---------------------------------------------------------------------------

class TestSearchEnhancements:
    def test_search_content_supports_show_filter(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(_make_record(show_slug="tesla", episode_num=1, digest_md="Tesla robotaxi news"), db)
        store_episode(
            _make_record(show_slug="omni_view", episode_num=1, show_name="Omni View",
                         digest_md="World news about markets and Tesla"),
            db,
        )

        all_results = search_content("Tesla", db_path=db)
        assert len(all_results) == 2

        tesla_only = search_content("Tesla", show_slug="tesla", db_path=db)
        assert len(tesla_only) == 1
        assert tesla_only[0]["show_slug"] == "tesla"

    def test_get_all_search_docs_compact(self, tmp_path):
        db = tmp_path / "test.db"
        store_episode(_make_record(episode_num=42, title="Big Reveal", entities=["Cybercab"]), db)

        docs = get_all_search_docs(db)
        assert len(docs) == 1
        d = docs[0]
        assert d["episode_num"] == 42
        assert d["title"] == "Big Reveal"
        assert "Cybercab" in d["entities"]
        # Must not include heavy text fields in the search export
        assert "digest_md" not in d
        assert "podcast_script" not in d
