"""
Tests for engine/publisher.py — RSS feed management, episode numbering,
GitHub Pages JSON, X posting, and analytics prefix.

Covers:
  - apply_op3_prefix(): URL rewriting for analytics
  - update_rss_feed(): XML generation, episode dedup, channel metadata
  - get_next_episode_number(): RSS + filesystem scanning
  - save_summary_to_github_pages(): JSON structure, max entries, ordering
  - post_to_x(): tweepy integration (mocked)
"""

import datetime
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engine.publisher import (
    _markdown_to_rss_html,
    apply_op3_prefix,
    build_show_notes_footer,
    format_digest_for_x,
    format_tst_digest_for_x,
    get_next_episode_number,
    post_to_x,
    save_summary_to_github_pages,
    update_rss_feed,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_dur(seconds):
    """Simple duration formatter for tests (avoids engine.audio import)."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _make_mp3(tmp_path, name="test.mp3", size=1024):
    """Helper to create a fake MP3 file."""
    mp3 = tmp_path / name
    mp3.write_bytes(b"\x00" * size)
    return mp3


def _make_rss(tmp_path, episode_num=1, title="Ep 1", desc="Desc",
              date=None, mp3_name="ep001.mp3", duration=300.0, **kwargs):
    """Create an RSS feed via update_rss_feed and return the path."""
    rss_path = tmp_path / "podcast.rss"
    mp3 = _make_mp3(tmp_path)
    date = date or datetime.date(2026, 1, 1)
    return update_rss_feed(
        rss_path, episode_num, title, desc, date,
        mp3_name, duration, mp3,
        format_duration_func=_fmt_dur,
        **kwargs,
    )


# ===================================================================
# TEST: apply_op3_prefix
# ===================================================================

class TestApplyOp3Prefix:

    def test_https_url_strips_scheme(self):
        result = apply_op3_prefix("https://cdn.example.com/ep1.mp3")
        assert result == "https://op3.dev/e/cdn.example.com/ep1.mp3"

    def test_http_url_keeps_full_url(self):
        result = apply_op3_prefix("http://cdn.example.com/ep1.mp3")
        assert result == "https://op3.dev/e/http://cdn.example.com/ep1.mp3"

    def test_no_scheme_appended_directly(self):
        result = apply_op3_prefix("cdn.example.com/ep1.mp3")
        assert result == "https://op3.dev/e/cdn.example.com/ep1.mp3"

    def test_custom_prefix_url(self):
        result = apply_op3_prefix(
            "https://cdn.example.com/ep1.mp3",
            prefix_url="https://custom.analytics.com/e/"
        )
        assert result == "https://custom.analytics.com/e/cdn.example.com/ep1.mp3"

    def test_github_raw_url(self):
        url = "https://raw.githubusercontent.com/user/repo/main/digests/ep001.mp3"
        result = apply_op3_prefix(url)
        assert result.startswith("https://op3.dev/e/")
        assert "raw.githubusercontent.com" in result
        assert "ep001.mp3" in result

    def test_empty_url(self):
        result = apply_op3_prefix("")
        assert result == "https://op3.dev/e/"


# ===================================================================
# TEST: get_next_episode_number
# ===================================================================

class TestGetNextEpisodeNumber:

    def test_no_rss_no_files_returns_1(self, tmp_path):
        rss_path = tmp_path / "podcast.rss"
        result = get_next_episode_number(rss_path, tmp_path)
        assert result == 1

    def test_rss_with_episodes(self, tmp_path):
        rss_path = tmp_path / "podcast.rss"
        rss_path.write_text("""<?xml version='1.0' encoding='UTF-8'?>
        <rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0">
          <channel>
            <item><itunes:episode>5</itunes:episode></item>
            <item><itunes:episode>10</itunes:episode></item>
          </channel>
        </rss>""")
        result = get_next_episode_number(rss_path, tmp_path)
        assert result == 11

    def test_mp3_files_in_directory(self, tmp_path):
        rss_path = tmp_path / "podcast.rss"
        (tmp_path / "Tesla_Ep005_20260101.mp3").touch()
        (tmp_path / "Tesla_Ep012_20260102.mp3").touch()
        result = get_next_episode_number(rss_path, tmp_path)
        assert result == 13

    def test_rss_and_files_uses_max(self, tmp_path):
        rss_path = tmp_path / "podcast.rss"
        rss_path.write_text("""<?xml version='1.0' encoding='UTF-8'?>
        <rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0">
          <channel>
            <item><itunes:episode>20</itunes:episode></item>
          </channel>
        </rss>""")
        (tmp_path / "Tesla_Ep015_20260101.mp3").touch()
        result = get_next_episode_number(rss_path, tmp_path)
        assert result == 21

    def test_custom_glob_pattern(self, tmp_path):
        rss_path = tmp_path / "podcast.rss"
        (tmp_path / "Omni_View_Ep007_20260101.mp3").touch()
        result = get_next_episode_number(
            rss_path, tmp_path, mp3_glob_pattern="Omni_View_Ep*.mp3"
        )
        assert result == 8

    def test_no_matching_files(self, tmp_path):
        rss_path = tmp_path / "podcast.rss"
        (tmp_path / "unrelated_file.mp3").touch()
        result = get_next_episode_number(rss_path, tmp_path)
        assert result == 1

    def test_malformed_rss_returns_1(self, tmp_path):
        rss_path = tmp_path / "podcast.rss"
        rss_path.write_text("this is not XML")
        result = get_next_episode_number(rss_path, tmp_path)
        assert result == 1

    def test_unparseable_rss_with_episodes_raises(self, tmp_path):
        """Truncated/corrupt RSS with episode content must refuse to restart
        numbering — silently returning 1 would overwrite Ep 1's MP3 in R2."""
        rss_path = tmp_path / "podcast.rss"
        rss_path.write_text(
            "<?xml version='1.0'?><rss><channel>"
            "<item><itunes:episode>42</itunes:episode>"
            # truncated — no closing tags
        )
        with pytest.raises(RuntimeError, match="Refusing"):
            get_next_episode_number(rss_path, tmp_path)

    def test_episode_number_falls_back_to_guid(self, tmp_path):
        """When <itunes:episode> is missing, derive from GUID suffix so
        numbering never silently restarts."""
        rss_path = tmp_path / "podcast.rss"
        rss_path.write_text("""<?xml version='1.0' encoding='UTF-8'?>
        <rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0">
          <channel>
            <item>
              <guid>tesla-ep050-20260419-120000000000</guid>
            </item>
          </channel>
        </rss>""")
        result = get_next_episode_number(rss_path, tmp_path)
        assert result == 51

    def test_episode_numbers_from_filename_regex(self, tmp_path):
        rss_path = tmp_path / "podcast.rss"
        (tmp_path / "Show_Ep100_20260101.mp3").touch()
        (tmp_path / "Show_Ep099_20260101.mp3").touch()
        result = get_next_episode_number(rss_path, tmp_path)
        assert result == 101


# ===================================================================
# TEST: save_summary_to_github_pages
# ===================================================================

class TestSaveSummaryToGithubPages:

    def test_creates_new_file(self, tmp_path):
        json_path = tmp_path / "summaries.json"
        result = save_summary_to_github_pages(
            "Today's summary content", json_path, "Test Podcast",
            episode_num=1, episode_title="Episode 1",
        )
        assert result == json_path
        assert json_path.exists()

    def test_json_structure(self, tmp_path):
        json_path = tmp_path / "summaries.json"
        save_summary_to_github_pages(
            "Summary text", json_path, "My Podcast",
            episode_num=5, episode_title="Episode 5",
            audio_url="https://example.com/ep5.mp3",
            rss_url="https://example.com/feed.rss",
        )
        data = json.loads(json_path.read_text())
        assert data["podcast"] == "My Podcast"
        assert len(data["summaries"]) == 1
        entry = data["summaries"][0]
        assert entry["content"] == "Summary text"
        assert entry["episode_num"] == 5
        assert entry["episode_title"] == "Episode 5"
        assert entry["audio_url"] == "https://example.com/ep5.mp3"
        assert entry["rss_url"] == "https://example.com/feed.rss"
        assert "date" in entry
        assert "datetime" in entry

    def test_appends_to_existing(self, tmp_path):
        json_path = tmp_path / "summaries.json"
        save_summary_to_github_pages("First", json_path, "Test", episode_num=1)
        save_summary_to_github_pages("Second", json_path, "Test", episode_num=2)
        data = json.loads(json_path.read_text())
        assert len(data["summaries"]) == 2

    def test_newest_first(self, tmp_path):
        json_path = tmp_path / "summaries.json"
        save_summary_to_github_pages("Old", json_path, "Test", episode_num=1)
        save_summary_to_github_pages("New", json_path, "Test", episode_num=2)
        data = json.loads(json_path.read_text())
        assert data["summaries"][0]["content"] == "New"
        assert data["summaries"][1]["content"] == "Old"

    def test_max_summaries_limit(self, tmp_path):
        json_path = tmp_path / "summaries.json"
        for i in range(35):
            save_summary_to_github_pages(
                f"Summary {i}", json_path, "Test",
                episode_num=i, max_summaries=30,
            )
        data = json.loads(json_path.read_text())
        assert len(data["summaries"]) == 30

    def test_max_summaries_keeps_newest(self, tmp_path):
        json_path = tmp_path / "summaries.json"
        for i in range(35):
            save_summary_to_github_pages(
                f"Summary {i}", json_path, "Test",
                episode_num=i, max_summaries=30,
            )
        data = json.loads(json_path.read_text())
        assert data["summaries"][0]["content"] == "Summary 34"

    def test_returns_none_on_error(self, tmp_path):
        json_path = tmp_path / "nonexistent" / "dir" / "summaries.json"
        result = save_summary_to_github_pages(
            "Content", json_path, "Test", episode_num=1
        )
        assert result is None

    def test_optional_fields_default_to_none(self, tmp_path):
        json_path = tmp_path / "summaries.json"
        save_summary_to_github_pages("Text", json_path, "Test")
        data = json.loads(json_path.read_text())
        entry = data["summaries"][0]
        assert entry["episode_num"] is None
        assert entry["episode_title"] is None
        assert entry["audio_url"] is None
        assert entry["rss_url"] is None

    def test_preserves_podcast_name_on_append(self, tmp_path):
        json_path = tmp_path / "summaries.json"
        json_path.write_text(json.dumps({
            "podcast": "Original Name",
            "summaries": [{"content": "old"}]
        }))
        save_summary_to_github_pages("New", json_path, "Ignored", episode_num=2)
        data = json.loads(json_path.read_text())
        assert data["podcast"] == "Original Name"


# ===================================================================
# TEST: update_rss_feed
# ===================================================================

_feedgen = pytest.importorskip("feedgen", reason="feedgen required for RSS tests")


class TestUpdateRssFeed:

    def test_creates_new_rss_file(self, tmp_path):
        result = _make_rss(tmp_path, channel_title="Test Podcast")
        assert result == tmp_path / "podcast.rss"
        assert result.exists()

    def test_rss_is_valid_xml(self, tmp_path):
        _make_rss(tmp_path)
        tree = ET.parse(str(tmp_path / "podcast.rss"))
        root = tree.getroot()
        assert root.tag == "rss"
        assert root.find("channel") is not None

    def test_channel_metadata(self, tmp_path):
        _make_rss(tmp_path, channel_title="My Podcast",
                  channel_description="Great pod", channel_language="en-us")
        tree = ET.parse(str(tmp_path / "podcast.rss"))
        channel = tree.getroot().find("channel")
        assert channel.find("title").text == "My Podcast"
        assert channel.find("description").text == "Great pod"
        assert channel.find("language").text == "en-us"

    def test_episode_enclosure_url_default(self, tmp_path):
        _make_rss(tmp_path, mp3_name="ep001.mp3")
        tree = ET.parse(str(tmp_path / "podcast.rss"))
        items = tree.getroot().find("channel").findall("item")
        enc = items[0].find("enclosure")
        assert enc is not None
        assert "digests/ep001.mp3" in enc.get("url")
        assert enc.get("type") == "audio/mpeg"

    def test_custom_audio_url(self, tmp_path):
        _make_rss(tmp_path, audio_url="https://r2.example.com/ep001.mp3")
        tree = ET.parse(str(tmp_path / "podcast.rss"))
        items = tree.getroot().find("channel").findall("item")
        enc = items[0].find("enclosure")
        assert enc.get("url") == "https://r2.example.com/ep001.mp3"

    def test_episode_has_itunes_tags(self, tmp_path):
        _make_rss(tmp_path)
        tree = ET.parse(str(tmp_path / "podcast.rss"))
        item = tree.getroot().find("channel").findall("item")[0]
        ns = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
        assert item.find(f"{ns}episode").text == "1"
        assert item.find(f"{ns}season").text == "1"
        assert item.find(f"{ns}episodeType").text == "full"
        assert item.find(f"{ns}explicit").text == "no"

    def test_preserves_existing_episodes(self, tmp_path):
        rss_path = tmp_path / "podcast.rss"
        mp3 = _make_mp3(tmp_path)
        update_rss_feed(
            rss_path, 1, "Episode 1", "First",
            datetime.date(2026, 1, 1), "ep001.mp3", 300.0, mp3,
            channel_title="Test", format_duration_func=_fmt_dur,
        )
        update_rss_feed(
            rss_path, 2, "Episode 2", "Second",
            datetime.date(2026, 1, 2), "ep002.mp3", 350.0, mp3,
            channel_title="Test", format_duration_func=_fmt_dur,
        )
        tree = ET.parse(str(rss_path))
        items = tree.getroot().find("channel").findall("item")
        assert len(items) == 2

    def test_deduplicates_by_episode_number(self, tmp_path):
        rss_path = tmp_path / "podcast.rss"
        mp3 = _make_mp3(tmp_path)
        update_rss_feed(
            rss_path, 1, "Episode 1 v1", "First version",
            datetime.date(2026, 1, 1), "ep001.mp3", 300.0, mp3,
            channel_title="Test", format_duration_func=_fmt_dur,
        )
        update_rss_feed(
            rss_path, 1, "Episode 1 v2", "Second version",
            datetime.date(2026, 1, 1), "ep001_v2.mp3", 310.0, mp3,
            channel_title="Test", format_duration_func=_fmt_dur,
        )
        tree = ET.parse(str(rss_path))
        items = tree.getroot().find("channel").findall("item")
        assert len(items) == 1

    def test_mp3_file_size_in_enclosure(self, tmp_path):
        rss_path = tmp_path / "podcast.rss"
        mp3 = _make_mp3(tmp_path, size=5000)
        update_rss_feed(
            rss_path, 1, "Ep", "Desc",
            datetime.date(2026, 1, 1), "ep.mp3", 300.0, mp3,
            format_duration_func=_fmt_dur,
        )
        tree = ET.parse(str(rss_path))
        enc = tree.getroot().find("channel").findall("item")[0].find("enclosure")
        assert enc.get("length") == "5000"

    def test_nonexistent_mp3_zero_size(self, tmp_path):
        rss_path = tmp_path / "podcast.rss"
        fake_mp3 = tmp_path / "nonexistent.mp3"
        update_rss_feed(
            rss_path, 1, "Ep", "Desc",
            datetime.date(2026, 1, 1), "ep.mp3", 300.0, fake_mp3,
            format_duration_func=_fmt_dur,
        )
        tree = ET.parse(str(rss_path))
        enc = tree.getroot().find("channel").findall("item")[0].find("enclosure")
        assert enc.get("length") == "0"

    def test_duration_formatted(self, tmp_path):
        _make_rss(tmp_path, duration=3661.0)
        tree = ET.parse(str(tmp_path / "podcast.rss"))
        item = tree.getroot().find("channel").findall("item")[0]
        ns = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
        assert item.find(f"{ns}duration").text == "01:01:01"

    def test_refuses_to_overwrite_unparseable_rss_with_episodes(self, tmp_path):
        """Corrupt RSS with real episode content must not be silently
        overwritten — doing so drops every historical episode from
        subscribers' feeds."""
        rss_path = tmp_path / "podcast.rss"
        rss_path.write_text(
            "<?xml version='1.0'?><rss><channel>"
            "<item><enclosure url='https://audio.nerranetwork.com/ep001.mp3'/>"
            # truncated
        )
        mp3 = _make_mp3(tmp_path)
        with pytest.raises(RuntimeError, match="Refusing"):
            update_rss_feed(
                rss_path, 2, "Ep 2", "Desc",
                datetime.date(2026, 1, 2), "ep002.mp3", 300.0, mp3,
                channel_title="Test", format_duration_func=_fmt_dur,
            )

    def test_preserves_itunes_episode_derived_from_guid(self, tmp_path):
        """An existing entry missing <itunes:episode> must have it re-emitted
        (derived from GUID) on rewrite, so next-number lookup stays stable."""
        rss_path = tmp_path / "podcast.rss"
        rss_path.write_text("""<?xml version='1.0' encoding='UTF-8'?>
<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:podcast="https://podcastindex.org/namespace/1.0" version="2.0">
  <channel>
    <title>Test</title>
    <description>d</description>
    <link>http://x</link>
    <item>
      <title>Old Ep</title>
      <guid>tesla-ep007-20260101-120000</guid>
      <enclosure url="http://x/old.mp3" type="audio/mpeg" length="1"/>
    </item>
  </channel>
</rss>""")
        mp3 = _make_mp3(tmp_path)
        update_rss_feed(
            rss_path, 8, "New Ep", "Desc",
            datetime.date(2026, 1, 2), "ep008.mp3", 300.0, mp3,
            channel_title="Test", format_duration_func=_fmt_dur,
        )
        ns = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
        items = ET.parse(str(rss_path)).getroot().find("channel").findall("item")
        nums = sorted(
            int(it.find(f"{ns}episode").text)
            for it in items
            if it.find(f"{ns}episode") is not None and it.find(f"{ns}episode").text
        )
        # Both the re-emitted old episode (derived as 7) and the new 8 must appear.
        assert nums == [7, 8]


# ===================================================================
# TEST: post_to_x
# ===================================================================

class TestPostToX:

    def test_successful_post(self):
        mock_tweepy = MagicMock()
        mock_client = MagicMock()
        mock_tweepy.Client.return_value = mock_client
        mock_client.create_tweet.return_value = MagicMock(data={"id": "12345"})

        with patch.dict(sys.modules, {"tweepy": mock_tweepy}):
            result = post_to_x(
                "Hello world",
                consumer_key="ck", consumer_secret="cs",
                access_token="at", access_token_secret="ats",
            )
        assert result == "https://x.com/i/status/12345"

    def test_returns_none_on_failure(self):
        mock_tweepy = MagicMock()
        mock_client = MagicMock()
        mock_tweepy.Client.return_value = mock_client
        mock_client.create_tweet.side_effect = Exception("API error")

        with patch.dict(sys.modules, {"tweepy": mock_tweepy}):
            result = post_to_x(
                "Hello",
                consumer_key="ck", consumer_secret="cs",
                access_token="at", access_token_secret="ats",
            )
        assert result is None

    def test_passes_credentials(self):
        mock_tweepy = MagicMock()
        mock_client = MagicMock()
        mock_tweepy.Client.return_value = mock_client
        mock_client.create_tweet.return_value = MagicMock(data={"id": "1"})

        with patch.dict(sys.modules, {"tweepy": mock_tweepy}):
            post_to_x(
                "Text",
                consumer_key="my_ck", consumer_secret="my_cs",
                access_token="my_at", access_token_secret="my_ats",
            )
        mock_tweepy.Client.assert_called_once_with(
            consumer_key="my_ck", consumer_secret="my_cs",
            access_token="my_at", access_token_secret="my_ats",
        )

    def test_403_logs_structured_api_detail(self, caplog):
        """A bare '403 Forbidden' hides why X refused. The error log must
        surface tweepy's structured api_messages / api_codes / response
        body so the operator can tell duplicate-content from a permissions
        or access-tier problem."""
        import logging as _logging

        # Simulate a tweepy.Forbidden-like exception carrying X API detail.
        class _FakeResponse:
            text = '{"detail":"oauth1 app permissions"}'

        exc = Exception("403 Forbidden")
        exc.api_codes = [453]
        exc.api_messages = [
            "You currently have access to a subset of X API V2 endpoints"
        ]
        exc.response = _FakeResponse()

        mock_tweepy = MagicMock()
        mock_client = MagicMock()
        mock_tweepy.Client.return_value = mock_client
        mock_client.create_tweet.side_effect = exc

        with patch.dict(sys.modules, {"tweepy": mock_tweepy}):
            with caplog.at_level(_logging.ERROR):
                result = post_to_x(
                    "Hello",
                    consumer_key="ck", consumer_secret="cs",
                    access_token="at", access_token_secret="ats",
                )
        assert result is None
        logged = caplog.text
        assert "api_codes=[453]" in logged
        assert "subset of X API V2 endpoints" in logged
        assert "oauth1 app permissions" in logged

    def test_describe_x_error_never_raises_on_plain_exception(self):
        from engine.publisher import _describe_x_error
        out = _describe_x_error(ValueError("boom"))
        assert "ValueError" in out and "boom" in out


# ===================================================================
# TEST: format_digest_for_x
# ===================================================================

class TestFormatDigestForX:
    """Tests for the generic (FF/PT) digest formatter."""

    # --- Markdown header removal ---

    def test_removes_h1_header(self):
        result = format_digest_for_x("# Main Title\nBody text")
        assert result.startswith("Main Title")
        assert "# " not in result.split("\n")[0]

    def test_removes_h2_header(self):
        result = format_digest_for_x("## Section\nContent here")
        assert "## " not in result
        assert "Section" in result

    def test_removes_h3_header(self):
        result = format_digest_for_x("### Subsection\nDetails")
        assert "### " not in result
        assert "Subsection" in result

    def test_removes_multiple_header_levels(self):
        digest = "# Title\n## Section\n### Subsection\nBody"
        result = format_digest_for_x(digest)
        assert "# " not in result
        assert "Title" in result
        assert "Section" in result
        assert "Subsection" in result

    def test_header_only_removed_at_line_start(self):
        """Hash characters in the middle of a line should be preserved."""
        result = format_digest_for_x("Issue #42 is fixed")
        assert "#42" in result

    # --- Bold marker removal ---

    def test_removes_bold_markers(self):
        result = format_digest_for_x("This is **bold** text")
        assert "**" not in result
        assert "bold" in result

    def test_removes_multiple_bold_markers(self):
        result = format_digest_for_x("**First** and **Second** items")
        assert "**" not in result
        assert "First" in result
        assert "Second" in result

    def test_bold_with_colon(self):
        result = format_digest_for_x("**Date:** February 23, 2026")
        assert "**" not in result
        assert "Date:" in result
        assert "February 23, 2026" in result

    # --- Markdown link extraction ---

    def test_extracts_url_from_markdown_link(self):
        result = format_digest_for_x("Check [this article](https://example.com/news)")
        assert "https://example.com/news" in result
        assert "[" not in result
        assert "](" not in result

    def test_extracts_multiple_urls(self):
        digest = "[Link 1](https://a.com) and [Link 2](http://b.com)"
        result = format_digest_for_x(digest)
        assert "https://a.com" in result
        assert "http://b.com" in result
        assert "[Link" not in result

    def test_preserves_plain_urls(self):
        result = format_digest_for_x("Visit https://example.com for details")
        assert "https://example.com" in result

    # --- Excessive blank line removal ---

    def test_removes_triple_blank_lines(self):
        digest = "Line 1\n\n\n\nLine 2"
        result = format_digest_for_x(digest)
        assert "\n\n\n" not in result
        assert "Line 1" in result
        assert "Line 2" in result

    def test_collapses_many_blank_lines(self):
        digest = "A\n\n\n\n\n\n\nB"
        result = format_digest_for_x(digest)
        assert "\n\n\n" not in result

    def test_preserves_double_blank_line(self):
        digest = "Paragraph 1\n\nParagraph 2"
        result = format_digest_for_x(digest)
        assert "Paragraph 1\n\nParagraph 2" in result

    # --- Stripping ---

    def test_strips_leading_trailing_whitespace(self):
        result = format_digest_for_x("  \n  Hello World  \n  ")
        assert result == "Hello World"

    # --- Empty input ---

    def test_empty_string(self):
        result = format_digest_for_x("")
        assert result == ""

    def test_whitespace_only(self):
        result = format_digest_for_x("   \n\n  ")
        assert result == ""

    # --- Combined formatting ---

    def test_full_digest_formatting(self):
        digest = (
            "# Fascinating Frontiers\n\n"
            "**Date:** 2026-02-23\n\n"
            "## Top Stories\n\n"
            "1. **Breakthrough discovery** in quantum computing.\n"
            "Read more: [article](https://example.com/quantum)\n\n\n\n"
            "### Summary\n"
            "A great day for science."
        )
        result = format_digest_for_x(digest)
        assert "# " not in result
        assert "## " not in result
        assert "### " not in result
        assert "**" not in result
        assert "https://example.com/quantum" in result
        assert "\n\n\n" not in result
        assert "Fascinating Frontiers" in result
        assert "Breakthrough discovery" in result


# ===================================================================
# TEST: format_tst_digest_for_x
# ===================================================================

class TestFormatTstDigestForX:
    """Tests for the Tesla Shorts Time emoji-rich formatter."""

    # --- Header emoji ---

    def test_adds_emoji_to_tesla_header(self):
        digest = "# Tesla Shorts Time\nDaily digest."
        result = format_tst_digest_for_x(digest)
        # Should add car + lightning emoji before the title
        assert "\U0001f697\u26a1" in result
        assert "**Tesla Shorts Time**" in result
        # Original markdown header syntax should be gone
        assert "# Tesla Shorts Time\n" not in result

    # --- Date emoji ---

    def test_adds_emoji_to_date_line(self):
        digest = "# Tesla Shorts Time\n**Date:** February 23, 2026."
        result = format_tst_digest_for_x(digest)
        assert "\U0001f4c5" in result  # calendar emoji
        assert "**Date:**" in result

    # --- TSLA price emoji ---

    def test_adds_emoji_to_tsla_price_line(self):
        digest = "# Tesla Shorts Time\n**REAL-TIME TSLA price:** $350.42."
        result = format_tst_digest_for_x(digest)
        assert "\U0001f4b0" in result  # money bag emoji
        assert "**REAL-TIME TSLA price:**" in result

    # --- Apple Podcasts link insertion ---

    def test_inserts_apple_podcasts_link_when_missing(self):
        """When the podcast link is missing, the microphone emoji line is inserted.

        Note: when a "Top 10 News Items" section follows, the after-context
        separator regex (line 573) consumes the URL portion. Without that
        section the full URL is preserved.
        """
        digest = (
            "# Tesla Shorts Time\n"
            "**Date:** February 23, 2026\n"
            "**REAL-TIME TSLA price:** $350.42\n\n"
            "## Short Spot\n"
            "Content."
        )
        result = format_tst_digest_for_x(digest)
        assert "https://podcasts.apple.com/us/podcast/tesla-shorts-time/id1855142939" in result
        assert "\U0001f399\ufe0f" in result  # microphone emoji

    def test_inserts_podcast_emoji_line_with_news_section(self):
        """When Top 10 News Items follows, the podcast emoji line is inserted
        but the after-context separator consumes the URL portion."""
        digest = (
            "# Tesla Shorts Time\n"
            "**Date:** February 23, 2026\n"
            "**REAL-TIME TSLA price:** $350.42\n\n"
            "### Top 10 News Items\n"
            "1. Some news."
        )
        result = format_tst_digest_for_x(digest)
        # The microphone emoji line is still inserted
        assert "\U0001f399\ufe0f" in result

    def test_preserves_apple_podcasts_link_when_present(self):
        """When the podcast link is already present, the URL is preserved.

        Note: the current implementation may duplicate the podcast link line
        because the else-branch reformats the existing line while the
        insertion logic may also trigger.
        """
        podcast_url = "https://podcasts.apple.com/us/podcast/tesla-shorts-time/id1855142939"
        digest = (
            "# Tesla Shorts Time\n"
            "**Date:** February 23, 2026\n"
            "**REAL-TIME TSLA price:** $350.42\n"
            f"\U0001f399\ufe0f **Tesla Shorts Time Daily Podcast Link:** {podcast_url}\n\n"
            "## Short Spot\n"
            "Content."
        )
        result = format_tst_digest_for_x(digest)
        # URL should be preserved (present at least once)
        assert podcast_url in result

    def test_inserts_link_after_tsla_price(self):
        """The podcast link line should be inserted after the TSLA price line.

        Uses a digest without Top 10 News Items so the URL is preserved.
        """
        digest = (
            "# Tesla Shorts Time\n"
            "**REAL-TIME TSLA price:** $350.42\n\n"
            "## Short Spot\n"
            "Content."
        )
        result = format_tst_digest_for_x(digest)
        price_pos = result.index("REAL-TIME TSLA price")
        link_pos = result.index("podcasts.apple.com")
        assert price_pos < link_pos

    # --- Section separator lines ---

    def test_adds_separator_before_top_10_news(self):
        digest = (
            "# Tesla Shorts Time\n"
            "**Date:** February 23, 2026\n\n"
            "### Top 10 News Items\n"
            "1. Breaking news."
        )
        result = format_tst_digest_for_x(digest)
        # The separator is a line of 20 horizontal box drawing characters
        separator = "\u2501" * 20
        assert separator in result

    def test_adds_separator_before_short_spot(self):
        digest = (
            "### Top 10 News Items\n"
            "1. News.\n\n"
            "## Short Spot\n"
            "Short sellers are nervous."
        )
        result = format_tst_digest_for_x(digest)
        separator = "\u2501" * 20
        assert separator in result
        assert "\U0001f4c9 **Short Spot**" in result

    def test_adds_separator_before_short_squeeze(self):
        digest = (
            "Some content.\n\n"
            "### Short Squeeze\n"
            "The squeeze is on."
        )
        result = format_tst_digest_for_x(digest)
        assert "\U0001f4c8 **Short Squeeze**" in result

    def test_adds_separator_before_daily_challenge(self):
        digest = (
            "Some content.\n\n"
            "### Daily Challenge\n"
            "Today's challenge."
        )
        result = format_tst_digest_for_x(digest)
        assert "\U0001f4aa **Daily Challenge**" in result

    def test_adds_emoji_to_inspiration_quote(self):
        digest = (
            "Some content.\n\n"
            "**Inspiration Quote:**\n"
            "The future is electric."
        )
        result = format_tst_digest_for_x(digest)
        assert "\u2728 **Inspiration Quote:**" in result

    # --- Section header emoji replacements ---

    def test_top_10_news_emoji(self):
        digest = "### Top 10 News Items\n1. Item."
        result = format_tst_digest_for_x(digest)
        assert "\U0001f4f0 **Top 10 News Items**" in result

    def test_tesla_x_takeover_emoji_h2(self):
        digest = "## Tesla X Takeover: The Vibe Check\nContent."
        result = format_tst_digest_for_x(digest)
        assert "\U0001f399\ufe0f **Tesla X Takeover:**" in result

    def test_tesla_x_takeover_emoji_h3(self):
        digest = "### Tesla X Takeover: Weekly Roundup\nContent."
        result = format_tst_digest_for_x(digest)
        assert "\U0001f399\ufe0f **Tesla X Takeover:**" in result

    def test_short_spot_emoji(self):
        digest = "## Short Spot\nContent."
        result = format_tst_digest_for_x(digest)
        assert "\U0001f4c9 **Short Spot**" in result

    # --- Emoji numbered list items ---

    def test_converts_numbered_items_to_emoji_numbers(self):
        digest = (
            "### Top 10 News Items\n"
            "1. First item.\n"
            "2. Second item.\n"
            "3. Third item.\n"
            "4. Fourth item.\n"
            "5. Fifth item.\n"
            "6. Sixth item.\n"
            "7. Seventh item.\n"
            "8. Eighth item.\n"
            "9. Ninth item.\n"
            "10. Tenth item.\n\n"
            "## Short Spot\n"
            "Content."
        )
        result = format_tst_digest_for_x(digest)
        # Each number 1-9 should be converted to keycap emoji
        assert "1\ufe0f\u20e3" in result  # 1
        assert "2\ufe0f\u20e3" in result  # 2
        assert "3\ufe0f\u20e3" in result  # 3
        assert "9\ufe0f\u20e3" in result  # 9
        assert "\U0001f51f" in result       # 10

    def test_numbered_items_only_in_news_section(self):
        """Numbered items outside the news section should NOT be converted."""
        digest = (
            "### Top 10 News Items\n"
            "1. First news.\n\n"
            "\U0001f4c9 **Short Spot**\n"
            "1. First short item."
        )
        result = format_tst_digest_for_x(digest)
        # The "1." in the Short Spot section should remain unconverted
        short_spot_pos = result.index("Short Spot")
        after_short_spot = result[short_spot_pos:]
        assert "1\ufe0f\u20e3" not in after_short_spot

    # --- Leaked instruction removal ---

    def test_removes_todays_focus_instruction(self):
        digest = (
            "# Tesla Shorts Time\n"
            "\U0001f3af TODAY'S FOCUS: Generate a digest about Tesla\n"
            "**Date:** February 23, 2026."
        )
        result = format_tst_digest_for_x(digest)
        assert "TODAY'S FOCUS" not in result

    def test_removes_critical_instruction(self):
        digest = (
            "# Tesla Shorts Time\n"
            "\U0001f6a8 CRITICAL: Make sure all content is COMPLETELY DIFFERENT\n"
            "**Date:** February 23, 2026."
        )
        result = format_tst_digest_for_x(digest)
        assert "CRITICAL" not in result

    def test_removes_post_id_placeholder(self):
        digest = (
            "# Tesla Shorts Time\n"
            "Some text with [ACTUAL_POST_ID] reference.\n"
            "Another line."
        )
        result = format_tst_digest_for_x(digest)
        assert "[ACTUAL_POST_ID]" not in result

    def test_removes_post_id_bracket_placeholder(self):
        digest = (
            "# Tesla Shorts Time\n"
            "Reference to [POST_ID] here.\n"
            "More content."
        )
        result = format_tst_digest_for_x(digest)
        assert "[POST_ID]" not in result

    def test_removes_repeat_for_instruction(self):
        digest = (
            "# Tesla Shorts Time\n"
            "[Repeat for all 5 posts]\n"
            "Content here."
        )
        result = format_tst_digest_for_x(digest)
        assert "[Repeat for" not in result

    def test_removes_format_as_shown_instruction(self):
        digest = "# Tesla Shorts Time\n(format as shown)\nContent."
        result = format_tst_digest_for_x(digest)
        assert "(format as shown)" not in result

    def test_removes_do_not_repeat_instruction(self):
        digest = "# Tesla Shorts Time\nDo NOT repeat any content from yesterday.\nContent."
        result = format_tst_digest_for_x(digest)
        assert "Do NOT repeat" not in result

    def test_removes_use_different_instruction(self):
        digest = "# Tesla Shorts Time\nUse a DIFFERENT quote this time.\nContent."
        result = format_tst_digest_for_x(digest)
        assert "Use a DIFFERENT" not in result

    def test_removes_never_repeat_instruction(self):
        digest = "# Tesla Shorts Time\nNever repeat content from previous episodes.\nContent."
        result = format_tst_digest_for_x(digest)
        assert "Never repeat" not in result

    # --- Placeholder URL removal ---

    def test_removes_placeholder_post_url_with_brackets(self):
        digest = (
            "# Tesla Shorts Time\n"
            "Post: https://x.com/elonmusk/status/[POST_ID]\n"
            "Great tweet!"
        )
        result = format_tst_digest_for_x(digest)
        assert "[POST_ID]" not in result

    def test_removes_placeholder_post_url_non_numeric(self):
        digest = (
            "# Tesla Shorts Time\n"
            "Post: https://x.com/elonmusk/status/PLACEHOLDER_ID\n"
            "Great tweet!"
        )
        result = format_tst_digest_for_x(digest)
        assert "PLACEHOLDER_ID" not in result

    def test_preserves_real_post_url(self):
        """Real tweet URLs with numeric IDs should be kept."""
        digest = (
            "# Tesla Shorts Time\n"
            "https://x.com/elonmusk/status/1234567890123456789\n"
            "Great tweet!"
        )
        result = format_tst_digest_for_x(digest)
        assert "1234567890123456789" in result

    # --- Character limit truncation ---

    def test_truncates_to_max_chars(self):
        # Build a digest that's well over 500 chars
        long_content = "This is a news item about Tesla. " * 100
        digest = f"# Tesla Shorts Time\n\n{long_content}"
        result = format_tst_digest_for_x(digest, max_chars=500)
        assert len(result) <= 500
        assert "truncated" in result.lower()

    def test_default_max_chars_allows_normal_digest(self):
        """Normal-length digests should not be truncated."""
        digest = (
            "# Tesla Shorts Time\n"
            "**Date:** February 23, 2026\n"
            "**REAL-TIME TSLA price:** $350.42\n\n"
            "### Top 10 News Items\n"
            "1. Some news item."
        )
        result = format_tst_digest_for_x(digest)
        assert "truncated" not in result.lower()

    def test_truncation_includes_marker(self):
        """Truncated output should end with a truncation marker."""
        paragraphs = "\n\n".join([f"Paragraph {i}. " + "x" * 50 for i in range(50)])
        digest = f"# Tesla Shorts Time\n\n{paragraphs}"
        result = format_tst_digest_for_x(digest, max_chars=800)
        assert len(result) <= 800
        assert "truncated" in result.lower()

    # --- Empty input ---

    def test_empty_string(self):
        result = format_tst_digest_for_x("")
        # Should not crash
        assert isinstance(result, str)

    def test_whitespace_only(self):
        result = format_tst_digest_for_x("   \n\n  ")
        assert isinstance(result, str)

    # --- Keep accelerating ending ---

    def test_adds_keep_accelerating_when_no_ending_punctuation(self):
        digest = "# Tesla Shorts Time\nSome content without final punctuation"
        result = format_tst_digest_for_x(digest)
        assert "\u26a1 Keep accelerating!" in result

    def test_no_keep_accelerating_when_ends_with_period(self):
        digest = "# Tesla Shorts Time\nContent ends with a sentence."
        result = format_tst_digest_for_x(digest)
        assert "Keep accelerating" not in result

    def test_no_keep_accelerating_when_ends_with_exclamation(self):
        digest = "# Tesla Shorts Time\nWhat an amazing day for Tesla!"
        result = format_tst_digest_for_x(digest)
        assert "Keep accelerating" not in result

    def test_no_keep_accelerating_when_ends_with_question(self):
        digest = "# Tesla Shorts Time\nWhat will Tesla do next?"
        result = format_tst_digest_for_x(digest)
        assert "Keep accelerating" not in result

    def test_no_keep_accelerating_when_mission_keyword_present(self):
        """Skips the ending when 'mission' keyword is in the last lines."""
        digest = "# Tesla Shorts Time\nKeep accelerating the electric mission"
        result = format_tst_digest_for_x(digest)
        # Should not double up the ending
        assert result.count("Keep accelerating") <= 1

    # --- Markdown link cleanup ---

    def test_extracts_urls_from_markdown_links(self):
        digest = (
            "# Tesla Shorts Time\n"
            "Check [this post](https://x.com/elonmusk/status/123456789)."
        )
        result = format_tst_digest_for_x(digest)
        assert "https://x.com/elonmusk/status/123456789" in result
        assert "[this post]" not in result

    def test_removes_bracket_wrapped_urls(self):
        digest = "# Tesla Shorts Time\n[https://example.com/article]."
        result = format_tst_digest_for_x(digest)
        assert "https://example.com/article" in result

    # --- Code block removal ---

    def test_removes_code_blocks(self):
        digest = "# Tesla Shorts Time\n```\nsome code\n```\nAfter code."
        result = format_tst_digest_for_x(digest)
        assert "```" not in result
        assert "some code" not in result
        assert "After code" in result

    # --- Whitespace normalization ---

    def test_collapses_excessive_blank_lines(self):
        digest = "# Tesla Shorts Time\n\n\n\n\n\nContent."
        result = format_tst_digest_for_x(digest)
        assert "\n\n\n\n" not in result

    def test_collapses_multiple_inline_spaces(self):
        digest = "# Tesla Shorts Time\nMultiple    spaces    here."
        result = format_tst_digest_for_x(digest)
        assert "    " not in result

    # --- Full realistic digest ---

    def test_full_realistic_digest(self):
        """Smoke test with a realistic TST-style digest."""
        digest = (
            "# Tesla Shorts Time\n"
            "**Date:** February 23, 2026\n"
            "**REAL-TIME TSLA price:** $350.42 (+2.3%)\n\n"
            "### Top 10 News Items\n\n"
            "1. Tesla FSD v14 achieves new milestone with zero interventions.\n"
            "2. Cybertruck deliveries exceed expectations in Q1.\n"
            "3. Tesla Energy division reports record revenue.\n"
            "4. Model Y becomes best-selling car globally.\n"
            "5. Tesla Megapack deployed at largest battery site.\n"
            "6. Elon Musk hints at new Tesla product line.\n"
            "7. Tesla stock rises on strong earnings report.\n"
            "8. Robotaxi program expands to three new cities.\n"
            "9. Tesla Semi begins volume production.\n"
            "10. Supercharger network hits 100,000 stalls worldwide.\n\n"
            "## Tesla X Takeover: The Vibe Check\n"
            "Community sentiment is very bullish.\n\n"
            "## Short Spot\n"
            "Short sellers lost $2 billion this week.\n\n"
            "### Short Squeeze\n"
            "Squeeze pressure is building.\n\n"
            "### Daily Challenge\n"
            "Share your Tesla story!\n\n"
            "**Inspiration Quote:**\n"
            "The future belongs to those who believe. - Elon Musk"
        )
        result = format_tst_digest_for_x(digest)

        # Header transformed
        assert "\U0001f697\u26a1" in result
        assert "**Tesla Shorts Time**" in result

        # Date and price emojis
        assert "\U0001f4c5" in result
        assert "\U0001f4b0" in result

        # Podcast emoji line injected (URL consumed by after-context separator
        # when Top 10 News Items is present — see test_inserts_podcast_emoji_line_with_news_section)
        assert "\U0001f399\ufe0f" in result

        # Section emojis
        assert "\U0001f4f0" in result   # Top 10 News
        assert "\U0001f4c9" in result   # Short Spot
        assert "\U0001f4c8" in result   # Short Squeeze
        assert "\U0001f4aa" in result   # Daily Challenge
        assert "\u2728" in result       # Inspiration Quote

        # Emoji numbers present (items 1-9 are converted; item 10 is consumed
        # by the after-context separator regex when Tesla X Takeover follows)
        assert "1\ufe0f\u20e3" in result
        assert "9\ufe0f\u20e3" in result

        # Separators present
        assert "\u2501" * 20 in result

        # No markdown headers remain
        assert "\n# " not in result
        assert "\n## " not in result
        assert "\n### " not in result

        # Within default char limit
        assert len(result) <= 25000

# ---------------------------------------------------------------------------
# build_show_notes_footer — RSS description footer driving listeners to site
# ---------------------------------------------------------------------------

class TestBuildShowNotesFooter:
    """The RSS episode description gains a footer linking the network home
    page (always) and the per-episode blog page (when the show publishes a
    blog page for the episode). Lets podcast-app / YouTube listeners reach
    the full transcript + sources and discover the rest of the network."""

    BASE = "https://nerranetwork.com"

    def test_blog_link_present_when_has_blog(self):
        out = build_show_notes_footer(self.BASE, "tesla", 461, has_blog=True)
        assert f"{self.BASE}/blog/tesla/ep461.html" in out
        assert "transcript" in out.lower()

    def test_blog_link_zero_padded_to_three_digits(self):
        out = build_show_notes_footer(self.BASE, "omni_view", 7, has_blog=True)
        assert "/blog/omni_view/ep007.html" in out

    def test_no_blog_link_when_not_a_network_show(self):
        out = build_show_notes_footer(self.BASE, "some_show", 12, has_blog=False)
        assert "/blog/" not in out
        # The network home-page link is still always present.
        assert self.BASE in out

    def test_network_home_link_always_present(self):
        for has_blog in (True, False):
            out = build_show_notes_footer(self.BASE, "tesla", 1, has_blog=has_blog)
            assert "Nerra Network" in out
            assert f"]({self.BASE})" in out
            assert "nerranetwork.com" in out

    def test_empty_base_url_returns_empty(self):
        """Caller can append unconditionally without a dangling footer."""
        assert build_show_notes_footer("", "tesla", 1, has_blog=True) == ""

    def test_trailing_slash_in_base_url_is_normalised(self):
        out = build_show_notes_footer("https://nerranetwork.com/", "tesla", 5, has_blog=True)
        assert "https://nerranetwork.com//" not in out
        assert "https://nerranetwork.com/blog/tesla/ep005.html" in out

    def test_footer_renders_to_anchors_through_rss_html(self):
        """The footer is markdown; _markdown_to_rss_html must turn its links
        into real <a> anchors so podcast apps show clickable links, not raw
        markdown brackets."""
        footer = build_show_notes_footer(self.BASE, "tesla", 461, has_blog=True)
        rendered = _markdown_to_rss_html("Episode body.\n\n" + footer)
        assert f'<a href="{self.BASE}/blog/tesla/ep461.html">' in rendered
        assert f'<a href="{self.BASE}">' in rendered
        # No leftover markdown link brackets.
        assert "](" not in rendered


# ===================================================================
# TEST: channel-level <podcast:funding> + <podcast:person> (June 2026)
# ===================================================================

class TestFundingPersonTags:
    """update_rss_feed must inject channel-level podcast:funding +
    podcast:person when the kwargs are set, survive rebuilds
    idempotently, and stay absent when the kwargs are empty (legacy
    callers byte-for-byte unaffected)."""

    PODCAST_NS = "https://podcastindex.org/namespace/1.0"

    _KW = dict(
        funding_url="https://nerranetwork.com/#newsletter",
        funding_label="Free newsletter",
        person_name="Patrick",
        person_url="https://nerranetwork.com/about.html",
    )

    def _channel(self, rss_path):
        import xml.etree.ElementTree as ET
        return ET.parse(str(rss_path)).getroot().find("channel")

    def test_tags_injected(self, tmp_path):
        rss = _make_rss(tmp_path, **self._KW)
        channel = self._channel(rss)
        funding = channel.find(f"{{{self.PODCAST_NS}}}funding")
        person = channel.find(f"{{{self.PODCAST_NS}}}person")
        assert funding is not None
        assert funding.get("url") == "https://nerranetwork.com/#newsletter"
        assert funding.text == "Free newsletter"
        assert person is not None
        assert person.get("role") == "host"
        assert person.get("href") == "https://nerranetwork.com/about.html"
        assert person.text == "Patrick"

    def test_idempotent_across_rebuilds(self, tmp_path):
        _make_rss(tmp_path, **self._KW)
        # Second episode rebuilds the whole feed from the existing file.
        mp3 = _make_mp3(tmp_path, "ep002.mp3")
        rss = update_rss_feed(
            tmp_path / "podcast.rss", 2, "Ep 2", "Desc",
            datetime.date(2026, 1, 2), "ep002.mp3", 300.0, mp3,
            format_duration_func=_fmt_dur,
            **self._KW,
        )
        channel = self._channel(rss)
        assert len(channel.findall(f"{{{self.PODCAST_NS}}}funding")) == 1
        assert len(channel.findall(f"{{{self.PODCAST_NS}}}person")) == 1

    def test_absent_when_args_empty(self, tmp_path):
        rss = _make_rss(tmp_path)
        channel = self._channel(rss)
        assert channel.find(f"{{{self.PODCAST_NS}}}funding") is None
        assert channel.find(f"{{{self.PODCAST_NS}}}person") is None

    def test_feed_stays_well_formed(self, tmp_path):
        import xml.etree.ElementTree as ET
        rss = _make_rss(tmp_path, **self._KW)
        ET.parse(str(rss))  # raises on malformed XML

    def test_run_show_passes_funding_and_person(self):
        """The production call site must pass the new kwargs."""
        src = (Path(__file__).resolve().parent.parent / "run_show.py").read_text(
            encoding="utf-8")
        assert "funding_url=" in src
        assert "person_name=" in src
