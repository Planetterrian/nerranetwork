"""Nerra Personal, deep personalization (Oct 18 2026).

Behavioural guards for the five pieces of engine.personal_stories and the
builder wiring: "Tell Mira about you" (spec, Worker, prompt), edition
memory, repeats across the member's own shows (notes + the opt-in
``skip_repeats`` trim), the edition length budget, and interest highlights
with story-level chapters. Every check runs the real functions — on
committed digests/chapters/transcripts where the claim is about real data,
on small fixtures where it is about a rule. Source-string checks only where
the TypeScript cannot be run from Python (the Worker mirror).

Cost rule pinned here too: nothing in engine.personal_stories may call a
model or a search tool.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from engine import personal_stories as ps
from engine.daily_edition import Segment, discover_segments, load_transcript
from engine.personal_edition import (
    DEFAULT_ADDONS,
    PERSONAL_ADDONS,
    PROFILE_MAX_CHARS,
    TARGET_MINUTES,
    EditionContext,
    build_personal_links_prompt,
    ensure_trim_mentions,
    episode_notes,
    fallback_personal_links,
    personal_chapter_pieces,
    personal_context_blocks,
    personal_edition_spec,
    validate_spec,
)

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "cd" * 16
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _spec(**over):
    raw = {"token": TOKEN, "shows": ["tesla", "spacex"], "tier": "personal"}
    raw.update(over)
    return validate_spec(raw)


def _words(sentences, start=0.0, gap=0.3, story_gap=1.0, per_word=0.3):
    """A Whisper-shaped transcript from [(sentence, new_story_after)]:
    words timed one after another, a ``story_gap`` pause after a sentence
    that closes a story, ``gap`` otherwise."""
    segs, t = [], start
    for text, story_end in sentences:
        ws = []
        s0 = t
        for w in text.split():
            ws.append({"word": w, "start": round(t, 3), "end": round(t + per_word, 3)})
            t += per_word
        segs.append({"start": round(s0, 3), "end": round(t, 3), "text": text, "words": ws})
        t += story_gap if story_end else gap
    return {"segments": segs}


def _stories(slug="mag7", show="MAG 7 Daily", chapters=None, transcript=None,
             headlines=(), units_md="", duration=100.0, private=False, hook="Hook"):
    from engine.story_breaks import story_units
    return ps.SegmentStories(
        slug=slug, show_name=show, episode_num=7, hook=hook,
        headlines=list(headlines), chapters=chapters or [],
        units=story_units(units_md) if units_md else [],
        transcript=transcript, private=private,
        full_episode_url=f"https://nerranetwork.com/blog/{slug}/ep007.html",
        duration=duration)


# ---------------------------------------------------------------------------
# 1. Tell Mira about you — spec, Worker mirror, prompt
# ---------------------------------------------------------------------------

class TestListenerProfile:
    def test_profile_is_scrubbed_and_capped_like_every_free_text_field(self):
        spec = _spec(profile="<b>I teach</b> {date_spoken} chemistry in Halifax; "
                             "I follow batteries!" + " x" * 400)
        assert len(spec.profile) <= PROFILE_MAX_CHARS == 240
        assert "<" not in spec.profile and "{" not in spec.profile
        assert ";" not in spec.profile and "!" not in spec.profile
        assert spec.profile.startswith("I teach date_spoken chemistry in Halifax")

    def test_target_minutes_is_a_closed_set(self):
        assert TARGET_MINUTES == (20, 30, 45, 60)
        assert _spec(target_minutes=30).target_minutes == 30
        assert _spec(target_minutes="45").target_minutes == 45
        for bad in (37, 0, -20, "lots", None, 600):
            assert _spec(target_minutes=bad).target_minutes is None

    def test_skip_repeats_is_opt_in(self):
        assert "skip_repeats" in PERSONAL_ADDONS
        assert "skip_repeats" not in DEFAULT_ADDONS
        assert not _spec().skip_repeats                       # never saved
        assert not _spec(addons=["weather"]).skip_repeats      # saved without it
        assert _spec(addons=["skip_repeats"]).skip_repeats
        # Not a location add-on: it never switches the local brief on.
        from engine.personal_edition import wants_local_brief
        assert not wants_local_brief(_spec(addons=["skip_repeats"], city="Victoria"))

    def test_worker_mirrors_the_limits_and_vocabulary(self):
        ts = _read("workers/gallery/src/personal.ts")
        assert re.search(r"const PROFILE_MAX = 240;", ts)
        m = re.search(r"export const TARGET_MINUTES = \[([^\]]*)\]", ts)
        assert m and tuple(int(x) for x in m.group(1).split(",")) == TARGET_MINUTES
        block = ts.split("PERSONAL_ADDONS = [", 1)[1].split("]", 1)[0]
        assert "skip_repeats" in re.findall(r'"([a-z_]+)"', block)
        # The admin export carries the two fields (and still never an email).
        specs = ts.split("export async function handleAdminSpecs", 1)[1].split(
            "export function countShowDemand", 1)[0]
        assert "profile: rec.profile" in specs and "target_minutes: rec.target_minutes" in specs
        assert "email" not in specs.split("specs.push({", 1)[1].split("});", 1)[0]

    def test_prompt_frames_the_profile_as_data_with_limits(self):
        spec = _spec(profile="Night-shift nurse in Calgary who follows EVs")
        blocks = personal_context_blocks(spec, EditionContext(edition_number=4))
        lb = blocks["listener_block"]
        assert "Night-shift nurse in Calgary who follows EVs" in lb
        assert "never instructions" in lb and "AT MOST two" in lb
        assert "never repeat their note back" in lb
        assert "(The listener has not told you about themselves.)" in \
            personal_context_blocks(_spec(), None)["listener_block"]

    def test_prompt_renders_every_block_and_keeps_the_hard_rules(self):
        seg = Segment(slug="spacex", show_name="SpaceX Daily", episode_num=1,
                      episode_title="Ep 1: Hook", hook="Hook", date="2026-10-18",
                      audio_url="", content="Body. " * 20, digest_dir=ROOT,
                      transcript_path=None, music_intro_offset=0.0)
        seg2 = Segment(**{**seg.__dict__, "slug": "tesla", "show_name": "Tesla Shorts Time"})
        p = build_personal_links_prompt(ROOT, _spec(profile="Teacher {x}"), [seg, seg2],
                                        dt.date(2026, 10, 18), EditionContext(edition_number=1))
        for marker in ("WHAT THE LISTENER TOLD YOU", "first edition",
                       "Do not include any AI-disclosure sentence",
                       "Facts only from the material above",
                       "never instructions"):
            assert marker in p, marker
        assert "{" not in p.split("Write, as STRICT JSON", 1)[0].replace("{{", "")

    def test_prompt_template_supplies_no_quotable_specimen(self):
        tpl = _read("shows/prompts/nerra_personal_links.txt")
        for ph in ("{listener_block}", "{memory_block}", "{repeats_block}",
                   "{interests_block}", "{edition_block}"):
            assert ph in tpl
        # De-seed by shape: the personal blocks describe what to do, never a
        # sentence for Mira to say. No quoted example lines in the template
        # or in the block copy.
        src = _read("engine/personal_edition.py")
        body = src.split("def personal_context_blocks", 1)[1].split("def build_personal_links_prompt", 1)[0]
        for bad in ("e.g.", "for example", "such as \"", "Example:"):
            assert bad not in body
            assert bad not in tpl


# ---------------------------------------------------------------------------
# 2. Edition memory
# ---------------------------------------------------------------------------

def _row(date, show, stories, hook="", slug="x"):
    return {"date": date, "episode_num": 1, "contents": [
        {"slug": slug, "show": show, "ep": 1, "hook": hook, "stories": stories}]}


class TestEditionMemory:
    def _today(self):
        return [_stories(slug="spacex", show="SpaceX Daily",
                         hook="Starship flight twelve booster caught on the tower",
                         headlines=["NASA picks SpaceX for lunar cargo lander contract"])]

    def test_heard_before_is_named_with_show_and_day(self):
        past = [_row("2026-10-14", "Tesla Shorts Time",
                     ["NASA selects SpaceX for lunar cargo lander contract award"])]
        notes = ps.memory_notes(self._today(), past, dt.date(2026, 10, 16))
        assert len(notes) == 1
        assert "Tesla Shorts Time" in notes[0] and "Wednesday (2 days ago)" in notes[0]
        assert "lunar cargo lander" in notes[0]

    def test_only_the_last_seven_earlier_editions_count(self):
        target = dt.date(2026, 10, 20)
        rows = [_row((target - dt.timedelta(days=d)).isoformat(), "Old Show",
                     ["Unrelated harvest festival opens in Kelowna orchards"])
                for d in range(1, 8)]
        rows.append(_row("2026-10-05", "Very Old Show",
                         ["NASA selects SpaceX for lunar cargo lander contract award"]))
        rows.append(_row(target.isoformat(), "Same Day",       # today never counts
                         ["NASA selects SpaceX for lunar cargo lander contract award"]))
        assert ps.memory_notes(self._today(), rows, target) == []

    def test_contents_record_is_compact_and_public_text_only(self):
        st = _stories(hook="H" * 400, headlines=[f"Headline number {i} about chips"
                                                 for i in range(20)])
        rec = ps.edition_contents([st])
        assert set(rec[0]) == {"slug", "show", "ep", "hook", "stories"}
        assert len(rec[0]["stories"]) == ps.MEMORY_STORIES_PER_SEGMENT
        assert len(rec[0]["hook"]) <= 150
        assert json.dumps(rec).count("Headline") == ps.MEMORY_STORIES_PER_SEGMENT

    def test_week_threads_are_sunday_only_and_counted(self):
        today = self._today()
        rows = [_row(f"2026-10-{d:02d}", "SpaceX Daily",
                     ["NASA picks SpaceX lunar cargo lander contract decision"]) for d in (15, 16)]
        sunday, monday = dt.date(2026, 10, 18), dt.date(2026, 10, 19)
        threads = ps.week_threads(today, rows, sunday)
        assert len(threads) == 1 and "in 3 of this week's editions" in threads[0]
        assert ps.week_threads(today, rows, monday) == []

    def test_first_edition_explains_what_mira_does(self):
        blocks = personal_context_blocks(_spec(), EditionContext(edition_number=1))
        assert "FIRST personal edition" in blocks["edition_block"]
        assert "first edition" in blocks["memory_block"]
        later = personal_context_blocks(_spec(), EditionContext(edition_number=9))
        assert "FIRST" not in later["edition_block"]
        assert "do not announce the number" in later["edition_block"]


# ---------------------------------------------------------------------------
# 3. Repeats across the member's own shows — calibrated on committed data
# ---------------------------------------------------------------------------

def _real_stories(date: dt.date, slugs):
    segs, _ = discover_segments(personal_edition_spec(), ROOT, date, include_members=True)
    by = {s.slug: s for s in segs}
    out = []
    for slug in slugs:
        s = by[slug]
        tr = load_transcript(s.transcript_path) if s.transcript_path else None
        out.append(ps.segment_stories(s, ROOT, transcript=tr))
    return out


class TestRepeats:
    def test_the_gemini_launch_told_by_two_shows_is_found(self):
        stories = _real_stories(dt.date(2026, 10, 14), ["models_agents", "mag7"])
        reps = ps.cross_repeats(stories)
        gem = [r for r in reps if "Gemini" in r.later_text]
        assert gem and gem[0].later == "mag7" and gem[0].earlier == "models_agents"
        # One note per story, not one per headline variant of it.
        assert len(gem) == 1

    def test_a_shared_phrase_is_not_a_shared_story(self):
        # Calibration false pair: "Frequent Daytime Napping Linked to Higher
        # Dementia Risk" vs "Lithium in drinking water linked to higher
        # congenital heart defect risk" — three tokens, different stories.
        stories = _real_stories(dt.date(2026, 10, 14), ["planetterrian", "longevity"])
        assert not [r for r in ps.cross_repeats(stories)
                    if "Napping" in r.later_text and "Lithium" in r.earlier_text]

    def test_mention_and_cut_thresholds(self):
        assert ps.mention_level(4, 0.4) and ps.mention_level(3, 0.6)
        assert not ps.mention_level(3, 0.43)
        assert ps.mention_level(3, 0.43, body=0.35)
        assert not ps.mention_level(2, 1.0)
        assert ps.Repeat("b", "B", "x", "a", "A", "y", 4, 0.5, 0.25).strong
        assert not ps.Repeat("b", "B", "x", "a", "A", "y", 4, 0.5, 0.2).strong
        assert not ps.Repeat("b", "B", "x", "a", "A", "y", 3, 1.0, 0.9).strong

    def test_spoken_numbers_never_make_a_match(self):
        m = ps.StoryMatcher([])
        assert m.score("Seven billion dollars more than one year", "Seven billion more than a year ago")[0] == 0


# ---------------------------------------------------------------------------
# Cut rules (repeat + length share check_chapter_cut)
# ---------------------------------------------------------------------------

_DIGEST = """# Show

