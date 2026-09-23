"""Guards for Prediction Markets Daily (Phase 2b, docs/new_shows_plan_2026_09_22.md §4.11).

The show is about the prediction-market ecosystem, never a price tape (the
MAG 7 lesson, plan §9b), and never a bet. Each guard names what it protects.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SLUG = "prediction_markets"
NOW = dt.datetime(2026, 9, 23, 5, 0, tzinfo=dt.timezone.utc)


def _cfg():
    from engine.config import load_config
    return load_config(ROOT / "shows" / f"{SLUG}.yaml")


def _prompt(name: str) -> str:
    return (ROOT / "shows" / "prompts" / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# engine/prediction_board.py — The Board as hook articles
# ---------------------------------------------------------------------------

def _poly_event(title="Fed Decision in October?", slug="fed-october", vol=500_000,
                tags=("economy",), neg_risk=True, markets=None, start="2026-06-17T00:00:00Z"):
    return {
        "title": title, "slug": slug, "volume24hr": vol, "volume": vol * 20,
        "tags": [{"slug": t} for t in tags], "negRisk": neg_risk,
        "startDate": start, "endDate": "2026-10-29T00:00:00Z",
        "markets": markets if markets is not None else [
            {"groupItemTitle": "No change", "outcomePrices": '["0.455", "0.545"]',
             "oneDayPriceChange": 0.04},
            {"groupItemTitle": "25 bps increase", "outcomePrices": '["0.535", "0.465"]',
             "oneDayPriceChange": 0.0},
        ],
    }


class TestPolymarket:
    def _run(self, events):
        from engine.prediction_board import polymarket_articles
        return polymarket_articles(fetch=lambda url: events, now=NOW)

    def test_one_article_per_market_with_its_own_url_and_numbers(self):
        [art] = self._run([_poly_event()])
        assert art["url"] == "https://polymarket.com/event/fed-october"
        body = art["content_text"]
        assert "read at 2026-09-23 05:00 UTC" in body
        assert "$500,000 (US dollars)" in body
        assert "+4.0 points in 24 hours" in body
        assert art["exempt_stale"] is True

    def test_mutually_exclusive_outcomes_rank_by_probability(self):
        body = self._run([_poly_event()])[0]["content_text"]
        assert body.index("25 bps increase") < body.index("No change")

    def test_a_date_ladder_keeps_its_own_order(self):
        """The first live read ranked a "by...?" ladder by price and put
        December above October."""
        ev = _poly_event(title="US announces end of blockade by...?", neg_risk=False, markets=[
            {"groupItemTitle": "September 30", "outcomePrices": '["0.075", "0.925"]'},
            {"groupItemTitle": "October 31", "outcomePrices": '["0.325", "0.675"]'},
            {"groupItemTitle": "December 31", "outcomePrices": '["0.65", "0.35"]'},
        ])
        body = self._run([ev])[0]["content_text"]
        assert body.index("September 30") < body.index("October 31") < body.index("December 31")

    @pytest.mark.parametrize("tags", [("sports", "mlb"), ("esports",), ("crypto-prices", "hit-price"),
                                      ("tweets-markets",), ("recurring",)])
    def test_noise_categories_never_reach_the_board(self, tags):
        assert self._run([_poly_event(tags=tags)]) == []

    def test_volume_floor_and_near_certain_markets(self):
        from engine.prediction_board import MIN_USD_VOLUME_24H
        assert self._run([_poly_event(vol=MIN_USD_VOLUME_24H - 1)]) == []
        aliens = _poly_event(title="Will the US confirm that aliens exist?", neg_risk=False, markets=[
            {"groupItemTitle": "December 31", "outcomePrices": '["0.031", "0.969"]'}])
        assert self._run([aliens]) == []

    def test_a_thin_market_is_called_thin(self):
        body = self._run([_poly_event(vol=12_000)])[0]["content_text"]
        assert "thin market" in body

    def test_a_network_failure_is_an_empty_board(self):
        from engine.prediction_board import polymarket_articles

        def boom(url):
            raise OSError("down")
        assert polymarket_articles(fetch=boom, now=NOW) == []


def _kalshi_event(category="Elections", strike="custom", vol="60000", mve=None, excl=True):
    return {
        "title": "Which party will win the U.S. House?", "category": category,
        "series_ticker": "CONTROLH", "event_ticker": "CONTROLH-26", "mutually_exclusive": excl,
        "markets": [
            {"yes_sub_title": "Democratic Party", "last_price_dollars": "0.9130",
             "previous_price_dollars": "0.8800", "volume_24h_fp": vol, "strike_type": strike,
             "mve_collection_ticker": mve, "open_time": "2025-01-01T00:00:00Z"},
            {"yes_sub_title": "Republican Party", "last_price_dollars": "0.0930",
             "previous_price_dollars": "0.1200", "volume_24h_fp": vol, "strike_type": strike,
             "mve_collection_ticker": mve, "open_time": "2025-01-01T00:00:00Z"},
        ],
    }


class TestKalshi:
    def _run(self, pages):
        from engine.prediction_board import kalshi_articles
        seq = iter(pages)
        return kalshi_articles(fetch=lambda url: next(seq), now=NOW, sleep=lambda s: None)

    def test_volume_is_contracts_never_dollars(self):
        [art] = self._run([{"events": [_kalshi_event()], "cursor": ""}])
        body = art["content_text"]
        assert "120,000 contracts" in body and "$" not in body
        assert art["url"] == "https://kalshi.com/markets/controlh"

    @pytest.mark.parametrize("category", ["Sports", "Mentions", "Crypto"])
    def test_excluded_categories(self, category):
        assert self._run([{"events": [_kalshi_event(category=category)], "cursor": ""}]) == []

    def test_ladders_and_parlays_are_excluded(self):
        assert self._run([{"events": [_kalshi_event(strike="greater")], "cursor": ""}]) == []
        assert self._run([{"events": [_kalshi_event(mve="KXMVE-R")], "cursor": ""}]) == []

    def test_paging_stops_cleanly_on_repeated_429(self):
        from engine.prediction_board import kalshi_articles
        calls = []

        def fetch(url):
            calls.append(url)
            if len(calls) == 1:
                return {"events": [_kalshi_event()], "cursor": "abc"}
            raise RuntimeError("HTTP Error 429: Too Many Requests")
        arts = kalshi_articles(fetch=fetch, now=NOW, sleep=lambda s: None)
        # Page 1 kept; page 2 tried twice (one retry), then ranked what was read.
        assert len(arts) == 1 and len(calls) == 3


class TestManifold:
    def _run(self, markets):
        from engine.prediction_board import manifold_articles
        return manifold_articles(fetch=lambda url: markets, now=NOW)

    def test_play_money_is_called_play_money(self):
        [art] = self._run([{"outcomeType": "BINARY", "question": "Will X happen?", "probability": 0.34,
                            "uniqueBettorCount": 4614, "volume24Hours": 19796,
                            "url": "https://manifold.markets/a/b", "createdTime": 1676851200000}])
        assert "play money" in art["content_text"] and "mana" in art["content_text"]

    def test_perpetuals_and_small_markets_are_excluded(self):
        assert self._run([{"outcomeType": "PERP", "question": "MiniMax", "uniqueBettorCount": 900,
                           "url": "https://manifold.markets/x"}]) == []
        assert self._run([{"outcomeType": "BINARY", "question": "Q", "probability": 0.5,
                           "uniqueBettorCount": 20, "url": "https://manifold.markets/x"}]) == []


class TestBoardBlock:
    def test_no_data_means_one_honest_sentence(self):
        from engine.prediction_board import board_block
        block = board_block([])
        assert "ONE sentence" in block and "never a market" in block

    def test_the_board_is_capped_at_five_and_units_are_never_converted(self):
        from engine.prediction_board import board_block
        block = board_block([{"source_name": "Kalshi", "title": "Kalshi: Q"}])
        assert "at most FIVE" in block and "never convert" in block

    def test_the_venue_line_makes_no_specific_legal_claim(self):
        """Board text is the pipeline's own copy, so the claims gate treats it
        as sourced: a specific claim about a province or a lawsuit would be
        verified against nothing and go stale with the next ruling."""
        from engine.prediction_board import VENUE_ACCESS_LINE
        line = VENUE_ACCESS_LINE.lower()
        assert "depends on where the user lives" in line
        for claim in ("canada", "ontario", "court", "illegal", "banned", "cftc"):
            assert claim not in line


# ---------------------------------------------------------------------------
# engine/research_papers.py — How It Works has real abstracts behind it
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code, self._payload, self.text = status, payload, text

    def json(self):
        return self._payload


ABSTRACT = "We study " + "information aggregation in markets " * 12


class TestResearchPapers:
    def test_title_rules_or_alternatives_and_exclusions(self):
        from engine.research_papers import _title_ok
        assert _title_ok("Futarchy in decentralized science", ["futarch|decision market"], [])
        assert _title_ok("Securities Based Decision Markets", ["futarch|decision market"], [])
        assert not _title_ok("The Going-Public Decision", ["futarch|decision market"], [])
        assert not _title_ok("Cortical prediction markets", ["prediction market"], ["cortical"])

    def test_crossref_filters_on_title_then_ranks_by_citations(self):
        from engine.research_papers import crossref_abstracts
        items = [
            {"DOI": "10.1/alpha", "title": ["Highly accurate protein structure prediction"],
             "abstract": ABSTRACT, "is-referenced-by-count": 45000},
            {"DOI": "10.1/b", "title": ["Prediction Markets"], "abstract": ABSTRACT,
             "is-referenced-by-count": 811, "container-title": ["Journal of Economic Perspectives"],
             "issued": {"date-parts": [[2004]]}},
            {"DOI": "10.1/c", "title": ["Prediction markets vs polls"], "abstract": ABSTRACT,
             "is-referenced-by-count": 7},
        ]
        arts = crossref_abstracts("prediction markets", require=["prediction market"],
                                  get=lambda url, params: _Resp(payload={"message": {"items": items}}))
        assert [a["url"] for a in arts] == ["https://doi.org/10.1/b", "https://doi.org/10.1/c"]
        assert arts[0]["source_name"] == "Journal of Economic Perspectives (2004)"
        assert arts[0]["exempt_stale"] is True

    def test_arxiv_atom_is_parsed(self):
        from engine.research_papers import arxiv_abstracts
        atom = f"""<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>http://arxiv.org/abs/1212.5764v1</id><title>Strategy-Proof Prediction Markets</title>
