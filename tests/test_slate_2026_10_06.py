"""Oct 6 2026 — the first slate after the Oct 5 merges.

* Modern Investing published nothing: the Oct 5 share-class fix finally
  priced HPS.A (picked 08-26), the NASDAQ benchmark still fetched one month
  of bars, so the trade closed with ``alpha_pct = None``, and the
  strategy-performance sum hit ``float += None``. The exception took the
  whole pre-fetch hook down, run_show "continued without hook data", and
  the digest prompt died on ``KeyError: 'market_indices'``.
* The claims metrics were written once, before repair and the coverage
  floor, so Tesla Ep626 read "2 verified" beside a committed ledger of 7.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from shows.hooks import modern_investing as mi

ROOT = Path(__file__).resolve().parent.parent


def _closed(symbol, alpha, *, sector="tech", tags=("momentum",), pnl=1.0):
    return {"symbol": symbol, "status": "closed", "pnl_pct": pnl,
            "alpha_pct": alpha, "sector": sector, "lesson_tags": list(tags)}


class TestAMissingAlphaIsNotZero:
    def test_a_closed_trade_without_alpha_no_longer_raises(self):
        tracker = {"trades": [_closed("A", 2.0), _closed("B", -1.0),
                              _closed("HPS.A", None, pnl=1.36)]}
        block = mi._build_strategy_performance(tracker)
        assert "STRATEGY PERFORMANCE ANALYSIS" in block

    def test_the_average_is_over_trades_that_carry_an_alpha(self):
        tracker = {"trades": [_closed("A", 2.0), _closed("B", 4.0),
                              _closed("C", None)]}
        block = mi._build_strategy_performance(tracker)
        # 3 trades in the sector, alpha averaged over the 2 that have one.
        assert "tech: 3 trades" in block and "avg alpha +3.00%" in block

    def test_best_and_worst_ignore_the_missing_alpha(self):
        tracker = {"trades": [_closed("A", 2.0), _closed("B", -4.0),
                              _closed("C", None)]}
        block = mi._build_strategy_performance(tracker)
        assert "Best trade: A" in block and "Worst trade: B" in block

    def test_nan_alpha_is_treated_as_missing(self):
        tracker = {"trades": [_closed("A", 2.0), _closed("B", 1.0),
                              _closed("C", float("nan"))]}
        assert "nan" not in mi._build_strategy_performance(tracker)


class TestTheBenchmarkReachesTheEntryBar:
    def test_a_late_priced_trade_fetches_a_window_back_to_its_entry(self, monkeypatch):
        periods = []

        def fake_bars(symbol, *, period="15d", attempts=3):
            periods.append((symbol, period))
            return None
        monkeypatch.setattr(mi, "_fetch_history_bars", fake_bars)
        entry = datetime.date.today() - datetime.timedelta(days=41)
        trade = {"trade_type": "flash", "entry_bar_date": entry.isoformat(),
                 "exit_bar_date": entry.isoformat(), "pnl_pct": 1.36}
        mi._annotate_trade_with_nasdaq(trade)
        assert periods and all(p == "3mo" for _s, p in periods)

    def test_a_fresh_trade_keeps_at_least_the_old_month(self, monkeypatch):
        periods = []
        monkeypatch.setattr(mi, "_fetch_history_bars",
                            lambda s, *, period="15d", attempts=3: periods.append(period))
        today = datetime.date.today().isoformat()
        mi._annotate_trade_with_nasdaq({"entry_bar_date": today, "pnl_pct": 1.0})
        assert periods and set(periods) == {"1mo"}


class TestOneFailingSectionCostsOnlyThatSection:
    @pytest.fixture
    def offline(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NERRA_HOOKS_READONLY", "1")
        monkeypatch.setattr(mi, "_fetch_market_indices", lambda: "INDICES")
        monkeypatch.setattr(mi, "_compute_benchmark_state", lambda tracker: None)
        tracker = {"trades": [_closed("A", 2.0), _closed("B", -1.0),
                              _closed("C", None)]}
        (tmp_path / mi.TRACKER_FILENAME).write_text(json.dumps(tracker))
        return SimpleNamespace(
            episode=SimpleNamespace(output_dir=str(tmp_path)),
            memory_enabled=False)

    def test_market_indices_survive_a_broken_analysis_block(self, offline, monkeypatch):
        def boom(_tracker):
            raise TypeError("unsupported operand type(s) for +=: 'float' and 'NoneType'")
        monkeypatch.setattr(mi, "_build_strategy_performance", boom)
        ctx = mi.pre_fetch(offline, episode_num=999)
        assert ctx["market_indices"] == "INDICES"
        assert "strategy_performance" in ctx
        assert ctx["metrics"]["mit_prefetch_failed_sections"] == 1

    def test_every_prompt_variable_is_present_when_a_section_fails(self, offline, monkeypatch):
        import re
        monkeypatch.setattr(mi, "_build_narrative_callback",
                            lambda t: (_ for _ in ()).throw(RuntimeError("x")))
        ctx = mi.pre_fetch(offline, episode_num=999)
        for name in ("modern_investing_digest.txt", "modern_investing_podcast.txt"):
            text = (ROOT / "shows" / "prompts" / name).read_text(encoding="utf-8")
            hook_keys = {"market_indices", "portfolio_summary", "strategy_performance",
                         "narrative_callback", "lessons_learned_block", "tone_hint"}
            used = set(re.findall(r"\{([a-z_]+)\}", text)) & hook_keys
            assert used <= set(ctx), (name, used - set(ctx))

    def test_a_clean_run_reports_zero_failed_sections(self, offline):
        assert mi.pre_fetch(offline, episode_num=999)["metrics"] == {
            "mit_prefetch_failed_sections": 0}

    def test_resume_path_never_passes_hook_metrics_to_a_prompt(self):
        src = (ROOT / "engine" / "pipeline_resume.py").read_text(encoding="utf-8")
        assert 'extra_context.pop("metrics", None)' in src


class TestClaimsMetricsRecordWhatShips:
    def test_counts_are_re_recorded_after_the_coverage_floor(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        floor = src.index("attempt_item_coverage_repair(")
        final = src.index('metrics.record("source_integrity_verified", _si_gate.claims_verified)', floor)
        flag = src.index("# Flag mode (Oct 1 2026", floor)
        assert floor < final < flag

    def test_the_pre_floor_reading_is_kept_under_its_own_name(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'metrics.record("source_integrity_verified_pre_floor"' in src


class TestPromoFrameWithoutItsOpener:
    def test_the_frame_second_clause_anchors_a_promo_cut(self):
        from engine.daily_edition import find_promo_cut
        body = ("Ridership on the new lines rose every year since they opened . " * 4)
        words = (body + "The city opened three lines that year . If you like today's "
                 "episode, our sister show Prediction Markets Daily is worth a "
                 "spot in your feed . Mira is an AI host .").split()
        seg = {"start": 0.0, "end": float(len(words)),
               "words": [{"word": w, "start": float(i), "end": i + 0.9}
                         for i, w in enumerate(words)]}
        hit = find_promo_cut({"duration": float(len(words)), "segments": [seg]})
        assert hit["kind"] == "promo" and hit["anchor"] == "frame"
        assert words[int(hit["raw_seconds"]) + 1] == "If"  # cut lands just before the frame


class TestATimelineIsNotARepetitionLoop:
    """SpaceX Ep122's crew-return timeline ("6:20 a.m. EDT on October 7",
    "11:34 a.m. EDT on October 8"…) scored 3 and read as a regeneration
    candidate; the clock words are timestamp furniture."""

    def _score(self, text):
        from engine.generator import _validate_llm_output
        return _validate_llm_output(text, "digest", "spacex", 0, ())

    def test_the_committed_timeline_does_not_score(self):
        text = (ROOT / "digests" / "spacex" / "SpaceX_Daily_Ep122_20261006.md")
        if not text.exists():
            pytest.skip("digest not in this checkout")
        assert self._score(text.read_text(encoding="utf-8")) < 3

    def test_a_prose_loop_beside_clock_times_still_counts(self):
        filler = "Engineers reviewed telemetry from the booster after landing today. " * 6
        loop = "watch for the kicker here, " * 8
        times = "Hatch close at 6:20 a.m. EDT on October 7. " * 5
        assert self._score(filler + loop + times) >= 1
