"""Guards for the Nov 24 2026 pass on the Grok review agent's proposals.

* Modern Investing's Market Pulse chapter keys on the spoken tape, and the
  story map is no witness against a section the digest labels above its
  first heading (``engine.chapters._pre_heading_labels``). A map spoken after
  the disclaimer never opens a chapter or the lead while a later line can
  (``engine.chapters._is_spoken_map``).
* Models & Agents' Under the Hood is a required section
  (``engine.validation.ma_validation_config``).
* AI Chips drops consumer desktop, laptop, console and hobby-board titles at
  fetch time (``shows/ai_chips.yaml``).

Synthetic fixtures only: committed episodes roll off.
"""
from __future__ import annotations

import re

import yaml

from engine.chapters import _is_spoken_map, _pre_heading_labels, parse_chapters
from engine.config import load_config
from engine.validation import check_item_counts, ma_validation_config


# --------------------------------------------------------------------------
# Modern Investing: Market Pulse
# --------------------------------------------------------------------------

_MIT_DIGEST = """# Modern Investing Techniques
> **Copper miners face a test as Chinese demand cools.**

**Market Pulse:** Friday closes showed the S&P 500 at 6,910 down 3.7 percent and the NASDAQ Composite at 22,618 down 5.3 percent while the TSX Composite fell 2.5 percent on mining and energy weakness.
---
### Strategy Spotlight
Copper miners with low cash costs survive demand slowdowns that bankrupt marginal producers. Screen for all-in sustaining cost below the spot price, net debt under one times earnings, and a dividend covered by free cash flow. Freeport and Teck both clear the screen this quarter.
Source: https://example.com/copper
---
### Practice Investment of the Day
Teck Resources, ticker TECK, is the simulated weekly hold on a valuation entry with an invalidation below the fifty-day average and a stop at eight percent.
---
### Yesterday's Trade Review
The prior simulated weekly hold in Costco closed after five sessions at a small loss against the NASDAQ benchmark window, and the lesson is that membership growth alone did not hold the multiple.
---
### Portfolio Performance
The record since the rules-based era began covers fifty trades with a modest negative alpha against the NASDAQ.
"""

_MIT_SCRIPT = """Copper miners face a test as Chinese demand cools.

This is Modern Investing Techniques, episode two hundred forty.

Quick reminder, everything we discuss here is for education and entertainment. The Practice Investment of the Day uses simulated trades with no real money. I'm not a licensed financial advisor and this isn't financial advice.

After the tape, a copper cost screen, a simulated Teck weekly hold, then the Costco review and the record, with market pulse and trade review in their usual places.

Friday's close left the NASDAQ Composite at twenty-two thousand six hundred eighteen, down five point three percent.

The S&P 500 finished at six thousand nine hundred ten, down three point seven percent, and the T S X Composite fell two point five percent on mining and energy weakness.

Copper miners with low cash costs survive demand slowdowns that bankrupt marginal producers, and that is today's strategy spotlight.

Screen for all-in sustaining cost below the spot price, net debt under one times earnings, and a dividend covered by free cash flow.

Freeport and Teck both clear that copper screen this quarter, which is the point of running it before the cycle turns.

Teck Resources, ticker T E C K, is today's simulated weekly hold on a valuation entry, with an invalidation below the fifty-day average and a stop at eight percent.

The prior simulated weekly hold in Costco closed after five sessions at a small loss against the NASDAQ benchmark window, and the lesson is that membership growth alone did not hold the multiple.

Portfolio performance: the record since the rules-based era began covers fifty trades with a modest negative alpha against the NASDAQ.

That's Modern Investing Techniques for today. Thanks for listening.
"""


def _mit_chapters():
    cfg = load_config("shows/modern_investing.yaml")
    return parse_chapters(
        _MIT_SCRIPT, cfg.chapters.section_markers,
        show_name="modern_investing", digest_text=_MIT_DIGEST,
        story_headlines=[])


class TestMarketPulseChapter:
    def test_the_marker_matches_the_spoken_tape(self):
        cfg = yaml.safe_load(open("shows/modern_investing.yaml"))
        pattern = next(m["pattern"] for m in cfg["chapters"]["section_markers"]
                       if m["title"] == "Market Pulse")
        spoken = [
            "Friday's close left the NASDAQ Composite at twenty-two thousand.",
            "Friday's close in New York left the S&P 500 at six thousand.",
            "The S&P five hundred closed at seven thousand three hundred.",
            "The S and P 500 closed at seven thousand five hundred.",
            "United States benchmarks finished mixed on Friday.",
            "U S large-cap indexes sold off hard, with the S&P 500 closing at seven thousand.",
            "The NASDAQ Composite finished at twenty-two thousand.",
        ]
        for line in spoken:
            assert re.search(pattern, line, re.IGNORECASE), line
        assert not re.search(pattern, "Teck is today's simulated weekly hold.", re.IGNORECASE)

    def test_the_digest_label_is_not_overruled_by_the_story_map(self):
        assert "market pulse" in _pre_heading_labels(_MIT_DIGEST)
        assert _pre_heading_labels("### Lead\n**Market Pulse:** x") == set()

    def test_market_pulse_opens_on_the_tape_not_the_map(self):
        chapters = _mit_chapters()
        titles = [c.title for c in chapters]
        assert "Market Pulse" in titles
        pulse = chapters[titles.index("Market Pulse")]
        start = _MIT_SCRIPT.split()[pulse.word_start:pulse.word_start + 3]
        assert start == ["Friday's", "close", "left"]

    def test_the_trade_review_never_opens_on_the_tape(self):
        chapters = _mit_chapters()
        titles = [c.title for c in chapters]
        if "Trade Review & Lessons" in titles:
            assert titles.index("Trade Review & Lessons") > titles.index("Market Pulse")


