"""Tests for the YouTube uploader and metadata builders.

These tests use mocks for the Google API client so the suite never
touches the network. They verify three things:

  1. The video metadata builders honour YouTube's hard limits (title
     100 chars, description 5000, tag total 500) and produce well-formed
     chapter blocks.
  2. The upload request body always sets
     ``status.containsSyntheticMedia=True`` (the AI disclosure flag).
  3. Credential plumbing — ``get_channel_credentials_from_env`` returns
     ``None`` cleanly when secrets are missing instead of raising.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from engine import youtube
from engine import video_metadata as vm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides):
    """Build a stand-in for ShowConfig with the fields the metadata
    builders touch. Avoids depending on the real dataclass + YAML loader."""
    publishing = SimpleNamespace(
        rss_title=overrides.get("rss_title", "Tesla Shorts Time Daily"),
        base_url=overrides.get("base_url", "https://nerranetwork.com"),
        rss_link=overrides.get(
            "rss_link", "https://nerranetwork.com/tesla.html"
        ),
    )
    youtube_cfg = SimpleNamespace(
        tags=overrides.get("tags", ["tesla", "ev"]),
        category_id=overrides.get("category_id", 28),
        default_language=overrides.get("default_language", "en"),
        synthetic_disclosure=overrides.get(
            "synthetic_disclosure", "AI Disclosure: synthesized voice."
        ),
        description_prompt_file=overrides.get("description_prompt_file", ""),
        pinned_comment_template=overrides.get("pinned_comment_template", ""),
        enabled=True,
        channel="en",
    )
    return SimpleNamespace(
        name=overrides.get("name", "Tesla Shorts Time"),
        publishing=publishing,
        youtube=youtube_cfg,
        keywords=overrides.get(
            "keywords", ["model 3", "fsd", "robotaxi", "tsla"]
        ),
    )


# ---------------------------------------------------------------------------
# Markdown stripping
# ---------------------------------------------------------------------------

def test_strip_markdown_removes_headers_bold_and_links():
    """Markdown links are stripped to their LABEL ONLY (the URL is dropped).

    Tesla Ep459-465 (May 2-5 2026) — every long-form upload failed with
    ``invalidDescription`` because Tesla digests embed Google News
    redirect URLs of the form
    ``https://news.google.com/rss/articles/CBMimgFB...?oc=5`` (200+
    char base64-encoded paths). YouTube's spam classifier flagged the
    description, and Shorts (which use a separate metadata path
    without body content) were unaffected. Drop the URL portion of
    every markdown link so the description stays clean — readers
    still get citation links via the .md / blog post / RSS, all of
    which are unchanged."""
    raw = (
        "# Big news\n"
        "**Tesla** delivers on Q3.\n"
        "Read [the announcement](https://example.com/post).\n"
    )
    out = vm._strip_markdown(raw)
    assert "**" not in out
    assert "#" not in out.split("\n")[0]
    # Label survives, URL gone.
    assert "the announcement" in out
    assert "https://example.com" not in out


def test_strip_markdown_drops_long_google_news_redirect_urls():
    """Tesla Ep459-465 specific — the actual production trigger for the
    May 2026 invalidDescription regression. Confirms a realistic
    Google News redirect URL is removed from the body."""
    raw = (
        "1. **California Opens Roads to Autonomous Semi Trucks**: "
        "Source: [Google News](https://news.google.com/rss/articles/"
        "CBMimgFBVV95cUxNRWRNMzJUNTVYWURwdjh2ckxST2dpelFHSzBycFBsQXFD"
        "eHI0S0RjREUza0I2TU5VNW9KWGhnVWJBOC1OX0VLXzBGZkVocFhiYzFyNmVp"
        "TlRtSjBsUFlOMlloQ0lob2c4RlZYaHBLaUJCaTN3Z3dNakNDdy13TEU4TF80"
        "eUJ0aTlOLVhnSHNxaGVXTWNCSktMQ013?oc=5)"
    )
    out = vm._strip_markdown(raw)
    # The base64-looking redirect path must be gone.
    assert "CBMimgFBVV95" not in out
    # And the prose around it survives.
    assert "California Opens Roads" in out
    assert "Source: Google News" in out


def test_strip_markdown_strips_bare_long_urls():
    """Belt-and-braces: any non-markdown raw URL longer than 80 chars
    also gets dropped, so a hand-written digest with a bare redirect
    URL doesn't sneak past."""
    raw = (
        "See https://news.google.com/rss/articles/" + "x" * 200 + "?oc=5 "
        "for context, but the short link https://x.com/y stays."
    )
    out = vm._strip_markdown(raw)
    # Long URL gone; short URL survives.
    assert "x" * 200 not in out
    assert "https://x.com/y" in out


