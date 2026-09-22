"""The Age of AI pages say only what the record supports (Sep 22 2026).

Four things on the live show page and interview posts were not true, and one
publish-order bug made every new episode ship without its article link:

* ``generate_html.py --show <slug> --blogs`` rendered the show page BEFORE it
  wrote the posts, and every article link on that page is a file-exists
  check — so the Nerra Voices publish run (which writes only the digest and
  then calls exactly that command) shipped ``age-of-ai.html`` with no link to
  the episode it had just published, every time. Ep6 and Ep7 both did.
* Ep5, Ep6 and Ep7 carried chapter lists about a film studio banning AI
  storyboards — for a network-automation builder, a propulsion founder and a
  novelist — because the chapter prompt supplied that title as its example
  and the model reproduced it. Every guest card's run time was derived from
  the last chapter's ``end``, so it was wrong on every episode (Ep2 "23 min"
  beside a player reading 44:52).
* The creator credit said Patrick "is not in the room while Mira is talking
  to a guest"; he co-hosted five of the seven published episodes.
* The Mira claim's basis said nothing publishes "until the guest has approved
  it"; gate 2 auto-approves after seven days of silence.

Plus: every blog post on the site printed ``\\ud83d\\udc4d`` where a thumbs-up
belonged — JSON escapes pasted into a Jinja template.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

import generate_html as G
from engine import brand
from engine.interviews import (
    _run_time,
    cohost_display_name,
    cohost_label,
    feed_durations,
    interview_context,
    interview_episode_cards,
    interview_transcript_markdown,
    parse_interview_digest,
    supported_chapters,
)

ROOT = Path(__file__).resolve().parent.parent
AOAI_DIGESTS = ROOT / "digests" / "age_of_ai"
AOAI_SUMMARIES = AOAI_DIGESTS / "summaries_age_of_ai.json"
AOAI_RSS = ROOT / "age_of_ai_podcast.rss"
WORKER_TS = ROOT / "workers" / "voices" / "src" / "index.ts"
CHAPTER_PROMPT = (ROOT / "pipelines" / "voices" / "prompts" / "editorial_passes"
                  / "02_chapter_markers.txt")


def _strip_jinja_comments(text: str) -> str:
    return re.sub(r"\{#.*?#\}", "", text, flags=re.S)


def _digest(num: int) -> str:
    return next(AOAI_DIGESTS.glob(f"Age_of_AI_Ep{num:03d}_*.md")).read_text(
        encoding="utf-8")


def _transcript(num: int) -> str:
    return interview_transcript_markdown(_digest(num))


# ---------------------------------------------------------------------------
# 1. Posts are written before the page that links them
# ---------------------------------------------------------------------------

class TestPostsRenderBeforeThePage:
    def test_the_per_show_path_writes_posts_first(self, monkeypatch):
        """Run the real ``main()`` with every generator replaced by a recorder.

        The property is the ORDER, so it is asserted on the calls the real
        dispatch makes, not on how the source spells them.
        """
        calls = []

        def _rec(name):
            def f(*a, **k):
                calls.append(name)
                return []
            return f

        for name in ("generate_blog_posts", "generate_show_page",
                     "generate_summaries_page", "generate_narrative_page",
                     "generate_ru_landing_page", "generate_blog_index",
                     "generate_network_page"):
            monkeypatch.setattr(G, name, _rec(name))
        monkeypatch.setattr(sys, "argv",
                            ["generate_html.py", "--show", "age_of_ai", "--blogs"])
        G.main()
        assert "generate_blog_posts" in calls and "generate_show_page" in calls
        assert calls.index("generate_blog_posts") < calls.index("generate_show_page"), (
            f"the show page was rendered before its posts existed: {calls}"
        )
        assert calls.index("generate_blog_posts") < calls.index("generate_blog_index")

    def test_the_link_is_a_file_check_so_order_is_load_bearing(self):
        """Documents WHY the order matters: no file, no link."""
        assert G._blog_url_for_episode("age_of_ai", episode_num=999) == ""


# ---------------------------------------------------------------------------
# 2. The feedback row carries characters, not escapes
# ---------------------------------------------------------------------------

class TestNoEscapedCharactersInTemplates:
    def test_no_template_carries_a_surrogate_escape(self):
        for path in sorted((ROOT / "templates").glob("*.j2")):
            src = _strip_jinja_comments(path.read_text(encoding="utf-8"))
            assert "\\ud8" not in src and "\\ude" not in src, (
                f"{path.name} carries a JSON surrogate escape that Jinja "
                "prints literally"
            )

    def test_the_feedback_row_renders_a_thumbs_up(self):
        src = (ROOT / "templates" / "blog_post.html.j2").read_text(encoding="utf-8")
        assert "👍 Tell Patrick" in src
        assert "💡 Suggest" in src


# ---------------------------------------------------------------------------
# 3. The co-host is read from the transcript, never assumed either way
# ---------------------------------------------------------------------------

class TestCohostFromTheTranscript:
    def test_a_co_hosted_episode_names_him(self):
        assert cohost_label(_transcript(7), "Vincent Rylan") == "Patrick"

    def test_upper_case_labels_count(self):
        """Ep6 writes ``PATRICK:``; a case-sensitive count read it as zero."""
        assert cohost_label(_transcript(6), "Matt Davis").lower() == "patrick"

    def test_a_solo_episode_has_no_co_host(self):
        assert cohost_label(_transcript(4), "Hogan Shrum") == ""

    def test_the_guest_is_never_reported_as_the_co_host(self):
        """Ep1's guest IS Patrick; his lines are the guest's, not a co-host's."""
        cards = {c["episode"]: c for c in interview_episode_cards(
            "age_of_ai", AOAI_SUMMARIES, AOAI_DIGESTS, rss_path=AOAI_RSS)}
        assert cards[1]["cohost"] == ""

    def test_a_stray_label_is_not_a_person_in_the_room(self):
        tr = "[00:01] Mira: hi\n[00:02] Vince: hello\n[00:03] Bob: what\n"
        assert cohost_label(tr, "Vince Smith") == ""

    def test_the_label_maps_to_the_creator_name(self):
        assert cohost_display_name("Patrick") == brand.NETWORK_CREATOR_NAME
        assert cohost_display_name("") == ""

    def test_credit_agrees_with_the_transcripts(self):
        """If any committed transcript has him co-hosting, the credit may not
        deny it; it must describe the arrangement instead."""
        cohosted = [
            p.name for p in AOAI_DIGESTS.glob("Age_of_AI_Ep*.md")
            if cohost_label(interview_transcript_markdown(
                p.read_text(encoding="utf-8")),
                parse_interview_digest(p.read_text(encoding="utf-8"))["guest_name"])
        ]
        joined = " ".join(brand.creator_credit("age_of_ai")).lower()
        if cohosted:
            assert "co-host" in joined, (
                f"{len(cohosted)} transcripts show him co-hosting and the "
                "credit does not say so"
            )
        assert "not in the room" not in joined


