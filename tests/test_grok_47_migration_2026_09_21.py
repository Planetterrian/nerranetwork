"""The staged grok-4.6 -> 4.7 migration, and the traps in it.

``docs/model_upgrade_playbook.md`` was written after a network-wide,
all-stages flip took down 7 of 12 shows the next morning. Its sharpest line
is that the registered revert triggers watched hallucination rate, reviewer
flags and fetch tool-calls, and **nobody watched latency** — the failure that
actually fired was operational and unmonitored.

These guards pin the parts of the playbook a future model change can break
silently. They deliberately do NOT pin "grok-4.7 is the current model": that
is a value the operator changes, and a test that fails on it is noise. They
pin the *invariants* that make a model change safe.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def _defaults() -> dict:
    return yaml.safe_load(
        (ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))


def _show_yamls():
    for path in sorted((ROOT / "shows").glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        yield path.stem, yaml.safe_load(path.read_text(encoding="utf-8")) or {}


class TestEveryModelInUseIsPriced:
    """Playbook rule 4. The retired grok-4-1-fast slug was mis-costed 6x for
    three months because nothing priced it before a stage used it, so every
    credit file written in that window is wrong and cannot be re-scored."""

    def _models_in_use(self) -> set:
        from engine.config import load_config

        models = set()
        defaults = _defaults().get("llm", {}) or {}
        for key in ("model", "fallback_model", "synth_model",
                    "reviewer_model", "podcast_model"):
            if defaults.get(key):
                models.add(str(defaults[key]))
        for slug, _raw in _show_yamls():
            cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
            for key in ("model", "fallback_model", "synth_model",
                        "reviewer_model", "podcast_model"):
                value = getattr(cfg.llm, key, "")
                if value:
                    models.add(str(value))
        return {m for m in models if m.startswith("grok")}

    def test_every_configured_model_has_a_price(self):
        from engine.tracking import GROK_PRICING

        missing = sorted(self._models_in_use() - set(GROK_PRICING))
        assert not missing, (
            f"configured but unpriced: {missing} — every credit_usage file "
            "written while this ships costs out wrong, and the error is "
            "unrecoverable after the fact")

    def test_a_price_is_complete(self):
        """A half-filled row silently zeroes one side of the cost."""
        from engine.tracking import GROK_PRICING

        for model in self._models_in_use():
            row = GROK_PRICING[model]
            assert row.get("input_per_1m") and row.get("output_per_1m"), (
                f"{model} has an incomplete pricing row: {row}")


class TestNoFloatingAlias:
    """Playbook rule 6. A `-latest` alias lets a vendor release change
    shipped audio with no commit, which is how the translation stage rode an
    alias until 2026-08-18."""

    _FLOATING = re.compile(r"(latest|preview|beta|-dev)\b", re.I)

    def test_no_configured_stage_rides_an_alias(self):
        from engine.config import load_config

        for slug, _raw in _show_yamls():
            cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
            for key in ("model", "fallback_model", "synth_model",
                        "reviewer_model", "podcast_model"):
                value = str(getattr(cfg.llm, key, "") or "")
                assert not self._FLOATING.search(value), (
                    f"{slug}.llm.{key} = {value!r} is a floating alias")


class TestTheFallbackIsADifferentSnapshot:
    """A refusal fallback pointed at the primary retries the same model and
    the refusal simply happens twice. Playbook rule 5 calls this out because
    a fallback repoint rides along with upgrades."""

    def test_primary_and_fallback_differ(self):
        from engine.config import load_config

        for slug, _raw in _show_yamls():
            cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
            if cfg.llm.fallback_model:
                assert cfg.llm.fallback_model != cfg.llm.model, (
                    f"{slug}: refusal fallback is the primary model")


class TestTheReviewerKeepsItsLowEffort:
    """The trap this migration nearly walked into.

    ``review_episodes.py`` forces ``reasoning_effort: low`` on the reviewer,
    because at default effort the 4.6 reviewer blew the 300s request timeout
    on ~1/3 of episodes and the 35-minute audit job died with no report. That
    branch matched a single model id, so moving the pin to 4.7 would have
    matched NOTHING and silently restored default effort — a one-line model
    change that was really two.
    """

    def test_the_configured_reviewer_gets_low_effort(self):
        import review_episodes

        reviewer = str(_defaults()["llm"]["reviewer_model"])
        forced_low = reviewer.startswith(
            review_episodes._LOW_EFFORT_REVIEWER_PREFIXES)
        explicitly_none = reviewer.startswith("grok-4.3")
        assert forced_low or explicitly_none, (
            f"reviewer_model {reviewer!r} matches no effort branch in "
            "review_episodes.py — it would run at DEFAULT effort and "
            "reproduce the 2026-08-21 audit outage")

    def test_the_branch_is_a_family_not_one_id(self):
        """Pinned to a single id it breaks again on the next successor."""
        import review_episodes

        assert isinstance(
            review_episodes._LOW_EFFORT_REVIEWER_PREFIXES, tuple)
        assert len(review_episodes._LOW_EFFORT_REVIEWER_PREFIXES) >= 2


class TestStagingIsStaged:
    """Playbook rule 1: never network-wide on day one.

    Asserted as a property — the DIGEST path, which is what failed in
    August, must not move with a script-stage or reviewer trial.
    """

    def test_no_show_digest_left_the_network_default(self):
        """Digest and fetch stages stay on the network default. A show that
        pins its own digest model is opting the facts-first path into a
        trial, which is the August shape."""
        from engine.config import load_config

        default_model = str(_defaults()["llm"]["model"])
        pinned = []
        for slug, raw in _show_yamls():
            cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
            if str(cfg.llm.model) != default_model:
                pinned.append((slug, cfg.llm.model))
        # spacex pins its DEEP-DIVE model under `deep_dive:`, which is
        # manual-force only and has no daily slot; that is not this key.
        assert not pinned, (
            f"shows pinning their own digest model: {pinned} — the digest "
            "path is what fell over on 2026-08-18")

    def test_the_script_trial_covers_one_show_at_most_per_model(self):
        """A script-stage trial is per-show by design. If a single
        non-default model appears on most of the network, the trial has
        quietly become a rollout."""
        from engine.config import load_config

        counts: dict = {}
        total = 0
        for slug, _raw in _show_yamls():
            cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
            total += 1
            if cfg.llm.podcast_model:
                counts[str(cfg.llm.podcast_model)] = counts.get(
                    str(cfg.llm.podcast_model), 0) + 1
        for model, n in counts.items():
            assert n <= max(3, total // 4), (
                f"{model} is the script model on {n} of {total} shows — "
                "that is a rollout, not a staged trial")


class TestTheTrialReportIsUsable:
    """The gate has to run from the committed repo with no API key, or the
    verdict is not reproducible later by anyone."""

    def test_it_runs_and_reports_nothing_on_a_future_date(self):
        from scripts.model_trial_report import main

        assert main(["--since", "2099-01-01"]) == 0

    def test_it_dates_episodes_from_committed_filenames_not_mtime(self):
        """A fresh checkout rewrites every mtime in the repo, so an
        mtime-dated report reads as 'everything happened today'."""
        from scripts.model_trial_report import _episode_dates

        dates = _episode_dates(ROOT / "digests" / "omni_view")
        assert dates, "no dated episodes found for omni_view"
        assert len(set(dates.values())) > 1, (
            "every episode resolved to one date — the report is reading "
            "file mtimes")

    def test_it_fails_the_gate_on_a_real_latency_regression(self):
        """Fed a window that contains one, it must say so — a gate that
        cannot fail is decoration."""
        from scripts.model_trial_report import summarise

        rows = [{"episode": 1, "date": None,
                 "stages": [{"name": "generate_digest",
                             "duration_s": 280.0, "success": True}],
                 "total_duration_s": 280.0}]
        stats = summarise(rows)["generate_digest"]
        assert stats["p95"] == 280.0
        from scripts.model_trial_report import (
            P95_TIMEOUT_SHARE_LIMIT, _is_llm_stage)
        assert _is_llm_stage("generate_digest")
        assert stats["p95"] / 300.0 > P95_TIMEOUT_SHARE_LIMIT

    def test_a_render_stage_never_gates_a_model_trial(self):
        """ffmpeg is not the model's fault."""
        from scripts.model_trial_report import _is_llm_stage

        assert not _is_llm_stage("long_form_render")
        assert not _is_llm_stage("fetch_and_dedup")


class TestTheExperimentIsRegistered:
    """Playbook rule 4: an entry with a readout AND latency/run-success
    revert triggers, not only quality ones."""

    @pytest.fixture(scope="module")
    def entry(self):
        data = yaml.safe_load(
            (ROOT / "docs" / "experiments.yaml").read_text(encoding="utf-8"))
        found = [e for e in data["experiments"]
                 if e.get("id") == "grok-47-staged-migration"]
        assert found, "the migration is not in the experiment register"
        return found[0]

    def test_it_has_a_readout_date(self, entry):
        assert entry.get("readout")

    def test_its_revert_triggers_include_latency(self, entry):
        criteria = str(entry.get("criteria", "")).lower()
        assert "p95" in criteria or "latency" in criteria, (
            "the August outage's triggers watched quality only, and the "
            "failure that fired was operational")
        assert "timeout" in criteria

    def test_it_names_the_rollback(self, entry):
        blob = " ".join(str(v) for v in entry.values()).lower()
        assert "revert" in blob or "rollback" in blob
