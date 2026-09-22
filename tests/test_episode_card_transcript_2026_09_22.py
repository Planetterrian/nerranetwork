"""One card to hear it and read it, and a transcript that is not the page.

**The transcript.** An interview digest is 90% transcript — 730 of Ep006's 785
lines — and it was printed open in the article body, so the page a visitor
landed on was a wall of speaker turns with the chapter list stranded above it.
The news shows had the opposite problem: their transcript was already behind a
``<details>``, but the toggle said only "Full Episode Transcript", which tells
a reader nothing about what is in there. Both now show their opening lines and
say how long the whole thing is, and the full text stays in the HTML either
way — collapsed, not withheld, so Ctrl-F and crawlers still see every word.

**The card.** Every show page offered a player that said "Loading..." until
the script ran, a summary that was hidden by default, and no link at all to
the episode's own article — which lived four screens further down under
"Latest from the Blog". Now one card carries the player, the summary and the
route to the article, rendered at build time from the same summaries JSON the
script fetches.

Every render goes into ``tmp_path``. Generated HTML is refreshed by the
pipeline, not committed from a working tree, so a guard that reads a committed
page is asserting against the previous chrome.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import generate_html as G
from engine.blog import TRANSCRIPT_PREVIEW_CHARS, transcript_preview
from engine.interviews import (
    interview_body_markdown,
    interview_transcript_markdown,
)
from engine.summaries_ssr import (
    CARD_PREVIEW_CHARS,
    SHORT_HOOK_CHARS,
    plain_preview,
    summary_cards,
)

ROOT = Path(__file__).resolve().parent.parent
INTERVIEW_DIGESTS = sorted((ROOT / "digests" / "age_of_ai").glob("Age_of_AI_Ep*.md"))


def _markup_only(html: str) -> str:
    """Drop ``<script>`` and ``<style>``.

    The card markup also exists as a template literal inside the page's own
    script, so counting class names across the whole document measures the
    script rather than what a browser paints before it runs.
    """
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S)
    return re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.S)


# ---------------------------------------------------------------------------
# Pulling the transcript out of the interview body
# ---------------------------------------------------------------------------

class TestInterviewTranscriptSplit:
    @pytest.mark.parametrize("path", INTERVIEW_DIGESTS, ids=lambda p: p.name)
    def test_every_committed_interview_yields_one(self, path):
        text = path.read_text(encoding="utf-8")
        assert len(interview_transcript_markdown(text).split()) > 1000

    @pytest.mark.parametrize("path", INTERVIEW_DIGESTS, ids=lambda p: p.name)
    def test_the_body_no_longer_carries_it(self, path):
        """Printed in both places the article would be twice as long and the
        collapse would buy nothing."""
        text = path.read_text(encoding="utf-8")
        body = interview_body_markdown(text)
        transcript = interview_transcript_markdown(text)
        opening = transcript.split("\n")[0]
        assert opening not in body
        assert "### Transcript" not in body

    @pytest.mark.parametrize("path", INTERVIEW_DIGESTS, ids=lambda p: p.name)
    def test_the_rest_of_the_digest_survives(self, path):
        """The chapter list is the only thing left; losing it would leave an
        interview post with an empty body."""
        assert "Chapters" in interview_body_markdown(
            path.read_text(encoding="utf-8"))

    def test_a_digest_with_no_transcript_section_is_not_an_error(self):
        """Ep001 predates the current shape and has no markdown at all; a
        parser that raised on a missing section takes the blog build down."""
        assert interview_transcript_markdown("### Listen\n\nnothing here") == ""
        assert interview_transcript_markdown("") == ""

    def test_the_guest_words_are_handed_through_unchanged(self):
        """engine.interviews states plainly that the transcript is the text a
        named human being read and approved, and is never reformatted."""
        text = INTERVIEW_DIGESTS[-1].read_text(encoding="utf-8")
        transcript = interview_transcript_markdown(text)
        # Every non-blank line of the extract appears verbatim in the digest.
        for line in transcript.splitlines():
            if line.strip():
                assert line in text


# ---------------------------------------------------------------------------
# The preview
# ---------------------------------------------------------------------------

class TestTranscriptPreview:
    def test_a_short_transcript_gets_no_preview(self):
        """An expander that reveals one more sentence is noise."""
        assert transcript_preview("Short enough already.") == ""

    def test_it_is_a_literal_prefix(self):
        """Not a summary, not a re-wrap: the opening words as recorded."""
        text = interview_transcript_markdown(
            INTERVIEW_DIGESTS[-1].read_text(encoding="utf-8"))
        preview = transcript_preview(text)
        assert preview
        assert text.startswith(preview)

    def test_it_ends_on_a_sentence_where_it_can(self):
        body = ("filler words " * 18) + "and here it ends. " + ("more " * 200)
        assert transcript_preview(body).endswith("ends.")

    def test_a_sentence_end_too_early_to_use_is_ignored(self):
        """Cutting at the first full stop would ship a three-word preview."""
        body = "Hi. " + ("filler words " * 200)
        assert transcript_preview(body) != "Hi."

    def test_it_never_returns_a_bare_stub(self):
        """A cut that lands three words in is worse than no preview."""
        body = "x" * 20 + " " + "y" * 800
        preview = transcript_preview(body)
        assert len(preview) >= int(TRANSCRIPT_PREVIEW_CHARS * 0.55)

    def test_it_respects_the_budget(self):
        text = interview_transcript_markdown(
            INTERVIEW_DIGESTS[-1].read_text(encoding="utf-8"))
        assert len(transcript_preview(text)) <= TRANSCRIPT_PREVIEW_CHARS


# ---------------------------------------------------------------------------
# The rendered box
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def interview_post(tmp_path_factory):
    out = tmp_path_factory.mktemp("ivpost")
    G.generate_blog_posts("age_of_ai", output_dir=out)
    newest = sorted((out / "blog" / "age_of_ai").glob("ep*.html"))[-1]
    return newest.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def news_post(tmp_path_factory):
    out = tmp_path_factory.mktemp("newspost")
    G.generate_blog_posts("offshore_north", output_dir=out)
    newest = sorted((out / "blog" / "offshore_north").glob("ep*.html"))[-1]
    return newest.read_text(encoding="utf-8")


class TestTheRenderedTranscriptBox:
    def test_the_interview_post_finally_has_one(self, interview_post):
        """It never did: extract_blog_metadata finds no *_reader.txt beside an
        interview digest, so ``transcript`` was empty and the section did not
        render — the words were loose in the article body instead."""
        assert 'class="blog-transcript" id="transcript"' in interview_post

    @pytest.mark.parametrize("fixture", ["interview_post", "news_post"])
    def test_it_is_collapsed_with_a_preview(self, fixture, request):
        html = request.getfixturevalue(fixture)
        box = re.search(r'<section class="blog-transcript".*?</details>',
                        html, re.S).group(0)
        assert "<details>" in box, "the box shipped open"
        assert 'class="transcript-preview"' in box
        assert re.search(r'class="transcript-length">[\d,]+ words', box)

    def test_the_preview_is_hidden_from_assistive_tech(self, interview_post):
        """It sits inside <summary> so a closed <details> still paints it, and
        the same words are read again three lines below. A 400-character
        button label is not a button label."""
        box = re.search(r'<summary>.*?</summary>', interview_post, re.S).group(0)
        preview = re.search(r'<span class="transcript-preview"([^>]*)>', box)
        assert 'aria-hidden="true"' in preview.group(1)

    def test_the_body_does_not_print_the_transcript_a_second_time(
            self, interview_post):
        text = interview_transcript_markdown(
            INTERVIEW_DIGESTS[-1].read_text(encoding="utf-8"))
        # A line long enough to be unmistakable, from the middle of the file.
        long_lines = [ln for ln in text.splitlines() if len(ln) > 200]
        assert long_lines
        sample = long_lines[len(long_lines) // 2]
        assert interview_post.count(sample) == 1

    def test_the_whole_transcript_is_still_in_the_page(self, interview_post):
        """Collapsed, not withheld. A box that fetched its contents would cost
        the in-page search a reader uses to find a quote, and every crawler's
        view of what the episode said."""
        text = interview_transcript_markdown(
            INTERVIEW_DIGESTS[-1].read_text(encoding="utf-8"))
        content = re.search(r'<div class="transcript-content">(.*?)</div>',
                            interview_post, re.S).group(1)
        assert len(content.split()) >= len(text.split()) * 0.95

    def test_the_transcript_url_reaches_the_json_ld(self, interview_post):
        """The PodcastEpisode block only emits it when a transcript exists, so
        the interviews had been publishing without one."""
        assert "#transcript" in interview_post
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            interview_post, re.S)
        transcripts = [
            node.get("transcript")
            for raw in blocks
            for node in ([json.loads(raw)] if isinstance(json.loads(raw), dict)
                         else json.loads(raw))
            if isinstance(node, dict)
        ]
        assert any(t and t.endswith("#transcript") for t in transcripts)


# ---------------------------------------------------------------------------
# The summary preview the card shows
# ---------------------------------------------------------------------------

class TestSummaryPreview:
    def test_the_hook_leads(self):
        """It is the episode's own headline, written for exactly this job."""
        content = ("# Tesla Shorts Time\n"
                   "**REAL-TIME TSLA price:** $348.95 ▼ $13.91 (3.8%)\n"
                   "> **Nevada's Tesla Semi factory will test 50,000-unit "
                   "annual output next month.**\n---\n### Top 12 News Items\n")
        assert plain_preview(content).startswith("Nevada's Tesla Semi")

    def test_the_price_line_is_not_a_sentence(self):
        """"(3.8%)" contains a full stop, so an "is there a . anywhere" test
        kept the line and the card opened on a stock quote."""
        assert plain_preview("**REAL-TIME TSLA price:** $348.95 ▼ "
                             "$13.91 (3.8%)") == ""

    def test_branding_and_headings_are_dropped(self):
        content = ("# Planetterrian Daily\n"
                   "\U0001f30d **Planetterrian Daily** - Science, Longevity & Health\n"
                   "> **Human cells break down shared proteins more slowly "
                   "than mouse cells.**\n")
        out = plain_preview(content)
        assert out.startswith("Human cells")
        assert "Planetterrian Daily" not in out

    def test_a_one_word_hook_keeps_reading(self):
        """Привет, Русский!'s hook is its word of the day."""
        out = plain_preview("> **Медведь**\nEnglish meaning: bear. "
                            "The bear loves honey and sleeps all winter long.")
        assert len(out) > SHORT_HOOK_CHARS

    def test_a_show_with_no_hook_starts_from_its_first_real_line(self):
        cards = summary_cards(
            ROOT / "digests" / "age_of_ai" / "summaries_age_of_ai.json",
            "age_of_ai", limit=1)
        assert cards[0]["summary_preview"]
        assert not cards[0]["summary_preview"].startswith("#")

    def test_every_show_previews_to_something_readable(self):
        """A preview that opens on the show's own name, a date or a price tells
        a reader nothing they did not already have."""
        for slug, cfg in G.NETWORK_SHOWS.items():
            cards = summary_cards(ROOT / cfg.get("json_path", ""), slug, limit=1)
            if not cards or not cards[0]["summary_preview"]:
                continue
            preview = cards[0]["summary_preview"]
            assert len(preview) > 40, f"{slug}: {preview!r}"
            assert not preview.startswith("#"), slug
            assert cfg["name"] not in preview[:len(cfg["name"]) + 5], slug

    def test_the_script_cuts_at_the_same_numbers(self):
        """The script replaces this text on load. Two lengths make the card
        flicker into different words a moment after paint."""
        src = (ROOT / "templates" / "show_page.html.j2").read_text(
            encoding="utf-8")
        assert "const PREVIEW_CHARS = {{ card_preview_chars }};" in src
        assert "const SHORT_HOOK_CHARS = {{ short_hook_chars }};" in src
        rendered = G.generate_show_page  # the values come from one module
        assert CARD_PREVIEW_CHARS and SHORT_HOOK_CHARS and rendered


