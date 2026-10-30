"""Oct 30 2026 — a listener review of Offshore North Ep011, acted on.

The reviewer's five points, each checked against the primary source before
it was acted on:

* The RORC Transatlantic is NOT a Vendée Globe qualifier. Ep011 said it
  "counts as a qualifying passage". The 2028 Notice of Race (section 9.1)
  requires a SOLO finish from a list of IMOCA Globe Series races, on the
  same boat, within twice the first finisher's time; the RORC Transatlantic
  is double-handed and outside the series. The team's announcement never
  claimed otherwise: the show supplied the qualifier claim.
* The host-experience lines ("Dan's lens", required once a week since
  Sep 14) are out of the show, in the prompts and in code.
* Every team item is dated; the race start (10 January 2027, Marina
  Lanzarote) is on record.
* The 2023 record was set on the team's earlier IMOCA, not EMIRA IV; Alan
  Roberts gets one line of who he is.
* No padding (a photo, a mascot, a fact told twice, an explainer that
  aired the week before), and The Fleet's chapter starts where the segment
  does (1:49 in the published MP3: "Now, the fleet." was too short for the
  transcript matcher, so the chapter kept its word-count time, 1:59).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ON = ROOT / "digests" / "offshore_north"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _prompts() -> dict:
    return {name: _read(f"shows/prompts/offshore_north_{name}.txt")
            for name in ("digest", "podcast", "system", "field_guide", "standing_facts")}


class TestQualificationIsTheNoticeOfRace:
    def test_field_guide_lists_the_solo_qualifiers(self):
        guide = _prompts()["field_guide"]
        for race in ("Vendée Arctique 2026", "Route du Rhum 2026", "Retour à la Base 2027",
                     "The Transat CIC 2028", "New York Vendée"):
            assert race in guide, race
        assert "twice the first finisher's time" in guide
        assert "top 37 in the IMOCA Globe Series" in guide
        assert "RORC Transatlantic" in guide and "never a 9.1 qualifier" in guide

    def test_the_old_double_count_line_is_gone(self):
        # "every solo race finished on EMIRA IV ... can tick the solo-qualifier
        # box" was the line the model generalised to a double-handed race.
        assert "count double" not in _prompts()["field_guide"]

    def test_standing_facts_say_the_rorc_is_not_a_qualifier(self):
        facts = _prompts()["standing_facts"]
        assert "It is NOT a Vendée Globe qualifier" in facts
        assert "10 January 2027" in facts and "Marina Lanzarote" in facts
        assert "Retour à la Base 2027 or The Transat CIC 2028" in facts
        assert "Ep011 (26 Oct 2026) said the RORC Transatlantic" in facts

    def test_both_prompts_ban_calling_an_unlisted_race_a_qualifier(self):
        p = _prompts()
        assert "QUALIFICATION IS THE NOTICE OF RACE LIST" in p["digest"]
        assert "field guide's Notice of Race list and nothing else" in p["podcast"]

    def test_the_dashboard_record_agrees(self):
        d = json.loads(_read("site/data/offshore_north_dashboard.json"))
        rorc = next(c for c in d["countdowns"] if c["id"] == "rorc_2027")
        assert rorc["when"].startswith("2027-01-10") and rorc["emira_entered"] is True
        assert "not a Vendée Globe qualifier" in rorc["sub"]
        q = d["qualification"]
        assert any("Retour à la Base 2027" in line for line in q["outline"])
        assert any("RORC Transatlantic is not" in line for line in q["outline"])
        assert "Route du Rhum on 1 November 2026 is the first opportunity" not in q["ledger"][0]["status"]

    def test_the_next_milestone_is_the_race_emira_is_in(self):
        import datetime as dt

        from engine.offshore_north_status import campaign_status_from_files

        out = campaign_status_from_files(now=dt.datetime(2026, 11, 2, 12, tzinfo=dt.timezone.utc))
        assert "Next milestone on record: RORC Transatlantic Race start" in out


class TestTheRecordAndThePartner:
    def test_the_2023_record_names_its_boat(self):
        facts = _prompts()["standing_facts"]
        assert "set in January 2023 on the team's EARLIER IMOCA" in facts
        assert "not on EMIRA IV" in facts and "9 days, 12 hours and 26 minutes" in facts

    def test_alan_roberts_gets_one_line(self):
        facts = _prompts()["standing_facts"]
        assert "Fourth in The Ocean Race 2022–23 with Biotherm" in facts
        assert "nine seasons on the French Figaro solo circuit" in facts
        assert "A PARTNER OR CO-SKIPPER GETS ONE LINE" in _prompts()["digest"]

    def test_team_items_are_dated_without_a_copyable_date(self):
        p = _prompts()
        assert "DATE EVERY TEAM ITEM" in p["digest"]
        assert '"<channel>, <day> <month>:"' in p["digest"]
        # De-seed by shape: no specimen date the model could copy every week.
        assert "October twenty-third" not in p["podcast"]
        assert '"Canada Ocean Racing, 23 October:"' not in p["digest"]


class TestNoHostLines:
    def test_no_prompt_asks_for_one(self):
        for name, text in _prompts().items():
            if name == "standing_facts":
                continue
            assert "Dan's lens (writer-only" not in text, name
            assert "personal reference per episode" not in text, name
            assert "Boeing 737" not in text, name
            assert "flight planning" not in text, name

    def test_the_filter_removes_the_ep011_line_and_keeps_the_source(self):
        from engine.host_experience import strip_host_experience

        brief = ("Dan's lens: The RORC Transatlantic pairs weather-routing decisions across the "
                 "North Atlantic with the same pressure systems Dan reads from the flight deck. "
                 "Source: [sail-world.com](https://www.sail-world.com/news/301001/)\n")
        out, n = strip_host_experience(brief)
        assert n == 1
        assert out.strip() == "Source: [sail-world.com](https://www.sail-world.com/news/301001/)"
        script = ("Every mile counts.\n\nThe RORC Transatlantic pairs weather-routing decisions "
                  "with the same pressure systems I read from the flight deck.\n\nNow, the fleet.\n")
        out, n = strip_host_experience(script)
        assert n == 1 and "flight deck" not in out
        assert out == "Every mile counts.\n\nNow, the fleet.\n"

    def test_the_filter_leaves_ordinary_lines_alone(self):
        from engine.host_experience import strip_host_experience

        text = ("I had to look this up.\n\nThe autopilot steers more of the race than the skipper.\n\n"
                "Scott's Laser-sharp focus paid off.\n\nThe pilot boat met them at the harbour mouth.\n")
        assert strip_host_experience(text) == (text, 0)

    def test_every_host_line_in_the_archive_is_caught(self):
        """The replay: the lines the old prompts asked for, Ep001-Ep011."""
        from engine.host_experience import strip_host_experience

        caught = 0
        for path in sorted(ON.glob("Offshore_North_Ep0*_tts.txt")):
            caught += strip_host_experience(path.read_text(encoding="utf-8"))[1]
        assert caught >= 2  # Ep001's introduction, Ep006's wing foil (Ep011 corrected)

    def test_opt_in_and_wired(self):
        from engine.config import load_config

        assert load_config(ROOT / "shows" / "offshore_north.yaml").host_experience_filter is True
        assert load_config(ROOT / "shows" / "tesla.yaml").host_experience_filter is False
        src = _read("run_show.py")
        assert src.count('getattr(config, "host_experience_filter", False)') == 2


class TestPlainSailingMemory:
    def test_the_block_lists_the_aired_explainers_newest_first(self):
        from engine.offshore_north_status import recent_plain_sailing

        block = recent_plain_sailing(before_episode=11)
        lines = block.splitlines()
        assert lines[0].startswith("- 19 October 2026: An IMOCA skipper at sea never gets a full night's sleep")
        assert len(lines) == 8
        assert "26 October 2026" not in block  # the episode being written is not its own memory

    def test_both_prompts_carry_it_and_default_it(self):
        from engine.generator import load_prompt

        for rel in ("shows/prompts/offshore_north_digest.txt", "shows/prompts/offshore_north_podcast.txt"):
            text = load_prompt(str(ROOT / rel))
            keys = set(re.findall(r"(?<!\{)\{([a-z_]+)\}(?!\})", text))
            assert "recent_plain_sailing" in keys
            text.format_map({k: "" for k in keys})
        assert 'template_vars.setdefault("recent_plain_sailing", "")' in _read("run_show.py")
        assert 'pod_vars.setdefault("recent_plain_sailing", "")' in _read("engine/pipeline.py")
        assert 'ctx["recent_plain_sailing"] = recent_plain_sailing(before_episode=episode_num)' in _read(
            "shows/hooks/offshore_north.py")

    def test_padding_rules(self):
        p = _prompts()
        assert "NO PADDING" in p["digest"] and "NO PADDING" in p["podcast"]
        assert "Never describe a photo" in p["digest"]
        assert "Say each fact once" in p["digest"]
        # The thin-week rule no longer sends the writer to Plain Sailing.
        assert "If the brief is thin, DEEPEN Plain Sailing" not in p["podcast"]


class TestTheFleetChapter:
    def test_a_short_line_is_anchored_by_the_lines_after_it(self):
        from engine import story_breaks as sb

        script = (ON / "Offshore_North_Ep011_20261026_tts.txt").read_text(encoding="utf-8")
        tx = json.loads((ON / "Offshore_North_Ep011_20261026_transcript.json").read_text(encoding="utf-8"))
        lines = sb.script_lines(script)
        k = next(i for i, ln in enumerate(lines) if ln.strip() == "Now, the fleet.")
        anchors, unmatched = sb.boundary_anchors(script, [k], tx)
        assert unmatched == 0
        assert anchors[0][1] == pytest.approx(108.86, abs=0.05)

    def test_ep011_chapters_carry_it(self):
        d = json.loads((ON / "chapters_ep011.json").read_text(encoding="utf-8"))
        fleet = next(c for c in d["chapters"] if c["title"] == "The Fleet")
        assert fleet["startTime"] == 108.9

    def test_the_repair_tool_times_chapters_like_run_show(self):
        src = _read("scripts/resynthesize_episode.py")
        assert "config.audio.voice_intro_delay + config.audio.intro_duration" not in src
        assert "align_timestamps_to_transcript(" in src
        assert "published_episode_title(art.chapters_path)" in src


class TestEp011IsCorrected:
    def test_the_correction_is_filed(self):
        from engine.corrections import load_corrections

        entries = [c for c in load_corrections(ON) if c["episode"] == 11]
        assert entries and entries[0]["where"] == "both"

    def test_the_committed_text_no_longer_carries_the_errors(self):
        for suffix in (".md", "_tts.txt", "_reader.txt"):
            text = (ON / f"Offshore_North_Ep011_20261026{suffix}").read_text(encoding="utf-8")
            for bad in ("qualifying passage", "mascot", "flight deck", "Dan's lens",
                        "photo of Alan", "twenty-minute sleep"):
                assert bad not in text, (suffix, bad)
        md = (ON / "Offshore_North_Ep011_20261026.md").read_text(encoding="utf-8")
        assert "Canada Ocean Racing, 23 October:" in md
        assert "isn't a Vendée qualifier" in md
        assert "on the team's earlier IMOCA, not EMIRA IV" in md
