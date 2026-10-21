"""Oct 16 2026 slate review: story breaks that reach the audio, Nerra Daily
handoffs that introduce their own segment, and smaller defects the slate
put on air.

Data-driven guards read FIXED dated files (the Oct 16 episodes), never the
newest file, so tomorrow's slate cannot turn them red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import story_breaks as sb  # noqa: E402


def _episode(rel: str):
    base = ROOT / rel
    script = base.with_name(base.name + "_tts.txt").read_text(encoding="utf-8")
    digest = base.with_name(base.name + ".md").read_text(encoding="utf-8")
    tj = base.with_name(base.name + "_transcript.json")
    transcript = json.loads(tj.read_text(encoding="utf-8")) if tj.exists() else None
    return script, digest, transcript


class TestStoryUnits:
    def test_a_link_at_the_end_of_a_paragraph_makes_it_a_story(self):
        # Fascinating Frontiers Ep224 put each item's Source at the END of
        # its paragraph, under the hook rule: one beat for seven stories.
        md = ("# Show\n> **Hook sentence about the moon contracting.**\n---\n"
              "**Lunar faults map the moon shrinking — Phys.org**\n"
              "A new study of young scarps measures how much the moon has contracted "
              "as its interior cooled over billions of years. Source: [phys.org](https://phys.org/a)\n\n"
              "**Rare methanol detected in a star-forming region — Universe Today**\n"
              "Astronomers detected a rare isotopic form of methanol in a planet-forming "
              "disk for the first time with ALMA spectra. Source: [universetoday.com](https://universetoday.com/b)\n")
        units = sb.story_units(md)
        assert len(units) == 2
        assert all(u.label == "item" for u in units)

    def test_a_numbered_heading_is_one_story_with_its_sources_list(self):
        # Omni View writes "### 1) <title>" over prose and a Read-more list;
        # the list was its own story and the second source's sentence got a
        # beat in the middle of the lead.
        md = ("# Omni View\n> **Hook.**\n\n## Today's lead story (1)\n"
              "### 1) G7 plans first coordinated drills against AI cyber threats\n"
              "**What happened:** The Group of Seven announced joint exercises testing "
              "defences against artificial-intelligence-assisted attacks on grids.\n\n"
              "**Read more (sources):**\n- [Reuters](https://reuters.com/a) — announcement\n"
              "- [Al Jazeera](https://aljazeera.com/b) — background on coding tools\n\n"
              "### 2) Rubio urges Lebanon to keep seized explosives from Hezbollah\n"
              "**What happened:** The Secretary of State pressed Lebanon's president over "
              "seven hundred eighty kilograms of intercepted explosives.\n\n"
              "**Read more (sources):**\n- [Al Jazeera](https://aljazeera.com/c) — call\n")
        units = sb.story_units(md)
        assert [u.section[:2] for u in units] == ["1)", "2)"]
        assert all(u.label == "item" for u in units)

    def test_the_two_real_episodes(self):
        ff = _episode("digests/fascinating_frontiers/Fascinating_Frontiers_Ep224_20261016")
        assert len(sb.story_boundary_lines(ff[0], ff[1])) >= 6
        ov = _episode("digests/omni_view/Omni_View_Ep207_20261016")
        lines = sb.script_lines(ov[0])
        breaks = sb.story_boundary_lines(ov[0], ov[1])
        # The beat before the second story lands before Rubio, not before
        # the G7 story's last sentence.
        rubio = next(i for i, ln in enumerate(lines) if ln.startswith("United States Secretary of State Marco Rubio"))
        assert rubio in breaks and rubio - 1 not in breaks and rubio - 2 not in breaks


class TestAdjacentBeats:
    def test_a_section_opener_wins_the_pair(self):
        units = [
            SimpleNamespace(section="what's on", tokens=frozenset({"film"})),
            SimpleNamespace(section="sports", tokens=frozenset({"lions"})),
        ]
        assert sb._opens_on_section("For what's on around town, a film opens Friday.", units)
        assert not sb._opens_on_section("Whyte kicked eight field goals for the Lions.", units)

    def test_no_two_beats_on_consecutive_lines_on_the_slate(self):
        for rel in ("digests/omni_view/Omni_View_Ep207_20261016",
                    "digests/fascinating_frontiers/Fascinating_Frontiers_Ep224_20261016",
                    "digests/unintended_consequences/Unintended_Consequences_Ep144_20261016",
                    "digests/vancouver/Vancouver_Daily_Ep024_20261016"):
            script, digest, _ = _episode(rel)
            br = sb.story_boundary_lines(script, digest)
            assert all(b - a > 1 for a, b in zip(br, br[1:])), rel


class TestAnchorsReachTheAudio:
    def test_accents_fold(self):
        assert sb._norm("Nación") == sb._norm("Nacion") == "nacion"

    def test_a_spoken_year_finds_whisper_digits(self):
        words = [("the", 0.0, 0.2), ("program", 0.2, 0.6), ("grew", 0.6, 0.9),
                 ("in", 1.6, 1.7), ("the", 1.7, 1.8), ("early", 1.8, 2.1), ("2000s", 2.1, 2.6),
                 ("biologists", 2.6, 3.2), ("sampling", 3.2, 3.6), ("coho", 3.6, 3.9),
                 ("kept", 3.9, 4.1), ("finding", 4.1, 4.5), ("marks", 4.5, 4.9)]
        transcript = {"segments": [{"words": [{"word": w, "start": s, "end": e} for w, s, e in words]}]}
        script = ("The program grew.\n"
                  "In the early two thousands, biologists sampling coho kept finding marks.")
        anchors, unmatched = sb.boundary_anchors(script, [1], transcript)
        assert unmatched == 0
        assert anchors == [(0.9, 1.6)]

    def test_the_slate_places_nine_in_ten_more(self):
        # Before: 4 of 6 breaks on UC Ep144 never anchored (spoken years,
        # Whisper's own spellings). Every one anchors now.
        script, digest, transcript = _episode(
            "digests/unintended_consequences/Unintended_Consequences_Ep144_20261016")
        br = sb.story_boundary_lines(script, digest)
        anchors, unmatched = sb.boundary_anchors(script, br, transcript)
        assert unmatched == 0 and len(anchors) == len(br)


class TestNerraDailyHandoffs:
    def _segments(self):
        from engine.daily_edition import Segment
        def seg(name, hook):
            return Segment(slug=name.lower(), show_name=name, episode_num=1, episode_title="",
                           hook=hook, date="2026-10-16", audio_url="", content="",
                           digest_dir=ROOT, transcript_path=None, music_intro_offset=0.0)
        return [
            seg("SpaceX Daily", "SpaceX thrusters give the Roadster aerial flight"),
            seg("Planetterrian Daily", "Researchers mapped PFAS across Finger Lakes water bodies"),
            seg("Models & Agents", "Pause-token compression shrinks the inference cache"),
            seg("Fascinating Frontiers", "Young lunar faults measure how much the moon contracted"),
            seg("Omni View", "G7 nations will run joint drills against cyber attacks"),
        ]

    def test_a_shifted_draft_is_realigned(self):
        from engine.daily_edition import realign_handoffs
        segs = self._segments()
        links = {"handoffs": [
            "Next, PFAS samples from the Finger Lakes water bodies.",
            "After the water data, lunar faults show how far the moon contracted.",
            "The edition closes with the G7 drills against cyber attacks.",
            "No new episode of The Age of AI aired today.",
        ]}
        out = realign_handoffs(links, segs)
        assert out["_handoffs_realigned"] >= 2
        assert "PFAS" in out["handoffs"][0]
        assert "Models & Agents" in out["handoffs"][1]
        assert "lunar" in out["handoffs"][2]
        assert "G7" in out["handoffs"][3]

    def test_an_aligned_draft_is_untouched(self):
        from engine.daily_edition import realign_handoffs
        links = {"handoffs": [
            "Next, PFAS across the Finger Lakes water bodies.",
            "A cache trick: pause-token compression for inference.",
            "Then the moon, and the young lunar faults.",
            "Finally the G7 drills against cyber attacks.",
        ]}
        out = realign_handoffs(dict(links), self._segments())
        assert out["handoffs"] == links["handoffs"] and out["_handoffs_realigned"] == 0

    def test_the_build_calls_it(self):
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        assert "links = realign_handoffs(links, segments)" in src

    def test_yesterdays_lineup_is_excluded_from_the_field_note(self):
        from engine import daily_edition as de
        src = (ROOT / "engine" / "daily_edition.py").read_text(encoding="utf-8")
        body = src.split("def build_find_prompt(")[1].split("\ndef ")[0]
        assert "recent_lineup_hooks(spec, root)" in body
        assert de.RECENT_LINEUP_EDITIONS >= 2


class TestSmallerDefects:
    @pytest.mark.parametrize("text, banned", [
        ("A mom-and-pop buyer stepped in.", "month over month"),
        ("моя мама means my mom.", "month over month"),
        ("Roe v. Wade was decided in 1973.", "R O E"),
        ("Gideon Sa'ar called the scenes shameful.", "A R"),
    ])
    def test_ratio_shorthands_match_only_their_own_case(self, text, banned):
        from assets.pronunciation import apply_pronunciation_fixes
        assert banned not in apply_pronunciation_fixes(text)

    def test_the_shorthand_itself_still_expands(self):
        from assets.pronunciation import apply_pronunciation_fixes
        assert "month over month" in apply_pronunciation_fixes("Sales rose 4% MoM.")

    def test_paid_placements_never_reach_a_prompt(self):
        from engine.utils import drop_excluded_titles
        arts = [{"title": "Pipes", "url": "https://www.datacenterdynamics.com/en/marketwatch/the-future-of-data-center-efficiency-starts-with-pipes/"},
                {"title": "News", "url": "https://www.datacenterdynamics.com/en/news/a-real-story/"}]
        kept, dropped = drop_excluded_titles(arts, ["zzzz-no-title-match"])
        assert dropped == 1 and kept[0]["title"] == "News"

    def test_both_sides_is_never_deduped_away(self):
        from engine.config import load_config
        for slug in ("vancouver", "collingwood", "omni_view_world"):
            cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
            assert "Both Sides" in cfg.digest_overlap_exempt_sections, slug

    def test_mit_names_the_record_start(self):
        sys.path.insert(0, str(ROOT / "shows" / "hooks"))
        import modern_investing as mit
        phrase = mit._record_start_phrase({"metadata": {"inception_date": "2026-03-16"}})
        assert phrase == "since the practice portfolio opened on March 16, 2026"
        src = (ROOT / "shows" / "hooks" / "modern_investing.py").read_text(encoding="utf-8")
        assert "since inception {_sign(bench_itd)}" not in src

    def test_mit_teaser_is_the_next_session(self):
        p = (ROOT / "shows" / "prompts" / "modern_investing_podcast.txt").read_text(encoding="utf-8")
        assert "something to watch for tomorrow" not in p
        assert "next trading session" in p

    def test_top_world_does_not_call_gated_desks_late(self):
        sys.path.insert(0, str(ROOT / "shows" / "hooks"))
        import omni_view_world as ow
        assert "press time" not in ow.intake_line(0, 5)

    def test_uc_cross_promo_has_no_stock_line(self):
        p = (ROOT / "shows" / "prompts" / "unintended_consequences_podcast.txt").read_text(encoding="utf-8")
        assert "covers the regulatory side" not in p
        assert "Environmental Intelligence" in p

    def test_omni_view_names_an_outlet_only_for_its_own_story(self):
        p = (ROOT / "shows" / "prompts" / "omni_view_digest.txt").read_text(encoding="utf-8")
        assert "AT LEAST TWO distinct outlets" not in p
        assert "covers THIS story" in p
        assert "Compare how [Outlet A](URL)" not in p

    def test_week_board_counts_single_readings(self, tmp_path):
        import datetime as _dt
        from engine.board_week import board_lines, week_board_block
        line = ("US-Iran ceasefire continues through October 31, priced at 80.5 cents, an 80.5 "
                "percent implied probability, on Polymarket, read at 11:20 UTC on October 13, 2026.")
        row = board_lines("### The Board\n" + line + "\n")[0]
        # The question stops before the price, never at the reading time.
        assert row["question"] == "US-Iran ceasefire continues through October 31"
        (tmp_path / "PM_Ep018_20261010.md").write_text(
            "### The Board\nDoes the U.S.-Iran ceasefire continue through October 31: that date "
            "at a 75.5 percent implied probability; Polymarket.\n"
            "Georgia governor: Rick Jackson is priced at 52 cents, a 52 percent implied "
            "probability, on Kalshi.\n### Next\n", encoding="utf-8")
        (tmp_path / "PM_Ep021_20261013.md").write_text("### The Board\n" + line + "\n### Next\n",
                                                       encoding="utf-8")
        block = week_board_block(tmp_path, _dt.date(2026, 10, 16))
        assert "75.5% on Saturday → 80.5% on Tuesday (+5 points)" in block
        assert "do not list or price them): 1 — Georgia governor — Rick Jackson (Kalshi)" in block
