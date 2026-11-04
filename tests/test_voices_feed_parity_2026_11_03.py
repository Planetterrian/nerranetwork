"""The interview shows inherit the feed and page surface (Nov 4 2026, voices-7).

The fifth instance of the bypass-run_show class (after the OP3 prefix, the
per-language OP3 feeds, the newsletter/YouTube flags and episode_page_url):
age_of_ai_podcast.rss (15 items) and nerra_voices_podcast.rss (4) carried 0
``podcast:transcript``, 0 ``podcast:person`` and 0 ``podcast:funding`` tags
while Tesla's feed carried 240 transcript tags, a host and a funding tag,
because ``publish_one`` passed none of the kwargs ``update_rss_feed`` takes
and run_show passes. Six of nineteen feed titles ended in "…" because the
whole thesis was clipped at a word; eight of eighteen About sections were
under 25 words ("WorkID talk", "longevityresearch.ca", a bare URL) and the
page printed each under "In their own words".

These pin: the VTT written from the EDIT transcript beside the digest (no
cue over 20 s), the four kwargs on the feed call and the tags they produce
in a real feed, titles fitted whole through ``engine.titles``, an About that
prints the facts the pipeline holds and never the placeholder when it holds
any, the page's blurb guard, and the one-time backfill.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT))

import publish_episode as pe  # noqa: E402
from shows import get_show  # noqa: E402

PUB = (V / "publish_episode.py").read_text(encoding="utf-8")
PODCAST_NS = "{https://podcastindex.org/namespace/1.0}"
ITUNES_NS = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"

EDIT_TRANSCRIPT = """[00:01] Mira (narration): Welcome to The Age of AI.
[00:12] Mira: Thor, where did this start?
[00:18] Thor: With fifty applicants, half of them avatars.
[01:05] Mira: Say more.
[01:05] Thor: The same second as her question.
[01:30] Thor: And a last line about verified credentials."""


def _cues(vtt: str) -> list:
    out = []
    for m in re.finditer(r"(\d\d):(\d\d):(\d\d)\.(\d{3}) --> (\d\d):(\d\d):(\d\d)\.(\d{3})\n(.+)", vtt):
        g = [int(x) for x in m.groups()[:8]]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        out.append((start, end, m.group(9)))
    return out


def _tmp_show(tmp_path: Path, slug: str = "age_of_ai"):
    """The real show, with its files pointed into *tmp_path* (an absolute
    path replaces ROOT when joined)."""
    sub = tmp_path / f"digests_{slug}"
    sub.mkdir(exist_ok=True)
    return replace(get_show(slug), audio_subdir=str(sub),
                   rss_file=str(tmp_path / f"{slug}.rss"),
                   summaries_json=str(tmp_path / f"summaries_{slug}.json"))


# ---------------------------------------------------------------------------
# 1. The VTT from the edit transcript
# ---------------------------------------------------------------------------

class TestTheTranscriptVtt:
    def test_it_is_written_beside_the_digest_from_the_edit_transcript(self, tmp_path):
        show = _tmp_show(tmp_path)
        path = pe.write_transcript_vtt({"edit_transcript": EDIT_TRANSCRIPT}, show, 16,
                                       dt.date(2026, 11, 4))
        assert path is not None and path.exists()
        assert path.name == "Age_of_AI_Ep016_20261104.vtt"
        assert path.parent == Path(show.audio_subdir)
        vtt = path.read_text(encoding="utf-8")
        assert vtt.startswith("WEBVTT\n")
        cues = _cues(vtt)
        assert len(cues) == 6
        for start, end, text in cues:
            assert 0 < end - start <= pe.VTT_CUE_MAX_SECONDS, (start, end, text)
        # A cue ends where the next line starts; a long gap caps at 20 s.
        assert cues[0] == (1.0, 12.0, "Mira (narration): Welcome to The Age of AI.")
        assert cues[2][0] == 18.0 and cues[2][1] == 38.0           # 65 s is 47 s away: capped
        # Two lines on the same second both run to the next later stamp — 25 s
        # away here, so both are capped at 20 s, together.
        assert cues[3][:2] == (65.0, 85.0) and cues[4][:2] == (65.0, 85.0)
        # The last cue has no next line and runs its fixed length.
        assert cues[5][:2] == (90.0, 90.0 + pe.VTT_LAST_CUE_SECONDS)
        assert cues[5][2].startswith("Thor: ")

    def test_only_the_edit_transcript_qualifies(self, tmp_path):
        """A room transcript is on a clock nobody hears; a VTT on it would
        point every cue up to three minutes late. None, never a guess."""
        show = _tmp_show(tmp_path)
        assert pe.write_transcript_vtt({"transcript_cleaned": EDIT_TRANSCRIPT}, show, 16,
                                       dt.date(2026, 11, 4)) is None
        assert pe.write_transcript_vtt({"edit_transcript": "no stamped lines here"}, show,
                                       16, dt.date(2026, 11, 4)) is None
        assert pe.write_transcript_vtt({}, show, 16, dt.date(2026, 11, 4)) is None
        assert not list(Path(show.audio_subdir).glob("*.vtt"))

    def test_the_segments_never_cross_each_other_or_exceed_the_cap(self):
        segs = pe.transcript_segments(EDIT_TRANSCRIPT)
        for seg in segs:
            assert seg["end"] - seg["start"] <= pe.VTT_CUE_MAX_SECONDS
            assert seg["end"] > seg["start"]
            assert ": " in seg["text"]


# ---------------------------------------------------------------------------
# 2. The feed call carries the Podcasting 2.0 kwargs, and the feed shows them
# ---------------------------------------------------------------------------

class TestTheFeedTags:
    def test_the_kwargs_are_the_ones_run_show_passes(self):
        show = get_show("age_of_ai")
        vtt = Path("digests/age_of_ai/Age_of_AI_Ep016_20261104.vtt")
        tags = pe.feed_podcast_tags(show, 16, vtt, host_name="Mira")
        assert tags == {
            "funding_url": "https://nerranetwork.com/support.html",
            "funding_label": "Support the Nerra Network",
            "person_name": "Mira",
            "person_url": "https://nerranetwork.com/mira.html",
            "transcript_url": "https://nerranetwork.com/blog/age_of_ai/ep016.html#transcript",
            "transcript_vtt_url":
                "https://nerranetwork.com/digests/age_of_ai/Age_of_AI_Ep016_20261104.vtt",
        }
        # The pages the tags point at exist.
        assert (ROOT / "support.html").exists() and (ROOT / "mira.html").exists()
        # No VTT: the Support button and the host still go; no transcript tag.
        without = pe.feed_podcast_tags(show, 16, None)
        assert "transcript_url" not in without and "transcript_vtt_url" not in without
        assert without["person_name"] == "Mira"      # engine.brand.MIRA_HOST_NAME
        assert without["funding_url"].endswith("/support.html")

    def test_publish_one_writes_the_vtt_before_the_feed_and_spreads_the_tags(self):
        body = PUB.split("def publish_one(")[1].split("\ndef ")[0]
        vtt_at = body.index("vtt_path = write_transcript_vtt(pkg, show, episode_num, today)")
        tags_at = body.index("podcast_tags = feed_podcast_tags(show, episode_num, vtt_path")
        feed_at = body.index("update_rss_feed(\n")
        assert vtt_at < tags_at < feed_at
        feed_call = body[feed_at:body.index(")\n", feed_at)]
        assert "**podcast_tags" in feed_call
        # The guest's own words — the edit transcript — are the only source.
        vtt_body = PUB.split("def write_transcript_vtt")[1].split("\ndef ")[0]
        assert '.get("edit_transcript")' in vtt_body and "transcript_cleaned" not in vtt_body

    def test_a_real_feed_built_with_these_kwargs_carries_the_tags(self, tmp_path):
        """update_rss_feed accepts exactly what feed_podcast_tags builds, and
        the feed on disk then carries transcript (text/vtt + text/html),
        funding and person — the three tags both interview feeds had none of."""
        from engine.publisher import update_rss_feed
        show = _tmp_show(tmp_path)
        vtt = pe.write_transcript_vtt({"edit_transcript": EDIT_TRANSCRIPT}, show, 16,
                                      dt.date(2026, 11, 4))
        mp3 = tmp_path / "Age_of_AI_Ep016_20261104.mp3"
        mp3.write_bytes(b"\0" * 2048)
        rss = update_rss_feed(
            show.rss_path, 16, "Ep16: Ada Lovelace — A thesis", "Notes.",
            dt.date(2026, 11, 4), mp3.name, 60.0, mp3,
            audio_url="https://audio.nerranetwork.com/age_of_ai/raw/x.mp3",
            audio_subdir="digests/age_of_ai", channel_title=show.name,
            channel_link=show.rss_link, channel_description=show.rss_description,
            channel_author=show.rss_author, channel_email=show.rss_email,
            channel_image=show.rss_image, guid_prefix=show.guid_prefix,
            episode_page_url="https://nerranetwork.com/blog/age_of_ai/ep016.html",
            **pe.feed_podcast_tags(show, 16, vtt, host_name="Mira"),
        )
        channel = ET.parse(str(rss)).getroot().find("channel")
        funding = channel.find(f"{PODCAST_NS}funding")
        person = channel.find(f"{PODCAST_NS}person")
        assert funding is not None and funding.get("url").endswith("/support.html")
        assert person is not None and person.text == "Mira"
        item = channel.find("item")
        transcripts = item.findall(f"{PODCAST_NS}transcript")
        kinds = {(el.get("type"), el.get("url").rsplit("/", 1)[-1].split("#")[0]) for el in transcripts}
        assert ("text/vtt", "Age_of_AI_Ep016_20261104.vtt") in kinds
        assert ("text/html", "ep016.html") in kinds
        assert len(transcripts) == 2

    def test_a_transcript_page_url_is_typed_text_html_and_the_old_shapes_are_unchanged(self):
        from engine.publisher import transcript_tag_type
        assert transcript_tag_type("https://n/blog/age_of_ai/ep012.html#transcript") == "text/html"
        assert transcript_tag_type("https://n/digests/x/E_transcript.json") == "application/json"
        assert transcript_tag_type("https://n/digests/x/E_transcript.txt") == "text/plain"
        assert transcript_tag_type("") == "text/plain"

    def test_the_committed_interview_feeds_will_be_measured_by_this(self):
        """The acceptance line: ``grep -c podcast:transcript`` on both feeds
        equals the episode count from today. Pinned as a count of what the
        committed feeds carry so the backfill's effect can be read later —
        this is NOT a pass/fail on the feeds' past (they were built before
        this change) but a guard that the parser reads them."""
        for feed in ("age_of_ai_podcast.rss", "nerra_voices_podcast.rss"):
            channel = ET.parse(str(ROOT / feed)).getroot().find("channel")
            assert channel is not None and channel.findall("item")


# ---------------------------------------------------------------------------
# 3. Titles fitted whole
# ---------------------------------------------------------------------------

class TestTitlesFittedWhole:
    THESES = {
        (12, "Thor Hesselberg"): (
            "A recruitment founder counters AI deepfakes flooding hiring pipelines by"
            " building portable verified credentials that replace self-reported CVs"
            " with employer-confirmed trust scores."),
        (13, "Jon Cheney"): (
            "A founder racing to embed agentic systems and fractional CAIO leadership"
            " across enterprises now tests whether those same tools can scale human"
            " judgment without eroding the critical thinking his own doctrine requires."),
        (14, "Piper Martz"): (
            "How a DTC lifecycle operator moving from static CRM automations to agentic"
            " engagement stacks experiences the loss of junior execution practice and"
            " the limits of community dinners in closing the documented gender gap in"
            " AI adoption."),
        (15, "Michael Kamins"): (
            "A CPG hiring veteran builds candidate-owned living portfolios that let AI"
            " surface matches without rejections so humans can restore authenticity"
            " and cut early turnover where static resumes failed."),
        (3, "Scott Pulcini"): (
            "A scalper who once handled a tenth of E-mini volume rebuilt a durable edge"
            " by reading iceberg orders and stop runs after algorithms erased his"
            " original speed advantage, then teaches the resulting rule set to retail"
            " traders."),
        (4, "Stuart Berkowitz"): (
            "Translating scattered trial data into a public Bayesian atlas that models"
            " upper-bound life-year gains from overlapping interventions while exposing"
            " every assumption for inspection."),
    }

    def test_the_six_titles_that_ended_in_an_ellipsis_now_read_whole(self):
        from engine.titles import ELLIPSIS, PODCAST_EPISODE_TITLE_MAX
        for (num, guest), thesis in self.THESES.items():
            title = pe.interview_episode_title(num, guest, thesis)
            assert len(title) <= PODCAST_EPISODE_TITLE_MAX, title
            assert ELLIPSIS not in title, title
            assert title.startswith(f"Ep{num}: {guest} — "), title
            clause = title.split(" — ", 1)[1]
            assert thesis.startswith(clause) and len(clause.split()) >= 5, title

    def test_the_title_helper_never_splits_the_thesis_itself(self):
        """CLAUDE.md titles rule: the limit and the cut live in engine.titles.
        This function may only call in; no slice, no split of its own."""
        body = PUB.split("def interview_episode_title")[1].split("\ndef ")[0]
        assert "fit_first_clause(thesis, room)" in body
        assert ".split(" not in body and "[:" not in body
        assert "from engine.titles import" in body

    def test_a_short_thesis_and_the_pinned_shape_still_hold(self):
        assert pe.interview_episode_title(3, "Ann", "Short thesis.") == "Ep3: Ann — Short thesis."
        assert pe.interview_episode_title(9, "Ann", "") == "Ep9: Ann"


# ---------------------------------------------------------------------------
# 4. The About section says what we know
# ---------------------------------------------------------------------------

LONG_BIO = ("Ada Lovelace wrote the first published algorithm intended for a machine, "
            "working from Babbage's notes on the Analytical Engine in 1843. She saw that "
            "the engine could manipulate symbols as well as numbers, and said so in a set "
            "of notes longer than the paper they annotated, which is why the field counts "
            "her as its first programmer and names a language after her.")


def _digest(**over) -> str:
    app = {"name": "Ada Lovelace", "title": "Mathematician",
           "organization": "Analytical Engine", "bio": LONG_BIO,
           "topics": ["symbols as well as numbers", "the first program"],
           "links": {"raw": "https://example.org"}}
    for key in ("bio", "title", "organization", "topics", "links"):
        if key in over:
            app[key] = over.pop(key)
    pkg = {"episode_notes": "The lead paragraph.\n\nThe rest of it.",
           "transcript_cleaned": "[00:01] Ada: Hello. The engine computes."}
    pkg.update(over)
    path = pe.write_episode_digest(get_show("age_of_ai"), 7, dt.date(2026, 9, 17),
                                   "Ep7", {"episode_thesis": "A thesis."},
                                   app, pkg, "https://audio/x.mp3")
    try:
        return path.read_text(encoding="utf-8")
    finally:
        path.unlink()


def _about(text: str) -> str:
    return text.split("### About Ada Lovelace")[1].split("---")[0]


class TestTheAboutSection:
    def test_a_label_is_never_printed_as_a_biography(self):
        about = _about(_digest(bio="WorkID talk"))
        assert "WorkID talk" not in about
        assert "**Mathematician, Analytical Engine**" in about
        assert "**What they came to talk about:** symbols as well as numbers; the first program" in about
        assert "joined Mira for this conversation" not in about

    def test_a_bare_domain_is_a_link_not_a_biography(self):
        text = _digest(bio="longevityresearch.ca", links={})
        assert "longevityresearch.ca" not in _about(text)
        assert "### Where to find Ada Lovelace" in text
        assert "](https://longevityresearch.ca)" in text

    def test_the_guests_own_prose_is_printed_and_a_long_bio_needs_no_facts_beside_it(self):
        about = _about(_digest())
        assert LONG_BIO in about
        assert "What they came to talk about" not in about

    def test_a_short_sentence_is_prose_and_the_topics_stand_beside_it(self):
        about = _about(_digest(bio="She wrote the first program."))
        assert "She wrote the first program." in about
        assert "**What they came to talk about:**" in about

    def test_the_placeholder_only_when_the_pipeline_holds_nothing(self):
        about = _about(_digest(bio="", title="", organization="", topics=[]))
        assert "Ada Lovelace joined Mira for this conversation." in about
        about = _about(_digest(bio="", topics=[]))
        assert "joined Mira" not in about and "**Mathematician, Analytical Engine**" in about
        about = _about(_digest(bio="", title="", organization=""))
        assert "joined Mira" not in about and "What they came to talk about" in about

    def test_topics_are_the_applications_own_in_either_stored_shape(self):
        assert pe.application_topics({"topics": ["a", " b ", "", "[object Object]", "a"]}) == ["a", "b"]
        assert pe.application_topics({"topics": '["x", "y"]'}) == ["x", "y"]
        assert pe.application_topics({"topics": "plain string"}) == ["plain string"]
        assert pe.application_topics({}) == []

    def test_the_source_never_prints_bio_or_placeholder(self):
        body = PUB.split("def write_episode_digest")[1].split("\ndef ")[0]
        assert 'bio or f"{name} joined Mira' not in body
        assert "is_guest_prose(bio)" in body


# ---------------------------------------------------------------------------
# 5. The page: "In their own words" only for the guest's own words
# ---------------------------------------------------------------------------

class TestThePageBlurbGuard:
    def test_is_guest_prose_by_shape(self):
        from engine.interviews import is_guest_prose
        assert not is_guest_prose("WorkID talk")
        assert not is_guest_prose("Futures trader")
        assert not is_guest_prose("longevityresearch.ca")
        assert not is_guest_prose("https://example.org/team")
        assert not is_guest_prose("Scott Pulcini joined Mira for this conversation.")
        assert not is_guest_prose("")
        assert is_guest_prose("She wrote the first program.")
        assert is_guest_prose(LONG_BIO)

    def test_the_parser_drops_a_label_and_reads_the_topics_line(self):
        from engine.interviews import parse_interview_digest
        md = ("# The Age of AI\n\n### About Thor Hesselberg\n\n**Founder, WorkID**\n\n"
              "**What they came to talk about:** deepfakes in hiring; verified credentials\n\n"
              "---\n\n### Listen\n\n[x](https://a/b.mp3)\n")
        ctx = parse_interview_digest(md)
        assert ctx["guest_blurb"] == ""
        assert ctx["guest_identifier"] == "Founder, WorkID"
        assert ctx["came_to_talk_about"] == "deepfakes in hiring; verified credentials"
        md = "# The Age of AI\n\n### About Thor Hesselberg\n\nWorkID talk\n\n---\n"
        assert parse_interview_digest(md)["guest_blurb"] == ""
        md = "# Nerra Voices\n\n### About Stuart Berkowitz\n\nlongevityresearch.ca\n\n---\n"
        ctx = parse_interview_digest(md)
        assert ctx["guest_blurb"] == ""
        assert ctx["guest_links"] == [{"label": "longevityresearch.ca",
                                       "url": "https://longevityresearch.ca"}]
        md = "# Nerra Voices\n\n### About Scott Pulcini\n\nScott Pulcini joined Mira for this conversation.\n\n---\n"
        assert parse_interview_digest(md)["guest_blurb"] == ""

    def test_the_template_renders_the_topics_line_under_its_own_label(self):
        tmpl = (ROOT / "templates" / "blog_post.html.j2").read_text(encoding="utf-8")
        assert "{% if interview.came_to_talk_about %}" in tmpl
        assert "What they came to talk about" in tmpl
        # "In their own words" is still gated on the blurb alone.
        blurb = tmpl.split("{% if interview.guest_blurb %}")[1].split("{% endif %}")[0]
        assert "In their own words" in blurb


# ---------------------------------------------------------------------------
# 6. The backfill: VTTs for the published episodes, tags on their items
# ---------------------------------------------------------------------------

class TestTheBackfill:
    def _feed(self, show, episodes):
        from engine.publisher import update_rss_feed
        mp3 = Path(show.rss_file).parent / "x.mp3"
        mp3.write_bytes(b"\0" * 2048)
        for num, when in episodes:
            update_rss_feed(show.rss_path, num, f"Ep{num}: Guest — thesis", "Notes.", when,
                            mp3.name, 60.0, mp3,
                            audio_url=f"https://audio.nerranetwork.com/age_of_ai/raw/{num}.mp3",
                            audio_subdir="digests/age_of_ai", channel_title=show.name,
                            channel_link=show.rss_link, channel_author=show.rss_author,
                            channel_email=show.rss_email, guid_prefix=show.guid_prefix)
        Path(show.summaries_json).write_text(json.dumps({"episodes": [
            {"episode": num, "date": when.isoformat(), "title": f"Ep{num}", "guest": "G",
             "audio_url": f"https://audio.nerranetwork.com/age_of_ai/raw/{num}.mp3"}
            for num, when in episodes]}), encoding="utf-8")

    def test_it_writes_the_vtt_and_tags_the_item_once_and_lists_what_it_cannot(
            self, tmp_path, monkeypatch, caplog):
        show = _tmp_show(tmp_path)
        self._feed(show, [(12, dt.date(2026, 10, 14)), (13, dt.date(2026, 10, 24))])
        import shows as shows_mod
        monkeypatch.setattr(shows_mod, "get_show", lambda slug=None: show)
        monkeypatch.setattr(pe, "_show_config", lambda s: None)
        rows = {
            "interviews": [{"id": "i12", "episode_number": 12}, {"id": "i13", "episode_number": 13}],
            "i12": [{"edit_transcript": EDIT_TRANSCRIPT}],
            "i13": [{"transcript_cleaned": EDIT_TRANSCRIPT}],       # assembled before the edit had one
        }

        def fake_select(table, query=""):
            if table == "interviews":
                assert "status=eq.published" in query and "show=eq.age_of_ai" in query
                return rows["interviews"]
            iid = re.search(r"interview_id=eq\.(\w+)", query).group(1)
            return rows[iid]
        monkeypatch.setattr(pe, "sb_select", fake_select)

        with caplog.at_level(logging.WARNING):
            assert pe.vtt_backfill("age_of_ai") == 0
        vtt = Path(show.audio_subdir) / "Age_of_AI_Ep012_20261014.vtt"
        assert vtt.exists() and not (Path(show.audio_subdir) / "Age_of_AI_Ep013_20261024.vtt").exists()
        guid12, tagged12 = pe._feed_item(show.rss_path, 12)
        guid13, tagged13 = pe._feed_item(show.rss_path, 13)
        assert guid12 and tagged12 and guid13 and not tagged13
        channel = ET.parse(str(show.rss_path)).getroot().find("channel")
        item12 = next(i for i in channel.findall("item")
                      if i.find(f"{ITUNES_NS}episode").text == "12")
        tags = item12.findall(f"{PODCAST_NS}transcript")
        assert {t.get("type") for t in tags} == {"text/vtt", "text/html"}
        assert any(t.get("url").endswith("/Age_of_AI_Ep012_20261014.vtt") for t in tags)
        assert any(t.get("url").endswith("/ep012.html#transcript") for t in tags)
        assert "Ep13: no edit transcript on the package" in caplog.text
        # The feed's items were not moved: two items, Ep13 first.
        assert [i.find(f"{ITUNES_NS}episode").text for i in channel.findall("item")] == ["13", "12"]

        # A second run writes the same VTT and never duplicates the tags.
        pe.vtt_backfill("age_of_ai")
        channel = ET.parse(str(show.rss_path)).getroot().find("channel")
        item12 = next(i for i in channel.findall("item")
                      if i.find(f"{ITUNES_NS}episode").text == "12")
        assert len(item12.findall(f"{PODCAST_NS}transcript")) == 2

    def test_the_workflow_offers_it_and_the_sweep_never_runs_it(self):
        wf = (ROOT / ".github" / "workflows" / "nerra_voices_publish.yml").read_text(encoding="utf-8")
        assert "vtt_backfill:" in wf
        assert "VTT_BACKFILL: ${{ github.event.inputs.vtt_backfill }}" in wf
        main = PUB.split("def main()")[1]
        assert 'os.environ.get("VTT_BACKFILL", "").strip() in ("1", "true")' in main
        assert main.index("VTT_BACKFILL") < main.index("find_publishable()")

    def test_refresh_post_still_leaves_the_feed_alone(self):
        body = PUB.split("def refresh_post")[1].split("\ndef ")[0]
        assert "update_rss_feed" not in body and "_inject_transcript_tag" not in body


# ---------------------------------------------------------------------------
# 7. The directory doc knows the second interview show
# ---------------------------------------------------------------------------

def test_the_directory_doc_lists_nerra_voices_with_a_dated_pending():
    text = (ROOT / "docs" / "podcast_directories.md").read_text(encoding="utf-8")
    assert "| Nerra Voices | `https://nerranetwork.com/nerra_voices_podcast.rss` |" in text
    row = next(l for l in text.splitlines() if l.startswith("| Nerra Voices | PENDING"))
    assert "2026-11-04" in row and "LIVE" not in row
