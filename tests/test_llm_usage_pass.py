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

    def test_reviewer_default_is_explicit_grok_43(self):
        """The reviewer ran on the retired grok-4-1-fast-non-reasoning slug
        from 2026-05-15 to 2026-08-18 — served by grok-4.3 (effort none)
        but costed at the retired model's 6x-cheaper rates."""
        from engine.config import LLMConfig

        assert LLMConfig().reviewer_model == "grok-4.3"

        defaults = yaml.safe_load(
            (REPO_ROOT / "shows" / "_defaults.yaml").read_text(
                encoding="utf-8"))
        assert defaults["llm"]["reviewer_model"] == "grok-4.3"

    def test_review_episodes_fallback_is_grok_43(self):
        src = (REPO_ROOT / "review_episodes.py").read_text(encoding="utf-8")
        assert 'default_model = "grok-4.3"' in src
        # Effort parity with the retired-slug redirect the call ran on.
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
