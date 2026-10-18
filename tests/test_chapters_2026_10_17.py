"""Oct 17 2026 — chapters where the stories are, titled whole, at the time spoken.

The Oct 17 slate's chapter lists, replayed from the committed files:

* Tesla Ep637 shipped two word-clipped headlines ("Luxury estate in South
  Africa has off-grid home fitted", "History Says Tesla Stock Swings Hard on
  Earnings. It Has Moved 8%") — the lead split and the headline anchors
  still called ``_clip_title``; and one chapter ran 244-451 s over four
  stories and the essay.
* Fascinating Frontiers Ep224/225 titled the El Gordo lead "Cosmic
  Spotlight" (the digest's first heading, a different story) and opened
  "NASA's Hubble spies spiral's edge" inside the deep dive, 75 s before the
  Hubble story (a fixed-interval segment titled with whichever headline its
  text echoed).
* Planetterrian Ep213-216 had a two-chapter body: the deep-dive marker
  matched, so the opening chapter no longer spanned half the script and
  headline auto-segmentation never ran — eight news items sat inside
  "Science Deep Dive".
* AI Chips Ep026 titled the TSMC Arizona lead with "Samsung's second Taylor
  fab…" (two shared words, "second" and "fab"), and six stories shared one
  chapter for the same gating reason as Planetterrian.
* Modern Investing Ep203 opened "Trade Review & Lessons" on the pick ("…is
  today's simulated weekly hold") and "Practice Investment of the Day" on
  the pick's closing disclaimer, where the review began; and every start
  was a word-count estimate that ran up to 30 s late.

What binds now (``engine/chapters.py``):

* A headline is a chapter title WHOLE (``engine.titles.
  HEADLINE_CHAPTER_TITLE_MAX``) or not at all, on every path.
* Story chapters come from the story-change detector that places the audio
  beat (``engine.story_breaks``), across the whole body — a chapter opens on
  the line where its story begins, titled with that story's own headline.
* The lead's section name titles the lead only when that section holds the
  hook's story; a headline the story map places in another story never
  titles the lead.
* A body marker that fires inside another marker's section is dropped.
* ``align_timestamps_to_transcript`` moves each start onto the Whisper time
  of its line (run_show, after ``calculate_timestamps``).
* Chapters are metadata: nothing here raises.
"""
from __future__ import annotations

import glob
import json
import logging
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.chapters import (  # noqa: E402
    Chapter,
    _clean_item_title,
    _digest_item_titles,
    _lead_section_for_hook,
    _lead_story_split,
    _whole_title,
    align_timestamps_to_transcript,
    calculate_timestamps,
    parse_chapters,
)
from engine.config import load_config  # noqa: E402
from engine.grok_imagine import extract_story_headlines  # noqa: E402
from engine.titles import HEADLINE_CHAPTER_TITLE_MAX  # noqa: E402


@pytest.fixture(autouse=True)
def _quiet():
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _episode(show_dir: str, stem_glob: str):
    hits = [p for p in glob.glob(str(ROOT / "digests" / show_dir / f"{stem_glob}.md"))
            if "_claims" not in p]
    if not hits:
        pytest.skip(f"{show_dir}/{stem_glob} not on disk")
    md = Path(hits[0])
    tts = md.with_name(md.stem + "_tts.txt")
    if not tts.exists():
        pytest.skip(f"{tts.name} not on disk")
    return md, md.read_text(encoding="utf-8"), tts.read_text(encoding="utf-8")


def _replay(slug: str, show_dir: str, stem_glob: str):
    md, digest, script = _episode(show_dir, stem_glob)
    cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
    chapters = parse_chapters(
        script, cfg.chapters.section_markers, show_name=cfg.name,
        story_headlines=extract_story_headlines(digest, max_count=12),
        digest_text=digest,
        known_sections_only=getattr(cfg.chapters, "known_sections_only", False))
    return chapters, script, digest, cfg, md


def _opens(chapter, script) -> str:
    return script[chapter.char_start:].lstrip()


def _by_title(chapters, title):
    hit = [c for c in chapters if c.title == title]
    assert hit, (title, [c.title for c in chapters])
    return hit[0]


# ---------------------------------------------------------------------------
# Titles: whole or not at all
# ---------------------------------------------------------------------------

