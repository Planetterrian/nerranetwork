"""Tests for engine/content_tracker.py — cross-episode content tracking."""

import datetime
import json
import tempfile
from pathlib import Path

import pytest

from engine.content_tracker import (
    ContentTracker,
    FF_SECTION_PATTERNS,
    PT_SECTION_PATTERNS,
    TST_SECTION_PATTERNS,
    OV_SECTION_PATTERNS,
    _extract_bold_headlines,
    _extract_quote_author,
)


# ---- Helpers ----

SAMPLE_FF_DIGEST = """
# Fascinating Frontiers
**Date:** 23 February 2026
🚀 **Fascinating Frontiers** - Space & Astronomy News

━━━━━━━━━━━━━━━━━━━━
### Top 15 Space & Astronomy Stories
1. **SpaceX Starship Completes First Orbital Flight: 23 Feb 2026 • SpaceNews**
   SpaceX achieved a historic milestone. This changes the cost equation.
   Source: https://example.com/1

2. **NASA Selects New Mars Rover Design: 23 Feb 2026 • NASA**
   The next Mars rover will carry new instruments. Life detection is the goal.
   Source: https://example.com/2

3. **James Webb Discovers New Exoplanet: 22 Feb 2026 • Space.com**
   JWST found a planet in the habitable zone. Could host liquid water.
   Source: https://example.com/3

━━━━━━━━━━━━━━━━━━━━
### Cosmic Spotlight
The SpaceX Starship achievement represents a paradigm shift. Full reusability
means launch costs could drop by 90%. What does this mean for Mars colonization?

━━━━━━━━━━━━━━━━━━━━
### Daily Inspiration
"The Earth is the cradle of humanity, but one cannot live in the cradle forever." – Konstantin Tsiolkovsky

Reach for the stars — they're closer than you think.
"""

SAMPLE_TST_DIGEST = """
# Tesla Shorts Time
**Date:** 23 February 2026
**TSLA:** $245.67 +$3.21 (+1.32%)

━━━━━━━━━━━━━━━━━━━━
### Top News
1. **Tesla Cybertruck Production Ramps to 2,500/Week: 23 Feb 2026, SpaceX News**
   Production milestone. This matters for delivery targets.
   Source: https://example.com/ct

2. **FSD v13 Achieves Zero Interventions on Cross-Country Trip: 22 Feb 2026, Teslarati**
   Breakthrough in autonomous driving. Regulatory implications.
   Source: https://example.com/fsd

━━━━━━━━━━━━━━━━━━━━
## Tesla X Takeover: What's Hot Right Now
🎙️ Tesla X Takeover

1. 🚨 **Megapack Sales Triple Year-Over-Year** - Energy storage is booming.
   Source: https://example.com/mp

━━━━━━━━━━━━━━━━━━━━
## Short Spot
📉 **Short Spot**: Bears point to margin pressure. But margins will recover.

━━━━━━━━━━━━━━━━━━━━
### Tesla First Principles
🧠 Tesla First Principles - Battery cost reduction analysis.

**The Fundamental Question:** Can Tesla reach $50/kWh?

━━━━━━━━━━━━━━━━━━━━
### Daily Challenge
💪 Today's challenge: Calculate your household energy savings.

━━━━━━━━━━━━━━━━━━━━
✨ **Inspiration Quote:** "The future is already here — it's just not evenly distributed." – William Gibson
"""


