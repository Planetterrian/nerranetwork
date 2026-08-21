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

from engine import show_memory


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

# ---------------------------------------------------------------------------
# Trading policy (2026-08-18) — the rules live in shows/_trading_policy.yaml
# ---------------------------------------------------------------------------

POLICY_PATH = Path(__file__).resolve().parents[1] / "_trading_policy.yaml"

_POLICY_FALLBACK = {
    "version": 2,
    "era": {"name": "Era 2 — rules-based", "inception_date": "2026-08-18"},
    "position_size_usd": 1000,
    "entry": {"max_days_to_fill": 10},
    "exit": {"horizon_sessions": {"weekly": 5, "flash": 1}},
    "reporting": {"min_trades_for_rate_claims": 5,
                  "significance_t_threshold": 2.0},
}


def load_policy() -> dict:
    """The simulated-trading rulebook, or a pinned fallback.

    Read once per process. A missing or unparseable file must not stop an
    episode — but it must not silently change the rules either, so the
    fallback mirrors the committed file and says so in the log.
    """
    global _POLICY_CACHE
    if _POLICY_CACHE is not None:
        return _POLICY_CACHE
    try:
        import yaml
        with open(POLICY_PATH, encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        if not loaded.get("exit", {}).get("horizon_sessions"):
            raise ValueError("policy missing exit.horizon_sessions")
        _POLICY_CACHE = loaded
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Trading policy unreadable (%s) — using the pinned fallback. "
            "Entry/exit rules are UNCHANGED; fix %s.", exc, POLICY_PATH,
        )
        _POLICY_CACHE = dict(_POLICY_FALLBACK)
    return _POLICY_CACHE


_POLICY_CACHE: dict | None = None


def era_inception() -> datetime.date | None:
    """First pick date counted in the on-air track record."""
    raw = (load_policy().get("era") or {}).get("inception_date")
    try:
        return datetime.date.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def horizon_sessions(trade_type: str) -> int:
    """Sessions a trade is held before the scheduled exit."""
    table = (load_policy().get("exit") or {}).get("horizon_sessions") or {}
    default = 1 if trade_type == "flash" else 5
    try:
        return max(1, int(table.get(trade_type, default)))
    except (TypeError, ValueError):
        return default


def _in_era(trade: dict) -> bool:
    """True when the trade was picked on/after the era inception date."""
    start = era_inception()
    if start is None:
        return True
    pick = _trade_pick_date(trade)
    return pick is not None and pick >= start


# How stale a closed trade may be and still be narrated in the Trade
# Review segment. Anything older is retired unreviewed rather than
# presented as a fresh result (August 2026 review — see
# ``_build_trade_review``). Two weeks covers a missed weekly hold plus
# the weekend either side; the 43-trade historical backlog is far
# outside it and drains on the first run without ever reaching air.
REVIEW_BACKLOG_MAX_DAYS = 14

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

    # One-off methodology correction (August 2026). Stamps the tracker the
    # same way the trade review does, so it rides the save below rather
    # than risking a re-air if a later step raises.
    context["methodology_disclosure"] = _build_methodology_disclosure(
        tracker, episode_num)

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
    context["strategy_family_performance"] = (
        _build_strategy_family_performance(tracker))
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

    # Narrative memory (July 24 2026): the market-narrative layer the
    # investment tracker can't hold (rate cycle, AI-infra trade, Canadian
    # wealth mechanics …). Gated on config.memory_enabled; returns the
    # {narrative_memory_section} key (empty string when disabled) so the
    # prompt placeholder never KeyErrors.
    context.update(show_memory.memory_pre_fetch(config, "modern_investing"))

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
# July 18 2026 recalibration: the original mean-based trigger (avg < -0.5
# or drawdown > $100) DEADLOCKED the show — one -11.8% outlier (Ep81 MDA)
# poisoned the rolling mean, $164 of standing drawdown tripped the $100
# threshold permanently, and the cold streak suppressed the very trades
# that would refresh the window. Both Monday weekly picks were skipped
# and the signature segment went dark 12 of 14 episodes. Now: MEDIAN
# (outlier-robust), a full-position drawdown threshold, and an escape
# valve — a pick drought longer than a week downgrades COLD to a
# SELECTIVE reset so the show trades (and teaches) again.
_REGIME_COLD_MEDIAN = -1.0
_REGIME_COLD_DRAWDOWN = 250.0
_REGIME_PICK_DROUGHT_DAYS = 7


def _days_since_last_pick(tracker: dict) -> int | None:
    dates = []
    for t in tracker.get("trades", []):
        d = t.get("date")
        if isinstance(d, str):
            try:
                dates.append(datetime.date.fromisoformat(d))
            except ValueError:
                continue
    if not dates:
        return None
    return (datetime.date.today() - max(dates)).days


