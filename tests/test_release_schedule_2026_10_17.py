"""Oct 17 2026 — the network is timed to an East-coast morning.

Nerra Daily goes out at 7:00 AM New York time; each show's hook Short follows
from 7:00 ET in release order, its long-form in two waves (12:00 / 18:00 ET),
its X post from 7:30 ET, its newsletter at 7:00 ET. ``engine/release_schedule``
owns every one of those times; the YouTube upload, the X queue and the
newsletter send read it. A passed slot means "publish now" and so does any
failure, so scheduling can never cost an upload or a send.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import release_schedule as rs  # noqa: E402

E = rs.EASTERN
P = rs.PACIFIC
UTC = dt.timezone.utc
RUN_SHOW = (ROOT / "run_show.py").read_text(encoding="utf-8")

# The English YouTube shows in release order (Oct 17 2026).
EN_YT = ["spacex", "tesla", "modern_investing", "omni_view", "models_agents",
         "fascinating_frontiers", "planetterrian", "models_agents_beginners",
         "unintended_consequences", "first_principles", "dp_pod", "age_of_ai"]


def et(y, m, d, h, mi=0):
    return dt.datetime(y, m, d, h, mi, tzinfo=E)


def wall(t, tz=E):
    return t.astimezone(tz).strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------ order --
class TestOrder:
    def test_news_and_markets_lead_and_vancouver_closes(self):
        assert rs.RELEASE_ORDER[:3] == ("omni_view_world", "spacex", "tesla")
        assert rs.RELEASE_ORDER[-1] == "vancouver"
        assert len(set(rs.RELEASE_ORDER)) == len(rs.RELEASE_ORDER)

    def test_every_run_show_show_is_in_the_order(self):
        """A missing show still works (it goes last), but every show that
        runs today was placed on purpose."""
        import yaml
        missing = []
        for path in sorted((ROOT / "shows").glob("*.yaml")):
            if path.name.startswith("_"):
                continue
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            slug = doc.get("slug") if isinstance(doc, dict) else None
            if not slug or slug in ("age_of_ai", "nerra_voices"):
                continue  # interview shows publish outside run_show
            if (doc.get("access") or {}).get("mode") == "members_only":
                continue  # gated desks have no public release
            if slug not in rs.RELEASE_ORDER:
                missing.append(slug)
        assert missing == []

    def test_missing_shows_go_last_and_never_share_a_rank(self):
        order = rs.ranked(["tesla", "zeta_show", "alpha_show"])
        assert order == ["tesla", "alpha_show", "zeta_show"]
        assert rs.release_rank("brand_new", ["tesla"]) == 1

    def test_rank_counts_only_peers(self):
        assert rs.release_rank("tesla", EN_YT) == 1
        assert rs.release_rank("tesla") == 2  # against the whole tuple


# -------------------------------------------------------------- the Short --
class TestHookShort:
    def test_slots_run_every_fifteen_minutes_from_seven(self):
        run = et(2026, 10, 19, 5, 0)
        got = [wall(rs.youtube_short_time(s, run, peers=EN_YT)) for s in EN_YT[:4]]
        assert got == ["2026-10-19 07:00", "2026-10-19 07:15",
                       "2026-10-19 07:30", "2026-10-19 07:45"]

    def test_returns_aware_utc(self):
        t = rs.youtube_short_time("spacex", et(2026, 10, 19, 5), peers=EN_YT)
        assert t.tzinfo is not None and t.utcoffset() == dt.timedelta(0)
        assert t == dt.datetime(2026, 10, 19, 11, 0, tzinfo=UTC)

    def test_a_passed_slot_means_now(self):
        assert rs.youtube_short_time("spacex", et(2026, 10, 19, 9, 0), peers=EN_YT) is None

    def test_a_slot_inside_the_upload_lead_means_now(self):
        # 6:50 ET is ten minutes before 7:00: too close to promise YouTube.
        assert rs.youtube_short_time("spacex", et(2026, 10, 19, 6, 50), peers=EN_YT) is None
        assert rs.youtube_short_time("spacex", et(2026, 10, 19, 6, 40), peers=EN_YT) is not None

    def test_vancouver_gets_its_own_local_morning(self):
        # Runs 5:15 Pacific (8:15 ET) — 7:00 Pacific (10:00 ET) is ahead.
        t = rs.youtube_short_time("vancouver", dt.datetime(2026, 10, 19, 5, 15, tzinfo=P))
        assert wall(t, P) == "2026-10-19 07:00" and wall(t) == "2026-10-19 10:00"
        late = rs.youtube_short_time("vancouver", dt.datetime(2026, 10, 19, 7, 30, tzinfo=P))
        assert late is None

    def test_the_wall_clock_holds_across_the_clock_change(self):
        # Nov 1 2026: EDT (UTC-4) -> EST (UTC-5). 7:00 ET stays 7:00 ET.
        before = rs.youtube_short_time("spacex", et(2026, 10, 31, 5), peers=EN_YT)
        after = rs.youtube_short_time("spacex", et(2026, 11, 2, 5), peers=EN_YT)
        assert before == dt.datetime(2026, 10, 31, 11, 0, tzinfo=UTC)
        assert after == dt.datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
        assert wall(before)[-5:] == wall(after)[-5:] == "07:00"

    def test_naive_now_is_read_as_utc(self):
        naive = dt.datetime(2026, 10, 19, 9, 0)  # 5:00 ET
        assert rs.youtube_short_time("spacex", naive, peers=EN_YT) == \
            dt.datetime(2026, 10, 19, 11, 0, tzinfo=UTC)


# ---------------------------------------------------------- the long-form --
class TestLongForm:
    def test_two_waves_split_the_ranked_shows(self):
        run = et(2026, 10, 19, 5)
        got = {s: wall(rs.youtube_long_time(s, run, peers=EN_YT))[-5:] for s in EN_YT}
        # 12 shows -> six at noon, six at 6 PM.
        assert [got[s] for s in EN_YT[:6]] == ["12:00", "12:30", "13:00", "13:30", "14:00", "14:30"]
        assert [got[s] for s in EN_YT[6:]] == ["18:00", "18:30", "19:00", "19:30", "20:00", "20:30"]

    def test_odd_counts_give_the_extra_show_to_the_first_wave(self):
        peers = EN_YT[:3]
        run = et(2026, 10, 19, 5)
        assert [wall(rs.youtube_long_time(s, run, peers=peers))[-5:] for s in peers] == \
            ["12:00", "12:30", "18:00"]

    def test_long_follows_the_short(self):
        run = et(2026, 10, 19, 5)
        for s in EN_YT:
            assert rs.youtube_long_time(s, run, peers=EN_YT) > rs.youtube_short_time(s, run, peers=EN_YT)

    def test_a_passed_wave_means_now_and_a_later_one_still_holds(self):
        run = et(2026, 10, 19, 15, 0)  # a manual rerun at 3 PM
        assert rs.youtube_long_time("spacex", run, peers=EN_YT) is None
        assert wall(rs.youtube_long_time("planetterrian", run, peers=EN_YT))[-5:] == "18:00"

    def test_dst_boundary(self):
        a = rs.youtube_long_time("spacex", et(2026, 10, 31, 5), peers=EN_YT)
        b = rs.youtube_long_time("spacex", et(2026, 11, 2, 5), peers=EN_YT)
        assert a == dt.datetime(2026, 10, 31, 16, 0, tzinfo=UTC)
        assert b == dt.datetime(2026, 11, 2, 17, 0, tzinfo=UTC)


# ----------------------------------------------------------------------- X --
class TestXSlot:
    def test_the_edition_holds_seven(self):
        assert wall(rs.x_slot(rs.NERRA_DAILY_SLUG, et(2026, 10, 19, 5)))[-5:] == "07:00"

    def test_shows_start_at_half_past_seven_in_rank_order(self):
        run = et(2026, 10, 19, 5)
        assert wall(rs.x_slot("omni_view_world", run))[-5:] == "07:30"
        assert wall(rs.x_slot("spacex", run))[-5:] == "08:00"
        assert wall(rs.x_slot("tesla", run))[-5:] == "08:30"

    def test_every_show_slot_is_inside_the_window_and_none_is_seven(self):
        run = et(2026, 10, 19, 5)
        for s in rs.RELEASE_ORDER:
            t = rs.x_slot(s, run).astimezone(E)
            assert dt.time(7, 30) <= t.time() <= dt.time(22, 0), s

    def test_a_slot_past_the_window_is_none(self):
        peers = [f"show{i:02d}" for i in range(40)]
        assert rs.x_slot("show39", et(2026, 10, 19, 5), peers=peers) is None

    def test_a_passed_slot_is_none(self):
        assert rs.x_slot("omni_view_world", et(2026, 10, 19, 7, 28)) is None

    def test_reserved_slot_is_seven_et_on_both_sides_of_the_change(self):
        assert rs.x_reserved_slots(dt.date(2026, 10, 31)) == [dt.datetime(2026, 10, 31, 11, 0, tzinfo=UTC)]
        assert rs.x_reserved_slots(dt.date(2026, 11, 2)) == [dt.datetime(2026, 11, 2, 12, 0, tzinfo=UTC)]


# -------------------------------------------------------------- newsletter --
class TestNewsletter:
    def test_an_early_run_is_scheduled_for_seven_et(self):
        t = rs.newsletter_send_time("tesla", et(2026, 10, 19, 5, 30))
        assert t == dt.datetime(2026, 10, 19, 11, 0, tzinfo=UTC)

    def test_after_seven_it_sends_now(self):
        assert rs.newsletter_send_time("tesla", et(2026, 10, 19, 7, 5)) is None

    def test_a_run_from_the_day_before_does_not_wait_for_tomorrow(self):
        # 11 PM ET: the slot for that ET date has passed -> now, never
        # tomorrow morning.
        assert rs.newsletter_send_time("tesla", et(2026, 10, 19, 23, 0)) is None

    def test_vancouver_at_six_pacific(self):
        t = rs.newsletter_send_time("vancouver", dt.datetime(2026, 10, 19, 5, 15, tzinfo=P))
        assert wall(t, P) == "2026-10-19 06:00"
        assert rs.newsletter_send_time("vancouver", dt.datetime(2026, 10, 19, 6, 30, tzinfo=P)) is None

    def test_dst_boundary(self):
        assert rs.newsletter_send_time("tesla", et(2026, 10, 31, 5)) == dt.datetime(2026, 10, 31, 11, 0, tzinfo=UTC)
        assert rs.newsletter_send_time("tesla", et(2026, 11, 2, 5)) == dt.datetime(2026, 11, 2, 12, 0, tzinfo=UTC)

    def test_iso_utc(self):
        assert rs.iso_utc(et(2026, 10, 19, 7)) == "2026-10-19T11:00:00Z"
        assert rs.iso_utc(None) == ""


# ------------------------------------------------------- newsletter send --
class _Resp:
    status_code = 201
    text = ""

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class TestButtondownScheduling:
    def _post(self, monkeypatch, payload=None):
        from engine import newsletter
        sent = {}

        def fake_post(url, headers=None, json=None, timeout=None):
            sent.update(json)
            return _Resp(payload or {"id": "em_1", "num_recipients": 3})
        monkeypatch.setattr(newsletter.requests, "post", fake_post)
        return newsletter, sent

    def test_a_future_publish_date_schedules(self, monkeypatch):
        newsletter, sent = self._post(monkeypatch)
        when = dt.datetime.now(UTC) + dt.timedelta(hours=2)
        assert newsletter.send_newsletter("s", "b", api_key="k", publish_date=when) == "em_1"
        assert sent["status"] == "scheduled"
        assert sent["publish_date"] == when.strftime("%Y-%m-%dT%H:%M:%SZ")
        assert "scheduled" in newsletter._VALID_STATUSES

    def test_no_or_past_publish_date_sends_now(self, monkeypatch):
        newsletter, sent = self._post(monkeypatch)
        newsletter.send_newsletter("s", "b", api_key="k")
        assert sent["status"] == "about_to_send" and "publish_date" not in sent
        sent.clear()
        newsletter.send_newsletter("s", "b", api_key="k",
                                   publish_date=dt.datetime.now(UTC) - dt.timedelta(minutes=1))
        assert sent["status"] == "about_to_send" and "publish_date" not in sent

    def test_a_draft_stays_a_draft(self, monkeypatch):
        newsletter, sent = self._post(monkeypatch)
        newsletter.send_newsletter("s", "b", api_key="k", status="draft",
                                   publish_date=dt.datetime.now(UTC) + dt.timedelta(hours=1))
        assert sent["status"] == "draft" and "publish_date" not in sent

    def test_zero_recipients_on_a_scheduled_email_is_not_a_failure(self, monkeypatch):
        newsletter, sent = self._post(monkeypatch, {"id": "em_2", "num_recipients": 0})
        monkeypatch.setattr(newsletter, "_resolve_tag_ids", lambda tags, key: {"Tesla": "tag_1"})
        when = dt.datetime.now(UTC) + dt.timedelta(hours=1)
        assert newsletter.send_newsletter("s", "b", api_key="k", tags=["Tesla"],
                                          publish_date=when) == "em_2"
        # ...and still is on a send-now email.
        assert newsletter.send_newsletter("s", "b", api_key="k", tags=["Tesla"]) is None


class TestShowNewsletterUsesTheSchedule:
    def test_send_show_newsletter_passes_the_release_time(self):
        src = (ROOT / "engine" / "newsletter.py").read_text(encoding="utf-8")
        body = src[src.index("def send_show_newsletter("):src.index("def _lastsend_path(")]
        assert "newsletter_send_time(" in body
        assert '_send_kwargs["publish_date"] = _when' in body
        # Only an episode send in the about_to_send state is timed.
        assert 'if episode_num and _status == "about_to_send":' in body

    def test_the_double_send_guard_keys_on_creation_time(self):
        src = (ROOT / "engine" / "newsletter.py").read_text(encoding="utf-8")
        record = src[src.index("def _record_send("):src.index("def _buttondown_slug_for(")]
        assert "_dt.datetime.now(_dt.timezone.utc).isoformat()" in record

    def test_weekly_newsletters_are_untouched(self):
        weekly = (ROOT / "scripts" / "run_weekly_newsletters.py").read_text(encoding="utf-8")
        assert "publish_date" not in weekly and "release_schedule" not in weekly


# ----------------------------------------------------------------- wiring --
class TestYouTubeWiring:
    def _body(self):
        i = RUN_SHOW.index("def _publish_youtube")
        return RUN_SHOW[i:RUN_SHOW.find("\ndef ", i + 10)]

    def test_long_and_hook_short_take_the_release_slot(self):
        body = self._body()
        assert "youtube_long_time(" in body and "youtube_short_time(" in body
        assert "publish_at=_long_publish_at" in body
        assert "else (_short1_at if short_idx == 0 else None)" in body

    def test_later_shorts_are_staggered_from_the_hook_short(self):
        body = self._body()
        stagger = body[body.index("_stagger_times = stagger_publish_times("):]
        assert "_short1_at or datetime.datetime.now(" in stagger[:400]

    def test_a_scheduled_long_form_queues_its_comment(self):
        body = self._body()
        blk = body[body.index("if _pin_text and _long_publish_at is not None:"):]
        assert "queue_comment(" in blk[:800] and "publish_at=_long_publish_at" in blk[:800]

    def test_only_a_public_show_is_scheduled(self):
        body = self._body()
        setup = body[body.index("_release_on = bool("):body.index("_release_peers:")]
        assert "release_schedule_enabled" in setup and '"public"' in setup

    def test_a_refused_publish_at_uploads_now(self):
        body = self._body()
        assert body.count("_schedule_refused(_sched_exc)") == 2

    def test_config_gate(self):
        from engine.config import YouTubeConfig, load_config
        assert YouTubeConfig().release_schedule_enabled is False
        assert load_config(ROOT / "shows" / "tesla.yaml").youtube.release_schedule_enabled is True

    def test_scheduled_times_are_recorded(self):
        pipe = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert '"long_publish_at", "short_publish_at"' in pipe

    def test_metrics_record_the_publish_times(self):
        from engine.pipeline import record_youtube_outcomes
        got = {}
        m = SimpleNamespace(record=lambda k, v: got.__setitem__(k, v))
        record_youtube_outcomes(m, {"long_url": "u", "long_publish_at": "2026-10-19T16:00:00Z",
                                    "short_publish_at": "2026-10-19T11:00:00Z"}, 1.0,
                                config=SimpleNamespace(youtube=SimpleNamespace(enabled=True)))
        assert got["youtube_long_publish_at"] == "2026-10-19T16:00:00Z"
        assert got["youtube_short_publish_at"] == "2026-10-19T11:00:00Z"


class TestCommentSweepWorkflow:
    def test_x_queue_runs_the_sweep_half_hourly_without_committing(self):
        wf = (ROOT / ".github" / "workflows" / "x-queue.yml").read_text(encoding="utf-8")
        step = wf[wf.index("Post comments on scheduled videos"):]
        assert "post_scheduled_short_comments.py --stateless" in step
        assert "continue-on-error: true" in step and "!cancelled()" in step
        for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN_EN",
                  "YOUTUBE_REFRESH_TOKEN_RU", "YOUTUBE_REFRESH_TOKEN_FR"):
            assert f"{k}: ${{{{ secrets.{k} }}}}" in step
        assert "timeout-minutes: 30" in wf
        assert "contents: read" in wf  # it never commits; --stateless is why


@pytest.mark.parametrize("now_h", [4, 6])
def test_queue_comment_round_trip_for_a_long_form(tmp_path, now_h):
    from engine.shorts_stagger import queue_comment
    when = rs.youtube_long_time("spacex", et(2026, 10, 19, now_h), peers=EN_YT)
    assert queue_comment(tmp_path, video_id="L", channel="en", text="t", publish_at=when)
    data = json.loads((tmp_path / "scheduled_comments.json").read_text())
    assert data["pending"][0]["publish_at"] == "2026-10-19T16:00:00Z"
