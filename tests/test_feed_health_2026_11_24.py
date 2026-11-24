"""Nov 24 2026 — a weekly show's web search looks back as far as its feeds,
and a search that ran and found nothing is not reported as an outage.

Offshore North is weekly (``fetch_expansion_hours: [168]``) and declares its
web search load-bearing (``web_search_always``). The search prompt was fixed
at "the last 24 hours": on the 2026-11-23 run all eight queries got a 200 and
the model's own NO_RECENT_ARTICLES, the log said the search "may be down",
and the episode skipped as too thin. ``window_hours`` widens what is asked
for; 24 renders the prompt exactly as before.

Also pinned: four feeds that returned nothing on four to eight straight
weekly audits (``data/feed_audit_*.json``) stay out of the live feed lists
until someone restores them with a URL that was fetched and parsed.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest
import yaml

import engine.fetcher as fetcher

ROOT = Path(__file__).resolve().parent.parent

_BLOCK = (
    "ARTICLE_TITLE: A fleet story\n"
    "ARTICLE_URL: https://example.com/a-fleet-story\n"
    "ARTICLE_DESCRIPTION: Something happened at sea.\n"
    "ARTICLE_SOURCE: Example\n"
    "ARTICLE_DATE: {date}\n"
)


def _capture(monkeypatch, reply):
    seen = []

    def fake(**kw):
        seen.append(kw["prompt"])
        if isinstance(reply, Exception):
            raise reply
        return reply, {}

    monkeypatch.setattr("digests.xai_grok.grok_generate_text", fake, raising=False)
    monkeypatch.setenv("GROK_API_KEY", "test-key")
    return seen


class TestSearchWindow:
    def test_default_prompt_is_unchanged(self, monkeypatch):
        seen = _capture(monkeypatch, "NO_RECENT_ARTICLES")
        fetcher.fetch_web_search_articles(["q"], keywords=[])
        assert "recent news articles (last 24 hours) about: q" in seen[0]
        assert "- Only include articles from the last 24 hours\n" in seen[0]
        assert "days" not in seen[0]

    def test_a_weekly_window_asks_for_the_week(self, monkeypatch):
        seen = _capture(monkeypatch, "NO_RECENT_ARTICLES")
        fetcher.fetch_web_search_articles(["q"], keywords=[], window_hours=168)
        assert "(last 7 days)" in seen[0]
        assert "last 24 hours" not in seen[0]

    def test_a_result_inside_the_asked_window_is_kept(self, monkeypatch):
        import datetime as dt
        five_days = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=5)).date().isoformat()
        _capture(monkeypatch, _BLOCK.format(date=five_days))
        assert fetcher.fetch_web_search_articles(["q"], keywords=[]) == []
        kept = fetcher.fetch_web_search_articles(["q"], keywords=[], window_hours=168)
        assert [a["title"] for a in kept] == ["A fleet story"]

    def test_a_window_under_a_day_is_a_day(self, monkeypatch):
        seen = _capture(monkeypatch, "NO_RECENT_ARTICLES")
        fetcher.fetch_web_search_articles(["q"], keywords=[], window_hours=0)
        assert "(last 24 hours)" in seen[0]


class TestZeroResultsMessage:
    def test_all_queries_answered_empty_is_not_an_outage(self, monkeypatch, caplog):
        _capture(monkeypatch, "NO_RECENT_ARTICLES")
        with caplog.at_level(logging.WARNING, logger="engine.fetcher"):
            assert fetcher.fetch_web_search_articles(["a", "b"], keywords=[]) == []
        text = " ".join(r.getMessage() for r in caplog.records)
        assert "ran but found nothing" in text
        assert "may be down" not in text
        assert not [r for r in caplog.records if r.levelno >= logging.ERROR]

    def test_calls_that_fail_are_still_an_error(self, monkeypatch, caplog):
        _capture(monkeypatch, RuntimeError("boom"))
        with caplog.at_level(logging.WARNING, logger="engine.fetcher"):
            assert fetcher.fetch_web_search_articles(["a", "b"], keywords=[]) == []
        assert any("may be down" in r.getMessage() and r.levelno == logging.ERROR
                   for r in caplog.records)

    def test_an_empty_reply_is_still_an_error(self, monkeypatch, caplog):
        _capture(monkeypatch, "")
        with caplog.at_level(logging.WARNING, logger="engine.fetcher"):
            fetcher.fetch_web_search_articles(["a"], keywords=[])
        assert any("may be down" in r.getMessage() for r in caplog.records)


DEAD_FEEDS = {
    "finansy_prosto": ["https://financialpost.com/category/personal-finance/feed/",
                       "https://nationalpost.com/category/news/economy/feed"],
    "modern_investing": ["https://financialpost.com/feed"],
    "models_agents": ["https://www.artificialintelligence-news.com/feed/"],
}


class TestDeadFeedsStayOut:
    @pytest.mark.parametrize("slug", sorted(DEAD_FEEDS))
    def test_dead_feed_is_not_live(self, slug):
        raw = (ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8")
        live = {s.get("url") for s in (yaml.safe_load(raw).get("sources") or []) if isinstance(s, dict)}
        for url in DEAD_FEEDS[slug]:
            assert url not in live, f"{url} returned nothing for weeks; restore it only with a URL that parsed"
            # Commented out with its evidence, not deleted, so the next
            # reader knows what the show used to read and why it stopped.
            assert f"# - url: {url}\n" in raw
