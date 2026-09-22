"""The Age of AI finishing pass (Sep 22 2026, PR E2).

After the truth pass (tests/test_age_of_ai_truth_2026_09_22.py) the pages
said nothing false; this pass makes them complete:

* the interview steps have ONE owner (engine.brand) and one macro, rendered
  in full on /mira.html and in compact form on the interview show pages;
* a show whose YAML carries a Spotify id gets a Spotify chip (six did not);
* the guest rail, the creator credit and the steps are styled from the
  shared stylesheet, not from one page's <style> block;
* an interview post carries its chapters in the page's real chapter section
  (click-to-seek), a one-line provenance under the player, the scoped
  creator credit, the guest's name in the breadcrumb and the JSON-LD, the
  bio labelled as the guest's own words, and "Suggest a guest";
* the interview blog index leads each card with the person;
* the registry no longer says Mira "calls" people, and the about text no
  longer interviews them twice.

Every rendered assertion renders into tmp_path — a committed page still
carries the previous chrome on any checkout.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

import generate_html as G
from engine import brand
from engine.interviews import interview_body_markdown

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
AOAI_DIGESTS = ROOT / "digests" / "age_of_ai"
CSS = (ROOT / "styles" / "main.css").read_text(encoding="utf-8")


def _strip_jinja_comments(text: str) -> str:
    return re.sub(r"\{#.*?#\}", "", text, flags=re.S)


def _template(name: str) -> str:
    return _strip_jinja_comments((TEMPLATES / name).read_text(encoding="utf-8"))


def _post(num: int, prev: int, nxt, slug: str = "age_of_ai") -> str:
    from engine.blog import extract_blog_metadata, generate_blog_post_html

    digest_dir = ROOT / "digests" / G._SHOW_DIRS.get(slug, slug)
    path = sorted(digest_dir.glob(f"*Ep{num:03d}_*.md"))[-1]
    md = path.read_text(encoding="utf-8")
    meta = extract_blog_metadata(md, slug, path.name, file_path=path)
    meta["_md_path"] = path
    return G._strip_lone_surrogates(generate_blog_post_html(
        md, meta, G.NETWORK_SHOWS[slug], G._get_jinja_env(),
        prev_post={"episode_num": prev},
        next_post={"episode_num": nxt} if nxt else None,
    ))


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    out = tmp_path_factory.mktemp("finish")
    G.generate_mira_page(output_dir=out)
    for slug in ("age_of_ai", "nerra_daily", "tesla", "nerra_voices"):
        G.generate_show_page(slug, output_dir=out)
    G.generate_blog_index("age_of_ai", output_dir=out)
    G.generate_blog_index("tesla", output_dir=out)
    return {
        "mira": (out / "mira.html").read_text(encoding="utf-8"),
        "aoai": (out / "age-of-ai.html").read_text(encoding="utf-8"),
        "daily": (out / "nerra-daily.html").read_text(encoding="utf-8"),
        "tesla": (out / "tesla.html").read_text(encoding="utf-8"),
        "voices": (out / "nerra-voices.html").read_text(encoding="utf-8"),
        "aoai_index": (out / "blog" / "age_of_ai" / "index.html").read_text(encoding="utf-8"),
        "tesla_index": (out / "blog" / "tesla" / "index.html").read_text(encoding="utf-8"),
    }


# ---------------------------------------------------------------------------
# 1. The interview steps have one owner
# ---------------------------------------------------------------------------

class TestInterviewStepsHaveOneOwner:
    def test_generate_html_re_exports_the_same_list(self):
        assert G.MIRA_INTERVIEW_STEPS is brand.MIRA_INTERVIEW_STEPS
        assert len(brand.MIRA_INTERVIEW_STEPS) == 8

    def test_the_compact_subset_indexes_the_full_list(self):
        assert all(0 <= i < len(brand.MIRA_INTERVIEW_STEPS)
                   for i in brand.MIRA_INTERVIEW_STEPS_COMPACT)
        assert len(set(brand.MIRA_INTERVIEW_STEPS_COMPACT)) == len(brand.MIRA_INTERVIEW_STEPS_COMPACT)
        titles = [brand.MIRA_INTERVIEW_STEPS[i][0] for i in brand.MIRA_INTERVIEW_STEPS_COMPACT]
        # The two human gates are never left out of the short form.
        assert any("human reads" in t.lower() for t in titles)
        assert any("human edits" in t.lower() for t in titles)

    def test_no_template_types_a_step(self):
        """The detail sentences are the quotable copy; a title is three words
        that can turn up in honest prose (start-here says "you approve your
        transcript" in a sentence of its own)."""
        for path in TEMPLATES.glob("*.j2"):
            body = _strip_jinja_comments(path.read_text(encoding="utf-8"))
            for title, detail in brand.MIRA_INTERVIEW_STEPS:
                probe = detail[:48]
                assert probe not in body, f"{path.name} hardcodes the step {title!r}"

    def test_the_macro_reads_the_registered_globals(self):
        macros = (TEMPLATES / "_macros.html.j2").read_text(encoding="utf-8")
        body = macros.split("macro mira_steps_list(")[1]
        assert "mira_steps_compact" in body and "mira_steps" in body
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert 'env.globals["mira_steps"]' in src
        assert 'env.globals["mira_steps_compact"]' in src

    def test_the_hub_renders_all_eight_and_the_show_page_the_short_form(self, pages):
        for title, _ in brand.MIRA_INTERVIEW_STEPS:
            assert f"<h3>{title}</h3>" in pages["mira"]
        compact = [brand.MIRA_INTERVIEW_STEPS[i][0] for i in brand.MIRA_INTERVIEW_STEPS_COMPACT]
        for title in compact:
            assert f"<h3>{title}</h3>" in pages["aoai"]
        assert pages["aoai"].count('<ol class="mira-steps') == 1
        assert "mira-steps--compact" in pages["aoai"]

    def test_a_mira_show_without_interviews_shows_no_steps(self, pages):
        """Nerra Daily is strand: mira and takes no guests."""
        assert '<ol class="mira-steps' not in pages["daily"]
        assert '<ol class="mira-steps' not in pages["tesla"]


# ---------------------------------------------------------------------------
# 2. Spotify follows the show YAML the way Apple does
# ---------------------------------------------------------------------------

class TestSpotifyLinkDerivedFromTheYaml:
    def test_registry_wins_when_set(self):
        assert G._spotify_url_for("tesla", "https://example.test/x") == "https://example.test/x"

    def test_the_id_fills_the_gap(self):
        data = yaml.safe_load((ROOT / "shows" / "age_of_ai.yaml").read_text(encoding="utf-8"))
        assert data["spotify_show_id"]
        assert G._spotify_url_for("age_of_ai", None) == (
            f"https://open.spotify.com/show/{data['spotify_show_id']}")

    def test_no_id_and_no_registry_url_renders_nothing(self):
        assert G._spotify_url_for("nerra_voices", None) == ""

    def test_the_chip_is_on_the_page(self, pages):
        assert "open.spotify.com/show/" in pages["aoai"]
        assert "open.spotify.com/show/" not in pages["voices"]


# ---------------------------------------------------------------------------
# 3. Shared styles live in the shared stylesheet
# ---------------------------------------------------------------------------

class TestSharedStylesAreShared:
    @pytest.mark.parametrize("token", [".nn-guest-grid", ".nn-guest-cohost",
                                       ".nn-creator", ".mira-steps",
                                       ".mira-steps--compact",
                                       ".blog-idx-guest-role"])
    def test_token_is_in_main_css(self, token):
        assert token in CSS

    def test_no_page_keeps_a_private_copy(self):
        for name in ("show_page.html.j2", "mira_page.html.j2"):
            body = _template(name)
            assert ".nn-guest-grid {" not in body, f"{name} still carries the guest CSS"
            assert ".mira-steps {" not in body, f"{name} still carries the steps CSS"
            assert ".nn-creator {" not in body


# ---------------------------------------------------------------------------
# 4. The interview post
# ---------------------------------------------------------------------------

class TestInterviewPost:
    @pytest.fixture(scope="class")
    def ep4(self):
        return _post(4, 3, 5)

    @pytest.fixture(scope="class")
    def ep7(self):
        return _post(7, 6, None)

    @pytest.fixture(scope="class")
    def tesla(self):
        nums = sorted(int(re.search(r"Ep(\d+)_", p.name).group(1))
                      for p in (ROOT / "digests" / "tesla_shorts_time").glob("*Ep*_*.md"))
        return _post(nums[-1], nums[-2], None, slug="tesla")

    def test_chapters_render_in_the_real_section_not_the_body(self, ep4):
        assert '<section class="blog-chapters" id="chapters">' in ep4
        assert ep4.count('class="chapter-time"') == 8
        assert "In this conversation" in ep4
        assert '<h4 id="chapters"' not in ep4
        assert '<div class="blog-toc-title">' not in ep4  # no one-item TOC

    def test_the_body_no_longer_carries_the_chapter_list(self):
        md = sorted(AOAI_DIGESTS.glob("*Ep004_*.md"))[-1].read_text(encoding="utf-8")
        assert "### Chapters" in md
        assert "### Chapters" not in interview_body_markdown(md)

    def test_an_episode_without_chapters_has_no_section(self, ep7):
        assert '<section class="blog-chapters"' not in ep7

    def test_seeking_falls_back_to_the_interview_player(self):
        tpl = _template("blog_post.html.j2")
        script = tpl.split('id="chapters"')[1][:2500]
        assert 'getElementById("nn-i18n-audio")' in script  # the pinned literal
        assert '.nn-iv-player audio' in script

    def test_the_provenance_line_says_what_the_pipeline_does(self, ep4, ep7):
        for html in (ep4, ep7):
            assert 'class="nn-iv-provenance"' in html
            assert f"Hosted by {brand.MIRA_HOST_NAME}, an AI" in html
            assert f"Reviewed before release by {brand.NETWORK_CREATOR_NAME}" in html
            assert "Transcript sent to" in html
        assert f"{brand.NETWORK_CREATOR_NAME} co-hosted" in ep7
        assert f"{brand.NETWORK_CREATOR_NAME} co-hosted" not in ep4

    def test_the_provenance_never_claims_an_approval(self):
        """Seven days of silence also publishes; "approved by" would be a
        claim the pipeline cannot make for every episode."""
        line = " ".join(brand.interview_provenance("Jane Doe", "")).lower()
        assert "approved by" not in line
        assert "approve, cut or refuse" in line

    def test_the_credit_is_on_the_post_and_scoped(self, ep4, tesla):
        for para in brand.creator_credit("age_of_ai"):
            assert para in ep4
        assert 'class="nn-creator"' in ep4
        assert 'class="nn-creator"' not in tesla
        assert brand.CREATOR_REVIEW_ROLE not in tesla

    def test_the_breadcrumb_and_json_ld_name_the_guest(self, ep4):
        assert ">Hogan Shrum</li>" in ep4
        assert '"name": "Hogan Shrum"}' in ep4  # BreadcrumbList
        blocks = re.findall(r'<script type="application/ld\+json">\s*(\[.*?\])\s*</script>',
                            ep4, re.S)
        assert blocks, "no JSON-LD array on the post"
        data = json.loads(blocks[0])
        for entry in data:
            assert entry.get("about") == {"@type": "Person", "name": "Hogan Shrum"}

    def test_the_bio_is_labelled_as_the_guests_own_words(self, ep4):
        assert "In their own words" in ep4

    def test_the_feedback_row_asks_for_a_guest(self, ep4, tesla):
        assert "Suggest a guest" in ep4
        assert "Suggest a story" in tesla and "Suggest a guest" not in tesla

    def test_the_latest_post_gets_a_real_placeholder_card(self, ep7):
        assert 'class="next nav-next-placeholder"' in ep7
        assert "Next interview" in ep7 and "When it is ready" in ep7

    def test_a_news_post_carries_none_of_the_interview_chrome(self, tesla):
        for marker in ("nn-iv-provenance\"", "In their own words",
                       'class="nn-creator"', "Next interview"):
            assert marker not in tesla


# ---------------------------------------------------------------------------
# 5. The interview blog index leads with the person
# ---------------------------------------------------------------------------

class TestInterviewIndexCards:
    def test_every_published_guest_is_a_card(self, pages):
        data = json.loads((AOAI_DIGESTS / "summaries_age_of_ai.json").read_text(encoding="utf-8"))
        guests = [e["guest"] for e in data["episodes"] if e.get("guest") and e["episode"] != 1]
        for guest in guests:
            assert f"<h2>{guest}</h2>" in pages["aoai_index"], guest
        assert pages["aoai_index"].count("blog-idx-card--guest") == len(guests)

    def test_cards_carry_role_run_time_and_co_host(self, pages):
        idx = pages["aoai_index"]
        assert "Author, Memoirs of the End" in idx
        assert "46 min" in idx
        assert f"with {brand.NETWORK_CREATOR_NAME}" in idx
        assert "Listen &amp; read" in idx

    def test_a_news_index_is_untouched(self, pages):
        idx = pages["tesla_index"]
        assert "blog-idx-card--guest" not in idx
        assert "Read article" in idx


# ---------------------------------------------------------------------------
# 6. The copy
# ---------------------------------------------------------------------------

class TestCopy:
    def test_the_feed_no_longer_says_she_calls_people(self):
        data = yaml.safe_load((ROOT / "shows" / "age_of_ai.yaml").read_text(encoding="utf-8"))
        blob = json.dumps(data, ensure_ascii=False).lower()
        assert "calls real people" not in blob

    def test_about_text_interviews_them_once(self):
        about = G.NETWORK_SHOWS["age_of_ai"]["about_text"]
        assert about.count("interviews") == 1
