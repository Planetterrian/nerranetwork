"""Oct 1 2026 (Patrick). Jonathan Bautista's interview fell back to a phone
call and dropped. Phone audio is compressed and thin; a computer with
headphones and a good microphone sounds clear and full, and listeners enjoy
those interviews most. Every email leading up to an interview now says so in
the same words, and gives the same three steps into the studio, with the
phone as the fallback rather than the plan.

Oct 27 2026 (Patrick): phone-call interviews are gone altogether. The way out
of a computer that won't cooperate is the same studio in the phone's
BROWSER, or another time; no email offers a call.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))

import common  # noqa: E402
import fire_interviews as fi  # noqa: E402

WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
BRIEF_T = (ROOT / "templates" / "email" / "voices_prep_brief.j2").read_text(encoding="utf-8")
BOOK_T = (ROOT / "templates" / "email" / "voices_booking_confirmation.j2").read_text(encoding="utf-8")
BRIEFS = (ROOT / "pipelines" / "voices" / "generate_briefs.py").read_text(encoding="utf-8")


class _Show:
    name = "Nerra Voices"
    slug = "nerra_voices"

    def studio_url(self, iid):
        return f"https://nerranetwork.com/studio?interview={iid}&show=nerra_voices"


def _iv(**kw):
    base = {"id": "11111111-1111-1111-1111-111111111111", "call_mode": "webrtc",
            "scheduled_at": "2026-10-01T19:45:00+00:00", "guest_timezone": None}
    base.update(kw)
    return base


APP = {"name": "Priyanka Sharma", "email": "p@example.com"}


def test_the_audio_paragraph_says_why():
    a = common.GUEST_AUDIO_HTML
    assert "headphones" in a and "good microphone" in a
    # Oct 27 2026: no comparison with "phone audio" now that the phone's
    # browser is the recommended way out of a stuck computer.
    assert "Phone audio" not in a
    assert "listeners tell us those are the interviews they enjoy most" in a


def test_the_worker_copy_matches():
    flat = common.GUEST_AUDIO_HTML
    for phrase in ("A computer with headphones", "listeners tell us those are the ",
                   "USB microphone is even better"):
        assert phrase in flat and phrase in WORKER
    assert "${GUEST_AUDIO_HTML}" in WORKER and "${studioStepsHtml(studio)}" in WORKER


def test_steps_are_numbered_and_phone_is_the_fallback():
    s = str(common.studio_steps_html("https://x/studio?a=1&b=2"))
    assert "Check my microphone" in s and "Sounds good" in s and "Join your interview" in s
    assert "&amp;b=2" in s
    assert "open the same link on your phone" in s and "pick another time" in s
    assert "not by phone call" in s
    assert "Have Mira call" not in s
    assert "pick another time" not in str(common.studio_steps_html("x", phone_fallback=False))
    # The Worker's copy of the steps says the same.
    assert "pick another time, so nothing is lost. Interviews happen in the studio only" in WORKER


def test_two_hour_reminder_has_audio_steps_and_test_nudge():
    subject, body = fi.reminder_email(_iv(), APP, _Show(), "https://m")
    assert "listeners tell us" in body
    assert "Check my microphone" in body
    assert "&test=1" in body and "Please take 30 seconds now" in body
    assert "Pacific" in body or "PT" in body or "PDT" in body


def test_two_hour_reminder_thanks_a_guest_who_passed():
    _, body = fi.reminder_email(_iv(setup_check={"mic": "ok"}), APP, _Show(), "")
    assert "Your setup test passed" in body
    assert "Please take 30 seconds now" not in body


def test_studio_open_email_repeats_the_steps():
    _, body = fi.reminder_email(_iv(), APP, _Show(), "", soon=True)
    assert "Check my microphone" in body and "Headphones on" in body


def test_a_row_still_marked_phone_gets_the_studio():
    # Oct 27 2026: no interview is a phone interview any more.
    _, body = fi.reminder_email(_iv(call_mode="pstn"), APP, _Show(), "")
    assert "Check my microphone" in body and "I'll call" not in body
    subject, soon = fi.reminder_email(_iv(call_mode="pstn"), APP, _Show(), "", soon=True)
    assert "studio is open" in subject and "call your phone" not in soon


def test_brief_and_booking_templates_carry_it():
    assert "{{ audio_html }}" in BRIEF_T and "{{ steps_html }}" in BRIEF_T
    assert "audio_html=guest_audio_html()" in BRIEFS and "steps_html=studio_steps_html(" in BRIEFS
    assert "{{ audio_html }}" in BOOK_T


def test_sms_mentions_the_sound():
    src = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text(encoding="utf-8")
    assert "join from a computer with headphones and a good mic" in src
    assert "I'll be calling" not in src