# ---------------------------------------------------------------------------
# The combined card
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    out = tmp_path_factory.mktemp("showpages")
    rendered = {}
    for slug in G.NETWORK_SHOWS:
        path = G.generate_show_page(slug, output_dir=out)
        rendered[slug] = Path(path).read_text(encoding="utf-8")
    return rendered


def _card(html: str) -> str:
    match = re.search(r'<div class="latest-episode glass-card".*?\n    </section>',
                      html, re.S)
    return match.group(0) if match else ""


class TestTheCombinedCard:
    def test_every_show_with_a_feed_has_one(self, pages):
        for slug, html in pages.items():
            has_feed = 'id="latest-player"' in html or 'class="dpc-latest"' in html
            if not (ROOT / G.NETWORK_SHOWS[slug].get("rss_file", "")).exists():
                continue
            assert has_feed, f"{slug} has a feed and no latest-episode card"

    def test_a_show_with_no_feed_advertises_nothing(self, pages):
        """Nerra Voices showed a permanent "Loading..." above its own
        "Not published yet" band."""
        html = pages["nerra_voices"]
        assert 'id="latest-player"' not in html
        assert "Not published yet" in html

    def test_the_card_is_readable_before_the_script_runs(self, pages):
        card = _markup_only(_card(pages["tesla"]))
        assert "Loading..." not in card
        # Match the element, not one spelling of its start tag: the title
        # carries attributes (``data-rendered``) and a guard pinned to
        # ``id="latest-title">`` breaks on the next one added.
        assert re.search(r'id="latest-title"[^>]*>\s*\S', card)
        assert re.search(r'id="latest-audio"[^>]*src="https://', card)
        assert re.search(r'id="latest-summary"[^>]*>\s*\S', card)

    def test_it_routes_to_the_article(self, pages):
        """The written version existed for every show and the card never said
        so — the blog rail was four screens down."""
        for slug in ("tesla", "spacex", "omni_view", "age_of_ai", "nerra_daily"):
            card = _card(pages[slug])
            assert 'id="latest-article"' in card, slug

    def test_the_article_link_is_a_page_that_exists(self, pages):
        """A redirect stub IS a file at an epNNN.html path. "The file exists"
        stopped being a proxy for "the article exists" the moment stubs
        appeared, which is why this resolves through _blog_url_for_episode."""
        stubs = G.redirect_stub_paths()
        for slug, html in pages.items():
            href = re.search(r'id="latest-article" href="([^"]+)"', html)
            if not href:
                continue
            rel = href.group(1).lstrip("./")
            while rel.startswith("../"):
                rel = rel[3:]
            assert (ROOT / rel).exists(), f"{slug}: {rel} does not exist"
            assert rel not in stubs, f"{slug}: {rel} is a redirect stub"

    def test_no_episode_link_anywhere_on_a_show_page_is_a_stub(self, pages):
        """The card was not the only place building blog/<slug>/epNNN.html by
        hand. The blog rail did it in the template and the interview guest rail
        did it in engine.interviews, which cannot know about stubs — so Age of
        AI's show page linked its retired Ep001 twice."""
        stubs = G.redirect_stub_paths()
        for slug, html in pages.items():
            for href in re.findall(r'href="([^"]*blog/[^"]*ep\d{3}\.html)"', html):
                rel = href.lstrip("./")
                while rel.startswith("../"):
                    rel = rel[3:]
                assert rel not in stubs, f"{slug} links the stub {rel}"
                assert (ROOT / rel).exists(), f"{slug} links missing {rel}"

    def test_the_summary_matches_what_the_script_would_write(self, pages):
        """Server and client render the same sentence or the card twitches."""
        for slug in ("tesla", "dp_pod", "omni_view"):
            cfg = G.NETWORK_SHOWS[slug]
            expected = summary_cards(
                ROOT / cfg["json_path"], slug, limit=1)[0]["summary_preview"]
            assert expected[:80] in pages[slug], slug

    def test_the_bespoke_dp_pod_page_carries_it_too(self, pages):
        """This page does not use show_page.html.j2 — the same gap left its
        Story Tracker unlinked for two months."""
        html = pages["dp_pod"]
        card = re.search(r'<div class="dpc-latest">.*?</div>', html, re.S).group(0)
        assert "<audio" in card
        assert 'class="lt-summary"' in card
        assert 'class="lt-read"' in card

    def test_the_script_drops_a_link_it_cannot_vouch_for(self):
        """If the feed has moved past the episode the page was built from, the
        link points at the previous one while the player plays this one."""
        src = (ROOT / "templates" / "show_page.html.j2").read_text(
            encoding="utf-8")
        assert 'data-episode="{{ latest_episode.episode_num }}"' in src
        assert "articleEl.style.display = 'none'" in src


