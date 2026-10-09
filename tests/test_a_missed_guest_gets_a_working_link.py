"""Oct 9 2026 (Piper Martz). Piper missed her closing session and Mira's
"sorry we missed each other" email went out with a link that went nowhere:
the fire workflow never had CALCOM_BOOKING_URL, so the href was empty, and a
closing session books on its own page anyway. She wrote back that the link
was broken. The booking page now has a live default, a closing session gets
the closing page and its own words, and an empty link is never sent.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))

import common  # noqa: E402
import fire_interviews as fi  # noqa: E402

FIRE_WF = (ROOT / ".github" / "workflows" / "nerra_voices_fire_interview.yml").read_text(encoding="utf-8")
POST = (ROOT / "pipelines" / "voices" / "post_interview.py").read_text(encoding="utf-8")
CLOSING = "https://cal.com/patrick-novak-lkcqo4/age-of-ai-closing"


def _clear(monkeypatch):
    for k in ("CALCOM_BOOKING_URL", "CALCOM_BOOKING_URL_NERRA_VOICES", "CALCOM_BOOKING_URL_CLOSING"):
        monkeypatch.delenv(k, raising=False)


def test_the_booking_link_is_never_empty(monkeypatch):
    _clear(monkeypatch)
    assert common.booking_url("age_of_ai").endswith("/age-of-ai-interview")
    assert common.booking_url("nerra_voices").endswith("/nerra-voices-interview")
    assert common.booking_url("age_of_ai", closing=True) == CLOSING
    assert common.booking_url("") .startswith("https://cal.com/")
    monkeypatch.setenv("CALCOM_BOOKING_URL", "https://cal.com/x/y")
    assert common.booking_url("age_of_ai") == "https://cal.com/x/y"


def test_a_missed_closing_session_points_at_the_closing_page(monkeypatch):
    _clear(monkeypatch)
    show = common.show_for({"show": "age_of_ai"}, {})
    iv = {"id": "i1", "session_kind": "closing"}
    app = {"name": "Piper Martz", "topics": ["agentic AI in customer engagement"]}
    subject, html = common.missed_email(iv, app, show, "Piper")
    assert "closing session" in subject
    assert f'href="{CLOSING}"' in html
    flat = " ".join(html.split())
    assert "last word" in flat and "agentic AI in customer engagement" in flat
    assert 'href=""' not in html


def test_a_missed_interview_says_what_it_was_about(monkeypatch):
    _clear(monkeypatch)
    show = common.show_for({"show": "age_of_ai"}, {})
    subject, html = common.missed_email({"id": "i1"}, {"pitch_summary": "Robots in kitchens"}, show, "Sam")
    assert subject == f"Sorry we missed each other: pick a new time for {show.name}"
    assert "age-of-ai-interview" in html and "Robots in kitchens" in " ".join(html.split())
    assert 'href=""' not in html


def test_without_a_link_the_template_asks_for_a_reply():
    html = common.render_email("voices_interview_reminder.j2", show="age_of_ai",
                               guest_name="Sam", missed=True, booking_url="")
    assert 'href=""' not in html and "Reply to this email" in html


def test_the_studio_no_show_sends_the_closing_link(monkeypatch):
    _clear(monkeypatch)
    now = dt.datetime.now(dt.timezone.utc)
    iv = {"id": "i1", "application_id": "a1", "status": "briefed", "call_mode": "webrtc",
          "scheduled_at": (now - dt.timedelta(hours=1)).isoformat(), "show": "age_of_ai",
          "session_kind": "closing"}
    mails = []

    def select(table, q):
        if table == "interviews":
            return [iv]
        if table == "interview_runs":
            return [{"id": "r1", "status": "awaiting_guest"}]
        return [{"id": "a1", "name": "Piper Martz", "email": "p@x.com",
                 "publicist_email": "press@x.com"}]

    monkeypatch.setattr(fi, "sb_select", select)
    monkeypatch.setattr(fi, "sb_update", lambda *a, **k: None)
    monkeypatch.setattr(fi, "notify_operator", lambda *a, **k: None)
    monkeypatch.setattr(fi, "send_email", lambda to, subj, html, **k: mails.append((to, subj, html, k)))
    assert fi.sweep_browser_no_shows() == 1
    to, subj, html, k = mails[0]
    assert CLOSING in html and 'href=""' not in html
    assert k.get("cc_operator") is True and "press@x.com" in k.get("cc", [])


def test_the_fire_workflow_has_the_booking_pages():
    assert "CALCOM_BOOKING_URL: ${{ secrets.CALCOM_BOOKING_URL }}" in FIRE_WF
    assert "CALCOM_BOOKING_URL_NERRA_VOICES: ${{ secrets.CALCOM_BOOKING_URL_NERRA_VOICES }}" in FIRE_WF


def test_the_phone_no_show_uses_the_same_mail():
    assert "missed_email(interview, app, show, first_name(app))" in POST
    assert 'os.environ.get("CALCOM_BOOKING_URL", "")' not in POST


def test_the_two_hour_reminder_copies_the_team_and_says_what(monkeypatch):
    sent = []
    monkeypatch.setattr(fi, "send_email", lambda to, subj, html, **k: sent.append((to, subj, html, k)))

    class _Show:
        name = "The Age of AI"
        slug = "age_of_ai"

        def studio_url(self, iid):
            return f"https://nerranetwork.com/studio?interview={iid}"

    iv = {"id": "i1", "call_mode": "webrtc", "scheduled_at": "2026-10-09T18:00:00+00:00"}
    app = {"name": "Piper Martz", "email": "p@x.com", "publicist_email": "press@x.com",
           "topics": ["closing the gender gap in AI adoption"]}
    fi.send_guest_reminder(iv, app, _Show(), "https://m")
    to, subj, html, k = sent[0]
    assert k.get("cc_operator") is True and "press@x.com" in k.get("cc", [])
    assert "What we'll talk about" in html and "gender gap" in html
    fi.send_guest_reminder(dict(iv, session_kind="closing"), app, _Show(), "https://m")
    assert "closing session" in sent[1][1]
    fi.send_guest_reminder(iv, app, _Show(), "", soon=True)
    assert not sent[2][3].get("cc_operator")


def test_each_show_carries_its_own_pages(monkeypatch):
    _clear(monkeypatch)
    aoa, nv = common.resolve_show("age_of_ai"), common.resolve_show("nerra_voices")
    assert aoa.booking_url and aoa.closing_booking_url == CLOSING
    assert nv.booking_url.endswith("/nerra-voices-interview")
    assert common.booking_url(nv, closing=True) == CLOSING
    monkeypatch.setenv("CALCOM_BOOKING_URL_NERRA_VOICES", "https://cal.com/x/nv")
    assert common.booking_url("nerra_voices") == "https://cal.com/x/nv"
