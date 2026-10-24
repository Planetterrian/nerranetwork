"""Modern Investing deep review, Oct 24 2026 — guards.

Review: docs/reviews/modern_investing_review_2026_10_24.md. What the record
showed: a stop the sim could read on 9 of 41 rules-based picks (the worst
trade, -27%, ran to its horizon), every one of 44 picks rated Medium, no
options position in 103 trades, the lifetime 87-trade blend handed to the
model inside the trade review, an "Alpha vs NASDAQ" line the model wrote
from nothing (6 of 8 wrong), the era headline moving from a compounded
chain to the average trade with nothing said, and the "learning loop"
scoring whether a rule's text was shown rather than whether its condition
held.
"""
from __future__ import annotations

import copy
import datetime
import json
from pathlib import Path

import pytest
import yaml

from shows.hooks import modern_investing as mi

ROOT = Path(__file__).resolve().parents[1]
ERA = datetime.date(2026, 8, 18)


def _era_trade(i, alpha, *, vol=None, ma=None, pnl=None, conf="Medium",
               structure="long_equity", stop=None):
    d = (ERA + datetime.timedelta(days=i)).isoformat()
    t = {"episode_num": 141 + i, "symbol": f"S{i}", "status": "closed",
         "trade_type": "weekly", "strategy": "s", "confidence": conf,
         "structure": structure, "date": d, "entry_bar_date": d,
         "exit_bar_date": d, "entry_price": 100.0,
         "exit_price": 100.0 + (pnl if pnl is not None else alpha),
         "pnl_pct": pnl if pnl is not None else alpha,
         "pnl_dollars": (pnl if pnl is not None else alpha) * 10,
         "nasdaq_return_pct": 0.0, "alpha_pct": alpha}
    if vol is not None:
        t["entry_volume_ratio_20d"] = vol
    if ma is not None:
        t["entry_vs_50dma_pct"] = ma
    if stop is not None:
        t["stop_loss"] = stop
    return t


# ---------------------------------------------------------------------------
# The stop is read from what the pick states, and the percent form wins
# ---------------------------------------------------------------------------

class TestStopParsing:
    @pytest.mark.parametrize("risk, want", [
        ("Maximum acceptable loss 8 percent on the position.", {"pct": 8.0}),
        ("max loss capped at 6% of the $1,000 position", {"pct": 6.0}),
        ("Stop set at the 200-day moving average level; maximum acceptable loss approximately 6-8%", {"pct": 8.0}),
        # GM Ep206: the percent is stated first; the $60 is the dollar loss.
        ("Stop-loss set 6 percent below entry to limit loss to roughly $60 on the $1,000 position", {"pct": 6.0}),
        # The position size is never a stop.
        ("maximum loss capped at position size of $1,000", None),
        ("stop set at the 50-day moving average near CA$152.", {"price": 152.0}),
        ("Volatility is elevated.", None),
    ])
    def test_narrated_stops(self, risk, want):
        digest = f"### Practice Investment of the Day\n**Risk Assessment:** {risk}\n"
        assert mi._extract_stop_loss(digest) == want

    def test_the_structured_line_parses(self):
        digest = ("### Practice Investment of the Day\n**Today's Pick:** X — Y\n"
                  "**Stop-Loss:** 8% below entry\n")
        assert mi._extract_stop_loss(digest) == {"pct": 8.0}

    def test_pre_check_ignores_a_stop_at_or_above_entry(self):
        bars = [(datetime.date(2026, 10, 20), 82.0, 81.0, 80.0, 1.0),
                (datetime.date(2026, 10, 21), 81.0, 80.0, 79.0, 1.0)]
        trade = {"stop_loss": {"price": 1000.0}}
        assert mi._stop_already_breached(trade, bars, datetime.date(2026, 10, 20)) is False

    def test_open_stops_are_re_read_from_the_committed_digest(self, tmp_path):
        (tmp_path / "Modern_Investing_Ep206_20261020.md").write_text(
            "### Practice Investment of the Day\n**Today's Pick:** GM — General Motors\n"
            "- **Risk Assessment:** Stop-loss set 6 percent below entry to limit "
            "loss to roughly $60 on the $1,000 position\n", encoding="utf-8")
        tracker = {"trades": [{"episode_num": 206, "symbol": "GM", "status": "open",
                               "stop_loss": {"price": 60.0}}]}
        assert mi._refresh_open_stops(tracker, tmp_path) == 1
        assert tracker["trades"][0]["stop_loss"] == {"pct": 6.0}

    def test_the_lint_fires_only_on_a_pick_with_no_readable_stop(self):
        from engine.digest_lint import LINTS, run_digest_lints
        assert "pick_stop_loss" in LINTS
        no_stop = ("### Practice Investment of the Day\n**Today's Pick:** COIN — Coinbase\n"
                   "**Invalidation:** a break below the 50-day average\n")
        fired, metrics = run_digest_lints(no_stop, ["pick_stop_loss"])
        assert fired and "COIN" in fired[0].note and metrics["pick_without_stop"] == 1
        with_stop = no_stop + "**Stop-Loss:** 8% below entry\n"
        assert run_digest_lints(with_stop, ["pick_stop_loss"])[0] == []
        none_day = "### Practice Investment of the Day\n**Today's Pick:** None — monitoring TW\n"
        assert run_digest_lints(none_day, ["pick_stop_loss"])[0] == []

    def test_the_show_opts_into_the_lint_and_the_prompt_requires_the_line(self):
        raw = yaml.safe_load((ROOT / "shows/modern_investing.yaml").read_text(encoding="utf-8"))
        assert "pick_stop_loss" in raw["digest_lints"]
        prompt = (ROOT / "shows/prompts/modern_investing_digest.txt").read_text(encoding="utf-8")
        assert "**Stop-Loss:** [REQUIRED" in prompt