def test_strip_markdown_drops_code_fences():
    raw = "```python\nprint(1)\n```\n\nAfter."
    out = vm._strip_markdown(raw)
    assert "print" not in out
    assert "After." in out


def test_strip_markdown_drops_blockquote_marker():
    """May 2026 fix — every Tesla / FF / OV digest opens with a
    ``> **Hook**`` blockquote. The bold strip used to leave a literal
    ``>`` at the start of the YouTube description, and ``videos.insert``
    rejects any description containing ``<`` or ``>`` with HTTP 400
    ``invalidDescription``. Every long-form upload was failing while
    Shorts (which uses a separate metadata path) still succeeded."""
    raw = "> **Cybercab production begins in Texas.**\n\nBody continues."
    out = vm._strip_markdown(raw)
    # No leading ``>``; bold also stripped.
    assert ">" not in out
    assert "**" not in out
    assert "Cybercab production begins in Texas." in out
    assert "Body continues." in out


def test_strip_markdown_removes_stray_angle_brackets():
    """Defense-in-depth — math expressions like ``<2030`` and any
    speech tags that slipped past upstream sanitization must not
    reach the YouTube description."""
    raw = "Population <2030 reached 8B. <emphasis>Critical</emphasis> shift."
    out = vm._strip_markdown(raw)
    assert "<" not in out
    assert ">" not in out
    assert "Population" in out
    assert "Critical" in out


# ---------------------------------------------------------------------------
# Chapter formatting
# ---------------------------------------------------------------------------

def test_format_chapter_timestamp_under_an_hour():
    assert vm._format_chapter_timestamp(0) == "0:00"
    assert vm._format_chapter_timestamp(75) == "1:15"
    assert vm._format_chapter_timestamp(3599) == "59:59"


def test_format_chapter_timestamp_over_an_hour():
    assert vm._format_chapter_timestamp(3600) == "1:00:00"
    assert vm._format_chapter_timestamp(3725) == "1:02:05"


def test_chapter_block_requires_zero_start():
    chapters = [
        {"title": "Intro", "startTime": 30},  # YouTube ignores blocks not starting at 0
        {"title": "Main", "startTime": 120},
    ]
    assert vm._format_chapter_block(chapters) == ""


def test_chapter_block_renders_when_starts_at_zero():
    chapters = [
        {"title": "Intro", "startTime": 0},
        {"title": "Top Stories", "startTime": 30},
        {"title": "Closing", "startTime": 600},
    ]
    block = vm._format_chapter_block(chapters)
    lines = block.split("\n")
    assert lines[0] == "0:00 Intro"
    assert lines[1] == "0:30 Top Stories"
    assert lines[2] == "10:00 Closing"


def test_chapter_block_handles_short_lists():
    assert vm._format_chapter_block([]) == ""
    assert vm._format_chapter_block([{"title": "Solo", "startTime": 0}]) == ""


# ---------------------------------------------------------------------------
# Tag handling
# ---------------------------------------------------------------------------