# ---------------------------------------------------------------------------
# 4. Gate 2 is described as built: a week to approve, cut or refuse
# ---------------------------------------------------------------------------

class TestGateTwoWordingMatchesTheWorker:
    OVERCLAIMS = ("until the guest has approved", "until the guest has read",
                  "until you have signed off", "nothing reaches a feed until",
                  "no interview publishes until")

    def _surfaces(self):
        return {
            "brand.basis": brand.MIRA_FIRST_CLAIM_BASIS,
            "steps": " ".join(body for _t, body in G.MIRA_INTERVIEW_STEPS),
            "about": (ROOT / "templates" / "about.html.j2").read_text(encoding="utf-8"),
            "topic_hubs": (ROOT / "engine" / "topic_hubs.py").read_text(encoding="utf-8"),
        }

    def test_the_worker_still_auto_approves(self):
        """The guard's premise, read from the code that does it."""
        ts = WORKER_TS.read_text(encoding="utf-8")
        assert "auto-approve" in ts.lower() and "guest_review_deadline" in ts

    def test_no_surface_claims_a_gate_the_code_lacks(self):
        for name, text in self._surfaces().items():
            low = " ".join(text.lower().split())
            for phrase in self.OVERCLAIMS:
                assert phrase not in low, (
                    f"{name} says {phrase!r}, but gate 2 auto-approves after "
                    "seven days of silence (workers/voices/src/index.ts)"
                )

    def test_every_surface_states_the_week_and_the_takedown(self):
        for name, text in self._surfaces().items():
            low = " ".join(text.lower().split())
            assert "takedown" in low, f"{name} drops the takedown"
            assert "week" in low or "seven days" in low, (
                f"{name} does not say how long the guest has"
            )

    def test_the_narrow_claim_still_rests_on_the_guest(self):
        assert "guest decides whether the conversation is published" in \
            brand.MIRA_FIRST_CLAIM


