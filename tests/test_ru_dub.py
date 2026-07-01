"""Drift guards for the Russian-dubbed YouTube pipeline (engine.ru_dub).

Covers the pure logic + the self-guarding no-op contract. Render/upload
need ffmpeg + @NerraRU credentials and are validated by a real workflow run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine import ru_dub
from engine.config import load_config


def _cfg(**yt):
    return SimpleNamespace(
        slug="tesla", name="Tesla Shorts Time",
        youtube=SimpleNamespace(ru_dub_enabled=True, **yt),
        multilingual=SimpleNamespace(enabled=True, languages=["ru"]),
        publishing=SimpleNamespace(summaries_json="nope.json",
                                   base_url="https://nerranetwork.com"),
        episode=SimpleNamespace(output_dir="digests/tesla_shorts_time"),
        keywords=["Tesla", "Cybercab"],
    )


class TestGalleryImageSelection:
    def _manifest(self, tmp_path):
        m = tmp_path / "gallery-manifest.json"
        m.write_text(json.dumps({"images": [
            {"show_slug": "tesla", "episode_id": "ep526",
             "intended_use": "segment_card", "original_url": "https://r2/a.jpg"},
            {"show_slug": "tesla", "episode_id": "ep526",
             "intended_use": "social", "original_url": "https://r2/b.jpg"},
            {"show_slug": "tesla", "episode_id": "ep525",
             "intended_use": "segment_card", "original_url": "https://r2/c.jpg"},
            {"show_slug": "spacex", "episode_id": "ep526",
             "intended_use": "segment_card", "original_url": "https://r2/d.jpg"},
            {"show_slug": "tesla", "episode_id": "ep526",
             "intended_use": "segment_card"},  # no url → skipped
        ]}), encoding="utf-8")
        return m

    def test_filters_by_show_episode_and_use(self, tmp_path):
        m = self._manifest(tmp_path)
        seg = ru_dub.gallery_images_for_episode(
            "tesla", 526, intended_use="segment_card", manifest_path=m)
        assert seg == ["https://r2/a.jpg"]  # not the social, ep525, spacex, or url-less
        soc = ru_dub.gallery_images_for_episode(
            "tesla", 526, intended_use="social", manifest_path=m)
        assert soc == ["https://r2/b.jpg"]

    def test_zero_padded_episode_id(self):
        assert ru_dub._episode_id(7) == "ep007"
        assert ru_dub._episode_id(526) == "ep526"

    def test_missing_manifest_returns_empty(self, tmp_path):
        assert ru_dub.gallery_images_for_episode(
            "tesla", 1, manifest_path=tmp_path / "nope.json") == []


class TestTextHelpers:
    def test_cap_title(self):
        assert ru_dub._cap_title("short") == "short"
        long = "я" * 200
        assert len(ru_dub._cap_title(long, 95)) <= 95
        assert ru_dub._cap_title(long, 95).endswith("…")

    def test_ru_description_has_disclosure_and_links(self):
        out = ru_dub._ru_long_description(_cfg(), "Описание выпуска")
        assert "Описание выпуска" in out
        assert ru_dub._AI_DISCLOSURE_RU in out
        assert "nerranetwork.com" in out
        assert "#Tesla" in out  # keyword hashtag


class TestShortParity:
    """RU shorts reach EN parity: Russian captions (transcribe the RU audio) +
    smart engaging-beat start + end-card CTA. Full render needs ffmpeg+creds,
    so pin the wiring structurally so it can't silently regress."""

    def test_russian_end_card_text_is_cyrillic(self):
        assert ru_dub._RU_END_CARD_MAIN and ru_dub._RU_END_CARD_SUB
        # Contains Cyrillic (not the English EN defaults).
        assert any("Ѐ" <= ch <= "ӿ" for ch in ru_dub._RU_END_CARD_MAIN)

    def test_short_path_wires_transcript_captions_and_endcard(self):
        src = (Path(ru_dub.__file__)).read_text(encoding="utf-8")
        # Transcribe the RU audio in Russian.
        assert "generate_transcript(" in src and 'language="ru"' in src
        # Smart engaging-beat start + per-word ASS captions.
        assert "pick_engaging_window(" in src
        assert "transcript_to_ass_window(" in src
        assert "subtitles_path=ass_path" in src
        # End-card CTA on the short.
        assert "generate_shorts_end_card(" in src
        assert "end_card=True" in src


