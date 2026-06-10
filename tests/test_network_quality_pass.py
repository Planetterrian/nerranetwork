"""Drift guards for the June 2026 network-wide show quality pass.

Covers the ten non-flagship shows (Tesla/MIT had their own passes):
* every chronically-short show opts into podcast_expand_below_target;
* the generalized show_memory engine inherited (and now has fixed) the
  Tesla theme-pollution + narrative-freshness bugs;
* the hardcoded + fallback X teasers are hook-led network-wide;
* boilerplate-tic bans landed in the prompts;
* the narrative shows' topic queues have real runway.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _yaml(slug):
    return yaml.safe_load((_ROOT / "shows" / f"{slug}.yaml").read_text(
        encoding="utf-8")) or {}


class TestExpandBelowTargetOptIns:
    # Shows the review found chronically below target (>=50% of recent eps).
    EXPECTED = [
        "models_agents", "fascinating_frontiers", "planetterrian",
        "models_agents_beginners", "env_intel", "finansy_prosto",
        "unintended_consequences", "first_principles",
    ]

    @pytest.mark.parametrize("slug", EXPECTED)
    def test_show_opts_in(self, slug):
        llm = _yaml(slug).get("llm") or {}
        assert llm.get("podcast_expand_below_target") is True, (
            f"{slug} ships chronically below target — it must opt into "
            f"podcast_expand_below_target"
        )

    def test_models_agents_has_explicit_target(self):
        # Was relying on the implicit 1500 default; made explicit.
        assert (_yaml("models_agents").get("llm") or {}).get(
            "min_podcast_words") == 1500


class TestShowMemoryFixesPorted:
    def test_theme_mining_is_digest_only(self, tmp_path):
        from engine import show_memory as sm

        cfg = sm.get_config("models_agents")
        assert cfg is not None
        digest = "OpenAI shipped a new frontier model with agentic tool use."
        sm.update_theme_history_from_digest(tmp_path, cfg, digest, 80)
        import json
        themes = json.loads(
            (tmp_path / cfg.theme_filename).read_text())["recurring_themes"]
        # Template phrases must never appear.
        for noise in ("open questions", "questions show", "narrative memory"):
            assert noise not in themes

    def test_auto_narrative_freshness_exists_and_runs(self, tmp_path):
        from engine import show_memory as sm

        cfg = sm.get_config("fascinating_frontiers")
        mentioned = sm.auto_update_narrative_from_digest(
            tmp_path, cfg, "Starship completed another Mars-bound test.",
            96, "2026-06-09")
        assert "starship_mars" in mentioned
        tracker = sm.load_narrative_tracker(tmp_path, cfg)
        assert tracker["programs"]["starship_mars"]["last_mentioned_episode"] == 96

    def test_status_block_has_continuity_instruction(self):
        from engine import show_memory as sm

        cfg = sm.get_config("planetterrian")
        tracker = sm.load_narrative_tracker(
            _ROOT / "digests" / "planetterrian", cfg)
        block = sm.build_narrative_status_block(tracker, cfg.label)
        assert "MAKE THE CONTINUITY AUDIBLE" in block


class TestHookLedTeasersNetworkWide:
    @pytest.mark.parametrize("slug,name", [
        ("omni_view", "Omni View"),
        ("fascinating_frontiers", "Fascinating Frontiers"),
        ("planetterrian", "Planetterrian Daily"),
        ("models_agents", "Models & Agents"),
        ("unintended_consequences", "Unintended Consequences"),
    ])
    def test_teaser_leads_with_hook_and_links_blog(self, slug, name):
        import run_show

        cfg = SimpleNamespace(
            slug=slug, name=name,
            publishing=SimpleNamespace(x_teaser_template=""))
        teaser = run_show._build_teaser(
            cfg, 80, "June 10, 2026",
            {"hook": "A distinctive hook for this episode."})
        assert "A distinctive hook for this episode." in teaser
        assert f"blog/{slug}/ep080.html" in teaser
        assert "summaries.html" not in teaser

    def test_no_hook_no_blog_falls_back_gracefully(self):
        import run_show

        cfg = SimpleNamespace(
            slug="some_unknown_show", name="Unknown Show",
            publishing=SimpleNamespace(x_teaser_template=""))
        teaser = run_show._build_teaser(cfg, 5, "June 10, 2026", {})
        assert teaser  # never empty


class TestPromptTicBans:
    CASES = [
        ("models_agents_podcast.txt", "This development sits within the ongoing"),
        ("fascinating_frontiers_podcast.txt", "blew my mind"),
        ("planetterrian_podcast.txt", "this development fits the tracked program"),
        ("omni_view_podcast.txt", "VARY HOW YOU INTRODUCE THE SIDES"),
        ("unintended_consequences_podcast.txt", "That wraps today's case"),
        ("mab_podcast.txt", "go do this right now"),
        ("env_intel_digest.txt", "REQUIRED EVERY EPISODE"),
    ]

    @pytest.mark.parametrize("fname,needle", CASES)
    def test_prompt_mentions_the_ban_or_requirement(self, fname, needle):
        text = (_ROOT / "shows" / "prompts" / fname).read_text(
            encoding="utf-8")
        assert needle in text, f"{fname} missing expected guidance: {needle!r}"


class TestNarrativeQueueRunway:
    @pytest.mark.parametrize("slug,per_week,min_weeks", [
        ("unintended_consequences", 5, 4.0),
        ("first_principles", 7, 3.0),
    ])
    def test_queue_has_runway(self, slug, per_week, min_weeks):
        q = yaml.safe_load(
            (_ROOT / "shows" / "topic_queues" / f"{slug}.yaml").read_text(
                encoding="utf-8"))["queue"]
        unproduced = [e for e in q if not e.get("produced")]
        weeks = len(unproduced) / per_week
        assert weeks >= min_weeks, (
            f"{slug} queue runway is only {weeks:.1f} weeks — restock it "
            f"(min {min_weeks})"
        )

    def test_queue_ids_unique(self):
        for slug in ("unintended_consequences", "first_principles"):
            q = yaml.safe_load(
                (_ROOT / "shows" / "topic_queues" / f"{slug}.yaml").read_text(
                    encoding="utf-8"))["queue"]
            ids = [e["id"] for e in q]
            assert len(ids) == len(set(ids)), f"{slug} has duplicate queue ids"

    def test_first_principles_alternation_stocked(self):
        q = yaml.safe_load(
            (_ROOT / "shows" / "topic_queues" / "first_principles.yaml").read_text(
                encoding="utf-8"))["queue"]
        unproduced = [e for e in q if not e.get("produced")]
        cats = {e.get("category") for e in unproduced}
        # Both arms of the alternation must remain available.
        assert "concrete_example" in cats
        assert "opportunity_area" in cats


class TestFinansyProstoCategoryFix:
    def test_youtube_category_is_education(self):
        yt = _yaml("finansy_prosto").get("youtube") or {}
        # Was 25 (News & Politics) — a financial-literacy education show.
        assert yt.get("category_id") == 27
