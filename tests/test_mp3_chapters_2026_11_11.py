"""Chapters reach every podcast app (Nov 11 2026).

The chapter JSON and ``<podcast:chapters>`` were on every feed, but Apple
Podcasts and Overcast read chapters only from the MP3's ID3 tag and Spotify
only from description timestamps, so no episode had chapters there. These
guards pin the three ways chapters now reach an app, and that a published
MP3's chapters never ride into a splice.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from engine.audio_chapters import (
    chapter_marks,
    chapter_timestamp_block,
    embed_chapters_cmd,
    embed_chapters_in_mp3,
    ffmetadata_text,
    read_mp3_chapters,
)

ROOT = Path(__file__).resolve().parent.parent
HAVE_FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")

CHAPTERS = {"version": "1.2.0", "chapters": [
    {"startTime": 0.0, "title": "Introduction"},
    {"startTime": 14.6, "title": "Lead; story = one #1"},
    {"startTime": 31.0, "title": "Second story"},
    {"startTime": 50.0, "title": "Closing"},
]}


def _mp3(path: Path, seconds: int = 60) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=f=330:d={seconds}", "-ac", "2", "-c:a", "libmp3lame",
         "-q:a", "0", "-metadata", "title=Ep 1", str(path)], check=True)
    return path


def _pcm_md5(path: Path) -> str:
    return subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(path), "-f", "md5", "-"],
        check=True, capture_output=True, text=True).stdout.strip()


class TestFfmetadata:
    def test_one_chapter_block_per_mark_ending_at_the_next(self):
        text = ffmetadata_text(chapter_marks(CHAPTERS), 60.0)
        assert text.startswith(";FFMETADATA1\n")
        assert text.count("[CHAPTER]") == 4
        assert "START=14600\nEND=31000" in text
        assert "END=60000" in text

    def test_syntax_characters_are_escaped(self):
        text = ffmetadata_text(chapter_marks(CHAPTERS), 60.0)
        assert r"title=Lead\; story \= one \#1" in text

    def test_fewer_than_two_or_past_the_end_writes_nothing(self):
        one = {"chapters": [{"startTime": 0, "title": "Only"}]}
        assert ffmetadata_text(chapter_marks(one), 60.0) == ""
        assert ffmetadata_text(chapter_marks(CHAPTERS), 40.0) == ""

    def test_the_command_copies_audio_and_takes_chapters_from_the_metadata(self):
        cmd = embed_chapters_cmd(Path("in.mp3"), Path("m.ffmeta"), Path("out.mp3"))
        assert cmd[cmd.index("-c") + 1] == "copy"
        assert cmd[cmd.index("-map_chapters") + 1] == "1"
        assert cmd[cmd.index("-map_metadata") + 1] == "0"
        assert cmd[cmd.index("-id3v2_version") + 1] == "3"


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")
class TestEmbed:
    def test_chapters_land_in_the_id3_tag_and_the_audio_is_untouched(self, tmp_path):
        mp3 = _mp3(tmp_path / "ep.mp3")
        before = _pcm_md5(mp3)
        assert embed_chapters_in_mp3(mp3, CHAPTERS) == 4
        assert _pcm_md5(mp3) == before
        got = read_mp3_chapters(mp3)
        assert [c["title"] for c in got] == [c["title"] for c in CHAPTERS["chapters"]]
        assert got[1]["start"] == pytest.approx(14.6, abs=0.01)
        head = mp3.read_bytes()[:8192]
        assert head[:3] == b"ID3" and head[3] == 3
        assert b"CTOC" in head and b"CHAP" in head

    def test_existing_tags_survive_and_a_re_embed_replaces(self, tmp_path):
        mp3 = _mp3(tmp_path / "ep.mp3")
        embed_chapters_in_mp3(mp3, CHAPTERS)
        fewer = {"chapters": CHAPTERS["chapters"][:2]}
        assert embed_chapters_in_mp3(mp3, fewer) == 2
        assert len(read_mp3_chapters(mp3)) == 2
        tags = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format_tags",
             "-of", "json", str(mp3)], capture_output=True, text=True).stdout)
        assert tags["format"]["tags"]["title"] == "Ep 1"

    def test_nothing_to_embed_leaves_the_file_byte_identical(self, tmp_path):
        mp3 = _mp3(tmp_path / "ep.mp3")
        raw = mp3.read_bytes()
        assert embed_chapters_in_mp3(mp3, {"chapters": []}) == 0
        assert embed_chapters_in_mp3(mp3, tmp_path / "missing.json") == 0
        assert mp3.read_bytes() == raw
        assert list(tmp_path.iterdir()) == [mp3]

    def test_a_join_never_inherits_an_episodes_chapters(self, tmp_path):
        from engine.audio import concatenate_audio

        a = _mp3(tmp_path / "a.mp3", 30)
        embed_chapters_in_mp3(a, {"chapters": [
            {"startTime": 0, "title": "A1"}, {"startTime": 15, "title": "A2"}]})
        b = _mp3(tmp_path / "b.mp3", 20)
        out = tmp_path / "joined.mp3"
        concatenate_audio([a, b], out)
        assert read_mp3_chapters(out) == []


class TestShowNotes:
    def test_block_follows_the_youtube_rules(self):
        block = chapter_timestamp_block(CHAPTERS)
        lines = block.splitlines()
        assert lines[0] == "Chapters:"
        assert lines[1] == "0:00 Introduction"
        assert all(re.match(r"^\d+:\d{2} \S", ln) for ln in lines[1:])

    def test_russian_label(self):
        assert chapter_timestamp_block(CHAPTERS, language="ru").startswith("Главы:")

    def test_nothing_renders_without_two_chapters(self):
        assert chapter_timestamp_block({"chapters": []}) == ""


class TestWiring:
    def test_run_show_embeds_before_publish_and_writes_notes(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        embed = src.index("embed_chapters_in_mp3(")
        assert embed < src.index("=== Rehearsal stop (--rehearse) ===")
        assert "chapter_timestamp_block(" in src

    def test_edition_and_personal_embed_their_own_chapters(self):
        for rel in ("scripts/build_daily_edition.py",
                    "scripts/build_personal_feeds.py"):
            assert "embed_chapters_in_mp3(" in (ROOT / rel).read_text(encoding="utf-8")

    def test_segment_trim_never_carries_the_episode_chapters(self):
        from engine.daily_edition import segment_trim_cmd

        cmd = segment_trim_cmd(Path("in.mp3"), Path("out.flac"), None)
        assert cmd[cmd.index("-map_chapters") + 1] == "-1"

    def test_interview_publish_writes_vouched_chapters_to_the_feed(self):
        src = (ROOT / "pipelines/voices/publish_episode.py").read_text(encoding="utf-8")
        assert "write_chapters_json(vouched_chapters(pkg)" in src
        assert 'podcast_tags["chapters_url"]' in src

    @pytest.mark.parametrize("feed", ["age_of_ai_podcast.rss",
                                      "nerra_voices_podcast.rss"])
    def test_interview_feed_chapter_urls_point_at_committed_files(self, feed):
        text = (ROOT / feed).read_text(encoding="utf-8")
        urls = re.findall(r'<podcast:chapters url="https://nerranetwork.com/([^"]+)"', text)
        assert urls, f"{feed} carries no <podcast:chapters>"
        for rel in urls:
            data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            assert len(data["chapters"]) >= 2
