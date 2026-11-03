"""Repository hygiene (Nov 3 2026).

Two things that made the repository grow for no reader:

* Every one of ~2,750 committed posts carried the same 39 KB ``<style>``
  block from ``templates/blog_post.html.j2`` (~108 MB in the repo, ~6 MB a
  week). The tail of it is ``styles/blog.css`` now, loaded through
  ``asset_v`` (content-hashed) AFTER an inline head of under 10 KB, so the
  cascade order is the original block's.
* The media guard under ``digests/`` was an extension denylist, and the
  class had failed on mp3, png and flac in turn. The guard here is a SIZE:
  the largest legitimate tracked file under ``digests/`` is a 474 KB
  transcript, so any tracked file over 2 MB fails, whatever it is called.
  The allow-list is empty on purpose.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BLOB_LIMIT_BYTES = 2 * 1024 * 1024
#: Tracked paths under digests/ allowed over the limit. Empty on purpose:
#: a name here is a decision, never a convenience.
ALLOWED_OVER_LIMIT: frozenset[str] = frozenset()


def tracked_sizes(root: Path = ROOT) -> list[tuple[int, str]]:
    """``(bytes, path)`` for every tracked file under digests/."""
    out = subprocess.run(["git", "ls-files", "-z", "digests"], cwd=root,
                         capture_output=True, check=True).stdout
    rows = []
    for rel in out.decode("utf-8").split("\0"):
        if not rel:
            continue
        try:
            rows.append(((root / rel).stat().st_size, rel))
        except FileNotFoundError:  # deleted in the working tree, still tracked
            continue
    return rows


def oversized(rows, limit: int = BLOB_LIMIT_BYTES,
              allowed: frozenset[str] = ALLOWED_OVER_LIMIT) -> list[tuple[int, str]]:
    return sorted((size, rel) for size, rel in rows if size > limit and rel not in allowed)


class TestNoTrackedBlobOverTwoMBUnderDigests:
    def test_the_committed_tree_passes(self):
        rows = tracked_sizes()
        assert len(rows) > 1000, "git ls-files returned almost nothing"
        assert oversized(rows) == [], (
            "a file over 2 MB is tracked under digests/ — episode media belongs "
            "on R2 (landmine #1); a transcript is a tenth of that")

    def test_a_three_mb_fixture_added_to_the_tracked_set_fails(self):
        fixture = (3 * 1024 * 1024, "digests/tesla_shorts_time/youtube_tmp/fixture.bin")
        assert oversized(tracked_sizes() + [fixture]) == [fixture]

    def test_the_allow_list_is_empty(self):
        assert ALLOWED_OVER_LIMIT == frozenset()

    def test_the_guard_reads_size_not_extension(self):
        rows = [(BLOB_LIMIT_BYTES + 1, "digests/x/a.json"), (BLOB_LIMIT_BYTES, "digests/x/b.flac")]
        assert oversized(rows) == [(BLOB_LIMIT_BYTES + 1, "digests/x/a.json")]


def _strip_css_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _strip_jinja_comments(text: str) -> str:
    return re.sub(r"\{#.*?#\}", "", text, flags=re.S)


@pytest.fixture(scope="module")
def template() -> str:
    return _strip_jinja_comments(
        (ROOT / "templates" / "blog_post.html.j2").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def blog_css() -> str:
    return (ROOT / "styles" / "blog.css").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rendered_post() -> str:
    import generate_html as G
    from engine.blog import extract_blog_metadata, generate_blog_post_html

    show_dir = ROOT / "digests" / "dp_pod"
    md_path = sorted(p for p in show_dir.glob("*_Ep*_*.md")
                     if re.search(r"_Ep\d+_\d{8}\.md$", p.name))[-1]
    md = md_path.read_text(encoding="utf-8")
    meta = extract_blog_metadata(md, "dp_pod", md_path.name, file_path=md_path)
    meta["_md_path"] = md_path
    return generate_blog_post_html(md, meta, G.NETWORK_SHOWS["dp_pod"],
                                   G._get_jinja_env(), related_posts=[])


class TestTheBlogStylesheetIsShared:
    def test_the_inline_block_is_under_ten_kb_and_holds_no_jinja(self, template):
        block = re.search(r"<style>(.*?)</style>", template, re.S).group(1)
        assert len(block.encode("utf-8")) <= 10 * 1024
        assert "{{" not in block and "{%" not in block

    def test_the_link_follows_the_inline_block(self, template):
        """The head stays inline and the sheet is linked AFTER it, so a
        later rule in the sheet (the phone media queries) still wins over an
        earlier one inline — the order the one block had."""
        link = '<link rel="stylesheet" href="{{ path_prefix }}{{ asset_v("styles/blog.css") }}">'
        assert template.count(link) == 1
        assert template.index("</style>") < template.index(link)

    def test_a_rendered_post_links_the_sheet_once_versioned_after_main(self, rendered_post):
        links = re.findall(r'<link rel="stylesheet" href="([^"]+)"', rendered_post)
        blog = [h for h in links if "styles/blog.css" in h]
        assert len(blog) == 1 and re.search(r"styles/blog\.css\?v=[0-9a-f]{8}$", blog[0]), links
        main = [h for h in links if "styles/main.css" in h]
        assert main and links.index(main[0]) < links.index(blog[0])
        style = re.search(r"<style>(.*?)</style>", rendered_post, re.S).group(1)
        assert len(style.encode("utf-8")) <= 10 * 1024

    def test_the_sheets_braces_balance(self, blog_css):
        depth = 0
        for i, ch in enumerate(_strip_css_comments(blog_css)):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                assert depth >= 0, f"unmatched '}}' at char {i} of blog.css"
        assert depth == 0

    def test_the_sheet_holds_no_jinja(self, blog_css):
        assert "{{" not in blog_css and "{%" not in blog_css and "{#" not in blog_css

    def test_the_rules_the_guards_read_are_where_they_say(self, template, blog_css):
        inline = re.search(r"<style>(.*?)</style>", template, re.S).group(1)
        for selector in (".blog-hero {", ".blog-toc {", ".blog-article {"):
            assert selector in inline, selector
        for selector in (".blog-article .blog-list-cont {", ".blog-article .blog-body-lang {",
                         ".blog-article a {", ".blog-chapter-list .chapter-time {",
                         ".blog-related-card {", "@media (max-width: 640px)"):
            assert selector in blog_css, selector
            assert selector not in inline, f"{selector} is in both"

    def test_the_covers_print_through_cover_img(self, template):
        """Never the 3000-square JPEG for a 28 px badge: the macro's srcset
        with sizes="60px" lets the browser take the 400 px WebP."""
        assert template.count("cover_img(path_prefix ~ podcast_image") == 2
        assert template.count("sizes='60px'") == 2
        assert "-400.webp" not in template
        assert 'import ai_badge, cover_img' in template

    def test_a_rendered_post_prints_its_cover_with_sizes(self, rendered_post):
        assert 'sizes="60px"' in rendered_post
        assert re.search(r'srcset="[^"]*-400\.webp 400w, [^"]*-800\.webp 800w, [^"]*\.webp 1400w" sizes="60px"',
                         rendered_post)


class TestTheServiceWorkerServesTheSheet:
    SW = (ROOT / "sw.js").read_text(encoding="utf-8")

    def test_styles_are_network_first(self):
        assert ("if (/^\\/(styles|assets\\/js)\\//.test(url.pathname)) {\n"
                "    event.respondWith(networkFirst(req, STATIC, null));") in self.SW

    def test_the_version_moved_with_the_sheet(self):
        m = re.search(r"var VERSION = 'nn-(\d{4}-\d{2}-\d{2})", self.SW)
        assert m and m.group(1) >= "2026-11-03", "bump VERSION: the posts load a new sheet"

    def test_the_sheet_is_precached_beside_main(self):
        precache = self.SW.split("var PRECACHE = [", 1)[1].split("];", 1)[0]
        assert "'/styles/main.css'" in precache and "'/styles/blog.css'" in precache
        assert (ROOT / "styles" / "blog.css").is_file()