# ---------------------------------------------------------------------------
# 5. Chapters: no specimen in the prompt, and a gate on what is rendered
# ---------------------------------------------------------------------------

# The list Ep7 shipped with, verbatim. A NOVELIST's episode, and every title
# is about an animation studio. Kept here as the gate's negative example; it
# was removed from the committed record in the same change.
FABRICATED_EP7 = [
    {"start": 0, "end": 300, "title": "Vincent Rylan's early experiments with AI-generated storyboards"},
    {"start": 300, "end": 720, "title": "Why the studio banned AI storyboards"},
    {"start": 720, "end": 1080, "title": "Patrick Novak joins to debate creative control vs efficiency"},
    {"start": 1080, "end": 1500, "title": "Real-world production failures from over-relying on AI tools"},
    {"start": 1500, "end": 1920, "title": "Future of hybrid human-AI workflows in animation"},
    {"start": 1920, "end": 2280, "title": "Lightning round and closing bet on the next industry shift"},
]


class TestChapterPromptIsDeseeded:
    def test_no_quoted_specimen_title(self):
        """De-seed by shape: the rule describes a title, it never shows one."""
        rules = [ln for ln in CHAPTER_PROMPT.read_text(encoding="utf-8").splitlines()
                 if ln.lstrip().startswith("-") and "itle" in ln]
        assert rules, "the Titles rule is gone"
        for ln in rules:
            assert not re.search(r'\("[^"]{12,}"\)', ln), (
                f"the chapter prompt supplies a quotable specimen: {ln!r}"
            )
        assert "storyboard" not in CHAPTER_PROMPT.read_text(encoding="utf-8").lower()

    def test_the_rule_binds_titles_to_the_transcript(self):
        text = CHAPTER_PROMPT.read_text(encoding="utf-8").lower()
        assert "transcript" in text and "speaker" in text


class TestSupportedChapters:
    def test_the_real_lists_survive_intact(self):
        data = json.loads(AOAI_SUMMARIES.read_text(encoding="utf-8"))
        records = {e["episode"]: e for e in data["episodes"]}
        for num in (2, 3, 4):
            kept = supported_chapters(records[num]["chapters"], _transcript(num))
            assert kept == records[num]["chapters"], f"Ep{num} lost real chapters"

    def test_the_fabricated_list_is_dropped_whole(self):
        assert supported_chapters(FABRICATED_EP7, _transcript(7)) == []

    def test_a_title_naming_a_host_with_no_lines_fails(self):
        tr = _transcript(4)  # Ep4 is the solo episode
        assert "patrick" not in {l.lower() for l in re.findall(
            r"^\[\d\d:\d\d\]\s+(\w+):", tr, re.M)}
        ch = [{"start": 0, "end": 60, "title": "Patrick and Hogan on ethical AI royalties for artists"}]
        assert supported_chapters(ch, tr) == []

    def test_no_transcript_vouches_for_nothing(self):
        assert supported_chapters(FABRICATED_EP7, "") == []
        assert supported_chapters([], _transcript(7)) == []

    def test_the_committed_record_carries_no_storyboard_chapters(self):
        text = AOAI_SUMMARIES.read_text(encoding="utf-8").lower()
        assert "storyboard" not in text
        for num in (5, 6, 7):
            assert "### chapters" not in _digest(num).lower()

    def test_the_post_context_goes_through_the_gate(self):
        ctx = interview_context(_digest(7), "age_of_ai", 7,
                                summaries_path=str(AOAI_SUMMARIES),
                                rss_path=str(AOAI_RSS))
        assert ctx["chapters"] == []
        ctx4 = interview_context(_digest(4), "age_of_ai", 4,
                                 summaries_path=str(AOAI_SUMMARIES),
                                 rss_path=str(AOAI_RSS))
        assert len(ctx4["chapters"]) == 8


