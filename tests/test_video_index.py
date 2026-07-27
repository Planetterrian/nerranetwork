"""Drift guards for the durable episode-video index (July 2026).

``engine.video_feed`` builds the video podcast feed from each show's
summaries JSON, which ``publisher.save_summary_to_github_pages`` truncates
to 30 records. ``engine.video_index`` is the durable copy that keeps an
episode in the feed after summaries forgets it — without it, every video
episode silently leaves the feed a month after it ships and Apple de-lists
it, while its MP4 stays in R2 forever with nothing pointing at it.

The failure is invisible for the first 30 days, so it is pinned here.
"""

from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytest.importorskip("feedgen", reason="feedgen required to build feeds")

from engine import video_index  # noqa: E402
from engine.config import load_config  # noqa: E402
from engine.summaries_io import load_summaries, save_summaries, upsert_video  # noqa: E402
from engine.video_feed import build_video_feed_for_show  # noqa: E402


@dataclass
class _Episode:
    output_dir: str = "digests/demo"


@dataclass
class _Config:
    slug: str = "demo"
    episode: _Episode = None

    def __post_init__(self):
        self.episode = self.episode or _Episode()


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setattr(video_index, "PROJECT_ROOT", tmp_path)
    return _Config()


def _track(ep: int, size: int = 187_432_100) -> dict:
    return {
        "url": f"https://audio.nerranetwork.com/video/spacex/Ep{ep:03d}.mp4",
        "bytes": size,
        "filename": f"Ep{ep:03d}.mp4",
        "duration_sec": 742.5,
    }


class TestIndexBasics:
    def test_record_then_read_back(self, cfg):
        assert video_index.record_video(
            config=cfg, episode=42, url="https://x/Ep042.mp4",
            bytes=150_000_000, duration_sec=610.0, date="2026-07-15",
            title="Ep 42")
        rows = video_index.indexed_episodes(video_index.index_path(cfg))
        assert rows[42]["bytes"] == 150_000_000
        assert rows[42]["title"] == "Ep 42"

    def test_record_is_idempotent_on_episode(self, cfg):
        for size in (100, 200):
            video_index.record_video(config=cfg, episode=42,
                                     url="https://x/Ep042.mp4", bytes=size)
        data = json.loads(video_index.index_path(cfg).read_text())
        assert len(data["videos"]) == 1
        assert data["videos"][0]["bytes"] == 200

    def test_rows_are_capped_newest_first(self, cfg, monkeypatch):
        monkeypatch.setattr(video_index, "_MAX_ROWS", 3)
        for ep in range(1, 6):
            video_index.record_video(config=cfg, episode=ep,
                                     url=f"https://x/Ep{ep}.mp4", bytes=10)
        data = json.loads(video_index.index_path(cfg).read_text())
        assert [r["episode"] for r in data["videos"]] == [5, 4, 3]

    def test_zero_byte_and_urlless_rows_are_not_publishable(self, cfg):
        """Zero length is the fingerprint of a half-finished upload, and
        Apple's validator flags it."""
        video_index.record_video(config=cfg, episode=1, url="https://x/1.mp4", bytes=0)
        video_index.record_video(config=cfg, episode=2, url="", bytes=99)
        video_index.record_video(config=cfg, episode=3, url="https://x/3.mp4", bytes=99)
        assert sorted(video_index.indexed_episodes(
            video_index.index_path(cfg))) == [3]

    def test_corrupt_index_degrades_to_empty(self, cfg):
        path = video_index.index_path(cfg)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        assert video_index.load_index(path)["videos"] == []

    def test_record_never_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(video_index, "PROJECT_ROOT", tmp_path / "\0bad")
        assert video_index.record_video(
            config=_Config(), episode=1, url="https://x/1.mp4", bytes=1) is False

    def test_index_path_honours_an_alternate_root(self, tmp_path):
        """Callers building a feed for a staged tree must not read the live
        repo's index — that would list episodes the tree doesn't have."""
        other = tmp_path / "elsewhere"
        assert str(video_index.index_path(_Config(), other)).startswith(str(other))


@pytest.fixture
def repo(tmp_path):
    """Throwaway repo root with real spacex summaries, video tracks stripped."""
    dest = tmp_path / "digests" / "spacex"
    dest.mkdir(parents=True)
    out = dest / "summaries_spacex.json"
    shutil.copy(ROOT / "digests" / "spacex" / "summaries_spacex.json", out)
    wrapper, recs = load_summaries(out)
    for rec in recs:
        rec.pop("video", None)
    save_summaries(out, wrapper, recs)
    return tmp_path


def _spacex():
    return load_config(ROOT / "shows" / "spacex.yaml")


