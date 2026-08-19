"""Drift guards for the 2026-08-18 LLM usage review.

Canonical writeup: docs/reviews/llm_usage_review_2026_08_18.md.

Three silent-number/silent-drift fixes are pinned here:

1. No LIVE call site may resolve to a slug xAI retired on 2026-05-15
   (they redirect silently, so nothing breaks — the bill and the served
   model just stop matching the config).
2. The multilingual translation stage must never ride a floating model
   alias (``grok-latest``) — a vendor flagship release must not be able
   to change shipped dub audio without an explicit edit in this repo.
3. Search-tool spend bills per CALL under 2026 xAI pricing; the cost of
   a call with no reported source count must be nonzero.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Slugs retired by xAI on 2026-05-15 (docs.x.ai May-15 retirement page).
# They still resolve — requests redirect to grok-4.3 / grok-build-0.1 at
# the REDIRECT TARGET's billing — which is exactly why config referencing
# them is a silent cost/model mismatch rather than a visible failure.
RETIRED_SLUGS = {
    "grok-4-1-fast-reasoning",
    "grok-4-1-fast-non-reasoning",
    "grok-4-fast-reasoning",
    "grok-4-fast-non-reasoning",
    "grok-4-0709",
    "grok-code-fast-1",
    "grok-3",
    "grok-imagine-image-pro",
}


def _yaml_without_comments(path: Path) -> str:
    """The scan must not trip on explanatory comments that NAME a retired
    slug while documenting why it was removed — only live values count."""
    return "\n".join(
        line.split("#", 1)[0]
        for line in path.read_text(encoding="utf-8").splitlines()
    )


class TestNoLiveRetiredSlugs:
    def test_defaults_yaml_references_no_retired_slug(self):
        text = _yaml_without_comments(REPO_ROOT / "shows" / "_defaults.yaml")
        for slug in RETIRED_SLUGS:
            assert slug not in text, (
                f"shows/_defaults.yaml references retired slug {slug} — "
                "xAI silently redirects it, so the served model and the "
                "tracked cost stop matching the config"
            )

    def test_show_yamls_reference_no_retired_slug(self):
        for path in sorted((REPO_ROOT / "shows").glob("*.yaml")):
            text = _yaml_without_comments(path)
            for slug in RETIRED_SLUGS:
                assert slug not in text, f"{path.name} references {slug}"

    def test_reviewer_default_is_an_explicit_priced_model(self):
        """The reviewer ran on the retired grok-4-1-fast-non-reasoning slug
        from 2026-05-15 to 2026-08-18 — served by grok-4.3 (effort none)
        but costed at the retired model's 6x-cheaper rates. grok-4.6
        since the 2026-08-18 staged trial (staged-grok-46-trial) — the
        invariant is: an explicit, priced, non-retired model id."""
        from engine.config import LLMConfig
        from engine.tracking import GROK_PRICING

        assert LLMConfig().reviewer_model == "grok-4.6"

        defaults = yaml.safe_load(
            (REPO_ROOT / "shows" / "_defaults.yaml").read_text(
                encoding="utf-8"))
        assert defaults["llm"]["reviewer_model"] == "grok-4.6"
        assert defaults["llm"]["reviewer_model"] in GROK_PRICING

    def test_review_episodes_fallback_is_pinned_and_priced(self):
        src = (REPO_ROOT / "review_episodes.py").read_text(encoding="utf-8")
        assert 'default_model = "grok-4.3"' in src
        # The grok-4.3 redirect-parity branch (effort none) must survive
        # for anyone pinning reviewer_model back to 4.3.
        assert '"reasoning_effort": "none"' in src


class TestTranslationModelIsPinned:
    def test_no_floating_alias(self):
        from engine import translate

        assert translate._TRANSLATION_MODEL != "grok-latest", (
            "translation must not ride a floating alias — a vendor "
            "flagship release would silently change every dub track"
        )
        assert not translate._TRANSLATION_MODEL.endswith("latest")

    def test_pinned_model_is_priced(self):
        """The multilingual cost estimate prices the ACTUAL pinned model;
        an unpriced pin would silently fall back to grok-4.3 rates."""
        from engine.tracking import GROK_PRICING
        from engine.translate import _TRANSLATION_MODEL

        assert _TRANSLATION_MODEL in GROK_PRICING

    def test_env_override_wins(self, monkeypatch):
        import importlib

        monkeypatch.setenv("NERRA_TRANSLATION_MODEL", "grok-4.3")
        from engine import translate

        importlib.reload(translate)
        try:
            assert translate._TRANSLATION_MODEL == "grok-4.3"
        finally:
            monkeypatch.delenv("NERRA_TRANSLATION_MODEL")
            importlib.reload(translate)


class TestDashboardCostBreakout:
    """Images + search were 41% of tracked 30d spend yet invisible as
    dashboard categories (absorbed into `total` only)."""

    def test_rollup_buckets_carry_images_and_search(self):
        src = (REPO_ROOT / "scripts" / "generate_dashboard.py").read_text(
            encoding="utf-8")
        assert '"images": 0.0' in src and '"search": 0.0' in src
        assert 'bucket["images"] += images' in src
        assert 'bucket["search"] += search' in src

    def test_aggregate_costs_reads_image_and_search_services(self, tmp_path):
        import importlib.util
        import json as _json
        import sys

        spec = importlib.util.spec_from_file_location(
            "gen_dash", REPO_ROOT / "scripts" / "generate_dashboard.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["gen_dash"] = mod
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.modules.pop("gen_dash", None)

        import datetime as _dt
        ddir = tmp_path / "digests" / "tesla_shorts_time"
        ddir.mkdir(parents=True)
        today = _dt.date.today().isoformat()
        (ddir / f"credit_usage_{today}_ep001.json").write_text(_json.dumps({
            "date": today,
            "services": {
                "grok_api": {"total_cost_usd": 0.02},
                "tts_api": {"estimated_cost_usd": 0.10},
                "image_api": {"estimated_cost_usd": 0.16},
                "search_api": {"estimated_cost_usd": 0.03},
            },
            "total_estimated_cost_usd": 0.31,
        }), encoding="utf-8")

        out = mod.aggregate_costs(
            tmp_path, [{"slug": "tesla", "name": "Tesla Shorts Time"}])
        net30 = out["network_last_30_days"]
        assert net30["images"] == pytest.approx(0.16)
        assert net30["search"] == pytest.approx(0.03)
        assert net30["total"] == pytest.approx(0.31)


class TestStagedGrok46Trial:
    """Scope guards for the 2026-08-18 staged grok-4.6 trial
    (experiment ``staged-grok-46-trial`` — the first rollout run under
    docs/model_upgrade_playbook.md).

    The trial's whole safety argument is its SCOPE: dialogue/narrative
    writing and analysis stages move, the facts-first news digests do
    not. A pin quietly widening (or quietly disappearing) is exactly the
    silent-config drift class this file exists for.
    """

    TRIAL_NARRATIVE_SHOWS = ("first_principles", "unintended_consequences")
    NEWS_SHOWS_STAY_43 = (
        "tesla", "spacex", "omni_view", "modern_investing",
        "models_agents", "models_agents_beginners", "planetterrian",
        "fascinating_frontiers", "env_intel", "finansy_prosto",
        "privet_russian", "offshore_north",
    )

    def _load(self, slug):
        from engine.config import load_config
        return load_config(REPO_ROOT / "shows" / f"{slug}.yaml")

    def test_trial_narrative_shows_are_on_46(self):
        for slug in self.TRIAL_NARRATIVE_SHOWS:
            assert self._load(slug).llm.model == "grok-4.6", slug

    def test_dp_pod_script_stage_only(self):
        """dp_pod's DIGEST must keep inheriting the grok-4.3 network
        default — only the script stage rides 4.6."""
        cfg = self._load("dp_pod")
        assert cfg.llm.podcast_model == "grok-4.6"
        assert cfg.llm.model == "grok-4.3"

    def test_every_news_show_digest_stays_on_43(self):
        """The four biggest-prompt shows timed out on 4.6 and the
        facts-first digests carry the hallucination stakes — none of
        them may follow the trial by accident."""
        for slug in self.NEWS_SHOWS_STAY_43:
            path = REPO_ROOT / "shows" / f"{slug}.yaml"
            if not path.exists():
                continue
            assert self._load(slug).llm.model == "grok-4.3", slug

    def test_request_timeout_covers_46_latency(self):
        """Measured 4.6 latency on the trial shows is 205-242s — the
        workflow must carry NERRA_LLM_TIMEOUT_SECONDS >= 600 while any
        show is on 4.6, and the envelope arithmetic must still hold
        (3 tenacity attempts x timeout under the 50-min watchdog)."""
        wf = yaml.safe_load(
            (REPO_ROOT / ".github" / "workflows" / "run-show.yml")
            .read_text(encoding="utf-8"))
        step = next(s for s in wf["jobs"]["run"]["steps"]
                    if s.get("name") == "Run show pipeline")
        llm_timeout = int(step["env"]["NERRA_LLM_TIMEOUT_SECONDS"])
        watchdog = int(step["env"]["PIPELINE_TIMEOUT_SECONDS"])
        assert llm_timeout >= 600
        assert 3 * llm_timeout <= watchdog + 600, (
            "one worst-case LLM stage must not be able to consume the "
            "whole watchdog budget by itself"
        )

    def test_trial_models_are_priced(self):
        from engine.tracking import GROK_PRICING
        assert "grok-4.6" in GROK_PRICING
        assert "grok-4.3" in GROK_PRICING

    def test_trial_is_registered(self):
        reg = yaml.safe_load(
            (REPO_ROOT / "docs" / "experiments.yaml").read_text(
                encoding="utf-8"))
        ids = {e.get("id") for e in reg["experiments"]}
        assert "staged-grok-46-trial" in ids


class TestGrok46FunnelAndOpsWave:
    """Scope guards for experiment grok-46-funnel-and-ops (2026-08-19):
    grok-4.6 on the metadata/ops surfaces where writing quality is the
    product and latency doesn't gate a daily slot. Each pin is a
    one-line revert; none touches a daily news digest."""

    def test_title_bundle_runs_on_46(self):
        src = (REPO_ROOT / "engine" / "youtube_titles.py").read_text(
            encoding="utf-8")
        assert src.count('model: str = "grok-4.6"') == 3
        assert 'model: str = "grok-4.3"' not in src

    def test_restock_runs_on_46_with_env_rollback(self):
        src = (REPO_ROOT / "scripts" / "restock_topic_queues.py").read_text(
            encoding="utf-8")
        assert "NERRA_RESTOCK_MODEL" in src
        assert '"grok-4.6"' in src

    def test_spacex_specials_run_on_46_daily_stays_43(self):
        from engine.config import load_config
        cfg = load_config(REPO_ROOT / "shows" / "spacex.yaml")
        assert cfg.deep_dive.model == "grok-4.6"
        assert cfg.llm.model == "grok-4.3"

    def test_deep_dive_model_default_is_inherit(self):
        from engine.config import DeepDiveConfig
        assert DeepDiveConfig().model == ""

    def test_run_show_applies_the_deep_dive_model_swap(self):
        src = (REPO_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "config.llm.model = _dd_cfg.model" in src

    def test_model_era_stamps_are_recorded(self):
        """Per-episode model ids (the RENDER_LOOK_VERSION pattern for
        LLMs): without them, split-model episodes are unattributable in
        analytics — the credit file's single label proved that on the
        trial's first day."""
        src = (REPO_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'metrics.record("llm_digest_model"' in src
        assert '"llm_script_model"' in src
        tsrc = (REPO_ROOT / "engine" / "tracking.py").read_text(
            encoding="utf-8")
        assert 'grok[step]["model"] = model' in tsrc
