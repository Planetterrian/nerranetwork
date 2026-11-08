"""Guards for the digest-lints pass of the six-month review (Nov 3 2026).

1. ``deep_dive_distinct`` — the flagship deep dive is a second STORY, never a
   second pass on a body item. The measure is the share of a body item's
   salient vocabulary the essay carries; the FIRING form (threshold 0.5)
   names the re-told item and rides the one-shot structural regeneration,
   the MEASURE form records ``deep_dive_contains_body_item`` and never fires
   (the skeptic's amendment: a week of readings before Tesla and
   Planetterrian pay for the rule against the 0.22 regeneration-share
   ceiling). Tesla Ep647 (item 9) and Planetterrian Ep227 (item 10) fire;
   AI Chips, MAG 7 and Omni View do not.
2. ``DEEP_DIVE_FETCHED_SECTIONS`` reads every essay (The Teardown, the
   Practitioner Deep Dive and the eight flagship essays) and measures
   ``deep_dive_source_read`` on all of them; only the sections whose prompt
   states the rule FIRE (``DEEP_DIVE_FETCHED_FIRING_SECTIONS``). A social
   URL is never the article a deep dive was built from.
3. ``hook_figure_sourced`` — on the narrative shows a digit-written hook
   figure must sit in a read research article or in the episode's own
   claims ledger. UC Ep161's "Over 500 native species vanished" fires with
   an empty research context and not when the figure is in the ledger.
4. The YAML opt-ins: the seven flagships carry the measure form and the
   fetched-source lint; UC and FPD carry the hook lint; env_intel.yaml and
   ai_chips.yaml are untouched; a show without the lints is byte-identical.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import digest_lint as DL  # noqa: E402
from engine.claims import restore_stashed_claims  # noqa: E402
from engine.config import load_config  # noqa: E402

DIGESTS = ROOT / "digests"

TEN_NAMES = (
    "Tesla First Principles", "Engineering Deep Dive", "Under the Hood",
    "Science Deep Dive", "Cosmic Deep Dive", "Understanding the Issue",
    "Planetterrian Spotlight", "Cosmic Spotlight", "The Thread",
    "Practitioner Deep Dive",
)
FLAGSHIPS = ("tesla", "spacex", "models_agents", "planetterrian",
             "fascinating_frontiers", "omni_view", "mag7")


def _digest(pattern: str) -> str:
    hits = sorted(p for p in DIGESTS.glob(pattern) if "_reader" not in p.name)
    if not hits:
        pytest.skip(f"committed digest {pattern} is not in this checkout")
    return hits[0].read_text(encoding="utf-8")


def _yaml(slug: str) -> dict:
    return yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))


# ------------------------------------------------------------ the registry --

class TestRegistry:
    def test_the_three_lints_are_registered_and_the_context_one_is_marked(self):
        for name in ("deep_dive_distinct", "deep_dive_distinct_measure", "hook_figure_sourced"):
            assert name in DL.LINTS, name
        assert "hook_figure_sourced" in DL.CONTEXT_LINTS
        assert "deep_dive_distinct" not in DL.CONTEXT_LINTS
        assert "deep_dive_distinct_measure" not in DL.CONTEXT_LINTS

    def test_the_tuples(self):
        assert DL.DEEP_DIVE_DISTINCT_SECTIONS == TEN_NAMES
        for name in TEN_NAMES + ("The Teardown",):
            assert name in DL.DEEP_DIVE_FETCHED_SECTIONS, name
        assert set(DL.DEEP_DIVE_FETCHED_FIRING_SECTIONS) <= set(DL.DEEP_DIVE_FETCHED_SECTIONS)
        assert DL.DEEP_DIVE_DISTINCT_MAX == 0.5

    def test_a_firing_section_is_one_whose_prompt_states_the_rule(self):
        """A section fires only when its digest prompt says the section is
        built from a read article and ends on its Source line; the flagship
        essays are measured until theirs do (the 0.22 regeneration-share
        ceiling)."""
        prompts = ROOT / "shows" / "prompts"
        stated = {
            "The Teardown": ("ai_chips_digest.txt", "end the Teardown on that article's Source line"),
            "Practitioner Deep Dive": ("env_intel_digest.txt", "End the section on that document's Source line"),
        }
        assert set(DL.DEEP_DIVE_FETCHED_FIRING_SECTIONS) == set(stated)
        for section, (fname, phrase) in stated.items():
            assert phrase in (prompts / fname).read_text(encoding="utf-8"), section

    def test_run_show_still_feeds_the_context_lints_and_lints_the_narrative_shows(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert src.count("context=_lint_ctx") == 3  # Nov 8 2026: articles + past hooks + briefing
        assert '_lint_ctx: dict = {"articles": articles}' in src
        # Lints run wherever a show lists them; only the manual deep-dive
        # special is excluded — a narrative show is linted like any other.
        assert "if _lint_names and not is_deep_dive:" in src


# --------------------------------------------------- deep_dive_distinct --

class TestDeepDiveDistinct:
    @pytest.mark.parametrize("pattern,section,item", [
        ("tesla_shorts_time/*_Ep647_*.md", "Tesla First Principles", 9),
        ("planetterrian/*_Ep227_*.md", "Science Deep Dive", 10),
        ("planetterrian/*_Ep229_*.md", "Science Deep Dive", 9),
    ])
    def test_the_firing_form_names_the_retold_item(self, pattern, section, item):
        f = DL.lint_deep_dive_distinct(_digest(pattern))
        assert f is not None and f.lint == "deep_dive_distinct"
        assert f.note.startswith(f"{section} re-tells item {item} (")
        assert "second story" in f.note and "fetched article" in f.note
        assert f.metrics["deep_dive_contains_body_item"] >= DL.DEEP_DIVE_DISTINCT_MAX

    @pytest.mark.parametrize("pattern", [
        "ai_chips/*_Ep042_*.md",
        "mag7/*_Ep042_*.md",
        "omni_view/*_Ep225_*.md",
    ])
    def test_the_cohort_essays_do_not_fire(self, pattern):
        f = DL.lint_deep_dive_distinct(_digest(pattern))
        if f is None:
            return  # no deep-dive section in this digest: nothing to judge
        assert f.note == ""
        assert f.metrics["deep_dive_contains_body_item"] < DL.DEEP_DIVE_DISTINCT_MAX

    def test_the_measure_form_records_and_never_fires(self):
        digest = _digest("tesla_shorts_time/*_Ep647_*.md")
        f = DL.lint_deep_dive_distinct_measure(digest)
        assert f is not None and f.lint == "deep_dive_distinct_measure"
        assert f.note == ""
        assert f.metrics["deep_dive_contains_body_item"] >= DL.DEEP_DIVE_DISTINCT_MAX
        fired, metrics = DL.run_digest_lints(digest, ["deep_dive_distinct_measure"])
        assert fired == [] and metrics["deep_dive_contains_body_item"] >= 0.5

    def test_the_best_item_is_the_one_the_reader_found(self):
        best = DL.deep_dive_item_containment(_digest("tesla_shorts_time/*_Ep647_*.md"))
        assert best is not None
        assert best.section == "Tesla First Principles" and best.item_number == 9
        assert best.item_title and len(best.item_title) <= 80

    def test_an_essay_never_scores_against_itself(self):
        digest = (
            "# Show\n\n### Top News\n\n"
            "**Nvidia posts record quarter: Reuters**\n"
            "Nvidia reported revenue of 57 billion dollars for the quarter, with data centre "
            "sales doubling on hyperscaler demand and gross margin holding at 73 percent.\n"
            "Source: https://www.reuters.com/a\n\n"
            "### The Thread\n\n"
            "**Memory bandwidth decides the next rack: SemiAnalysis**\n"
            "High bandwidth memory stacks bond twelve dies through silicon vias, and the "
            "packaging step limits how many accelerators leave the fab each month, so the "
            "memory vendors rather than the logic foundries set the shipping cadence this year.\n"
        )
        best = DL.deep_dive_item_containment(digest)
        assert best is not None and best.section == "The Thread"
        assert best.item_number == 1 and best.item_title.startswith("Nvidia posts record quarter")
        assert best.share < DL.DEEP_DIVE_DISTINCT_MAX

    def test_items_are_read_in_every_shape_the_shows_write(self):
        """Oct 21 2026's lesson, inherited: Models & Agents writes
        ``**Title:** body … Source:`` inline and Omni View writes each story
        as a ``### N) Title`` heading. The reader counts both (the heading
        section as ONE item, never its ``Read more`` block), and the note's
        title is the bold span with no stray ``*``."""
        inline = (
            "# Models & Agents\n\n### Model Updates\n\n"
            "**Zyphra retrofits frozen models with tree-indexed sparse attention:** Zyphra "
            "released a sparse attention method that uses a hierarchical tree index for "
            "subquadratic scaling and matches dense attention on retrieval benchmarks after "
            "distillation. Source: [marktechpost.com](https://www.marktechpost.com/a)\n\n"
            "### Under the Hood: Sparse attention\n\n"
            "Zyphra's tree-indexed sparse attention retrofits frozen models: the hierarchical "
            "tree index gives subquadratic scaling and matches dense attention on retrieval "
            "benchmarks after distillation.\n"
        )
        best = DL.deep_dive_item_containment(inline)
        assert best is not None and best.item_number == 1
        assert best.item_title == "Zyphra retrofits frozen models with tree-indexed sparse attention"
        assert best.share >= DL.DEEP_DIVE_DISTINCT_MAX
        heading = (
            "# Omni View\n\n## Today's lead story (1)\n"
            "### 1) Lebanon cuts electricity to public institutions amid deepening crisis\n"
            "**What happened (neutral):** The Energy Ministry began shutting off power to "
            "roughly 100 public bodies that owe unpaid bills after months of disputes over "
            "fuel costs and supply shortfalls.\n\n"
            "**Read more (sources):**\n- [Al Jazeera](https://www.aljazeera.com/a)\n\n"
            "### Understanding the Issue: Lebanon's grid\n\n"
            "Lebanon's Energy Ministry shutting off power to roughly 100 public bodies over "
            "unpaid bills follows months of disputes over fuel costs and supply shortfalls.\n"
        )
        best = DL.deep_dive_item_containment(heading)
        assert best is not None and best.item_number == 1
        assert best.item_title.startswith("Lebanon cuts electricity")
        assert best.share >= DL.DEEP_DIVE_DISTINCT_MAX
        assert "*" not in DL._item_title("1. **Tesla opens a Supercharger: 164 stalls**: Electrek")
        assert DL._item_title("1. **Tesla opens a Supercharger: 164 stalls**: Electrek") == (
            "Tesla opens a Supercharger: 164 stalls")

    def test_a_digest_without_an_essay_measures_nothing(self):
        digest = "# Show\n\n### Top News\n\n**A story: Outlet**\nOne sentence of body.\n"
        assert DL.deep_dive_item_containment(digest) is None
        assert DL.lint_deep_dive_distinct(digest) is None
        assert DL.lint_deep_dive_distinct_measure(digest) is None

    def test_a_show_without_the_lint_is_byte_identical(self):
        digest = _digest("tesla_shorts_time/*_Ep647_*.md")
        before = DL.run_digest_lints(digest, ["items_without_source", "hook_supported"])
        assert "deep_dive_contains_body_item" not in before[1]
        assert "deep_dive_source_read" not in before[1]
        cfg = load_config(ROOT / "shows" / "ai_chips.yaml")
        assert "deep_dive_distinct_measure" not in cfg.digest_lints
        assert "deep_dive_distinct" not in cfg.digest_lints


# ----------------------------------------------- deep_dive_fetched_source --

class TestFetchedSourceOnTheEssays:
    def _read(self, outlet: str, url: str) -> dict:
        return {"title": "t", "url": url, "source_name": outlet, "full_text": "x" * 3000}

    def test_the_feedback_x_link_is_not_a_cited_article(self):
        digest = _digest("tesla_shorts_time/*_Ep647_*.md")
        body = DL.section_body(digest, "Tesla First Principles")
        assert body and "x.com/teslashortstime" in body
        status, leaned_on = DL.deep_dive_source_status(
            body, [self._read("Electrek", "https://electrek.co/a")])
        assert status is None and leaned_on == []

    def test_an_essay_is_measured_never_fired(self):
        digest = _digest("tesla_shorts_time/*_Ep647_*.md")
        f = DL.lint_deep_dive_fetched_source(
            digest, {"articles": [self._read("Electrek", "https://electrek.co/a")]})
        assert f is not None and f.lint == "deep_dive_fetched_source"
        assert f.note == ""
        assert f.metrics["deep_dive_source_read"] is None
        assert f.metrics["deep_dive_read_candidates"] == 1

    def test_an_essay_from_an_unread_page_records_false_and_a_read_page_true(self):
        essay = ("Electrek walked the line with the engineers; the framing cell runs at "
                 "full automation and the paint shop is gone.\n")
        digest = "# Tesla\n\n### Top 12 News Items\n\n1. **A story**\nBody.\nSource: https://a.b/c\n\n### Tesla First Principles\n\n" + essay
        unread = {"title": "t", "url": "https://electrek.co/a", "source_name": "Electrek"}
        other = self._read("Teslarati", "https://www.teslarati.com/b")
        f = DL.lint_deep_dive_fetched_source(digest, {"articles": [unread, other]})
        assert f.note == "" and f.metrics["deep_dive_source_read"] is False
        ok = DL.lint_deep_dive_fetched_source(
            digest, {"articles": [self._read("Electrek", "https://electrek.co/a")]})
        assert ok.note == "" and ok.metrics["deep_dive_source_read"] is True
        # The same body under a FIRING section fires.
        teardown = digest.replace("### Tesla First Principles", "### The Teardown")
        bad = DL.lint_deep_dive_fetched_source(teardown, {"articles": [unread, other]})
        assert bad.note and "The Teardown" in bad.note and "Electrek" in bad.note


# -------------------------------------------------- hook_figure_sourced --

UC161 = "unintended_consequences/*_Ep161_*.md"


class TestHookFigureSourced:
    def setup_method(self):
        restore_stashed_claims(None)  # never read another test's ledger

    def _ledger(self) -> list:
        hits = sorted((DIGESTS / "unintended_consequences").glob("*_Ep161_*_claims.json"))
        if hits:
            return json.loads(hits[0].read_text(encoding="utf-8"))["claims"]
        return [{"claim": "More than 500 endemic haplochromine species were extirpated.",
                 "source_url": "https://www.tandfonline.com/x", "supporting_quote": "500+ endemic"},
                {"claim": "Nile perch were stocked into Lake Victoria in August 1954.",
                 "source_url": "https://academic.oup.com/x", "supporting_quote": "in August 1954"}]

    def test_uc_ep161_fires_with_an_empty_research_context(self):
        digest = _digest(UC161)
        assert DL.hook_figures(DL.hook_line(digest)) == ["500", "1954"]
        f = DL.lint_hook_figure_sourced(digest, {"articles": []})
        assert f is not None and f.lint == "hook_figure_sourced"
        assert f.note.startswith("the hook's 500, 1954 is in no fetched source")
        assert "named person" in f.note
        assert f.metrics["hook_figures_unsourced"] == 2

    def test_a_figure_in_the_ledger_does_not_fire(self):
        digest = _digest(UC161)
        f = DL.lint_hook_figure_sourced(digest, {"articles": [], "claims": self._ledger()})
        assert f.note == "" and f.metrics["hook_figures_unsourced"] == 0

    def test_a_fenced_ledger_still_in_the_digest_counts(self):
        digest = _digest(UC161) + "\n```claims\n" + json.dumps(self._ledger()) + "\n```\n"
        f = DL.lint_hook_figure_sourced(digest, {"articles": []})
        assert f.note == "" and f.metrics["hook_figures_unsourced"] == 0

    def test_a_read_research_article_carrying_the_figures_does_not_fire(self):
        digest = _digest(UC161)
        text = "x " * 700 + "Nile perch were stocked in 1954 and 500 species were lost."
        research = {"url": "https://doi.org/x", "source_kind": "research", "full_text": text}
        ok = DL.lint_hook_figure_sourced(digest, {"articles": [research], "claims": []})
        assert ok.note == "" and ok.metrics["hook_figures_unsourced"] == 0
        # A read NEWS article is not the narrative show's research; a teaser
        # is not a read page.
        news = dict(research, source_kind="news")
        assert DL.lint_hook_figure_sourced(digest, {"articles": [news], "claims": []}).note
        teaser = dict(research, full_text="In 1954, 500 species.")
        assert DL.lint_hook_figure_sourced(digest, {"articles": [teaser], "claims": []}).note

    def test_one_figure_sourced_and_one_not_names_only_the_missing_one(self):
        digest = _digest(UC161)
        ledger = [c for c in self._ledger() if "1954" in json.dumps(c)]
        f = DL.lint_hook_figure_sourced(digest, {"articles": [], "claims": ledger})
        assert f.note.startswith("the hook's 500 is in no fetched source")
        assert f.metrics["hook_figures_unsourced"] == 1

    def test_no_context_and_a_spelled_hook_measure_nothing(self):
        digest = _digest(UC161)
        assert DL.lint_hook_figure_sourced(digest, None) is None
        spelled = ("> **Power looms in Lancashire wove seven pieces a week against two from "
                   "hand looms.**\n\n### Segment 1\nBody.\n")
        f = DL.lint_hook_figure_sourced(spelled, {"articles": []})
        assert f.note == "" and f.metrics["hook_figures_unsourced"] == 0
        assert DL.lint_hook_figure_sourced("### Segment 1\nNo hook.\n", {"articles": []}) is None


# ---------------------------------------------------------- the YAML --

class TestOptIns:
    def test_the_seven_flagships_carry_the_measure_and_the_fetched_source_lint(self):
        for slug in FLAGSHIPS:
            lints = load_config(ROOT / "shows" / f"{slug}.yaml").digest_lints
            assert "deep_dive_distinct_measure" in lints, slug
            assert "deep_dive_fetched_source" in lints, slug
            # The firing form waits for a week of readings (the operator lists
            # it on Tesla and Planetterrian after the per-show threshold check).
            if "deep_dive_distinct" in lints:
                assert "deep_dive_distinct_measure" in lints, slug

    def test_the_narrative_shows_carry_the_hook_lint(self):
        for slug in ("unintended_consequences", "first_principles"):
            lints = load_config(ROOT / "shows" / f"{slug}.yaml").digest_lints
            assert lints == ["hook_figure_sourced"], slug

    def test_env_intel_and_ai_chips_are_untouched_by_this_pass(self):
        assert _yaml("env_intel")["digest_lints"] == [
            "x_only_lead", "items_without_source", "deep_dive_fetched_source"]
        ai = _yaml("ai_chips")["digest_lints"]
        assert "deep_dive_distinct_measure" not in ai and "hook_figure_sourced" not in ai

    def test_every_opted_in_essay_show_has_a_section_the_lints_know(self):
        """A show that lists the measure with no section in the tuple gets a
        lint that can never measure: the committed digests of each flagship
        carry one of the names. Read over the last SEVEN digests, never the
        latest alone — a guard that reads today's committed data must
        tolerate today (SpaceX Ep114 and MAG 7 Ep017 shipped without their
        essay; 2 of the 280 digests before this pass)."""
        dirs = {"tesla": "tesla_shorts_time", "spacex": "spacex", "models_agents": "models_agents",
                "planetterrian": "planetterrian", "fascinating_frontiers": "fascinating_frontiers",
                "omni_view": "omni_view", "mag7": "mag7"}
        for slug, d in dirs.items():
            hits = sorted(p for p in (DIGESTS / d).glob("*_Ep*_2026*.md") if "_reader" not in p.name)[-7:]
            if not hits:
                continue
            found = [p.name for p in hits
                     if DL.deep_dive_section(p.read_text(encoding="utf-8")) is not None]
            assert found, (slug, [p.name for p in hits])
