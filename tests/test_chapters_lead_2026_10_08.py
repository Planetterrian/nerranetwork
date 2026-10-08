"""Oct 8 2026 — the lead story gets its own chapter; titles are never fragments.

An outside review of the Oct 6-8 slates found the lead story missing from
the chapter list on every show, and clipped sentences as chapter titles on
Longevity, Unintended Consequences and Models & Agents. Both reproduced:

* The lead had a chapter on 2 of 21 Oct 8 episodes. Every script opens on
  the hook, the identity line, then the lead story, all inside
  "Introduction"; headline anchoring dropped the lead because it starts
  fewer than 60 words in, and marker-driven shows never split the opening.
* A segment with no matching digest headline was titled with its first
  spoken sentence, clipped with an ellipsis ("Yet these observations
  received little weight in the final…", UC Ep136).
* AI Chips, Peptides and Longevity write ``**Title:** Outlet``, which the
  headline extractor did not recognise, so their chapters had no headlines.

What binds:
* ``_lead_story_split`` titles the lead with the headline that matches the
  hook, or the hook cut cleanly; it splits only where the body opens on the
  hook's story, never on a guess, and never on a known_sections_only show.
* A spoken sentence is a chapter title only when it fits whole and does not
  continue the sentence before it; otherwise there is no chapter break.
* Unintended Consequences chapters its five segments from the digest.

Publishing is NOT blocked on a missing lead chapter: chapters are metadata.
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.chapters import (  # noqa: E402
    _clip_title,
    _first_sentence_as_title,
    parse_chapters,
)
from engine.grok_imagine import extract_story_headlines  # noqa: E402

MARKERS = [
    {"pattern": r"This is Test Show", "title": "Introduction", "where": "start"},
    {"pattern": r"That's the show", "title": "Closing", "where": "end"},
]

HOOK = "Tesla plans sixteen new Superchargers on a vacant Somerset site beside a closed motorhome dealer"
HEADLINES = [
    HOOK,
    "Tesla applies for sixteen Supercharger stalls in Somerset",
    "California Virtual Power Plant dispatches five gigawatt-hours",
]


def _script(lead_first: bool = True) -> str:
    lead = ("Tesla applied this week for sixteen Supercharger stalls on a vacant "
            "Somerset site that used to sell motorhomes. The council will decide "
            "next month, and the site sits beside the A303.")
    other = ("California's virtual power plant dispatched five gigawatt-hours "
             "across ten events this year, drawing on Powerwalls in homes across "
             "the state during evening peaks.")
    filler = " ".join(["More detail follows on the story here."] * 12)
    body = [lead, filler, other, filler] if lead_first else [other, filler, filler, filler, lead]
    return "\n\n".join([
        HOOK + ".",
        "This is Test Show, episode one.",
        *body,
        "That's the show for today.",
    ])


def _titles(chapters):
    return [c.title for c in chapters]


class TestTheLeadHasAChapter:
    def test_the_lead_story_follows_the_introduction(self):
        ch = parse_chapters(_script(), MARKERS, story_headlines=HEADLINES,
                            min_chapters=2)
        titles = _titles(ch)
        assert titles[0] == "Introduction"
        assert titles[1] == "Tesla applies for sixteen Supercharger stalls in Somerset"
        intro, lead = ch[0], ch[1]
        assert intro.word_end == lead.word_start
        assert lead.word_start - intro.word_start < 20, "the intro is the cold open only"

    def test_no_lead_split_when_the_body_opens_elsewhere(self):
        """The opening is not relabelled as the lead when another story is
        told there; headline anchoring may still find the lead later, where
        it is actually told."""
        script = _script(lead_first=False)
        ch = parse_chapters(script, MARKERS, story_headlines=HEADLINES,
                            min_chapters=2)
        lead = [c for c in ch
                if c.title == "Tesla applies for sixteen Supercharger stalls in Somerset"]
        for c in lead:
            assert script[c.char_start:].lstrip().startswith("Tesla applied"), (
                "a lead chapter must start where the lead story is told")

    def test_known_sections_only_shows_keep_their_section_set(self):
        ch = parse_chapters(_script(), MARKERS, story_headlines=HEADLINES,
                            min_chapters=2, known_sections_only=True)
        assert _titles(ch) == ["Introduction", "Closing"]

    def test_a_lead_with_no_headline_takes_the_hook_cut_cleanly(self):
        ch = parse_chapters(_script(), MARKERS, story_headlines=[HOOK],
                            min_chapters=2)
        title = _titles(ch)[1]
        assert HOOK.startswith(title) and not title.endswith("…")
        assert len(title) <= 60


class TestTitlesAreNeverFragments:
    @pytest.mark.parametrize("sentence", [
        "Yet these observations received little weight in the final plan.",
        "And the regulator agreed.",
        "They compared full fine-tuning with merging.",
        "Giorgos Mazonakis, fifty-four, died on September ninth after a clinic visit in Athens.",
    ])
    def test_a_continuation_or_a_clipped_sentence_is_not_a_title(self, sentence):
        assert _first_sentence_as_title(sentence) == ""

    def test_a_whole_short_sentence_is_a_title(self):
        assert _first_sentence_as_title("Regulators disclosed the Semi battery sizes. More.") == \
            "Regulators disclosed the Semi battery sizes"

    def test_a_clipped_headline_ends_on_a_clause_boundary(self):
        out = _clip_title("Tesla applies for sixteen Supercharger stalls on former motorhome site in Somerset")
        assert out == "Tesla applies for sixteen Supercharger stalls"

    def test_no_placeholder_and_no_ellipsis_titles_from_the_fallback(self):
        para = " ".join(["This paragraph runs on for a long while without a break."] * 8)
        script = "This is Test Show, episode one.\n\n" + "\n\n".join([para] * 12) + \
            "\n\nThat's the show for today."
        ch = parse_chapters(script, MARKERS, min_chapters=4)
        for t in _titles(ch):
            assert not t.startswith("Segment "), t
            assert not t.endswith("…"), t


class TestBoldColonHeadlines:
    DIGEST = "\n".join([
        "# AI Chips & Data Centres Daily",
        "> **Eighty billion dollars is Samsung's estimated quarter.**",
        "",
        "**What You Need to Know:** Samsung Electronics estimated third-quarter operating profit at 107.4 trillion won.",
        "**REAL-TIME TSLA price:** $380.68 ▲ $1.95 (0.5%)",
        "**Trade Type:** Weekly Hold",
        "### Silicon",
        "**HPE's next ProLiant generation is built on 6th Gen AMD EPYC:** AMD",
        "**TogetherAI downgraded in ClusterMAX over reliability:** Dylan Patel (SemiAnalysis)",
    ])

    def test_story_titles_are_extracted_and_labels_are_not(self):
        heads = extract_story_headlines(self.DIGEST)
        assert "HPE's next ProLiant generation is built on 6th Gen AMD EPYC" in heads
        assert "TogetherAI downgraded in ClusterMAX over reliability" in heads
        for label in ("What You Need to Know", "REAL-TIME TSLA price", "Trade Type"):
            assert not any(h.startswith(label) for h in heads), label


class TestCommittedEpisodesReplay:
    """Committed scripts and digests do not change; these replays pin the
    shapes the review reported, on the episodes it reported them on."""

    @staticmethod
    def _replay(show_dir: str, stem_glob: str, yaml_name: str):
        from engine.config import load_config
        md = Path(glob.glob(str(ROOT / "digests" / show_dir / f"{stem_glob}.md"))[0])
        cfg = load_config(ROOT / "shows" / yaml_name)
        digest = md.read_text(encoding="utf-8")
        script = md.with_name(md.stem + "_tts.txt").read_text(encoding="utf-8")
        return _titles(parse_chapters(
            script, cfg.chapters.section_markers, story_headlines=extract_story_headlines(digest),
            digest_text=digest,
            known_sections_only=getattr(cfg.chapters, "known_sections_only", False)))

    def test_tesla_628_lead_is_a_chapter(self):
        titles = self._replay("tesla_shorts_time", "*Ep628_20261008", "tesla.yaml")
        assert titles[1].startswith("Tesla applies for sixteen Supercharger stalls")

    def test_uc_136_chapters_are_its_segments(self):
        titles = self._replay("unintended_consequences", "*Ep136_20261008",
                              "unintended_consequences.yaml")
        for seg in ("The Good Intention", "The Implementation",
                    "The Unintended Consequences", "The Aftermath"):
            assert seg in titles
        assert not any(t.endswith("…") for t in titles)

    def test_longevity_ep003_has_no_fragment_titles(self):
        titles = self._replay("longevity", "*Ep003_20261007", "longevity.yaml")
        assert "Mechanism of the Week" in titles
        assert not any(t.endswith("…") for t in titles), titles
