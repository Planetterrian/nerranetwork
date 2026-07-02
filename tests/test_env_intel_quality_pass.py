"""Drift guards for the June 10 2026 Environmental Intelligence quality
pass (docs/reviews/env_intel_review_2026_06_10.md) — the same review
process as the Tesla flagship pass and the four-show pass
(docs/four_show_review_2026_06_10.md), applied to a show that was
missed in those rounds.

Pins:
* chapter `where` positional anchors (Introduction=start, Tomorrow
  Teaser/Closing=end) so the Tesla chapter-bug class can't recur —
  Ep040 had shipped a "Closing" chapter at word-position 5 of 7 with
  real content after it;
* the Closing chapter pattern matches BOTH closing-pool variants (the
  "That covers today's environmental intelligence" variant previously
  matched no pattern, the MAB orphan-closing bug);
* the Industry & Practice pattern no longer matches the closing's
  "useful to your practice";
* cadence-accurate spoken copy — env_intel runs odd weekdays, so the
  intro/framing/closing must not claim "daily" or "back tomorrow";
* one unified prompt length target aligned with the tuned YAML floor
  (the prompt had demanded 1500-2200 words on a show whose episodes
  ship ~750 words, contradicting both the 900-word YAML target and the
  prompt's own "let the episode be shorter" instruction).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.intros import _SHOW_PERSONALITIES  # noqa: E402
from engine.chapters import parse_chapters  # noqa: E402

_YAML = _ROOT / "shows/env_intel.yaml"
_PODCAST_PROMPT = _ROOT / "shows/prompts/env_intel_podcast.txt"
_DIGEST_PROMPT = _ROOT / "shows/prompts/env_intel_digest.txt"


def _marker_list():
    cfg = yaml.safe_load(_YAML.read_text(encoding="utf-8"))
    return cfg["chapters"]["section_markers"]


def _markers():
    return {m["title"]: m for m in _marker_list()}


class _Marker:
    """Lightweight stand-in matching what parse_chapters reads off a
    config object (``.pattern`` / ``.title`` / ``.where``)."""

    def __init__(self, d):
        self.pattern = d["pattern"]
        self.title = d["title"]
        self.where = d.get("where", "")


class TestChapterPositionalAnchors:
    def test_introduction_anchored_to_start(self):
        assert _markers()["Introduction"].get("where") == "start"

    def test_closing_unanchored_and_teaser_anchored_to_end(self):
        """July 2 2026: Closing deliberately carries NO `where: end` anymore.
        The parser's end window (last 15%) EXCLUDED the closing line itself
        on short episodes (Ep049 word 539 vs window 555; Ep050 730 vs 738;
        Ep051 676 vs 685 — EI's sign-off + promo + disclosure block runs
        ~120-140 words on a ~650-870-word episode), which is why those
        episodes shipped with no Closing chapter. The brand-anchored
        pattern ("That's/That covers today's Environmental Intelligence")
        provides the positional safety instead."""
        by = _markers()
        assert not by["Closing"].get("where"), (
            "Closing must NOT be `where: end` — the last-15% window "
            "excludes EI's early-starting closing block on short episodes "
            "(the Ep049/050/051 orphan-Closing bug)"
        )
        assert by["Tomorrow Teaser"].get("where") == "end"

    def test_closing_pattern_matches_every_closing_variant(self):
        pattern = _markers()["Closing"]["pattern"]
        regex = re.compile(pattern, re.IGNORECASE)
        for variant in _SHOW_PERSONALITIES["env_intel"]["closings"]:
            assert regex.search(variant), (
                "env_intel closing variant ships without a Closing "
                f"chapter: {variant[:80]!r}"
            )

    def test_industry_pattern_excludes_closing_your_practice(self):
        """Bare 'practice' matched the closing's 'useful to your
        practice' and stole the final segment's title."""
        regex = re.compile(_markers()["Industry & Practice"]["pattern"], re.IGNORECASE)
        assert not regex.search("this briefing is useful to your practice")
        # but a real industry mention still matches
        assert regex.search("in practice this changes site closure criteria")

    def test_introduction_pattern_matches_every_greeting_variant(self):
        """June 17 2026. The original 'This is Environmental Intelligence'
        pattern missed the 'Welcome to' greeting (engine/intros.py rotates
        three greetings); Ep037/038/042/046 — the four 'Welcome to'
        episodes of the last ten — each shipped with NO Introduction
        chapter. The pattern must match every greeting × show-name opener."""
        regex = re.compile(_markers()["Introduction"]["pattern"], re.IGNORECASE)
        personality = _SHOW_PERSONALITIES["env_intel"]
        show_name = personality["show_name"]
        for greeting in personality["greetings"]:
            opener = f"{greeting} {show_name}, episode forty-six, for June 17."
            assert regex.search(opener), (
                "env_intel intro greeting ships without an Introduction "
                f"chapter: {opener!r}"
            )

    def test_welcome_to_opener_yields_introduction_chapter(self):
        """End-to-end: a 'Welcome to' episode (the Ep046 shape) must
        produce an Introduction chapter, not start on a content chapter."""
        markers = [_Marker(m) for m in _marker_list()]
        body = "Host: " + ("Regulatory update for the day. " * 80) + "\n\n"
        script = (
            "Welcome to Environmental Intelligence, episode forty-six, for "
            "June seventeenth, twenty twenty-six. Your briefing on what "
            "matters for Canadian professionals.\n\n"
            + body
            + "That's Environmental Intelligence for today. We'll be back "
            "with the next briefing.\n"
        )
        titles = [c.title for c in parse_chapters(script, markers, show_name="ei")]
        assert titles and titles[0] == "Introduction", (
            f"'Welcome to' opener must yield a leading Introduction chapter; got {titles}"
        )


class TestClosingWinsOverTeaserWhenMerged:
    """June 11 2026 follow-up. Ep044 (2026-06-11) shipped with NO Closing
    chapter: the LLM merged the Tomorrow Teaser sentence and the closing
    block into ONE paragraph, and the parser's first-marker-wins rule
    titled that line "Tomorrow Teaser". Listing Closing before Tomorrow
    Teaser makes Closing win on a shared line so the standard final
    chapter is preserved; separate lines still produce both chapters."""

    def test_closing_marker_precedes_tomorrow_teaser(self):
        titles = [m["title"] for m in _marker_list()]
        assert titles.index("Closing") < titles.index("Tomorrow Teaser"), (
            "Closing must be listed before Tomorrow Teaser so a merged "
            "teaser+closing paragraph still yields a Closing chapter"
        )

    def test_merged_teaser_and_closing_yields_closing_chapter(self):
        markers = [_Marker(m) for m in _marker_list()]
        # One paragraph that fuses the teaser sentence and the closing,
        # exactly the Ep044 shape. Padded with body so the closing lands
        # in the `where: end` window.
        body = "Host: " + ("Regulatory update for the day. " * 80) + "\n\n"
        merged = (
            "This is Environmental Intelligence, episode forty-four.\n\n"
            + body
            + "Tomorrow, watch for any late Canada Gazette postings. "
            "That's Environmental Intelligence for today. Share it with a "
            "colleague. We'll be back with the next briefing.\n"
        )
        titles = [c.title for c in parse_chapters(merged, markers, show_name="ei")]
        assert "Closing" in titles, (
            "merged teaser+closing paragraph must still produce a Closing "
            f"chapter; got {titles}"
        )
        assert titles[-1] == "Closing"

    def test_separate_teaser_and_closing_yield_both_chapters(self):
        markers = [_Marker(m) for m in _marker_list()]
        body = "Host: " + ("Regulatory update for the day. " * 80) + "\n\n"
        separate = (
            "This is Environmental Intelligence, episode forty-four.\n\n"
            + body
            + "Before we wrap, tomorrow watch for late Canada Gazette postings.\n\n"
            "That's Environmental Intelligence for today. We'll be back with "
            "the next briefing.\n"
        )
        titles = [c.title for c in parse_chapters(separate, markers, show_name="ei")]
        assert "Tomorrow Teaser" in titles and "Closing" in titles, (
            f"separate teaser/closing lines must yield both chapters; got {titles}"
        )


class TestThinDayHookNotAbsence:
    """June 11 2026 follow-up. Ep044's digest hook was 'No major Canadian
    regulatory announcements or enforcement actions appeared in today's
    feed' — which became the blog <title>/<h1>, the chapter title, and the
    spoken opener. The digest prompt now forbids an absence-of-news hook
    and steers thin days to a forward-looking hook."""

    def test_digest_prompt_forbids_absence_hook(self):
        prompt = _DIGEST_PROMPT.read_text(encoding="utf-8").lower()
        assert "never write a hook that states the absence" in prompt

    def test_digest_prompt_steers_thin_day_hook_forward(self):
        prompt = _DIGEST_PROMPT.read_text(encoding="utf-8").lower()
        # the low-content strategy block must also reinforce it
        assert "never a sentence announcing that nothing happened" in prompt


class TestCadenceAccurateCopy:
    """env_intel publishes odd weekdays — spoken copy must not claim a
    daily cadence or promise a 'tomorrow' episode."""

    def test_no_daily_or_tomorrow_in_intro_or_closing(self):
        p = _SHOW_PERSONALITIES["env_intel"]
        copy = " ".join(p["openers"] + p["framings"] + list(p["closings"])).lower()
        assert "daily" not in copy
        assert "tomorrow" not in copy


class TestDeepDiveOpenerNotTic:
    """June 15 2026 pass. The Practitioner Deep Dive opened with the
    verbatim "You arrive at a…" scenario in 9/10 recent episodes (the
    digest prompt seeded that exact example at line 173) and the podcast
    prompt seeded the transition "here's something I wish someone had told
    me early in my career" (verbatim in 5/10). Both are the boilerplate-tic
    class the Omni View / MAB / Tesla passes fixed by removing the seeded
    literal phrase and requiring rotation. The seed example string itself
    is the root cause — the podcast faithfully echoes the digest's deep
    dive, so the fix lives primarily in the digest prompt."""

    def test_digest_prompt_does_not_seed_you_arrive_opener(self):
        # The literal seed example "You arrive at a former gas station
        # site" must be gone (it produced "You arrive at a…" every episode).
        prompt = _DIGEST_PROMPT.read_text(encoding="utf-8")
        assert "You arrive at a former gas station" not in prompt

    def test_digest_prompt_requires_varied_deep_dive_opener(self):
        prompt = _DIGEST_PROMPT.read_text(encoding="utf-8").lower()
        assert "you arrive at a" in prompt  # named explicitly as the tic to avoid
        assert "rotate the entry point" in prompt

    def test_podcast_prompt_bans_repetitive_deep_dive_lead_in(self):
        prompt = _PODCAST_PROMPT.read_text(encoding="utf-8").lower()
        # the old verbatim transition must no longer be the sole seeded option
        assert "vary the lead-in" in prompt
        assert "avoid starting every deep dive" in prompt


class TestChapterClosingOrderingJuly2:
    """July 2 2026 pass (orphan-Closing variant 3, the EI June-11 /
    SpaceX June-18 / FF June-24 ordering class). Ep049/050/051 shipped
    with NO Closing chapter: unconsumed BODY markers ate the closing
    paragraph — `science|technical` matched the network promo "…covering
    tech, science, markets" (Ep049/051) and bare `deep dive` matched the
    Tesla cross-promo "daily deep dive into everything Tesla" (Ep050).
    Fixes pinned here: Closing + Tomorrow Teaser listed BEFORE all body
    markers; the Science & Technical pattern can't match the promos or
    "geotechnical"; the Practitioner Deep Dive pattern dropped bare
    `deep dive`/`under the hood` and anchors on the section's signature
    "most common mistake" beat; and the five real committed episodes
    re-parse to a shape that ends on Closing."""

    _BODY_TITLES = (
        "Executive Summary", "Lead Story", "Regulatory & Policy Watch",
        "Science & Technical", "Industry & Practice",
        "Practitioner Deep Dive", "Action Items", "Week Ahead",
    )

    def test_closing_and_teaser_listed_before_all_body_markers(self):
        titles = [m["title"] for m in _marker_list()]
        first_body = min(titles.index(t) for t in self._BODY_TITLES)
        assert titles.index("Closing") < first_body, (
            "Closing must precede every body marker so an unconsumed body "
            "marker can't steal the closing paragraph (Ep049/050/051)"
        )
        assert titles.index("Tomorrow Teaser") < first_body

    def test_science_pattern_cannot_match_closing_promos(self):
        rx = re.compile(_markers()["Science & Technical"]["pattern"], re.IGNORECASE)
        promos = [
            "a family of daily podcasts covering tech, science, markets, and more.",
            "a family of daily podcasts on tech, science, and markets, each one a short briefing.",
            "give Planetterrian Daily a listen: daily breakthroughs in science, health, and longevity.",
            "Fascinating Frontiers, the most fascinating news from space and science. Find every show at nerranetwork dot com.",
            "Your briefing on environmental regulatory, science, and compliance developments.",
        ]
        for promo in promos:
            assert not rx.search(promo), f"promo must not open a Science & Technical chapter: {promo!r}"

    def test_science_pattern_still_matches_real_section_not_geotechnical(self):
        rx = re.compile(_markers()["Science & Technical"]["pattern"], re.IGNORECASE)
        # The real spoken section label (Ep048).
        assert rx.search("In Science and Technical, a long-term grassland experiment examined soils.")
        # "geotechnical" mid-story created false chapters (Ep047/Ep050).
        assert not rx.search("citing improved geotechnical stability and reduced disturbance")

    def test_deep_dive_pattern_cannot_match_tesla_cross_promo(self):
        rx = re.compile(_markers()["Practitioner Deep Dive"]["pattern"], re.IGNORECASE)
        assert not rx.search(
            "here's your next listen — Tesla Shorts Time, your daily deep dive into everything Tesla"
        )
        assert not rx.search("let's go under the hood")
        # Signature deep-dive beat, present in 7/7 recent episodes.
        assert rx.search("The mistake I see most often is treating glacial lake risks separately.")
        assert rx.search("the most common mistake is skipping the vapour pathway check")

    def test_closing_pattern_tolerates_curly_apostrophe(self):
        rx = re.compile(_markers()["Closing"]["pattern"], re.IGNORECASE)
        assert rx.search("That’s Environmental Intelligence for today.")
        assert rx.search("That's Environmental Intelligence for today.")
        assert rx.search("That covers today's environmental intelligence.")

    def test_real_committed_episodes_reparse_ends_on_closing(self):
        """Re-parse the actual shipped scripts (the FF June-24
        TestChapterClosingOrdering method): every episode must start on
        Introduction and end on Closing — Ep049/050/051 previously ended
        on a bogus Science & Technical / Practitioner Deep Dive chapter
        opened by the closing promos."""
        markers = [_Marker(m) for m in _marker_list()]
        scripts = sorted((_ROOT / "digests/env_intel").glob("Env_Intel_Ep0*_tts.txt"))
        scripts = [p for p in scripts if any(
            f"Ep{ep}_" in p.name for ep in ("047", "048", "049", "050", "051"))]
        if not scripts:
            pytest.skip("EI Ep047-051 scripts not present")
        for p in scripts:
            titles = [c.title for c in parse_chapters(
                p.read_text(encoding="utf-8"), markers, show_name="env_intel")]
            assert titles, f"{p.name}: no chapters parsed"
            assert titles[0] == "Introduction", f"{p.name}: {titles}"
            assert titles[-1] == "Closing", (
                f"{p.name} must end on a Closing chapter; got {titles}"
            )


class TestUnifiedLengthTarget:
    def test_yaml_target_and_prompt_target_aligned(self):
        cfg = yaml.safe_load(_YAML.read_text(encoding="utf-8"))
        assert cfg["llm"]["min_podcast_words"] == 900
        prompt = _PODCAST_PROMPT.read_text(encoding="utf-8")
        assert "900–1300 words" in prompt

    def test_contradictory_length_targets_removed(self):
        prompt = _PODCAST_PROMPT.read_text(encoding="utf-8")
        assert "1500–2200 words" not in prompt
        assert "at least 1500 words" not in prompt
        assert "6–9 minute" not in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