class TestWholeTitles:
    LONG = ("Luxury estate in South Africa has off-grid home fitted with 86 solar "
            "panels and 5 Tesla Powerwalls")
    HOOK = ("A South African estate runs entirely off-grid on five Powerwalls paired "
            "with eighty six solar panels")

    def _lines(self):
        text = ("This is Test Show, episode one.\n\n"
                "Those packs hold the array's output for night and overcast days.\n\n"
                "The South African estate pairs its Powerwalls with eighty six solar panels.\n\n"
                "A different story about a factory follows here.\n")
        return text.splitlines(keepends=True)

    def _head(self, lines):
        n = sum(len(ln.split()) for ln in lines)
        return Chapter(title="Introduction", word_start=0, word_end=n,
                       char_start=0, char_end=sum(len(ln) for ln in lines))

    def test_an_over_budget_lead_headline_is_never_clipped(self):
        assert len(self.LONG) > HEADLINE_CHAPTER_TITLE_MAX
        lines = self._lines()
        found = _lead_story_split(lines, self._head(lines), [self.HOOK, self.LONG],
                                  whole_only=True)
        assert found is None  # no title that fits, no fallback: no lead chapter
        found = _lead_story_split(lines, self._head(lines), [self.HOOK, self.LONG],
                                  whole_only=True, fallback_title="Top 12 News Items")
        assert found and found[2] == "Top 12 News Items"

    def test_the_lead_backs_up_over_a_continuation_paragraph(self):
        lines = self._lines()
        found = _lead_story_split(lines, self._head(lines), [self.HOOK, self.LONG],
                                  whole_only=True, fallback_title="Lead")
        assert "".join(lines)[found[1]:].startswith("Those packs hold")

    def test_seo_tails_are_not_part_of_a_headline(self):
        assert _whole_title("Tesla Q3 Preview: The Trillion-Dollar Robot Dream Hits "
                            "A 2nm Silicon Bottleneck (TSLA)") == (
            "Tesla Q3 Preview: The Trillion-Dollar Robot Dream Hits A 2nm Silicon Bottleneck")
        assert _whole_title("Sleeping Tesla Driver on FSD Injures 2 CHP Officers [2026]") == (
            "Sleeping Tesla Driver on FSD Injures 2 CHP Officers")

    @pytest.mark.parametrize("raw,expected", [
        ("Peshawar school roof collapse kills at least 34 children: The Globe and Mail",
         "Peshawar school roof collapse kills at least 34 children"),
        ("Naming one chicken cuts preschoolers' poultry choices — Phys.org",
         "Naming one chicken cuts preschoolers' poultry choices"),
        ("iShares A.I. Innovation and Tech ETF (TSX", ""),
        ("Segment 2 — Why It Costs What It Costs Today", ""),
        ("Song Jae-hee's 160 Million Won Cybertruck: 'People Prefer Car'",
         "Song Jae-hee's 160 Million Won Cybertruck: 'People Prefer Car'"),
    ])
    def test_item_title_cleaning(self, raw, expected):
        assert _clean_item_title(raw) == expected

    def test_item_titles_read_every_heading_shape(self):
        digest = (
            "# Show\n> **The hook is a sentence, never a title.**\n---\n"
            "**Astronomer leads global team on NASA mission to early universe — Phys.org Space**\n"
            "Body.\n\n"
            "1. **Myosin gene sets left or right shell coiling — Phys.org**\nBody.\n\n"
            "**Samsung's second Taylor fab is lined up:** TechPowerUp\nBody.\n\n"
            "### 3) Aid groups warn of health-system collapse in Sudan\nBody.\n\n"
            "**What You Need to Know:** Samsung said a long sentence here today.\n"
        )
        assert _digest_item_titles(digest) == [
            "Astronomer leads global team on NASA mission to early universe",
            "Myosin gene sets left or right shell coiling",
            "Samsung's second Taylor fab is lined up",
            "Aid groups warn of health-system collapse in Sudan",
        ]

    def test_the_lead_section_name_needs_the_hooks_story(self):
        ff = ("# FF\n> **El Gordo's two quadrillion solar masses test dark matter.**\n---\n"
              "**A distant supercluster points to dark matter — Phys.org**\nBody.\n\n"
              "### Cosmic Spotlight\nThe search around 70 Oph AB shows how non-detections "
              "still tighten constraints on planets.\n")
        hook = "El Gordo's two quadrillion solar masses test dark matter"
        assert _lead_section_for_hook(ff, [hook]) == ("", set())
        desk = ("# Desk\n> **Sixteen people drowned in Bihar on Tuesday.**\n\n### Lead\n"
                "**Sixteen drown in Bihar: NDTV**\nSixteen people drowned in Bihar on "
                "Tuesday collecting festival offerings.\n")
        name, toks = _lead_section_for_hook(desk, ["Sixteen people drowned in Bihar on Tuesday"])
        assert name == "Lead" and toks


