"""Guards from the Omni View desk Episode 1 review (2026-09-23).

Four desks published (Europe died on a grok-4.7 503 and a timed-out fetch —
those guards live in test_pinned_model_fallback_2026_09_23.py). All four ran
end to end on grok-4.7 and all four narrated their own workshop: 37 of 305
script sentences were about the briefing, "the item", this desk's rules or
the length target instead of the news. The shared podcast rules now describe
the shape (no quotable specimen), and the opt-in absence filter removes it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.absence_sentences import (
    is_absence_sentence,
    is_self_narration_sentence,
    strip_absence_sentences,
)

ROOT = Path(__file__).resolve().parent.parent

# Verbatim from the published Ep1 scripts.
WORKSHOP = [
    "That is the AP News headline on the item.",
    "Nothing in the AP News item, as provided for this brief, describes an agreement already signed.",
    "The item does not, in the reporting provided here, give a count of the dead, name the fifteen men, name the court.",
    "The facts the item does carry are the allegation, the denial, and the question of which account stands.",
    "It does not, in the text given for this brief, name a route, a delivery year, a speed.",
    "The brief does not treat the talks as a result already delivered.",
    "This desk does not add a third account.",
    "That is a reported toll from one named newsroom, not a figure this desk has independently verified.",
    "It does not, in the material this desk has, set out the details of the alleged offences.",
    "This brief does not add a response from Israel, because none is in the material filed for this item.",
    "A proposal of that kind is not the same as a poll having been scheduled, and this brief will not treat it as one.",
    "The digest has no further stories and no further reported facts.",
    "Stretching this to 1, would mean inventing details or padding items already covered, which this brief does not allow.",
    "That is all the digest states on it, so that is all I will say.",
]

# Must survive: the debut's AI disclosure, a fact that mentions the brief in
# passing, the shows' own closings, and ordinary news prose.
KEEP = [
    "Software picks and writes the items from named newsrooms, and each item names its source.",
    "At least 11 people were killed there, which is the count this brief carries from BBC News Africa.",
    "This brief is for listeners who want one region, every day, told straight.",
    "That wraps today's briefing.",
    "If you're new here, subscribe and this briefing finds you every day.",
    "The Justice Department's brief argues the map violates the Voting Rights Act.",
    "The budget adds a line item for rural clinics.",
    "Reporters at the White House briefing asked about the tariff.",
    "Casualties were reported on both sides of the border.",
]


@pytest.mark.parametrize("sentence", WORKSHOP)
def test_workshop_narration_is_removed(sentence):
    assert is_absence_sentence(sentence), sentence


@pytest.mark.parametrize("sentence", KEEP)
def test_news_and_debut_copy_survive(sentence):
    assert not is_self_narration_sentence(sentence), sentence


def test_a_written_domain_counts_before_the_tts_speaks_the_dot():
    # The filter runs on the script before "apnews.com" becomes "apnews dot com".
    assert is_absence_sentence("The source is the Australian Defence department, at defence.gov.au.")
    assert is_absence_sentence("The source named for the lead is AP News, at apnews dot com.")
    assert not is_absence_sentence("Visit nerranetwork.com for every show's page.")


def test_stripping_a_real_script_keeps_the_news():
    script = "\n".join([
        "Host: Xi Jinping is arriving in Washington for a state visit.",
        "Host: The source named for the lead is AP News, at apnews.com.",
        "Host: The visit is expected to include a planeside greeting from Trump.",
        "Host: The brief does not treat the talks as a result already delivered.",
    ])
    out, n = strip_absence_sentences(script)
    assert n == 2
    assert "planeside greeting" in out and "Xi Jinping" in out
    assert "apnews" not in out and "brief does not" not in out


class TestListenerRules:
    SNIPPET = ROOT / "shows" / "prompts" / "_shared" / "omni_listener_rules.txt"

    def test_every_omni_desk_prompt_and_top_world_carry_the_rules(self):
        from engine.generator import load_prompt

        class D(dict):
            def __missing__(self, k):
                return "{" + k + "}"

        slugs = ["europe", "asia_pacific", "africa_mideast", "latam", "north_america", "world"]
        for slug in slugs:
            text = load_prompt(str(ROOT / "shows" / "prompts" / f"omni_view_{slug}_podcast.txt"), D())
            assert "NEVER THE WORKSHOP" in text, slug
            assert "What You Need to Know" in text, slug
            # The per-sentence attribution rule is gone: it produced "The Times
            # reports… The Times says…" on ten consecutive lines.
            assert "Every claim by a government" not in text, slug

    def test_the_rules_describe_a_shape_and_quote_no_specimen(self):
        # De-seed by shape: no quoted example sentence the model can copy.
        body = self.SNIPPET.read_text(encoding="utf-8")
        assert "“" not in body
        quoted = [q for q in body.split('"')[1::2]]
        assert quoted == ["What You Need to Know"], quoted