def test_build_tags_dedupes_and_lowercases():
    tags = vm._build_tags(
        extra=["Tesla", "TESLA", " Model 3 "],
        keywords=["model 3", "FSD"],
        network_tags=[],
    )
    assert tags == ["tesla", "model 3", "fsd"]


def test_build_tags_respects_500_char_cap():
    long_extras = [f"tag-{i:03d}-padded-out" for i in range(50)]
    tags = vm._build_tags(extra=long_extras, keywords=[], network_tags=[])
    assert len(",".join(tags)) <= vm.YOUTUBE_TAG_TOTAL_MAX


# ---------------------------------------------------------------------------
# Metadata builders
# ---------------------------------------------------------------------------

def test_youtube_oauth_scopes_include_force_ssl():
    from engine.youtube import YOUTUBE_SCOPES
    assert "https://www.googleapis.com/auth/youtube.force-ssl" in YOUTUBE_SCOPES


def test_build_long_form_metadata_uses_description_template(tmp_path):
    prompt = tmp_path / "yt_intro.txt"
    prompt.write_text(
        "Ep {episode_num}: {hook}\nShow: {show_name}",
        encoding="utf-8",
    )
    cfg = _make_config()
    cfg.youtube.description_prompt_file = str(prompt)
    meta = vm.build_long_form_metadata(
        cfg,
        episode_num=5,
        today_str="2026-05-20",
        hook="Cybertruck news",
        digest_text="# Digest\n\n**Should not appear** in YouTube body.",
        audio_url="",
    )
    assert "Ep 5" in meta["description"]
    assert "Cybertruck news" in meta["description"]
    assert "Should not appear" not in meta["description"]


def test_build_long_form_metadata_truncates_title_to_100_chars():
    config = _make_config(rss_title="X" * 80)
    meta = vm.build_long_form_metadata(
        config,
        episode_num=1,
        today_str="2026-04-26",
        hook="Y" * 80,
        digest_text="A short digest body.",
        audio_url="https://audio.nerranetwork.com/tesla/ep001.mp3",
    )
    assert len(meta["title"]) <= vm.YOUTUBE_TITLE_MAX
    assert meta["title"].endswith("...")


def test_build_long_form_metadata_includes_disclosure_and_utm():
    config = _make_config()
    meta = vm.build_long_form_metadata(
        config,
        episode_num=42,
        today_str="2026-04-26",
        hook="Robotaxi expands to Vancouver",
        digest_text="Tesla announced robotaxi expansion today...",
        audio_url="https://audio.nerranetwork.com/tesla/ep042.mp3",
    )
    assert "AI Disclosure" in meta["description"]
    assert "utm_source=youtube" in meta["description"]
    assert "utm_medium=video" in meta["description"]
    assert "utm_campaign=ep42" in meta["description"]
    assert meta["category_id"] == 28
    assert meta["default_language"] == "en"


def test_build_long_form_metadata_includes_show_page_link_above_fold():
    """Operator (May 8 2026) asked for a direct link to the show
    webpage in every YouTube description so listeners can click
    through to nerranetwork.com from the video. The link must appear
    BEFORE the body paragraphs so it's visible above YouTube's
    "Show more" fold (~150 chars on mobile).
    """
    config = _make_config()
    meta = vm.build_long_form_metadata(
        config,
        episode_num=42,
        today_str="2026-04-26",
        hook="Robotaxi expands to Vancouver",
        digest_text="Tesla announced robotaxi expansion today...",
        audio_url="https://audio.nerranetwork.com/tesla/ep042.mp3",
    )
    desc = meta["description"]
    # A visible "Show page:" line carries the bare canonical URL.
    assert "Show page:" in desc
    # The link itself (no UTM — that's the subscribe line below).
    assert "https://nerranetwork.com/tesla.html" in desc
    # Above-the-fold ordering: show page line appears before the body.
    sp_idx = desc.index("Show page:")
    body_idx = desc.index("robotaxi expansion")
    assert sp_idx < body_idx, (
        "Show page link must come before body paragraphs to stay above "
        "YouTube's 'Show more' fold."
    )


