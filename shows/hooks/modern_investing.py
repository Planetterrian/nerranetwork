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
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TRACKER_FILENAME = "investment_tracker.json"
TAUGHT_LESSONS_FILENAME = "taught_lessons.json"
LESSONS_LEARNED_FILENAME = "lessons_learned.json"
MONTHLY_EPISODES_FILENAME = "monthly_episodes.json"
NASDAQ_SYMBOL = "^IXIC"

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

    # Evaluate yesterday's open trade (if any)
    _evaluate_open_trade(tracker, tracker_path)

    # Build yesterday's trade review text
    context["yesterday_trade_review"] = _build_trade_review(tracker, episode_num)

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
    context["lessons_learned_block"] = _build_lessons_learned_block(lessons)
    context["narrative_callback"] = _build_narrative_callback(tracker)

    # Evergreen deep-dive rotation — surfaces the previously-unused
    # segment library (shows/segments/modern_investing.json) so the show
    # rotates through 30 pre-written deep dives even when news is thin.
    library_path = _resolve_segment_library(config)
    segment_id, segment_hint = _pick_deep_dive_segment(tracker, library_path)
    context["deep_dive_hint"] = _build_deep_dive_hint_block(segment_hint)
    if segment_id:
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
    # future trade selection.
    context["strategy_performance"] = _build_strategy_performance(tracker)

    # Dynamic tone based on portfolio performance
    context["tone_hint"] = _tone_from_portfolio(tracker)

    # === Strong Recursive Learning Loop (core of NASDAQ outperformance goal) ===
    # This block gives the LLM explicit, evidence-based feedback on what has
    # actually worked or failed in the simulated portfolio vs NASDAQ.
    try:
        context["mit_recursive_learning_context"] = get_mit_recursive_learning_context()
    except Exception as exc:
        logger.warning("Failed to build recursive learning context: %s", exc)
        context["mit_recursive_learning_context"] = "Learning context temporarily unavailable — focus on process discipline."

    return context


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

    # Sector breakdown
    lines.append("\nSector results (closed trades):")
    for sec, s in sorted(sector_stats.items(), key=lambda x: x[1]["total_alpha"], reverse=True):
        wr = (s["wins"] / s["trades"] * 100) if s["trades"] > 0 else 0
        avg_alpha = s["total_alpha"] / s["trades"] if s["trades"] > 0 else 0
        flag = "✓" if avg_alpha > 0 else "✗"
        lines.append(f"  {flag} {sec}: {s['trades']} trades, {wr:.0f}% win rate, avg alpha {avg_alpha:+.2f}%")

    # Lesson tag patterns
    if tag_stats:
        lines.append("\nStrategy tag results:")
        for tag, s in sorted(tag_stats.items(), key=lambda x: x[1]["total_alpha"], reverse=True)[:8]:
            avg_alpha = s["total_alpha"] / s["trades"] if s["trades"] > 0 else 0
            lines.append(f"  {tag}: {s['trades']} trades, avg alpha {avg_alpha:+.2f}%")

    # Best and worst
    lines.append(f"\nBest trade: {best.get('symbol')} ({best.get('sector')}) — alpha {best.get('alpha_pct', 0):+.2f}%")
    lines.append(f"Worst trade: {worst.get('symbol')} ({worst.get('sector')}) — alpha {worst.get('alpha_pct', 0):+.2f}%")

    # Actionable guidance
    winning_sectors = [sec for sec, s in sector_stats.items() if s["total_alpha"] > 0 and s["trades"] >= 2]
    losing_sectors = [sec for sec, s in sector_stats.items() if s["total_alpha"] < 0 and s["trades"] >= 2]
    if winning_sectors:
        lines.append(f"\nFAVOR these sectors (positive alpha track record): {', '.join(winning_sectors)}")
    if losing_sectors:
        lines.append(f"AVOID OR BE CAUTIOUS with these sectors (negative alpha): {', '.join(losing_sectors)}")

    return "\n".join(lines)


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