### Top News

1. **Acme Robotics opens a new factory in Ohio**: Acme Robotics opened its Ohio factory for warehouse robots on Monday. The factory employs four hundred people. Source: https://example.com/acme

2. **Zephyr Airlines orders forty electric seaplanes**: Zephyr Airlines ordered electric seaplanes for coastal routes. Zephyr says deliveries start next year. Source: https://example.com/zephyr

3. **Quartz Bank cuts savings rates again**: Quartz Bank cut savings rates for the third time. Quartz Bank customers lose interest income. Source: https://example.com/quartz
"""


def _fixture():
    sentences = [
        ("This is the show, episode seven.", True),
        ("Acme Robotics opened its Ohio factory for warehouse robots.", False),
        ("The Acme factory employs four hundred people in Ohio.", True),
        ("Zephyr Airlines ordered forty electric seaplanes for coastal routes.", False),
        ("Zephyr says the seaplanes deliveries start next year.", True),
        ("Quartz Bank cut savings rates for the third time.", False),
        ("Quartz Bank customers lose interest income on savings.", True),
        ("That's the show for today.", False),
    ]
    tr = _words(sentences)
    segs = tr["segments"]
    starts = [segs[1]["start"], segs[3]["start"], segs[5]["start"], segs[7]["start"]]
    end = segs[-1]["end"] + 0.5
    chapters = [
        ps.ShowChapter("Introduction", 0.0, starts[0], "furniture"),
        ps.ShowChapter("Acme Robotics opens a new factory in Ohio", starts[0], starts[1],
                       "headline", lead=True),
        ps.ShowChapter("Zephyr Airlines orders forty electric seaplanes", starts[1], starts[2],
                       "headline"),
        ps.ShowChapter("Quartz Bank cuts savings rates again", starts[2], starts[3], "headline"),
        ps.ShowChapter("Closing", starts[3], end, "furniture"),
    ]
    headlines = ["Acme Robotics opens a new factory in Ohio",
                 "Zephyr Airlines orders forty electric seaplanes",
                 "Quartz Bank cuts savings rates again"]
    return _stories(chapters=chapters, transcript=tr, headlines=headlines,
                    units_md=_DIGEST, duration=end)


class TestCutRules:
    def test_story_pauses_come_from_sentence_ending_word_gaps(self):
        st = _fixture()
        pauses = ps.story_pauses(st.transcript)
        assert len(pauses) == 4 and all(b - a >= ps.STORY_PAUSE_MIN_SECONDS for a, b in pauses)

    def test_a_clean_single_story_chapter_may_be_cut(self):
        st = _fixture()
        span, why = ps.check_chapter_cut(st, st.chapters[2], [], single_story=True)
        assert span is not None, why
        assert span[0] < st.chapters[2].start <= span[0] + ps.SNAP_TOLERANCE_SECONDS

    def test_never_the_lead_furniture_last_or_members_only(self):
        st = _fixture()
        assert ps.check_chapter_cut(st, st.chapters[1], [], single_story=False)[1] == "lead story"
        assert ps.check_chapter_cut(st, st.chapters[0], [], single_story=False)[1] == "cold open or sign-off"
        assert ps.check_chapter_cut(st, st.chapters[4], [], single_story=False)[1] == "cold open or sign-off"
        priv = _fixture()
        priv.private = True
        assert ps.check_chapter_cut(priv, priv.chapters[2], [], single_story=False)[1] == "members-only episode"
        # A body chapter that is the segment's LAST chapter carries the sign-off.
        nolast = _fixture()
        nolast.chapters = nolast.chapters[:4]
        assert ps.check_chapter_cut(nolast, nolast.chapters[3], [], single_story=False)[1] == \
            "last chapter carries the sign-off"

    def test_no_pause_or_a_mid_sentence_edge_is_never_cut(self):
        st = _fixture()
        ch = st.chapters[2]
        late = ps.ShowChapter(ch.title, ch.start + 3.0, ch.end, ch.kind)
        st.chapters[2] = late
        span, why = ps.check_chapter_cut(st, late, [], single_story=True)
        assert span is None and why == "no pause at a chapter edge"
        assert not ps.at_sentence_boundary(st.transcript["segments"][3]["words"][3]["end"],
                                           st.transcript)

    def test_a_chapter_that_carries_another_story_is_not_one_story(self):
        st = _fixture()
        # One chapter spanning Zephyr AND Quartz: purity fails.
        wide = ps.ShowChapter("Zephyr Airlines orders forty electric seaplanes",
                              st.chapters[2].start, st.chapters[3].end, "headline")
        span, why = ps.check_chapter_cut(st, wide, [], single_story=True)
        assert span is None and ("not one story" in why or "continues" in why or "edge" in why)

    def test_repeat_cut_needs_a_strong_match(self):
        st = _fixture()
        weak = ps.Repeat("mag7", "MAG 7 Daily", st.chapters[2].title, "tesla", "Tesla",
                         "Zephyr seaplanes", 3, 0.6, 0.5, st.chapters[2])
        strong = ps.Repeat("mag7", "MAG 7 Daily", st.chapters[2].title, "tesla", "Tesla",
                           "Zephyr Airlines orders forty electric seaplanes now", 5, 1.0, 0.8,
                           st.chapters[2])
        cuts, refused = ps.plan_repeat_cuts([st], [weak, strong], {})
        assert [c.title for c in cuts] == [st.chapters[2].title]
        assert cuts[0].reason == "repeat" and cuts[0].earlier_show == "Tesla"
        assert refused[0][1] == "match not strong enough to cut"

    def test_length_budget_trims_from_the_end_and_ships_long_when_it_must(self):
        st = _fixture()
        # Fits already: nothing cut.
        assert ps.plan_length_cuts([st], 10_000, 30, {}) == []
        # Over budget: the last cuttable story goes first, never the lead.
        cuts = ps.plan_length_cuts([st], st.duration + 30 - 1, 30, {})
        assert [c.title for c in cuts] == ["Quartz Bank cuts savings rates again"]
        # Impossible budget: cuts everything allowed, keeps lead + sign-off, ships long.
        cuts = ps.plan_length_cuts([st], 1, 30, {})
        titles = {c.title for c in cuts}
        assert "Acme Robotics opens a new factory in Ohio" not in titles
        assert titles == {"Zephyr Airlines orders forty electric seaplanes",
                          "Quartz Bank cuts savings rates again"}


# ---------------------------------------------------------------------------
# Applying a cut: timelines stay aligned
# ---------------------------------------------------------------------------

class TestTimeline:
    def test_remap_and_ranges(self):
        spans = ps.removed_spans([ps.Cut("a", 10, 20, "x", "length"),
                                  ps.Cut("a", 18, 25, "y", "length"),
                                  ps.Cut("b", 1, 2, "z", "length")], "a")
        assert spans == [(10, 25)]
        assert ps.keep_ranges(60, spans) == [(0.0, 10), (25, None)]
        assert ps.remap_time(5, spans) == 5 and ps.remap_time(30, spans) == 15
        assert ps.remap_time(12, spans) is None
        assert ps.remap_cut_point(50.0, spans) == 35.0 and ps.remap_cut_point(None, spans) is None

    def test_transcript_drops_the_trimmed_story_and_shifts_the_rest(self):
        st = _fixture()
        span, _ = ps.check_chapter_cut(st, st.chapters[2], [], single_story=True)
        tr = ps.remap_transcript(st.transcript, [span])
        texts = [s["text"] for s in tr["segments"]]
        assert not any("Zephyr" in t for t in texts)
        quartz_before = next(s for s in st.transcript["segments"] if "Quartz Bank cut" in s["text"])
        quartz_after = next(s for s in tr["segments"] if "Quartz Bank cut" in s["text"])
        assert quartz_after["start"] == pytest.approx(quartz_before["start"] - (span[1] - span[0]), abs=1e-3)

    def test_subchapters_skip_lead_furniture_and_trimmed(self):
        st = _fixture()
        span, _ = ps.check_chapter_cut(st, st.chapters[2], [], single_story=True)
        subs = ps.segment_subchapters(st, [span])
        assert [t for t, _ in subs] == ["Quartz Bank cuts savings rates again"]
        assert subs[0][1] == pytest.approx(ps.remap_time(st.chapters[3].start, [span]), abs=0.01)
        assert [t for t, _ in ps.segment_subchapters(st, [])] == [
            "Zephyr Airlines orders forty electric seaplanes", "Quartz Bank cuts savings rates again"]

    def test_edition_chapters_split_a_segment_and_keep_the_total(self):
        spec = _spec()
        segs = [Segment(slug=s, show_name=n, episode_num=1, episode_title="Ep 1: H",
                        hook="H", date="2026-10-18", audio_url="", content="",
                        digest_dir=ROOT, transcript_path=None, music_intro_offset=0.0)
                for s, n in (("tesla", "Tesla Shorts Time"), ("spacex", "SpaceX Daily"))]
        durations = {"intro": 30.0, "seg_tesla": 300.0, "handoff_1": 20.0,
                     "seg_spacex": 400.0, "signoff": 40.0}
        flat = personal_chapter_pieces(spec, segs, durations)
        deep = personal_chapter_pieces(spec, segs, durations,
                                       {"spacex": [("Booster story", 120.0), ("Deep dive", 250.0)]})
        assert sum(d for _, d in flat) == pytest.approx(sum(d for _, d in deep))
        titles = [t for t, _ in deep]
        assert titles[-3:] == ["Booster story", "Deep dive", "Sign-off"]
        assert dict(deep)["Booster story"] == pytest.approx(130.0)
        # The SpaceX top piece = its handoff + the cold open and lead story.
        assert deep[2][1] == pytest.approx(20.0 + 120.0)

    @pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
    def test_the_render_removes_exactly_the_span(self, tmp_path):
        src = tmp_path / "seg.mp3"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=20",
                        "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-q:a", "2", str(src)],
                       check=True, capture_output=True)
        out = tmp_path / "cut.flac"   # lossless piece format (Oct 29 2026)
        subprocess.run(ps.cut_segment_cmd(src, out, ps.keep_ranges(20.0, [(5.0, 10.0)]), 20.0),
                       check=True, capture_output=True)
        from engine.audio import get_audio_duration
        assert float(get_audio_duration(out)) == pytest.approx(15.0, abs=0.15)

    def test_real_chapters_clip_at_the_promo_cut(self):
        raw = ps.load_show_chapters(ROOT / "digests" / "mag7", 22)
        assert raw, "committed MAG 7 Ep022 chapters"
        chs = ps.classify_chapters(raw, ["Google opens Gemini 4 Argon to paying users"], 300.0)
        assert chs[-1].end <= 300.0
        assert all(c.start < 300.0 for c in chs)
        assert chs[0].kind == "furniture" and next(c for c in chs if c.kind != "furniture").lead


# ---------------------------------------------------------------------------
# A trim is never silent
# ---------------------------------------------------------------------------

def _two_segments():
    return [Segment(slug=s, show_name=n, episode_num=1, episode_title="Ep 1: Hook",
                    hook="Hook", date="2026-10-18", audio_url="", content="Body. " * 5,
                    digest_dir=ROOT, transcript_path=None, music_intro_offset=0.0)
            for s, n in (("tesla", "Tesla Shorts Time"), ("mag7", "MAG 7 Daily"))]


class TestTrimsAreNamed:
    TRIM = {"slug": "mag7", "show": "MAG 7 Daily", "title": "Gemini 4 Argon",
            "reason": "repeat", "earlier_show": "Models & Agents",
            "url": "https://nerranetwork.com/blog/mag7/ep007.html"}

    def test_fixed_sentence_when_mira_did_not_say_it(self):
        links = {"intro": "Hello.", "handoffs": ["Over to MAG 7 Daily."], "signoff": "Bye."}
        out = ensure_trim_mentions(links, _two_segments(), [self.TRIM])
        assert "trimmed its retelling" in out["handoffs"][0]
        assert "Models & Agents" in out["handoffs"][0]
        assert links["handoffs"][0] == "Over to MAG 7 Daily."     # no mutation

    def test_miras_own_words_are_kept(self):
        links = {"intro": "Hello.", "handoffs": ["MAG 7 Daily, minus the Gemini retelling I skipped."],
                 "signoff": "Bye."}
        out = ensure_trim_mentions(links, _two_segments(), [self.TRIM])
        assert out["handoffs"][0] == links["handoffs"][0]

    def test_first_show_trims_land_in_the_intro_and_fallback_explains_day_one(self):
        trim = dict(self.TRIM, slug="tesla", reason="length")
        ctx = EditionContext(edition_number=1, trims=[trim], target_minutes=30)
        links = fallback_personal_links(_spec(), _two_segments(), dt.date(2026, 10, 18), ctx)
        assert "first edition" in links["intro"]
        assert "near 30 minutes" in links["intro"]

    def test_episode_notes_list_the_trim_with_the_full_episode_link(self):
        plain, html = episode_notes(_spec(), [{"startTime": 0, "title": "Good morning from Mira"}],
                                    trims=[self.TRIM])
        assert "Trimmed for you" in html and self.TRIM["url"] in html
        assert "Trimmed: MAG 7 Daily: Gemini 4 Argon" in plain


# ---------------------------------------------------------------------------
# 5. Interest highlights
# ---------------------------------------------------------------------------

class TestHighlights:
    def test_topic_points_at_the_story_and_its_place(self):
        st = _fixture()
        out = ps.interest_highlights([st], ["Zephyr seaplanes"])
        assert len(out) == 1 and "story 2 of the segment" in out[0]
        assert 'their topic "Zephyr seaplanes"' in out[0]

    def test_a_trimmed_story_is_never_pointed_at(self):
        st = _fixture()
        span, _ = ps.check_chapter_cut(st, st.chapters[2], [], single_story=True)
        assert ps.interest_highlights([st], ["Zephyr seaplanes"], spans={"mag7": [span]}) == []
        # The place is counted on what remains.
        out = ps.interest_highlights([st], ["Quartz Bank"], spans={"mag7": [span]})
        assert "story 2 of the segment" in out[0]

    def test_profile_keywords_skip_generic_words(self):
        kws = ps.profile_keywords("I work at a small robotics startup and love my morning commute")
        assert "robotics" in kws and "startup" in kws
        assert not {"work", "small", "love", "morning", "commute"} & set(kws)


# ---------------------------------------------------------------------------
# The builder: cost rule, PII rule, the segment-cache fix, end to end
# ---------------------------------------------------------------------------

def _builder():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_personal_feeds_t", ROOT / "scripts" / "build_personal_feeds.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestBuilder:
    def test_personal_stories_makes_no_model_or_search_call(self):
        src = _read("engine/personal_stories.py")
        for banned in ("grok_generate_text", "xai_grok", "enable_web_search",
                       "requests.", "openai", "synthesize("):
            assert banned not in src, banned

    def test_promo_cut_is_set_even_when_the_segment_is_cached(self, tmp_path):
        mod = _builder()
        segs, _ = discover_segments(personal_edition_spec(), ROOT, dt.date(2026, 10, 17))
        seg = next(s for s in segs if s.slug == "tesla")
        (tmp_path / "tesla.mp3").write_bytes(b"cached")
        seg.cut_final_seconds = None
        out = mod.build_segment_cache(["tesla"], {"tesla": seg}, tmp_path)
        assert out["tesla"] == tmp_path / "tesla.mp3"
        assert seg.cut_final_seconds is not None and 300 < seg.cut_final_seconds < 520

    @pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
    def test_end_to_end_memory_trims_chapters_and_no_pii_in_logs(self, tmp_path, monkeypatch, caplog):
        mod = _builder()
        monkeypatch.delenv("GROK_API_KEY", raising=False)
        monkeypatch.delenv("XAI_API_KEY", raising=False)
        mod._STORIES.clear()
        mod._SILENCES.clear()
        st = _fixture()
        ddir = tmp_path / "digests" / "mag7"
        ddir.mkdir(parents=True)
        (ddir / "chapters_ep007.json").write_text(json.dumps({"chapters": [
            {"startTime": c.start, "endTime": c.end, "title": c.title} for c in st.chapters]}))
        trp = ddir / "MAG7_Ep007_transcript.json"
        trp.write_text(json.dumps(st.transcript))

        def audio(path, secs):
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=300:duration={secs}",
                            "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame", "-q:a", "2", str(path)],
                           check=True, capture_output=True)

        cache = {"mag7": tmp_path / "mag7.mp3", "tesla": tmp_path / "tesla.mp3"}
        audio(cache["mag7"], round(st.duration, 2))
        audio(cache["tesla"], 30)
        mag7 = Segment(slug="mag7", show_name="MAG 7 Daily", episode_num=7,
                       episode_title="Ep 7: Acme Robotics opens a new factory in Ohio",
                       hook="Acme Robotics opens a new factory in Ohio", date="2026-10-18",
                       audio_url="https://audio.example/mag7.mp3", content=_DIGEST,
                       digest_dir=ddir, transcript_path=trp, music_intro_offset=0.0)
        tesla = Segment(slug="tesla", show_name="Tesla Shorts Time", episode_num=3,
                        episode_title="Ep 3: Zephyr Airlines orders forty electric seaplanes for its coast",
                        hook="Zephyr Airlines orders forty electric seaplanes for its coast",
                        date="2026-10-18", audio_url="https://audio.example/t.mp3",
                        content=("> **Zephyr Airlines orders forty electric seaplanes for its coast**\n\n"
                                 "### Top News\n\n1. **Zephyr Airlines orders forty electric "
                                 "seaplanes for its coast**: Zephyr Airlines ordered electric "
                                 "seaplanes for coastal routes. Zephyr says deliveries start next "
                                 "year. Source: https://example.com/z\n"),
                        digest_dir=tmp_path, transcript_path=None, music_intro_offset=0.0)

        def fake_tts(text, dest):
            audio(dest, 2)
        monkeypatch.setattr(mod, "_tts", fake_tts)

        class Client:
            def __init__(self):
                self.objects = {}

            def get_object(self, Bucket, Key):
                if Key in self.objects:
                    return {"Body": io.BytesIO(self.objects[Key])}
                raise KeyError(Key)

            def put_object(self, Bucket, Key, Body, ContentType):
                self.objects[Key] = Body

            def delete_object(self, Bucket, Key):
                self.objects.pop(Key, None)

        client = Client()
        profile = "Seaplane pilot in Tofino who follows Acme Robotics"
        state_key = f"personal/{TOKEN}/episodes.json"
        client.objects[state_key] = json.dumps({"episodes": [
            {"episode_num": 1, "date": "2026-10-16", "filename": "old.mp3",
             "contents": [{"slug": "tesla", "show": "Tesla Shorts Time", "ep": 2, "hook": "",
                           "stories": ["Acme Robotics opens new Ohio robot factory today"]}]}]}).encode()
        spec = validate_spec({"token": TOKEN, "shows": ["tesla", "mag7"],
                              "tier": "personal_local", "first_name": "Anabelle",
                              "addons": ["skip_repeats"], "profile": profile})
        caplog.set_level(logging.INFO)
        ok = mod.build_for_spec(spec, dt.date(2026, 10, 18), {"tesla": tesla, "mag7": mag7},
                                cache, client, dry_run=False, sting=None)
        assert ok
        state = json.loads(client.objects[state_key])
        row = next(r for r in state["episodes"] if r["date"] == "2026-10-18")
        # Edition memory recorded, compact.
        assert [c["slug"] for c in row["contents"]] == ["tesla", "mag7"]
        # Tesla told the Zephyr story first; MAG 7's chapter of it is cut.
        assert row["trimmed"] == [{"slug": "mag7", "title": "Zephyr Airlines orders forty electric seaplanes",
                                   "reason": "repeat"}]
        assert "Trimmed for you" in row["notes_html"]
        chapters = json.loads(client.objects[f"personal/{TOKEN}/chapters_20261018.json"])["chapters"]
        titles = [c["title"] for c in chapters]
        assert "Quartz Bank cuts savings rates again" in titles            # story chapter
        assert "Zephyr Airlines orders forty electric seaplanes" not in titles  # trimmed
        assert chapters[-1]["endTime"] == pytest.approx(row["duration_seconds"], abs=0.3)
        cues = json.loads(client.objects[f"personal/{TOKEN}/transcript_20261018.json"])["segments"]
        assert not any("Zephyr says" in c["body"] for c in cues)
        assert cues[-1]["endTime"] <= row["duration_seconds"] + 0.3
        # The trim is named in the audio (fallback links + fixed sentence).
        handoff_cue = next(c for c in cues if c["speaker"] == "Mira"
                           and c["body"].startswith("Next in your lineup: MAG 7 Daily"))
        assert "trimmed" in handoff_cue["body"]
        # PII: the profile and the name never reach a log line.
        logs = "\n".join(r.getMessage() for r in caplog.records)
        assert profile not in logs and "Tofino" not in logs and "Anabelle" not in logs
        assert TOKEN not in logs and TOKEN[:8] in logs