# ---------------------------------------------------------------------------
# Story chapters on a synthetic episode
# ---------------------------------------------------------------------------

DIGEST = """# Test Show
> **Regulators fined the Arizona chip plant after its coolant spill reached the Salt River banks this week.**

### Top News
1. **Arizona chip plant fined for coolant spill near river — Local Paper**
The state environment agency fined the Arizona chip plant after coolant reached the Salt River banks. Inspectors measured glycol at three sites. Source: https://example.com/a

2. **Samsung's second Taylor fab is lined up for an early-November start — TechPowerUp**
Samsung Austin Semiconductor said construction of the Taylor Fab 2 building starts in November. The building is one and a half times Fab 1. Source: https://example.com/b

3. **Swedish supercomputer Sferical One launches for Ericsson, Saab and AstraZeneca members — HPCwire with an outlet name far too long to use**
Sweden launched the sovereign supercomputer Sferical One this week. Founding members include Ericsson, AstraZeneca, Saab and SEB. Source: https://example.com/c

4. **Langdao Silex shows a homegrown EUV laser source — TechPowerUp**
Chinese startup Langdao Silex demonstrated an extreme ultraviolet laser source rated above fifteen watts. Ninety percent of components are domestic. Source: https://example.com/d

### The Teardown: Wafer bow and overlay
Overlay alignment fails when wafer bow from film stress pushes the surface out of the focal plane. Metrology tools measure bow and flatten the wafer before exposure. Panel-level packaging moves deposition from round wafers onto glass panels with through-glass vias.
"""

SCRIPT = """Regulators fined the Arizona chip plant after its coolant spill reached the Salt River banks this week.

This is Test Show, episode one.

The state environment agency fined the plant after coolant reached the Salt River banks.

Inspectors measured glycol at three sites along the river banks near the Arizona plant.

Samsung's second fab in Taylor has a construction start in November, Samsung Austin Semiconductor said.

The Taylor Fab 2 building is one and a half times the size of Fab 1.

Sweden launched the sovereign supercomputer Sferical One this week for its founding members.

Ericsson, AstraZeneca, Saab and SEB are the founding members of Sferical One in Sweden.

Langdao Silex, a Chinese startup, demonstrated an extreme ultraviolet laser source above fifteen watts.

Ninety percent of the Langdao Silex laser components are domestic, the startup said.

Overlay alignment fails when wafer bow from film stress pushes the surface out of the focal plane.

Metrology tools measure wafer bow and flatten the wafer before exposure so overlay holds.

Panel-level packaging moves deposition from round wafers onto glass panels with through-glass vias.

Before we go, watch the Taylor start date.

That's the show for today.
"""

MARKERS = [
    {"pattern": "This is Test Show", "title": "Introduction", "where": "start"},
    {"pattern": "take it apart", "title": "The Teardown", "digest_section": "The Teardown"},
    {"pattern": "Before we go", "title": "Tomorrow Teaser", "where": "end"},
    {"pattern": "That's the show", "title": "Closing", "where": "end"},
]


