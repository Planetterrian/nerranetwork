"""Drift guards for the June 10 2026 workflow efficiency pass
(docs/workflow_review_2026_06_10.md)."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_WF = _ROOT / ".github" / "workflows"


def _read(name: str) -> str:
    return (_WF / name).read_text(encoding="utf-8")


class TestRunShowWorkflow:
    def test_shallow_checkouts(self):
        """The repo carries 2.2 GB of legacy MP3 history (landmine #1);
        fetch-depth 0 cost minutes + GBs on every one of ~13 daily jobs."""
        wf = _read("run-show.yml")
        assert "fetch-depth: 0" not in wf
        assert wf.count("fetch-depth: 1") >= 2  # run + finalize

    def test_whisper_model_cached(self):
        wf = _read("run-show.yml")
        assert "~/.cache/huggingface" in wf
        assert "whisper-faster-base" in wf

    def test_secrets_as_env_not_dotenv_file(self):
        """Secrets go to the pipeline step's env block — no .env heredoc
        on disk, no indentation-sensitive sed hack."""
        wf = _read("run-show.yml")
        assert "ENVEOF" not in wf
        assert "Create .env" not in wf
        assert "GROK_API_KEY: ${{ secrets.GROK_API_KEY }}" in wf
        assert "BUTTONDOWN_API_KEY: ${{ secrets.BUTTONDOWN_API_KEY }}" in wf

    def test_smoke_tests_include_quality_pass_guards(self):
        wf = _read("run-show.yml")
        for t in ("test_chapters.py", "test_tesla_quality_pass.py",
                  "test_four_show_quality_pass.py",
                  "test_russian_shows_quality_pass.py"):
            assert t in wf, f"smoke suite must include {t}"

    def test_finalize_builds_gallery_manifest(self):
        wf = _read("run-show.yml")
        assert "build_gallery_manifest.py" in wf
        assert "R2_GALLERY_BUCKET" in wf


class TestGalleryWorkflowConsolidated:
    def test_no_per_show_workflow_run_trigger(self):
        """A fresh runner per Run Podcast Show completion (~13/day) was
        replaced by the finalize-job rebuild + nightly safety rebuild."""
        wf = _read("build-gallery-manifest.yml")
        assert "workflow_run:" not in wf
        assert "workflow_dispatch:" in wf


class TestNightlyShallow:
    def test_nightly_shallow_checkout(self):
        wf = _read("nightly-maintenance.yml")
        assert "fetch-depth: 1" in wf
        assert "fetch-depth: 0" not in wf


class TestAuditTargetsFollowYaml:
    def test_review_uses_config_floor(self):
        src = (_ROOT / "review_episodes.py").read_text(encoding="utf-8")
        assert "_config_min_words" in src
        assert '_config_min_words(ep.show_slug) or info["min_tts_words"]' in src


class TestTeslaXAccounts:
    def test_teslaaibot_removed(self):
        import yaml
        cfg = yaml.safe_load((_ROOT / "shows" / "tesla.yaml").read_text(encoding="utf-8"))
        handles = [a["handle"] for a in cfg["x_accounts"]]
        assert "TeslaAIBot" not in handles


class TestBackfillSkipsMetaYamls:
    def test_meta_yaml_skip(self):
        src = (_ROOT / "scripts" / "backfill_content_lake.py").read_text(encoding="utf-8")
        assert "_NON_SHOW_YAMLS" in src
        assert 'startswith("_")' in src
