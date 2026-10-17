"""The full episode on X, as a reply under the show's post (Oct 17 2026).

engine/x_queue.enqueue_reply + post_due_replies, engine/x_post.post_video_reply,
engine/x_media subtitles, run_show wiring, and the migration.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import x_media, x_post, x_queue  # noqa: E402
from engine.config import load_config  # noqa: E402

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 18, 15, 1, tzinfo=UTC)
RUN_SHOW = (ROOT / "run_show.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------- enqueue --
def test_a_reply_without_a_queue_is_not_made(monkeypatch):
    monkeypatch.setattr(x_queue, "configured", lambda: False)
    assert x_queue.enqueue_reply(show_slug="s", episode_num=1, env_prefix="P_", text="t",
                                 media_url="https://a/x.mp4") == (False, "queue_not_configured")


def test_a_reply_needs_its_video():
    assert x_queue.enqueue_reply(show_slug="s", episode_num=1, env_prefix="P_", text="t",
                                 media_url="")[1] == "no_media"


def test_enqueue_reply_writes_the_reply_table(monkeypatch):
    sent = {}
    monkeypatch.setattr(x_queue, "configured", lambda: True)
    monkeypatch.setattr(x_queue, "_rest", lambda method, path, **kw: sent.update(path=path, **kw) or [{"id": "1"}])
    ok, why = x_queue.enqueue_reply(show_slug="spacex", episode_num=134, env_prefix="NERRANETWORK_X_",
                                    text="The full episode: SpaceX Daily, episode 134.",
                                    media_url="https://audio.nerranetwork.com/x_queue/spacex/a.mp4",
                                    subtitles_url="https://audio.nerranetwork.com/x_queue/spacex/a.srt")
    assert ok and why == "queued"
    assert sent["path"] == "x_post_replies"
    assert sent["params"]["on_conflict"] == "show_slug,episode_num,kind"
    assert sent["json"]["kind"] == "long" and sent["json"]["subtitles_url"].endswith(".srt")


def test_a_missing_table_drops_the_hosted_copies(monkeypatch):
    forgot = []
    monkeypatch.setattr(x_queue, "configured", lambda: True)
    monkeypatch.setattr(x_queue, "_rest", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("404")))
    monkeypatch.setattr(x_queue, "_forget_media", forgot.append)
    assert x_queue.enqueue_reply(show_slug="s", episode_num=1, env_prefix="P_", text="t",
                                 media_url="u1", subtitles_url="u2") == (False, "queue_error")
    assert forgot == ["u1", "u2"]


# --------------------------------------------------------------- posting --
def _fake_rest(replies, parent, patches):
    def rest(method, path, params=None, json=None, prefer=""):
        if method == "GET" and path == "x_post_replies":
            return replies
        if method == "GET" and path == "x_post_queue":
            return [parent] if parent else []
        patches.append((path, params, json))
        return [{"id": "r"}] if json and json.get("status") == "posting" else []
    return rest


REPLY = {"id": "r", "show_slug": "spacex", "episode_num": 134, "kind": "long",
         "env_prefix": "NERRANETWORK_X_", "text": "The full episode.", "attempts": 0,
         "media_url": "https://audio.nerranetwork.com/x_queue/spacex/a.mp4",
         "subtitles_url": "", "created_at": "2026-10-18T10:00:00Z"}


def test_a_reply_waits_for_its_parent(monkeypatch):
    patches = []
    monkeypatch.setattr(x_queue, "_rest", _fake_rest([REPLY], {"status": "queued", "tweet_url": None}, patches))
    assert x_queue.post_due_replies(now=NOW) == []
    assert not any(j and j.get("status") == "posting" for _, _, j in patches)


def test_a_failed_parent_cancels_the_reply(monkeypatch):
    patches, forgot = [], []
    monkeypatch.setattr(x_queue, "_rest", _fake_rest([REPLY], {"status": "failed"}, patches))
    monkeypatch.setattr(x_queue, "_forget_media", forgot.append)
    out = x_queue.post_due_replies(now=NOW)
    assert out[0]["status"] == "cancelled" and forgot == [REPLY["media_url"]]


def test_a_reply_posts_under_its_parent(monkeypatch, tmp_path):
    patches, forgot, calls = [], [], {}
    parent = {"status": "posted", "tweet_url": "https://x.com/nerranetwork/status/1979000000000000001"}
    monkeypatch.setattr(x_queue, "_rest", _fake_rest([REPLY], parent, patches))
    monkeypatch.setattr(x_queue, "_forget_media", forgot.append)
    monkeypatch.setattr(x_queue, "_download", lambda url, folder: str(tmp_path / "a.mp4"))

    def fake_reply(**kw):
        calls.update(kw)
        return True, "no_subtitles", "https://x.com/nerranetwork/status/2"
    monkeypatch.setattr(x_post, "post_video_reply", fake_reply)
    out = x_queue.post_due_replies(now=NOW)
    assert out == [{"id": "r", "show": "spacex ep134 (long)", "status": "posted",
                    "url": "https://x.com/nerranetwork/status/2"}]
    assert calls["in_reply_to"] == "1979000000000000001"
    assert forgot == [REPLY["media_url"]]


def test_three_failed_attempts_give_up_and_drop_the_copy(monkeypatch, tmp_path):
    patches, forgot = [], []
    row = dict(REPLY, attempts=2)
    parent = {"status": "posted", "tweet_url": "https://x.com/n/status/5"}
    monkeypatch.setattr(x_queue, "_rest", _fake_rest([row], parent, patches))
    monkeypatch.setattr(x_queue, "_forget_media", forgot.append)
    monkeypatch.setattr(x_queue, "_download", lambda url, folder: str(tmp_path / "a.mp4"))
    monkeypatch.setattr(x_post, "post_video_reply", lambda **kw: (False, "upload_failed", ""))
    out = x_queue.post_due_replies(now=NOW)
    assert out[0]["status"] == "failed" and forgot == [REPLY["media_url"]]


def test_post_video_reply_never_falls_back_to_text(monkeypatch, tmp_path):
    monkeypatch.setattr(x_post, "x_credentials", lambda prefix: {"consumer_key": "a"})
    monkeypatch.setattr(x_media, "upload_media", lambda *a, **k: None)
    video = tmp_path / "a.mp4"
    video.write_bytes(b"x")
    assert x_post.post_video_reply(env_prefix="P_", text="t", video_path=video,
                                   in_reply_to="1", label="l") == (False, "upload_failed", "")


def test_reply_text_carries_no_link():
    text = x_post.long_form_reply_text("SpaceX Daily", 134)
    assert "http" not in text and "134" in text


# ----------------------------------------------------------------- media --
def test_srt_uploads_as_subtitles():
    assert x_media._TYPES[".srt"] == "text/srt"
    assert x_media._CATEGORY["text/srt"] == "subtitles"


def test_subtitles_request_shape():
    sent = {}

    class S:
        def post(self, url, **kw):
            sent.update(url=url, **kw)

            class R:
                def raise_for_status(self):
                    return None
            return R()
    creds = {"consumer_key": "a", "consumer_secret": "b", "access_token": "c",
             "access_token_secret": "d"}
    assert x_media.add_subtitles("111", "222", creds, session=S())
    assert sent["url"].endswith("/2/media/subtitles")
    assert sent["json"] == {"id": "111", "media_category": "TweetVideo",
                            "subtitles": {"display_name": "English", "id": "222",
                                          "language_code": "EN"}}


# ---------------------------------------------------------------- wiring --
def test_the_pilot_shows():
    on = {s for s in ("spacex", "fascinating_frontiers", "models_agents", "tesla", "omni_view")
          if load_config(ROOT / "shows" / f"{s}.yaml").publishing.x_long_form}
    assert on == {"spacex", "fascinating_frontiers", "models_agents"}


def test_the_mp4_is_hosted_before_the_cleanup_deletes_it():
    host = RUN_SHOW.index("_xq.host_file(long_video_path, config.slug)")
    cleanup = RUN_SHOW.index("            long_video_path.unlink()")
    assert host < cleanup
    assert "_ep_duration <= _xq.LONG_FORM_MAX_SECONDS" in RUN_SHOW
    assert x_queue.LONG_FORM_MAX_SECONDS == 20 * 60


def test_the_reply_is_queued_only_under_a_queued_post():
    i = RUN_SHOW.index("# Oct 17 2026: the full episode, as a reply under this post.")
    block = RUN_SHOW[i:i + 1200]
    assert "if _long_url and _queued:" in block and "x_queue.enqueue_reply(" in block
    assert "x_queue.forget_media(_u)" in block


def test_the_poster_runs_replies_and_the_workflow_has_time():
    script = (ROOT / "scripts" / "post_x_queue.py").read_text(encoding="utf-8")
    assert "x_queue.post_due_replies()" in script
    wf = (ROOT / ".github" / "workflows" / "x-queue.yml").read_text(encoding="utf-8")
    assert "timeout-minutes: 30" in wf


def test_the_migration_is_a_separate_table():
    sql = (ROOT / "supabase" / "migrations" / "20261017_x_post_replies.sql").read_text(encoding="utf-8")
    assert "create table if not exists public.x_post_replies" in sql
    assert "unique (show_slug, episode_num, kind)" in sql
    assert "enable row level security" in sql
