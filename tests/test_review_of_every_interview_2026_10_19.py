"""Oct 19 2026, Patrick, after Cory O'Daniel: make sure the fixes improve the
interviews as a whole and are not just a reaction to one of them.

Eleven graded interviews, read together. Overall averages 5.0 of 10 and has
not risen: 4, 5, 7, 7, 2, 4, 7, 6, 6, 5, 2. Pacing (4.9) and warmth (5.4,
never above 7) are the weakest grades. What the tapes and traces show:

* Every guest complaint about the experience is about rhythm, not research:
  Jason Fishman "it feels like I'm talking to an answering machine", Thor
  Hesselberg "not as personal", Scott Pulcini "came a little too quick",
  Cory O'Daniel "it doesn't feel like a conversation". The standing lessons
  had drifted the other way: "acknowledge with at most one neutral word or
  nothing" outranked the prompt's own warmth.
* The lightning round, ten questions back to back, is where the
  answering-machine line was said and where questions got stacked.
* Several of the worst moments were the room, not Mira. One sign-off fired
  two rescues two seconds apart (Fishman, Piper Martz Oct 13: three
  sign-offs). The opening fired a turn on top of the server's own answer to
  the guest's hello (Piper Oct 13, Cory). And miraSpeaking was only ever set
  for turns the room asked for, so an ordinary turn was never cancelled when
  the guest cut in: at most two yields an hour against up to ten
  interruptions, and she believed she had asked what nobody heard.
* At the lesson cap the loop retired the OLDEST lesson by date, which would
  next have been "Do not re-ask a question", broken twice and still live.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "pipelines" / "voices"
if str(V) not in sys.path:
    sys.path.insert(0, str(V))

PROMPT = (V / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
RETRO = (V / "prompts" / "editorial_passes" / "09_interview_retro.txt").read_text(encoding="utf-8")
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _jsfn(name: str, src: str = SCENARIO) -> str:
    start = src.index(f"function {name}(")
    nxt = re.search(r"\n(?:async )?function |\n// -{10,}", src[start + 10:])
    return src[start: start + 10 + (nxt.start() if nxt else len(src))]


class TestThePromptTeachesRhythm:
    def test_what_guests_have_told_us_is_in_her_prompt(self):
        flat = _flat(PROMPT)
        assert "WHAT GUESTS HAVE TOLD US" in flat
        for said in ("answering machine", "not as personal", "came a little too quick",
                     "it doesn't feel like a conversation"):
            assert said in flat, said
        assert "give it one specific, human beat in plain words" in flat
        assert "Never grade the answer and never summarise it back" in flat

    def test_a_short_answer_needs_no_acknowledgment_but_a_real_one_does(self):
        flat = _flat(PROMPT)
        assert "Most answers need no acknowledgment" not in flat
        assert "A short answer needs no acknowledgment" in flat
        # The ban on grading stays.
        assert "Do not grade an answer with an adjective at all" in flat

    def test_the_lightning_round_reacts_between_questions(self):
        flat = _flat(PROMPT)
        assert "Each question is its own turn: ask it, stop, and let them answer in full" in flat
        assert "react to what they actually said in a few words that prove you heard it" in flat
        assert "never stack two into one turn" in flat
        assert "Never answer one yourself" in flat

    def test_a_complaint_is_taken_on_board_not_explained_back(self):
        flat = _flat(PROMPT)
        assert "never explain their complaint back to them" in flat

    def test_the_change_of_course_line_is_not_a_banned_phrase(self):
        # "Fair enough" is on her retired list; "Fair." was its echo.
        assert '("Fair.")' not in PROMPT
        assert "Okay, let's leave that one." in PROMPT

    def test_no_em_dash_in_what_was_added(self):
        start = PROMPT.index("WHAT GUESTS HAVE TOLD US")
        end = PROMPT.index("SAY IT A DIFFERENT WAY EVERY TIME")
        assert "—" not in PROMPT[start:end]


class TestTheGraderGuardsAgainstColderLessons:
    def test_a_lesson_must_not_make_her_colder(self):
        flat = _flat(RETRO)
        assert "not make her colder" in flat
        assert "Say what a warm, attentive host does instead" in flat

    def test_the_rooms_own_turns_are_not_her_relapses(self):
        flat = _flat(RETRO)
        assert "WHEN THE ROOM STEPPED IN" in flat
        assert "do not count it as a second sign-off, a repeated question or a relapse" in flat


class TestTheCapRetiresWhatSheHasLearned:
    def test_a_rule_she_keeps_breaking_is_not_the_one_retired(self, monkeypatch):
        import learning as L
        rows = [
            {"id": "old-broken", "show": "network", "lesson": "Do not re-ask a question already answered.",
             "decided_at": "2026-09-18T00:00:00Z", "relapses": 2},
            {"id": "old-kept", "show": "network", "lesson": "Ask the uncomfortable question plainly, once.",
             "decided_at": "2026-09-19T00:00:00Z", "relapses": 0},
            {"id": "newer", "show": "network", "lesson": "Probe the bet they cannot prove yet.",
             "decided_at": "2026-10-05T00:00:00Z", "relapses": 0},
        ]
        monkeypatch.setattr(L, "active_lessons", lambda scope: list(rows) if scope == L.NETWORK else [])
        monkeypatch.setattr(L, "lesson_cap", lambda scope: 3)
        retired = []
        monkeypatch.setattr(L, "retire_lessons", lambda ids, why="": retired.extend(ids) or len(ids))
        monkeypatch.setattr(L, "sb_insert", lambda table, row: {**row, "id": "new-1"})
        L.adopt_lessons("age_of_ai", "iv-1", [{"lesson": "Name the book back before the next lightning question.",
                                               "category": "tone"}])
        assert retired == ["old-kept"]

    def test_when_every_rule_is_still_broken_the_oldest_goes(self, monkeypatch):
        import learning as L
        rows = [
            {"id": "a", "show": "network", "lesson": "Do not re-ask a question already answered.",
             "decided_at": "2026-09-18T00:00:00Z", "relapses": 2},
            {"id": "b", "show": "network", "lesson": "Ask the uncomfortable question plainly, once.",
             "decided_at": "2026-09-19T00:00:00Z", "relapses": 1},
        ]
        monkeypatch.setattr(L, "active_lessons", lambda scope: list(rows) if scope == L.NETWORK else [])
        monkeypatch.setattr(L, "lesson_cap", lambda scope: 2)
        retired = []
        monkeypatch.setattr(L, "retire_lessons", lambda ids, why="": retired.extend(ids) or len(ids))
        monkeypatch.setattr(L, "sb_insert", lambda table, row: {**row, "id": "new-1"})
        L.adopt_lessons("age_of_ai", "iv-1", [{"lesson": "Name the book back before the next lightning question.",
                                               "category": "tone"}])
        assert retired == ["a"]


class TestTheRoomNeverTalksOverItself:
    def test_every_turn_she_starts_can_be_cut_off(self):
        assert "function markTurnStarted(agent)" in SCENARIO
        assert "Grok.VoiceAgentAPIEvents.ResponseCreated" in SCENARIO
        assert 'raw.indexOf("\\"response.created\\"") >= 0) markTurnStarted(agent)' in SCENARIO
        # The barge-in still cancels only when a turn is in flight.
        assert "if (!miraSpeaking) return;" in SCENARIO

    def test_a_room_turn_waits_for_the_one_in_flight(self):
        body = _jsfn("requestTurn")
        assert "if (miraSpeaking) { pendingTurn = true; return; }" in body
        # ResponseDone releases it, unless someone is talking.
        done = SCENARIO[SCENARIO.index("Grok.VoiceAgentAPIEvents.ResponseDone, function () {\n        miraSpeaking = false;"):]
        done = done[:done.index("});")]
        assert "if (pendingTurn && agent === grokAgent && !roomEnded)" in done
        assert "if (!inboundSpeaking)" in done
        # The guest starting to talk drops it.
        started = SCENARIO[SCENARIO.index("InputAudioBufferSpeechStarted, function () {"):]
        assert started.index("pendingTurn = false;") < started.index("agent.clearMediaBuffer();")

    def test_one_sign_off_earns_one_rescue(self):
        assert "const RESCUE_COOLDOWN_MS = 20 * 1000;" in SCENARIO
        closing = _jsfn("catchClosingWithoutTheAnswer")
        early = _jsfn("catchEarlySignOff")
        assert "if (!rescueAllowed()) return true;" in closing
        assert "if (!rescueAllowed()) return;" in early
        for body in (closing, early):
            assert "requestTurn(grokAgent);" in body
            assert "grokAgent.responseCreate" not in body

    def test_the_opening_never_greets_twice(self):
        body = _jsfn("openWhenReady")
        assert "|| miraSpeaking)) {" in body
        assert "lastMiraLineAt > guestJoinedAt()" in body
        assert "You have already said hello" in body
        assert "if (!alreadyGreeted) {" in body
        # Time checks and the mic check still start either way.
        assert body.index("if (!alreadyGreeted) {") < body.index("startTimeChecks();")

    def test_she_records_when_she_last_spoke(self):
        assert "lastMiraLineAt = Date.now();" in _jsfn("remember")

    @pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
    def test_the_scenario_still_parses(self):
        path = ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js"
        out = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
        assert out.returncode == 0, out.stderr


class TestAStagedRunCarriesTheLatestLessons:
    """A run is staged a day ahead and graded lessons land an hour after each
    interview, so the next day's guest met a Mira who had not learned from
    the last one. Each fire tick now refreshes a staged prompt."""

    def _fi(self, monkeypatch, briefs=({"id": "b"},)):
        import fire_interviews as F
        monkeypatch.delenv("MIRA_TURN_SILENCE_MS", raising=False)
        updates = []
        monkeypatch.setattr(F, "sb_select", lambda table, q="": (
            [{"id": "app"}] if table == "guest_applications" else list(briefs)))
        monkeypatch.setattr(F, "sb_update", lambda table, q, patch: updates.append((table, q, patch)) or [patch])
        monkeypatch.setattr(F, "compile_mira_prompt", lambda iv, app, brief: "NEW PROMPT")
        monkeypatch.setattr(F, "is_closing_session", lambda iv: False)
        return F, updates

    def test_a_staged_prompt_is_brought_up_to_date(self, monkeypatch):
        F, updates = self._fi(monkeypatch)
        run = {"id": "run-1", "status": "staged", "mira_system_prompt": "OLD",
               "turn_detection": F.turn_detection()}
        assert F.refresh_staged_prompt(run, {"id": "iv", "application_id": "app"}) is True
        table, q, patch = updates[0]
        assert table == "interview_runs" and "status=eq.staged" in q and "id=eq.run-1" in q
        assert patch == {"mira_system_prompt": "NEW PROMPT"}

    def test_an_unchanged_prompt_is_not_rewritten(self, monkeypatch):
        F, updates = self._fi(monkeypatch)
        run = {"id": "run-1", "status": "staged", "mira_system_prompt": "NEW PROMPT",
               "turn_detection": F.turn_detection()}
        assert F.refresh_staged_prompt(run, {"id": "iv", "application_id": "app"}) is False
        assert updates == []

    def test_a_room_already_open_is_left_alone(self, monkeypatch):
        F, updates = self._fi(monkeypatch)
        for status in ("awaiting_guest", "in_progress", "completed"):
            run = {"id": "run-1", "status": status, "mira_system_prompt": "OLD"}
            assert F.refresh_staged_prompt(run, {"id": "iv", "application_id": "app"}) is False
        assert updates == []

    def test_no_brief_keeps_the_prompt_it_has(self, monkeypatch):
        F, updates = self._fi(monkeypatch, briefs=())
        run = {"id": "run-1", "status": "staged", "mira_system_prompt": "OLD"}
        assert F.refresh_staged_prompt(run, {"id": "iv", "application_id": "app"}) is False
        assert updates == []

    def test_every_tick_refreshes_the_runs_it_skips(self):
        src = (V / "fire_interviews.py").read_text(encoding="utf-8")
        skip = src[src.index('already has an active run — skipping'):]
        skip = skip[:skip.index("continue")]
        assert "refresh_staged_prompt(r, interview)" in skip


class TestAGuestTakeIsPlacedOnTheWholeLeg:
    """Jon Cheney, Oct 19 2026. His browser take was on the leg's clock to a
    tenth of a second; align_to_reference, measuring only the first sixty
    seconds, trimmed 21.9 s off it, and every answer in the mix, the
    transcript and the grade sat twenty-two seconds before its question."""

    def _pi(self, monkeypatch, *, windows, on_clock=True, delay=0.0):
        import post_interview as pi
        calls = {}
        monkeypatch.setattr(pi, "whole_file_delay", lambda t, r, w: calls.setdefault("whole", (-21.9, 0.6)))
        def room(track, room, workdir, expected=None, pieces_out=None):
            calls["expected"] = expected
            return Path(str(track) + ".room"), delay, windows
        monkeypatch.setattr(pi, "align_to_room", room)
        monkeypatch.setattr(pi, "place_phrases", lambda g, r, out: (Path(str(g) + ".phr"), {"moved": 3}))
        monkeypatch.setattr(pi, "gate_to_reference", lambda g, r, out, heard_wav=None: (Path(str(g) + ".gated"), {"kept": 1}))
        monkeypatch.setattr(pi, "take_on_clock", lambda t, r, w: on_clock)
        return pi, calls

    def test_the_whole_file_estimate_is_the_expectation(self, monkeypatch, tmp_path):
        pi, calls = self._pi(monkeypatch, windows=3)
        out = pi.place_local_take(Path("take.wav"), Path("leg.wav"), Path("heard.wav"), tmp_path)
        assert calls["expected"] == -21.9
        assert out is not None and out.name.endswith(".room.phr.gated")

    def test_a_take_that_cannot_be_placed_is_not_used(self, monkeypatch, tmp_path):
        pi, _ = self._pi(monkeypatch, windows=0)
        assert pi.place_local_take(Path("take.wav"), Path("leg.wav"), None, tmp_path) is None

    def test_a_take_off_the_clock_after_placement_is_not_used(self, monkeypatch, tmp_path):
        pi, _ = self._pi(monkeypatch, windows=3, on_clock=False)
        assert pi.place_local_take(Path("take.wav"), Path("leg.wav"), None, tmp_path) is None

    def test_the_old_head_window_estimate_is_gone_from_the_guest_path(self):
        src = (V / "post_interview.py").read_text(encoding="utf-8")
        body = src[src.index("def build_tracks("):src.index("def place_local_take(")]
        assert "align_to_reference(local_guest" not in body
        assert "place_local_take(local_guest, guest_vox, guest_r" in body

    def test_whole_file_delay_sign(self, tmp_path):
        """A take whose recorder started 21.9 s after the leg's shows every
        event 21.9 s sooner on its own clock, and is delayed by +21.9 s (the
        same convention as estimate_room_delay: pad it)."""
        import numpy as np
        import audio.local_tracks as lt
        rng = np.random.default_rng(1)
        sr = lt.ROOM_ENVELOPE_SR
        room = np.abs(rng.normal(size=600 * sr)).astype(np.float32)
        lead = int(21.9 * sr)
        take = np.concatenate([room[lead:], np.zeros(lead, dtype=np.float32)])
        envs = {"take": take, "room": room}
        lt_env = lt._whole_envelope
        try:
            lt._whole_envelope = lambda path, workdir: envs[Path(path).stem]
            delay, strength = lt.whole_file_delay(Path("take.wav"), Path("room.wav"), tmp_path)
        finally:
            lt._whole_envelope = lt_env
        assert abs(delay - 21.9) < 0.05 and strength > 0.5


class TestItIsTheGuestsHour:
    """Patrick, Oct 19 2026: guests are told, before the day and by Mira at
    the open, that they can steer, skip, start again, pause and have things
    cut, so the hour is about what they came to say, and the edit keeps the
    promise."""

    YOUR_HOUR = "It's your hour."

    def test_mira_says_so_at_the_open(self):
        flat = _flat(PROMPT)
        beat2 = flat[flat.index("2. ONE SENTENCE ON HOW THIS WORKS, ONE THAT IT IS THEIR HOUR"):flat.index("{{cohost_intro_step}}")]
        assert "This is your hour" in beat2
        assert "anything can come out afterwards" in beat2
        assert "never again" in beat2

    def test_and_knows_what_to_do_when_they_take_her_up_on_it(self):
        flat = _flat(PROMPT)
        rule = flat[flat.index("IT IS THEIR HOUR, AND YOU TOLD THEM SO"):flat.index("A PERSONAL STORY IS NOT A CLAIM")]
        for cue, answer in (("skip a question", '"Of course"'),
                            ("start an answer again", '"Go ahead"'),
                            ("something to be cut", '"Done, that stays out"'),
                            ("want a moment", '"Take your time"')):
            assert cue in rule and answer in rule, cue
        assert "never that one again in any form" in rule
        assert "a thinking pause is never the end of an answer" in rule

    def test_the_booking_email_says_so(self):
        worker = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
        assert "const GUEST_YOUR_HOUR_HTML" in worker
        booked = worker[worker.index("Thank you for booking. We're on"):]
        booked = booked[:booked.index("miraSignature(show)")]
        assert "${GUEST_YOUR_HOUR_HTML}" in booked
        tpl = (ROOT / "templates" / "email" / "voices_booking_confirmation.j2").read_text(encoding="utf-8")
        assert self.YOUR_HOUR in tpl and "start an answer again" in tpl

    def test_the_brief_says_so_and_names_the_words(self):
        tpl = (ROOT / "templates" / "email" / "voices_prep_brief.j2").read_text(encoding="utf-8")
        assert "<h3>In the room</h3>" in tpl
        assert self.YOUR_HOUR in tpl
        assert '"give me a second"' in tpl and '"let\'s cut that"' in tpl

    def test_the_five_minute_notice_reminds_them(self):
        src = (V / "fire_interviews.py").read_text(encoding="utf-8")
        body = src[src.index("def start_notice_email("):src.index("def start_notice_sms(")]
        assert "it's your hour" in body

    def test_the_edit_keeps_the_promise(self):
        edit = _flat((V / "prompts" / "auto_edit.txt").read_text(encoding="utf-8"))
        assert "WHAT THE GUEST ASKED TO HAVE OUT COMES OUT" in edit
        for words in ("let me start over", "can we cut that", "I'd rather not"):
            assert words in edit, words
        assert "not subject to the twenty-five-second minimum" in edit

    def test_no_em_dash_in_the_guest_wording(self):
        for path in (ROOT / "templates" / "email" / "voices_prep_brief.j2",
                     ROOT / "templates" / "email" / "voices_booking_confirmation.j2"):
            body = path.read_text(encoding="utf-8")
            body = body[body.index("#}") + 2:]   # the template comment is not sent
            assert "—" not in body, path.name


class TestSheWaitsForAThought:
    def test_the_end_of_turn_silence_is_long_enough_to_think_in(self):
        import fire_interviews as F
        assert F.TURN_SILENCE_MS == 1800

    def test_a_staged_run_picks_up_the_new_silence(self, monkeypatch):
        import fire_interviews as F
        updates = []
        monkeypatch.setattr(F, "sb_select", lambda table, q="": (
            [{"id": "app"}] if table == "guest_applications" else [{"id": "b"}]))
        monkeypatch.setattr(F, "sb_update", lambda table, q, patch: updates.append(patch) or [patch])
        monkeypatch.setattr(F, "compile_mira_prompt", lambda iv, app, brief: "SAME")
        monkeypatch.setattr(F, "is_closing_session", lambda iv: False)
        monkeypatch.delenv("MIRA_TURN_SILENCE_MS", raising=False)
        run = {"id": "run-1", "status": "staged", "mira_system_prompt": "SAME",
               "turn_detection": {"silence_duration_ms": 1300}}
        assert F.refresh_staged_prompt(run, {"id": "iv", "application_id": "app"}) is True
        assert updates == [{"turn_detection": {"silence_duration_ms": 1800}}]


class TestTheInvitationComesBeforeTheSignOff:
    """Jon Cheney, Oct 19 2026 (rebuilt tape): "You can hang up now", then
    three sentences inviting listeners to apply. The invitation belongs
    between the thank-you and the sign-off, so the sign-off is the last
    thing the guest hears."""

    def test_the_order_is_thanks_invitation_sign_off(self):
        flat = _flat(PROMPT)
        ends = flat[flat.index("HOW IT ENDS, FOR THE GUEST."):flat.index("## Guardrails")]
        assert ends.index("thank them once, for something particular") \
            < ends.index("Then the invitation to listeners") \
            < ends.index('say the words "that\'s the end of the recording"')
        assert "never after the sign-off" in ends
