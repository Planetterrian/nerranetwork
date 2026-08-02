"""Drift guards for the Pexels stock-video fetcher.

The Pexels *API* imposes an attribution obligation the site licence
does not (credit the creator, link Pexels), so the credit line is a
licence term here rather than a courtesy — those tests are
load-bearing.

Queries and the safety filter are deliberately shared with the still-
image path: landmine #14 (raw ``model 3`` keyword → fashion models in a
Tesla video) was fixed once by curating ``image_queries`` per show, and
video must not reintroduce it by rolling its own.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_SCRIPTS = PROJECT_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import fetch_stock_broll as F  # noqa: E402


def _video(**over):
    base = {
        "id": 12345,
        "duration": 12,
        "url": "https://www.pexels.com/video/rocket-launch-12345/",
        "user": {"name": "Jane Doe", "url": "https://www.pexels.com/@jane"},
        "video_files": [
            {"quality": "hd", "width": 1920, "height": 1080,
             "link": "https://x/hd.mp4"},
            {"quality": "sd", "width": 640, "height": 360,
             "link": "https://x/sd.mp4"},
            {"quality": "uhd", "width": 3840, "height": 2160,
             "link": "https://x/uhd.mp4"},
        ],
    }
    base.update(over)
    return base


class TestOrientation:
    def test_classifies_frames(self):
        assert F.orientation_of(1920, 1080) == "landscape"
        assert F.orientation_of(1080, 1920) == "portrait"
        assert F.orientation_of(1080, 1080) == "square"

    def test_zero_dimensions_are_safe(self):
        assert F.orientation_of(0, 0) == "square"


class TestPickVideoFile:
    def test_prefers_hd_over_uhd_and_sd(self):
        """4K is a needless download for a 1080p render; sd is too soft
        to intercut with the Grok stills."""
        got = F.pick_video_file(_video(), "landscape")
        assert got["quality"] == "hd"

    def test_prefers_a_rendition_matching_the_orientation(self):
        """Pexels returns portrait crops of the same clip; taking the
        wrong one letterboxes or crops the subject out."""
        video = _video(video_files=[
            {"quality": "hd", "width": 1920, "height": 1080,
             "link": "https://x/land.mp4"},
            {"quality": "hd", "width": 1080, "height": 1920,
             "link": "https://x/port.mp4"},
        ])
        assert F.pick_video_file(video, "portrait")["link"].endswith(
            "port.mp4")
        assert F.pick_video_file(video, "landscape")["link"].endswith(
            "land.mp4")

    def test_falls_back_when_no_orientation_matches(self):
        video = _video(video_files=[
            {"quality": "hd", "width": 1920, "height": 1080,
             "link": "https://x/land.mp4"},
        ])
        assert F.pick_video_file(video, "portrait") is not None

    def test_no_files_is_none(self):
        assert F.pick_video_file(_video(video_files=[]), "landscape") is None
        assert F.pick_video_file({}, "landscape") is None

    def test_ignores_entries_without_a_link(self):
        video = _video(video_files=[
            {"quality": "hd", "width": 1920, "height": 1080},
            {"quality": "sd", "width": 640, "height": 360,
             "link": "https://x/sd.mp4"},
        ])
        assert F.pick_video_file(video, "landscape")["link"].endswith(
            "sd.mp4")


class TestAttribution:
    def test_credits_creator_and_links_pexels(self):
        """API terms require both — this is a licence condition."""
        line = F.build_attribution(_video())
        assert "Jane Doe" in line
        assert "Pexels" in line
        assert "https://www.pexels.com/video/rocket-launch-12345/" in line

    def test_missing_user_still_produces_a_credit(self):
        line = F.build_attribution(_video(user={}))
        assert "Pexels" in line
        assert line.strip()

    def test_every_downloaded_row_would_carry_attribution(self):
        """The provenance row shape build_broll_pool reads."""
        row = {
            "file": "a.mp4",
            "attribution": F.build_attribution(_video()),
            "license": "Pexels License (API use requires attribution)",
        }
        assert row["attribution"]
        assert "attribution" in row["license"]


class TestUsabilityGate:
    def test_rejects_clips_too_short_or_too_long(self):
        assert not F.video_is_usable(_video(duration=2), [])
        assert not F.video_is_usable(_video(duration=600), [])
        assert F.video_is_usable(_video(duration=12), [])

    def test_applies_the_shared_safety_filter(self):
        """Landmine #14: the image path's skip terms must protect video
        too, via the SAME helper."""
        bad = _video(url="https://www.pexels.com/video/topless-model-999/")
        assert not F.video_is_usable(bad, ["topless"])
        assert F.video_is_usable(_video(), ["topless"])

    def test_safety_filter_is_imported_not_reimplemented(self):
        from engine.visual_assets import _photo_is_safe
        assert F._photo_is_safe is _photo_is_safe
        src = (_SCRIPTS / "fetch_stock_broll.py").read_text(encoding="utf-8")
        assert "def _photo_is_safe" not in src


class TestQueryResolution:
    def _cfg(self, **yt):
        return SimpleNamespace(
            youtube=SimpleNamespace(**yt), keywords=["model 3", "model y"])

    def test_explicit_queries_win(self):
        cfg = self._cfg(image_queries=["curated one"])
        assert F.resolve_queries(cfg, ["ad hoc"]) == ["ad hoc"]

    def test_uses_the_shows_curated_image_queries(self):
        cfg = self._cfg(image_queries=["tesla car charging at a station"])
        assert F.resolve_queries(cfg, []) == [
            "tesla car charging at a station"]

    def test_keyword_fallback_applies_the_disambiguating_prefix(self):
        """Raw 'model 3' is exactly what shipped fashion models into a
        Tesla video; the prefix is the fix."""
        cfg = self._cfg(image_queries=[], image_query_prefix="tesla electric car")
        got = F.resolve_queries(cfg, [])
        assert all(q.startswith("tesla electric car") for q in got)

    def test_real_shows_have_queries_to_drive_video_search(self):
        from engine.config import load_config
        for slug in ("tesla", "spacex", "models_agents"):
            cfg = load_config(f"shows/{slug}.yaml")
            assert F.resolve_queries(cfg, []), f"{slug} has no queries"


class TestProvenance:
    def test_merge_preserves_earlier_rows(self, tmp_path):
        (tmp_path / "_provenance.json").write_text(
            json.dumps([{"file": "old.mp4", "attribution": "old credit"}]),
            encoding="utf-8")
        F._write_provenance(tmp_path, [
            {"file": "new.mp4", "attribution": "new credit"}])
        rows = json.loads(
            (tmp_path / "_provenance.json").read_text(encoding="utf-8"))
        assert {r["file"] for r in rows} == {"old.mp4", "new.mp4"}

    def test_filenames_are_filesystem_safe(self):
        name = F.safe_name(_video(), "rocket launch / at dusk!")
        assert "/" not in name and name.endswith(".mp4")


class TestDocumentation:
    def test_source_survey_records_the_disqualifying_licences(self):
        """The two findings most likely to be re-proposed by someone
        reading a listicle."""
        doc = (PROJECT_ROOT / "docs" / "broll_sources.md").read_text(
            encoding="utf-8")
        assert "CC BY-NC" in doc
        assert "CC BY-SA" in doc
        assert "0 of 210" in doc
