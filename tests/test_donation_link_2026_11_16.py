"""The retired one-time donation link never comes back (Nov 16 2026).

Every failed payment on the Stripe account from Oct 3 to Nov 14 2026 was
card testing on the one-time donation Payment Link: a bot ran 21 stolen
cards through it at the prefilled $10, and Radar blocked all of them. The
link was replaced so the saved URL stops working; the old one is
deactivated in Stripe. A page or workflow fallback that still carries it
would send a real donor to a dead page.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RETIRED = "donate.stripe.com/dRm8wQ8XEd5weiC0Rx0Ba03"
CURRENT = "https://donate.stripe.com/7sY6oIc9Q0iK2zUbwb0Ba04"


def _surfaces():
    yield from (ROOT / ".github" / "workflows").glob("*.yml")
    yield ROOT / "support.html"
    yield from (ROOT / "templates").glob("*.j2")


def test_retired_donation_link_is_gone():
    hits = [str(p.relative_to(ROOT)) for p in _surfaces()
            if RETIRED in p.read_text(encoding="utf-8")]
    assert not hits, f"retired donation link still on: {hits}"


def test_workflow_fallback_is_the_current_link():
    text = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
    assert f"STRIPE_LINK_DONATE_ONCE || '{CURRENT}'" in text
