"""A locked X account keeps the queue, it does not empty it (Nov 7 2026).

@nerranetwork was locked by X from 13:35 UTC on Nov 7 ("Your account is
temporarily locked. Please log in to https://x.com to unlock your account.").
Each queued post spent its three attempts in 90 minutes and failed for good,
so a day's teasers were lost to a lock only a login clears. A lock is not the
post's fault: the post stays queued without spending an attempt for up to
``LOCKED_MAX_AGE``, the run stops at the first lock, and the run is red.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import publisher, x_post, x_queue  # noqa: E402

UTC = dt.timezone.utc
LOCK = ('Forbidden: 403 Forbidden\nYour account is temporarily locked. Please log in to '
        'https://x.com to unlock your account. | body={"status":403}')


def _rows(created="2026-11-07T11:00:00Z"):
    return [{"id": "a", "show_slug": "first_principles", "episode_num": 154, "text": "t",
             "media_url": "", "env_prefix": "NERRANETWORK_X_", "attempts": 1,
             "due_at": "2026-11-07T13:30:00Z", "created_at": created},
            {"id": "b", "show_slug": "spacex", "episode_num": 154, "text": "t",
             "media_url": "", "env_prefix": "NERRANETWORK_X_", "attempts": 0,
             "due_at": "2026-11-07T14:00:00Z", "created_at": created}]


def _run(monkeypatch, rows, now):
    patches = []

    def rest(method, path, params=None, json=None, prefer=""):
        if method == "GET":
            return rows
        patches.append((params, json))
        return [{"id": params.get("id")}] if json and json.get("status") == "posting" else []
    monkeypatch.setattr(x_queue, "_rest", rest)
    calls = []

    def post_media(**kw):
        calls.append(kw["label"])
        return False, "account_locked", "", ""
    monkeypatch.setattr(x_post, "post_media", post_media)
    return x_queue.post_due(now=now), patches, calls


def test_a_lock_keeps_the_post_and_its_attempts(monkeypatch):
    out, patches, calls = _run(monkeypatch, _rows(), dt.datetime(2026, 11, 7, 21, 5, tzinfo=UTC))
    assert [r["status"] for r in out] == ["locked"]
    assert calls == ["first_principles ep154"], "the run stops at the first lock"
    kept = [j for p, j in patches if p.get("id") == "eq.a" and j.get("error") == "account_locked"]
    assert kept and kept[0]["status"] == "queued" and kept[0]["attempts"] == 1
    assert kept[0]["due_at"] > "2026-11-07T21:05"


def test_a_lock_older_than_a_day_fails_the_stale_post(monkeypatch):
    out, patches, _ = _run(monkeypatch, _rows(created="2026-11-06T11:00:00Z"),
                           dt.datetime(2026, 11, 7, 21, 5, tzinfo=UTC))
    assert [r["status"] for r in out] == ["failed"]
    final = [j for p, j in patches if p.get("id") == "eq.a" and j.get("status") == "failed"]
    assert final and final[0]["error"] == "account_locked"


def test_post_media_names_the_lock(monkeypatch):
    monkeypatch.setattr(x_post, "x_credentials", lambda prefix: {
        "consumer_key": "k", "consumer_secret": "s", "access_token": "t",
        "access_token_secret": "u"})

    def refused(text, **kw):
        publisher.LAST_X_ERROR = LOCK
        return None
    monkeypatch.setattr(publisher, "post_to_x", refused)
    assert x_post.post_media(env_prefix="NERRANETWORK_X_", text="t", media_paths=[],
                             label="x")[1] == "account_locked"

    def other(text, **kw):
        publisher.LAST_X_ERROR = "Forbidden: 403 Forbidden | duplicate content"
        return None
    monkeypatch.setattr(publisher, "post_to_x", other)
    assert x_post.post_media(env_prefix="NERRANETWORK_X_", text="t", media_paths=[],
                             label="x")[1] == "post_failed"


def test_the_workflow_run_is_red_on_a_lock():
    src = (ROOT / "scripts" / "post_x_queue.py").read_text(encoding="utf-8")
    assert 'r["status"] in ("failed", "locked")' in src
    assert "https://x.com" in src
