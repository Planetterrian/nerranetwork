"""Nov 14 2026 — thumbnail impressions and click-through, and the map card
that read "Principles".

1. ``scripts/fetch_youtube_reach.py`` reads the Reporting API's reach report
   into ``api/youtube_reach.json``: absent is never 0, a CTR is printed only
   over ``CTR_MIN_IMPRESSIONS``, every video is read at the same age, and a
   failed night never shrinks the file.
2. The "Coming up" card stripped "First" from "First Principles" (Tesla, four
   long-forms Nov 9-14), and skipped maps that close on section names or say
   "come in that order".
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_youtube_reach as reach  # noqa: E402
from engine import long_form_cards as lfc  # noqa: E402

CSV = (
    "date,channel_id,video_id,live_or_on_demand,subscribed_status,country_code,"
    "video_thumbnail_impressions,video_thumbnail_impressions_ctr\n"
    "20261110,UC1,vidA,on_demand,subscribed,CA,300,0.05\n"
    "20261110,UC1,vidA,on_demand,not_subscribed,US,700,0.02\n"
    "20261110,UC1,vidB,on_demand,subscribed,CA,40,0.10\n"
)


def _items(text):
    got = lfc.rundown_items(text)
    return [t for t, _ in got] if got else None


class TestParse:
    def test_rows_sum_and_clicks_are_weighted(self):
        got = reach.parse_reach_csv(CSV)
        assert got["vidA"]["2026-11-10"] == [1000, 29.0]   # 15 + 14 clicks
        assert got["vidB"]["2026-11-10"] == [40, 4.0]

    def test_a_percent_column_is_read_as_percent(self):
        got = reach.parse_reach_csv(CSV.replace("0.05", "5.0").replace("0.02", "2.0")
                                    .replace("0.10", "10.0"))
        assert got["vidA"]["2026-11-10"] == [1000, 29.0]

    def test_a_changed_header_writes_nothing(self):
        assert reach.parse_reach_csv("date,video_id,views\n20261110,a,3\n") is None


class TestMergeAndPrune:
    def test_a_reissued_day_replaces_and_other_days_stay(self):
        videos = {"vidA": {"channel": "en", "days": {"2026-11-09": [5, 1.0],
                                                    "2026-11-10": [9, 1.0]}}}
        reach.merge_days(videos, "en", {"vidA": {"2026-11-10": [12, 2.0]}})
        assert videos["vidA"]["days"] == {"2026-11-09": [5, 1.0], "2026-11-10": [12, 2.0]}

    def test_old_days_go_and_an_empty_video_goes(self):
        videos = {"old": {"channel": "en", "days": {"2026-08-01": [5, 1.0]}},
                  "new": {"channel": "en", "days": {"2026-08-01": [5, 1.0],
                                                    "2026-11-10": [9, 1.0]}}}
        reach.prune(videos, dt.date(2026, 11, 14))
        assert "old" not in videos and list(videos["new"]["days"]) == ["2026-11-10"]


class TestSummary:
    STATS = {"shows": {"spacex": {"videos": [
        {"video_id": "L1", "kind": "long", "channel": "en", "published": "2026-11-01"},
        {"video_id": "L2", "kind": "long", "channel": "en", "published": "2026-11-12"},
        {"video_id": "S1", "kind": "short", "channel": "en", "published": "2026-11-01"},
    ]}}}

    def _days(self, start, n, impr, clicks):
        d0 = dt.date.fromisoformat(start)
        return {(d0 + dt.timedelta(days=i)).isoformat(): [impr, clicks] for i in range(n)}

    def test_first_week_only_and_young_videos_wait(self):
        videos = {
            "L1": {"channel": "en", "days": self._days("2026-11-01", 10, 100, 5.0)},
            "L2": {"channel": "en", "days": self._days("2026-11-12", 2, 100, 5.0)},
            "S1": {"channel": "en", "days": self._days("2026-11-01", 10, 10, 1.0)},
        }
        s = reach.summarise(videos, self.STATS, dt.date(2026, 11, 14))
        g = s["groups"]["en"]["long"]["_all"]
        # L1's first seven days only; L2 is not a week old yet.
        assert g == {"videos": 1, "impressions_week1": 700,
                     "impressions_week1_per_video": 700, "ctr_week1_pct": 5.0}
        # 70 impressions is under the floor: no rate, never a zero.
        assert s["groups"]["en"]["short"]["spacex"]["ctr_week1_pct"] is None

    def test_a_video_whose_rows_stop_early_is_not_read(self):
        videos = {"L1": {"channel": "en", "days": self._days("2026-11-01", 3, 100, 5.0)}}
        s = reach.summarise(videos, self.STATS, dt.date(2026, 11, 14))
        assert s["groups"] == {}


class FakeReq:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class FakeService:
    def __init__(self, jobs, types=("channel_reach_basic_a1",)):
        self._jobs, self._types, self.created = jobs, types, []
        outer = self

        class Jobs:
            def list(self):
                return FakeReq({"jobs": outer._jobs})

            def create(self, body):
                outer.created.append(body)
                return FakeReq({"id": "J9"})

        class Types:
            def list(self):
                return FakeReq({"reportTypes": [{"id": t} for t in outer._types]})

        self._j, self._t = Jobs(), Types()

    def jobs(self):
        return self._j

    def reportTypes(self):
        return self._t


class TestJob:
    def test_an_existing_job_is_used(self):
        svc = FakeService([{"id": "J1", "reportTypeId": "channel_reach_basic_a1"}])
        assert reach.ensure_job(svc) == ("J1", "ok") and not svc.created

    def test_a_missing_job_is_created_once(self):
        svc = FakeService([{"id": "J0", "reportTypeId": "channel_basic_a2"}])
        assert reach.ensure_job(svc) == ("J9", "job_created")
        assert svc.created == [{"reportTypeId": "channel_reach_basic_a1", "name": "nerra-reach"}]

    def test_an_unoffered_type_is_said_never_guessed(self):
        svc = FakeService([], types=("channel_basic_a2",))
        assert reach.ensure_job(svc) == (None, "unavailable") and not svc.created

    def test_read_reports_are_never_read_again(self):
        reps = [{"id": "r2", "startTime": "2026-11-11T08:00:00Z", "downloadUrl": "u2"},
                {"id": "r1", "startTime": "2026-11-10T08:00:00Z", "downloadUrl": "u1"},
                {"id": "r0", "startTime": "2026-11-09T08:00:00Z", "downloadUrl": "u0"}]
        assert [r["id"] for r in reach.pending_reports(reps, ["r0"])] == ["r1", "r2"]


class TestWiring:
    def test_the_nightly_runs_it_and_commits_its_file(self):
        wf = (ROOT / ".github/workflows/nightly-maintenance.yml").read_text(encoding="utf-8")
        assert "python scripts/fetch_youtube_reach.py || true" in wf
        assert "api/youtube_reach.json" in wf

    def test_the_register_names_it(self):
        reg = yaml.safe_load((ROOT / "docs/experiments.yaml").read_text(encoding="utf-8"))
        entries = reg["experiments"] if isinstance(reg, dict) else reg
        ids = {e.get("id") for e in entries}
        assert "youtube-reach-instrument-2026-11-14" in ids


class TestMapCard:
    def test_first_principles_keeps_its_first_word(self):
        assert _items("Cybercab battery design, Texas robotaxi registrations, Waymo’s "
                      "new coverage, then First Principles.")[-1] == "First Principles"
        assert _items("First Principles, electric semis on daily routes, and a "
                      "glass-roof redesign follow.")[0] == "First Principles"

    def test_an_opening_first_is_still_dropped(self):
        assert _items("First a Deep Dive on stacked guesses, then election-fact "
                      "mixups, Apple's China switch, Cool Stuff and Try This, and "
                      "Quick Bits.")[0] == "A Deep Dive on stacked guesses"

    def test_section_names_after_then_close_the_map(self):
        assert _items("Dividend screening inside a TFSA, a simulated Killam Apartment "
                      "hold, and the closed COIN trade — then Tools, Quick Hits, and "
                      "the record.")[-3:] == ["Tools", "Quick Hits", "The record"]

    def test_one_word_places_before_then_still_refuse(self):
        assert _items("Finland, Ontario, two power plants and a grid sale, then "
                      "Spotlight.") is None

    def test_in_that_order_and_is_next_are_trimmed(self):
        got = _items("Indonesia's vice-presidential choice, Europe at the next "
                     "Ukraine talks, and a tanker explosion in the Strait of Hormuz "
                     "come in that order, then Understanding the Issue.")
        assert got[2] == "A tanker explosion in the Strait of Hormuz"
        assert _items("Optimus reservations, Powerwall heat-pump software, and "
                      "owner-voted Superchargers are next, then First Principles."
                      )[2] == "Owner-voted Superchargers"

    def test_a_long_item_splits_at_and_plus_an_article_only(self):
        assert _items("Startup cheques in Seoul, a consent fight in Apple stores, and "
                      "a board probe follow, then the counterpoint and a look at who "
                      "still gets the heavier chatbot model.")[-2:] == [
            "The counterpoint", "A look at who still gets the heavier chatbot model"]
        assert "Super Heavy engines and Ship 40 at Starbase" in _items(
            "New Zealand’s Starshield trial, Super Heavy engines and Ship 40 at "
            "Starbase, and NASA’s next astronaut class, then Counterpoint, an "
            "Engineering Deep Dive, and a week in review.")

    def test_a_bare_later_is_not_an_item(self):
        assert _items("Grok's Starbase inspections, a NASA lunar-relay award, and a "
                      "New Glenn upgrade follow; later, The Counterpoint and the "
                      "engineering deep dive.") == [
            "Grok's Starbase inspections", "A NASA lunar-relay award",
            "A New Glenn upgrade", "The Counterpoint and the engineering deep dive"]
