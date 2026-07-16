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

from engine import ru_dub  # noqa: E402
from engine.config import load_config  # noqa: E402


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


class TestRuShortTitle:
    """The RU Short title must be DISTINCT from the long title, word-boundary
    trimmed (never mid-word), carry ' #Shorts', and clear YouTube's 100-char
    cap. Replaces the old `_cap_title(ru_title, 90) + ' #Shorts'` which was a
    carbon copy of the long, truncated mid-word."""

    def test_appends_shorts_and_drops_episode_prefix(self):
        t = ru_dub._ru_short_title(
            "Эп. 5: Патент Tesla превращает компрессор в бойлер")
        assert t.endswith(" #Shorts")
        assert not t.lstrip().startswith("Эп")
        assert "Патент Tesla" in t
        assert len(t) <= 100

    def test_word_boundary_never_mid_word(self):
        long = "Эп. 5: " + "Патент " * 30  # far over the ceiling
        t = ru_dub._ru_short_title(long)
        body = t[: -len(" #Shorts")]
        # The trim breaks between words, so the last token is a whole "Патент".
        assert body.split()[-1] == "Патент"
        assert len(t) <= 100

    def test_no_ellipsis_before_shorts_and_distinct_from_long(self):
        long_title = "Эп. 5: " + "слово " * 40
        long_cap = ru_dub._cap_title(long_title)   # long form (ends with …)
        short = ru_dub._ru_short_title(long_title)
        assert short != long_cap
        assert "…" not in short
        assert short.endswith(" #Shorts")
        assert len(short) <= 100

    def test_short_title_short_input_still_distinct(self):
        # Even a short title (no prefix, no trim) differs by the suffix.
        long = "Патент Tesla"
        short = ru_dub._ru_short_title(long)
        assert short == "Патент Tesla #Shorts"
        assert short != long


class TestRuLongTitleFromOptimized:
    """The RU long-form title prefers the EN optimized YouTube title
    (translated), falling back to the legacy hook-based ru_track title when
    there's no optimized title or translation fails — never raises."""

    _LEGACY = "Эп. 5: старый хук из перевода который довольно длинный текст для проверки"

    def _cfg_with(self, tmp_path, *, en_long_title="Tesla Patent Runs Compressor As Boiler"):
        out = tmp_path / "out"
        out.mkdir()
        if en_long_title is not None:
            (out / "youtube_videos.json").write_text(json.dumps({"videos": [
                {"episode": 5, "kind": "long", "title": en_long_title,
                 "hook": "Tesla's new winter heat patent turns the compressor..."},
                {"episode": 5, "kind": "short", "title": "some short headline"},
            ]}), encoding="utf-8")
        summaries = tmp_path / "summaries.json"
        summaries.write_text(json.dumps({"podcast": "TST", "summaries": [{
            "episode_num": 5, "date": "2026-07-01", "episode_title": "Ep 5",
            "translations": {"ru": {"title": self._LEGACY, "description": "Оп",
                                    "audio_url": ""}}}]}), encoding="utf-8")
        cfg = _cfg()
        cfg.publishing.summaries_json = str(summaries)
        cfg.episode.output_dir = str(out)
        return cfg

    def test_reads_optimized_long_title_from_index(self, tmp_path):
        cfg = self._cfg_with(tmp_path)
        assert ru_dub._en_optimized_long_title(cfg, 5) == \
            "Tesla Patent Runs Compressor As Boiler"

    def test_missing_index_returns_empty(self, tmp_path):
        cfg = self._cfg_with(tmp_path, en_long_title=None)
        assert ru_dub._en_optimized_long_title(cfg, 5) == ""

    def test_long_title_prefers_translated_optimized(self, tmp_path, monkeypatch):
        cfg = self._cfg_with(tmp_path)
        import engine.translate as tr
        monkeypatch.setattr(tr, "translate_metadata", lambda title, desc, lang: (
            "Патент Tesla превращает компрессор в бойлер", desc))
        res = ru_dub.publish_ru_dub(cfg, 5, dry_run=True)
        assert res["status"] == "dryrun"
        assert res["title"] == "Патент Tesla превращает компрессор в бойлер"
        # Short is derived + distinct.
        assert res["short_title"].endswith(" #Shorts")
        assert res["short_title"] != res["title"]
        assert len(res["short_title"]) <= 100

    def test_falls_back_to_hook_when_no_optimized(self, tmp_path, monkeypatch):
        cfg = self._cfg_with(tmp_path, en_long_title=None)
        import engine.translate as tr

        def boom(*a, **k):
            raise AssertionError("translate must not be called without a title")
        monkeypatch.setattr(tr, "translate_metadata", boom)
        res = ru_dub.publish_ru_dub(cfg, 5, dry_run=True)
        assert res["title"] == ru_dub._cap_title(self._LEGACY)

    def test_translate_failure_keeps_legacy_title(self, tmp_path, monkeypatch):
        cfg = self._cfg_with(tmp_path)
        import engine.translate as tr

        def boom(*a, **k):
            raise RuntimeError("grok down")
        monkeypatch.setattr(tr, "translate_metadata", boom)
        res = ru_dub.publish_ru_dub(cfg, 5, dry_run=True)  # must NOT raise
        assert res["status"] == "dryrun"
        assert res["title"] == ru_dub._cap_title(self._LEGACY)

    def test_english_result_rejected_keeps_legacy_title(self, tmp_path, monkeypatch):
        # translate_metadata falls back to the English input on failure — a
        # no-Cyrillic result must not ship an English title on @NerraRU.
        cfg = self._cfg_with(tmp_path)
        import engine.translate as tr
        monkeypatch.setattr(tr, "translate_metadata",
                            lambda title, desc, lang: (title, desc))
        res = ru_dub.publish_ru_dub(cfg, 5, dry_run=True)
        assert res["title"] == ru_dub._cap_title(self._LEGACY)


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