<summary>{ABSTRACT}</summary><published>2012-12-23T05:57:01Z</published></entry></feed>"""
        [art] = arxiv_abstracts('ti:"prediction markets"', require=["prediction market"],
                                get=lambda url, params: _Resp(text=atom))
        assert art["url"] == "https://arxiv.org/abs/1212.5764v1"
        assert art["source_name"] == "arXiv (2012)"

    def test_failures_are_empty(self):
        from engine.research_papers import papers_for

        def boom(url, params):
            raise OSError("down")
        assert papers_for({"search": "x", "arxiv": "ti:x"}, get=boom) == []
        assert papers_for(None) == []


class TestCurriculum:
    DATA = yaml.safe_load((ROOT / "shows" / "curricula" / f"{SLUG}.yaml").read_text(encoding="utf-8"))

    def test_runway_at_launch(self):
        queue = self.DATA["queue"]
        assert sum(1 for e in queue if not e.get("produced")) >= 20
        assert queue[0]["id"] == "price-as-probability" and queue[0]["category"] == "debut"

    def test_every_entry_can_find_papers_and_carries_the_posture(self):
        for e in self.DATA["queue"]:
            assert e["id"] and e["title"] and e["brief"], e.get("id")
            assert e.get("search") or e.get("arxiv"), e["id"]
            assert e.get("require"), e["id"]
            assert "never" in e["brief"].lower() and (
                "recommendation" in e["brief"].lower() or "legal advice" in e["brief"].lower()), e["id"]

    def test_no_brief_supplies_a_quotable_line(self):
        """De-seed by shape: a quoted slogan or a worked example in a brief is
        the sentence the model reproduces."""
        for e in self.DATA["queue"]:
            assert '"' not in e["brief"], e["id"]

    def test_ids_are_unique(self):
        ids = [e["id"] for e in self.DATA["queue"]]
        assert len(ids) == len(set(ids))


class TestSpotlightPeriod:
    def test_the_weeklies_are_unchanged(self):
        from engine.curriculum import spotlight_block
        topic = {"title": "T", "brief": "B"}
        assert spotlight_block(topic, "Mechanism of the Week").startswith(
            "### THIS WEEK'S MECHANISM OF THE WEEK")
        assert "the week's most-covered item" in spotlight_block(None, "Mechanism of the Week")

    def test_a_daily_says_today(self):
        from engine.curriculum import spotlight_block
        assert spotlight_block({"title": "T", "brief": "B"}, "How It Works", period="day").startswith(
            "### TODAY'S HOW IT WORKS")
        assert "today's most-covered item" in spotlight_block(None, "How It Works", period="day")


def test_hook_returns_board_papers_and_both_instructions(monkeypatch, capsys):
    import shows.hooks.prediction_markets as hook
    monkeypatch.setattr(hook, "gather_board", lambda builders: [
        {"title": "Kalshi: Q", "url": "https://kalshi.com/markets/q", "source_name": "Kalshi"}])
    monkeypatch.setattr(hook, "next_spotlight", lambda slug: {"id": "calibration", "title": "Calibration",
                                                              "brief": "B", "search": "calibration"})
    monkeypatch.setattr(hook, "papers_for", lambda topic: [
        {"title": "Paper", "url": "https://doi.org/10.1/x", "source_name": "J (2020)"}])
    monkeypatch.setattr(hook, "_remaining", lambda: 3)
    monkeypatch.setattr(hook.show_memory, "memory_pre_fetch", lambda cfg, s: {})
    ctx = hook.pre_fetch(_cfg())
    assert [a["url"] for a in ctx["articles"]] == ["https://kalshi.com/markets/q", "https://doi.org/10.1/x"]
    assert "THE BOARD DATA" in ctx["hook_context"] and "TODAY'S HOW IT WORKS" in ctx["hook_context"]
    assert "::warning::" in capsys.readouterr().out  # 3 subjects left


# ---------------------------------------------------------------------------
# The show's wiring and posture
# ---------------------------------------------------------------------------

class TestWiring:
    def test_config(self):
        c = _cfg()
        assert c.llm.model == "grok-4.7"
        assert c.publishing.host_name == "Patrick" and c.publishing.host_kind == "human"
        assert c.newsletter.requires_financial_disclaimer is True
        assert c.min_articles_skip == 4

    def test_registry(self):
        reg = yaml.safe_load((ROOT / "shows" / "network_meta.yaml").read_text(encoding="utf-8"))[SLUG]
        assert reg["strand"] == "markets" and reg["host"] == "patrick"
        assert reg["show_page"] == "prediction-markets.html"
        assert "markets" in reg["picker_tags"]["topics"]
        # Its own accent, not AI Chips' indigo (plan §5a: family + per-show accent).
        assert reg["brand_color"] != "#4338CA"

    def test_launched_and_on_the_clock(self):
        # Launch-cohort PR C (2026-09-23): daily at 11:16 UTC.
        from review_episodes import PRELAUNCH_SLUGS, SHOW_REGISTRY
        assert SLUG not in PRELAUNCH_SLUGS and SHOW_REGISTRY[SLUG]["schedule"] == "daily"
        wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
        assert f"          - {SLUG}\n" in wf
        cron_block = wf[wf.index("CRON_MAP"):wf.index("CRON_MAP") + 6000]
        assert f'"{SLUG}"' in cron_block

    def test_run_show_owns_the_pages_now(self):
        # Launch-cohort PR C (2026-09-23) put the show on the clock, so run-show
        # regenerates its pages and the nightly add-paths must not name them
        # (a stale pathspec fails test_page_regen_ownership).
        wf = (ROOT / ".github" / "workflows" / "nightly-maintenance.yml").read_text(encoding="utf-8")
        for path in ("prediction-markets.html", "prediction-markets-summaries.html",
                     "blog/prediction_markets/**"):
            assert f"            {path}\n" not in wf

    def test_closing_carries_the_posture_and_matches_the_chapter(self):
        from engine.intros import _SHOW_PERSONALITIES as SHOW_PERSONALITIES
        closing = SHOW_PERSONALITIES[SLUG]["closings"][0]
        assert "financial advice" in closing and "help is available" in closing
        pattern = next(m.pattern for m in _cfg().chapters.section_markers if m.title == "Closing")
        assert re.search(pattern, closing, re.I)

    def test_identity_line_is_short_and_anchors_the_introduction(self):
        from engine.intros import build_intro_line
        line = build_intro_line(SLUG, episode_num=1, today_str="September 24, 2026")
        assert len(line.split()) <= 20
        pattern = next(m.pattern for m in _cfg().chapters.section_markers if m.title == "Introduction")
        assert re.search(pattern, line, re.I)

    def test_segment_anchors_are_required_phrases_the_chapters_key_on(self):
        podcast = _prompt(f"{SLUG}_podcast.txt")
        markers = {m.title: m.pattern for m in _cfg().chapters.section_markers}
        assert '"on the board today"' in podcast and re.search(markers["The Board"], "on the board today")
        assert '"how it works"' in podcast and re.search(markers["How It Works"], "how it works")

    def test_the_board_is_not_tracked_as_covered_content(self):
        from engine.content_tracker import SHOW_SECTION_PATTERNS
        patterns = SHOW_SECTION_PATTERNS[SLUG]
        assert "headlines" in patterns and not any("board" in k for k in patterns)


class TestPosture:
    def test_every_prompt_forbids_the_bet(self):
        for name in ("system", "digest", "podcast", "weekly"):
            text = _prompt(f"{SLUG}_{name}.txt").lower()
            assert "never" in text and ("recommend" in text or "tell anyone to buy" in text), name

    def test_the_new_show_rules_are_included(self):
        digest = _prompt(f"{SLUG}_digest.txt")
        assert "<<include: _shared/interesting_first.txt>>" in digest
        assert "<<include: _shared/content_discipline.txt>>" in _prompt(f"{SLUG}_podcast.txt")

    def test_markets_on_events_are_covered_as_markets(self):
        assert "never as coverage of the event" in _prompt(f"{SLUG}_digest.txt")
        assert "never as election coverage" in _prompt(f"{SLUG}_system.txt")

    @pytest.mark.parametrize("title", [
        "Kalshi Promo Code MILE: Claim Up to $2,000 Bonus in September 2026",
        "Polymarket Promo Code GOAL: Get $50 Trading Bonuses in September 2026",
        "Polymarket upgrades $50 invite code for Astros vs. Mariners live odds",
        "Best Prediction Market Apps for 2026",
    ])
    def test_affiliate_headlines_are_filtered(self, title):
        pats = [re.compile(p, re.I) for p in _cfg().exclude_title_patterns]
        assert any(p.search(title) for p in pats), title

    @pytest.mark.parametrize("title", [
        "CFTC says prediction markets' 'mentions' contracts present a higher risk of manipulation",
        "Prediction market companies ordered to end sports 'event contracts' in Missouri",
        "Kalshi asks CFTC to allow margin trading on its platform",
    ])
    def test_real_news_passes(self, title):
        pats = [re.compile(p, re.I) for p in _cfg().exclude_title_patterns]
        assert not any(p.search(title) for p in pats), title
