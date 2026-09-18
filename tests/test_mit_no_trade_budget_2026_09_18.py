"""MIT no-trade loop (Sep 18 2026): the cold streak must not starve the record.

From Ep152 (2026-08-28), the first episode after the rules-based era's
record turned negative, ``_build_regime_block`` told the model an
explicit no-trade day was "acceptable and unremarkable" and the show
declared no trade on 19 of 23 episodes. The drought valve fired about
weekly, the pick it forced was voided (ILMN, PATH) or closed into the
same cold ten-trade window, and that window never turned over — a
self-starving loop with 9 closed era trades in a month. Three data-side
changes, all prompt-context (A/B-listen per landmine #17):

- the COLD text raises the bar on the pick, never on picking;
- a voided pick does not reset the drought clock;
- a no-trade budget of one per five episodes, counted from the
  committed trade_signal files, makes a pick mandatory once spent.
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shows.hooks import modern_investing as mi  # noqa: E402


def _closed(alpha, pnl_dollars, date):
    return {"status": "closed", "alpha_pct": alpha, "pnl_pct": alpha,
            "pnl_dollars": pnl_dollars, "date": date}


def _signals(tmp_path, actions, start_ep=100):
    for i, action in enumerate(actions):
        (tmp_path / f"trade_signal_ep{start_ep + i:03d}.json").write_text(
            json.dumps({"action": action, "episode_num": start_ep + i}),
            encoding="utf-8")
    return start_ep + len(actions)


class TestColdTextNoLongerLicensesNoTrade:
    def test_cold_streak_expects_a_pick(self):
        recent = datetime.date.today().isoformat()
        block = mi._build_regime_block(
            {"trades": [_closed(-2.0, -20.0, recent) for _ in range(10)]})
        assert "COLD STREAK" in block
        assert "acceptable and unremarkable" not in block
        assert "still expected" in block
        assert "3+ independent aligned factors" in block
        assert "specific to today's tape" in block
        assert "never the streak" in block

    def test_cold_keeps_the_transparency_line(self):
        recent = datetime.date.today().isoformat()
        block = mi._build_regime_block(
            {"trades": [_closed(-2.0, -20.0, recent) for _ in range(10)]})
        assert "TELL LISTENERS PLAINLY" in block

    def test_live_tracker_no_longer_reads_no_trade_as_unremarkable(self):
        tracker = json.loads((ROOT / "digests" / "modern_investing"
                              / "investment_tracker.json").read_text())
        assert "acceptable and unremarkable" not in mi._build_regime_block(tracker)


class TestVoidedPicksDoNotResetTheDrought:
    def test_voided_pick_is_ignored(self):
        old = (datetime.date.today() - datetime.timedelta(days=12)).isoformat()
        fresh = datetime.date.today().isoformat()
        tracker = {"trades": [_closed(-2.0, -20.0, old) for _ in range(10)]
                   + [{"status": "voided", "date": fresh}]}
        assert mi._days_since_last_pick(tracker) == 12
        assert "SELECTIVE RESET" in mi._build_regime_block(tracker)

    def test_open_pick_still_counts(self):
        old = (datetime.date.today() - datetime.timedelta(days=12)).isoformat()
        fresh = datetime.date.today().isoformat()
        tracker = {"trades": [_closed(-2.0, -20.0, old) for _ in range(10)]
                   + [{"status": "open", "date": fresh}]}
        assert mi._days_since_last_pick(tracker) == 0


class TestNoTradeBudget:
    def test_no_signals_means_no_block(self, tmp_path):
        assert mi._no_trade_budget_block(tmp_path, 10) == ""

    def test_spent_budget_makes_a_pick_mandatory(self, tmp_path):
        nxt = _signals(tmp_path, ["new_trade", "no_trade", "no_trade",
                                  "no_trade", "no_trade"])
        block = mi._no_trade_budget_block(tmp_path, nxt)
        assert "4 of the last 5" in block
        assert "SPENT" in block and "MUST name a pick" in block

    def test_one_no_trade_in_five_spends_it(self, tmp_path):
        nxt = _signals(tmp_path, ["new_trade", "new_trade", "no_trade",
                                  "new_trade", "new_trade"])
        assert "SPENT" in mi._no_trade_budget_block(tmp_path, nxt)

    def test_clean_window_keeps_the_allowance_with_conditions(self, tmp_path):
        nxt = _signals(tmp_path, ["new_trade"] * 5)
        block = mi._no_trade_budget_block(tmp_path, nxt)
        assert "0 of the last 5" in block
        assert "SPENT" not in block
        assert "specific to today's tape" in block

    def test_only_signals_before_this_episode_count(self, tmp_path):
        # Six signals; the episode being written is 103, so only 100-102
        # are in the window and none of them is a no_trade.
        _signals(tmp_path, ["new_trade", "new_trade", "new_trade",
                            "no_trade", "no_trade", "no_trade"])
        assert "SPENT" not in mi._no_trade_budget_block(tmp_path, 103)

    def test_window_is_the_last_five_only(self, tmp_path):
        nxt = _signals(tmp_path, ["no_trade"] * 3 + ["new_trade"] * 5)
        assert "SPENT" not in mi._no_trade_budget_block(tmp_path, nxt)

    def test_unreadable_signal_is_skipped(self, tmp_path):
        nxt = _signals(tmp_path, ["new_trade"] * 4)
        (tmp_path / f"trade_signal_ep{nxt:03d}.json").write_text("{not json",
                                                                encoding="utf-8")
        block = mi._no_trade_budget_block(tmp_path, nxt + 1)
        assert "0 of the last 4" in block

    def test_live_signals_spend_the_budget_today(self):
        """The real Sep 18 state: 4 of the last 5 signals were no_trade."""
        block = mi._no_trade_budget_block(
            ROOT / "digests" / "modern_investing", 175)
        assert "SPENT" in block


class TestWiring:
    def test_budget_reaches_the_prompt_slot(self):
        src = (ROOT / "shows" / "hooks" / "modern_investing.py").read_text(
            encoding="utf-8")
        i = src.index("def pre_fetch(")
        j = src.index("\ndef ", i + 10)
        body = src[i:j]
        assert "_no_trade_budget_block(output_dir, episode_num)" in body
        assert 'context["strategy_performance"] = strategy_block' in body

    def test_budget_constants(self):
        assert mi._NO_TRADE_BUDGET == 1
        assert mi._NO_TRADE_BUDGET_WINDOW == 5

    def test_register_metric_is_computable(self):
        from scripts import generate_dashboard as gd
        val = gd._experiment_live_metrics(ROOT).get("mit_new_trade_share_10ep")
        assert val is None or 0.0 <= val <= 1.0
