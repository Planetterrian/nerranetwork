"""Drift guards for the show-generic Mira interview pipeline (Sept 2026).

Nerra Voices is the second Mira-hosted live-interview show. It runs through
the SAME code as The Age of AI (pipelines/voices/*.py) — every script
resolves the show per Supabase row via ``show_for(interview, app)`` and
reads show-specific settings from ``pipelines/voices/shows.py`` (backed by
``shows/<slug>.yaml``). These tests pin:

* the registry: both shows load with distinct feeds / paths / pages;
* ``show_for`` precedence (interview → application → default);
* Mira's compiled prompt carries the right show identity;
* per-show episode memory;
* NO hardcoded ``age_of_ai`` / ``Age of AI`` / ``age-of-ai`` literals in the
  pipeline code, prompts or email templates (the registry is the only place
  a show name may live).
"""

from __future__ import annotations

import html as _html
import io
import sys
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PIPELINES = ROOT / "pipelines" / "voices"
PROMPTS = PIPELINES / "prompts"
EMAIL_TEMPLATES = ROOT / "templates" / "email"

sys.path.insert(0, str(PIPELINES))

from pipelines.voices.shows import (  # noqa: E402
    DEFAULT_SHOW, VOICE_SHOW_SLUGS, VoiceShow, all_shows, get_show, show_for,
)

SHOW_LITERALS = ("age_of_ai", "Age of AI", "age-of-ai")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_both_shows_registered(self):
        assert set(VOICE_SHOW_SLUGS) == {"age_of_ai", "nerra_voices"}
        assert DEFAULT_SHOW == "age_of_ai"
        assert {s.slug for s in all_shows()} == set(VOICE_SHOW_SLUGS)

    def test_names(self):
        assert get_show("age_of_ai").name == "The Age of AI"
        assert get_show("nerra_voices").name == "Nerra Voices"

    @pytest.mark.parametrize("attr", [
        "r2_prefix", "rss_file", "summaries_json", "page", "apply_page",
        "guid_prefix", "audio_subdir", "episode_prefix", "brand_color",
        "sign_off", "premise", "opening_line", "closing_question",
        "music_bed", "cover",
    ])
    def test_shows_are_distinct(self, attr):
        a, b = get_show("age_of_ai"), get_show("nerra_voices")
        assert getattr(a, attr) and getattr(b, attr), attr
        assert getattr(a, attr) != getattr(b, attr), (
            f"{attr} is shared between the two shows — the feeds/paths "
            f"would collide")

    def test_r2_keys_are_namespaced(self):
        """Do NOT change R2 bucket paths (CLAUDE.md) — Age of AI keeps its
        July 2026 prefix exactly; Nerra Voices gets its own."""
        assert get_show("age_of_ai").r2_key("raw", "x.mp3") == "age_of_ai/raw/x.mp3"
        assert get_show("nerra_voices").r2_key("video", "v.mp4") == "nerra_voices/video/v.mp4"

    def test_age_of_ai_feed_unchanged(self):
        """The July 2026 publish literals now come from the registry — pin
        them so the live feed's channel metadata does not drift."""
        s = get_show("age_of_ai")
        assert s.rss_file == "age_of_ai_podcast.rss"
        assert s.audio_subdir == "digests/age_of_ai"
        assert s.summaries_json == "digests/age_of_ai/summaries_age_of_ai.json"
        assert s.guid_prefix == "age-of-ai"
        assert s.rss_link == "https://nerranetwork.com/age-of-ai.html"
        assert s.page_url == "https://nerranetwork.com/age-of-ai.html"
        assert s.rss_category == "Society & Culture"
        assert s.rss_subcategory == "Personal Journals"
        assert s.episode_prefix == "Age_of_AI"
        assert s.brand_color.upper() == "#7C3AED"

    def test_nerra_voices_feed(self):
        s = get_show("nerra_voices")
        assert s.rss_file == "nerra_voices_podcast.rss"
        assert s.page == "nerra-voices.html"
        assert s.rss_link == s.page_url
        assert s.summaries_json == "digests/nerra_voices/summaries_nerra_voices.json"
        assert s.episode_prefix == "Nerra_Voices"
        assert "show=nerra_voices" in s.studio_url("abc")
        assert "interview=abc" in s.studio_url("abc")

    def test_unknown_slug_rejected(self):
        with pytest.raises(KeyError):
            get_show("tesla")

    def test_prompt_path_falls_back_to_shared(self):
        """The per-show prompt dir only holds a README today — every
        template resolves to the shared prompt for both shows."""
        for slug in VOICE_SHOW_SLUGS:
            p = get_show(slug).prompt_path("mira_system_prompt.txt")
            assert p == PROMPTS / "mira_system_prompt.txt", (slug, p)
        assert (PROMPTS / "nerra_voices" / "README.md").exists()


