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


# ---------------------------------------------------------------------------
# Phase 1 — the four Patrick shows (plan §4.1-4.4)
# ---------------------------------------------------------------------------

PHASE1 = ("ai_chips", "mag7", "peptides", "longevity")
WEEKLY = {"peptides": "thursday", "longevity": "wednesday"}


def _cfg(slug):
    from engine.config import load_config
    return load_config(ROOT / "shows" / f"{slug}.yaml")


@pytest.mark.parametrize("slug", PHASE1)
class TestPhase1ShowWiring:
    def test_config_loads_with_host_and_breaker(self, slug):
        c = _cfg(slug)
        assert c.publishing.host_kind == "human" and c.publishing.host_name == "Patrick"
        assert c.max_weekly_cost_usd > 0, "breaker must be TOP-level to take effect"
        assert c.youtube.enabled is False and c.newsletter.enabled is False
        assert c.publishing.x_enabled is False

    def test_prompts_exist_and_share_content_discipline(self, slug):
        for kind in ("system", "digest", "podcast", "weekly"):
            assert (ROOT / f"shows/prompts/{slug}_{kind}.txt").read_text(encoding="utf-8").strip()
        pod = (ROOT / f"shows/prompts/{slug}_podcast.txt").read_text(encoding="utf-8")
        assert "<<include: _shared/content_discipline.txt>>" in pod
        dig = (ROOT / f"shows/prompts/{slug}_digest.txt").read_text(encoding="utf-8")
        assert "{hook_context}" in dig

    def test_no_title_placeholder_that_reads_as_content(self, slug):
        # The SpaceX Ep70 lesson: a literal **Title: Source Name** template
        # is reproduced verbatim by the model.
        dig = (ROOT / f"shows/prompts/{slug}_digest.txt").read_text(encoding="utf-8")
        assert "**Title:" not in dig and "Source Name**" not in dig

    def test_digest_forbids_absence_sentences(self, slug):
        # AI Chips dry run 2026-09-22 shipped "No power or core-count figures
        # were released with the samples." — a filler shape the network's
        # content discipline already bans in scripts.
        dig = (ROOT / f"shows/prompts/{slug}_digest.txt").read_text(encoding="utf-8")
        assert "NO ABSENCE SENTENCES" in dig

    def test_registries(self, slug):
        from engine.content_tracker import SHOW_SECTION_PATTERNS
        from engine.first_episode import _SHOW_DIGEST_EP1, _SHOW_PODCAST_EP1
        from engine.intros import _SHOW_PERSONALITIES
        from engine.show_memory import SHOW_MEMORY_CONFIGS
        from engine.validation import SHOW_VALIDATION_CONFIGS
        for reg in (SHOW_SECTION_PATTERNS, SHOW_VALIDATION_CONFIGS, SHOW_MEMORY_CONFIGS,
                    _SHOW_PERSONALITIES, _SHOW_DIGEST_EP1, _SHOW_PODCAST_EP1):
            assert slug in reg

    def test_chapter_anchors_match_identity_and_closing(self, slug):
        from engine.intros import build_closing_block, build_intro_line
        markers = {m.title: m for m in _cfg(slug).chapters.section_markers}
        intro = build_intro_line(slug, episode_num=1, today_str="x")
        closing = build_closing_block(slug, episode_num=1, today_str="x")
        assert re.search(markers["Introduction"].pattern, intro, re.I)
        assert re.search(markers["Closing"].pattern, closing, re.I)

    def test_no_topic_word_chapter_markers(self, slug):
        # Sep 4 2026: M&A's "open.source" marker fired on news content.
        bare = {"silicon", "gpu", "nvidia", "tesla", "apple", "peptide", "aging"}
        for m in _cfg(slug).chapters.section_markers:
            assert m.pattern.lower() not in bare, m.pattern

    def test_registry_page_and_cover(self, slug):
        import generate_html as G
        entry = G.NETWORK_SHOWS[slug]
        assert entry["host"] == "patrick" and entry["strand"] in {"ai", "markets", "health"}
        assert (ROOT / entry["podcast_image"]).exists()
        for px in ("400", "800"):
            assert (ROOT / entry["podcast_image"].replace(".jpg", f"-{px}.webp")).exists()
        assert (ROOT / entry["show_page"]).exists(), "rss_link must resolve"
        if slug in WEEKLY:
            assert "week" in entry["schedule"].lower()
            assert "daily" not in _cfg(slug).publishing.rss_description.lower()


