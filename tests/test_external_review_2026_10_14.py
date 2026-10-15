"""Oct 14 2026 — an outside review of the Oct 13 slate, checked and acted on.

Checked against the committed data: chapter titles cut mid-phrase and lead
chapters missing (TRUE — the clip ran at 60 while most desk lead headlines
run 60-80 and every hook runs over 60); bare URL lines under items (TRUE —
49 in seven days on the desks and the Board); FF Ep221's headline not
matching the opening story (TRUE — the hook's item sat at 2; the hook's
story led the list on 4 of 7 FF, 4 of 8 PT and 3 of 8 Tesla episodes); the
narrative shows listing no sources (TRUE — the research pages verified the
claims and reached no reader). NOT true: Top World's Both Sides "about a
different story" (its spec is a named disagreement from today's articles,
not the lead); Vancouver "20% where the source says 18%" (the source says
20 per cent; the ledger verified it); Nerra Daily "lists no sources" (its
rundown links each show's post by design).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Chapter titles: one budget, whole headlines, a lead chapter on every desk
# ---------------------------------------------------------------------------

class TestChapterTitles:
    def test_one_budget_for_headline_titles(self):
        from engine.chapters import HEADLINE_TITLE_MAX, _best_headline_for_segment, _clip_title
        from engine.titles import HEADLINE_CHAPTER_TITLE_MAX
        assert HEADLINE_TITLE_MAX == HEADLINE_CHAPTER_TITLE_MAX == 80
        h = "Nigeria's forces say they killed over 1,000 militants in a three-day operation"
        assert len(h) == 78
        assert _clip_title(h) == h
        assert _best_headline_for_segment("militants killed operation forces nigeria", [h], set()) == h

    def test_the_slate_fragment_is_whole_now(self):
        from engine.chapters import _clip_title
        h = "Saudi Arabia halts the number of pilgrims it will admit next year from Pakistan"
        out = _clip_title(h)
        assert out == h, out
        assert "halts the number" != out[-16:]

    def test_lead_section_name(self):
        from engine.chapters import lead_section_name
        assert lead_section_name("# S\n> **Hook.**\n\n### Lead\nbody") == "Lead"
        assert lead_section_name("# S\n### Top Story\n") == "Top Story"
        assert lead_section_name("# S\n## Today's lead story (1)\n### 1) Headline\n") == "Today's lead story"
        assert lead_section_name("# S\n### Top 15 Science & Health Discoveries\n") == "Top 15 Science & Health Discoveries"
        # A story heading is never a slot name.
        assert lead_section_name("# S\n### 1) China-North Korea bridge opens\n") == ""
        assert lead_section_name("# S\n### Both Sides: Should they keep striking?\n") == ""
        assert lead_section_name("") == ""

    def test_a_long_hook_under_a_bare_heading_gets_the_lead_chapter(self):
        """Asia Pacific Ep021's shape: a 94-char hook, the lead written under
        ``### Lead`` with no headline of its own. Before: no lead chapter."""
        from engine.chapters import Chapter, _lead_story_split
        hook = ("Sixteen people drowned in Bihar while collecting festival offerings "
                "from a swollen river on Tuesday")
        assert len(hook) > 80
        intro = "This is the desk. " * 4
        lead = ("Sixteen people drowned in Bihar on Tuesday while collecting festival "
                "offerings from a river swollen by three days of rain, police said.")
        lines = (intro + "\n\n" + lead + "\n\nNext story about a port.\n").splitlines(keepends=True)
        n = sum(len(ln.split()) for ln in lines)
        head = Chapter(title="Introduction", word_start=0, word_end=n, char_start=0,
                       char_end=sum(len(ln) for ln in lines))
        assert _lead_story_split(lines, head, [hook]) is None
        found = _lead_story_split(lines, head, [hook], fallback_title="Lead")
        assert found and found[2] == "Lead"
        # A hook that fits the budget is still used whole, never the fallback.
        short = "Sixteen drowned in Bihar collecting festival offerings"
        found = _lead_story_split(lines, head, [short], fallback_title="Lead")
        assert found and found[2] == short

    def test_parse_chapters_titles_the_lead_from_the_digest_heading(self):
        from engine.chapters import parse_chapters
        from engine.config import SectionMarker
        hook = ("Sixteen people drowned in Bihar while collecting festival offerings "
                "from a swollen river on Tuesday morning")
        digest = f"# Desk\n> **{hook}**\n\n### Lead\n{hook}\n\n### Across the Region\n1. **Port** — x\n"
        script = ("Welcome to the desk, this is Mira. " * 3 + "\n\n" +
                  "Sixteen people drowned in Bihar on Tuesday while collecting festival "
                  "offerings from a river swollen by rain, police said. " * 3 + "\n\n" +
                  "Across the region now. " * 8 + "\n\nThat's the desk for today.")
        markers = [SectionMarker(pattern="Welcome to the desk", title="Introduction", where="start"),
                   SectionMarker(pattern="Across the region", title="Across the Region"),
                   SectionMarker(pattern="That's the desk", title="Closing", where="end")]
        titles = [c.title for c in parse_chapters(script, markers, show_name="Desk",
                                                  story_headlines=[hook], digest_text=digest)]
        assert "Lead" in titles, titles
        assert not any(hook.startswith(t) and len(t) < len(hook) for t in titles)


