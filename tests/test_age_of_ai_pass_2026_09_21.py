"""Drift guards for the 2026-09-21 Age of AI pass.

Two things are guarded here and they are guarded differently on purpose.

The CREDIT guards assert a SCOPE PROPERTY: "the sentence that says a human
approves every episode is never handed to a show that has no such gate."
They are written against ``engine.brand.creator_credit`` and against rendered
pages, not against the wording, so rewriting the paragraph does not break
them and moving a show into ``HUMAN_REVIEW_SHOW_SLUGS`` without the gate does.
That is the failure this pass exists to prevent: the same overclaim sat on
``ai-disclosure.html`` for five months.

The RENDER guards render the CURRENT template into ``tmp_path`` via
``output_dir=``. They never read a committed ``.html`` file: generated HTML is
refreshed by the pipeline rather than committed from a working tree, so on any
checkout the committed page still carries the previous chrome and a guard that
reads it is asserting against yesterday.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import generate_html as G
from engine import brand
from engine.interviews import (
    INTERVIEW_SHOW_SLUGS,
    interview_body_markdown,
    interview_context,
    interview_episode_cards,
    is_interview_show,
    parse_interview_digest,
)

ROOT = Path(__file__).resolve().parent.parent
AOAI_DIGESTS = ROOT / "digests" / "age_of_ai"
AOAI_SUMMARIES = AOAI_DIGESTS / "summaries_age_of_ai.json"


def _markup_only(html: str) -> str:
    """*html* with its ``<style>`` blocks removed.

    Both templates are SHARED — the interview rules live in the same
    stylesheet every show's page carries, so a rule named ``.nn-guest-audio``
    is present in the source of a Tesla page that renders no guest cards.
    Counting class names across the whole document therefore measures the
    stylesheet, not the page. Strip the styles and the count means what the
    test says it means.
    """
    return re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.S)


def _strip_jinja_comments(text: str) -> str:
    """Remove ``{# ... #}`` blocks.

    A guard that reads a template as text can otherwise be satisfied by the
    comment that explains the rule it is checking, which is how one of this
    repo's footer guards passed under a mutation that broke the footer.
    """
    return re.sub(r"\{#.*?#\}", "", text, flags=re.S)


# ---------------------------------------------------------------------------
# The creator credit is scoped
# ---------------------------------------------------------------------------

class TestCreatorCreditScope:
    def test_review_claim_only_for_shows_with_the_gate(self):
        """The approval paragraph goes to ``HUMAN_REVIEW_SHOW_SLUGS`` alone.

        Every other show in the registry must get the network paragraph and
        nothing that claims an episode was read before it shipped.
        """
        for slug in G.NETWORK_SHOWS:
            paragraphs = brand.creator_credit(slug)
            has_review = brand.CREATOR_REVIEW_ROLE in paragraphs
            assert has_review == (slug in brand.HUMAN_REVIEW_SHOW_SLUGS), (
                f"{slug}: review claim present={has_review} but "
                f"in HUMAN_REVIEW_SHOW_SLUGS={slug in brand.HUMAN_REVIEW_SHOW_SLUGS}"
            )

    def test_every_human_review_show_bypasses_run_show(self):
        """A show only earns the claim if it has no ``shows/<slug>.yaml`` run.

        The gate lives in ``pipelines/voices/``. A run_show show has no human
        in the publish path at all, so adding one to the tuple would be the
        overclaim this module exists to stop. Age of AI keeps a registry-only
        ``shows/age_of_ai.yaml`` for publish surfaces, so the real test is
        that the Voices publisher — not run_show — is what ships it.
        """
        publisher = (ROOT / "pipelines" / "voices" / "publish_episode.py")
        assert publisher.exists()
        for slug in brand.HUMAN_REVIEW_SHOW_SLUGS:
            assert slug in INTERVIEW_SHOW_SLUGS, (
                f"{slug} claims a human review gate but is not an interview "
                "show; the gate is a Nerra Voices pipeline step"
            )

    def test_network_paragraph_claims_nothing_about_episode_review(self):
        """The always-rendered paragraph must be safe on a run_show page.

        It is the only one a daily show gets, and ``ai-disclosure.html`` says
        no human reads those before they ship.
        """
        text = brand.CREATOR_NETWORK_ROLE.lower()
        for forbidden in ("every episode", "approves", "before it publishes",
                          "before publication", "reviews each"):
            assert forbidden not in text, (
                f"network-wide credit implies per-episode review: {forbidden!r}"
            )

    def test_credit_never_puts_patrick_in_the_room(self):
        """He is not a co-host and does not sit in on interviews."""
        joined = " ".join(brand.creator_credit("age_of_ai")).lower()
        for forbidden in ("co-host", "cohost", "joins the conversation",
                          "sits in", "in the room as"):
            assert forbidden not in joined, (
                f"creator credit describes Patrick as present: {forbidden!r}"
            )
        assert "not in the room" in joined

    def test_credit_does_not_claim_a_training_loop(self):
        """"He tunes Mira" means prompts and rules, not fine-tuning."""
        text = brand.CREATOR_MIRA_ROLE.lower()
        for forbidden in ("trains her", "training data", "fine-tune",
                          "fine tunes", "retrains"):
            assert forbidden not in text, (
                f"Mira paragraph implies a training loop: {forbidden!r}"
            )
        assert "no model is retrained" in text


# ---------------------------------------------------------------------------
# The Mira claim is not widened by any of this
# ---------------------------------------------------------------------------

class TestMiraClaimNotWidened:
    def test_claim_still_rests_on_the_guest_deciding(self):
        claim = brand.MIRA_FIRST_CLAIM.lower()
        assert "decides whether the conversation is published" in claim

    def test_claim_ships_with_basis_and_footnote(self):
        paragraphs = brand.mira_claim_paragraphs()
        assert len(paragraphs) == 3
        assert brand.MIRA_FIRST_CLAIM_BASIS in paragraphs
        assert brand.MIRA_FIRST_CLAIM_FOOTNOTE in paragraphs

    def test_creator_credit_carries_no_superlative(self):
        """A "first"/"only" in the credit would be a second, unbacked claim.

        The network has exactly one superlative and it lives in the Mira
        claim, where its basis and its correction invitation travel with it.
        """
        joined = " ".join(brand.creator_credit("age_of_ai")).lower()
        for forbidden in ("the first", "the only", "world's", "nobody else",
                          "unique"):
            assert forbidden not in joined, (
                f"creator credit smuggles in a superlative: {forbidden!r}"
            )

    def test_templates_never_hardcode_the_claim(self):
        """The claim is rendered from engine/brand.py, never typed."""
        probe = brand.MIRA_FIRST_CLAIM[:45]
        for path in (ROOT / "templates").glob("*.j2"):
            body = _strip_jinja_comments(path.read_text(encoding="utf-8"))
            assert probe not in body, f"{path.name} hardcodes the Mira claim"


# ---------------------------------------------------------------------------
# No surface calls this a phone-call show
# ---------------------------------------------------------------------------

class TestNotAPhoneCallShow:
    """Since 2026-09-09 a guest joins a studio room; PSTN is the fallback.

    CLAUDE.md: "Do not describe the show as a phone-call show on any surface."
    """

    def test_registry_and_templates_are_clean(self):
        import yaml

        registry = (ROOT / "shows" / "network_meta.yaml").read_text(
            encoding="utf-8")
        entries = yaml.safe_load(registry) or {}
        for slug in INTERVIEW_SHOW_SLUGS:
            blob = json.dumps(entries.get(slug, {}), ensure_ascii=False).lower()
            for forbidden in ("phone call", "phone interview", "over the phone",
                              "phones "):
                assert forbidden not in blob, (
                    f"{slug} registry entry calls it a phone show: {forbidden!r}"
                )

    def test_brand_module_is_clean(self):
        text = (brand.MIRA_FIRST_CLAIM + brand.MIRA_FIRST_CLAIM_BASIS
                + brand.MIRA_SHORT_DESCRIPTION).lower()
        assert "over the phone" not in text
        assert "phones " not in text


# ---------------------------------------------------------------------------
# The interview parser
# ---------------------------------------------------------------------------

class TestInterviewParsing:
    def test_only_interview_shows_are_interview_shows(self):
        assert is_interview_show("age_of_ai")
        assert not is_interview_show("tesla")
        assert interview_context("anything", "tesla", 1, None) == {}

    def test_every_committed_digest_yields_a_named_guest(self):
        digests = sorted(AOAI_DIGESTS.glob("*.md"))
        assert digests, "no Age of AI digests committed"
        for path in digests:
            num = int(re.search(r"_Ep(\d+)_", path.name).group(1))
            ctx = interview_context(
                path.read_text(encoding="utf-8"), "age_of_ai", num,
                str(AOAI_SUMMARIES))
            assert ctx["guest_name"], f"{path.name}: no guest name"
            assert ctx["audio_url"], f"{path.name}: no audio to play"
            assert ctx["talking_points"], f"{path.name}: no talking points"

    def test_parser_never_raises_on_junk(self):
        """A digest the parser does not understand costs that episode its
        extras, never the whole blog build."""
        for junk in ("", "# Heading only", "no headings at all",
                     "### About\n\n", "### Where to find\n"):
            result = parse_interview_digest(junk)
            assert result["guest_name"] == "" or isinstance(
                result["guest_name"], str)
            assert isinstance(result["talking_points"], list)

    def test_body_keeps_the_transcript_and_drops_the_promoted_sections(self):
        path = AOAI_DIGESTS / "Age_of_AI_Ep004_20260919.md"
        body = interview_body_markdown(path.read_text(encoding="utf-8"))
        assert "Transcript" in body
        # Promoted above the fold — printing them twice is the bug.
        assert "What we talked about" not in body
        assert "Where to find" not in body
        assert "### Listen" not in body

    def test_unknown_section_is_kept_not_silently_dropped(self):
        md = ("# Show\n\n### About Jane Doe\n\n**CTO, Acme**\n\n"
              "### Something New\n\nbody text here\n\n### Transcript\n\nwords\n")
        body = interview_body_markdown(md)
        assert "Something New" in body
        assert "body text here" in body

    def test_guest_cards_are_newest_first_and_complete(self):
        cards = interview_episode_cards(
            "age_of_ai", AOAI_SUMMARIES, AOAI_DIGESTS)
        assert len(cards) >= 6
        numbers = [c["episode"] for c in cards]
        assert numbers == sorted(numbers, reverse=True)
        for card in cards:
            assert card["guest"], f"ep{card['episode']} has no guest"
            assert card["post_url"].endswith(".html")

    def test_a_news_show_gets_no_guest_cards(self):
        assert interview_episode_cards("tesla", AOAI_SUMMARIES, AOAI_DIGESTS) == []


# ---------------------------------------------------------------------------
# Rendered pages — always into tmp_path, never a committed file
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def aoai_page(tmp_path_factory):
    """The Age of AI show page, rendered from the CURRENT template."""
    out = tmp_path_factory.mktemp("showpages")
    return G.generate_show_page(
        "age_of_ai", output_dir=out).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def aoai_post():
    """One interview post, rendered from the CURRENT template."""
    from engine.blog import extract_blog_metadata, generate_blog_post_html

    path = AOAI_DIGESTS / "Age_of_AI_Ep004_20260919.md"
    md = path.read_text(encoding="utf-8")
    meta = extract_blog_metadata(md, "age_of_ai", path.name, file_path=path)
    meta["_md_path"] = path
    return G._strip_lone_surrogates(generate_blog_post_html(
        md, meta, G.NETWORK_SHOWS["age_of_ai"], G._get_jinja_env(),
        prev_post={"episode_num": 3}, next_post={"episode_num": 5},
    ))


class TestRenderedShowPage:

    def test_every_guest_is_named_on_the_page(self, aoai_page):
        cards = interview_episode_cards(
            "age_of_ai", AOAI_SUMMARIES, AOAI_DIGESTS)
        for card in cards:
            assert card["guest"] in aoai_page, (
                f"{card['guest']} missing from the show page")

    def test_the_page_can_be_listened_to(self, aoai_page):
        """One player per published episode, in the rail."""
        cards = interview_episode_cards(
            "age_of_ai", AOAI_SUMMARIES, AOAI_DIGESTS)
        playable = [c for c in cards if c["audio_url"]]
        assert playable, "no episode on the rail can be played"
        assert _markup_only(aoai_page).count("nn-guest-audio") == len(playable)

    def test_the_page_routes_to_the_apply_form(self, aoai_page):
        apply_page = G.NETWORK_SHOWS["age_of_ai"]["apply_page"]
        assert apply_page in aoai_page
        assert (ROOT / apply_page).exists(), (
            "the show page links an apply form that does not exist")

    def test_the_credit_is_on_the_page_and_names_him(self, aoai_page):
        assert brand.NETWORK_CREATOR_NAME in aoai_page
        for paragraph in brand.creator_credit("age_of_ai"):
            assert paragraph in aoai_page

    def test_a_run_show_page_carries_no_review_claim(self, tmp_path):
        """The scope property, checked on rendered HTML rather than a dict."""
        for slug in ("tesla", "spacex", "models_agents"):
            html = G.generate_show_page(
                slug, output_dir=tmp_path).read_text(encoding="utf-8")
            assert brand.CREATOR_REVIEW_ROLE not in html, (
                f"{slug}'s page claims a human reviews every episode")
            assert brand.NETWORK_CREATOR_NAME in html

    def test_a_news_show_keeps_its_rss_rail(self, tmp_path):
        html = G.generate_show_page(
            "tesla", output_dir=tmp_path).read_text(encoding="utf-8")
        assert 'id="episodes-grid"' in html
        assert "nn-guest-card\"" not in html

    def test_every_show_still_renders(self, tmp_path):
        """The rail and credit are additive; nothing may fail to build."""
        for slug in G.NETWORK_SHOWS:
            assert G.generate_show_page(slug, output_dir=tmp_path) is not None


class TestRenderedInterviewPost:

    def test_the_guest_is_the_h1(self, aoai_post):
        body = aoai_post.split("</style>", 1)[-1]
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
        assert h1, "no <h1> on the post"
        assert "Hogan Shrum" in re.sub(r"<[^>]+>", "", h1.group(1))

    def test_the_post_has_a_player(self, aoai_post):
        """Until this pass no interview post on the site had one at all."""
        assert "<audio" in aoai_post
        assert "nn-iv-player" in aoai_post

    def test_the_title_names_the_person(self, aoai_post):
        title = re.search(r"<title>(.*?)</title>", aoai_post, re.S).group(1)
        assert "Hogan Shrum" in title

    def test_neighbours_are_named_not_numbered(self, aoai_post):
        titles = re.findall(r'nav-title">([^<]*)', aoai_post)
        assert "Adrian Wolfberg" in titles
        assert "John Capobianco" in titles

    def test_promoted_sections_are_not_printed_twice(self, aoai_post):
        body = _markup_only(aoai_post)
        # The section is promoted into the hero, so it renders exactly once
        # there and not again inside the article.
        assert body.count('nn-iv-card-label">What we talked about') == 1
        assert "Where to find Hogan Shrum" not in body

    def test_the_post_routes_onward(self, aoai_post):
        assert "age-of-ai-apply.html" in aoai_post
        assert "mira.html" in aoai_post

    def test_a_news_post_is_unchanged_in_shape(self):
        """The interview branch must be invisible to every other show."""
        from engine.blog import extract_blog_metadata, generate_blog_post_html

        digests = sorted((ROOT / "digests" / "tesla_shorts_time").glob("*.md"))
        if not digests:
            pytest.skip("no Tesla digests committed")
        path = digests[-1]
        md = path.read_text(encoding="utf-8")
        meta = extract_blog_metadata(md, "tesla", path.name, file_path=path)
        meta["_md_path"] = path
        html = generate_blog_post_html(
            md, meta, G.NETWORK_SHOWS["tesla"], G._get_jinja_env())
        body = _markup_only(html)
        assert "nn-iv-hero" not in body, (
            "the interview hero rendered on a news post")
        assert 'class="blog-hero"' in body
