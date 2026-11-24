"""Nov 24 2026: a room cut short is not thanked for the hour.

On Nov 23 a guest's browser left the Age of AI room 6 min 18 s into a
45-minute interview, two seconds after a question, with no goodbye and no
closing round. The room closed after its 45 s rejoin wait, the Worker treated
a room past five minutes as a finished interview, and eleven minutes later
Mira emailed the guest (a colleague copied) "Thank you for the hour". The
room's trace said only "disconnected", so nobody could tell an End press from
a dropped call.

* ``guest_thanks.cut_short`` holds the thank-you for a room under half its
  planned minutes with the closing round unfinished, and Patrick is told.
* The studio page records how it left the call (``ended_by``) on its take,
  and the Worker keeps it, a closed vocabulary.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))

import guest_thanks as gt  # noqa: E402

STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")

TRANSCRIPT = """[00:20] Mira: What did the first year teach you?
[00:25] Jane Doe: The first year taught us that pricing is a story, and we told it badly for eleven months before the first big client walked.
"""


def _run(dur, closing=False, ended_by=None, planned=45):
    take = {"started_at": "2026-11-23T21:47:04Z", "chunks": 82}
    if ended_by:
        take["ended_by"] = ended_by
    return {"id": "r1", "duration_sec": dur, "planned_minutes": planned,
            "grok_session_log": {"closing_round_complete": closing,
                                 "local_takes": {"guest": [take]}}}


IV = {"id": "i1", "session_kind": "interview", "duration_min": 45}
APP = {"name": "Jane Doe", "email": "jane@example.com"}


class TestCutShort:
    def test_the_nov_23_room_is_cut_short(self):
        assert gt.cut_short(_run(408), IV) is True

    def test_a_full_room_is_not(self):
        assert gt.cut_short(_run(2678, closing=True), IV) is False
        assert gt.cut_short(_run(2534), IV) is False

    def test_a_finished_closing_round_is_never_cut_short(self):
        # A guest who said goodbye early and got the round is a whole interview.
        assert gt.cut_short(_run(900, closing=True), IV) is False

    def test_short_planned_sessions_are_out_of_scope(self):
        assert gt.cut_short(_run(300, planned=15), {"session_kind": "interview", "duration_min": 15}) is False

    def test_other_session_kinds_are_out_of_scope(self):
        assert gt.cut_short(_run(408), {"session_kind": "closing"}) is False

    def test_missing_duration_is_not_cut_short(self):
        assert gt.cut_short({"planned_minutes": 45}, IV) is False


class TestTheThankYouIsHeld:
    def test_patrick_hears_instead_of_the_guest(self, monkeypatch):
        sent, pings = [], []
        monkeypatch.setattr(gt, "send_email", lambda to, s, b, **kw: sent.append((to, s, b)))
        monkeypatch.setattr(gt, "notify_operator", lambda t, **kw: pings.append(t))
        monkeypatch.setattr(gt, "sb_update", lambda *a, **k: (_ for _ in ()).throw(AssertionError("stamped")))
        assert gt.send_thank_you(_run(408, ended_by="dropped"), IV, APP, TRANSCRIPT, {"id": "p"}) is False
        assert len(sent) == 1
        to, subject, body = sent[0]
        assert to == gt.OPERATOR_EMAIL
        assert "6.8 of 45 minutes" in subject
        assert "dropped off the call" in body
        assert "for the hour" in body  # explains why the usual note was held
        assert pings

    def test_a_full_room_still_gets_the_note(self, monkeypatch):
        sent = []
        monkeypatch.setattr(gt, "send_email", lambda to, s, b, **kw: sent.append(to))
        monkeypatch.setattr(gt, "sb_update", lambda *a, **k: None)
        monkeypatch.setattr(gt, "show_for", lambda i, a: type("S", (), {"slug": "age_of_ai"})())
        monkeypatch.setattr(gt, "kits_html", lambda *a, **k: "")
        monkeypatch.setattr(gt, "mira_signature_html", lambda *a, **k: "")
        assert gt.send_thank_you(_run(2678, closing=True), IV, APP, TRANSCRIPT, {"id": "p"}) is True
        assert sent == ["jane@example.com"]


class TestHowThePageLeft:
    def test_ended_by_is_read_from_the_newest_take(self):
        assert gt.guest_ended_by(_run(408, ended_by="guest_end")) == "guest_end"
        assert gt.guest_ended_by(_run(408)) == ""
        assert gt.guest_ended_by(_run(408, ended_by="something")) == ""

    def test_the_page_says_how_it_left(self):
        assert 'rec.endedBy = (isHost ? leaving : guestEnded) ? "guest_end" : "dropped";' in STUDIO
        assert "payload.ended_by = rec.endedBy" in STUDIO
        # A rejoin starts a fresh take with no stale answer.
        assert 'rec.done = false; rec.endedBy = "";' in STUDIO

    def test_the_worker_keeps_a_closed_vocabulary(self):
        assert 'body?.ended_by === "guest_end" || body?.ended_by === "dropped"' in WORKER
