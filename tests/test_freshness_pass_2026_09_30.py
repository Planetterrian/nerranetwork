"""Network review, Sep 30 2026 — freshness, repetition and reproducibility.

The operator heard months-old stories aired as today's news and stories
told twice. The sweep of 09-16..30 found a 2013 Teslarati page aired three
times on Tesla, a 2021 Mashable story and a January-2025 Starlink deal on
SpaceX, a June article read as September on Tesla — every one behind an
UNDATED URL whose page carried its real date — and SpaceX telling a story
in Top News, the Deep Dive and the teaser after the digest dedupe had
removed its second copy. These guards pin the fixes:

* engine/article_dates.py — one owner for what an article's date is.
* engine/fetcher.py — undated is undated (never the run clock); a Google
  News feed date is an INDEX date; web-search results carry the model's
  date or none; X posts carry the model's date or none; the live X parser
  credits a linked article (the Sep 23 fix had shipped into a dead path).
* digests/xai_grok.py — a search request never falls back to answering
  from memory.
* engine/content_tracker.py — the URL-dedup window is the retention.
* engine/digest_overlap.py — a dropped duplicate's second telling leaves
  the combined script.
* scripts/grok_show_check.py — the health check reads the YAML floor.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import article_dates as ad  # noqa: E402
from engine.fetcher import (  # noqa: E402
    _parse_structured_blocks,
    _parse_x_posts,
    _parse_x_posts_multi,
    _x_post_entry,
    apply_x_source_policy,
    fetch_web_search_articles,
)
from engine.digest_overlap import (  # noqa: E402
    dedupe_cross_section_items,
    strip_second_tellings,
)

NOW = dt.datetime(2026, 9, 30, 12, 0, tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------------------
# engine/article_dates.py
# ---------------------------------------------------------------------------

class TestArticleDates:
    def test_a_date_token_is_the_end_of_that_day(self):
        when = ad.parse_date_token("2026-09-29")
        assert when is not None
        assert when.date() == dt.date(2026, 9, 29)
        assert when.hour == 23 and when.minute == 59

    def test_unknown_and_garbage_are_none(self):
        for raw in ("", "unknown", "none", "N/A", "yesterday", "09/29/2026"):
            assert ad.parse_date_token(raw) is None, raw

    def test_stamp_writes_empty_and_unknown_when_there_is_no_date(self):
        art = {"published_date": "2026-09-30T00:00:00+00:00"}
        ad.stamp(art, None, ad.DATE_SOURCE_MODEL)
        assert art["published_date"] == ""
        assert art["date_source"] == ad.DATE_SOURCE_UNKNOWN

    def test_empty_date_sorts_last_under_the_prompt_order(self):
        """run_show sorts the prompt newest-first on the string; "" must
        land last, never first (the run clock landed FIRST)."""
        arts = [
            {"published_date": ""},
            {"published_date": "2026-09-29T10:00:00+00:00"},
            {"published_date": "2026-09-30T08:00:00+00:00"},
        ]
        arts.sort(key=lambda a: a.get("published_date", ""), reverse=True)
        assert arts[-1]["published_date"] == ""

    def test_needs_probe_only_for_untrusted_openable_pages(self):
        assert ad.needs_probe({"url": "https://pub.example/story", "date_source": "index"})
        assert ad.needs_probe({"url": "https://pub.example/story", "date_source": "unknown"})
        assert ad.needs_probe({"url": "https://pub.example/story", "date_source": "model"})
        assert not ad.needs_probe({"url": "https://pub.example/story", "date_source": "feed"})
        assert not ad.needs_probe({"url": "https://pub.example/2026/09/29/x", "date_source": "url_path"})
        assert not ad.needs_probe({"url": "https://pub.example/story", "date_source": "index",
                                   "page_published_date": "2026-09-29T00:00:00+00:00"})
        assert not ad.needs_probe({"url": "https://x.com/a/status/1", "date_source": "unknown"})
        assert not ad.needs_probe({"url": "https://pub.example/s", "date_source": "unknown",
                                   "source_kind": "hook"})
        assert not ad.needs_probe({"url": "https://pub.example/s", "date_source": "unknown",
                                   "exempt_stale": True})

    def test_too_old_has_a_day_of_slack_and_never_fires_on_unknown(self):
        old = NOW - dt.timedelta(hours=72 + 24 + 1)
        fresh = NOW - dt.timedelta(hours=72 + 23)
        assert ad.too_old(old, max_age_hours=72, now=NOW)
        assert not ad.too_old(fresh, max_age_hours=72, now=NOW)
        assert not ad.too_old(None, max_age_hours=72, now=NOW)

    def test_probe_reads_the_page_date_and_replaces_the_index_date(self):
        html = ('<html><head><meta property="article:published_time" '
                'content="2021-05-09T14:00:00Z"></head><body></body></html>')
        arts = [
            {"url": "https://mashable.com/article/tenth-launch", "date_source": "index",
             "published_date": "2026-09-28T06:00:00+00:00", "title": "old"},
            {"url": "https://pub.example/fresh", "date_source": "feed",
             "published_date": "2026-09-29T06:00:00+00:00", "title": "fresh"},
        ]
        opened = []

        def fake_fetch(url):
            opened.append(url)
            return 200, html

        counters = ad.probe_page_dates(arts, max_probes=12, fetch=fake_fetch)
        assert opened == ["https://mashable.com/article/tenth-launch"]
        assert counters == {"candidates": 1, "probed": 1, "dated": 1}
        assert arts[0]["page_published_date"].startswith("2021-05-09")
        assert arts[0]["published_date"].startswith("2021-05-09")
        assert arts[0]["date_source"] == ad.DATE_SOURCE_PAGE
        assert arts[1]["published_date"].startswith("2026-09-29")

    def test_probe_leaves_an_undated_page_undated_and_is_bounded(self):
        arts = [{"url": f"https://pub.example/{i}", "date_source": "unknown",
                 "published_date": ""} for i in range(5)]
        calls = []

        def fake_fetch(url):
            calls.append(url)
            return 200, "<html><body>no date here</body></html>"

        counters = ad.probe_page_dates(arts, max_probes=3, fetch=fake_fetch)
        assert len(calls) == 3
        assert counters["dated"] == 0 and counters["candidates"] == 5
        assert all(a["published_date"] == "" for a in arts)
        assert ad.count_undated(arts) == 5

    def test_probe_survives_a_fetch_that_raises(self):
        arts = [{"url": "https://pub.example/x", "date_source": "unknown", "published_date": ""}]

        def boom(url):
            raise RuntimeError("403")

        assert ad.probe_page_dates(arts, fetch=boom)["dated"] == 0

    def test_the_probed_page_date_feeds_the_stale_gate(self):
        from engine.article_text import drop_stale_articles
        art = {"url": "https://mashable.com/article/tenth-launch", "date_source": "index",
               "published_date": "2026-09-28T06:00:00+00:00", "title": "old"}
        html = '<meta property="article:published_time" content="2021-05-09T14:00:00Z">'
        ad.probe_page_dates([art], fetch=lambda u: (200, html))
        kept, dropped = drop_stale_articles([art], max_age_days=3, now=NOW)
        assert dropped and not kept


# ---------------------------------------------------------------------------
# engine/fetcher.py — web search and X posts
# ---------------------------------------------------------------------------

_WEB_TEXT = """ARTICLE_TITLE: Fresh story
ARTICLE_URL: https://pub.example/news/fresh-story
ARTICLE_DESCRIPTION: Something happened today.
ARTICLE_SOURCE: Pub
ARTICLE_DATE: 2026-09-30