# ---------------------------------------------------------------------------
# Bare URL lines become Source lines
# ---------------------------------------------------------------------------

class TestBareUrlLines:
    def test_standalone_url_lines_become_source_lines(self):
        from engine.newsletter_body import linkify_bare_url_lines
        text = ("Text. Source: [polymarket.com](https://polymarket.com/e/a)\n"
                "https://manifold.markets/x/y\n"
                "  https://www.bbc.com/news/1).\n"
                "- https://x.com/a\n"
                "See https://a.b/c now\n"
                "```claims\nhttps://q.r/s\n```\n")
        out = linkify_bare_url_lines(text)
        assert "Source: [manifold.markets](https://manifold.markets/x/y)" in out
        assert "  Source: [bbc.com](https://www.bbc.com/news/1)" in out
        assert "- https://x.com/a" in out and "See https://a.b/c now" in out
        assert "```claims\nhttps://q.r/s\n```" in out
        assert linkify_bare_url_lines(out) == out  # idempotent

    def test_it_runs_in_the_canonical_transform(self):
        from engine.newsletter_body import transform_daily_body
        out = transform_daily_body("# S\n> **Hook.**\n\n1. **A** — x\nbody.\nhttps://example.org/a\n")
        assert "Source: [example.org](https://example.org/a)" in out

    def test_the_show_notes_and_the_lint_see_them(self):
        from engine.digest_lint import items_without_source
        from engine.newsletter_body import transform_daily_body
        from engine.show_notes import source_pairs
        raw = "# S\n> **Hook.**\n\n### Lead\n1. **A story** — Outlet\nbody.\nhttps://example.org/a\n\n2. **B story** — Outlet\nbody.\nhttps://example.net/b\n"
        before = items_without_source(raw)
        out = transform_daily_body(raw)
        assert [d for d, _ in source_pairs(out)] == ["example.org", "example.net"]
        assert items_without_source(out)[1] == 0 and before[0] == 2


# ---------------------------------------------------------------------------
# The hook's story is item one
# ---------------------------------------------------------------------------

DIGEST = """# Fascinating Frontiers
> **New helium measurements are confirming the exact mix forged in the universe's first minutes.**

### Space Stories
1. **APOD captures desert stairway under the Milky Way** — NASA
A photograph of a stairway. Source: https://a.org/1

2. **Primordial helium matches Big Bang predictions** — Phys.org
New helium measurements in distant clouds match the mix forged in the first minutes. Source: https://a.org/2

3. **Starship prepares for a Florida launch** — Space
Pad 39A work continues. Source: https://a.org/3

### Cosmic Spotlight
Something deeper.
"""