class TestStoryChapters:
    def _chapters(self):
        return parse_chapters(SCRIPT, MARKERS, story_headlines=extract_story_headlines(DIGEST),
                              digest_text=DIGEST)

    def test_each_story_opens_its_own_chapter(self):
        chapters = self._chapters()
        samsung = _by_title(chapters, "Samsung's second Taylor fab is lined up for an early-November start")
        assert _opens(samsung, SCRIPT).startswith("Samsung's second fab in Taylor")
        silex = _by_title(chapters, "Langdao Silex shows a homegrown EUV laser source")
        assert _opens(silex, SCRIPT).startswith("Langdao Silex, a Chinese startup")
        teardown = _by_title(chapters, "The Teardown")
        assert _opens(teardown, SCRIPT).startswith("Overlay alignment fails")

    def test_the_lead_is_never_titled_with_another_story(self):
        titles = [c.title for c in self._chapters()]
        assert titles[1] == "Arizona chip plant fined for coolant spill near river", titles

    def test_an_over_budget_headline_gets_no_chapter_and_nothing_is_clipped(self):
        chapters = self._chapters()
        for c in chapters:
            assert len(c.title) <= HEADLINE_CHAPTER_TITLE_MAX, c.title
            assert not c.title.endswith("…")
        assert not any(t.startswith("Swedish supercomputer") for t in (c.title for c in chapters))

    def test_closing_is_final_and_order_holds(self):
        chapters = self._chapters()
        assert chapters[-1].title == "Closing"
        starts = [c.word_start for c in chapters]
        assert starts == sorted(starts) and len(set(starts)) == len(starts)
        for a, b in zip(chapters, chapters[1:]):
            assert a.word_end == b.word_start

    def test_without_a_digest_nothing_changes_shape(self):
        chapters = parse_chapters(SCRIPT, MARKERS, story_headlines=[])
        assert [c.title for c in chapters][0] == "Introduction"

    def test_a_broken_digest_never_raises(self):
        for digest in ("", "###", "# x\n" + "\x00" * 50, DIGEST.replace("\n", "\r")):
            parse_chapters(SCRIPT, MARKERS, story_headlines=["x" * 300, "(unbalanced"],
                           digest_text=digest)


# ---------------------------------------------------------------------------
# The Oct 17 slate, replayed from the committed files
# ---------------------------------------------------------------------------

