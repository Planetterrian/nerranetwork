"""Tests for Cyrillic rendering in generated HTML.

The Russian shows ("Финансы Просто", "Привет, Русский!") were
rendering with Python's default ``ensure_ascii=True`` JSON behavior,
which produced unreadable ``\\u0424\\u0438...`` escape sequences
inside ``<script type="application/ld+json">`` blocks and
``const SHOW_NAME = ...`` template emissions. That's bad for SEO
(Google parsers prefer Unicode) and bad for shareable copy-paste.

These tests lock in the fix so a future change can't silently
re-introduce the regression.
"""

from __future__ import annotations


def test_jinja_env_emits_unicode_for_cyrillic_via_tojson():
    """The shared Jinja env's ``tojson`` filter must render Cyrillic
    show names as readable Unicode, not as ``\\u0424...`` escapes."""
    from generate_html import _get_jinja_env

    env = _get_jinja_env()
    rendered = env.from_string("{{ s | tojson }}").render(s="Финансы Просто")
    assert rendered == '"Финансы Просто"'
    assert "\\u04" not in rendered


def test_jinja_env_handles_attribute_dict_through_tojson():
    """Schema.org JSON-LD blocks pass dicts through ``tojson``; make
    sure nested Cyrillic strings come through unescaped too."""
    from generate_html import _get_jinja_env

    env = _get_jinja_env()
    rendered = env.from_string("{{ d | tojson }}").render(
        d={"name": "Привет, Русский!", "lang": "ru"}
    )
    assert "Привет, Русский!" in rendered
    assert "\\u04" not in rendered


def test_blog_jsonld_emits_unicode():
    """``engine.blog._build_jsonld`` should produce a JSON-LD block
    with readable Cyrillic, not ``\\u04..`` escapes."""
    from engine.blog import _build_jsonld

    metadata = {
        "title": "Привет, Русский! — Урок 1",
        "hook": "Сегодня учим погоду.",
        "date_iso": "2026-04-30",
        "word_count": 120,
        "episode_num": 1,
    }
    out = _build_jsonld(
        metadata,
        show_name="Привет, Русский!",
        blog_url="https://nerranetwork.com/blog/privet_russian/ep001.html",
        show_config={"slug": "privet_russian", "name": "Привет, Русский!"},
    )
    assert "Привет, Русский!" in out
    assert "Урок 1" in out
    assert "Сегодня учим погоду." in out
    # No Unicode escapes leaked through.
    assert "\\u04" not in out