# ---------------------------------------------------------------------------
# 6. Run time comes from the feed's measured duration
# ---------------------------------------------------------------------------

class TestRunTimeFromTheFeed:
    def test_durations_are_read_by_episode_number(self):
        d = feed_durations(AOAI_RSS)
        assert d[7] == 46 * 60 + 5
        assert d[2] == 44 * 60 + 52

    def test_cards_carry_the_measured_figure(self):
        cards = {c["episode"]: c for c in interview_episode_cards(
            "age_of_ai", AOAI_SUMMARIES, AOAI_DIGESTS, rss_path=AOAI_RSS)}
        assert cards[7]["run_time"] == "46 min"
        assert cards[2]["run_time"] == "45 min"  # was "23 min" from chapters

    def test_chapters_can_no_longer_supply_a_run_time(self):
        assert _run_time(FABRICATED_EP7) == ""
        assert _run_time(None) == "" and _run_time(59) == ""
        assert _run_time(2765) == "46 min" and _run_time(3900) == "1 hr 5 min"

    def test_a_missing_feed_omits_the_figure(self, tmp_path):
        assert feed_durations(tmp_path / "nope.rss") == {}
        cards = interview_episode_cards(
            "age_of_ai", AOAI_SUMMARIES, AOAI_DIGESTS, rss_path=None)
        assert all(c["run_time"] == "" for c in cards)


# ---------------------------------------------------------------------------
# 7. Rendered pages — always into tmp_path, never a committed file
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def aoai_page(tmp_path_factory):
    out = tmp_path_factory.mktemp("aoai")
    return G.generate_show_page("age_of_ai", output_dir=out).read_text(encoding="utf-8")


def _post(num: int, prev: int, nxt) -> str:
    from engine.blog import extract_blog_metadata, generate_blog_post_html

    path = next(AOAI_DIGESTS.glob(f"Age_of_AI_Ep{num:03d}_*.md"))
    md = path.read_text(encoding="utf-8")
    meta = extract_blog_metadata(md, "age_of_ai", path.name, file_path=path)
    meta["_md_path"] = path
    return G._strip_lone_surrogates(generate_blog_post_html(
        md, meta, G.NETWORK_SHOWS["age_of_ai"], G._get_jinja_env(),
        prev_post={"episode_num": prev},
        next_post={"episode_num": nxt} if nxt else None,
    ))


class TestRenderedTruth:
    def test_the_show_page_tags_only_the_co_hosted_episodes(self, aoai_page):
        cards = interview_episode_cards(
            "age_of_ai", AOAI_SUMMARIES, AOAI_DIGESTS, rss_path=AOAI_RSS)
        expected = sum(1 for c in cards if c["cohost"])
        assert expected >= 1
        assert aoai_page.count(f"with {brand.NETWORK_CREATOR_NAME}</span>") == expected

    def test_the_show_page_carries_the_corrected_credit(self, aoai_page):
        for para in brand.creator_credit("age_of_ai"):
            assert para in aoai_page
        assert "not in the room" not in aoai_page

    def test_the_show_page_run_times_are_measured(self, aoai_page):
        assert "46 min" in aoai_page and "23 min" not in aoai_page

    def test_a_co_hosted_post_says_so_and_a_solo_post_does_not(self):
        assert f"with {brand.NETWORK_CREATOR_NAME}, co-host" in _post(7, 6, None)
        assert "co-host</span>" not in _post(4, 3, 5)

    def test_the_fabricated_chapters_are_not_on_the_post(self):
        html = _post(7, 6, None)
        assert "storyboard" not in html.lower()

    def test_the_feedback_row_is_readable(self):
        html = _post(4, 3, 5)
        assert "👍 Tell Patrick" in html and "\\ud83d" not in html