class TestPrelaunchShows:
    def _cron_map_slugs(self):
        wf = (ROOT / ".github/workflows/run-show.yml").read_text(encoding="utf-8")
        return set(re.findall(r'"\S+ \S+ \S+ \S+ \S+":\s*\("(\w+)"', wf))

    def test_prelaunch_shows_are_not_scheduled_or_audited(self):
        import review_episodes as R
        scheduled = self._cron_map_slugs()
        for slug in R.PRELAUNCH_SLUGS:
            assert slug not in scheduled, (
                f"{slug} is on a cron but still pre-launch — move it into "
                "SHOW_REGISTRY in the same PR that schedules it")
            assert slug not in R.SHOW_REGISTRY

    def test_scheduled_shows_are_never_prelaunch(self):
        import review_episodes as R
        assert not (R.PRELAUNCH_SLUGS & self._cron_map_slugs())

    def test_prelaunch_shows_are_dispatchable_but_not_in_all(self):
        import review_episodes as R
        wf = (ROOT / ".github/workflows/run-show.yml").read_text(encoding="utf-8")
        opts = wf[wf.index("options:"):wf.index("test_mode:")]
        all_line = next(line for line in wf.splitlines()
                        if line.strip().startswith('shows = ["tesla"'))
        for slug in R.PRELAUNCH_SLUGS:
            assert f"- {slug}\n" in opts
            assert slug not in all_line

    def test_prelaunch_shows_join_no_topic_hub(self):
        from engine.topic_hubs import TOPIC_HUBS, hub_shows
        shows = [{"slug": "ai_chips", "has_feed": False, "picker_tags": {"topics": ["ai"]}}]
        for hub in TOPIC_HUBS:
            assert hub_shows(hub, shows) == []


class TestMarketTape:
    def _quotes(self, tmp_path, fetch):
        from engine.market_quotes import fetch_daily_closes
        return fetch_daily_closes(("AAPL", "MSFT", "NVDA"), cache_path=tmp_path / "q.json",
                                  fetch=fetch)

    def test_every_line_is_a_close_with_its_session_date(self, tmp_path):
        from engine.market_quotes import tape_block
        qs = self._quotes(tmp_path, lambda t: (100.0, 99.0, "2026-09-18"))
        block = tape_block(qs, {"AAPL": "Apple"}, ("AAPL", "MSFT", "NVDA"))
        assert "trading at" not in block
        assert block.count("closed at") == 3 and "2026-09-18" in block

    def test_failed_ticker_is_named_missing_not_guessed(self, tmp_path):
        from engine.market_quotes import tape_block

        def fetch(t):
            if t == "MSFT":
                raise RuntimeError("down")
            return (100.0, 100.0, "2026-09-18")
        qs = self._quotes(tmp_path, fetch)
        block = tape_block(qs, {}, ("AAPL", "MSFT", "NVDA"))
        assert "No validated close today for: MSFT" in block
        assert "(unchanged)" in block, "a zero move is unchanged, never up/down zero"

    def test_deviation_guard_rejects_a_garbled_close(self, tmp_path):
        import json

        from engine.market_quotes import fetch_daily_closes
        cache = tmp_path / "q.json"
        cache.write_text(json.dumps({"quotes": [{"ticker": "AAPL", "close": 200.0}]}))
        qs = fetch_daily_closes(("AAPL",), cache_path=cache, fetch=lambda t: (20.0, 19.0, "d"))
        assert qs == []

    def test_no_prices_means_no_prices(self):
        from engine.market_quotes import tape_block
        block = tape_block([], {}, ("AAPL",))
        assert "no price may appear" in block

    def test_empty_run_never_overwrites_cache(self, tmp_path):
        from engine.market_quotes import persist
        cache = tmp_path / "q.json"
        cache.write_text("keep")
        persist([], cache)
        assert cache.read_text() == "keep"