class TestFreshEpisode:
    """_is_fresh_episode decides defer-vs-cover for scene-less episodes."""

    def test_today_and_yesterday_are_fresh(self):
        import datetime
        today = datetime.date(2026, 7, 1)
        assert ru_dub._is_fresh_episode("2026-07-01", today=today) is True
        assert ru_dub._is_fresh_episode("2026-06-30", today=today) is True

    def test_older_episodes_are_not_fresh(self):
        import datetime
        today = datetime.date(2026, 7, 1)
        assert ru_dub._is_fresh_episode("2026-06-29", today=today) is False
        assert ru_dub._is_fresh_episode("2026-01-01", today=today) is False

    def test_unparsable_dates_count_as_old(self):
        # Malformed record must PUBLISH (with cover), never stall forever.
        assert ru_dub._is_fresh_episode("") is False
        assert ru_dub._is_fresh_episode("soonish") is False

    def test_datetime_prefix_accepted(self):
        import datetime
        today = datetime.date(2026, 7, 1)
        assert ru_dub._is_fresh_episode("2026-07-01T09:00:00+00:00",
                                        today=today) is True


class TestManifestRefresh:
    """_fresh_manifest_path: best-effort origin/main refresh, checked-out
    fallback on ANY failure — the sweep's checkout can lag the manifest
    rebuild workflow, so fresh episodes' scenes only exist on origin/main."""

    def _fake_run(self, show_rc=0, show_stdout=b'{"images": []}'):
        calls = []

        def run(cmd, **kwargs):
            calls.append(cmd)
            assert kwargs.get("timeout"), "git calls must carry a timeout"
            if cmd[:2] == ["git", "fetch"]:
                return SimpleNamespace(returncode=0, stdout=b"")
            if cmd[:2] == ["git", "show"]:
                return SimpleNamespace(returncode=show_rc, stdout=show_stdout)
            raise AssertionError(f"unexpected command {cmd}")

        return run, calls

    def test_refresh_writes_origin_copy(self, tmp_path, monkeypatch):
        run, calls = self._fake_run(
            show_stdout=b'{"images": [{"image_id": "x"}]}')
        monkeypatch.setattr(ru_dub.subprocess, "run", run)
        p = ru_dub._fresh_manifest_path(tmp_path)
        assert p.parent == tmp_path
        assert json.loads(p.read_text(encoding="utf-8"))["images"]
        assert [c[:2] for c in calls] == [["git", "fetch"], ["git", "show"]]

    def test_git_failure_falls_back_to_checkout(self, tmp_path, monkeypatch):
        run, _ = self._fake_run(show_rc=128, show_stdout=b"")
        monkeypatch.setattr(ru_dub.subprocess, "run", run)
        assert ru_dub._fresh_manifest_path(tmp_path) == ru_dub._MANIFEST

    def test_corrupt_origin_blob_falls_back(self, tmp_path, monkeypatch):
        run, _ = self._fake_run(show_stdout=b"{truncated")
        monkeypatch.setattr(ru_dub.subprocess, "run", run)
        assert ru_dub._fresh_manifest_path(tmp_path) == ru_dub._MANIFEST

    def test_subprocess_exception_falls_back(self, tmp_path, monkeypatch):
        def boom(*a, **k):
            raise OSError("no git binary")
        monkeypatch.setattr(ru_dub.subprocess, "run", boom)
        assert ru_dub._fresh_manifest_path(tmp_path) == ru_dub._MANIFEST

    def test_non_repo_manifest_skips_git(self, tmp_path, monkeypatch):
        def never(*a, **k):
            raise AssertionError("git must not run for a non-repo manifest")
        monkeypatch.setattr(ru_dub.subprocess, "run", never)
        outside = tmp_path / "m.json"
        assert ru_dub._fresh_manifest_path(
            tmp_path, manifest_path=outside) == outside


