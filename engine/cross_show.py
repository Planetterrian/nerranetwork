"""Which of today's articles a sibling show has already told (Oct 21 2026).

The ``{cross_show_context}`` block sits in 23 digest prompts and had never
fired: it filtered the content lake on ``headlines``, which the CI rebuild
left empty, so every prompt read "(No recent cross-network coverage …)". Its
design was also the wrong shape for a fix: ten random headlines from other
shows, under an instruction to "avoid redundancy" — but a Tesla listener still
needs the merger story SpaceX led with.

Now the block names only the articles IN TODAY'S LIST whose story a sibling
show told in the last :data:`WINDOW_DAYS` days (story matching from
``engine.story_catalog`` against the lake's aired items), and asks for this
show's angle rather than silence.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

WINDOW_DAYS = 2
MAX_LINES = 12

NONE_TEXT = "(No story in today's list was told by a sibling Nerra show in the last two days.)"


def sibling_matches(articles: List[dict], show_slug: str, today: dt.date, *,
                    db_path=None) -> List[Dict]:
    """``[{"index", "title", "show_name", "date", "told_as"}, ...]`` — one per
    article (1-based ``index`` as numbered in the prompt) whose story a sibling
    show aired between ``today - WINDOW_DAYS`` and today."""
    from engine import content_lake
    from engine.story_catalog import StoryAssigner, item_tokens

    kwargs = {"db_path": db_path} if db_path else {}
    start = (today - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    items = content_lake.query_items(start, today.isoformat(), exclude_show=show_slug, **kwargs)
    items = [i for i in items if i.get("kind") != "essay" and i.get("story_id")]
    if not items:
        return []
    assigner = StoryAssigner()
    by_date: Dict[str, list] = {}
    latest: Dict[str, dict] = {}
    for it in items:
        by_date.setdefault(it["date"], []).append(
            (it["story_id"], frozenset(it.get("tokens") or []), it["show_slug"]))
        latest[it["story_id"]] = it
    for date in sorted(by_date):
        assigner.observe(date, by_date[date])
    out: List[Dict] = []
    for idx, art in enumerate(articles, 1):
        title = (art.get("title") or "").strip()
        if not title:
            continue
        sid = assigner.match_story(item_tokens(title, art.get("description") or ""), show_slug)
        if not sid or sid not in latest:
            continue
        hit = latest[sid]
        out.append({"index": idx, "title": title,
                    "show_name": hit.get("show_name") or hit["show_slug"],
                    "date": hit["date"], "told_as": hit.get("title") or ""})
    return out


def render_block(matches: List[Dict]) -> str:
    if not matches:
        return NONE_TEXT
    lines = []
    for m in matches[:MAX_LINES]:
        when = m["date"]
        try:
            when = dt.date.fromisoformat(m["date"]).strftime("%b %-d")
        except ValueError:
            pass
        lines.append(f'- Article {m["index"]} ("{m["title"][:110]}") — told by '
                     f'{m["show_name"]} on {when} as "{m["told_as"][:110]}"')
    return (
        "Stories in today's article list that a sibling Nerra show has already told. "
        "Many listeners follow only this show, so cover any of them on their merits; "
        "when you do, tell it from this show's angle, lead with what is new or what "
        "matters to this show's listener, and never assume the listener heard the "
        "other show:\n" + "\n".join(lines)
    )


def cross_show_context(articles: List[dict], show_slug: str, today: dt.date, *,
                       db_path=None) -> Optional[str]:
    """The rendered block, or None when the lake cannot be read."""
    try:
        return render_block(sibling_matches(articles, show_slug, today, db_path=db_path))
    except Exception as exc:  # noqa: BLE001 — context only, never blocks
        logger.warning("Cross-show context unavailable: %s", exc)
        return None


__all__ = ["sibling_matches", "render_block", "cross_show_context", "NONE_TEXT", "WINDOW_DAYS"]