class TestFeedSurvivesSummariesTruncation:
    """The regression this module exists for."""

    def test_episode_aged_out_of_summaries_stays_in_the_feed(self, repo):
        config = _spacex()
        summaries = repo / config.publishing.summaries_json
        _w, recs = load_summaries(summaries)
        newest = recs[0]["episode_num"]

        # One episode still in summaries, one only in the durable index —
        # exactly the state a show reaches on day 31.
        upsert_video(summaries, newest, _track(newest))
        video_index.record_video(
            config=config, episode=1, url="https://audio.nerranetwork.com/video/spacex/Ep001.mp4",
            bytes=120_000_000, duration_sec=500.0, date="2026-06-13",
            title="Ep 1: the one summaries forgot", project_root=repo)

        out, count = build_video_feed_for_show(config, repo)
        assert count == 2
        titles = [i.find("title").text
                  for i in ET.parse(out).getroot().find("channel").findall("item")]
        assert "Ep 1: the one summaries forgot" in titles

    def test_summaries_wins_over_the_index_for_the_same_episode(self, repo):
        """The index is machine-owned; summaries carries operator edits."""
        config = _spacex()
        summaries = repo / config.publishing.summaries_json
        _w, recs = load_summaries(summaries)
        newest = recs[0]["episode_num"]
        real_title = recs[0]["episode_title"]

        upsert_video(summaries, newest, _track(newest))
        video_index.record_video(
            config=config, episode=newest, url=_track(newest)["url"],
            bytes=1, title="index-side title", project_root=repo)

        out, count = build_video_feed_for_show(config, repo)
        assert count == 1
        item = ET.parse(out).getroot().find("channel").find("item")
        assert item.find("title").text == real_title
        # And the summaries byte length, not the index's placeholder.
        assert item.find("enclosure").get("length") == str(_track(newest)["bytes"])

    def test_index_only_feed_still_declares_video_mp4(self, repo):
        """An episode recovered from the index must be as valid as any other."""
        config = _spacex()
        video_index.record_video(
            config=config, episode=7, url="https://audio.nerranetwork.com/video/spacex/Ep007.mp4",
            bytes=99_000_000, duration_sec=400.0, date="2026-06-20",
            title="Ep 7", project_root=repo)
        out, count = build_video_feed_for_show(config, repo)
        assert count == 1
        enc = ET.parse(out).getroot().find("channel").find("item").find("enclosure")
        assert enc.get("type") == "video/mp4"
        assert enc.get("length") == "99000000"

    def test_max_episodes_is_now_a_real_knob(self, repo):
        """Before the index, raising max_episodes above 30 did nothing —
        the records simply weren't in summaries to find."""
        config = _spacex()
        for ep in range(1, 41):
            video_index.record_video(
                config=config, episode=ep,
                url=f"https://audio.nerranetwork.com/video/spacex/Ep{ep:03d}.mp4",
                bytes=100_000_000, date="2026-06-20", title=f"Ep {ep}",
                project_root=repo)
        config.video_podcast.max_episodes = 35
        _out, count = build_video_feed_for_show(config, repo)
        assert count == 35, "max_episodes should no longer be capped at 30"


class TestBackfillIdempotency:
    """The smoke run re-rendered an episode the live pipeline had already
    published, because the gate consulted only the durable index — which was
    empty on first run. Sixteen wasted minutes, and it overwrote a good R2
    object with a different render (the scene library moves, so a re-render
    is never byte-identical), briefly leaving the feed's advertised length
    disagreeing with what the CDN served."""

    def test_an_already_published_episode_is_adopted_not_re_rendered(
            self, repo, monkeypatch):
        import engine.video_backfill as vb

        config = _spacex()
        monkeypatch.setattr(vb, "PROJECT_ROOT", repo)
        summaries = repo / config.publishing.summaries_json
        _w, recs = load_summaries(summaries)
        ep = recs[0]["episode_num"]
        upsert_video(summaries, ep, _track(ep))

        def _boom(*a, **k):  # noqa: ANN001 — must never be reached
            raise AssertionError("re-rendered an episode that already had video")

        monkeypatch.setattr("engine.video.build_long_form_video", _boom)
        monkeypatch.setattr(video_index, "PROJECT_ROOT", repo)

        result = vb.backfill_episode_video(config, ep)
        assert result["status"] == "adopted"
        # And the point of adopting: it now survives summaries truncation.
        assert ep in video_index.indexed_episodes(
            video_index.index_path(config, repo))

    def test_force_still_re_renders(self, repo, monkeypatch):
        import engine.video_backfill as vb

        config = _spacex()
        monkeypatch.setattr(vb, "PROJECT_ROOT", repo)
        summaries = repo / config.publishing.summaries_json
        _w, recs = load_summaries(summaries)
        ep = recs[0]["episode_num"]
        upsert_video(summaries, ep, _track(ep))
        monkeypatch.setattr(video_index, "PROJECT_ROOT", repo)

        calls = []
        monkeypatch.setattr(vb, "_download_audio",
                            lambda *a, **k: calls.append(1) or None)
        result = vb.backfill_episode_video(config, ep, force=True)
        assert calls, "--force must bypass the idempotency gate"
        assert result["status"] == "no_audio"  # got past the gate, then stubbed
