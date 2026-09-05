"""Drift guards for the September 2026 show routing in the Voices Worker.

The Age of AI got a sister show, Nerra Voices, on the same Worker, tables
and studio page. These are string-level assertions on the Worker source
and the static pages (the pattern tests/test_scheduling_punctuality.py
uses on the scheduler Worker): both apply pages post their `show`, the
Worker carries a SHOWS map for both slugs, the Cal.com lookup filters by
show, the booking link per show has a fallback, every studio URL carries
`&show=`, and the shared studio page reads `show` from the query string.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
README = (ROOT / "workers" / "voices" / "README.md").read_text(encoding="utf-8")
WRANGLER = (ROOT / "workers" / "voices" / "wrangler.toml").read_text(encoding="utf-8")
STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")
APPLY_PAGES = {
    "age_of_ai": (ROOT / "age-of-ai-apply.html").read_text(encoding="utf-8"),
    "nerra_voices": (ROOT / "nerra-voices-apply.html").read_text(encoding="utf-8"),
}

APPLY_URL = "https://api.nerranetwork.com/voices/apply"


# ---------------------------------------------------------------------------
# Apply pages
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slug", sorted(APPLY_PAGES))
def test_apply_page_posts_show_to_worker(slug):
    page = APPLY_PAGES[slug]
    assert APPLY_URL in page, f"{slug} apply page must post to the Worker"
    assert f"show: '{slug}'" in page, f"{slug} apply page must send show={slug}"
    # The other show's slug must not leak into the payload.
    other = (set(APPLY_PAGES) - {slug}).pop()
    assert f"show: '{other}'" not in page


def test_nerra_voices_apply_page_branding():
    page = APPLY_PAGES["nerra_voices"]
    assert "<title>Apply to be a guest — Nerra Voices" in page
    assert "Real people. Real work. AI host." in page
    assert "Mira, an AI, asks the questions. Real people answer." in page
    assert "#0F766E" in page, "brand colour from shows/nerra_voices.yaml"
    assert 'href="nerra-voices.html"' in page
    assert "assets/covers/nerra-voices.jpg" in page
    # No Age of AI residue.
    assert "Age of AI" not in page
    assert "#7C3AED" not in page


def test_age_of_ai_apply_page_unchanged_otherwise():
    page = APPLY_PAGES["age_of_ai"]
    assert "The Age of AI" in page and "#7C3AED" in page


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def _shows_block() -> str:
    m = re.search(r"export const SHOWS: Record<ShowSlug, Show> = \{(.*?)\n\};", WORKER, re.S)
    assert m, "SHOWS map missing from index.ts"
    return m.group(1)


def test_worker_shows_map_has_both_slugs():
    block = _shows_block()
    for slug in ("age_of_ai", "nerra_voices"):
        assert f'slug: "{slug}"' in block, f"SHOWS map missing {slug}"
    assert 'brandColor: "#7C3AED"' in block
    assert 'brandColor: "#0F766E"' in block
    assert 'applyPage: "nerra-voices-apply.html"' in block
    assert block.count('studioPage: "age-of-ai-studio.html"') == 2, "studio page is shared"
    for helper in ("function showFor(", "function isShow(", "function studioUrl(", "function bookingUrl("):
        assert helper in WORKER, f"missing helper {helper}"


def test_worker_routes_triage_reassign():
    assert 'path === "/voices/triage-reassign"' in WORKER
    assert "handleTriageReassign" in WORKER
    body = WORKER.split("async function handleTriageReassign")[1].split("\nasync function")[0]
    assert "requireAdmin(req, env)" in body, "reassign must be admin-gated"
    assert "isShow(body.show)" in body
    assert "{ show: body.show }" in body


def test_worker_calcom_lookup_filters_by_show():
    body = WORKER.split("async function handleCalComBooked")[1].split("\nasync function")[0]
    assert "show=eq." in body, "approved-application lookup must filter by show"
    assert "showFromCalCom(" in body
    assert 'status: "scheduled", show: show.slug' in body, "interview insert must include show"
    assert "CALCOM_EVENT_SLUG_NERRA_VOICES" in WORKER
    assert "CALCOM_EVENT_SLUG_AGE_OF_AI" in WORKER
    assert 'slug.includes("voices")' in WORKER


def test_worker_booking_url_falls_back():
    body = WORKER.split("function bookingUrl(")[1].split("\n}")[0]
    assert "CALCOM_BOOKING_URL_NERRA_VOICES" in body
    assert "return env.CALCOM_BOOKING_URL;" in body
    assert "You're invited — book your ${show.name} interview" in WORKER


def test_worker_apply_accepts_show_and_merges_invited():
    body = WORKER.split("async function handleApply")[1].split("\nasync function")[0]
    assert "show: show.slug" in body, "insert whitelist must include show"
    assert "status=eq.invited" in body
    assert '{ status: "pending" }' in body


def test_worker_studio_urls_carry_show():
    assert 'age-of-ai-studio.html?interview=' not in WORKER, \
        "studio URLs must go through studioUrl(show, id) with &show="
    assert "?interview=${interviewId}&show=${show.slug}" in WORKER


def test_worker_no_hardcoded_show_strings_outside_map():
    """Every 'Age of AI' literal lives in the SHOWS map or a comment."""
    code = re.sub(r"/\*.*?\*/", "", WORKER, flags=re.S)
    code = re.sub(r"(^|\s)//.*$", "", code, flags=re.M)  # line + trailing comments
    code = code.replace(_shows_block(), "")
    assert "Age of AI" not in code, "hardcoded 'Age of AI' outside SHOWS map"
    assert "#7C3AED" not in code
    assert "age-of-ai-studio.html" not in code


def test_worker_studio_state_returns_show():
    body = WORKER.split("async function handleStudioState")[1].split("\nasync function")[0]
    assert "show: show.slug" in body and "show_name: show.name" in body


def test_worker_docs_mention_new_vars_and_route():
    for text in (README, WRANGLER):
        assert "CALCOM_BOOKING_URL_NERRA_VOICES" in text
        assert "CALCOM_EVENT_SLUG_NERRA_VOICES" in text
    assert "/voices/triage-reassign" in README


# ---------------------------------------------------------------------------
# Studio page
# ---------------------------------------------------------------------------

def test_studio_page_reads_show_from_query():
    assert 'params.get("show")' in STUDIO
    assert "nerra_voices" in STUDIO and "age_of_ai" in STUDIO
    assert "#0F766E" in STUDIO
    assert "s.show_name" in STUDIO, "studio-state show_name brands the page"
    # The run-id flow and Voximplant headers are untouched.
    assert '"X-Run-Id": runId' in STUDIO
    assert "/studio-state?interview=" in STUDIO
