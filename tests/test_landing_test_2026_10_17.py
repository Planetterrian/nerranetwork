"""Guards for ``landing-test.html`` — the network as a news front page (Oct 17 2026).

An operator-directed TEST page: every public show's newest episode laid out as
a news front (lead, Latest list, top stories, topic sections, most played,
Listen rail). What these pin:

* it is a test — ``noindex``, never in the sitemap;
* every internal link resolves to a file in the repo (a redirect stub is never
  an article: links go through ``_blog_url_for_episode``);
* members-only shows never appear in the page body;
* no internal link carries a ``utm_*`` tag;
* every image has alt text and explicit dimensions;
* no stories renders an honest empty state, not a crash;
* a picture is only ever THIS episode's own scene (show + id + date), and the
  headline is the digest's hook, printed whole.

Every render goes to ``tmp_path``: never read a committed generated page.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import generate_html as G  # noqa: E402
from engine import landing_test as LT  # noqa: E402
from engine import titles  # noqa: E402

_HREF_RE = re.compile(r'href="([^"]*)"')
_IMG_RE = re.compile(r"<img\b[^>]*>", re.S)


@pytest.fixture(scope="module")
def rendered(tmp_path_factory) -> str:
    out = tmp_path_factory.mktemp("landing")
    path = G.generate_landing_test_page(output_dir=out)
    return Path(path).read_text(encoding="utf-8")


def _body(html: str) -> str:
    """The page's own content — the shared nav/footer list every show,
    members-only desks included, and are not this page's to change."""
    start = html.index('<div class="lt-page">')
    end = html.index('<footer class="nn-footer">')
    return html[start:end]


def _internal(href: str) -> bool:
    return not href.startswith(("http://", "https://", "#", "mailto:", "data:"))


