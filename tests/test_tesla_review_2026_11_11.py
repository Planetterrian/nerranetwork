"""Nov 11 2026 — the Tesla Shorts Time review's quick fixes.

Review: https://claude.ai/artifact/4txxbgJ53fj9FnaZ8CTdNb (Ep637-661).
1. Publishers the show never cites (``exclude_sources``), matched on the URL
   host or the whole Google News publisher label — never a substring.
2. The blog never prints an empty section, the X Takeover's template intro
   line, or the digest's "Sign-off:" label (Ep661 printed all three).
3. Tesla reads its primary X accounts and fires ``deep_dive_distinct``.
4. @teslashortstime posts the clip, naming the show, not the network, and
   the queue workflow carries its credentials.
"""
from __future__ import annotations

import datetime
from pathlib import Path

from engine.blog import clean_digest_for_blog, drop_empty_sections
from engine.config import load_config
from engine.utils import drop_excluded_titles, is_excluded_source
from engine.x_post import clip_post_text, post_closers

ROOT = Path(__file__).resolve().parent.parent


class TestExcludeSources:
    def test_domain_matches_host_and_subdomain(self):
        assert is_excluded_source({"url": "https://shattered.io/a"}, ["shattered.io"])
        assert is_excluded_source({"url": "https://www.basenor.com/b"}, ["basenor.com"])
        assert is_excluded_source({"url": "https://finance.biggo.com/x"}, ["biggo.com"])

    def test_domain_never_matches_a_lookalike_host(self):
        assert not is_excluded_source({"url": "https://notshattered.io/a"}, ["shattered.io"])

    def test_google_news_label_matches_whole(self):
        art = {"url": "https://news.google.com/rss/articles/x",
               "source_name": "https://tech-insider.org/"}
        assert is_excluded_source(art, ["tech-insider.org"])
        art = {"url": "https://news.google.com/rss/articles/y",
               "source_name": "BASENOR - Tesla Accessories"}
        assert is_excluded_source(art, ["BASENOR - Tesla Accessories"])

    def test_a_name_is_never_a_substring(self):
        art = {"url": "https://www.reddit.com/r/electricvehicles/x",
               "source_name": "r/electricvehicles"}
        assert not is_excluded_source(art, ["Electric Vehicles"])

    def test_drop_runs_with_no_title_patterns(self):
        arts = [{"title": "a", "url": "https://shattered.io/1"},
                {"title": "b", "url": "https://electrek.co/2"}]
        kept, n = drop_excluded_titles(arts, [], sources=["shattered.io"])
        assert n == 1 and [a["title"] for a in kept] == ["b"]

    def test_unset_is_a_no_op(self):
        arts = [{"title": "a", "url": "https://shattered.io/1"}]
        assert drop_excluded_titles(arts, [])[1] == 0


class TestEmptySections:
    EP661_TAIL = (
        "### Also Today\n**Item:** Outlet\nA fact. Source: [x.com](https://x.com/a)\n\n"
        "## Tesla X Takeover: What's Hot Right Now\n"
        "Tesla X Takeover - What's breaking in the Tesla world today! Here are the "
        "most interesting, fresh Tesla developments that have everyone talking.\n\n"
        "## Short Spot\n\n### Tesla First Principles\nThe essay.\n\n"
        "Sign-off: Share your thoughts on X at [@teslashortstime](https://x.com/teslashortstime).\n"
    )

    def test_ep661_shape(self):
        out = clean_digest_for_blog(self.EP661_TAIL)
        assert "Tesla X Takeover" not in out
        assert "Short Spot" not in out
        assert "Sign-off" not in out
        assert "### Tesla First Principles" in out and "The essay." in out
        assert "Share your thoughts on X" in out

    def test_a_section_with_items_stays(self):
        md = "## Short Spot\nA bearish item. Source: [a](https://a.com)\n\n## Next\nx"
        assert "## Short Spot" in drop_empty_sections(md)

    def test_a_parent_of_sub_headings_stays(self):
        md = "## Top Stories\n\n### 1. A story\nBody."
        assert "## Top Stories" in drop_empty_sections(md)

    def test_an_empty_heading_at_the_end_goes(self):
        assert drop_empty_sections("Body.\n\n### Progress Watch\n").strip() == "Body."


class TestTeslaConfig:
    def _cfg(self):
        return load_config(ROOT / "shows" / "tesla.yaml")

    def test_primary_x_accounts(self):
        handles = {a.handle.lower() for a in self._cfg().x_accounts}
        assert {"elonmusk", "tesla", "tesla_ai", "tesla_optimus", "teslaenergy"} <= handles

    def test_content_farms_excluded(self):
        assert {"tech-insider.org", "shattered.io", "basenor.com"} <= set(self._cfg().exclude_sources)

    def test_deep_dive_distinct_fires(self):
        lints = self._cfg().digest_lints
        assert "deep_dive_distinct" in lints and "deep_dive_distinct_measure" in lints

    def test_posts_the_clip_on_its_own_account(self):
        pub = self._cfg().publishing
        assert pub.x_post_format == "clip" and pub.x_env_prefix == "X_"


class TestOwnAccountClip:
    def test_the_closer_names_the_show(self):
        closers = post_closers("tesla", datetime.date(2026, 11, 11))
        assert closers and all("Tesla Shorts Time" in c and "Nerra" not in c for c in closers)
        text = clip_post_text(label="Tesla Shorts Time", hook="Tesla began earthworks.",
                              episode_num=662, closers=closers)
        assert text.endswith("search Tesla Shorts Time in any podcast app.")

    def test_the_queue_workflow_carries_the_tesla_credentials(self):
        wf = (ROOT / ".github" / "workflows" / "x-queue.yml").read_text(encoding="utf-8")
        for key in ("X_CONSUMER_KEY", "X_CONSUMER_SECRET", "X_ACCESS_TOKEN",
                    "X_ACCESS_TOKEN_SECRET"):
            assert f"  {key}: ${{{{ secrets.{key} }}}}" in wf, key


class TestShowPageCopy:
    def test_no_fifteen_minutes_and_no_shorting_tagline(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        start = src.index('"x_account": "teslashortstime"')
        block = src[start:start + 2500]
        assert '"tagline": "Shorting' not in block
        assert '"hero_tagline": "Shorting' not in block
        assert '"episode_length": "~10 min"' in block
