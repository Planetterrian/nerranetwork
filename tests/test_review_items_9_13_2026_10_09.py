"""Oct 9 2026 — review items 9–13 and the afternoon slate's fixes.

9.  The structural digest regeneration fired on 35% of episodes. Three
    validator rules fired on sections the pipeline itself emptied or on an
    optional section that was present; six prompts supplied their own
    over-limit specimen hook. The reasons are recorded now.
10. The dead-Shorts probe tier draws two portrait scenes, keyed on the
    plan's ``shorts_probe`` flag — never a show list.
11. The cohort's 7–9 search calls were per-account X fetches, not web
    queries: ``x_accounts_per_run`` reads four a day on a rotation.
13. X is on for SpaceX, Nerra Daily and The Age of AI; every poster
    records an outcome. The two bypass publishers post through
    ``engine.x_post``.
Afternoon: the grok-4.6 script arms stream; an empty jobs read narrows
the multilingual sweep to nothing.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import validation as val  # noqa: E402
from engine.config import load_config  # noqa: E402
from engine.fetcher import rotate_x_accounts  # noqa: E402
from engine.youtube_policy import (  # noqa: E402
    PROBE_PORTRAIT_SCENES, portrait_scene_count, resolve_publish_plan,
)

HOOK_INCLUDE_SHOWS = {
    "unintended_consequences": "unintended_consequences_episode.txt",
    "first_principles": "first_principles_episode.txt",
}
# The Sep 22 spoken-open experiment (long_open_hold_5pct_arm vs _control,
# readout Oct 13) reads tesla / spacex / FF against these; their hook
# prompts stay exactly as they are until it is scored, over-limit
# specimens included. Second-largest regen source after it: omni_view
# 12/14, modern_investing 5, models_agents 5, env_intel 2/2.
CONTROL_SHOWS_WAITING = ("omni_view", "models_agents", "modern_investing", "env_intel")
ROTATED_SHOWS = ("vancouver", "ai_chips", "mag7", "peptides", "longevity")


# ---------------------------------------------------------------- item 9 --
class TestStructuralRegen:
    def test_present_optional_section_with_zero_items_is_not_an_issue(self):
        cfg = val.ValidationConfig(sections=[val.SectionRule(
            name="Listener Challenge",
            pattern=r"(?:### Listener Challenge)(.*?)(?=━━|$)",
            min_items=1, optional=True)])
        digest = "# MIT\n\n### Listener Challenge\nWrite down one holding you would sell first.\n"
        passed, issues, _ = val.validate_digest(digest, cfg)
        assert not [i for i in issues if "Listener Challenge" in i], issues

    def test_mandatory_section_with_zero_items_still_flags(self):
        cfg = val.ValidationConfig(sections=[val.SectionRule(
            name="Body", pattern=r"(?:### Body)(.*?)(?=━━|$)", min_items=1)])
        _, issues, _ = val.validate_digest("# X\n\n### Body\nshort\n", cfg)
        assert any("Body" in i and "0 items" in i for i in issues)

    def test_tesla_short_spot_is_optional(self):
        rule = next(s for s in val.tst_validation_config().sections if s.name == "Short Spot")
        assert rule.optional is True

    def test_tesla_committed_digests_no_longer_fail_on_short_spot(self):
        files = sorted((ROOT / "digests" / "tesla_shorts_time").glob("*_Ep6*_2026*.md"))[-10:]
        assert files
        for f in files:
            _, issues, _ = val.validate_digest(f.read_text(encoding="utf-8"), val.tst_validation_config())
            assert not [i for i in issues if "Short Spot" in i], (f.name, issues)

    def test_ff_space_stories_accepts_the_headerless_list(self):
        digest = ("# Fascinating Frontiers\n🚀 **Fascinating Frontiers** - Space\n"
                  "> **A hook here.**\n---\n"
                  + "".join(f"{i}. **Story {i} headline today** — Outlet\n   Body.\n\n" for i in range(1, 10))
                  + "━━━━━━━━━━━━━━━━━━━━\n### Cosmic Spotlight\n**One** — x\n   b.\n")
        _, issues, _ = val.validate_digest(digest, val.ff_validation_config())
        assert not [i for i in issues if "Space Stories" in i], issues

    def test_ff_space_stories_still_reads_the_header_form(self):
        digest = ("# FF\n> **A hook.**\n---\n### Top 15 Space & Astronomy Stories\n"
                  + "".join(f"{i}. **Story {i} headline today** — Outlet\n   Body.\n\n" for i in range(1, 10))
                  + "━━━━━━━━━━━━━━━━━━━━\n### Cosmic Spotlight\n**One** — x\n   b.\n")
        _, issues, _ = val.validate_digest(digest, val.ff_validation_config())
        assert not [i for i in issues if "Space Stories" in i], issues

    def test_reasons_are_recorded(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'metrics.record("digest_structural_regen_reasons", list(_struct_defects))' in src

    @pytest.mark.parametrize("slug,prompt", sorted(HOOK_INCLUDE_SHOWS.items()))
    def test_hook_is_shape_only_and_includes_the_shared_snippet(self, slug, prompt):
        text = (ROOT / "shows" / "prompts" / prompt).read_text(encoding="utf-8")
        assert "<<include: _shared/hook_shape.txt>>" in text, slug
        assert "Compare: WEAK" not in text, slug
        hook_line = next(ln for ln in text.splitlines() if ln.startswith("**HOOK:**"))
        assert 'Example: "' not in hook_line, slug
        assert "characters" not in hook_line, (slug, "the include owns the length")

    @pytest.mark.parametrize("slug", CONTROL_SHOWS_WAITING)
    def test_control_shows_wait_for_the_oct_13_readout(self, slug):
        text = (ROOT / "shows" / "prompts" / f"{slug}_digest.txt").read_text(encoding="utf-8")
        assert "hook_shape" not in text, (slug, "not before the spoken-open readout")

    def test_dashboard_reads_the_share(self):
        import scripts.generate_dashboard as gd
        out = gd._episode_counter_shares(ROOT, dt.date(2026, 10, 9), days=7, min_n=1)
        assert "digest_structural_regen_share_7d" in out and "x_posted_share_7d" in out
        assert out["digest_structural_regen_share_7d"] is None or 0 <= out["digest_structural_regen_share_7d"] <= 1


# --------------------------------------------------------------- item 10 --
class TestProbeTierImagery:
    def _policy(self, probe: bool):
        return {"channels": {"en": {"omni_view": {
            "tier": "B", "publish_long_form": True, "shorts_per_episode": 0,
            "shorts_probe_weekly": probe}}}}

    def test_plan_carries_the_probe_flag(self):
        plan = resolve_publish_plan(self._policy(True), slug="omni_view", channel="en",
                                    yaml_publish_long=True, yaml_shorts=1, smart_mode=True,
                                    adaptive_enabled=True, probe_today=dt.date(2026, 10, 9))
        assert plan["shorts_probe"] is True
        plan = resolve_publish_plan(self._policy(False), slug="omni_view", channel="en",
                                    yaml_publish_long=True, yaml_shorts=1, smart_mode=True,
                                    adaptive_enabled=True, probe_today=dt.date(2026, 10, 9))
        assert plan["shorts_probe"] is False
        plan = resolve_publish_plan(None, slug="omni_view", channel="en",
                                    yaml_publish_long=True, yaml_shorts=1, smart_mode=True,
                                    adaptive_enabled=True)
        assert plan["shorts_probe"] is False

    def test_probe_caps_portrait_scenes_at_two(self):
        class _Yt:
            short_scenes_per_episode = 5
            ru_dub_enabled = False
            dub_languages = []
            multi_platform_enabled = False
        assert PROBE_PORTRAIT_SCENES == 2
        assert portrait_scene_count(_Yt(), shorts_planned=1, shorts_probe=True) == 2
        assert portrait_scene_count(_Yt(), shorts_planned=1) == 5
        assert portrait_scene_count(_Yt(), shorts_planned=0, shorts_probe=True) == 0
        _Yt.short_scenes_per_episode = 1
        assert portrait_scene_count(_Yt(), shorts_planned=1, shorts_probe=True) == 1, "never raised"

    def test_runner_passes_the_flag_and_binds_the_plan_first(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'shorts_probe=bool(_yt_plan.get("shorts_probe"))' in src
        assert src.index("_yt_plan: dict = {}") < src.index("_yt_plan = resolve_publish_plan(")

    def test_the_live_policy_has_probe_entries(self):
        policy = json.loads((ROOT / "api" / "youtube_policy.json").read_text(encoding="utf-8"))
        en = policy["channels"]["en"]
        assert any(v.get("shorts_probe_weekly") for v in en.values())


# --------------------------------------------------------------- item 11 --
class TestXAccountRotation:
    def test_rotation_covers_the_list_and_is_stable_per_day(self):
        accounts = list("ABCDEFGHI")
        day = dt.date(2026, 10, 9)
        today = rotate_x_accounts(accounts, 4, day)
        assert len(today) == 4 and len(set(today)) == 4
        assert rotate_x_accounts(accounts, 4, day) == today, "a same-day re-run reads the same accounts"
        seen = set()
        for i in range(3):
            seen.update(rotate_x_accounts(accounts, 4, day + dt.timedelta(days=i)))
        assert seen == set(accounts), "nine accounts are covered inside three days"

    def test_zero_or_large_cap_reads_everything(self):
        accounts = list("ABC")
        assert rotate_x_accounts(accounts, 0, dt.date(2026, 10, 9)) == accounts
        assert rotate_x_accounts(accounts, 3, dt.date(2026, 10, 9)) == accounts
        assert rotate_x_accounts([], 4, dt.date(2026, 10, 9)) == []

    @pytest.mark.parametrize("slug", ROTATED_SHOWS)
    def test_the_five_cohort_shows_read_four_a_day(self, slug):
        cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
        assert cfg.x_accounts_per_run == 4, slug
        assert len(cfg.x_accounts) > 4, slug

    def test_every_other_show_reads_all(self):
        for y in sorted((ROOT / "shows").glob("*.yaml")):
            if y.name.startswith("_") or y.stem in ROTATED_SHOWS or y.stem == "network_meta":
                continue
            assert load_config(y).x_accounts_per_run == 0, y.name

    def test_runner_rotates_before_the_fetch(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "rotate_x_accounts(" in src
        assert src.index("rotate_x_accounts(") < src.index("return fetch_x_posts(\n                _x_accounts")


# --------------------------------------------------------------- item 13 --
class TestXOutcome:
    def test_spacex_posts_from_the_x_app(self):
        cfg = load_config(ROOT / "shows" / "spacex.yaml")
        assert cfg.publishing.x_enabled is True
        assert cfg.publishing.x_env_prefix == "X_"
        assert cfg.publishing.x_handle == "@teslashortstime"

    def test_age_of_ai_posts_from_the_network_account(self):
        cfg = load_config(ROOT / "shows" / "age_of_ai.yaml")
        assert cfg.publishing.x_enabled is True
        assert cfg.publishing.x_env_prefix == "NERRANETWORK_X_"

    def test_runner_records_the_outcome(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'metrics.record("x_posted", _x_posted)' in src
        assert 'metrics.record("x_post_skipped", _x_skip_reason or "post_failed")' in src
        assert '_x_skip_reason = "no_credentials"' in src

    def test_poster_skips_cleanly_without_credentials(self, monkeypatch):
        from engine import x_post
        for k in ("CONSUMER_KEY", "CONSUMER_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET"):
            monkeypatch.delenv(f"NERRANETWORK_X_{k}", raising=False)
        posted, reason = x_post.post_teaser(env_prefix="NERRANETWORK_X_", title="T",
                                            link="https://nerranetwork.com/x", label="t")
        assert (posted, reason) == (False, "no_credentials")

    def test_poster_posts_with_credentials_and_reports_failure(self, monkeypatch):
        from engine import publisher, x_post
        for k in ("CONSUMER_KEY", "CONSUMER_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET"):
            monkeypatch.setenv(f"NERRANETWORK_X_{k}", "x")
        seen = {}

        def fake(text, **kw):
            seen["text"] = text
            return "https://x.com/nerranetwork/status/1"
        monkeypatch.setattr(publisher, "post_to_x", fake)
        posted, reason = x_post.post_teaser(env_prefix="NERRANETWORK_X_", title="A title",
                                            link="https://nerranetwork.com/x?utm_source=x", label="t")
        assert posted and reason == ""
        assert seen["text"].startswith("A title\n\nhttps://nerranetwork.com/x")
        monkeypatch.setattr(publisher, "post_to_x", lambda text, **kw: None)
        assert x_post.post_teaser(env_prefix="NERRANETWORK_X_", title="A", link="L", label="t") == (False, "post_failed")

    def test_teaser_text_is_clipped_by_the_titles_module(self):
        from engine.titles import X_TEASER_TEXT_MAX
        from engine.x_post import teaser_text
        long = "word " * 80
        text = teaser_text(long, "https://nerranetwork.com/x")
        head = text.rsplit("\n\n", 1)[0]
        assert len(head) <= X_TEASER_TEXT_MAX and text.endswith("https://nerranetwork.com/x")

    def test_edition_metrics_carry_the_outcome(self):
        from engine.daily_edition import EDITIONS, build_edition_metrics
        assert EDITIONS["en"].x_env_prefix == "NERRANETWORK_X_"
        m = build_edition_metrics(1, dt.date(2026, 10, 9), 60.0, [], links_source="fallback",
                                  field_note_included=False, missing_expected=[], dropped=[],
                                  x_posted=False, x_post_skipped="no_credentials")
        assert m["x_posted"] is False and m["x_post_skipped"] == "no_credentials"
        m = build_edition_metrics(1, dt.date(2026, 10, 9), 60.0, [], links_source="fallback",
                                  field_note_included=False, missing_expected=[], dropped=[])
        assert m["x_posted"] is None

    def test_edition_builder_posts_after_publish(self):
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        assert src.index("_append_summary(spec, target_date, digest_md") < src.index("post_edition_to_x(spec, episode_num, title)") < src.index("x_posted=x_posted,")

    def test_voices_publisher_posts_and_the_workflows_carry_the_secrets(self):
        src = (ROOT / "pipelines" / "voices" / "publish_episode.py").read_text(encoding="utf-8")
        assert "def maybe_post_x(" in src and "maybe_post_x(show, cfg, episode_num, title)" in src
        assert src.index("maybe_publish_youtube(show, cfg, episode_num, today") < src.index("maybe_post_x(show, cfg, episode_num, title)")
        for wf in ("nerra-daily.yml", "nerra_voices_publish.yml"):
            text = (ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8")
            for k in ("CONSUMER_KEY", "CONSUMER_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET"):
                assert f"NERRANETWORK_X_{k}: ${{{{ secrets.NERRANETWORK_X_{k} }}}}" in text, (wf, k)
        assert "tweepy" in (ROOT / "pipelines" / "requirements.txt").read_text(encoding="utf-8")


# -------------------------------------------------------------- afternoon --
class TestAfternoonSlateFixes:
    @pytest.mark.parametrize("slug", ("spacex", "omni_view"))
    def test_pinned_script_arms_stream(self, slug):
        cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
        assert cfg.llm.podcast_model == "grok-4.6"
        assert cfg.llm.stream is True

    def test_empty_jobs_read_narrows_the_sweep(self):
        text = (ROOT / ".github" / "workflows" / "multilingual.yml").read_text(encoding="utf-8")
        assert "if published:" not in text
        assert "shows = [s for s in published if s in enabled]" in text

    def test_register_entries_exist(self):
        import yaml
        reg = yaml.safe_load((ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8"))
        ids = {e["id"] for e in reg["experiments"]}
        for i in ("structural-regen-2026-10-09", "probe-tier-imagery-2026-10-09",
                  "x-accounts-rotation-2026-10-09", "x-on-spacex-daily-aoai-2026-10-09"):
            assert i in ids, i

    def test_doc_names_the_three_french_feeds(self):
        text = (ROOT / "docs" / "podcast_directories.md").read_text(encoding="utf-8")
        for f in ("models_agents_podcast.fr.rss", "first_principles_podcast.fr.rss", "env_intel_podcast.fr.rss"):
            assert f in text, f