class TestExtractBoldHeadlines:
    def test_basic_extraction(self):
        text = """
1. **SpaceX Launches Starship Successfully** - Big deal.
2. **NASA Mars Rover Finds Water** - Amazing.
3. **Short Item** - Too short to extract.
"""
        headlines = _extract_bold_headlines(text)
        assert len(headlines) == 2
        assert "SpaceX Launches Starship Successfully" in headlines
        assert "NASA Mars Rover Finds Water" in headlines

    def test_max_items(self):
        text = "\n".join(f"{i}. **Headline Number {i} Is Long Enough**" for i in range(30))
        headlines = _extract_bold_headlines(text, max_items=5)
        assert len(headlines) == 5

    def test_deduplicates(self):
        text = "**Same Long Headline Here** and **Same Long Headline Here** again."
        headlines = _extract_bold_headlines(text)
        assert len(headlines) == 1

    def test_prose_section_falls_back_to_first_sentence(self):
        """Operator caught (MAB Ep031, May 7 2026) ``The Big Story``
        section emitting zero headlines because it's pure prose — no
        bold, no numbered list, no sub-headers. Cross-episode dedup
        then missed yesterday's mention and the LLM retold the same
        story (Perplexity Personal Computer) in two blocks of one
        episode. The prose-fallback captures the topic via the first
        substantive sentence."""
        text = (
            "Google DeepMind just unveiled Aletheia, an AI agent that "
            "moves from competition-style math problems to professional "
            "research-level discoveries. It iterates on proofs in plain "
            "language and verifies them against known facts."
        )
        headlines = _extract_bold_headlines(text)
        assert len(headlines) == 1
        assert "Google DeepMind" in headlines[0]
        assert "Aletheia" in headlines[0]

    def test_prose_fallback_strips_inline_markdown(self):
        """First-sentence fallback must clean up residual inline bold /
        italic / code so the dedup signature is plain text."""
        text = (
            "OpenAI announced **Codex** today, a new *coding* assistant "
            "that integrates with `vscode`. It runs locally."
        )
        headlines = _extract_bold_headlines(text)
        # Either the bold ``Codex`` is captured by the bold pass (if the
        # 10-char min still matches) OR the prose fallback fires. Either
        # way the topic gets a signature; the test pins SOMETHING is
        # extracted so cross-episode dedup never silently sees zero.
        assert len(headlines) >= 1
        # No inline markdown leaks through the prose path.
        for h in headlines:
            assert "*" not in h
            assert "`" not in h

    def test_prose_fallback_handles_cyrillic(self):
        """Russian shows (FP, PR) might also benefit from the fallback —
        confirm the regex anchors on Cyrillic capitals too."""
        text = (
            "Канадский фондовый рынок открылся ростом сегодня утром, "
            "несмотря на падение технологического сектора в США."
        )
        headlines = _extract_bold_headlines(text)
        assert len(headlines) == 1
        assert "Канадский" in headlines[0]


class TestExtractQuoteAuthor:
    def test_standard_format(self):
        text = '"The future is here" – William Gibson'
        assert _extract_quote_author(text) == "William Gibson"

    def test_em_dash(self):
        text = '"Be curious" — Richard Feynman'
        assert _extract_quote_author(text) == "Richard Feynman"

    def test_no_quote(self):
        assert _extract_quote_author("no quote here") is None


class TestContentTrackerBasics:
    def test_load_save_roundtrip(self, tmp_path):
        tracker = ContentTracker("test_show", tmp_path)
        tracker.load()
        tracker.data["episodes"].append({
            "date": datetime.date.today().isoformat(),
            "headlines": ["Test headline one", "Test headline two"],
            "quote_author": "Test Author",
            "sections": {"spotlight": "Some content"},
        })
        tracker.save()

        # Reload
        tracker2 = ContentTracker("test_show", tmp_path)
        tracker2.load()
        assert len(tracker2.data["episodes"]) == 1
        assert tracker2.data["episodes"][0]["headlines"] == ["Test headline one", "Test headline two"]

    def test_prune_old_episodes(self, tmp_path):
        tracker = ContentTracker("test_show", tmp_path, max_days=7)
        tracker.load()

        # Add old episode
        old_date = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
        tracker.data["episodes"].append({
            "date": old_date,
            "headlines": ["Old headline"],
            "quote_author": None,
            "sections": {},
        })

        # Add recent episode
        recent_date = datetime.date.today().isoformat()
        tracker.data["episodes"].append({
            "date": recent_date,
            "headlines": ["Recent headline"],
            "quote_author": None,
            "sections": {},
        })

        tracker.save()
        tracker2 = ContentTracker("test_show", tmp_path, max_days=7)
        tracker2.load()
        assert len(tracker2.data["episodes"]) == 1
        assert tracker2.data["episodes"][0]["date"] == recent_date

    def test_fresh_tracker_has_empty_episodes(self, tmp_path):
        tracker = ContentTracker("test_show", tmp_path)
        tracker.load()
        assert tracker.data["episodes"] == []

    def test_get_recent_headlines(self, tmp_path):
        tracker = ContentTracker("test_show", tmp_path)
        tracker.load()
        tracker.data["episodes"].append({
            "date": datetime.date.today().isoformat(),
            "headlines": ["Headline A", "Headline B"],
            "quote_author": None,
            "sections": {},
        })
        headlines = tracker.get_recent_headlines()
        assert "Headline A" in headlines
        assert "Headline B" in headlines