# ---------------------------------------------------------------------------
# show_for precedence
# ---------------------------------------------------------------------------

class TestShowFor:
    def test_default_when_no_row_carries_show(self):
        assert show_for({}, {}).slug == DEFAULT_SHOW
        assert show_for(None).slug == DEFAULT_SHOW
        assert show_for({"show": ""}, {"show": None}).slug == DEFAULT_SHOW

    def test_interview_wins_over_application(self):
        assert show_for({"show": "nerra_voices"}, {"show": "age_of_ai"}).slug == "nerra_voices"
        assert show_for({"show": "age_of_ai"}, {"show": "nerra_voices"}).slug == "age_of_ai"

    def test_application_fallback(self):
        assert show_for({}, {"show": "nerra_voices"}).slug == "nerra_voices"
        assert show_for({"show": None}, {"show": "nerra_voices"}).slug == "nerra_voices"

    def test_returns_registry_instance(self):
        assert isinstance(show_for({"show": "nerra_voices"}), VoiceShow)


# ---------------------------------------------------------------------------
# Mira's compiled prompt
# ---------------------------------------------------------------------------

_APP = {"name": "Jane Doe", "title": "Welder", "organization": "Doe Fabrication"}
_BRIEF = {"bio_research": "BRIEF-X",
          "likely_questions": [{"question": "Q-ONE?"}, "Q-TWO?"]}


class TestCompiledPrompt:
    def test_nerra_voices_prompt(self):
        from fire_interviews import compile_mira_prompt
        nv = get_show("nerra_voices")
        prompt = compile_mira_prompt(
            {"episode_thesis": "THESIS-X", "show": "nerra_voices"}, _APP, _BRIEF)
        assert "Nerra Voices" in prompt
        assert nv.closing_question in prompt
        assert nv.opening_line in prompt
        assert nv.premise in prompt
        assert "The Age of AI" not in prompt
        assert "the one bet you're making" not in prompt
        assert "{{" not in prompt
        for needle in ("Jane Doe", "Welder", "Doe Fabrication", "THESIS-X",
                       "BRIEF-X", "Q-ONE?", "Q-TWO?"):
            assert needle in prompt, needle

    def test_age_of_ai_prompt(self):
        from fire_interviews import compile_mira_prompt
        aoa = get_show("age_of_ai")
        prompt = compile_mira_prompt(
            {"episode_thesis": "THESIS-X", "show": "age_of_ai"}, _APP, _BRIEF)
        assert "The Age of AI" in prompt
        assert aoa.closing_question in prompt
        assert "the one bet you're making" in prompt
        assert "Nerra Voices" not in prompt
        assert "{{" not in prompt

    def test_show_from_application_when_interview_lacks_it(self):
        from fire_interviews import compile_mira_prompt
        prompt = compile_mira_prompt(
            {"episode_thesis": "T"}, {**_APP, "show": "nerra_voices"}, _BRIEF)
        assert "Nerra Voices" in prompt and "The Age of AI" not in prompt

    def test_every_prompt_template_renders_for_both_shows(self):
        """Every shared prompt (brief, thesis, questions, narration, the 8
        editorial passes) must leave no show token unfilled for either
        show — load_prompt does literal replacement, so a stray token
        ships verbatim into the LLM prompt."""
        from common import load_prompt
        templates = [p.name for p in PROMPTS.glob("*.txt")] + [
            f"editorial_passes/{p.name}"
            for p in (PROMPTS / "editorial_passes").glob("*.txt")]
        assert len(templates) >= 13
        for slug in VOICE_SHOW_SLUGS:
            show = get_show(slug)
            for t in templates:
                text = load_prompt(t, show=show)
                for tok in ("{{show_name}}", "{{show_premise}}", "{{show_slug}}",
                            "{{opening_line}}", "{{closing_question}}"):
                    assert tok not in text, (slug, t, tok)
                if "{{show_name}}" in (show.prompt_path(t)).read_text(encoding="utf-8"):
                    assert show.name in text, (slug, t)


