"""Drift guards for per-episode deep-dive episodes (May 2026).

Modern Investing Techniques (and any future show) can produce an occasional
standalone single-subject deep-dive episode without permanently switching to
``narrative_mode``. Covered here:

  - ``engine.topic_queue.pick_deep_dive_topic`` selection priority:
    forced id > scheduled date == today > ``when: next`` > nothing.
  - ``DeepDiveConfig`` loads from a show YAML.
  - The shipped MIT deep-dive queue + prompts are wired correctly so the
    SpaceX IPO episode fires on the next run.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def _write_queue(path: Path, entries: list) -> None:
    path.write_text(yaml.safe_dump({"queue": entries}, sort_keys=False))


# ---------------------------------------------------------------------------
# pick_deep_dive_topic — selection priority
# ---------------------------------------------------------------------------

class TestPickDeepDiveTopic:

    def test_fires_on_when_next(self, tmp_path: Path):
        from engine.topic_queue import pick_deep_dive_topic
        q = tmp_path / "q.yaml"
        _write_queue(q, [
            {"id": "a", "title": "A", "brief": "b", "when": "next",
             "produced": False},
        ])
        # Any date — "next" is date-agnostic.
        t = pick_deep_dive_topic(q, "2026-05-31")
        assert t and t["id"] == "a"

    def test_fires_on_scheduled_date(self, tmp_path: Path):
        from engine.topic_queue import pick_deep_dive_topic
        q = tmp_path / "q.yaml"
        _write_queue(q, [
            {"id": "a", "title": "A", "brief": "b", "date": "2026-06-15",
             "produced": False},
        ])
        assert pick_deep_dive_topic(q, "2026-06-15")["id"] == "a"
        # Wrong day → no deep dive (normal news episode).
        assert pick_deep_dive_topic(q, "2026-06-14") is None

    def test_no_fire_without_schedule_or_next(self, tmp_path: Path):
        """A plain unproduced entry with neither date nor when must NOT
        hijack a news show — otherwise every run would be a deep dive."""
        from engine.topic_queue import pick_deep_dive_topic
        q = tmp_path / "q.yaml"
        _write_queue(q, [
            {"id": "a", "title": "A", "brief": "b", "produced": False},
        ])
        assert pick_deep_dive_topic(q, "2026-05-31") is None
        # ...but it can still be forced explicitly.
        assert pick_deep_dive_topic(q, "2026-05-31", force_id="a")["id"] == "a"

    def test_date_today_wins_over_when_next(self, tmp_path: Path):
        from engine.topic_queue import pick_deep_dive_topic
        q = tmp_path / "q.yaml"
        _write_queue(q, [
            {"id": "later", "title": "L", "brief": "b", "when": "next",
             "produced": False},
            {"id": "today", "title": "T", "brief": "b", "date": "2026-05-31",
             "produced": False},
        ])
        assert pick_deep_dive_topic(q, "2026-05-31")["id"] == "today"

    def test_forced_id_overrides_schedule(self, tmp_path: Path):
        from engine.topic_queue import pick_deep_dive_topic
        q = tmp_path / "q.yaml"
        _write_queue(q, [
            {"id": "sched", "title": "S", "brief": "b", "date": "2026-05-31",
             "produced": False},
            {"id": "forced", "title": "F", "brief": "b", "produced": False},
        ])
        assert pick_deep_dive_topic(
            q, "2026-05-31", force_id="forced")["id"] == "forced"

    def test_forced_unknown_or_produced_returns_none(self, tmp_path: Path):
        from engine.topic_queue import pick_deep_dive_topic
        q = tmp_path / "q.yaml"
        _write_queue(q, [
            {"id": "done", "title": "D", "brief": "b", "when": "next",
             "produced": True},
        ])
        assert pick_deep_dive_topic(q, "2026-05-31", force_id="missing") is None
        # Already-produced entries are never re-selected (even forced).
        assert pick_deep_dive_topic(q, "2026-05-31", force_id="done") is None
        assert pick_deep_dive_topic(q, "2026-05-31") is None

    def test_skips_produced_entries(self, tmp_path: Path):
        from engine.topic_queue import pick_deep_dive_topic
        q = tmp_path / "q.yaml"
        _write_queue(q, [
            {"id": "old", "title": "O", "brief": "b", "when": "next",
             "produced": True},
            {"id": "new", "title": "N", "brief": "b", "when": "next",
             "produced": False},
        ])
        assert pick_deep_dive_topic(q, "2026-05-31")["id"] == "new"


# ---------------------------------------------------------------------------
# DeepDiveConfig loading
# ---------------------------------------------------------------------------

class TestDeepDiveConfig:

    def test_defaults_disabled(self):
        from engine.config import DeepDiveConfig
        dd = DeepDiveConfig()
        assert dd.enabled is False
        assert dd.queue_file == ""

    def test_mit_yaml_wires_deep_dive(self):
        from engine.config import load_config
        c = load_config("shows/modern_investing.yaml")
        assert c.deep_dive.enabled is True
        assert c.deep_dive.queue_file == "shows/deep_dives/modern_investing.yaml"
        assert c.deep_dive.digest_prompt_file.endswith("modern_investing_deep_dive.txt")
        assert c.deep_dive.podcast_prompt_file.endswith(
            "modern_investing_deep_dive_podcast.txt"
        )
        # Deep dives push a fuller word target than the daily show (Ep059 was
        # only 1252 words) so the length gate drives a real deep dive.
        assert c.deep_dive.min_podcast_words >= 2000
        assert c.deep_dive.min_podcast_words > c.llm.min_podcast_words

    def test_deep_dive_min_words_defaults_to_inherit(self):
        from engine.config import DeepDiveConfig
        assert DeepDiveConfig().min_podcast_words == 0

    def test_news_shows_default_to_no_deep_dive(self):
        """A show without a deep_dive: block must stay news-driven."""
        from engine.config import load_config
        c = load_config("shows/omni_view.yaml")
        assert c.deep_dive.enabled is False


# ---------------------------------------------------------------------------
# Shipped MIT deep-dive assets
# ---------------------------------------------------------------------------

class TestShippedMITDeepDive:

    def test_current_spacex_entry_is_next_and_research_grounded(self):
        data = yaml.safe_load(
            Path("shows/deep_dives/modern_investing.yaml").read_text()
        )
        # The original spacex-ipo entry is retired (produced) so it can't
        # re-fire; the replacement is the live one.
        old = next(e for e in data["queue"] if e["id"] == "spacex-ipo")
        assert old["produced"] is True
        assert "when" not in old  # must not re-fire

        entry = next(e for e in data["queue"] if e["id"] == "spacex-ipo-current")
        assert entry["when"] == "next"
        assert entry["produced"] is False
        # Time-sensitive topic MUST carry live-research queries (the whole
        # point of the v2 episode — Ep059 was stale without them).
        assert entry["web_search_queries"], "SpaceX deep dive needs live research queries"
        brief = entry["brief"].lower()
        assert "spacex" in brief and "ipo" in brief
        assert "current_research" in brief  # brief tells the host to ground in live research
        # Must structure the investment perspective by holding horizon.
        assert "short-term" in brief and "medium-term" in brief and "long-term" in brief
        # And set the current market backdrop, not just the company.
        assert "market backdrop" in brief or "ipo environment" in brief

    def test_deep_dive_prompts_exist_and_reference_topic(self):
        digest = Path("shows/prompts/modern_investing_deep_dive.txt").read_text()
        podcast = Path(
            "shows/prompts/modern_investing_deep_dive_podcast.txt"
        ).read_text()
        # Brief prompt must consume the queue topic, the live research, + emit a HOOK.
        assert "{topic_title}" in digest and "{topic_brief}" in digest
        assert "{current_research}" in digest
        assert "**HOOK:**" in digest
        # Podcast prompt must consume the brief + the extracted hook.
        assert "{digest}" in podcast and "{hook}" in podcast

    def test_deep_dive_prompts_render(self):
        from engine.generator import load_prompt
        v = {
            "today_str": "May 31, 2026", "topic_title": "T",
            "topic_brief": "B", "topic_category": "special",
            "current_research": "- per Reuters (date): ...",
            "episode_num": 7, "hook": "H", "digest": "D",
        }
        load_prompt("shows/prompts/modern_investing_deep_dive.txt", v)
        load_prompt("shows/prompts/modern_investing_deep_dive_podcast.txt", v)


# ---------------------------------------------------------------------------
# Deep-dive vs Sunday weekly-recap precedence
# ---------------------------------------------------------------------------

class TestDeepDiveVsWeeklyRecap:
    """A deep dive scheduled onto a Sunday must win over the automatic Sunday
    weekly recap — otherwise the run builds a recap digest but uses the
    deep-dive podcast prompt (a broken hybrid) AND marks the deep-dive topic
    produced, burning the slot. The monthly MIT episode is a separate entry
    point and is intentionally not involved."""

    import datetime as _dt

    SUNDAY = _dt.date(2026, 5, 31)   # the next MIT run after the SpaceX merge
    WEEKDAY = _dt.date(2026, 5, 29)  # a Friday

    def test_recap_fires_on_sunday_normally(self):
        from run_show import _resolve_weekly_recap
        assert _resolve_weekly_recap(True, self.SUNDAY, is_deep_dive=False) is True

    def test_deep_dive_suppresses_sunday_recap(self):
        from run_show import _resolve_weekly_recap
        assert _resolve_weekly_recap(True, self.SUNDAY, is_deep_dive=True) is False

    def test_no_recap_on_weekday(self):
        from run_show import _resolve_weekly_recap
        assert _resolve_weekly_recap(True, self.WEEKDAY, is_deep_dive=False) is False

    def test_opt_out_show_never_recaps(self):
        from run_show import _resolve_weekly_recap
        assert _resolve_weekly_recap(False, self.SUNDAY, is_deep_dive=False) is False