class TestSiblingCoverage:
    def test_headlines_from_recent_sibling_digests_only(self, tmp_path):
        import datetime as dt

        from engine.sibling_coverage import sibling_block
        d = tmp_path / "digests" / "sib"
        d.mkdir(parents=True)
        (d / "Sib_Ep010_20260922.md").write_text(
            "# Sib\n**HOOK:** x\n### Top Story\n**Nvidia ships a new rack system: The Verge**\n"
            "### Model Updates\n**Delegation vs. Judgment: how agents decide: Outlet**\n")
        (d / "Sib_Ep001_20260101.md").write_text("**Ancient headline far away: Old**\n")
        block = sibling_block("Sib", "digests/sib", days=1, lens="Add only new facts.",
                              today=dt.date(2026, 9, 22), root=tmp_path)
        assert "Nvidia ships a new rack system" in block
        assert "Delegation vs. Judgment: how agents decide" in block, "outlet is the LAST part"
        assert "Ancient" not in block and "Top Story" not in block.split("\n", 2)[2]
        assert "do not include in output" in block

    def test_missing_dir_is_empty(self, tmp_path):
        from engine.sibling_coverage import sibling_block
        assert sibling_block("X", "nope", days=1, lens="", root=tmp_path) == ""


class TestHealthWeeklies:
    def test_curricula_are_complete_and_start_from_ground_truth(self):
        import yaml
        firsts = {"peptides": "insulin", "longevity": "hallmarks"}
        for slug, first in firsts.items():
            q = yaml.safe_load((ROOT / f"shows/curricula/{slug}.yaml").read_text())["queue"]
            assert len(q) >= 24, "six months of weekly spotlights"
            assert first in q[0]["id"]
            for e in q:
                assert e["id"] and e["title"] and e["brief"] and e["search"]
                assert "never dosing" in e["brief"].lower() or "never medical" in e["brief"].lower() \
                    or "never dosing, sourcing" in e["brief"].lower()

    def test_curricula_live_outside_the_narrative_queues(self):
        assert not (ROOT / "shows/topic_queues/peptides.yaml").exists()
        wf = (ROOT / ".github/workflows/run-show.yml").read_text(encoding="utf-8")
        assert "git add -A shows/curricula/" in wf

    def test_closing_carries_the_posture_verbatim(self):
        from engine.intros import build_closing_block
        for slug in ("peptides", "longevity"):
            assert "not medical advice" in build_closing_block(slug, episode_num=2, today_str="x")
        assert "financial advice" in build_closing_block("mag7", episode_num=2, today_str="x")

    def test_newsletter_health_callout_is_configured_and_renders(self):
        from engine.newsletter_template import _build_health_disclaimer_html, _load_show_branding
        assert _load_show_branding("peptides")["requires_health_disclaimer"] == "true"
        assert _load_show_branding("tesla")["requires_health_disclaimer"] == "false"
        assert "not medical advice" in _build_health_disclaimer_html()

    def test_europe_pmc_abstracts_become_citable_hook_articles(self):
        from engine.europe_pmc import abstracts_for
        rec = {"source": "MED", "pmid": "123", "title": "A trial of X.",
               "abstractText": "<p>" + "Randomized trial result. " * 20 + "</p>",
               "pubYear": "2024", "firstPublicationDate": "2024-01-02",
               "journalInfo": {"journal": {"title": "Journal of Things"}}}
        arts = abstracts_for("X", get=lambda params: {"resultList": {"result": [rec]}})
        assert len(arts) == 1, "the two slices de-duplicate"
        a = arts[0]
        assert a["url"] == "https://europepmc.org/article/MED/123"
        assert a["exempt_stale"] is True and "<p>" not in a["content_text"]
        from engine.claims import build_local_texts
        from engine.hook_articles import normalize_hook_articles
        assert build_local_texts(normalize_hook_articles(arts))

    def test_europe_pmc_failure_is_empty_not_raised(self):
        from engine.europe_pmc import abstracts_for

        def boom(params):
            raise OSError("offline")
        assert abstracts_for("X", get=boom) == []

    def test_spotlight_block_names_subject_or_falls_back(self):
        from engine.curriculum import spotlight_block
        assert "Subject: Insulin" in spotlight_block({"title": "Insulin", "brief": "b"}, "Peptide Spotlight")
        assert "curriculum is empty" in spotlight_block(None, "Peptide Spotlight")


