"""Oct 2 2026. Jonathan Bautista and Jason Fishman both wrote during their
slots that they were in a room where nobody came (the calendar's video
room). Both were held for Patrick. Now Mira answers at once, from facts,
with the studio link, the steps, the phone's browser and, last, a call; and
the inbox runs every five minutes while an interview is live.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from pipelines.producer import guest_reply as g

ROOT = Path(__file__).resolve().parents[1]
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")


class FakeGmail:
    user = "mira@nerranetwork.com"

    def __init__(self):
        self.sent, self.labels = [], []

    def send_reply(self, **kw):
        self.sent.append(kw)

    def add_label(self, tid, label):
        self.labels.append(label)

    def create_draft(self, **kw):
        return True


def _guest(minutes_from_now):
    at = (datetime.now(timezone.utc) + timedelta(minutes=minutes_from_now)).isoformat()
    return {"app": {"id": "a1", "name": "Jason Fishman", "email": "j@x.com", "show": "age_of_ai"},
            "interviews": [{"id": "588ad174-42da-4766-9c0d-aed0bc5cf4bf", "status": "briefed",
                            "scheduled_at": at, "show": "age_of_ai", "call_mode": "webrtc"}]}


def _run(monkeypatch, text, minutes):
    sent_mail = []
    monkeypatch.setattr(g, "send_email", lambda *a, **k: sent_mail.append(a))
    monkeypatch.setattr(g, "plan", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no model call")))
    monkeypatch.setattr("pipelines.producer.inbox.newest_is_inbound", lambda t, u: True)
    gm = FakeGmail()
    thread = {"id": "t1", "subject": "Re: studio", "messages": []}
    inbound = {"from_email": "j@x.com", "body": text}
    policy = SimpleNamespace(mode="auto", processed_label="p", hold_label="h")
    line = g.handle_guest_reply(thread=thread, inbound=inbound, guest=_guest(minutes),
                                gmail=gm, policy=policy, dry_run=False)
    return line, gm, sent_mail


def test_answered_at_once_during_the_slot(monkeypatch):
    line, gm, mail = _run(monkeypatch, "Says waiting for others to join. I am in\n\nTalk soon,\nJason", -8)
    assert line["action"] == "send" and line["intent"] == "live_join_help"
    body = gm.sent[0]["body_text"]
    assert "588ad174-42da-4766-9c0d-aed0bc5cf4bf" in body
    assert "Check my microphone" in body and "phone's browser" in body
    assert "isn't my studio" in body
    assert mail and "couldn't get into the studio" in mail[0][1]


def test_not_triggered_outside_the_slot():
    assert g.live_interview(_guest(24 * 60)) is None
    assert g.live_interview(_guest(-8)) is not None


def test_quoted_text_does_not_trigger():
    assert not g._LIVE_TROUBLE.search(g.own_words("Thanks!\nOn Thu, Mira wrote:\n> I'm here and ready"))


def test_inbox_runs_every_five_minutes_while_live():
    assert 'if (await interviewIsLive(env)) await dispatch(env, "producer-tick", { source: "live-interview" });' in WORKER


def test_phone_browser_comes_before_a_call():
    studio = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")
    assert "Join from my phone instead" in studio
    assert "Last resort: have Mira call my phone" in studio
    assert 'path === "/voices/studio-text") return handleStudioText(req, env);' in WORKER
    assert "SendSmsMessage" in WORKER
