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
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "generate_translations", PROJECT_ROOT / "scripts" / "generate_translations.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._derive_track_key_url

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