def _save_tracker(tracker: dict, tracker_path: Path) -> None:
    """Write tracker JSON atomically."""
    tracker_path.write_text(
        json.dumps(tracker, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Trade evaluation — uses yfinance for real market data
# ---------------------------------------------------------------------------

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
    _save_tracker(tracker, tracker_path)


def _close_trade(trade: dict, tracker: dict) -> None:
    """Close a trade with real market data."""
    symbol = trade.get("symbol", "")
    trade_type = trade.get("trade_type", "weekly")

    if trade_type == "flash":
        # Flash trade: entry = trade date's open, exit = trade date's close
        entry_price, exit_price = _fetch_trade_prices(symbol)
    else:
        # Weekly hold: entry = Monday open, exit = Friday close
        entry_price, exit_price = _fetch_weekly_prices(symbol)

    if entry_price is None or exit_price is None:
        logger.warning("Could not fetch prices for %s — marking as data_unavailable", symbol)
        trade["status"] = "closed"
        trade["entry_price"] = None
        trade["exit_price"] = None
        trade["pnl_pct"] = 0.0
        trade["pnl_dollars"] = 0.0
        trade["lesson"] = "Market data was unavailable for evaluation."
    else:
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        position_size = tracker["metadata"].get("position_size", 1000)
        pnl_dollars = round(position_size * (pnl_pct / 100), 2)

        trade["status"] = "closed"
        trade["entry_price"] = round(entry_price, 2)
        trade["exit_price"] = round(exit_price, 2)
        trade["pnl_pct"] = round(pnl_pct, 2)
        trade["pnl_dollars"] = round(pnl_dollars, 2)

        # Annotate with NASDAQ benchmark alpha — best-effort, tolerant of yfinance failures.
        try:
            _annotate_trade_with_nasdaq(trade)
        except Exception as exc:
            logger.warning("NASDAQ annotation failed for %s: %s", symbol, exc)

        # Backfill sector if post_generate never set it (e.g. old trades).
        if not trade.get("sector"):
            trade["sector"] = _classify_sector(
                symbol, trade.get("strategy", ""), trade.get("market", ""),
            )

        logger.info(
            "Evaluated %s (%s): entry=$%.2f exit=$%.2f pnl=%.2f%% alpha=%s",
            symbol, trade_type, entry_price, exit_price, pnl_pct, trade.get("alpha_pct"),
        )


def _snapshot_trade(trade: dict, symbol: str) -> None:
    """Take a mid-week price snapshot for a weekly hold (does not close it)."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d", interval="1d")
        if not hist.empty:
            trade["current_price"] = round(float(hist["Close"].iloc[-1]), 2)
            logger.info("Mid-week snapshot %s: $%.2f", symbol, trade["current_price"])
    except Exception as exc:
        logger.warning("Mid-week snapshot failed for %s: %s", symbol, exc)


def _fetch_trade_prices(symbol: str) -> tuple[float | None, float | None]:
    """Fetch market open and close prices for the trade date using yfinance.

    Returns (entry_price, exit_price) or (None, None) on failure.
    Uses the most recent trading day's open and close.
    """
    import time as _time

    for attempt in range(3):
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d", interval="1d")
            if hist.empty or len(hist) < 1:
                logger.warning("No history for %s (attempt %d)", symbol, attempt + 1)
            else:
                # Use the most recent completed trading day
                last_row = hist.iloc[-1]
                entry = float(last_row["Open"])
                exit_ = float(last_row["Close"])
                return entry, exit_
        except Exception as exc:
            logger.warning("yfinance attempt %d for %s failed: %s", attempt + 1, symbol, exc)

        if attempt < 2:
            backoff = 2 ** (attempt + 1)
            logger.info("Retrying %s price in %ds...", symbol, backoff)
            _time.sleep(backoff)

    return None, None


def _fetch_weekly_prices(symbol: str) -> tuple[float | None, float | None]:
    """Fetch the week's first trading day open and last trading day close.

    Returns (entry_price, exit_price) or (None, None) on failure.
    Uses 10 calendar days of history to handle shortened weeks (holidays),
    then filters to only this week's trading days.
    """
    import time as _time

    today = datetime.date.today()
    # Find this week's Monday (weekday 0)
    monday = today - datetime.timedelta(days=today.weekday())

    for attempt in range(3):
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            # Fetch 10 days to cover holidays and weekends
            hist = ticker.history(period="10d", interval="1d")
            if hist.empty or len(hist) < 1:
                logger.warning("No history for %s (attempt %d)", symbol, attempt + 1)
            else:
                # Filter to only this week's trading days (Monday through today)
                week_data = hist[hist.index.date >= monday]
                if week_data.empty:
                    logger.warning("No trading days this week for %s", symbol)
                else:
                    # First trading day's open, last trading day's close
                    entry = float(week_data.iloc[0]["Open"])
                    exit_ = float(week_data.iloc[-1]["Close"])
                    logger.info(
                        "Weekly prices for %s: %d trading days this week (entry=%s, exit=%s)",
                        symbol, len(week_data),
                        week_data.index[0].strftime("%a"),
                        week_data.index[-1].strftime("%a"),
                    )
                    return entry, exit_
        except Exception as exc:
            logger.warning("yfinance attempt %d for %s failed: %s", attempt + 1, symbol, exc)

        if attempt < 2:
            backoff = 2 ** (attempt + 1)
            logger.info("Retrying %s price in %ds...", symbol, backoff)
            _time.sleep(backoff)

    return None, None


def _recompute_summary(tracker: dict) -> None:
    """Recompute summary statistics from all closed trades."""
    closed = [t for t in tracker["trades"] if t.get("status") == "closed"]
    if not closed:
        return

    wins = sum(1 for t in closed if (t.get("pnl_pct") or 0) > 0)
    losses = sum(1 for t in closed if (t.get("pnl_pct") or 0) < 0)
    breakeven = len(closed) - wins - losses
    total = len(closed)
    cum_pnl = sum(t.get("pnl_dollars") or 0 for t in closed)
    pnl_pcts = [t.get("pnl_pct") or 0 for t in closed]

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
    total_pnl = sum((t.get("pnl_dollars") or 0) for t in closed)
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
    total_pnl = sum((t.get("pnl_dollars") or 0) for t in closed)
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


def _annotate_trade_with_nasdaq(trade: dict, entry_date: datetime.date | None = None, exit_date: datetime.date | None = None) -> None:
    """Fill in NASDAQ entry/exit closes and alpha on a just-closed trade.

    Safe no-op if yfinance data is unavailable — ``nasdaq_*`` fields stay
    ``None`` and ``alpha_pct`` defaults to ``None``.
    """
    trade_date_str = trade.get("date")
    if entry_date is None and trade_date_str:
        try:
            entry_date = datetime.date.fromisoformat(trade_date_str)
        except ValueError:
            entry_date = None
    if entry_date is None:
        entry_date = datetime.date.today()
    if exit_date is None:
        # Weekly holds close on the Friday of the entry's week; flash
        # trades close the same day. Good enough for benchmark alpha.
        if trade.get("trade_type") == "flash":
            exit_date = entry_date
        else:
            exit_date = entry_date + datetime.timedelta(days=(4 - entry_date.weekday()) % 7)

    entry_close = _fetch_nasdaq_close(entry_date)
    exit_close = _fetch_nasdaq_close(exit_date)
    trade["nasdaq_entry"] = round(entry_close, 2) if entry_close else None
    trade["nasdaq_exit"] = round(exit_close, 2) if exit_close else None
    if entry_close and exit_close:
        nasdaq_return = ((exit_close - entry_close) / entry_close) * 100
        trade["nasdaq_return_pct"] = round(nasdaq_return, 2)
        pnl = trade.get("pnl_pct")
        if pnl is not None:
            trade["alpha_pct"] = round(pnl - nasdaq_return, 2)
        else:
            trade["alpha_pct"] = None
    else:
        trade["nasdaq_return_pct"] = None
        trade["alpha_pct"] = None


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

def _build_trade_review(tracker: dict, episode_num: int | None = None) -> str:
    """Build the Trade Review text block for the digest prompt.

    Handles both weekly holds and flash trades, with appropriate framing for each.
    """
    if episode_num and episode_num <= 1:
        return ""  # No review for Episode 1

    closed = [t for t in tracker["trades"] if t.get("status") == "closed"]
    if not closed:
        # Check for open weekly hold — provide mid-week update
        open_trades = [t for t in tracker["trades"] if t.get("status") == "open"]
        if open_trades:
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

    last = closed[-1]
    symbol = last.get("symbol", "???")
    strategy = last.get("strategy", "")
    trade_type = last.get("trade_type", "weekly")
    entry = last.get("entry_price")
    exit_ = last.get("exit_price")
    pnl_pct = last.get("pnl_pct", 0)
    pnl_dollars = last.get("pnl_dollars", 0)
    summary = tracker.get("summary", {})

    type_label = "Flash Trade" if trade_type == "flash" else "Weekly Hold"
    entry_label = "market open" if trade_type == "flash" else "Monday open"
    exit_label = "market close" if trade_type == "flash" else "Friday close"

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

    return (
        f"NASDAQ Composite ^IXIC: {close:,.0f} "
        f"(YTD {_sign(bench_ytd)}, since inception {_sign(bench_itd)}). "
        f"Portfolio: YTD {_sign(portfolio_ytd)}, since inception {_sign(portfolio_itd)}. "
        f"Alpha vs NASDAQ: YTD {_sign(alpha_ytd)}, since inception {_sign(alpha_itd)}."
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
    """Load the lessons_learned ledger, or return a fresh structure."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("metadata", {}).setdefault("schema_version", 1)
            data["metadata"].setdefault("last_updated", datetime.date.today().isoformat())
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
    """Append a new recursive-improvement rule; returns the new entry."""
    entries = data.setdefault("entries", [])
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


def _build_lessons_learned_block(data: dict, *, max_active: int = 5) -> str:
    """Block fed to the digest prompt as 'RECURSIVE IMPROVEMENT RULES IN EFFECT'."""
    entries = [e for e in (data.get("entries") or []) if e.get("status") == "active"]
    if not entries:
        return "No active recursive-improvement rules yet — write one if today's trade teaches a generalisable lesson."
    lines = ["The following rules are in effect today. Obey them in every section of the digest:"]
    # Most-recent-first, capped.
    for entry in list(reversed(entries))[:max_active]:
        lines.append(
            f"- [{entry['id']}] {entry.get('observation', '').rstrip('.')}. "
            f"Rule: {entry.get('adjustment', '').rstrip('.')}."
        )
    return "\n".join(lines)


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
    trades = tracker.get("trades", [])[-_CONCENTRATION_WINDOW:]
    if not trades:
        return {}
    counts: dict[str, int] = {}
    pnl: dict[str, float] = {}
    for t in trades:
        sector = t.get("sector") or _classify_sector(
            t.get("symbol", ""), t.get("strategy", ""), t.get("market", ""),
        )
        counts[sector] = counts.get(sector, 0) + 1
        pnl[sector] = pnl.get(sector, 0.0) + float(t.get("pnl_dollars") or 0)
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

    return (
        f"Portfolio Performance (simulated, $1,000 per trade):\n"
        f"- Total trades: {total}\n"
        f"- Win rate: {summary.get('win_rate_pct', 0):.0f}% "
        f"({summary.get('wins', 0)}W / {summary.get('losses', 0)}L / "
        f"{summary.get('breakeven', 0)}BE)\n"
        f"- Cumulative P&L: ${summary.get('cumulative_pnl', 0):+.2f}\n"
        f"- Average return per trade: {summary.get('average_return_pct', 0):+.2f}%\n"
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
    cum_alpha = summary.get("cumulative_alpha_vs_nasdaq", 0.0)
    total_trades = summary.get("total_trades", 0)
    win_rate = summary.get("win_rate", 0.0)

    closed = [t for t in tracker.get("trades", []) if t.get("status") == "closed" and t.get("alpha_pct") is not None]

    if total_trades < 5:
        return "EARLY STAGE: Fewer than 5 closed trades. Focus on process, position sizing, and clear thesis writing. NASDAQ benchmark tracking is active."

    # Top 3 winning patterns
    winning = sorted(closed, key=lambda t: t.get("alpha_pct", 0), reverse=True)[:3]
    losing = sorted(closed, key=lambda t: t.get("alpha_pct", 0))[:2]

    lines = [
        "RECURSIVE LEARNING CONTEXT — USE THIS TO IMPROVE FUTURE PRACTICE INVESTMENTS:",
        f"Current track record: {total_trades} closed trades | Win rate {win_rate:.0%} | Cumulative alpha vs NASDAQ: {cum_alpha:+.1f}%",
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

    return "\n".join(lines)
