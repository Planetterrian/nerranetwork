"""Content Lake — Persistent structured storage for all Nerra Network episode content.

Stores digests, scripts, metadata, and derived data for downstream content
products (weekly newsletters, monthly reports, cross-show briefings).

Uses SQLite for reliable concurrent access and efficient querying.  The
database lives at ``data/content_lake.db`` by default.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "content_lake.db"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EpisodeRecord:
    show_slug: str
    episode_num: int
    date: str  # ISO format YYYY-MM-DD
    title: str
    hook: str
    digest_md: str  # Full markdown digest
    podcast_script: str  # TTS-ready script
    summary: str  # Short description for RSS/web
    headlines: List[str]
    source_urls: List[str]
    entities: List[str]  # Companies, people, products mentioned
    topics: List[str]  # Topic tags
    word_count: int
    show_name: str  # Human-readable show name
    language: str  # "en" or "ru"


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

def init_db(db_path: Path = DB_PATH) -> None:
    """Create the content lake database and tables if they don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            show_slug TEXT NOT NULL,
            episode_num INTEGER NOT NULL,
            date TEXT NOT NULL,
            title TEXT,
            hook TEXT,
            digest_md TEXT,
            podcast_script TEXT,
            summary TEXT,
            headlines TEXT,  -- JSON array
            source_urls TEXT,  -- JSON array
            entities TEXT,  -- JSON array
            topics TEXT,  -- JSON array
            word_count INTEGER,
            show_name TEXT,
            language TEXT DEFAULT 'en',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(show_slug, episode_num)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_episodes_show_date
        ON episodes(show_slug, date)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_episodes_date
        ON episodes(date)
    """)
    # Full-text search index (standalone — content-sync has SQLite 3.45 bugs)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts
        USING fts5(title, hook, digest_md, summary, headlines, entities, topics)
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_episode(record: EpisodeRecord, db_path: Path = DB_PATH) -> None:
    """Store an episode record in the content lake.

    Upserts on ``(show_slug, episode_num)`` so re-runs are safe.
    """
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            INSERT INTO episodes (show_slug, episode_num, date, title, hook,
                                  digest_md, podcast_script, summary, headlines,
                                  source_urls, entities, topics, word_count,
                                  show_name, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(show_slug, episode_num) DO UPDATE SET
                date=excluded.date, title=excluded.title, hook=excluded.hook,
                digest_md=excluded.digest_md, podcast_script=excluded.podcast_script,
                summary=excluded.summary, headlines=excluded.headlines,
                source_urls=excluded.source_urls, entities=excluded.entities,
                topics=excluded.topics, word_count=excluded.word_count,
                show_name=excluded.show_name, language=excluded.language
        """, (
            record.show_slug, record.episode_num, record.date,
            record.title, record.hook, record.digest_md, record.podcast_script,
            record.summary,
            json.dumps(record.headlines), json.dumps(record.source_urls),
            json.dumps(record.entities), json.dumps(record.topics),
            record.word_count, record.show_name, record.language,
        ))
        # Get the actual rowid (lastrowid is 0 on upsert)
        rowid = conn.execute(
            "SELECT id FROM episodes WHERE show_slug = ? AND episode_num = ?",
            (record.show_slug, record.episode_num),
        ).fetchone()[0]
        # Update standalone FTS index
        conn.execute("DELETE FROM episodes_fts WHERE rowid = ?", (rowid,))
        conn.execute("""
            INSERT INTO episodes_fts(rowid, title, hook, digest_md, summary,
                                     headlines, entities, topics)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rowid, record.title, record.hook, record.digest_md, record.summary,
            json.dumps(record.headlines), json.dumps(record.entities),
            json.dumps(record.topics),
        ))
        conn.commit()
        logger.info("[ContentLake] Stored %s ep%d (%s)",
                    record.show_slug, record.episode_num, record.date)
    except Exception as e:
        logger.error("[ContentLake] Failed to store episode: %s", e)
        conn.rollback()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def _rows_to_dicts(rows: list) -> List[Dict[str, Any]]:
    """Convert sqlite3.Row objects to dicts, deserialising JSON fields."""
    results = []
    for row in rows:
        d = dict(row)
        for field in ("headlines", "source_urls", "entities", "topics"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
            else:
                d[field] = []
        results.append(d)
    return results


def query_show_range(
    show_slug: str,
    start_date: str,
    end_date: str,
    db_path: Path = DB_PATH,
) -> List[Dict[str, Any]]:
    """Query all episodes for a show within a date range."""
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM episodes
        WHERE show_slug = ? AND date >= ? AND date <= ?
        ORDER BY date ASC
    """, (show_slug, start_date, end_date)).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def query_all_shows_range(
    start_date: str,
    end_date: str,
    db_path: Path = DB_PATH,
) -> List[Dict[str, Any]]:
    """Query all episodes across all shows within a date range."""
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM episodes
        WHERE date >= ? AND date <= ?
        ORDER BY date ASC, show_slug ASC
    """, (start_date, end_date)).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def query_by_entity(
    entity: str,
    limit: int = 50,
    db_path: Path = DB_PATH,
) -> List[Dict[str, Any]]:
    """Find all episodes mentioning a specific entity."""
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM episodes
        WHERE entities LIKE ?
        ORDER BY date DESC
        LIMIT ?
    """, (f'%"{entity}"%', limit)).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def search_content(
    query: str,
    limit: int = 20,
    show_slug: Optional[str] = None,
    db_path: Path = DB_PATH,
) -> List[Dict[str, Any]]:
    """Full-text search across episode content using FTS5.

    Supports optional show_slug filter. Results are FTS-ranked (bm25).
    Safe to call after compaction (FTS retains historical text).
    """
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    if show_slug:
        rows = conn.execute("""
            SELECT e.* FROM episodes_fts fts
            JOIN episodes e ON fts.rowid = e.id
            WHERE episodes_fts MATCH ? AND e.show_slug = ?
            ORDER BY rank
            LIMIT ?
        """, (query, show_slug, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT e.* FROM episodes_fts fts
            JOIN episodes e ON fts.rowid = e.id
            WHERE episodes_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit)).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def get_all_search_docs(db_path: Path = DB_PATH) -> List[Dict[str, Any]]:
    """Export compact episode docs for static client-side search index.

    Includes only metadata + short fields (no full digest/script post-compaction).
    Used by build_search_index.py (Item 2 of May 2026 review).
    """
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT show_slug, episode_num, date, title, hook, summary,
               headlines, entities, topics, show_name, language
        FROM episodes
        ORDER BY date DESC, show_slug ASC
    """).fetchall()
    conn.close()
    docs = []
    for r in rows:
        d = dict(r)
        for f in ("headlines", "entities", "topics"):
            try:
                d[f] = json.loads(d[f]) if d.get(f) else []
            except Exception:
                d[f] = []
        docs.append(d)
    return docs


def get_lake_stats(db_path: Path = DB_PATH) -> Dict[str, Any]:
    """Return summary statistics about the content lake."""
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    stats: Dict[str, Any] = {}
    stats["total_episodes"] = conn.execute(
        "SELECT COUNT(*) FROM episodes"
    ).fetchone()[0]
    stats["shows"] = [
        r[0] for r in conn.execute(
            "SELECT DISTINCT show_slug FROM episodes ORDER BY show_slug"
        ).fetchall()
    ]
    stats["date_range"] = {
        "earliest": conn.execute("SELECT MIN(date) FROM episodes").fetchone()[0],
        "latest": conn.execute("SELECT MAX(date) FROM episodes").fetchone()[0],
    }
    stats["per_show"] = {}
    for row in conn.execute(
        "SELECT show_slug, COUNT(*), MIN(date), MAX(date) "
        "FROM episodes GROUP BY show_slug"
    ):
        stats["per_show"][row[0]] = {
            "count": row[1], "earliest": row[2], "latest": row[3],
        }
    stats["total_words"] = conn.execute(
        "SELECT SUM(word_count) FROM episodes"
    ).fetchone()[0] or 0
    conn.close()
    return stats


# ---------------------------------------------------------------------------
# Medium item: Compaction / retention (May 2026 review)
# ---------------------------------------------------------------------------

def compact_lake(retention_days: int = 180, db_path: Path = DB_PATH) -> dict:
    """Remove large text fields (digest_md, podcast_script) for old episodes.

    Keeps all metadata, headlines, entities, topics, and FTS index entries
    for weekly recaps, search, and cross-show analysis.

    This is the recommended way to control content lake growth without
    losing analytical value.
    """
    from datetime import date, timedelta  # already used in compact_lake

    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    cutoff = (date.today() - timedelta(days=retention_days)).isoformat()

    try:
        before = conn.execute(
            "SELECT COUNT(*) FROM episodes "
            "WHERE date < ? AND (digest_md IS NOT NULL OR podcast_script IS NOT NULL)",
            (cutoff,)
        ).fetchone()[0]

        conn.execute(
            "UPDATE episodes SET digest_md = NULL, podcast_script = NULL "
            "WHERE date < ? AND (digest_md IS NOT NULL OR podcast_script IS NOT NULL)",
            (cutoff,)
        )
        affected = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()

        return {
            "retention_days": retention_days,
            "cutoff": cutoff,
            "episodes_cleared": affected,
            "full_text_episodes_before": before,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Entity & topic extraction
# ---------------------------------------------------------------------------

# Known entities for pattern matching
_KNOWN_ENTITIES = [
    "OpenAI", "Anthropic", "Google", "DeepMind", "Meta", "Microsoft",
    "Apple", "Tesla", "SpaceX", "Nvidia", "AMD", "Intel", "Samsung",
    "Amazon", "AWS", "Hugging Face", "Mistral", "Cohere", "Stability AI",
    "Elon Musk", "Sam Altman", "Dario Amodei", "Sundar Pichai",
    "GPT", "Claude", "Gemini", "Llama", "Grok",
    "NASA", "ESA", "JAXA", "ISRO", "Blue Origin", "Rocket Lab",
    "Bank of Canada", "TFSA", "RRSP",
]

_TOPIC_PATTERNS = {
    "language-models": r"(?i)language model|LLM|GPT|transformer",
    "robotics": r"(?i)robot|humanoid|actuator",
    "autonomous-vehicles": r"(?i)self.driving|autonomous|FSD|autopilot",
    "climate": r"(?i)climate|carbon|emission|renewable",
    "biotech": r"(?i)biotech|gene therapy|CRISPR|longevity",
    "space": r"(?i)NASA|SpaceX|orbit|launch|asteroid|Mars",
    "regulation": r"(?i)regulat|compliance|legislation|EPA|SEC",
    "safety": r"(?i)AI safety|alignment|guardrail",
    "energy": r"(?i)solar|battery|grid|energy storage|megapack",
    "finance": r"(?i)invest|stock|market|portfolio|budget",
    "manufacturing": r"(?i)factory|gigafactory|production|manufacturing",
    "health": r"(?i)health|clinical trial|FDA|drug|therapy|disease",
}


def extract_entities_and_topics(
    digest_text: str,
    show_slug: str,
) -> Dict[str, List[str]]:
    """Extract named entities and topic tags from a digest.

    Uses regex patterns and known-entity matching.
    Returns ``{"entities": [...], "topics": [...]}``.
    """
    entities: set[str] = set()
    topics: set[str] = set()

    # Extract bold-text items (often company/product names in digests)
    bold_items = re.findall(r"\*\*([^*]+)\*\*", digest_text)
    for item in bold_items:
        if len(item.split()) <= 5 and item[0:1].isupper():
            entities.add(item.strip())

    # Match known entities
    text_lower = digest_text.lower()
    for entity in _KNOWN_ENTITIES:
        if entity.lower() in text_lower:
            entities.add(entity)

    # Topic extraction
    for topic, pattern in _TOPIC_PATTERNS.items():
        if re.search(pattern, digest_text):
            topics.add(topic)

    return {
        "entities": sorted(entities),
        "topics": sorted(topics),
    }


# ---------------------------------------------------------------------------
# CLI + URL helpers (Item 2 search UX)
# ---------------------------------------------------------------------------

def episode_search_url(show_slug: str, episode_num: int) -> str:
    """Return the best public deep link for an episode.

    Prefers the dedicated per-episode blog post (e.g. /blog/tesla/ep491.html)
    which exists for all indexed episodes. Falls back to the show page.
    """
    slug = str(show_slug or '').replace('_', '-')
    if not slug or not episode_num:
        return f"/{slug}.html" if slug else "/"

    # Per-episode blog posts are the canonical deep links
    return f"/blog/{slug}/ep{episode_num}.html"


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Content Lake search (FTS over episodes)")
    parser.add_argument("query", help="FTS5 query (supports AND, OR, NEAR, prefix*)")
    parser.add_argument("--show", help="Limit to one show slug")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    try:
        results = search_content(args.query, limit=args.limit, show_slug=args.show)
        print(f"Found {len(results)} results for: {args.query}")
        for r in results:
            print(f"  {r['show_slug']} Ep{r['episode_num']} ({r['date']}): {r['title'] or r['hook'][:80]}")
            print(f"    url: {episode_search_url(r['show_slug'], r['episode_num'])}")
    except Exception as e:
        print(f"Search error: {e}", file=sys.stderr)
        sys.exit(1)
