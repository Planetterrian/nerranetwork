"""Oct 5 2026 (Patrick, after Thor Hesselberg and Piper Martz).

1. Warmth. Piper said hello and got a recited paragraph over the top of her,
   then a question Mira answered herself. The opening is now three short
   beats that each listen: a greeting by name and one easy question, then
   how the hour works, then the welcome; and the scenario waits for a guest
   who is still speaking.
2. Time. The closing round takes about nine minutes and was only required in
   the last three, five minutes before the hard cap: Piper was cut off
   mid-answer at 50:00 with no thank-you. It is now required nine minutes
   from the end, and the cap asks for a close instead of cutting.
3. No-shows in the studio. Stan Lewis never opened the studio and nothing
   happened at all; the run sat at awaiting_guest.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
PROMPT = (ROOT / "pipelines" / "voices" / "prompts" / "mira_system_prompt.txt").read_text(encoding="utf-8")
SCENARIO = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text(encoding="utf-8")


def _flat(t):
    return " ".join(t.split())


class TestTheOpeningIsWarm:
    def test_greeting_first_and_listening(self):
        flat = _flat(PROMPT)
        assert "WHO YOU ARE IN THE ROOM" in PROMPT
        assert "Three short beats, each one a turn that ends and LISTENS" in flat
        assert "never start talking while the guest is still saying hello" in flat
        assert "GREET THEM AS A PERSON" in PROMPT
        assert flat.index("GREET THEM AS A PERSON") < flat.index("I'm Mira. I'm the AI who hosts {{show_name}}.")

    def test_tagline_is_not_the_first_words(self):
        assert "never as your first words: {{opening_line}}" in _flat(PROMPT)

    def test_warmth_through_the_hour(self):
        flat = _flat(PROMPT)
        assert "WARMTH THROUGH THE WHOLE HOUR" in PROMPT
        assert "come back to one later in the hour" in flat
        assert "Warmth is not compliments and it is not gushing; it is attention" in flat

    def test_scenario_waits_for_a_hello_and_asks_for_beat_one(self):
        assert "inboundSpeaking || Date.now() - inboundSpokeAt < 900" in SCENARIO
        assert "This turn is beat 1 of HOW TO OPEN only" in SCENARIO
        assert "Do not answer your" in SCENARIO


class TestItFinishesOnTime:
    def test_closing_required_nine_minutes_out(self):
        assert "function closingRoundMin() { return Math.min(9, closingWindowMin()); }" in SCENARIO
        assert "} else if (remainMin > closingRoundMin()) {" in SCENARIO
        assert "closing round required (scheduled note)" in SCENARIO

    def test_the_cap_closes_instead_of_cutting(self):
        cap = SCENARIO[SCENARIO.index("hardCapTimer = setTimeout(function () {"):]
        cap = cap[:cap.index("}, hardCapMs());")]
        assert "three" in cap and "hours past the plan" in cap
        assert 'setTimeout(function () { endRoom("hard_cap"); }, 5 * 60 * 1000)' in cap


class TestTimeNeverRunsOut:
    """Oct 5 2026 (Patrick): "Time shouldn't ever run out for an interview."""

    def test_no_cut_off_at_the_planned_time(self):
        assert "SAFETY_CAP_AFTER_PLAN_MIN = 180" in SCENARIO
        assert "HARD_CAP_SLACK_MIN" not in SCENARIO
        assert "the guest may go on as long as they like" in SCENARIO
        assert "Time is up." not in SCENARIO
        assert "which is all the time that is left" not in SCENARIO

    def test_prompt_says_no_cap(self):
        flat = _flat(PROMPT)
        assert "There is no time cap" in flat
        assert "an interview never ends because the clock ran out" in flat
        assert "Hard time cap" not in flat


class TestStudioNoShows:
    def test_sweep_marks_missed_and_writes(self, monkeypatch):
        import fire_interviews as fi
        now = dt.datetime.now(dt.timezone.utc)
        iv = {"id": "i1", "application_id": "a1", "status": "briefed", "call_mode": "webrtc",
              "scheduled_at": (now - dt.timedelta(hours=3)).isoformat(), "show": "age_of_ai"}
        updates, mails = [], []

        def select(table, q):
            if table == "interviews":
                return [iv]
            if table == "interview_runs":
                return [{"id": "r1", "status": "awaiting_guest"}]
            return [{"id": "a1", "name": "Stan Lewis", "email": "s@x.com"}]

        monkeypatch.setattr(fi, "sb_select", select)
        monkeypatch.setattr(fi, "sb_update", lambda t, q, d: updates.append((t, d)))
        monkeypatch.setattr(fi, "send_email", lambda to, subj, html, **k: mails.append((to, subj)))
        monkeypatch.setattr(fi, "render_email", lambda *a, **k: "<p>x</p>")
        monkeypatch.setattr(fi, "notify_operator", lambda *a, **k: None)
        assert fi.sweep_browser_no_shows() == 1
        assert ("interview_runs", {"status": "failed", "disconnect_reason": "no_show"}) in updates
        assert ("interviews", {"status": "missed", "no_show_count": 1}) in updates
        assert mails and mails[0][0] == "s@x.com"

    def test_a_joined_run_is_left_alone(self, monkeypatch):
        import fire_interviews as fi
        monkeypatch.setattr(fi, "sb_select", lambda t, q: [{"id": "i1", "application_id": "a1"}]
                            if t == "interviews" else [{"id": "r1", "status": "completed"}])
        monkeypatch.setattr(fi, "sb_update", lambda *a: (_ for _ in ()).throw(AssertionError("no write")))
        assert fi.sweep_browser_no_shows() == 0