class TestRecordEpisode:
    def test_record_ff_digest(self, tmp_path):
        tracker = ContentTracker("fascinating_frontiers", tmp_path)
        tracker.load()
        tracker.record_episode(SAMPLE_FF_DIGEST, FF_SECTION_PATTERNS)

        assert len(tracker.data["episodes"]) == 1
        ep = tracker.data["episodes"][0]
        assert ep["date"] == datetime.date.today().isoformat()
        assert len(ep["headlines"]) >= 2
        assert "SpaceX Starship Completes First Orbital Flight" in ep["headlines"][0]
        assert ep["quote_author"] == "Konstantin Tsiolkovsky"

    def test_record_tst_digest(self, tmp_path):
        tracker = ContentTracker("tesla_shorts_time", tmp_path)
        tracker.load()
        tracker.record_episode(SAMPLE_TST_DIGEST, TST_SECTION_PATTERNS)

        ep = tracker.data["episodes"][0]
        assert len(ep["headlines"]) >= 2  # Top News + Takeover
        assert ep["quote_author"] == "William Gibson"

    def test_dedup_by_date(self, tmp_path):
        tracker = ContentTracker("test_show", tmp_path)
        tracker.load()
        tracker.record_episode(SAMPLE_FF_DIGEST, FF_SECTION_PATTERNS)
        tracker.record_episode(SAMPLE_FF_DIGEST, FF_SECTION_PATTERNS)
        assert len(tracker.data["episodes"]) == 1


class TestFilterRecentArticles:
    def test_filters_similar_titles(self, tmp_path):
        tracker = ContentTracker("test_show", tmp_path)
        tracker.load()
        tracker.data["episodes"].append({
            "date": datetime.date.today().isoformat(),
            "headlines": ["SpaceX Starship Completes First Orbital Flight"],
            "quote_author": None,
            "sections": {},
        })

        articles = [
            {"title": "SpaceX Starship Completes First Orbital Flight Today", "url": "a"},
            {"title": "NASA Discovers New Exoplanet in Habitable Zone", "url": "b"},
        ]
        filtered = tracker.filter_recent_articles(articles, similarity_threshold=0.65)
        assert len(filtered) == 1
        assert filtered[0]["url"] == "b"

    def test_keeps_unique_articles(self, tmp_path):
        tracker = ContentTracker("test_show", tmp_path)
        tracker.load()

        articles = [
            {"title": "SpaceX Launch Succeeds", "url": "a"},
            {"title": "NASA Mars Discovery", "url": "b"},
        ]
        filtered = tracker.filter_recent_articles(articles, similarity_threshold=0.65)
        assert len(filtered) == 2

    def _ep(self, days_ago, headlines, urls):
        d = (datetime.date.today() - datetime.timedelta(days=days_ago)).isoformat()
        return {"date": d, "headlines": headlines, "urls": urls,
                "quote_author": None, "sections": {}}

    def test_url_match_drops_refetched_article_up_to_7_days(self, tmp_path):
        """A publisher keeps a story in its feed for days; the SAME URL
        re-surfacing 5 days later must be dropped even with the 3-day title
        window, because URL-exact match has zero false-positive risk and uses
        a 7-day window (matching the validation check). FF Ep087 lingering
        almanac/news stories were missed here before."""
        tracker = ContentTracker("test_show", tmp_path)
        tracker.load()
        tracker.data["episodes"].append(
            self._ep(5, ["Pair-Instability Supernova Erases Massive Star"],
                     ["https://space.com/pair-instability-supernova-2026"])
        )
        articles = [
            # Same URL, rewritten title, 5 days old -> dropped by URL match.
            {"title": "A completely rephrased headline about the star",
             "url": "https://space.com/pair-instability-supernova-2026"},
            {"title": "Brand new distinct discovery", "url": "https://space.com/fresh"},
        ]
        filtered = tracker.filter_recent_articles(articles, days=3)
        urls = {a["url"] for a in filtered}
        assert "https://space.com/pair-instability-supernova-2026" not in urls
        assert "https://space.com/fresh" in urls

    def test_title_similarity_stays_on_narrow_window(self, tmp_path):
        """A title-similar (not URL-identical) story from 5 days ago is NOT
        dropped under a 3-day title window — the fuzzy match must stay narrow
        so legitimately-distinct follow-ups aren't over-filtered."""
        tracker = ContentTracker("test_show", tmp_path)
        tracker.load()
        tracker.data["episodes"].append(
            self._ep(5, ["Pair-Instability Supernova Erases Massive Star"],
                     ["https://space.com/old-url"])
        )
        articles = [{"title": "Pair-Instability Supernova Erases Massive Star",
                     "url": "https://space.com/today-different-url"}]
        filtered = tracker.filter_recent_articles(articles, days=3)
        assert len(filtered) == 1  # title match at 5d is beyond the 3d title window

    def test_url_match_beyond_window_kept(self, tmp_path):
        """A same-URL article older than the 7-day URL window is kept."""
        tracker = ContentTracker("test_show", tmp_path)
        tracker.load()
        tracker.data["episodes"].append(
            self._ep(9, ["Old Story"], ["https://space.com/nine-days-old"])
        )
        articles = [{"title": "Old Story resurfaces", "url": "https://space.com/nine-days-old"}]
        filtered = tracker.filter_recent_articles(articles, days=3)
        assert len(filtered) == 1