class TestOct17Slate:
    def test_tesla_637_titles_are_whole_and_stories_split(self):
        chapters, script, digest, *_ = _replay("tesla", "tesla_shorts_time", "*Ep637_20261017")
        titles = [c.title for c in chapters]
        assert "Luxury estate in South Africa has off-grid home fitted" not in titles
        assert not any(t.startswith("History Says Tesla Stock") for t in titles)
        heads = [_whole_title(h) for h in extract_story_headlines(digest, 12)]
        for t in titles:
            assert len(t) <= HEADLINE_CHAPTER_TITLE_MAX
            assert not any(h != t and h.startswith(t) and not re.match(r"^\s*[:—(\[]", h[len(t):])
                           for h in heads), t
        q3 = _by_title(chapters, "Tesla Q3 Preview: The Trillion-Dollar Robot Dream Hits A 2nm Silicon Bottleneck")
        assert _opens(q3, script).startswith("Advanced two nanometer silicon")
        assert _opens(_by_title(chapters, "Sleeping Tesla Driver on FSD Injures 2 CHP Officers"),
                      script).startswith("A Tesla driver who had fallen asleep")
        assert _opens(_by_title(chapters, "Tesla First Principles"), script).startswith("Grid-tied homes")
        teaser = _by_title(chapters, "Tomorrow Teaser")
        assert all(c.word_end - c.word_start < 300 for c in chapters if c.word_start < teaser.word_start
                   and c.title != "Tesla First Principles")

    def test_ff_225_spotlight_and_hubble_sit_on_their_stories(self):
        chapters, script, *_ = _replay("fascinating_frontiers", "fascinating_frontiers", "*Ep225_20261017")
        lead = chapters[1]
        assert lead.title == "A distant supercluster of galaxies points to self-interacting dark matter"
        assert _opens(lead, script).startswith("El Gordo")
        spot = _by_title(chapters, "Cosmic Spotlight")
        oph = script.index("seventy Oph")
        assert spot.char_start > oph - 400  # never inside the El Gordo lead
        hubble = _by_title(chapters, "NASA's Hubble spies spiral's edge")
        assert _opens(hubble, script).startswith("Hubble recorded")

    def test_ff_224_spotlight_is_not_the_lead(self):
        chapters, *_ = _replay("fascinating_frontiers", "fascinating_frontiers", "*Ep224_20261016")
        assert chapters[1].title != "Cosmic Spotlight"

    def test_planetterrian_216_news_items_leave_the_deep_dive(self):
        chapters, script, *_ = _replay("planetterrian", "planetterrian", "*Ep216_20261017")
        dive = _by_title(chapters, "Science Deep Dive")
        assert script.index("A bacterial strain isolated from yogurt") >= dive.char_end
        dive_i = [c.title for c in chapters].index("Science Deep Dive")
        assert len(chapters) - dive_i - 1 >= 8  # the news items after it, + teaser/closing

    def test_ai_chips_026_lead_is_not_samsung(self):
        chapters, script, *_ = _replay("ai_chips", "ai_chips", "*Ep026_20261017")
        titles = [c.title for c in chapters]
        assert titles[1] != "Samsung's second Taylor fab is lined up for an early-November start"
        samsung = _by_title(chapters, "Samsung's second Taylor fab is lined up for an early-November start")
        assert _opens(samsung, script).startswith("Samsung's second fab in Taylor")
        assert titles.index("The Teardown") >= 7  # lead + five stories before it

    def test_mit_203_pick_and_review_are_not_swapped(self):
        chapters, script, *_ = _replay("modern_investing", "modern_investing", "*Ep203_20261017")
        pick = _by_title(chapters, "Practice Investment of the Day")
        review = _by_title(chapters, "Trade Review & Lessons")
        assert _opens(pick, script).startswith("Enbridge, ticker E N B")
        assert _opens(review, script).startswith("No newly closed simulated hold")
        titles = [c.title for c in chapters]
        for t in ("Strategy Spotlight", "Investor Education", "Portfolio Performance"):
            assert t in titles

    def test_mit_portfolio_lands_where_it_is_spoken(self):
        chapters, script, _d, cfg, md = _replay("modern_investing", "modern_investing", "*Ep203_20261017")
        tj = md.with_name(md.stem + "_transcript.json")
        cj = md.parent / "chapters_ep203.json"
        if not (tj.exists() and cj.exists()):
            pytest.skip("transcript or chapters not on disk")
        duration = json.loads(cj.read_text())["chapters"][-1]["endTime"]
        # Oct 18 2026: one frame for both passes — the voice sits
        # voice_intro_delay into the mix, never intro_duration as well.
        calculate_timestamps(chapters, duration,
                             music_intro_offset=cfg.audio.voice_intro_delay)
        transcript = json.loads(tj.read_text())
        align_timestamps_to_transcript(chapters, script, transcript,
                                       music_intro_offset=cfg.audio.voice_intro_delay,
                                       total_duration=duration)
        spoken = next(s["start"] for s in transcript["segments"] if "simulated book" in s["text"])
        assert abs(_by_title(chapters, "Portfolio Performance").startTime
                   - (cfg.audio.voice_intro_delay + spoken)) < 2.0
        starts = [c.startTime for c in chapters]
        assert starts == sorted(starts)
        assert chapters[-1].endTime == pytest.approx(duration, abs=0.1)


class TestMitMarkers:
    def _rx(self, title):
        cfg = load_config(ROOT / "shows" / "modern_investing.yaml")
        m = next(m for m in cfg.chapters.section_markers if m.title == title)
        return re.compile(m.pattern, re.IGNORECASE)

    @pytest.mark.parametrize("line", [
        "Enbridge, ticker E N B on the T S X, is today's simulated weekly hold, shares only.",
        "Brookfield Corp, ticker B N on the T S X, is this week's simulated weekly hold.",
        "This is a simulated weekly hold for learning purposes, with no real money on the line.",
    ])
    def test_the_pick_is_the_practice_investment(self, line):
        assert self._rx("Practice Investment of the Day").search(line)
        assert not self._rx("Trade Review & Lessons").search(line)

    @pytest.mark.parametrize("line", [
        "Advanced Micro Devices, ticker AMD, was the last simulated weekly hold, built as a catalyst play.",
        "XNDU was the prior weekly hold, a catalyst play on a manufacturing partnership.",
        "No newly closed simulated hold has printed since the last review.",
        "The most recent Practice Investment has already been scored.",
    ])
    def test_a_past_hold_is_the_trade_review(self, line):
        assert self._rx("Trade Review & Lessons").search(line)
        if "last simulated weekly hold" in line:
            assert not re.search(r"(?<!last )(?<!prior )(?<!previous )simulated weekly hold", line)


