"""MAG 7 Daily hooks (Sep 2026, docs/new_shows_plan_2026_09_22.md §4.2).

pre_fetch supplies, in one ``hook_context`` block for the digest prompt:
  1. THE TAPE — the seven companies' last regular-session closes with the
     session date (engine.market_quotes). It feeds one reader-only line at
     the foot of the digest; the podcast never reads it (operator brief,
     2026-09-23: the show is about what the seven build, ship and discover,
     not their prices).
  2. What Tesla Shorts Time covered in the last day, so MAG 7 speaks Tesla
     only at company level and never re-tells TST's product and community
     stories.
Plus the show's narrative memory. Every step is non-fatal.

The earnings calendar the first episodes carried is gone for the same
brief: dates weeks away are not news, and seven yfinance calls spent a
third of the 60-second pre_fetch budget on them.
"""

from __future__ import annotations

import logging
from pathlib import Path

from engine import show_memory
from engine.market_quotes import fetch_daily_closes, persist, tape_block
from engine.sibling_coverage import sibling_block

logger = logging.getLogger(__name__)

_SLUG = "mag7"
_ROOT = Path(__file__).resolve().parent.parent.parent
# NOT api/mag7.json: generate_html writes the per-show public episode API to
# api/<slug>.json for every registry show, and the two files collided on the
# first live run (2026-09-22) — the finalize job committed the episode API as
# api/mag7.json while this cache sat untracked on the show runner, and every
# rebase of the episode commit aborted on "untracked working tree file would
# be overwritten". The episode went to a recovery PR instead of main.
CACHE_PATH = _ROOT / "api" / "mag7_quotes.json"

#: The seven, in the show's fixed order. Alphabet trades as GOOGL and GOOG;
#: the tape carries GOOGL (the two classes move together) and the show copy
#: names both.
TICKERS = ("GOOGL", "AMZN", "AAPL", "META", "MSFT", "NVDA", "TSLA")
NAMES = {
    "GOOGL": "Alphabet", "AMZN": "Amazon", "AAPL": "Apple", "META": "Meta",
    "MSFT": "Microsoft", "NVDA": "NVIDIA", "TSLA": "Tesla",
}

_TST_LENS = (
    "MAG 7 covers Tesla only as a company — capital, regulation, deals and "
    "stories that run across several of the seven — and leaves products, "
    "FSD, energy and community to Tesla Shorts Time."
)


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    context = show_memory.memory_pre_fetch(config, _SLUG)
    parts = []
    try:
        quotes = fetch_daily_closes(TICKERS, cache_path=CACHE_PATH)
        # A --test run must not rewrite the public cache (NERRA_HOOKS_READONLY).
        import os
        if os.environ.get("NERRA_HOOKS_READONLY", "").strip() != "1":
            persist(quotes, CACHE_PATH)
        parts.append(tape_block(quotes, NAMES, TICKERS))
    except Exception as exc:  # noqa: BLE001
        logger.warning("mag7 tape failed (non-fatal): %s", exc)
        parts.append(tape_block([], NAMES, TICKERS))
    try:
        sib = sibling_block("Tesla Shorts Time", "digests/tesla_shorts_time",
                            days=1, lens=_TST_LENS)
        if sib:
            parts.append(sib)
    except Exception as exc:  # noqa: BLE001
        logger.warning("mag7 sibling block failed (non-fatal): %s", exc)
    context["hook_context"] = "\n\n".join(p for p in parts if p)
    return context


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    show_memory.memory_post_generate(config, _SLUG, digest_text or "", episode_num or 0)