def test_build_short_metadata_includes_show_page_link():
    """Shorts descriptions are brief; the show page link must still
    appear so a listener tapping into the description can reach the
    show webpage."""
    config = _make_config()
    meta = vm.build_short_metadata(
        config,
        episode_num=42,
        today_str="2026-04-26",
        hook="Robotaxi expands to Vancouver",
        long_form_url="https://www.youtube.com/watch?v=abcd1234",
    )
    desc = meta["description"]
    assert "Show page:" in desc
    assert "https://nerranetwork.com/tesla.html" in desc


def test_build_long_form_metadata_strips_angle_brackets_from_hook():
    """Defense-in-depth final strip — even if the hook contains
    ``<`` / ``>`` (a chapter title quoting math, an unfortunate
    LLM artifact, etc.) the YouTube description must come out clean
    so ``videos.insert`` doesn't 400."""
    config = _make_config()
    meta = vm.build_long_form_metadata(
        config,
        episode_num=10,
        today_str="2026-05-05",
        hook="Robotaxi market share <5% in Q1 — <emphasis>but climbing</emphasis>",
        digest_text="> **Hook here.**\n\nBody paragraph one.",
        audio_url="https://audio.nerranetwork.com/tesla/ep010.mp3",
    )
    assert "<" not in meta["description"], (
        "YouTube rejects descriptions containing '<' — strip leaked"
    )
    assert ">" not in meta["description"], (
        "YouTube rejects descriptions containing '>' — strip leaked"
    )
    # Content survives the strip — words are preserved, only the
    # angle brackets are removed.
    assert "Robotaxi" in meta["description"]
    assert "Body paragraph one." in meta["description"]


def test_build_long_form_metadata_chapter_block_appears(tmp_path):
    chapters_path = tmp_path / "chapters_ep042.json"
    chapters_path.write_text(
        '{"chapters": ['
        '{"title": "Intro", "startTime": 0},'
        '{"title": "Top Stories", "startTime": 45}'
        ']}', encoding="utf-8",
    )
    config = _make_config()
    meta = vm.build_long_form_metadata(
        config,
        episode_num=42,
        today_str="2026-04-26",
        hook="Big news",
        digest_text="Body text.",
        audio_url="https://example.com/ep.mp3",
        chapters_path=chapters_path,
    )
    assert "Chapters:" in meta["description"]
    assert "0:00 Intro" in meta["description"]
    assert "0:45 Top Stories" in meta["description"]


def test_build_short_metadata_uses_shorts_hashtag():
    config = _make_config()
    meta = vm.build_short_metadata(
        config,
        episode_num=42,
        today_str="2026-04-26",
        hook="Robotaxi expands",
        long_form_url="https://www.youtube.com/watch?v=abc",
    )
    assert "#Shorts" in meta["title"]
    assert "https://www.youtube.com/watch?v=abc" in meta["description"]
    assert "utm_medium=shorts" in meta["description"]
    assert "AI Disclosure" in meta["description"]
    # Tags should include the shorts marker.
    assert "shorts" in meta["tags"]


# ---------------------------------------------------------------------------
# YouTube API plumbing
# ---------------------------------------------------------------------------

def test_build_video_body_sets_synthetic_media_flag():
    body = youtube._build_video_body(
        title="Ep 1",
        description="hello",
        tags=["t"],
        category_id=28,
        default_language="en",
        privacy_status="public",
        contains_synthetic_media=True,
        made_for_kids=False,
    )
    assert body["status"]["containsSyntheticMedia"] is True
    assert body["status"]["selfDeclaredMadeForKids"] is False
    assert body["status"]["privacyStatus"] == "public"
    assert body["snippet"]["title"] == "Ep 1"
    assert body["snippet"]["categoryId"] == "28"
    assert body["snippet"]["defaultLanguage"] == "en"


