"""Oct 1 2026, Jonathan Bautista. He had the studio open at 9:30 AM PT,
never got past the microphone check that unlocks Join, and emailed "I'm in
the room but no one is joining?". Nothing had reached Mira, so nobody on our
side knew until he wrote. Mira called his phone and the interview went ahead.

What changes, and these tests hold it in place:
  1. Until the guest is in, the studio says plainly "You're not in the
     interview yet", lists the two steps, and offers the phone from the start.
  2. Once the slot has started it counts the minutes.
  3. Three minutes after the start the page reports the guest as stuck, once.
  4. The Worker emails Patrick once, with a signed link that switches the
     interview to a phone call (GET confirms, POST dials: mail scanners
     prefetch links).
  5. A browser that refuses the microphone gets the phone offer too.

Oct 27 2026: phone-call interviews were retired. "The phone" in 1 and 5 is
now the same studio in the phone's BROWSER, plus a button to pick another
time; Patrick's one-click link (4) sends the guest their studio link for
their phone instead of dialling them.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")


def _body(src: str, start: str, end: str) -> str:
    s = src[src.index(start):]
    return s[:s.index(end)]


class TestTheStudioSaysTheGuestIsNotIn:
    def test_banner_and_steps(self):
        assert 'id="notIn"' in STUDIO
        assert "You're not in the interview yet." in STUDIO
        assert 'id="notInStep1"' in STUDIO and 'id="notInStep2"' in STUDIO

    def test_phone_browser_and_another_time_offered_from_the_start_and_on_error(self):
        assert 'id="troubleTop"' in STUDIO and 'id="troubleErr"' in STUDIO
        assert 'id="troubleSetup"' in STUDIO and 'id="troubleCall"' in STUDIO
        assert '["Top", "Setup", "Call", "Err"].forEach(troubleBox);' in STUDIO
        box = _body(STUDIO, "function troubleBox(where)", '["Top", "Setup", "Call", "Err"].forEach(troubleBox);')
        assert "Join from my phone instead" in box and "Pick another time" in box
        assert "/studio-reschedule" in box and "/studio-text" in box
        assert "studio-phone" not in STUDIO and "Have Mira call" not in STUDIO

    def test_counts_minutes_after_start(self):
        upd = _body(STUDIO, "function updateNotIn()", "function stopNotIn()")
        assert "minutesLate()" in upd
        assert "Mira is waiting, but you're not in the interview yet." in upd
        assert "if (s.scheduled_at) scheduledAt = Date.parse(s.scheduled_at);" in STUDIO

    def test_reports_stuck_once_three_minutes_in(self):
        assert "var STUCK_AFTER_MS = 3 * 60 * 1000;" in STUDIO
        tick = _body(STUDIO, "function notInTick()", "function startNotIn()")
        assert "if (!stuckReported" in tick and "stuckReported = true;" in tick
        assert "stuck: true" in tick

    def test_stops_once_connected_and_not_in_test_or_host(self):
        assert "everConnected = true; stopNotIn();" in STUDIO
        start = _body(STUDIO, "function startNotIn()", "// ---- 3. Join")
        assert "if (isHost || testMode || notInTimer) return;" in start
        assert "#consentNote, #notIn" in STUDIO

    def test_microphone_refused_offers_phone(self):
        assert "micAccess = false;" in STUDIO
        assert 'getElementById("troubleErr").classList.remove("hidden")' in STUDIO


class TestPatrickHearsAboutAStuckGuest:
    def test_worker_handles_stuck_once(self):
        chk = _body(WORKER, "async function handleStudioCheck(", "/** POST /voices/studio-silence")
        assert 'body?.stuck === true && !test && record.role === "guest"' in chk
        assert "stuck_alerted_at" in chk
        assert "if (!alertedBefore) await alertStuckGuest(" in chk

    def test_email_has_signed_link_for_their_phone(self):
        alert = _body(WORKER, "async function alertStuckGuest(", "async function handleStudioCheck(")
        assert "textGuestLink(env, iv.id)" in alert
        assert "phone call" not in alert and "callGuestLink" not in WORKER
        assert "has the studio open but isn't in the interview" in alert
        assert "pacificTime(iv.scheduled_at)" in alert

    def test_text_guest_confirms_before_sending(self):
        h = _body(WORKER, "async function handleTextGuest(", "async function archivePackage(")
        assert "sig !== await textGuestSig(env, interviewId)" in h
        assert 'if (req.method !== "POST")' in h
        assert '<form method="post">' in h
        assert "handleStudioText(" in h
        assert 'path === "/voices/admin/text-guest") return handleTextGuest(req, env);' in WORKER
        # The old call link answers 410 and dials nobody.
        assert 'path === "/voices/admin/call-guest") return handleCallGuestRetired();' in WORKER

    def test_archive_token_unchanged(self):
        assert 'return adminSig(env, "nerra-archive");' in WORKER
