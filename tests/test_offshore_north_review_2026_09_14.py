"""Drift guards for the Offshore North review of 14 September 2026.

Review: docs/reviews/offshore_north_review_2026_09_14.md. The operator's
fix list (12 items) plus the two defects the review found on its own:
Ep005 aired a race START as its RESULT (a team-malizia.com headline
re-surfaced by Google News after the race had finished with a different
winner), and every episode said the boat's position was "unconfirmed"
while the team's own post said where it was going.

Root cause of both: the digest prompt saw headline + one-line teaser +
URL and never the article. These guards pin the full-text layer, the
Scott's Notes feed, the prompt rules, the cadence-aware blog footer, and
the campaign dashboard.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.config import load_config  # noqa: E402

_SHOW_YAML = _ROOT / "shows" / "offshore_north.yaml"
_PROMPTS = _ROOT / "shows" / "prompts"


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _digest():
    return _read("shows/prompts/offshore_north_digest.txt")


def _podcast():
    return _read("shows/prompts/offshore_north_podcast.txt")


def _system():
    return _read("shows/prompts/offshore_north_system.txt")


def _facts():
    return _read("shows/prompts/offshore_north_standing_facts.txt")


# ---------------------------------------------------------------------------
# Fix 1 — read the article, not the index
# ---------------------------------------------------------------------------

class TestFullTextLayer:
    # Deliberate opt-ins, by name. The four Sep 2026 new shows joined after
    # their Episode 1 digests were written from feed teasers (Ep1 review,
    # tests/test_new_shows_ep1_review_2026_09_22.py).
    _FULL_TEXT_OPT_INS = frozenset({
        "offshore_north", "ai_chips", "mag7", "peptides", "longevity"})

    def test_show_opts_in_and_every_other_show_is_untouched(self):
        cfg = load_config(str(_SHOW_YAML))
        assert cfg.fetch_full_text >= 8, "Offshore North must open its articles"
        assert cfg.fetch_full_text_chars >= 1500
        offenders = []
        for path in sorted((_ROOT / "shows").glob("*.yaml")):
            if path.stem.startswith("_") or path.stem in self._FULL_TEXT_OPT_INS:
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict) and data.get("fetch_full_text"):
                offenders.append(path.stem)
        assert not offenders, f"full-text is opt-in; these shows gained it: {offenders}"

    def test_dataclass_default_is_off(self):
        from engine.config import ShowConfig

        assert ShowConfig().fetch_full_text == 0

    def test_extractor_prefers_article_prose_and_drops_chrome(self):
        from engine.article_text import extract_article_text

        html = """<html><head><script type="application/ld+json">{"x":"NOT PROSE"}</script>
        <style>.a{}</style></head><body><nav><a href="/">Home</a></nav>
        <div class="elementor-widget"><article><h1>Thank you, Canada</h1>
        <p>With Emira IV now leaving Canada and heading back to Europe, Scott looks back on a summer spent getting to know the boat.</p>
        <p>Scott has sailed on Lake Huron for over 40 years, so the conditions themselves held few surprises.</p>
        <div class="share-row"><p>Share this post on your socials today!</p></div>
        </article></div><footer><p>Copyright notice that is long enough to look like a sentence.</p></footer></body></html>"""
        text = extract_article_text(html)
        assert "heading back to Europe" in text
        assert "Lake Huron" in text
        assert "NOT PROSE" not in text
        assert "Share this post" not in text
        assert "Copyright" not in text

    def test_page_builder_wrapper_does_not_eat_the_article(self):
        """The first cut decomposed every 'widget'-classed div and reduced an
        Elementor page to 'Skip to content'."""
        from engine.article_text import extract_article_text

        body = " ".join(["This is a real paragraph of the article about the boat and the summer."] * 6)
        html = f'<html><body><div class="elementor-widget elementor-widget-theme-post-content"><p>{body}</p></div></body></html>'
        assert "real paragraph" in extract_article_text(html)

    def test_enrichment_prefers_campaign_feeds_and_feed_bodies(self):
        from engine.article_text import enrich_articles_with_full_text

        arts = [
            {"title": "press", "description": "short", "url": "https://x.example/1", "source_name": "Sail-World"},
            {"title": "team", "description": "short", "url": "https://x.example/2",
             "source_name": "Canada Ocean Racing — Scott's Notes",
             "content_text": "Body from the feed. " * 40},
            {"title": "press2", "description": "short", "url": "https://x.example/3", "source_name": "Sailorz"},
        ]
        calls = []

        def fake_fetch(url):
            calls.append(url)
            return 200, "<html><body><article><p>" + ("Fetched article prose sentence. " * 30) + "</p></article></body></html>"

        n = enrich_articles_with_full_text(arts, max_articles=2, max_chars=500, priority_sources=["Canada Ocean Racing — Scott's Notes"], fetch=fake_fetch)
        assert n == 2
        assert arts[1]["full_text_source"] == "feed"       # campaign first, no HTTP
        assert arts[0]["full_text_source"] == "page"       # then list order
        assert "full_text" not in arts[2]                  # budget respected
        assert calls == ["https://x.example/1"]
        assert len(arts[1]["full_text"]) <= 520

    def test_enrichment_never_raises(self):
        from engine.article_text import enrich_articles_with_full_text

        arts = [{"title": "t", "description": "", "url": "https://x.example/boom", "source_name": "S"}]

        def boom(url):
            raise RuntimeError("network down")

        assert enrich_articles_with_full_text(arts, max_articles=1, fetch=boom) == 0
        assert "full_text" not in arts[0]

    def test_run_show_renders_full_text_under_the_headline(self):
        src = _read("run_show.py")
        assert 'getattr(config, "fetch_full_text", 0)' in src
        assert "enrich_articles_with_full_text(" in src
        assert "render_full_text_block(art)" in src
        assert 'metrics.record("articles_full_text"' in src

    def test_fetcher_stores_feed_bodies(self):
        import feedparser
        from engine.fetcher import _entry_body_text

        feed = feedparser.parse(
            '<?xml version="1.0"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">'
            "<channel><item><title>T</title><link>https://x.example/p</link>"
            "<description>teaser only</description>"
            "<content:encoded><![CDATA[<p>Full body paragraph one about the boat.</p><p>Paragraph two with the position: leaving Canada and heading back to Europe.</p>]]></content:encoded>"
            "</item></channel></rss>"
        )
        text = _entry_body_text(feed.entries[0])
        assert "heading back to Europe" in text and "<p>" not in text

    def test_digest_and_system_prompts_carry_the_read_the_body_rule(self):
        assert "READ THE ARTICLE, NOT THE HEADLINE" in _digest()
        assert "FULL TEXT" in _digest()
        assert "Read the article, not the headline" in _system()


# ---------------------------------------------------------------------------
# Fix 2 — Scott's Notes
# ---------------------------------------------------------------------------

class TestScottsNotesSource:
    def test_category_feed_wired_and_flagged(self):
        raw = yaml.safe_load(_SHOW_YAML.read_text(encoding="utf-8"))
        hits = [s for s in raw["sources"] if "scotts-blog/feed" in s["url"]]
        assert len(hits) == 1, "Scott's Notes category feed missing"
        assert hits[0].get("freshness_report") is True
        assert "Scott" in hits[0]["label"]

    def test_yaml_explains_why_the_page_urls_are_not_feeds(self):
        text = _SHOW_YAML.read_text(encoding="utf-8")
        assert "/scott-notes/" in text and "COMMENTS feed" in text


# ---------------------------------------------------------------------------
# Fixes 3-10 — the editorial rules
# ---------------------------------------------------------------------------

class TestEditorialRules:
    def test_position_report_is_last_known_plus_date_never_unconfirmed(self):
        d, p, s = _digest(), _podcast(), _system()
        for src, name in ((d, "digest"), (p, "podcast"), (s, "system")):
            assert "unconfirmed" in src, f"{name}: the banned word must be named"
        assert "LAST KNOWN position" in d
        assert "the DATE of that fix" in d
        assert "date of that fix" in p
        assert "canadaoceanracing.com/follow/" in d

    def test_report_what_not_when(self):
        assert "What it said" in _digest()
        assert 'NEVER WRITE A "LAST UPDATED" SENTENCE' in _digest()
        assert "not when the website changed" in _podcast()
        assert "Report WHEN a channel was updated instead of WHAT" in _system()

    def test_freshness_block_carries_an_excerpt(self):
        import feedparser
        from engine.fetcher import _freshness_excerpt, FRESHNESS_EXCERPT_CHARS

        feed = feedparser.parse(
            '<?xml version="1.0"?><rss version="2.0"><channel><item><title>T</title>'
            "<link>https://x.example/p</link><description>"
            + ("Sentence about the boat. " * 80)
            + "</description></item></channel></rss>"
        )
        ex = _freshness_excerpt(feed.entries[0])
        assert ex.startswith("Sentence about the boat.")
        assert len(ex) <= FRESHNESS_EXCERPT_CHARS + 4
        src = _read("engine/fetcher.py")
        assert "What it said:" in src

    def test_standings_are_cut(self):
        assert "STANDINGS ARE NOT CONTENT" in _digest()
        assert "roll-call" in _digest() and "roll-call" in _podcast()
        assert "NO STANDINGS" in _podcast()
        assert "skipper-and-position roll-call" in _system()

    def test_canadian_boat_leads_and_is_longest(self):
        d, p = _digest(), _podcast()
        assert "LEAD AND THE LONGEST" in d
        assert "FIRST SEGMENT AND THE LONGEST" in p
        # Fleet word budget now sits below the Canadian Boat's.
        cb = re.search(r"THE FIRST SEGMENT AND THE LONGEST: (\d+)–(\d+) words", p)
        fl = re.search(r"\[The Fleet\].*?About (\d+)–(\d+) words", p, re.S)
        assert cb and fl
        assert int(cb.group(1)) > int(fl.group(2)) - 100 and int(cb.group(2)) > int(fl.group(2))

    def test_incidents_not_leaderboards(self):
        assert "INCIDENTS, NOT LEADERBOARDS" in _digest()
        assert "INCIDENTS, NOT LEADERBOARDS" in _podcast()
        assert "ONE PERSON sailing alone" in _digest()

    def test_standing_facts_never_spoken_and_pedigree_rationed(self):
        p, d, s = _podcast(), _digest(), _system()
        assert 'NEVER SPEAK THE WORDS "standing facts", "standing item"' in p
        assert "**Standing item:**" not in d, "the old writer label was spoken on air"
        assert "writer-only label — never spoken" in d  # Dan's lens keeps its label
        assert "NO BACKGROUND BLOCK, NO LABELS" in d  # round 1 (Sep 18): the block is gone
        assert "at most once in any four-week span" in _facts()
        assert 'Say "standing facts", "standing item"' in s

    def test_plain_sailing_is_evergreen(self):
        assert "EVERGREEN, OR IT IS NOT PLAIN SAILING" in _digest()
        assert "EVERGREEN:" in _podcast()
        assert "useful in a year" in _system()

    def test_dan_is_required_once_per_episode(self):
        p, s, d = _podcast(), _system(), _digest()
        assert "REQUIRED: EXACTLY ONE personal reference per episode" in p
        assert "never zero" in p
        assert "at most ONE personal reference" not in p
        assert "exactly ONE personal reference per episode, required" in s
        assert "Dan's lens" in d and "Dan's lens" in p

    def test_race_finish_outranks_a_resurfaced_start(self):
        assert "A finish inside this week's window outranks every earlier report" in _digest()
        assert "MANDATORY item and leads The Fleet" in _digest()
        assert "aired a race START as its RESULT" in _facts()
        assert "United by the Ocean (Paul Meilhat) won" in _facts()

    def test_standing_facts_refreshed(self):
        f = _facts()
        # the verification date moves with each pass (19 Sep 2026 onward);
        # the guard is that it is dated, not what day it says
        assert re.search(r"\*\*Last verified:\*\* \d{1,2} [A-Z][a-z]+ 20\d\d", f)
        assert "CAN 80" in f
        assert "heading back to Europe" in f
        assert "Entry CONFIRMED" in f
        assert "118 skippers" in f
        guide = _read("shows/prompts/offshore_north_field_guide.txt")
        assert "118 solo skippers" in guide
        assert "Scott Shawyer is entered" in guide
        assert "Won by United by the Ocean" in guide
        assert "Ambrogio Beccaria" in guide

    def test_includes_still_render(self):
        from engine.generator import load_prompt

        for name in ("offshore_north_digest.txt", "offshore_north_podcast.txt"):
            text = load_prompt(str(_PROMPTS / name))
            assert "<<include" not in text
            assert "{" + "campaign_freshness" + "}" in text or "{digest}" in text


# ---------------------------------------------------------------------------
# Fix 11 — original URLs
# ---------------------------------------------------------------------------

class TestOriginalUrls:
    def test_no_published_digest_carries_an_aggregator_or_index_url(self):
        for md in sorted((_ROOT / "digests" / "offshore_north").glob("Offshore_North_Ep*.md")):
            text = md.read_text(encoding="utf-8")
            assert "news.google.com" not in text, md.name

    def test_sources_spec_bans_redirects_and_index_pages(self):
        d = _digest()
        assert "never a Google News redirect" in d
        assert "never an index page" in d


# ---------------------------------------------------------------------------
# Fix 12 — the footer
# ---------------------------------------------------------------------------

class TestCadenceAwareFooter:
    def test_placeholder_copy_follows_the_schedule(self):
        from engine.blog import next_episode_placeholder as n

        assert n("Daily")["title"] == "New episode tomorrow"
        assert n("Weekly — Mondays")["title"] == "New episode Monday"
        assert "tomorrow" not in n("Weekly — Mondays")["title"].lower()
        assert "tomorrow" not in n("Odd weekdays")["title"].lower()
        assert "tomorrow" not in n("When an interview is ready")["title"].lower()
        assert n("", is_ru=True)["title"]

    def test_template_uses_the_context_not_a_literal(self):
        tpl = _read("templates/blog_post.html.j2")
        assert "next_episode_nav" in tpl
        assert ">New episode tomorrow<" not in tpl

    def test_blog_context_carries_it(self):
        assert '"next_episode_nav": next_episode_placeholder(' in _read("engine/blog.py")

    def test_published_latest_post_says_monday(self):
        posts = sorted((_ROOT / "blog" / "offshore_north").glob("ep*.html"))
        if not posts:
            return
        html = posts[-1].read_text(encoding="utf-8")
        if "nav-next-placeholder" in html:
            assert "New episode Monday" in html
            assert "New episode tomorrow" not in html


# ---------------------------------------------------------------------------
# The campaign dashboard
# ---------------------------------------------------------------------------

class TestCampaignDashboard:
    def test_curated_data_is_dated_and_sourced(self):
        d = json.loads(_read("site/data/offshore_north_dashboard.json"))
        assert d["last_verified"] >= "2026-09-14"
        assert d["campaign"]["boat"]["sail_number"] == "CAN 80"
        for fix in d["position_log"]:
            assert fix["date"] and fix["url"].startswith("https://"), fix
        assert any("heading back to Europe" in f["text"] for f in d["position_log"])
        primary = [c for c in d["countdowns"] if c.get("primary")]
        assert len(primary) == 1 and primary[0]["when"].startswith("2026-11-01T13:02")
        assert any(e.get("canada") for e in d["rdr_imoca_entries"]["entries"])
        groups = {g["group"] for g in d["follow"]}
        assert "The campaign" in groups and "Class and race organisers" in groups
        links = [l["url"] for g in d["follow"] for l in g["links"]]
        assert "https://www.canadaoceanracing.com/scott-notes/" in links
        assert "https://www.canadaoceanracing.com/follow/" in links
        assert all(u.startswith("https://") for u in links)

    def test_fetch_script_shapes(self):
        sys.path.insert(0, str(_ROOT / "scripts"))
        import fetch_offshore_north_dashboard as m

        posts = [
            {"channel": "Canada Ocean Racing — Scott's Notes", "title": "Thank you, Canada", "url": "https://x/1", "date": "2026-09-02",
             "excerpt": "For Scott Shawyer, skipper and president…", "_body": "Intro. With Emira IV now leaving Canada and heading back to Europe, Scott looks back. More."},
            {"channel": "Canada Ocean Racing — YouTube", "title": "Welland Canal transit", "url": "https://x/2", "date": "2026-08-31", "excerpt": "How do you get a 60ft IMOCA through the Welland Canal?"},
        ]
        pos = m.derive_position(posts)
        assert pos["date"] == "2026-09-02"
        assert "heading back to Europe" in pos["text"]
        assert pos["url"] == "https://x/1"
        assert m._HEADLINE_KEYWORDS_RE.search("The Ocean Race Atlantic: testing at every level")
        assert not m._HEADLINE_KEYWORDS_RE.search("Maxi Yacht Rolex Cup — the ultimate regatta")
        feeds = m._campaign_feeds()
        assert any("scotts-blog" in f["url"] for f in feeds)

    def test_live_cache_committed_and_position_derived(self):
        d = json.loads(_read("api/offshore_north_dashboard.json"))
        assert d["campaign_posts"] and d["headlines"]
        assert d["position"] and d["position"]["date"] and d["position"]["url"]

    def test_page_renders_and_is_wired(self):
        import generate_html as g

        g.generate_offshore_north_dashboard(dry_run=True)
        gh = _read("generate_html.py")
        assert gh.count("generate_offshore_north_dashboard(dry_run=args.dry_run)") >= 3  # per-show, --all, --network
        assert '"offshore-north-dashboard.html"' in gh  # sitemap
        assert "offshore-north-dashboard.html" in _read("templates/show_page.html.j2")
        assert "offshore-north-dashboard.html" in _read("templates/data_hub.html.j2")
        tpl = _read("templates/offshore_north_dashboard.html.j2")
        assert "api/offshore_north_dashboard.json" in tpl
        assert "my.yb.tl/emira4" in tpl or "tracker_embed_url" in tpl

    def test_workflows_commit_the_data_and_the_page(self):
        nightly = _read(".github/workflows/nightly-maintenance.yml")
        assert "fetch_offshore_north_dashboard.py" in nightly
        assert "offshore-north-dashboard.html" in nightly
        assert "api/offshore_north_dashboard.json" in nightly
        assert "api/offshore_north_dashboard.json" in _read(".github/workflows/run-show.yml")
        assert "_refresh_dashboard_data" in _read("shows/hooks/offshore_north.py")

    def test_generated_page_exists_with_the_position(self):
        page = _ROOT / "offshore-north-dashboard.html"
        assert page.exists()
        html = page.read_text(encoding="utf-8")
        assert "heading back to Europe" in html
        assert "Route du Rhum" in html and "Follow the sport" in html