def test_build_oauth_credentials_validates_inputs():
    with pytest.raises(ValueError, match="client_id"):
        youtube.build_oauth_credentials(
            client_id="", client_secret="x", refresh_token="y",
        )
    with pytest.raises(ValueError, match="refresh_token"):
        youtube.build_oauth_credentials(
            client_id="x", client_secret="y", refresh_token="",
        )


def test_get_channel_credentials_from_env_returns_none_when_missing(monkeypatch):
    for var in (
        "YOUTUBE_CLIENT_ID",
        "YOUTUBE_CLIENT_SECRET",
        "YOUTUBE_REFRESH_TOKEN_EN",
        "YOUTUBE_REFRESH_TOKEN_RU",
    ):
        monkeypatch.delenv(var, raising=False)
    assert youtube.get_channel_credentials_from_env("en") is None
    assert youtube.get_channel_credentials_from_env("ru") is None


def test_get_channel_credentials_from_env_picks_correct_token(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "id")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN_EN", "rt-en")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN_RU", "rt-ru")
    creds_en = youtube.get_channel_credentials_from_env("en")
    creds_ru = youtube.get_channel_credentials_from_env("ru")
    assert creds_en is not None and creds_en.refresh_token == "rt-en"
    assert creds_ru is not None and creds_ru.refresh_token == "rt-ru"


def test_upload_video_invokes_api_and_returns_watch_url(monkeypatch, tmp_path):
    """End-to-end test of upload_video with a fully mocked Google client.

    We assert the request body shape (containsSyntheticMedia=True) and
    the watch URL is constructed from the returned video id.
    """
    video_path = tmp_path / "ep001.mp4"
    video_path.write_bytes(b"\x00" * 1024)

    captured = {}

    class _FakeRequest:
        def __init__(self, response):
            self._response = response

        def next_chunk(self):
            return None, self._response

        def execute(self):
            return self._response

    class _FakeVideos:
        def insert(self, **kwargs):
            captured["insert_kwargs"] = kwargs
            return _FakeRequest({"id": "abc123"})

    class _FakeThumbnails:
        def set(self, **kwargs):
            captured["thumb_kwargs"] = kwargs
            return _FakeRequest({})

    class _FakeYouTube:
        def videos(self):
            return _FakeVideos()

        def thumbnails(self):
            return _FakeThumbnails()

    class _FakeMediaFileUpload:
        def __init__(self, *args, **kwargs):
            captured["media_args"] = (args, kwargs)

    # Patch the lazy imports inside upload_video.
    import sys
    fake_googleapiclient = type(sys)("googleapiclient")
    fake_discovery = type(sys)("googleapiclient.discovery")
    fake_http = type(sys)("googleapiclient.http")
    fake_discovery.build = lambda *a, **kw: _FakeYouTube()
    fake_http.MediaFileUpload = _FakeMediaFileUpload
    fake_googleapiclient.discovery = fake_discovery
    fake_googleapiclient.http = fake_http
    monkeypatch.setitem(sys.modules, "googleapiclient", fake_googleapiclient)
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery",
                        fake_discovery)
    monkeypatch.setitem(sys.modules, "googleapiclient.http", fake_http)

    result = youtube.upload_video(
        video_path,
        credentials=object(),  # not used by the fake
        title="Test",
        description="desc",
        tags=["t"],
        category_id=28,
        default_language="en",
        privacy_status="public",
    )
    assert isinstance(result, youtube.UploadResult)
    assert result.video_id == "abc123"
    assert result.watch_url == "https://www.youtube.com/watch?v=abc123"

    body = captured["insert_kwargs"]["body"]
    assert body["status"]["containsSyntheticMedia"] is True
    assert body["snippet"]["title"] == "Test"
    assert captured["insert_kwargs"]["part"] == "snippet,status"


