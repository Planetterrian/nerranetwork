"""Guards for the Oct 7 2026 blog pass (article pages, indexes, topic hubs).

GA4 put blog episode pages at a third of measured landing sessions with a 70%
bounce, and the review found why on the page itself: every post laid out
500-980px wide on a 390px phone, ~2,000 posts had no player, the headline was
printed three or four times before the first fact, and the interview posts
said the guest had approved a transcript the pipeline only SENDS them.

Every rendering guard here renders through the real template and the real
engine.blog path; none reads a committed .html, which the pipeline refreshes
and a working tree does not.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"


def _template(name: str) -> str:
    """Template source with Jinja comments stripped, so prose describing a
    rule can never satisfy (or trip) an assertion about the rule."""
    src = (TEMPLATES / name).read_text(encoding="utf-8")
    return re.sub(r"\{#.*?#\}", "", src, flags=re.S)


def _latest_digest(show_dir: str) -> Path:
    paths = sorted(
        p for p in (ROOT / "digests" / show_dir).glob("*_Ep*_*.md")
        if re.search(r"_Ep\d+_\d{8}\.md$", p.name))
    if not paths:
        pytest.skip(f"no committed digest for {show_dir}")
    return paths[-1]


def _render(slug: str, md_path: Path, *, related=None, keep_audio=False) -> str:
    import generate_html as G
    from engine.blog import extract_blog_metadata, generate_blog_post_html

    md = md_path.read_text(encoding="utf-8")
    meta = extract_blog_metadata(md, slug, md_path.name, file_path=md_path)
    meta["_md_path"] = md_path
    if not keep_audio:
        meta.pop("audio_url", None)
    return generate_blog_post_html(
        md, meta, G.NETWORK_SHOWS[slug], G._get_jinja_env(),
        related_posts=[] if related is None else related)


@pytest.fixture(scope="module")
def tesla_post():
    return _render("tesla", _latest_digest("tesla_shorts_time"))


@pytest.fixture(scope="module")
def dp_pod_post():
    return _render("dp_pod", _latest_digest("dp_pod"))


@pytest.fixture(scope="module")
def interview_post():
    return _render("age_of_ai", _latest_digest("age_of_ai"))


def _body(html: str) -> str:
    m = re.search(r'<div class="blog-body-lang" data-lang="en">(.*?)</div>\s*'
                  r'(?:<div class="blog-body-lang"|<!-- Sources -->|\{)', html, re.S)
    assert m, "no English body block"
    return m.group(1)


class TestThePageFitsAPhone:
    """P0: the provenance spans were ``white-space: nowrap`` and joined with no
    whitespace, so the whole line was one unbreakable run."""

    def test_provenance_parts_are_not_nowrap(self):
        css = _template("blog_post.html.j2")
        assert not re.search(r"\.nn-iv-provenance\s+span\s*\{[^}]*nowrap", css)

    @pytest.mark.parametrize("fixture", ["tesla_post", "dp_pod_post", "interview_post"])
    def test_provenance_parts_are_separated_by_whitespace(self, fixture, request):
        html = request.getfixturevalue(fixture)
        m = re.search(r'<p class="nn-iv-provenance[^"]*">(.*?)</p>', html, re.S)
        assert m, f"{fixture}: no provenance line rendered"
        line = m.group(1)
        assert "</span><span" not in line, "parts glued into one run"
        assert re.search(r'</span>\s+<span aria-hidden="true">', line)

    def test_article_column_cannot_be_widened_by_its_content(self):
        css = _template("blog_post.html.j2")
        block = re.search(r"\.blog-article\s*\{([^}]*)\}", css).group(1)
        assert "overflow-wrap: anywhere" in block
        assert "max-width: 100%" in block
        assert "minmax(0, 1fr)" in css


class TestEveryPostHasAPlayer:
    def test_english_only_post_renders_a_player(self, dp_pod_post):
        """The only <audio> used to be inside the language switcher."""
        assert 'id="listen"' in dp_pod_post
        # The player box, not the language switcher (no pills, no tracks).
        assert 'class="nn-listen"' in dp_pod_post
        m = re.search(r'<audio id="nn-i18n-audio"[^>]*src="([^"]+)"', dp_pod_post)
        assert m, "no player on an episode with published audio"
        assert m.group(1).startswith("https://op3.dev/e/audio.nerranetwork.com/"), (
            "the player must play the measured (OP3) URL the feed carries")

    def test_hero_listen_button_goes_to_the_player(self, dp_pod_post):
        hero = dp_pod_post.split('<header class="blog-hero">', 1)[1].split("</header>", 1)[0]
        assert 'href="#listen" class="blog-listen-cta"' in hero

    def test_audio_url_comes_from_the_feed_when_summaries_have_aged_out(self):
        """Summaries keep ~30 records; the feed carries every live episode."""
        import generate_html as G
        from engine.blog import _summaries_audio, _feed_enclosures, episode_audio_url

        cfg = G.NETWORK_SHOWS["tesla"]
        summ = ROOT / cfg["json_path"]
        feed = ROOT / cfg["rss_file"]
        in_summaries = _summaries_audio(str(summ), summ.stat().st_mtime)
        in_feed = _feed_enclosures(str(feed), feed.stat().st_mtime)
        older = sorted(set(in_feed) - set(in_summaries))
        if not older:
            pytest.skip("every feed episode is also in the summaries file")
        ep = older[0]
        assert episode_audio_url(cfg, ep) == in_feed[ep]
        assert episode_audio_url(cfg, 0) == ""

    def test_no_audio_means_no_player_and_no_dead_anchor(self):
        """No surface advertises something that does not exist."""
        src = _template("blog_post.html.j2")
        assert "{% elif audio_url and not interview %}" in src
        assert '{% if audio_url %}\n                <a href="#listen"' in src


class TestTheHeadlineIsPrintedOnce:
    def test_h1_is_the_title_alone(self, tesla_post):
        h1 = re.search(r'<header class="blog-hero">.*?<h1>(.*?)</h1>', tesla_post, re.S).group(1)
        assert "Episode" not in re.sub(r"<[^>]+>", "", h1)

    def test_no_sub_line_that_repeats_the_title(self, tesla_post, dp_pod_post):
        for html in (tesla_post, dp_pod_post):
            title = re.sub(r"<[^>]+>", "", re.search(
                r'<header class="blog-hero">.*?<h1>(.*?)</h1>', html, re.S).group(1)).strip()
            hook = re.search(r'<p class="blog-hero-hook">(.*?)</p>', html, re.S)
            assert hook is None or hook.group(1).strip() != title

    def test_body_does_not_reopen_on_show_name_or_hook(self, dp_pod_post):
        import generate_html as G

        body = _body(dp_pod_post)
        first = re.search(r"<(h\d|p|hr)\b[^>]*>(.*?)(?:</\1>|$)", body.strip(), re.S)
        show = G.NETWORK_SHOWS["dp_pod"]["name"]
        title = re.sub(r"<[^>]+>", "", re.search(
            r'<header class="blog-hero">.*?<h1>(.*?)</h1>', dp_pod_post, re.S).group(1)).strip()
        text = re.sub(r"<[^>]+>", "", first.group(2)).strip()
        assert first.group(1) != "hr", "body opens on a bare rule"
        assert not text.startswith(show)
        assert text != title

    def test_drop_leading_repeats_only_touches_the_lead(self):
        from engine.blog import drop_leading_repeats

        md = ("# Show Name\n\n**Price:** 1\n\n*The hook.*\n\n---\n\n### Section\n\n"
              "*The hook.*\n\n# Show Name later\n")
        out = drop_leading_repeats(md, "Show Name", "The hook.")
        assert "# Show Name\n" not in out
        assert out.count("*The hook.*") == 1, "only the leading copy goes"
        assert "# Show Name later" in out
        assert "**Price:** 1" in out


class TestHeadingOutline:
    @pytest.mark.parametrize("fixture", ["tesla_post", "dp_pod_post"])
    def test_body_starts_at_h2_and_never_skips_a_level(self, fixture, request):
        levels = [int(n) for n in re.findall(r"<h([1-6])\b", _body(request.getfixturevalue(fixture)))]
        assert levels, "no headings"
        assert levels[0] == 2
        for prev, cur in zip(levels, levels[1:]):
            assert cur <= prev + 1, f"skipped a level: h{prev} -> h{cur}"

    def test_levels_nest_rather_than_shift(self):
        from engine.blog import convert_md_to_blog_html

        def levels(md):
            return [t["level"] for t in convert_md_to_blog_html(md)[1]]

        assert levels("### A\n\ntext\n\n### B\n") == [2, 2]
        assert levels("## A\n\n### B\n\n## C\n") == [2, 3, 2]
        # Tesla: one "##" between "###" sections must not open on an h3.
        assert levels("### A\n\n### B\n\n## C\n\n### D\n") == [2, 2, 2, 3]


class TestReadability:
    def test_item_bodies_are_full_text_colour(self):
        block = re.search(r"\.blog-article \.blog-list-cont\s*\{([^}]*)\}",
                          _template("blog_post.html.j2")).group(1)
        assert "var(--nn-text)" in block and "muted" not in block

    def test_body_has_a_reading_measure(self):
        block = re.search(r"\.blog-article \.blog-body-lang\s*\{([^}]*)\}",
                          _template("blog_post.html.j2")).group(1)
        m = re.search(r"max-width:\s*(\d+)ch", block)
        assert m and 66 <= int(m.group(1)) <= 75


class TestTextContrast:
    def test_chapter_times_use_the_text_variant(self):
        block = re.search(r"\.blog-chapter-list \.chapter-time\s*\{([^}]*)\}",
                          _template("blog_post.html.j2")).group(1)
        assert "var(--show-color-text" in block

    @pytest.mark.parametrize("name", ["blog_index.html.j2", "network_blog_index.html.j2"])
    def test_card_text_in_show_colour_is_lightened(self, name):
        src = _template(name)
        assert re.search(r"\.blog-idx-card \.blog-idx-ep,\s*\.blog-idx-card \.blog-idx-read-more[^{]*\{\s*"
                         r"color:\s*color-mix\(in srgb, var\(--card-accent\), white 35%\)", src)

    def test_network_index_never_sets_raw_show_colour_as_text(self):
        src = _template("network_blog_index.html.j2")
        assert not re.search(r"[;\"]\s*color:\s*\{\{\s*post\.show_color\s*\}\}", src)
        assert not re.search(r"(?<![-\w])color:\s*var\(--nn-purple\)", src)


class TestCrossShowRecommendations:
    def test_pool_is_newest_first_on_iso_date(self):
        import generate_html as G

        pool = G._cross_show_pool()
        assert pool, "empty pool — no post could recommend anything"
        dates = [p["date_iso"] for p in pool]
        assert dates == sorted(dates, reverse=True)

    def test_a_post_rendered_without_a_pool_still_recommends(self):
        """run_show and the per-show regen passed no pool, so no post they
        wrote ever carried "You Might Also Like"."""
        import generate_html as G
        from engine.blog import extract_blog_metadata, generate_blog_post_html

        md_path = _latest_digest("dp_pod")
        md = md_path.read_text(encoding="utf-8")
        meta = extract_blog_metadata(md, "dp_pod", md_path.name, file_path=md_path)
        meta["_md_path"] = md_path
        html = generate_blog_post_html(md, meta, G.NETWORK_SHOWS["dp_pod"], G._get_jinja_env())
        assert "You Might Also Like" in html

    def test_explicit_empty_list_still_means_none(self, dp_pod_post):
        assert "You Might Also Like" not in dp_pod_post

    def test_per_show_regen_builds_a_pool(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        body = src.split("def generate_blog_posts(", 1)[1].split("\ndef ", 1)[0]
        assert "if cross_show_posts is None:" in body
        assert "_cross_show_pool()" in body


class TestCardsSayTheSentenceOnce:
    def test_show_index_card(self, tmp_path):
        import generate_html as G

        G.generate_blog_index("dp_pod", output_dir=tmp_path)
        html = (tmp_path / "blog" / "dp_pod" / "index.html").read_text(encoding="utf-8")
        cards = re.findall(r"<h2>(.*?)</h2>\s*(?:<p>(.*?)</p>)?", html, re.S)
        assert cards
        for title, para in cards:
            assert not para or para.strip() != title.strip()

    def test_network_index_card(self):
        import generate_html as G
        from engine.blog import extract_blog_metadata, generate_network_blog_index_html

        posts = []
        for slug, show_dir in (("dp_pod", "dp_pod"), ("spacex", "spacex")):
            for p in sorted((ROOT / "digests" / show_dir).glob("*_Ep*_*.md"))[-5:]:
                meta = extract_blog_metadata(p.read_text(encoding="utf-8"), slug,
                                             p.name, file_path=p)
                meta["show_slug"] = slug
                posts.append(meta)
        assert posts
        html = generate_network_blog_index_html(posts, G.NETWORK_SHOWS, G._get_jinja_env())
        cards = re.findall(r"<h2>(.*?)</h2>\s*(?:<p>(.*?)</p>)?", html, re.S)
        assert cards
        for title, para in cards:
            assert not para or para.strip() != title.strip()

    def test_related_card(self):
        src = _template("blog_post.html.j2")
        assert "rp.hook | trim != rp.title | trim" in src


class TestNetworkIndexOnAPhone:
    def test_chips_are_one_scrolling_row_under_640(self):
        src = _template("network_blog_index.html.j2")
        m = re.search(r"@media \(max-width: 640px\)\s*\{(.*?)\n        \}", src, re.S)
        assert m
        assert "flex-wrap: nowrap" in m.group(1) and "overflow-x: auto" in m.group(1)

    def test_search_box_says_what_it_does(self):
        src = _template("network_blog_index.html.j2")
        assert 'placeholder="Filter these posts…"' in src
        assert "Search articles" not in src

    def test_active_page_button_is_marked_current(self):
        assert "setAttribute('aria-current', 'page')" in _template("network_blog_index.html.j2")


class TestInterviewApprovalWording:
    """A guest is SENT the transcript to approve, cut from or refuse, and
    seven days of silence publishes — never "approved by the guest"."""

    _BANNED = re.compile(r"approved by|when they approved|until the guest (?:has )?(?:read and )?approve",
                         re.I)

    def test_committed_interview_digests(self):
        for show_dir in ("age_of_ai", "nerra_voices"):
            for path in (ROOT / "digests" / show_dir).glob("*.md"):
                head = path.read_text(encoding="utf-8").split("### Transcript", 1)
                # The guest's own words below the transcript note are theirs.
                note = head[1].split("\n\n", 2)[1] if len(head) > 1 else ""
                for text in (head[0], note):
                    assert not self._BANNED.search(text), f"{path.name}: {text[:120]!r}"

    def test_publisher_writes_the_gate_as_built(self):
        src = (ROOT / "pipelines" / "voices" / "publish_episode.py").read_text(encoding="utf-8")
        code = "\n".join(
            n.value for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and not n.value.lstrip().startswith(("Publish an approved", "Interview ids")))
        assert not re.search(r"approved by \{name\}|when they approved|"
                             r"published until the guest", code)
        note = next(n.value.value for n in ast.walk(ast.parse(src))
                    if isinstance(n, ast.Assign)
                    and getattr(n.targets[0], "id", "") == "TRANSCRIPT_NOTE")
        assert "approve, cut from or refuse before publication" in note

    def test_post_and_hub_copy(self, interview_post):
        from engine.topic_hubs import hub_by_id

        assert not self._BANNED.search(re.sub(r"<[^>]+>", " ", interview_post).split(
            "Full conversation transcript", 1)[0])
        hub = hub_by_id("interviews")
        for key in ("title", "intro", "angle", "meta_description"):
            assert not self._BANNED.search(hub[key]), key
            assert "guest-approved" not in hub[key]

    def test_talking_points_render_markdown(self, interview_post):
        points = re.search(r'<ul class="nn-iv-points">(.*?)</ul>', interview_post, re.S)
        if not points:
            pytest.skip("latest interview has no talking points")
        assert not re.search(r"(?<![\w*])\*[^*\s][^*]*\*", points.group(1))


class TestTopicHubCounts:
    _NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8}

    def test_no_typed_count_contradicts_the_shows_listed(self):
        """Hub membership is a registry edit; a count typed into the intro
        ("Four shows", "three ways") goes stale the day a show joins."""
        import generate_html as G
        from engine.topic_hubs import TOPIC_HUBS, hub_shows

        shows = G._build_all_shows_list()
        for hub in TOPIC_HUBS:
            n = len(hub_shows(hub, shows))
            for word in re.findall(r"\b(one|two|three|four|five|six|seven|eight)\s+"
                                   r"(?:\w+\s+)?(?:shows|ways|jobs)\b",
                                   hub["intro"], re.I):
                assert self._NUMBERS[word.lower()] == n, (
                    f"hub {hub['id']!r} says {word!r} but lists {n} show(s)")

    def test_story_tracker_box_has_a_space_after_the_question(self, tesla_post):
        if "blog-story-tracker" not in tesla_post:
            pytest.skip("no story tracker on this show")
        box = tesla_post.split('class="blog-story-tracker"', 1)[1].split("</section>", 1)[0]
        assert re.search(r"long arcs\?</strong>\s+\S", box)

    def test_prev_next_name_the_episode(self):
        src = _template("blog_post.html.j2")
        assert "prev_post.title" in src and "next_post.title" in src