class TestHookItemFirst:
    def test_the_hooks_item_moves_to_the_top_and_renumbers(self):
        from engine.hook_item import promote_hook_item
        out, moved = promote_hook_item(DIGEST)
        assert moved == 2
        items = re.findall(r"^(\d+)\. \*\*(.+?)\*\*", out, re.M)
        assert [n for n, _ in items] == ["1", "2", "3"]
        assert items[0][1].startswith("Primordial helium")
        assert items[1][1].startswith("APOD")
        assert "### Cosmic Spotlight\nSomething deeper." in out
        # Idempotent: a second pass moves nothing.
        assert promote_hook_item(out) == (out, 0)

    def test_a_weak_or_tied_match_moves_nothing(self):
        from engine.hook_item import promote_hook_item
        weak = DIGEST.replace("New helium measurements in distant clouds match the mix forged in the first minutes.",
                              "Something else entirely about neutrinos.")
        assert promote_hook_item(weak)[1] == 0
        nohook = DIGEST.replace("> **New helium", "New helium")
        assert promote_hook_item(nohook) == (nohook, 0)
        assert promote_hook_item("") == ("", 0)

    def test_replay_on_the_committed_digests(self):
        """SpaceX, M&A, the desks and MAG 7 wrote the lead first on the Oct 8-14
        calibration set: the promoter must move nothing there. FF / PT / Tesla
        carry the cases it is for.

        Oct 15 2026: pinned to the dated calibration set. This guard read the
        LATEST six digests and went red the first day SpaceX's hook told its
        second story (Ep131, Grok Bot over the Starshield lead) — a reading of
        the data, not a rule; SpaceX is not opted in, so nothing shipped
        differently. A guard that reads committed data judges fixed files."""
        import glob
        from engine.hook_item import promote_hook_item
        for show in ("spacex", "models_agents", "omni_view_europe", "mag7"):
            files = [f for f in sorted(glob.glob(str(ROOT / "digests" / show / "*_Ep*_202610??.md")))
                     if "claims" not in f and "20261008" <= f.rsplit("_", 1)[-1][:8] <= "20261014"]
            assert files, show
            for f in files:
                assert promote_hook_item(Path(f).read_text(encoding="utf-8"))[1] == 0, f
        f = ROOT / "digests/fascinating_frontiers/Fascinating_Frontiers_Ep221_20261013.md"
        if f.is_file():
            out, moved = promote_hook_item(f.read_text(encoding="utf-8"))
            assert moved == 2 and "1. **Primordial Helium" in out

    def test_opt_in_and_wiring(self):
        from engine.config import load_config
        for slug, want in (("tesla", True), ("fascinating_frontiers", True),
                           ("planetterrian", True), ("spacex", False), ("omni_view_europe", False)):
            assert load_config(ROOT / "shows" / f"{slug}.yaml").hook_item_first is want, slug
        src = (ROOT / "run_show.py").read_text()
        assert src.count("_promote_hook_item(") == 3  # def + both dedupe sites
        assert src.index("_dedupe_digest_sections(x_thread, config, metrics)") < src.index(
            "_promote_hook_item(x_thread, config, metrics)")


# ---------------------------------------------------------------------------
# Research sources on the narrative shows
# ---------------------------------------------------------------------------

