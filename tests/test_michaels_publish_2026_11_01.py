"""Michael Kamins' published episode (Ep15, Nov 1 2026), reviewed.

He chose "Come back in about six months" on the review page and the
publish-day mail told him "I have put February 2027 in the calendar", the
network's three-month default, because ``published_email`` never read
``guest_followup``. The guest's answer decides the invitation now.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))

import publish_episode as pe  # noqa: E402

WHEN = dt.date(2026, 11, 1)


def test_six_months_is_counted_from_the_day_he_chose_it():
    html = pe.return_invitation_html(
        {"guest_followup": "return_6", "guest_followup_at": "2026-10-30T19:09:56.965+00:00"}, WHEN)
    assert "April 2027" in html and "six months" in html
    assert "February 2027" not in html


def test_a_year_and_no_answer():
    assert "October 2027" in pe.return_invitation_html(
        {"guest_followup": "return_12", "guest_followup_at": "2026-10-30T19:09:56Z"}, WHEN)
    assert "February 2027" in pe.return_invitation_html({}, WHEN)


def test_nothing_for_now_gets_no_date():
    assert pe.return_invitation_html({"guest_followup": "none"}, WHEN) == ""
    other = pe.return_invitation_html({"guest_followup": "return_other"}, WHEN)
    assert "another time" in other and "2027" not in other


def test_the_mail_carries_the_guests_answer():
    class Show:
        name = "The Age of AI"
        short_label = "Age of AI"
        page_url = "https://nerranetwork.com/age-of-ai.html"
        base_url = "https://nerranetwork.com"
        apple_url = spotify_url = ""
        audio_subdir = "digests/age_of_ai_test_nowhere"

        @staticmethod
        def post_url(n):
            return f"https://nerranetwork.com/blog/age_of_ai/ep{n:03d}.html"
    pe_kits, pe_sig = pe.kits_html, pe.mira_signature_html
    pe.kits_html = lambda *a, **k: ""
    pe.mira_signature_html = lambda *a, **k: ""
    try:
        _, body = pe.published_email(
            Show, {"name": "Michael Kamins"},
            {"guest_followup": "return_6", "guest_followup_at": "2026-10-30T19:09:56Z"},
            15, when=WHEN)
    finally:
        pe.kits_html, pe.mira_signature_html = pe_kits, pe_sig
    assert "April 2027" in body and "February 2027" not in body


def test_a_chapter_title_opens_on_a_capital(monkeypatch):
    import engine.interviews as iv
    monkeypatch.setattr(iv, "supported_chapters", lambda chs, t: chs)
    out = pe.vouched_chapters({"chapter_markers": [
        {"start": 0, "title": "the document that decided a person's worth in six seconds"},
        {"start": 594, "title": "Conflict as a source of creativity"},
        {"start": 900, "title": "iPhone hiring"}], "transcript_cleaned": "x"})
    assert [c["title"] for c in out] == [
        "The document that decided a person's worth in six seconds",
        "Conflict as a source of creativity", "iPhone hiring"]
    assert out[0]["start"] == 0


def test_the_transcript_note_says_the_edit_is_edited():
    src = (ROOT / "pipelines" / "voices" / "publish_episode.py").read_text(encoding="utf-8")
    body = src.split("def write_episode_digest")[1].split("\ndef ")[0]
    assert 'EDIT_TRANSCRIPT_NOTE if pkg.get("edit_transcript") else TRANSCRIPT_NOTE' in body
    assert "edited for length" in pe.EDIT_TRANSCRIPT_NOTE
    assert "approve, cut from or refuse before publication" in pe.EDIT_TRANSCRIPT_NOTE
    assert "as it was recorded" not in pe.EDIT_TRANSCRIPT_NOTE
