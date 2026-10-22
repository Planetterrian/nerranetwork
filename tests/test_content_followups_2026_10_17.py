"""Guards for the content follow-ups left by the Oct 17 2026 slate review
(docs/reviews/slate_review_2026_10_17.md, "Found and left for a later pass").

1. Prediction Markets' Board collapsed to one market: story-recurrence memory
   marked 9 of 10 board markets "already covered — pick a different story"
   (10-17; 8 of 8 on 10-16). Board articles are now exempt from recurrence
   and same-story clustering, the board instruction asks for two venues when
   two supplied markets, and ``board_venue_mix`` records and enforces it.
2. Vancouver Ep025 aired a sportsbook moneyline: betting-page titles are
   dropped and betting-line sentences stripped where the show opts in.
3. Hooks that claim more than their items carry: ``hook_supported`` now
   checks figures and the figure-to-consequence join (Modern Investing Ep203
   tied a US PPI print to Bank of Canada hike odds) and runs on MIT and the
   cohort, each prompt stating the rule.
4. AI Chips Ep026's Teardown was written from an EE Times page the runner
   never read: ``deep_dive_fetched_source``.
5. Models & Agents Ep206 aired a Startup Fortune sidebar teaser as reporting:
   the full-text extractor drops suggested-article cards and link rails.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import digest_lint as DL  # noqa: E402
from engine import prediction_board as PB  # noqa: E402
from engine.config import load_config  # noqa: E402
from engine.story_clusters import annotate_articles as cluster_annotate  # noqa: E402
from engine.story_clusters import cluster_articles  # noqa: E402
from engine.story_recurrence import RecurrenceIndex, annotate_articles  # noqa: E402
from engine.utils import (  # noqa: E402
    BETTING_LINE_TITLE_PATTERNS,
    exclude_title_patterns_for,
    is_betting_line_sentence,
    strip_betting_lines,
    strip_betting_lines_from_articles,
)

DIGESTS = ROOT / "digests"


def _one(pattern: str) -> Path:
    hits = sorted(DIGESTS.glob(pattern))
    assert hits, pattern
    return hits[0]


def _text(pattern: str) -> str:
    return _one(pattern).read_text(encoding="utf-8")


# ------------------------------------------------------------------ item 1 --
NOW = dt.datetime(2026, 10, 17, 11, 20, tzinfo=dt.timezone.utc)


def _poly_event(slug: str, title: str) -> dict:
    return {"slug": slug, "title": title, "volume24hr": 500_000, "volume": 9e6,
            "tags": [{"slug": "politics"}], "startDate": "2026-01-01T00:00:00Z",
            "endDate": "2026-11-03T00:00:00Z",
            "markets": [{"outcomePrices": '["0.6", "0.4"]', "groupItemTitle": ""}]}


def _board_articles() -> list:
    poly = PB.polymarket_articles(
        fetch=lambda _u: [_poly_event("which-party-will-win-the-house-in-2026",
                                      "Which party will win the House in 2026?")],
        now=NOW)
    mani = PB.manifold_articles(fetch=lambda _u: [{
        "outcomeType": "BINARY", "uniqueBettorCount": 400, "probability": 0.4,
        "question": "Will a large language model beat a super grandmaster by 2028?",
        "url": "https://manifold.markets/x/llm-chess", "createdTime": 1.7e12,
        "volume24Hours": 9000}], now=NOW)
    assert poly and mani
    return poly + mani


class TestBoardIsNotARepeat:
    def test_board_articles_carry_the_exemption_and_their_venue(self):
        arts = _board_articles()
        assert all(a["recurrence_exempt"] is True for a in arts)
        assert {a["board_venue"] for a in arts} == {"Polymarket", "Manifold"}

    def test_recurrence_skips_board_markets_that_ran_before(self):
        # Pin Ep025 (2026-10-17) board titles + a minimal prior index.
        # The live content tracker rotates (that day's entry was rewritten
        # 40 → 6 headlines by 2026-10-22), so reading digests/ here is not
        # a stable guard. Digests stay untouched.
        board = [
            "Manifold: Does Claude Opus 5.5 make egregious errors?",
            "Manifold: Will a large language model beat a super grandmaster playing chess by EOY 2028?",
            "Kalshi: Which party will win the U.S. House?",
            "Kalshi: 2026 Midterms: Congress Balance of Power?",
            "Kalshi: 2028 Democratic presidential nominee",
            "Kalshi: Who will be Trump's next Press Secretary?",
            "Polymarket: US-Iran ceasefire continues through...?",
            "Polymarket: Brazil Presidential Election",
            "Polymarket: Republican Presidential Nominee 2028",
            "Polymarket: Israel x Iran ceasefire continues through...?",
        ]
        assert len(board) == 10
        prior = [
            {"date": "2026-09-23", "headlines": [
                "Kalshi: Which party will win the U.S. House?",
                "Kalshi: 2026 Midterms: Congress Balance of Power?",
                "Kalshi: 2028 Democratic presidential nominee",
                "Polymarket: Republican Presidential Nominee 2028",
                "Polymarket: Brazil Presidential Election",
            ]},
            {"date": "2026-09-27", "headlines": [
                "Polymarket: US-Iran ceasefire continues through...?",
                "Polymarket: Israel x Iran ceasefire continues through...?",
            ]},
            {"date": "2026-10-11", "headlines": [
                "Kalshi reviews small bets that correctly predicted Trump’s next press secretary",
            ]},
            {"date": "2026-10-12", "headlines": [
                "Manifold: Will a large language model beat a super grandmaster playing chess by EOY 2028?",
            ]},
        ]
        index = RecurrenceIndex(prior)
        plain = [{"title": h} for h in board]
        # The defect: nine of ten markets carried "pick a different story".
        assert len(annotate_articles(plain, index)) == 9
        flagged = [{"title": h, "recurrence_exempt": True} for h in board]
        assert annotate_articles(flagged, index) == {}

    def test_an_ordinary_article_is_still_annotated(self):
        index = RecurrenceIndex([{"date": "2026-10-16", "headlines": [
            "Sixth Circuit deepens circuit split on Kalshi sports contracts"]}])
        notes = annotate_articles(
            [{"title": "Sixth Circuit deepens circuit split over Kalshi sports contracts"}], index)
        assert len(notes) == 1

    def test_two_venues_on_one_question_are_not_one_story(self):
        arts = [{"title": "Kalshi: Which party will win the U.S. House?",
                 "recurrence_exempt": True},
                {"title": "Polymarket: Which party will win the U.S. House in 2026?",
                 "recurrence_exempt": True}]
        assert cluster_articles(arts) == []
        assert cluster_annotate(arts) == {}


class TestBoardVenueMix:
    SUPPLIED = [{"board_venue": v} for v in ("Polymarket", "Kalshi", "Manifold")]

    def test_ep025_one_manifold_market_fires(self):
        digest = _text("prediction_markets/Prediction_Markets_Ep025_20261017.md")
        f = DL.lint_board_venue_mix(digest, {"articles": self.SUPPLIED})
        assert f.note and "two venues" in f.note
        assert f.metrics["board_venues"] == ["Manifold"]
        assert f.metrics["board_venues_supplied"] == ["Kalshi", "Manifold", "Polymarket"]

    def test_ep023_two_venue_board_passes(self):
        digest = _text("prediction_markets/Prediction_Markets_Ep023_20261015.md")
        f = DL.lint_board_venue_mix(digest, {"articles": self.SUPPLIED})
        assert f.note == ""
        assert f.metrics["board_venues"] == ["Kalshi", "Polymarket"]

    def test_one_supplied_venue_cannot_fire(self):
        digest = _text("prediction_markets/Prediction_Markets_Ep025_20261017.md")
        f = DL.lint_board_venue_mix(digest, {"articles": [{"board_venue": "Manifold"}]})
        assert f.note == ""

    def test_no_context_measures_nothing(self):
        digest = _text("prediction_markets/Prediction_Markets_Ep025_20261017.md")
        assert DL.lint_board_venue_mix(digest) is None
        fired, metrics = DL.run_digest_lints(digest, ["board_venue_mix"])
        assert fired == [] and metrics == {}

    def test_urls_outrank_the_access_line(self):
        body = ("Which party wins the House: 90 percent, Kalshi. Whether Kalshi or "
                "Polymarket is available depends on where you live. "
                "Source: [kalshi.com](https://kalshi.com/markets/controlh)")
        assert PB.board_venues_in(body) == {"Kalshi"}

    def test_the_instruction_states_the_rule_only_when_two_venues_supplied(self):
        two = PB.board_block(_board_articles())
        assert "at least one market from each of two venues" in two
        one = PB.board_block([a for a in _board_articles() if a["board_venue"] == "Manifold"])
        assert "each of two venues" not in one

    def test_prediction_markets_opts_in(self):
        cfg = load_config(ROOT / "shows" / "prediction_markets.yaml")
        assert "board_venue_mix" in cfg.digest_lints


# ------------------------------------------------------------------ item 2 --
class TestBettingLines:
    @pytest.mark.parametrize("title", [
        "NHL Week 1 Odds 2026-27: Panthers-Hurricanes, Canucks-Oilers Best Bets",
        "Best Bets Today, Oct. 11: Canucks Vs Rangers Odds, CPL And NLCS Picks",
        "Lightning vs. Canucks Prediction: Picks, Live Odds and Moneyline - Saturday, October 17, 2026",
        "Portugal vs Norway Predictions, Picks & Odds – 04/10/2026",
        "Denmark vs Wales prediction & betting tips: Danes may dominate injury-hit visitors",
    ])
    def test_betting_pages_match(self, title):
        assert any(re.search(p, title, re.I) for p in BETTING_LINE_TITLE_PATTERNS)

    @pytest.mark.parametrize("title", [
        "NHL Game Preview: Vancouver Canucks at Edmonton Oilers with Line Combinations 09/29/2026",
        "AHL Game Preview: Abbotsford Canucks at Colorado Eagles with Projected Lines 10/09/2026",
        "Flames Pick Up First Preseason Win Against Canucks",
        "Les Leyne: Eby urges municipal candidates to 'pick a side'",
        "Vancouver Goldeneyes sign No. 1 PWHL draft pick Caroline Harvey to 3-year deal",
        "Vancouver mayoral race a dead heat between Fry and Sim: poll",
        "Surrey's amazing pick your own pumpkin patches and Halloween events in 2026",
    ])
    def test_local_news_does_not(self, title):
        assert not any(re.search(p, title, re.I) for p in BETTING_LINE_TITLE_PATTERNS)

    def test_the_aired_sentence_and_its_source_copy_are_betting_lines(self):
        aired = ("Bleacher Nation listed the Lightning at minus three hundred ninety-seven "
                 "and the Canucks at plus three hundred one, and predicted a Lightning win "
                 "and the over at six and a half goals.")
        assert is_betting_line_sentence(aired)
        assert is_betting_line_sentence("Tampa Bay is the -397 favourite and Vancouver +301.")
        assert is_betting_line_sentence("The puck line has Tampa Bay -1.5.")

    @pytest.mark.parametrize("sentence", [
        "The Canucks are two, six and one, with five points.",
        "Temperatures fell to -12 overnight and the lines at the ferry terminal grew.",
        "The SkyTrain line carries 150,000 riders a day.",
        "Pages 100-150 of the report list the odds of a flood in any year.",
    ])
    def test_ordinary_sentences_are_kept(self, sentence):
        assert not is_betting_line_sentence(sentence)

    def test_committed_local_and_desk_digests_match_only_the_aired_line(self):
        hits = []
        shows = ("vancouver", "collingwood", "omni_view_world", "omni_view_europe",
                 "omni_view_asia_pacific", "omni_view_africa_mideast", "omni_view_latam",
                 "omni_view_north_america")
        for show in shows:
            for p in list((DIGESTS / show).glob("*.md")) + list((DIGESTS / show).glob("members/*.md")):
                for line in p.read_text(encoding="utf-8").splitlines():
                    if line.lstrip().startswith("Source:"):
                        continue
                    for s in re.split(r"(?<=[.!?])\s+", line):
                        if not s.startswith("Source:") and is_betting_line_sentence(s):
                            hits.append((p.name, s[:60]))
        assert [h[0] for h in hits] == ["Vancouver_Daily_Ep025_20261017.md"], hits

    def test_strip_keeps_the_rest_of_the_article(self):
        text = ("The Canucks visit Tampa Bay today.\nOdds: Lightning -397, Canucks +301. "
                "Faceoff is at 4 p.m.")
        out, n = strip_betting_lines(text)
        assert n == 1
        assert out == "The Canucks visit Tampa Bay today.\nFaceoff is at 4 p.m."
        arts = [{"description": text, "full_text": text}]
        assert strip_betting_lines_from_articles(arts) == 2

    def test_the_flag_is_on_where_local_news_is_read_and_off_on_prediction_markets(self):
        for slug in ("vancouver", "collingwood", "omni_view_world", "omni_view_europe",
                     "omni_view_asia_pacific", "omni_view_africa_mideast",
                     "omni_view_latam", "omni_view_north_america"):
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
            assert cfg.exclude_betting_lines is True, slug
            assert set(BETTING_LINE_TITLE_PATTERNS) <= set(exclude_title_patterns_for(cfg))
        pm = load_config(ROOT / "shows" / "prediction_markets.yaml")
        assert pm.exclude_betting_lines is False
        assert not set(BETTING_LINE_TITLE_PATTERNS) & set(exclude_title_patterns_for(pm))

    def test_run_show_strips_before_the_listing(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        strip = src.index("strip_betting_lines_from_articles(articles)")
        listing = src.index("news_lines = []")
        enrich = src.index("enrich_articles_with_full_text(")
        assert enrich < strip < listing


# ------------------------------------------------------------------ item 3 --
HOOK_SUPPORTED_SHOWS = ("tesla", "modern_investing", "ai_chips", "mag7",
                        "prediction_markets", "vancouver", "collingwood",
                        "omni_view_world", "peptides", "longevity")


class TestHookSupported:
    def test_mit_ep203_joins_a_us_print_to_the_bank_of_canada(self):
        digest = _text("modern_investing/Modern_Investing_Ep203_20261017.md")
        assert DL.hook_unsupported_names(digest) == []  # every name is somewhere
        assert set(DL.hook_unjoined_names(digest)) == {"Bank", "Canada"}
        f = DL.lint_hook_supported(digest)
        assert f.note and "never mentions" in f.note

    def test_mit_ep190_aired_the_prompt_specimen(self):
        digest = _text("modern_investing/Modern_Investing_Ep190_20261004.md")
        assert DL.hook_unsupported_figures(digest) == ["11"]

    def test_tesla_ep634_figure_is_in_no_item(self):
        digest = _text("tesla_shorts_time/*Ep634_20261014.md")
        assert DL.hook_unsupported_figures(digest) == ["9.35"]

    @pytest.mark.parametrize("pattern", [
        "omni_view_world/Omni_View_World_Ep025_20261017.md",   # "100 percent"
        "mag7/MAG7_Daily_Ep025_20261017.md",                   # "16,000-plus"
        "omni_view_latam/Omni_View_LatAm_Ep023_20261015.md",   # 514,158 vs 514,158.45
    ])
    def test_figures_the_items_carry_pass(self, pattern):
        digest = _text(pattern)
        assert DL.hook_unsupported_figures(digest) == []
        assert DL.lint_hook_supported(digest).note == ""

    def test_name_numbers_and_dates_are_not_figures(self):
        assert DL.hook_figures("Investors watch the S&P 500 before October 28.") == []
        assert DL.hook_figures("After 16,000-plus checks, Model 3 sales rose 6.3%.") == ["16000", "6.3"]

    def test_replay_counts(self):
        def fires(show, n):
            files = sorted((p for p in (DIGESTS / show).glob("*.md")
                            if re.search(r"_Ep\d+_\d{8}\.md$", p.name)),
                           key=lambda p: p.name.split("_")[-1])
            files = [p for p in files if p.name.split("_")[-1] <= "20261017.md"][-n:]
            return [p.name for p in files
                    if (DL.lint_hook_supported(p.read_text(encoding="utf-8")) or
                        DL.LintFinding("", "")).note]
        mit = fires("modern_investing", 15)
        assert [re.search(r"Ep(\d+)", n).group(1) for n in mit] == ["190", "193", "195", "203"]
        for show in ("ai_chips", "mag7", "prediction_markets", "vancouver",
                     "omni_view_world"):
            assert fires(show, 10) == [], show

    @pytest.mark.parametrize("slug", HOOK_SUPPORTED_SHOWS)
    def test_a_show_that_runs_the_lint_states_the_rule(self, slug):
        cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
        assert "hook_supported" in cfg.digest_lints, slug
        prompt = (ROOT / "shows" / "prompts" / f"{slug}_digest.txt").read_text(encoding="utf-8")
        assert "<<include: _shared/hook_supported.txt>>" in prompt, slug

    def test_the_rule_is_shape_only(self):
        rule = (ROOT / "shows" / "prompts" / "_shared" / "hook_supported.txt").read_text(encoding="utf-8")
        assert "HOOK SUPPORT" in rule
        assert not re.search(r"\d", rule), "no specimen figures in the rule"
        assert "Bank of Canada" not in rule and '"' not in rule


# ------------------------------------------------------------------ item 4 --
EE_URL = "https://www.eetimes.com/semicon-west-2026-displays-ai-era-chipmaking-workforce-development/"


class TestTeardownFromAReadArticle:
    def _arts(self, ee_read: bool, other_read: bool = True) -> list:
        arts = [{"title": "SEMICON West 2026 displays AI-era chipmaking", "url": EE_URL,
                 "source_name": "EE Times", "description": "teaser"}]
        if ee_read:
            arts[0]["full_text"] = "x" * 3000
        arts.append({"title": "Inside HBM4 stacking", "url": "https://www.servethehome.com/hbm4/",
                     "source_name": "ServeTheHome",
                     **({"full_text": "y" * 3000} if other_read else {})})
        return arts

    def test_ep026_teardown_on_an_unread_ee_times_page_fires(self):
        digest = _text("ai_chips/AI_Chips_Ep026_20261017.md")
        f = DL.lint_deep_dive_fetched_source(digest, {"articles": self._arts(ee_read=False)})
        assert f.note and "EE Times" in f.note and "Source line" in f.note
        assert f.metrics["deep_dive_source_read"] is False

    def test_the_same_teardown_from_a_read_page_passes(self):
        digest = _text("ai_chips/AI_Chips_Ep026_20261017.md")
        f = DL.lint_deep_dive_fetched_source(digest, {"articles": self._arts(ee_read=True)})
        assert f.note == "" and f.metrics["deep_dive_source_read"] is True

    def test_nothing_read_today_is_measured_never_fired(self):
        digest = _text("ai_chips/AI_Chips_Ep026_20261017.md")
        f = DL.lint_deep_dive_fetched_source(
            digest, {"articles": self._arts(ee_read=False, other_read=False)})
        assert f.note == "" and f.metrics["deep_dive_read_candidates"] == 0

    def test_a_cited_source_url_decides(self):
        digest = ("# AI Chips\n\n### The Teardown: Stacks\nHBM stacks bond twelve dies.\n"
                  "Source: [servethehome.com](https://www.servethehome.com/hbm4/)\n")
        ok = DL.lint_deep_dive_fetched_source(digest, {"articles": self._arts(ee_read=False)})
        assert ok.note == ""
        bad = digest.replace("https://www.servethehome.com/hbm4/", EE_URL)
        assert DL.lint_deep_dive_fetched_source(
            bad, {"articles": self._arts(ee_read=False)}).note

    def test_ai_chips_opts_in_and_its_prompt_states_the_rule(self):
        cfg = load_config(ROOT / "shows" / "ai_chips.yaml")
        assert "deep_dive_fetched_source" in cfg.digest_lints
        prompt = (ROOT / "shows" / "prompts" / "ai_chips_digest.txt").read_text(encoding="utf-8")
        assert "end the Teardown on that article's Source line" in prompt
        assert "leave The Teardown section out" in prompt

    def test_run_show_passes_the_articles(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert src.count('context={"articles": articles}') == 3


# ------------------------------------------------------------------ item 5 --
SIDEBAR_PAGE = """<html><body><article>
<p>Researchers at MIT's Computer Science and Artificial Intelligence Laboratory gave an AI agent a
lobster-shaped virtual body and left it alone on an island for thirty hours.</p>
<p>None of that means the lobster was bored, curious, or self-aware in any meaningful sense.</p>
<div class="sf-suggested-card"><div class="sf-suggested-inner">
<a href="https://startupfortune.com/anthropic-found/" class="sf-suggested-title">Anthropic Found Its Claude Agents Attacked Each Other With Malware</a>
<p class="sf-suggested-excerpt">Anthropic ran an experiment putting three Claude agents on the same coding
task, and every model tested concluded it was under attack. Only its newest model class, Mythos 5,
reliably found a truce.</p></div></div>
<p>The comparison that comes up immediately is Stanford and Google's 2023 Smallville experiment.</p>
<p><strong>Also read:</strong> <a href="https://startupfortune.com/a/">South Korean Regulators Confirm AI Agent Breached 16 Banks</a> &bull; <a href="https://startupfortune.com/b/">Claude Opus beats a human baseline</a></p>
<p><strong><em>This article is posted in <a href="https://startupfortune.com/category/ai/">AI News</a>, check it out for more related stories.</em></strong></p>
</article></body></html>"""


class TestSidebarTeaser:
    def test_suggested_card_and_link_rails_are_not_the_article(self):
        from engine.article_text import extract_article_text

        text = extract_article_text(SIDEBAR_PAGE)
        assert "lobster-shaped virtual body" in text
        assert "Smallville" in text
        assert "truce" not in text and "under attack" not in text
        assert "Also read" not in text and "posted in" not in text

    def test_an_ordinary_paragraph_with_one_link_survives(self):
        from engine.article_text import extract_article_text

        page = ("<html><body><article><p>The study, published in <a href='https://n.example/x'>"
                "Nature</a>, followed 194 patients for two years and found lasting relief.</p>"
                "</article></body></html>")
        assert "194 patients" in extract_article_text(page)
