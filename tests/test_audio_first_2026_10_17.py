"""Audio first, video after (Oct 17 2026).

A run used to commit once, at the end, so an episode reached main ~35 minutes
after its run started while the audio, feed, summaries and blog post were done
in ~15. run_show now pushes the episode between the two halves through
scripts/checkpoint_publish.sh, then rewrites the feed item and the blog post
when YouTube adds its links, on the SAME feed GUID.
"""
from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RUN_SHOW = (ROOT / "run_show.py").read_text(encoding="utf-8")
WF = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")


# ----------------------------------------------------------------- order --
def test_the_episode_is_complete_before_the_video():
    # Oct 18 2026: the video and X code moved out of run() into module-level
    # functions (the separate video job runs them too); the order holds in
    # run() and inside the video stage.
    run_start = RUN_SHOW.index("def run(args: argparse.Namespace) -> None:")
    run_body = RUN_SHOW[run_start:RUN_SHOW.index("\ndef ", run_start + 10)]
    pos = {k: run_body.index(k) for k in (
        "    _write_rss_feed()\n",
        "    save_summary_to_github_pages(",
        "    _write_blog_post()\n",
        "    validation_passed = run_post_validation(",
        "    _checkpoint_publish(args, metrics)",
        "        _run_video_stage(",
        "    # 12b. Send newsletter",
        "        _run_x_stage(",
    )}
    order = sorted(pos, key=pos.get)
    assert order == list(pos), order
    stage = RUN_SHOW[RUN_SHOW.index("def _run_video_stage("):RUN_SHOW.index("def _run_x_stage(")]
    pos = {k: stage.index(k) for k in (
        "    youtube_urls = _publish_youtube(",
        "        _write_rss_feed(youtube_long_url, refresh=True,",
        # Oct 31 2026: the post is written with the scheduled video's
        # release instant (hidden until then), never a blank link.
        "        _write_blog_post(\n            youtube_long_url, youtube_short_url, refresh=True,",
        "    # 12b. Video podcast (July 2026 pilot).",
    )}
    order = sorted(pos, key=pos.get)
    assert order == list(pos), order
    assert "    # 13. Post to X" in RUN_SHOW[RUN_SHOW.index("def _run_x_stage("):]


def test_the_refresh_never_notifies_directories_twice():
    fn = RUN_SHOW[RUN_SHOW.index("    def _write_rss_feed("):RUN_SHOW.index("    return _write_rss_feed\n")]
    assert "keep_existing_guid=refresh" in fn
    assert fn.index("if refresh:\n            return") < fn.index("notify_directories(")


# ------------------------------------------------------------------ GUID --
def _feed(tmp_path, **kw):
    from engine.publisher import update_rss_feed
    mp3 = tmp_path / "ep.mp3"
    mp3.write_bytes(b"\0" * 1000)
    rss = tmp_path / "feed.rss"
    base = dict(rss_path=rss, episode_num=5, episode_title="Ep 5",
                episode_description="Notes.", episode_date=dt.date(2026, 10, 17),
                mp3_filename="ep.mp3", mp3_duration=600.0, mp3_path=mp3,
                guid_prefix="show", audio_url="https://audio.example/ep.mp3")
    base.update(kw)
    update_rss_feed(**base)
    return rss.read_text(encoding="utf-8")


def _guids(xml):
    import re
    return re.findall(r"<guid[^>]*>([^<]+)</guid>", xml)


def test_the_refresh_keeps_the_published_guid(tmp_path):
    first = _guids(_feed(tmp_path))
    second_xml = _feed(tmp_path, episode_description="Notes.\n\nWatch on YouTube: https://y/1",
                       keep_existing_guid=True)
    assert _guids(second_xml) == first and len(first) == 1
    assert "https://y/1" in second_xml


def test_without_the_flag_a_rewrite_still_mints_a_new_guid(tmp_path):
    first = _guids(_feed(tmp_path))
    assert _guids(_feed(tmp_path)) != first


# ------------------------------------------------------------- the switch --
def test_checkpoint_needs_the_workflow_switch(monkeypatch):
    import run_show
    monkeypatch.delenv(run_show.AUDIO_FIRST_ENV, raising=False)
    assert run_show._checkpoint_publish(SimpleNamespace(show="s", test=False), None) is False
    monkeypatch.setenv(run_show.AUDIO_FIRST_ENV, "1")
    assert run_show._checkpoint_publish(SimpleNamespace(show="s", test=True), None) is False


