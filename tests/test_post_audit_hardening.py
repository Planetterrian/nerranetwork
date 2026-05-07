"""Drift guards for fixes shipped in the May 7 2026 audit cycle.

Three pinning tests covering work that's now load-bearing:

  * ``audio.mix_with_music`` raises a clear ``FileNotFoundError`` when
    the voice file is missing / empty, instead of letting a cryptic
    ``Invalid data found when processing input`` ffmpeg error mask
    the upstream TTS failure.

  * ``PipelineMetrics`` preserves the ``podcast_script_word_count`` /
    ``podcast_script_target_words`` counters that ``run_show.py``
    started recording in PR #335. The fields are how post-hoc
    calibration audits validate the per-show ``min_podcast_words``
    targets without grepping workflow logs — silent regressions in
    the metrics serialization would defeat the whole point.

  * The ``Commit and push output`` step in ``.github/workflows/run-show.yml``
    is gated on ``steps.pipeline.outcome == 'success'``. PR #331
    added that guard after the May 7 incident lost a day's commits
    because GitHub Actions' implicit ``success()`` clause skipped the
    commit step when a peripheral regen step failed. Removing this
    guard would silently re-introduce the May 7 failure mode.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# audio.mix_with_music — voice file validation
# ---------------------------------------------------------------------------


class TestMixWithMusicVoiceGuard:

    def test_raises_file_not_found_when_voice_missing(self, tmp_path):
        """The pre-flight guard surfaces missing TTS output as an
        actionable error, instead of letting ffmpeg fail cryptically."""
        from engine.audio import mix_with_music
        voice = tmp_path / "voice.mp3"   # never created
        music = tmp_path / "music.mp3"
        music.write_bytes(b"\x00" * 64)  # exists so we hit the voice gate
        out = tmp_path / "out.mp3"

        with pytest.raises(FileNotFoundError, match="upstream TTS"):
            mix_with_music(voice, music, out)

    def test_raises_file_not_found_when_voice_zero_bytes(self, tmp_path):
        """A 0-byte voice file is what TTS produces on a silent failure
        (e.g. tenacity gave up). The guard catches it before ffmpeg."""
        from engine.audio import mix_with_music
        voice = tmp_path / "voice.mp3"
        voice.write_bytes(b"")
        music = tmp_path / "music.mp3"
        music.write_bytes(b"\x00" * 64)
        out = tmp_path / "out.mp3"

        with pytest.raises(FileNotFoundError, match="missing or empty"):
            mix_with_music(voice, music, out)

    def test_falls_back_to_voice_only_when_music_missing(self, tmp_path):
        """The legacy graceful-fallback for missing music is preserved —
        the new guard only fires for voice failures."""
        from engine.audio import mix_with_music
        voice = tmp_path / "voice.mp3"
        voice.write_bytes(b"\x00" * 1024)  # non-empty
        music = tmp_path / "missing-music.mp3"  # absent
        out = tmp_path / "out.mp3"

        # Should not raise — and ``normalize_voice`` is invoked instead.
        with patch("engine.audio.normalize_voice", return_value=out) as mock_norm:
            result = mix_with_music(voice, music, out)
            assert result == out
            mock_norm.assert_called_once_with(voice, out)


# ---------------------------------------------------------------------------
# metrics.PipelineMetrics — calibration counters preserved through to_dict
# ---------------------------------------------------------------------------


class TestPodcastWordCountMetrics:
    """``run_show.py`` records the actual podcast script word count plus
    the per-show ``min_podcast_words`` target on every run (PR #335).
    These counters are the post-hoc audit signal for whether the May
    2026 Phase-3 recalibration of ``min_podcast_words`` landed cleanly.
    Silent regressions in metrics serialization would erase that signal."""

    def test_word_count_counter_round_trips_through_to_dict(self):
        from engine.metrics import PipelineMetrics
        m = PipelineMetrics(show_slug="tesla", episode_num=466)
        m.record("podcast_script_word_count", 1623)
        m.record("podcast_script_target_words", 1700)

        out = m.to_dict()
        counters = out.get("counters", {})
        assert counters.get("podcast_script_word_count") == 1623
        assert counters.get("podcast_script_target_words") == 1700

    def test_word_count_counter_persists_to_disk(self, tmp_path):
        from engine.metrics import PipelineMetrics
        m = PipelineMetrics(show_slug="tesla", episode_num=466)
        m.record("podcast_script_word_count", 1623)
        m.record("podcast_script_target_words", 1700)
        path = m.save(tmp_path)

        loaded = json.loads(path.read_text(encoding="utf-8"))
        counters = loaded.get("counters", {})
        assert counters.get("podcast_script_word_count") == 1623
        assert counters.get("podcast_script_target_words") == 1700


# ---------------------------------------------------------------------------
# run-show.yml — commit-step pipeline.outcome guard
# ---------------------------------------------------------------------------


def _load_run_show_workflow() -> dict:
    import yaml
    repo_root = Path(__file__).resolve().parent.parent
    path = repo_root / ".github" / "workflows" / "run-show.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class TestCommitStepGuard:
    """PR #331 added ``if: always() && steps.pipeline.outcome == 'success'``
    to the commit-and-push step after the May 7 2026 incident dropped a
    full day's commits. GitHub Actions implicitly prepends ``success()``
    to every ``if:`` clause, so when ``generate_html.py --blogs`` failed
    on a UTF-16 surrogate, the next step (commit) was *also* silently
    skipped — losing every show's digest .md, transcript, and metrics.
    Removing this guard or simplifying the condition would re-introduce
    the original failure mode."""

    def test_commit_step_gates_on_pipeline_outcome(self):
        wf = _load_run_show_workflow()
        # ``on:`` is parsed as a boolean key by PyYAML 6 because YAML
        # spec interprets bare ``on`` as True. The other top-level
        # keys (``jobs``, ``permissions``) come through normally.
        run_job = wf["jobs"]["run"]
        commit_step = next(
            (s for s in run_job["steps"] if s.get("name") == "Commit and push output"),
            None,
        )
        assert commit_step is not None, (
            "'Commit and push output' step missing from run-show.yml"
        )
        guard = commit_step.get("if", "")
        # Must reference pipeline.outcome — the explicit gate that
        # bypasses GitHub Actions' implicit success() short-circuit.
        assert "steps.pipeline.outcome" in guard, (
            f"Commit step lost the pipeline-outcome guard. Guard now: {guard!r}. "
            "See PR #331 — May 7 2026 incident."
        )
        # And ``always()`` must wrap the whole expression so the guard
        # gets a chance to evaluate even after a previous step failed.
        assert "always()" in guard, (
            f"Commit step lost the always() wrapper. Guard now: {guard!r}. "
            "Without it, GitHub Actions implicitly adds success() and the "
            "guard never gets to evaluate after a peripheral failure."
        )

    def test_commit_step_still_respects_skipped_pipelines(self):
        """A skipped pipeline (insufficient articles) must NOT trigger
        a commit. The guard preserves the original ``skipped != 'true'``
        check — losing it would commit empty / partial output."""
        wf = _load_run_show_workflow()
        commit_step = next(
            s for s in wf["jobs"]["run"]["steps"]
            if s.get("name") == "Commit and push output"
        )
        guard = commit_step["if"]
        assert "steps.pipeline.outputs.skipped" in guard
