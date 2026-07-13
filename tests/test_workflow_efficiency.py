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

    def test_aggregate_exclusion_leaves_clean_tree(self):
        """Per-show commits exclude the cross-show aggregates, but must use
        `git checkout HEAD --` (reverts index + working tree), NOT `git reset
        HEAD --` (unstages only). `reset` leaves the regenerated aggregates
        dirty, which makes the push-retry `git pull --rebase` abort with
        'cannot pull with rebase: you have unstaged changes' and sends shows
        to recovery branches (the June 28 2026 regression).

        July 2026: the restore must also be PER-FILE — a single multi-path
        checkout is all-or-nothing (any one path missing from HEAD rejects
        the whole pathspec, the 2>/dev/null hides it, and the dirty tree
        re-triggers the same stranding mode)."""
        wf = _read("run-show.yml")
        assert "for aggregate in blog.rss network.rss blog/index.html" in wf
        assert 'git checkout HEAD -- "$aggregate" 2>/dev/null || true' in wf
        # The buggy all-or-nothing multi-path form must not come back.
        assert "git checkout HEAD -- blog.rss network.rss blog/index.html" not in wf
        # The buggy reset form must not be what excludes the aggregates.
        assert "git reset HEAD -- blog.rss network.rss blog/index.html" not in wf

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


class TestNoEpisodeMediaAtHead:
    """The clone-cost fix holds only while HEAD stays free of episode
    media (landmine #1: 2.2 GB of MP3s live in history; a shallow clone
    still downloads every blob at HEAD)."""

    def test_no_episode_mp3s_tracked(self):
        import subprocess
        out = subprocess.run(
            ["git", "ls-files", "digests/*.mp3", "digests/**/*.mp3",
             "digests/**/*.mp4", "digests/**/*.wav"],
            capture_output=True, text=True, cwd=_ROOT,
        ).stdout.strip()
        assert out == "", f"episode media tracked at HEAD: {out[:200]}"

    def test_no_episode_pngs_tracked(self):
        """youtube_tmp PNG intermediates (thumbnails, end cards, hook
        overlays) grew ~140 MB/month at HEAD because .gitignore covered
        mp4/jpg/srt/ass but not *.png while run-show.yml does
        `git add -A digests/` (landmine #1 regression, June 2026)."""
        import subprocess
        out = subprocess.run(
            ["git", "ls-files", "digests/*/youtube_tmp/*.png"],
            capture_output=True, text=True, cwd=_ROOT,
        ).stdout.strip()
        assert out == "", f"youtube_tmp PNGs tracked at HEAD: {out[:200]}"

    def test_no_thumbnail_variant_jpgs_tracked(self):
        """Thumbnail-variant JPGs (*_thumb_v2/v3.jpg) grew ~200 MB/month at
        HEAD: PR #751 uploads them to R2 but the local temp files were swept
        in by `git add -A digests/` because .gitignore's *_thumb.jpg pattern
        does not match the _thumb_vN suffix (landmine #1 regression, July
        2026 — third instance of the youtube_tmp intermediate class)."""
        import subprocess
        out = subprocess.run(
            ["git", "ls-files", "digests/*/youtube_tmp/*thumb_v*.jpg"],
            capture_output=True, text=True, cwd=_ROOT,
        ).stdout.strip()
        assert out == "", f"thumbnail variants tracked at HEAD: {out[:200]}"

    def test_gitignore_guards_present(self):
        gi = (_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert "digests/**/*.mp3" in gi
        assert "!assets/music/*.mp3" in gi
        assert "digests/*/youtube_tmp/*.png" in gi
        assert "digests/*/youtube_tmp/*_thumb_v*.jpg" in gi
