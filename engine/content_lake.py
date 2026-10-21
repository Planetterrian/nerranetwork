"""Content Lake — Persistent structured storage for all Nerra Network episode content.

Stores digests, scripts, metadata, and derived data for downstream content
products (weekly newsletters, monthly reports, cross-show briefings).

Uses SQLite for reliable concurrent access and efficient querying.  The
database lives at ``data/content_lake.db`` by default.

Oct 21 2026 — items and story ids. Every episode's aired stories
(``engine.aired_items``) are stored one row each in ``items``, with the story
id ``engine.story_catalog`` assigns (the same story across days and shows).
``store_episode`` derives them from the episode's own digest, so the runtime
write and the CI rebuild fill the same rows; ``rebuild_story_ids`` re-derives
every id in the canonical order after a rebuild. The durable copy lives in the
story catalog (``engine/catalog.py``, Supabase); this lake is its offline,
rebuildable mirror for build-time readers (prompts, books, search).
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_key TEXT NOT NULL UNIQUE,
            show_slug TEXT NOT NULL,
            episode_num INTEGER NOT NULL,
            date TEXT NOT NULL,
            position INTEGER NOT NULL,
            section TEXT,
            title TEXT,
            body TEXT,
            urls TEXT,  -- JSON array
            kind TEXT,
            story_id TEXT,
            tokens TEXT,  -- JSON array (salient tokens used for story matching)
            language TEXT DEFAULT 'en'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_items_date ON items(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_items_story ON items(story_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_items_show_ep ON items(show_slug, episode_num)")
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(title, body)
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
    aired = []
    if record.digest_md and not record.headlines:
        try:
            from engine.aired_items import extract_aired_items
            aired = extract_aired_items(record.digest_md)
            record.headlines = [i.title for i in aired if i.kind != "essay"]
            if not record.source_urls:
                seen: set = set()
                record.source_urls = [u for i in aired for u in i.urls
                                      if not (u in seen or seen.add(u))]
        except Exception as exc:  # noqa: BLE001 — items are a bonus
            logger.warning("[ContentLake] Aired items failed for %s ep%s: %s",
                           record.show_slug, record.episode_num, exc)
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
        _store_items(conn, record, aired)
        conn.commit()
        logger.info("[ContentLake] Stored %s ep%d (%s)",
                    record.show_slug, record.episode_num, record.date)
    except Exception as e:
        logger.error("[ContentLake] Failed to store episode: %s", e)
        conn.rollback()
    finally:
        conn.close()


def _store_items(conn: sqlite3.Connection, record: EpisodeRecord, aired=None) -> None:
    """Replace this episode's item rows (story ids are assigned separately)."""
    from engine.aired_items import extract_aired_items
    from engine.story_catalog import item_key, item_tokens

    if aired is None or (not aired and record.digest_md):
        aired = extract_aired_items(record.digest_md or "")
    old_ids = [r[0] for r in conn.execute(
        "SELECT id FROM items WHERE show_slug = ? AND episode_num = ?",
        (record.show_slug, record.episode_num))]
    for rid in old_ids:
        conn.execute("DELETE FROM items_fts WHERE rowid = ?", (rid,))
    conn.execute("DELETE FROM items WHERE show_slug = ? AND episode_num = ?",
                 (record.show_slug, record.episode_num))
    for pos, it in enumerate(aired):
        toks = sorted(item_tokens(it.title, it.body)) if it.kind != "essay" else []
        cur = conn.execute("""
            INSERT INTO items (item_key, show_slug, episode_num, date, position,
                               section, title, body, urls, kind, tokens, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (item_key(record.show_slug, record.episode_num, pos), record.show_slug,
              record.episode_num, record.date, pos, it.section, it.title, it.body,
              json.dumps(it.urls), it.kind, json.dumps(toks), record.language))
        conn.execute("INSERT INTO items_fts(rowid, title, body) VALUES (?, ?, ?)",
                     (cur.lastrowid, it.title, it.body))


def _item_rows(conn: sqlite3.Connection, where: str = "", params: tuple = ()) -> list:
    return conn.execute(
        "SELECT item_key, show_slug, date, tokens, kind, story_id FROM items "
        + (f"WHERE {where} " if where else "")
        + "ORDER BY date, show_slug, episode_num, position", params).fetchall()


def rebuild_story_ids(db_path: Path = DB_PATH, since: Optional[str] = None) -> int:
    """Assign story ids in the canonical order (date, show, episode, item).

    ``since=None`` re-derives every id (the CI rebuild). With ``since`` the
    window before it is taken in with its stored ids and only items on or
    after ``since`` are (re)assigned — what a single show run needs. Returns
    the number of items assigned."""
    import datetime as _dt
    from engine.story_catalog import WINDOW_DAYS, StoryAssigner

    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        assigner = StoryAssigner()
        if since:
            seed_from = (_dt.date.fromisoformat(since) - _dt.timedelta(days=WINDOW_DAYS)).isoformat()
            by_date: Dict[str, list] = {}
            for key, show, date, toks, kind, sid in _item_rows(
                    conn, "date >= ? AND date < ?", (seed_from, since)):
                if kind != "essay" and sid:
                    by_date.setdefault(date, []).append((sid, frozenset(json.loads(toks or "[]")), show))
            for date in sorted(by_date):
                assigner.observe(date, by_date[date])
            rows = _item_rows(conn, "date >= ?", (since,))
        else:
            rows = _item_rows(conn)
        days: Dict[str, list] = {}
        for key, show, date, toks, kind, _sid in rows:
            days.setdefault(date, []).append((key, frozenset(json.loads(toks or "[]")), show, kind))
        n = 0
        for date in sorted(days):
            batch = days[date]
            ids = assigner.assign(date, batch)
            conn.executemany("UPDATE items SET story_id = ? WHERE item_key = ?",
                             [(sid, row[0]) for sid, row in zip(ids, batch)])
            n += len(batch)
        conn.commit()
        return n
    finally:
        conn.close()


def query_items(start_date: str, end_date: str, *, exclude_show: str = "",
                show_slug: str = "", db_path: Path = DB_PATH) -> List[Dict[str, Any]]:
    """Aired items between two dates (inclusive), optionally for one show or
    excluding one."""
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    sql = ("SELECT i.*, e.show_name FROM items i LEFT JOIN episodes e "
           "ON e.show_slug = i.show_slug AND e.episode_num = i.episode_num "
           "WHERE i.date >= ? AND i.date <= ?")
    params: list = [start_date, end_date]
    if show_slug:
        sql += " AND i.show_slug = ?"
        params.append(show_slug)
    if exclude_show:
        sql += " AND i.show_slug != ?"
        params.append(exclude_show)
    sql += " ORDER BY i.date, i.show_slug, i.episode_num, i.position"
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    for r in rows:
        r["urls"] = json.loads(r.get("urls") or "[]")
        r["tokens"] = json.loads(r.get("tokens") or "[]")
    return rows


def story_timeline(story_id: str, db_path: Path = DB_PATH) -> List[Dict[str, Any]]:
    """Every aired item of one story, oldest first."""
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT i.*, e.show_name FROM items i LEFT JOIN episodes e "
        "ON e.show_slug = i.show_slug AND e.episode_num = i.episode_num "
        "WHERE i.story_id = ? ORDER BY i.date, i.show_slug, i.position",
        (story_id,)).fetchall()]
    conn.close()
    for r in rows:
        r["urls"] = json.loads(r.get("urls") or "[]")
    return rows


def search_items(query: str, limit: int = 50, db_path: Path = DB_PATH) -> List[Dict[str, Any]]:
    """Full-text search over aired items (title + body), best match first."""
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT i.*, e.show_name FROM items_fts f JOIN items i ON i.id = f.rowid "
            "LEFT JOIN episodes e ON e.show_slug = i.show_slug AND e.episode_num = i.episode_num "
            "WHERE items_fts MATCH ? ORDER BY rank LIMIT ?", (query, limit)).fetchall()]
    except sqlite3.OperationalError as exc:
        logger.warning("[ContentLake] Item search failed for %r: %s", query, exc)
        rows = []
    conn.close()
    for r in rows:
        r["urls"] = json.loads(r.get("urls") or "[]")
    return rows


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

    # Extract bold-text items (often company/product names in digests).
    # Aug 27 2026: bold SECTION LABELS were being stored as entities —
    # Omni View's every-episode "What happened (neutral):", "Context &
    # perspectives:" and "Read more (sources):" labels each recorded as a
    # recurring "entity", which polluted query_by_entity and made the
    # weekly-summary segment's recurring-threads signal name a formatting
    # label as the week's biggest ongoing story. A label announces itself:
    # it ends with a colon. Real names never do.
    bold_items = re.findall(r"\*\*([^*]+)\*\*", digest_text)
    for item in bold_items:
        item = item.strip()
        if item.endswith(":"):
            continue
        if len(item.split()) <= 5 and item[0:1].isupper():
            entities.add(item)

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
