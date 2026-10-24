"""Oct 24 2026: guest_applications is service-role only.

The anon INSERT policy let anyone with the publishable key write a
pre-screened application straight into the Producer's queue. The apply
pages never used it (they post to the Voices Worker, which writes with the
service key), so the migration takes every anon/authenticated privilege
away. These tests keep the pages off Supabase and keep the lockdown in place.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "supabase/migrations/20261024_guest_applications_service_role_only.sql"
APPLY_PAGES = ("age-of-ai-apply.html", "nerra-voices-apply.html")


def test_migration_revokes_and_drops_the_anon_policy():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "revoke all on table public.guest_applications from public, anon, authenticated" in sql
    assert 'drop policy if exists "anon can submit applications" on public.guest_applications' in sql
    assert "raise exception" in sql  # guard fails the migration if access remains


def test_apply_pages_post_to_the_worker_not_supabase():
    for page in APPLY_PAGES:
        html = (ROOT / page).read_text(encoding="utf-8")
        assert "https://api.nerranetwork.com/voices/apply" in html, page
        assert "supabase.co" not in html, page
        assert "/rest/v1/" not in html, page