class TestItIsATest:
    def test_noindex(self, rendered):
        head = rendered.split("</head>")[0]
        assert re.search(r'<meta name="robots" content="noindex', head)

    def test_not_in_the_sitemap(self, tmp_path):
        out = tmp_path / "sitemap.xml"
        G.generate_sitemap(out=out)
        assert G.LANDING_TEST_PATH not in out.read_text(encoding="utf-8")

    def test_not_linked_from_the_shared_chrome(self):
        for name in ("base.html.j2", "_macros.html.j2", "network_page.html.j2"):
            text = (ROOT / "templates" / name).read_text(encoding="utf-8")
            assert "landing-test" not in text, name

    def test_refreshed_by_the_nightly_and_the_flag(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        static = src.split("def generate_static_pages(")[1].split("\ndef ")[0]
        assert "generate_landing_test_page(dry_run=dry_run)" in static
        assert '"--landing-test"' in src
        assert "generate_landing_test_page(dry_run=args.dry_run)" in src


class TestLinks:
    def test_every_internal_link_resolves(self, rendered):
        missing = []
        for href in _HREF_RE.findall(_body(rendered)):
            if not _internal(href):
                continue
            rel = href.split("#")[0].split("?")[0]
            if rel and not (ROOT / rel).is_file():
                missing.append(href)
        assert not missing, missing

    def test_story_links_are_articles_or_show_pages(self, rendered):
        body = _body(rendered)
        posts = re.findall(r'href="(blog/[a-z_0-9]+/ep\d{3}\.html)"', body)
        assert posts, "the page linked no episode article at all"
        stubs = G.redirect_stub_paths()
        assert not [p for p in posts if p in stubs]

    def test_no_utm_on_internal_links(self, rendered):
        # v2 (Oct 17 2026): an EXTERNAL share intent (x.com, linkedin, …)
        # carries the shared article's funnel-tagged URL as a parameter —
        # that is the blog share row's own pattern, not an internal link. A
        # link is internal when it is relative or its HOST is ours.
        from urllib.parse import urlparse

        def _ours(h):
            return _internal(h) or (urlparse(h).hostname or "").endswith("nerranetwork.com")

        bad = [h for h in _HREF_RE.findall(rendered) if "utm_" in h and _ours(h)]
        assert not bad, bad


class TestMembersOnly:
    def test_no_members_only_show_in_the_body(self, rendered):
        body = _body(rendered)
        gated = [s for s in G._build_all_shows_list() if s["access"] == "members_only"]
        assert gated, "expected the Omni View desks to be members-only"
        for show in gated:
            assert f'href="{show["show_page"]}"' not in body, show["slug"]
            assert show["name"] not in body, show["slug"]

    def test_a_show_marked_members_only_is_dropped(self, tmp_path):
        tesla = next(s for s in G._build_all_shows_list() if s["slug"] == "tesla")
        G.generate_landing_test_page(
            output_dir=tmp_path, all_shows=[{**tesla, "access": "members_only"}])
        body = _body((tmp_path / G.LANDING_TEST_PATH).read_text(encoding="utf-8"))
        assert "Tesla Shorts Time" not in body

    def test_never_reads_a_members_directory(self):
        for path in (ROOT / "engine" / "landing_test.py",):
            assert "members/" not in path.read_text(encoding="utf-8").replace(
                "digests/*/members/", "")


class TestImages:
    def test_every_image_has_alt_and_dimensions(self, rendered):
        imgs = _IMG_RE.findall(_body(rendered))
        assert imgs
        for tag in imgs:
            alt = re.search(r'alt="([^"]*)"', tag)
            assert alt and alt.group(1).strip(), tag
            assert re.search(r'width="\d+"', tag) and re.search(r'height="\d+"', tag), tag

    def test_scene_images_come_from_the_gallery_host(self, rendered):
        for src in re.findall(r'<img src="(https?://[^"]+)"', _body(rendered)):
            assert src.startswith("https://gallery.nerranetwork.com/"), src
            assert src.endswith(".thumb.webp"), "display-size thumbnails only"


class TestEmpty:
    def test_no_stories_renders_an_empty_state(self, tmp_path):
        path = G.generate_landing_test_page(output_dir=tmp_path, all_shows=[])
        html = Path(path).read_text(encoding="utf-8")
        assert "lt-empty" in html
        assert "lt-lead" not in _body(html)


# --------------------------------------------------------------------------
# engine.landing_test units
# --------------------------------------------------------------------------

def _index(episodes, images, base="https://gallery.example.com"):
    return {
        "base_url": base,
        "episode_fields": ["show_slug", "episode_date", "episode_id", "episode_title"],
        "image_fields": ["image_id", "episode", "format", "caption", "intended_use"],
        "episodes": episodes,
        "images": images,
        "overrides": {},
    }


class TestEpisodeScene:
    def test_requires_show_id_and_date(self):
        idx = _index([["spacex", "2026-10-16", "ep133", "t"]],
                     [["abc", 0, "png", "", "segment_card"]])
        # Same id, different date: an older episode's picture is not this one's.
        assert LT.episode_scene(idx, "spacex", 133, "2026-10-17") is None
        assert LT.episode_scene(idx, "tesla", 133, "2026-10-16") is None
        hit = LT.episode_scene(idx, "spacex", 133, "2026-10-16")
        assert hit["url"] == "https://gallery.example.com/spacex/2026-10-16/ep133/abc.thumb.webp"
        assert hit["orientation"] == "landscape"

    def test_landscape_preferred_portrait_as_fallback(self):
        idx = _index([["dp_pod", "2026-10-12", "ep079", "t"]],
                     [["p1", 0, "png", "", "social"], ["l1", 0, "png", "", "segment_card"]])
        assert LT.episode_scene(idx, "dp_pod", 79, "2026-10-12")["url"].endswith("/l1.thumb.webp")
        idx["images"] = [["p1", 0, "png", "", "social"]]
        assert LT.episode_scene(idx, "dp_pod", 79, "2026-10-12")["orientation"] == "portrait"

    def test_the_scene_that_depicts_the_headline_wins(self):
        idx = _index([["spacex", "2026-10-17", "ep133", "t"]],
                     [["robot", 0, "png", "", "segment_card"],
                      ["dragon", 0, "png", "", "segment_card"]])
        prompts = {"robot": "A Tesla Optimus robot assembling a toy",
                   "dragon": "SpaceX Dragon docked to the station with retina samples"}
        hit = LT.episode_scene(
            idx, "spacex", 133, "2026-10-17", prompts=prompts,
            hook="SpaceX Dragon experiments on artificial retinas aboard the station.")
        assert hit["url"].endswith("/dragon.thumb.webp") and hit["matched"]
        # No prompt evidence: the episode's first scene, never a guess.
        hit = LT.episode_scene(idx, "spacex", 133, "2026-10-17", hook="Unrelated words")
        assert hit["url"].endswith("/robot.thumb.webp") and not hit["matched"]

    def test_book_art_is_never_a_story_picture(self):
        idx = _index([["first_principles", "2026-10-17", "ep133", "t"]],
                     [["b", 0, "png", "", "book_chapter"]])
        assert LT.episode_scene(idx, "first_principles", 133, "2026-10-17") is None


class TestHeadline:
    def test_hook_from_markdown_reads_the_digest_hook_whole(self):
        md = "# Show\n\n> **A whole headline that the feed title would have clipped at one hundred characters, here in full.**\n"
        assert LT.hook_from_markdown(md).endswith("here in full.")

    def test_story_headline_is_the_hook_not_the_clipped_feed_title(self):
        show = {"slug": "x", "name": "X", "show_page": "x.html", "blog_page": "blog/x/index.html",
                "brand_color": "#123456", "podcast_image": "assets/covers/x.jpg"}
        record = {"episode_num": 5, "date": "2026-10-17",
                  "episode_title": "Ep 5: A headline clipped by the feed…",
                  "content": "> **A headline clipped by the feed, here printed whole for the reader.**"}
        story = LT.build_story(show, record, blog_url_for=lambda s, n: "",
                               audio_url_for=lambda u: "", gallery=None, hub=None)
        assert story["hook"] == "A headline clipped by the feed, here printed whole for the reader."
        assert len(story["ticker_text"]) <= titles.LANDING_TICKER_MAX
        assert story["image_url"] == "" and story["cover_url"] == "assets/covers/x.jpg"

    def test_strip_episode_label(self):
        assert LT.strip_episode_label("Ep 133: SpaceX Dragon") == "SpaceX Dragon"
        assert LT.strip_episode_label("Ep12: Thor Hesselberg — A founder") == "Thor Hesselberg — A founder"

    def test_more_headlines_skip_the_hook(self):
        md = ("> **The lead story headline about a thing happening today.**\n\n"
              "1. **The lead story headline about a thing happening today**\n   body\n"
              "2. **A second story about something else entirely**\n   body\n")
        more = LT.more_headlines(md, "The lead story headline about a thing happening today.")
        assert more == ["A second story about something else entirely"]


class TestAssemble:
    def _story(self, slug, d, img="", hub="ai"):
        from datetime import date
        return {"slug": slug, "date_obj": date.fromisoformat(d), "image_url": img,
                "image_orientation": "landscape" if img else "", "hub_id": hub}

    def test_lead_is_newest_pictured_story_and_nothing_prints_twice(self):
        stories = [self._story("a", "2026-10-17"), self._story("b", "2026-10-17", "u"),
                   self._story("c", "2026-10-16", "u"), self._story("d", "2026-10-15"),
                   self._story("e", "2026-10-15", "u", "space"),
                   self._story("f", "2026-10-14", "", "space"),
                   self._story("g", "2026-10-14", "", "space")]
        page = LT.assemble(stories, audience_order=["a", "b"])
        assert page["lead"]["slug"] == "b"
        placed = [page["lead"]["slug"]] + [s["slug"] for s in page["top"]]
        for sec in page["sections"]:
            placed += [s["slug"] for s in sec["stories"]]
        placed += [s["slug"] for s in page["more"]]
        assert sorted(placed) == sorted(s["slug"] for s in stories)

    def test_stale_stories_drop_off_the_front(self):
        stories = [self._story("new", "2026-10-17", "u"), self._story("old", "2026-09-01", "u")]
        page = LT.assemble(stories)
        assert [s["slug"] for s in page["latest"]] == ["new"]

    def test_empty(self):
        assert LT.assemble([])["lead"] is None
