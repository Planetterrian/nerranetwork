"""Guards for the Sep 2026 new-shows Phase 0 enablers.

Plan: docs/new_shows_plan_2026_09_22.md §2. Each class pins one enabler
that more than one of the fourteen new shows depends on.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine.hook_articles import (
    HOOK_ARTICLES_KEY,
    SOURCE_KIND_HOOK,
    merge_hook_articles,
    normalize_hook_articles,
    pop_hook_articles,
)

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# §2a — hook-supplied articles
# ---------------------------------------------------------------------------

class TestHookArticles:
    def test_pop_removes_list_from_template_context(self):
        ctx = {"tone_hint": "x", HOOK_ARTICLES_KEY: [
            {"title": "PR 1 merged", "url": "https://github.com/o/r/pull/1"},
        ]}
        arts = pop_hook_articles(ctx, slug="t")
        assert HOOK_ARTICLES_KEY not in ctx, "a list must never reach prompt vars"
        assert ctx == {"tone_hint": "x"}
        assert arts[0]["source_kind"] == SOURCE_KIND_HOOK

    def test_malformed_entries_are_dropped_not_raised(self):
        arts = normalize_hook_articles([
            {"title": "ok", "url": "https://a.example/1"},
            {"title": "", "url": "https://a.example/2"},
            {"url": "https://a.example/3"},
            "not a dict",
            {"title": "dup url", "url": "https://a.example/1"},
        ])
        assert [a["url"] for a in arts] == ["https://a.example/1"]

    def test_non_list_payload_ignored(self):
        assert normalize_hook_articles({"title": "x"}) == []
        assert pop_hook_articles(None) == []

    def test_link_alias_and_fields_carried(self):
        (a,) = normalize_hook_articles([{
            "title": "Road closure", "link": "https://drivebc.example/e/1",
            "description": "Lane closed", "content_text": "Full body",
            "published_date": "2026-09-22T10:00:00Z", "exempt_stale": True,
        }])
        assert a["url"] == "https://drivebc.example/e/1"
        assert a["content_text"] == "Full body"
        assert a["exempt_stale"] is True

    def test_merge_dedups_against_fetched_titles_and_urls(self):
        fetched = [{"title": "Nvidia unveils Rubin GPU at GTC", "url": "https://x/1"}]
        hook = normalize_hook_articles([
            {"title": "Nvidia unveils Rubin GPU at GTC event", "url": "https://y/2"},
            {"title": "Same url different words", "url": "https://x/1"},
            {"title": "TSMC breaks ground on Arizona fab three", "url": "https://z/3"},
        ])
        merged, added = merge_hook_articles(fetched, hook)
        assert added == 1
        assert merged[-1]["url"] == "https://z/3"

    def test_hook_article_reaches_claims_local_texts(self):
        from engine.claims import build_local_texts

        (a,) = normalize_hook_articles([{
            "title": "Scaffold repairs merged",
            "url": "https://github.com/Planetterrian/nerranetwork/pull/9",
            "content_text": "The weekly prompt template no longer carries stray braces.",
        }])
        texts = build_local_texts([a])
        assert any("stray braces" in t for t in texts.values())

    def test_stale_gate_honours_exemption(self):
        from engine.article_text import drop_stale_articles

        old = {"title": "PR from last week", "url": "u",
               "published_date": "2020-01-01T00:00:00Z", "exempt_stale": True}
        kept, dropped = drop_stale_articles([old], max_age_days=3)
        assert kept == [old] and dropped == []

    def test_run_show_merges_before_gates(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        merge_at = src.index("merge_hook_articles(articles, _hook_articles)")
        skip_at = src.index('_skip_episode("no_articles"')
        news_at = src.index("news_section = \"\\n\\n\".join(news_lines)")
        assert merge_at < skip_at < news_at
        assert 'metrics.record("articles_from_hook"' in src


class TestMinArticlesSkipZero:
    def test_explicit_zero_is_not_coerced(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'getattr(config, "min_articles_skip", 3) or 3' not in src
        assert "skip_threshold = 3 if _mas is None else int(_mas)" in src


# ---------------------------------------------------------------------------
# §2b — an AI host on a run_show show
# ---------------------------------------------------------------------------

class _Cfg:
    """Minimal stand-in for ShowConfig in disclosure selection."""

    def __init__(self, host_kind="human", host_name="Patrick", dialogue=False):
        from types import SimpleNamespace
        self.publishing = SimpleNamespace(host_kind=host_kind, host_name=host_name)
        self.tts = SimpleNamespace(dialogue_mode=dialogue)


class TestAiHostDisclosure:
    def test_human_show_unchanged(self):
        from run_show import _AI_DISCLOSURE, _AI_DISCLOSURE_RSS, _rss_disclosure_for, _spoken_disclosure
        assert _spoken_disclosure(_Cfg(), "tesla") == _AI_DISCLOSURE
        assert _rss_disclosure_for(_Cfg(), "tesla") == _AI_DISCLOSURE_RSS

    def test_dialogue_and_russian_unchanged(self):
        from run_show import _AI_DISCLOSURE_DIALOGUE, _AI_DISCLOSURE_RU, _spoken_disclosure
        assert _spoken_disclosure(_Cfg(dialogue=True), "dp_pod") == _AI_DISCLOSURE_DIALOGUE
        assert _spoken_disclosure(_Cfg(), "finansy_prosto") == _AI_DISCLOSURE_RU

    def test_ai_host_never_claims_a_human_voice_or_editor(self):
        from run_show import _rss_disclosure_for, _spoken_disclosure
        spoken = _spoken_disclosure(_Cfg("ai", "Mira"), "vancouver")
        rss = _rss_disclosure_for(_Cfg("ai", "Mira"), "vancouver")
        for text in (spoken, rss):
            assert "Mira" in text and "AI" in text
            assert "my voice" not in text and "my own" not in text
            assert "Patrick" not in text
            # The human-review claim belongs only to the interview shows.
            assert "review" not in text.lower()
        assert "synthesis" in spoken and len(spoken) < 200
        assert "AI Disclosure" in rss

    def test_host_kind_is_a_config_field(self):
        from engine.config import PublishingConfig
        assert PublishingConfig().host_kind == "human"

    def test_label_stripper_is_case_insensitive_for_host(self):
        from run_show import _clean_podcast_script
        out = _clean_podcast_script(
            "MIRA: Good morning, Vancouver.\n\nMira: Second line.",
            host_name="Mira",
        )
        assert "MIRA:" not in out and "Mira:" not in out
        assert "Good morning, Vancouver." in out

    def test_newsletter_credit_follows_host(self):
        from engine.newsletter_template import _editorial_credit
        assert _editorial_credit({"host_name": "Patrick", "host_kind": "human"}) == "Editorial by Patrick"
        ai = _editorial_credit({"host_name": "Mira", "host_kind": "ai"})
        assert "Mira" in ai and "AI" in ai and "Patrick" not in ai

    def test_mira_badge_reads_host_not_only_strand(self):
        macros = (ROOT / "templates" / "_macros.html.j2").read_text(encoding="utf-8")
        assert "s.host == 'mira'" in macros


# ---------------------------------------------------------------------------
# §2c — named-weekday cadence
# ---------------------------------------------------------------------------

_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday",
         "saturday", "sunday")


class TestNamedWeekdayCadence:
    def test_review_episodes_knows_every_weekday(self):
        import datetime

        import review_episodes as re_mod
        monday = datetime.date(2026, 9, 21)
        for offset, name in enumerate(_DAYS):
            day = monday + datetime.timedelta(days=offset)
            assert re_mod._should_run_on(name, day)
            assert not re_mod._should_run_on(name, day + datetime.timedelta(days=1))

    def test_gate_and_worker_know_every_weekday(self):
        wf = (ROOT / ".github/workflows/run-show.yml").read_text(encoding="utf-8")
        ts = (ROOT / "workers/scheduler/src/index.ts").read_text(encoding="utf-8")
        for name in _DAYS:
            assert f'"{name}":' in wf, f"gate WEEKDAY_FILTERS lacks {name}"
            assert f'case "{name}":' in ts, f"scheduler Worker lacks {name}"

    def test_worker_weekday_numbers_are_utc_getday(self):
        ts = (ROOT / "workers/scheduler/src/index.ts").read_text(encoding="utf-8")
        assert re.search(r'case "sunday":\s*return weekday === 0;', ts)
        assert re.search(r'case "saturday":\s*return weekday === 6;', ts)

    def test_dashboard_derives_weekly_thresholds(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import generate_dashboard as g
        weekly = g._weekly_slugs_from_cron_map()
        assert "dp_pod" in weekly, "dp_pod is weekly since 2026-09-21"
        assert g._pub_age_thresholds("dp_pod", weekly) == g._PUB_AGE_WEEKLY_H
        assert g._pub_age_thresholds("tesla", weekly) == g._PUB_AGE_DEFAULT_H


# ---------------------------------------------------------------------------
# §2d — scaffold repairs (the tool shipped four CI failures per new show)
# ---------------------------------------------------------------------------

class TestScaffoldRepairs:
    @pytest.fixture()
    def scaffolded(self, tmp_path):
        import shutil

        from engine.show_scaffold import ScaffoldSpec, scaffold_show
        (tmp_path / "shows").mkdir()
        shutil.copy(ROOT / "shows" / "network_meta.yaml", tmp_path / "shows" / "network_meta.yaml")
        spec = ScaffoldSpec(
            show_name="Probe Weekly", slug="probe_weekly",
            description="A probe show.", audience="testers",
            host_name="Mira", host_kind="ai", host_key="mira", voice_id="ara",
            strand="local", cron="7 10 * * 5", cron_day_filter="friday",
            cadence="weekly", display_order=3.8,
        )
        log = scaffold_show(tmp_path, spec)
        return tmp_path, "\n".join(log)

    def test_weekly_prompt_formats_with_synth_kwargs(self, scaffolded):
        root, _ = scaffolded
        text = (root / "shows/prompts/probe_weekly_weekly.txt").read_text(encoding="utf-8")
        text.format(show_name="S", episode_count=1, start_date="a", end_date="b",
                    episodes_text="e", entities="x")

    def test_slow_news_not_enabled_without_library(self, scaffolded):
        import yaml
        root, _ = scaffolded
        data = yaml.safe_load((root / "shows/probe_weekly.yaml").read_text(encoding="utf-8"))
        sn = data.get("slow_news") or {}
        assert not sn.get("enabled") or sn.get("library_file")

    def test_registry_append_keeps_comments_and_order(self, scaffolded):
        root, _ = scaffolded
        before = (ROOT / "shows/network_meta.yaml").read_text(encoding="utf-8")
        after = (root / "shows/network_meta.yaml").read_text(encoding="utf-8")
        assert after.startswith(before), "existing registry text must be untouched"
        import yaml
        entry = yaml.safe_load(after)["probe_weekly"]
        assert entry["host"] == "mira" and entry["strand"] == "local"
        assert "AI host" in entry["about_host"]

    def test_ai_host_fields_and_voice_in_yaml(self, scaffolded):
        import yaml
        root, _ = scaffolded
        data = yaml.safe_load((root / "shows/probe_weekly.yaml").read_text(encoding="utf-8"))
        assert data["tts"]["voice_id"] == "ara"
        assert data["publishing"]["host_kind"] == "ai"
        assert data["publishing"]["host_name"] == "Mira"
        assert data["publishing"]["rss_author"] == "Nerra Network"

    def test_patch_prints_weekly_audit_limit_and_real_tag(self, scaffolded):
        _, log = scaffolded
        assert '"probe_weekly_podcast.rss": ("Probe Weekly", 240)' in log
        assert "Probe Weekly" in log.split("Buttondown tag")[1].splitlines()[1]
        assert "SIX places" in log

    def test_duplicate_registry_entry_refused(self, tmp_path):
        import shutil

        from engine.show_scaffold import build_network_meta_entry, merge_network_meta, ScaffoldSpec
        (tmp_path / "shows").mkdir()
        shutil.copy(ROOT / "shows" / "network_meta.yaml", tmp_path / "shows" / "network_meta.yaml")
        spec = ScaffoldSpec(show_name="SpaceX", slug="spacex", description="d", audience="a")
        with pytest.raises(FileExistsError):
            merge_network_meta(tmp_path, build_network_meta_entry(spec), dry_run=False)
