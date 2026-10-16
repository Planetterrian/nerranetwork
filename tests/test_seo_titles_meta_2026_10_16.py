"""Drift guard: the 11 approved GSC CTR titles/metas (HoM, Oct 16 2026).

Each page's <title>, og:title, twitter:title must equal the Title column,
and meta description / og:description / twitter:description must equal
the Meta column, of docs/seo-titles-final.md (``&#124;`` = literal ``|``).
Show pages must NOT inject the daily hook into those tags.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SEO_FILE = ROOT / "docs" / "seo-titles-final.md"

# URL path → committed HTML basename
URL_TO_FILE = {
    "/": "index.html",
    "/personal-interest.html": "personal-interest.html",
    "/join.html": "join.html",
    "/claims.html": "claims.html",
    "/nerra-voices-apply.html": "nerra-voices-apply.html",
    "/spacex.html": "spacex.html",
    "/tesla.html": "tesla.html",
    "/fascinating-frontiers.html": "fascinating-frontiers.html",
    "/models-agents.html": "models-agents.html",
    "/age-of-ai.html": "age-of-ai.html",
    "/nerra-voices.html": "nerra-voices.html",
}

TITLE_TAGS = ("title", "og:title", "twitter:title")
META_TAGS = ("description", "og:description", "twitter:description")


def _parse_seo_file(path: Path = SEO_FILE) -> dict[str, tuple[str, str]]:
    """Return {url: (title, meta)} from the approved markdown table."""
    text = path.read_text(encoding="utf-8")
    rows: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        url, title, meta = cells[0], cells[1], cells[2]
        if url in ("URL", "---") or url.startswith("---") or not url.startswith("/"):
            continue
        title = title.replace("&#124;", "|")
        meta = meta.replace("&#124;", "|")
        rows[url] = (title, meta)
    return rows


class _HeadMetaParser(HTMLParser):
    """Pull <title> text and selected meta content attrs from <head>."""

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
    out = {
        "title": p.title,
        "description": p.meta.get("description", ""),
        "og:title": p.meta.get("og:title", ""),
        "og:description": p.meta.get("og:description", ""),
        "twitter:title": p.meta.get("twitter:title", ""),
        "twitter:description": p.meta.get("twitter:description", ""),
    }
    return out


@pytest.fixture(scope="module")
def approved() -> dict[str, tuple[str, str]]:
    rows = _parse_seo_file()
    assert set(rows) == set(URL_TO_FILE), (
        f"seo file URLs {sorted(rows)} != expected {sorted(URL_TO_FILE)}"
    )
    return rows


def test_seo_file_has_eleven_pages(approved):
    assert len(approved) == 11


@pytest.mark.parametrize("url", list(URL_TO_FILE))
def test_six_tags_match_approved_file(url, approved):
    title, meta = approved[url]
    path = ROOT / URL_TO_FILE[url]
    assert path.exists(), f"missing committed HTML for {url}: {path}"
    tags = _page_seo_tags(path.read_text(encoding="utf-8"))

    for key in TITLE_TAGS:
        assert tags[key] == title, (
            f"{URL_TO_FILE[url]} {key}:\n  got:  {tags[key]!r}\n  want: {title!r}"
        )
    for key in META_TAGS:
        assert tags[key] == meta, (
            f"{URL_TO_FILE[url]} {key}:\n  got:  {tags[key]!r}\n  want: {meta!r}"
        )


def test_seo_show_pages_do_not_inject_daily_hook():
    """The generate_show_page path must prefer SEO_PAGE_COPY over the hook."""
    src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
    assert "SEO_PAGE_COPY" in src
    assert "approved SEO pages keep the exact title" in src
    # The hook injection still exists for non-SEO shows.
    assert 'f"{cfg[\'name\']} — {hook_snippet} | Nerra Network"' in src


def test_generator_seo_copy_matches_file(approved):
    import generate_html as G

    for url, (title, meta) in approved.items():
        page = URL_TO_FILE[url]
        assert page in G.SEO_PAGE_COPY, page
        assert G.SEO_PAGE_COPY[page] == (title, meta), page


def test_title_and_meta_length_caps(approved):
    for url, (title, meta) in approved.items():
        assert len(title) <= 60, (url, len(title), title)
        assert len(meta) <= 160, (url, len(meta), meta)