class TestAlignment:
    def _transcript(self, words):
        return {"segments": [{"start": words[0][1], "end": words[-1][2], "text": "",
                              "words": [{"word": w, "start": s, "end": e} for w, s, e in words]}]}

    def test_starts_follow_the_spoken_words_and_never_reorder(self):
        script = ("This is Test Show, episode one.\n\nAlpha bravo charlie delta echo foxtrot golf.\n\n"
                  "Hotel india juliet kilo lima mike november.\n")
        lines = script.splitlines(keepends=True)
        ch = [Chapter(title="Introduction", word_start=0, word_end=6, char_start=0, char_end=0),
              Chapter(title="A", word_start=6, word_end=13), Chapter(title="B", word_start=13, word_end=20)]
        ch[1].char_start = len("".join(lines[:2]))
        ch[2].char_start = len("".join(lines[:4]))
        for c in ch:
            c.opening = script[c.char_start:].strip().split("\n")[0]
        words = [(w, i * 0.5, i * 0.5 + 0.4) for i, w in enumerate(
            "this is test show episode one".split())]
        words += [(w, 17 + i * 0.5, 17.4 + i * 0.5) for i, w in enumerate(
            "alpha bravo charlie delta echo foxtrot golf".split())]
        words += [(w, 36 + i * 0.5, 36.4 + i * 0.5) for i, w in enumerate(
            "hotel india juliet kilo lima mike november".split())]
        calculate_timestamps(ch, 60.0, music_intro_offset=3.0)
        align_timestamps_to_transcript(ch, script, self._transcript(words),
                                       music_intro_offset=0.0, total_duration=60.0)
        # The word-count estimate put them at 20.1 s and 40.1 s.
        assert ch[1].startTime == pytest.approx(17.0, abs=0.01)
        assert ch[2].startTime == pytest.approx(36.0, abs=0.01)
        assert ch[0].endTime == ch[1].startTime and ch[-1].endTime == 60.0

    def test_garbage_never_raises_and_changes_nothing(self):
        ch = [Chapter(title="Introduction", startTime=1.0, endTime=5.0),
              Chapter(title="B", startTime=5.0, endTime=9.0, char_start=3)]
        for bad in (None, {}, {"segments": [{"words": [{"word": None}]}]}, "nope"):
            align_timestamps_to_transcript(ch, "ab\ncd\n", bad, total_duration=9.0)
        assert [c.startTime for c in ch] == [1.0, 5.0]

    def test_run_show_aligns_after_the_estimate(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        est = src.index("calculate_timestamps(\n                        episode_chapters")
        align = src.index("align_timestamps_to_transcript(", est)
        assert align > est
        assert "voice_intro_delay" in src[align:align + 600]


# ---------------------------------------------------------------------------
# Every committed episode of the week: the invariants
# ---------------------------------------------------------------------------

def _week():
    out = []
    for yml in sorted((ROOT / "shows").glob("*.yaml")):
        if yml.name.startswith("_"):
            continue
        try:
            cfg = load_config(yml)
        except Exception:
            continue
        if not (cfg.chapters.enabled and cfg.chapters.section_markers):
            continue
        for md in sorted((ROOT / cfg.episode.output_dir).glob("*_Ep*_2026101[0-7].md")):
            tts = md.with_name(md.stem + "_tts.txt")
            if tts.exists():
                out.append((cfg, md, tts))
    return out


def test_the_week_keeps_every_invariant():
    episodes = _week()
    if not episodes:
        pytest.skip("no committed Oct 10-17 episodes")
    for cfg, md, tts in episodes:
        digest = md.read_text(encoding="utf-8")
        chapters = parse_chapters(
            tts.read_text(encoding="utf-8"), cfg.chapters.section_markers, show_name=cfg.name,
            story_headlines=extract_story_headlines(digest, 12), digest_text=digest,
            known_sections_only=getattr(cfg.chapters, "known_sections_only", False))
        titles = [c.title for c in chapters]
        where = f"{md.name}: {titles}"
        for t in titles:
            assert len(t) <= HEADLINE_CHAPTER_TITLE_MAX, where
            assert not t.endswith("…"), where
            assert not re.match(r"^(segment|part)\s+\d", t, re.IGNORECASE), where
        closing = [i for i, t in enumerate(titles) if t.lower() in ("closing", "sign-off")]
        if closing:
            assert closing[-1] == len(titles) - 1, where
        starts = [c.word_start for c in chapters]
        assert starts == sorted(starts), where
