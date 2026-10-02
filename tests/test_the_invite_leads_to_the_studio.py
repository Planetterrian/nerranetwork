"""Oct 1 2026. Jonathan Bautista ("I'm in the room but no one is joining")
and Jason Fishman ("Says waiting for others to join. I am in") both opened
the meeting from their calendar invite. Its location was Cal.com's own video
room, empty by design, so each sat waiting while Mira waited in the studio,
and both interviews fell back to a phone line. The invite now carries the
guest's studio link, and the event types' default location is a join page
that finds the guest's studio from the address they booked with.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")


def _body(start: str, end: str) -> str:
    s = WORKER[WORKER.index(start):]
    return s[:s.index(end)]


def test_booking_puts_the_studio_link_in_the_invite():
    assert "await setCalendarLocation(env, show, String(p.uid ?? p.bookingUid" in WORKER
    loc = _body("async function setCalendarLocation(", "/** GET/POST /voices/join")
    assert "/v2/bookings/${encodeURIComponent(uid)}/location" in loc
    assert '{ location: { type: "link", link: studio } }' in loc
    assert "CAL_API_KEY" in loc and "slack(" in loc


def test_join_page_finds_the_studio():
    j = _body("async function handleJoin(", "async function handleCallGuest(")
    assert "Response.redirect(studio, 302)" in j
    assert "minsToStart <= 30" in j
    assert "publicist_email.ilike" in j
    # Far from the start, the link goes to the guest's inbox, not the browser.
    assert "email(env, String(app.email)" in j
    assert 'path === "/voices/join") return handleJoin(req, env);' in WORKER