class TestNoScenesYetGate:
    """A FRESH scene-less episode defers (no_scenes_yet) instead of shipping
    a cover-only dub; an OLD scene-less episode still publishes with the
    cover (no scenes are ever coming for it)."""

    def _cfg_with_summaries(self, tmp_path, date_str):
        summaries = tmp_path / "summaries.json"
        summaries.write_text(json.dumps({"podcast": "TST", "summaries": [{
            "episode_num": 5,
            "date": date_str,
            "episode_title": "Ep 5",
            "translations": {"ru": {"title": "Заголовок", "description": "Оп",
                                    "audio_url": ""}},
        }]}), encoding="utf-8")
        cfg = _cfg()
        cfg.publishing.summaries_json = str(summaries)
        cfg.episode.output_dir = str(tmp_path / "out")
        return cfg

    def _arm(self, monkeypatch, tmp_path, scene_urls):
        import engine.youtube as yt_mod
        monkeypatch.setattr(yt_mod, "get_channel_credentials_from_env",
                            lambda channel="en": object())
        cover = tmp_path / "cover.jpg"
        cover.write_bytes(b"jpg")
        monkeypatch.setattr(ru_dub, "_cover_path", lambda config: cover)
        # No real git: the "refreshed" manifest is the checked-in stub.
        manifest = tmp_path / "manifest.json"
        manifest.write_text(json.dumps({"images": [
            {"show_slug": "tesla", "episode_id": "ep005",
             "intended_use": "segment_card", "original_url": u}
            for u in scene_urls
        ]}), encoding="utf-8")
        monkeypatch.setattr(ru_dub, "_fresh_manifest_path",
                            lambda dest_dir, **kw: manifest)
        # Stop the proceed-path before any render/network work.
        monkeypatch.setattr(ru_dub, "_resolve_ru_audio",
                            lambda *a, **k: None)

    def test_fresh_episode_without_scenes_defers(self, tmp_path, monkeypatch):
        import datetime
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        cfg = self._cfg_with_summaries(tmp_path, today)
        self._arm(monkeypatch, tmp_path, scene_urls=[])
        res = ru_dub.publish_ru_dub(cfg, 5)
        assert res["status"] == "no_scenes_yet"
        assert res["scene_count"] == 0

    def test_fresh_episode_with_one_scene_defers(self, tmp_path, monkeypatch):
        import datetime
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        cfg = self._cfg_with_summaries(tmp_path, today)
        self._arm(monkeypatch, tmp_path, scene_urls=["https://r2/a.jpg"])
        res = ru_dub.publish_ru_dub(cfg, 5)
        assert res["status"] == "no_scenes_yet"
        assert res["scene_count"] == 1

    def test_old_episode_without_scenes_proceeds_with_cover(
            self, tmp_path, monkeypatch):
        cfg = self._cfg_with_summaries(tmp_path, "2026-01-01")
        self._arm(monkeypatch, tmp_path, scene_urls=[])
        res = ru_dub.publish_ru_dub(cfg, 5)
        # Past the scene gate — stopped by the armed no-audio stub instead.
        assert res["status"] == "no_ru_audio"

    def test_fresh_episode_with_scenes_proceeds(self, tmp_path, monkeypatch):
        import datetime
        today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        cfg = self._cfg_with_summaries(tmp_path, today)
        self._arm(monkeypatch, tmp_path,
                  scene_urls=["https://r2/a.jpg", "https://r2/b.jpg"])
        res = ru_dub.publish_ru_dub(cfg, 5)
        assert res["status"] == "no_ru_audio"


