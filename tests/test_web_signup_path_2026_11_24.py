"""Nov 24 2026 — the path from a visitor to a listener, a follower, a subscriber.

Measured on a 390x844 phone against the committed pages:

* every show page opened on its cover and a description up to a screen and a
  half long; the play and follow buttons were on screen two;
* ``nerra-daily.html`` is the address every ask for the email points at
  (the show notes, and the on-air line), and its form sat two screens down;
* an episode post, where search and shared links land, linked no podcast
  app anywhere on a phone;
* the hero and post sign-up bands put their status line AFTER the form, and
  ``footer-subscribe.js`` looked for it only INSIDE the form, so the
  confirmation sentence and every error on the front page's own sign-up
  form were never shown.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHOW_TPL = (ROOT / "templates" / "show_page.html.j2").read_text(encoding="utf-8")
POST_TPL = (ROOT / "templates" / "blog_post.html.j2").read_text(encoding="utf-8")
MACROS = (ROOT / "templates" / "_macros.html.j2").read_text(encoding="utf-8")
MAIN_CSS = (ROOT / "styles" / "main.css").read_text(encoding="utf-8")
SUBSCRIBE_JS = (ROOT / "assets" / "js" / "footer-subscribe.js").read_text(encoding="utf-8")


def _strip_jinja_comments(src: str) -> str:
    return re.sub(r"\{#.*?#\}", "", src, flags=re.S)


def _phone_hero_block() -> str:
    start = MAIN_CSS.index("Show hero on a phone: the actions first")
    block = MAIN_CSS[start:]
    return block[block.index("@media (max-width: 639px)"):]


class TestShowHeroOnAPhone:
    def test_actions_and_follow_come_before_the_description(self):
        css = _phone_hero_block()
        order = {
            name: int(re.search(
                re.escape(sel) + r"\s*\{[^}]*order:\s*(\d+)", css).group(1))
            for name, sel in {
                "actions": ".show-hero-info > .show-hero-actions",
                "follow": ".show-hero-info > .show-hero-subscribe",
                "email": ".show-hero-info > .show-hero-email",
                "desc": ".show-hero-info > .show-hero-desc",
            }.items()
        }
        assert order["email"] < order["actions"] < order["follow"] < order["desc"]

    def test_the_cover_is_small_enough_to_leave_room(self):
        m = re.search(r"\.show-hero-art\s*\{\s*width:\s*(\d+)px", _phone_hero_block())
        assert m and int(m.group(1)) <= 128

    def test_the_description_is_clamped_only_by_the_script(self):
        # No script, no clamp: the class the CSS clamps is one only the
        # script adds, and the button that undoes it ships hidden.
        assert ".show-hero-desc.is-clamped" in _phone_hero_block()
        src = _strip_jinja_comments(SHOW_TPL)
        assert 'id="showHeroDesc">{{ show_description }}</p>' in src
        assert re.search(r'id="showHeroDescMore"[^>]*\bhidden\b', src)
        assert "classList.add('is-clamped')" in src

    def test_listen_now_starts_the_latest_episode(self):
        src = _strip_jinja_comments(SHOW_TPL)
        assert "data-nn-play-latest" in src
        assert "NNPlayer.playElement(a)" in src


class TestNerraDailyPageAsksForTheEmailFirst:
    def test_the_form_is_in_the_hero_before_the_buttons(self):
        src = _strip_jinja_comments(SHOW_TPL)
        call = src.index("hero_email_signup(path_prefix")
        assert "show_slug == 'nerra_daily'" in src[call - 200:call]
        assert call < src.index('<div class="show-hero-actions">')

    def test_one_ask_not_two(self):
        src = _strip_jinja_comments(SHOW_TPL)
        band = src.index("{% if soft_personal_hero and not _is_ru %}")
        skip = src.index("{% elif show_slug == 'nerra_daily' and not _is_ru %}", band)
        assert skip < src.index("{% elif newsletter_tag %}", band)

    @pytest.fixture()
    def rendered(self):
        import jinja2

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(ROOT / "templates")),
            autoescape=True)
        macro = env.get_template("_macros.html.j2").module.hero_email_signup
        shows = [
            {"slug": "nerra_daily", "name": "Nerra Daily", "newsletter_tag": "Nerra Daily"},
            {"slug": "tesla", "name": "Tesla Shorts Time", "newsletter_tag": "Tesla Shorts Time"},
            {"slug": "no_tag", "name": "No Tag", "newsletter_tag": ""},
        ]
        return str(macro("", "nerra_daily", "src-nerranetwork", shows))

    def test_it_joins_the_newsletter_list_itself(self, rendered):
        # ``member`` carries nerra-member, the tag the one email goes to.
        assert 'data-list="member"' in rendered
        assert 'method="post"' in rendered
        assert 'data-source="src-nerranetwork"' in rendered

    def test_the_picker_offers_shows_never_the_page_itself(self, rendered):
        values = re.findall(r'name="tag" value="([^"]*)"', rendered)
        assert values == ["Tesla Shorts Time"]

    def test_it_says_what_happens_next_and_never_check_your_email(self, rendered):
        assert "7:00 AM Eastern" in rendered
        assert "data-nn-subscribe-status" in rendered
        assert "check your email" not in rendered.lower()

    def test_no_free_surface_claim(self, rendered):
        assert "ad-free" not in rendered.lower()


class TestTheStatusLineIsFound:
    def test_the_bands_put_the_status_line_after_the_form(self):
        # The premise of the fix: if this stops being true the fallback is
        # dead code, not wrong.
        for macro in ("soft_personal_hero_band", "soft_personal_post_band",
                      "hero_email_signup"):
            body = MACROS[MACROS.index("macro " + macro):]
            body = body[:body.index("endmacro")]
            assert body.index("</form>") < body.index("data-nn-subscribe-status"), macro

    def test_the_script_looks_beside_the_form_too(self):
        fn = SUBSCRIBE_JS[SUBSCRIBE_JS.index("function statusEl(form)"):]
        fn = fn[:fn.index("function say(")]
        assert "form.querySelector(sel)" in fn
        assert "form.parentNode.querySelector(sel)" in fn


class TestEmailFieldsDoNotZoomThePage:
    """iOS Safari zooms the page when a focused field is under 16px."""

    @pytest.mark.parametrize("name,src", [("macros", MACROS), ("show", SHOW_TPL)])
    def test_inline_styled_email_fields_are_16px(self, name, src):
        for tag in re.findall(r'<input type="email"[^>]*>', _strip_jinja_comments(src), flags=re.S):
            m = re.search(r"font-size:\s*([^;\"]+)", tag)
            if m:
                assert m.group(1).strip() == "16px", (name, tag[:120])

    def test_the_hero_field_is_16px(self):
        assert re.search(
            r'\.show-hero-email-form input\[type="email"\]\s*\{[^}]*font-size:\s*16px', MAIN_CSS)


class TestEpisodePostsLinkThePodcastApps:
    def test_public_show_gets_its_apps_and_feed(self):
        from engine.blog import show_follow_links
        from generate_html import NETWORK_SHOWS

        links = show_follow_links("tesla", NETWORK_SHOWS["tesla"])
        kinds = [x["kind"] for x in links]
        assert kinds[0] == "apple" and "spotify" in kinds and kinds[-1] == "rss"
        assert all(x["url"] for x in links)

    def test_a_members_only_show_asks_for_no_follow(self):
        from engine import access
        from engine.blog import show_follow_links
        from generate_html import NETWORK_SHOWS

        gated = [s for s in access.gated_shows() if s in NETWORK_SHOWS]
        assert gated, "expected at least one gated show in the registry"
        for slug in gated:
            assert show_follow_links(slug, NETWORK_SHOWS[slug]) == []

    def test_a_show_with_no_feed_on_disk_links_nothing(self):
        from engine.blog import show_follow_links

        assert show_follow_links("tesla", {"rss_file": "no_such_feed.rss"}) == []
        assert show_follow_links("tesla", None) == []

    def test_the_row_sits_in_the_hero_and_tags_its_links(self):
        src = _strip_jinja_comments(POST_TPL)
        row = src.index('class="blog-follow-row"')
        assert src.index('<header class="blog-hero">') < row < src.index('class="blog-article-wrap"')
        seg = src[row:row + 1600]
        assert "with_utm(campaign=show_slug, medium='blog')" in seg
        assert 'data-show="{{ show_slug }}"' in seg  # tracking.js subscribe_click

    def test_the_share_button_shows_only_where_a_share_sheet_exists(self):
        src = _strip_jinja_comments(POST_TPL)
        assert re.search(r'class="blog-follow-chip blog-share-native" hidden', src)
        assert "if (!b || !navigator.share) return;" in src

    def test_the_share_event_is_one_the_nightly_reads(self):
        from scripts.fetch_ga4_stats import ENGAGEMENT_EVENTS

        assert "share" in ENGAGEMENT_EVENTS


def test_nerra_daily_has_an_approved_search_title():
    import generate_html as G

    title, meta = G.SEO_PAGE_COPY["nerra-daily.html"]
    assert title.startswith("Nerra Daily:") and len(title) <= 60
    assert "email" in title.lower() and len(meta) <= 160
    assert "ad-free" not in (title + meta).lower()
