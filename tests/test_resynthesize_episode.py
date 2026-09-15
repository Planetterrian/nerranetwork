"""Drift guards for the episode-repair path (Sep 15 2026).

``scripts/resynthesize_episode.py`` re-runs a published episode's
committed script through the same synthesis when the audio that shipped
was not the script (Tesla Ep605). It touches published surfaces, so the
properties that matter are the ones that keep it from doing harm:

* it uploads to the SAME R2 key, or the repair re-points every
  subscriber's enclosure URL;
* it refuses to publish audio the spoken-text gate has not passed, or
  the repair tool becomes another way to ship the defect;
* it names only the derived videos that actually carry the defect. The
  second Ep605 Short opens past the three-minute mark and is clean, and
  the RU/FR dubs are a separate synthesis of the translated script —
  listing either for deletion destroys good videos.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.resynthesize_episode as rs  # noqa: E402

TESLA_YAML = ROOT / "shows" / "tesla.yaml"
EP605 = 605


@pytest.fixture(scope="module")
def tesla_config():
    from engine.config import load_config
    return load_config(TESLA_YAML)


@pytest.fixture(scope="module")
def ep605(tesla_config):
    art = rs.resolve_artifacts(tesla_config, EP605)
    if not art.script_path.exists():
        pytest.skip("Ep605 artifacts not committed")
    return art


# ---------------------------------------------------------------------------
# The enclosure URL must not move
# ---------------------------------------------------------------------------

class TestSameR2Key:
    def test_key_is_slug_plus_filename(self, ep605):
        assert ep605.r2_key == f"tesla/{ep605.final_mp3.name}"

    def test_key_matches_engine_storage(self, ep605, tesla_config):
        """``upload_episode`` builds the key itself; if the two ever
        disagree the repair silently writes a second object and the feed
        keeps serving the broken one."""
        src = (ROOT / "engine" / "storage.py").read_text(encoding="utf-8")
        assert 'remote_key = f"{config.slug}/{local_path.name}"' in src, (
            "engine.storage.upload_episode changed its key shape — "
            "EpisodeArtifacts.r2_key must follow or the repair misses."
        )

    def test_key_matches_the_published_enclosure(self, ep605):
        """The whole point: the repaired object lands where the feed
        already points."""
        rss = (ROOT / "podcast.rss").read_text(encoding="utf-8")
        assert ep605.final_mp3.name in rss
        assert f"/tesla/{ep605.final_mp3.name}" in rss


# ---------------------------------------------------------------------------
# Artifact resolution
# ---------------------------------------------------------------------------

class TestResolveArtifacts:
    def test_resolves_ep605(self, ep605):
        assert ep605.episode_num == EP605
        assert ep605.date_str == "20260914"
        assert ep605.script_path.name.endswith("_tts.txt")
        assert ep605.final_mp3.suffix == ".mp3"
        assert ep605.chapters_path.name == "chapters_ep605.json"

    def test_missing_episode_is_a_clear_error(self, tesla_config):
        with pytest.raises(FileNotFoundError, match="No committed script"):
            rs.resolve_artifacts(tesla_config, 99999)

    def test_missing_episode_exits_without_a_traceback(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv",
                            ["x", "--show", "tesla", "--episode", "99999"])
        assert rs.main() == 1


# ---------------------------------------------------------------------------
# The safety property: unverified audio is never published
# ---------------------------------------------------------------------------

class TestGateRefusal:
    def _patch(self, monkeypatch, ep605, transcript_for):
        uploaded = []
        monkeypatch.setenv("GROK_API_KEY", "test-key")
        monkeypatch.setattr(rs, "synthesize_script",
                            lambda *a, **k: Path(a[2]).write_bytes(b"\xff\xfb\x90"))

        class _Result:
            txt_path = transcript_for.transcript_txt
            json_path = transcript_for.transcript_json
            text = ""

        monkeypatch.setattr(rs, "transcribe", lambda *a, **k: _Result())

        import engine.storage as storage
        monkeypatch.setattr(storage, "upload_episode",
                            lambda *a, **k: uploaded.append(a) or "http://x")
        return uploaded

    def test_failing_gate_aborts_before_upload(self, monkeypatch, ep605):
        """Ep605's committed transcript fails the gate. Handing the tool
        that transcript as the 'new' audio must stop the run."""
        uploaded = self._patch(monkeypatch, ep605, ep605)
        monkeypatch.setattr(sys, "argv", [
            "x", "--show", "tesla", "--episode", str(EP605),
            "--apply", "--retries", "0",
        ])
        assert rs.main() == 1
        assert uploaded == [], "aborted run must not upload"

    def test_missing_transcript_aborts(self, monkeypatch, ep605):
        uploaded = self._patch(monkeypatch, ep605, ep605)
        monkeypatch.setattr(rs, "transcribe", lambda *a, **k: None)
        monkeypatch.setattr(sys, "argv", [
            "x", "--show", "tesla", "--episode", str(EP605), "--apply",
        ])
        assert rs.main() == 1
        assert uploaded == []

    def test_no_api_key_aborts(self, monkeypatch, ep605):
        monkeypatch.delenv("GROK_API_KEY", raising=False)
        monkeypatch.delenv("XAI_API_KEY", raising=False)
        monkeypatch.setattr(sys, "argv", [
            "x", "--show", "tesla", "--episode", str(EP605), "--apply",
        ])
        assert rs.main() == 1


class TestDryRunWritesNothing:
    def test_dry_run_touches_no_file(self, monkeypatch, ep605):
        watched = [ep605.transcript_txt, ep605.transcript_json,
                   ep605.chapters_path, ROOT / "podcast.rss"]
        before = {p: p.stat().st_mtime_ns for p in watched if p.exists()}

        def _boom(*a, **k):
            raise AssertionError("a dry run must not synthesize")

        monkeypatch.setattr(rs, "synthesize_script", _boom)
        monkeypatch.setattr(sys, "argv",
                            ["x", "--show", "tesla", "--episode", str(EP605)])
        assert rs.main() == 0
        for path, mtime in before.items():
            assert path.stat().st_mtime_ns == mtime, f"{path.name} was written"


# ---------------------------------------------------------------------------
# Which surfaces are actually affected
# ---------------------------------------------------------------------------

class TestDefectWindow:
    def test_ep605_window_covers_the_opening(self, ep605):
        window = rs.defect_window(
            ep605.script_path.read_text(encoding="utf-8"), ep605.transcript_json)
        assert window is not None
        start, end = window
        assert start < 20.0, "the leak is at the top of the episode"
        assert 25.0 < end < 60.0, f"unexpected defect end {end}"


class TestFollowups:
    def _notes(self, ep605, tesla_config):
        return rs.manual_followups(ep605, tesla_config, window=(0.0, 34.7))

    def test_long_form_is_flagged(self, ep605, tesla_config):
        notes = " ".join(self._notes(ep605, tesla_config))
        assert "J9ENRcR65sc" in notes and "delete + re-upload" in notes

    def test_hook_short_flagged_and_late_short_kept(self, ep605, tesla_config):
        notes = self._notes(ep605, tesla_config)
        hook = [n for n in notes if "Cfi81jyH6Xc" in n]
        late = [n for n in notes if "qARzIvraPTw" in n]
        assert hook and "delete + re-upload" in hook[0]
        assert late and late[0].startswith("YouTube: KEEP"), (
            "the second Short opens past the defect; deleting it is pure loss"
        )

    def test_dub_videos_are_never_listed_for_deletion(self, ep605, tesla_config):
        """RU/FR dubs are a separate synthesis of the translated script,
        so an English-audio defect cannot reach them."""
        for note in self._notes(ep605, tesla_config):
            if "@NerraRU" in note or "@NerraFR" in note:
                assert "UNAFFECTED" in note and "Do not delete" in note
                assert "delete + re-upload" not in note

    def test_apple_video_and_daily_edition_are_named(self, ep605, tesla_config):
        notes = " ".join(self._notes(ep605, tesla_config))
        assert "Apple video feed" in notes
        assert "Nerra Daily" in notes


# ---------------------------------------------------------------------------
# Chapters and the feed item carry over unchanged
# ---------------------------------------------------------------------------

class TestChaptersReproduce:
    def test_titles_match_the_published_ones(self, ep605, tesla_config):
        """Only timestamps may move in a repair. Titles come from the
        same script and digest, so they must come out identical."""
        chapters = rs.rebuild_chapters(
            tesla_config, ep605,
            ep605.script_path.read_text(encoding="utf-8"),
            audio_duration=490.0)
        assert chapters, "Ep605 has chapters"
        published = rs.published_chapter_titles(ep605.chapters_path)
        assert [c.title for c in chapters] == published

    def test_timestamps_follow_the_new_duration(self, ep605, tesla_config):
        script = ep605.script_path.read_text(encoding="utf-8")
        short = rs.rebuild_chapters(tesla_config, ep605, script, 400.0)
        long_ = rs.rebuild_chapters(tesla_config, ep605, script, 600.0)
        assert short[-1].endTime == pytest.approx(400.0, abs=0.5)
        assert long_[-1].endTime == pytest.approx(600.0, abs=0.5)


class TestPublishedItem:
    def test_reads_title_and_description(self, tesla_config):
        item = rs.read_published_item(ROOT / "podcast.rss", EP605)
        assert item is not None, "Ep605 is in the feed"
        assert item["title"], "a repair reuses the published title verbatim"
        assert "605" in item["title"] or "4680" in item["title"]

    def test_absent_episode_returns_none(self):
        assert rs.read_published_item(ROOT / "podcast.rss", 99999) is None


# ---------------------------------------------------------------------------
# Shows the tool must refuse rather than approximate
# ---------------------------------------------------------------------------

class TestRefusals:
    def test_section_tts_show_is_refused(self, tesla_config, tmp_path):
        object.__setattr__(tesla_config.tts, "use_section_tts", True)
        try:
            with pytest.raises(NotImplementedError, match="use_section_tts"):
                rs.synthesize_script(tesla_config, "hi", tmp_path / "o.mp3", "k")
        finally:
            object.__setattr__(tesla_config.tts, "use_section_tts", False)

    def test_unlabeled_dialogue_script_is_refused(self, tmp_path):
        from engine.config import load_config
        cfg = load_config(ROOT / "shows" / "dp_pod.yaml")
        if not cfg.tts.dialogue_mode:
            pytest.skip("dp_pod is no longer a dialogue show")
        with pytest.raises(ValueError, match="speaker labels"):
            rs.synthesize_script(cfg, "No labels here.", tmp_path / "o.mp3", "k")


# ---------------------------------------------------------------------------
# Workflow wiring
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def wf():
    import yaml
    path = ROOT / ".github" / "workflows" / "resynthesize-episode.yml"
    assert path.exists(), "the repair workflow is how this is actually run"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class TestWorkflow:
    def test_dry_run_is_the_default(self, wf):
        inputs = wf[True]["workflow_dispatch"]["inputs"]
        assert inputs["apply"]["default"] is False

    def test_commit_only_on_a_successful_apply(self, wf):
        step = wf["jobs"]["resynthesize"]["steps"][-1]
        assert "safe-commit-push" in step["uses"]
        cond = step["if"]
        assert "inputs.apply" in cond
        assert "resynth_status == '0'" in cond, (
            "a failed repair must not commit artifacts describing audio "
            "that was never published"
        )

    def test_no_mp3_is_ever_committed(self, wf):
        step = wf["jobs"]["resynthesize"]["steps"][-1]
        assert ".mp3" not in step["with"]["add-paths"], (
            "episode audio never enters git history (landmine #1)"
        )

    def test_ffmpeg_and_credentials_present(self, wf):
        steps = wf["jobs"]["resynthesize"]["steps"]
        assert any("ffmpeg" in (s.get("name") or "").lower() for s in steps)
        env = next(s for s in steps if s.get("name") == "Re-synthesize")["env"]
        for key in ("GROK_API_KEY", "R2_ENDPOINT_URL",
                    "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            assert key in env