class TestScenesDeferralIndex:
    """publish_ru_dubs.py retry semantics: a no_scenes_yet deferral is
    recorded like the short-failure rows (status row, no video_id) and the
    episode stays NOT done so the next sweep retries it."""

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

    def test_deferral_row_matches_index_conventions(self, tmp_path):
        drv = self._driver()
        cfg = self._cfg(tmp_path)
        drv._record_scenes_deferral(cfg, 5)
        data = json.loads((tmp_path / "youtube_videos.ru.json").read_text())
        rows = [v for v in data["videos"]
                if v.get("episode") == 5 and v.get("status") == "deferred"]
        assert len(rows) == 1
        assert rows[0]["kind"] == "long"
        assert rows[0]["reason"] == "no_scenes_yet"
        assert "video_id" not in rows[0]
        assert rows[0]["recorded"]

    def test_deferred_episode_is_not_done(self, tmp_path):
        drv = self._driver()
        cfg = self._cfg(tmp_path)
        drv._record_scenes_deferral(cfg, 5)
        assert drv._already_done(cfg, 5) is False  # next sweep retries

    def test_absent_entry_is_not_done(self, tmp_path):
        drv = self._driver()
        assert drv._already_done(self._cfg(tmp_path), 5) is False

    def test_repeat_deferral_keeps_single_row(self, tmp_path):
        drv = self._driver()
        cfg = self._cfg(tmp_path)
        drv._record_scenes_deferral(cfg, 5)
        drv._record_scenes_deferral(cfg, 5)
        data = json.loads((tmp_path / "youtube_videos.ru.json").read_text())
        assert len([v for v in data["videos"]
                    if v.get("status") == "deferred"]) == 1

    def test_real_long_row_is_done_and_clear_drops_deferral(self, tmp_path):
        drv = self._driver()
        cfg = self._cfg(tmp_path)
        drv._record_scenes_deferral(cfg, 5)
        idx = tmp_path / "youtube_videos.ru.json"
        data = json.loads(idx.read_text())
        data["videos"].append({"video_id": "v1", "episode": 5, "kind": "long"})
        idx.write_text(json.dumps(data), encoding="utf-8")
        assert drv._already_done(cfg, 5) is True
        drv._clear_scenes_deferral(cfg, 5)
        data = json.loads(idx.read_text())
        assert [v for v in data["videos"]
                if v.get("status") == "deferred"] == []
        assert drv._already_done(cfg, 5) is True  # real row survives

    def test_status_only_long_row_never_counts_as_done(self, tmp_path):
        # Defensive: a long row WITHOUT video_id (nothing uploaded) must not
        # gate the retry, whatever its status says.
        drv = self._driver()
        cfg = self._cfg(tmp_path)
        idx = tmp_path / "youtube_videos.ru.json"
        idx.write_text(json.dumps({"videos": [
            {"episode": 5, "kind": "long", "status": "whatever"}]}),
            encoding="utf-8")
        assert drv._already_done(cfg, 5) is False

    def test_main_loop_wires_deferral_recording(self):
        src = (_ROOT / "scripts" / "publish_ru_dubs.py").read_text(
            encoding="utf-8")
        assert '== "no_scenes_yet"' in src
        assert "_record_scenes_deferral(config, ep)" in src
        assert "_clear_scenes_deferral(config, ep)" in src


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


