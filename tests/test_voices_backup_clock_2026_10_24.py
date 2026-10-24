"""Oct 24 2026 — the Voices Worker's backup clock (docs/voices_backup_clock.md).

Cloudflare's cron for nerra-voices-api went dark for 23 hours on Oct 23 and
a guest's T-2h reminder never went out. The tick now runs from whichever
clock claims its five-minute slot first: Cloudflare's cron, or Supabase's
pg_cron posting /voices/cron-tick a minute later. The behaviour is tested in
workers/voices/test/backup_clock.test.ts (vitest, run by hand: no workflow
runs it); these guards read the wiring from CI.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TS = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
TOML = (ROOT / "workers" / "voices" / "wrangler.toml").read_text(encoding="utf-8")
TICKS_SQL = (ROOT / "supabase" / "migrations" / "20261024_cron_ticks.sql").read_text(encoding="utf-8")
CLOCK_SQL = (ROOT / "supabase" / "migrations" / "20261024_voices_backup_clock.sql").read_text(encoding="utf-8")


def fn(name: str) -> str:
    i = TS.index(f"function {name}(")
    return TS[i:TS.index("\n}\n", i)]


class TestOneTickTwoClocks:
    def test_scheduled_is_the_cloudflare_clock(self):
        body = TS.split("async scheduled(", 1)[1].split("\n  },", 1)[0]
        assert 'await runTick(env, new Date(event.scheduledTime), "cloudflare");' in body
        assert "dispatch(" not in body and "gate2Housekeeping" not in body

    def test_the_trigger_stays_as_re_registered(self):
        assert 'crons = ["0-59/5 * * * *"]' in TOML

    def test_the_tick_claims_its_slot_first_and_reads_the_slot(self):
        tick = fn("runTick")
        assert tick.index("claimSlot(") < tick.index("fireTickDue(")
        assert 'if (claim === "taken")' in tick
        assert "const minute = slot.getUTCMinutes();" in tick
        assert "const gate2Hour = slot.getUTCHours() === 17 && minute === 0;" in tick
        assert "getUTCMinutes()" not in tick.replace("slot.getUTCMinutes()", "")

    def test_the_claim_is_an_ignore_duplicates_insert_and_fails_open(self):
        claim = fn("claimSlot")
        assert '"resolution=ignore-duplicates,return=representation"' in claim
        assert 'return "unknown";' in claim.split("catch", 1)[1]

    def test_the_endpoint_takes_only_the_tick_secret(self):
        h = fn("handleCronTick")
        assert "env.CRON_TICK_SECRET" in h and "tokenEquals(given, secret)" in h
        assert "tokenEquals(given, admin)" in h       # ADMIN_TOKEN is refused
        assert 'return json({ error: "unauthorized" }, 401);' in h
        assert 'runTick(env, new Date(), "supabase")' in h
        assert '"/voices/cron-tick"' in TS
        assert "CRON_TICK_SECRET?: string;" in TS
        assert "cron_tick_secret: !!(env.CRON_TICK_SECRET" in TS

    def test_the_watchdog_keeps_its_state_in_supabase(self):
        w = fn("watchCloudflare")
        assert "cron_clock_state?name=eq.cloudflare&outage_since=is.null" in w
        assert "cron_clock_state?name=eq.cloudflare&outage_since=not.is.null" in w
        assert "CLOUDFLARE_QUIET_MS" in w
        assert "export const CLOUDFLARE_QUIET_MS = 20 * 60 * 1000;" in TS
        assert "Cloudflare's timer has stopped; the backup clock is carrying reminders." in TS
        assert "Cloudflare's timer is back." in TS


class TestTheMigrations:
    def test_cron_ticks_and_the_clock_state(self):
        assert "slot       timestamptz primary key" in TICKS_SQL
        assert "source     text not null" in TICKS_SQL
        assert "claimed_at timestamptz not null default now()" in TICKS_SQL
        assert "alter table public.cron_ticks enable row level security;" in TICKS_SQL
        assert "alter table public.cron_clock_state enable row level security;" in TICKS_SQL
        assert "create policy" not in TICKS_SQL.lower()
        assert "insert into public.cron_clock_state (name) values ('cloudflare')" in TICKS_SQL

    def test_the_supabase_clock_runs_a_minute_after_cloudflare(self):
        assert "create extension if not exists pg_cron;" in CLOCK_SQL
        assert "create extension if not exists pg_net;" in CLOCK_SQL
        assert "'voices-backup-tick',\n  '1-59/5 * * * *'" in CLOCK_SQL
        assert "https://api.nerranetwork.com/voices/cron-tick" in CLOCK_SQL
        assert "timeout_milliseconds := 25000" in CLOCK_SQL

    def test_the_secret_lives_only_in_vault(self):
        assert "vault.decrypted_secrets where name = 'voices_cron_tick_secret'" in CLOCK_SQL
        for text in (CLOCK_SQL, TICKS_SQL, TOML):
            assert not re.search(r"\b[0-9a-f]{64}\b", text)

    def test_the_cleanup(self):
        assert "'voices-backup-clock-cleanup'" in CLOCK_SQL
        assert "delete from public.cron_ticks where slot < now() - interval '14 days';" in CLOCK_SQL
        assert "delete from cron.job_run_details where end_time < now() - interval '7 days';" in CLOCK_SQL


def test_github_stays_the_third_clock():
    wf = (ROOT / ".github" / "workflows" / "nerra_voices_fire_interview.yml").read_text(encoding="utf-8")
    assert "schedule:" in wf and "- cron: '*/5 * * * *'" in wf
