"""Lean rehearsals: one room, a room log, and no room on a refusing account (Oct 23 2026).

Thirty-four rehearsal rooms in two days (about 870 Voice Agent minutes) found
four real faults in Mira's room, and each was read from a room's own trace and
Mira's words, never from the two-arm medians: one configuration's guest words
per answer ran 31 to 84 across rooms, and Mira's median turn sat at 4-5 s in
every fixture room. The morning of Oct 23 then placed four rooms and two
probes on an account that was out of credit. So a rehearsal now checks xAI
first, places one room of the proposed arm by default, stops after a refused
room, and reports each room's log: the sessions, the closing round line by
line, and when her words carried each question the room handed her.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
PIPELINES = ROOT / "pipelines" / "voices"
WORKFLOW = ROOT / ".github" / "workflows" / "nerra_voices_rehearsal.yml"
SCENARIO = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"

if str(PIPELINES) not in sys.path:
    sys.path.insert(0, str(PIPELINES))

import audio_metrics as am  # noqa: E402


@pytest.fixture(scope="module")
def rehearsal():
    spec = importlib.util.spec_from_file_location("rehearsal_lean", PIPELINES / "rehearsal.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _trace(lines, start="2026-10-23T09:00:00"):
    """[(seconds, kind, detail)] -> trace events on a fixed clock."""
    import datetime as dt
    t0 = dt.datetime.fromisoformat(start)
    return [{"t": (t0 + dt.timedelta(seconds=s)).isoformat() + "Z", "e": e, "d": d}
            for s, e, d in lines]


def _clock(sec):
    return f"[{int(sec) // 60:02d}:{int(sec) % 60:02d}]"


# The closing round as rehearsal 0ac88c67 traced it (timings kept, guest words
# left out): the room handed each question on time, her words ran one behind,
# and the room's only record of that was three "said late" lines.
LAGGING_ROUND = [
    (0, "room", "opened (webrtc); mixer via sendMediaBetween"),
    (1, "grok", "agent created (model grok-voice-3.0)"),
    (240, "grok", "response done"),
    (903, "round", "room-driven closing round begins (the answer in progress ended)"),
    (903, "round", "asked 1/7: the show's own question"),
    (930, "round", "answered 1/7"),
    (930, "round", "asked 2/7: a book they would recommend"),
    (944, "round", "answered 2/7"),
    (944, "round", "asked 3/7: who you should interview next"),
    (959, "round", "answered 3/7"),
    (959, "round", "asked 4/7: the best advice they were ever given"),
    (961, "round", "said late: who you should interview next"),
    (973, "round", "answered 4/7"),
    (973, "round", "asked 5/7: who has inspired them most"),
    (975, "round", "said late: the best advice they were ever given"),
    (998, "round", "answered 5/7"),
    (998, "round", "asked 6/7: how being interviewed by an AI was, and one improvement"),
    (999, "round", "said late: who has inspired them most"),
    (1014, "round", "answered 6/7"),
    (1014, "round", "asked 7/7: whether they would like a follow-up interview"),
    (1044, "round", "answered 7/7"),
    (1044, "round", "every closing question asked; handing them the last word"),
    (1079, "round", "complete; closing thanks"),
    (1320, "room", "ending: normal"),
]


class TestTheRoundMetricReadsTheLag:
    def test_said_late_is_not_a_complete_round(self):
        out = am.closing_round(_trace(LAGGING_ROUND))
        assert out["round_asked"] == 7 and out["round_answered"] == 7
        assert out["round_late"] == 3
        assert out["closing_round_complete"] is False

    def test_asked_again_is_a_repeat_not_another_question(self):
        # Run 4729e7b6's shape: eight questions, five "asked again" lines.
        lines = [(0, "room", "opened")]
        t = 10
        for n, label in enumerate(["a", "b", "c", "d", "e", "f", "g", "h"], start=1):
            lines += [(t, "round", f"asked {n}/8: {label}")]
            if n > 1 and n <= 6:
                lines += [(t + 1, "round", f"asked again: {chr(ord(label) - 1)} (first at 15 min)")]
            lines += [(t + 5, "round", f"answered {n}/8")]
            t += 10
        out = am.closing_round(_trace(lines))
        assert out["round_asked"] == 8 and out["round_repeats"] == 5
        assert out["round_stacked"] == 0
        assert out["closing_round_complete"] is False

    def test_a_question_handed_again_counts_once(self):
        lines = [(0, "round", "asked 1/2: a"),
                 (5, "round", "her turn asked nothing; a goes again when they finish"),
                 (9, "round", "they finished their thought; handing 1/2 again"),
                 (9, "round", "asked 1/2: a"), (15, "round", "answered 1/2"),
                 (16, "round", "asked 2/2: b (her own words)"), (20, "round", "answered 2/2")]
        out = am.closing_round(_trace(lines), expected=2)
        assert out["round_asked"] == 2 and out["round_stacked"] == 0
        assert out["round_rehanded"] == 1
        assert out["closing_round_complete"] is True

    def test_a_question_she_asked_herself_counts(self):
        lines = [(0, "round", "asked on her own: a"), (5, "round", "asked 2/2: b"),
                 (9, "round", "answered 2/2")]
        out = am.closing_round(_trace(lines), expected=2)
        assert out["round_asked"] == 2 and out["closing_round_complete"] is True


    def test_the_room_count_wins_over_the_callers(self):
        # Oct 23 2026: the round went from eight questions to seven. A room
        # that asked all seven is complete whatever count a caller passed.
        lines = []
        for n in range(1, 8):
            lines += [(n * 10, "round", f"asked {n}/7: q{n}"), (n * 10 + 5, "round", f"answered {n}/7")]
        assert am.closing_round(_trace(lines), expected=8)["closing_round_complete"] is True
        assert am.closing_round(_trace(lines[:-2]), expected=6)["closing_round_complete"] is False

    def test_a_question_never_heard_is_handed_again_not_stacked(self):
        lines = [(0, "round", "asked 6/7: f"),
                 (3, "close", "cancelled mid-sentence: a sign-off with the closing round at 6/7"),
                 (9, "round", "they spoke, but f never reached them; handing 6/7 again"),
                 (9, "round", "asked 6/7: f"), (15, "round", "answered 6/7")]
        out = am.closing_round(_trace(lines), expected=1)
        assert out["round_stacked"] == 0 and out["round_rehanded"] == 1
        assert out["round_asked"] == 1 and out["round_answered"] == 1


class TestTheRoomLog:
    def test_the_report_and_the_room_name_the_same_questions(self, rehearsal):
        labels = [q for q, _ in rehearsal.round_questions()]
        src = SCENARIO.read_text(encoding="utf-8")
        block = src[src.index("const ROUND_QUESTIONS = ["):]
        block = block[:block.index("];")]
        assert len(labels) == 7 and all(f'"{q}"' in block for q in labels)

    def test_the_wider_pattern_hears_how_she_asks(self, rehearsal):
        rx = dict(rehearsal.round_questions())
        assert rx["whether they would like a follow-up interview"].search("Would you do this again?")
        assert rx["who you should interview next"].search("Who should I interview next?")
        assert rx["a book they would recommend"].search("Is there a book you'd recommend?")

    def test_each_question_handed_and_heard(self, rehearsal):
        # Her words a turn behind, a sentence split across Whisper segments,
        # and two questions never put to the guest.
        mira = [
            (946, "Who should I interview"), (962, "next? What's the best advice you were ever given?"),
            (1000, "Who's inspired you most? Would you do"), (1017, "this again? Thank you."),
        ]
        transcript = "\n".join(f"{_clock(s)} Mira: {t}" for s, t in mira)
        log = rehearsal.room_log(_trace(LAGGING_ROUND), transcript)
        q = {x["question"]: x for x in log["questions"]}
        assert q["a book they would recommend"]["never_heard"]
        assert q["how being interviewed by an AI was, and one improvement"]["never_heard"]
        assert q["who you should interview next"]["heard_at"] == "15:46"
        assert q["who has inspired them most"]["late"] is True
        assert log["round"]["round_late"] == 3
        assert log["length_min"] == 22.0
        assert [x["line"] for x in log["round_lines"]][1] == "asked 1/7: the show's own question"

    def test_the_sessions_and_turns_are_counted(self, rehearsal):
        tr = _trace([(0, "room", "opened"), (1, "grok", "agent created (model grok-voice-3.0)"),
                     (60, "grok", "connection dropped code 1006 (No close code frame has been received)"),
                     (62, "grok", "rescued after a dropped connection — session 2 is live"),
                     (70, "turn", "server turn after guest speech cancelled; the room decides it (#1)"),
                     (80, "turn", "dead air after her line; nudge 1"),
                     (90, "hold", "entered: she said she would wait"),
                     (150, "hold", "left: they turned back to her after 60s"),
                     (200, "room", "ending: normal")])
        log = rehearsal.room_log(tr)
        assert log["sessions"] == {"started": 2, "refused": 0, "rescued": 1, "gave_up": False}
        assert log["turns"]["server_turns_rerouted"] == 1 and log["turns"]["dead_air_nudges"] == 1
        assert log["holds"]["entered"] == 1 and log["holds"]["left"] == 1
        assert log["ending"] == "normal"


# The four rooms of run 39935894461: every session refused at start.
REFUSED = [
    (0, "room", "opened (webrtc); mixer via sendMediaBetween"),
    (1, "grok", "agent created (model grok-voice-3.0)"),
    (1, "grok", "connection dropped code 1011 (Internal server error while operating) — 93ms "
                "after startup, so xAI refused the session (model grok-voice-3.0)"),
    (2, "grok", "rescued after a dropped connection — session 2 is live with the conversation so far (0 lines)"),
    (2, "grok", "connection dropped code 1011 (Internal server error while operating) — 281ms "
                "after startup, so xAI refused the session (model grok-voice-3.0)"),
    (4, "leg", "guest #1 left: disconnected (0 in room)"),
    (49, "room", "ending: normal"),
]


class TestNoRoomOnARefusingAccount:
    def test_a_refused_room_is_recognised(self, rehearsal):
        assert rehearsal.room_refused(_trace(REFUSED)) is True
        assert rehearsal.room_refused(_trace(LAGGING_ROUND)) is False
        # A drop mid-room that was rescued is not a refused room.
        mid = LAGGING_ROUND[:3] + [(300, "grok", "connection dropped code 1006 — so xAI refused the session")]
        assert rehearsal.room_refused(_trace(mid)) is False

    def test_the_run_stops_after_a_refused_room(self, rehearsal, monkeypatch, tmp_path):
        started = []
        monkeypatch.setattr(rehearsal, "ensure_rehearsal_interview",
                            lambda f, m: {"interview": {"id": "i"}})
        monkeypatch.setattr(rehearsal, "build_run_row", lambda **kw: {})
        monkeypatch.setattr(rehearsal, "create_run",
                            lambda row: {"id": f"run-{len(started)}"})
        monkeypatch.setattr(rehearsal, "fixture_persona", lambda f: "persona")
        monkeypatch.setattr(rehearsal, "start_fixture", lambda rid, *a, **k: started.append(rid))
        monkeypatch.setattr(rehearsal, "wait_for_room", lambda rid, m: {
            "id": "00000000-0000-0000-0000-000000000001", "scenario_trace": _trace(REFUSED),
            "planned_minutes": 12})
        monkeypatch.setattr(rehearsal, "proposed_prompt", lambda f: "prompt")
        measured = []
        monkeypatch.setattr(rehearsal, "measure_and_write", lambda **kw: measured.append(kw))
        code = rehearsal.main(["run", "--arm", "proposed", "--fixture", "roddy",
                               "--repeat", "3", "--out-dir", str(tmp_path)])
        assert code == 3 and len(started) == 1 and measured == []
        rec = json.loads(next(tmp_path.glob("*.json")).read_text())
        assert rec["refused"] is True
        result = rehearsal.single_arm_verdict(rehearsal.load_records(tmp_path))
        assert result["result"] == "FAIL"
        assert "refused" in result["rooms"][0]["checks"][0]["detail"]

    def test_preflight_stops_on_credit_and_goes_ahead_otherwise(self, rehearsal):
        class R:
            def __init__(self, code, text=""):
                self.status_code, self.text = code, text

        credit = ('{"code":"permission-denied","error":"Your team has either used all available '
                  'credits or reached its monthly spending limit."}')
        out = rehearsal.xai_preflight("k", post=lambda *a, **k: R(403, credit))
        assert out["ok"] is False and "credit" in out["why"]
        assert rehearsal.xai_preflight("k", post=lambda *a, **k: R(429, credit))["ok"] is False
        assert rehearsal.xai_preflight("k", post=lambda *a, **k: R(200, "{}"))["ok"] is True
        assert rehearsal.xai_preflight("k", post=lambda *a, **k: R(503, "busy"))["ok"] is True
        assert rehearsal.xai_preflight("k", post=lambda *a, **k: R(429, "slow down"))["ok"] is True

        def boom(*a, **k):
            raise OSError("no route")
        assert rehearsal.xai_preflight("k", post=boom)["ok"] is True
        assert rehearsal.xai_preflight("")["checked"] is False


def _room(**over):
    rec = {"arm": "proposed", "fixture": "roddy", "run_id": "r1", "planned_minutes": 12,
           "listen_url": "https://x/room",
           "metrics": {"self_answered_turns": 0, "overlap_events": 0,
                       "closing_round_complete": True},
           "room_log": {"length_min": 12.4, "sessions": {"started": 1, "refused": 0,
                                                         "rescued": 0, "gave_up": False},
                        "round": {"round_asked": 8, "round_answered": 8, "round_late": 0,
                                  "round_repeats": 0, "closing_round_complete": True},
                        "questions": [{"question": "a book they would recommend",
                                       "handed_at": "08:10", "heard_at": "08:11",
                                       "late": False, "never_heard": False}]}}
    for k, v in over.items():
        rec[k] = v
    return rec


class TestOneRoomIsJudgedOnItsOwnChecks:
    def test_a_clean_room_passes(self, rehearsal):
        assert rehearsal.single_arm_verdict([_room()])["result"] == "PASS"

    def test_a_lost_question_fails(self, rehearsal):
        r = _room()
        r["room_log"]["questions"][0].update(heard_at=None, never_heard=True)
        result = rehearsal.single_arm_verdict([r])
        assert result["result"] == "FAIL"
        rnd = next(c for c in result["rooms"][0]["checks"] if c["check"] == "closing round")
        assert "never in her words: a book they would recommend" in rnd["detail"]

    def test_a_self_answered_turn_or_talking_over_fails(self, rehearsal):
        for m in ({"self_answered_turns": 1}, {"overlap_events": 3}):
            r = _room()
            r["metrics"].update(m)
            assert rehearsal.single_arm_verdict([r])["result"] == "FAIL"

    def test_a_short_room_or_an_unreached_round_is_not_a_pass(self, rehearsal):
        short = _room()
        short["room_log"]["length_min"] = 3.0
        assert rehearsal.single_arm_verdict([short])["result"] == "FAIL"
        early = _room()
        early["room_log"]["round"] = {"round_asked": 0}
        assert rehearsal.single_arm_verdict([early])["result"] == "INCONCLUSIVE"
        assert rehearsal.single_arm_verdict([])["result"] == "INCONCLUSIVE"

    def test_the_report_prints_the_room_and_what_it_cost(self, rehearsal, tmp_path):
        (tmp_path / "proposed_roddy_1_r1.json").write_text(json.dumps(_room()), encoding="utf-8")
        records = rehearsal.load_records(tmp_path)
        result = rehearsal.single_arm_verdict(records)
        md = rehearsal.report_markdown(rehearsal.summarise(records), result, records)
        assert "**PASS**" in md and "Listen: https://x/room" in md
        assert "| a book they would recommend | 08:10 | 08:11 |" in md
        assert "Voice Agent minutes" in md and "listened" in md
        assert rehearsal.main(["report", str(tmp_path)]) == 0

    def test_two_arms_still_get_the_comparison(self, rehearsal, tmp_path):
        for arm in ("proposed", "current"):
            (tmp_path / f"{arm}.json").write_text(json.dumps(_room(arm=arm)), encoding="utf-8")
        records = rehearsal.load_records(tmp_path)
        summary = rehearsal.summarise(records)
        assert {"proposed", "current"} <= set(summary)
        assert rehearsal.verdict(summary)["checks"]


class TestTheWorkflowDefaultsToOneRoom:
    def _wf(self):
        wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        return wf[True] if True in wf else wf["on"]

    def test_defaults(self):
        inputs = self._wf()["workflow_dispatch"]["inputs"]
        assert inputs["minutes"]["default"] == 15
        assert inputs["repeat"]["default"] == 1
        assert inputs["arms"]["default"] == "proposed"
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "inputs.minutes || 15" in text and "inputs.repeat || 1" in text
        assert "inputs.arms || 'proposed'" in text

    def test_xai_is_checked_before_anything_is_uploaded_or_placed(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        pre = text.index("rehearsal.py preflight")
        assert pre < text.index("upload_candidate_scenario()")
        assert pre < text.index("--arm current") and pre < text.index("--arm proposed")

    def test_the_default_room_reaches_the_closing_round(self, rehearsal):
        # The first "12-minute" test room never opened the round: the room
        # reads a planned length under 15 as its 45-minute default.
        src = SCENARIO.read_text(encoding="utf-8")
        assert "asked < 15 || asked > 90) return DEFAULT_PLANNED_MIN" in src
        assert rehearsal.ROOM_MIN_MINUTES == 15
        inputs = self._wf()["workflow_dispatch"]["inputs"]
        assert inputs["minutes"]["default"] >= rehearsal.ROOM_MIN_MINUTES
