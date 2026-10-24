"""Oct 24 2026 slate review guards (docs/reviews/slate_review_2026_10_24.md)."""
from __future__ import annotations

import importlib
from pathlib import Path

import engine.story_clusters as sc

ROOT = Path(__file__).resolve().parents[1]

# The four articles behind Tesla Ep644's false "retold" cluster: a market
# roundup whose teaser touches three unrelated stories, and one article on
# each of those stories (titles from the run's catalog rows).
ROUNDUP = {
    "title": ("Stocktwits Zero To Sixty: Tesla And SpaceX Form Merger Committees "
              "As Profits Drop, While Rivian Buys AI Startup"),
    "description": ("Tesla and SpaceX formed special committees to weigh a merger. "
                    "Tesla says Optimus production will reach 20,000 units per week. "
                    "Tesla Japan adds V2L power export to the new Model 3 and Model Y."),
}
MERGER = {"title": "What to know about SpaceX, Tesla merger",
          "description": "Tesla and SpaceX boards formed special committees to explore a merger."}
OPTIMUS = {"title": "Tesla Optimus: 20,000/Week Goal vs Reality [2026]",
           "description": "Tesla says Optimus production will reach 20,000 units per week by 2027."}
V2L = {"title": ("Tesla Japan adds V2L power-export support to new Model 3 and Model Y; "
                 "adapter ¥15,000 from Jan 2027"),
       "description": "Tesla Japan adds V2L power export to the new Model 3 and Model Y."}
ARTICLES = [ROUNDUP, MERGER, OPTIMUS, V2L]

FURNITURE = (
    "4. **Tesla App Now on Big Screens**\nb\n\n"
    "7. **Tesla produces 7,000 Model Ys in one week at Giga Berlin**\nb\n\n"
    "8. **Tesla Committed $4.3 Billion to LFP Batteries**\nb\n\n"
    "9. **Tesla reveals Optimus Academy, where robots teach themselves**\nb\n\n"
    "5. **Tesla Cybertruck draws massive crowd at new China showroom**\nb\n\n"
    "6. **Tesla Megapacks Arrive at Massive 400MWh Battery Storage Project in Belgium**\nb\n"
)
THREE_STORIES = (
    "### Top News\n\n"
    "1. **Tesla Japan adds V2L power-export support to new Model 3 and Model Y; adapter ¥15,000**\nb\n\n"
    "2. **SpaceX Tesla Merger Committees Formed**\nb\n\n"
    "3. **Optimus 20,000 Per Week Target**\nb\n\n" + FURNITURE
)
MERGER_TWICE = (
    "### Top News\n\n"
    "1. **SpaceX Tesla Merger Committees Formed**\nb\n\n"
    "2. **Tesla and SpaceX boards form special merger committees**\nb\n\n"
    "3. **Optimus 20,000 Per Week Target**\nb\n\n" + FURNITURE
)


class TestRetoldIsOneStoryTwice:
    def test_the_roundup_joins_one_cluster(self):
        # The clustering itself is unchanged: the roundup leads a cluster.
        assert sc.cluster_articles(ARTICLES) == [[0, 1, 2, 3]]

    def test_three_stories_from_one_roundup_are_not_retold(self):
        assert sc.retold_clusters(THREE_STORIES, ARTICLES, [[0, 1, 2, 3]]) == []

    def test_one_story_told_twice_is_still_retold(self):
        got = sc.retold_clusters(MERGER_TWICE, ARTICLES, [[0, 1, 2, 3]])
        assert len(got) == 1
        assert got[0][0] == "SpaceX Tesla Merger Committees Formed"
        assert "special merger committees" in got[0][1]

    def test_furniture_and_bare_numbers_never_match(self):
        heads = [sc.salient_tokens(t) for t in sc.digest_item_titles(THREE_STORIES)]
        furniture = sc._title_furniture(heads)
        assert "tesla" in furniture and "000" in furniture
        assert "merger" not in furniture


