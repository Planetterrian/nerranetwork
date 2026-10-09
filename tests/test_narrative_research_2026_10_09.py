"""Oct 9 2026 — the narrative shows get sources (operator-directed).

Unintended Consequences and First Principles are topic-queue shows: the
runner skips the news fetch and the episode prompt took the topic title,
brief and category and nothing else. So their digests carried no Source
lines, and UC verified zero claims across eight episodes — the claims gate
had nothing to verify against.

Now ``narrative_research: N`` runs ONE web search for the picked topic
(``engine.fetcher.fetch_topic_research_articles`` — any date; the news
searcher drops anything older than 72 h and a 1935 cane toad is the whole
point), merges the results as hook articles so they reach fetch_full_text,
news_section and the claims gate, and renders them into the episode prompt
as ``{research_sources}``. What binds:

* An empty or failed search never skips the episode: the prompt gets an
  honest fallback line and the brief still carries it.
* The claims gate never verifies against the search model's summary —
  only the fetched PAGE vouches for a research article, else HTTP.
* The three guards that keep narrative runs off the news gates are
  untouched; the research merge sits beside the hook merge.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import fetcher  # noqa: E402
from engine.claims import build_local_texts  # noqa: E402
from engine.config import load_config  # noqa: E402
from engine.hook_articles import normalize_hook_articles  # noqa: E402

SHOWS = ("unintended_consequences", "first_principles")

RESPONSE = """ARTICLE_TITLE: Cane toads in Australia
ARTICLE_URL: https://www.environment.gov.au/biodiversity/invasive/cane-toads
ARTICLE_DESCRIPTION: 102 toads were released in Queensland in 1935 to control cane beetles. They never ate the beetles.
ARTICLE_SOURCE: Australian Government Department of the Environment
ARTICLE_DATE: unknown

ARTICLE_TITLE: The biological control that was not
ARTICLE_URL: https://example.org/2018/04/12/cane-toad-study
ARTICLE_DESCRIPTION: A 2018 review of the toad's spread rate across northern Australia.
ARTICLE_SOURCE: Example Journal
ARTICLE_DATE: 2018-04-12
"""


class TestTheSearch:
    def test_results_keep_any_date_and_are_marked(self, monkeypatch):
        monkeypatch.setenv("GROK_API_KEY", "x")
        seen = {}

        def fake(prompt, **kw):
            seen["prompt"] = prompt
            return RESPONSE, {}
        import digests.xai_grok as xg
        monkeypatch.setattr(xg, "grok_generate_text", fake)
        out = fetcher.fetch_topic_research_articles("Cane toads", "Queensland, 1935", max_results=8)
        assert [a["title"] for a in out] == ["Cane toads in Australia",
                                             "The biological control that was not"]
        assert out[0]["published_date"] == "" and out[1]["published_date"].startswith("2018-04-12")
        assert all(a["source_kind"] == "research" and a["exempt_stale"] for a in out)
        assert out[0]["source_name"].endswith("(research)")
        assert "ANY date is fine" in seen["prompt"] and "last 24 hours" not in seen["prompt"]

    def test_unavailable_search_is_an_empty_list(self, monkeypatch):
        monkeypatch.setenv("GROK_API_KEY", "x")
        import digests.xai_grok as xg

        def boom(prompt, **kw):
            raise xg.SearchUnavailable("down")
        monkeypatch.setattr(xg, "grok_generate_text", boom)
        assert fetcher.fetch_topic_research_articles("Cane toads", "", max_results=8) == []

    def test_no_sources_sentinel_and_no_key(self, monkeypatch):
        monkeypatch.setenv("GROK_API_KEY", "x")
        import digests.xai_grok as xg
        monkeypatch.setattr(xg, "grok_generate_text", lambda prompt, **kw: ("NO_SOURCES_FOUND", {}))
        assert fetcher.fetch_topic_research_articles("Cane toads", "", max_results=8) == []
        monkeypatch.delenv("GROK_API_KEY", raising=False)
        monkeypatch.delenv("XAI_API_KEY", raising=False)
        assert fetcher.fetch_topic_research_articles("Cane toads", "", max_results=8) == []

    def test_off_by_default(self):
        assert fetcher.fetch_topic_research_articles("Cane toads", "", max_results=0) == []


class TestTheGateNeverReadsTheSummary:
    def test_summary_is_not_a_local_text_but_the_page_is(self):
        art = normalize_hook_articles([{
            "title": "Cane toads in Australia",
            "url": "https://www.environment.gov.au/cane-toads",
            "description": "102 toads were released in Queensland in 1935.",
        }])[0]
        art["source_kind"] = "research"
        texts = build_local_texts([art])
        key = next(iter(texts), "")
        assert "102 toads" not in texts.get(key, ""), (
            "the search model's summary must never verify a quote")
        art["full_text"] = "In 1935, 102 toads were brought from Hawaii to Gordonvale."
        art["full_text_source"] = "page"
        texts = build_local_texts([art])
        assert "Gordonvale" in next(iter(texts.values()))

    def test_a_fetched_news_article_is_unchanged(self):
        texts = build_local_texts([{"title": "T", "url": "https://x.example/a",
                                    "description": "the feed teaser carries the quote"}])
        assert "feed teaser" in next(iter(texts.values()))


class TestWiring:
    def test_both_shows_opt_in_with_page_fetches(self):
        for slug in SHOWS:
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
            assert cfg.narrative_mode is True
            assert cfg.narrative_research == 8, slug
            assert cfg.fetch_full_text >= 6, slug

    def test_off_everywhere_else(self):
        for y in sorted((ROOT / "shows").glob("*.yaml")):
            if y.name.startswith("_") or y.stem in SHOWS or y.stem == "network_meta":
                continue
            assert load_config(y).narrative_research == 0, y.name

    def test_both_prompts_take_the_sources(self):
        for slug in SHOWS:
            text = (ROOT / "shows" / "prompts" / f"{slug}_episode.txt").read_text(encoding="utf-8")
            assert "{research_sources}" in text, slug
            assert "RESEARCH SOURCES" in text
        uc = (ROOT / "shows/prompts/unintended_consequences_episode.txt").read_text(encoding="utf-8")
        assert "Use ONLY the topic information" not in uc

    def test_runner_merges_research_beside_the_hook_merge(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        hook_at = src.index("merge_hook_articles(articles, _hook_articles)")
        research_at = src.index("merge_hook_articles(articles, _research)")
        news_at = src.index('news_section = "\\n\\n".join(news_lines)')
        assert hook_at < research_at < news_at
        assert 'metrics.record("narrative_research_articles"' in src
        assert 'template_vars["research_sources"]' in src
        # The fallback line renders when the search returned nothing.
        assert "No research sources were retrieved" in src
        # Narrative runs still skip the news gates (an empty search never skips).
        assert 'if _hook_articles and not _topic_driven:' in src