def test_upload_result_has_video_id_and_watch_url():
    result = youtube.UploadResult(
        video_id="abc123",
        watch_url="https://www.youtube.com/watch?v=abc123",
    )
    assert result.video_id == "abc123"
    assert result.watch_url == "https://www.youtube.com/watch?v=abc123"


def _patch_googleapiclient(monkeypatch, fake_youtube, http_error_cls=None):
    """Install a fake googleapiclient module tree for the duration of a test."""
    import sys

    fake_googleapiclient = type(sys)("googleapiclient")
    fake_discovery = type(sys)("googleapiclient.discovery")
    fake_http = type(sys)("googleapiclient.http")
    fake_errors = type(sys)("googleapiclient.errors")
    fake_discovery.build = lambda *a, **kw: fake_youtube
    fake_http.MediaFileUpload = lambda *a, **kw: None

    if http_error_cls is None:
        class HttpError(Exception):
            def __init__(self, status=400, message="error"):
                super().__init__(message)
                self.resp = SimpleNamespace(status=status)
        http_error_cls = HttpError
    fake_errors.HttpError = http_error_cls

    fake_googleapiclient.discovery = fake_discovery
    fake_googleapiclient.http = fake_http
    fake_googleapiclient.errors = fake_errors
    monkeypatch.setitem(sys.modules, "googleapiclient", fake_googleapiclient)
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery", fake_discovery)
    monkeypatch.setitem(sys.modules, "googleapiclient.http", fake_http)
    monkeypatch.setitem(sys.modules, "googleapiclient.errors", fake_errors)
    return http_error_cls


def test_add_video_to_playlist_calls_playlistitems_insert(monkeypatch):
    captured = {}

    class _FakeRequest:
        def execute(self):
            captured["executed"] = True
            return {"id": "playlistitem123"}

    class _FakePlaylistItems:
        def insert(self, **kwargs):
            captured["insert_kwargs"] = kwargs
            return _FakeRequest()

    class _FakeYouTube:
        def playlistItems(self):
            return _FakePlaylistItems()

    _patch_googleapiclient(monkeypatch, _FakeYouTube())

    ok = youtube.add_video_to_playlist(
        credentials=object(),
        video_id="abc123",
        playlist_id="PLRHMnzNNXPYCRrcYpPwAzjaRXqzKRUl23",
    )
    assert ok is True
    assert captured["executed"] is True
    assert captured["insert_kwargs"]["part"] == "snippet"
    body = captured["insert_kwargs"]["body"]
    assert body["snippet"]["playlistId"] == (
        "PLRHMnzNNXPYCRrcYpPwAzjaRXqzKRUl23"
    )
    assert body["snippet"]["resourceId"] == {
        "kind": "youtube#video",
        "videoId": "abc123",
    }


def test_add_video_to_playlist_returns_false_on_http_error(monkeypatch, caplog):
    class HttpError(Exception):
        def __init__(self, status=403, message="forbidden"):
            super().__init__(message)
            self.resp = SimpleNamespace(status=status)

    http_error_cls = _patch_googleapiclient(
        monkeypatch, fake_youtube=None, http_error_cls=HttpError,
    )

    class _FakeRequest:
        def execute(self):
            raise http_error_cls(status=403, message="forbidden")

    class _FakePlaylistItems:
        def insert(self, **kwargs):
            return _FakeRequest()

    class _FakeYouTube:
        def playlistItems(self):
            return _FakePlaylistItems()

    # Re-patch build to return the youtube fake now that classes exist.
    import sys
    sys.modules["googleapiclient.discovery"].build = (
        lambda *a, **kw: _FakeYouTube()
    )

    with caplog.at_level("WARNING", logger="engine.youtube"):
        ok = youtube.add_video_to_playlist(
            credentials=object(),
            video_id="abc123",
            playlist_id="PL_bad",
        )
    assert ok is False
    assert any("403" in rec.message or "Failed" in rec.message
               for rec in caplog.records)