class TestTitleFiltersKeepRealNews:
    """A drop-any title filter with a common word in it silently removes the
    show's own news (the first draft dropped every "deal" — power, supply and
    acquisition deals — and every FDA "order")."""

    KEEP = {
        "ai_chips": ["Nvidia signs $10B supply deal with Microsoft",
                     "Utility strikes power deal for 1 GW data center",
                     "TSMC sale of stake in Arizona fab approved"],
        "mag7": ["Apple agrees $2B deal to buy AI startup",
                 "Amazon wins antitrust order appeal",
                 "Meta sale of VR unit under review"],
        "peptides": ["FDA order restricts compounded semaglutide",
                     "Trial protocol amended for retatrutide phase 3"],
        "longevity": ["Executive order on aging research funding",
                      "TAME trial protocol published"],
    }

    @pytest.mark.parametrize("slug", PHASE1)
    def test_real_headlines_survive(self, slug):
        from engine.utils import drop_excluded_titles
        arts = [{"title": t} for t in self.KEEP[slug]]
        kept, dropped = drop_excluded_titles(arts, _cfg(slug).exclude_title_patterns)
        assert dropped == 0, [a["title"] for a in arts if a not in kept]


class TestTestModeNeverPublishes:
    def test_commit_and_publish_steps_skip_test_mode(self):
        wf = (ROOT / ".github/workflows/run-show.yml").read_text(encoding="utf-8")
        for step in ("Validate output", "Regenerate network RSS",
                     "Regenerate show HTML pages", "Commit and push output"):
            block = wf[wf.index(f"- name: {step}"):]
            block = block[:block.index("run:")]
            assert "github.event.inputs.test_mode != 'true'" in block, step

    def test_readonly_run_never_consumes_a_spotlight(self, monkeypatch, tmp_path):
        from engine import curriculum
        monkeypatch.setenv("NERRA_HOOKS_READONLY", "1")
        assert curriculum.mark_spotlight_done("peptides", "insulin-the-first-peptide", 1,
                                              root=tmp_path) is False


class TestHookArticlesSurviveTheCap:
    def test_cap_keeps_hook_articles(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        cap = src[src.index("MAX_ARTICLES_FOR_LLM = 40"):]
        cap = cap[:cap.index("# Get content tracker summary") if "# Get content tracker summary" in cap else 3000]
        assert 'a.get("source_kind") == "hook"' in cap
        assert "articles = articles[:MAX_ARTICLES_FOR_LLM]" not in src


class TestTapeIgnoresTheLiveBar:
    def test_todays_bar_is_not_a_close_until_16h_new_york(self):
        import datetime as dt

        from engine.market_quotes import completed_bars
        rows = [("2026-09-21", 100.0), ("2026-09-22", 105.0)]
        during = dt.datetime(2026, 9, 22, 19, 37, tzinfo=dt.timezone.utc)   # 15:37 ET
        after = dt.datetime(2026, 9, 22, 20, 30, tzinfo=dt.timezone.utc)    # 16:30 ET
        assert completed_bars(rows, during) == (100.0, None, "2026-09-21")
        assert completed_bars(rows, after) == (105.0, 100.0, "2026-09-22")

    def test_pre_market_run_uses_yesterdays_close(self):
        import datetime as dt

        from engine.market_quotes import completed_bars
        rows = [("2026-09-18", 98.0), ("2026-09-21", 100.0)]
        pre = dt.datetime(2026, 9, 22, 10, 46, tzinfo=dt.timezone.utc)      # 06:46 ET
        assert completed_bars(rows, pre) == (100.0, 98.0, "2026-09-21")


class TestNoLabelSeededEvidenceTic:
    @pytest.mark.parametrize("slug", ("peptides", "longevity"))
    def test_evidence_level_is_prose_not_a_label(self, slug):
        dig = (ROOT / f"shows/prompts/{slug}_digest.txt").read_text(encoding="utf-8")
        # The Longevity dry run shipped "Evidence level: human ..." 11 times.
        assert "never as a label line" in " ".join(dig.split())
