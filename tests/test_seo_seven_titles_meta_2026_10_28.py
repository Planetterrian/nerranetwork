"""Drift guard: seven approved SEO titles/metas (Oct 28 2026).

Covers /mira.html, /explore.html, /about.html and the four show pages
added to docs/seo-titles-final.md (ai-chips, mag7, prediction-markets,
modern-investing). Titles ≤60, metas ≤160; explore/about must not carry
a show-count phrase.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

MIRA_TITLE = "Mira, the Nerra Network's AI host"
MIRA_META = (
    "Mira is Nerra Network's AI host. She anchors the daily combined "
    "edition and interviews real people live. Guests get a week to "
    "approve or refuse a transcript."
)

EXPLORE_TITLE = "Explore the shows: browse every Nerra podcast | Nerra"
EXPLORE_META = (
    "Browse the Nerra Network's shows by subject and language: AI, "
    "space, markets, science, climate, world news and language learning. "
    "Free to listen."
)

ABOUT_TITLE = "About Nerra Network: independent, free podcasts | Nerra"
ABOUT_META = (
    "Nerra Network is an independent podcast network of daily shows on "
    "AI, Tesla, investing, space and science, made in Vancouver. Every "
    "Nerra show stays free."
)

SHOW_PAGES = {
    "ai_chips": (
        "AI Chips & Data Centres Daily: AI Power News Podcast | Nerra",
        "A daily podcast on AI chips, data centres, power and the "
        "semiconductor supply chain: specs, megawatts and capex, with "
        "sources. Free to listen.",
    ),
    "mag7": (
        "MAG 7 Daily: Big Tech News Podcast | Nerra",
        "A daily podcast on Alphabet, Amazon, Apple, Meta, Microsoft, "
        "NVIDIA and Tesla: what they shipped and one cross-company "
        "thread. Not financial advice.",
    ),
    "prediction_markets": (
        "Prediction Markets Daily: Kalshi & Polymarket News | Nerra",
        "A daily podcast on prediction markets in Canada, the US and "
        "the world: Kalshi, Polymarket, the CFTC and the courts. Not "
        "financial advice.",
    ),
    "modern_investing": (
        "Modern Investing Techniques: Markets Podcast | Nerra",
        "AI-powered daily market intelligence with simulated trades, "
        "strategy breakdowns and tools for Canadian and US investors. "
        "Free to listen.",
    ),
}

TITLE_TAGS = ("title", "og:title", "twitter:title")
META_TAGS = ("description", "og:description", "twitter:description")
FREE_SHOWS_RE = re.compile(r"\d+ free shows")


class _HeadMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title = ""
        self.meta: dict[str, str] = {}
        self._done_head = False

    def handle_starttag(self, tag, attrs):
        if self._done_head:
            return
        attrs_d = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "meta":
            name = attrs_d.get("name") or attrs_d.get("property") or ""
            if name in (
                "description",
                "og:title",
                "og:description",
                "twitter:title",
                "twitter:description",
            ):
                self.meta[name] = attrs_d.get("content", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "head":
            self._done_head = True

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def _page_seo_tags(html: str) -> dict[str, str]:
    p = _HeadMetaParser()
    p.feed(html)
    return {
        "title": p.title,
        "description": p.meta.get("description", ""),
        "og:title": p.meta.get("og:title", ""),
        "og:description": p.meta.get("og:description", ""),
        "twitter:title": p.meta.get("twitter:title", ""),
        "twitter:description": p.meta.get("twitter:description", ""),
    }


def _unescape_meta(s: str) -> str:
    return (
        s.replace("&#39;", "'")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#34;", '"')
    )


def _assert_title_meta(tags: dict[str, str], title: str, meta: str, label: str):
    for key in TITLE_TAGS:
        got = _unescape_meta(tags[key])
        assert got == title, f"{label} {key}:\n  got:  {got!r}\n  want: {title!r}"
    for key in META_TAGS:
        got = _unescape_meta(tags[key])
        assert got == meta, f"{label} {key}:\n  got:  {got!r}\n  want: {meta!r}"
    assert len(title) <= 60, (label, len(title), title)
    assert len(meta) <= 160, (label, len(meta), meta)


def test_mira_explore_about_seo_tags(tmp_path):
    import generate_html as G

    cases = [
        ("mira.html", G.generate_mira_page, MIRA_TITLE, MIRA_META),
        ("explore.html", G.generate_explore_page, EXPLORE_TITLE, EXPLORE_META),
        ("about.html", G.generate_about_page, ABOUT_TITLE, ABOUT_META),
    ]
    for basename, gen, title, meta in cases:
        path = Path(gen(output_dir=tmp_path))
        html = path.read_text(encoding="utf-8")
        tags = _page_seo_tags(html)
        _assert_title_meta(tags, title, meta, basename)
        if basename in ("explore.html", "about.html"):
            assert not FREE_SHOWS_RE.search(html), (
                f"{basename} must not contain a show-count phrase"
            )


@pytest.mark.parametrize("slug", sorted(SHOW_PAGES))
def test_four_show_pages_use_approved_seo(slug, tmp_path):
    import generate_html as G

    title, meta = SHOW_PAGES[slug]
    path = Path(G.generate_show_page(slug, output_dir=tmp_path))
    tags = _page_seo_tags(path.read_text(encoding="utf-8"))
    _assert_title_meta(tags, title, meta, slug)


def test_mira_page_description_constant():
    from engine import brand

    assert brand.MIRA_PAGE_DESCRIPTION == MIRA_META
    assert "week" in brand.MIRA_PAGE_DESCRIPTION
    for phrase in (
        "until the guest approves",
        "nothing publishes until",
        "approves their own transcript",
        "guest approves their own transcript",
    ):
        assert phrase not in brand.MIRA_PAGE_DESCRIPTION.lower()
