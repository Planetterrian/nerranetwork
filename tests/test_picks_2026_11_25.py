"""Nov 25 2026: the operator's picks 3a, 5a and 6a.

3a  the LLM request timeout is 900 s and any completed call slower than an
    ABSOLUTE 480 s raises an annotation (the relative canary moves with the
    timeout, so the raise alone would have silenced it);
5a  a show whose digest prompt asks for the podcast-app TITLE line gets one
    small follow-up call when the digest left the line out, and anything
    short of a fitting answer keeps the hook, as before;
6a  requests to Reddit leave one at a time; the two weekly news shows read
    their week; a read-only probe checks a candidate URL from a runner.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def _wf(name):
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))


class TestTheTimeoutAndItsAbsoluteAlarm:
    def test_both_jobs_that_call_the_model_wait_900_seconds(self):
        run = next(s for s in _wf("run-show.yml")["jobs"]["run"]["steps"]
                   if s.get("name") == "Run show pipeline")
        assert run["env"]["NERRA_LLM_TIMEOUT_SECONDS"] == "900"
        assert "NERRA_LLM_TIMEOUT_SECONDS: '900'" in (
            ROOT / ".github" / "workflows" / "render-video.yml").read_text(encoding="utf-8")
        # One worst-case stage (three attempts) still cannot eat the watchdog.
        assert 3 * 900 <= int(run["env"]["PIPELINE_TIMEOUT_SECONDS"]) + 600

    def test_the_alarm_is_absolute_and_below_the_old_timeout(self):
        from engine import generator
        assert generator.SLOW_CALL_ALARM_S == 480.0
        assert generator.SLOW_CALL_ALARM_S < 600

    def test_a_slow_call_annotates_and_is_counted(self, capsys, monkeypatch):
        from engine import generator
        monkeypatch.setattr(generator, "_slow_call_stats",
                            {"slowest_s": None, "slowest_model": "", "alarms": 0})
        monkeypatch.delenv("NERRA_LLM_SLOW_ALARM_SECONDS", raising=False)
        assert generator.note_call_latency("grok-4.7", 120.0, 900.0) is False
        assert capsys.readouterr().out == ""
        assert generator.note_call_latency("grok-4.7", 508.7, 900.0) is True
        out = capsys.readouterr().out
        assert out.startswith("::warning::slow LLM call: grok-4.7 took 509s")
        stats = generator.slow_call_stats()
        assert stats == {"slowest_s": 508.7, "slowest_model": "grok-4.7", "alarms": 1}
        # A faster later call never lowers the run's slowest.
        generator.note_call_latency("grok-4.3", 30.0, 900.0)
        assert generator.slow_call_stats()["slowest_s"] == 508.7

    def test_the_call_path_and_the_run_record_it(self):
        gen = (ROOT / "engine" / "generator.py").read_text(encoding="utf-8")
        assert "note_call_latency(model, _elapsed, timeout)" in gen
        run = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'metrics.record("llm_slowest_call_s"' in run
        assert '"llm_slowest_call_s"' in (
            ROOT / "scripts" / "model_trial_report.py").read_text(encoding="utf-8")


class TestTheMissingAppTitleIsAskedForOnce:
    def _cfg(self, slug):
        from engine.config import load_config
        return load_config(str(ROOT / "shows" / f"{slug}.yaml"))

    def test_only_shows_whose_prompt_asks_for_the_line(self):
        from engine.app_title import wants_app_title
        assert wants_app_title(self._cfg("tesla"))
        assert wants_app_title(self._cfg("spacex"))
        assert not wants_app_title(self._cfg("omni_view"))
        assert not wants_app_title(SimpleNamespace(llm=SimpleNamespace(digest_prompt_file="")))

    def test_a_fitting_answer_is_the_title(self):
        from engine.app_title import followup_app_title
        calls = []

        def call(prompt, **kw):
            calls.append((prompt, kw))
            return "**TITLE:** \"Cybercab Line Starts Volume Builds.\"", {}

        hook = "Tesla started volume builds of the Cybercab at Giga Texas this week"
        title = followup_app_title(self._cfg("tesla"), "### Top\nThe story.", hook, call=call)
        assert title == "Cybercab Line Starts Volume Builds"
        assert len(calls) == 1, "one call, never a retry"
        prompt, kw = calls[0]
        assert hook in prompt and "The story." in prompt
        assert kw["timeout"] <= 60

    def test_anything_else_keeps_the_hook(self):
        from engine.app_title import followup_app_title
        from engine.titles import APP_TITLE_FOLLOWUP_MAX
        cfg = self._cfg("tesla")
        hook = "A hook sentence about the day"

        def boom(*a, **k):
            raise RuntimeError("down")

        assert followup_app_title(cfg, "d", hook, call=boom) is None
        too_long = "x" * (APP_TITLE_FOLLOWUP_MAX + 1)
        assert followup_app_title(cfg, "d", hook, call=lambda *a, **k: (too_long, {})) is None
        assert followup_app_title(cfg, "d", hook, call=lambda *a, **k: ("", {})) is None
        # The hook restated is not a title.
        assert followup_app_title(cfg, "d", hook, call=lambda *a, **k: (hook + ".", {})) is None
        # No call at all when the budget is nearly spent or the show never asked.
        never = lambda *a, **k: (_ for _ in ()).throw(AssertionError("called"))  # noqa: E731
        assert followup_app_title(cfg, "d", hook, call=never, budget_left_s=120) is None
        assert followup_app_title(self._cfg("omni_view"), "d", hook, call=never) is None

    def test_the_answer_is_never_clipped(self):
        src = (ROOT / "engine" / "app_title.py").read_text(encoding="utf-8")
        assert "clip_words" not in src and "[:APP_TITLE" not in src

    def test_run_show_asks_only_when_the_line_is_missing(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        i = src.index("title_hook = _extract_short_title(x_thread)")
        block = src[i:i + 1600]
        assert "if not title_hook and hook:" in block
        assert "followup_app_title(" in block
        assert "title_hook = title_hook or hook" in block


class TestSourcesAreReadFromWhereTheShowsReadThem:
    def test_reddit_requests_leave_one_at_a_time(self, monkeypatch):
        from engine import fetcher
        clock = [100.0]
        slept = []
        monkeypatch.setattr(fetcher, "_pacing_clock", lambda: clock[0])
        monkeypatch.setattr(fetcher, "_pacing_sleep", lambda s: slept.append(round(s, 2)))
        monkeypatch.setattr(fetcher, "_host_last_request", {})
        gap = fetcher._HOST_PACING_S["reddit.com"]
        for url in ("https://www.reddit.com/r/a/.rss", "https://www.reddit.com/r/b/.rss",
                    "https://example.com/feed", "https://old.reddit.com/r/c/.rss"):
            fetcher._pace_request(url)
        assert slept == [gap, 2 * gap], "the first leaves at once; no other host waits"
        assert "_pace_request(url)" in (ROOT / "engine" / "fetcher.py").read_text(encoding="utf-8")

    def test_the_weekly_news_shows_read_their_week(self):
        for slug in ("finansy_prosto", "env_intel", "offshore_north"):
            data = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            assert max(data["fetch_expansion_hours"]) >= 168, slug

    def test_the_probe_reads_and_never_writes(self):
        wf = _wf("probe-urls.yml")
        assert wf["permissions"] == {"contents": "read"}
        text = (ROOT / ".github" / "workflows" / "probe-urls.yml").read_text(encoding="utf-8")
        assert "secrets." not in text and "git push" not in text
        assert wf["jobs"]["probe"]["runs-on"] == "ubuntu-26.04"

    def test_the_probe_describes_a_feed_and_a_page(self):
        import probe_urls
        feed = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>'
                b'<item><title>One</title><pubDate>Mon, 23 Nov 2026 10:00:00 GMT</pubDate></item>'
                b'</channel></rss>')
        lines = probe_urls.describe("u", 200, "application/rss+xml", feed, None)
        assert "feed: 1 entries, newest 2026-11-23" in lines
        page = (b'<link rel="alternate" type="application/rss+xml" href="/x/feed">'
                b'<tr><th>Architect</th><td>VPLP</td></tr>')
        lines = probe_urls.describe("u", 200, "text/html", page, r"<tr>\s*<th[^>]*>.*?</tr>")
        assert "declares feed: /x/feed" in lines
        assert any("Architect" in ln for ln in lines)
        rows = probe_urls.read_list(probe_urls.DEFAULT_LIST)
        assert rows and all(u.startswith("https://") for u, _ in rows)


class TestMovedPagesAreReadAtTheirNewAddress:
    """Nov 25 2026, read from a GitHub runner by Actions "Probe URLs"."""

    def test_env_intel_reads_no_renamed_ministry_feed(self):
        text = (ROOT / "shows/env_intel.yaml").read_text(encoding="utf-8")
        for dead in ("environment-and-parks", "energy-and-climate-solutions",
                     "water-land-and-resource-stewardship",
                     "emergency-management-and-climate-readiness"):
            assert f"news.gov.bc.ca/ministries/{dead}/feed" not in text
        # The two feeds that carried November items on the day of the probe.
        assert "news.gov.bc.ca/themes/environmental-protection-and-sustainability/feed" in text
        assert "news.gov.bc.ca/news-subscribe/natural-resources/feed" in text

    def test_no_boat_entry_points_at_a_page_that_redirects_home(self):
        import json

        data = json.loads((ROOT / "site/data/offshore_north_dashboard.json").read_text(encoding="utf-8"))
        slugs = {e.get("imoca_slug") for e in data["rdr_imoca_entries"]["entries"]}
        assert not slugs & {"emira-iv", "horizon-29", "coup-de-pouce-1", "tr-racing-1"}
        canada = next(e for e in data["rdr_imoca_entries"]["entries"] if e.get("canada"))
        assert canada["imoca_slug"] == "canada-ocean-racing-be-water-positive"
