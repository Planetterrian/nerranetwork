"""Modern Investing Techniques pre-fetch and post-generation hooks.

Provides:
- Market index data (S&P 500, NASDAQ, TSX) for digest context
- Yesterday's simulated trade evaluation using real market data
- Running portfolio performance stats
- Post-generation trade extraction from the generated digest
"""

from __future__ import annotations

import datetime
import json
import logging
import math
import os
import re
import uuid
from pathlib import Path


def _finite(value, default=0.0):
    """Return *value* if it's a finite number, else *default*.

    yfinance occasionally returns ``float('nan')`` instead of ``None``
    (a NaN close on a halted/delisted bar). NaN is truthy, passes
    ``is None`` checks, and poisons every downstream sum — two trades
    closed with NaN exits (DELL, HIMS) turned the tracker's
    ``cumulative_pnl`` into NaN for weeks and put "Running Total: $nan"
    on air (June 2026 review). Every aggregation in this module now
    routes numbers through this guard.
    """
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    return default

logger = logging.getLogger(__name__)


def _hooks_readonly() -> bool:
    """True when the runner asked hooks not to persist state.

    ``run_show.py`` sets ``NERRA_HOOKS_READONLY=1`` for ``--test`` and
    ``--rehearse`` runs (July 2026 review): previously a ``--test`` run —
    the exact command the review playbook tells agents to execute —
    appended a REAL trade to the tracker via post_generate (which runs
    before the test-mode early exit) and pre_fetch closed/stamped open
    trades. Test invocations must never mutate the live track record.
    """
    return os.environ.get("NERRA_HOOKS_READONLY", "").strip() == "1"


TRACKER_FILENAME = "investment_tracker.json"
TAUGHT_LESSONS_FILENAME = "taught_lessons.json"
LESSONS_LEARNED_FILENAME = "lessons_learned.json"
MONTHLY_EPISODES_FILENAME = "monthly_episodes.json"
NASDAQ_SYMBOL = "^IXIC"

# Multi-index benchmarking (July 2026 "beat all major indices" pass).
# ^IXIC stays THE headline benchmark (the show's identity and every legacy
# field); the other two majors are scored over the same matched windows so
# the show can honestly say how many of the three it is beating.
BENCHMARK_INDICES = {
    "nasdaq": "^IXIC",
    "sp500": "^GSPC",
    "tsx": "^GSPTSE",
}
BENCHMARK_LABELS = {
    "nasdaq": "NASDAQ Composite",
    "sp500": "S&P 500",
    "tsx": "TSX Composite",
}

# Sector vocabulary — canonical tags used across tracker, taught_lessons,
# lessons_learned, and the dashboard. Keep this list in sync with
# ``_SECTOR_BY_SYMBOL`` below and the digest prompt's required
# ``**Sector:**`` field.
SECTOR_TAGS = (
    "precious_metals",
    "energy",
    "tech",
    "financials",
    "healthcare",
    "consumer",
    "crypto",
    "industrials",
    "utilities",
    "other",
)

# Direct symbol -> sector lookup for tickers that have appeared (or are
# likely to appear) in the Practice Investment segment. Fallback is
# keyword-matched against the strategy text in ``_classify_sector``.
_SECTOR_BY_SYMBOL = {
    # Precious metals / mining
    "LGD": "precious_metals", "FSM": "precious_metals", "SSRM": "precious_metals",
    "WRLG": "precious_metals", "AEM": "precious_metals", "ABX": "precious_metals",
    "GOLD": "precious_metals", "NEM": "precious_metals", "FNV": "precious_metals",
    "WPM": "precious_metals", "K": "precious_metals",
    # Energy
    "XOM": "energy", "CVX": "energy", "CNQ": "energy", "SU": "energy",
    "ENB": "energy", "TRP": "energy", "IMO": "energy", "CVE": "energy",
    # Tech / semis / cloud
    "WDC": "tech", "SSNLF": "tech", "TMUS": "tech", "AAPL": "tech",
    "MSFT": "tech", "GOOGL": "tech", "META": "tech", "NVDA": "tech",
    "AMD": "tech", "TSM": "tech", "AVGO": "tech", "ORCL": "tech",
    "CRM": "tech", "INTC": "tech", "MU": "tech", "SHOP": "tech",
    # Financials
    "SOFI": "financials", "JPM": "financials", "BAC": "financials",
    "RY": "financials", "TD": "financials", "BMO": "financials",
    "BNS": "financials", "CM": "financials", "MFC": "financials",
    "SLF": "financials",
    # Consumer
    "TSLA": "consumer", "LCID": "consumer", "LUCID": "consumer",
    "SWGAY": "consumer", "AMZN": "consumer", "COST": "consumer",
    "WMT": "consumer", "L": "consumer",
    # Crypto
    "BTC-USD": "crypto", "ETH-USD": "crypto", "COIN": "crypto",
    "MARA": "crypto", "HUT": "crypto",
    # Healthcare
    "JNJ": "healthcare", "PFE": "healthcare", "LLY": "healthcare",
    "MRK": "healthcare", "ABBV": "healthcare",
    # Industrials / utilities
    "CAT": "industrials", "CNR": "industrials", "CP": "industrials",
    "FTS": "utilities", "EMA": "utilities", "H": "utilities",
}

# Lesson-tag vocabulary — paired with the digest prompt's required
# ``**Lesson Tags:**`` field. When the digest is parsed post-generation,
# ``_extract_lesson_tags`` pulls any of these strings and ``taught_lessons.json``
# is updated. Adding a new tag requires updating this list AND the prompt.
LESSON_VOCABULARY = (
    "bid_ask_spread",
    "order_flow_slippage",
    "sector_rotation",
    "sector_concentration",
    "risk_management",
    "position_sizing",
    "tax_loss_harvesting",
    "tfsa_rrsp_mechanics",
    "momentum_entry",
    "mean_reversion",
    "catalyst_confirmation",
    "catalyst_fade",
    "earnings_surprise",
    "technical_breakout",
    "technical_support",
    "valuation_discipline",
    "macro_rotation",
    "geopolitical_premium",
    "insider_buying",
    "analyst_upgrade",
    "activist_defense",
    "dividend_compounding",
    "dollar_cost_averaging",
    "covered_call",
    "fx_hedging",
    "portfolio_rebalancing",
)


def pre_fetch(config, *, episode_num: int | None = None, today_str: str | None = None) -> dict:
    """Return extra template variables for the Modern Investing digest/podcast prompts.

    Called by ``run_show.py`` before digest generation.  Returns a dict
    that gets merged into the prompt template variables.
    """
    context: dict = {}

    output_dir = Path(config.episode.output_dir)
    tracker_path = output_dir / TRACKER_FILENAME

    # Load tracker
    tracker = _load_tracker(tracker_path)

    readonly = _hooks_readonly()
    if readonly:
        logger.info(
            "Hooks are read-only (test/rehearse run) — skipping trade "
            "evaluation and all tracker writes."
        )
    else:
        # Evaluate yesterday's open trade (if any)
        _evaluate_open_trade(tracker, tracker_path)

    # Build yesterday's trade review text. This may stamp
    # ``reviewed_in_episode`` on the latest closed trade (double-review
    # guard) — persist it immediately so a later benchmark-refresh failure
    # can't lose the stamp and re-review the same trade next episode.
    context["yesterday_trade_review"] = _build_trade_review(tracker, episode_num)
    if not readonly:
        _save_tracker(tracker, tracker_path)

    # Build portfolio summary
    context["portfolio_summary"] = _build_portfolio_summary(tracker)

    # Fetch market indices
    context["market_indices"] = _fetch_market_indices()

    # Refresh NASDAQ benchmark state (inception/YTD/current close + alpha)
    # and expose a prompt-ready block. Save immediately so the dashboard
    # aggregator and the website always read a fresh ``benchmark`` block.
    try:
        _compute_benchmark_state(tracker)
        tracker["sectors"] = _compute_sector_exposure(tracker)
        if not readonly:
            _save_tracker(tracker, tracker_path)
    except Exception as exc:
        logger.warning("Benchmark state refresh failed: %s", exc)
    context["benchmark_state"] = _build_benchmark_block(tracker)

    # Taught-lessons repetition guard, sector warning, lessons-learned
    # ledger, narrative callback — all new prompt template vars.
    taught_path = output_dir / TAUGHT_LESSONS_FILENAME
    lessons_path = output_dir / LESSONS_LEARNED_FILENAME
    taught = _load_taught_lessons(taught_path)
    lessons = _load_lessons_learned(lessons_path)
    context["taught_lessons_block"] = _build_taught_lessons_block(taught)
    context["sector_warning"] = _build_sector_warning_block(tracker)
    lessons_block = _build_lessons_learned_block(lessons)
    scoreboard = _build_rule_scoreboard(lessons, tracker)
    if scoreboard:
        lessons_block = f"{lessons_block}\n\n{scoreboard}"
    context["lessons_learned_block"] = lessons_block
    context["narrative_callback"] = _build_narrative_callback(tracker)

    # Evergreen deep-dive rotation — surfaces the previously-unused
    # segment library (shows/segments/modern_investing.json) so the show
    # rotates through 30 pre-written deep dives even when news is thin.
    library_path = _resolve_segment_library(config)
    segment_id, segment_hint = _pick_deep_dive_segment(tracker, library_path)
    context["deep_dive_hint"] = _build_deep_dive_hint_block(segment_hint)
    if segment_id and not readonly:
        _record_segment_used(tracker, segment_id)
        _save_tracker(tracker, tracker_path)

    # Recent strategies for freshness enforcement
    closed_trades = [t for t in tracker["trades"] if t.get("status") == "closed"]
    recent = closed_trades[-5:] if closed_trades else []
    if recent:
        lines = [f"- Ep{t.get('episode_num', '?')}: {t.get('symbol', '?')} ({t.get('strategy', 'unknown')})" for t in recent]
        context["recent_strategies"] = "\n".join(lines)
    else:
        context["recent_strategies"] = "No previous trades yet — this may be the first episode."

    # Strategy-level performance analysis — tells the LLM which approaches
    # are producing alpha and which are underperforming, so it can refine
    # future trade selection. The regime check (rolling streak + drawdown
    # → selection pressure) rides in the same prompt slot.
    strategy_block = _build_strategy_performance(tracker)
    regime = _build_regime_block(tracker)
    if regime:
        strategy_block = f"{strategy_block}\n\n{regime}"
    context["strategy_performance"] = strategy_block

    # Dynamic tone based on portfolio performance
    context["tone_hint"] = _tone_from_portfolio(tracker)

    # === Strong Recursive Learning Loop (core of NASDAQ outperformance goal) ===
    try:
        context["mit_recursive_learning_context"] = get_mit_recursive_learning_context()
        context["mit_operating_principles"] = _derive_operating_principles(tracker)
        context["mit_confidence_calibration"] = get_mit_confidence_calibration(tracker)
    except Exception as exc:
        logger.warning("Failed to build recursive learning context: %s", exc)
        context["mit_recursive_learning_context"] = "Learning context temporarily unavailable — focus on process discipline."

    return context


_MIN_SAMPLE_TRADES = 5


def _build_strategy_performance(tracker: dict) -> str:
    """Analyze win/loss patterns by strategy keyword and sector.

    Produces a prompt block that shows the LLM which types of trades
    are generating alpha and which are dragging performance, so it can
    adjust future picks toward proven approaches.
    """
    closed = [t for t in tracker.get("trades", []) if t.get("status") == "closed" and t.get("pnl_pct") is not None]
    if len(closed) < 3:
        return "Not enough closed trades to analyze strategy patterns yet."

    # Sector performance
    sector_stats: dict = {}
    for t in closed:
        sec = t.get("sector", "other")
        if sec not in sector_stats:
            sector_stats[sec] = {"trades": 0, "wins": 0, "total_pnl": 0.0, "total_alpha": 0.0}
        sector_stats[sec]["trades"] += 1
        sector_stats[sec]["total_pnl"] += t.get("pnl_pct", 0.0)
        sector_stats[sec]["total_alpha"] += t.get("alpha_pct", 0.0)
        if t.get("pnl_pct", 0) > 0:
            sector_stats[sec]["wins"] += 1

    # Lesson tag effectiveness
    tag_stats: dict = {}
    for t in closed:
        for tag in t.get("lesson_tags", []):
            if tag not in tag_stats:
                tag_stats[tag] = {"trades": 0, "wins": 0, "total_alpha": 0.0}
            tag_stats[tag]["trades"] += 1
            tag_stats[tag]["total_alpha"] += t.get("alpha_pct", 0.0)
            if t.get("pnl_pct", 0) > 0:
                tag_stats[tag]["wins"] += 1

    # Best and worst
    best = max(closed, key=lambda t: t.get("alpha_pct", 0))
    worst = min(closed, key=lambda t: t.get("alpha_pct", 0))

    lines = ["STRATEGY PERFORMANCE ANALYSIS (use this to improve trade selection):"]

    # Sector breakdown. Statistical discipline (July 2026): a ✓/✗ verdict
    # on 2-3 trades is noise-chasing — the loop was steering picks off
    # coin-flip samples. Verdict flags require n >= _MIN_SAMPLE_TRADES;
    # smaller samples are shown but explicitly labeled inconclusive.
    lines.append("\nSector results (closed trades):")
    for sec, s in sorted(sector_stats.items(), key=lambda x: x[1]["total_alpha"], reverse=True):
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0
        avg_alpha = s["total_alpha"] / s["trades"] if s["trades"] > 0 else 0
        if s["trades"] >= _MIN_SAMPLE_TRADES:
            flag = "✓" if avg_alpha > 0 else "✗"
            suffix = ""
        else:
            flag = "·"
            suffix = (f" [n={s['trades']} — insufficient sample, "
                      f"no conclusion]")
        lines.append(
            f"  {flag} {sec}: {s['trades']} trades, {wr:.0f}% win rate, "
            f"avg alpha {avg_alpha:+.2f}%{suffix}")

    # Lesson tag patterns
    if tag_stats:
        lines.append("\nStrategy tag results:")
        for tag, s in sorted(tag_stats.items(), key=lambda x: x[1]["total_alpha"], reverse=True)[:8]:
            avg_alpha = s["total_alpha"] / s["trades"] if s["trades"] > 0 else 0
            lines.append(f"  {tag}: {s['trades']} trades, avg alpha {avg_alpha:+.2f}%")

    # Best and worst
    lines.append(f"\nBest trade: {best.get('symbol')} ({best.get('sector')}) — alpha {best.get('alpha_pct', 0):+.2f}%")
    lines.append(f"Worst trade: {worst.get('symbol')} ({worst.get('sector')}) — alpha {worst.get('alpha_pct', 0):+.2f}%")

    # Actionable guidance — FAVOR/AVOID only on samples big enough to
    # mean something (n >= _MIN_SAMPLE_TRADES; was 2, i.e. coin flips).
    winning_sectors = [
        sec for sec, s in sector_stats.items()
        if s["total_alpha"] > 0 and s["trades"] >= _MIN_SAMPLE_TRADES]
    losing_sectors = [
        sec for sec, s in sector_stats.items()
        if s["total_alpha"] < 0 and s["trades"] >= _MIN_SAMPLE_TRADES]
    if winning_sectors:
        lines.append(f"\nFAVOR these sectors (positive alpha track record): {', '.join(winning_sectors)}")
    if losing_sectors:
        lines.append(f"AVOID OR BE CAUTIOUS with these sectors (negative alpha): {', '.join(losing_sectors)}")
    if not winning_sectors and not losing_sectors:
        lines.append(
            "\nNo sector has a large enough sample for FAVOR/AVOID guidance "
            "yet — judge today's pick on its own merits.")

    return "\n".join(lines)