ARTICLE_TITLE: Old story the model dated
ARTICLE_URL: https://pub.example/news/old-story
ARTICLE_DESCRIPTION: Something happened in January.
ARTICLE_SOURCE: Pub
ARTICLE_DATE: 2025-01-06

ARTICLE_TITLE: Path-dated old story
ARTICLE_URL: https://pub.example/2021/05/09/tenth-launch
ARTICLE_DESCRIPTION: A booster flew a tenth time.
ARTICLE_SOURCE: Pub
ARTICLE_DATE: 2026-09-30

ARTICLE_TITLE: Undated story
ARTICLE_URL: https://pub.example/news/undated
ARTICLE_DESCRIPTION: No date anywhere.
ARTICLE_SOURCE: Pub
ARTICLE_DATE: unknown
"""


class TestWebSearchDates:
    def test_results_carry_the_date_they_came_with_and_old_ones_are_dropped(self, monkeypatch):
        monkeypatch.setenv("GROK_API_KEY", "test")
        with patch("digests.xai_grok.grok_generate_text", return_value=(_WEB_TEXT, {})):
            arts = fetch_web_search_articles(["q"])
        by_title = {a["title"]: a for a in arts}
        assert set(by_title) == {"Fresh story", "Undated story"}
        assert by_title["Fresh story"]["date_source"] == "model"
        assert by_title["Fresh story"]["published_date"].startswith("2026-09-30")
        assert by_title["Undated story"]["published_date"] == ""
        assert by_title["Undated story"]["date_source"] == "unknown"
        # Neither the model-dated January story nor the /2021/05/09/ path
        # reached the list, and nothing carries the run clock.
        assert not any(a["published_date"].startswith(dt.date.today().isoformat())
                       and a["date_source"] == "unknown" for a in arts)

    def test_the_prompt_asks_for_a_publication_date(self, monkeypatch):
        monkeypatch.setenv("GROK_API_KEY", "test")
        seen = {}

        def fake(prompt, **kw):
            seen["prompt"] = prompt
            return "NO_RECENT_ARTICLES", {}

        with patch("digests.xai_grok.grok_generate_text", side_effect=fake):
            fetch_web_search_articles(["q"])
        assert "ARTICLE_DATE" in seen["prompt"]
        assert "PUBLISHED" in seen["prompt"]


class TestXPostDates:
    RAW = (
        "POST_TITLE: BBC Africa on the election\n"
        "POST_TEXT: Results are in. https://bbc.com/news/africa-1\n"
        "POST_URL: https://x.com/BBCAfrica/status/1\n"
        "POST_LINK: https://www.bbc.com/news/articles/c1\n"
        "POST_DATE: 2026-09-23\n\n"
        "POST_TITLE: Old explainer re-shared\n"
        "POST_TEXT: Worth a read.\n"
        "POST_URL: https://x.com/BBCAfrica/status/2\n"
        "POST_LINK: https://www.bbc.com/news/2024/03/01/explainer\n"
        "POST_DATE: 2026-09-23\n\n"
        "POST_TITLE: Just a post\n"
        "POST_TEXT: Thoughts.\n"
        "POST_URL: https://x.com/BBCAfrica/status/3\n"
        "POST_LINK: none\n"
    )

    def test_the_live_parser_credits_the_linked_article(self):
        """fetch_x_posts -> _parse_x_posts_multi -> _parse_structured_blocks:
        the Sep 23 POST_LINK fix lived in _parse_x_posts, which that path
        never calls, so no post was ever x_linked in production."""
        posts = _parse_x_posts_multi(self.RAW, ["bbcafrica"], {"bbcafrica": "BBC Africa"}, "now")
        assert [p["x_linked"] for p in posts] == [True, False, False]
        assert posts[0]["url"] == "https://www.bbc.com/news/articles/c1"
        assert posts[0]["x_url"] == "https://x.com/BBCAfrica/status/1"
        assert posts[0]["source_name"] == "BBC Africa"
        assert posts[0]["source_kind"] == "x_post"
        assert all(p["source_kind"] == "x_post" for p in posts)

    def test_both_parsers_build_the_same_entry(self):
        a = _parse_structured_blocks(self.RAW, ["bbcafrica"], {"bbcafrica": "BBC Africa"}, "now")
        b = _parse_x_posts(self.RAW, "bbcafrica", "BBC Africa", "now")
        assert [(p["url"], p["x_linked"], p["published_date"]) for p in a] == \
               [(p["url"], p["x_linked"], p["published_date"]) for p in b]

    def test_a_post_carries_the_date_the_model_reported_or_none(self):
        posts = _parse_structured_blocks(self.RAW, ["bbcafrica"], {}, "now")
        assert posts[0]["published_date"].startswith("2026-09-23")
        assert posts[0]["date_source"] == "x_post"
        assert posts[2]["published_date"] == ""
        assert posts[2]["date_source"] == "unknown"

    def test_a_linked_article_dated_outside_the_window_is_not_credited(self):
        posts = _parse_structured_blocks(self.RAW, ["bbcafrica"], {}, "now")
        old = posts[1]
        assert old["x_linked"] is False
        assert old["url"] == "https://x.com/BBCAfrica/status/2"

    def test_linked_only_keeps_a_linked_post_on_the_live_path(self):
        posts = _parse_x_posts_multi(self.RAW, ["bbcafrica"], {}, "now")
        kept, dropped = apply_x_source_policy(posts, "linked_only")
        assert len(kept) == 1 and dropped == 2

    def test_the_prompt_asks_for_the_post_date(self):
        import inspect
        from engine import fetcher
        src = inspect.getsource(fetcher.fetch_x_posts)
        assert "POST_DATE" in src

    def test_entry_builder_never_stamps_the_run_clock(self):
        e = _x_post_entry(title="t", desc="d", url="https://x.com/a/status/9", link="",
                          post_date="", label="A", handle="a", now_iso="2026-09-30T00:00:00+00:00")
        assert e["published_date"] == ""


# ---------------------------------------------------------------------------
# engine/fetcher.py — feed entries (a Google News date is an index date)
# ---------------------------------------------------------------------------

class TestFeedEntryDates:
    def test_google_news_items_are_marked_index(self, monkeypatch):
        from unittest.mock import MagicMock
        from engine import fetcher

        from tests.test_fetcher import _make_entry, _make_feed

        published = (NOW - dt.timedelta(hours=2)).timetuple()
        entry = _make_entry(
            title="Story - Publisher", link="https://news.google.com/rss/articles/CBMi",
            description="d", published_parsed=published,
        )
        feed = _make_feed([entry], title="Google News")
        mock_fp = MagicMock()
        mock_fp.parse.return_value = feed

        resp = MagicMock()
        resp.content = b"<rss/>"
        resp.status_code = 200
        monkeypatch.setattr(fetcher.requests, "get", lambda *a, **k: resp)
        monkeypatch.setattr("engine.url_utils.resolve_google_news_url",
                            lambda u: "https://publisher.example/story")
        from threading import Lock
        with patch.dict(sys.modules, {"feedparser": mock_fp}):
            _, arts, _ = fetcher._fetch_single_feed(
                "https://news.google.com/rss/search?q=x", NOW - dt.timedelta(hours=24),
                None, set(), Lock(), label="Google News: x")
        assert len(arts) == 1
        assert arts[0]["date_source"] == "index"
        assert arts[0]["published_date"].startswith("2026-09-30")

    def test_the_source_kinds_are_the_module_constants(self):
        from engine import fetcher
        assert fetcher._DATE_SOURCE_INDEX == ad.DATE_SOURCE_INDEX
        assert fetcher._DATE_SOURCE_UNKNOWN == ad.DATE_SOURCE_UNKNOWN


# ---------------------------------------------------------------------------
# digests/xai_grok.py — no answer from memory for a search
# ---------------------------------------------------------------------------

class TestSearchNeverFallsBackToMemory:
    def test_a_failed_search_raises_instead_of_answering_without_tools(self, monkeypatch):
        import digests.xai_grok as xg
        monkeypatch.setenv("GROK_API_KEY", "test")
        chat_called = []

        def boom(client, **kw):
            raise RuntimeError("503")

        monkeypatch.setattr(xg, "_responses_create", boom)
        monkeypatch.setattr(xg, "_chat_create", lambda *a, **k: chat_called.append(1))
        with pytest.raises(xg.SearchUnavailable):
            xg.grok_generate_text(prompt="Search the web for the last 24 hours", enable_web_search=True)
        assert not chat_called, "the tool-less fallback ran for a search request"

    def test_plain_generation_still_uses_chat_completions(self, monkeypatch):
        import digests.xai_grok as xg
        from types import SimpleNamespace
        monkeypatch.setenv("GROK_API_KEY", "test")
        resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))], usage=None)
        monkeypatch.setattr(xg, "_chat_create", lambda *a, **k: resp)
        text, meta = xg.grok_generate_text(prompt="hello")
        assert text == "hi" and meta["provider"] == "openai_compat"

    def test_every_search_caller_catches_the_exception(self):
        """Grep-level guard: each site that asks for a search sits inside a
        try/except, so a raised SearchUnavailable is a logged fetch failure,
        never a crashed run."""
        import re
        sites = {
            ROOT / "engine" / "fetcher.py",
            ROOT / "engine" / "deep_dive_research.py",
            ROOT / "scripts" / "build_daily_edition.py",
            ROOT / "scripts" / "build_personal_feeds.py",
        }
        for path in sites:
            src = path.read_text(encoding="utf-8")
            for m in re.finditer(r"enable_(?:web|x)_search=True", src):
                # The call sits inside a try: a `try:` line opens within the
                # dozen lines above the argument, before any `except`.
                above = src[: m.start()].splitlines()[-40:]
                opened = [i for i, ln in enumerate(above) if ln.strip() == "try:"]
                closed = [i for i, ln in enumerate(above) if ln.strip().startswith("except")]
                assert opened and (not closed or max(closed) < max(opened)), (
                    f"{path.name}: a search call outside try/except near offset {m.start()}")


# ---------------------------------------------------------------------------
# engine/content_tracker.py + config — the URL window is the retention
# ---------------------------------------------------------------------------

class TestTrackerWindows:
    def test_defaults_declare_45_days_and_run_show_passes_it(self):
        defaults = yaml.safe_load((ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert defaults["content_tracking"]["max_days"] == 45
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'max_days=int(getattr(ct_cfg, "max_days"' in src

    def test_url_window_follows_retention(self, tmp_path):
        from engine.content_tracker import ContentTracker
        t = ContentTracker("t", tmp_path, max_days=45)
        t.load()
        t.data["episodes"].append({
            "date": (dt.date.today() - dt.timedelta(days=30)).isoformat(),
            "episode_num": 1,
            "headlines": ["Portable Solar Powered Electric Vehicle Charging Stations"],
            "urls": ["https://www.teslarati.com/portable-solar-powered-electric-vehicle-charging-stations/"],
        })
        arts = [{"title": "Portable solar EV charging stations, revisited",
                 "url": "https://www.teslarati.com/portable-solar-powered-electric-vehicle-charging-stations/"}]
        assert t.filter_recent_articles(arts, days=3) == []

    def test_x_posts_and_web_results_meet_the_tracker(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "filtered_x = content_tracker.filter_recent_articles(filtered_x)" in src
        assert "deduped_web = content_tracker.filter_recent_articles(deduped_web)" in src


class TestShowConfig:
    ESTABLISHED = ["tesla", "spacex", "models_agents", "models_agents_beginners",
                   "fascinating_frontiers", "planetterrian", "omni_view", "env_intel",
                   "modern_investing", "finansy_prosto", "mag7", "ai_chips"]

    @pytest.mark.parametrize("slug", ESTABLISHED)
    def test_established_news_shows_drop_anything_older_than_three_days(self, slug):
        from engine.config import load_config
        cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
        assert cfg.stale_article_days == 3, slug
        assert cfg.date_probe_max >= 12, slug

    def test_narrative_shows_are_untouched(self):
        from engine.config import load_config
        for slug in ("unintended_consequences", "first_principles"):
            assert load_config(ROOT / "shows" / f"{slug}.yaml").stale_article_days == 0

    def test_the_probe_can_be_switched_off_per_show(self, tmp_path):
        from engine.config import load_config
        base = yaml.safe_load((ROOT / "shows" / "tesla.yaml").read_text(encoding="utf-8"))
        base["date_probe_max"] = 0
        p = tmp_path / "tesla.yaml"
        p.write_text(yaml.safe_dump(base, allow_unicode=True), encoding="utf-8")
        with patch("engine.config.DEFAULTS_PATH", ROOT / "shows" / "_defaults.yaml", create=True):
            cfg = load_config(p)
        assert cfg.date_probe_max == 0

    def test_run_show_probes_before_the_stale_gate(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        probe = src.index("probe_page_dates(articles, max_probes=_probe_max)")
        gate = src.index('_stale_days = int(getattr(config, "stale_article_days", 0) or 0)')
        assert probe < gate
        for key in ("articles_date_probe_candidates", "articles_date_probed",
                    "articles_date_probe_dated", "articles_undated_in_prompt",
                    "articles_date_source_untrusted"):
            assert f'metrics.record("{key}"' in src, key


# ---------------------------------------------------------------------------
# engine/digest_overlap.py — the second telling leaves the combined script
# ---------------------------------------------------------------------------

_DIGEST = """# SpaceX Daily

