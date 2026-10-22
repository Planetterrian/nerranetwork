"""The story catalog — the durable copy of what the network aired (Oct 21 2026).

Tables (``supabase/migrations/20261021_story_catalog.sql``, Nerra Voices
project): ``catalog_episodes``, ``catalog_items`` (one row per aired story,
with a story id), ``catalog_stories``, ``catalog_articles`` (every article a
run fetched, aired or not), ``catalog_claims`` and ``catalog_corrections``.

The content lake (``engine/content_lake.py``, SQLite rebuilt from the repo)
computes items and story ids; this module copies them to Supabase. So:

* every table except ``catalog_articles`` can be rebuilt from the repo
  (``scripts/sync_story_catalog.py --full``); the committed digests stay the
  record;
* ``catalog_articles`` is the one thing only a run can know — what it fetched
  and did not air — and losing it loses a measurement, never an episode;
* nothing here ever blocks a run: unconfigured is a logged no-op, every call
  is time-boxed, every failure is caught by the caller.

Credentials: ``CATALOG_SUPABASE_URL`` / ``CATALOG_SUPABASE_KEY`` first, then
the names the workflows already pass for the same project
(``X_QUEUE_SUPABASE_*``, ``VOICES_SUPABASE_URL`` +
``VOICES_SUPABASE_SERVICE_KEY``, ``SUPABASE_URL`` + ``SUPABASE_SERVICE_KEY``).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sqlite3
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent

_ENV_PAIRS = (
    ("CATALOG_SUPABASE_URL", "CATALOG_SUPABASE_KEY"),
    ("X_QUEUE_SUPABASE_URL", "X_QUEUE_SUPABASE_KEY"),
    ("VOICES_SUPABASE_URL", "VOICES_SUPABASE_SERVICE_KEY"),
    ("SUPABASE_URL", "SUPABASE_SERVICE_KEY"),
)

TIMEOUT_SECONDS = 20
BATCH = 200
#: Unaired articles older than this are deleted by the nightly sync.
UNAIRED_RETENTION_DAYS = 90
#: A missed story is carried by at least this many distinct outlets.
MISSED_MIN_OUTLETS = 3


# ---------------------------------------------------------------- plumbing --
def _db() -> Tuple[str, str]:
    for url_name, key_name in _ENV_PAIRS:
        url = os.getenv(url_name, "").strip().rstrip("/")
        key = os.getenv(key_name, "").strip()
        if url and key:
            return url, key
    return "", ""


def configured() -> bool:
    url, key = _db()
    return bool(url and key)


def _rest(method: str, table: str, *, params=None, body=None,
          prefer: str = "return=minimal"):
    import requests

    url, key = _db()
    r = requests.request(
        method, f"{url}/rest/v1/{table}", params=params, json=body,
        timeout=TIMEOUT_SECONDS,
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": prefer})
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {table}: HTTP {r.status_code} {r.text[:300]}")
    return r.json() if r.text.strip() else []


def upsert(table: str, rows: List[dict], on_conflict: str) -> int:
    """Insert-or-merge *rows* (only the columns present are written).

    Rows repeating a conflict key are collapsed first, the last one winning:
    Postgres refuses an upsert that touches one row twice in one statement
    (21000), and one bad pair would fail the whole batch (the first full fill,
    Oct 21 2026, lost every correction behind a claims batch).
    """
    keys = [k.strip() for k in on_conflict.split(",")]
    unique: Dict[tuple, dict] = {}
    for r in rows:
        unique[tuple(r.get(k) for k in keys)] = r
    rows = list(unique.values())
    n = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        _rest("POST", table, params={"on_conflict": on_conflict}, body=chunk,
              prefer="resolution=merge-duplicates,return=minimal")
        n += len(chunk)
    return n


def select(table: str, params: dict) -> List[dict]:
    return _rest("GET", table, params=params, prefer="return=representation") or []


def _in_list(values: Iterable[str]) -> str:
    quoted = ['"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"' for v in values]
    return "in.(" + ",".join(quoted) + ")"


# ------------------------------------------------------------- the lake side --
def _lake(db_path: Optional[Path]):
    from engine import content_lake

    path = Path(db_path) if db_path else content_lake.DB_PATH
    content_lake.init_db(path)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def episode_key(show_slug: str, episode_num: int) -> str:
    return f"{show_slug}:{int(episode_num)}"


def _show_dirs() -> Dict[str, Path]:
    """slug -> committed digest directory, from the show YAMLs."""
    out: Dict[str, Path] = {}
    from engine.config import load_config

    for yml in sorted((ROOT / "shows").glob("*.yaml")):
        if yml.name.startswith("_"):
            continue
        try:
            cfg = load_config(yml)
        except Exception:  # noqa: BLE001 — not a show config
            continue
        if getattr(cfg, "slug", ""):
            out[cfg.slug] = ROOT / cfg.episode.output_dir
    return out


def _ledger_for(show_dir: Path, episode_num: int, date: str) -> Optional[Path]:
    stamp = date.replace("-", "")
    for p in show_dir.glob(f"*_Ep{int(episode_num):03d}_{stamp}_claims.json"):
        return p
    return None


def lake_rows(*, since: str = "", show: str = "", episode: int = 0,
              db_path: Optional[Path] = None) -> Tuple[List[dict], List[dict]]:
    """``(episode_rows, item_rows)`` for the catalog, from the lake."""
    conn = _lake(db_path)
    where, params = [], []
    if since:
        where.append("date >= ?")
        params.append(since)
    if show:
        where.append("show_slug = ?")
        params.append(show)
    if episode:
        where.append("episode_num = ?")
        params.append(int(episode))
    sql_where = (" WHERE " + " AND ".join(where)) if where else ""
    eps = conn.execute(
        "SELECT show_slug, show_name, episode_num, date, title, hook, language, word_count "
        "FROM episodes" + sql_where, params).fetchall()
    items = conn.execute(
        "SELECT item_key, show_slug, episode_num, date, position, section, title, body, "
        "urls, kind, story_id, tokens, language FROM items" + sql_where
        + " ORDER BY date, show_slug, episode_num, position", params).fetchall()
    conn.close()
    counts: Dict[str, int] = defaultdict(int)
    item_rows = []
    for r in items:
        key = episode_key(r["show_slug"], r["episode_num"])
        counts[key] += 1
        item_rows.append({
            "item_key": r["item_key"], "episode_key": key, "show_slug": r["show_slug"],
            "episode_num": r["episode_num"], "date": r["date"], "position": r["position"],
            "section": r["section"] or "", "title": r["title"] or "", "body": r["body"] or "",
            "urls": json.loads(r["urls"] or "[]"), "kind": r["kind"] or "item",
            "story_id": r["story_id"], "tokens": json.loads(r["tokens"] or "[]"),
            "language": r["language"] or "en",
        })
    ep_rows = []
    for r in eps:
        key = episode_key(r["show_slug"], r["episode_num"])
        ep_rows.append({
            "episode_key": key, "show_slug": r["show_slug"], "show_name": r["show_name"] or "",
            "episode_num": r["episode_num"], "date": r["date"], "title": r["title"] or "",
            "hook": r["hook"] or "", "language": r["language"] or "en",
            "word_count": r["word_count"] or 0, "item_count": counts.get(key, 0),
        })
    return ep_rows, item_rows


def story_rows(story_ids: Iterable[str], db_path: Optional[Path] = None) -> List[dict]:
    """Aggregate ``catalog_stories`` rows from every lake item of each story."""
    ids = sorted({s for s in story_ids if s})
    if not ids:
        return []
    conn = _lake(db_path)
    out = []
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        q = ",".join("?" * len(chunk))
        rows = conn.execute(
            f"SELECT story_id, date, show_slug, title, kind FROM items WHERE story_id IN ({q}) "
            "ORDER BY date, show_slug, episode_num, position", chunk).fetchall()
        groups: Dict[str, list] = defaultdict(list)
        for r in rows:
            groups[r["story_id"]].append(r)
        for sid, members in groups.items():
            shows = sorted({m["show_slug"] for m in members})
            out.append({
                "story_id": sid, "title": members[0]["title"] or "",
                "first_seen": members[0]["date"], "last_seen": members[-1]["date"],
                "item_count": len(members), "day_count": len({m["date"] for m in members}),
                "show_count": len(shows), "shows": shows,
            })
    conn.close()
    return out


def claim_rows(ep_rows: List[dict], show_dirs: Dict[str, Path]) -> List[dict]:
    out = []
    for ep in ep_rows:
        d = show_dirs.get(ep["show_slug"])
        if not d:
            continue
        ledger = _ledger_for(d, ep["episode_num"], ep["date"])
        if not ledger:
            continue
        try:
            data = json.loads(ledger.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        claims = data.get("claims") if isinstance(data, dict) else data
        seen: set = set()
        for n, c in enumerate(claims or []):
            if not isinstance(c, dict):
                continue
            # A ledger can carry one id twice (a repair or coverage-floor entry
            # beside the original); both claims are kept, under distinct keys.
            cid = str(c.get("id") or n)
            if cid in seen:
                cid = f"{cid}#{n}"
            seen.add(cid)
            out.append({
                "claim_key": f"{ep['episode_key']}:{cid}",
                "episode_key": ep["episode_key"], "show_slug": ep["show_slug"],
                "episode_num": ep["episode_num"], "date": ep["date"],
                "claim": c.get("claim") or "", "source_url": c.get("source_url") or "",
                "source_title": c.get("source_title") or "",
                "supporting_quote": c.get("supporting_quote") or "",
                "status": c.get("status") or "",
            })
    return out


def correction_items(correction: dict, episode_items: List[dict]) -> List[dict]:
    """The items of the corrected episode that the correction is ABOUT: those
    holding a replacement's ``find`` text, else those whose title shares three
    salient words with the correction text, else none (a correction is about
    one or two stories, never the whole episode)."""
    from engine.story_catalog import item_tokens

    # An applied correction's find text is gone from the digest and its
    # replacement is there, so either one locates the item.
    finds = [t for r in correction.get("replacements") or []
             for t in (r.get("find") or "", r.get("replace") or "")]
    finds = [f for f in finds if len(f) >= 12]
    hits = [i for i in episode_items
            if any(f in (i.get("body") or "") or f in (i.get("title") or "") for f in finds)]
    if hits:
        return hits
    ctoks = item_tokens(correction.get("text") or "")
    return [i for i in episode_items
            if len(item_tokens(i.get("title") or "", "") & ctoks) >= 3]


def correction_rows(shows: Iterable[str], show_dirs: Dict[str, Path],
                    db_path: Optional[Path] = None) -> List[dict]:
    from engine.corrections import load_corrections

    conn = _lake(db_path)
    out = []
    for slug in sorted(set(shows)):
        d = show_dirs.get(slug)
        if not d:
            continue
        for n, c in enumerate(load_corrections(d)):
            ep_items = [dict(r) for r in conn.execute(
                "SELECT title, body, story_id FROM items WHERE show_slug = ? AND episode_num = ? "
                "AND story_id IS NOT NULL", (slug, int(c["episode"])))]
            ids = sorted({i["story_id"] for i in correction_items(c, ep_items)})
            out.append({
                "correction_key": f"{slug}:{c['episode']}:{c['date']}:{n}",
                "show_slug": slug, "episode_num": int(c["episode"]), "date": str(c["date"]),
                "text": c.get("text") or "", "where_": c.get("where") or "",
                "story_ids": sorted(ids),
            })
    conn.close()
    return out


# ----------------------------------------------------------------- writes --
def sync_from_lake(*, since: str = "", show: str = "", episode: int = 0, full: bool = False,
                   db_path: Optional[Path] = None, dry_run: bool = False) -> Dict[str, int]:
    """Copy episodes, items, their stories, claims and corrections from the
    lake. ``full`` copies everything; otherwise ``since`` / ``show`` /
    ``episode`` narrow it. On a narrow sync, items an episode no longer has
    are deleted (a re-run that told fewer stories)."""
    if not (full or since or show or episode):
        raise ValueError("sync_from_lake: pass full=True or a filter")
    ep_rows, item_rows = lake_rows(since="" if full else since, show=show,
                                   episode=episode, db_path=db_path)
    stories = story_rows((i["story_id"] for i in item_rows), db_path=db_path)
    dirs = _show_dirs()
    claims = claim_rows(ep_rows, dirs)
    corrections = correction_rows((e["show_slug"] for e in ep_rows), dirs, db_path=db_path)
    counts = {"episodes": len(ep_rows), "items": len(item_rows), "stories": len(stories),
              "claims": len(claims), "corrections": len(corrections)}
    if dry_run or not configured():
        if not dry_run:
            logger.info("Story catalog not configured — sync skipped (%s)", counts)
        return counts
    upsert("catalog_episodes", ep_rows, "episode_key")
    upsert("catalog_items", item_rows, "item_key")
    if not full:
        for ep in ep_rows:
            _rest("DELETE", "catalog_items", params={
                "episode_key": f"eq.{ep['episode_key']}", "position": f"gte.{ep['item_count']}"})
    upsert("catalog_stories", stories, "story_id")
    upsert("catalog_claims", claims, "claim_key")
    upsert("catalog_corrections", corrections, "correction_key")
    return counts


def article_rows(*, show_slug: str, date: str, fetched: List[dict], listed: List[dict],
                 db_path: Optional[Path] = None) -> List[dict]:
    """One row per fetched article (deduped by normalised URL), with whether
    this episode aired it and the story it belongs to."""
    from engine import content_lake
    from engine.content_tracker import _normalize_url_for_dedup
    from engine.story_catalog import StoryAssigner, WINDOW_DAYS, item_tokens

    path = Path(db_path) if db_path else content_lake.DB_PATH
    today = dt.date.fromisoformat(date)
    start = (today - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    window = content_lake.query_items(start, date, db_path=path)
    aired_story: Dict[str, str] = {}
    assigner = StoryAssigner()
    by_date: Dict[str, list] = defaultdict(list)
    for it in window:
        if it.get("kind") == "essay" or not it.get("story_id"):
            continue
        by_date[it["date"]].append((it["story_id"], frozenset(it.get("tokens") or []), it["show_slug"]))
        if it["show_slug"] == show_slug and it["date"] == date:
            for u in it.get("urls") or []:
                k = _normalize_url_for_dedup(u)
                if k:
                    aired_story[k] = it["story_id"]
    for d in sorted(by_date):
        assigner.observe(d, by_date[d])
    listed_keys = {_normalize_url_for_dedup(a.get("url") or "") for a in listed}
    rows: Dict[str, dict] = {}
    for a in fetched:
        url = (a.get("url") or "").strip()
        key = _normalize_url_for_dedup(url)
        if not key or key in rows:
            continue
        toks = item_tokens(a.get("title") or "", a.get("description") or "")
        aired = key in aired_story
        sid = aired_story.get(key) or assigner.match_story(toks, show_slug)
        pub = (a.get("published_date") or "")[:10]
        try:
            pub = dt.date.fromisoformat(pub).isoformat() if pub else None
        except ValueError:
            pub = None
        rows[key] = {
            "url_key": key, "url": url, "title": (a.get("title") or "")[:500],
            "outlet": (a.get("source_name") or "")[:200], "published_date": pub,
            "date_source": a.get("date_source") or "", "first_seen": date, "last_seen": date,
            "shows": [show_slug], "listed_shows": [show_slug] if key in listed_keys else [],
            "aired": aired, "story_id": sid, "tokens": sorted(toks),
        }
    return list(rows.values())


def record_articles(rows: List[dict]) -> int:
    """Merge article rows with what the catalog already holds (shows and
    listed_shows are unions, ``aired`` sticks once true, ``first_seen`` keeps
    the earliest date)."""
    if not rows or not configured():
        return 0
    existing: Dict[str, dict] = {}
    keys = [r["url_key"] for r in rows]
    # 40 keys a request keeps the query string well under a proxy's URL limit
    # (a normalised article URL runs ~100-150 characters once encoded).
    for i in range(0, len(keys), 40):
        for r in select("catalog_articles", {
                "select": "url_key,first_seen,shows,listed_shows,aired,story_id",
                "url_key": _in_list(keys[i:i + 40])}):
            existing[r["url_key"]] = r
    merged = []
    for r in rows:
        old = existing.get(r["url_key"])
        if old:
            r = dict(r)
            r["first_seen"] = min(str(old.get("first_seen") or r["first_seen"]), r["first_seen"])
            r["shows"] = sorted(set(old.get("shows") or []) | set(r["shows"]))
            r["listed_shows"] = sorted(set(old.get("listed_shows") or []) | set(r["listed_shows"]))
            r["aired"] = bool(old.get("aired")) or r["aired"]
            if old.get("aired") and old.get("story_id"):
                r["story_id"] = old["story_id"]
        merged.append(r)
    return upsert("catalog_articles", merged, "url_key")


def record_run(*, show_slug: str, episode_num: int, date: str, fetched: List[dict],
               listed: List[dict], page_url: str = "", audio_url: str = "",
               db_path: Optional[Path] = None, budget_seconds: float = 60.0) -> Dict[str, object]:
    """What a show run writes after it publishes: its episode, items, stories,
    claims and corrections (from the lake) and every article it fetched."""
    if not configured():
        return {"status": "unconfigured"}
    t0 = time.monotonic()
    errors: List[str] = []
    try:
        counts = sync_from_lake(show=show_slug, episode=episode_num, db_path=db_path)
    except Exception as exc:  # noqa: BLE001 — the nightly sync heals it
        counts = {}
        errors.append(f"sync: {exc}"[:300])
    if page_url or audio_url:
        # A PATCH, never an upsert: an upsert is an INSERT first, and Postgres
        # checks NOT NULL columns before it merges into the existing row, so
        # a row carrying only the two links was refused on every run of the
        # first slate (Oct 22 2026, code 23502) and the articles behind it
        # were never written.
        try:
            _rest("PATCH", "catalog_episodes",
                  params={"episode_key": f"eq.{episode_key(show_slug, episode_num)}"},
                  body={"page_url": page_url or None, "audio_url": audio_url or None})
        except Exception as exc:  # noqa: BLE001
            errors.append(f"links: {exc}"[:300])
    if time.monotonic() - t0 > budget_seconds:
        return {"status": "partial", **counts}
    rows = article_rows(show_slug=show_slug, date=date, fetched=fetched, listed=listed,
                        db_path=db_path)
    try:
        counts["articles"] = record_articles(rows)
    except Exception as exc:  # noqa: BLE001 — only a run can write these
        errors.append(f"articles: {exc}"[:300])
        counts["articles"] = 0
    counts["articles_aired"] = sum(1 for r in rows if r["aired"])
    if errors:
        for e in errors:
            logger.warning("Story catalog: %s", e)
        return {"status": "partial", "errors": errors, **counts}
    return {"status": "ok", **counts}


def prune_unaired(days: int = UNAIRED_RETENTION_DAYS, today: Optional[dt.date] = None) -> None:
    if not configured():
        return
    cutoff = ((today or dt.date.today()) - dt.timedelta(days=days)).isoformat()
    _rest("DELETE", "catalog_articles", params={"aired": "eq.false", "last_seen": f"lt.{cutoff}"})


# ------------------------------------------------------------------ reads --
def missed_stories(day: dt.date, *, min_outlets: int = MISSED_MIN_OUTLETS,
                   rows: Optional[List[dict]] = None) -> List[dict]:
    """Stories carried by ``min_outlets`` or more distinct outlets on *day*
    (and the day before) that no show aired. An unaired article that matches
    an aired story is not missed — some show told it."""
    from engine.story_catalog import StoryAssigner

    if rows is None:
        if not configured():
            return []
        rows = select("catalog_articles", {
            "select": "url,title,outlet,shows,listed_shows,aired,story_id,tokens,last_seen",
            "last_seen": f"gte.{(day - dt.timedelta(days=1)).isoformat()}",
            "aired": "eq.false", "story_id": "is.null", "limit": "10000"})
    cand = [r for r in rows if not r.get("aired") and not r.get("story_id")]
    cand.sort(key=lambda r: (str(r.get("last_seen") or ""), r.get("url") or ""))
    assigner = StoryAssigner()
    groups: Dict[str, list] = defaultdict(list)
    batch = [(f"a:{n}", frozenset(r.get("tokens") or []),
              (r.get("outlet") or "?").lower()) for n, r in enumerate(cand)]
    ids = assigner.assign(day.isoformat(), batch)
    for sid, r in zip(ids, cand):
        groups[sid].append(r)
    out = []
    for members in groups.values():
        outlets = sorted({(m.get("outlet") or "").strip() for m in members if m.get("outlet")})
        if len(outlets) < min_outlets:
            continue
        out.append({
            "title": members[0].get("title") or "",
            "outlets": outlets,
            "fetched_by": sorted({s for m in members for s in (m.get("shows") or [])}),
            "listed_by": sorted({s for m in members for s in (m.get("listed_shows") or [])}),
            "urls": [m.get("url") for m in members][:6],
        })
    out.sort(key=lambda s: (-len(s["outlets"]), s["title"]))
    return out


def search(query: str, limit: int = 25) -> List[dict]:
    """Full-text search over aired items in the catalog."""
    if not configured():
        return []
    return select("catalog_items", {
        "select": "item_key,show_slug,episode_num,date,title,urls,story_id",
        "fts": f"wfts(simple).{query}", "order": "date.desc", "limit": str(limit)})


def story(story_id: str) -> List[dict]:
    """Every aired item of one story, oldest first, from the catalog."""
    if not configured():
        return []
    return select("catalog_items", {
        "select": "item_key,show_slug,episode_num,date,title,body,urls",
        "story_id": f"eq.{story_id}", "order": "date.asc"})


__all__ = [
    "configured", "sync_from_lake", "record_run", "article_rows", "record_articles",
    "prune_unaired", "missed_stories", "search", "story", "episode_key",
]
