"""The queue drains a backlog slowly (Nov 13 2026).

After the Nov 12 unlock (~13:00 UTC) the queue posted two teasers and one
full-episode video every half hour for six hours, many for episodes three days
old; two runs landed 80 seconds apart at 19:07 and the account was locked again
at 19:08. A run that meets backlog posts one row, a run within MIN_POST_GAP of
the account's last post posts nothing, and a stale full-episode reply is
cancelled instead of uploaded.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import x_post, x_queue  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 11, 12, 15, 5, tzinfo=UTC)


def _row(i, created, prefix="NERRANETWORK_X_"):
    return {"id": i, "show_slug": "spacex", "episode_num": int(i), "text": "t", "media_url": "",
            "env_prefix": prefix, "attempts": 0, "due_at": "2026-11-12T13:00:00Z",
            "created_at": created}


def _run(monkeypatch, due, posted):
    def rest(method, path, params=None, json=None, prefer=""):
        if method == "GET":
            return posted if params.get("status") == "eq.posted" else due
        return [{"id": params.get("id")}] if json and json.get("status") == "posting" else []
    monkeypatch.setattr(x_queue, "_rest", rest)
    calls = []

    def post_media(**kw):
        calls.append(kw["label"])
        return True, "", "https://x.com/i/status/1", "m"
    monkeypatch.setattr(x_post, "post_media", post_media)
    return x_queue.post_due(now=NOW), calls


def test_a_fresh_day_still_posts_two(monkeypatch):
    out, calls = _run(monkeypatch, [_row("1", "2026-11-12T10:00:00Z"), _row("2", "2026-11-12T10:00:00Z")], [])
    assert len(calls) == 2


def test_backlog_posts_one_per_run(monkeypatch):
    out, calls = _run(monkeypatch, [_row("1", "2026-11-09T10:00:00Z"), _row("2", "2026-11-10T10:00:00Z")], [])
    assert calls == ["spacex ep1"]


def test_a_run_right_after_a_post_waits(monkeypatch):
    posted = [{"posted_at": "2026-11-12T15:00:00Z", "env_prefix": "NERRANETWORK_X_"}]
    out, calls = _run(monkeypatch, [_row("1", "2026-11-12T10:00:00Z")], posted)
    assert out == [] and calls == []


def test_the_gap_is_per_account(monkeypatch):
    posted = [{"posted_at": "2026-11-12T15:00:00Z", "env_prefix": "NERRANETWORK_X_"}]
    out, calls = _run(monkeypatch, [_row("1", "2026-11-12T10:00:00Z"),
                                    _row("2", "2026-11-12T10:00:00Z", prefix="X_")], posted)
    assert calls == ["spacex ep2"]


def test_an_older_post_does_not_hold_the_run(monkeypatch):
    posted = [{"posted_at": "2026-11-12T14:35:00Z", "env_prefix": "NERRANETWORK_X_"}]
    out, calls = _run(monkeypatch, [_row("1", "2026-11-12T10:00:00Z")], posted)
    assert calls == ["spacex ep1"]


def test_a_stale_reply_is_cancelled_and_its_copy_dropped(monkeypatch):
    reply = {"id": "r", "show_slug": "spacex", "episode_num": 156, "kind": "long",
             "env_prefix": "NERRANETWORK_X_", "text": "Full.", "attempts": 0,
             "media_url": "https://audio.nerranetwork.com/x_queue/spacex/a.mp4",
             "subtitles_url": "", "created_at": "2026-11-09T11:00:00Z"}
    patches, forgot = [], []

    def rest(method, path, params=None, json=None, prefer=""):
        if method == "GET" and path == "x_post_replies":
            return [reply]
        if method == "GET":
            return [{"status": "posted", "tweet_url": "https://x.com/n/status/5"}]
        patches.append(json)
        return []
    monkeypatch.setattr(x_queue, "_rest", rest)
    monkeypatch.setattr(x_queue, "_forget_media", forgot.append)
    monkeypatch.setattr(x_post, "post_video_reply",
                        lambda **kw: (_ for _ in ()).throw(AssertionError("uploaded a stale reply")))
    out = x_queue.post_due_replies(now=NOW)
    assert out[0]["status"] == "cancelled" and out[0]["error"] == "stale"
    assert forgot == [reply["media_url"]]


def test_the_pacing_constants():
    assert x_queue.MIN_POST_GAP <= dt.timedelta(minutes=25), "must not skip the next half-hour slot"
    assert x_queue.CATCH_UP_AGE >= dt.timedelta(hours=12), "a same-day post is never backlog"
