"""The Age of AI on YouTube: a title bundle, a thumbnail, chapters; the kind
of video recorded; the waveform never silently shipped for a camera episode
(Nov 4 2026 — youtube-8 stage 1 + voices-3's record).

``maybe_publish_youtube`` ("Deliberately minimal") uploaded the feed title
with no title bundle, no thumbnail (the kwarg existed), no chapter block
(the package carried markers and ``_format_chapter_block`` renders one): 27
views across three longs, 1.5% watched. And when an edit carried a camera
``video_url`` whose HEAD was not 200 it set ``render_locally`` and shipped
the WAVEFORM in silence. These pin the packaging on a fixture upload and
the refusal on a missing camera cut.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT))

import publish_episode as pe  # noqa: E402
from shows import get_show  # noqa: E402
from engine.titles import YOUTUBE_TITLE_MAX  # noqa: E402

PUB = (V / "publish_episode.py").read_text(encoding="utf-8")
GUEST = "Thor Hesselberg"
THESIS = ("A recruitment founder counters AI deepfakes flooding hiring pipelines by "
          "building portable verified credentials.")
TRANSCRIPT = ("[00:01] Mira: Thor, the fifty applicants — where did it start?\n"
              "[00:20] Thor: Half of the eight shortlisted were avatars. So we built "
              "verified credentials, employer confirmed.\n")
CHAPTERS = [{"start": 0, "title": "The fifty applicants"},
            {"start": 600, "title": "Verified credentials"}]


def _cfg(**over):
    yt = dict(enabled=True, channel="en", tags=["AI", "hiring"], category_id=28,
              privacy_status="public", podcast_playlist_id="")
    yt.update(over)
    return SimpleNamespace(name="The Age of AI", youtube=SimpleNamespace(**yt))


class _Resp:
    def __init__(self, data: bytes):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, n):
        yield self.data


@pytest.fixture
def harness(tmp_path, monkeypatch):
    """The real show with its index in tmp; YouTube, Grok and the network
    replaced by fakes that record what they were handed."""
    import engine.youtube as yt_mod
    import engine.youtube_titles as titles_mod
    show = replace(get_show("age_of_ai"), audio_subdir=str(tmp_path / "idx"))
    calls: dict = {"uploads": [], "notified": [], "bundle": []}

    def fake_upload(path, **kw):
        calls["uploads"].append({**kw, "video_path": Path(path),
                                 "video_bytes": Path(path).stat().st_size,
                                 "thumbnail_exists": bool(kw.get("thumbnail_path"))
                                 and Path(kw["thumbnail_path"]).exists()})
        return SimpleNamespace(video_id="vid123")

    def fake_bundle(**kw):
        calls["bundle"].append(kw)
        return {"titles": ["Why Hiring Broke", "Half the Shortlist Were Avatars"],
                "punch_text": "FAKE CVS", "short_titles": []}

    monkeypatch.setattr(yt_mod, "get_channel_credentials_from_env", lambda ch: object())
    monkeypatch.setattr(yt_mod, "upload_video", fake_upload)
    monkeypatch.setattr(yt_mod, "add_video_to_playlist", lambda *a, **k: None)
    monkeypatch.setattr(titles_mod, "generate_title_bundle", fake_bundle)
    monkeypatch.setattr(pe, "notify_operator", lambda text, **k: calls["notified"].append(text))
    monkeypatch.setattr(pe.requests, "get", lambda url, **kw: _Resp(b"\0" * 4096))
    calls["head"] = {"status": 200}
    monkeypatch.setattr(pe, "_head_status", lambda url: calls["head"]["status"])
    pkg = {"edit_transcript": TRANSCRIPT, "transcript_cleaned": TRANSCRIPT,
           "chapter_markers": CHAPTERS, "guest_video_ok": None}
    app = {"name": GUEST, "title": "Founder", "organization": "WorkID"}
    return SimpleNamespace(show=show, pkg=pkg, app=app, calls=calls, tmp=tmp_path)


def _publish(h, video_url="", **over):
    outcome: dict = {}
    vid = pe.maybe_publish_youtube(
        h.show, _cfg(), 16, dt.date(2026, 11, 4),
        f"Ep16: {GUEST} — A recruitment founder counters AI deepfakes",
        "Episode notes.", "https://audio.nerranetwork.com/age_of_ai/raw/x.mp3",
        GUEST, video_url=video_url, pkg=over.get("pkg", h.pkg), app=h.app,
        photo=over.get("photo", ""), thesis=THESIS, outcome=outcome)
    return vid, outcome


def _index(h) -> list:
    path = Path(h.show.audio_subdir) / "youtube_videos.json"
    return json.loads(path.read_text(encoding="utf-8"))["videos"] if path.exists() else []


# ---------------------------------------------------------------------------
# 1. The packaging on the upload
# ---------------------------------------------------------------------------

class TestThePackaging:
    def test_the_upload_carries_a_title_with_the_guest_a_thumbnail_and_chapters(self, harness):
        vid, outcome = _publish(harness)
        assert vid == "vid123"
        [up] = harness.calls["uploads"]
        assert GUEST in up["title"] and len(up["title"]) <= YOUTUBE_TITLE_MAX
        assert up["title"] == f"{GUEST}: Why Hiring Broke"
        assert up["thumbnail_path"] is not None and up["thumbnail_exists"]
        assert "\n0:00 The fifty applicants\n10:00 Verified credentials" in up["description"]
        assert "utm_" in up["description"]                    # the page link through engine.funnel
        assert "hosted by Mira, an AI" in up["description"]
        assert up["tags"] == ["AI", "hiring"] and up["contains_synthetic_media"] is True
        # The bundle read the thesis and the edit transcript, under the show's tags.
        [bundle] = harness.calls["bundle"]
        assert bundle["hook"] == THESIS and "avatars" in bundle["digest_text"]
        assert bundle["keywords"] == ["AI", "hiring"] and bundle["tracker"] is None
        assert outcome["title"] == up["title"] and outcome["chapters"] is True

    def test_the_index_row_says_which_video_shipped_and_that_the_packaging_was_on(self, harness):
        _publish(harness)
        [row] = _index(harness)
        assert row["kind"] == "long" and row["video_id"] == "vid123"
        assert row["variant"] == pe.YOUTUBE_VARIANT == "interview_v2"
        assert row["video_kind"] == pe.VIDEO_KIND_WAVEFORM
        assert row["thumbnail_base"] == "mira_studio"
        assert row["hook"] == GUEST and GUEST in row["title"]
        for key in ("show_slug", "episode", "channel", "watch_url", "published"):
            assert key in row

    def test_the_waveform_is_rendered_when_the_produce_step_left_none(self, harness, monkeypatch):
        harness.calls["head"]["status"] = 404
        rendered = []

        def fake_render(show, audio_url, out, guest_name):
            rendered.append(audio_url)
            Path(out).write_bytes(b"\0" * 4096)
            return Path(out)
        monkeypatch.setattr(pe, "render_episode_video", fake_render)
        vid, outcome = _publish(harness)
        assert vid == "vid123" and rendered and outcome["video_kind"] == pe.VIDEO_KIND_WAVEFORM

    def test_an_empty_bundle_falls_back_to_the_feed_title_and_no_punch(self, harness, monkeypatch):
        import engine.youtube_titles as titles_mod
        monkeypatch.setattr(titles_mod, "generate_title_bundle",
                            lambda **kw: {"titles": [], "punch_text": "", "short_titles": []})
        _publish(harness)
        [up] = harness.calls["uploads"]
        assert up["title"] == f"Ep16: {GUEST} — A recruitment founder counters AI deepfakes"
        assert up["thumbnail_exists"]


# ---------------------------------------------------------------------------
# 2. The camera cut, and never the waveform in its place
# ---------------------------------------------------------------------------

class TestTheCameraEpisode:
    def test_a_camera_cut_that_answers_is_the_video(self, harness):
        vid, outcome = _publish(harness, video_url="https://audio.nerranetwork.com/age_of_ai/video/e.mp4")
        assert vid == "vid123" and outcome["video_kind"] == pe.VIDEO_KIND_CAMERA
        [row] = _index(harness)
        assert row["video_kind"] == "camera" and row["variant"] == "interview_v2"

    def test_a_camera_cut_that_does_not_answer_is_never_the_waveform(self, harness, caplog):
        harness.calls["head"]["status"] = 404
        with caplog.at_level(logging.WARNING):
            vid, outcome = _publish(harness, video_url="https://audio.nerranetwork.com/age_of_ai/video/e.mp4")
        assert vid == "" and harness.calls["uploads"] == []
        assert outcome["video_kind"] == pe.VIDEO_KIND_CAMERA_MISSING
        assert outcome["camera_status"] == 404 and outcome["video_id"] == ""
        assert "::warning::" in caplog.text and "never ships the waveform" in caplog.text
        assert harness.calls["notified"] and "HTTP 404" in harness.calls["notified"][0]
        assert _index(harness) == []                          # no row for a video that did not go up

    def test_a_camera_cut_whose_head_fails_counts_as_missing_too(self, harness):
        harness.calls["head"]["status"] = 0
        vid, outcome = _publish(harness, video_url="https://audio.nerranetwork.com/age_of_ai/video/e.mp4")
        assert vid == "" and outcome["video_kind"] == pe.VIDEO_KIND_CAMERA_MISSING

    def test_the_source_has_no_render_locally_path_in_the_camera_branch(self):
        body = PUB.split("def maybe_publish_youtube(")[1].split("\ndef ")[0]
        camera = body.split("if video_url:")[1].split("else:")[0]
        assert "render_locally = True" not in camera
        assert "VIDEO_KIND_CAMERA_MISSING" in camera and "return \"\"" in camera
        assert "thumbnail_path=thumbnail" in body
        assert "chapter_block_for(pkg)" in body


# ---------------------------------------------------------------------------
# 3. The title keeps the guest; the thumbnail base follows the guest's choice
# ---------------------------------------------------------------------------

class TestTitleAndThumbnailRules:
    def test_the_guests_name_is_always_in_the_title_inside_the_limit(self):
        feed = f"Ep16: {GUEST} — A recruitment founder counters AI deepfakes"
        assert pe.youtube_title_for(feed, GUEST, ["Why Hiring Broke"]) == f"{GUEST}: Why Hiring Broke"
        assert pe.youtube_title_for(feed, GUEST, [f"{GUEST} on why hiring broke"]) == f"{GUEST} on why hiring broke"
        assert pe.youtube_title_for(feed, GUEST, ["x" * 95]) == feed      # too long with the name: feed title
        assert pe.youtube_title_for(feed, GUEST, []) == feed
        assert pe.youtube_title_for(feed, GUEST, ["", None, "  "]) == feed
        for cand in ("short", "a" * 60, "the guest's own name Thor Hesselberg mid-title"):
            title = pe.youtube_title_for(feed, GUEST, [cand])
            assert GUEST.lower() in title.lower() and len(title) <= YOUTUBE_TITLE_MAX

    def test_the_guest_photo_only_when_the_review_page_allowed_a_picture(self, tmp_path, monkeypatch):
        still = ROOT / "assets" / "mira" / "mira-studio.jpg"
        monkeypatch.setattr(pe, "_download",
                            lambda url, dest: shutil.copy(still, dest) and Path(dest))
        photo = "https://audio.nerranetwork.com/age_of_ai/photos/thor.jpg"
        base, kind = pe.thumbnail_base_for({"guest_video_ok": True}, photo, tmp_path)
        assert kind == "guest_photo" and base.exists() and base != still
        for choice in ({"guest_video_ok": None}, {"guest_video_ok": False}, {}):
            base, kind = pe.thumbnail_base_for(choice, photo, tmp_path)
            assert kind == "mira_studio" and base == still
        base, kind = pe.thumbnail_base_for({"guest_video_ok": True}, "", tmp_path)
        assert kind == "mira_studio"

    def test_the_thumbnail_on_the_guest_photo_is_recorded_and_told_to_the_guest(self, harness, monkeypatch):
        still = ROOT / "assets" / "mira" / "mira-studio.jpg"
        monkeypatch.setattr(pe, "_download",
                            lambda url, dest: shutil.copy(still, dest) and Path(dest))
        pkg = {**harness.pkg, "guest_video_ok": True}
        _vid, outcome = _publish(harness, pkg=pkg, photo="https://audio.nerranetwork.com/p/thor.jpg")
        assert outcome["thumbnail_base"] == "guest_photo"
        assert _index(harness)[0]["thumbnail_base"] == "guest_photo"
        _subject, body = pe.published_email(harness.show, harness.app, pkg, 16, youtube=outcome)
        assert "thumbnail uses your profile photo" in body
        assert "https://www.youtube.com/watch?v=vid123" in body
        # Mira's still on the thumbnail: nothing to tell the guest about.
        _subject, body = pe.published_email(harness.show, harness.app, pkg, 16,
                                            youtube={"video_id": "vid123", "thumbnail_base": "mira_studio"})
        assert "profile photo" not in body
        _subject, body = pe.published_email(harness.show, harness.app, pkg, 16)
        assert "profile photo" not in body

    def test_publish_one_hands_the_record_and_the_outcome_through(self):
        body = PUB.split("def publish_one(")[1].split("\ndef ")[0]
        assert "pkg=pkg, app=app, photo=photo," in body
        assert "outcome=yt_outcome)" in body
        assert "tell_the_guest(show, app, pkg, episode_num, run=run, youtube=yt_outcome)" in body


# ---------------------------------------------------------------------------
# 4. The switch is explicit, the workflow carries the key
# ---------------------------------------------------------------------------

def test_the_camera_switch_is_written_in_both_show_yamls():
    import yaml
    for slug in ("age_of_ai", "nerra_voices"):
        raw = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
        assert (raw.get("voices") or {}).get("local_video") is False
        assert get_show(slug).local_video is False


def test_the_publish_workflow_passes_the_grok_key_the_title_bundle_needs():
    wf = (ROOT / ".github" / "workflows" / "nerra_voices_publish.yml").read_text(encoding="utf-8")
    assert "GROK_API_KEY: ${{ secrets.GROK_API_KEY }}" in wf