class TestRuDubWorkflowEnv:
    """The Jul 14-16 2026 incident class: the optimized RU-title path
    (`_translate_title_to_ru`) shipped but the workflow step never passed
    the Grok key, so every @NerraRU upload silently fell back to the
    truncated hook title. Pin the step's env so the fix can't regress."""

    def _ru_dub_step(self):
        import yaml
        wf = yaml.safe_load(
            (_ROOT / ".github" / "workflows" / "multilingual.yml").read_text(
                encoding="utf-8"))
        for job in wf.get("jobs", {}).values():
            for step in job.get("steps", []) or []:
                if "publish_ru_dubs.py" in str(step.get("run", "")):
                    return step
        raise AssertionError("publish_ru_dubs step not found in multilingual.yml")

    def test_step_env_has_grok_key_for_title_translation(self):
        env = self._ru_dub_step().get("env", {}) or {}
        assert "GROK_API_KEY" in env, (
            "RU-dub step must pass GROK_API_KEY — without it the optimized "
            "RU title translation silently degrades to the hook title")
        assert "XAI_API_KEY" in env

    def test_step_env_has_r2_credentials_for_scene_fallback(self):
        env = self._ru_dub_step().get("env", {}) or {}
        for key in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID",
                    "R2_SECRET_ACCESS_KEY"):
            assert key in env, (
                f"RU-dub step must pass {key} — the gallery-scene download "
                "falls back to authenticated R2 when the public CDN 403s CI")


class TestSceneDownloadRobustness:
    def test_download_images_routes_through_gallery_library(self, tmp_path,
                                                            monkeypatch):
        """RU dub scene downloads must use gallery_library's downloader so
        the public-CDN → authenticated-R2 fallback (Ep537 403 class)
        protects them too."""
        from engine import gallery_library
        seen = []

        def _fake(entry, dest_dir, failures=None):
            seen.append(entry["original_url"])
            p = Path(dest_dir) / f"x{len(seen)}.jpg"
            p.write_bytes(b"img")
            return p

        monkeypatch.setattr(gallery_library, "_download_entry", _fake)
        urls = ["https://gallery.nerranetwork.com/tesla/a.jpeg",
                "https://gallery.nerranetwork.com/tesla/b.jpeg"]
        got = ru_dub._download_images(urls, tmp_path)
        assert seen == urls
        assert len(got) == 2

    def test_download_images_skips_failures(self, tmp_path, monkeypatch):
        from engine import gallery_library
        monkeypatch.setattr(gallery_library, "_download_entry",
                            lambda *a, **k: None)
        assert ru_dub._download_images(["https://x/a.jpg"], tmp_path) == []


class TestShortIndexTitleFidelity:
    def test_short_record_uses_uploaded_short_title(self):
        """The ru index must record the title the Short actually shipped
        with (`_ru_short_title(...)`, '#Shorts'-suffixed) — recording the
        long title hid what @NerraRU displayed (Jul 2026 verification)."""
        import inspect
        import re
        src = inspect.getsource(ru_dub.publish_ru_dub)
        m = re.search(
            r"short_title = _ru_short_title\(ru_title\)(.*?)"
            r"record_video\((.*?)\)", src, re.DOTALL)
        assert m, "short upload must bind short_title before recording"
        assert "title=short_title" in m.group(2)
