"""Drift guards for the multilingual audio pipeline (June 2026).

Covers the additive, non-breaking pieces so a regression is caught without
spending Grok credits or hitting the network:
  * MultilingualConfig round-trips through load_config (no silent key drop).
  * Per-language phonetic overrides load + apply (word-boundary).
  * R2 key derivation suffixes the language correctly.
  * summaries_io round-trips both shapes and persists edits.
  * The blog post renders the switcher only when translations exist — and
    never for an English-only episode.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESLA_DIGESTS = PROJECT_ROOT / "digests" / "tesla_shorts_time"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestMultilingualConfig:
    def test_english_show_inherits_enabled_default(self):
        from engine.config import load_config
        cfg = load_config("shows/tesla.yaml")
        assert cfg.multilingual.enabled is True
        assert cfg.multilingual.languages == ["fr", "ru", "es", "zh"]
        assert cfg.multilingual.cloned_voice_env == "GROK_CLONED_VOICE_ID"

    def test_russian_shows_opt_out(self):
        from engine.config import load_config
        for slug in ("finansy_prosto", "privet_russian"):
            cfg = load_config(f"shows/{slug}.yaml")
            assert cfg.multilingual.enabled is False, slug

    def test_auto_enabled_for_english_shows(self):
        from engine.config import load_config
        assert load_config("shows/tesla.yaml").multilingual.auto is True

    def test_russian_shows_have_auto_off_via_disabled(self):
        # Russian shows opt out of multilingual entirely, so auto never runs.
        from engine.config import load_config
        cfg = load_config("shows/finansy_prosto.yaml")
        assert cfg.multilingual.enabled is False

    def test_no_silent_key_drop(self):
        # Every field set in YAML must be DECLARED on the dataclass
        # (landmine #20) — loading without a warning-only fallback means
        # the round-trip is faithful.
        from engine.config import MultilingualConfig
        fields = set(MultilingualConfig.__dataclass_fields__)
        assert {"enabled", "languages", "cloned_voice_env"} <= fields


# ---------------------------------------------------------------------------
# Phonetic overrides
# ---------------------------------------------------------------------------

class TestOverrides:
    def test_overrides_yaml_loads(self):
        from engine.translate import overrides_for_language
        ru = overrides_for_language("ru")
        assert "TSLA" in ru and ru["TSLA"]

    def test_language_scoping(self):
        from engine.translate import overrides_for_language
        # A term present only for some languages must not leak to others.
        ru = overrides_for_language("ru")
        es = overrides_for_language("es")
        assert ru.get("Tesla")  # has a Cyrillic spelling
        assert "Tesla" not in es  # no es override for the plain brand name

    def test_apply_overrides_word_boundary(self):
        from engine.translate import apply_overrides
        out = apply_overrides("Acheter des actions TSLA aujourd'hui.", "fr")
        assert "T-S-L-A" in out
        # Must not rewrite a substring inside another token.
        assert apply_overrides("TSLAX fund", "fr") == "TSLAX fund"

    def test_unsupported_language_rejected(self):
        from engine.translate import translate_script
        with pytest.raises(ValueError):
            translate_script("hello", "de")


class TestTranslationValidation:
    def test_empty_rejected(self):
        from engine.translate import TranslationError, validate_translation
        with pytest.raises(TranslationError):
            validate_translation("   ", "fr", "Some English source text.")

    def test_refusal_rejected(self):
        from engine.translate import TranslationRefusalError, validate_translation
        with pytest.raises(TranslationRefusalError):
            validate_translation(
                "I'm sorry, but I cannot generate this podcast episode.", "fr", "x" * 200
            )

    def test_untranslated_echo_rejected(self):
        from engine.translate import TranslationError, validate_translation
        src = "Tesla expanded its robotaxi program across Texas today."
        with pytest.raises(TranslationError):
            validate_translation(src, "fr", src)

    def test_too_short_rejected(self):
        from engine.translate import TranslationError, validate_translation
        with pytest.raises(TranslationError):
            validate_translation("Bonjour.", "fr", "x" * 500)

    def test_wrong_script_rejected_for_ru(self):
        from engine.translate import TranslationError, validate_translation
        # Latin text claiming to be Russian → wrong script.
        latin = "This is clearly English text, not Russian at all, repeated. " * 5
        with pytest.raises(TranslationError):
            validate_translation(latin, "ru", latin.replace("Russian", "x"))

    def test_wrong_script_rejected_for_zh(self):
        from engine.translate import TranslationError, validate_translation
        latin = "This is English not Chinese characters here. " * 5
        with pytest.raises(TranslationError):
            validate_translation(latin, "zh", "y" * 400)

    def test_valid_russian_passes(self):
        from engine.translate import validate_translation
        ru = ("Сегодня Тесла расширила программу роботакси по всему Техасу, "
              "и это важная новость для инвесторов и водителей.")
        assert validate_translation(ru, "ru", "x" * 80) == ru

    def test_valid_chinese_passes(self):
        from engine.translate import validate_translation
        zh = "今天特斯拉在德克萨斯州扩展了它的无人驾驶出租车项目，这对投资者来说是重要消息。"
        assert validate_translation(zh, "zh", "x" * 40) == zh

    def test_valid_french_passes(self):
        from engine.translate import validate_translation
        fr = ("Aujourd'hui, Tesla a étendu son programme de robotaxi à travers "
              "le Texas, une nouvelle importante pour les investisseurs.")
        en = "Today Tesla expanded its robotaxi program across Texas."
        assert validate_translation(fr, "fr", en) == fr


# ---------------------------------------------------------------------------
# R2 key / URL derivation
# ---------------------------------------------------------------------------

class TestTrackKeyDerivation:
    def _fn(self):
        from engine.multilingual import derive_track_key_url
        return derive_track_key_url

    def test_suffix_before_extension(self):
        fn = self._fn()
        base = "https://audio.nerranetwork.com"
        url = f"{base}/tesla_shorts_time/Tesla_Shorts_Time_Pod_Ep511_20260615.mp3"
        key, public = fn(url, "fr", base)
        assert key == "tesla_shorts_time/Tesla_Shorts_Time_Pod_Ep511_20260615.fr.mp3"
        assert public == f"{base}/{key}"

    def test_falls_back_to_path_when_base_mismatch(self):
        fn = self._fn()
        url = "https://cdn.example.com/x/Ep1_2026.mp3"
        key, public = fn(url, "zh", "https://audio.nerranetwork.com")
        assert key == "x/Ep1_2026.zh.mp3"


# ---------------------------------------------------------------------------
# summaries_io
# ---------------------------------------------------------------------------

class TestSummariesIO:
    def test_wrapped_roundtrip_persists_edit(self, tmp_path: Path):
        from engine.summaries_io import load_summaries, save_summaries
        p = tmp_path / "s.json"
        p.write_text(json.dumps({
            "podcast": "tesla",
            "summaries": [{"episode_num": 1, "audio_url": "u"}],
        }), encoding="utf-8")
        wrapper, records = load_summaries(p)
        records[0].setdefault("translations", {})["fr"] = {"audio_url": "u.fr.mp3"}
        save_summaries(p, wrapper, records)
        again = json.loads(p.read_text(encoding="utf-8"))
        assert again["podcast"] == "tesla"  # sibling key preserved
        assert again["summaries"][0]["translations"]["fr"]["audio_url"] == "u.fr.mp3"

    def test_upsert_translation_targets_one_record(self, tmp_path: Path):
        from engine.summaries_io import upsert_translation
        p = tmp_path / "s.json"
        p.write_text(json.dumps({
            "podcast": "tesla",
            "summaries": [
                {"episode_num": 10, "audio_url": "a"},
                {"episode_num": 11, "audio_url": "b"},
            ],
        }), encoding="utf-8")
        ok = upsert_translation(p, 11, "fr", {"audio_url": "b.fr.mp3"})
        assert ok is True
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["summaries"][1]["translations"]["fr"]["audio_url"] == "b.fr.mp3"
        assert "translations" not in data["summaries"][0]  # only ep11 touched

    def test_upsert_translation_missing_episode_returns_false(self, tmp_path: Path):
        from engine.summaries_io import upsert_translation
        p = tmp_path / "s.json"
        p.write_text(json.dumps({"podcast": "t", "summaries": [{"episode_num": 1}]}),
                     encoding="utf-8")
        assert upsert_translation(p, 999, "fr", {"audio_url": "x"}) is False

    def test_upsert_preserves_concurrently_added_record(self, tmp_path: Path):
        # Simulates the live English cron appending a NEW episode between a
        # translation run's initial load and its per-track write. Because
        # upsert re-reads fresh, the new record must survive.
        from engine.summaries_io import load_summaries, upsert_translation
        p = tmp_path / "s.json"
        p.write_text(json.dumps({"podcast": "t", "summaries": [{"episode_num": 5}]}),
                     encoding="utf-8")
        _wrapper, _stale = load_summaries(p)  # translation run's initial snapshot
        # Concurrent writer appends episode 6.
        cur = json.loads(p.read_text(encoding="utf-8"))
        cur["summaries"].append({"episode_num": 6, "audio_url": "new"})
        p.write_text(json.dumps(cur), encoding="utf-8")
        # Translation run now writes its track for episode 5.
        assert upsert_translation(p, 5, "ru", {"audio_url": "5.ru.mp3"}) is True
        data = json.loads(p.read_text(encoding="utf-8"))
        nums = {r["episode_num"] for r in data["summaries"]}
        assert nums == {5, 6}  # episode 6 NOT clobbered
        ep5 = next(r for r in data["summaries"] if r["episode_num"] == 5)
        assert ep5["translations"]["ru"]["audio_url"] == "5.ru.mp3"

    def test_bare_list_roundtrip(self, tmp_path: Path):
        from engine.summaries_io import load_summaries, save_summaries
        p = tmp_path / "s.json"
        p.write_text(json.dumps([{"episode_num": 2}]), encoding="utf-8")
        wrapper, records = load_summaries(p)
        assert wrapper is None
        save_summaries(p, wrapper, records)
        assert json.loads(p.read_text(encoding="utf-8")) == [{"episode_num": 2}]


# ---------------------------------------------------------------------------
# Cloned voice env helper
# ---------------------------------------------------------------------------

class TestClonedVoice:
    def test_missing_env_fails_loud(self, monkeypatch):
        from engine.tts import get_cloned_voice_id
        monkeypatch.delenv("GROK_CLONED_VOICE_ID", raising=False)
        with pytest.raises(RuntimeError):
            get_cloned_voice_id("GROK_CLONED_VOICE_ID")

    def test_reads_env(self, monkeypatch):
        from engine.tts import get_cloned_voice_id
        monkeypatch.setenv("GROK_CLONED_VOICE_ID", "abc123")
        assert get_cloned_voice_id("GROK_CLONED_VOICE_ID") == "abc123"


# ---------------------------------------------------------------------------
# Blog template — switcher gating
# ---------------------------------------------------------------------------

_MD = "## Top Story\n\nTesla expanded its robotaxi program today. " * 5


def _ep_with_tts():
    for tts in sorted(TESLA_DIGESTS.glob("*_tts.txt")):
        m = re.search(r"_Ep(\d+)_", tts.stem)
        if m:
            return int(m.group(1))
    return None


def _metadata(ep_num, translations=None):
    meta = {
        "episode_num": ep_num,
        "date": "2026-06-15",
        "date_iso": "2026-06-15",
        "hook": "A uniquely worded hook about Tesla robotaxis.",
        "source_urls": [],
        "word_count": 500,
        "reading_time_min": 3,
        "audio_url": "https://audio.nerranetwork.com/tesla_shorts_time/Ep_x.mp3",
        "_md_path": str(TESLA_DIGESTS / "probe.md"),
    }
    if translations is not None:
        meta["translations"] = translations
    return meta


def _render(translations):
    from engine.blog import generate_blog_post_html
    from generate_html import NETWORK_SHOWS, _get_jinja_env
    ep = _ep_with_tts()
    assert ep is not None, "expected at least one Tesla _tts.txt"
    return generate_blog_post_html(
        _MD, _metadata(ep, translations), NETWORK_SHOWS["tesla"], _get_jinja_env()
    )


class TestSwitcherGating:
    def test_no_switcher_for_english_only(self):
        html = _render(None)
        # The switcher SECTION + JSON island must not render. (The swap JS
        # lives in the scripts block unconditionally and early-returns when
        # the island is absent — so we check the rendered markup, not the
        # JS source which always mentions the element id.)
        assert 'class="nn-i18n"' not in html
        assert 'id="nn-i18n-tracks"' not in html

    def test_switcher_present_with_translations(self):
        tr = {
            "fr": {"audio_url": "https://audio.nerranetwork.com/tesla_shorts_time/Ep_x.fr.mp3",
                   "title": "Titre FR", "description": "Desc FR"},
        }
        html = _render(tr)
        assert "nn-i18n-tracks" in html
        assert 'data-lang="fr"' in html
        # The JSON island must be valid JSON with both languages.
        m = re.search(r'<script type="application/json" id="nn-i18n-tracks">\s*(\{.*?\})\s*</script>',
                      html, re.DOTALL)
        assert m, "tracks JSON island not found"
        data = json.loads(m.group(1))
        assert set(data.keys()) == {"en", "fr"}
        assert data["fr"]["url"].endswith(".fr.mp3")


class TestJsonLdMultilingual:
    def _podcast_episode(self, html):
        for raw in re.findall(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, re.DOTALL
        ):
            try:
                data = json.loads(raw)
            except Exception:
                continue
            for item in (data if isinstance(data, list) else [data]):
                if item.get("@type") == "PodcastEpisode":
                    return item
        return None

    def test_english_only_has_single_media_no_availablelanguage(self):
        ep = self._podcast_episode(_render(None))
        assert ep is not None
        assert "availableLanguage" not in ep
        # Single track stays a lone object, not a list (back-compat).
        assert isinstance(ep.get("associatedMedia"), dict)

    def test_translations_listed_in_jsonld(self):
        tr = {
            "fr": {"audio_url": "https://audio.nerranetwork.com/x/Ep.fr.mp3"},
            "ru": {"audio_url": "https://audio.nerranetwork.com/x/Ep.ru.mp3"},
        }
        ep = self._podcast_episode(_render(tr))
        assert set(ep["availableLanguage"]) == {"en", "fr", "ru"}
        urls = {m["contentUrl"] for m in ep["associatedMedia"]}
        assert any(u.endswith(".fr.mp3") for u in urls)
        assert any(u.endswith(".ru.mp3") for u in urls)
        langs = {m["inLanguage"] for m in ep["associatedMedia"]}
        assert langs == {"en", "fr", "ru"}


class TestAutoGeneration:
    def _fake_config(self, tmp_path, *, enabled=True, auto=True, voice_id="kdif6sqjcyiq"):
        from types import SimpleNamespace
        return SimpleNamespace(
            slug="tshow",
            episode=SimpleNamespace(output_dir=str(tmp_path)),
            publishing=SimpleNamespace(summaries_json=str(tmp_path / "s.json")),
            tts=SimpleNamespace(max_chars=10000, voice_id=voice_id),
            storage=SimpleNamespace(
                public_base_url="https://audio.nerranetwork.com",
                endpoint_env="R2_ENDPOINT_URL", access_key_env="R2_ACCESS_KEY_ID",
                secret_key_env="R2_SECRET_ACCESS_KEY", bucket="b"),
            multilingual=SimpleNamespace(
                enabled=enabled, auto=auto, languages=["fr", "ru"],
                cloned_voice_env="GROK_CLONED_VOICE_ID"),
        )

    def _lay_episode(self, tmp_path):
        (tmp_path / "X_Ep005_20260101_tts.txt").write_text("English script.", encoding="utf-8")
        (tmp_path / "s.json").write_text(json.dumps({"podcast": "t", "summaries": [
            {"episode_num": 5,
             "audio_url": "https://audio.nerranetwork.com/tshow/X_Ep005_20260101.mp3",
             "episode_title": "Title"}]}), encoding="utf-8")

    def test_generate_for_episode_records_tracks(self, tmp_path, monkeypatch):
        from engine import multilingual, translate
        self._lay_episode(tmp_path)
        cfg = self._fake_config(tmp_path)
        # Mock out the network/heavy calls.
        monkeypatch.setattr(translate, "translate_script", lambda s, lang, **k: f"[{lang}]script")
        monkeypatch.setattr(translate, "translate_metadata", lambda t, d, lang, **k: (f"T{lang}", f"D{lang}"))
        monkeypatch.setattr(multilingual, "render_track",
                            lambda *a, **k: Path(a[4]).write_bytes(b"x"))
        monkeypatch.setattr(multilingual, "ffprobe_duration", lambda *a, **k: 120.0)
        # No R2 creds → upload skipped, but record still written with derived URL.
        monkeypatch.setattr(multilingual, "PROJECT_ROOT", Path("/"))
        for v in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            monkeypatch.delenv(v, raising=False)

        res = multilingual.generate_for_episode(
            cfg, 5, ["fr", "ru"], voice_id="vid", api_key="k")
        assert res == {"fr": "done", "ru": "done"}
        data = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
        tr = data["summaries"][0]["translations"]
        assert tr["fr"]["audio_url"].endswith("X_Ep005_20260101.fr.mp3")
        assert tr["ru"]["title"] == "Tru"

    def test_auto_skips_when_disabled(self, tmp_path):
        from engine import multilingual
        cfg = self._fake_config(tmp_path, enabled=False)
        assert multilingual.auto_generate_after_publish(cfg, 5) == {}

    def test_resolve_voice_defaults_to_show_voice(self, tmp_path, monkeypatch):
        from engine import multilingual
        monkeypatch.delenv("GROK_CLONED_VOICE_ID", raising=False)
        cfg = self._fake_config(tmp_path, voice_id="kdif6sqjcyiq")
        # No env override → reuse the show's existing Grok voice.
        assert multilingual.resolve_multilingual_voice(cfg) == "kdif6sqjcyiq"

    def test_resolve_voice_env_override_wins(self, tmp_path, monkeypatch):
        from engine import multilingual
        monkeypatch.setenv("GROK_CLONED_VOICE_ID", "other-voice")
        cfg = self._fake_config(tmp_path, voice_id="kdif6sqjcyiq")
        assert multilingual.resolve_multilingual_voice(cfg) == "other-voice"

    def test_auto_skips_when_no_voice_anywhere(self, tmp_path, monkeypatch):
        from engine import multilingual
        monkeypatch.delenv("GROK_CLONED_VOICE_ID", raising=False)
        cfg = self._fake_config(tmp_path, enabled=True, auto=True, voice_id="")
        # Neither a show voice nor an override → non-blocking skip.
        assert multilingual.auto_generate_after_publish(cfg, 5) == {}


class TestBlogIndexBadges:
    def _render_index(self, posts):
        from engine.blog import generate_blog_index_html
        from generate_html import NETWORK_SHOWS, _get_jinja_env
        return generate_blog_index_html(posts, NETWORK_SHOWS["tesla"], _get_jinja_env())

    def _post(self, ep, translations=None):
        p = {"episode_num": ep, "date": "2026-06-15", "title": "A title",
             "hook": "A hook.", "reading_time_min": 3, "filename": f"ep{ep}.md"}
        if translations:
            p["translations"] = translations
        return p

    def test_badges_shown_when_translations(self):
        html = self._render_index([self._post(5, {"fr": {"audio_url": "a.fr.mp3"},
                                                   "zh": {"audio_url": "a.zh.mp3"}})])
        # The rendered badge ROW (not just the CSS rule) must be present.
        assert '<span class="blog-idx-langs"' in html
        assert ">FR<" in html and "中文" in html

    def test_no_badges_for_english_only(self):
        # CSS defining `.blog-idx-langs`/`.lang-badge` always ships; assert the
        # rendered badge markup is absent for an English-only post.
        html = self._render_index([self._post(6)])
        assert '<span class="blog-idx-langs"' not in html
