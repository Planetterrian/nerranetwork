"""Findability a search engine can read (Nov 3 2026).

Organic Search was 19 sessions in 28 days on 2,966 sitemap URLs — the same
as Sep 10 — and the 17 topic hubs received no landing session. Every post
``<title>`` was shaped ``<hook>… — Ep653 | Tesla Shorts Time`` (median 88
characters, 97.8% over the ~60 a result displays), so a search result never
showed the show; the article schema was a ``BlogPosting`` with no
``dateModified`` and the square cover as its image; the homepage
Organization had no ``sameAs`` although ``network_social_sameas()`` existed
and fed only about.html; nothing told Google which pages were news, or when.

What this pins:

* a news show's post carries a ``NewsArticle`` whose author is the show
  ORGANIZATION (never a Person — a cloned voice reading model-written text
  is not an author, and the AI-disclosure page says so) with ``sameAs`` on
  that page, ``publisher.logo`` an ImageObject, ``image`` the episode's own
  share card, ``dateModified`` from the corrections record (never the build
  clock), ``isAccessibleForFree`` — and still a ``PodcastEpisode``;
* narrative, lesson, dialogue and interview posts keep ``BlogPosting``;
* the homepage Organization has ``sameAs`` and a logo ImageObject;
* every post ``<title>`` is ``"<lead> · <Show>"`` with the lead inside
  ``WEB_TITLE_LEAD_MAX`` (58) and no episode number;
* ``news-sitemap.xml`` lists only NewsArticle posts dated within 48 hours
  of the build (a valid empty urlset otherwise), robots.txt names it, and
  every workflow that commits sitemap.xml commits it too.

Every render goes to ``tmp_path``; no test reads a committed generated page.
"""

from __future__ import annotations

import datetime as dt
import html as _html
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate_html as G  # noqa: E402
from engine import blog as B  # noqa: E402
from engine import corrections as C  # noqa: E402
from engine.titles import (  # noqa: E402
    WEB_TITLE_LEAD_MAX, WEB_TITLE_SEPARATOR, web_page_title,
)

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
NEWS_NS = "http://www.google.com/schemas/sitemap-news/0.9"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _digest_dir(slug: str) -> Path:
    return ROOT / "digests" / G._SHOW_DIRS.get(slug, slug)


def _newest_digest(slug: str) -> Path:
    paths = sorted(_digest_dir(slug).glob("*_Ep*.md"))
    assert paths, f"no committed digest for {slug}"
    return paths[-1]


def _render(slug: str, md_path: Path) -> tuple[str, dict]:
    """The real entry point on the real registry entry and Jinja env."""
    from engine.blog import extract_blog_metadata, generate_blog_post_html
    cfg = G.NETWORK_SHOWS[slug]
    text = md_path.read_text(encoding="utf-8")
    meta = extract_blog_metadata(text, slug, md_path.name, file_path=md_path)
    meta["_md_path"] = md_path
    page = generate_blog_post_html(text, meta, cfg, G._get_jinja_env(), related_posts=[])
    return G._strip_lone_surrogates(page), meta


