"""Tests for engine.newsletter — slug, transliteration, send guardrail,
and the daily caller's wiring of sanitizer + subject + body transforms."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Buttondown slug + Cyrillic transliteration
# ---------------------------------------------------------------------------

class TestButtondownSlug:

    def test_english_show_returns_none(self):
        from engine.newsletter import _buttondown_slug_for
        assert _buttondown_slug_for("tesla", 42, "Cybertruck production begins") is None

    def test_russian_show_transliterates(self):
        from engine.newsletter import _buttondown_slug_for
        slug = _buttondown_slug_for(
            "privet_russian", 18, "Космос: 9 русских слов",
        )
        assert slug is not None
        assert slug.startswith("privet-russian-ep018-")
        assert "kosmos" in slug.lower()
        # No percent escapes / Cyrillic.
        assert all(c.isascii() for c in slug)

    def test_finansy_transliterates(self):
        from engine.newsletter import _buttondown_slug_for
        slug = _buttondown_slug_for(
            "finansy_prosto", 30, "Bank of Canada ставка",
        )
        assert slug.startswith("finansy-prosto-ep030-")
        assert all(c.isascii() for c in slug)

    def test_no_hook_falls_back_to_episode_only(self):
        from engine.newsletter import _buttondown_slug_for
        slug = _buttondown_slug_for("privet_russian", 5, "")
        assert slug == "privet-russian-ep005"


class TestTransliteration:

    def test_basic_cyrillic_to_latin(self):
        from engine.newsletter import _transliterate_cyrillic
        assert _transliterate_cyrillic("Космос") == "Kosmos"
        assert _transliterate_cyrillic("Финансы Просто") == "Finansy Prosto"
        assert _transliterate_cyrillic("Привет, Русский!") == "Privet, Russkiy!"

    def test_keeps_non_cyrillic(self):
        from engine.newsletter import _transliterate_cyrillic
        assert _transliterate_cyrillic("Tesla 2026") == "Tesla 2026"

    def test_empty(self):
        from engine.newsletter import _transliterate_cyrillic
        assert _transliterate_cyrillic("") == ""
        assert _transliterate_cyrillic(None) == ""


# ---------------------------------------------------------------------------
# Send guardrail (max 1 send per show per N hours)
# ---------------------------------------------------------------------------

class TestSendGuardrail:

    def test_allows_first_send(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from engine.newsletter import _can_send_now
        assert _can_send_now("test_show", min_hours=20) is True

    def test_blocks_recent_send(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        slug = "test_show"
        # Record a send 1 hour ago.
        now = datetime.datetime.now(datetime.timezone.utc)
        last = (now - datetime.timedelta(hours=1)).isoformat()
        path = Path("digests") / slug / "_newsletter_lastsend.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(last, encoding="utf-8")
        from engine.newsletter import _can_send_now
        assert _can_send_now(slug, min_hours=20) is False

    def test_allows_old_send(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        slug = "test_show"
        now = datetime.datetime.now(datetime.timezone.utc)
        last = (now - datetime.timedelta(hours=25)).isoformat()
        path = Path("digests") / slug / "_newsletter_lastsend.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(last, encoding="utf-8")
        from engine.newsletter import _can_send_now
        assert _can_send_now(slug, min_hours=20) is True

    def test_corrupt_lastsend_does_not_block(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        slug = "test_show"
        path = Path("digests") / slug / "_newsletter_lastsend.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("garbage", encoding="utf-8")
        from engine.newsletter import _can_send_now
        # Conservative — never block on file errors.
        assert _can_send_now(slug, min_hours=20) is True

    def test_record_send_writes_iso_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from engine.newsletter import _record_send
        _record_send("test_show")
        path = Path("digests") / "test_show" / "_newsletter_lastsend.txt"
        assert path.exists()
        # Round-trips as ISO datetime.
        datetime.datetime.fromisoformat(path.read_text(encoding="utf-8").strip())


# ---------------------------------------------------------------------------
# Subject builder daily-mode
# ---------------------------------------------------------------------------

class TestDailySubjectBuilder:

    def test_caps_hook_at_50_chars_for_dailies(self):
        from engine.newsletter_template import build_subject_line
        long_hook = (
            "Tesla has introduced its cheapest Model 3 in Canada at a record "
            "low while planning a robotaxi launch in Texas"
        )
        subject = build_subject_line(
            "tesla", long_hook, hook_max_chars=50, is_daily=True,
        )
        # Hook side should be ≤50+1 (ellipsis) chars.
        # Suffix is " · Tesla Shorts 🚀" or similar.
        assert len(subject) < 100
        assert "Tesla Shorts" in subject  # show short label preserved

    def test_no_hook_uses_daily_fallback(self):
        from engine.newsletter_template import build_subject_line
        send_date = datetime.date(2026, 5, 2)
        subject = build_subject_line(
            "tesla", "", send_date=send_date, is_daily=True,
        )
        assert "May 2 update" in subject