# ---------------------------------------------------------------------------
# Episode memory is per show
# ---------------------------------------------------------------------------

class TestEpisodeMemory:
    def test_nerra_voices_empty_without_summaries(self, tmp_path, monkeypatch):
        from common import episode_memory_block
        nv = get_show("nerra_voices")
        if nv.summaries_path.exists():
            pytest.skip("nerra_voices summaries exist — absent-file case not testable here")
        assert episode_memory_block(show="nerra_voices") == ""
        assert episode_memory_block(show=nv) == ""

    def test_age_of_ai_memory_unchanged(self):
        from common import episode_memory_block
        default = episode_memory_block()
        assert default == episode_memory_block(show="age_of_ai")
        if get_show("age_of_ai").summaries_path.exists():
            assert "Ep1" in default


# ---------------------------------------------------------------------------
# Email templates
# ---------------------------------------------------------------------------

class TestEmailTemplates:
    @pytest.mark.parametrize("slug", VOICE_SHOW_SLUGS)
    def test_templates_render_with_show_branding(self, slug):
        from common import render_email
        show = get_show(slug)
        ctx = dict(guest_name="Jane", scheduled_at="soon", interview_id="abc",
                   thesis="T", questions=["Q?"], booking_url="https://b",
                   review_url="https://r", episode_number=3,
                   episode_url="https://e", body_html="<p>x</p>", missed=True)
        for tpl in sorted(EMAIL_TEMPLATES.glob("voices_*.j2")):
            html = _html.unescape(render_email(tpl.name, show=show, **ctx))
            if tpl.name != "voices_weekly_digest.j2":  # unbranded wrapper
                assert show.brand_color in html, (slug, tpl.name)
                assert show.sign_off in html, (slug, tpl.name)
            assert show.name in html, (slug, tpl.name)
            other = [s for s in all_shows() if s.slug != slug][0]
            assert other.name not in html, (slug, tpl.name)
            assert "{{" not in html

    def test_studio_url_is_per_show(self):
        from common import render_email
        html = _html.unescape(render_email(
            "voices_prep_brief.j2", show="nerra_voices",
            guest_name="J", scheduled_at="s", interview_id="ID1",
            thesis="T", questions=[]))
        assert "interview=ID1" in html and "show=nerra_voices" in html
        assert get_show("nerra_voices").closing_question in html

    def test_every_render_email_call_passes_show(self):
        for py in PIPELINES.glob("*.py"):
            src = py.read_text(encoding="utf-8")
            for i, line in enumerate(src.splitlines()):
                if "render_email(" in line and "def render_email" not in line:
                    window = "\n".join(src.splitlines()[i:i + 8])
                    assert "show=" in window, (py.name, i + 1)


# ---------------------------------------------------------------------------
# No hardcoded show literals outside the registry
# ---------------------------------------------------------------------------

def _code_only(source: str) -> str:
    """Python source with comments and docstrings stripped (a mention of
    the original show in a comment is fine; in code it is a regression)."""
    out = []
    prev_type = tokenize.ENCODING
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING and prev_type in (
                tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                tokenize.ENCODING, tokenize.NL):
            prev_type = tok.type
            continue  # docstring / bare string statement
        if tok.type not in (tokenize.NL,):
            prev_type = tok.type
        out.append(tok.string)
    return " ".join(out)