def _build_regime_block(tracker: dict) -> str:
    """Adaptive selectivity from the rolling record (July 2026).

    Turns the rolling last-``_REGIME_WINDOW`` MEDIAN matched-window alpha
    + the drawdown from the P&L high-water mark into explicit selection
    pressure. A cold streak raises the bar; a hot streak holds discipline
    flat (never "press harder"); a pick drought releases the brake so the
    practice segment keeps teaching. Deterministic — thresholds are code.
    """
    closed = [t for t in tracker.get("trades", []) if t.get("status") == "closed"]
    scored = [
        t for t in closed
        if isinstance(t.get("alpha_pct"), (int, float))
        and math.isfinite(t["alpha_pct"])
    ]
    if len(scored) < 5:
        return ""
    recent = [t["alpha_pct"] for t in scored[-_REGIME_WINDOW:]]
    median_alpha = sorted(recent)[len(recent) // 2] if len(recent) % 2 else (
        sum(sorted(recent)[len(recent) // 2 - 1:len(recent) // 2 + 1]) / 2)
    wins = sum(1 for t in scored[-_REGIME_WINDOW:]
               if _finite(t.get("pnl_pct")) > 0)

    # Drawdown from the cumulative-P&L high-water mark (all closed trades).
    running = peak = 0.0
    for t in closed:
        running += _finite(t.get("pnl_dollars"))
        peak = max(peak, running)
    drawdown = round(peak - running, 2)

    header = (
        f"REGIME CHECK (rolling last {len(recent)} closed trades): "
        f"median matched-window alpha {median_alpha:+.2f}%, {wins}/{len(recent)} "
        f"wins, ${drawdown:.2f} below the P&L high-water mark."
    )
    is_cold = (median_alpha < _REGIME_COLD_MEDIAN
               or drawdown > _REGIME_COLD_DRAWDOWN)
    drought = _days_since_last_pick(tracker)
    if is_cold and drought is not None and drought > _REGIME_PICK_DROUGHT_DAYS:
        guidance = (
            f" SELECTIVE RESET — the record is cold but the show has made "
            f"no pick in {drought} days, and an extended drought teaches "
            f"nothing. Take the best available setup (a Monday weekly hold "
            f"is expected), state honestly that conviction is moderate and "
            f"the playbook is rebuilding, and keep the risk framing tight. "
            f"A no-trade day now requires a REASON specific to today's "
            f"tape, not the streak."
        )
    elif is_cold:
        guidance = (
            " COLD STREAK — RAISE THE BAR for today's Practice Investment: "
            "an explicit no-trade day is acceptable and unremarkable, and "
            "a pick needs 3+ independent aligned factors. Do not chase a "
            "comeback. TELL LISTENERS PLAINLY that the playbook is in "
            "capital-preservation mode after the recent drawdown and what "
            "would re-open normal trading — that transparency is part of "
            "the product, not an admission of failure."
        )
    elif median_alpha > 1.0:
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
        # Stop-loss capture (July 2026): store the narrated stop so the
        # close-time evaluation can ENFORCE it (and the future live layer
        # can attach it to a bracket order). None when unparseable — the
        # sim never invents a stop the show didn't state.
        stop = _extract_stop_loss(digest_text)
        if stop:
            trade["stop_loss"] = stop
        # Rule-effectiveness stamping (July 2026): record which
        # recursive-improvement rules were shown to the model when it made
        # this pick. Read BEFORE today's lesson is appended below, so the
        # stamp reflects exactly the pick-day prompt. The rule scoreboard
        # scores these stamps once trades close.
        try:
            pick_day_lessons = _load_lessons_learned(
                output_dir / LESSONS_LEARNED_FILENAME)
            trade["rules_in_effect"] = [
                e["id"] for e in _selected_active_rules(
                    pick_day_lessons, episode_num=episode_num,
                    tracker=tracker)
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
        # Options position (2026-08-19): quote the contract NOW, because
        # a premium cannot be reconstructed later from free data. If the
        # chain cannot be quoted the position degrades to plain long
        # equity — the sim never fills an option at an estimated price.
        if trade.get("structure") in OPTION_STRUCTURES:
            try:
                ref = trade.get("pick_reference_price") or trade.get("current_price")
                pos = build_option_position(
                    trade.get("resolved_symbol") or trade.get("symbol", ""),
                    trade["structure"],
                    _trade_pick_date(trade) or datetime.date.today(),
                    float(ref) if ref else 0.0,
                ) if ref else None
            except Exception as exc:  # noqa: BLE001
                logger.warning("option quote failed for %s: %s",
                               trade.get("symbol"), exc)
                pos = None
            if pos:
                trade["option"] = pos
                logger.info(
                    "%s: %s %s $%s strike, premium $%s (capital $%s)",
                    trade.get("symbol"), pos["structure"], pos["expiry"],
                    pos["strike"], pos["premium"], pos["capital_usd"],
                )
            else:
                print(
                    f"::warning::modern_investing: could not quote a "
                    f"{trade['structure']} on {trade.get('symbol')} — "
                    f"recorded as long equity instead. The premium is never "
                    f"estimated.", flush=True,
                )
                trade["structure"] = "long_equity"
                trade["option_quote_failed"] = True

        # Wrong-instrument tripwire (July 24 2026, Ep113 BTC): if the
        # narrated stop and the resolved listing's price are on different
        # scales, the resolution is wrong — void at record time so the
        # sim never prices it and the execution layers never see it.
        if _instrument_scale_mismatch(trade):
            logger.error(
                "PICK VOIDED AT RECORD: %s stop $%s vs reference $%s — the "
                "resolved listing is not the instrument the show discussed. "
                "Check the digest's Today's Pick symbol format.",
                trade.get("symbol"),
                (trade.get("stop_loss") or {}).get("price"),
                trade.get("pick_reference_price"),
            )
            trade["status"] = "voided"
            trade["void_reason"] = "instrument_scale_mismatch"
            trade["lesson"] = (
                "Trade voided — the price tracker resolved the wrong "
                "instrument for this symbol."
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

    # Execution bridge (July 2026 live-trading prep): emit a
    # machine-readable trade signal for the (future, isolated) SnapTrade
    # execution layer. The executor consumes THIS artifact — never the
    # digest prose — so LLM formatting drift can't reach an order ticket.
    # Best-effort: a signal-write failure must never block the pipeline.
    try:
        # A trade voided at record time must never reach the execution
        # layers — the signal carries an explicit no_trade with the void
        # reason instead (fail-closed for shadow AND live).
        if trade is not None and trade.get("status") == "voided":
            _write_trade_signal(
                output_dir, None, digest_text, episode_num, tracker,
                override_reason=trade.get("void_reason") or "pick_voided",
            )
        else:
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

    # Narrative-memory mining (July 24 2026): theme history + per-program
    # freshness from the just-generated digest. Gated on memory_enabled;
    # honors NERRA_HOOKS_READONLY via the readonly guard at the top of
    # this function (we only reach here on live runs).
    show_memory.memory_post_generate(
        config, "modern_investing", digest_text or "", episode_num or 0)


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
    _void_instrument_scale_mismatch_trades(tracker)


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
    # Already exchange-suffixed or crypto-quoted (CNR.TO, BTC-USD): the
    # digest named the exact listing — use it verbatim, never re-suffix.
    if "." in sym or sym.endswith("-USD"):
        return [sym]
    m = (market or "").upper().replace("_", "-").strip()
    if m in ("TSX-V", "TSXV"):
        return [f"{sym}.V", f"{sym}.TO", sym]
    if m == "TSX":
        return [f"{sym}.TO", sym]
    if m == "CRYPTO":
        # Yahoo quotes spot crypto as <SYM>-USD. The bare symbol is NOT a
        # safe fallback here — "BTC" resolves to an unrelated equity
        # (the Ep113 wrong-instrument shape), so crypto never falls back.
        return [f"{sym}-USD"]
    return [sym]


def _trade_symbol_candidates(trade: dict) -> list[str]:
    """Candidates for an existing trade — a pick-time resolution wins."""
    resolved = trade.get("resolved_symbol")
    if resolved:
        return [resolved]
    return _yf_symbol_candidates(trade.get("symbol", ""), trade.get("market", ""))


def _bars_from_history(hist) -> list[tuple]:
    """Convert a yfinance history frame to ``[(bar_date, open, close, low)]``.

    Bars with a non-finite open or close are dropped — yfinance returns
    NaN floats for halted/missing bars (the DELL/HIMS shape) and a NaN
    must never become an entry or exit price. The intraday ``low`` (July
    2026 stop-enforcement pass) is best-effort: ``None`` when the column
    is missing/NaN, and every consumer treats bars as len>=3 tuples so
    3-tuple fixtures keep working.
    """
    bars: list[tuple] = []
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
        try:
            low = float(row["Low"])
            if not math.isfinite(low):
                low = None
        except (KeyError, TypeError, ValueError):
            low = None
        bar_date = idx.date() if hasattr(idx, "date") else idx
        bars.append((bar_date, open_, close, low))
    return bars


def _bar_low(bar) -> float | None:
    """Intraday low of a bar tuple; None for legacy 3-tuple bars."""
    if len(bar) > 3 and isinstance(bar[3], (int, float)):
        return bar[3]
    return None


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

# Explicit no-trade markers (July 18 2026 review): the original regex only
# matched "Today's Pick: No…"; two weeks of real digests used
# "**Today's Pick:** None", "**Trade Type:** No new trade" and
# "**Trade Type:** No Trade" — all deliberate no-trade days that the
# signal then mislabeled "no_pick_extracted" (extraction drift), making
# the drift alarm meaningless. Recognize every observed deliberate form.
_EXPLICIT_NO_TRADE_RE = re.compile(
    r"(?:Today's Pick[:*\s]+(?:No\b|None\b|—?\s*None)"
    r"|Trade Type[:*\s]+No(?:\s+new)?\s+[Tt]rade"
    r"|Trade Type[:*\s]+Mid-?Week Update)",
    re.IGNORECASE,
)


_SCALE_MISMATCH_FACTOR = 3.0


def _instrument_scale_mismatch(trade: dict) -> bool:
    """True when the narrated stop and the resolved instrument's price are
    on wildly different scales — the wrong-instrument tripwire.

    July 24 2026 (Ep113): the digest picked Bitcoin ("BTC-USD", stop
    $64,500) but the tracker resolved bare "BTC" to an equity at $28.80
    and marked the pick VALIDATED; the shadow executor then would_place'd
    $1,000 of the wrong instrument. A stop 2,200× the reference price is
    not a stop — it's proof the resolved listing is not the instrument
    the show talked about. Anything outside [ref/3, ref*3] trips.
    """
    stop = trade.get("stop_loss")
    ref = trade.get("pick_reference_price") or trade.get("entry_price")
    if not (isinstance(stop, dict) and isinstance(ref, (int, float)) and ref > 0):
        return False
    price = stop.get("price")
    if not (isinstance(price, (int, float)) and price > 0):
        return False
    ratio = price / ref
    return ratio > _SCALE_MISMATCH_FACTOR or ratio < 1.0 / _SCALE_MISMATCH_FACTOR


def _void_instrument_scale_mismatch_trades(tracker: dict) -> None:
    """One-time/self-healing migration: void trades whose stop price and
    reference/entry price sit on different scales (wrong instrument).

    Covers the shipped Ep113 BTC state (open, resolved to the wrong
    equity) AND any close that happened against the wrong listing before
    this fix merged. Mirrors ``_void_nonfinite_closed_trades``: voided
    trades leave every aggregate and are never narrated as outcomes.
    """
    for trade in tracker.get("trades", []):
        if trade.get("status") == "voided":
            continue
        if _instrument_scale_mismatch(trade):
            logger.error(
                "VOIDING trade Ep%s %s: stop $%s vs reference $%s — "
                "instrument scale mismatch (wrong listing resolved).",
                trade.get("episode_num"), trade.get("symbol"),
                (trade.get("stop_loss") or {}).get("price"),
                trade.get("pick_reference_price") or trade.get("entry_price"),
            )
            trade["status"] = "voided"
            trade["void_reason"] = "instrument_scale_mismatch"
            trade["pnl_pct"] = None
            trade["pnl_dollars"] = None
            trade["lesson"] = (
                "Trade voided — the price tracker resolved the wrong "
                "instrument for this symbol."
            )


def _no_trade_reason(digest_text: str) -> str:
    """Classify why today's signal carries no trade.

    - ``explicit_no_trade`` — the digest deliberately declared no pick
      (or a mid-week update, which by design creates no new trade);
    - ``no_practice_section`` — no Practice Investment section at all
      (weekend/recap episodes);
    - ``no_pick_extracted`` — a pick section exists but nothing matched:
      the only remaining case that genuinely means formatting drift.
    """
    if not digest_text:
        return "no_practice_section"
    if _EXPLICIT_NO_TRADE_RE.search(digest_text):
        return "explicit_no_trade"
    if re.search(r"Today's Pick|Practice Investment", digest_text,
                 re.IGNORECASE):
        return "no_pick_extracted"
    return "no_practice_section"

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
    *,
    override_reason: str | None = None,
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
        signal["action"] = "no_trade"
        signal["reason"] = override_reason or _no_trade_reason(digest_text)
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
            "stop_loss": trade.get("stop_loss"),
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
    # Hold exactly ``horizon`` sessions (2026-08-18 policy). Returning
    # window[-1] made the exit whatever bar the evaluating run happened to
    # see: the Friday pre-market run prices THURSDAY, so a Wednesday pick
    # closed after one session and a Monday pick after four, from the same
    # rule. Across the ten trades with trustworthy windows the holds ran
    # 0-6 sessions against picks written to a five-day thesis, so per-trade
    # alpha measured pick quality and pick weekday together. The exit index
    # is now fixed at entry time and does not depend on when the sim looks.
    horizon = horizon_sessions("weekly")
    if len(window) < horizon:
        return window[0], None  # not enough sessions yet — stay open
    return window[0], window[horizon - 1]


_STOP_PRICE_RE = re.compile(
    r"stop[- ]?loss[^.\n%$]{0,60}?\$\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_STOP_PCT_RE = re.compile(
    r"stop[- ]?loss[^.\n%$]{0,60}?(\d{1,2}(?:\.\d+)?)\s*%", re.IGNORECASE)


def _extract_stop_loss(digest_text: str) -> dict | None:
    """Pull the narrated stop-loss from the Practice Investment section.

    July 2026 fidelity pass: the digest states a stop-loss level in every
    Risk Assessment, but the sim never enforced it — losers rode to the
    scheduled exit while the show TAUGHT stop discipline. Returns
    ``{"price": x}`` or ``{"pct": y}`` (percent below entry), or ``None``
    when no parseable stop exists (enforcement simply doesn't apply —
    never guess one).
    """
    if not digest_text:
        return None
    # Scope to the Practice Investment block when present so a stop
    # mentioned in the education section can't leak onto the trade.
    section = digest_text
    m = re.search(r"### Practice Investment.*?(?=\n### |\Z)", digest_text,
                  re.DOTALL | re.IGNORECASE)
    if m:
        section = m.group(0)
    price_m = _STOP_PRICE_RE.search(section)
    if price_m:
        try:
            return {"price": float(price_m.group(1).replace(",", ""))}
        except ValueError:
            pass
    pct_m = _STOP_PCT_RE.search(section)
    if pct_m:
        try:
            pct = float(pct_m.group(1))
            if 0 < pct < 50:
                return {"pct": pct}
        except ValueError:
            pass
    return None


def _stop_breach(bars, entry_bar, exit_bar, stop_price: float):
    """First bar in (entry, exit] whose low (or close) breaches the stop.

    Returns ``(bar_date, exit_price)`` or ``None``. Gap-aware: a bar that
    OPENS below the stop fills at its open (a real stop order can't fill
    better than the gap), otherwise the stop price itself is used. The
    entry bar is excluded — intraday ordering within the entry bar is
    unknowable from daily data, so same-day breaches are not claimed.
    """
    if stop_price is None or entry_bar is None or exit_bar is None:
        return None
    for bar in bars:
        if bar[0] <= entry_bar[0] or bar[0] > exit_bar[0]:
            continue
        low = _bar_low(bar)
        probe = low if low is not None else bar[2]
        if probe <= stop_price:
            fill = min(stop_price, bar[1])  # gap-through fills at the open
            return bar[0], round(fill, 2)
    return None


def _trade_pick_date(trade: dict) -> datetime.date | None:
    d = trade.get("date")
    if isinstance(d, str):
        try:
            return datetime.date.fromisoformat(d)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Options positions (2026-08-19) — real quotes in, exact arithmetic out
# ---------------------------------------------------------------------------

OPTION_STRUCTURES = ("covered_call", "cash_secured_put")


def _options_policy() -> dict:
    return (load_policy().get("options") or {})


def _fetch_option_chain(symbol: str, expiry: str, *, attempts: int = 3):
    """(calls, puts) for one expiry, or None.

    yfinance for the same reason every other price path here uses it: it
    manages Yahoo's cookie/crumb session, which the bare HTTP endpoints
    now require. Returns None on total failure — and None must never be
    turned into an estimated premium downstream.
    """
    import time as _time
    for attempt in range(attempts):
        try:
            import yfinance as yf
            chain = yf.Ticker(symbol).option_chain(expiry)
            return (
                chain.calls.to_dict("records"),
                chain.puts.to_dict("records"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("option chain attempt %d for %s %s failed: %s",
                           attempt + 1, symbol, expiry, exc)
        if attempt < attempts - 1:
            _time.sleep(2 ** (attempt + 1))
    return None


def _list_option_expiries(symbol: str) -> list[str] | None:
    try:
        import yfinance as yf
        return list(yf.Ticker(symbol).options or [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("option expiry list for %s failed: %s", symbol, exc)
        return None


def _select_expiry(expiries, pick_date: datetime.date) -> str | None:
    """Nearest listed expiry inside the policy's day window.

    A rule, not a preference: given the pick date and the listed expiries,
    every reader picks the same one.
    """
    pol = (_options_policy().get("expiry") or {})
    lo = int(pol.get("min_days", 21))
    hi = int(pol.get("max_days", 45))
    best = None
    for raw in (expiries or []):
        try:
            d = datetime.date.fromisoformat(str(raw))
        except ValueError:
            continue
        days = (d - pick_date).days
        if lo <= days <= hi and (best is None or days < best[0]):
            best = (days, raw)
    return best[1] if best else None


def _contract_premium(row: dict) -> float | None:
    """Mid of bid/ask, else lastPrice. Never a guess, never zero."""
    pol = (_options_policy().get("premium") or {})
    bid, ask = row.get("bid"), row.get("ask")
    if (isinstance(bid, (int, float)) and isinstance(ask, (int, float))
            and bid > 0 and ask > 0 and ask >= bid):
        return round((bid + ask) / 2, 4)
    if pol.get("source") == "mid_of_bid_ask":
        last = row.get("lastPrice")
        if isinstance(last, (int, float)) and last > 0:
            return round(float(last), 4)
    return None


def _select_contract(rows, underlying: float, structure: str):
    """The listed strike closest to the policy's OTM target, with a real quote.

    Returns (strike, premium) or None. Contracts with no usable quote are
    skipped rather than filled at a made-up price, so a thin chain
    produces no trade instead of a fictional one.
    """
    pol = (_options_policy().get("strike") or {})
    target_pct = float(pol.get("target_otm_pct", 4.0))
    if not rows or not underlying or underlying <= 0:
        return None
    if structure == "covered_call":
        target = underlying * (1 + target_pct / 100)
    else:
        target = underlying * (1 - target_pct / 100)

    best = None
    for row in rows:
        strike = row.get("strike")
        if not isinstance(strike, (int, float)) or strike <= 0:
            continue
        # Only genuinely out-of-the-money strikes: an in-the-money covered
        # call is a different trade than the one the show describes.
        if structure == "covered_call" and strike <= underlying:
            continue
        if structure == "cash_secured_put" and strike >= underlying:
            continue
        premium = _contract_premium(row)
        if premium is None:
            continue
        gap = abs(strike - target)
        if best is None or gap < best[0]:
            best = (gap, float(strike), premium)
    return (best[1], best[2]) if best else None


def build_option_position(symbol: str, structure: str, pick_date: datetime.date,
                          underlying: float) -> dict | None:
    """A fully-specified options position, or None.

    None means "could not be quoted" and the caller must fall back to an
    equity trade — never to an invented premium.
    """
    if structure not in OPTION_STRUCTURES:
        return None
    expiries = _list_option_expiries(symbol)
    expiry = _select_expiry(expiries, pick_date)
    if not expiry:
        logger.warning("%s: no listed expiry in the policy window — no option "
                       "trade today", symbol)
        return None
    chain = _fetch_option_chain(symbol, expiry)
    if not chain:
        return None
    calls, puts = chain
    rows = calls if structure == "covered_call" else puts
    picked = _select_contract(rows, underlying, structure)
    if not picked:
        logger.warning("%s %s: no strike with a usable quote — no option trade",
                       symbol, expiry)
        return None
    strike, premium = picked
    contracts = int(_options_policy().get("contracts", 1) or 1)
    shares = 100 * contracts
    capital = (underlying if structure == "covered_call" else strike) * shares
    return {
        "structure": structure,
        "expiry": expiry,
        "strike": round(strike, 4),
        "premium": premium,
        "contracts": contracts,
        "underlying_entry": round(underlying, 4),
        "capital_usd": round(capital, 2),
        "premium_received_usd": round(premium * shares, 2),
        "quoted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "quote_source": "yahoo_option_chain",
    }


def option_payoff(position: dict, underlying_close: float) -> dict:
    """Exact payoff at expiry. No pricing model, no free parameters.

    Covered call: hold 100 shares per contract and sell a call.
      settle = min(close, strike) * shares + premium * shares
    Cash-secured put: set aside strike * shares and sell a put.
      settle = capital + premium*shares - max(0, strike - close) * shares

    Both reduce to arithmetic on the underlying's closing price, which is
    why a reader with public data can reproduce them exactly.
    """
    structure = position.get("structure")
    shares = 100 * int(position.get("contracts", 1) or 1)
    strike = float(position["strike"])
    premium = float(position["premium"])
    capital = float(position["capital_usd"])
    close = float(underlying_close)

    if structure == "covered_call":
        share_value = min(close, strike) * shares
        pnl = share_value + premium * shares - capital
        assigned = close > strike
    elif structure == "cash_secured_put":
        pnl = premium * shares - max(0.0, strike - close) * shares
        assigned = close < strike
    else:
        raise ValueError(f"unknown option structure: {structure!r}")

    return {
        "pnl_dollars": round(pnl, 2),
        "pnl_pct": round((pnl / capital) * 100, 4) if capital else 0.0,
        "assigned": assigned,
        "underlying_exit": round(close, 4),
    }


def _sessions_since_pick(bars, pick_date) -> int:
    """How many sessions have printed on/after the pick date.

    Session 1 is the entry bar itself, so a weekly hold with a 5-session
    horizon closes once this reaches 5. Returns 0 when bars are missing —
    a fetch failure must read as "not due yet", never as "due now", or a
    bad network day would close every open trade at whatever price came
    back.
    """
    if not bars:
        return 0
    if pick_date is None:
        return len(bars)
    return sum(1 for b in bars if b[0] >= pick_date)


def _stop_already_breached(trade: dict, bars, pick_date) -> bool:
    """True when a narrated stop was hit before the scheduled exit.

    Only a cheap pre-check so a stopped-out trade does not sit open for
    the rest of its horizon; ``_close_trade`` does the authoritative
    gap-aware fill. Entry-bar breaches are deliberately not claimed —
    daily bars cannot show whether the low came before or after the open.
    """
    stop = trade.get("stop_loss")
    if not isinstance(stop, dict) or not bars:
        return False
    window = [b for b in bars if pick_date is None or b[0] >= pick_date]
    if len(window) < 2:
        return False
    entry_price = window[0][1]
    if isinstance(stop.get("price"), (int, float)):
        stop_price = float(stop["price"])
    elif isinstance(stop.get("pct"), (int, float)):
        stop_price = entry_price * (1 - float(stop["pct"]) / 100)
    else:
        return False
    for bar in window[1:]:
        low = bar[3] if len(bar) > 3 else None
        if isinstance(low, (int, float)) and low <= stop_price:
            return True
    return False


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

    for trade in open_trades:
        symbol = trade.get("symbol", "")
        if not symbol:
            logger.warning("Open trade has no symbol — skipping evaluation")
            continue

        trade_type = trade.get("trade_type", "weekly")

        # The exit is a rule, not a weekday (2026-08-18 policy). A trade
        # closes when its stated horizon of sessions has actually printed
        # — five for a weekly hold, one for a flash — or earlier if its
        # narrated stop was breached (enforced inside _close_trade). The
        # old test was "is today Friday, and is the pick at least two
        # calendar days old", which let the evaluating run's timing decide
        # the holding period. Counting real sessions means a pick made any
        # weekday gets the same holding period, so alpha is attributable
        # to the pick instead of to the calendar.
        pick_date = _trade_pick_date(trade)
        bars = _fetch_bars_for_trade(trade)
        sessions = _sessions_since_pick(bars, pick_date)

        option = trade.get("option")
        if option:
            # Held to expiry (policy). The horizon rule governs equity;
            # an option's life is set by the contract, and closing it on
            # session five would price a contract that has not expired —
            # which needs a pricing model, which is exactly what this
            # design refuses to introduce.
            try:
                expiry = datetime.date.fromisoformat(option["expiry"])
            except (KeyError, ValueError):
                expiry = None
            should_close = bool(
                expiry and bars and max(b[0] for b in bars) >= expiry)
        elif trade_type == "flash":
            should_close = sessions >= 1
        else:
            should_close = sessions >= horizon_sessions("weekly")

        # A stop breach exits early — check it before the horizon so a
        # stopped-out trade does not sit open for the remaining sessions.
        if (not should_close and not option
                and _stop_already_breached(trade, bars, pick_date)):
            logger.info("%s breached its stop before the horizon — closing",
                        symbol)
            should_close = True

        # Nothing has printed since the pick (weekend/holiday pick) — hold,
        # unless it has been stale long enough that the pick is dead.
        if should_close:
            _close_trade(trade, tracker, bars=bars)
        else:
            _snapshot_trade(trade, symbol)

    # Recompute summary stats and save
    _recompute_summary(tracker)
    _maybe_record_monthly_snapshot(tracker, today)
    _save_tracker(tracker, tracker_path)


def _settle_option_trade(trade: dict, option: dict, bars, tracker: dict) -> bool:
    """Settle a held-to-expiry option from the underlying's closing price.

    Returns True when the trade was closed. The payoff is arithmetic with
    no free parameters (see ``option_payoff``), so anyone with the
    underlying's expiry-date close can reproduce it.
    """
    try:
        expiry = datetime.date.fromisoformat(option["expiry"])
    except (KeyError, ValueError):
        logger.warning("Option on %s has no usable expiry — cannot settle",
                       trade.get("symbol"))
        return False

    # Expiry must actually have PASSED. Without this the "last bar on or
    # before expiry" is simply the most recent bar — so a freshly opened
    # position settles against its own entry day at a premium it has not
    # yet earned. Require evidence that the market has traded on or after
    # the expiry date before settling anything.
    if not bars or max(b[0] for b in bars) < expiry:
        return False
    # Then the last bar on/before expiry IS the settlement close (an expiry
    # falling on a holiday settles against the prior session, which is what
    # a broker does too).
    candidates = [b for b in bars if b[0] <= expiry]
    if not candidates:
        return False
    settle_bar = candidates[-1]

    result = option_payoff(option, settle_bar[2])
    trade["status"] = "closed"
    trade["entry_price"] = option["underlying_entry"]
    trade["exit_price"] = round(settle_bar[2], 4)
    trade["pnl_pct"] = result["pnl_pct"]
    trade["pnl_dollars"] = result["pnl_dollars"]
    trade["option_result"] = result
    trade["entry_bar_date"] = (
        trade.get("entry_bar_date") or (_trade_pick_date(trade) or expiry).isoformat()
    )
    trade["exit_bar_date"] = settle_bar[0].isoformat()

    try:
        _annotate_trade_with_nasdaq(trade)
    except Exception as exc:  # noqa: BLE001
        logger.warning("benchmark annotation failed for %s: %s",
                       trade.get("symbol"), exc)

    logger.info(
        "Settled %s %s on %s: underlying %.2f vs strike %.2f -> %s%.2f%% "
        "(%s)", trade.get("symbol"), option["structure"], settle_bar[0],
        settle_bar[2], option["strike"],
        "+" if result["pnl_pct"] >= 0 else "", result["pnl_pct"],
        "assigned" if result["assigned"] else "expired worthless",
    )
    return True


def _close_trade(trade: dict, tracker: dict, *, bars=None) -> None:
    """Close a trade with real market data (pick-date-aligned bars).

    ``bars`` may be supplied by the caller so the exit decision and the
    exit pricing read the SAME data — re-fetching between the two would
    let a trade be judged due on one snapshot and priced from another.
    """
    symbol = trade.get("symbol", "")
    trade_type = trade.get("trade_type", "weekly")
    pick_date = _trade_pick_date(trade)

    if bars is None:
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

    option = trade.get("option")
    if option:
        settled = _settle_option_trade(trade, option, bars, tracker)
        if settled:
            return
        # Fall through only when the expiry bar is genuinely missing; the
        # generic path below then voids rather than guessing.

    entry_date, entry_price = entry_bar[0], entry_bar[1]
    exit_date, exit_price = exit_bar[0], exit_bar[2]

    # Stop-loss enforcement (July 2026 fidelity pass): the digest narrates
    # a stop on every pick but the sim let losers ride to the scheduled
    # exit. If the pick carried a parseable stop and any bar between entry
    # and scheduled exit breached it, the trade closes AT THE STOP on the
    # breach day (gap-aware) — matching what the show tells listeners it
    # would do, and what a live bracket order will actually do.
    stop = trade.get("stop_loss")
    if isinstance(stop, dict) and bars:
        stop_price = None
        if isinstance(stop.get("price"), (int, float)):
            stop_price = float(stop["price"])
        elif isinstance(stop.get("pct"), (int, float)):
            stop_price = round(entry_price * (1 - float(stop["pct"]) / 100), 2)
        # Sanity: a "stop" at/above entry is a parse artifact — ignore it.
        if stop_price is not None and 0 < stop_price < entry_price:
            breach = _stop_breach(bars, entry_bar, exit_bar, stop_price)
            if breach:
                exit_date, exit_price = breach
                trade["stopped_out"] = True
                trade["stop_price"] = stop_price
                logger.info(
                    "STOP ENFORCED for %s: breached %s, exit at $%.2f",
                    symbol, exit_date, exit_price,
                )

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

    # Statistical significance of the per-trade alpha (July 2026): "are
    # we beating the index?" needs "…and is that distinguishable from
    # luck?". One-sample t-stat on per-trade alpha; |t| >= 2 ≈ 95%
    # confidence the true mean isn't zero. Spoken honestly either way.
    alpha_t_stat = None
    if len(alphas) >= 2:
        mean_alpha = sum(alphas) / len(alphas)
        variance = sum((a - mean_alpha) ** 2 for a in alphas) / (len(alphas) - 1)
        std = variance ** 0.5
        if std > 0:
            alpha_t_stat = round(mean_alpha / (std / len(alphas) ** 0.5), 2)

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
    # VERIFIED subset (August 2026 review): the same compounding restricted
    # to trades whose benchmark window was built by the July-3 pick-date-
    # aligned code path — identified by ``entry_bar_date`` (only that path
    # writes it). Everything older carries a window the July-3 integrity
    # pass itself declared untrustworthy ("old-window inflation", carried
    # in the ledger as an unrun operator recompute since 2026-07-03), and
    # blending the two produced a headline the show states on air EVERY
    # episode: +9.28% across 45 trades, while the 10 honestly-measured
    # trades were at -1.95%. A number that survives only because it is
    # averaged with numbers we know are wrong is not a measurement.
    # ``scripts/recompute_mit_benchmarks.py --apply`` backfills the legacy
    # windows; when it runs, every trade gains ``entry_bar_date`` and the
    # verified figure simply becomes the whole record.
    comp_v_port = 1.0
    comp_v_ndq = 1.0
    n_verified = 0
    verified_alphas: list[float] = []
    # ERA subset (2026-08-18): trades picked on/after the rulebook's
    # inception date, i.e. the ones whose entry, exit and benchmark window
    # all followed rules published before the trade opened. This is the
    # record the show is judged on. Earlier trades are kept — they are the
    # show's history — but their exits were a side effect of when the
    # evaluating run happened to look, so they cannot answer "is the
    # method beating the NASDAQ?" and are never blended into an on-air
    # figure with the ones that can.
    comp_e_port = 1.0
    comp_e_ndq = 1.0
    n_era = 0
    era_alphas: list[float] = []
    era_wins = 0
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
            if t.get("entry_bar_date"):
                comp_v_port *= 1 + pnl / 100
                comp_v_ndq *= 1 + ndq / 100
                n_verified += 1
                verified_alphas.append(pnl - ndq)
                if _in_era(t):
                    comp_e_port *= 1 + pnl / 100
                    comp_e_ndq *= 1 + ndq / 100
                    n_era += 1
                    era_alphas.append(pnl - ndq)
                    if pnl > ndq:
                        era_wins += 1

    # Significance on the VERIFIED subset only — a t-stat computed over
    # windows we do not trust answers a question nobody asked.
    era_t_stat = None
    if len(era_alphas) >= 2:
        _m = sum(era_alphas) / len(era_alphas)
        _v = sum((a - _m) ** 2 for a in era_alphas) / (len(era_alphas) - 1)
        _s = _v ** 0.5
        if _s > 0:
            era_t_stat = round(_m / (_s / len(era_alphas) ** 0.5), 2)

    verified_t_stat = None
    if len(verified_alphas) >= 2:
        _mean = sum(verified_alphas) / len(verified_alphas)
        _var = sum((a - _mean) ** 2 for a in verified_alphas) / (len(verified_alphas) - 1)
        _std = _var ** 0.5
        if _std > 0:
            verified_t_stat = round(_mean / (_std / len(verified_alphas) ** 0.5), 2)

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
            # No legacy fallback (August 18 2026). The NASDAQ leg used to
            # fall back to ``nasdaq_return_pct``, which exists on 45 trades
            # while ``benchmark_returns`` exists on 10 — so the sweep put a
            # 45-trade NASDAQ score beside 10-trade S&P/TSX scores and
            # reported "beating 1 of 3". The July-18 n>=5 gate passed it
            # because it checks each sample's SIZE, not that the samples
            # are the SAME TRADES. A head-to-head across different trade
            # sets is not a comparison. All three legs now read the same
            # verified windows, so the NASDAQ leg equals the headline
            # alpha instead of contradicting it in the same paragraph.
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
        # Verified-window figures (August 2026). These are what the show
        # states on air; the blended pair above is retained for continuity
        # with the performance page and the recompute script.
        "verified_window_alpha_pct": round((comp_v_port - comp_v_ndq) * 100, 2)
        if n_verified else None,
        "verified_window_return_pct": round((comp_v_port - 1) * 100, 2)
        if n_verified else None,
        "verified_window_nasdaq_pct": round((comp_v_ndq - 1) * 100, 2)
        if n_verified else None,
        "verified_window_trades": n_verified,
        "unverified_window_trades": n_matched - n_verified,
        "verified_alpha_t_stat": verified_t_stat,
        "verified_alpha_statistically_significant": bool(
            verified_t_stat is not None and abs(verified_t_stat) >= 2.0),
        # The on-air record (2026-08-18 rulebook era).
        "era_name": (load_policy().get("era") or {}).get("name"),
        "era_inception": (load_policy().get("era") or {}).get("inception_date"),
        "era_trades": n_era,
        "era_alpha_pct": round((comp_e_port - comp_e_ndq) * 100, 2)
        if n_era else None,
        "era_return_pct": round((comp_e_port - 1) * 100, 2) if n_era else None,
        "era_nasdaq_pct": round((comp_e_ndq - 1) * 100, 2) if n_era else None,
        "era_beat_benchmark": era_wins,
        "era_mean_alpha_pct": round(sum(era_alphas) / len(era_alphas), 2)
        if era_alphas else None,
        "era_alpha_t_stat": era_t_stat,
        "era_alpha_statistically_significant": bool(
            era_t_stat is not None and abs(era_t_stat) >= 2.0),
        "benchmark_scores": benchmark_scores,
        "indices_beaten": indices_beaten,
        "indices_scored": len(benchmark_scores),
        "alpha_t_stat": alpha_t_stat,
        "alpha_statistically_significant": bool(
            alpha_t_stat is not None and alpha_t_stat >= 2.0),
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

def _finite_close(value) -> float | None:
    """Return *value* as float if finite, else None."""
    try:
        close = float(value)
    except (TypeError, ValueError):
        return None
    return close if math.isfinite(close) else None


def _fetch_nasdaq_via_history(for_date: datetime.date | None = None) -> float | None:
    """Primary: yfinance history bars."""
    import yfinance as yf
    ticker = yf.Ticker(NASDAQ_SYMBOL)
    if for_date is None:
        hist = ticker.history(period="5d", interval="1d")
        if hist.empty:
            return None
        return _finite_close(hist["Close"].iloc[-1])
    start = for_date - datetime.timedelta(days=5)
    end = for_date + datetime.timedelta(days=1)
    hist = ticker.history(start=start.isoformat(), end=end.isoformat(), interval="1d")
    if hist.empty:
        return None
    mask = hist.index.date <= for_date
    if mask.any():
        return _finite_close(hist[mask]["Close"].iloc[-1])
    return _finite_close(hist["Close"].iloc[-1])


def _fetch_nasdaq_via_fast_info() -> float | None:
    """Secondary: yfinance fast_info (live / last price)."""
    import yfinance as yf
    info = yf.Ticker(NASDAQ_SYMBOL).fast_info
    price = (
        getattr(info, "last_price", None)
        or getattr(info, "regularMarketPrice", None)
        or getattr(info, "previous_close", None)
    )
    return _finite_close(price)


def _fetch_nasdaq_via_yahoo_v8(for_date: datetime.date | None = None) -> float | None:
    """Tertiary: direct Yahoo v8 chart HTTP (Tesla landmine-#22 pattern)."""
    import requests
    params = {"interval": "1d", "range": "5d"}
    if for_date is not None:
        # Chart API wants unix seconds; pull a short window around the date.
        start = datetime.datetime.combine(
            for_date - datetime.timedelta(days=7), datetime.time.min,
            tzinfo=datetime.timezone.utc,
        )
        end = datetime.datetime.combine(
            for_date + datetime.timedelta(days=2), datetime.time.min,
            tzinfo=datetime.timezone.utc,
        )
        params = {
            "interval": "1d",
            "period1": int(start.timestamp()),
            "period2": int(end.timestamp()),
        }
    resp = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{NASDAQ_SYMBOL}",
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; NerraNetwork/1.0)",
            "Accept": "application/json",
        },
        timeout=12,
    )
    if resp.status_code != 200:
        logger.warning("Yahoo v8 ^IXIC HTTP %s", resp.status_code)
        return None
    result = resp.json()["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    valid = [c for c in closes if c is not None]
    if not valid:
        meta_price = result.get("meta", {}).get("regularMarketPrice")
        return _finite_close(meta_price)
    if for_date is None:
        return _finite_close(valid[-1])
    # Prefer the last bar on/before for_date when timestamps exist.
    try:
        ts_list = result.get("timestamp") or []
        picked = None
        for ts, close in zip(ts_list, closes):
            if close is None:
                continue
            bar_day = datetime.datetime.fromtimestamp(
                ts, tz=datetime.timezone.utc).date()
            if bar_day <= for_date:
                picked = close
        if picked is not None:
            return _finite_close(picked)
    except Exception:
        pass
    return _finite_close(valid[-1])


def _fetch_nasdaq_close(for_date: datetime.date | None = None) -> float | None:
    """Return the ^IXIC close for the given date (or most recent if None).

    Multi-source chain (July 2026 improvements pack — MIT Ep117 NaN day):
    1. yfinance history  2. yfinance fast_info  3. Yahoo v8 chart HTTP.
    Each source is tried with retries; non-finite closes are rejected.
    """
    import time as _time
    sources = (
        ("yfinance_history", lambda: _fetch_nasdaq_via_history(for_date)),
        ("yfinance_fast_info", _fetch_nasdaq_via_fast_info),
        ("yahoo_v8_chart", lambda: _fetch_nasdaq_via_yahoo_v8(for_date)),
    )
    # fast_info is live-only — skip when a historical date was requested.
    if for_date is not None:
        sources = (
            ("yfinance_history", lambda: _fetch_nasdaq_via_history(for_date)),
            ("yahoo_v8_chart", lambda: _fetch_nasdaq_via_yahoo_v8(for_date)),
        )
    for name, fetcher in sources:
        for attempt in range(2):
            try:
                close = fetcher()
                if close is not None:
                    # Sanity band for the composite (~5k–40k in 2020s).
                    if 3000.0 <= close <= 50000.0:
                        if name != "yfinance_history":
                            logger.info("NASDAQ close via %s: %.2f", name, close)
                        return close
                    logger.warning(
                        "NASDAQ %s returned out-of-band %.2f — trying next",
                        name, close,
                    )
                    break
            except Exception as exc:
                logger.warning(
                    "NASDAQ %s attempt %d (%s): %s",
                    name, attempt + 1, for_date, exc,
                )
            if attempt == 0:
                _time.sleep(1.5)
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
    prev_close = benchmark.get("current_close")
    if isinstance(prev_close, (int, float)) and not math.isfinite(prev_close):
        prev_close = None
    if current_close is not None and math.isfinite(current_close):
        benchmark["current_close"] = round(current_close, 2)
    else:
        # Keep the last finite close; never persist NaN (MIT Ep117).
        benchmark["current_close"] = prev_close
    benchmark["last_updated"] = today_iso

    inception_close = meta.get("nasdaq_inception_close")
    ytd_start = meta.get("nasdaq_ytd_start_close")
    if isinstance(inception_close, (int, float)) and not math.isfinite(inception_close):
        inception_close = None
    if isinstance(ytd_start, (int, float)) and not math.isfinite(ytd_start):
        ytd_start = None
    ref_close = benchmark["current_close"]
    if isinstance(ref_close, (int, float)) and not math.isfinite(ref_close):
        ref_close = None
        benchmark["current_close"] = None

    if ref_close is not None and inception_close:
        benchmark["inception_to_date_pct"] = round(
            ((ref_close - inception_close) / inception_close) * 100, 2)
    else:
        prev_itd = benchmark.get("inception_to_date_pct")
        if not (isinstance(prev_itd, (int, float)) and math.isfinite(prev_itd)):
            benchmark["inception_to_date_pct"] = None
    if ref_close is not None and ytd_start:
        benchmark["ytd_pct"] = round(((ref_close - ytd_start) / ytd_start) * 100, 2)
    else:
        prev_ytd = benchmark.get("ytd_pct")
        if not (isinstance(prev_ytd, (int, float)) and math.isfinite(prev_ytd)):
            benchmark["ytd_pct"] = None

    alpha = tracker.setdefault("alpha", {"monthly": {}})
    bench_itd = benchmark.get("inception_to_date_pct")
    bench_ytd = benchmark.get("ytd_pct")
    if isinstance(bench_itd, (int, float)) and math.isfinite(bench_itd):
        alpha["inception_to_date_pct"] = round(
            _portfolio_return_pct(tracker) - bench_itd, 2)
    else:
        alpha["inception_to_date_pct"] = None
    if isinstance(bench_ytd, (int, float)) and math.isfinite(bench_ytd):
        alpha["ytd_pct"] = round(_portfolio_return_ytd_pct(tracker) - bench_ytd, 2)
    else:
        alpha["ytd_pct"] = None


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


# How many episodes carry the one-off methodology correction. The record
# the show used to quote (+9.28% across 45 trades) DISAPPEARED from air
# when the era-scoped record started, and from a listener's seat a show
# that stops quoting a strong number looks exactly like a show burying a
# bad result. The truth is the opposite — the old number could not be
# reproduced — and saying so is both the honest move and the single most
# transferable lesson the show has ever had to teach. Three episodes is
# enough for the correction to reach a daily audience without becoming a
# recurring changelog; internal plumbing (rule rotation, review coverage,
# scoreboard mechanics) is deliberately NOT in scope — a listener cares
# what the numbers mean, not how the repo is wired.
METHODOLOGY_DISCLOSURE_EPISODES = 3


def _build_methodology_disclosure(
    tracker: dict, episode_num: int | None = None
) -> str:
    """One-off on-air correction explaining why the record restarted.

    Returns an empty string once the disclosure has aired
    ``METHODOLOGY_DISCLOSURE_EPISODES`` times, so this can never become a
    permanent segment. The airing count is stamped on the tracker (a list
    of episode numbers, so the record shows exactly which episodes carry
    it) and, like every other stamp in this module, is skipped on
    read-only (test/rehearse) runs.
    """
    aired = list(
        (tracker.get("metadata") or {}).get(
            "methodology_disclosure_episodes", []
        )
    )
    if len(aired) >= METHODOLOGY_DISCLOSURE_EPISODES:
        return ""
    if episode_num is not None and episode_num in aired:
        return ""

    start = era_inception()
    start_str = start.strftime("%B %-d, %Y") if start else "the inception date"

    if episode_num is not None and not _hooks_readonly():
        aired.append(episode_num)
        tracker.setdefault("metadata", {})[
            "methodology_disclosure_episodes"
        ] = aired

    remaining = METHODOLOGY_DISCLOSURE_EPISODES - len(aired)
    return (
        "**METHODOLOGY CORRECTION — include this as a short segment "
        "(roughly 200-300 words) inside Portfolio Performance, then move "
        f"on. This airs {remaining} more time(s) after today and is then "
        "retired — do NOT turn it into a recurring feature.**\n"
        "\n"
        "The show recently restarted its simulated track record, and a "
        "listener who was here before deserves to be told why in plain "
        "language. Cover these points in your own words, in this order, "
        "without jargon and without defensiveness:\n"
        "\n"
        "1. The show used to quote a cumulative alpha figure across "
        "roughly forty-five trades. It is gone from the scoreboard, and "
        "that is deliberate. Say so directly — a number that quietly "
        "vanishes is the oldest tell in performance reporting.\n"
        "2. Why it went: that figure blended trades whose entry and exit "
        "prices could not be tied back to the actual sessions the trade "
        "was held. An audit could not reproduce it, so it was not the "
        "show's to claim.\n"
        "3. The exit rule was the deeper problem. A position used to be "
        "closed on whichever session the next pre-market run happened to "
        "price it — so a Monday pick was held about five sessions and a "
        "Wednesday pick about one. Per-trade performance was measuring "
        "the day of the week as much as the quality of the idea. The "
        "hold is now a fixed, published number of sessions.\n"
        "4. Some older trades match no market prices at all, and they "
        "include the best and the worst results on the books. They stay "
        "published as history, flagged, and they are never blended into "
        "what the show says on air.\n"
        f"5. What replaced it: from {start_str}, every pick is scored "
        "under one written rulebook — entry at the first session open on "
        "or after the pick, exit at the stop or at the fixed horizon, "
        "one position, one thousand dollars, no discretionary exits. The "
        "rules and the full trade-by-trade ledger, including the losers "
        "and the voided picks, are published for anyone to check — say "
        "WHERE, out loud, in the show's usual spoken-URL style: the "
        "Modern Investing performance page at nerranetwork dot com. An "
        "invitation to check with no destination is not an invitation.\n"
        "6. The honest cost, stated plainly: the record is now small, so "
        "for the next several weeks the alpha number will be based on a "
        "handful of trades and will not mean much on its own. That is "
        "what an honest track record looks like early. Do not spin it.\n"
        "7. Close on the transferable skill, because this is the point "
        "of the segment: this is exactly how a listener should audit ANY "
        "track record they are shown — ask when the record started and "
        "whether that date was chosen after the fact, ask what the exit "
        "rule is and whether it was fixed in advance, ask whether losers "
        "and abandoned positions are included, and ask whether the "
        "individual trades are published or only the summary. A record "
        "that cannot answer those four questions is a story.\n"
        "\n"
        "Keep this as its own paragraph, ahead of the usual performance "
        "numbers — do not run the two together into one block.\n"
        "\n"
        "Do NOT discuss internal tooling, code, prompts, or pipeline "
        "mechanics. Speak only about the trading method and what it "
        "means for the listener."
    )


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

    # Void transparency (July 24 2026): when a pick the show ANNOUNCED on
    # air gets voided (wrong-instrument resolution, data failure), say so
    # once instead of silently dropping it — listeners heard the pick and
    # deserve to know no simulated result is being claimed. Disclosed
    # exactly once (stamped), only for recent voids so old migrations
    # don't resurface.
    void_note = ""
    today = datetime.date.today()  # noqa: DTZ011 — matches the tracker's naive dates
    for t in tracker["trades"]:
        if t.get("status") != "voided" or t.get("void_disclosed_in_episode"):
            continue
        try:
            age = (today - datetime.date.fromisoformat(t.get("date", ""))).days
        except ValueError:
            continue
        if age <= 7:
            if episode_num is not None:
                t["void_disclosed_in_episode"] = episode_num
            void_note = (
                f"**Correction first:** the {t.get('symbol', '?')} practice "
                f"pick from episode {t.get('episode_num', '?')} was VOIDED — "
                f"a tracking error (not a market outcome), so no simulated "
                f"result is claimed for it and it is excluded from the "
                f"running totals. State this plainly and briefly.\n"
            )
            break

    closed = [t for t in tracker["trades"] if t.get("status") == "closed"]
    open_trades = [t for t in tracker["trades"] if t.get("status") == "open"]
    if not closed:
        # Check for open weekly hold — provide mid-week update
        return void_note + _weekly_hold_update(open_trades)

    # Pick the OLDEST unreviewed close, not the newest (August 2026
    # review). The guard shipped in July fixed over-reviewing (the MU
    # flash trade narrated three times) by stamping the trade it
    # narrated — but it only ever looked at ``closed[-1]``, the last
    # trade APPENDED. Once the pick cadence went to roughly one a day,
    # more than one trade routinely closed between reviews, and every
    # close except the newest was silently skipped forever: 43 of 50
    # closed trades had never been narrated, including five that closed
    # in the ten days before this review (LNTH, MU, TBBK, IPCO.TO,
    # AAPL). Those results still counted in the running totals, so the
    # segment was reporting an aggregate built from trades the audience
    # never heard resolve. Draining the backlog oldest-first keeps every
    # result narrated exactly once and self-heals the existing gap at
    # one trade per episode.
    # Bounded by freshness: a result older than REVIEW_BACKLOG_MAX_DAYS is
    # stale news, so the historical backlog is retired in place (stamped
    # ``review_skipped_stale``) instead of being narrated as if it just
    # happened. Only genuinely recent closes are drained.
    def _closed_on(t: dict) -> datetime.date | None:
        for key in ("exit_bar_date", "date"):
            try:
                return datetime.date.fromisoformat(t.get(key) or "")
            except ValueError:
                continue
        return None

    unreviewed = [t for t in closed if t.get("reviewed_in_episode") is None]

    def _is_stale(t: dict) -> bool:
        when = _closed_on(t)
        return when is not None and (today - when).days > REVIEW_BACKLOG_MAX_DAYS

    if unreviewed:
        fresh = [t for t in unreviewed if not _is_stale(t)]
        # The newest unreviewed close is never retired, however old it is.
        # Staleness exists to stop a months-old backlog being narrated as
        # today's news, not to make the segment go silent — if the
        # pipeline has been down long enough that nothing is fresh, the
        # most recent result is still the right thing to report.
        last = fresh[0] if fresh else unreviewed[-1]
        for t in unreviewed:
            if t is not last and _is_stale(t):
                # Retired in place: never claimed as a fresh result,
                # never re-examined on a later run.
                if episode_num is not None and not _hooks_readonly():
                    t["review_skipped_stale"] = True
                    t["reviewed_in_episode"] = 0
    else:
        last = closed[-1]

    # Double-review guard: don't re-narrate an already-reviewed result.
    already = last.get("reviewed_in_episode")
    if already is not None and already != episode_num:
        hold_update = _weekly_hold_update(open_trades)
        if hold_update:
            return void_note + hold_update
        return void_note + (
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
        return void_note + (
            f"**Last {type_label}:** {symbol}\n"
            f"**Result:** Market data was unavailable for evaluation.\n"
            f"**Running Total:** ${summary.get('cumulative_pnl', 0):.2f}\n"
            f"**Win Rate:** {summary.get('wins', 0)} wins / "
            f"{summary.get('total_trades', 0)} total trades "
            f"({summary.get('win_rate_pct', 0):.0f}%)\n"
        )

    # State the hold length that actually happened (August 2026 review).
    # "Weekly Hold" is the label the digest prompt assigns at pick time,
    # but exits are pinned to the Friday pre-market run — which prices
    # Thursday's bar — so a Wednesday pick resolves after a single
    # session. Across the ten trades with verified windows the holds ran
    # 0-6 calendar days (median 3), while the scripts kept describing a
    # "five-day window" that the pick's own target range was written
    # against. Handing the real span to the model stops the mismatch at
    # the source instead of asking it to remember.
    hold_note = ""
    try:
        if last.get("entry_bar_date") and last.get("exit_bar_date"):
            _in = datetime.date.fromisoformat(last["entry_bar_date"])
            _out = datetime.date.fromisoformat(last["exit_bar_date"])
            _days = (_out - _in).days
            hold_note = (
                f"**Actual hold:** {_days} calendar day(s) of market data "
                f"({_in.strftime('%A')} → {_out.strftime('%A')}). Describe "
                f"the window you actually held — never call it a five-day "
                f"or full-week hold unless the dates say so.\n"
            )
    except ValueError:
        pass

    direction = "gained" if pnl_pct >= 0 else "lost"
    stop_note = ""
    if last.get("stopped_out"):
        stop_note = (
            f"**Stopped out:** the narrated stop-loss "
            f"(${_finite(last.get('stop_price')):.2f}) was breached and the "
            f"position exited at the stop — say so plainly; stop discipline "
            f"working as designed is a teachable win.\n"
        )
    return void_note + (
        f"**Last {type_label}:** {symbol} — {strategy}\n"
        f"{hold_note}"
        f"{stop_note}"
        f"**Entry:** ${entry:.2f} ({entry_label}) → **Exit:** ${exit_:.2f} ({exit_label})\n"
        f"**Result:** {direction} {abs(pnl_pct):.2f}% (${pnl_dollars:+.2f} on $1,000 position)\n"
        f"**Running Total:** ${summary.get('cumulative_pnl', 0):.2f} across "
        f"{summary.get('total_trades', 0)} trades\n"
        f"**Win Rate:** {summary.get('wins', 0)} wins / "
        f"{summary.get('total_trades', 0)} total trades "
        f"({summary.get('win_rate_pct', 0):.0f}%)\n"
        f"**Current Streak:** {_format_streak(summary.get('current_streak', 0))}\n"
    )


def _alpha_scope(summary: dict) -> dict:
    """Which alpha the show is allowed to speak, and what to call it.

    THE single source for both prompt blocks. They previously chose
    independently and the model fused a value from one with a label from
    the other (Ep138: "+9.28% across forty-five VERIFIED-window trades").
    Order: the rulebook era -> verified windows -> the blended legacy
    pair. ``scope == "era_empty"`` means the era has started but nothing
    has closed, which is a statement, not a number.
    """
    era_n = summary.get("era_trades", 0)
    era_alpha = summary.get("era_alpha_pct")
    era_start = summary.get("era_inception")
    if era_n and era_alpha is not None:
        return {
            "scope": "era", "alpha": era_alpha, "n": era_n,
            "portfolio": summary.get("era_return_pct"),
            "index": summary.get("era_nasdaq_pct"),
            "t": summary.get("era_alpha_t_stat"),
            "significant": summary.get("era_alpha_statistically_significant"),
            "label": "rules-based", "era_start": era_start,
            "era_name": summary.get("era_name"),
        }
    if era_start and not era_n:
        return {"scope": "era_empty", "alpha": None, "n": 0,
                "era_start": era_start, "era_name": summary.get("era_name")}
    alpha = summary.get("verified_window_alpha_pct")
    n = summary.get("verified_window_trades", 0)
    if n and alpha is not None:
        return {
            "scope": "verified", "alpha": alpha, "n": n,
            "portfolio": summary.get("verified_window_return_pct"),
            "index": summary.get("verified_window_nasdaq_pct"),
            "t": summary.get("verified_alpha_t_stat"),
            "significant": summary.get(
                "verified_alpha_statistically_significant"),
            "label": "verified-window",
        }
    return {
        "scope": "blended", "alpha": summary.get("matched_window_alpha_pct"),
        "n": summary.get("matched_window_trades", 0),
        "portfolio": summary.get("compounded_return_pct"),
        "index": summary.get("compounded_nasdaq_matched_pct"),
        "t": summary.get("alpha_t_stat"),
        "significant": summary.get("alpha_statistically_significant"),
        "label": "benchmarked",
    }


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
    if isinstance(close, (int, float)) and not math.isfinite(close):
        close = None
    bench_ytd = benchmark.get("ytd_pct")
    bench_itd = benchmark.get("inception_to_date_pct")
    alpha_ytd = alpha.get("ytd_pct")
    alpha_itd = alpha.get("inception_to_date_pct")
    for _name, _val in (
        ("bench_ytd", bench_ytd), ("bench_itd", bench_itd),
        ("alpha_ytd", alpha_ytd), ("alpha_itd", alpha_itd),
    ):
        if isinstance(_val, (int, float)) and not math.isfinite(_val):
            if _name == "bench_ytd":
                bench_ytd = None
            elif _name == "bench_itd":
                bench_itd = None
            elif _name == "alpha_ytd":
                alpha_ytd = None
            else:
                alpha_itd = None

    def _sign(v):
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            return "n/a"
        return f"{v:+.2f}%"

    # Two DIFFERENT scores exist and episodes have spoken them
    # interchangeably (+11% one day, -13.1% the Sunday recap — July 2026
    # review). Label them so the script can never conflate the two.
    summary = tracker.get("summary", {}) or {}
    # VERIFIED subset only (August 18 2026). The August 15 pass switched
    # ``_build_portfolio_summary`` to the verified-window figure but left
    # THIS block — the "PORTFOLIO vs NASDAQ COMPOSITE (state every
    # episode)" scoreboard — reading the blended one. Both blocks reach
    # the same prompt, so the model was handed two different alphas under
    # two labels and fused them: Ep138 said "+9.28% across forty-five
    # VERIFIED-window trades" — the inflated number wearing the honest
    # label, which is strictly worse than the bug the pass set out to fix.
    # One number, one source, both blocks.
    # ONE scope, ONE render (2026-08-18) — see _alpha_scope.
    _sc = _alpha_scope(summary)
    if _sc["scope"] == "era_empty":
        return _compose_benchmark(
            close, bench_ytd, bench_itd, alpha_ytd, alpha_itd,
            portfolio_ytd, portfolio_itd,
            (f"1) TRACK RECORD — {_sc.get('era_name') or 'current era'} "
             f"began {_sc['era_start']} and has NO closed trades yet. Say "
             f"exactly that: the rules-based record starts now and the "
             f"first result arrives when the first hold completes its five "
             f"sessions. Do NOT quote any lifetime or historical alpha as "
             f"though it measured the current method — earlier trades were "
             f"exited on whatever day the evaluating run happened to look, "
             f"so they cannot answer whether these rules beat the index. "
             f"The earlier record remains published as history. "),
            _sign)
    matched_alpha, matched_n = _sc["alpha"], _sc["n"]
    _port, _idx = _sc.get("portfolio"), _sc.get("index")
    _t, _sig, _n_label = _sc.get("t"), _sc.get("significant"), _sc["label"]
    _scope_note = (
        f"This is the {_sc.get('era_name') or 'current'} record, started "
        f"{_sc.get('era_start')}: every trade entered and exited on the "
        f"published rules. " if _sc["scope"] == "era" else ""
    )

    if isinstance(matched_alpha, float) and not math.isfinite(matched_alpha):
        matched_alpha = None

    matched_line = ""
    if matched_n and matched_alpha is not None:
        # July 18 2026: the significance caveat now lives INSIDE the alpha
        # sentence. The previous design put it in a separate STATISTICAL
        # CONFIDENCE instruction, and 2 weeks of transcripts show the
        # model quoted the alpha in most episodes while speaking the
        # hedge in zero — models echo data lines and drop instructions,
        # so the hedge must be part of the data line it qualifies.
        # July 24 2026 (second miss on this metric): the em-dash
        # instruction caveat ("never quote this alpha without…") was
        # dropped by the model in 5 of 6 alpha mentions since July 18 —
        # instruction-shaped text gets stripped during paraphrase even
        # when it rides the data line. Third mechanism: make the caveat
        # part of the alpha VALUE itself, a data-shaped parenthetical the
        # model has to copy to quote the number at all.
        t_stat = _t
        if _sig:
            alpha_phrase = (
                f"{_sign(matched_alpha)} (statistically significant, "
                f"t={t_stat:+.2f})"
            )
        elif t_stat is not None:
            alpha_phrase = (
                f"{_sign(matched_alpha)} (early, not yet statistically "
                f"significant, t={t_stat:+.2f})"
            )
        else:
            alpha_phrase = _sign(matched_alpha)
        matched_line = (
            f"1) MATCHED-WINDOW SCORE (the honest head-to-head — each "
            f"$1,000 trade vs the NASDAQ over the SAME holding window, "
            f"compounded): {_scope_note}portfolio {_sign(_port)} vs NASDAQ "
            f"{_sign(_idx)} → alpha {alpha_phrase} across {matched_n} "
            f"{_n_label} trades. Speak the alpha, the trade count and "
            f"the parenthetical together — they are one statistic. "
        )
        if matched_n < _MIN_SAMPLE_TRADES:
            matched_line += (
                "With this few trades it is a scoreboard, not evidence — "
                "say so rather than implying an edge. "
            )
        # Index sweep — only from samples big enough to mean something.
        # July 18 2026: before the gate, the sweep compared a 37-trade
        # NASDAQ score against 2-trade S&P/TSX scores ("beating 1 of 3")
        # — technically true, statistically meaningless. Indices qualify
        # at n >= _MIN_SAMPLE_TRADES; the sweep appears once 2+ qualify
        # (i.e. after the operator's recompute backfills history or
        # enough new trades close).
        scores = summary.get("benchmark_scores") or {}
        qualified = {
            key: s for key, s in scores.items()
            if s.get("trades", 0) >= _MIN_SAMPLE_TRADES
        }
        if len(qualified) > 1:
            parts = [
                f"{BENCHMARK_LABELS[key]} {_sign(qualified[key]['alpha_pct'])}"
                for key in ("nasdaq", "sp500", "tsx") if key in qualified
            ]
            beaten = sum(1 for s in qualified.values() if s["alpha_pct"] > 0)
            matched_line += (
                f"MAJOR-INDEX SWEEP (same matched windows): currently beating "
                f"{beaten} of {len(qualified)} major indices — "
                + "; ".join(parts)
                + ". NASDAQ stays the headline benchmark; mention the sweep "
                  "at most once per episode. "
            )
    return _compose_benchmark(close, bench_ytd, bench_itd, alpha_ytd,
                              alpha_itd, portfolio_ytd, portfolio_itd,
                              matched_line, _sign)


def _compose_benchmark(close, bench_ytd, bench_itd, alpha_ytd, alpha_itd,
                       portfolio_ytd, portfolio_itd, matched_line, _sign):
    """Render the scoreboard text once, for every caller path."""
    if close is None:
        # Live index quote failed (NaN/missing) — still speak the
        # scoreboard when we have it (MIT Ep117 went silent on alpha even
        # though the score was healthy).
        if matched_line:
            return (
                "NASDAQ Composite: live index level temporarily unavailable — "
                "acknowledge the gap on air; do NOT invent a level or a YTD "
                "benchmark move. Still report the SCOREBOARD below (it does "
                "not need today's quote):\n"
                f"{matched_line}\n"
                "Skip the buy-and-hold gap numbers today — they need the "
                "live NASDAQ level."
            )
        return (
            "NASDAQ Composite: data temporarily unavailable — acknowledge the "
            "gap on air rather than inventing numbers. Skip portfolio alpha "
            "versus the NASDAQ today."
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


# Rules that describe how the PIPELINE must behave, not how to invest.
# Six of the thirteen active "recursive improvement rules" were of this
# kind (2026-08-19 audit): re-teach cooldowns, "every episode must state
# the NASDAQ level", "every Quick Hit ends with an Action line", and
# three variants of "verify price data from multiple providers" — the
# last of which are the sim's OWN historical data-fetch bugs, written up
# as though they were investing wisdom and fed back into the pick prompt.
# They are real production requirements and stay enforced elsewhere; they
# simply are not evidence about how to beat an index, and stamping them
# on trades pollutes the rule scoreboard with rules that cannot possibly
# have an effect on returns.
# Two rules whose CONSTRAINTS match this closely are the same rule
# wearing different scopes.
_RULE_CORE_THRESHOLD = 0.72

_PIPELINE_RULE_RE = re.compile(
    r"data availability|data provider|price (data|feed)s?|multiple "
    r"(independent )?(providers|sources)|closing-price confirmation|"
    r"every episode must|every quick hit|re-?teach|cooldown window",
    re.IGNORECASE,
)


_RULE_SCOPE_SPLIT = re.compile(
    r"\s+(?:before|when|unless|for|on|in)\s+", re.IGNORECASE)


def _rule_core(text: str) -> str:
    """The rule's constraint, with its scope clause removed.

    Whole-sentence similarity misses the paraphrase family that actually
    forms here: LL-017 "require volume confirmation above the 20-day
    average BEFORE ENTERING MOMENTUM TRADES ON EARNINGS BEATS", LL-041
    "...BEFORE COMMITTING CAPITAL TO HEALTHCARE LAUNCHES", LL-067
    "...BEFORE ENTERING ANY CATALYST-DRIVEN NAME". One constraint, three
    scopes, scoring 0.51-0.61 against a 0.62 threshold — so all three
    reached the prompt as separate rules and all three got stamped on
    every trade. Comparing the constraint alone collapses them.
    """
    return _RULE_SCOPE_SPLIT.split((text or "").strip(), maxsplit=1)[0]


def _is_trading_rule(entry: dict) -> bool:
    """True when a lesson is about investing rather than about the show."""
    text = f"{entry.get('adjustment', '')} {entry.get('observation', '')}"
    if entry.get("kind") == "pipeline":
        return False
    if entry.get("kind") == "trading":
        return True
    return not _PIPELINE_RULE_RE.search(text)


# ---------------------------------------------------------------------------
# Strategy families (2026-08-20)
# ---------------------------------------------------------------------------
# 61 trades produced 61 UNIQUE free-text strategy strings, so the show could
# report which SECTORS worked but never which APPROACHES did — "are our
# momentum entries better than our valuation screens?" was unanswerable for
# the operator and for the audience. A closed vocabulary makes per-strategy
# alpha reportable; deriving it from the existing text makes the 61 historic
# trades usable immediately instead of starting the count from zero.
#
# Order matters: the first family whose pattern matches wins, so the more
# specific ones are listed first.
STRATEGY_FAMILIES: list[tuple[str, str]] = [
    ("merger_arb", r"\bm&a\b|merger|acquisition|takeover|arb\b|spread capture"),
    ("earnings_surprise", r"earnings[- ](beat|surprise|revision|driven|momentum)|"
                          r"beat and|post-earnings|reported beat"),
    ("dividend_income", r"dividend|distribution|yield|buyback|issuer bid|"
                        r"covered call|cash[- ]secured put"),
    ("catalyst_event", r"catalyst|announced|launch|approval|contract win|"
                       r"policy|regulatory|phase 3|data readout"),
    ("valuation", r"valuation|value assessment|multiple|cheap|discount|"
                  r"free cash flow|screen on"),
    ("mean_reversion", r"mean[- ]reversion|contrarian|oversold|recovery from|"
                       r"fade of|rebound"),
    ("technical_breakout", r"breakout|technical|moving average|range|"
                           r"chart|support|resistance"),
    ("macro_rotation", r"macro|sector rotation|rotation into|geopolitical|"
                       r"rate|cross-asset|commodity"),
    ("momentum", r"momentum|follow-through|price action|relative strength"),
]


def strategy_family(trade: dict) -> str:
    """The closed-vocabulary family for a trade's strategy.

    Prefers an explicit ``strategy_family`` written by the digest; falls
    back to deriving one from the free-text strategy so the historic
    record is groupable too. ``other`` when nothing matches — an honest
    bucket beats forcing a wrong label.
    """
    explicit = (trade.get("strategy_family") or "").strip().lower()
    known = {name for name, _ in STRATEGY_FAMILIES}
    if explicit in known:
        return explicit
    text = f"{trade.get('strategy', '')} {trade.get('target_range', '')}".lower()
    for name, pattern in STRATEGY_FAMILIES:
        if re.search(pattern, text):
            return name
    return "other"


def _build_strategy_family_performance(tracker: dict, *,
                                       min_trades: int = 3) -> str:
    """Per-approach scoreboard for the pick prompt.

    Sector performance answers "what have we been buying"; this answers
    "which of our methods actually works", which is the question the show
    is nominally in business to resolve.
    """
    from collections import defaultdict

    def _usable(t: dict) -> bool:
        alpha = t.get("alpha_pct")
        return (t.get("status") == "closed"
                and isinstance(alpha, (int, float)) and math.isfinite(alpha))

    # Same window discipline as every other number this show speaks:
    # prefer trades whose benchmark window was built by the pick-date
    # aligned path. Fall back to the legacy windows only when the verified
    # set is too thin to say anything — and then SAY it is legacy, so this
    # block can never be quoted as if it carried the same weight.
    closed = [t for t in tracker.get("trades", []) if _usable(t)]
    verified = [t for t in closed if t.get("entry_bar_date")]
    if len(verified) >= min_trades * 2:
        pool, scope = verified, "verified-window trades"
    else:
        pool, scope = closed, (
            "trades that INCLUDE pre-2026-08-18 benchmark windows — "
            "indicative only, do NOT quote these as measured results on air"
        )

    buckets: dict[str, list[float]] = defaultdict(list)
    for t in pool:
        buckets[strategy_family(t)].append(t["alpha_pct"])

    if not buckets:
        return ""
    ranked = sorted(
        ((name, vals) for name, vals in buckets.items()
         if len(vals) >= min_trades),
        key=lambda kv: sum(kv[1]) / len(kv[1]), reverse=True,
    )
    if not ranked:
        return ""
    lines = [f"STRATEGY-FAMILY RECORD (alpha by APPROACH, not by sector; "
             f"computed over {scope}):"]
    for name, vals in ranked:
        mean = sum(vals) / len(vals)
        beat = sum(1 for a in vals if a > 0)
        note = ""
        if len(vals) < _MIN_SAMPLE_TRADES:
            note = " — too few to lean on"
        lines.append(
            f"- {name}: {mean:+.2f}% mean alpha over {len(vals)} trades "
            f"({beat} beat the benchmark){note}"
        )
    thin = [n for n, v in buckets.items() if len(v) < min_trades]
    if thin:
        lines.append(
            f"- Not yet scoreable ({min_trades}-trade minimum): "
            + ", ".join(sorted(thin))
        )
    lines.append(
        "Favour approaches with a positive record and enough trades behind "
        "it. When choosing one with a negative record, say what is "
        "different about today's setup rather than ignoring the history."
    )
    return "\n".join(lines) + "\n"


def _proven_rule_ids(tracker: dict | None, data: dict) -> set[str]:
    """Rules that have demonstrated an edge, or are pinned by hand.

    A proven rule is never rotated out: the point of rotation is to learn
    which heuristics work, not to withhold one already known to.
    """
    pinned = {
        e["id"] for e in (data.get("entries") or [])
        if e.get("always_on") and e.get("id")
    }
    if not tracker:
        return pinned
    closed = [
        t for t in tracker.get("trades", [])
        if t.get("status") == "closed" and _in_era(t)
        and isinstance(t.get("alpha_pct"), (int, float))
        and math.isfinite(t["alpha_pct"])
    ]
    for entry in (data.get("entries") or []):
        rid = entry.get("id")
        if not rid:
            continue
        with_rule = [t for t in closed
                     if rid in (t.get("rules_in_effect") or [])]
        without = [t for t in closed
                   if rid not in (t.get("rules_in_effect") or [])]
        if len(with_rule) < _MIN_SAMPLE_TRADES or len(without) < _MIN_SAMPLE_TRADES:
            continue
        avg_with = sum(t["alpha_pct"] for t in with_rule) / len(with_rule)
        avg_without = sum(t["alpha_pct"] for t in without) / len(without)
        if avg_with > avg_without:
            pinned.add(rid)
    return pinned


def _rotate(pool: list[dict], slots: int, episode_num: int | None) -> list[dict]:
    """A deterministic, evenly-cycling subset of *pool*.

    Deterministic on the episode number so the selection is reproducible
    from the trade record — a listener auditing the ledger can recompute
    which rules were in effect. Consecutive-with-wraparound gives every
    rule the same exposure over a cycle instead of the lumpy coverage a
    hash would produce.
    """
    if slots >= len(pool) or slots <= 0:
        return pool
    offset = (episode_num or 0) % len(pool)
    doubled = pool + pool
    return doubled[offset:offset + slots]


def _selected_active_rules(data: dict, *, max_active: int = 5,
                           episode_num: int | None = None,
                           tracker: dict | None = None) -> list[dict]:
    """The distinct active rules shown to the LLM today (most recent first).

    Shared by the prompt block AND the trade-stamping in post_generate so
    the ``rules_in_effect`` recorded on each trade is exactly the set the
    model was told to obey when it made the pick.
    """
    entries = [
        e for e in (data.get("entries") or [])
        if e.get("status") == "active" and _is_trading_rule(e)
    ]

    # Distinct rules, most recent first. Deduped over the WHOLE pool, not
    # just the first max_active, so pinning below can reach a proven rule
    # that recency alone would have pushed out of the window.
    eligible: list[dict] = []
    for entry in reversed(entries):
        if any(
            _lesson_similarity(entry.get("adjustment", ""), s.get("adjustment", ""))
            >= _LESSON_SIMILARITY_THRESHOLD
            or _lesson_similarity(
                _rule_core(entry.get("adjustment", "")),
                _rule_core(s.get("adjustment", ""))) >= _RULE_CORE_THRESHOLD
            for s in eligible
        ):
            continue
        eligible.append(entry)

    # Rotation (2026-08-20). Without it the stamped rule set is constant
    # between ledger edits, every trade carries the same rules, and no
    # rule can ever be told apart from any other — the scoreboard is
    # honest and permanently silent. Proven rules stay pinned; the rest
    # cycle so each accrues both a with-rule and a without-rule arm.
    pol = ((load_policy().get("learning") or {}).get("rule_rotation") or {})
    if pol.get("enabled") and len(eligible) > 1:
        proven = (_proven_rule_ids(tracker, data)
                  if pol.get("pin_proven", True) else set())
        pinned = [e for e in eligible if e.get("id") in proven]
        pool = [e for e in eligible if e.get("id") not in proven]
        slots = max(1, int(pol.get("slots", 4)) - len(pinned))
        return (pinned + _rotate(pool, slots, episode_num))[:max(
            max_active, len(pinned) + 1)]
    return eligible[:max_active]


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
    # Era-scoped (2026-08-19). The comparison used to be "trades carrying
    # this rule" against ALL other closed trades — but stamping only began
    # in July, so the control group WAS the pre-era trades whose benchmark
    # windows the integrity passes disowned. The scoreboard was therefore
    # measuring new-trades-vs-old-trades and reporting it as rule
    # effectiveness.
    closed = [
        t for t in tracker.get("trades", [])
        if t.get("status") == "closed"
        and _in_era(t)
        and isinstance(t.get("alpha_pct"), (int, float))
        and math.isfinite(t["alpha_pct"])
    ]
    active = [e for e in (data.get("entries") or []) if e.get("status") == "active"]
    if not active:
        return ""
    if not closed:
        # Say so rather than injecting nothing. Silence is what let the
        # previous scoreboard's artifacts ride unnoticed for weeks.
        return (
            "RULE EFFECTIVENESS: no closed trades in the current record "
            "yet, so no rule has been scored. Obey them all; claim nothing "
            "about which of them works.\n"
        )

    # A rule can only be scored if some trades carried it and some did
    # NOT. Every stamped trade so far carried the SAME five rules, so the
    # five were perfectly collinear and the scoreboard emitted five
    # identical verdicts — the same 10 trades, the same -0.17% vs +0.43%,
    # five separate "RETIREMENT CANDIDATE" flags — from one undivided
    # sample. Identical numbers under different rule names is the
    # signature of an experiment that never varied its treatment, and
    # reporting it as five findings invited the model to act on evidence
    # that does not exist. Say what is measurable and nothing more.
    # "No rules stamped" is itself a treatment arm — a trade made without
    # a rule is exactly the control the comparison needs — so the empty
    # set counts as a distinct set rather than being filtered out.
    stamp_sets = {
        tuple(sorted(t.get("rules_in_effect") or [])) for t in closed
    }
    if len(stamp_sets) < 2:
        return (
            "RULE EFFECTIVENESS: not measurable yet — every stamped trade "
            "so far carried the SAME rule set, so no rule can be told apart "
            "from any other. Do not treat any rule as proven or disproven; "
            "keep obeying them all. (Attribution becomes possible once the "
            "rule set varies between picks.)\n"
        )

    lines = []
    for entry in active:
        rid = entry.get("id")
        stamped = [t for t in closed if rid in (t.get("rules_in_effect") or [])]
        if len(stamped) < min_trades:
            continue
        others = [t for t in closed if rid not in (t.get("rules_in_effect") or [])]
        if len(others) < min_trades:
            # No usable control group: "trades without this rule" is too
            # small to compare against, so any difference is noise.
            lines.append(
                f"- [{rid}] in effect for {len(stamped)} closed trades — no "
                f"comparison group yet ({len(others)} trades without it), so "
                f"its effect is UNMEASURED, not zero"
            )
            continue
        # Perfectly collinear with another rule => the two cannot be told
        # apart, and presenting them as separate findings double-counts one
        # piece of evidence.
        twins = [
            other.get("id") for other in active
            if other.get("id") != rid
            and {id(t) for t in stamped} == {
                id(t) for t in closed
                if other.get("id") in (t.get("rules_in_effect") or [])}
        ]
        avg_with = sum(t["alpha_pct"] for t in stamped) / len(stamped)
        line = (
            f"- [{rid}] in effect for {len(stamped)} closed trades: "
            f"avg alpha {avg_with:+.2f}%"
        )
        if others:
            avg_without = sum(t["alpha_pct"] for t in others) / len(others)
            line += f" (trades without it: {avg_without:+.2f}%)"
            if twins:
                line += (
                    f" — NOTE: indistinguishable from {', '.join(sorted(twins))}"
                    f" (identical trade set); treat these as ONE piece of"
                    f" evidence, not several"
                )
            elif len(stamped) >= retire_after and avg_with <= avg_without:
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
        verified_alpha = summary.get("verified_window_alpha_pct")
        verified_n = summary.get("verified_window_trades", 0)
        unverified_n = summary.get("unverified_window_trades", 0)
        _sc = _alpha_scope(summary)
        if _sc["scope"] == "era_empty":
            alpha_line = (
                f"- Track record: {_sc.get('era_name') or 'current era'} "
                f"began {_sc['era_start']}; NO closed trades yet, so there "
                f"is no alpha to report. State that the rules-based record "
                f"starts now. Never substitute a lifetime or historical "
                f"figure for it.\n"
            )
        elif _sc["alpha"] is not None and _sc["n"]:
            alpha_line = (
                f"- Matched-window alpha vs NASDAQ: {_finite(_sc['alpha']):+.1f}% "
                f"across {_sc['n']} {_sc['label']} trades — THE headline "
                f"number; state it on air every episode, always call it the "
                f"'matched-window' score, and always say the trade count in "
                f"the same sentence so the sample size travels with the "
                f"claim\n"
            )
            if _sc["scope"] == "era":
                alpha_line += (
                    f"- This record began {_sc.get('era_start')} under the "
                    f"published rules; earlier trades are history and are "
                    f"NOT blended into it\n"
                )
            if _sc["n"] < _MIN_SAMPLE_TRADES:
                alpha_line += (
                    "- Too few trades to call an edge — a scoreboard, not "
                    "evidence\n"
                )
        elif verified_n and verified_alpha is not None:
            # The headline is the verified subset only (August 2026). The
            # qualifier is fused into the value the way mechanism 3 did it
            # — the sample size is part of the number, not a separate
            # instruction the model can paraphrase away.
            alpha_line = (
                f"- Matched-window alpha vs NASDAQ: "
                f"{_finite(verified_alpha):+.1f}% across {verified_n} "
                f"verified-window trades — THE headline number; state it on "
                f"air every episode, always call it the 'matched-window' "
                f"score, and always say the trade count in the same "
                f"sentence so the sample size travels with the claim\n"
            )
            if unverified_n:
                alpha_line += (
                    f"- NOT for air: {unverified_n} older trades have "
                    f"benchmark windows that predate the pick-date "
                    f"alignment fix and are excluded from the headline. "
                    f"Never quote a blended lifetime alpha figure.\n"
                )
        elif matched_n and matched_alpha is not None:
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

    # Label the lifetime figures as history whenever the on-air record is
    # the era. Leaving "Total trades: 50 / Win rate: 56%" unlabelled above
    # a line that says the era has no trades yet invites exactly the
    # conflation this whole design exists to prevent — the model reaches
    # for the nearest impressive number and attaches it to the current
    # method.
    _era_n = summary.get("era_trades", 0)
    _hist = "" if _era_n else (
        " — HISTORY ONLY, produced under the pre-2026-08-18 exit rules; "
        "never present these as the current method's results"
    )
    return (
        f"Portfolio Performance (simulated, $1,000 per trade):\n"
        f"- Lifetime totals{_hist}\n"
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

    # Extract ticker symbol. July 24 2026: the pattern must accept
    # exchange-suffixed and hyphenated symbols — the July 3 integrity pass
    # taught the DIGEST to emit "CNR.TO" / "BTC-USD", but the extractor
    # still only took bare [A-Z]{1,5}: Ep111 spoke a CNR.TO weekly pick
    # that was silently LOST (signal: no_pick_extracted), and Ep113's
    # "BTC-USD — Bitcoin" was truncated to "BTC", which _probe_pick then
    # validated against the WRONG INSTRUMENT (an equity at $28.80 vs the
    # spoken Bitcoin pick with a $64,500 stop).
    _SYM = r"([A-Z]{1,5}(?:[.-][A-Z]{1,4})?)"
    ticker_match = re.search(
        r"\*\*Today's Pick:\*\*\s*\[?" + _SYM + r"\]?\s*[-—]",
        digest_text,
    )
    if not ticker_match:
        # Fallback: try alternative patterns
        ticker_match = re.search(
            r"Today's Pick[:\s]+" + _SYM + r"\s",
            digest_text,
        )
    if not ticker_match:
        # Distinguish "deliberately no trade today" (a legitimate,
        # common outcome — e.g. "**Today's Pick:** No trade") from a
        # formatting drift that would silently lose a real pick (June
        # 2026 review: silent extraction failures were indistinguishable
        # from no-trade days in the tracker).
        if re.search(r"Today's Pick", digest_text):
            if _EXPLICIT_NO_TRADE_RE.search(digest_text):
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

    # Extract market. CRYPTO added July 24 2026 — Ep113's "**Market:**
    # Crypto" line fell through to UNKNOWN, so the candidate resolver had
    # no signal that the bare symbol needed the -USD crypto quote.
    market_match = re.search(
        r"\*\*Market:\*\*\s*(TSX-V|TSX|NYSE|NASDAQ|CRYPTO)",
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
        r"\*\*Confidence(?: Level)?:\*\*\s*\[?(Low|Medium|High)",
        digest_text, re.IGNORECASE,
    )
    confidence = confidence_match.group(1).capitalize() if confidence_match else "Unknown"

    # Extract target
    target_match = re.search(
        r"\*\*Target:\*\*\s*(.+?)(?:\n|$)",
        digest_text,
    )
    target = target_match.group(1).strip() if target_match else ""

    # Invalidation (2026-08-18): the observable condition that would prove
    # the thesis wrong. Recorded on the trade so a closed position can be
    # scored on whether the thesis broke or the trade simply ran out of
    # sessions — two very different lessons that P&L alone cannot tell
    # apart, and the difference the show is supposed to be teaching.
    invalidation_match = re.search(
        r"\*\*Invalidation:\*\*\s*(.+?)(?:\n\*\*|\n\n|\Z)",
        digest_text, re.DOTALL,
    )
    invalidation = (
        invalidation_match.group(1).strip() if invalidation_match else ""
    )

    # Options structure (2026-08-19). Absent or "shares" => a plain long
    # equity position, which is every trade before this date.
    family_match = re.search(
        r"\*\*Strategy Family:\*\*\s*\[?([a-z_]+)", digest_text, re.IGNORECASE)
    strategy_family_raw = (
        family_match.group(1).strip().lower() if family_match else "")

    structure_match = re.search(
        r"\*\*Structure:\*\*\s*\[?([A-Za-z \-_]+)", digest_text)
    structure = ""
    if structure_match:
        raw = structure_match.group(1).strip().lower().replace("-", " ")
        if "covered call" in raw:
            structure = "covered_call"
        elif "cash secured put" in raw or "cash-secured put" in raw:
            structure = "cash_secured_put"

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
        "invalidation": invalidation,
        "structure": structure or "long_equity",
        "strategy_family": strategy_family_raw,
        "trade_type": trade_type,
        "policy_version": load_policy().get("version"),
        "horizon_sessions": horizon_sessions(trade_type),
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
    # Era-scoped (2026-08-18): calibration computed over trades exited
    # under the old rules would grade the model on a different game —
    # those exits landed on whatever session the evaluating run happened
    # to price, so a "wrong" High-confidence call might only have been an
    # unlucky weekday.
    closed = [
        t for t in tracker.get("trades", [])
        if t.get("status") == "closed" and t.get("confidence")
        and _in_era(t)
        and isinstance(t.get("alpha_pct"), (int, float))
        and math.isfinite(t["alpha_pct"])
    ]
    rubric = (
        " RUBRIC — High: the catalyst is already confirmed and the setup "
        "is one this record has scored well on. Medium: the thesis is "
        "sound but the catalyst is pending. Low: a reasonable idea you "
        "would size smaller. The rating is a FORECAST and it is graded "
        "when the trade closes; if every pick is Medium the field is "
        "noise. Across the 50 trades before this era, 48 were Medium, 2 "
        "Low and none High — do not repeat that."
    )
    if len(closed) < 5:
        return (
            f"Confidence calibration: {len(closed)} graded pick(s) in this "
            f"era — not enough to score the buckets yet." + rubric
        )

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
    line = ("Calibration by stated confidence (this era only) — "
            + " · ".join(parts) + ".")
    dominant = max(buckets.values(), key=len)
    if len(dominant) / len(closed) > 0.9:
        line += (
            " NOTE: over 90% of picks used a single confidence level, which "
            "makes the field uninformative — commit to High or Low whenever "
            "the rubric supports it, and say WHY."
        )
    _hi = buckets.get("High") or []
    _lo = buckets.get("Low") or []
    if len(_hi) >= 3 and len(_lo) >= 3 and (
            sum(_hi) / len(_hi) <= sum(_lo) / len(_lo)):
        line += (
            " WARNING: High-confidence picks are NOT outperforming Low ones "
            "— say so on air and tighten what earns a High."
        )
    return line + rubric


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