_REGIME_WINDOW = 10


def _build_regime_block(tracker: dict) -> str:
    """Adaptive selectivity from the rolling record (July 2026).

    The loop previously treated every day identically regardless of how
    the last stretch of picks performed. This block turns the rolling
    last-``_REGIME_WINDOW`` matched-window alpha + the drawdown from the
    P&L high-water mark into explicit selection pressure: a cold streak
    RAISES the bar (prefer explicit no-trade days, demand more aligned
    factors); a hot streak holds discipline flat (never "press harder").
    Deterministic — thresholds are code, not vibes.
    """
    closed = [t for t in tracker.get("trades", []) if t.get("status") == "closed"]
    scored = [
        t for t in closed
        if isinstance(t.get("alpha_pct"), (int, float))
        and math.isfinite(t["alpha_pct"])
    ]
    if len(scored) < 5:
        return ""
    recent = scored[-_REGIME_WINDOW:]
    avg_alpha = sum(t["alpha_pct"] for t in recent) / len(recent)
    wins = sum(1 for t in recent if _finite(t.get("pnl_pct")) > 0)

    # Drawdown from the cumulative-P&L high-water mark (all closed trades).
    running = peak = 0.0
    for t in closed:
        running += _finite(t.get("pnl_dollars"))
        peak = max(peak, running)
    drawdown = round(peak - running, 2)

    header = (
        f"REGIME CHECK (rolling last {len(recent)} closed trades): "
        f"avg matched-window alpha {avg_alpha:+.2f}%, {wins}/{len(recent)} "
        f"wins, ${drawdown:.2f} below the P&L high-water mark."
    )
    if avg_alpha < -0.5 or drawdown > 100:
        guidance = (
            " COLD STREAK — RAISE THE BAR for today's Practice Investment: "
            "an explicit no-trade day is the DEFAULT unless a setup has 3+ "
            "independent aligned factors (which also justifies High "
            "confidence). Do not chase a comeback; smaller, clearer edges "
            "only."
        )
    elif avg_alpha > 1.0:
        guidance = (
            " HOT STREAK — the process is working. Keep the SAME selection "
            "bar and position discipline; do not loosen criteria or reach "
            "for riskier names because recent picks worked."
        )
    else:
        guidance = (
            " NEUTRAL — apply the standard selection criteria; no-trade "
            "days remain acceptable."
        )
    return header + guidance


def _tone_from_portfolio(tracker: dict) -> str:
    """Return a tone hint based on recent portfolio performance."""
    summary = tracker.get("summary", {})
    streak = summary.get("current_streak", 0)
    cum_pnl = summary.get("cumulative_pnl", 0)
    total = summary.get("total_trades", 0)

    if total == 0:
        return "enthusiastic and welcoming — this is early days, set the foundation"
    if streak >= 3:
        return "momentum is building — confident and energetic, but stay disciplined"
    if streak <= -2:
        return "learning week — reflective and analytical, focus on what the losses teach"
    if cum_pnl > 50:
        return "portfolio doing well — upbeat but measured, credit the process not luck"
    if cum_pnl < -30:
        return "drawdown mode — humble and educational, remind listeners this is learning"
    return "steady progress — balanced and conversational"


def pronunciation_overrides() -> dict:
    """Return financial-term pronunciation fixes for ElevenLabs TTS."""
    return {
        "extra_acronyms": {
            "ETF": "E T F",
            "TFSA": "T F S A",
            "RRSP": "R R S P",
            "FHSA": "F H S A",
            "RESP": "R E S P",
            "RSI": "R S I",
            "MACD": "mac dee",
            "P/E": "P E",
            "EPS": "E P S",
            "IPO": "I P O",
            "NYSE": "N Y S E",
            "TSX": "T S X",
            "SPY": "S P Y",
            "QQQ": "Q Q Q",
            "VFV": "V F V",
            "VOO": "V O O",
            "CAD": "C A D",
            "USD": "U S D",
            "ACB": "A C B",
            "DRIP": "D R I P",
            "GIC": "G I C",
            "VGRO": "V G R O",
            "XEQT": "X E Q T",
            # Common tickers discussed frequently
            "NVDA": "N V D A",
            "ARKK": "A R K K",
            "SCHD": "S C H D",
            # Canadian tickers
            "BCE": "B C E",
            "ENB": "E N B",
            "CNR": "C N R",
            # Financial terms
            "YTD": "year to date",
            "MoM": "month over month",
            "QoQ": "quarter over quarter",
            "BoC": "Bank of Canada",
            "FOMC": "F O M C",
            "AUM": "A U M",
            "DCA": "D C A",
            "MER": "M E R",
            "CRA": "C R A",
            "HELOC": "H E L O C",
            "ROI": "R O I",
            "PE": "P E",
            "NAV": "N A V",
            "ATH": "all time high",
            # Canadian ETFs/tickers
            "BTCC": "B T C C",
            "XGRO": "X G R O",
            "VEQT": "V E Q T",
            "XIU": "X I U",
            "ZSP": "Z S P",
            "HXT": "H X T",
        },
        "extra_words": {
            "robo-advisor": "robo advisor",
            "fintech": "fin tech",
            "bps": "basis points",
        },
    }


