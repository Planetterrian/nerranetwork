"""Oct 17 2026: two X items left by the move to an East-coast morning.

1. Nerra Daily's post goes in its reserved 7:00 ET slot. The edition used to
   post straight from the build (~6:45 ET); it now hosts its cover on R2 and
   queues itself into the slot engine.release_schedule reserves for it, which
   engine.x_queue never hands to a show. No queue, or a failed enqueue, posts
   directly as before — and a queued edition NEVER also posts directly.

2. The follow ask is phased on the X posting order. engine.x_post had phased
   it on a hand-kept roster that stopped matching the order posts go out once
   the slots moved to engine.release_schedule. The roster's ORDER is now
   derived from the X slot rank; the Oct 15 guarantees are proven here over
   60 days: a daily show asks every fourth day, posting neighbours never ask
   on the same day, and a weekly show asks once in four of its weekdays.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import release_schedule as rs  # noqa: E402
from engine import x_post, x_queue  # noqa: E402
from engine.daily_edition import build_edition_metrics, edition  # noqa: E402

E = rs.EASTERN
UTC = dt.timezone.utc
START = dt.date(2026, 10, 19)  # a Monday
DAYS = [START + dt.timedelta(days=i) for i in range(60)]


def et(y, m, d, h, mi=0):
    return dt.datetime(y, m, d, h, mi, tzinfo=E)


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_daily_edition_t", ROOT / "scripts" / "build_daily_edition.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------ the 7:00 ET slot --
class TestTheQueueHandsOutTheReservedSlotOnRequest:
    def test_an_explicit_slot_is_used_when_free(self):
        now = et(2026, 10, 19, 6, 45)
        want = rs.x_slot(rs.NERRA_DAILY_SLUG, now)
        assert x_queue.slot_for("nerra_daily", [], now, want).astimezone(E) == et(2026, 10, 19, 7)

    def test_a_show_never_gets_seven_without_asking(self):
        assert x_queue.choose_slot("spacex", [], et(2026, 10, 19, 5)).astimezone(E) != et(2026, 10, 19, 7)
        assert x_queue.next_slot([], et(2026, 10, 19, 5)).astimezone(E) == et(2026, 10, 19, 7, 30)

    def test_a_taken_or_passed_slot_falls_back_to_the_grid(self):
        seven = et(2026, 10, 19, 7).astimezone(UTC)
        late = et(2026, 10, 19, 6, 58)
        assert x_queue.slot_for("nerra_daily", [], late, seven) != seven
        early = et(2026, 10, 19, 6, 30)
        assert x_queue.slot_for("nerra_daily", [seven], early, seven) != seven

    def test_enqueue_writes_the_requested_slot_and_the_hosted_url(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(x_queue, "configured", lambda: True)
        monkeypatch.setattr(x_queue, "_taken", lambda now: [])
        monkeypatch.setattr(x_queue, "_host", lambda *a: pytest.fail("already hosted"))

        def rest(method, path, **kw):
            seen.update(kw.get("json") or {})
            return [{"id": 1}]
        monkeypatch.setattr(x_queue, "_rest", rest)
        now = et(2026, 10, 19, 6, 40)
        ok, due = x_queue.enqueue(
            show_slug="nerra_daily", episode_num=60, env_prefix="NERRANETWORK_X_", text="t",
            media_url="https://audio.nerranetwork.com/x_queue/nerra_daily/c-ep060.jpg",
            media_kind="image", slot=rs.x_slot("nerra_daily", now), now=now)
        assert ok and due == "2026-10-19T11:00:00Z"
        assert seen["due_at"] == "2026-10-19T11:00:00Z"
        assert seen["media_url"].endswith("c-ep060.jpg") and seen["media_kind"] == "image"


class TestTheEditionQueuesIntoSeven:
    @pytest.fixture
    def builder(self, monkeypatch):
        mod = _load_builder()
        for k in ("CONSUMER_KEY", "CONSUMER_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET"):
            monkeypatch.setenv(f"NERRANETWORK_X_{k}", "x")
        return mod

    def test_a_queued_edition_never_posts_directly(self, builder, monkeypatch):
        calls = {}
        monkeypatch.setattr(x_queue, "configured", lambda: True)
        monkeypatch.setattr(x_queue, "host_file", lambda path, slug: (
            calls.setdefault("hosted", Path(path).name), f"https://audio.nerranetwork.com/x_queue/{slug}/{Path(path).name}")[1])

        def enqueue(**kw):
            calls["enqueue"] = kw
            return True, "2026-10-19T11:00:00Z"
        monkeypatch.setattr(x_queue, "enqueue", enqueue)
        monkeypatch.setattr(x_queue, "forget_media", lambda url: pytest.fail("kept media deleted"))
        monkeypatch.setattr(x_post, "post_media",
                            lambda **kw: pytest.fail("the edition queued AND posted directly"))
        out = builder.post_edition_to_x(edition("en"), 60, "Ep 60: A Monday edition",
                                        day=dt.date(2026, 10, 19), now=et(2026, 10, 19, 6, 44))
        assert out == (True, "", "2026-10-19T11:00:00Z")
        kw = calls["enqueue"]
        assert kw["show_slug"] == "nerra_daily" and kw["env_prefix"] == "NERRANETWORK_X_"
        assert kw["slot"].astimezone(E) == et(2026, 10, 19, 7)
        assert kw["media_kind"] == "image" and kw["media_url"].endswith("-ep060.jpg")
        assert calls["hosted"] == "nerra-daily-ep060.jpg"
        assert "Ep 60" in kw["text"] and "Ep 60: A Monday" not in kw["text"]

    def test_no_queue_posts_directly_as_before(self, builder, monkeypatch):
        monkeypatch.setattr(x_queue, "configured", lambda: False)
        monkeypatch.setattr(x_queue, "enqueue", lambda **kw: pytest.fail("no queue to use"))
        seen = {}

        def post_media(**kw):
            seen.update(kw)
            return True, "", "https://x.com/nerranetwork/status/1", kw["media_paths"][0]
        monkeypatch.setattr(x_post, "post_media", post_media)
        out = builder.post_edition_to_x(edition("en"), 60, "Ep 60: A title",
                                        day=dt.date(2026, 10, 19), now=et(2026, 10, 19, 6, 44))
        assert out == (True, "", "")
        assert seen["media_paths"][0].endswith("nerra-daily.jpg")

    def test_a_failed_enqueue_posts_directly_and_drops_the_hosted_copy(self, builder, monkeypatch):
        dropped = []
        monkeypatch.setattr(x_queue, "configured", lambda: True)
        monkeypatch.setattr(x_queue, "host_file", lambda path, slug: "https://audio.nerranetwork.com/x_queue/n/c.jpg")
        monkeypatch.setattr(x_queue, "enqueue", lambda **kw: (False, "queue_error"))
        monkeypatch.setattr(x_queue, "forget_media", dropped.append)
        monkeypatch.setattr(x_post, "post_media", lambda **kw: (False, "post_failed", "", ""))
        out = builder.post_edition_to_x(edition("en"), 60, "Ep 60: A title",
                                        day=dt.date(2026, 10, 19), now=et(2026, 10, 19, 6, 44))
        assert out == (False, "post_failed", "")
        assert dropped == ["https://audio.nerranetwork.com/x_queue/n/c.jpg"]

    def test_no_credentials_is_a_skip_before_the_queue(self, monkeypatch):
        mod = _load_builder()
        for k in ("CONSUMER_KEY", "CONSUMER_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET"):
            monkeypatch.delenv(f"NERRANETWORK_X_{k}", raising=False)
        monkeypatch.setattr(x_queue, "enqueue", lambda **kw: pytest.fail("queued with no keys"))
        assert mod.post_edition_to_x(edition("en"), 60, "t", day=dt.date(2026, 10, 19)) == \
            (False, "no_credentials", "")


class TestTheOutcomeIsRecorded:
    def test_the_metrics_carry_the_queue_outcome(self):
        m = build_edition_metrics(60, dt.date(2026, 10, 19), 60.0, [], links_source="llm",
                                  field_note_included=False, missing_expected=[], dropped=[],
                                  x_posted=True, x_post_queued=True,
                                  x_post_queued_for="2026-10-19T11:00:00Z")
        assert m["x_posted"] is True and m["x_post_queued"] is True
        assert m["x_post_queued_for"] == "2026-10-19T11:00:00Z"
        m = build_edition_metrics(60, dt.date(2026, 10, 19), 60.0, [], links_source="llm",
                                  field_note_included=False, missing_expected=[], dropped=[])
        assert m["x_post_queued"] is None and m["x_post_queued_for"] == ""

    def test_the_builder_wires_the_outcome_into_the_metrics(self):
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        assert "x_post_queued=bool(x_post_queued_for)," in src
        assert "x_post_queued_for=x_post_queued_for," in src

    def test_the_workflow_carries_the_queue_secrets_under_the_shared_names(self):
        daily = (ROOT / ".github/workflows/nerra-daily.yml").read_text(encoding="utf-8")
        for wf in ("x-queue.yml", "run-show.yml"):
            other = (ROOT / ".github/workflows" / wf).read_text(encoding="utf-8")
            for line in ("X_QUEUE_SUPABASE_URL: ${{ secrets.VOICES_SUPABASE_URL }}",
                         "X_QUEUE_SUPABASE_KEY: ${{ secrets.VOICES_SUPABASE_SERVICE_KEY }}",
                         "R2_ENDPOINT_URL: ${{ secrets.R2_ENDPOINT_URL }}",
                         "R2_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}",
                         "R2_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}"):
                assert line in other, (wf, line)
                assert line in daily, line


# ------------------------------------------------ the follow-ask phase --
def _asks(slug, day):
    return x_post.post_closers(slug, day)[0] in x_post.FOLLOW_ASK_CLOSERS


class TestThePhaseFollowsThePostingOrder:
    def test_the_roster_order_is_the_x_slot_order(self):
        slugs = x_post._roster_slugs()
        assert slugs[0] == "nerra_daily"
        run = et(2026, 10, 19, 4)
        times = [rs.x_slot(s, run) for s in slugs]
        assert all(t is not None for t in times)
        assert times == sorted(times) and len(set(times)) == len(times)

    def test_every_roster_show_has_a_release_rank(self):
        missing = [s for s in x_post._roster_slugs()
                   if s != rs.NERRA_DAILY_SLUG and s not in rs.RELEASE_ORDER]
        assert not missing, f"{missing} have no place in engine.release_schedule.RELEASE_ORDER"

    def test_moving_a_show_in_the_release_order_moves_its_phase(self, monkeypatch):
        order = list(rs.RELEASE_ORDER)
        order.remove("vancouver")
        order.insert(0, "vancouver")
        monkeypatch.setattr(rs, "RELEASE_ORDER", tuple(order))
        assert rs.x_posting_order(["spacex", "vancouver", "nerra_daily"]) == \
            ["nerra_daily", "vancouver", "spacex"]


class TestTheGuaranteeOverSixtyDays:
    def test_every_daily_show_asks_every_fourth_day(self):
        for slug, wd in x_post.FOLLOW_ASK_ROSTER:
            if wd is not None:
                continue
            days = [d for d in DAYS if _asks(slug, d)]
            assert days, slug
            gaps = {(b - a).days for a, b in zip(days, days[1:])}
            assert gaps == {x_post.FOLLOW_ASK_EVERY}, (slug, gaps)

    def test_posting_neighbours_never_ask_on_the_same_day(self):
        pairs = 0
        for day in DAYS:
            posting = [s for s, wd in x_post.FOLLOW_ASK_ROSTER if wd is None or wd == day.weekday()]
            for a, b in zip(posting, posting[1:]):
                pairs += 1
                assert not (_asks(a, day) and _asks(b, day)), (day, a, b)
        assert pairs >= 60 * 12  # twelve daily neighbour pairs a day, more on weekly days

    def test_weekly_shows_ask_once_in_four_of_their_weekdays(self):
        span = [START + dt.timedelta(days=i) for i in range(7 * 16)]  # 16 weeks
        for slug, wd in x_post.FOLLOW_ASK_ROSTER:
            if wd is None:
                continue
            assert not any(_asks(slug, d) for d in span if d.weekday() != wd), slug
            posting = [d for d in span if d.weekday() == wd]
            for i in range(0, len(posting), x_post.FOLLOW_ASK_EVERY):
                block = posting[i:i + x_post.FOLLOW_ASK_EVERY]
                assert sum(_asks(slug, d) for d in block) == 1, (slug, block[0])

    def test_weekly_shows_and_their_neighbours_on_their_weekdays(self):
        for slug, wd in x_post.FOLLOW_ASK_ROSTER:
            if wd is None:
                continue
            for day in (d for d in DAYS if d.weekday() == wd):
                posting = x_post._posters_on(day)
                i = posting.index(slug)
                if not _asks(slug, day):
                    continue
                for j in (i - 1, i + 1):
                    if 0 <= j < len(posting):
                        assert not _asks(posting[j], day), (day, slug, posting[j])

    def test_every_closer_list_still_ends_on_the_old_closer(self):
        for slug in x_post._roster_slugs():
            for day in DAYS:
                assert x_post.post_closers(slug, day)[-1] == x_post.CLIP_CLOSER
