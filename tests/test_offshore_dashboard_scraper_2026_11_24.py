"""Nov 24 2026 — the Offshore North fleet guide says when a boat page has
been unreadable for weeks.

Four of the twenty imoca.org boat pages (EMIRA IV's among them) had answered
200 with no facts since late September / late October. Each run logged four
per-boat warnings, kept the earlier record and marked it stale, which is the
right data behaviour, and nothing summed it up. ``fleet_stale_report`` is one
annotation: silent for a one-night miss, loud after two weeks or when every
page fails. It reads the dates the records already carry and writes nothing.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _mod():
    spec = importlib.util.spec_from_file_location(
        "fetch_offshore_north_dashboard_1124", ROOT / "scripts" / "fetch_offshore_north_dashboard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TODAY = dt.date(2026, 11, 24)


def _fresh(slug):
    return {"slug": slug, "architect": "A", "fetched": TODAY.isoformat()}


class TestFleetStaleReport:
    def test_all_fresh_is_silent(self):
        f = _mod()
        assert f.fleet_stale_report([_fresh("a"), _fresh("b")], today=TODAY) is None

    def test_one_night_miss_is_silent(self):
        f = _mod()
        fleet = [_fresh("a"), {"slug": "b", "fetched": "2026-11-23", "stale": True}]
        assert f.fleet_stale_report(fleet, today=TODAY) is None

    def test_weeks_stale_names_the_boat_and_its_last_read(self):
        f = _mod()
        fleet = [_fresh("a"), _fresh("c"),
                 {"slug": "emira-iv", "fetched": "2026-10-26", "stale": True},
                 {"slug": "b", "fetched": "2026-11-23", "stale": True}]
        note = f.fleet_stale_report(fleet, today=TODAY)
        assert note and "emira-iv (last read 2026-10-26)" in note
        assert "1 of 4" in note
        assert "b (last read" not in note

    def test_a_boat_never_read_is_named(self):
        f = _mod()
        note = f.fleet_stale_report([_fresh("a"), {"slug": "new-boat"}], today=TODAY)
        assert note and "new-boat (last read never)" in note

    def test_every_page_failing_is_loud_even_on_the_first_night(self):
        f = _mod()
        fleet = [{"slug": s, "fetched": "2026-11-23", "stale": True} for s in ("a", "b", "c")]
        note = f.fleet_stale_report(fleet, today=TODAY)
        assert note and "none of the 3" in note

    def test_empty_fleet_is_silent(self):
        f = _mod()
        assert f.fleet_stale_report([], today=TODAY) is None


class TestAFailedPageNeverLooksFresh:
    def test_failed_page_keeps_the_earlier_date_and_the_stale_mark(self, monkeypatch):
        f = _mod()

        class _Resp:
            text = "<html><body>no facts here</body></html>"

            def raise_for_status(self):
                return None

        import requests
        monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp())
        monkeypatch.setattr(f, "_rdr_entries", lambda: [
            {"imoca_slug": "emira-iv", "skipper": "Scott Shawyer", "boat": "EMIRA IV", "canada": True}])
        prev = {"fleet": [{"slug": "emira-iv", "architect": "Guillaume Verdier", "fetched": "2026-10-26"}]}
        out = f.collect_fleet(prev)
        assert out[0]["fetched"] == "2026-10-26"
        assert out[0]["stale"] is True
        assert out[0]["architect"] == "Guillaume Verdier"

    def test_main_prints_one_annotation(self, monkeypatch, tmp_path, capsys):
        f = _mod()
        fleet = [_fresh("a"), {"slug": "emira-iv", "fetched": "2026-10-26", "stale": True}]
        monkeypatch.setattr(f, "build", lambda previous=None: {
            "fetched_at": "x", "campaign_posts": [{"title": "t"}], "position": None,
            "headlines": [{"title": "h"}], "press": [], "fleet": fleet,
            "tracker": None, "instagram": []})
        out = tmp_path / "d.json"
        assert f.main(["--out", str(out)]) == 0
        printed = capsys.readouterr().out
        assert printed.count("::warning::") == 1 and "emira-iv" in printed
        assert json.loads(out.read_text())["fleet"][1]["fetched"] == "2026-10-26"

