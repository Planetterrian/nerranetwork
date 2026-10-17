"""Guards for the Oct 17 2026 slate review (docs/reviews/slate_review_2026_10_17.md).

Story breaks: the 20 s spacing dropped real stories, the cold open and the
sign-off set the story, all-essay digests got beats mid-thought, and an
anchor search backed off by a count of script words. Content: the digest
expansion's dedup deleted the claims ledger's lines, a stale story re-surfaced
behind a dated slug, MIT picked a symbol it already held, Top World told
public readers about the members-only desks, and the X teaser was clipped
outside engine/titles.py. X: a queued post was counted as posted.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import story_breaks as S  # noqa: E402
from engine.article_dates import url_slug_date  # noqa: E402
from engine.generator import _dedup_expansion_sentences  # noqa: E402


# ------------------------------------------------------------ story breaks --
def _digest(*sections):
    out = ["# Show", "", "> **The hook.**", ""]
    for name, paras in sections:
        out += [f"### {name}", ""]
        for p in paras:
            out += [p, ""]
    return "\n".join(out)


class TestSpacing:
    def test_floor_is_twelve_seconds(self):
        assert S.MIN_STORY_SECONDS == 12.0
        # Tesla's stories run 14-22 s apart: a 15 s pair keeps both beats.
        anchors = [(30.0, 30.4), (45.0, 45.4)]
        sil = [(29.9, 30.4), (44.9, 45.4)]
        breaks, _ = S.plan_breaks(anchors, sil, gap_seconds=1.0)
        assert len(breaks) == 2


def _real(pattern):
    hits = sorted(ROOT.glob(f"digests/*/{pattern}_tts.txt"))
    if not hits:
        pytest.skip("fixture episode pruned")
    tts = hits[0]
    md = Path(str(tts).replace("_tts.txt", ".md"))
    return tts.read_text(encoding="utf-8"), md.read_text(encoding="utf-8")


class TestColdOpenAndSignOff:
    def test_the_hook_never_sets_the_story(self):
        # FF Ep225: "El Gordo, as the cluster is nicknamed…" is the lead
        # story's first body line, not a new story.
        script, md = _real("Fascinating_Frontiers_Ep225_20261017")
        lines = S.script_lines(script)
        starts = [lines[i][:20] for i in S.story_boundary_lines(script, md)]
        assert "El Gordo, as the clu" not in starts
        assert len(starts) >= 6

    def test_nothing_after_the_sign_off_gets_a_beat(self):
        script, md = _real("Omni_View_Africa_Mideast_Ep023_20261015")
        lines = S.script_lines(script)
        signoff = next(i for i, ln in enumerate(lines) if "see you tomorrow" in ln.lower())
        assert all(i < signoff for i in S.story_boundary_lines(script, md))

    def test_identity_and_signoff_patterns(self):
        assert S._IDENTITY_RE.match("This is Fascinating Frontiers, episode two hundred.")
        assert S._SIGNOFF_RE.search("That's Omni View Africa and Middle East for today.")
        assert S._SIGNOFF_RE.search("I'm Mira — see you tomorrow.")


class TestSectionsAreNotSplitByTheirCitation:
    def test_unsourced_paragraphs_join_the_sourced_one_after_them(self):
        md = _digest(("The Closer Look", [
            "**Equipment maker sued: Global BC** Dealers say the company cut them off.",
            "Civil lawsuits now allege the maker defrauded equipment dealers in Canada.",
            "The company told Global News the dealer bought inventory. Source: https://g.example/x",
        ]), ("Sports", ["**Canucks at Lightning: Fox** The Canucks play Tampa today, wrapping "
                        "a six-game road trip. Source: https://f.example/y"]))
        units = S.story_units(md)
        assert [u.section for u in units] == ["the closer look", "sports"]

    def test_a_sourced_item_with_its_own_title_stays_separate(self):
        # MAB pools both Source lines at the end of a section's last item.
        md = _digest(("Quick Bits", [
            "**Anthropic opens Singapore office** Anthropic opened a fifth Asia-Pacific "
            "office and signed a safety testing agreement with the government.",
            "**Agents caught scraping maps** Researchers found uncontrolled agents on a "
            "cloud service pulling mapping data thousands of times. "
            "Source: https://a.example/1 Source: https://b.example/2",
        ]))
        assert len(S.story_units(md)) == 2


class TestNarrativeDigestsMoveForward:
    def test_a_segment_already_told_never_gets_a_second_beat(self):
        md = _digest(
            ("Segment 1", ["Marshes of southern Iraq fed fisheries and reed villages for "
                           "centuries before upstream dams cut the flood pulse."]),
            ("Segment 2", ["Turkey built dams on the Euphrates and Tigris to irrigate the "
                           "Harran plain and generate hydropower turbines."]),
        )
        script = "\n".join([
            "This is Unintended Consequences, episode one.",
            "Marshes of southern Iraq fed fisheries and reed villages for centuries.",
            "The marsh fisheries and reed villages depended on the flood pulse.",
            "Turkey built dams on the Euphrates and Tigris to irrigate the Harran plain.",
            "The dams irrigate the Harran plain and turn hydropower turbines.",
            "Marshes of southern Iraq lost fisheries and reed villages.",
            "Reed villages and marsh fisheries in southern Iraq emptied.",
        ])
        assert S.story_boundary_lines(script, md) == [3]


class TestAnchorBacksOffByLetters:
    def test_split_whisper_words_anchor_on_the_first_word(self):
        words = ["the", "fourteenth", "m", "i", "t", "c", "s", "a", "l", "researchers",
                 "placed", "an", "agent", "inside", "a", "lobster", "tank"]
        transcript = {"segments": [{"words": [
            {"word": w, "start": float(i), "end": i + 0.5} for i, w in enumerate(words)]}]}
        script = "Intro line here.\nMIT CSAIL researchers placed an agent inside a lobster tank."
        anchors, unmatched = S.boundary_anchors(script, [1], transcript)
        assert unmatched == 0
        assert anchors[0][1] == 2.0  # "m", not "a" five words late


# --------------------------------------------------------- ledger dedup --
class TestExpansionDedupKeepsTheLedger:
    def test_fenced_lines_are_never_deduplicated(self):
        sentence = "The company shipped forty thousand cells to grid storage buyers last month."
        script = "\n".join([
            sentence,
            "",
            "```claims",
            json.dumps([{"claim": sentence, "supporting_quote": sentence}]),
            "```",
        ])
        out = _dedup_expansion_sentences(script)
        cleaned = out[0] if isinstance(out, tuple) else out
        assert cleaned.count(sentence) == 3


# ------------------------------------------------------------ slug dates --
class TestSlugDates:
    def test_the_hindu_quake_update_is_dated_by_its_slug(self):
        d = url_slug_date("https://www.thehindu.com/news/international/"
                          "panama-earthquake-toll-injuries-damage-update-october-10-2026/article1.ece")
        assert d is not None and d.date() == dt.date(2026, 10, 10)

    def test_iso_slug(self):
        assert url_slug_date("https://x.example/news/storm-2026-10-01-update").date() == dt.date(2026, 10, 1)

    def test_a_path_dated_url_is_left_to_its_path(self):
        assert url_slug_date("https://x.example/2026/10/15/dividend-for-period-ending-september-30-2026") is None

    def test_no_date_no_answer(self):
        assert url_slug_date("https://x.example/news/plain-story") is None

    def test_the_earliest_slug_date_wins(self):
        d = url_slug_date("https://x.example/report-october-3-2026-deadline-march-31-2027")
        assert d.date() == dt.date(2026, 10, 3)

    def test_the_stale_gate_reads_the_slug(self):
        from engine.article_text import article_age_days
        art = {"url": "https://www.thehindu.com/news/panama-quake-update-october-10-2026/a.ece",
               "published_date": "2026-10-17T06:00:00+00:00"}
        now = dt.datetime(2026, 10, 17, 12, tzinfo=dt.timezone.utc)
        try:
            age = article_age_days(art, now=now)
        except TypeError:
            age = article_age_days(art)
        assert age is not None and age >= 6


# ------------------------------------------------------------------ MIT --
class TestMitOpenPositions:
    def test_held_symbols_are_named(self):
        sys.path.insert(0, str(ROOT / "shows" / "hooks"))
        import importlib
        mit = importlib.import_module("shows.hooks.modern_investing")
        note = mit._open_positions_note({"trades": [
            {"symbol": "ENB.TO", "status": "open"}, {"symbol": "TD.TO", "status": "closed"},
            {"symbol": "ENB.TO", "status": "open"}]})
        assert "ENB.TO" in note and "TD.TO" not in note and note.count("ENB.TO") == 1
        assert mit._open_positions_note({"trades": []}) == ""


# ----------------------------------------------------------- MAB / Top World --
def test_mab_explainer_is_exempt_from_the_overlap_dedupe():
    from engine.config import load_config
    cfg = load_config(ROOT / "shows" / "models_agents_beginners.yaml")
    assert "Explain Like I'm 14" in cfg.digest_overlap_exempt_sections


def test_top_world_has_no_intake_line_without_desks():
    import importlib
    tw = importlib.import_module("shows.hooks.omni_view_world")
    assert tw.intake_line(0, 5) == ""


# ------------------------------------------------------------------- X --
def test_x_teaser_clips_through_engine_titles():
    src = (ROOT / "run_show.py").read_text(encoding="utf-8")
    start = src.index("def _build_teaser(")
    body = src[start:src.index("\ndef ", start + 10)]
    assert not re.search(r"hook_text\[:\d+\]", body)
    assert "clip_words(hook_text, X_TEASER_TEXT_MAX)" in body


def test_a_queued_post_is_recorded_as_queued():
    src = (ROOT / "run_show.py").read_text(encoding="utf-8")
    assert 'metrics.record("x_post_queued", True)' in src


def test_dashboard_separates_queued_from_posted(tmp_path):
    import scripts.generate_dashboard as gd
    show = tmp_path / "digests" / "s"
    show.mkdir(parents=True)
    for n, queued in ((1, True), (2, False)):
        (show / f"S_Ep{n:03d}_20261016.md").write_text("x", encoding="utf-8")
        counters = {"x_posted": True}
        if queued:
            counters["x_post_queued"] = True
        (show / f"metrics_ep{n:03d}.json").write_text(json.dumps({"counters": counters}),
                                                      encoding="utf-8")
    out = gd._episode_counter_shares(tmp_path, dt.date(2026, 10, 17), days=7, min_n=1)
    assert out["x_posted_share_7d"] == 1.0
    assert out["x_queued_share_7d"] == 0.5