class TestClusterOnlyRetryMustImprove:
    class _M:
        def __init__(self):
            self.rec = {}

        def record(self, k, v):
            self.rec[k] = v

    def test_an_unchanged_count_is_rejected_when_clusters_were_the_only_reason(self):
        rs = importlib.import_module("run_show")
        before = sc.retold_clusters(MERGER_TWICE, ARTICLES, [[0, 1, 2, 3]])
        m = self._M()
        assert rs._cluster_retry_worse(MERGER_TWICE, ARTICLES, [[0, 1, 2, 3]],
                                       before, m, must_improve=True) is True
        assert rs._cluster_retry_worse(MERGER_TWICE, ARTICLES, [[0, 1, 2, 3]],
                                       before, m, must_improve=False) is False

    def test_a_retry_that_folds_the_story_is_kept(self):
        rs = importlib.import_module("run_show")
        before = sc.retold_clusters(MERGER_TWICE, ARTICLES, [[0, 1, 2, 3]])
        assert rs._cluster_retry_worse(THREE_STORIES, ARTICLES, [[0, 1, 2, 3]],
                                       before, self._M(), must_improve=True) is False

    def test_run_show_passes_must_improve_only_for_a_cluster_only_retry(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "must_improve=_struct_defects == [_lint_findings[-1].note]" in src


class TestHoldingsFilingsByUrl:
    def test_marketbeat_filings_are_excluded_and_its_news_is_not(self):
        import re

        from engine.utils import NETWORK_EXCLUDE_URL_PATTERNS
        pats = [re.compile(p, re.I) for p in NETWORK_EXCLUDE_URL_PATTERNS]

        def excluded(u):
            return any(p.search(u) for p in pats)
        base = "https://www.marketbeat.com/instant-alerts/"
        assert excluded(base + "filing-spacex-spcx-stock-brookstone-capital-management-"
                        "increases-holdings-2026-10-24/")
        assert excluded(base + "filing-24777-shares-in-spacex-spcx-purchased-by-"
                        "investment-house-llc-2026-10-23/")
        assert not excluded(base + "insider-spacex-nasdaq-spcx-coo-gwynne-shotwell-sells-"
                            "342170-shares-of-company-stock-2026-09-24/")
        assert not excluded(base + "analyst-spacex-nasdaq-spcx-rating-upgraded-by-wall-"
                            "street-zen-2026-10-24/")


class TestUrlParensInText:
    def test_a_raw_pii_url_keeps_its_whole_address(self):
        from engine.url_utils import encode_url_parens_in_text as enc
        cell = "https://www.cell.com/cell-metabolism/fulltext/S1550-4131(26)00412-4"
        out = enc(f"Source: [cell.com]({cell})")
        assert out == ("Source: [cell.com](https://www.cell.com/cell-metabolism/fulltext/"
                       "S1550-4131%2826%2900412-4)")
        assert enc(f"Source: {cell}").endswith("S1550-4131%2826%2900412-4")

    def test_urls_without_parens_and_prose_parens_are_untouched(self):
        from engine.url_utils import encode_url_parens_in_text as enc
        for s in ("(see https://example.com/a) here", "[y](https://example.com/b).",
                  "no url (here)", "open https://example.com/a(b"):
            assert enc(s) == s

    def test_the_canonical_transform_encodes_before_linkifying(self):
        src = (ROOT / "engine" / "newsletter_body.py").read_text(encoding="utf-8")
        i = src.index("body = encode_url_parens_in_text(body)")
        assert i < src.index("body = shorten_source_urls(body)")


class TestTradeReviewHeaderIsAFact:
    def test_no_instruction_in_the_label(self):
        src = (ROOT / "shows" / "hooks" / "modern_investing.py").read_text(encoding="utf-8")
        assert "never the last one" not in src and "call it an earlier hold" not in src
        assert 'closed since):**' in src