class TestGetSummaryForPrompt:
    def test_empty_tracker_returns_empty(self, tmp_path):
        tracker = ContentTracker("test_show", tmp_path)
        tracker.load()
        assert tracker.get_summary_for_prompt() == ""

    def test_summary_includes_headlines(self, tmp_path):
        tracker = ContentTracker("test_show", tmp_path)
        tracker.load()
        tracker.data["episodes"].append({
            "date": datetime.date.today().isoformat(),
            "headlines": ["Mars Rover Finds Water"],
            "quote_author": "Feynman",
            "sections": {"cosmic_spotlight": "Mars water analysis"},
        })
        summary = tracker.get_summary_for_prompt()
        assert "RECENTLY COVERED NEWS STORIES" in summary
        assert "Mars Rover Finds Water" in summary
        assert "RECENTLY USED QUOTE AUTHORS" in summary
        assert "Feynman" in summary


class TestCheckQuoteReuse:
    def test_detects_same_author(self, tmp_path):
        tracker = ContentTracker("test_show", tmp_path)
        tracker.load()
        tracker.data["episodes"].append({
            "date": datetime.date.today().isoformat(),
            "headlines": [],
            "quote_author": "Carl Sagan",
            "sections": {},
        })
        assert tracker.check_quote_reuse("We are star stuff – Carl Sagan") is True

    def test_allows_different_author(self, tmp_path):
        tracker = ContentTracker("test_show", tmp_path)
        tracker.load()
        tracker.data["episodes"].append({
            "date": datetime.date.today().isoformat(),
            "headlines": [],
            "quote_author": "Carl Sagan",
            "sections": {},
        })
        assert tracker.check_quote_reuse("The future is here – William Gibson") is False


class TestSectionPatterns:
    """Verify section patterns can extract content from sample digests."""

    def test_ff_headlines_pattern(self):
        import re
        m = re.search(FF_SECTION_PATTERNS["headlines"], SAMPLE_FF_DIGEST, re.DOTALL | re.IGNORECASE)
        assert m is not None

    def test_tst_headlines_pattern(self):
        import re
        m = re.search(TST_SECTION_PATTERNS["headlines"], SAMPLE_TST_DIGEST, re.DOTALL | re.IGNORECASE)
        assert m is not None

    def test_tst_takeover_pattern(self):
        import re
        m = re.search(TST_SECTION_PATTERNS["takeover_headlines"], SAMPLE_TST_DIGEST, re.DOTALL | re.IGNORECASE)
        assert m is not None


class TestSourceTitleJunkFilter:
    """June 2026: raw fetched X/Reddit titles ("Laughing Emojis 🤣🤣",
    "Video post", slur-bearing posts) were merged into recorded headlines
    via ``source_titles`` — polluting a public JSON and the daily
    "recently covered" prompt block. Junk must be filtered at record time."""

    def test_junk_source_titles_filtered(self, tmp_path):
        tracker = ContentTracker("tesla_shorts_time", tmp_path)
        tracker.load()
        tracker.record_episode(
            SAMPLE_TST_DIGEST, TST_SECTION_PATTERNS,
            source_titles=[
                "Laughing Emojis 🤣🤣",
                "Video post",
                "NY is full of liberal retards 🤣",
                "Same",
                "Tesla opens new Supercharger corridor across British Columbia",
            ],
        )
        headlines = tracker.data["episodes"][0]["headlines"]
        joined = " ".join(headlines)
        assert "Laughing Emojis" not in joined
        assert "Video post" not in joined
        assert "retards" not in joined
        assert "Same" not in headlines
        assert any("Supercharger corridor" in h for h in headlines)
