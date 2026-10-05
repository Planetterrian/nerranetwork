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

    def test_phone_offered_from_the_start_and_on_error(self):
        assert 'id="phoneBtnTop"' in STUDIO and 'id="phoneBtnErr"' in STUDIO
        assert '["Setup", "Call", "Top", "Err"].forEach' in STUDIO
        assert '"phoneMsg" + where' in STUDIO

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
        assert 'getElementById("phoneBoxErr").classList.remove("hidden")' in STUDIO


class TestPatrickHearsAboutAStuckGuest:
    def test_worker_handles_stuck_once(self):
        chk = _body(WORKER, "async function handleStudioCheck(", "/** POST /voices/studio-silence")
        assert 'body?.stuck === true && !test && record.role === "guest"' in chk
        assert "stuck_alerted_at" in chk
        assert "if (!alertedBefore) await alertStuckGuest(" in chk

    def test_email_has_signed_phone_link(self):
        alert = _body(WORKER, "async function alertStuckGuest(", "async function handleStudioCheck(")
        assert "callGuestLink(env, iv.id)" in alert
        assert "has the studio open but isn't in the interview" in alert
        assert "pacificTime(iv.scheduled_at)" in alert

    def test_call_guest_confirms_before_dialing(self):
        h = _body(WORKER, "async function handleCallGuest(", "async function archivePackage(")
        assert "sig !== await callGuestSig(env, interviewId)" in h
        assert 'if (req.method !== "POST")' in h
        assert '<form method="post">' in h
        assert 'by: "patrick"' in h
        assert 'path === "/voices/admin/call-guest") return handleCallGuest(req, env);' in WORKER

    def test_archive_token_unchanged(self):
        assert 'return adminSig(env, "nerra-archive");' in WORKER