# ---------------------------------------------------------------------------
# The cadence claims this pass turned up
# ---------------------------------------------------------------------------

class TestNoPublicStringStillSaysDaily:
    """The Sep-21 guard read ``schedule`` and the feed description. It missed
    eight more claims on the DP Pod page, four in its own registry entry, and
    six on env_intel and Финансы Просто — all of them prose a visitor reads.
    """

    _FIELDS = ("schedule", "tagline", "hero_tagline", "meta_description",
               "description", "description_long", "about_text")
    _CLAIMS = re.compile(r"(?i)\b(daily|every day|each day)\b|ежедневн")

    def _monday_only(self):
        from tests.test_dp_pod_weekly_2026_09_21 import _cron_map

        return [s for s, (_c, day) in _cron_map().items() if day == "monday"]

    def test_no_monday_show_describes_itself_as_daily(self):
        # Four shows are genuinely named "<something> Daily"; strip every
        # show's NAME before reading the prose so a sibling plug is not a
        # false positive.
        names = [c["name"] for c in G.NETWORK_SHOWS.values() if c.get("name")]
        for slug in self._monday_only():
            cfg = G.NETWORK_SHOWS[slug]
            for field in self._FIELDS:
                value = cfg.get(field) or ""
                if not isinstance(value, str):
                    continue
                stripped = value
                for name in names:
                    stripped = stripped.replace(name, "")
                assert not self._CLAIMS.search(stripped), (
                    f"{slug}.{field} says it publishes daily: {value[:120]!r}")

    def test_the_dp_pod_page_copy_agrees(self):
        """Its bespoke template is prose no registry check reaches."""
        src = (ROOT / "templates" / "show_page_dp_pod.html.j2").read_text(
            encoding="utf-8")
        assert not self._CLAIMS.search(src), (
            "show_page_dp_pod.html.j2 still promises a daily briefing")