def post_generate(config, *, digest_text: str = "", episode_num: int | None = None) -> None:
    """Extract today's Practice Investment pick from the generated digest.

    Called by ``run_show.py`` after digest generation.  Parses the pick
    and saves it as an open trade in the tracker for next-day evaluation.
    """
    if _hooks_readonly():
        logger.info(
            "Hooks are read-only (test/rehearse run) — NOT recording the "
            "Practice Investment pick or lesson state."
        )
        return

    output_dir = Path(config.episode.output_dir)
    tracker_path = output_dir / TRACKER_FILENAME

    tracker = _load_tracker(tracker_path)

    trade = _extract_trade_from_digest(digest_text, episode_num)
    if trade:
        # Always stamp sector from the symbol/strategy even if the prompt
        # didn't produce a **Sector:** line yet. Keeps the dashboard clean.
        if not trade.get("sector"):
            trade["sector"] = _classify_sector(
                trade.get("symbol", ""), trade.get("strategy", ""), trade.get("market", ""),
            )
        # Rule-effectiveness stamping (July 2026): record which
        # recursive-improvement rules were shown to the model when it made
        # this pick. Read BEFORE today's lesson is appended below, so the
        # stamp reflects exactly the pick-day prompt. The rule scoreboard
        # scores these stamps once trades close.
        try:
            pick_day_lessons = _load_lessons_learned(
                output_dir / LESSONS_LEARNED_FILENAME)
            trade["rules_in_effect"] = [
                e["id"] for e in _selected_active_rules(pick_day_lessons)
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("rules_in_effect stamping failed: %s", exc)
        # Pick-time validation probe: resolve the Yahoo symbol (TSX picks
        # get their .TO/.V listing) and record a reference price so a
        # wrong-instrument resolution is caught at close (Ep50 CNR class).
        # Best-effort — a probe failure is loud but never blocks the pick.
        try:
            _probe_pick(trade)
        except Exception as exc:
            logger.warning("Pick validation probe failed for %s: %s", trade.get("symbol"), exc)
        tracker["trades"].append(trade)
        tracker["metadata"]["last_updated"] = datetime.date.today().isoformat()
        tracker["sectors"] = _compute_sector_exposure(tracker)
        _save_tracker(tracker, tracker_path)
        logger.info(
            "Recorded trade pick: %s (%s, sector=%s) — confidence: %s",
            trade["symbol"], trade["strategy"], trade.get("sector"), trade["confidence"],
        )
    else:
        logger.warning("Could not extract Practice Investment pick from digest")

    # Execution bridge (July 2026 live-trading prep): emit a
    # machine-readable trade signal for the (future, isolated) SnapTrade
    # execution layer. The executor consumes THIS artifact — never the
    # digest prose — so LLM formatting drift can't reach an order ticket.
    # Best-effort: a signal-write failure must never block the pipeline.
    try:
        _write_trade_signal(output_dir, trade, digest_text, episode_num, tracker)
    except Exception as exc:
        logger.warning("Trade-signal write failed (non-fatal): %s", exc)

    # Repetition guard: record whichever lesson tags the digest taught.
    taught_path = output_dir / TAUGHT_LESSONS_FILENAME
    taught = _load_taught_lessons(taught_path)
    tags = _extract_lesson_tags(digest_text)
    if tags:
        _record_taught_lessons(taught, tags, episode_num)
        _save_taught_lessons(taught, taught_path)
        logger.info("Recorded taught lesson tags: %s", ", ".join(tags))

    # Recursive improvement ledger: append a new entry ONLY if the digest
    # emitted a structured "Lesson Learned ... Rule: ..." block.
    lessons_path = output_dir / LESSONS_LEARNED_FILENAME
    extracted = _extract_lesson_learned_from_digest(digest_text)
    if extracted:
        observation, adjustment = extracted
        lessons = _load_lessons_learned(lessons_path)
        entry = _append_lesson_learned(
            lessons,
            observation=observation,
            adjustment=adjustment,
            episode_num=episode_num,
            source="post_generate",
            category="content",
        )
        _save_lessons_learned(lessons, lessons_path)
        logger.info("Appended lesson_learned %s: %s", entry["id"], entry["observation"][:80])


# ---------------------------------------------------------------------------
# Internal helpers — tracker I/O
# ---------------------------------------------------------------------------

def _load_tracker(tracker_path: Path) -> dict:
    """Load the investment tracker JSON, or return a fresh one.

    Older trackers that predate the NASDAQ-benchmark / sector / alpha
    schema are upgraded in-place with safe defaults the first time they
    are read, so existing files keep working without a manual migration.
    """
    if tracker_path.exists():
        try:
            tracker = json.loads(tracker_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load tracker: %s — starting fresh", exc)
            tracker = _fresh_tracker()
        else:
            _ensure_schema(tracker)
            return tracker
    else:
        tracker = _fresh_tracker()
    return tracker


def _fresh_tracker() -> dict:
    today_iso = datetime.date.today().isoformat()
    return {
        "metadata": {
            "show": "Modern Investing Techniques",
            "description": "Simulated trade performance tracker",
            "disclaimer": "All trades are simulated for educational purposes only.",
            "position_size": 1000,
            "currency": "USD",
            "created": today_iso,
            "last_updated": today_iso,
            "inception_date": today_iso,
            "benchmark_symbol": NASDAQ_SYMBOL,
            "nasdaq_inception_close": None,
            "nasdaq_ytd_start_close": None,
            "nasdaq_ytd_year": datetime.date.today().year,
        },
        "summary": {
            "total_trades": 0, "wins": 0, "losses": 0, "breakeven": 0,
            "win_rate_pct": 0.0, "cumulative_pnl": 0.0,
            "best_trade_pct": 0.0, "worst_trade_pct": 0.0,
            "average_return_pct": 0.0,
            "current_streak": 0, "longest_win_streak": 0, "longest_loss_streak": 0,
        },
        "benchmark": {
            "current_close": None,
            "inception_to_date_pct": 0.0,
            "ytd_pct": 0.0,
            "last_updated": today_iso,
        },
        "alpha": {
            "inception_to_date_pct": 0.0,
            "ytd_pct": 0.0,
            "monthly": {},
        },
        "sectors": {},
        "monthly_snapshots": [],
        "trades": [],
    }


def _ensure_schema(tracker: dict) -> None:
    """Upgrade an older tracker dict in-place to the current schema."""
    today_iso = datetime.date.today().isoformat()
    meta = tracker.setdefault("metadata", {})
    meta.setdefault("inception_date", meta.get("created", today_iso))
    meta.setdefault("benchmark_symbol", NASDAQ_SYMBOL)
    meta.setdefault("nasdaq_inception_close", None)
    meta.setdefault("nasdaq_ytd_start_close", None)
    meta.setdefault("nasdaq_ytd_year", datetime.date.today().year)
    tracker.setdefault("benchmark", {
        "current_close": None,
        "inception_to_date_pct": 0.0,
        "ytd_pct": 0.0,
        "last_updated": today_iso,
    })
    tracker.setdefault("alpha", {
        "inception_to_date_pct": 0.0,
        "ytd_pct": 0.0,
        "monthly": {},
    })
    tracker.setdefault("sectors", {})
    tracker.setdefault("monthly_snapshots", [])
    tracker.setdefault("trades", [])
    _void_nonfinite_closed_trades(tracker)


def _void_nonfinite_closed_trades(tracker: dict) -> None:
    """Self-healing migration: a CLOSED trade with a non-finite P&L or
    exit price is a data failure, not a market outcome — void it.

    July 2026 follow-up: the phantom-trade fix voided the four
    null-price closes (XLF/KO/ROKU/ION) but MISSED the two NaN-exit
    closes (DELL Ep57, HIMS Ep63), which stayed ``status: closed`` with
    ``pnl_pct: NaN`` — ``_finite()`` coerced them to 0.0 in every
    aggregate, so 2 of the 3 spoken "breakeven" trades were still data
    failures narrated as market results. Runs on every tracker load so
    the shape can never ship again.
    """
    changed = False
    for trade in tracker.get("trades", []):
        if trade.get("status") != "closed":
            continue
        pnl = trade.get("pnl_pct")
        exit_price = trade.get("exit_price")
        bad_pnl = not (isinstance(pnl, (int, float)) and math.isfinite(pnl))
        bad_exit = not (
            isinstance(exit_price, (int, float)) and math.isfinite(exit_price)
        )
        if bad_pnl or bad_exit:
            logger.warning(
                "Voiding closed trade %s (Ep%s): non-finite %s — data "
                "failure, not a market outcome",
                trade.get("symbol"), trade.get("episode_num"),
                "pnl" if bad_pnl else "exit price",
            )
            trade["status"] = "voided"
            trade["void_reason"] = "market_data_unavailable"
            trade["entry_price"] = None
            trade["exit_price"] = None
            trade["pnl_pct"] = None
            trade["pnl_dollars"] = None
            trade["alpha_pct"] = None
            trade["nasdaq_return_pct"] = None
            trade["lesson"] = (
                "Trade voided — market data was unavailable for evaluation."
            )
            changed = True
    if changed:
        _recompute_summary(tracker)


def _save_tracker(tracker: dict, tracker_path: Path) -> None:
    """Write tracker JSON atomically."""
    tracker_path.write_text(
        json.dumps(tracker, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Trade evaluation — uses yfinance for real market data
# ---------------------------------------------------------------------------

def _yf_symbol_candidates(symbol: str, market: str = "") -> list[str]:
    """Yahoo Finance symbols to try, exchange-suffixed first for Canadian picks.

    July 2026 review: Ep50 picked "CNR — Canadian National Railway
    (TSX:CNR)" but the bare symbol was handed to yfinance, which resolved
    "CNR" to Core Natural Resources on the NYSE — the sim booked +8.66%
    on the WRONG COMPANY. For TSX picks the ``.TO`` listing must be tried
    first (``.V`` for TSX-V), falling back to the bare symbol only for
    dual-listed names where the suffixed lookup fails.
    """
    sym = (symbol or "").upper().strip()
    if not sym:
        return []
    m = (market or "").upper().replace("_", "-").strip()
    if m in ("TSX-V", "TSXV"):
        return [f"{sym}.V", f"{sym}.TO", sym]
    if m == "TSX":
        return [f"{sym}.TO", sym]
    return [sym]


def _trade_symbol_candidates(trade: dict) -> list[str]:
    """Candidates for an existing trade — a pick-time resolution wins."""
    resolved = trade.get("resolved_symbol")
    if resolved:
        return [resolved]
    return _yf_symbol_candidates(trade.get("symbol", ""), trade.get("market", ""))


def _bars_from_history(hist) -> list[tuple[datetime.date, float, float]]:
    """Convert a yfinance history frame to ``[(bar_date, open, close)]``.

    Bars with a non-finite open or close are dropped — yfinance returns
    NaN floats for halted/missing bars (the DELL/HIMS shape) and a NaN
    must never become an entry or exit price.
    """
    bars: list[tuple[datetime.date, float, float]] = []
    if hist is None or getattr(hist, "empty", True):
        return bars
    for idx, row in hist.iterrows():
        try:
            open_ = float(row["Open"])
            close = float(row["Close"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(open_) and math.isfinite(close)):
            continue
        bar_date = idx.date() if hasattr(idx, "date") else idx
        bars.append((bar_date, open_, close))
    return bars


def _fetch_history_bars(
    yf_symbol: str, *, period: str = "15d", attempts: int = 3,
) -> list[tuple[datetime.date, float, float]] | None:
    """Fetch daily bars for *yf_symbol* with retries.

    Returns a list of ``(date, open, close)`` bars (possibly empty when
    Yahoo knows the symbol but has no data), or ``None`` on total
    network/API failure.
    """
    import time as _time

    for attempt in range(attempts):
        try:
            import yfinance as yf
            hist = yf.Ticker(yf_symbol).history(period=period, interval="1d")
            return _bars_from_history(hist)
        except Exception as exc:
            logger.warning(
                "yfinance attempt %d for %s failed: %s", attempt + 1, yf_symbol, exc,
            )
        if attempt < attempts - 1:
            _time.sleep(2 ** (attempt + 1))
    return None


def _fetch_bars_for_trade(trade: dict, *, period: str = "15d") -> list | None:
    """Fetch bars for a trade, trying exchange-suffixed candidates in order.

    Stamps ``resolved_symbol`` on the trade with whichever candidate
    produced data, so subsequent snapshots/closes price the SAME listing.
    """
    for cand in _trade_symbol_candidates(trade):
        bars = _fetch_history_bars(cand, period=period)
        if bars:
            trade["resolved_symbol"] = cand
            return bars
    return None


def _probe_pick(trade: dict) -> bool:
    """Resolve the pick's Yahoo symbol at record time and store a reference.

    Stamps ``resolved_symbol`` (exchange-suffixed for TSX/TSX-V picks) and
    ``pick_reference_price`` (latest close) on the trade. Returns False —
    with a LOUD warning — when no candidate returns data, which almost
    always means the digest emitted a bogus or ambiguous ticker (Ep79
    "ION" voided at close; Ep50 "CNR" priced the wrong company for a
    week). Catching it on pick day gives the operator a same-day signal
    instead of a silent void or phantom result four days later.
    """
    candidates = _yf_symbol_candidates(trade.get("symbol", ""), trade.get("market", ""))
    for cand in candidates:
        bars = _fetch_history_bars(cand, period="5d", attempts=1)
        if bars:
            trade["resolved_symbol"] = cand
            trade["pick_reference_price"] = round(bars[-1][2], 2)
            logger.info(
                "Pick validated: %s → %s, reference close $%.2f",
                trade.get("symbol"), cand, trade["pick_reference_price"],
            )
            return True
    logger.warning(
        "PICK VALIDATION FAILED: no price data for %s (market=%s; tried %s) "
        "— the ticker may be bogus/ambiguous and the trade will likely void "
        "at close. Check today's digest.",
        trade.get("symbol"), trade.get("market"), ", ".join(candidates) or "nothing",
    )
    return False


TRADE_SIGNAL_LATEST_FILENAME = "trade_signal_latest.json"
TRADE_SIGNAL_SCHEMA_VERSION = 1

# uuid5 namespace for deterministic client_order_ids — SnapTrade's
# place-order endpoint accepts a caller-supplied ``client_order_id`` for
# idempotent placement, which protects a retried cron from double-buying.
_SIGNAL_ORDER_NAMESPACE = uuid.UUID("6d49f5a4-1a68-4f6e-9c7e-a1b2c3d4e5f6")


def _write_trade_signal(
    output_dir: Path,
    trade: dict | None,
    digest_text: str,
    episode_num: int | None,
    tracker: dict,
) -> None:
    """Write the per-episode machine-readable trade signal.

    July 2026 live-trading prep: the future SnapTrade execution layer (and
    the shadow-mode logger before it) must consume a schema-versioned
    artifact, not the digest markdown — the tracker has already lost real
    picks to LLM formatting drift, which is survivable for a sim and
    unacceptable for an order ticket. The signal is explicit about
    NO-trade days too, so the executor can distinguish "the show chose
    not to trade" from "the signal never arrived" (fail-closed either way).

    Fields are chosen for SnapTrade specifically:
    - ``snaptrade_symbol`` is the Yahoo-format symbol (``CNR.TO``) —
      SnapTrade's canonical symbology follows the Yahoo ticker format, so
      the tracker's resolved symbol maps 1:1;
    - ``currency``/``suggested_account`` route TSX picks to a CAD account
      (Wealthsimple) and US picks to a USD account (Webull) so no order
      eats a cross-currency conversion spread;
    - ``client_order_id`` is a deterministic uuid5 of
      (episode, symbol, date) for idempotent placement across cron
      retries.
    """
    today_iso = datetime.date.today().isoformat()
    signal: dict = {
        "schema_version": TRADE_SIGNAL_SCHEMA_VERSION,
        "generated_at": today_iso,
        "episode_num": episode_num,
        "show": "modern_investing",
        "simulated_position_size_usd": (
            tracker.get("metadata", {}).get("position_size", 1000)
        ),
    }

    if trade is None:
        explicit_no_trade = bool(
            digest_text
            and re.search(r"Today's Pick[:*\s]+No\b", digest_text, re.IGNORECASE)
        )
        signal["action"] = "no_trade"
        signal["reason"] = (
            "explicit_no_trade" if explicit_no_trade else "no_pick_extracted"
        )
        signal["trade"] = None
    else:
        symbol = trade.get("symbol", "")
        market = trade.get("market", "")
        resolved = trade.get("resolved_symbol")
        if not resolved:
            candidates = _yf_symbol_candidates(symbol, market)
            resolved = candidates[0] if candidates else symbol
        is_canadian = (market or "").upper().startswith("TSX")
        seed = f"mit-ep{episode_num or 0}-{symbol}-{trade.get('date', today_iso)}"
        signal["action"] = "new_trade"
        signal["reason"] = None
        signal["trade"] = {
            "symbol": symbol,
            "market": market,
            "snaptrade_symbol": resolved,
            "side": "BUY",
            "trade_type": trade.get("trade_type", "weekly"),
            "confidence": trade.get("confidence", "Unknown"),
            "strategy": trade.get("strategy", ""),
            "target_range": trade.get("target_range", ""),
            "sector": trade.get("sector", ""),
            "pick_date": trade.get("date", today_iso),
            "pick_reference_price": trade.get("pick_reference_price"),
            "pick_validated": bool(trade.get("pick_reference_price")),
            "currency": "CAD" if is_canadian else "USD",
            "suggested_account": "wealthsimple" if is_canadian else "webull",
            "client_order_id": str(uuid.uuid5(_SIGNAL_ORDER_NAMESPACE, seed)),
        }

    payload = json.dumps(signal, indent=2, ensure_ascii=False) + "\n"
    latest = output_dir / TRADE_SIGNAL_LATEST_FILENAME
    latest.write_text(payload, encoding="utf-8")
    if episode_num is not None:
        per_episode = output_dir / f"trade_signal_ep{episode_num:03d}.json"
        per_episode.write_text(payload, encoding="utf-8")
    logger.info(
        "Trade signal written: action=%s%s",
        signal["action"],
        f" {signal['trade']['snaptrade_symbol']}" if signal.get("trade") else "",
    )


def _pick_flash_bar(bars, pick_date):
    """The bar ON *pick_date*, else the FIRST bar after it — never before.

    July 2026 review: the old code took ``hist.iloc[-1]`` ("most recent
    completed trading day"), which silently priced the WRONG DAY whenever
    the cron ran late into market hours (a partial live bar) or the pick
    landed on a non-trading day (the prior day's bar — look-back
    contamination). Returns ``None`` when no bar on/after the pick date
    exists yet — the caller keeps the trade open instead of voiding.
    """
    if pick_date is None:
        return bars[-1] if bars else None
    for bar in bars:
        if bar[0] >= pick_date:
            return bar
    return None


def _pick_weekly_bars(bars, pick_date):
    """(entry_bar, exit_bar) for a weekly hold: first/last bar >= pick date.

    July 2026 review: the old code filtered to "this week's Monday", so a
    weekly hold picked mid-week was BACKDATED to Monday's open — the LLM
    picked with Mon-Wed price action already known and the sim booked
    gains it could never have captured (hindsight bias; e.g. Ep35 AMD
    picked Wednesday, credited from Monday's open, +13.36%). Entry now
    starts at the first bar on/after the pick date.
    """
    if pick_date is None:
        window = list(bars)
    else:
        window = [b for b in bars if b[0] >= pick_date]
    if not window:
        return None, None
    return window[0], window[-1]


def _trade_pick_date(trade: dict) -> datetime.date | None:
    d = trade.get("date")
    if isinstance(d, str):
        try:
            return datetime.date.fromisoformat(d)
        except ValueError:
            return None
    return None


def _evaluate_open_trade(tracker: dict, tracker_path: Path) -> None:
    """Evaluate open trades using the hybrid model.

    - **Weekly holds** are only closed on Fridays (weekday 4).
    - **Flash trades** (trade_type == "flash") are closed the next trading day.
    - On non-Friday weekdays, weekly holds get a mid-week price snapshot
      (stored as ``current_price``) but remain open.
    """
    open_trades = [t for t in tracker["trades"] if t.get("status") == "open"]
    if not open_trades:
        return

    today = datetime.date.today()
    is_friday = today.weekday() == 4  # Monday=0, Friday=4

    for trade in open_trades:
        symbol = trade.get("symbol", "")
        if not symbol:
            logger.warning("Open trade has no symbol — skipping evaluation")
            continue

        trade_type = trade.get("trade_type", "weekly")

        # Flash trades close the next day; weekly holds close on Friday only
        should_close = (trade_type == "flash") or is_friday

        if should_close:
            _close_trade(trade, tracker)
        else:
            # Mid-week snapshot for weekly holds
            _snapshot_trade(trade, symbol)

    # Recompute summary stats and save
    _recompute_summary(tracker)
    _maybe_record_monthly_snapshot(tracker, today)
    _save_tracker(tracker, tracker_path)


def _close_trade(trade: dict, tracker: dict) -> None:
    """Close a trade with real market data (pick-date-aligned bars)."""
    symbol = trade.get("symbol", "")
    trade_type = trade.get("trade_type", "weekly")
    pick_date = _trade_pick_date(trade)

    bars = _fetch_bars_for_trade(trade)

    entry_bar = exit_bar = None
    if bars:
        if trade_type == "flash":
            # Flash trade: the pick-date bar's open and close.
            entry_bar = exit_bar = _pick_flash_bar(bars, pick_date)
        else:
            # Weekly hold: first bar on/after the pick date → latest bar.
            entry_bar, exit_bar = _pick_weekly_bars(bars, pick_date)
        if entry_bar is None:
            # Data came back but no bar on/after the pick date exists yet
            # (e.g. a weekend pick evaluated before the next session).
            # Keep the trade open — voiding here would discard a real,
            # evaluable trade. If the pick is stale (halted/delisted right
            # after the pick), void instead of holding a zombie open.
            if pick_date and (datetime.date.today() - pick_date).days > 10:
                logger.warning(
                    "No trading data for %s in the 10 days since the %s pick "
                    "— voiding stale trade", symbol, pick_date,
                )
                trade["status"] = "voided"
                trade["void_reason"] = "no_trading_data_after_pick"
                trade["pnl_pct"] = None
                trade["pnl_dollars"] = None
                trade["lesson"] = "Trade voided — no trading data after the pick date."
                return
            logger.info(
                "No bar on/after %s for %s yet — leaving trade open",
                pick_date, symbol,
            )
            return

    if entry_bar is None or exit_bar is None:
        # VOID, don't breakeven-close (July 2026 review). Recording a
        # data-fetch failure as a $0.00 breakeven CLOSE lied twice: it
        # counted the phantom trade in the spoken record ("41 trades… 7
        # breakeven outcomes") AND let the trade-review/lookback narration
        # later present it as a real market outcome ("ROKU closed flat…
        # illustrates how announced deals require extended holding
        # periods"). A voided trade is excluded from every aggregation and
        # never narrated as a result — it only records that the sim could
        # not be evaluated. (Ep74 XLF / Ep75 KO / Ep77 ROKU / Ep79 ION,
        # plus the DELL/HIMS NaN-exit shape.)
        logger.warning("Could not fetch prices for %s — voiding trade (market data unavailable)", symbol)
        trade["status"] = "voided"
        trade["void_reason"] = "market_data_unavailable"
        trade["entry_price"] = None
        trade["exit_price"] = None
        trade["pnl_pct"] = None
        trade["pnl_dollars"] = None
        trade["lesson"] = "Trade voided — market data was unavailable for evaluation."
        return

    entry_date, entry_price, _ = entry_bar[0], entry_bar[1], entry_bar[2]
    exit_date, exit_price = exit_bar[0], exit_bar[2]

    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
    position_size = tracker["metadata"].get("position_size", 1000)
    pnl_dollars = round(position_size * (pnl_pct / 100), 2)

    trade["status"] = "closed"
    trade["entry_price"] = round(entry_price, 2)
    trade["exit_price"] = round(exit_price, 2)
    trade["entry_bar_date"] = entry_date.isoformat()
    trade["exit_bar_date"] = exit_date.isoformat()
    trade["pnl_pct"] = round(pnl_pct, 2)
    trade["pnl_dollars"] = round(pnl_dollars, 2)

    # Wrong-instrument tripwire: if the close-time entry price is wildly
    # far from the price observed when the pick was validated, the symbol
    # probably resolved to a different listing/company between pick and
    # close (the Ep50 CNR class). Flag loudly for the operator; do NOT
    # auto-void — a genuine halving/doubling is a real (instructive)
    # outcome that a human should adjudicate.
    ref = trade.get("pick_reference_price")
    if isinstance(ref, (int, float)) and math.isfinite(ref) and ref > 0:
        if abs(entry_price - ref) / ref > 0.5:
            trade["price_discontinuity"] = True
            logger.warning(
                "PRICE DISCONTINUITY for %s: entry $%.2f vs pick-time "
                "reference $%.2f (>50%% apart) — possible wrong-instrument "
                "pricing; review this trade before trusting its P&L",
                symbol, entry_price, ref,
            )

    # Annotate with NASDAQ benchmark alpha over the SAME bar window —
    # best-effort, tolerant of yfinance failures.
    try:
        _annotate_trade_with_nasdaq(trade, entry_date, exit_date)
    except Exception as exc:
        logger.warning("NASDAQ annotation failed for %s: %s", symbol, exc)

    # Backfill sector if post_generate never set it (e.g. old trades).
    if not trade.get("sector"):
        trade["sector"] = _classify_sector(
            symbol, trade.get("strategy", ""), trade.get("market", ""),
        )

    logger.info(
        "Evaluated %s (%s): entry=$%.2f (%s) exit=$%.2f (%s) pnl=%.2f%% alpha=%s",
        symbol, trade_type, entry_price, entry_date, exit_price, exit_date,
        pnl_pct, trade.get("alpha_pct"),
    )


def _snapshot_trade(trade: dict, symbol: str) -> None:
    """Take a mid-week price snapshot for a weekly hold (does not close it)."""
    try:
        bars = _fetch_bars_for_trade(trade, period="5d")
        if bars:
            trade["current_price"] = round(bars[-1][2], 2)
            logger.info("Mid-week snapshot %s: $%.2f", symbol, trade["current_price"])
    except Exception as exc:
        logger.warning("Mid-week snapshot failed for %s: %s", symbol, exc)


def _recompute_summary(tracker: dict) -> None:
    """Recompute summary statistics from all closed trades.

    Voided trades (``status == "voided"`` — a market-data-fetch failure,
    July 2026 review) are excluded here by the ``status == "closed"``
    filter, so they never inflate ``total_trades`` / ``breakeven`` or land
    in the spoken record.
    """
    closed = [t for t in tracker["trades"] if t.get("status") == "closed"]
    if not closed:
        return

    wins = sum(1 for t in closed if _finite(t.get("pnl_pct")) > 0)
    losses = sum(1 for t in closed if _finite(t.get("pnl_pct")) < 0)
    breakeven = len(closed) - wins - losses
    total = len(closed)
    cum_pnl = sum(_finite(t.get("pnl_dollars")) for t in closed)
    pnl_pcts = [_finite(t.get("pnl_pct")) for t in closed]
    # Cumulative alpha vs NASDAQ across trades that have it — THE show
    # metric (the intro promises NASDAQ outperformance) yet it was never
    # summarized; get_mit_recursive_learning_context read a key that
    # didn't exist and reported 0.0 forever (June 2026 review).
    alphas = [
        t["alpha_pct"] for t in closed
        if isinstance(t.get("alpha_pct"), (int, float))
        and math.isfinite(t["alpha_pct"])
    ]
    cum_alpha = sum(alphas)

    # Matched-window compounded score (July 2026 review): the honest
    # "are the picks beating the NASDAQ?" number. Compounds each
    # benchmarked trade's return against the index's return over the SAME
    # bar window. Distinct from BOTH the per-trade alpha sum above (an
    # additive approximation) and the buy-and-hold gap in the ``alpha``
    # block (which is not capital-matched — the sim holds one $1,000
    # position at a time while the index compounds fully-invested).
    comp_port = 1.0
    comp_ndq = 1.0
    n_matched = 0
    for t in closed:
        pnl = t.get("pnl_pct")
        ndq = t.get("nasdaq_return_pct")
        if (
            isinstance(pnl, (int, float)) and math.isfinite(pnl)
            and isinstance(ndq, (int, float)) and math.isfinite(ndq)
        ):
            comp_port *= 1 + pnl / 100
            comp_ndq *= 1 + ndq / 100
            n_matched += 1

    # Per-index matched-window scores (July 2026 multi-index pass): the
    # same compounding, one score per major index, so the show can state
    # "beating N of 3 major indices" with a defensible number. Legacy
    # trades that predate ``benchmark_returns`` fall back to the NASDAQ
    # field for that index only.
    def _finite_num(v):
        return isinstance(v, (int, float)) and math.isfinite(v)

    benchmark_scores: dict = {}
    for key in BENCHMARK_INDICES:
        comp_p = comp_i = 1.0
        n = 0
        for t in closed:
            pnl = t.get("pnl_pct")
            ret = (t.get("benchmark_returns") or {}).get(key)
            if key == "nasdaq" and ret is None:
                ret = t.get("nasdaq_return_pct")
            if _finite_num(pnl) and _finite_num(ret):
                comp_p *= 1 + pnl / 100
                comp_i *= 1 + ret / 100
                n += 1
        if n:
            benchmark_scores[key] = {
                "portfolio_pct": round((comp_p - 1) * 100, 2),
                "index_pct": round((comp_i - 1) * 100, 2),
                "alpha_pct": round((comp_p - comp_i) * 100, 2),
                "trades": n,
            }
    indices_beaten = sum(
        1 for v in benchmark_scores.values() if v["alpha_pct"] > 0)

    # Streak calculation
    current_streak = 0
    longest_win = 0
    longest_loss = 0
    streak = 0
    for t in closed:
        pnl = t.get("pnl_pct") or 0
        if pnl > 0:
            streak = streak + 1 if streak > 0 else 1
            longest_win = max(longest_win, streak)
        elif pnl < 0:
            streak = streak - 1 if streak < 0 else -1
            longest_loss = max(longest_loss, abs(streak))
        else:
            streak = 0
    current_streak = streak

    tracker["summary"] = {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
        "win_rate_pct": round((wins / total) * 100, 1) if total else 0.0,
        "cumulative_pnl": round(cum_pnl, 2),
        "best_trade_pct": round(max(pnl_pcts), 2) if pnl_pcts else 0.0,
        "worst_trade_pct": round(min(pnl_pcts), 2) if pnl_pcts else 0.0,
        "average_return_pct": round(sum(pnl_pcts) / len(pnl_pcts), 2) if pnl_pcts else 0.0,
        "cumulative_alpha_vs_nasdaq": round(cum_alpha, 2),
        "trades_with_alpha": len(alphas),
        "compounded_return_pct": round((comp_port - 1) * 100, 2),
        "compounded_nasdaq_matched_pct": round((comp_ndq - 1) * 100, 2),
        "matched_window_alpha_pct": round((comp_port - comp_ndq) * 100, 2),
        "matched_window_trades": n_matched,
        "benchmark_scores": benchmark_scores,
        "indices_beaten": indices_beaten,
        "indices_scored": len(benchmark_scores),
        "current_streak": current_streak,
        "longest_win_streak": longest_win,
        "longest_loss_streak": longest_loss,
    }


# ---------------------------------------------------------------------------
# Market index data
# ---------------------------------------------------------------------------

def _fetch_market_indices() -> str:
    """Fetch current S&P 500, NASDAQ, and TSX levels for context."""
    import time as _time

    indices = {
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ Composite",
        "^GSPTSE": "TSX Composite",
    }
    results = []

    for symbol, name in indices.items():
        for attempt in range(2):
            try:
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d", interval="1d")
                if not hist.empty:
                    close = float(hist["Close"].iloc[-1])
                    prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else close
                    change_pct = ((close - prev) / prev) * 100 if prev else 0
                    direction = "+" if change_pct >= 0 else ""
                    results.append(f"{name}: {close:,.0f} ({direction}{change_pct:.1f}%)")
                    break
            except Exception as exc:
                logger.warning("Index fetch %s attempt %d: %s", symbol, attempt + 1, exc)
                if attempt < 1:
                    _time.sleep(2)
        else:
            results.append(f"{name}: data unavailable")

    return " | ".join(results) if results else "Market index data temporarily unavailable"


# ---------------------------------------------------------------------------
# NASDAQ benchmark — fetch, alpha math, per-trade annotation
# ---------------------------------------------------------------------------

def _fetch_nasdaq_close(for_date: datetime.date | None = None) -> float | None:
    """Return the ^IXIC close for the given date (or most recent if None).

    Uses the same 3-retry pattern as ``_fetch_trade_prices``. Returns
    ``None`` on total failure — callers must tolerate missing data.
    """
    import time as _time
    for attempt in range(3):
        try:
            import yfinance as yf
            ticker = yf.Ticker(NASDAQ_SYMBOL)
            if for_date is None:
                hist = ticker.history(period="5d", interval="1d")
                if not hist.empty:
                    return float(hist["Close"].iloc[-1])
            else:
                start = for_date - datetime.timedelta(days=5)
                end = for_date + datetime.timedelta(days=1)
                hist = ticker.history(start=start.isoformat(), end=end.isoformat(), interval="1d")
                if not hist.empty:
                    # Pick the most recent close on or before ``for_date``.
                    mask = hist.index.date <= for_date
                    if mask.any():
                        return float(hist[mask]["Close"].iloc[-1])
                    return float(hist["Close"].iloc[-1])
        except Exception as exc:
            logger.warning("NASDAQ fetch attempt %d (%s): %s", attempt + 1, for_date, exc)
        if attempt < 2:
            _time.sleep(2 ** (attempt + 1))
    return None


def _portfolio_return_pct(tracker: dict) -> float:
    """Cumulative portfolio return as a percentage of total capital deployed.

    Treats every trade as ``position_size`` dollars of capital; divides
    summed P&L by (trades * position_size). Matches how listeners already
    hear the ``Running Total`` framed.
    """
    closed = [t for t in tracker.get("trades", []) if t.get("status") == "closed"]
    if not closed:
        return 0.0
    position = tracker.get("metadata", {}).get("position_size", 1000) or 1000
    total_pnl = sum(_finite(t.get("pnl_dollars")) for t in closed)
    capital = len(closed) * position
    return round((total_pnl / capital) * 100, 2) if capital else 0.0


def _portfolio_return_ytd_pct(tracker: dict) -> float:
    """Same as ``_portfolio_return_pct`` but filtered to trades closed this year."""
    this_year = datetime.date.today().year
    closed = [
        t for t in tracker.get("trades", [])
        if t.get("status") == "closed"
        and isinstance(t.get("date"), str)
        and t["date"][:4] == str(this_year)
    ]
    if not closed:
        return 0.0
    position = tracker.get("metadata", {}).get("position_size", 1000) or 1000
    total_pnl = sum(_finite(t.get("pnl_dollars")) for t in closed)
    capital = len(closed) * position
    return round((total_pnl / capital) * 100, 2) if capital else 0.0


def _compute_benchmark_state(tracker: dict) -> None:
    """Populate ``tracker['benchmark']`` and ``tracker['alpha']`` blocks.

    Mutates *tracker* in place. Refreshes the YTD baseline if the calendar
    year rolled over since the last run. Safe to call on every episode.
    """
    today = datetime.date.today()
    today_iso = today.isoformat()
    meta = tracker["metadata"]

    # Seed inception close if missing — this runs on day one or after an
    # operator-forced reset.
    if meta.get("nasdaq_inception_close") is None:
        inception = meta.get("inception_date") or meta.get("created") or today_iso
        try:
            inception_date = datetime.date.fromisoformat(inception)
        except ValueError:
            inception_date = today
        seeded = _fetch_nasdaq_close(inception_date)
        if seeded is not None:
            meta["nasdaq_inception_close"] = round(seeded, 2)

    # Refresh YTD baseline on Jan 2 rollover (or if missing).
    if meta.get("nasdaq_ytd_year") != today.year or meta.get("nasdaq_ytd_start_close") is None:
        ytd_anchor = datetime.date(today.year, 1, 2)
        ytd_close = _fetch_nasdaq_close(ytd_anchor)
        if ytd_close is not None:
            meta["nasdaq_ytd_start_close"] = round(ytd_close, 2)
            meta["nasdaq_ytd_year"] = today.year

    current_close = _fetch_nasdaq_close()

    benchmark = tracker.setdefault("benchmark", {})
    benchmark["current_close"] = round(current_close, 2) if current_close is not None else benchmark.get("current_close")
    benchmark["last_updated"] = today_iso

    inception_close = meta.get("nasdaq_inception_close")
    ytd_start = meta.get("nasdaq_ytd_start_close")
    ref_close = benchmark["current_close"]

    if ref_close is not None and inception_close:
        benchmark["inception_to_date_pct"] = round(((ref_close - inception_close) / inception_close) * 100, 2)
    if ref_close is not None and ytd_start:
        benchmark["ytd_pct"] = round(((ref_close - ytd_start) / ytd_start) * 100, 2)

    alpha = tracker.setdefault("alpha", {"monthly": {}})
    alpha["inception_to_date_pct"] = round(_portfolio_return_pct(tracker) - benchmark.get("inception_to_date_pct", 0.0), 2)
    alpha["ytd_pct"] = round(_portfolio_return_ytd_pct(tracker) - benchmark.get("ytd_pct", 0.0), 2)


def _matched_nasdaq_window(bars, entry_date, exit_date):
    """Return ``(entry_open, exit_close, entry_bar_date, exit_bar_date)``
    for the ^IXIC window matching a trade's actual bar window, or ``None``.

    Entry snaps FORWARD (bar on ``entry_date``, else the first bar after);
    exit snaps BACKWARD (bar on ``exit_date``, else the last bar before) —
    the window only ever shrinks inward, never expands past the trade.
    """
    if not bars or entry_date is None or exit_date is None:
        return None
    entry_bar = next((b for b in bars if b[0] >= entry_date), None)
    exit_bar = next((b for b in reversed(bars) if b[0] <= exit_date), None)
    if entry_bar is None or exit_bar is None or entry_bar[0] > exit_bar[0]:
        return None
    return entry_bar[1], exit_bar[2], entry_bar[0], exit_bar[0]


def _annotate_trade_with_nasdaq(trade: dict, entry_date: datetime.date | None = None, exit_date: datetime.date | None = None) -> None:
    """Fill in the NASDAQ move over the trade's OWN bar window, plus alpha.

    July 2026 review — the old implementation compared close-to-close on
    the calendar dates, with two corruptions: (1) every FLASH trade got
    ``nasdaq_entry == nasdaq_exit`` (same close twice) so its benchmark
    return was always 0.0 and "alpha" was just the raw trade return;
    (2) weekly holds compared a Monday-OPEN stock entry to the PREVIOUS
    Friday's index close (weekend gap contamination). The benchmark now
    uses the index OPEN on the trade's entry bar date and the index CLOSE
    on its exit bar date — the exact same window the trade's own P&L is
    measured over.

    Safe no-op if yfinance data is unavailable — ``nasdaq_*`` fields stay
    ``None`` and ``alpha_pct`` defaults to ``None``.
    """
    if entry_date is None:
        for key in ("entry_bar_date", "date"):
            val = trade.get(key)
            if isinstance(val, str):
                try:
                    entry_date = datetime.date.fromisoformat(val)
                    break
                except ValueError:
                    continue
    if exit_date is None:
        val = trade.get("exit_bar_date")
        if isinstance(val, str):
            try:
                exit_date = datetime.date.fromisoformat(val)
            except ValueError:
                exit_date = None
    if entry_date is None:
        entry_date = datetime.date.today()
    if exit_date is None:
        # Weekly holds close on the Friday of the entry's week; flash
        # trades close the same day. Good enough for benchmark alpha.
        if trade.get("trade_type") == "flash":
            exit_date = entry_date
        else:
            exit_date = entry_date + datetime.timedelta(days=(4 - entry_date.weekday()) % 7)

    bars = _fetch_history_bars(NASDAQ_SYMBOL, period="1mo")
    window = _matched_nasdaq_window(bars, entry_date, exit_date) if bars else None
    if window:
        entry_open, exit_close, entry_bar_date, exit_bar_date = window
        trade["nasdaq_entry"] = round(entry_open, 2)
        trade["nasdaq_exit"] = round(exit_close, 2)
        trade["nasdaq_entry_date"] = entry_bar_date.isoformat()
        trade["nasdaq_exit_date"] = exit_bar_date.isoformat()
        nasdaq_return = ((exit_close - entry_open) / entry_open) * 100
        trade["nasdaq_return_pct"] = round(nasdaq_return, 2)
        pnl = trade.get("pnl_pct")
        if isinstance(pnl, (int, float)) and math.isfinite(pnl):
            trade["alpha_pct"] = round(pnl - nasdaq_return, 2)
        else:
            trade["alpha_pct"] = None
    else:
        trade["nasdaq_entry"] = None
        trade["nasdaq_exit"] = None
        trade["nasdaq_return_pct"] = None
        trade["alpha_pct"] = None

    # Multi-index annotation (July 2026): the same matched window scored
    # against every major index, so the record can honestly answer "does
    # this beat ALL of them?". Best-effort per index; NASDAQ reuses the
    # window computed above rather than refetching.
    returns: dict[str, float | None] = {}
    for key, symbol in BENCHMARK_INDICES.items():
        if key == "nasdaq":
            returns[key] = trade.get("nasdaq_return_pct")
            continue
        try:
            idx_bars = _fetch_history_bars(symbol, period="1mo")
            idx_window = (
                _matched_nasdaq_window(idx_bars, entry_date, exit_date)
                if idx_bars else None
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Benchmark %s annotation failed: %s", symbol, exc)
            idx_window = None
        if idx_window:
            idx_open, idx_close, _, _ = idx_window
            returns[key] = round(((idx_close - idx_open) / idx_open) * 100, 2)
        else:
            returns[key] = None
    trade["benchmark_returns"] = returns


# ---------------------------------------------------------------------------
# Sector classification + lesson-tag extraction
# ---------------------------------------------------------------------------

_SECTOR_KEYWORDS = (
    ("precious_metals", ("gold", "silver", "mining", "miner", "platinum", "palladium", "bullion", "ore")),
    ("energy", ("oil", "gas", "petroleum", "lng", "energy", "pipeline", "refiner", "wti", "brent")),
    ("tech", ("semiconductor", "chip", "cloud", "software", "saas", "ai infrastructure", "data center", "fintech platform", "memory")),
    ("financials", ("bank", "insurer", "insurance", "mortgage", "broker", "credit union", "digital banking")),
    ("healthcare", ("pharma", "biotech", "therap", "vaccine", "hospital", "medical device", "clinical trial")),
    ("consumer", ("retail", "consumer", "ev ", "electric vehicle", "apparel", "beverage", "restaurant", "grocer")),
    ("crypto", ("crypto", "bitcoin", "ethereum", "stablecoin", "defi", "miner pool")),
    ("industrials", ("industrial", "rail", "transport", "logistics", "machinery", "construction")),
    ("utilities", ("utility", "utilities", "power generation", "grid")),
)


def _classify_sector(symbol: str, strategy: str = "", market: str = "") -> str:
    """Return a canonical sector tag for a Practice Investment pick.

    Direct symbol lookup wins; falls back to keyword matching on the
    strategy text. Always returns a tag from ``SECTOR_TAGS`` — defaults
    to ``"other"`` when uncertain so the dashboard aggregator never NPEs.
    """
    if symbol:
        sym = symbol.upper().strip()
        if sym in _SECTOR_BY_SYMBOL:
            return _SECTOR_BY_SYMBOL[sym]
    haystack = f"{strategy} {market}".lower()
    for sector, keywords in _SECTOR_KEYWORDS:
        for kw in keywords:
            if kw in haystack:
                return sector
    return "other"


def _extract_lesson_tags(text: str) -> list[str]:
    """Pull any tags from ``LESSON_VOCABULARY`` that appear in *text*.

    The digest prompt emits ``**Lesson Tags:** foo, bar`` after each
    Trade Review and Practice Investment; this function also matches
    loose mentions inside the Investor Education section so older
    episodes aren't silently missed.
    """
    if not text:
        return []
    # Normalise so "bid-ask spread", "bid ask spread", "bid_ask_spread"
    # all collapse to a single matching token stream.
    lowered = re.sub(r"[\-_\s]+", " ", text.lower())
    found: list[str] = []
    for tag in LESSON_VOCABULARY:
        needle = tag.replace("_", " ")
        if needle in lowered and tag not in found:
            found.append(tag)
    return found


# ---------------------------------------------------------------------------
# Trade review text builders
# ---------------------------------------------------------------------------

def _weekly_hold_update(open_trades: list) -> str:
    """Mid-week unrealized-P&L update for the latest open weekly hold, or ''."""
    if not open_trades:
        return ""
    hold = open_trades[-1]
    current = hold.get("current_price")
    if current and hold.get("entry_price"):
        unrealized = ((current - hold["entry_price"]) / hold["entry_price"]) * 100
        direction = "up" if unrealized >= 0 else "down"
        return (
            f"**Current Weekly Hold:** {hold.get('symbol', '???')} — {hold.get('strategy', '')}\n"
            f"**Entry:** ${hold['entry_price']:.2f} (Monday open)\n"
            f"**Current:** ${current:.2f} ({direction} {abs(unrealized):.2f}%)\n"
            f"**Status:** Holding until Friday evaluation\n"
        )
    return ""


def _build_trade_review(tracker: dict, episode_num: int | None = None) -> str:
    """Build the Trade Review text block for the digest prompt.

    Handles both weekly holds and flash trades, with appropriate framing
    for each. Voided trades (market-data failures) are excluded by the
    ``status == "closed"`` filter — they are never narrated as outcomes.

    Double-review guard (July 2026 review): each closed trade is reviewed
    EXACTLY ONCE. Previously the block always reviewed the most-recent
    closed trade, so on days when nothing new closed (the between-trade
    cadence gap) the same result was re-narrated as if fresh — the MU
    flash trade was re-told as "yesterday's" on Ep089/091/093. We stamp
    ``reviewed_in_episode`` on the trade the first time it's narrated; if
    the latest closed trade was already reviewed in a PRIOR episode, we
    give an open-hold update instead, or state holdings are pending.
    """
    if episode_num and episode_num <= 1:
        return ""  # No review for Episode 1

    closed = [t for t in tracker["trades"] if t.get("status") == "closed"]
    open_trades = [t for t in tracker["trades"] if t.get("status") == "open"]
    if not closed:
        # Check for open weekly hold — provide mid-week update
        return _weekly_hold_update(open_trades)

    last = closed[-1]

    # Double-review guard: don't re-narrate an already-reviewed result.
    already = last.get("reviewed_in_episode")
    if already is not None and already != episode_num:
        hold_update = _weekly_hold_update(open_trades)
        if hold_update:
            return hold_update
        return (
            "**No newly closed trade since the last review.** The most "
            "recent Practice Investment has already been reviewed; current "
            "holdings remain open and pending their scheduled evaluation, "
            "so there is no new realized result to report today.\n"
        )

    # Stamp so this result is narrated once (persisted by the caller's save).
    if episode_num is not None:
        last["reviewed_in_episode"] = episode_num
    symbol = last.get("symbol", "???")
    strategy = last.get("strategy", "")
    trade_type = last.get("trade_type", "weekly")
    entry = last.get("entry_price")
    exit_ = last.get("exit_price")
    pnl_pct = last.get("pnl_pct", 0)
    pnl_dollars = _finite(last.get("pnl_dollars"))
    summary = tracker.get("summary", {})

    type_label = "Flash Trade" if trade_type == "flash" else "Weekly Hold"
    # Prefer the ACTUAL bar dates recorded at close (July 2026 review: the
    # Friday pre-market run closes weekly holds on Thursday's bar, so the
    # old hardcoded "Friday close" label put a wrong day on air — and the
    # Saturday scripts then said "Friday's close" about a Thursday price).
    entry_label = "market open" if trade_type == "flash" else "Monday open"
    exit_label = "market close" if trade_type == "flash" else "Friday close"
    try:
        if last.get("entry_bar_date"):
            entry_label = (
                datetime.date.fromisoformat(last["entry_bar_date"]).strftime("%A")
                + " open"
            )
        if last.get("exit_bar_date"):
            exit_label = (
                datetime.date.fromisoformat(last["exit_bar_date"]).strftime("%A")
                + " close"
            )
    except ValueError:
        pass

    if entry is None or exit_ is None:
        return (
            f"**Last {type_label}:** {symbol}\n"
            f"**Result:** Market data was unavailable for evaluation.\n"
            f"**Running Total:** ${summary.get('cumulative_pnl', 0):.2f}\n"
            f"**Win Rate:** {summary.get('wins', 0)} wins / "
            f"{summary.get('total_trades', 0)} total trades "
            f"({summary.get('win_rate_pct', 0):.0f}%)\n"
        )

    direction = "gained" if pnl_pct >= 0 else "lost"
    return (
        f"**Last {type_label}:** {symbol} — {strategy}\n"
        f"**Entry:** ${entry:.2f} ({entry_label}) → **Exit:** ${exit_:.2f} ({exit_label})\n"
        f"**Result:** {direction} {abs(pnl_pct):.2f}% (${pnl_dollars:+.2f} on $1,000 position)\n"
        f"**Running Total:** ${summary.get('cumulative_pnl', 0):.2f} across "
        f"{summary.get('total_trades', 0)} trades\n"
        f"**Win Rate:** {summary.get('wins', 0)} wins / "
        f"{summary.get('total_trades', 0)} total trades "
        f"({summary.get('win_rate_pct', 0):.0f}%)\n"
        f"**Current Streak:** {_format_streak(summary.get('current_streak', 0))}\n"
    )


def _build_benchmark_block(tracker: dict) -> str:
    """One-line benchmark block fed to the digest/podcast prompt.

    Names NASDAQ Composite level, YTD benchmark move, portfolio return,
    and alpha in both YTD and inception-to-date windows — the show is
    required by its system prompt to state all four in every episode.
    """
    benchmark = tracker.get("benchmark", {}) or {}
    alpha = tracker.get("alpha", {}) or {}
    portfolio_itd = _portfolio_return_pct(tracker)
    portfolio_ytd = _portfolio_return_ytd_pct(tracker)
    close = benchmark.get("current_close")
    bench_ytd = benchmark.get("ytd_pct")
    bench_itd = benchmark.get("inception_to_date_pct")
    alpha_ytd = alpha.get("ytd_pct")
    alpha_itd = alpha.get("inception_to_date_pct")

    if close is None:
        return (
            "NASDAQ Composite: data temporarily unavailable — acknowledge the gap "
            "on air rather than inventing numbers."
        )

    def _sign(v):
        if v is None:
            return "n/a"
        return f"{v:+.2f}%"

    # Two DIFFERENT scores exist and episodes have spoken them
    # interchangeably (+11% one day, -13.1% the Sunday recap — July 2026
    # review). Label them so the script can never conflate the two.
    summary = tracker.get("summary", {}) or {}
    matched_alpha = summary.get("matched_window_alpha_pct")
    matched_n = summary.get("matched_window_trades", 0)
    matched_line = ""
    if matched_n and matched_alpha is not None:
        matched_line = (
            f"1) MATCHED-WINDOW SCORE (the honest head-to-head — each $1,000 "
            f"trade vs the NASDAQ over the SAME holding window, compounded): "
            f"portfolio {_sign(summary.get('compounded_return_pct'))} vs NASDAQ "
            f"{_sign(summary.get('compounded_nasdaq_matched_pct'))} → alpha "
            f"{_sign(matched_alpha)} across {matched_n} benchmarked trades. "
        )
        scores = summary.get("benchmark_scores") or {}
        if len(scores) > 1:
            parts = []
            for key in ("nasdaq", "sp500", "tsx"):
                s = scores.get(key)
                if s:
                    parts.append(
                        f"{BENCHMARK_LABELS[key]} {_sign(s['alpha_pct'])}"
                    )
            beaten = summary.get("indices_beaten", 0)
            scored = summary.get("indices_scored", 0)
            matched_line += (
                f"MAJOR-INDEX SWEEP (same matched windows): currently beating "
                f"{beaten} of {scored} major indices — "
                + "; ".join(parts)
                + ". NASDAQ stays the headline benchmark; mention the sweep "
                  "at most once per episode. "
            )
    return (
        f"NASDAQ Composite ^IXIC: {close:,.0f} "
        f"(YTD {_sign(bench_ytd)}, since inception {_sign(bench_itd)}).\n"
        f"SCOREBOARD — two different measures; ALWAYS name the measure when "
        f"speaking a number, never mix them in one sentence:\n"
        f"{matched_line}\n"
        f"2) BUY-AND-HOLD GAP (context only; NOT capital-matched — the sim "
        f"holds one $1,000 position at a time while the index compounds "
        f"fully invested): portfolio YTD {_sign(portfolio_ytd)} / since "
        f"inception {_sign(portfolio_itd)}; gap vs NASDAQ YTD "
        f"{_sign(alpha_ytd)} / since inception {_sign(alpha_itd)}."
    )


# ---------------------------------------------------------------------------
# Taught-lessons repetition guard + lessons_learned recursive ledger
# ---------------------------------------------------------------------------

def _load_taught_lessons(path: Path) -> dict:
    """Load the taught-lessons JSON, or return a fresh structure."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("metadata", {}).setdefault("last_updated", datetime.date.today().isoformat())
            data.setdefault("lessons", {})
            data.setdefault("cooldown_days_default", 21)
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load taught_lessons: %s — starting fresh", exc)
    return {
        "metadata": {"last_updated": datetime.date.today().isoformat()},
        "lessons": {},
        "cooldown_days_default": 21,
    }


def _save_taught_lessons(data: dict, path: Path) -> None:
    data["metadata"]["last_updated"] = datetime.date.today().isoformat()
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _record_taught_lessons(data: dict, tags: list[str], episode_num: int | None) -> None:
    """Bump counts + last-seen for each taught lesson tag."""
    if not tags:
        return
    today_iso = datetime.date.today().isoformat()
    default_cooldown = int(data.get("cooldown_days_default", 21))
    lessons = data.setdefault("lessons", {})
    for tag in tags:
        entry = lessons.setdefault(tag, {
            "count": 0,
            "last_episode": None,
            "last_date": None,
            "cooldown_days": default_cooldown,
        })
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_episode"] = episode_num if episode_num is not None else entry.get("last_episode")
        entry["last_date"] = today_iso


def _stale_lesson_tags(data: dict) -> list[tuple[str, int]]:
    """Return [(tag, days_since)] for lessons still inside their cooldown window.

    Tags the digest prompt should AVOID re-teaching today. Sorted by
    most-recently-taught first so the prompt lists the hottest blocks
    at the top.
    """
    today = datetime.date.today()
    stale: list[tuple[str, int]] = []
    for tag, entry in (data.get("lessons") or {}).items():
        last_date = entry.get("last_date")
        if not last_date:
            continue
        try:
            last = datetime.date.fromisoformat(last_date)
        except ValueError:
            continue
        cooldown = int(entry.get("cooldown_days", data.get("cooldown_days_default", 21)))
        # Escalating cooldown (June 2026): a flat 21-day window let the
        # bid-ask-spread lesson get retaught 13 times in 71 episodes —
        # each repeat was "legal" because 3+ weeks had passed, but the
        # show's own audit (LL-001) flagged listeners tuning out. Every
        # 3 repeats now adds another full cooldown period, capped at
        # ~6 months, so a lesson taught 13 times effectively retires.
        count = int(entry.get("count", 1) or 1)
        cooldown = min(cooldown * (1 + count // 3), 180)
        days_since = (today - last).days
        if days_since < cooldown:
            stale.append((tag, days_since))
    stale.sort(key=lambda x: x[1])
    return stale


def _build_taught_lessons_block(data: dict) -> str:
    """Human-readable block injected into the digest prompt."""
    stale = _stale_lesson_tags(data)
    if not stale:
        return "No lessons are in their cooldown window today — you have full latitude on what to teach."
    lines = ["Do NOT re-teach any of the following today (inside cooldown):"]
    lessons = data.get("lessons") or {}
    for tag, days_since in stale[:12]:
        entry = lessons.get(tag, {})
        cooldown = entry.get("cooldown_days", data.get("cooldown_days_default", 21))
        lines.append(
            f"- {tag} (count={entry.get('count', '?')}, "
            f"last Ep{entry.get('last_episode', '?')}, "
            f"{days_since}d ago; cools in {max(cooldown - days_since, 0)}d)"
        )
    return "\n".join(lines)


def _load_lessons_learned(path: Path) -> dict:
    """Load the lessons_learned ledger, or return a fresh structure.
    Normalizes to always use the 'entries' key for consistency (post day-one review fix).
    """
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("metadata", {}).setdefault("schema_version", 1)
            data["metadata"].setdefault("last_updated", datetime.date.today().isoformat())
            # Back-compat normalization (some early versions used "lessons")
            if "lessons" in data and "entries" not in data:
                data["entries"] = data.pop("lessons")
            data.setdefault("entries", [])
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load lessons_learned: %s — starting fresh", exc)
    return {
        "metadata": {
            "schema_version": 1,
            "last_updated": datetime.date.today().isoformat(),
        },
        "entries": [],
    }


def _save_lessons_learned(data: dict, path: Path) -> None:
    data["metadata"]["last_updated"] = datetime.date.today().isoformat()
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


_LESSON_SIMILARITY_THRESHOLD = 0.62


def _lesson_similarity(a: str, b: str) -> float:
    """Similarity ratio between two lesson texts (shared engine helper)."""
    try:
        from engine.utils import calculate_similarity
        return calculate_similarity(a, b)
    except Exception:
        return 0.0


def _find_similar_active_lesson(data: dict, observation: str, adjustment: str) -> dict | None:
    """Return an existing ACTIVE entry that says essentially the same thing.

    The comparison weights the Rule (adjustment) text — that's the part
    the LLM parrots back — and falls back to the combined text.
    """
    adjustment = (adjustment or "").strip()
    combined = f"{(observation or '').strip()} {adjustment}"
    for entry in data.get("entries") or []:
        if entry.get("status") != "active":
            continue
        if _lesson_similarity(adjustment, entry.get("adjustment", "")) >= _LESSON_SIMILARITY_THRESHOLD:
            return entry
        existing_combined = f"{entry.get('observation', '')} {entry.get('adjustment', '')}"
        if _lesson_similarity(combined, existing_combined) >= _LESSON_SIMILARITY_THRESHOLD:
            return entry
    return None


def _append_lesson_learned(
    data: dict,
    *,
    observation: str,
    adjustment: str,
    episode_num: int | None,
    source: str = "post_generate",
    category: str = "content",
    metric_target: dict | None = None,
) -> dict:
    """Append a new recursive-improvement rule; returns the entry.

    Dedup-on-append (July 2026 review): the ledger had become a feedback
    echo chamber — the prompt showed the 5 newest rules, the LLM
    paraphrased them back in its **Lesson Learned** block, and the
    extractor appended the paraphrase as a NEW rule. 65 entries
    accumulated, ~35 of them copies of one volume-confirmation rule and
    12 of the closing-price-confirmation rule (the 9-of-10-episodes
    spoken tic). A near-duplicate of an active rule now REINFORCES that
    rule (count + freshness stamp) instead of multiplying it, so the
    5-rule prompt window stays diverse and the show can actually learn
    five different things.
    """
    entries = data.setdefault("entries", [])
    existing = _find_similar_active_lesson(data, observation, adjustment)
    if existing is not None:
        existing["reinforced_count"] = int(existing.get("reinforced_count", 0)) + 1
        existing["last_reinforced"] = datetime.date.today().isoformat()
        if episode_num is not None:
            existing["last_reinforced_episode"] = episode_num
        logger.info(
            "Lesson learned duplicates active rule %s — reinforced (x%d), not re-appended",
            existing.get("id"), existing["reinforced_count"],
        )
        return existing
    next_id = f"LL-{len(entries) + 1:03d}"
    entry = {
        "id": next_id,
        "date": datetime.date.today().isoformat(),
        "episode_num": episode_num,
        "source": source,
        "category": category,
        "observation": observation.strip(),
        "adjustment": adjustment.strip(),
        "status": "active",
        "metric_target": metric_target or {},
    }
    entries.append(entry)
    return entry


def _selected_active_rules(data: dict, *, max_active: int = 5) -> list[dict]:
    """The distinct active rules shown to the LLM today (most recent first).

    Shared by the prompt block AND the trade-stamping in post_generate so
    the ``rules_in_effect`` recorded on each trade is exactly the set the
    model was told to obey when it made the pick.
    """
    entries = [e for e in (data.get("entries") or []) if e.get("status") == "active"]
    selected: list[dict] = []
    for entry in reversed(entries):
        if len(selected) >= max_active:
            break
        if any(
            _lesson_similarity(entry.get("adjustment", ""), s.get("adjustment", ""))
            >= _LESSON_SIMILARITY_THRESHOLD
            for s in selected
        ):
            continue
        selected.append(entry)
    return selected


def _build_lessons_learned_block(data: dict, *, max_active: int = 5) -> str:
    """Block fed to the digest prompt as 'RECURSIVE IMPROVEMENT RULES IN EFFECT'.

    Selects the most recent DISTINCT rules — near-duplicate actives (the
    pre-dedup backlog) collapse to their freshest instance so the block
    never shows the same rule five times.
    """
    selected = _selected_active_rules(data, max_active=max_active)
    if not selected:
        return "No active recursive-improvement rules yet — write one if today's trade teaches a generalisable lesson."
    lines = ["The following rules are in effect today. Obey them in every section of the digest:"]
    for entry in selected:
        lines.append(
            f"- [{entry['id']}] {entry.get('observation', '').rstrip('.')}. "
            f"Rule: {entry.get('adjustment', '').rstrip('.')}."
        )
    return "\n".join(lines)


def _build_rule_scoreboard(data: dict, tracker: dict, *,
                           min_trades: int = 5,
                           retire_after: int = 8) -> str:
    """Measured effectiveness of each active rule — the loop's own audit.

    July 2026 "learn whether it's learning" pass: rules accumulated but
    nothing ever checked whether obeying them helped. Every recorded
    trade now carries ``rules_in_effect`` (the rule IDs shown to the
    model on pick day); once a rule has been in effect for enough closed
    trades, its stamped-trade average alpha is compared against the
    average alpha of closed trades made WITHOUT it. Rules with enough
    evidence and no measurable edge are flagged as retirement candidates
    — surfaced for the OPERATOR (rules are never auto-retired).
    """
    closed = [
        t for t in tracker.get("trades", [])
        if t.get("status") == "closed"
        and isinstance(t.get("alpha_pct"), (int, float))
        and math.isfinite(t["alpha_pct"])
    ]
    active = [e for e in (data.get("entries") or []) if e.get("status") == "active"]
    if not closed or not active:
        return ""

    lines = []
    for entry in active:
        rid = entry.get("id")
        stamped = [t for t in closed if rid in (t.get("rules_in_effect") or [])]
        if len(stamped) < min_trades:
            continue
        others = [t for t in closed if rid not in (t.get("rules_in_effect") or [])]
        avg_with = sum(t["alpha_pct"] for t in stamped) / len(stamped)
        line = (
            f"- [{rid}] in effect for {len(stamped)} closed trades: "
            f"avg alpha {avg_with:+.2f}%"
        )
        if others:
            avg_without = sum(t["alpha_pct"] for t in others) / len(others)
            line += f" (trades without it: {avg_without:+.2f}%)"
            if len(stamped) >= retire_after and avg_with <= avg_without:
                line += (
                    " → RETIREMENT CANDIDATE: no measurable edge — flag for "
                    "the operator; keep obeying it until retired"
                )
        lines.append(line)
    if not lines:
        return ""
    return (
        "RULE EFFECTIVENESS (measured on closed trades — weight proven "
        "rules more heavily when selecting today's pick):\n"
        + "\n".join(lines)
    )


def _extract_lesson_learned_from_digest(digest_text: str) -> tuple[str, str] | None:
    """If the digest wrote a **Lesson Learned:** block with a Rule: suffix,
    return (observation, adjustment). Otherwise return None.
    """
    if not digest_text:
        return None
    match = re.search(
        r"\*\*Lesson Learned:\*\*\s*(.+?)(?:\n\s*\*\*|\Z)",
        digest_text,
        re.DOTALL,
    )
    if not match:
        return None
    body = match.group(1).strip()
    # Split on a literal "Rule:" sentence so only deliberate rules are captured.
    rule_match = re.search(r"Rule:\s*(.+?)(?:\.\s|$)", body, re.DOTALL)
    if not rule_match:
        return None
    observation = body[: rule_match.start()].strip(" .\n")
    adjustment = rule_match.group(1).strip(" .\n")
    if not observation or not adjustment:
        return None
    return observation, adjustment


# ---------------------------------------------------------------------------
# Sector concentration warning + narrative callback
# ---------------------------------------------------------------------------

_CONCENTRATION_THRESHOLD_PCT = 30.0
_CONCENTRATION_WINDOW = 10


def _compute_sector_exposure(tracker: dict) -> dict:
    """Return {sector: {trade_count, exposure_pct, cumulative_pnl}} over the
    last ``_CONCENTRATION_WINDOW`` trades (open + closed combined).
    """
    # Exclude voided trades (July 2026): a data-fetch failure isn't real
    # market exposure and must not count toward a concentration warning.
    real = [t for t in tracker.get("trades", []) if t.get("status") != "voided"]
    trades = real[-_CONCENTRATION_WINDOW:]
    if not trades:
        return {}
    counts: dict[str, int] = {}
    pnl: dict[str, float] = {}
    for t in trades:
        sector = t.get("sector") or _classify_sector(
            t.get("symbol", ""), t.get("strategy", ""), t.get("market", ""),
        )
        counts[sector] = counts.get(sector, 0) + 1
        pnl[sector] = pnl.get(sector, 0.0) + _finite(t.get("pnl_dollars"))
    total = sum(counts.values())
    return {
        sector: {
            "trade_count": n,
            "exposure_pct": round((n / total) * 100, 1),
            "cumulative_pnl": round(pnl.get(sector, 0.0), 2),
        }
        for sector, n in counts.items()
    }


def _build_sector_warning_block(tracker: dict) -> str:
    """If any sector exceeds the concentration threshold over the recent
    window, emit an AVOID instruction for today's pick.
    """
    sectors = tracker.get("sectors") or _compute_sector_exposure(tracker)
    if not sectors:
        return "No sector concentration detected — pick based on today's best setup."
    over = [(s, d) for s, d in sectors.items() if d.get("exposure_pct", 0) >= _CONCENTRATION_THRESHOLD_PCT]
    if not over:
        return "Sector exposure is balanced — no concentration warning today."
    # Sort biggest-first so the most-overweight sector leads the warning.
    over.sort(key=lambda x: x[1]["exposure_pct"], reverse=True)
    lines = ["SECTOR CONCENTRATION WARNING — today's Practice Investment MUST AVOID the following sectors:"]
    for sector, data in over:
        lines.append(
            f"- {sector}: {data['exposure_pct']:.0f}% of the last "
            f"{_CONCENTRATION_WINDOW} trades ({data['trade_count']} trades, "
            f"cumulative P&L ${data['cumulative_pnl']:+.2f})"
        )
    lines.append("Pick a DIFFERENT sector. Diversification is an explicit rule of this show.")
    return "\n".join(lines)


def _resolve_segment_library(config) -> Path | None:
    """Return the segment-library path for MIT, checking config + default."""
    default = Path("shows/segments/modern_investing.json")
    if default.exists():
        return default
    sn = getattr(config, "slow_news", None)
    if sn and getattr(sn, "library_file", ""):
        p = Path(sn.library_file)
        if p.exists():
            return p
    return None


def _pick_deep_dive_segment(tracker: dict, library_path: Path | None) -> tuple[str | None, tuple[str, str] | None]:
    """Return ``(segment_id, (title, prompt_template))`` for a deep-dive
    segment the show hasn't used in its last ~30 picks, or ``(None, None)``
    when the library is empty / unavailable. Powered by
    ``shows/segments/modern_investing.json`` (30 evergreen segments that
    were previously dead code — surfacing them here gives the show a
    built-in rotation of pre-written deep dives).
    """
    if not library_path or not library_path.exists():
        return None, None
    try:
        data = json.loads(library_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load segment library %s: %s", library_path, exc)
        return None, None
    segments = data.get("segments") or []
    if not segments:
        return None, None
    recent = tracker.get("used_segment_ids") or []
    cooldown_len = 30
    recent_set = set(recent[-cooldown_len:])
    available = [s for s in segments if s.get("id") not in recent_set]
    if not available:
        order = {sid: idx for idx, sid in enumerate(recent)}
        available = sorted(segments, key=lambda s: order.get(s.get("id"), -1))
    pick = available[0]
    return pick.get("id"), (pick.get("title", ""), pick.get("prompt_template", ""))


def _build_deep_dive_hint_block(hint: tuple[str, str] | None) -> str:
    """Prompt-ready block describing today's evergreen deep-dive suggestion."""
    if not hint or not hint[0]:
        return "No evergreen deep-dive suggestion today — pick an Investor Education topic from the day's news as usual."
    title, prompt = hint
    return (
        f"EVERGREEN DEEP-DIVE SUGGESTION: '{title}'. "
        f"Use this as the Investor Education topic UNLESS today's news demands a fresher mechanic. "
        f"Segment brief: {prompt}"
    )


def _record_segment_used(tracker: dict, segment_id: str) -> None:
    """Append segment_id to the tracker's used list, capped at 60 entries."""
    if not segment_id:
        return
    used = tracker.setdefault("used_segment_ids", [])
    used.append(segment_id)
    if len(used) > 60:
        del used[:-60]


def _build_narrative_callback(tracker: dict) -> str:
    """Pick one closed trade from 14-30 days ago, formatted as a recall line.
    The daily podcast weaves this in naturally on Fridays and monthlies.
    """
    today = datetime.date.today()
    candidates = []
    for t in tracker.get("trades", []):
        if t.get("status") != "closed":
            continue
        d = t.get("date")
        if not isinstance(d, str):
            continue
        try:
            tdate = datetime.date.fromisoformat(d)
        except ValueError:
            continue
        days = (today - tdate).days
        if 14 <= days <= 35:
            candidates.append((days, t))
    if not candidates:
        return "No callback-worthy trade from 2-5 weeks ago yet — skip the narrative callback today."
    # Prefer the freshest that's still clearly in the callback window.
    candidates.sort(key=lambda x: x[0])
    days, trade = candidates[0]
    symbol = trade.get("symbol", "???")
    pnl = trade.get("pnl_pct")
    sector = trade.get("sector", "?")
    strategy = (trade.get("strategy") or "").rstrip(".")
    result = (
        f"closed {pnl:+.2f}%"
        if isinstance(pnl, (int, float))
        else "was closed with unavailable data"
    )
    return (
        f"About {days} days ago (Ep{trade.get('episode_num', '?')}) we picked {symbol} "
        f"({sector}) — {strategy}. It {result}. Reference it once and draw a one-sentence lesson."
    )


def _build_portfolio_summary(tracker: dict) -> str:
    """Build the Portfolio Performance summary for the digest prompt."""
    summary = tracker.get("summary", {})
    total = summary.get("total_trades", 0)
    if total == 0:
        return "No simulated trades completed yet — this is the first episode."

    alpha_line = ""
    trades_with_alpha = summary.get("trades_with_alpha", 0)
    if trades_with_alpha:
        matched_alpha = summary.get("matched_window_alpha_pct")
        matched_n = summary.get("matched_window_trades", 0)
        if matched_n and matched_alpha is not None:
            alpha_line = (
                f"- Matched-window alpha vs NASDAQ (compounded over each "
                f"trade's own holding window): {_finite(matched_alpha):+.1f}% "
                f"across {matched_n} benchmarked trades — THE headline "
                f"number; state it on air every episode and always call it "
                f"the 'matched-window' score\n"
                f"- Sum of per-trade alpha (simple additive tally, secondary): "
                f"{_finite(summary.get('cumulative_alpha_vs_nasdaq')):+.1f}%\n"
            )
        else:
            alpha_line = (
                f"- Cumulative alpha vs NASDAQ: "
                f"{_finite(summary.get('cumulative_alpha_vs_nasdaq')):+.1f}% "
                f"(across {trades_with_alpha} benchmarked trades) — THE headline "
                f"number; state it on air every episode\n"
            )

    return (
        f"Portfolio Performance (simulated, $1,000 per trade):\n"
        f"- Total trades: {total}\n"
        f"- Win rate: {summary.get('win_rate_pct', 0):.0f}% "
        f"({summary.get('wins', 0)}W / {summary.get('losses', 0)}L / "
        f"{summary.get('breakeven', 0)}BE)\n"
        f"- Cumulative P&L: ${_finite(summary.get('cumulative_pnl')):+.2f}\n"
        f"{alpha_line}"
        f"- Average return per trade: {_finite(summary.get('average_return_pct')):+.2f}%\n"
        f"- Best trade: {summary.get('best_trade_pct', 0):+.2f}%\n"
        f"- Worst trade: {summary.get('worst_trade_pct', 0):+.2f}%\n"
        f"- Current streak: {_format_streak(summary.get('current_streak', 0))}\n"
    )


def _format_streak(streak: int) -> str:
    """Format streak number as human-readable text."""
    if streak > 0:
        return f"{streak} win{'s' if streak != 1 else ''}"
    elif streak < 0:
        return f"{abs(streak)} loss{'es' if abs(streak) != 1 else ''}"
    return "even"


# ---------------------------------------------------------------------------
# Post-generation trade extraction
# ---------------------------------------------------------------------------

def _extract_trade_from_digest(digest_text: str, episode_num: int | None = None) -> dict | None:
    """Parse the Practice Investment of the Day from the generated digest.

    Returns a trade dict ready for the tracker, or None if extraction fails.
    """
    if not digest_text:
        return None

    # Extract ticker symbol
    ticker_match = re.search(
        r"\*\*Today's Pick:\*\*\s*\[?([A-Z]{1,5})\]?\s*[-—]",
        digest_text,
    )
    if not ticker_match:
        # Fallback: try alternative patterns
        ticker_match = re.search(
            r"Today's Pick[:\s]+([A-Z]{1,5})\s",
            digest_text,
        )
    if not ticker_match:
        # Distinguish "deliberately no trade today" (a legitimate,
        # common outcome — e.g. "**Today's Pick:** No trade") from a
        # formatting drift that would silently lose a real pick (June
        # 2026 review: silent extraction failures were indistinguishable
        # from no-trade days in the tracker).
        if re.search(r"Today's Pick", digest_text):
            if re.search(r"Today's Pick[:*\s]+No\b", digest_text, re.IGNORECASE):
                logger.info("Digest declared no trade today — tracker unchanged.")
            else:
                logger.warning(
                    "Digest contains a Today's Pick section but no ticker "
                    "matched the extraction patterns — possible LLM "
                    "formatting drift; a real pick may have been lost. "
                    "First 120 chars after marker: %r",
                    digest_text.split("Today's Pick", 1)[1][:120],
                )
        return None

    symbol = ticker_match.group(1).strip()

    # Extract market
    market_match = re.search(
        r"\*\*Market:\*\*\s*(TSX|NYSE|NASDAQ|TSX-V)",
        digest_text, re.IGNORECASE,
    )
    market = market_match.group(1).upper() if market_match else "UNKNOWN"

    # Extract strategy
    strategy_match = re.search(
        r"\*\*Strategy:\*\*\s*(.+?)(?:\n|$)",
        digest_text,
    )
    strategy = strategy_match.group(1).strip().rstrip('"') if strategy_match else ""

    # Extract confidence
    confidence_match = re.search(
        r"\*\*Confidence Level:\*\*\s*(Low|Medium|High)",
        digest_text, re.IGNORECASE,
    )
    confidence = confidence_match.group(1).capitalize() if confidence_match else "Unknown"

    # Extract target
    target_match = re.search(
        r"\*\*Target:\*\*\s*(.+?)(?:\n|$)",
        digest_text,
    )
    target = target_match.group(1).strip() if target_match else ""

    # Extract trade type (hybrid model: weekly hold vs flash trade)
    trade_type_match = re.search(
        r"\*\*Trade Type:\*\*\s*(Weekly Hold|Flash Trade|Mid-Week Update)",
        digest_text, re.IGNORECASE,
    )
    if trade_type_match:
        raw_type = trade_type_match.group(1).strip().lower()
        trade_type = "flash" if "flash" in raw_type else "weekly"
    else:
        # Default: Monday = weekly, other days = flash (if it's a new pick)
        trade_type = "weekly" if datetime.date.today().weekday() == 0 else "flash"

    # Mid-week updates don't create new trades
    if trade_type_match and "update" in trade_type_match.group(1).lower():
        logger.info("Mid-week update detected — no new trade to record")
        return None

    return {
        "episode_num": episode_num or 0,
        "date": datetime.date.today().isoformat(),
        "symbol": symbol,
        "market": market,
        "strategy": strategy,
        "confidence": confidence,
        "target_range": target,
        "trade_type": trade_type,
        "status": "open",
        "entry_price": None,
        "exit_price": None,
        "pnl_pct": None,
        "pnl_dollars": None,
        "lesson": "",
    }


def _analyze_strategy_patterns(tracker: dict) -> str:
    """FAVOR/AVOID sector guidance from the closed-trade track record.

    June 2026: this function was CALLED by
    ``get_mit_recursive_learning_context`` but never defined — the
    resulting NameError was swallowed by the caller's try/except in
    ``pre_fetch``, so every episode shipped with "Learning context
    temporarily unavailable" instead of the recursive learning loop
    (and the operating-principles + confidence-calibration blocks died
    with it). This implements the FAVOR/AVOID contract the call site
    expects: sectors with >= 3 closed trades and a clearly positive /
    negative average alpha.
    """
    closed = [
        t for t in tracker.get("trades", [])
        if t.get("status") == "closed"
        and isinstance(t.get("alpha_pct"), (int, float))
        and math.isfinite(t["alpha_pct"])
    ]
    if len(closed) < 5:
        return ""

    sector_alpha: dict = {}
    for t in closed:
        sec = t.get("sector") or "other"
        sector_alpha.setdefault(sec, []).append(t["alpha_pct"])

    favor, avoid = [], []
    for sec, alphas in sector_alpha.items():
        if len(alphas) < _MIN_SAMPLE_TRADES:
            continue
        avg = sum(alphas) / len(alphas)
        if avg >= 1.0:
            favor.append((sec, avg, len(alphas)))
        elif avg <= -1.0:
            avoid.append((sec, avg, len(alphas)))

    if not favor and not avoid:
        return ""
    lines = ["SECTOR GUIDANCE FROM TRACK RECORD:"]
    for sec, avg, n in sorted(favor, key=lambda x: -x[1]):
        lines.append(f"  FAVOR {sec}: avg alpha {avg:+.1f}% across {n} closed trades")
    for sec, avg, n in sorted(avoid, key=lambda x: x[1]):
        lines.append(f"  AVOID {sec}: avg alpha {avg:+.1f}% across {n} closed trades")
    return "\n".join(lines)


def get_mit_recursive_learning_context() -> str:
    """
    Returns a rich, structured block of learning context for the LLM.

    This is the core of the "strong recursive learning loop" for Modern
    Investing Techniques. It feeds:
    - Current portfolio alpha vs NASDAQ
    - Top performing strategies / sectors with evidence
    - Lessons that have statistically worked (or failed)
    - Explicit recommendations for the next Practice Investment

    The output is designed to be injected into the podcast prompt so the
    model continuously improves its stock selection and risk management
    toward the explicit goal of outperforming the NASDAQ over time.
    """
    output_dir = Path(__file__).resolve().parent.parent.parent / "digests" / "modern_investing"
    tracker = _load_tracker(output_dir / TRACKER_FILENAME)

    summary = tracker.get("summary", {})
    cum_alpha = _finite(summary.get("cumulative_alpha_vs_nasdaq"))
    total_trades = summary.get("total_trades", 0)
    # Summary stores ``win_rate_pct`` (e.g. 57.6) — the old read of a
    # nonexistent ``win_rate`` key reported 0% forever (June 2026 review).
    win_rate_pct = _finite(summary.get("win_rate_pct"))

    closed = [t for t in tracker.get("trades", []) if t.get("status") == "closed" and t.get("alpha_pct") is not None]

    if total_trades < 5:
        return "EARLY STAGE: Fewer than 5 closed trades. Focus on process, position sizing, and clear thesis writing. NASDAQ benchmark tracking is active."

    # Top 3 winning patterns
    winning = sorted(closed, key=lambda t: t.get("alpha_pct", 0), reverse=True)[:3]
    losing = sorted(closed, key=lambda t: t.get("alpha_pct", 0))[:2]

    lines = [
        "RECURSIVE LEARNING CONTEXT — USE THIS TO IMPROVE FUTURE PRACTICE INVESTMENTS:",
        f"Current track record: {total_trades} closed trades | Win rate {win_rate_pct:.0f}% | Cumulative alpha vs NASDAQ: {cum_alpha:+.1f}%",
    ]

    if winning:
        lines.append("\nStrongest recent patterns (highest alpha):")
        for t in winning:
            lines.append(f"  + {t.get('symbol')} ({t.get('sector')}): +{t.get('alpha_pct',0):.1f}% alpha — {t.get('strategy','')[:80]}")

    if losing:
        lines.append("\nAreas to improve (lowest alpha):")
        for t in losing:
            lines.append(f"  - {t.get('symbol')} ({t.get('sector')}): {t.get('alpha_pct',0):+.1f}% alpha")

    # Sector guidance from earlier analysis function
    sector_analysis = _analyze_strategy_patterns(tracker)
    if "FAVOR" in sector_analysis or "AVOID" in sector_analysis:
        lines.append("\n" + sector_analysis)

    lines.append("\nINSTRUCTION: When suggesting the next Practice Investment, heavily weight the patterns above. Explicitly reference what has worked or failed in recent trades. Prioritize ideas that increase the probability of positive alpha vs NASDAQ.")

    # Add confidence calibration
    try:
        calib = get_mit_confidence_calibration(tracker)
        if calib and "Not enough" not in calib:
            lines.append(f"\nCONFIDENCE CALIBRATION: {calib}")
    except Exception:
        pass

    return "\n".join(lines)


def _derive_operating_principles(tracker: dict) -> list:
    """
    Derives a small set of high-confidence 'Operating Principles' from the
    actual track record. These become living rules the model must consider.
    """
    closed = [t for t in tracker.get("trades", []) if t.get("status") == "closed" and t.get("alpha_pct") is not None]
    if len(closed) < 8:
        return []

    principles = []

    # 1. Sector discipline
    sector_stats = {}
    for t in closed:
        sec = t.get("sector", "other")
        if sec not in sector_stats:
            sector_stats[sec] = {"count": 0, "total_alpha": 0}
        sector_stats[sec]["count"] += 1
        sector_stats[sec]["total_alpha"] += t.get("alpha_pct", 0)

    best_sector = max(sector_stats.items(), key=lambda x: x[1]["total_alpha"] / max(x[1]["count"], 1), default=None)
    if best_sector and best_sector[1]["count"] >= _MIN_SAMPLE_TRADES and (best_sector[1]["total_alpha"] / best_sector[1]["count"]) > 2:
        principles.append({
            "title": f"Favor {best_sector[0].replace('_', ' ').title()}",
            "description": f"Data shows strong positive alpha in this sector across {best_sector[1]['count']} trades.",
            "evidence": f"Avg alpha +{(best_sector[1]['total_alpha'] / best_sector[1]['count']):.1f}%"
        })

    # 2. Lesson tag discipline (most effective tags)
    tag_performance = {}
    for t in closed:
        for tag in t.get("lesson_tags", []):
            if tag not in tag_performance:
                tag_performance[tag] = {"count": 0, "total_alpha": 0}
            tag_performance[tag]["count"] += 1
            tag_performance[tag]["total_alpha"] += t.get("alpha_pct", 0)

    if tag_performance:
        best_tag = max(tag_performance.items(), key=lambda x: x[1]["total_alpha"] / max(x[1]["count"], 1))
        if best_tag[1]["count"] >= _MIN_SAMPLE_TRADES and (best_tag[1]["total_alpha"] / best_tag[1]["count"]) > 3:
            principles.append({
                "title": f"Prioritize setups matching '{best_tag[0]}'",
                "description": "This lesson tag has shown the strongest alpha when present in winning trades.",
                "evidence": f"{best_tag[1]['count']} trades, avg +{(best_tag[1]['total_alpha']/best_tag[1]['count']):.1f}% alpha"
            })

    return principles[:6]


def get_mit_confidence_calibration(tracker: dict) -> str:
    """Per-bucket calibration report for the prompt.

    July 2026 review: every one of the 46 recorded picks declared
    "Medium" confidence, so the old High-only report returned
    "data still limited" forever and the calibration loop never engaged.
    Report every bucket that exists, and call out a degenerate
    distribution so the model starts committing to High/Low when the
    rubric supports it.
    """
    closed = [
        t for t in tracker.get("trades", [])
        if t.get("status") == "closed" and t.get("confidence")
        and isinstance(t.get("alpha_pct"), (int, float))
        and math.isfinite(t["alpha_pct"])
    ]
    if len(closed) < 5:
        return "Not enough data for confidence calibration yet."

    buckets: dict[str, list[float]] = {}
    for t in closed:
        label = str(t.get("confidence", "")).strip().capitalize()
        buckets.setdefault(label, []).append(t["alpha_pct"])

    parts = []
    for label in ("High", "Medium", "Low"):
        alphas = buckets.get(label)
        if not alphas:
            continue
        wins = sum(1 for a in alphas if a > 0)
        parts.append(
            f"{label}: {wins}/{len(alphas)} positive-alpha "
            f"(avg {sum(alphas) / len(alphas):+.1f}%)"
        )
    line = "Calibration by stated confidence — " + " · ".join(parts) + "."
    dominant = max(buckets.values(), key=len)
    if len(dominant) / len(closed) > 0.9:
        line += (
            " NOTE: over 90% of picks used a single confidence level, which "
            "makes the field uninformative — commit to High or Low whenever "
            "the calibration rubric supports it, and say WHY."
        )
    return line


def _maybe_record_monthly_snapshot(tracker: dict, today: "datetime.date") -> None:
    """Append a lightweight monthly snapshot if we have crossed into a new month.
    Populates the previously-empty monthly_snapshots list (post day-one review fix).
    """
    snapshots = tracker.setdefault("monthly_snapshots", [])
    current_month = today.strftime("%Y-%m")
    if snapshots and snapshots[-1].get("month") == current_month:
        return
    summary = tracker.get("summary", {})
    # Emit a snapshot shape compatible with the public show page template
    # (which expects portfolio_pct / nasdaq_pct / alpha_pct / trades / win_rate)
    # and the richer snapshots produced by scripts/run_monthly_mit_episode.py.
    # Daily hook snapshots (written on month rollover during a regular episode)
    # don't have the full per-month closed-trade aggregation, so the three
    # comparison percentages are left as None (template shows "—").
    snapshot = {
        "month": current_month,
        "trades": summary.get("total_trades", 0),
        "win_rate": summary.get("win_rate_pct", 0.0),
        "portfolio_pct": None,
        "nasdaq_pct": None,
        "alpha_pct": None,
        "portfolio_pnl": summary.get("cumulative_pnl", 0.0),
        # Legacy keys kept for any direct consumers of the raw tracker
        "total_trades": summary.get("total_trades", 0),
        "win_rate_pct": summary.get("win_rate_pct", 0.0),
        "cumulative_pnl": summary.get("cumulative_pnl", 0.0),
        # July 2026 fix: this read a key that never existed
        # ("ytd_vs_nasdaq") and recorded 0.0 in every snapshot.
        "alpha_vs_nasdaq": tracker.get("alpha", {}).get("ytd_pct", 0.0),
    }
    snapshots.append(snapshot)
    if len(snapshots) > 24:
        del snapshots[0]