class TestNoHardcodedShow:
    @pytest.mark.parametrize("py", sorted(
        p.name for p in PIPELINES.glob("*.py") if p.name != "shows.py"))
    def test_pipeline_scripts(self, py):
        code = _code_only((PIPELINES / py).read_text(encoding="utf-8"))
        for lit in SHOW_LITERALS:
            assert lit not in code, f"{py} still hardcodes {lit!r}"

    @pytest.mark.parametrize("py", sorted(
        p.relative_to(PIPELINES).as_posix()
        for p in (PIPELINES / "validators").glob("*.py")))
    def test_validators_only_list_the_show_as_a_target(self, py):
        from validators.schema_validators import KNOWN_SHOWS
        assert {"age_of_ai", "nerra_voices"} <= KNOWN_SHOWS

    @pytest.mark.parametrize("txt", sorted(
        p.relative_to(PROMPTS).as_posix() for p in PROMPTS.rglob("*.txt")))
    def test_prompts(self, txt):
        text = (PROMPTS / txt).read_text(encoding="utf-8")
        assert "Age of AI" not in text, f"{txt} hardcodes the show name"
        # The classify/callout passes may list age_of_ai as a TARGET slug.
        if "age_of_ai" in text:
            assert "{{show_slug}}" in text, txt

    @pytest.mark.parametrize("j2", sorted(
        p.name for p in EMAIL_TEMPLATES.glob("voices_*.j2")))
    def test_email_templates(self, j2):
        body = (EMAIL_TEMPLATES / j2).read_text(encoding="utf-8")
        body = body.split("#}", 1)[1] if "#}" in body else body  # header comment
        for lit in SHOW_LITERALS + ("#7C3AED", "7c3aed"):
            assert lit not in body, f"{j2} hardcodes {lit!r}"
        assert "{{ show_name }}" in body or j2 in (
            "voices_transcript_for_approval.j2",), j2

    def test_produce_sets_source_show(self):
        src = (PIPELINES / "produce_episode.py").read_text(encoding="utf-8")
        assert '"source_show": show.slug' in src

    def test_publish_regenerates_the_right_show(self):
        src = (PIPELINES / "publish_episode.py").read_text(encoding="utf-8")
        assert '"--show", show.slug' in src
        assert "show.rss_path" in src and "show.summaries_path" in src
        assert "def _next_episode_number(show" in src

    def test_reminder_sms_uses_show_name(self):
        src = (PIPELINES / "fire_interviews.py").read_text(encoding="utf-8")
        assert 'f"Mira here, from {show.name} (Nerra Network).' in src
        assert "show.studio_url(interview['id'])" in src

    def test_memory_registry_has_nerra_voices(self):
        from engine import show_memory
        assert "nerra_voices" in show_memory.SHOW_MEMORY_CONFIGS
        cfg = show_memory.get_config("nerra_voices")
        assert cfg.default_programs and cfg.theme_keywords


# ---------------------------------------------------------------------------
# Landmine guard: pipelines/voices/shows.py must not shadow shows/hooks
# ---------------------------------------------------------------------------

class TestRegistryDoesNotShadowShowsPackage:
    def test_shows_hooks_still_import_with_pipelines_on_path(self):
        """This module puts pipelines/voices at sys.path[0] (like the
        scripts themselves at runtime), which makes a bare ``import shows``
        resolve to the registry file instead of the repo's ``shows/``
        package. The registry compensates with a ``__path__`` so
        ``shows.hooks.*`` keeps importing — losing that broke collection
        of every hook test in the suite."""
        import importlib
        import shows as top
        if Path(top.__file__ or "").resolve() == (PIPELINES / "shows.py").resolve():
            assert str(ROOT / "shows") in list(top.__path__)
        mod = importlib.import_module("shows.hooks.tesla")
        assert Path(mod.__file__).resolve() == (ROOT / "shows" / "hooks" / "tesla.py").resolve()
