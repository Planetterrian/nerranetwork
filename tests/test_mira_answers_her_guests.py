"""Sept 28 2026. Dr. Elliot Justin answered Mira's prep brief with the point
he most wanted to make on the show. The Producer read his reply as a
publicist's pitch *about Elliot Justin*, found him booked, and sent him,
from Patrick's address and signed "Patrick":

    Hi There,
    Thanks for the note about Elliot Justin. Elliot is already booked with
    Mira for Monday, September 28 ...

Patrick had to apologise for it. These tests hold the fixes in place:

* every automated email comes from Mira, by name, and is signed by her;
* a guest writing to Mira is recognised by who they are and by the thread,
  never by subject, and is never classified as a pitch;
* what a guest sends for the interview is filed and reaches Mira's prompt;
* Mira's replies are checked before they go (no links that are not on
  file, no "Thanks for the note about"), and anything she should not
  answer goes to Patrick at once, by email, with what she would have said.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import pytest

from pipelines.producer import guest_reply, inbox, mira_mail
from pipelines.producer import policy as policy_mod
from pipelines.producer.gmail_client import GmailClient
from pipelines.voices import common
from tests.test_producer_inbox import FakeGmailService, OWNER, gmail_message

ROOT = Path(__file__).resolve().parent.parent
MIRA = "mira@nerranetwork.com"
ELLIOT = "elliot@myfirmtech.com"
ELLIOT_SAYS = ("Question #2-Arterial insufficiency is commonly thought to be the #1 cause of "
               "ED. Our data indicates that it is venous leak that is #1 and easily addressed.")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class GuestDB:
    def __init__(self):
        self.apps = [{"id": "app-elliot", "name": "Dr. Elliot Justin", "email": ELLIOT,
                      "show": "nerra_voices", "status": "approved", "guest_notes": None,
                      "desired_minutes": 45, "publicist_email": None}]
        self.interviews = [{"id": "iv-1", "application_id": "app-elliot", "status": "briefed",
                            "scheduled_at": "2099-09-28T16:45:00+00:00", "show": "nerra_voices",
                            "call_mode": "webrtc", "manage_token": "tok123"}]
        self.updates: List[Any] = []

    def select(self, table, query=""):
        from urllib.parse import unquote
        q = unquote(query)
        if table == "interviews":
            aid = q.split("application_id=eq.", 1)[1].split("&", 1)[0]
            return [iv for iv in self.interviews if iv["application_id"] == aid]
        if table == "guest_applications":
            m = re.search(r"(email|publicist_email)=ilike\.([^&]+)", q)
            if m and not q.startswith("or="):
                field, addr = m.group(1), m.group(2).lower()
                return [a for a in self.apps if (a.get(field) or "").lower() == addr]
            return []
        return []

    def update(self, table, query, patch):
        self.updates.append((table, query, patch))
        return [patch]


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://fake.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "k")
    monkeypatch.setenv("GMAIL_DELEGATED_USER", OWNER)
    monkeypatch.setenv("CALCOM_BOOKING_URL_NERRA_VOICES", "https://cal.com/nerra/voices")
    monkeypatch.delenv("PRODUCER_MODE", raising=False)
    policy_mod._load_yaml.cache_clear()


@pytest.fixture
def gdb(monkeypatch, env):
    db = GuestDB()
    monkeypatch.setattr(guest_reply, "sb_select", db.select)
    monkeypatch.setattr(guest_reply, "sb_update", db.update)
    # The pitch path must never be reached for a guest: make it loud if it is.
    monkeypatch.setattr(inbox, "sb_select", lambda t, q="": [])
    def insert(table, row):
        if table == "guest_applications":
            pytest.fail("no application row for a guest")
        return {"id": "run1"}
    monkeypatch.setattr(inbox, "sb_insert", insert)
    monkeypatch.setattr(inbox, "sb_update", db.update)
    monkeypatch.setattr(inbox, "notify_operator", lambda text, critical=False: None)
    return db


@pytest.fixture
def outbox(monkeypatch):
    """Everything Mira sends (via mira_mail) and every note to Patrick."""
    sent: List[Dict[str, Any]] = []
    patrick: List[Dict[str, Any]] = []
    monkeypatch.setattr(mira_mail, "send_email",
                        lambda to, subject, html, cc_operator=False, cc=None, **kw:
                        sent.append({"to": to, "subject": subject, "cc_operator": cc_operator, **kw}))
    monkeypatch.setattr(guest_reply, "send_email",
                        lambda to, subject, html, **kw: patrick.append(
                            {"to": to, "subject": subject, "html": html}))
    return {"sent": sent, "patrick": patrick}


@pytest.fixture
def grok(monkeypatch):
    calls: List[str] = []
    answers: Dict[str, Any] = {}

    def fake(*, prompt, **kw):
        calls.append(prompt)
        for key, value in answers.items():
            if key in prompt:
                return (value if isinstance(value, str) else json.dumps(value)), {}
        return json.dumps({"category": "newsletter_or_noise", "confidence": 0.9,
                           "is_ai_related": False}), {}

    import digests.xai_grok as xg
    monkeypatch.setattr(xg, "grok_generate_text", fake)
    fake.calls = calls  # type: ignore[attr-defined]
    fake.answers = answers  # type: ignore[attr-defined]
    return fake


def elliot_thread(reply_body: str = ELLIOT_SAYS) -> Dict[str, Any]:
    """Mira's prep brief (copied to Patrick), then Elliot's reply-all."""
    subject = "Your Nerra Voices interview: what Mira plans to ask"
    return {"id": "te", "messages": [
        gmail_message("te1", "te", f"Mira <{MIRA}>", "Hi Elliot, here is what I'm planning...",
                      subject, 1000, to=ELLIOT),
        gmail_message("te2", "te", f"Elliot Justin <{ELLIOT}>", reply_body,
                      f"Re: {subject}", 2000, to=MIRA),
    ]}


def run(threads, dry_run=False):
    svc = FakeGmailService(threads)
    client = GmailClient(svc, OWNER, dry_run=dry_run, mailer=mira_mail.MiraMailer())
    summary = inbox.run_inbox(gmail=client, dry_run=dry_run)
    return svc, client, summary


INPUT_PLAN = {
    "intent": "interview_input", "confidence": 0.93,
    "reply_text": ("Hi Elliot,\n\nThank you. The point that venous leak, not arterial "
                   "insufficiency, is the leading cause is exactly the kind of thing I want to "
                   "hear you make the case for, and I'll bring it up early."),
    "interview_note": "Venous leak, not arterial insufficiency, is the #1 cause of ED, and it is easily addressed.",
    "summary": "Elliot sent his answer to question 2; filed for the interview and thanked him.",
}


# ---------------------------------------------------------------------------
# The Elliot case, end to end
# ---------------------------------------------------------------------------

class TestElliot:
    def test_his_reply_is_answered_by_mira_as_a_guest(self, gdb, outbox, grok):
        grok.answers["You are Mira, the AI host of Nerra Voices"] = INPUT_PLAN
        svc, _client, summary = run([elliot_thread()])
        # Never classified as a pitch.
        assert not any("inbox triage assistant" in c for c in grok.calls)
        assert summary["sent"] == 0 and summary.get("guest_replies_sent") == 1
        assert not svc.sent, "nothing goes out of Patrick's mailbox"
        [mail] = outbox["sent"]
        assert mail["to"].endswith(f"<{ELLIOT}>") or mail["to"] == ELLIOT
        body = mail["text_body"]
        assert body.startswith("Hi Elliot,")
        assert "venous leak" in body
        assert body.rstrip().endswith("Sincerely,\n\nMira\nHost of Nerra Voices, Nerra Network")
        assert "Thanks for the note about" not in body and "Patrick" not in body
        assert mail["subject"].startswith("Re: ")
        assert mail["headers"]["In-Reply-To"] == "<te2@example.com>"
        assert mail["cc_operator"] is True

    def test_what_he_said_reaches_the_interview(self, gdb, outbox, grok):
        grok.answers["You are Mira, the AI host of Nerra Voices"] = INPUT_PLAN
        run([elliot_thread()])
        notes = [p["guest_notes"] for t, q, p in gdb.updates
                 if t == "guest_applications" and "guest_notes" in p]
        assert notes and "Venous leak" in notes[-1][-1]["text"]
        block = common.guest_notes_block({"guest_notes": notes[-1]})
        assert "WHAT THE GUEST SENT YOU BEFORE THE CALL" in block and "Venous leak" in block
        prompt = (ROOT / "pipelines" / "voices" / "prompts" / "mira_system_prompt.txt").read_text()
        assert "{{guest_notes}}" in prompt
        fire = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text()
        assert "guest_notes=guest_notes_block(app)" in fire

    def test_the_facts_come_from_the_rows(self, gdb):
        guest = guest_reply.find_guest(ELLIOT)
        facts = guest_reply.facts_for(guest)
        assert "booked for" in facts["standing"]
        assert any(l.endswith("&role=guest") for l in facts["links"])
        assert "https://api.nerranetwork.com/voices/manage/tok123" in facts["links"]

    def test_a_question_mira_cannot_answer_goes_to_patrick_now(self, gdb, outbox, grok):
        grok.answers["You are Mira, the AI host of Nerra Voices"] = {
            "intent": "needs_patrick", "confidence": 0.9, "reply_text": None,
            "interview_note": None, "summary": "asks whether we will pay for his travel"}
        svc, _c, summary = run([elliot_thread("Will you cover my travel to a studio?")])
        assert not outbox["sent"] and summary.get("guest_replies_held") == 1
        [note] = outbox["patrick"]
        assert note["subject"] == "Dr. Elliot Justin wrote to me: needs you"
        assert "cover my travel" in note["html"]
        assert svc.label_ids["Producer/Hold"] in svc.thread_labels["te"]

    def test_a_thank_you_gets_no_reply(self, gdb, outbox, grok):
        grok.answers["You are Mira, the AI host of Nerra Voices"] = {
            "intent": "thanks", "confidence": 0.95, "reply_text": None,
            "interview_note": None, "summary": "thanks"}
        run([elliot_thread("Thanks, see you Monday.")])
        assert not outbox["sent"] and not outbox["patrick"]


class TestTheGuard:
    LINKS = ["https://nerranetwork.com/nerra-voices.html", "https://nerranetwork.com"]

    def test_invented_links_are_stopped(self):
        why = guest_reply.guard("Hi Elliot,\n\nBook here: https://calendly.com/x", self.LINKS)
        assert "not on file" in why

    def test_the_old_sentence_is_stopped(self):
        assert guest_reply.guard("Hi There,\n\nThanks for the note about Elliot Justin.", self.LINKS)

    def test_a_good_reply_passes(self):
        assert guest_reply.guard("Hi Elliot,\n\nThank you, I'll bring it up.", self.LINKS) == ""


class TestNotAGuest:
    def test_a_platform_notice_with_a_guest_sounding_subject_is_not_a_guest(self, gdb, outbox, grok):
        t = {"id": "ts", "messages": [gmail_message("ts1", "ts", "Spotify <no-reply@spotify.com>",
                                                    "...", "Your episode is live", 1000)]}
        run([t])
        assert not outbox["sent"] and not outbox["patrick"]


# ---------------------------------------------------------------------------
# Every automated email is Mira's
# ---------------------------------------------------------------------------

class TestEverythingIsFromMira:
    def test_display_name_is_forced(self, monkeypatch):
        monkeypatch.setattr(common, "FROM_EMAIL", "mira@nerranetwork.com")
        assert common.mira_from() == "Mira <mira@nerranetwork.com>"
        monkeypatch.setattr(common, "FROM_EMAIL", "Nerra Network <mira@nerranetwork.com>")
        assert common.mira_from() == "Mira <mira@nerranetwork.com>"

    def test_resend_payload(self, monkeypatch):
        seen = {}

        class R:
            def raise_for_status(self):
                pass

        def post(url, headers=None, json=None, timeout=None):
            seen.update(json)
            return R()
        monkeypatch.setenv("RESEND_API_KEY", "k")
        monkeypatch.setattr(common.requests, "post", post)
        common.send_email("guest@example.com", "Hi", "<p>x</p>",
                          headers={"In-Reply-To": "<a@b>"})
        assert seen["from"] == "Mira <mira@nerranetwork.com>"
        assert seen["reply_to"] == "mira@nerranetwork.com"
        assert seen["headers"] == {"In-Reply-To": "<a@b>"}

    def test_the_worker_sends_as_mira(self):
        src = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text()
        assert "from: miraFrom(env)" in src
        assert "from: env.VOICES_FROM_EMAIL" not in src
        # Guest mail ends with Mira's signature, not the show's name.
        assert "<p>${esc(signOff(show))}</p>" not in src

    def test_no_template_signs_as_the_network(self):
        for p in (ROOT / "templates" / "email").glob("*.j2"):
            text = p.read_text()
            assert "— The Age of AI, Nerra Network" not in text, p.name
            assert not text.rstrip().endswith("Patrick"), p.name
        for p in (ROOT / "shows").glob("*.yaml"):
            assert "sign_off: \"— " not in p.read_text(), p.name

    def test_the_producer_sends_through_mira(self, monkeypatch):
        from pipelines.producer import gmail_client
        src = (ROOT / "pipelines" / "producer" / "gmail_client.py").read_text()
        assert "mailer=MiraMailer.from_env(dry_run=dry_run)" in src
        c = GmailClient(object(), OWNER, mailer=mira_mail.MiraMailer(dry_run=True))
        c.send_reply(thread_id="t", to="sam@reyespr.com", subject="Lena", body_text="Hi Sam")
        assert c.mailer.sent[0]["subject"] == "Re: Lena"


class TestMirasOwnMailbox:
    def test_a_copy_the_main_inbox_also_got_is_left_to_it(self):
        main = GmailClient(object(), OWNER)
        assert inbox.addressed_to_main_inbox({"to": MIRA, "cc": OWNER}, main)
        assert not inbox.addressed_to_main_inbox({"to": MIRA, "cc": ""}, main)

    def test_the_first_run_does_not_answer_old_mail(self):
        assert "newer_than:3d" in inbox.MIRA_INBOX_QUERY


class TestNeverTwice:
    def test_a_thread_patrick_already_answered_is_left_alone(self, gdb, outbox, grok):
        grok.answers["You are Mira, the AI host of Nerra Voices"] = INPUT_PLAN
        t = elliot_thread()
        t["messages"].append(gmail_message("te3", "te", f"Patrick Novak <{OWNER}>",
                                           "Sorry, Mira sent a strange reply.",
                                           "Re: Your Nerra Voices interview", 3000, to=ELLIOT))
        run([t])
        assert not outbox["sent"] and not outbox["patrick"]
