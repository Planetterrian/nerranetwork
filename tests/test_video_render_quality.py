"""Drift guards for the July 2026 video render quality pass.

Four things this pins, each of which was measured rather than assumed:

* **Caption size is not in pixels.** ffmpeg's ``subtitles`` filter
  renders SRT through libass at the ASS default ``PlayResY=288``, so
  every ``FontSize`` is multiplied by ``1080/288 = 3.75`` on a 1080p
  frame. FontSize=22 was ~82 px, already readable — an earlier draft of
  this change read the number as pixels, went to 32, and produced ~120 px
  captions that swallowed the lower third. The band below exists so
  nobody repeats that.
* **Every delivered pixel is an upsample.** Grok returns 1792x1024 for
  16:9, below the 1080p delivery frame. The zoom ceiling and scaler
  choice are the only levers, so they are pinned.
* **Two lossy encodes compound.** The stage-1 intermediate must stay at
  a materially lower CRF than the stage-2 delivery encode, or stage 1
  becomes the quality bottleneck for a file nobody keeps.
* **Chapters must reach the container.** They already reach the YouTube
  description and both RSS feeds; the MP4 chapter track is what Apple's
  video player and an offline copy can use.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

import engine.video as V  # noqa: E402


class TestCaptionLegibility:
    def test_long_form_font_size_is_in_the_measured_band(self):
        """Below 24 is the old too-small setting; above 28 renders over
        ~105 px and starts dominating the frame. See module docstring for
        why these are not pixel values."""
        size = int(re.search(r"FontSize=(\d+)", V._SUBTITLES_FORCE_STYLE).group(1))
        assert 24 <= size <= 28, (
            f"FontSize={size} renders at ~{size * 1080 / 288:.0f} px on a "
            f"1080p frame — outside the band that was visually compared")

    def test_long_form_stays_outline_only(self):
        """A BorderStyle=3 card would band across the slideshow imagery
        that is the whole point of a 16:9 video. The Shorts pipeline uses
        the card because a 9:16 frame is mostly empty."""
        assert "BorderStyle=1" in V._SUBTITLES_FORCE_STYLE

    def test_shorts_keep_their_card(self):
        assert "BorderStyle=3" in V._SHORTS_SUBTITLES_FORCE_STYLE


class TestKenBurnsGeometry:
    def test_zoom_ceiling_bounds_the_upsample(self):
        """1792 px sources into a 1920 px frame: the zoom is added on top
        of an upsample that already exists, so it has to stay modest."""
        assert 1.0 < V._ZOOM_MAX <= 1.10

    def test_prescale_keeps_headroom_above_the_output_frame(self):
        """Working above output resolution is what hides zoompan's
        integer-pixel stepping. At maximum zoom the sampled width must
        still be at least the delivery width, or the motion itself
        starts upsampling on top of everything else."""
        sampled = 1920 * V._PRESCALE / V._ZOOM_MAX
        assert sampled >= 1920, f"sampled width {sampled:.0f} < 1920"

    def test_scaler_is_lanczos(self):
        """ffmpeg defaults to bicubic, which is visibly softer on the
        upsample this pipeline is always doing."""
        assert "lanczos" in V._SCALE_FLAGS
        graph = V._slideshow_filter_graph(3)
        assert graph.count("flags=lanczos") == 3

    def test_graph_still_produces_one_output_label(self):
        for count in (1, 2, 5):
            assert V._slideshow_filter_graph(count).rstrip().endswith("[v]")


class TestEncodeProfile:
    def _flag(self, profile, name):
        return profile[profile.index(name) + 1]

    def test_intermediate_is_higher_quality_than_delivery(self):
        """Stage 1 is re-encoded by stage 2, so its errors compound into
        the delivered file. Lower CRF is higher quality."""
        intermediate = int(self._flag(V._VIDEO_ENCODE_FAST, "-crf"))
        delivery = int(self._flag(V._VIDEO_ENCODE, "-crf"))
        assert intermediate <= delivery - 4, (
            f"intermediate CRF {intermediate} is too close to delivery "
            f"CRF {delivery} — generational loss dominates")

    def test_intermediate_stays_on_a_fast_preset(self):
        """The render-minute budget lives in the preset, not the CRF."""
        assert self._flag(V._VIDEO_ENCODE_FAST, "-preset") == "veryfast"

    def test_delivery_has_a_bitrate_ceiling(self):
        """Episodes measure ~2.0 Mbps, so this never binds — it exists so
        a pathological still cannot produce an enclosure Apple times out
        fetching."""
        assert "-maxrate" in V._VIDEO_ENCODE and "-bufsize" in V._VIDEO_ENCODE

    def test_crf_still_drives_quality(self):
        """A ceiling without CRF would be constant-bitrate, which wastes
        bits on a slideshow and starves the few busy moments."""
        assert "-crf" in V._VIDEO_ENCODE
        assert "-b:v" not in V._VIDEO_ENCODE


class TestChapterMetadata:
    def _write(self, tmp_path, chapters):
        p = tmp_path / "ch.json"
        p.write_text(json.dumps({"version": "1.2.0", "chapters": chapters}))
        return p

    def test_writes_ffmetadata_for_a_real_chapter_list(self, tmp_path):
        src = self._write(tmp_path, [
            {"startTime": 0, "title": "Introduction"},
            {"startTime": 60, "title": "Middle"},
            {"startTime": 120, "title": "Close"},
        ])
        out = V.write_chapter_metadata(src, tmp_path / "m.ffmeta", 180.0)
        assert out is not None
        text = out.read_text()
        assert text.startswith(";FFMETADATA1")
        assert text.count("[CHAPTER]") == 3
        assert "END=180000" in text  # last chapter runs to the audio end

    def test_single_chapter_is_not_worth_a_track(self, tmp_path):
        src = self._write(tmp_path, [{"startTime": 0, "title": "All of it"}])
        assert V.write_chapter_metadata(src, tmp_path / "m.ffmeta", 180.0) is None

    def test_missing_file_degrades_quietly(self, tmp_path):
        assert V.write_chapter_metadata(
            tmp_path / "nope.json", tmp_path / "m.ffmeta", 180.0) is None

    def test_malformed_json_degrades_quietly(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json")
        assert V.write_chapter_metadata(bad, tmp_path / "m.ffmeta", 180.0) is None

    def test_duration_shorter_than_the_last_chapter_is_rejected(self, tmp_path):
        """Would emit END <= START and make ffmpeg fail the whole render."""
        src = self._write(tmp_path, [
            {"startTime": 0, "title": "A"}, {"startTime": 600, "title": "B"}])
        assert V.write_chapter_metadata(src, tmp_path / "m.ffmeta", 300.0) is None

    def test_titles_with_syntax_characters_are_escaped(self, tmp_path):
        src = self._write(tmp_path, [
            {"startTime": 0, "title": "Cost = $9; margin #1"},
            {"startTime": 60, "title": "Next"},
        ])
        out = V.write_chapter_metadata(src, tmp_path / "m.ffmeta", 120.0)
        line = [ln for ln in out.read_text().splitlines()
                if ln.startswith("title=Cost")][0]
        assert line == r"title=Cost \= $9\; margin \#1"

    def test_unsorted_chapters_are_ordered(self, tmp_path):
        src = self._write(tmp_path, [
            {"startTime": 120, "title": "Third"},
            {"startTime": 0, "title": "First"},
            {"startTime": 60, "title": "Second"},
        ])
        out = V.write_chapter_metadata(src, tmp_path / "m.ffmeta", 180.0)
        titles = [ln[6:] for ln in out.read_text().splitlines()
                  if ln.startswith("title=")]
        assert titles == ["First", "Second", "Third"]

    def test_real_committed_chapters_file_parses(self, tmp_path):
        """The shape actually on disk, not a hand-built fixture."""
        real = sorted(ROOT.glob("digests/*/chapters_ep*.json"))
        if not real:
            pytest.skip("no committed chapters files in this tree")
        out = V.write_chapter_metadata(real[-1], tmp_path / "m.ffmeta", 7200.0)
        assert out is not None and "[CHAPTER]" in out.read_text()


class TestChapterInputWiring:
    """The ffmetadata input carries no streams, so it must not disturb the
    ``[0:v]``/``[1:a]``/``[2:v]``/``[3:v]`` indices the filter graph is
    written against — it goes last, and -map_metadata points past them."""

    def test_metadata_index_without_the_url_pill(self):
        cmd = V._long_form_cmd("a.mp3", "bg.mp4", "brand.png", "o.mp4",
                               bg_is_video=True, chapter_metadata_in="m.ffmeta")
        assert cmd[cmd.index("-map_metadata") + 1] == "3"
        assert cmd[-2] == "-movflags" or cmd[-1] == "o.mp4"

    def test_metadata_index_with_the_url_pill(self):
        cmd = V._long_form_cmd("a.mp3", "bg.mp4", "brand.png", "o.mp4",
                               bg_is_video=True, url_pill_in="pill.png",
                               chapter_metadata_in="m.ffmeta")
        assert cmd[cmd.index("-map_metadata") + 1] == "4"

    def test_metadata_input_is_last(self):
        cmd = V._long_form_cmd("a.mp3", "bg.mp4", "brand.png", "o.mp4",
                               bg_is_video=True, url_pill_in="pill.png",
                               chapter_metadata_in="m.ffmeta")
        inputs = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-i"]
        assert inputs[-1] == "m.ffmeta"

    def test_no_metadata_flags_when_no_chapters(self):
        cmd = V._long_form_cmd("a.mp3", "bg.mp4", "brand.png", "o.mp4",
                               bg_is_video=True)
        assert "-map_metadata" not in cmd
        assert "ffmetadata" not in cmd


class TestGalleryBlendPoolSize:
    def test_long_form_pool_outgrew_the_slot_count_problem(self):
        """Only 4 fresh images are generated per episode and the scheduler
        can place up to 24 slots. The library blend is the free way to
        stop images repeating five times in one episode."""
        from engine.config import YouTubeConfig
        from engine.scene_scheduler import _MAX_SLIDESHOW_SLOTS

        fresh = 4
        pool = fresh + YouTubeConfig().gallery_blend_max_long
        assert pool >= _MAX_SLIDESHOW_SLOTS * 0.75, (
            f"pool of {pool} against {_MAX_SLIDESHOW_SLOTS} slots still "
            f"repeats heavily")
