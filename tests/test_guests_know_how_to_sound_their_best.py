"""Oct 1 2026 (Patrick). Jonathan Bautista's interview fell back to a phone
call and dropped. Phone audio is compressed and thin; a computer with
headphones and a good microphone sounds clear and full, and listeners enjoy
those interviews most. Every email leading up to an interview now says so in
the same words, and gives the same three steps into the studio, with the
phone as the fallback rather than the plan.
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
    assert "Phone audio is compressed" in a
    assert "headphones" in a and "good microphone" in a
    assert "listeners tell us those are the interviews they enjoy most" in a


def test_the_worker_copy_matches():
    flat = common.GUEST_AUDIO_HTML
    for phrase in ("Phone audio is compressed", "listeners tell us those are the interviews ",
                   "USB microphone is even better"):
        assert phrase in flat and phrase in WORKER
    assert "${GUEST_AUDIO_HTML}" in WORKER and "${studioStepsHtml(studio)}" in WORKER


def test_steps_are_numbered_and_phone_is_the_fallback():
    s = str(common.studio_steps_html("https://x/studio?a=1&b=2"))
    assert "Check my microphone" in s and "Sounds good" in s and "Join your interview" in s
    assert "&amp;b=2" in s
    assert "Have Mira call my phone" in s
    assert "Have Mira call my phone" not in str(common.studio_steps_html("x", phone_fallback=False))


def test_two_hour_reminder_has_audio_steps_and_test_nudge():
    subject, body = fi.reminder_email(_iv(), APP, _Show(), "https://m")
    assert "Phone audio is compressed" in body
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


def test_phone_mode_still_invites_the_computer():
    _, body = fi.reminder_email(_iv(call_mode="pstn"), APP, _Show(), "")
    assert "sounds noticeably better than a phone line" in body


def test_brief_and_booking_templates_carry_it():
    assert "{{ audio_html }}" in BRIEF_T and "{{ steps_html }}" in BRIEF_T
    assert "audio_html=guest_audio_html()" in BRIEFS and "steps_html=studio_steps_html(" in BRIEFS
    assert "{{ audio_html }}" in BOOK_T


def test_sms_mentions_the_sound():
    src = (ROOT / "pipelines" / "voices" / "fire_interviews.py").read_text(encoding="utf-8")
    assert "phone audio is much thinner" in src
