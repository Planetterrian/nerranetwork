"""Workflow review, Nov 24 2026.

* SpaceX's pre-fetch hook ran the launch-dashboard refresh inside itself.
  run_show waits 60 s for a hook; the refresh took longer on Nov 17, 20 and
  21, the hook was abandoned, and Ep165, Ep168 and Ep169 shipped with no
  share price, the fallback closing and no story memory. The refresh now
  runs beside the episode, and a lost hook is a metric.
* support.html was back on the retired, card-tested donation link because
  the repo variable still held it. A retired link is never rendered.
"""
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestSpacexHookNeverWaitsOnTheDashboard:
    def test_pre_fetch_returns_while_the_refresh_hangs(self, monkeypatch):
        import subprocess
        import shows.hooks.spacex as sx
        monkeypatch.setattr(sx.show_memory, "memory_pre_fetch", lambda *a, **k: {})
        monkeypatch.setattr(sx, "_fetch_spcx_quote",
                            lambda: (127.79, "-7.7%", "yfinance_history"))
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: time.sleep(3))
        t0 = time.monotonic()
        ctx = sx.pre_fetch(object(), episode_num=172, today_str="November 24, 2026")
        assert time.monotonic() - t0 < 1.5
        assert "127.79" in ctx["spcx_market_block"]
        assert "one hundred twenty-seven dollars" in ctx["closing_block"]

    def test_run_show_records_a_lost_hook(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'metrics.record("pre_fetch_hook_failed", type(exc).__name__)' in src


class TestRetiredDonationLinkNeverRenders:
    def test_the_variable_holding_the_retired_link_is_overridden(self, monkeypatch):
        import generate_html as gh
        monkeypatch.setenv("STRIPE_LINK_DONATE_ONCE",
                           "https://donate.stripe.com/dRm8wQ8XEd5weiC0Rx0Ba03")
        assert gh._donate_once_url() == gh.CURRENT_DONATE_ONCE_LINK

    def test_any_other_value_passes_through(self, monkeypatch):
        import generate_html as gh
        monkeypatch.setenv("STRIPE_LINK_DONATE_ONCE", "https://donate.stripe.com/newlink")
        assert gh._donate_once_url() == "https://donate.stripe.com/newlink"
        monkeypatch.delenv("STRIPE_LINK_DONATE_ONCE")
        assert gh._donate_once_url() == ""

    def test_the_workflow_fallback_matches(self):
        import generate_html as gh
        text = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
        assert f"STRIPE_LINK_DONATE_ONCE || '{gh.CURRENT_DONATE_ONCE_LINK}'" in text