class TestResearchSources:
    ARTS = [
        {"source_kind": "research", "link": "https://www.jstor.org/stable/1", "title": "The Coal Question"},
        {"source_kind": "research", "link": "https://energyhistory.yale.edu/jevons", "title": "Jevons"},
        {"source_kind": "research", "link": "https://www.jstor.org/stable/1", "title": "dup"},
        {"source_kind": "news", "link": "https://news.example/a", "title": "not research"},
        {"source_kind": "research", "link": "", "title": "no url"},
    ]

    def test_block_lists_each_research_page_once(self):
        from engine.research_sources import append_research_sources, research_sources_block
        block = research_sources_block(self.ARTS)
        assert block.startswith("### Sources\n")
        assert block.count("\n- [") == 2
        assert "- [jstor.org](https://www.jstor.org/stable/1) — The Coal Question" in block
        assert "news.example" not in block
        d = "# UC\n> **Hook.**\n\n### Segment 1 — The Cold Open\nbody.\n"
        out = append_research_sources(d, self.ARTS)
        assert out.endswith("### Sources\n- [jstor.org](https://www.jstor.org/stable/1) — The Coal Question\n"
                            "- [energyhistory.yale.edu](https://energyhistory.yale.edu/jevons) — Jevons\n")
        assert append_research_sources(out, self.ARTS) == out
        assert append_research_sources(d, []) == d

    def test_the_readers_see_it_and_the_script_does_not(self):
        from engine.blog import _extract_source_urls
        from engine.listener_noise import strip_reader_only_sections
        from engine.research_sources import append_research_sources
        from engine.show_notes import sources_footer
        d = append_research_sources("# UC\n> **Hook.**\n\n### Segment 1\nbody.\n\n### Sources of funding\nstory.\n", self.ARTS)
        assert _extract_source_urls(d) == ["https://www.jstor.org/stable/1", "https://energyhistory.yale.edu/jevons"]
        assert "[jstor.org](https://www.jstor.org/stable/1)" in sources_footer(d)
        spoken = strip_reader_only_sections(d)
        assert "### Sources\n" not in spoken and "jstor" not in spoken
        assert "### Sources of funding\nstory." in spoken  # a story heading is still spoken

    def test_run_show_appends_on_a_research_run(self):
        src = (ROOT / "run_show.py").read_text()
        i = src.index("append_research_sources(x_thread")
        assert "if _n_research:" in src[i - 600:i]
        assert src.index("x_thread = fix_phonetic_garbles(x_thread)") < i
        assert "research_sources_listed" in src


# ---------------------------------------------------------------------------
# A correction may amend the headline; the box renders above it
# ---------------------------------------------------------------------------

class TestCorrectionHeadline:
    def test_amend_headline_is_read_and_defaults_off(self, tmp_path):
        from engine import corrections as C
        C.corrections_path(tmp_path).write_text(
            "- episode: 139\n  date: 2026-10-11\n  text: Wrong premise.\n  where: both\n  amend_headline: true\n"
            "- episode: 140\n  date: 2026-10-12\n  text: A number.\n", encoding="utf-8")
        rows = {r["episode"]: r for r in C.load_corrections(tmp_path)}
        assert rows[139]["amend_headline"] is True and rows[140]["amend_headline"] is False

    def test_corrected_title_prefix(self):
        from engine.blog import corrected_title
        assert corrected_title("Toothfish licences cut orca survival") == "Corrected: Toothfish licences cut orca survival"
        assert corrected_title("Corrected: X") == "Corrected: X"
        assert corrected_title("Заголовок", is_ru=True) == "Исправлено: Заголовок"

    def test_the_box_renders_above_the_headline(self):
        tpl = (ROOT / "templates/blog_post.html.j2").read_text(encoding="utf-8")
        box = tpl.index('<aside class="nn-correction"')
        h1 = tpl.index('<h1><span class="nn-i18n-title">{{ episode_title }}</span></h1>')
        assert box < h1
        assert tpl.count('<aside class="nn-correction"') == 1

    def test_uc_139_is_the_operators_switch(self):
        """The mechanism exists; flipping UC Ep139's headline is the operator's
        call (docs/corrections.md). The entry is still filed either way."""
        from engine import corrections as C
        rows = C.corrections_for(ROOT / "digests/unintended_consequences", 139)
        assert rows and rows[0]["where"] == "both"
        assert "amend_headline" in rows[0]
