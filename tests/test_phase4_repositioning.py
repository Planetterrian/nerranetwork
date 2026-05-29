"""Phase 4 drift guards: per-show repositioning + per-episode blog title.

Repositioning is editorial (prompt/source) direction, so these guards pin that
the signature instructions are present (not that the LLM obeys them) plus the
YAML sourcing changes — and that the blog title now uses the unique episode
hook instead of the repeated show name.
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS = PROJECT_ROOT / "shows" / "prompts"


def _read(rel):
    return (PROMPTS / rel).read_text(encoding="utf-8")


class TestOmniViewSteelMan:
    def test_digest_has_steel_man(self):
        assert "STEEL-MAN" in _read("omni_view_digest.txt")

    def test_podcast_has_steel_man(self):
        assert "STEEL-MAN" in _read("omni_view_podcast.txt")


class TestFinansyProstoWomen:
    def test_digest_women_focus(self):
        txt = _read("fp_digest.txt")
        assert "spousal RRSP" in txt
        assert "ФОКУС НА ЖЕНЩИН" in txt

    def test_podcast_women_focus(self):
        assert "spousal RRSP" in _read("fp_podcast.txt")

    def test_yaml_has_women_finance_query(self):
        txt = (PROJECT_ROOT / "shows" / "finansy_prosto.yaml").read_text(encoding="utf-8")
        assert "spousal RRSP" in txt or "financial independence" in txt


class TestPrivetRussianVocabFirst:
    def test_digest_vocabulary_first(self):
        assert "VOCABULARY-FIRST" in _read("privet_russian_digest.txt")

    def test_podcast_vocabulary_first(self):
        assert "VOCABULARY-FIRST" in _read("privet_russian_podcast.txt")


class TestEnvIntelBrief:
    def test_digest_compliance_brief(self):
        assert "Compliance Brief" in _read("env_intel_digest.txt")

    def test_podcast_compliance_brief(self):
        assert "Compliance Brief" in _read("env_intel_podcast.txt")

    def test_yaml_all_province_queries(self):
        txt = (PROJECT_ROOT / "shows" / "env_intel.yaml").read_text(encoding="utf-8")
        for prov in ("Ontario", "Alberta", "Quebec"):
            assert prov in txt, f"missing all-province query for {prov}"


class TestPromptsStillRenderSafe:
    """The repositioning edits must not break prompt rendering."""

    @pytest.mark.parametrize("rel", [
        "omni_view_digest.txt", "omni_view_podcast.txt",
        "fp_digest.txt", "fp_podcast.txt",
        "privet_russian_digest.txt", "privet_russian_podcast.txt",
        "env_intel_digest.txt", "env_intel_podcast.txt",
    ])
    def test_renders_with_forgiving_map(self, rel):
        from engine.generator import load_prompt

        class _F(dict):
            def __missing__(self, k):
                return ""

        # Must not raise on a malformed/unescaped brace.
        load_prompt(str(PROMPTS / rel), _F())


class TestPerEpisodeTitle:
    def test_blog_title_uses_hook_not_show_name(self):
        import re
        from engine.blog import generate_blog_post_html
        from generate_html import NETWORK_SHOWS, _get_jinja_env

        hook = "A uniquely distinctive episode hook about frontier model releases."
        metadata = {
            "episode_num": 999,
            "title": "Models & Agents",          # the show-name fallback case
            "hook": hook,
            "date": "2026-05-29",
            "date_iso": "2026-05-29",
            "source_urls": [],
            "word_count": 400,
            "reading_time_min": 2,
        }
        html = generate_blog_post_html(
            "## Top Story\n\nSomething happened.\n",
            metadata, NETWORK_SHOWS["models_agents"], _get_jinja_env(),
        )
        # The BlogPosting headline (and <title>) should now be the hook.
        assert hook[:40] in html
        m = re.search(r"<title>(.*?)</title>", html)
        assert m and "Models & Agents" != m.group(1).strip(), "title is bare show name"
        assert hook[:30] in m.group(1), "title should carry the unique hook"

    def test_blog_title_falls_back_to_show_name_without_hook(self):
        from engine.blog import generate_blog_post_html
        from generate_html import NETWORK_SHOWS, _get_jinja_env

        metadata = {
            "episode_num": 998, "title": "", "hook": "",
            "date": "2026-05-29", "date_iso": "2026-05-29",
            "source_urls": [], "word_count": 100, "reading_time_min": 1,
        }
        # No title, no hook -> must not crash; falls back to show name.
        html = generate_blog_post_html(
            "## X\n\nText.\n", metadata, NETWORK_SHOWS["models_agents"], _get_jinja_env(),
        )
        assert "Models &amp; Agents" in html or "Models & Agents" in html
