"""Every email a pitched or applying guest gets, checked against what the
network actually does (Sept 24 2026).

The review behind this: forty pitched guests were invited with "reply and
I'll send a booking link", chased twice, and none was ever booked; among
those who did reply, the link converted. The follow-up prompt still told
Grok that Patrick sits in on every session as co-host. The application form
still offered Patrick in the room. The approval email said Mira would call
the guest, who in fact joins a browser studio. The booking email never said
when the interview was. A publicist's booking for one client landed on
another client's row. Dr. Brandt's prep brief went to his publicist and was
never re-sent. Four of the four items held for Patrick on Sept 22 were the
network's own mail.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_producer_inbox import (  # noqa: E402,F401
    OWNER, _classification, db, decode_raw, env, gmail_message, grok, make_thread, run, slack,
)
from tests.test_producer_autonomy import _app, _plan, booking, fdb  # noqa: E402,F401
from pipelines.producer import chase, followup, inbox  # noqa: E402

TEMPLATES = ROOT / "templates" / "email"
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
PROMPT = (ROOT / "pipelines" / "producer" / "prompts" / "followup_reply.txt").read_text(encoding="utf-8")


class TestTheInviteCarriesTheLink:
    def test_link_in_the_first_email(self, db, slack, grok, booking):
        t = make_thread("t1", "Sam Reyes <sam@reyespr.com>", "Guest: Lena Ortiz", "pitching Lena")
        svc, _ = run([t], grok, {"Lena Ortiz": _classification()})
        mime = decode_raw(svc.sent[0])
        assert "https://cal.com/patrick-novak-lkcqo4/age-of-ai-interview" in mime
        assert "own email address" in mime

    def test_both_chases_carry_it(self, booking):
        app = _app(name="Dr. Lena Ortiz")
        for step in (1, 2):
            body = chase.chase_body(app, step)
            assert "https://cal.com/patrick-novak-lkcqo4/age-of-ai-interview" in body
            assert "Dr. Lena Ortiz" in body

    def test_the_chase_workflow_has_the_link(self):
        wf = (ROOT / ".github" / "workflows" / "nerra_producer_daily.yml").read_text(encoding="utf-8")
        chase_step = wf[wf.index("python -m pipelines.producer.chase"):wf.index("Daily summary email")]
        assert "CALCOM_BOOKING_URL:" in chase_step
        assert "CALCOM_BOOKING_URL_NERRA_VOICES:" in chase_step

    @pytest.mark.parametrize("name,expected", [
        ("Dr. Michael Brandt", "Dr. Brandt"), ("Professor Ana Silva", "Professor Silva"),
        ("John Colascione", "John"), ("Lena Ortiz, PhD", "Lena"), ("", "your guest"),
    ])
    def test_how_the_guest_is_named_on_second_mention(self, name, expected):
        assert inbox.guest_first(name) == expected


class TestNothingPromisesPatrickInTheRoom:
    def test_the_follow_up_facts(self):
        assert "sits in on every session" not in PROMPT
        assert "does not join the call" in PROMPT

    @pytest.mark.parametrize("name", ["producer_guest_invite.j2", "producer_known_guest.j2",
                                      "producer_chase_1.j2", "producer_chase_2.j2",
                                      "voices_prep_brief.j2"])
    def test_no_template(self, name):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert "co-host" not in text and "cohost" not in text and "sit in" not in text

    @pytest.mark.parametrize("page", ["age-of-ai-apply.html", "nerra-voices-apply.html"])
    def test_the_form_no_longer_offers_it(self, page):
        html = (ROOT / page).read_text(encoding="utf-8")
        assert "wants_cohost" not in html and "Patrick in the room" not in html

    def test_the_booking_email_no_longer_promises_it(self):
        assert "He will be in the room with Mira" not in WORKER
        assert "host_mode: !!apps[0].wants_cohost" not in WORKER
        assert "she hosts every interview on her own" in WORKER


class TestTheFollowUpFacts:
    def test_computer_and_headphones_not_any_phone(self):
        assert "any laptop or phone browser" not in PROMPT
        assert "Headphones or earbuds are needed" in PROMPT

    def test_no_invented_audience_numbers(self):
        assert "never estimate" in PROMPT

    def test_a_colleague_is_not_a_stranger(self):
        assert "colleague at the same agency" in PROMPT


class TestBookedAndThanks:
    def test_booked_with_an_interview_on_file_is_confirmed_from_the_row(self):
        up = {"id": "iv1", "scheduled_at": "2099-10-05T20:45:00+00:00", "show": "age_of_ai"}
        d = followup.decide_followup(_plan(intent="booked", reply_text=None), _app(),
                                     mode="auto", inbound_auto=False, upcoming=up)
        assert d["action"] == "send"
        body = followup.booked_reply(_app(email="lena@fieldwork.ai"), up, "Sam Reyes")
        assert body.startswith("Hi Sam,")
        assert "Dr. Ortiz is on the calendar for Monday, October 5" in body
        assert "lena@fieldwork.ai" in body and "headphones" in body
        assert body.endswith("Sincerely,\n\nPatrick\n")

    def test_booked_with_nothing_on_file_goes_to_patrick(self):
        d = followup.decide_followup(_plan(intent="booked", reply_text=None), _app(),
                                     mode="auto", inbound_auto=False, upcoming=None)
        assert d["action"] == "draft" and "no upcoming interview" in d["reason"]

    def test_a_thank_you_is_not_answered_or_held(self):
        d = followup.decide_followup(_plan(intent="no_reply_needed", reply_text=None), _app(),
                                     mode="auto", inbound_auto=False)
        assert d["action"] == "label"

    def test_the_model_never_writes_those_replies(self):
        out = followup.validate_followup({"intent": "booked", "confidence": 0.9,
                                          "reply_text": "Hi, you're booked for Tuesday.",
                                          "summary": "booked"})
        assert out["reply_text"] is None


class TestOurOwnMail:
    def test_mira_and_patrick_are_labelled_not_held(self, db, slack, grok):
        t = make_thread("t5", "Mira <mira@nerranetwork.com>",
                        "Your Age of AI episode is ready for your approval", "review link")
        svc, summary = run([t], grok, {})
        assert not svc.sent and not svc.drafted and summary["drafted"] == 0
        assert not grok.calls

    def test_a_guest_answering_mira_is_held_with_a_real_reason(self, db, slack, grok):
        t = make_thread("t6", "Sheldon Poon <sheldon.poon@gmail.com>",
                        "Re: Reminder: your Age of AI transcript awaits", "approved, thanks")
        svc, summary = run([t], grok, {})
        assert summary["drafted"] == 1 and not svc.sent and not grok.calls
        assert any("replied to one of Mira's emails" in n for n in slack)

    def test_a_forwarded_pitch_is_still_a_pitch(self):
        assert not inbox.house_mail({"from_email": "patricknovak1@gmail.com",
                                     "subject": "Fwd: guest idea"})


class TestTheWorker:
    def test_a_shared_publicist_address_is_settled_by_name(self):
        body = WORKER[WORKER.index("function chooseApplication("):]
        body = body[:body.index("\n}\n")]
        assert "namesOverlap(r.name, booked)" in body
        assert "return named.length === 1 ? named : [];" in body
        assert WORKER.count("chooseApplication(await sb(") == 3
        assert "&limit=1`);\n      if (apps?.length) { matchedWith" not in WORKER

    def test_the_booking_email_says_when(self):
        assert "function bookedWhen(" in WORKER
        assert "You're booked${bookedWhen(startTime, p)" in WORKER

    def test_the_approval_email_describes_the_studio_not_a_call(self):
        assert "Mira — our AI host — will call you" not in WORKER
        assert "booking with this email address" in WORKER


class TestTheBrief:
    def test_it_remembers_who_got_it_and_resends_on_a_new_address(self):
        src = (ROOT / "pipelines" / "voices" / "generate_briefs.py").read_text(encoding="utf-8")
        assert '"sent_to": app["email"]' in src
        assert "def resend_to_new_address()" in src
        mig = ROOT / "supabase" / "migrations" / "20260924_brief_remembers_who_got_it.sql"
        assert "add column if not exists sent_to" in mig.read_text(encoding="utf-8")

    def test_the_email_is_well_formed_and_readable(self):
        text = (TEMPLATES / "voices_prep_brief.j2").read_text(encoding="utf-8")
        assert "{{ scheduled_at }}" not in text          # raw ISO timestamps
        assert "Mira's producers" not in text
        assert "&role=guest" not in text                   # built in code
        assert text.count("<p") == text.count("</p>")
        assert "If anything here is wrong about you" in " ".join(text.split())

    def test_when_text(self):
        sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
        import generate_briefs
        assert generate_briefs.when_text("2026-09-24T16:45:00+00:00").startswith(
            "Thursday, September 24 at 16:45 UTC")
