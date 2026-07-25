"""Drift guards for the video-podcast pilot (July 2026, tesla + spacex).

What this ships and why it can break quietly:

Apple relaunched video podcasts in Feb 2026 behind an HLS pipeline gated to
a handful of hosting partners, and it ignores ``podcast:alternateEnclosure``
— so a self-hoster's ONLY route into the Apple video player is a plain MP4
``<enclosure>``, published as a SEPARATE show. The network already renders a
1920x1080 long-form MP4 for YouTube every episode and then deletes it, so a
video edition costs one R2 upload and no extra render.

The failure modes these tests pin:

* the enclosure MIME type silently reverting to ``audio/mpeg`` (Apple
  refuses the episode) — including via ``upload_to_r2``'s content-type
  default, which is ``audio/mpeg`` for anything that isn't a ``.mp3``;
* the audio feed being touched (every existing subscriber depends on it);
* GUID instability, which re-notifies every subscriber on a rebuild;
* an empty feed being written (Apple rejects it);
* the R2 keyspace colliding with the audio objects;
* Tesla's ``podcast.video.rss`` falling out of the nightly add-paths glob
  (the youtube_channel_history class of silent-drop bug);
* the config block being silently dropped by ``_build_nested``.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.config import VideoPodcastConfig, load_config  # noqa: E402
from engine.summaries_io import load_summaries, upsert_video  # noqa: E402
from engine.video_feed import (  # noqa: E402
    VIDEO_ENCLOSURE_TYPE,
    _enclosure_length,
    _records_with_video,
    build_video_feed_for_show,
    upload_episode_video,
    video_feed_filename,
    video_r2_key,
)

PILOT_SHOWS = ("tesla", "spacex")


def _cfg(slug: str):
    return load_config(ROOT / "shows" / f"{slug}.yaml")


# ---------------------------------------------------------------------------
# Config wiring
# ---------------------------------------------------------------------------

class TestConfigWiring:
    def test_pilot_shows_are_exactly_tesla_and_spacex(self):
        """Pins the blast radius. A third show turning this on means a
        third Apple submission + a third R2 video keyspace — deliberate,
        never incidental."""
        enabled = []
        for path in sorted((ROOT / "shows").glob("*.yaml")):
            if path.stem.startswith("_") or path.stem in {
                    "network_meta", "pronunciation_map",
                    "translation_overrides", "scaffold_pending"}:
                continue
            try:
                cfg = load_config(path)
            except Exception:  # noqa: BLE001 — non-show yaml
                continue
            if cfg.video_podcast.enabled:
                enabled.append(path.stem)
        assert sorted(enabled) == sorted(PILOT_SHOWS), (
            f"video_podcast.enabled set is {sorted(enabled)}")

    def test_network_default_is_off(self):
        """A newly scaffolded show must not inherit video publishing —
        the multilingual `enabled: true` default did exactly that and
        silently switched on all four languages for env_intel."""
        defaults = yaml.safe_load(
            (ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert defaults["video_podcast"]["enabled"] is False

    def test_yaml_keys_are_all_declared_on_the_dataclass(self):
        """_build_nested drops undeclared keys (loudly, but it still drops
        them — the Tesla smart-Shorts threshold ran wrong for a month)."""
        declared = set(VideoPodcastConfig.__dataclass_fields__)
        defaults = yaml.safe_load(
            (ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert set(defaults["video_podcast"]) <= declared
        for slug in PILOT_SHOWS:
            raw = yaml.safe_load(
                (ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            assert set(raw.get("video_podcast") or {}) <= declared, slug

    def test_pilot_shows_host_on_r2(self):
        """Without R2 there is nowhere to serve a 200 MB enclosure from —
        and R2's zero egress is the only reason self-hosting video is
        economically viable at all."""
        for slug in PILOT_SHOWS:
            assert _cfg(slug).storage.provider == "r2", slug

    def test_pilot_shows_publish_long_form(self):
        """The video episode IS the YouTube long-form render. A show with
        publish_long_form off would produce a permanently empty feed."""
        for slug in PILOT_SHOWS:
            assert _cfg(slug).youtube.enabled, slug
            assert _cfg(slug).youtube.publish_long_form, slug


# ---------------------------------------------------------------------------
# Naming / keyspace
# ---------------------------------------------------------------------------

class TestNamingAndKeyspace:
    def test_video_feed_filename(self):
        assert video_feed_filename("spacex_podcast.rss") == "spacex_podcast.video.rss"
        assert video_feed_filename("podcast.rss") == "podcast.video.rss"
        assert video_feed_filename("weird") == "weird.video.rss"

    def test_video_feed_never_collides_with_the_audio_feed(self):
        """The audio feed is the one every existing subscriber polls."""
        for slug in PILOT_SHOWS:
            cfg = _cfg(slug)
            audio = cfg.publishing.rss_file
            video = cfg.video_podcast.rss_file or video_feed_filename(audio)
            assert video != audio, slug
            assert (ROOT / audio).exists(), f"{slug}: audio feed missing"

    def test_r2_key_is_outside_the_audio_keyspace(self):
        """Audio objects live at ``<slug>/<name>.mp3`` and are referenced by
        every published enclosure. Video gets its own prefix so a storage
        lifecycle rule can expire video without touching audio."""
        key = video_r2_key("video", "tesla", "Tesla_Ep545.mp4")
        assert key == "video/tesla/Tesla_Ep545.mp4"
        assert not key.startswith("tesla/")

    def test_r2_prefix_is_stripped_of_stray_slashes(self):
        assert video_r2_key("/video/", "spacex", "a.mp4") == "video/spacex/a.mp4"


# ---------------------------------------------------------------------------
# Feed contents
# ---------------------------------------------------------------------------

@pytest.fixture
def video_repo(tmp_path):
    """A throwaway repo root with spacex summaries carrying video tracks."""
    dest = tmp_path / "digests" / "spacex"
    dest.mkdir(parents=True)
    src = ROOT / "digests" / "spacex" / "summaries_spacex.json"
    shutil.copy(src, dest / "summaries_spacex.json")
    return tmp_path


def _attach_tracks(repo: Path, count: int = 3):
    path = repo / "digests" / "spacex" / "summaries_spacex.json"
    _w, recs = load_summaries(path)
    nums = [r.get("episode_num") for r in recs[:count]]
    for n in nums:
        upsert_video(path, n, {
            "url": f"https://audio.nerranetwork.com/video/spacex/Ep{n:03d}.mp4",
            "bytes": 187_432_100,
            "filename": f"Ep{n:03d}.mp4",
            "duration_sec": 742.5,
        })
    return nums


class TestFeedBuild:
    def test_no_tracks_writes_no_feed(self, video_repo):
        """Apple rejects an empty feed — never write one."""
        assert build_video_feed_for_show(_cfg("spacex"), video_repo) is None
        assert not list(video_repo.glob("*.rss"))

    def test_disabled_show_is_a_clean_no_op(self, video_repo):
        assert build_video_feed_for_show(_cfg("omni_view"), video_repo) is None

    def test_enclosures_are_video_mp4(self, video_repo):
        """THE load-bearing assertion. audio/mpeg on an MP4 makes Apple
        refuse the episode, and the type is hardcoded to audio/mpeg in
        three places in engine/publisher.py — this feed must not inherit
        that."""
        _attach_tracks(video_repo)
        out, count = build_video_feed_for_show(_cfg("spacex"), video_repo)
        xml = out.read_text(encoding="utf-8")
        assert count == 3
        assert xml.count(f'type="{VIDEO_ENCLOSURE_TYPE}"') == 3
        assert "audio/mpeg" not in xml

    def test_guids_are_deterministic_and_namespaced(self, video_repo):
        """An unstable GUID re-notifies every subscriber on each rebuild
        (publisher.py's GUIDs carry %H%M%S%f — do not copy that here), and
        an un-namespaced one could collide with the audio feed's."""
        nums = _attach_tracks(video_repo)
        out, _ = build_video_feed_for_show(_cfg("spacex"), video_repo)
        first = out.read_text(encoding="utf-8")
        assert f"spacex-video-ep{nums[0]:03d}-" in first
        out.unlink()
        build_video_feed_for_show(_cfg("spacex"), video_repo)
        import re
        guids = re.findall(r"<guid[^>]*>([^<]+)</guid>", out.read_text(encoding="utf-8"))
        assert guids == re.findall(r"<guid[^>]*>([^<]+)</guid>", first)

    def test_rebuild_is_byte_identical(self, video_repo):
        """Churn suppression: a nightly rebuild with no new episode must
        not produce a commit (the language feeds were generating ~35-42
        pure-churn commits a day before this)."""
        _attach_tracks(video_repo)
        out, _ = build_video_feed_for_show(_cfg("spacex"), video_repo)
        before = out.read_bytes()
        build_video_feed_for_show(_cfg("spacex"), video_repo)
        assert out.read_bytes() == before

    def test_newest_episode_first(self, video_repo):
        nums = _attach_tracks(video_repo)
        out, _ = build_video_feed_for_show(_cfg("spacex"), video_repo)
        import re
        eps = [int(m) for m in re.findall(
            r"<itunes:episode>(\d+)</itunes:episode>", out.read_text(encoding="utf-8"))]
        assert eps == sorted(nums, reverse=True)

    def test_channel_title_is_distinguishable_from_the_audio_show(self, video_repo):
        """Apple lists the audio and video editions side by side."""
        _attach_tracks(video_repo)
        out, _ = build_video_feed_for_show(_cfg("spacex"), video_repo)
        assert "<title>SpaceX Daily (Video)</title>" in out.read_text(encoding="utf-8")

    def test_enclosure_urls_are_not_op3_prefixed(self, video_repo):
        """OP3 is an audio-download analytics redirector, not a video CDN.
        Video play counts come from Apple Podcasts Connect."""
        _attach_tracks(video_repo)
        out, _ = build_video_feed_for_show(_cfg("spacex"), video_repo)
        assert "op3.dev" not in out.read_text(encoding="utf-8")

    def test_max_episodes_bounds_the_feed(self, video_repo):
        _attach_tracks(video_repo, count=5)
        cfg = _cfg("spacex")
        cfg.video_podcast.max_episodes = 2
        out, count = build_video_feed_for_show(cfg, video_repo)
        assert count == 2

    def test_audio_feed_is_never_written(self, video_repo):
        _attach_tracks(video_repo)
        build_video_feed_for_show(_cfg("spacex"), video_repo)
        assert not (video_repo / "spacex_podcast.rss").exists()


class TestEnclosureLength:
    def test_exact_bytes_win(self):
        assert _enclosure_length({"bytes": 123, "duration_sec": 900}) == "123"

    def test_falls_back_to_a_duration_estimate(self):
        """Advisory only — clients re-check on GET — but it must be a video
        scale estimate, not the audio one (~30 KB/s), or the number is off
        by ~8x."""
        assert int(_enclosure_length({"duration_sec": 100})) == 25_000_000

    def test_unknown_is_zero_not_a_crash(self):
        assert _enclosure_length({}) == "0"
        assert _enclosure_length({"bytes": "junk", "duration_sec": "junk"}) == "0"

    def test_records_without_a_url_are_ignored(self):
        recs = [{"episode_num": 2, "video": {"bytes": 1}},
                {"episode_num": 1, "video": {"url": "https://x/a.mp4"}},
                {"episode_num": 3}]
        assert [r["episode_num"] for r in _records_with_video(recs, 10)] == [1]


# ---------------------------------------------------------------------------
# Upload contract
# ---------------------------------------------------------------------------

class TestUploadContract:
    def test_disabled_show_never_uploads(self, tmp_path):
        mp4 = tmp_path / "x.mp4"
        mp4.write_bytes(b"0")
        assert upload_episode_video(mp4, _cfg("omni_view")) is None

    def test_missing_file_is_none_not_a_crash(self, tmp_path):
        assert upload_episode_video(tmp_path / "nope.mp4", _cfg("spacex")) is None

    def test_missing_credentials_degrade_to_none(self, tmp_path, monkeypatch):
        """A missing secret must cost the video episode, never the audio
        publish."""
        mp4 = tmp_path / "x.mp4"
        mp4.write_bytes(b"0")
        for var in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            monkeypatch.delenv(var, raising=False)
        assert upload_episode_video(mp4, _cfg("spacex")) is None

    def test_upload_passes_the_video_content_type(self, tmp_path, monkeypatch):
        """upload_to_r2 defaults non-.mp3 files to application/octet-stream
        and .mp3 to audio/mpeg — neither is servable to Apple as video, so
        the caller MUST pass content_type explicitly."""
        mp4 = tmp_path / "SpaceX_Ep044.mp4"
        mp4.write_bytes(b"0" * 1024)
        for var, val in (("R2_ENDPOINT_URL", "https://r2.example"),
                         ("R2_ACCESS_KEY_ID", "k"),
                         ("R2_SECRET_ACCESS_KEY", "s")):
            monkeypatch.setenv(var, val)

        captured = {}

        def _fake_upload(path, key, **kwargs):
            captured["key"] = key
            captured.update(kwargs)
            return f"https://audio.nerranetwork.com/{key}"

        import engine.storage
        monkeypatch.setattr(engine.storage, "upload_to_r2", _fake_upload)

        track = upload_episode_video(mp4, _cfg("spacex"))
        assert track is not None
        assert captured["content_type"] == VIDEO_ENCLOSURE_TYPE
        assert captured["key"] == "video/spacex/SpaceX_Ep044.mp4"
        assert track["bytes"] == 1024
        assert track["url"].endswith("/video/spacex/SpaceX_Ep044.mp4")

    def test_upload_failure_is_swallowed(self, tmp_path, monkeypatch):
        mp4 = tmp_path / "x.mp4"
        mp4.write_bytes(b"0")
        for var, val in (("R2_ENDPOINT_URL", "https://r2.example"),
                         ("R2_ACCESS_KEY_ID", "k"),
                         ("R2_SECRET_ACCESS_KEY", "s")):
            monkeypatch.setenv(var, val)

        def _boom(*a, **k):
            raise RuntimeError("R2 down")

        import engine.storage
        monkeypatch.setattr(engine.storage, "upload_to_r2", _boom)
        assert upload_episode_video(mp4, _cfg("spacex")) is None


class TestSummariesUpsert:
    def test_upsert_video_attaches_to_the_right_episode(self, tmp_path):
        path = tmp_path / "s.json"
        path.write_text(json.dumps({"podcast": "x", "summaries": [
            {"episode_num": 2, "content": "b"},
            {"episode_num": 1, "content": "a"},
        ]}), encoding="utf-8")
        assert upsert_video(path, 1, {"url": "https://x/1.mp4"}) is True
        _w, recs = load_summaries(path)
        assert recs[1]["video"]["url"] == "https://x/1.mp4"
        assert "video" not in recs[0]

    def test_unknown_episode_returns_false(self, tmp_path):
        path = tmp_path / "s.json"
        path.write_text(json.dumps({"podcast": "x", "summaries": []}),
                        encoding="utf-8")
        assert upsert_video(path, 9, {"url": "https://x/9.mp4"}) is False


# ---------------------------------------------------------------------------
# Pipeline + workflow wiring
# ---------------------------------------------------------------------------

class TestPipelineWiring:
    RUN_SHOW = (ROOT / "run_show.py").read_text(encoding="utf-8")

    def test_upload_happens_before_the_mp4_is_deleted(self):
        """_publish_youtube unlinks the long-form MP4 at the end of the
        function. The upload must be upstream of that or there is nothing
        left to host."""
        upload_at = self.RUN_SHOW.index("upload_episode_video(long_video_path")
        unlink_at = self.RUN_SHOW.index("long_video_path.unlink()")
        assert upload_at < unlink_at

    def test_upload_happens_before_the_youtube_upload(self):
        """They are independent products built from one asset: a YouTube
        API failure must not also cost the video-podcast episode."""
        upload_at = self.RUN_SHOW.index("upload_episode_video(long_video_path")
        yt_at = self.RUN_SHOW.index("upload = upload_video(")
        assert upload_at < yt_at

    def test_a_policy_long_form_skip_is_announced(self):
        """The video episode is a by-product of the long-form render, so a
        shorts-only tier silently stops the feed. That must be loud."""
        assert "video_podcast_skipped" in self.RUN_SHOW
        assert "::warning::%s: video podcast is enabled" in self.RUN_SHOW

    def test_feed_rebuild_is_wired_after_the_summaries_save(self):
        """The feed is built FROM the summaries record, so the upsert and
        the rebuild must both follow save_summary_to_github_pages."""
        save_at = self.RUN_SHOW.index("save_summary_to_github_pages(\n")
        assert self.RUN_SHOW.index("build_video_feed_for_show") > save_at
        assert self.RUN_SHOW.index("upsert_video") > save_at

    def test_video_step_cannot_break_the_audio_publish(self):
        block = self.RUN_SHOW[self.RUN_SHOW.index("if config.video_podcast.enabled:\n        try:"):]
        assert "except Exception as exc:  # noqa: BLE001 — never block the publish" in block[:1200]


class TestWorkflowWiring:
    NIGHTLY = (ROOT / ".github" / "workflows"
               / "nightly-maintenance.yml").read_text(encoding="utf-8")

    def test_nightly_rebuilds_video_feeds(self):
        assert "scripts/build_video_feeds.py --all" in self.NIGHTLY

    def test_tesla_video_feed_is_inside_the_add_paths_glob(self):
        """Tesla's audio feed is the ROOT podcast.rss, so its video feed is
        podcast.video.rss — which `*_podcast.*.rss` does NOT match. Without
        an explicit glob the file is generated and never committed (the
        youtube_channel_history silent-drop class)."""
        assert "*.video.rss" in self.NIGHTLY
        tesla_feed = video_feed_filename(_cfg("tesla").publishing.rss_file)
        assert tesla_feed == "podcast.video.rss"
        import fnmatch
        assert not fnmatch.fnmatch(tesla_feed, "*_podcast.*.rss")
        assert fnmatch.fnmatch(tesla_feed, "*.video.rss")

    def test_run_show_commit_step_picks_up_the_feed(self):
        run_show_yml = (ROOT / ".github" / "workflows"
                        / "run-show.yml").read_text(encoding="utf-8")
        assert "git add '*.rss'" in run_show_yml

    def test_no_comments_inside_the_add_paths_block(self):
        """add-paths is fed to `git add --pathspec-from-file`, which has no
        comment syntax — a `#` line becomes a pathspec that matches nothing."""
        start = self.NIGHTLY.index("add-paths: |")
        block = self.NIGHTLY[start:start + 2000]
        for line in block.splitlines()[1:]:
            if line.strip() and not line.startswith(" " * 12):
                break
            assert not line.strip().startswith("#"), line
