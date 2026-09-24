"""Launch-cohort follow-ups (2026-09-23, after PRs A/B/C): the published Ep1
citations that credited x.com are re-sourced to the articles the posts
linked, two dead LatAm feeds are replaced, and ``preferred_domains`` exists.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COHORT = (
    "ai_chips", "mag7", "peptides", "longevity", "prediction_markets",
    "vancouver", "collingwood", "omni_view_europe", "omni_view_asia_pacific",
    "omni_view_africa_mideast", "omni_view_latam", "omni_view_north_america",
    "omni_view_world",
)


def _latest_digest(slug: str) -> Path | None:
    d = ROOT / "digests" / slug
    hits = sorted(p for p in d.glob("*_Ep*.md") if "_reader" not in p.name)
    return hits[-1] if hits else None


#: x.com Source lines the 2026-09-23 re-source pass could not resolve (the
#: posts linked nothing, or linked a listing page): AI Chips Ep2 4,
#: Vancouver Ep1 3, Arab News's Gaza post 1. Committed digests only.
X_ONLY_LINES_LEFT_AFTER_RESOURCE = 8


def _cohort_digests():
    """The launch-week digests (2026-09-22/23) — the committed record."""
    for slug in COHORT:
        for p in sorted((ROOT / "digests" / slug).glob("*_Ep*.md")):
            if "_reader" in p.name:
                continue
            m = re.search(r"_(\d{8})\.md$", p.name)
            if m and m.group(1) in ("20260922", "20260923"):
                yield slug, p


# ---------------------------------------------------------------- D1: re-source

class TestResourceScript:
    def test_payload_parser_skips_self_links_and_keeps_order(self):
        from scripts.resource_x_citations import outbound_links_from_payload
        payload = {"entities": {"urls": [
            {"expanded_url": "https://x.com/BBCAfrica/status/1"},
            {"expanded_url": "https://bbc.in/4ydkMjN"},
            {"expanded_url": "https://t.co/abc"},
            {"expanded_url": "https://aje.news/res2p0"},
        ]}}
        assert outbound_links_from_payload(payload) == ["https://bbc.in/4ydkMjN", "https://aje.news/res2p0"]

    def test_tracking_params_are_stripped(self):
        from scripts.resource_x_citations import strip_tracking
        url = ("https://www.bbc.com/news/articles/crgjqxzl097eo?at_medium=social"
               "&at_link_origin=BBCAfrica&utm_source=x&ito=123&page=2#top")
        assert strip_tracking(url) == "https://www.bbc.com/news/articles/crgjqxzl097eo?page=2"

    def test_rewrite_uses_the_domain_label_shape(self):
        from scripts.resource_x_citations import rewrite_text
        text = ("Eleven people were killed. Source: [x.com](https://x.com/BBCAfrica/status/111)\n"
                "A second item. Source: [x.com](https://x.com/arabnews/status/222)\n"
                "A kept one. Source: [x.com](https://x.com/someone/status/333)\n")
        out, n = rewrite_text(text, {"111": "https://www.bbc.com/news/articles/a1",
                                     "222": "https://www.arabnews.com/node/9"})
        assert n == 2
        assert "Source: [bbc.com](https://www.bbc.com/news/articles/a1)" in out
        assert "Source: [arabnews.com](https://www.arabnews.com/node/9)" in out
        assert "Source: [x.com](https://x.com/someone/status/333)" in out

    def test_dry_run_writes_nothing(self, tmp_path, monkeypatch):
        import scripts.resource_x_citations as mod
        show = tmp_path / "digests" / "demo"
        show.mkdir(parents=True)
        digest = show / "Demo_Ep001_20260923.md"
        digest.write_text("Item. Source: [x.com](https://x.com/h/status/5)\n", encoding="utf-8")
        (show / "summaries_demo.json").write_text(
            '{"summaries": [{"episode_num": 1, "content": "Item. Source: [x.com](https://x.com/h/status/5)"}]}',
            encoding="utf-8")
        monkeypatch.setattr(mod, "ROOT", tmp_path)
        rows = mod.process_show("demo", None, apply=False, resolver=lambda sid: "https://pub.example/a")
        assert rows and rows[0]["ok"]
        assert "x.com" in digest.read_text(encoding="utf-8")
        rows = mod.process_show("demo", None, apply=True, resolver=lambda sid: "https://pub.example/a")
        assert "Source: [pub.example](https://pub.example/a)" in digest.read_text(encoding="utf-8")
        assert "pub.example" in (show / "summaries_demo.json").read_text(encoding="utf-8")

    def test_listing_pages_are_not_citations(self):
        from scripts.resource_x_citations import is_listing_page
        assert is_listing_page("https://backup.arabnews.com/tags/gaza-war")
        assert is_listing_page("https://www.example.com/topics/energy/")
        assert not is_listing_page("https://www.arabnews.com/middle-east/first-cohort-3002728")
        assert not is_listing_page("https://www.bbc.com/news/articles/crgjqxzl097eo")

    def test_the_committed_record_is_re_sourced(self):
        """The launch-week digests: no Lead sourced only to x.com; the x.com
        Source lines that remain are the posts with no outbound link (a
        ratchet — the count can fall, never rise back); every show's latest
        digest gives the blog page a real Sources list."""
        from engine.blog import _extract_source_urls
        from engine.digest_lint import x_only_lead_items
        remaining = 0
        for slug, p in _cohort_digests():
            text = p.read_text(encoding="utf-8")
            assert not x_only_lead_items(text), (slug, p.name)
            remaining += text.count("Source: [x.com]")
        assert remaining <= X_ONLY_LINES_LEFT_AFTER_RESOURCE, remaining
        for slug in COHORT:
            p = _latest_digest(slug)
            assert p is not None, slug
            urls = _extract_source_urls(p.read_text(encoding="utf-8"))
            assert len(urls) >= 3, (slug, p.name, urls)

    def test_africa_ep1_names_its_publishers(self):
        p = ROOT / "digests/omni_view_africa_mideast/Omni_View_Africa_Mideast_Ep001_20260923.md"
        text = p.read_text(encoding="utf-8")
        # 5 of 6 resolved; the Arab News Gaza post linked a tag page on a
        # mirror host, which is not a citation, so that item keeps x.com.
        assert text.count("Source: [x.com]") <= 1
        lead = text.split("### Lead", 1)[1].split("###", 1)[0]
        assert "Source: [bbc.com](https://www.bbc.com/news/articles/" in lead
        assert "aljazeera.com" in text and "arabnews.com" in text


# ---------------------------------------------------------------- D2: feeds

class TestFeedHygiene:
    def test_latam_dead_feeds_replaced(self):
        cfg = yaml.safe_load((ROOT / "shows/omni_view_latam.yaml").read_text(encoding="utf-8"))
        urls = [s["url"] for s in cfg["sources"]]
        assert "https://oglobo.globo.com/rss/oglobo/" in urls
        assert "https://oglobo.globo.com/rss/oglobo" not in urls  # 200 with zero items
        assert "https://www.infobae.com/arc/outboundfeeds/rss/category/america/" in urls
        assert "https://www.infobae.com/feeds/rss/" not in urls  # 404

    def test_tico_times_replaced_and_simcoe_dropped(self):
        # check_feeds.py 2026-09-23: ticotimes.net/feed returned zero entries
        # (qcostarica.com/feed/ carries 10); simcoe.ca/rss is a 307 loop with
        # no RSS behind it — CollingwoodToday covers the county's council.
        latam = yaml.safe_load((ROOT / "shows/omni_view_latam.yaml").read_text(encoding="utf-8"))
        urls = [s["url"] for s in latam["sources"]]
        assert "https://qcostarica.com/feed/" in urls and not any("ticotimes" in u for u in urls)
        cw = yaml.safe_load((ROOT / "shows/collingwood.yaml").read_text(encoding="utf-8"))
        assert not any("simcoe.ca" in s["url"] for s in cw["sources"])

    def test_africa_desk_reads_the_national(self):
        cfg = yaml.safe_load((ROOT / "shows/omni_view_africa_mideast.yaml").read_text(encoding="utf-8"))
        assert any("thenationalnews.com" in s["url"] for s in cfg["sources"])


# ---------------------------------------------------------------- D3: preferred_domains

class TestPreferredDomains:
    def test_host_match_is_exact_or_subdomain(self):
        from engine.preferred_sources import is_preferred_url
        doms = ["cftc.gov", "cbc.ca"]
        assert is_preferred_url("https://www.cftc.gov/PressRoom/PressReleases/1", doms)
        assert is_preferred_url("https://www.cbc.ca/news/canada/british-columbia/x", doms)
        assert is_preferred_url("https://ici.cbc.ca/x", doms)
        assert not is_preferred_url("https://notcbc.ca/x", doms)
        assert not is_preferred_url("https://x.com/cbc/status/1", doms)
        assert not is_preferred_url("", doms)

    def test_marking_boosts_and_tags_once(self):
        from engine.preferred_sources import PREFERRED_BONUS, mark_preferred_articles
        arts = [
            {"url": "https://www.cftc.gov/a", "relevance_score": 0.0},
            {"url": "https://x.com/h/status/1", "relevance_score": 0.7},
            {"url": "https://example.com/b"},
        ]
        assert mark_preferred_articles(arts, ["cftc.gov"]) == 1
        assert arts[0]["preferred_source"] is True
        assert arts[0]["relevance_score"] == PREFERRED_BONUS
        assert "preferred_source" not in arts[1] and "preferred_source" not in arts[2]
        assert mark_preferred_articles(arts, ["cftc.gov"]) == 0  # idempotent
        assert arts[0]["relevance_score"] == PREFERRED_BONUS

    def test_empty_list_is_a_no_op(self):
        from engine.preferred_sources import mark_preferred_articles
        arts = [{"url": "https://www.cftc.gov/a", "relevance_score": 0.0}]
        assert mark_preferred_articles(arts, []) == 0
        assert arts == [{"url": "https://www.cftc.gov/a", "relevance_score": 0.0}]

    def test_config_loads_the_list(self):
        from engine.config import load_config

        def _cfg(slug):
            return load_config(ROOT / "shows" / f"{slug}.yaml")

        cfg = _cfg("prediction_markets")
        assert "cftc.gov" in cfg.preferred_domains and "sec.gov" in cfg.preferred_domains
        for slug in ("peptides", "longevity"):
            assert "europepmc.org" in _cfg(slug).preferred_domains, slug
        assert "cbc.ca" in _cfg("vancouver").preferred_domains
        assert _cfg("tesla").preferred_domains == []

    def test_run_show_tags_the_listing_line(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "mark_preferred_articles" in src
        assert '" [preferred primary source]" if art.get("preferred_source")' in src
        assert 'metrics.record("articles_preferred_in_prompt"' in src