# ---------------------------------------------------------------------------
# The pick extractor reads the digest's own sector and an exchange prefix
# ---------------------------------------------------------------------------

class TestPickExtraction:
    DIGEST = ("### Practice Investment of the Day\n**Trade Type:** Weekly Hold\n"
              "**Today's Pick:** TSX:H — Hydro One Limited\n**Market:** TSX\n"
              "**Sector:** utilities\n**Strategy:** Valuation entry\n"
              "**Confidence Level:** Low\n")

    def test_exchange_prefix_is_dropped_and_sector_read(self):
        t = mi._extract_trade_from_digest(self.DIGEST, 205)
        assert t["symbol"] == "H" and t["sector"] == "utilities" and t["confidence"] == "Low"

    def test_an_unknown_sector_word_is_left_for_the_classifier(self):
        t = mi._extract_trade_from_digest(self.DIGEST.replace("utilities", "widgets"), 205)
        assert t["sector"] == ""


# ---------------------------------------------------------------------------
# The trade review grades the forecast and carries the real benchmark
# ---------------------------------------------------------------------------

class TestTradeReview:
    def _tracker(self):
        d = datetime.date.today().isoformat()
        return {"metadata": {"position_size": 1000}, "summary": {
            "cumulative_pnl": -14.73, "total_trades": 87, "wins": 45,
            "win_rate_pct": 52.0, "current_streak": -1},
            "trades": [{"symbol": "EDV.TO", "status": "closed", "trade_type": "weekly",
                        "strategy": "catalyst", "confidence": "Medium",
                        "invalidation": "Q3 results reset guidance",
                        "stop_loss": {"pct": 8.0}, "entry_price": 76.0,
                        "exit_price": 77.18, "pnl_pct": 1.55, "pnl_dollars": 15.53,
                        "date": d, "entry_bar_date": "2026-10-14",
                        "exit_bar_date": "2026-10-20", "horizon_sessions": 5,
                        "nasdaq_return_pct": -2.24, "alpha_pct": 3.79}]}

    def test_no_lifetime_figures_and_the_real_alpha(self):
        block = mi._build_trade_review(self._tracker(), episode_num=300)
        assert "Running Total" not in block and "Win Rate" not in block
        assert "Current Streak" not in block and "87" not in block
        assert "**NASDAQ over the same sessions:** -2.24%" in block
        assert "**alpha +3.79%**" in block

    def test_the_forecast_is_handed_over_and_the_hold_is_in_sessions(self):
        block = mi._build_trade_review(self._tracker(), episode_num=300)
        assert "**Stated confidence:** Medium" in block
        assert "**Stated invalidation:** Q3 results reset guidance" in block
        assert "**Stated stop:** 8% below entry — not reached." in block
        assert "**Hold:** 5 sessions (Wednesday open → Tuesday close) — the full horizon" in block
        assert "calendar day" not in block.split("Describe")[0]

    def test_a_trade_without_a_stop_says_so(self):
        tr = self._tracker()
        del tr["trades"][0]["stop_loss"]
        assert "none the sim could read" in mi._build_trade_review(tr, episode_num=300)

    def test_a_missing_benchmark_is_never_estimated(self):
        tr = self._tracker()
        tr["trades"][0]["nasdaq_return_pct"] = None
        tr["trades"][0]["alpha_pct"] = None
        assert "never estimate it" in mi._build_trade_review(tr, episode_num=300)


