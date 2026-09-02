"""Drift guards for the generalized language-dub engine (July 18 2026).

engine.lang_dub is the language-parameterized sibling of engine.ru_dub
(which keeps serving @NerraRU untouched — the show-memory precedent).
First registered language: French → @NerraFR, shipping DORMANT until
YOUTUBE_REFRESH_TOKEN_FR exists.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine import lang_dub  # noqa: E402


def _cfg(dub_languages=("fr",), ml_langs=("fr",), enabled=True):
    return SimpleNamespace(
        slug="tesla",
        name="Tesla Shorts Time",
        youtube=SimpleNamespace(
            dub_languages=list(dub_languages),
            dub_playlist_ids={},
            publish_shorts=True,
            adaptive_publishing=True,
            category_id=28,
            privacy_status="public",
            short_duration_seconds=40,
            shorts_start_offset=0.0,
            auto_comment=True,
        ),
        multilingual=SimpleNamespace(enabled=enabled, languages=list(ml_langs)),
        publishing=SimpleNamespace(
            summaries_json="digests/tesla_shorts_time/summaries_tesla.json",
            base_url="https://nerranetwork.com",
        ),
        episode=SimpleNamespace(output_dir="digests/tesla_shorts_time"),
        keywords=["tesla", "ev"],
    )


class TestRegistry:
    def test_french_registered_with_full_spec(self):
        fr = lang_dub.DUB_LANGUAGES["fr"]
        assert fr.channel == "fr"
        assert fr.whisper_language == "fr"
        assert fr.default_language == "fr"
        # French copy is actually French (accented) — not English defaults.
        assert "É" in fr.end_card_main or "É" in fr.disclosure or "é" in fr.disclosure
        assert "{url}" in fr.comment_full_episode
        assert fr.ep_prefix_re.sub("", "Ép. 5: Grande nouvelle") == "Grande nouvelle"

    def test_russian_deliberately_absent(self):
        # @NerraRU runs on the proven bespoke engine.ru_dub.
        assert "ru" not in lang_dub.DUB_LANGUAGES

    def test_dub_languages_for_reads_yaml_and_filters(self):
        cfg = _cfg(dub_languages=("fr", "ru", "xx"))
        # fr accepted; ru silently skipped (ru_dub owns it); xx warned+skipped.
        assert lang_dub.dub_languages_for(cfg) == ["fr"]

    def test_empty_default_is_noop(self):
        assert lang_dub.dub_languages_for(_cfg(dub_languages=())) == []


class TestHelpers:
    def test_short_title_shape(self):
        fr = lang_dub.DUB_LANGUAGES["fr"]
        t = lang_dub._short_title(
            "Ép. 12: Starship réussit son treizième vol d'essai", fr)
        assert t.endswith(" #Shorts")
        assert not t.startswith("Ép")
        assert len(t) <= 100

    def test_translate_title_rejects_english_echo(self, monkeypatch):
        from engine import translate
        fr = lang_dub.DUB_LANGUAGES["fr"]
        monkeypatch.setattr(translate, "translate_metadata",
                            lambda t, d, lang: (t, d))  # echo = no translation
        assert lang_dub._translate_title("Tesla Fleet Grows 50%", fr) == ""

    def test_translate_title_accepts_real_translation(self, monkeypatch):
        from engine import translate
        fr = lang_dub.DUB_LANGUAGES["fr"]
        monkeypatch.setattr(
            translate, "translate_metadata",
            lambda t, d, lang: ("La flotte Tesla grandit de 50 %", ""))
        out = lang_dub._translate_title("Tesla Fleet Grows 50%", fr)
        assert out == "La flotte Tesla grandit de 50 %"

    def test_index_path_per_language(self):
        cfg = _cfg()
        assert lang_dub.index_path(cfg, "fr").name == "youtube_videos.fr.json"


class TestPublishNoOps:
    """Every early-exit path must return a status dict and never raise."""

    def test_unknown_language(self):
        res = lang_dub.publish_lang_dub(_cfg(), 1, "xx")
        assert res["status"] == "unknown_language"

    def test_not_opted_in(self):
        res = lang_dub.publish_lang_dub(_cfg(dub_languages=()), 1, "fr")
        assert res["status"] == "skip"

    def test_no_multilingual_track_language(self):
        res = lang_dub.publish_lang_dub(_cfg(ml_langs=("ru",)), 1, "fr")
        assert res["status"] == "no_fr_lang"

    def test_no_record(self, monkeypatch):
        import engine.summaries_io as sio
        monkeypatch.setattr(sio, "load_summaries",
                            lambda p: ({}, []))
        res = lang_dub.publish_lang_dub(_cfg(), 999999, "fr")
        assert res["status"] == "no_record"

    def test_no_track_yet(self, monkeypatch):
        import engine.summaries_io as sio
        monkeypatch.setattr(sio, "load_summaries", lambda p: (
            {}, [{"episode_num": 7, "translations": {}}]))
        res = lang_dub.publish_lang_dub(_cfg(), 7, "fr")
        assert res["status"] == "no_fr_track"

    def test_dry_run_resolves_french_titles(self, monkeypatch):
        import engine.summaries_io as sio
        monkeypatch.setattr(sio, "load_summaries", lambda p: (
            {}, [{"episode_num": 7,
                  "translations": {"fr": {
                      "title": "Ép. 7: Starship réussit son vol",
                      "description": "desc"}}}]))
        monkeypatch.setattr(lang_dub, "_en_optimized_long_title",
                            lambda c, e: "")
        monkeypatch.setattr(lang_dub, "_policy_plan", lambda c, l: {
            "publish_long": True, "shorts": 1, "tier": "C",
            "applied": True, "reason": ""})
        res = lang_dub.publish_lang_dub(_cfg(), 7, "fr", dry_run=True)
        assert res["status"] == "dryrun"
        assert res["title"].startswith("Ép. 7")
        assert res["short_title"].endswith(" #Shorts")

    def test_no_credentials_is_dormant_noop(self, monkeypatch):
        import engine.summaries_io as sio
        import engine.youtube as eyt
        monkeypatch.setattr(sio, "load_summaries", lambda p: (
            {}, [{"episode_num": 7,
                  "translations": {"fr": {"title": "Titre", "description": "d"}}}]))
        monkeypatch.setattr(lang_dub, "_en_optimized_long_title",
                            lambda c, e: "")
        monkeypatch.setattr(lang_dub, "_policy_plan", lambda c, l: {
            "publish_long": True, "shorts": 1, "tier": "",
            "applied": False, "reason": ""})
        monkeypatch.setattr(eyt, "get_channel_credentials_from_env",
                            lambda ch: None)
        res = lang_dub.publish_lang_dub(_cfg(), 7, "fr")
        assert res["status"] == "no_fr_credentials"


class TestCredentialsGeneralization:
    def test_fr_reads_fr_token(self, monkeypatch):
        from engine.youtube import get_channel_credentials_from_env
        monkeypatch.setenv("YOUTUBE_CLIENT_ID", "id")
        monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "sec")
        monkeypatch.delenv("YOUTUBE_REFRESH_TOKEN_FR", raising=False)
        assert get_channel_credentials_from_env("fr") is None
        monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN_FR", "tok")
        assert get_channel_credentials_from_env("fr") is not None

    def test_en_and_ru_unchanged(self, monkeypatch):
        from engine.youtube import get_channel_credentials_from_env
        monkeypatch.setenv("YOUTUBE_CLIENT_ID", "id")
        monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "sec")
        monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN_EN", "tok-en")
        monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN_RU", "tok-ru")
        assert get_channel_credentials_from_env("en") is not None
        assert get_channel_credentials_from_env("ru") is not None
        # Default channel is EN.
        assert get_channel_credentials_from_env() is not None


class TestPolicyChannel:
    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "uyp", _ROOT / "scripts/update_youtube_policy.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_fr_seeded_shorts_only(self):
        m = self._mod()
        assert m.SEED_TIERS["fr"] == {
            "tesla": "C",
            "spacex": "C",
            "fascinating_frontiers": "C",
            "modern_investing": "C",
        }

    def test_fr_long_floor_matches_ru(self):
        m = self._mod()
        assert m.LONG_VPD_FLOOR["fr"] == m.LONG_VPD_FLOOR["ru"] == 2.0


class TestShowYamls:
    # modern_investing culled 2026-09-02 (operator): 533 views from 71 dub
    # videos in 28 days.
    _SHOWS = ["tesla", "spacex", "fascinating_frontiers"]

    def test_four_shows_opt_into_fr(self):
        for slug in self._SHOWS:
            cfg = yaml.safe_load(
                (_ROOT / f"shows/{slug}.yaml").read_text(encoding="utf-8"))
            assert cfg["youtube"]["dub_languages"] == ["fr"], slug

    def test_fr_audio_track_exists_for_every_dub_show(self):
        # The dub's input is the multilingual fr track — a show opted into
        # the FR dub without fr in its languages would no-op forever
        # (the modern_investing gap this pass closed).
        for slug in self._SHOWS:
            cfg = yaml.safe_load(
                (_ROOT / f"shows/{slug}.yaml").read_text(encoding="utf-8"))
            assert "fr" in cfg["multilingual"]["languages"], slug

    def test_ru_flags_untouched(self):
        for slug in self._SHOWS:
            cfg = yaml.safe_load(
                (_ROOT / f"shows/{slug}.yaml").read_text(encoding="utf-8"))
            assert cfg["youtube"]["ru_dub_enabled"] is True, slug


class TestWorkflowWiring:
    def test_multilingual_workflow_has_fr_step(self):
        src = (_ROOT / ".github/workflows/multilingual.yml"
               ).read_text(encoding="utf-8")
        assert "publish_lang_dubs.py" in src
        assert "--lang fr" in src
        step = src.split("French dubs", 1)[1].split("- name:")[0]
        # The FR step env must carry the FR token + Grok key (the RU-title
        # missing-GROK_API_KEY class from Jul 14-16) + R2 fallback creds.
        for needle in ("YOUTUBE_REFRESH_TOKEN_FR", "GROK_API_KEY",
                       "R2_ACCESS_KEY_ID"):
            assert needle in step, needle

    def test_ru_step_untouched(self):
        src = (_ROOT / ".github/workflows/multilingual.yml"
               ).read_text(encoding="utf-8")
        assert "publish_ru_dubs.py" in src
        assert "YOUTUBE_REFRESH_TOKEN_RU" in src


class TestSweepScript:
    def _mod(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "pld", _ROOT / "scripts/publish_lang_dubs.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_already_done_semantics(self, tmp_path, monkeypatch):
        m = self._mod()
        cfg = _cfg()
        monkeypatch.setattr(m.lang_dub, "index_path",
                            lambda c, l: tmp_path / "youtube_videos.fr.json")
        # Empty → not done.
        assert m._already_done(cfg, "fr", 7) is False
        # Status-only rows (deferral/failure) → still not done.
        (tmp_path / "youtube_videos.fr.json").write_text(json.dumps({
            "videos": [
                {"episode": 7, "kind": "long", "status": "deferred"},
                {"episode": 7, "kind": "short", "status": "failed"},
            ]}))
        assert m._already_done(cfg, "fr", 7) is False
        # A row with a video_id → done.
        (tmp_path / "youtube_videos.fr.json").write_text(json.dumps({
            "videos": [{"episode": 7, "kind": "short", "video_id": "abc"}]}))
        assert m._already_done(cfg, "fr", 7) is True

    def test_status_rows_roundtrip(self, tmp_path, monkeypatch):
        m = self._mod()
        cfg = _cfg()
        monkeypatch.setattr(m.lang_dub, "index_path",
                            lambda c, l: tmp_path / "youtube_videos.fr.json")
        m._record_status_row(cfg, "fr", 7, kind="long", status="deferred",
                             reason="no_scenes_yet")
        m._record_status_row(cfg, "fr", 7, kind="long", status="deferred",
                             reason="no_scenes_yet")  # replaces, not dupes
        data = json.loads(
            (tmp_path / "youtube_videos.fr.json").read_text())
        assert len(data["videos"]) == 1
        m._clear_status_row(cfg, "fr", 7, kind="long", status="deferred")
        data = json.loads(
            (tmp_path / "youtube_videos.fr.json").read_text())
        assert data["videos"] == []


class TestRuEngineUntouched:
    """The operator's no-breakage requirement: RU keeps its bespoke engine."""

    def test_ru_dub_public_api_intact(self):
        from engine import ru_dub
        assert callable(ru_dub.publish_ru_dub)
        src = (_ROOT / "engine/ru_dub.py").read_text(encoding="utf-8")
        # RU-specific strings still present (not refactored away).
        assert "СМОТРЕТЬ ВЫПУСК" in src
        assert "youtube_videos.ru.json" in src

    def test_lang_dub_imports_shared_helpers_from_ru_dub(self):
        # One implementation of the language-neutral machinery — lang_dub
        # must import it, not fork it.
        src = (_ROOT / "engine/lang_dub.py").read_text(encoding="utf-8")
        assert "from engine.ru_dub import" in src
        for helper in ("gallery_images_for_episode", "_fresh_manifest_path",
                       "_en_optimized_long_title", "_cover_path"):
            assert helper in src


