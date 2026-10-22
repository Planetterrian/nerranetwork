"""Guards for the Oct 22 2026 slate review (docs/reviews/slate_review_2026_10_22.md)."""

import datetime

UTC = datetime.timezone.utc


class TestModelNamesAreNotRanges:
    def test_model_sizes_keep_their_hyphen(self):
        from assets.pronunciation import replace_number_ranges
        for text in ("Llama-3.1-8B runs locally.", "Qwen2.5-7B is small.",
                     "GPT-4-32k is retired."):
            assert replace_number_ranges(text) == text

    def test_a_real_range_still_speaks_to(self):
        from assets.pronunciation import replace_number_ranges
        assert "to" in replace_number_ranges("between 10-20 dollars")
        out = replace_number_ranges("see pages 10–20.")
        assert out.endswith(".") and "to" in out
        assert replace_number_ranges("rose 2.5-3.5%") == "rose 2.5-3.5%"


class TestSpacexQuoteOutsideTheSession:
    def test_a_premarket_last_price_equal_to_the_last_close_is_that_close(self, monkeypatch):
        # Ep136-138: at 05:50 ET fast_info's last price was the prior
        # session's close and previous_close the session before, so the
        # closing said "is trading at" for a bar the body called a close.
        import shows.hooks.spacex as sx
        monkeypatch.setattr(sx, "_regular_session_open", lambda now=None: False)
        monkeypatch.setattr(sx, "_quote_from_fast_info", lambda: (159.31, 156.70))
        monkeypatch.setattr(sx, "_quote_from_history", lambda: (159.31, 156.70))
        monkeypatch.setattr(sx, "_validate", lambda p: True)
        monkeypatch.setattr(sx, "_persist", lambda *a, **k: None)
        _, change, source = sx._fetch_spcx_quote()
        assert source == "yfinance_history" and change == "+1.7%"

    def test_inside_the_session_a_live_trade_stays_live(self, monkeypatch):
        import shows.hooks.spacex as sx
        monkeypatch.setattr(sx, "_regular_session_open", lambda now=None: True)
        monkeypatch.setattr(sx, "_quote_from_fast_info", lambda: (159.31, 156.70))
        monkeypatch.setattr(sx, "_quote_from_history", lambda: (159.31, 156.70))
        monkeypatch.setattr(sx, "_validate", lambda p: True)
        monkeypatch.setattr(sx, "_persist", lambda *a, **k: None)
        assert sx._fetch_spcx_quote()[2] == "yfinance_fast_info"

    def test_the_session_clock(self):
        from shows.hooks.spacex import _regular_session_open
        # Thursday Oct 22 2026: 05:50 ET pre-market, 11:00 ET open, Saturday closed.
        assert not _regular_session_open(datetime.datetime(2026, 10, 22, 9, 50, tzinfo=UTC))
        assert _regular_session_open(datetime.datetime(2026, 10, 22, 15, 0, tzinfo=UTC))
        assert not _regular_session_open(datetime.datetime(2026, 10, 24, 15, 0, tzinfo=UTC))


class TestHoldingsFilingsAreNotNews:
    def _excluded(self, title):
        import re
        from engine.utils import NETWORK_EXCLUDE_TITLE_PATTERNS
        return any(re.search(p, title, re.IGNORECASE) for p in NETWORK_EXCLUDE_TITLE_PATTERNS)

    def test_13f_notices_are_dropped(self):
        for t in ("SpaceX $SPCX Shares Bought by Wealth Enhancement Advisory Services LLC",
                  "Tesla $TSLA Position Increased by Vanguard Group Inc.",
                  "Acme Capital Management LLC Buys 1,200 Shares of Tesla",
                  "Smith Wealth Partners LLC Opens a New Position in SpaceX"):
            assert self._excluded(t), t

    def test_ordinary_investment_news_survives(self):
        for t in ("Berkshire Hathaway sells part of its Apple stake",
                  "SoftBank buys a stake in OpenAI rival",
                  "SpaceX shares rise after the Starship flight"):
            assert not self._excluded(t), t


class TestArticleDatingFromThePublisher:
    def test_an_elsevier_pii_carries_its_year(self):
        from engine.article_dates import url_slug_date
        url = "https://www.sciencedirect.com/science/article/pii/S0012821X21004567"
        d = url_slug_date(url)
        assert d is not None and d.year <= 2022

    def test_parentheses_in_a_url_are_encoded(self):
        from engine.url_utils import sanitize_url
        out = sanitize_url("https://example.com/pii/S0012-821X(21)00456-7")
        assert "(" not in out and ")" not in out and "%2821%29" in out


class TestTheMapCarriesNoChapter:
    def test_new_map_shapes_read_as_maps(self):
        from engine.chapters import _looks_like_map
        assert _looks_like_map("From there it's the battery story, the factory note and the quick hits.")
        assert _looks_like_map("The launch pad, the engine test and the budget are the run from here.")
        assert _looks_like_map("A new chip, a supply deal and a recall come next.")

    def test_a_story_sentence_is_not_a_map(self):
        from engine.chapters import _looks_like_map
        assert not _looks_like_map("From the outside, the plant looks finished, but inside it is empty.")


class TestNumberedHeadlinesLoseTheirNumber:
    def test_top_world_bold_items(self):
        from engine.grok_imagine import extract_story_headlines
        digest = ("> **Lead hook sentence about a story in the world today**\n\n"
                  "**1. Nigeria's first Ebola patient holidayed in Uganda, officials say: BBC World**\n"
                  "Body.\n\n**3. Russian strikes hit Kyiv after Witkoff meets Putin: Reuters**\nBody.\n")
        heads = extract_story_headlines(digest)
        assert "Nigeria's first Ebola patient holidayed in Uganda, officials say" in heads
        assert not any(h[:1].isdigit() and h[1:3] in (". ", ") ") for h in heads)

    def test_a_headline_that_opens_on_a_figure_keeps_it(self):
        from engine.grok_imagine import extract_story_headlines
        heads = extract_story_headlines("1. **1.5 million people flee the floods in Pakistan: Reuters** body")
        assert heads and heads[0].startswith("1.5 million")