class TestSpokenMap:
    def test_a_list_after_the_disclaimer_is_a_map(self):
        assert _is_spoken_map(
            "A contracted-cash-flow dividend screen, a simulated rare-earths "
            "weekly hold, then tools and the record.")

    def test_a_dialogue_line_is_never_a_map(self):
        # DP Pod Ep083: the lead itself, map-shaped by its "Then" and commas.
        assert not _is_spoken_map(
            "PATRICK: Then you're going to like this. The James Webb Space "
            "Telescope, or J W S T, just doubled the record.")

    def test_two_sentences_are_never_a_map(self):
        assert not _is_spoken_map("Then the fleet, the race. The boat sails, later.")

    def test_a_map_still_names_a_section_nothing_else_names(self):
        # Offshore North Ep013: its map sits directly above The Canadian Boat
        # and is the only line naming it; the chapter is kept there.
        markers = [
            {"pattern": "This is Offshore North", "title": "Introduction", "where": "start"},
            {"pattern": "canadian boat", "title": "The Canadian Boat"},
            {"pattern": "out in the fleet|the fleet this week", "title": "The Fleet"},
            {"pattern": "that's offshore north", "title": "Sign-Off", "where": "end"},
        ]
        script = (
            "No Canadian has ever finished that race.\n\n"
            "This is Offshore North, episode thirteen.\n\n"
            "Every four years a handful of sailors set out alone around the world.\n\n"
            "On the Canadian boat first, then out in the fleet with the results, then Plain Sailing.\n\n"
            + "EMIRA IV sat in Gosport all week while the team finished the keel work. " * 12
            + "\n\nThe fleet this week was led by the Route du Rhum finishers. " * 12
            + "\n\nThat's Offshore North for this week.\n"
        )
        titles = [c.title for c in parse_chapters(script, markers, show_name="t")]
        assert "The Canadian Boat" in titles


# --------------------------------------------------------------------------
# Models & Agents: Under the Hood is required
# --------------------------------------------------------------------------

class TestUnderTheHoodRequired:
    _BASE = ("### Top Story\n" + "A model launched today with a benchmark score. " * 10
             + "\n━━━━\n### Model Updates\n**A: Outlet**\nText.\n")

    def test_a_missing_section_is_a_structural_defect(self):
        issues = check_item_counts(self._BASE, ma_validation_config().sections)
        assert "Section 'Under the Hood' is missing from digest" in issues

    def test_a_present_section_passes(self):
        digest = self._BASE + "━━━━\n### Under the Hood: KV caches\n" + "How it works. " * 30
        issues = check_item_counts(digest, ma_validation_config().sections)
        assert not any("Under the Hood" in i for i in issues)


# --------------------------------------------------------------------------
# AI Chips: consumer silicon is excluded at fetch time
# --------------------------------------------------------------------------

class TestAiChipsConsumerExcludes:
    def _excluded(self, title: str) -> bool:
        pats = yaml.safe_load(open("shows/ai_chips.yaml"))["exclude_title_patterns"]
        return any(re.search(p, title, re.IGNORECASE) for p in pats)

    def test_consumer_titles_are_dropped(self):
        for t in (
            "Intel Razor Lake-S Reportedly Due in 2028 on LGA-1954",
            "Leak: Intel Core Ultra 9 4995HX Leads Nova Lake Laptop Lineup",
            "A leaker puts PlayStation 6 memory and flash above $680",
            "BrainChip launches an AKD1500 Raspberry Pi 5 kit",
            "ASUS Showcases ProArt GR1X at Adobe MAX 2026",
        ):
            assert self._excluded(t), t

    def test_on_beat_titles_pass(self):
        for t in (
            "Nintendo ROM chip supplier Macronix quits to focus on chips for AI data centers",
            "Intel 18A yields improve as Panther Lake and Nova Lake ramp at the Arizona fab",
            "Anduril teams with Qualcomm on a military laptop using TSMC Arizona",
            "Nvidia tells data center partners to cut China exposure, limits RTX chip sales",
            "TSMC CoWoS capacity doubles for HBM4 packaging",
        ):
            assert not self._excluded(t), t
