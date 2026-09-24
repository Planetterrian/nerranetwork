"""A guest we already know is not pitched to us as a stranger (Sept 23 2026).

Think Right PR re-pitched John Colascione from media@ a month after
bookings@ had pitched him and his application was approved. The inbox only
checked the thread id, so it sent the first-contact invite again (claiming
Patrick sits in as co-host, which stopped being true) and filed a second
application. John Capobianco already had three. The guest's name is what
stays put when a publicist changes address or thread.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipelines.producer import inbox
from tests.test_producer_inbox import (  # noqa: F401  (fixtures)
    _classification, db, decode_raw, env, grok, make_thread, run, slack,
)

ROOT = Path(__file__).resolve().parent.parent


class TestTheName:
    @pytest.mark.parametrize("a,b", [
        ("Dr. Lena Ortiz", "lena ortiz"),
        ("Lena Ortiz, PhD", "Lena  Ortiz"),
        ("Doctor Lena Ortiz", "LENA ORTIZ"),
        ("John Colascione", "john colascione"),
    ])
    def test_the_same_person(self, a, b):
        assert inbox.guest_key(a) == inbox.guest_key(b) != ""

    def test_different_people(self):
        assert inbox.guest_key("John Colascione") != inbox.guest_key("John Capobianco")

    def test_a_first_name_alone_matches_nobody(self):
        assert inbox.guest_key("Dr. Lena") == ""
        assert inbox.guest_key(None) == ""


def _known(db, status="approved", interview=None, record_url=None, name="Dr. Lena Ortiz"):
    db.applications.append({"id": "old1", "name": name, "email": "old@reyespr.com",
                            "status": status, "show": "age_of_ai", "source": "form",
                            "email_thread_id": None, "publicist_email": None,
                            "created_at": "2026-08-24T15:53:53+00:00"})
    if interview:
        db.interviews.append({"id": "iv1", "application_id": "old1", "show": "age_of_ai",
                              **interview})
        if record_url:
            db.records.append({"interview_id": "iv1", "episode_url": record_url})


def _pitch(grok, **over):
    t = make_thread("t9", "Sam Reyes <sam@reyespr.com>", "Guest: Lena Ortiz",
                    "Hi Patrick, I represent Dr. Lena Ortiz...")
    return run([t], grok, {"Lena Ortiz": _classification(**over)})


class TestAKnownGuest:
    def test_on_file_gets_the_booking_link_not_the_invite(self, db, slack, grok, monkeypatch):
        monkeypatch.setenv("CALCOM_BOOKING_URL", "https://cal.com/nerra/age-of-ai")
        _known(db)
        svc, summary = _pitch(grok)
        mime = decode_raw(svc.sent[0])
        assert "no need for a new application" in mime
        assert "https://cal.com/nerra/age-of-ai" in mime
        assert "from August" in mime
        assert "application form" not in mime

    def test_no_second_application(self, db, slack, grok, monkeypatch):
        monkeypatch.setenv("CALCOM_BOOKING_URL", "https://cal.com/nerra/age-of-ai")
        _known(db)
        _pitch(grok)
        assert len(db.applications) == 1
        table, query, patch = db.updates[-1] if db.updates[-1][0] == "guest_applications" \
            else [u for u in db.updates if u[0] == "guest_applications"][-1]
        assert query == "id=eq.old1"
        assert patch["email_thread_id"] == "t9"
        assert patch["producer_action"] == "known_guest"
        assert patch["publicist_email"] == "sam@reyespr.com"

    def test_a_past_guest_is_welcomed_back(self, db, slack, grok, monkeypatch):
        monkeypatch.setenv("CALCOM_BOOKING_URL", "https://cal.com/nerra/age-of-ai")
        _known(db, interview={"status": "published", "scheduled_at": "2026-09-01T17:00:00+00:00"},
               record_url="https://nerranetwork.com/age-of-ai/ep5")
        svc, _ = _pitch(grok)
        mime = decode_raw(svc.sent[0])
        assert "Dr. Ortiz has already been on The Age of AI" in mime
        assert "https://nerranetwork.com/age-of-ai/ep5" in mime
        assert "https://cal.com/nerra/age-of-ai" in mime

    def test_a_booked_guest_is_told_so(self, db, slack, grok):
        _known(db, interview={"status": "scheduled", "scheduled_at": "2099-10-05T20:45:00+00:00"})
        svc, _ = _pitch(grok)
        mime = decode_raw(svc.sent[0])
        assert "Dr. Ortiz is already booked with Mira for Monday, October 5" in mime

    def test_a_recorded_guest_waits_for_the_episode(self, db, slack, grok):
        _known(db, interview={"status": "guest_review", "scheduled_at": "2026-09-20T17:00:00+00:00"})
        svc, _ = _pitch(grok)
        assert "that episode is in review now" in decode_raw(svc.sent[0])

    def test_a_declined_guest_is_patricks_call(self, db, slack, grok):
        _known(db, status="declined")
        svc, summary = _pitch(grok)
        assert not svc.sent and summary["drafted"] == 1
        assert any("declined before" in n for n in slack)

    def test_no_booking_link_means_patrick_sends_it(self, db, slack, grok, monkeypatch):
        monkeypatch.delenv("CALCOM_BOOKING_URL", raising=False)
        _known(db)
        svc, summary = _pitch(grok)
        assert not svc.sent and summary["drafted"] == 1

    def test_a_withdrawn_application_does_not_count(self, db, slack, grok):
        _known(db, status="withdrawn")
        svc, _ = _pitch(grok)
        assert "I'd like to have Dr. Ortiz on" in decode_raw(svc.sent[0])
        assert len(db.applications) == 2

    def test_a_reply_on_the_moved_thread_reaches_the_follow_up_path(self):
        src = (ROOT / "pipelines" / "producer" / "inbox.py").read_text(encoding="utf-8")
        assert 'app_row.get("producer_action") == "known_guest"' in src


class TestNobodyClaimsACoHost:
    def test_the_invite_no_longer_says_patrick_sits_in(self):
        for name in ("producer_guest_invite.j2", "producer_known_guest.j2"):
            text = (ROOT / "templates" / "email" / name).read_text(encoding="utf-8")
            assert "co-host" not in text and "sit in" not in text

    def test_the_known_guest_mail_is_in_patricks_voice(self):
        text = (ROOT / "templates" / "email" / "producer_known_guest.j2").read_text(encoding="utf-8")
        assert text.startswith("Hi {{ publicist_first_name }},")
        assert text.rstrip().endswith("Sincerely,\n\nPatrick")
        assert "—" not in text