# ---------------------------------------------------------------------------
# Portfolio Performance: the era record first, the lifetime blend as history
# ---------------------------------------------------------------------------

class TestPortfolioSummary:
    def _tracker(self):
        tr = {"metadata": {"position_size": 1000}, "summary": {},
              "trades": [_era_trade(i, a) for i, a in enumerate((2.0, -1.0, 0.5, -3.0, 1.0, 4.0))]}
        mi._recompute_summary(tr)
        return tr

    def test_the_record_leads_and_history_is_labelled(self):
        block = mi._build_portfolio_summary(self._tracker())
        assert block.index("THE RECORD") < block.index("HISTORY ONLY")
        assert "6 rules-based trades" in block
        assert "beat the index over their own window" in block
        assert "Best trade" not in block and "Worst trade" not in block
        assert "not yet distinguishable from luck" in block or "distinguishable from luck" in block

    def test_the_basis_note_airs_twice_then_retires(self, monkeypatch):
        monkeypatch.delenv("NERRA_HOOKS_READONLY", raising=False)
        tr = self._tracker()
        assert "ONE-TIME NOTE" in mi._build_portfolio_summary(tr, 300)
        assert "ONE-TIME NOTE" in mi._build_portfolio_summary(tr, 300)  # same episode, re-run
        assert "ONE-TIME NOTE" in mi._build_portfolio_summary(tr, 301)
        assert "ONE-TIME NOTE" not in mi._build_portfolio_summary(tr, 302)
        assert tr["metadata"]["basis_note_episodes"] == [300, 301]

    def test_a_readonly_run_never_stamps(self, monkeypatch):
        monkeypatch.setenv("NERRA_HOOKS_READONLY", "1")
        tr = self._tracker()
        mi._build_portfolio_summary(tr, 300)
        assert "basis_note_episodes" not in tr["metadata"]


# ---------------------------------------------------------------------------
# Measured entry factors: the market's record, scored on alpha
# ---------------------------------------------------------------------------

