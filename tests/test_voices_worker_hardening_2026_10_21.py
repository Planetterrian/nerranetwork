"""Oct 21 2026 — the Voices Worker hardening from the Age of AI review.

String-level guards on ``workers/voices/src/index.ts`` (the pattern of
``test_voices_worker_routing.py``; the Worker's vitest suite under
``workers/voices/test`` exercises the behaviour and is run by hand with
``npx vitest run``). Each item here is one the review found fail-open or
unsafe: unsigned webhooks, any review link deciding any lesson, a studio
phone button that could redial a finished interview, gate-2 housekeeping
that stopped on one failed email, a status written before the dispatch
that publishes, a /join that opened a studio to whoever typed an address,
and three emails that said "ten minutes" for a studio that opens fifteen.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
README = (ROOT / "workers" / "voices" / "README.md").read_text(encoding="utf-8")
WRANGLER = (ROOT / "workers" / "voices" / "wrangler.toml").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    """The body of one top-level function (up to the next top-level one)."""
    m = re.search(rf"\n(?:export )?(?:async )?function {re.escape(name)}\(", WORKER)
    assert m, f"{name} missing"
    rest = WORKER[m.end():]
    nxt = re.search(r"\n(?:export )?(?:async )?function \w+\(|\n// -{10,}", rest)
    return rest[: nxt.start()] if nxt else rest


# ---------------------------------------------------------------------------
# Signed webhooks
# ---------------------------------------------------------------------------

def test_webhook_signature_contract_is_named():
    assert 'export const SIGNATURE_HEADER = "X-Voices-Signature";' in WORKER
    assert "VOICES_WEBHOOK_SECRET?: string;" in WORKER
    assert "CALCOM_WEBHOOK_SECRET?: string;" in WORKER
    # HMAC-SHA256 over the raw body, constant-time compare, sha256= tolerated
    body = _fn("hmacHex")
    assert '{ name: "HMAC", hash: "SHA-256" }' in body
    ok = _fn("signatureOk")
    assert "tokenEquals(given, want)" in ok
    assert 'replace(/^sha256=/i, "")' in ok


def test_scenario_routes_require_the_signature_when_the_secret_is_set():
    for handler in ("handleInterviewComplete", "handleLegEvent", "handleNarrationTake"):
        body = _fn(handler)
        assert "readSignedJson(req, env, true)" in body, f"{handler} must verify the room's signature"
        assert "if (denied) return denied;" in body
    silence = _fn("handleStudioSilence")
    assert "readSignedJson(req, env, false)" in silence
    assert 'body?.source === "scenario"' in silence and '"signature required"' in silence


def test_browser_routes_keep_their_existing_gates():
    # The studio page cannot hold a secret: its routes are unchanged.
    for handler in ("handleStudioCheck", "handleUploadDone"):
        assert "readSignedJson" not in _fn(handler), f"{handler} is a browser route"
    assert "webhookVerdict" not in _fn("handleUploadChunk")


def test_unsigned_is_accepted_while_the_worker_has_no_secret():
    verdict = _fn("webhookVerdict")
    assert 'if (!secret) {' in verdict and 'return "ok";' in verdict
    assert "unsignedWarned" in verdict


def test_calcom_signature_is_verified_when_configured():
    assert 'export const CALCOM_SIGNATURE_HEADER = "X-Cal-Signature-256";' in WORKER
    assert "readCalComJson(req, env)" in _fn("handleCalComBooked")


def test_secrets_are_documented():
    for doc in (WRANGLER, README):
        assert "VOICES_WEBHOOK_SECRET" in doc and "CALCOM_WEBHOOK_SECRET" in doc
    assert "__VOICES_WEBHOOK_SECRET__" in WRANGLER
    assert "webhook_secret: !!(env.VOICES_WEBHOOK_SECRET" in _fn("handleHealth")


# ---------------------------------------------------------------------------
# Lesson ownership
# ---------------------------------------------------------------------------

def test_lesson_decision_checks_ownership():
    body = _fn("handleLessonDecision")
    assert "lessonDecisionAllowed(lesson, pkg)" in body
    assert "requireAdmin(req, env)" in body
    allowed = _fn("lessonDecisionAllowed")
    assert '=== "network") return false;' in allowed
    assert "String(lesson.interview_id) === String(pkg.interview_id)" in allowed
    # the review page shows the standing list's retire buttons to the admin only
    review = _fn("handleAdminReview")
    assert "const isAdmin = !requireAdmin(req, env);" in review
    assert "(isAdmin ? `<br><button" in review


# ---------------------------------------------------------------------------
# Studio phone, gate 2, dispatch ordering, /join
# ---------------------------------------------------------------------------

def test_studio_phone_dials_only_a_live_interview():
    assert 'export const LIVE_INTERVIEW_STATUSES = new Set(["scheduled", "briefed", "in_progress"]);' in WORKER
    assert "if (!LIVE_INTERVIEW_STATUSES.has(String(iv.status)))" in _fn("handleStudioPhone")


def test_gate2_housekeeping_isolates_each_package():
    body = _fn("gate2Housekeeping")
    assert "try {" in body and "await gate2Package(env, pkg, now);" in body
    assert "catch (err: any)" in body
    pkg = _fn("gate2Package")
    assert 'String(interview.status) === "approved"' in pkg, "retries a dispatch that failed"
    assert "approveAndDispatch(" in pkg


def test_production_is_dispatched_before_the_package_is_marked_approved():
    body = _fn("approveAndDispatch")
    assert body.index('"interview-approved-by-guest"') < body.index('status: "approved_by_guest"')
    submit = _fn("handleGuestReviewSubmit")
    assert "approveAndDispatch(" in submit
    assert "dispatched: false" in submit
    # the old order is gone
    assert '{ status: "approved_by_guest", guest_reviewed_at: now });\n    await sb(env, "PATCH", `interviews' not in WORKER


def test_join_opens_the_studio_only_for_the_guests_own_token():
    body = _fn("handleJoin")
    assert "manageInterview(env, token)" in body
    assert "String(own.id) === String(iv.id)" in body
    assert "if (minsToStart <= 30) return Response.redirect" not in body
    assert "emailed your personal" in body


def test_gate1_approve_is_idempotent():
    body = _fn("handleEditorialDecision")
    assert '["approved_by_patrick", "approved_by_guest", "published"].includes(String(before.status))' in body
    assert "already: before.status" in body


# ---------------------------------------------------------------------------
# The copy, the survey, redaction windows, the edit's transcript
# ---------------------------------------------------------------------------

def test_the_emails_say_fifteen_minutes():
    assert 'export const STUDIO_OPENS_BEFORE_TEXT = "fifteen minutes";' in WORKER
    assert "const STUDIO_OPENS_BEFORE_MS = 15 * 60 * 1000;" in WORKER
    assert not re.search(r"ten minutes before", WORKER.replace('"ten minutes"', "")), \
        "an email still says ten minutes"
    assert WORKER.count("${STUDIO_OPENS_BEFORE_TEXT}") >= 3


def test_survey_route_and_columns():
    assert re.search(r"path\.match\(/\^\\/voices\\/survey\\/", WORKER)
    for h in ("handleSurveyPage", "handleSurveySubmit", "pkgBySurveyToken"):
        assert f"function {h}(" in WORKER
    submit = _fn("handleSurveySubmit")
    assert "survey_answered_at: pkg.survey_answered_at ?? now" in submit
    answers = _fn("surveyAnswers")
    for col in ("survey_rating", "survey_change", "survey_recommend"):
        assert col in answers
    assert "survey_token=eq." in _fn("pkgBySurveyToken")
    page = _fn("handleSurveyPage")
    assert "compare with a human host" in page
    assert "One thing you would change" in page
    assert "recommend it to a peer" in page


def test_review_page_shows_the_edit_transcript_and_stores_windows():
    # The page carries inline JS with its own `function` lines, so slice it
    # between the two handlers rather than to the next top-level function.
    page = WORKER[WORKER.index("async function handleGuestReviewPage("):
                  WORKER.index("export function reviewTranscriptHtml(")]
    assert "pkg.edit_transcript" in page
    assert "transcript of the edit a listener will hear" in page
    assert "markedWindows()" in page
    submit = _fn("handleGuestReviewSubmit")
    assert "guest_redaction_windows: mergeWindows(existing, windows)" in submit
    assert "redactionWindows(body?.windows)" in submit
    lines = _fn("transcriptLines")
    assert "REDACTION_LINE_DEFAULT_SEC" in lines
    assert "export const REDACTION_LINE_DEFAULT_SEC = 15;" in WORKER


def test_worker_has_a_vitest_suite():
    pkg = (ROOT / "workers" / "voices" / "package.json").read_text(encoding="utf-8")
    assert '"test": "vitest run"' in pkg
    assert (ROOT / "workers" / "voices" / "test" / "hardening.test.ts").exists()
    assert (ROOT / "workers" / "voices" / "vitest.config.ts").exists()
