"""Tests for engine.russian_text — date Russification for FP / Привет.

Operator caught (Финансы Просто Ep32, May 6 2026) the LLM emitting
``May sixth, twenty twenty-six`` and ``May 6, 2026`` inside Russian
sentences. Grok TTS reads English literally with the Russian voice,
which sounds awful.
"""

from __future__ import annotations

import pytest

from engine.russian_text import russify_english_dates


class TestNumericDates:

    def test_full_date(self):
        out = russify_english_dates("Сегодня May 6, 2026, и у нас новости.")
        assert "May" not in out
        assert "шестое мая" in out
        assert "две тысячи двадцать шестого года" in out

    def test_ordinal_suffix_stripped(self):
        out = russify_english_dates("News from January 1st, 2026.")
        assert "первое января" in out
        assert "1st" not in out

    def test_no_comma(self):
        out = russify_english_dates("July 4 2026 is a holiday.")
        assert "четвёртое июля" in out

    def test_two_digit_day(self):
        out = russify_english_dates("December 25, 2025.")
        assert "двадцать пятое декабря" in out


class TestWordedDates:

    def test_worded_full(self):
        """Production-caught case: ``May sixth, twenty twenty-six``."""
        out = russify_english_dates(
            "Финансы Просто, выпуск 32, May sixth, twenty twenty-six.",
        )
        assert "May" not in out
        assert "twenty" not in out
        assert "шестое мая" in out
        assert "две тысячи двадцать шестого года" in out

    def test_hyphenated_ordinal(self):
        out = russify_english_dates("Born on April twenty-first, twenty twenty-five.")
        assert "двадцать первое апреля" in out
        assert "две тысячи двадцать пятого года" in out

    def test_space_separated_ordinal(self):
        out = russify_english_dates("Born on April twenty first, twenty twenty five.")
        assert "двадцать первое апреля" in out


class TestNonMatchingInput:

    def test_already_russian_unchanged(self):
        text = "Сегодня шестое мая две тысячи двадцать шестого года."
        assert russify_english_dates(text) == text

    def test_no_date_unchanged(self):
        text = "Это просто предложение без даты."
        assert russify_english_dates(text) == text

    def test_idempotent(self):
        text = "Today is May 6, 2026, и это важный день."
        once = russify_english_dates(text)
        twice = russify_english_dates(once)
        assert once == twice

    def test_unknown_year_passes_through(self):
        # 1999 isn't in the genitive table — should leave as digits
        out = russify_english_dates("On May 6, 1999, something happened.")
        assert "шестое мая" in out
        assert "1999" in out  # year falls through

    def test_empty_input(self):
        assert russify_english_dates("") == ""


class TestRussianShowAdjacencyFilter:
    """The newsletter ``_adjacent_shows_for`` helper must NOT recommend
    English shows to Russian-language subscribers (operator caught FP
    being told to listen to Modern Investing in Russian-language
    newsletters)."""

    def test_finansy_recommends_only_privet(self, monkeypatch):
        """FP's same-language sister is Привет Русский — that's the
        only show a Russian subscriber can fully consume."""
        from engine import newsletter

        def _fake_last_episode(slug):
            return {"slug": slug, "name": slug, "hook": "x", "url": "u"}

        monkeypatch.setattr(
            newsletter, "_last_episode_for_show", _fake_last_episode,
        )

        # Stub the YAML lookup to a known map that includes both
        # English and Russian sisters for FP.
        import yaml as _yaml
        original_safe_load = _yaml.safe_load
        def _fake_safe_load(text):
            return {
                "newsletter": {
                    "network_adjacencies": {
                        "finansy_prosto": [
                            "modern_investing", "privet_russian", "tesla",
                        ],
                    },
                },
            }
        monkeypatch.setattr(_yaml, "safe_load", _fake_safe_load)

        # Make the existence check pass
        from pathlib import Path as _P
        monkeypatch.setattr(_P, "exists", lambda self: True)
        monkeypatch.setattr(
            _P, "read_text", lambda self, encoding="utf-8": "stub",
        )

        adj = newsletter._adjacent_shows_for("finansy_prosto", "2026-05-06")
        assert adj is not None
        slugs = [s["slug"] for s in adj]
        assert "modern_investing" not in slugs, (
            "English-only show recommended to Russian-language "
            "subscriber — bug from May 2026 audit re-introduced"
        )
        assert "tesla" not in slugs
        assert "privet_russian" in slugs