class TestEntryFactors:
    def _bars(self, n=60, vol=100.0, entry_vol=150.0):
        start = datetime.date(2026, 7, 1)
        bars = []
        d = start
        while len(bars) < n:
            if d.weekday() < 5:
                bars.append((d, 100.0 + len(bars) * 0.1, 100.0 + len(bars) * 0.1, 99.0, vol))
            d += datetime.timedelta(days=1)
        entry = bars[-1]
        bars[-1] = (entry[0], 110.0, 110.5, 109.0, entry_vol)
        return bars

    def test_factors_from_the_bars(self):
        bars = self._bars()
        f = mi._entry_factors(bars, bars[-1])
        assert f["entry_volume_ratio_20d"] == 1.5
        assert f["entry_vs_50dma_pct"] > 0

    def test_a_short_history_gives_none_never_a_guess(self):
        bars = self._bars(n=10)
        f = mi._entry_factors(bars, bars[-1])
        assert f == {"entry_volume_ratio_20d": None, "entry_vs_50dma_pct": None}

    def test_sessions_between_counts_bars_then_weekdays(self):
        bars = self._bars(n=60)
        assert mi._sessions_between(bars[-5][0], bars[-1][0], bars) == 5
        assert mi._sessions_between(datetime.date(2026, 10, 14), datetime.date(2026, 10, 20)) == 5

    def test_scoreboard_says_not_measurable_below_five_a_side(self):
        tr = {"trades": [_era_trade(i, 1.0, vol=1.5) for i in range(6)]
              + [_era_trade(10, -1.0, vol=0.5)]}
        out = mi._build_factor_scoreboard(tr)
        assert "not measurable yet (6 trades with, 1 without" in out

    def test_a_verdict_needs_ten_a_side_and_an_agreeing_median(self):
        above = [_era_trade(i, -3.0, vol=1.5) for i in range(10)]
        below = [_era_trade(20 + i, 1.0, vol=0.5) for i in range(10)]
        out = mi._build_factor_scoreboard({"trades": above + below})
        assert "the factor is NOT paying" in out
        # One outlier that flips the mean but not the median is noise.
        above2 = [_era_trade(i, -0.2, vol=1.5) for i in range(9)] + [_era_trade(9, 30.0, vol=1.5)]
        out2 = mi._build_factor_scoreboard({"trades": above2 + below})
        assert "noise, not a finding" in out2

    def test_backfill_stamps_from_bars_and_marks_unfetchable(self, monkeypatch):
        bars = self._bars()
        entry_d = bars[-1][0]
        t_ok = _era_trade(1, 1.0)
        t_ok.update({"entry_bar_date": entry_d.isoformat(), "exit_bar_date": entry_d.isoformat()})
        t_bad = _era_trade(2, 1.0)
        calls = []

        def fake_fetch(trade, *, period):
            calls.append(period)
            return bars if trade is t_ok else None
        monkeypatch.setattr(mi, "_fetch_bars_for_trade", fake_fetch)
        tr = {"trades": [t_ok, t_bad]}
        assert mi._backfill_entry_factors(tr) == 2
        assert t_ok["factors_version"] == 1 and t_ok["entry_volume_ratio_20d"] == 1.5
        assert t_ok["sessions_held"] == 1
        assert t_bad["factors_version"] == 0
        assert mi._backfill_entry_factors(tr) == 0  # nothing left to stamp
        assert calls == ["6mo", "6mo"]

    def test_the_lessons_block_carries_the_factor_scoreboard(self):
        src = (ROOT / "shows/hooks/modern_investing.py").read_text(encoding="utf-8")
        assert "factors = _build_factor_scoreboard(tracker)" in src
        assert "_record_entry_factors(trade, bars, entry_bar, exit_bar)" in src


# ---------------------------------------------------------------------------
# Confidence and options budgets, counted from the recorded picks
# ---------------------------------------------------------------------------

class TestBudgets:
    def test_five_mediums_spend_the_confidence_budget(self):
        tr = {"trades": [_era_trade(i, 0.0) for i in range(5)]}
        assert "budget is SPENT" in mi._confidence_budget_block(tr)
        tr["trades"][-1]["confidence"] = "Low"
        out = mi._confidence_budget_block(tr)
        assert "4 of the last 5" in out and "SPENT" not in out
        assert mi._confidence_budget_block({"trades": tr["trades"][:3]}) == ""

    def test_ten_share_picks_require_an_options_structure(self):
        tr = {"trades": [_era_trade(i, 0.0) for i in range(10)]}
        out = mi._options_cadence_block(tr)
        assert "MUST be a Covered Call or a Cash-Secured Put" in out
        tr["trades"][3]["structure"] = "covered_call"
        assert "1 of the last 10" in mi._options_cadence_block(tr)
        assert mi._options_cadence_block({"trades": tr["trades"][:9]}) == ""

    def test_voided_picks_do_not_count(self):
        tr = {"trades": [_era_trade(i, 0.0) for i in range(4)] + [dict(_era_trade(4, 0.0), status="voided")]}
        assert mi._confidence_budget_block(tr) == ""

    def test_the_budgets_ride_the_strategy_block(self):
        src = (ROOT / "shows/hooks/modern_investing.py").read_text(encoding="utf-8")
        i = src.index("def _strategy_block()")
        body = src[i:i + 1500]
        assert "_confidence_budget_block(tracker)" in body
        assert "_options_cadence_block(tracker)" in body


# ---------------------------------------------------------------------------
# The narrative callback recalls each trade once
# ---------------------------------------------------------------------------