class TestAnalyticsCredentialsCoverEveryDubChannel:
    """Every channel the network UPLOADS to must also be readable back.

    July 30 2026: @NerraFR published 42 videos from 2026-07-21 while every
    FR show reported ``short_vpd: null`` and stayed frozen at its seed
    tier. Two separate causes, fixed a day apart:

      1. ``fetch_youtube_analytics`` globbed only ``youtube_videos.ru.json``
         beside the base index, so it never SAW the FR rows.
      2. ``nightly-maintenance.yml`` passed only the EN and RU refresh
         tokens, so even once it saw them it could not AUTHENTICATE to the
         channel — ``get_channel_credentials_from_env("fr")`` returned
         None and the loop skipped it. The 2026-07-30 nightly ran cleanly
         and still emitted zero fr rows.

    The upload path always had the FR token; only the read-back lacked it.
    A channel that can be written to and not read from is invisible to the
    adaptive policy, which is a channel that can never earn a promotion.
    """

    _NIGHTLY = ".github/workflows/nightly-maintenance.yml"

    def _nightly_env(self):
        import yaml as _yaml
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        raw = _yaml.safe_load((root / self._NIGHTLY).read_text(encoding="utf-8"))
        env = {}
        for job in (raw.get("jobs") or {}).values():
            for step in (job.get("steps") or []):
                env.update(step.get("env") or {})
        return env

    def test_every_registered_dub_language_is_readable(self):
        from engine.lang_dub import DUB_LANGUAGES
        env = self._nightly_env()
        for code, lang in DUB_LANGUAGES.items():
            var = f"YOUTUBE_REFRESH_TOKEN_{lang.channel.upper()}"
            assert var in env, (
                f"{lang.channel_handle} uploads but the nightly analytics "
                f"fetch has no {var} — the channel is invisible to the "
                "adaptive policy and can never earn a promotion"
            )

    def test_base_channels_still_present(self):
        env = self._nightly_env()
        for var in ("YOUTUBE_REFRESH_TOKEN_EN", "YOUTUBE_REFRESH_TOKEN_RU"):
            assert var in env, var


class TestBrandNameRestore:
    """Aug 15 2026 — deterministic repair of translation brand garbles
    that SHIPPED in dub Short titles on @NerraRU/@NerraFR (the network's
    highest-reach surface): "Grog 4.6", «Спейс-Экс», "Cloud Fable 5",
    "Global Star". Applied inside translate_metadata so every dub title
    and description passes through it."""

    def test_known_garbles_restored(self):
        from engine.translate import restore_brand_names
        assert restore_brand_names("présentent Grog 4.6") == "présentent Grok 4.6"
        assert "SpaceX" in restore_brand_names("что Спейс-Экс попытается")
        assert "Claude Fable 5" in restore_brand_names("о Cloud Fable 5")
        assert "Globalstar" in restore_brand_names("La mission Global Star avec 9")

    def test_clean_text_untouched(self):
        from engine.translate import restore_brand_names
        for s in ("Илон Маск и Tesla", "Grok 5 est là", "SpaceX запускает"):
            assert restore_brand_names(s) == s

    def test_wired_into_translate_metadata(self):
        import inspect
        from engine import translate
        src = inspect.getsource(translate.translate_metadata)
        assert "restore_brand_names" in src
