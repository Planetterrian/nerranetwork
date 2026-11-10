"""Nov 10 2026 growth review: SpaceX Daily and Tesla Shorts Time ask for a
short app title (a ``**TITLE:**`` line), the opt-in Offshore North uses.

The feed title was the whole hook clipped at 100 characters ("Ep 152:
Qualcomm Dragonwing platforms will power tens of thousands of Starlink
Mobile 5G base…"); Apple and Spotify show about 40-60.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SNIPPET = ROOT / "shows" / "prompts" / "_shared" / "app_title.txt"


def _extract_short_title():
    src = (ROOT / "run_show.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.FunctionDef) and n.name == "_extract_short_title")
    ns: dict = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "run_show", "exec"), ns)
    return ns["_extract_short_title"]


class TestTheFlagshipsAskForATitle:
    def test_both_digest_prompts_render_the_title_line(self):
        for slug in ("spacex", "tesla"):
            raw = (ROOT / "shows" / "prompts" / f"{slug}_digest.txt").read_text(encoding="utf-8")
            assert "<<include: _shared/app_title.txt>>" in raw


    def test_the_include_resolves_in_the_rendered_prompt(self):
        from engine.generator import _resolve_includes
        for slug in ("spacex", "tesla"):
            raw = (ROOT / "shows" / "prompts" / f"{slug}_digest.txt").read_text(encoding="utf-8")
            out = _resolve_includes(raw, ROOT / "shows" / "prompts")
            assert "**TITLE:** [The episode title podcast apps show" in out

    def test_the_snippet_states_the_shape_and_quotes_no_example(self):
        text = SNIPPET.read_text(encoding="utf-8")
        assert text.startswith("**TITLE:** [")
        assert "60 characters" in text
        # De-seed by shape: no quoted specimen headline.
        assert '"' not in text and "e.g." not in text.lower()

    def test_the_runner_reads_the_line(self):
        extract = _extract_short_title()
        digest = "# SpaceX Daily\n**HOOK:** A sentence.\n**TITLE:** Starship Flight 15 Ship Catch\n### Top News\n"
        assert extract(digest) == "Starship Flight 15 Ship Catch"

    def test_the_sanitizer_strips_it_from_every_published_copy(self):
        from engine.newsletter_sanitizer import scrub_scaffold
        text = scrub_scaffold("**TITLE:** Starship Flight 15 Ship Catch\nBody text.\n")
        assert "TITLE" not in text and "Body text." in text


class TestTheBlogKeepsTheHook:
    def test_the_blog_short_title_gate_stays_off_for_the_flagships(self):
        # The blog's <h1> switch reads the RAW prompt for "**TITLE:**". The
        # flagships' summaries hold years of CLIPPED-hook titles; switching
        # the gate on would put those truncated titles into old posts'
        # headings. The line lives in an include so the gate stays off.
        from engine.blog import _show_emits_short_title
        _show_emits_short_title.cache_clear()
        assert _show_emits_short_title("spacex") is False
        assert _show_emits_short_title("tesla") is False
