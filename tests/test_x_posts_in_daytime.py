"""Oct 11 2026 (Patrick: "make any improvements"). The shows publish in the
early morning and their first X posts went out then, to an audience that was
asleep. A post now waits for a half-hour slot, one post per slot; the
scheduler Worker dispatches x-queue.yml to post what is due. A second wave of
shows turns on by date.

Oct 17 2026: the grid is New York time, 7:00 AM to 10:00 PM ET. Nerra Daily
holds 7:00 ET; a show takes its own release slot (engine/release_schedule.py)
when it is free and not past, else the next free slot.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import x_queue  # noqa: E402
from engine.config import load_config  # noqa: E402

E = x_queue.EASTERN
UTC = dt.timezone.utc
RUN_SHOW = (ROOT / "run_show.py").read_text(encoding="utf-8")
WORKER = (ROOT / "workers" / "scheduler" / "src" / "index.ts").read_text(encoding="utf-8")


def et(y, m, d, h, mi):
    return dt.datetime(y, m, d, h, mi, tzinfo=E)


# ------------------------------------------------------------------ slots --
class TestSlots:
    def test_a_night_post_waits_for_the_morning_and_skips_the_edition_slot(self):
        # 7:00 ET is Nerra Daily's; the first slot a show can get is 7:30.
        assert x_queue.next_slot([], et(2026, 10, 12, 1, 15)) == et(2026, 10, 12, 7, 30).astimezone(UTC)

    def test_the_edition_slot_is_only_reserved_for_shows(self):
        assert x_queue.next_slot([], et(2026, 10, 12, 1, 15), reserve_edition=False) == \
            et(2026, 10, 12, 7, 0).astimezone(UTC)

    def test_one_post_per_slot(self):
        night = et(2026, 10, 12, 2, 0)
        taken = []
        for _ in range(4):
            taken.append(x_queue.next_slot(taken, night))
        assert [t.astimezone(E).strftime("%H:%M") for t in taken] == ["07:30", "08:00", "08:30", "09:00"]

    def test_daytime_posts_go_soon_and_on_the_grid(self):
        assert x_queue.next_slot([], et(2026, 10, 12, 9, 10)).astimezone(E) == et(2026, 10, 12, 9, 30)
        assert x_queue.next_slot([], et(2026, 10, 12, 9, 26)).astimezone(E) == et(2026, 10, 12, 10, 0)

    def test_the_last_slot_is_ten_pm_and_later_rolls_to_tomorrow(self):
        assert x_queue.next_slot([], et(2026, 10, 12, 21, 50)).astimezone(E) == et(2026, 10, 12, 22, 0)
        assert x_queue.next_slot([], et(2026, 10, 12, 22, 10)).astimezone(E) == et(2026, 10, 13, 7, 30)

    def test_slots_follow_eastern_across_the_clock_change(self):
        # Nov 1 2026: EDT -> EST. 7:30 AM stays 7:30 AM on the wall clock.
        slot = x_queue.next_slot([], et(2026, 11, 1, 2, 30))
        assert slot.astimezone(E).strftime("%H:%M") == "07:30"
        assert slot == dt.datetime(2026, 11, 1, 12, 30, tzinfo=UTC)
        before = x_queue.next_slot([], et(2026, 10, 31, 2, 30))
        assert before == dt.datetime(2026, 10, 31, 11, 30, tzinfo=UTC)


class TestPreferredSlot:
    def test_a_show_takes_its_release_slot(self):
        # spacex is second in the release order: 7:30 + 30 min = 8:00 ET.
        due = x_queue.choose_slot("spacex", [], et(2026, 10, 12, 5, 0))
        assert due.astimezone(E) == et(2026, 10, 12, 8, 0)

    def test_a_taken_release_slot_falls_back_to_the_next_free_one(self):
        taken = [et(2026, 10, 12, 8, 0).astimezone(UTC)]
        due = x_queue.choose_slot("spacex", taken, et(2026, 10, 12, 5, 0))
        assert due.astimezone(E) == et(2026, 10, 12, 7, 30)

    def test_a_passed_release_slot_falls_back_to_the_next_free_one(self):
        due = x_queue.choose_slot("omni_view_world", [], et(2026, 10, 12, 9, 10))
        assert due.astimezone(E) == et(2026, 10, 12, 9, 30)

    def test_a_show_never_lands_in_the_edition_slot(self):
        taken = [et(2026, 10, 12, 7, 30).astimezone(UTC)]
        due = x_queue.choose_slot("omni_view_world", taken, et(2026, 10, 12, 5, 0))
        assert due.astimezone(E) != et(2026, 10, 12, 7, 0)


# ---------------------------------------------------------------- enqueue --
def test_an_unconfigured_queue_means_post_now(monkeypatch):
    for k in ("X_QUEUE_SUPABASE_URL", "X_QUEUE_SUPABASE_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert x_queue.enqueue(show_slug="s", episode_num=1, env_prefix="P_", text="t") == (
        False, "queue_not_configured")


def test_a_queue_error_means_post_now(monkeypatch):
    monkeypatch.setattr(x_queue, "configured", lambda: True)
    monkeypatch.setattr(x_queue, "_taken", lambda now: (_ for _ in ()).throw(RuntimeError("down")))
    assert x_queue.enqueue(show_slug="s", episode_num=1, env_prefix="P_", text="t") == (
        False, "queue_error")


def test_enqueue_hosts_the_clip_and_takes_a_slot(monkeypatch, tmp_path):
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x")
    sent = {}
    monkeypatch.setattr(x_queue, "configured", lambda: True)
    monkeypatch.setattr(x_queue, "_taken", lambda now: [])
    monkeypatch.setattr(x_queue, "_host", lambda path, slug: f"{x_queue.R2_PUBLIC_BASE}/x_queue/{slug}/{path.name}")
    monkeypatch.setattr(x_queue, "_rest", lambda method, path, **kw: sent.update(kw) or [{"id": "1"}])
    ok, due = x_queue.enqueue(show_slug="spacex", episode_num=128, env_prefix="NERRANETWORK_X_",
                              text="t", media_path=str(clip), media_kind="clip",
                              now=et(2026, 10, 12, 5, 56).astimezone(UTC))
    # spacex's own release slot: 8:00 AM EDT.
    assert ok and due == "2026-10-12T12:00:00Z"
    assert sent["json"]["media_url"].endswith("/x_queue/spacex/c.mp4")
    assert "ignore-duplicates" in sent["prefer"] and sent["params"]["on_conflict"] == "show_slug,episode_num"


# --------------------------------------------------------------- post due --
def test_post_due_posts_marks_and_retries(monkeypatch):
    rows = [{"id": "a", "show_slug": "spacex", "episode_num": 1, "text": "t", "media_url": "",
             "env_prefix": "NERRANETWORK_X_", "attempts": 0, "due_at": "2026-10-12T13:30:00Z"},
            {"id": "b", "show_slug": "omni_view", "episode_num": 2, "text": "t", "media_url": "",
             "env_prefix": "NERRANETWORK_X_", "attempts": 2, "due_at": "2026-10-12T14:00:00Z"}]
    patches = []

    def rest(method, path, params=None, json=None, prefer=""):
        if method == "GET":
            return rows
        patches.append((params, json))
        return [{"id": params.get("id")}] if json and json.get("status") == "posting" else []
    monkeypatch.setattr(x_queue, "_rest", rest)
    from engine import x_post
    outcomes = iter([(True, "", "https://x.com/i/status/1", ""), (False, "post_failed", "", "")])
    monkeypatch.setattr(x_post, "post_media", lambda **kw: next(outcomes))
    out = x_queue.post_due(now=dt.datetime(2026, 10, 12, 14, 1, tzinfo=UTC))
    assert [r["status"] for r in out] == ["posted", "failed"]
    final = [j for p, j in patches if p.get("id") == "eq.b" and j.get("status") == "failed"]
    assert final and final[0]["error"] == "post_failed"


# ------------------------------------------------------------- wiring --
def test_run_show_queues_and_falls_back_to_posting_now():
    branch = RUN_SHOW[RUN_SHOW.index("if _x_clip_mode and all("):
                      RUN_SHOW.index("elif all([consumer_key, consumer_secret")]
    assert branch.index("x_queue.enqueue(") < branch.index("post_media(")
    assert 'metrics.record("x_post_queued_for", _due)' in branch


def test_the_start_date_holds_the_second_wave():
    ns: dict = {}
    src = RUN_SHOW[RUN_SHOW.index("def _x_on("):RUN_SHOW.index("def _x_label(")]
    exec(src, ns)
    cfg = load_config(ROOT / "shows" / "mag7.yaml")
    assert cfg.publishing.x_start_date == "2026-10-24"
    assert ns["_x_on"](cfg, dt.date(2026, 10, 23)) is False
    assert ns["_x_on"](cfg, dt.date(2026, 10, 24)) is True
    assert ns["_x_on"](load_config(ROOT / "shows" / "spacex.yaml"), dt.date(2026, 10, 12)) is True
    assert "_x_live = _x_on(config, today)" in RUN_SHOW


SECOND_WAVE = ("first_principles", "mag7", "ai_chips", "prediction_markets", "vancouver",
               "collingwood", "env_intel", "longevity", "offshore_north", "peptides")


@pytest.mark.parametrize("slug", SECOND_WAVE)
def test_second_wave_keeps_its_x_sourcing(slug):
    """Turning X posting on must not turn X *reading* on: sourcing followed
    x_enabled for shows without an explicit x_fetch_enabled."""
    from engine.fetcher import x_fetch_allowed
    cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
    assert cfg.publishing.x_post_format == "clip"
    if cfg.x_accounts:
        assert cfg.x_fetch_enabled is not None, slug


def test_overlapping_shows_stay_off():
    # Six regional Omni View editions would post near-duplicates of Omni
    # View; X's automation rules forbid that. Beginners overlaps M&A.
    # DP Pod: "X / multilingual stay off" (operator, Sep 4 2026).
    for slug in ("omni_view_europe", "omni_view_world", "models_agents_beginners", "dp_pod"):
        assert not load_config(ROOT / "shows" / f"{slug}.yaml").publishing.x_enabled


# ------------------------------------------------------------ scheduling --
def test_worker_dispatches_the_queue_on_eastern_half_hours():
    # Oct 17 2026: the X slot grid is 7:00 AM - 10:00 PM Eastern and the
    # Worker dispatches five minutes after each slot, :05 and :35 from
    # 7:05 AM to 10:05 PM Eastern (it was :01/:31 Pacific, 6:31 AM-7:31 PM).
    assert 'workflow: "x-queue.yml"' in WORKER and "minutes: [5, 35]" in WORKER
    m = re.search(r'X_QUEUE_DISPATCH = \{.*?tz: "([^"]+)",\s*first: \[(\d+), (\d+)\].*?'
                  r'last: \[(\d+), (\d+)\]', WORKER, re.S)
    assert m, "X_QUEUE_DISPATCH reshaped"
    assert m.group(1) == "America/New_York"
    assert (int(m.group(2)), int(m.group(3))) == (7, 5)
    assert (int(m.group(4)), int(m.group(5))) == (22, 5)
    assert "if (xQueueDue(clock.hour, clock.minute))" in WORKER
    # The queue is dispatched first and independently of the edition.
    assert WORKER.index("if (xQueueDue(clock.hour, clock.minute))") < WORKER.index(
        "EDITION_DISPATCH.times.some(")


def test_the_queue_workflow_carries_what_it_needs():
    wf = (ROOT / ".github" / "workflows" / "x-queue.yml").read_text(encoding="utf-8")
    for k in ("X_QUEUE_SUPABASE_URL", "X_QUEUE_SUPABASE_KEY", "NERRANETWORK_X_CONSUMER_KEY",
              "NERRANETWORK_X_ACCESS_TOKEN_SECRET", "R2_SECRET_ACCESS_KEY"):
        assert f"{k}:" in wf
    assert "python scripts/post_x_queue.py" in wf and "workflow_dispatch" in wf
    rs = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
    assert "X_QUEUE_SUPABASE_URL: ${{ secrets.VOICES_SUPABASE_URL }}" in rs


def test_the_migration_is_in_the_repo():
    sql = (ROOT / "supabase" / "migrations" / "20261011_x_post_queue.sql").read_text(encoding="utf-8")
    assert "create table if not exists public.x_post_queue" in sql
    assert "unique (show_slug, episode_num)" in sql and "enable row level security" in sql