class TestCallbackOnce:
    def test_each_trade_is_recalled_once(self, monkeypatch):
        monkeypatch.delenv("NERRA_HOOKS_READONLY", raising=False)
        d = (datetime.date.today() - datetime.timedelta(days=15)).isoformat()
        tr = {"trades": [{"status": "closed", "date": d, "symbol": "AVGO", "sector": "tech",
                          "strategy": "chips", "pnl_pct": -6.58, "episode_num": 194}]}
        first = mi._build_narrative_callback(tr, 208)
        assert "AVGO" in first and tr["trades"][0]["callback_in_episode"] == 208
        assert "AVGO" in mi._build_narrative_callback(tr, 208)  # a re-run of the same episode
        assert "skip" in mi._build_narrative_callback(tr, 209).lower()


# ---------------------------------------------------------------------------
# Public surfaces and the record's consumers
# ---------------------------------------------------------------------------

class TestPublicSurfaces:
    def test_ledger_rows_carry_the_new_columns(self):
        import scripts.build_mit_ledger as bl
        tr = {"summary": {"era_inception": "2026-08-18"},
              "trades": [dict(_era_trade(0, 1.0, vol=1.2, ma=3.0), sessions_held=5,
                              stop_loss={"pct": 8.0})]}
        row = bl.build(tr)["trades"][0]
        assert row["sessions_held"] == 5 and row["entry_volume_ratio_20d"] == 1.2
        assert row["stop_stated"] is True and row["stopped_out"] is False
        assert row["window_verified"] is True

    def test_the_signal_carries_structure_and_invalidation(self, tmp_path):
        trade = dict(_era_trade(0, 0.0), status="open", invalidation="a level",
                     structure="covered_call", date="2026-10-24")
        mi._write_trade_signal(tmp_path, trade, "", 300, {"metadata": {}})
        sig = json.loads((tmp_path / "trade_signal_ep300.json").read_text())
        assert sig["trade"]["structure"] == "covered_call"
        assert sig["trade"]["invalidation"] == "a level"

    def test_the_validator_requires_education_and_performance(self):
        from engine.validation import mi_validation_config
        names = {r.name for r in mi_validation_config().sections}
        assert {"Investor Education", "Portfolio Performance"} <= names

    def test_the_performance_pages_lead_with_the_era(self):
        perf = (ROOT / "templates/mit_performance_page.html.j2").read_text(encoding="utf-8")
        assert perf.index("The record: alpha vs NASDAQ") < perf.index("History: compounded matched-window alpha")
        show = (ROOT / "templates/show_page.html.j2").read_text(encoding="utf-8")
        assert "Monday: Pick" not in show and "Friday: Evaluate" not in show
        assert "Every episode: one pick" in show and "_es.era_alpha_pct" in show

    def test_the_method_doc_tells_the_truth(self):
        doc = (ROOT / "docs/mit_trading_method.md").read_text(encoding="utf-8")
        assert "one position at a time" not in doc
        assert "9 of the 41" in doc and "all 44 rules-based picks" in doc
        assert "no options position has been placed" in doc

    def test_prompts_carry_no_quotable_specimen_or_stale_cadence(self):
        system = (ROOT / "shows/prompts/modern_investing_system.txt").read_text(encoding="utf-8")
        assert "parking spot" not in system
        assert "Pick announced on Monday, evaluated on Friday" not in system
        digest = (ROOT / "shows/prompts/modern_investing_digest.txt").read_text(encoding="utf-8")
        assert "one position at a time" not in digest
        assert "WEEKLY HOLD (Monday episodes)" not in digest
        podcast = (ROOT / "shows/prompts/modern_investing_podcast.txt").read_text(encoding="utf-8")
        assert "habit the listener should copy" not in podcast
        assert "evaluate on Friday" not in podcast.split("Saturday")[0]

    def test_dashboard_metrics_exist(self):
        import scripts.generate_dashboard as gd
        keys = gd._experiment_live_metrics(ROOT).keys()
        assert {"mit_stop_stated_share_10ep", "mit_non_medium_share_10ep"} <= set(keys)


class TestTheCommittedRecord:
    """Read on the day of the review; the shape, not the values."""

    def test_the_tracker_recomputes_and_the_factor_scoreboard_renders(self):
        tr = json.loads((ROOT / "digests/modern_investing/investment_tracker.json").read_text(encoding="utf-8"))
        tr = copy.deepcopy(tr)
        mi._recompute_summary(tr)
        assert tr["summary"]["era_basis"] == "average_per_trade"
        # Renders whether or not the runs have backfilled the factors yet.
        assert isinstance(mi._build_factor_scoreboard(tr), str)