def test_upload_video_requires_existing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        youtube.upload_video(
            tmp_path / "missing.mp4",
            credentials=object(),
            title="t",
            description="d",
            tags=[],
            category_id=28,
        )


# ---------------------------------------------------------------------------
# Description ordering — subscribe link must sit above the fold
# ---------------------------------------------------------------------------

def test_long_form_description_subscribe_link_appears_before_body():
    """Subscribe link should be right after the hook, before the digest
    body — so it's visible above YouTube's "Show more" fold."""
    config = _make_config()
    meta = vm.build_long_form_metadata(
        config,
        episode_num=42,
        today_str="2026-04-26",
        hook="Robotaxi expands to Vancouver",
        digest_text="Tesla announced robotaxi expansion today, with...",
        audio_url="https://audio.nerranetwork.com/tesla/ep042.mp3",
    )
    desc = meta["description"]
    hook_idx = desc.find("Robotaxi expands to Vancouver")
    subscribe_idx = desc.find("Subscribe to")
    body_idx = desc.find("Tesla announced robotaxi expansion")
    assert hook_idx >= 0 and subscribe_idx >= 0 and body_idx >= 0
    assert hook_idx < subscribe_idx < body_idx, (
        "Order must be: hook → subscribe → body"
    )


def test_long_form_description_subscribe_uses_show_name():
    config = _make_config(rss_title="Tesla Shorts Time Daily")
    meta = vm.build_long_form_metadata(
        config,
        episode_num=1,
        today_str="2026-04-26",
        hook="A hook",
        digest_text="Body",
        audio_url="",
    )
    assert "Subscribe to Tesla Shorts Time Daily" in meta["description"]
    assert "🎧" in meta["description"]


# ---------------------------------------------------------------------------
# Caption track upload
# ---------------------------------------------------------------------------

def test_upload_caption_track_skips_when_srt_missing(tmp_path):
    from engine.youtube import upload_caption_track
    assert upload_caption_track(
        credentials=object(),
        video_id="abc",
        srt_path=tmp_path / "missing.srt",
        language="en",
    ) is False


def test_upload_caption_track_skips_when_video_id_empty(tmp_path):
    from engine.youtube import upload_caption_track
    srt = tmp_path / "captions.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nHi\n", encoding="utf-8")
    assert upload_caption_track(
        credentials=object(),
        video_id="",
        srt_path=srt,
        language="en",
    ) is False


def test_upload_caption_track_calls_api_with_correct_body(monkeypatch, tmp_path):
    """Happy-path: correct snippet shape (videoId, language, name,
    isDraft) and a media body, returns True."""
    from engine import youtube as yt_module

    srt = tmp_path / "ep001.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n",
                   encoding="utf-8")

    captured = {}

    class _FakeRequest:
        def execute(self):
            captured["executed"] = True
            return {"id": "cap123"}

    class _FakeCaptions:
        def insert(self, **kwargs):
            captured["insert_kwargs"] = kwargs
            return _FakeRequest()

    class _FakeYouTube:
        def captions(self):
            return _FakeCaptions()

    class _FakeMediaFileUpload:
        def __init__(self, *args, **kwargs):
            captured["media_args"] = (args, kwargs)

    import sys
    fake_googleapiclient = type(sys)("googleapiclient")
    fake_discovery = type(sys)("googleapiclient.discovery")
    fake_http = type(sys)("googleapiclient.http")
    fake_errors = type(sys)("googleapiclient.errors")
    fake_errors.HttpError = type("HttpError", (Exception,), {})
    fake_discovery.build = lambda *a, **kw: _FakeYouTube()
    fake_http.MediaFileUpload = _FakeMediaFileUpload
    fake_googleapiclient.discovery = fake_discovery
    fake_googleapiclient.http = fake_http
    fake_googleapiclient.errors = fake_errors
    monkeypatch.setitem(sys.modules, "googleapiclient", fake_googleapiclient)
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery",
                        fake_discovery)
    monkeypatch.setitem(sys.modules, "googleapiclient.http", fake_http)
    monkeypatch.setitem(sys.modules, "googleapiclient.errors", fake_errors)

    result = yt_module.upload_caption_track(
        credentials=object(),
        video_id="vid42",
        srt_path=srt,
        language="en",
        name="English",
    )
    assert result is True
    body = captured["insert_kwargs"]["body"]
    assert body["snippet"]["videoId"] == "vid42"
    assert body["snippet"]["language"] == "en"
    assert body["snippet"]["name"] == "English"
    assert body["snippet"]["isDraft"] is False
    assert captured["insert_kwargs"]["part"] == "snippet"