### Top News
1. **xAI adds three waves of GB300 GPUs at Colossus** — Teslarati
   xAI is installing three waves of 220,000 GB300 GPUs, reaching 1.44 million accelerators by December. Source: https://teslarati.com/a

### Engineering Deep Dive
1. **Colossus expansion: three waves of GB300 GPUs** — Teslarati
   xAI is installing three waves of 220,000 GB300 GPUs, reaching 1.44 million accelerators by December. Source: https://teslarati.com/a
"""

_SCRIPT = (
    "Top story. xAI is installing three waves of two hundred twenty thousand GB300 GPUs, "
    "reaching one point four four million accelerators by December.\n\n"
    "Now the engineering deep dive. xAI is installing three waves of two hundred twenty "
    "thousand GB300 GPUs, reaching one point four four million accelerators by December. "
    "That is a lot of silicon.\n\n"
    "Before we go, watch for the three waves of GB300 GPUs reaching one point four four "
    "million accelerators by December.\n"
)


class TestSecondTellings:
    def test_a_dropped_duplicate_carries_its_body(self):
        result = dedupe_cross_section_items(_DIGEST)
        assert result.count == 1
        assert "1.44 million accelerators" in result.removed[0].body

    def test_only_the_later_tellings_leave_the_script(self):
        result = dedupe_cross_section_items(_DIGEST)
        script, n = strip_second_tellings(_SCRIPT, [d.body for d in result.removed])
        assert n == 2
        assert script.count("three waves") == 1
        assert script.startswith("Top story. xAI is installing three waves")
        assert "That is a lot of silicon." in script

    def test_nothing_to_match_is_a_no_op(self):
        assert strip_second_tellings(_SCRIPT, []) == (_SCRIPT, 0)
        assert strip_second_tellings("", ["x y z w v"]) == ("", 0)

    def test_short_sentences_are_never_judged(self):
        script = "GB300 GPUs by December.\nGB300 GPUs by December.\n"
        assert strip_second_tellings(script, ["xAI installs GB300 GPUs at Colossus by December"])[1] == 0

    def test_the_stash_can_be_amended_and_run_show_does_it(self):
        from engine import generator as g
        g._STASHED_COMBINED = {"script": "a", "digest": "d"}
        try:
            assert g.peek_combined_script() == "a"
            assert g.amend_combined_script("b") is True
            assert g.take_combined_script() == {"script": "b", "digest": "d"}
            assert g.amend_combined_script("c") is False
        finally:
            g._STASHED_COMBINED = None
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "strip_second_tellings(" in src
        assert 'metrics.record("combined_script_second_tellings_removed"' in src


# ---------------------------------------------------------------------------
# scripts/grok_show_check.py — the health check reads the YAML floor
# ---------------------------------------------------------------------------

class TestHealthCheckFloor:
    def test_tesla_is_judged_against_its_configured_floor(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import importlib
        m = importlib.import_module("grok_show_check")
        from engine.config import load_config
        floor = load_config(ROOT / "shows" / "tesla.yaml").llm.min_podcast_words
        assert m._config_word_floor("tesla") == floor
        # 1,316 words on a 1,400 floor is "below target", not "66% of target".
        res = m.check_word_count("word " * 1316, "tesla")
        assert res["floor"] == floor
        assert [f["type"] for f in res["findings"]] == ["below_target_length"]
