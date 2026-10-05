"""Oct 4 2026 — review of the first full slate after the Oct 3 pass.

Three defects the Sunday slate exposed:

1. The weekly newsletter run hit its 45-minute timeout on four Sundays
   running (Sep 13 - Oct 4): Tesla, SpaceX, Planetterrian and UC got no
   weekly after Sep 6, ten cohort shows each spent ~4 minutes writing a
   weekly their missing Buttondown tag then refused, and the cancelled job
   never committed the sent markers of the shows that DID go out.
2. The Sunday week-in-review instruction offered "just after the intro" —
   the slot the cold-open rule forbids (13/19 scripts on Sep 27, 3/19 on
   Oct 4, Tesla among them).
3. Nerra Daily's handoffs ignored the one-in-three show-name rule on every
   full edition (18/18 on Oct 3, 18/19 on Oct 4).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_weekly_newsletters as rwn  # noqa: E402


def _cfg(enabled=True, tag="Tesla Shorts Time", key_env="BUTTONDOWN_API_KEY"):
    return SimpleNamespace(newsletter=SimpleNamespace(
        enabled=enabled, tag=tag, api_key_env=key_env))


class TestWeeklyOrder:
    def test_flagships_first_and_nothing_lost(self):
        shows = sorted(rwn.SHOWS)
        out = rwn.ordered_shows(shows)
        assert sorted(out) == shows and len(out) == len(set(out))
        assert out[:4] == ["tesla", "spacex", "models_agents", "fascinating_frontiers"]

    def test_priority_shows_are_real_shows(self):
        for slug in rwn.PRIORITY_SHOWS:
            assert slug in rwn.SHOWS, slug


class TestSendPreflight:
    @pytest.fixture(autouse=True)
    def _key(self, monkeypatch):
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "k")

    def _patch(self, monkeypatch, cfg, known_tags, resolved):
        import engine.config as ec
        import engine.newsletter as nl

        monkeypatch.setattr(ec, "load_config", lambda p: cfg)
        nl._ALL_TAG_NAMES.clear()
        nl._ALL_TAG_NAMES.extend(known_tags)
        monkeypatch.setattr(nl, "_resolve_tag_ids", lambda names, key: resolved)

    def test_missing_tag_is_skipped_before_synthesis(self, monkeypatch):
        self._patch(monkeypatch, _cfg(tag="MAG 7 Daily"), ["Tesla Shorts Time"], {})
        assert "no tag 'MAG 7 Daily'" in rwn.send_preflight("mag7")

    def test_a_resolved_tag_proceeds(self, monkeypatch):
        self._patch(monkeypatch, _cfg(), ["Tesla Shorts Time"], {"Tesla Shorts Time": "tag_1"})
        assert rwn.send_preflight("tesla") == ""

    def test_a_failed_tag_fetch_never_skips(self, monkeypatch):
        self._patch(monkeypatch, _cfg(), [], {})
        assert rwn.send_preflight("tesla") == ""

    def test_disabled_and_keyless_shows_are_skipped(self, monkeypatch):
        self._patch(monkeypatch, _cfg(enabled=False), [], {})
        assert rwn.send_preflight("x") == "newsletter not enabled"
        monkeypatch.delenv("BUTTONDOWN_API_KEY")
        self._patch(monkeypatch, _cfg(), [], {})
        assert rwn.send_preflight("x").startswith("no API key")

    def test_main_does_not_synthesize_a_show_it_cannot_send(self, monkeypatch, tmp_path):
        monkeypatch.setattr(rwn, "send_preflight", lambda slug: "no tag")
        monkeypatch.setattr(rwn, "get_lake_stats",
                            lambda: {"total_episodes": 0, "total_words": 0})

        def _boom(**kw):
            raise AssertionError("synthesized a show whose send could not happen")

        monkeypatch.setattr(rwn, "synthesize_weekly_newsletter", _boom)
        monkeypatch.setattr(sys, "argv", ["x", "--show", "mag7", "--date", "2026-10-04",
                                          "--output-dir", str(tmp_path)])
        rwn.main()

    def test_dry_run_still_synthesizes(self, monkeypatch, tmp_path):
        called = []
        monkeypatch.setattr(rwn, "send_preflight", lambda slug: "no tag")
        monkeypatch.setattr(rwn, "get_lake_stats",
                            lambda: {"total_episodes": 0, "total_words": 0})
        monkeypatch.setattr(rwn, "synthesize_weekly_newsletter",
                            lambda **kw: called.append(kw) or None)
        monkeypatch.setattr(sys, "argv", ["x", "--show", "mag7", "--date", "2026-10-04",
                                          "--dry-run", "--output-dir", str(tmp_path)])
        rwn.main()
        assert called


class TestWeeklyWorkflow:
    def test_timeouts_and_always_commit(self):
        wf = yaml.safe_load((ROOT / ".github/workflows/weekly-newsletter.yml").read_text())
        job = wf["jobs"]["generate"]
        steps = job["steps"]
        run = next(s for s in steps if s.get("name") == "Run weekly newsletters")
        commit = next(s for s in steps if "safe-commit-push" in str(s.get("uses", "")))
        assert run["timeout-minutes"] < job["timeout-minutes"]
        assert commit.get("if") == "always()"

    def test_todays_sends_are_recorded(self):
        for slug in ("fascinating_frontiers", "first_principles", "models_agents",
                     "models_agents_beginners", "modern_investing", "omni_view"):
            p = ROOT / "outputs/newsletters" / f"{slug}_weekly_2026-10-04.sent.json"
            assert json.loads(p.read_text())["email_id"].startswith("em_"), slug


class TestSundaySegmentPlacement:
    def test_segment_goes_before_the_close_only(self, monkeypatch):
        import engine.weekly_recap as wr

        eps = [{"episode_num": i, "date": f"2026-09-{28 + i}", "hook": f"Story {i} happened",
                "entities": ["Tesla"]} for i in range(3)]
        monkeypatch.setattr(wr, "query_show_range", lambda *a, **k: eps, raising=False)
        import engine.content_lake as cl
        monkeypatch.setattr(cl, "query_show_range", lambda *a, **k: eps)
        import datetime as dt
        seg = wr.build_weekly_summary_segment("tesla", "Tesla Shorts Time", dt.date(2026, 10, 4))
        assert seg and "right before the closing" in seg
        assert "just after the intro" not in seg
        assert "never between the cold open and the first story" in seg


class TestNerraDailyHandoffs:
    def _segments(self, n):
        from engine.daily_edition import Segment

        names = ["SpaceX Daily", "Tesla Shorts Time", "Models & Agents",
                 "Planetterrian Daily", "Omni View", "Fascinating Frontiers"]
        segs = []
        for i in range(n):
            seg = Segment.__new__(Segment)
            seg.show_name = names[i % len(names)]
            segs.append(seg)
        return segs

    def test_a_compliant_draft_is_left_alone(self):
        from engine.daily_edition import adopt_revised_handoffs, handoff_revision_prompt

        segs = self._segments(4)
        links = {"handoffs": ["A stake, then Tesla Shorts Time.", "A question on Models & Agents.",
                              "Planetterrian Daily looks at herbs."]}
        assert handoff_revision_prompt("P", links, segs) is None
        out = adopt_revised_handoffs(links, None, segs)
        assert out["_name_led_first_draft"] == 1 and out["_handoffs_revised"] is False

    def test_a_name_led_draft_is_sent_back_and_the_better_one_kept(self):
        from engine.daily_edition import adopt_revised_handoffs, handoff_revision_prompt

        segs = self._segments(4)
        draft = {"intro": "i", "signoff": "s", "title": "t",
                 "handoffs": ["Tesla Shorts Time follows.", "Models & Agents turns to.",
                              "Planetterrian Daily looks at."]}
        prompt = handoff_revision_prompt("BASE", draft, segs)
        assert prompt and prompt.startswith("BASE") and "3 of 3" in prompt and "at most 1" in prompt
        better = dict(draft, handoffs=["Solar Roof ends — Tesla Shorts Time.",
                                       "A desktop app, on Models & Agents.",
                                       "Planetterrian Daily looks at."])
        out = adopt_revised_handoffs(draft, better, segs)
        assert out["handoffs"] == better["handoffs"] and out["_handoffs_revised"]
        assert out["intro"] == "i" and out["_name_led_first_draft"] == 3

    def test_a_worse_or_misshapen_revision_is_refused(self):
        from engine.daily_edition import adopt_revised_handoffs

        segs = self._segments(3)
        draft = {"handoffs": ["Tesla Shorts Time follows.", "Models & Agents turns."]}
        assert adopt_revised_handoffs(draft, {"handoffs": ["only one"]}, segs)["handoffs"] == draft["handoffs"]
        assert adopt_revised_handoffs(draft, dict(draft), segs)["_handoffs_revised"] is False

    def test_metrics_record_the_first_draft(self):
        import datetime as dt

        from engine.daily_edition import build_edition_metrics

        m = build_edition_metrics(45, dt.date(2026, 10, 4), 60.0, [], links_source="llm",
                                  field_note_included=True, missing_expected=[], dropped=[],
                                  links={"handoffs": [], "_name_led_first_draft": 18,
                                         "_handoffs_revised": True})
        assert m["handoffs_show_name_led_first_draft"] == 18 and m["handoffs_revised"] is True


class TestScriptStageIsTimed:
    """The model-trial report gates ``generate_podcast_script`` but nothing
    recorded it, so a script-stage pin could never be latency-gated."""

    def test_record_stage_lands_in_stages_and_wall(self):
        from engine.metrics import PipelineMetrics

        m = PipelineMetrics(show_slug="omni_view", episode_num=1)
        m.record_stage("generate_podcast_script", 61.234)
        d = m.to_dict()
        assert {"name": "generate_podcast_script", "duration_s": 61.23} .items() <= next(
            s for s in d["stages"] if s["name"] == "generate_podcast_script").items()
        assert m.wall_duration() == 61.23

    def test_the_two_pass_call_is_timed_and_the_combined_path_is_not(self):
        src = (ROOT / "engine/pipeline.py").read_text()
        block = src[src.index("_script_stage_s = None"):src.index('template_vars["_script_stage_s"]')]
        assert "generate_podcast_script(" in block and "time.monotonic()" in block
        run = (ROOT / "run_show.py").read_text()
        assert 'metrics.record_stage("generate_podcast_script", _script_stage_s)' in run

    def test_the_report_gates_the_stage_it_now_receives(self):
        from scripts import model_trial_report as mtr

        assert mtr._is_llm_stage("generate_podcast_script")
