"""Drift guards for the June 16 2026 Финансы Просто quality pass
(docs/reviews/finansy_prosto_review_2026_06_16.md).

This is the first dedicated FP review (the June 10 pass covered FP + PR
together). It scores the June-10 floor-raise prediction (MISS — episodes
still ship ~700 words / ~5 min vs the claimed 8-10 min) and ships the next
tier of fixes:

P0 (audio):
* the YouTube call-out no longer voices "@" as the word "at"
  ("...find us on YouTube at at Nerra Network" shipped 49+ times across six
  shows) — the spoken handle is now stripped of the sigil;
* Финансы Просто (a Russian-SPOKEN show) gets a Russian YouTube call-out
  instead of an English sentence on the Olya voice (same wart class as the
  AI disclosure localized in June 2026);
* the FP closings no longer say "до завтра" — the show airs every other day
  (even days), so the sign-off is cadence-neutral (EI-class fix).

P1:
* _extract_hook recognizes the Russian "ЗАГОЛОВОК:" label the FP/PR digest
  prompts use, so the structural-integrity gate stops firing a wasted
  regeneration on every Russian episode;
* the structural-retry corrective suffix is GENERIC, not hardcoded to
  Tesla's section names (FP was being told to produce "Top 12 News Items,
  Tesla X Takeover…");
* the FP digest prompt asks for 3-4 practical tips and 5-7 articles, to
  match the podcast prompt that already requires a minimum of 3 tips.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.intros import (  # noqa: E402
    _RUSSIAN_SPOKEN_SHOWS,
    _maybe_append_youtube_cta,
    build_closing_block,
    _SHOW_PERSONALITIES,
)
from run_show import _extract_hook  # noqa: E402

_FP_DIGEST = (_ROOT / "shows/prompts/fp_digest.txt").read_text(encoding="utf-8")
_RUN_SHOW = (_ROOT / "run_show.py").read_text(encoding="utf-8")


class TestYouTubeCtaStutter:
    """The "@" sigil is voiced by the TTS as the word "at"."""

    # EN handle is split to the spaced brand "Nerra Network" so the TTS says
    # it the same way as the promo brand + the .com URL; the RU "NerraRU" stays
    # one token (a CamelCase split would voice it "Nerra R U" on the Olya voice).
    @pytest.mark.parametrize(
        "handle,expected_spoken",
        [("@NerraNetwork", "nerra network"), ("@NerraRU", "nerraru")],
    )
    def test_at_at_stutter_is_gone(self, handle, expected_spoken):
        out = _maybe_append_youtube_cta("Patrick: Bye.", handle).lower()
        assert "at at" not in out
        assert "@" not in out
        # The channel name (sans sigil) still spoken, in its normalized form.
        assert expected_spoken in out

    def test_idempotent_when_already_mentions_youtube(self):
        closing = "Patrick: That's it. Watch us on YouTube tomorrow."
        assert _maybe_append_youtube_cta(closing, "@NerraNetwork") == closing


class TestRussianCtaLocalized:
    def test_finansy_prosto_in_russian_spoken_set(self):
        assert "finansy_prosto" in _RUSSIAN_SPOKEN_SHOWS
        # Привет, Русский! is taught IN English — it keeps the English CTA.
        assert "privet_russian" not in _RUSSIAN_SPOKEN_SHOWS

    def test_fp_cta_is_russian(self):
        out = _maybe_append_youtube_cta("Ведущая: Пока.", "@NerraRU", is_ru=True)
        assert "Ссылка" in out  # Russian call-out present
        assert "show notes" not in out  # English replaced
        assert "NerraRU" in out and "@" not in out

    def test_build_closing_block_routes_fp_to_russian(self):
        closing = build_closing_block(
            "finansy_prosto", episode_num=5, today_str="x",
            youtube_channel_handle="@NerraRU",
        )
        assert "Ссылка" in closing
        assert "rather watch than listen" not in closing


class TestCadenceNeutralClosing:
    def test_fp_closings_have_no_tomorrow(self):
        for variant in _SHOW_PERSONALITIES["finansy_prosto"]["closings"]:
            assert "завтра" not in variant.lower(), (
                f"FP airs even days — 'до завтра' is a cadence bug: {variant[:60]!r}"
            )
            assert "до встречи" in variant.lower()

    def test_fp_closings_still_match_zavershenie_pattern(self):
        import yaml
        cfg = yaml.safe_load(
            (_ROOT / "shows/finansy_prosto.yaml").read_text(encoding="utf-8")
        )
        pat = next(m for m in cfg["chapters"]["section_markers"]
                   if m["title"] == "Завершение")["pattern"]
        rx = re.compile(pat, re.IGNORECASE)
        for variant in _SHOW_PERSONALITIES["finansy_prosto"]["closings"]:
            assert rx.search(variant)


class TestExtractHookRecognizesRussianLabel:
    def test_zagolovok_label(self):
        digest = (
            "# Финансы Просто\n**Дата:** June 16\n\n"
            "**ЗАГОЛОВОК:** Рынок жилья показывает признаки оживления\n\n"
            "**Что сегодня важного:** ...\n### Главная тема\n"
        )
        assert _extract_hook(digest) == "Рынок жилья показывает признаки оживления"

    def test_english_hook_still_works(self):
        assert _extract_hook("**HOOK:** Something happened") == "Something happened"

    def test_blockquote_fallback_still_works(self):
        digest = "# Show\n> **A leading blockquote hook line here**\n### Section"
        assert _extract_hook(digest) == "A leading blockquote hook line here"


class TestStructuralSuffixGeneric:
    def test_no_hardcoded_tesla_sections_in_suffix(self):
        # The corrective suffix used to name Tesla's sections, which were
        # applied to every show that hit the structural gate (FP regenerated
        # against "Top 12 News Items, Tesla X Takeover…" every episode).
        m = re.search(
            r"_struct_suffix = \((.*?)\n\s*\)", _RUN_SHOW, re.DOTALL
        )
        assert m, "could not locate _struct_suffix block"
        suffix = m.group(1)
        for tesla_section in (
            "Top 12 News Items", "Tesla X Takeover", "Short Spot",
            "Tesla First Principles",
        ):
            assert tesla_section not in suffix, (
                f"structural-retry suffix still hardcodes Tesla section "
                f"{tesla_section!r}"
            )


class TestDigestDepthMatchesPodcast:
    def test_digest_requires_at_least_three_tips(self):
        # The podcast prompt requires a minimum of 3 tips; the digest must
        # supply them (the podcast may not invent content).
        assert "3-4 полезных совета" in _FP_DIGEST
        assert "2-3 полезных совета" not in _FP_DIGEST

    def test_digest_article_count_raised(self):
        assert "Выбери 5-7 статей" in _FP_DIGEST
        assert "Выбери 4-6 статей" not in _FP_DIGEST
