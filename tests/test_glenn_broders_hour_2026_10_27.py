"""What Glenn Broder's episode (Oct 27 2026, run d0cdb835) taught.

The conversation was good; the production around it was not:

1. The cold open was the wrong clip. The auto edit meant his line at 16:00.9
   and wrote 1600.9 seconds, so the episode opened on "...of school
   districts" from 26:40. Times are now checked against the words the clip
   quotes, and a number past the end of the room is read as minutes and
   seconds.
2. The close sent listeners to humanjudgment.ai, which is not his: a
   narration may name only the guest's own addresses.
3. The transcript he was asked to approve had Mira cutting him off
   mid-sentence in 21 of her 37 turns; the call recording shows she waited
   four seconds every time. Whisper segments ran across her turns. They are
   now split at the guest's pauses before the speakers are merged, and
   mishearings ("Tell Moodic logic", "jungle gem", "Jensen Wang") are
   corrected as checked, one-for-one replacements.
4. The chapters were on the room's clock and would have been published up
   to three minutes late. The assembler records the clock it builds.
5. The launch copy's "Listen here" pointed at his LinkedIn profile.
6. "I have to go" was heard in "the tests that we need to run when...", and
   the room stopped holding the closing round open at 14 minutes.
7. The show's own closing question, promised in his prep email, was taken
   as asked without being asked.
8. Nearly every turn of hers opened on a few words summing up his answer;
   nothing measured it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT))
SCENARIO_PATH = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
SCENARIO = SCENARIO_PATH.read_text(encoding="utf-8")
SIM = ROOT / "tests" / "fixtures" / "room_sim.js"

TRANSCRIPT = """[15:55] Glenn: hired for a position to be able to make those kinds of decisions. The AI just
[16:01] Glenn: saved them a ton of time. They have to be willing to sign their name to the
[16:07] Glenn: final product. If they understand that that is their responsibility, that's
[16:14] Glenn: where they keep the control and the human judgment.
[16:22] Mira: Signing the name is where accountability becomes physical.
[26:36] Glenn: I spend half of the day on the phone with CEOs and half of the day with superintendents
[26:43] Glenn: of school districts.
[52:24] Mira: That's the end of the recording. You can hang up now.
"""


# 1. The cold open lands on its words --------------------------------------

class TestTheColdOpen:
    def test_minutes_and_seconds_read_as_seconds_are_caught(self):
        import auto_edit as ae
        out = ae.on_the_room_clock({"cold_open": {
            "from_sec": 1600.9, "to_sec": 1614.3, "lead": "x",
            "quote": "They have to be willing to sign their name to the final product"}},
            TRANSCRIPT)
        assert round(out["cold_open"]["from_sec"], 1) == 960.9
        assert round(out["cold_open"]["to_sec"], 1) == 974.3

    def test_a_stamp_is_accepted_as_written(self):
        import auto_edit as ae
        out = ae.on_the_room_clock({"start_sec": "00:44", "end_sec": "52:16",
                                    "drop": [{"from_sec": "10:00", "to_sec": "10:30"}],
                                    "cold_open": None}, TRANSCRIPT)
        assert out["start_sec"] == 44 and out["end_sec"] == 3136
        assert out["drop"][0]["from_sec"] == 600

    def test_words_that_are_not_in_the_tape_mean_no_cold_open(self):
        import auto_edit as ae
        out = ae.on_the_room_clock({"cold_open": {
            "from_sec": 960, "to_sec": 974, "lead": "x",
            "quote": "words nobody ever said in this room at all"}}, TRANSCRIPT)
        assert out["cold_open"] is None

    def test_the_prompt_asks_for_the_words(self):
        prompt = (V / "prompts" / "auto_edit.txt").read_text(encoding="utf-8")
        assert '"quote": "the clip\'s words, verbatim"' in prompt
        assert "[16:04] is 964 seconds" in prompt

    def test_the_slug_is_the_day_it_was_recorded(self):
        import auto_edit as ae
        when = ae.recorded_on({"created_at": "2026-10-26 18:02:59+00",
                               "guest_joined_at": "2026-10-27 17:57:07+00"}, {})
        assert str(when) == "2026-10-27"


# 2. Only their own addresses ------------------------------------------------

class TestOnlyTheirAddresses:
    APP = {"name": "Glenn Broder", "links": {"raw": "https://www.linkedin.com/in/glennbroder/"}}

    def test_an_invented_site_becomes_their_profile(self):
        import auto_edit as ae
        text = ("My thanks to Glenn. You can find his work at humanjudgment.ai. "
                "The Nerra Network at nerranetwork.com is where this show lives.")
        out = ae.only_their_domains(text, self.APP)
        assert "humanjudgment" not in out
        assert "You can find Glenn on LinkedIn; the link is in the episode notes." in out
        assert "nerranetwork.com" in out

    def test_a_spoken_address_is_caught_too(self):
        import auto_edit as ae
        out = ae.only_their_domains("Find him at human judgment dot ai.", self.APP)
        assert "dot ai" not in out

    def test_their_own_site_stays(self):
        import auto_edit as ae
        app = {"name": "Piper Martz", "links": {"raw": "https://tablestakesmedia.com"}}
        text = "You can find her work at tablestakesmedia.com."
        assert ae.only_their_domains(text, app) == text

    def test_no_links_no_address(self):
        import auto_edit as ae
        assert ae.only_their_domains("You can find him at glenn.ai.", {"name": "G"}) == ""


# 3. The transcript says who spoke when ----------------------------------------

class TestTheTranscript:
    def test_a_segment_is_split_where_the_speaker_stopped(self):
        from post_interview import split_on_pauses
        seg = {"start": 71.0, "text": "x", "words": [
            {"start": 71.0, "end": 71.4, "word": " I"},
            {"start": 71.4, "end": 71.9, "word": " was"},
            {"start": 72.0, "end": 72.6, "word": " hooked."},
            {"start": 86.5, "end": 87.0, "word": " The"},
            {"start": 87.0, "end": 87.6, "word": " governments"}]}
        assert split_on_pauses(seg) == [(71.0, "I was hooked."), (86.5, "The governments")]

    def test_stubs_rejoin_their_sentence(self):
        from post_interview import tidy_lines
        lines = [(112.0, "Glenn", "Well, I"), (112.5, "Glenn", "actually started to get involved."),
                 (2612.0, "Glenn", "If"), (2617.0, "Mira", "Practical over theoretical. Who next?"),
                 (2625.0, "Glenn", "I could interview anybody."),
                 (2630.0, "Glenn", "He sees it clearly.")]
        assert tidy_lines(lines) == [
            (112.0, "Glenn", "Well, I actually started to get involved."),
            (2617.0, "Mira", "Practical over theoretical. Who next?"),
            (2625.0, "Glenn", "If I could interview anybody."),
            (2630.0, "Glenn", "He sees it clearly.")]

    def test_a_segment_without_words_stays_whole(self):
        from post_interview import split_on_pauses
        assert split_on_pauses({"start": 3.0, "text": " Hello. "}) == [(3.0, "Hello.")]

    def test_known_mishearings_and_their_own_names(self):
        from terms import glossary_from_app, known_fixes
        app = {"organization": "Human Judgment in the Age of AI",
               "bio": "My work includes Human Judgment in the Age of AI and Learn AI Like a Pro."}
        text = ("[07:08] Glenn: a cognitive jungle gem, human judgment in the age of AI, "
                "learn AI like a pro, open AI and Jensen Wang\n"
                "[35:48] Mira: Tell Moodic logic as the operating system.")
        fixed, _ = known_fixes(text, glossary_from_app(app))
        assert "jungle gym" in fixed and "Human Judgment in the Age of AI" in fixed
        assert "Learn AI Like a Pro" in fixed and "OpenAI" in fixed and "Jensen Huang" in fixed
        assert "[35:48] Mira: Talmudic logic" in fixed

    def test_the_model_lists_fixes_and_only_safe_ones_apply(self):
        from terms import apply_fixes, vet_fixes
        text = "[36:46] Glenn: it's the anecdote for the problems. So our matrix at this point are practical."
        fixes = vet_fixes(text, [
            {"heard": "the anecdote for", "meant": "the antidote for"},
            {"heard": "our matrix", "meant": "our metrics"},
            {"heard": "So our matrix at this point are practical", "meant": "Our metrics are practical"},
            {"heard": "not in the text", "meant": "anything"},
            {"heard": "practical", "meant": "useless"}])
        assert fixes == [("the anecdote for", "the antidote for"), ("our matrix", "our metrics")]
        assert apply_fixes(text, fixes).startswith("[36:46] Glenn: it's the antidote for the problems. So our metrics")

    def test_the_corrections_run_before_anyone_reads_it(self):
        src = (V / "post_interview.py").read_text(encoding="utf-8")
        assert src.index('strip_echo_lines(transcript, "Mira")') < src.index("correct_transcript(transcript, app, show)")


# 4. Chapters on the published file's clock ------------------------------------

def _write(path: Path, x: np.ndarray, sr: int = 48000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


class TestTheEditClock:
    def test_close_gaps_says_what_it_took_out(self, tmp_path):
        import assemble_edit as ae
        sr = 48000
        word = 0.3 * np.sin(np.linspace(0, 2 * np.pi * 220 * 0.5, int(0.5 * sr)))
        x = np.concatenate([word, np.zeros(int(3.0 * sr)), word, np.zeros(int(2.0 * sr)), word])
        f = tmp_path / "p.wav"
        _write(f, x)
        out = ae.close_gaps(f)
        removed = sum(b - a for a, b in out["removed"])
        assert out["closed"] == 2 and abs(removed - out["removed_sec"]) < 0.01

    def test_a_moment_of_the_room_lands_where_it_is_in_the_edit(self):
        from edit_transcript import edit_clock, room_to_edit
        cuts = [{"from": "narration:intro"}, {"gap": 0.5},
                {"from": "mix:clean", "start": 100.0, "end": 400.0, "_gaps_removed": [[10.0, 15.0], [50.0, 60.0]]}]
        clock = edit_clock(cuts, [30.0, 0.5, 285.0])
        assert room_to_edit(clock, 105.0) == pytest.approx(35.5)        # before any gap
        assert room_to_edit(clock, 140.0) == pytest.approx(65.5)        # after the first
        assert room_to_edit(clock, 200.0) == pytest.approx(115.5)       # after both
        assert room_to_edit(clock, 112.0) == pytest.approx(40.5)        # in a closed silence

    def test_a_cold_open_clip_never_captures_a_chapter(self):
        from edit_transcript import edit_clock, room_to_edit
        cuts = [{"from": "track:guest", "start": 964.0, "end": 979.0, "gaps": False},
                {"from": "mix:clean", "start": 44.6, "end": 3000.0, "_gaps_removed": []}]
        clock = edit_clock(cuts, [15.0, 2955.4])
        assert room_to_edit(clock, 970.0) == pytest.approx(15.0 + 970.0 - 44.6)

    def test_chapters_move_and_the_first_starts_the_episode(self):
        from edit_transcript import chapters_on_edit_clock, edit_clock
        cuts = [{"from": "narration:intro"},
                {"from": "mix:clean", "start": 44.6, "end": 3000.0, "_gaps_removed": [[100.0, 160.0]]}]
        clock = edit_clock(cuts, [50.0, 2895.4])
        out = chapters_on_edit_clock([{"start": 0, "title": "a"}, {"start": 122, "title": "b"},
                                      {"start": 1921, "title": "c"}], clock)
        assert [c["start"] for c in out] == [0, round(50 + 122 - 44.6), round(50 + 1921 - 44.6 - 60)]
        assert out[0]["end"] == out[1]["start"]

    def test_the_edit_transcript_is_placed_exactly_when_it_can_be(self):
        from edit_transcript import transcript_of_the_edit
        cuts = [{"from": "mix:clean", "start": 0.0, "end": 100.0, "_gaps_removed": [[10.0, 40.0]]}]
        text = transcript_of_the_edit("[00:05] Glenn: a\n[00:50] Mira: b\n", cuts, [70.0])
        assert "[00:20] Mira: b" in text

    def test_the_chapter_pass_gives_stamps(self):
        from edit_transcript import normalise_chapters
        out = normalise_chapters([{"start": "00:00", "title": "a"}, {"start": "[16:04]", "title": "b"},
                                  {"start": 3500, "title": "c"}], TRANSCRIPT)
        assert [c["start"] for c in out] == [0, 964, 2100]
        prompt = (V / "prompts" / "editorial_passes" / "02_chapter_markers.txt").read_text(encoding="utf-8")
        assert '"start": "MM:SS"' in prompt and "never converted to seconds" in prompt

    def test_publish_and_refresh_use_the_edit_clock(self):
        src = (V / "publish_episode.py").read_text(encoding="utf-8")
        assert src.count("on_the_edit_clock(pkg,") == 2
        assembled = (V / "assemble_edit.py").read_text(encoding="utf-8")
        assert '"clock": clock,' in assembled and 'cut["_gaps_removed"]' in assembled


# 5. The launch copy links the episode -----------------------------------------

class TestLaunchCopy:
    def test_the_listen_link_is_the_episode(self):
        from validators.schema_validators import validate_pass_output
        with pytest.raises(ValueError):
            validate_pass_output("social_copy", {"twitter": "t {episode_url}", "instagram": "i",
                                                 "linkedin": "Listen here: https://www.linkedin.com/in/glennbroder"})

    def test_publish_fills_it_in(self, monkeypatch):
        import publish_episode as pe
        seen = {}
        monkeypatch.setattr(pe, "sb_update", lambda table, where, row: seen.update(row))
        pe.fill_social_links({"id": "p", "social_copy": {"linkedin": "Listen: {episode_url}", "instagram": "x"}},
                             "https://nerranetwork.com/e/1")
        assert seen["social_copy"]["linkedin"] == "Listen: https://nerranetwork.com/e/1"


# 6, 7. The room ----------------------------------------------------------------

def _phrases(lines):
    env = dict(os.environ, ROOM_SIM_PHRASES=json.dumps(lines))
    res = subprocess.run(["node", str(SIM), str(SCENARIO_PATH), "phrases"],
                         capture_output=True, text=True, check=True, env=env)
    return [p["stop"] for p in json.loads(res.stdout)["phrases"]]


class TestTheRoom:
    def test_a_sentence_that_carries_on_is_not_a_goodbye(self):
        assert _phrases([
            "We're learning about all the tests that we need to run when we're actually working with clients.",
            "We have to stop thinking that way.",
            "I have to go back to the point I made.",
        ]) == [False, False, False]

    def test_a_real_goodbye_still_is(self):
        assert _phrases([
            "I'm so sorry, I have to go now, something has come up.",
            "I need to run.",
            "We need to wrap up in five minutes.",
            "Can we stop here?",
        ]) == [True, True, True, True]

    def test_the_shows_own_question_gets_a_second_chance_and_no_reaction_first(self):
        assert 'const ROUND_REHANDS_MAX_FOR = { "the show\'s own question": 2 };' in SCENARIO
        assert 'const leadIn = roundLeadIn || (rehand ? REHAND_LEAD_IN : "");' in SCENARIO
        assert "Say nothing before it" in SCENARIO


# 8. The habit is measured ---------------------------------------------------------

class TestLabelOpeners:
    def test_measured(self):
        import audio_metrics as am
        turns = [{"words": ["Deadwood", "showing", "itself.", "Where", "does", "that", "leave", "them?"]},
                 {"words": ["Collective", "fattening.", "Who", "inspired", "you", "most?"]},
                 {"words": ["What", "pulled", "you", "in?"]},
                 {"words": ["Hello,", "Glenn.", "How", "are", "you?"]}]
        assert am.label_open_rate(turns) == 0.5

    def test_the_grader_is_told(self):
        retro = (V / "prompts" / "editorial_passes" / "09_interview_retro.txt").read_text(encoding="utf-8")
        assert "label_open_rate" in retro


class TestThankYouQuotes:
    def test_a_line_that_stalls_or_points_at_nothing_is_not_quoted(self):
        import guest_thanks as gt
        assert gt._score("If they are lazy, that could be part of the deadwood part of the scenario, "
                         "meaning the deadwood and I want to define that.") == 0
        assert gt._score("And we were taught that on a day in and day out basis and I think it I don't "
                         "know if it's the greatest word but it is the antidote.") == 0
        assert gt._score("They have to be willing to sign their name to the final product "
                         "and own every decision they make.") > 0


def test_one_segment_can_be_voiced_again():
    wf = (ROOT / ".github" / "workflows" / "nerra_voices_narrate.yml").read_text(encoding="utf-8")
    assert "NARRATION_SEGMENTS: ${{ inputs.segments }}" in wf


def test_the_scenario_parses():
    subprocess.run(["node", "--check", str(SCENARIO_PATH)], check=True)
