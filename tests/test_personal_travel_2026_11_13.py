"""Nerra Personal routes and trips (Nov 13 2026).

The traffic add-on follows a member's own routes ("Your commute"), and a
member's upcoming trips get a segment before the sign-off: the place's
angles once a week, the events during the stay as the dates near, what is
on each day of the stay. See engine/personal_travel.py.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from engine import personal_travel as pt
from engine.personal_edition import (
    PersonalSpec,
    build_local_brief_prompt,
    local_brief_addons,
    personal_chapter_pieces,
    validate_spec,
    wants_local_brief,
)

ROOT = Path(__file__).resolve().parent.parent
TOKEN = "a" * 32
MON = dt.date(2026, 11, 16)
SAT = dt.date(2026, 11, 21)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class TestRoutes:
    def test_clean_routes_requires_both_ends_and_closes_the_sets(self):
        routes = pt.clean_routes([
            {"from": "North Vancouver", "to": "Downtown <b>Vancouver</b>",
             "via": "Lions Gate Bridge", "days": "sometimes", "mode": "rocket"},
            {"from": "north vancouver", "to": "downtown vancouver",
             "via": "lions gate bridge"},                  # duplicate
            {"from": "", "to": "Burnaby"},                 # no origin
            {"from": "Home {date_spoken}", "to": "Gym", "days": "weekends",
             "mode": "cycle"},
            {"from": "A", "to": "B"}, {"from": "C", "to": "D"},
            "not a dict",
        ])
        assert len(routes) == pt.ROUTES_MAX
        first = routes[0]
        assert first.destination == "Downtown Vancouver"
        assert (first.days, first.mode) == ("weekdays", "any")
        assert "{" not in routes[1].origin
        assert routes[1].days == "weekends" and routes[1].mode == "cycle"

    def test_days(self):
        commute, gym = pt.clean_routes([
            {"from": "A", "to": "B"}, {"from": "C", "to": "D", "days": "weekends"}])
        assert commute.runs_on(MON) and not commute.runs_on(SAT)
        assert gym.runs_on(SAT) and not gym.runs_on(MON)
        assert pt.routes_today([commute, gym], SAT) == [gym]

    def test_commute_needs_the_traffic_addon_and_a_route_today(self):
        routes = pt.clean_routes([{"from": "A", "to": "B"}])
        assert pt.wants_commute(["traffic"], routes, MON)
        assert not pt.wants_commute(["weather"], routes, MON)   # switched off
        assert not pt.wants_commute(["traffic"], routes, SAT)   # not today
        assert not pt.wants_commute(["traffic"], [], MON)

    def test_commute_prompt_reads_reports_never_live_traffic(self):
        routes = pt.clean_routes([{"from": "Surrey", "to": "Vancouver",
                                   "via": "Highway 1", "mode": "drive"}])
        p = pt.build_commute_prompt(ROOT, routes, MON, "Sam", "Vancouver, BC")
        assert "Surrey to Vancouver via Highway 1, by car" in p
        assert "Monday, November 16, 2026" in p
        assert "never estimate a travel time" in p.lower()
        assert "SKIP" in p
        assert "{" not in p and "}" not in p

    def test_city_brief_drops_traffic_only_when_the_commute_ran(self):
        spec = PersonalSpec(token=TOKEN, shows=["spacex", "tesla"],
                            city="Vancouver, BC", addons=["traffic"])
        assert local_brief_addons(spec, commute_ran=False) == ["traffic"]
        assert local_brief_addons(spec, commute_ran=True) == []
        assert wants_local_brief(spec)
        assert not wants_local_brief(spec, local_brief_addons(spec, True))
        spec.addons = ["weather", "traffic"]
        p = build_local_brief_prompt(ROOT, spec, MON, "", addons=["weather"])
        assert "traffic or transit disruption" not in p


class TestTrips:
    def test_clean_trips(self):
        today = dt.date(2026, 11, 13)
        trips = pt.clean_trips([
            {"place": "Lisbon, Portugal", "start": "2026-12-01", "end": "2026-12-08"},
            {"place": "Kyoto", "start": "2026-12-10", "end": "2026-12-01"},  # end<start
            {"place": "Paris", "end": "2026-12-01"},                          # end alone
            {"place": "Rome", "start": "2026-11-01", "end": "2026-11-05"},   # over
            {"place": "Oslo", "start": "2031-01-01"},                         # too far
            {"place": "Banff", "start": "2026-12-01", "end": "2027-06-01"},  # too long
        ], today)
        assert [t.place for t in trips] == ["Lisbon, Portugal", "Kyoto", "Paris"]
        assert trips[1].end == trips[1].start
        assert trips[2].start is None and trips[2].end is None
        more = pt.clean_trips([{"place": p} for p in ("Oslo", "Banff")], today)
        assert [t.start for t in more] == [None, None]
        assert len(pt.clean_trips([{"place": f"P{i}"} for i in range(9)], today)) == pt.TRIPS_MAX

    def test_undated_trip_is_weekly_and_each_angle_once(self):
        trip = pt.Trip("Lisbon")
        heard = []
        told = []
        day = dt.date(2026, 11, 1)
        for _ in range(60):
            mode = pt.trip_mode(trip, day, heard)
            if mode:
                told.append((day, mode))
                heard.append({"date": day.isoformat(), "mode": mode})
            day += dt.timedelta(days=1)
        assert [m for _d, m in told] == list(pt.TRIP_ANGLES)
        gaps = [(b[0] - a[0]).days for a, b in zip(told, told[1:])]
        assert all(g == pt.TRIP_GAP_DAYS for g in gaps)

    def test_dated_trip_runs_up_to_and_through_the_stay(self):
        trip = pt.Trip("Lisbon", dt.date(2026, 12, 20), dt.date(2026, 12, 23))
        heard, told = [], {}
        day = dt.date(2026, 11, 20)
        while day <= dt.date(2026, 12, 26):
            mode = pt.trip_mode(trip, day, heard)
            if mode:
                told[day] = mode
                heard.append({"date": day.isoformat(), "mode": mode})
            day += dt.timedelta(days=1)
        modes = list(told.values())
        assert modes.count("events") == 1 and modes.count("events_final") == 1
        assert [told[dt.date(2026, 12, d)] for d in (20, 21, 22, 23)] == ["during"] * 4
        assert not any(d > dt.date(2026, 12, 23) for d in told)
        # The events come inside the near window, the final look in the last days.
        ev = next(d for d, m in told.items() if m == "events")
        fin = next(d for d, m in told.items() if m == "events_final")
        assert (trip.start - ev).days <= pt.TRIP_NEAR_DAYS
        assert (trip.start - fin).days <= pt.TRIP_FINAL_DAYS
        # Each angle at most once.
        for a in pt.TRIP_ANGLES:
            assert modes.count(a) <= 1

    def test_one_trip_an_edition_soonest_first(self):
        later = pt.Trip("Kyoto", dt.date(2027, 3, 1), dt.date(2027, 3, 9))
        soon = pt.Trip("Lisbon", dt.date(2026, 12, 1), dt.date(2026, 12, 5))
        undated = pt.Trip("Iceland")
        trip, mode = pt.plan_trip([undated, later, soon], dt.date(2026, 11, 20), {})
        assert trip is soon and mode == "events"
        assert pt.plan_trip([], MON, {}) is None

    def test_heard_keeps_only_current_trips(self):
        a, b = pt.Trip("Lisbon"), pt.Trip("Kyoto")
        heard = {"gone|": [{"date": "2026-11-01", "mode": "history"}]}
        out = pt.record_trip_heard(heard, a, "history", MON, [a, b])
        assert set(out) == {a.key}
        assert out[a.key] == [{"date": MON.isoformat(), "mode": "history"}]
        assert pt.prune_trip_heard(out, [b]) == {}

    def test_trip_prompts_render_and_ask_for_sources(self):
        trip = pt.Trip("Lisbon, Portugal", dt.date(2026, 12, 1), dt.date(2026, 12, 8))
        for mode in pt.TRIP_ANGLES + ("events", "events_final", "during"):
            day = dt.date(2026, 12, 3) if mode == "during" else dt.date(2026, 11, 20)
            p = pt.build_trip_prompt(ROOT, trip, mode, day, "Sam",
                                     "Lisbon: 18° and sunny" if mode == "during" else "")
            assert "Lisbon, Portugal" in p and "SKIP" in p
            assert "never from memory" in p
            assert "{" not in p and "}" not in p, mode
        p = pt.build_trip_prompt(ROOT, trip, "during", dt.date(2026, 12, 3), "Sam")
        assert "day 3 of their stay" in p

    def test_no_quotable_example_in_the_prompts(self):
        """De-seed by shape (CLAUDE.md): the prompts describe, never quote
        a sentence the model could copy."""
        for name in ("nerra_personal_commute.txt", "nerra_personal_trip.txt"):
            text = _read(f"shows/prompts/{name}")
            assert not re.search(r"(?i)for example, (say|start with)", text)


class TestSpecAndChapters:
    def test_validate_spec_carries_routes_and_trips(self):
        future = (dt.date.today() + dt.timedelta(days=30)).isoformat()
        spec = validate_spec({
            "token": TOKEN, "shows": ["spacex", "tesla"],
            "routes": [{"from": "Surrey", "to": "Vancouver"}],
            "trips": [{"place": "Lisbon", "start": future},
                      {"place": "Rome", "start": "2020-01-01"}],
        })
        assert [r.origin for r in spec.routes] == ["Surrey"]
        assert [t.place for t in spec.trips] == ["Lisbon"]
        plain = validate_spec({"token": TOKEN, "shows": ["spacex", "tesla"]})
        assert plain.routes == [] and plain.trips == []

    def test_chapters_place_commute_early_and_trip_before_signoff(self):
        from engine.personal_edition import Segment

        spec = PersonalSpec(token=TOKEN, shows=["spacex", "tesla"], city="Vancouver, BC")
        segs = [Segment(slug=s, show_name=s.title(), episode_num=1, episode_title="t",
                        hook="h", date="2026-11-16", audio_url="", content="",
                        digest_dir=ROOT, transcript_path=None, music_intro_offset=0.0)
                for s in spec.shows]
        durations = {"intro": 10, "local_1": 30, "commute": 20, "seg_spacex": 300,
                     "seg_tesla": 300, "handoff_1": 5, "trip": 40, "signoff": 8}
        title = pt.trip_chapter_title(pt.Trip("Lisbon"))
        rows = personal_chapter_pieces(spec, segs, durations, None, title)
        titles = [t for t, _d in rows]
        assert titles[:3] == ["Good morning from Mira", "Your Vancouver, BC brief",
                              pt.COMMUTE_CHAPTER_TITLE]
        assert titles[-2:] == ["Your trip to Lisbon", "Sign-off"]
        # With subchapters the tail still lines up: the trip is not a show.
        subs = {"spacex": [("Story two", 100.0)]}
        rows = personal_chapter_pieces(spec, segs, durations, subs, title)
        titles = [t for t, _d in rows]
        assert "Story two" in titles
        assert titles[-2:] == ["Your trip to Lisbon", "Sign-off"]
        assert abs(sum(d for _t, d in rows) - sum(durations.values())) < 1e-6


class TestWiring:
    def test_builder_wires_commute_and_trip(self):
        src = _read("scripts/build_personal_feeds.py")
        for marker in ("generate_commute(spec, target_date)",
                       "commute_ran=bool(commute_text)",
                       "generate_trip(spec, target_date, heard_before)",
                       '"trips_heard": trips_heard',
                       "if trip_piece:\n            splice.append(trip_piece)\n        splice.append(signoff)"):
            assert marker in src, marker
        # Personal data never reaches a log line: the builder logs the
        # token prefix and counts, never a route or a place.
        for line in src.splitlines():
            if "logger." in line:
                assert "routes" not in line and "trip.place" not in line, line

    def test_worker_mirrors_the_limits(self):
        ts = _read("workers/gallery/src/personal.ts")
        assert f"ROUTES_MAX = {pt.ROUTES_MAX}" in ts
        assert f"TRIPS_MAX = {pt.TRIPS_MAX}" in ts
        assert f"ROUTE_PART_MAX = {pt.ROUTE_PART_MAX}" in ts
        assert f"TRIP_PLACE_MAX = {pt.TRIP_PLACE_MAX}" in ts
        days = re.search(r"ROUTE_DAYS = \[([^\]]*)\]", ts).group(1)
        assert tuple(re.findall(r'"(\w+)"', days)) == pt.ROUTE_DAYS
        modes = re.search(r"ROUTE_MODES = \[([^\]]*)\]", ts).group(1)
        assert tuple(re.findall(r'"(\w+)"', modes)) == pt.ROUTE_MODES

    def test_account_page_and_privacy_policy(self):
        page = _read("account.html")
        assert page.count('class="me-row nn-route"') == pt.ROUTES_MAX
        assert page.count('class="me-row nn-trip"') == pt.TRIPS_MAX
        assert "routes: routeValues()" in page and "trips: tripValues()" in page
        for opt in pt.ROUTE_DAYS + pt.ROUTE_MODES:
            assert f'value="{opt}"' in page, opt
        assert "never written to a log" in page
        policy = _read("privacy-policy.html")
        assert "the routes and trips you add" in policy
