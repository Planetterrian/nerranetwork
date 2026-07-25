"""Drift guards for the July 25 2026 listener-feedback quality pass.

Fixes pinned here:
1. Narrative memory never seeds ``EpN`` abbreviations; continuity budget ≤1.
2. ``replace_episode_numbers`` expands ``Ep141`` / ``Ep 43`` to spoken words.
3. SpaceX prompts require naming Super Heavy booster vs Ship on landings.
4. MIT never persists NaN benchmark closes; scoreboard survives quote gaps.
5. Dashboard show_page URLs match public filenames; Monday shows aren't
   falsely stale at 72h; Portfolio YTD doesn't coalesce null→0.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class TestEpisodeAbbrevSpeech:
    def test_pronunciation_expands_ep_abbrev(self):
        from assets.pronunciation import replace_episode_numbers

        out = replace_episode_numbers(
            "Remember, the show covered Starship on Ep141 — today moves forward."
        )
        assert "Ep141" not in out
        assert "episode one hundred forty-one" in out

    def test_show_memory_block_has_budget_not_epn(self):
        import re
        from engine import show_memory as sm

        cfg = sm.get_config("fascinating_frontiers")
        tracker = {
            "programs": {
                "starship_mars": {
                    "display_name": "Starship",
                    "status": "Flight tests ongoing.",
                    "key_open_questions": ["Reuse cadence?"],
                    "last_major_update_episode": 140,
                    "last_major_update_date": "2026-07-23",
                    "last_mentioned_episode": 141,
                    "last_mentioned_date": "2026-07-24",
                }
            }
        }
        block = sm.build_narrative_status_block(tracker, cfg.label)
        assert "CONTINUITY BUDGET" in block
        assert "episode 141" in block
        assert "last covered on air: 2026-07-24; episode 141" in block
        for line in block.splitlines():
            if "last covered on air:" in line or "status last reviewed:" in line:
                assert not re.search(r"\bEp\d+\b", line), line


class TestSpaceXStageNaming:
    def test_digest_has_name_the_stage_rule(self):
        text = (_ROOT / "shows/prompts/spacex_digest.txt").read_text(
            encoding="utf-8")
        assert "HARD RULE — NAME THE STAGE" in text
        assert "Super Heavy booster" in text
        assert "Ship / Starship upper stage" in text

    def test_podcast_has_name_the_stage_rule(self):
        text = (_ROOT / "shows/prompts/spacex_podcast.txt").read_text(
            encoding="utf-8")
        assert "HARD RULE — NAME THE STAGE" in text
        assert "CONTINUITY BUDGET" in text


class TestMITNaNBenchmark:
    def test_fetch_rejects_nan(self):
        import types
        import pandas as pd
        from shows.hooks import modern_investing as mi

        class _FakeTicker:
            def history(self, **kwargs):
                return pd.DataFrame({"Close": [float("nan")]})

        fake_yf = types.ModuleType("yfinance")
        fake_yf.Ticker = lambda *_a, **_k: _FakeTicker()
        with patch.dict(sys.modules, {"yfinance": fake_yf}), \
             patch("time.sleep"):
            assert mi._fetch_nasdaq_close() is None

    def test_build_block_keeps_matched_window_when_close_nan(self):
        from shows.hooks import modern_investing as mi

        tracker = {
            "benchmark": {
                "current_close": float("nan"),
                "ytd_pct": float("nan"),
                "inception_to_date_pct": float("nan"),
            },
            "alpha": {"ytd_pct": float("nan"), "inception_to_date_pct": float("nan")},
            "summary": {
                "matched_window_alpha_pct": 6.59,
                "matched_window_trades": 40,
                "compounded_return_pct": 12.0,
                "compounded_nasdaq_matched_pct": 5.0,
                "alpha_t_stat": 1.2,
                "alpha_statistically_significant": False,
                "benchmark_scores": {},
            },
            "trades": [],
            "metadata": {"position_size": 1000},
        }
        block = mi._build_benchmark_block(tracker)
        assert "temporarily unavailable" in block.lower() or "unavailable" in block.lower()
        assert "MATCHED-WINDOW" in block
        assert "6.59" in block or "+6.59" in block
        assert "do NOT invent" in block

    def test_compute_benchmark_never_persists_nan(self):
        from shows.hooks import modern_investing as mi

        tracker = {
            "metadata": {
                "nasdaq_inception_close": 15000.0,
                "nasdaq_ytd_start_close": 18000.0,
                "nasdaq_ytd_year": 2026,
                "position_size": 1000,
            },
            "benchmark": {"current_close": float("nan")},
            "alpha": {"monthly": {}},
            "trades": [],
        }
        with patch.object(mi, "_fetch_nasdaq_close", return_value=float("nan")):
            mi._compute_benchmark_state(tracker)
        close = tracker["benchmark"]["current_close"]
        assert close is None or (isinstance(close, float) and math.isfinite(close))
        assert tracker["benchmark"]["current_close"] is None
        assert tracker["alpha"]["ytd_pct"] is None


class TestDashboardShowPagesAndCadence:
    def test_show_page_map_covers_network(self):
        from scripts import generate_dashboard as gd

        assert gd._SHOW_PAGE_BY_SLUG["dp_pod"] == "thedppod.html"
        assert gd._SHOW_PAGE_BY_SLUG["modern_investing"] == "modern-investing.html"
        assert gd._SHOW_PAGE_BY_SLUG["fascinating_frontiers"] == (
            "fascinating-frontiers.html")
        assert gd._SHOW_PAGE_BY_SLUG["finansy_prosto"].startswith("ru/")
        assert gd._SHOW_PAGE_BY_SLUG["age_of_ai"] == "age-of-ai.html"

    def test_monday_show_not_stale_at_four_days(self):
        from scripts import generate_dashboard as gd

        warn_h, stale_h = gd._PUB_AGE_THRESHOLDS_H["env_intel"]
        assert warn_h > 72
        assert stale_h > 96
        assert gd._PUB_AGE_THRESHOLDS_H["age_of_ai"] is None

    def test_management_html_portfolio_ytd_no_null_coalesce(self):
        html = (_ROOT / "management.html").read_text(encoding="utf-8")
        assert "sumOrDash" in html
        assert "alpha.ytd_pct ?? 0" not in html
        assert "matched_window_alpha_pct" in html
