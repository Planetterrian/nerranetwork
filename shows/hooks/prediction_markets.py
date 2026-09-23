"""Prediction Markets Daily hooks (Sep 2026, docs/new_shows_plan_2026_09_22.md §4.11).

pre_fetch:
  * the show's narrative memory;
  * The Board as hook ARTICLES (engine/prediction_board.py): the day's most
    traded Polymarket and Kalshi markets and the busiest Manifold play-money
    markets, one article per market, with the numbers in the article text so
    the claims gate verifies them against the copy the run already holds;
  * today's How It Works subject from the curriculum
    (shows/curricula/prediction_markets.yaml, engine/curriculum.py) and real
    abstracts for it (engine/research_papers.py: Crossref + arXiv), so the
    explainer cites papers instead of memory;
  * one ``hook_context`` block naming what feeds each section and the
    honest fallback when a venue does not answer.
post_generate: marks the subject produced (committed by run-show.yml's
success path only, so a skipped episode re-picks it) and mines themes.

Every step is non-fatal: a venue that times out is a shorter board, never a
failed episode.
"""

from __future__ import annotations

import datetime as _dt
import logging
from pathlib import Path

from engine import show_memory
from engine.board_week import week_board_block
from engine.curriculum import (
    curriculum_path,
    mark_spotlight_done,
    next_spotlight,
    spotlight_block,
)
from engine.prediction_board import (
    board_block,
    gather_board,
    kalshi_articles,
    manifold_articles,
    polymarket_articles,
)
from engine.research_papers import papers_for

logger = logging.getLogger(__name__)

_SLUG = "prediction_markets"
_LABEL = "How It Works"
_DIGESTS_DIR = Path(__file__).resolve().parents[2] / "digests" / _SLUG

#: Below this many unproduced subjects the hook warns: the curriculum is
#: hand-planned and a daily show uses one a day.
RUNWAY_WARN_ENTRIES = 7

# The subject chosen in pre_fetch, for post_generate (same process).
_selected: dict = {}


def _remaining() -> int:
    import yaml

    try:
        data = yaml.safe_load(curriculum_path(_SLUG).read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return 0
    return sum(1 for e in data.get("queue") or [] if not e.get("produced"))


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    context = show_memory.memory_pre_fetch(config, _SLUG)
    articles = gather_board([polymarket_articles, kalshi_articles, manifold_articles])
    logger.info("%s: %d board market(s) from the venues", _SLUG, len(articles))
    parts = [board_block(articles)]

    topic = None
    try:
        topic = next_spotlight(_SLUG)
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s: curriculum selection failed (non-fatal): %s", _SLUG, exc)
    _selected.clear()
    if topic:
        _selected.update(topic)
        try:
            papers = papers_for(topic)
            logger.info("%s: %d paper abstract(s) for %r", _SLUG, len(papers), topic.get("id"))
            articles.extend(papers)
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: paper fetch failed (non-fatal): %s", _SLUG, exc)
    parts.append(spotlight_block(topic, _LABEL, period="day"))

    # Friday: The Week's Board — the show scores its own week from the
    # committed Boards (engine/board_week.py; data-side, nothing looked up).
    try:
        today = _dt.date.fromisoformat(today_str) if today_str else _dt.datetime.now(_dt.timezone.utc).date()
    except ValueError:
        today = _dt.datetime.now(_dt.timezone.utc).date()
    if today.weekday() == 4:
        try:
            week = week_board_block(_DIGESTS_DIR, today, articles)
            if week:
                parts.append(week)
                context["metrics"] = {"week_board_rows": week.count("\n- ")}
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: week board failed (non-fatal): %s", _SLUG, exc)

    left = _remaining()
    if left < RUNWAY_WARN_ENTRIES:
        # GitHub annotation: the operator sees it on the run page.
        print(f"::warning::{_SLUG}: {left} How It Works subject(s) left in "
              f"shows/curricula/{_SLUG}.yaml — add more before it runs dry")

    if articles:
        context["articles"] = articles
    context["hook_context"] = "\n\n".join(p for p in parts if p)
    return context


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    if _selected.get("id") and digest_text:
        try:
            mark_spotlight_done(_SLUG, _selected["id"], int(episode_num or 0))
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: could not mark subject produced: %s", _SLUG, exc)
    show_memory.memory_post_generate(config, _SLUG, digest_text or "", episode_num or 0)
