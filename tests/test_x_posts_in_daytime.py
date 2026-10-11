"""Oct 11 2026 (Patrick: "make any improvements"). The shows publish between
about 11 PM and 5 AM Pacific and their first X posts went out then, to an
audience that was asleep. A post now waits for a half-hour slot between
6:30 AM and 7 PM Pacific, one post per slot; the scheduler Worker dispatches
x-queue.yml to post what is due. A second wave of shows turns on by date.
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

P = x_queue.PACIFIC
UTC = dt.timezone.utc
RUN_SHOW = (ROOT / "run_show.py").read_text(encoding="utf-8")
WORKER = (ROOT / "workers" / "scheduler" / "src" / "index.ts").read_text(encoding="utf-8")


def pt(y, m, d, h, mi):
    return dt.datetime(y, m, d, h, mi, tzinfo=P)


# ------------------------------------------------------------------ slots --
class TestSlots:
    def test_a_night_post_waits_for_the_morning(self):
        assert x_queue.next_slot([], pt(2026, 10, 12, 1, 15)) == pt(2026, 10, 12, 6, 30).astimezone(UTC)

    def test_one_post_per_slot(self):
        night = pt(2026, 10, 12, 2, 0)
        taken = []
        for _ in range(4):
            taken.append(x_queue.next_slot(taken, night))
        assert [t.astimezone(P).strftime("%H:%M") for t in taken] == ["06:30", "07:00", "07:30", "08:00"]

    def test_daytime_posts_go_soon_and_on_the_grid(self):
        assert x_queue.next_slot([], pt(2026, 10, 12, 9, 10)).astimezone(P) == pt(2026, 10, 12, 9, 30)
        assert x_queue.next_slot([], pt(2026, 10, 12, 9, 26)).astimezone(P) == pt(2026, 10, 12, 10, 0)

    def test_evening_rolls_to_tomorrow(self):
        assert x_queue.next_slot([], pt(2026, 10, 12, 19, 10)).astimezone(P) == pt(2026, 10, 13, 6, 30)

    def test_slots_follow_pacific_across_the_clock_change(self):
        # Nov 1 2026: PDT -> PST. 6:30 AM stays 6:30 AM on the wall clock.
        slot = x_queue.next_slot([], pt(2026, 11, 1, 2, 30))
        assert slot.astimezone(P).strftime("%H:%M") == "06:30"
        assert slot == dt.datetime(2026, 11, 1, 14, 30, tzinfo=UTC)


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
    monkeypatch.setattr(x_queue, "_host", lambda path, slug: f"https://g.example/x_queue/{slug}/{path.name}")
    monkeypatch.setattr(x_queue, "_rest", lambda method, path, **kw: sent.update(kw) or [{"id": "1"}])
    ok, due = x_queue.enqueue(show_slug="spacex", episode_num=128, env_prefix="NERRANETWORK_X_",
                              text="t", media_path=str(clip), media_kind="clip",
                              now=pt(2026, 10, 12, 2, 56).astimezone(UTC))
    assert ok and due == "2026-10-12T13:30:00Z"
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
def test_worker_dispatches_the_queue_on_pacific_half_hours():
    assert 'workflow: "x-queue.yml"' in WORKER and "minutes: [1, 31]" in WORKER
    assert "if (xQueueDue(ph, pm))" in WORKER
    # The edition branch returns, so the queue must be dispatched before it.
    assert WORKER.index("if (xQueueDue(ph, pm))") < WORKER.index("EDITION_DISPATCH.times.some(")


def test_the_queue_workflow_carries_what_it_needs():
    wf = (ROOT / ".github" / "workflows" / "x-queue.yml").read_text(encoding="utf-8")
    for k in ("X_QUEUE_SUPABASE_URL", "X_QUEUE_SUPABASE_KEY", "NERRANETWORK_X_CONSUMER_KEY",
              "NERRANETWORK_X_ACCESS_TOKEN_SECRET", "R2_GALLERY_PUBLIC_BASE_URL"):
        assert f"{k}:" in wf
    assert "python scripts/post_x_queue.py" in wf and "workflow_dispatch" in wf
    rs = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
    assert "X_QUEUE_SUPABASE_URL: ${{ secrets.VOICES_SUPABASE_URL }}" in rs


def test_the_migration_is_in_the_repo():
    sql = (ROOT / "supabase" / "migrations" / "20261011_x_post_queue.sql").read_text(encoding="utf-8")
    assert "create table if not exists public.x_post_queue" in sql
    assert "unique (show_slug, episode_num)" in sql and "enable row level security" in sql