def _ld_blocks(page: str) -> list:
    out = []
    for m in re.finditer(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', page, re.S):
        data = json.loads(m.group(1))
        out.extend(data if isinstance(data, list) else [data])
    return out


def _article(page: str) -> dict:
    return next(b for b in _ld_blocks(page)
                if b.get("@type") in (B.ARTICLE_TYPE_NEWS, B.ARTICLE_TYPE_BLOG))


def _title(page: str) -> str:
    return _html.unescape(re.search(r"<title>(.*?)</title>", page, re.S).group(1).strip())


def _scratch_copy(tmp_path: Path, slug: str, src: Path) -> Path:
    """One episode's digest + sidecars in a scratch digest dir, so a test can
    file a correction beside it without touching the repo."""
    dst_dir = tmp_path / "digests" / G._SHOW_DIRS.get(slug, slug)
    dst_dir.mkdir(parents=True)
    for f in src.parent.glob(src.stem + "*"):
        shutil.copy(f, dst_dir / f.name)
    return dst_dir / src.name


@pytest.fixture(scope="module")
def tesla():
    return _render("tesla", _newest_digest("tesla"))


@pytest.fixture(scope="module")
def uc():
    return _render("unintended_consequences", _newest_digest("unintended_consequences"))


@pytest.fixture(scope="module")
def aoai():
    return _render("age_of_ai", _newest_digest("age_of_ai"))


# ---------------------------------------------------------------------------
# 1. NewsArticle on a news post, the show Organization as author
# ---------------------------------------------------------------------------

class TestNewsArticleOnANewsPost:

    def test_the_article_is_news(self, tesla):
        page, _ = tesla
        assert _article(page)["@type"] == "NewsArticle"

    def test_the_author_is_the_show_organization_with_the_disclosure(self, tesla):
        """The skeptic's amendment: never a Person. A cloned voice reading
        Grok-written scripts did not write the piece, and ai-disclosure.html
        says so — the author's sameAs points there."""
        page, _ = tesla
        author = _article(page)["author"]
        assert author["@type"] == "Organization"
        assert author["name"] == G.NETWORK_SHOWS["tesla"]["name"]
        assert author["sameAs"] == [B.AI_DISCLOSURE_URL]
        assert B.AI_DISCLOSURE_URL.endswith("/ai-disclosure.html")
        assert author["url"] == f"https://nerranetwork.com/{G.NETWORK_SHOWS['tesla']['show_page']}"

    def test_no_post_names_a_person_as_author(self, tesla, uc, aoai):
        for page, _ in (tesla, uc, aoai):
            assert _article(page)["author"]["@type"] == "Organization"

    def test_the_publisher_logo_is_an_image_object_of_a_committed_png(self, tesla):
        page, _ = tesla
        logo = _article(page)["publisher"]["logo"]
        assert logo["@type"] == "ImageObject"
        assert logo["url"] == f"https://nerranetwork.com/{B.PUBLISHER_LOGO_PATH}"
        assert (ROOT / B.PUBLISHER_LOGO_PATH).is_file()
        assert isinstance(logo["width"], int) and isinstance(logo["height"], int)
        assert logo["width"] > logo["height"] >= 112, logo  # a wordmark, not the square icon
        assert _article(page)["publisher"]["name"] == "Nerra Network"

    def test_the_image_is_the_episodes_own_card(self, tesla):
        page, meta = tesla
        expected = B._episode_og_image(meta, G.NETWORK_SHOWS["tesla"], meta["episode_num"])
        assert _article(page)["image"] == expected

    def test_date_modified_is_the_published_date_when_nothing_was_corrected(self, tesla):
        page, meta = tesla
        article = _article(page)
        assert article["datePublished"] == meta["date_iso"]
        assert article["dateModified"] == article["datePublished"]
        # Never the build clock.
        assert article["dateModified"] != dt.date.today().isoformat() or \
            meta["date_iso"] == dt.date.today().isoformat()

    def test_free_to_read_and_still_a_podcast_episode(self, tesla):
        page, _ = tesla
        assert _article(page)["isAccessibleForFree"] is True
        types = [b.get("@type") for b in _ld_blocks(page)]
        assert "PodcastEpisode" in types
        assert types.count("NewsArticle") == 1 and "BlogPosting" not in types


class TestDateModifiedFromCorrections:

    def test_a_correction_moves_date_modified_to_the_correction_date(self, tmp_path):
        src = _newest_digest("tesla")
        md = _scratch_copy(tmp_path, "tesla", src)
        _, meta = _render("tesla", md)
        later = (dt.date.fromisoformat(meta["date_iso"]) + dt.timedelta(days=3)).isoformat()
        C.corrections_path(md.parent).write_text(yaml.safe_dump([
            {"episode": meta["episode_num"], "date": later,
             "text": "The figure was 248 percent, not 284.", "where": "digest"},
        ], allow_unicode=True), encoding="utf-8")
        page, _ = _render("tesla", md)
        article = _article(page)
        assert article["datePublished"] == meta["date_iso"]
        assert article["dateModified"] == later

    def test_a_correction_dated_before_publication_never_moves_the_date_back(self, tmp_path):
        src = _newest_digest("tesla")
        md = _scratch_copy(tmp_path, "tesla", src)
        _, meta = _render("tesla", md)
        earlier = (dt.date.fromisoformat(meta["date_iso"]) - dt.timedelta(days=3)).isoformat()
        C.corrections_path(md.parent).write_text(yaml.safe_dump([
            {"episode": meta["episode_num"], "date": earlier, "text": "A note."},
        ]), encoding="utf-8")
        page, _ = _render("tesla", md)
        assert _article(page)["dateModified"] == meta["date_iso"]


# ---------------------------------------------------------------------------
# 2. BlogPosting everywhere else
# ---------------------------------------------------------------------------

class TestBlogPostingElsewhere:

    def test_a_narrative_post_is_a_blog_posting(self, uc):
        page, _ = uc
        assert _article(page)["@type"] == "BlogPosting"

    def test_an_interview_post_is_a_blog_posting_and_the_guest_stays_a_person(self, aoai):
        page, _ = aoai
        article = _article(page)
        assert article["@type"] == "BlogPosting"
        if article.get("about"):
            assert article["about"]["@type"] == "Person"

    def test_the_decision_over_the_registry(self):
        """Narrative, lesson, dialogue and interview shows and the registry-
        only edition keep BlogPosting; a show that fetches articles is news."""
        blog = {"unintended_consequences", "first_principles", "age_of_ai",
                "nerra_voices", "dp_pod", "privet_russian", "nerra_daily"}
        news = {"tesla", "spacex", "omni_view", "vancouver", "mag7", "omni_view_world"}
        for slug, cfg in G.NETWORK_SHOWS.items():
            kind = B.article_schema_type(cfg)
            assert kind in (B.ARTICLE_TYPE_NEWS, B.ARTICLE_TYPE_BLOG), slug
            if slug in blog:
                assert kind == "BlogPosting", slug
            if slug in news:
                assert kind == "NewsArticle", slug
        assert B.article_schema_type(None) == "BlogPosting"
        assert B.article_schema_type({"slug": "no_such_show"}) == "BlogPosting"

    def test_every_narrative_yaml_is_a_blog_posting(self):
        for path in (ROOT / "shows").glob("*.yaml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict) or not data.get("narrative_mode"):
                continue
            cfg = G.NETWORK_SHOWS.get(path.stem)
            if cfg:
                assert B.article_schema_type(cfg) == "BlogPosting", path.stem


# ---------------------------------------------------------------------------
# 3. The homepage Organization
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def home(tmp_path_factory):
    out = tmp_path_factory.mktemp("home")
    return G.generate_network_page(output_dir=out, now=NOW).read_text(encoding="utf-8")


class TestHomepageOrganization:

    def test_same_as_and_logo(self, home):
        org = next(b for b in _ld_blocks(home) if b.get("@type") == "Organization")
        assert org["sameAs"] == G.network_social_sameas()
        assert org["sameAs"], "no social accounts resolved"
        assert all(u.startswith("https://") for u in org["sameAs"])
        assert org["logo"] == B.publisher_logo_ld()
        assert org["logo"]["@type"] == "ImageObject"


# ---------------------------------------------------------------------------
# 4. Titles: "<lead> · <Show>", under the budget, no episode number
# ---------------------------------------------------------------------------

class TestPageTitles:

    @staticmethod
    def _check(title: str, show_name: str) -> str:
        tail = f"{WEB_TITLE_SEPARATOR}{show_name}"
        assert title.endswith(tail), title
        assert " — Ep" not in title and " | " not in title, title
        lead = title[: -len(tail)]
        assert len(lead) <= WEB_TITLE_LEAD_MAX, (lead, len(lead))
        return lead

    def test_a_news_post(self, tesla):
        page, meta = tesla
        lead = self._check(_title(page), "Tesla Shorts Time")
        assert lead == web_page_title(meta["title"], "x")[: -len(f"{WEB_TITLE_SEPARATOR}x")]

    def test_a_narrative_post(self, uc):
        page, _ = uc
        self._check(_title(page), G.NETWORK_SHOWS["unintended_consequences"]["name"])

    def test_an_interview_post_names_the_guest_then_the_show(self, aoai):
        page, meta = aoai
        title = _title(page)
        self._check(title, G.NETWORK_SHOWS["age_of_ai"]["name"])
        from engine.blog import interview_context
        iv = interview_context(
            _newest_digest("age_of_ai").read_text(encoding="utf-8"), "age_of_ai",
            meta["episode_num"],
            summaries_path=G.NETWORK_SHOWS["age_of_ai"].get("json_path", ""),
            rss_path=G.NETWORK_SHOWS["age_of_ai"].get("rss_file", ""))
        if iv.get("guest_name"):
            assert title.startswith(iv["guest_name"]), title

    def test_the_blog_assembles_no_title_of_its_own(self):
        """One owner: both call sites go through engine.titles.web_page_title;
        nothing in engine/blog.py types the old tail."""
        src = (ROOT / "engine" / "blog.py").read_text(encoding="utf-8")
        assert "— Ep{ep_num}" not in src
        assert "| {show_config['name']} Ep{ep_num}" not in src
        assert src.count("_web_page_title(") >= 3  # the helper + two call sites
        assert "from engine.titles import web_page_title" in src

    def test_the_search_result_shows_the_show(self):
        """With the longest lead the separator sits at characters 58-60 and
        the show begins at 61 — the start of the show name is inside what a
        result displays (~60 characters, pixel-bound) instead of 30 past it
        as ``<hook>… — Ep653 | Tesla Shorts Time`` put it."""
        assert WEB_TITLE_LEAD_MAX == 58
        title = web_page_title("x" * 200, "Tesla Shorts Time")
        assert title.index(WEB_TITLE_SEPARATOR) == WEB_TITLE_LEAD_MAX
        assert title.index("Tesla Shorts Time") == WEB_TITLE_LEAD_MAX + len(WEB_TITLE_SEPARATOR) <= 61


# ---------------------------------------------------------------------------
# 5. The news sitemap
# ---------------------------------------------------------------------------

def _post_file(blog_dir: Path, slug: str, ep: int, *, kind: str, date: str,
               headline: str, lang: str = "en") -> Path:
    """A rendered-post stand-in: the ld+json array a real page opens with."""
    ld = [{"@context": "https://schema.org", "@type": kind, "headline": headline,
           "datePublished": date, "dateModified": date, "inLanguage": lang},
          {"@context": "https://schema.org", "@type": "PodcastEpisode", "name": headline}]
    path = blog_dir / slug / f"ep{ep:03d}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "<!doctype html><html><head><title>t</title>\n"
        '<script type="application/ld+json">\n' + json.dumps(ld, indent=2) +
        "\n</script></head><body></body></html>\n", encoding="utf-8")
    return path


def _news_rows(xml_path: Path) -> list:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    assert root.tag == f"{{{SITEMAP_NS}}}urlset"
    rows = []
    for url in root.findall(f"{{{SITEMAP_NS}}}url"):
        news = url.find(f"{{{NEWS_NS}}}news")
        assert news is not None
        rows.append({
            "loc": url.findtext(f"{{{SITEMAP_NS}}}loc"),
            "name": news.findtext(f"{{{NEWS_NS}}}publication/{{{NEWS_NS}}}name"),
            "language": news.findtext(f"{{{NEWS_NS}}}publication/{{{NEWS_NS}}}language"),
            "date": news.findtext(f"{{{NEWS_NS}}}publication_date"),
            "title": news.findtext(f"{{{NEWS_NS}}}title"),
        })
    return rows


class TestNewsSitemap:

    def test_lists_news_posts_of_the_last_48_hours_only(self, tmp_path):
        blog = tmp_path / "blog"
        day = lambda d: (NOW + dt.timedelta(days=d)).date().isoformat()  # noqa: E731
        _post_file(blog, "newsy", 1, kind="NewsArticle", date=day(0), headline="Today & now")
        _post_file(blog, "newsy", 2, kind="NewsArticle", date=day(-1), headline="Yesterday")
        _post_file(blog, "newsy", 3, kind="NewsArticle", date=day(-5), headline="Last week")
        _post_file(blog, "newsy", 4, kind="NewsArticle", date=day(1), headline="Tomorrow")
        _post_file(blog, "essay", 1, kind="BlogPosting", date=day(0), headline="An essay")
        _post_file(blog, "ru_desk", 1, kind="NewsArticle", date=day(0),
                   headline="Продажи жилья", lang="ru")
        out = tmp_path / "news-sitemap.xml"
        assert G.generate_news_sitemap(out=out, now=NOW, blog_dir=blog) == out
        rows = _news_rows(out)
        locs = [r["loc"] for r in rows]
        assert set(locs) == {
            "https://nerranetwork.com/blog/newsy/ep001.html",
            "https://nerranetwork.com/blog/newsy/ep002.html",
            "https://nerranetwork.com/blog/ru_desk/ep001.html",
        }
        assert locs[-1].endswith("newsy/ep002.html"), "newest first"
        by_loc = {r["loc"].rsplit("/", 2)[-2] + "/" + r["loc"].rsplit("/", 1)[-1]: r for r in rows}
        assert by_loc["newsy/ep001.html"]["title"] == "Today & now"  # escaped on the way out
        assert by_loc["newsy/ep001.html"]["date"] == day(0)
        assert by_loc["ru_desk/ep001.html"]["language"] == "ru"
        assert {r["name"] for r in rows} == {"Nerra Network"}
        assert {r["language"] for r in rows if "newsy" in r["loc"]} == {"en"}
        raw = out.read_text(encoding="utf-8")
        assert 'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"' in raw
        assert "Today &amp; now" in raw

    def test_an_empty_window_is_a_valid_empty_urlset(self, tmp_path):
        blog = tmp_path / "blog"
        _post_file(blog, "newsy", 1, kind="NewsArticle",
                   date=(NOW - dt.timedelta(days=9)).date().isoformat(), headline="Old")
        out = tmp_path / "news-sitemap.xml"
        G.generate_news_sitemap(out=out, now=NOW, blog_dir=blog)
        assert _news_rows(out) == []
        raw = out.read_text(encoding="utf-8")
        assert raw.startswith('<?xml version="1.0" encoding="UTF-8"?>')
        assert raw.rstrip().endswith("</urlset>")
        assert 'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"' in raw

    def test_a_missing_blog_dir_still_writes_the_file(self, tmp_path):
        out = tmp_path / "news-sitemap.xml"
        G.generate_news_sitemap(out=out, now=NOW, blog_dir=tmp_path / "nowhere")
        assert _news_rows(out) == []

    def test_the_committed_tree_validates_and_stays_inside_the_window(self, tmp_path):
        """Whatever the committed posts carry today, the file validates and
        every listed date is within 48 hours of the build clock."""
        out = tmp_path / "news-sitemap.xml"
        now = dt.datetime.now(UTC)
        G.generate_news_sitemap(out=out, now=now)
        floor = (now - dt.timedelta(hours=G.NEWS_SITEMAP_HOURS)).date().isoformat()
        for row in _news_rows(out):
            assert floor <= row["date"] <= now.date().isoformat(), row
            assert row["loc"].startswith("https://nerranetwork.com/blog/")

    def test_the_window_is_two_days(self):
        assert G.NEWS_SITEMAP_HOURS == 48
        assert G.NEWS_SITEMAP_FILE == "news-sitemap.xml"

    def test_robots_lists_both_sitemaps(self):
        robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
        assert "Sitemap: https://nerranetwork.com/sitemap.xml" in robots
        assert "Sitemap: https://nerranetwork.com/news-sitemap.xml" in robots

    def test_the_cli_writes_it_beside_the_sitemap(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        main = src.split("def main():", 1)[1]
        pair = "generate_sitemap(dry_run=args.dry_run)\n        generate_news_sitemap(dry_run=args.dry_run)"
        assert main.count(pair) == 2, "both the --sitemap and the --all branches"

    def test_every_committing_surface_carries_the_file(self):
        """A generated file that no workflow adds is a file that never ships
        (the add-paths whitelist lesson, Sep 4 2026)."""
        run_show = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
        stage = (ROOT / "scripts" / "stage_show_artifacts.sh").read_text(encoding="utf-8")
        for text in (run_show, stage):
            assert "git add sitemap.xml || true" in text
            assert "git add news-sitemap.xml || true" in text
            # One add per path: `git add sitemap.xml news-sitemap.xml` stages
            # NEITHER while news-sitemap.xml is absent from the checkout (a
            # multi-path pathspec is all-or-nothing — the staging script's
            # own `git checkout HEAD --` lesson).
            assert "git add sitemap.xml news-sitemap.xml" not in text
        special = (ROOT / ".github" / "workflows" / "produce-special.yml").read_text(encoding="utf-8")
        assert "sitemap.xml news-sitemap.xml" in special
        for name in ("test.yml", "e2e.yml"):
            wf = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
            on = wf.get("on") or wf.get(True)
            assert "news-sitemap.xml" in on["push"]["paths-ignore"], name