def test_upload_caption_track_returns_false_on_api_error(monkeypatch, tmp_path):
    """Failures must not raise — caption upload is best-effort."""
    from engine import youtube as yt_module

    srt = tmp_path / "ep001.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nHi\n", encoding="utf-8")

    class _FakeHttpError(Exception):
        pass

    class _FakeRequest:
        def execute(self):
            err = _FakeHttpError("boom")
            err.resp = type("R", (), {"status": 403})()
            raise err

    class _FakeCaptions:
        def insert(self, **kwargs):
            return _FakeRequest()

    class _FakeYouTube:
        def captions(self):
            return _FakeCaptions()

    import sys
    fake_googleapiclient = type(sys)("googleapiclient")
    fake_discovery = type(sys)("googleapiclient.discovery")
    fake_http = type(sys)("googleapiclient.http")
    fake_errors = type(sys)("googleapiclient.errors")
    fake_errors.HttpError = _FakeHttpError
    fake_discovery.build = lambda *a, **kw: _FakeYouTube()
    fake_http.MediaFileUpload = lambda *a, **kw: None
    fake_googleapiclient.discovery = fake_discovery
    fake_googleapiclient.http = fake_http
    fake_googleapiclient.errors = fake_errors
    monkeypatch.setitem(sys.modules, "googleapiclient", fake_googleapiclient)
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery",
                        fake_discovery)
    monkeypatch.setitem(sys.modules, "googleapiclient.http", fake_http)
    monkeypatch.setitem(sys.modules, "googleapiclient.errors", fake_errors)

    result = yt_module.upload_caption_track(
        credentials=object(),
        video_id="vid42",
        srt_path=srt,
        language="en",
    )
    assert result is False


# ---------------------------------------------------------------------------
# X teaser — "Watch on YouTube" line gets appended when URL is set
# ---------------------------------------------------------------------------

def test_append_youtube_line_adds_url_when_set():
    """``_append_youtube_line`` should append a "Watch on YouTube" line
    when ``extra_context["youtube_url"]`` is non-empty."""
    from run_show import _append_youtube_line
    base = "🚀 Tesla Shorts Time — April 30, 2026\n🎧 Listen here."
    out = _append_youtube_line(base, {"youtube_url": "https://www.youtube.com/watch?v=abc123"})
    assert "🎬 Watch on YouTube" in out
    assert "https://www.youtube.com/watch?v=abc123" in out


def test_append_youtube_line_noop_when_empty():
    from run_show import _append_youtube_line
    base = "Tesla Shorts Time — Episode 1"
    out = _append_youtube_line(base, {})
    assert out == base
    out = _append_youtube_line(base, {"youtube_url": ""})
    assert out == base


def test_append_youtube_line_idempotent():
    """If the URL already appears in the teaser (e.g. via a YAML
    template), don't append a duplicate line."""
    from run_show import _append_youtube_line
    base = "Episode 1\nWatch: https://www.youtube.com/watch?v=abc"
    out = _append_youtube_line(
        base, {"youtube_url": "https://www.youtube.com/watch?v=abc"},
    )
    # No second occurrence appended.
    assert out.count("https://www.youtube.com/watch?v=abc") == 1