class TestGuards:
    def test_skip_when_not_enabled(self):
        cfg = _cfg()
        cfg.youtube.ru_dub_enabled = False
        assert ru_dub.publish_ru_dub(cfg, 1)["status"] == "skip"

    def test_skip_when_ru_not_a_language(self):
        cfg = _cfg()
        cfg.multilingual.languages = ["fr", "es"]
        assert ru_dub.publish_ru_dub(cfg, 1)["status"] == "no_ru_lang"

    def test_no_record_when_summaries_missing(self):
        # summaries_json points at a nonexistent file → no record → skip.
        cfg = _cfg()
        assert ru_dub.publish_ru_dub(cfg, 999)["status"] in ("skip", "no_record")


class TestShortFailureIndex:
    """publish_ru_dubs.py: a failed Short can't be retried alone (publish_ru_dub
    has no short-only path — a retry would re-upload a duplicate long), so the
    failure must at least be recorded durably in the index instead of living
    only in a runner log."""

    def _driver(self):
        import importlib.util
        path = _ROOT / "scripts" / "publish_ru_dubs.py"
        spec = importlib.util.spec_from_file_location("publish_ru_dubs", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _cfg(self, tmp_path):
        return SimpleNamespace(
            episode=SimpleNamespace(output_dir=str(tmp_path)),
        )

    def test_records_failure_row_without_video_id(self, tmp_path):
        drv = self._driver()
        cfg = self._cfg(tmp_path)
        drv._record_short_failure(cfg, 7, "ffmpeg exploded")
        data = json.loads((tmp_path / "youtube_videos.ru.json").read_text())
        rows = [v for v in data["videos"]
                if v.get("episode") == 7 and v.get("status") == "failed"]
        assert len(rows) == 1
        assert rows[0]["kind"] == "short"
        assert "ffmpeg exploded" in rows[0]["error"]
        assert "video_id" not in rows[0]  # analytics/done-check both skip it

    def test_repeat_failure_keeps_single_row(self, tmp_path):
        drv = self._driver()
        cfg = self._cfg(tmp_path)
        drv._record_short_failure(cfg, 7, "first")
        drv._record_short_failure(cfg, 7, "second")
        data = json.loads((tmp_path / "youtube_videos.ru.json").read_text())
        rows = [v for v in data["videos"] if v.get("status") == "failed"]
        assert len(rows) == 1 and rows[0]["error"] == "second"

    def test_failure_row_does_not_mark_episode_done(self, tmp_path):
        drv = self._driver()
        cfg = self._cfg(tmp_path)
        drv._record_short_failure(cfg, 7, "boom")
        # No long row yet → NOT done (the failed episode's long can retry).
        assert drv._already_done(cfg, 7) is False
        # Long recorded → done, even alongside the failed-short row.
        idx = tmp_path / "youtube_videos.ru.json"
        data = json.loads(idx.read_text())
        data["videos"].append({"video_id": "v1", "episode": 7, "kind": "long"})
        idx.write_text(json.dumps(data), encoding="utf-8")
        assert drv._already_done(cfg, 7) is True

    def test_clear_removes_stale_failure_row(self, tmp_path):
        drv = self._driver()
        cfg = self._cfg(tmp_path)
        drv._record_short_failure(cfg, 7, "boom")
        drv._clear_short_failure(cfg, 7)
        data = json.loads((tmp_path / "youtube_videos.ru.json").read_text())
        assert [v for v in data["videos"] if v.get("status") == "failed"] == []


class TestRealShowConfigs:
    def test_four_shows_enabled(self):
        for slug in ("tesla", "spacex", "fascinating_frontiers", "modern_investing"):
            c = load_config(f"shows/{slug}.yaml")
            assert c.youtube.ru_dub_enabled is True, slug
            assert "ru" in (c.multilingual.languages or []), slug

    def test_other_shows_not_enabled(self):
        for slug in ("omni_view", "env_intel", "planetterrian"):
            c = load_config(f"shows/{slug}.yaml")
            assert c.youtube.ru_dub_enabled is False, slug

    def test_ru_dub_requires_ru_audio_track(self):
        """A ru_dub-enabled show MUST also generate a Russian audio track
        (multilingual.enabled + 'ru' in languages) — otherwise the dub has
        no audio to build from. This guards the MIT-class misconfig where
        ru_dub was on but multilingual was off (the dub silently no-ops and
        the translate step errors)."""
        from engine.config import discover_show_slugs
        for slug in discover_show_slugs():
            c = load_config(f"shows/{slug}.yaml")
            if getattr(c.youtube, "ru_dub_enabled", False):
                ml = c.multilingual
                assert ml.enabled and "ru" in (ml.languages or []), (
                    f"{slug}: ru_dub_enabled but no RU audio track "
                    f"(multilingual.enabled={ml.enabled}, languages={ml.languages})"
                )