def test_the_workflow_turns_it_on_outside_test_mode():
    assert ("NERRA_AUDIO_FIRST_PUSH: ${{ github.event.inputs.test_mode == 'true' && '0' || '1' }}"
            in WF)
    assert "bash scripts/stage_show_artifacts.sh" in WF


def test_the_duplicate_guard_reads_the_checkpoint_commit():
    # "Auto-generated: <show> <date> (audio)" must count as published.
    assert "m.startswith(marker)" in WF
    script = (ROOT / "scripts" / "checkpoint_publish.sh").read_text(encoding="utf-8")
    assert 'git commit -q -m "Auto-generated: ${SHOW} $(date -u +%Y-%m-%d) (audio)"' in script


# ------------------------------------------------------------- real git --
pytestmark_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), check=True,
                          capture_output=True, text=True)


@pytest.fixture()
def clone(tmp_path):
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git("init", "--bare", "--initial-branch=main", cwd=origin)
    work = tmp_path / "work"
    work.mkdir()
    _git("init", "--initial-branch=main", cwd=work)
    _git("config", "user.email", "t@example.com", cwd=work)
    _git("config", "user.name", "T", cwd=work)
    (work / "scripts").mkdir()
    for name in ("checkpoint_publish.sh", "stage_show_artifacts.sh", "push_show_artifacts.sh"):
        shutil.copy(ROOT / "scripts" / name, work / "scripts" / name)
    (work / "digests" / "s").mkdir(parents=True)
    (work / "digests" / "s" / "old.md").write_text("old\n")
    (work / "run_notes.txt").write_text("v1\n")
    _git("add", "-A", cwd=work)
    _git("commit", "-m", "seed", cwd=work)
    _git("remote", "add", "origin", str(origin), cwd=work)
    _git("push", "-u", "origin", "main", cwd=work)
    return work, origin


def _checkpoint(work):
    import os
    return subprocess.run(["bash", "scripts/checkpoint_publish.sh"], cwd=str(work),
                          env={**os.environ, "SHOW": "s", "PUSH_ATTEMPTS": "1"},
                          capture_output=True, text=True)


@pytestmark_git
def test_the_checkpoint_lands_on_main_while_the_run_is_still_writing(clone):
    work, origin = clone
    (work / "digests" / "s" / "S_Ep005_20261017.md").write_text("episode\n")
    (work / "run_notes.txt").write_text("v2, still being written\n")  # unstaged, tracked
    done = _checkpoint(work)
    assert done.returncode == 0, done.stdout + done.stderr
    log = _git("log", "-1", "--format=%s", "main", cwd=origin).stdout.strip()
    assert log.startswith("Auto-generated: s ") and log.endswith("(audio)")
    shown = _git("show", "--stat", "--format=", "main", cwd=origin).stdout
    assert "S_Ep005_20261017.md" in shown and "run_notes.txt" not in shown
    assert (work / "run_notes.txt").read_text() == "v2, still being written\n"


@pytestmark_git
def test_a_failed_push_leaves_everything_staged_for_the_final_commit(clone):
    work, origin = clone
    head = _git("rev-parse", "HEAD", cwd=work).stdout.strip()
    _git("remote", "set-url", "origin", str(origin) + "-missing", cwd=work)
    (work / "digests" / "s" / "S_Ep005_20261017.md").write_text("episode\n")
    done = _checkpoint(work)
    assert done.returncode != 0
    assert _git("rev-parse", "HEAD", cwd=work).stdout.strip() == head
    staged = _git("diff", "--cached", "--name-only", cwd=work).stdout
    assert "digests/s/S_Ep005_20261017.md" in staged


# --------------------------------------------- a long-form scheduled later --
def test_the_feed_says_when_a_scheduled_long_form_goes_public():
    from engine.release_schedule import describe_public_at
    morning = dt.datetime(2026, 10, 19, 10, 30, tzinfo=dt.timezone.utc)  # 6:30 AM EDT
    assert describe_public_at("2026-10-19T16:30:00Z", now=morning) == "12:30 PM ET"
    assert describe_public_at("2026-10-19T09:00:00Z", now=morning) == ""
    assert describe_public_at("", now=morning) == ""
    assert describe_public_at("garbage", now=morning) == ""
    assert "Watch on YouTube{_when}" in RUN_SHOW


def test_the_feed_refresh_after_the_video_is_non_fatal():
    i = RUN_SHOW.index("# 12d. The YouTube links reach the feed item")
    block = RUN_SHOW[i:i + 900]
    assert "try:" in block and "Feed refresh with the YouTube link failed (non-fatal)" in block
