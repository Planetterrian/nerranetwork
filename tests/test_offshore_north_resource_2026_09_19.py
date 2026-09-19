"""Drift guards for the Offshore North resource pass (19 September 2026).

Operator brief: keep improving the show, blog, website and dashboard so
they become a real resource for people interested in the sport. Shipped:

* the computed CAMPAIGN STATUS block (``engine/offshore_north_status.py``)
  — the show's verified campaign record rendered into both prompts by the
  clock: last known position with its age, race states (NOT STARTED /
  RUNNING / FINISHED) from official dates, results on record, the Route du
  Rhum entry, the countdown. One record, two surfaces: the dashboard
  bakes the same JSON in, so the show and the page cannot disagree;
* the Plain Sailing glossary page (``offshore-north-glossary.html``) —
  a hand-written, sourced glossary plus the archive of every aired
  explainer with a link that opens the audio at the segment;
* dashboard v2 — an "In the press" rail resolved to publisher URLs, race
  states on the calendar, the Défi Azimut result, the Route du Rhum
  entries' 48H Azimut form, and the verified absence of EMIRA IV from
  Lorient recorded as a dated note, never as a position;
* Offshore North blog posts carry a companion-resources panel.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_CURATED = _ROOT / "site" / "data" / "offshore_north_dashboard.json"
_GLOSSARY = _ROOT / "site" / "data" / "offshore_north_glossary.json"


def _read(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _curated() -> dict:
    return json.loads(_CURATED.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# The computed campaign status block
# ---------------------------------------------------------------------------

class TestCampaignStatusBlock:
    NOW = dt.datetime(2026, 9, 21, 13, 0, tzinfo=dt.timezone.utc)

    def test_race_state_by_the_clock(self):
        from engine.offshore_north_status import race_state

        when = dt.datetime(2026, 11, 1, 12, 2, tzinfo=dt.timezone.utc)
        end = dt.datetime(2026, 11, 30, tzinfo=dt.timezone.utc)
        assert race_state(when, end, dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)) == "NOT STARTED"
        assert race_state(when, end, dt.datetime(2026, 11, 10, tzinfo=dt.timezone.utc)) == "RUNNING"
        assert race_state(when, end, dt.datetime(2026, 12, 5, tzinfo=dt.timezone.utc)) == "FINISHED"
        assert race_state(None, None, self.NOW) == "DATE UNKNOWN"

    def test_block_from_the_committed_record(self):
        """The Ep005 error class, by construction: on 21 Sep the block says
        the Défi Azimut is FINISHED and EMIRA IV did not sail it, the Route
        du Rhum is NOT STARTED with the campaign ENTERED, the newest fix is
        dated and aged, and the countdown is arithmetic."""
        from engine.offshore_north_status import build_campaign_status

        out = build_campaign_status(_curated(), now=self.NOW)
        assert "LAST KNOWN POSITION / MOVEMENT: 2026-09-02 (19 days ago)" in out
        assert "heading back to Europe" in out
        assert "Défi Azimut-Lorient Agglomération (15 September 2026): FINISHED" in out
        assert "EMIRA IV not entered / did not sail" in out
        assert "Route du Rhum – Destination Guadeloupe start (1 November 2026): NOT STARTED — 41 days to go. EMIRA IV ENTERED." in out
        assert "783 days to the Vendée Globe start (12 November 2028)" in out
        assert "RESULTS ON RECORD" in out and "Sam Goodchild" in out and "United by the Ocean" in out
        assert "22 registered" in out and "Scott Shawyer IS on the list" in out
        assert "unconfirmed" in out  # only inside the "never 'unconfirmed'" instruction
        assert "position unconfirmed" not in out.lower()

    def test_live_fix_wins_only_when_newer(self):
        from engine.offshore_north_status import build_campaign_status

        older = {"position": {"date": "2026-08-01", "text": "old", "url": "u", "channel": "c"}}
        newer = {"position": {"date": "2026-09-20", "text": "Arrived in Lorient", "url": "u2", "channel": "Scott's Notes"}}
        assert "2026-09-02 (19 days ago)" in build_campaign_status(_curated(), live=older, now=self.NOW)
        out = build_campaign_status(_curated(), live=newer, now=self.NOW)
        assert "2026-09-20 (1 day ago) — Arrived in Lorient — Scott's Notes" in out

    def test_empty_record_degrades_to_nothing(self):
        from engine.offshore_north_status import build_campaign_status, campaign_status_from_files

        assert build_campaign_status({}, now=self.NOW) == ""
        assert isinstance(campaign_status_from_files(now=self.NOW), str)

    def test_wired_into_hook_prompts_and_defaults(self):
        hook = _read("shows/hooks/offshore_north.py")
        assert 'ctx["campaign_status"] = campaign_status_from_files()' in hook
        assert "{campaign_status}" in _read("shows/prompts/offshore_north_digest.txt")
        assert "{campaign_status}" in _read("shows/prompts/offshore_north_podcast.txt")
        assert 'template_vars.setdefault("campaign_status", "")' in _read("run_show.py")
        assert 'pod_vars.setdefault("campaign_status", "")' in _read("engine/pipeline.py")

    def test_prompts_render_without_the_hook(self):
        """The setdefault contract in practice: both prompts format with an
        empty block (the hook-failure path) and never KeyError."""
        from engine.generator import load_prompt

        for rel in ("shows/prompts/offshore_north_digest.txt", "shows/prompts/offshore_north_podcast.txt"):
            text = load_prompt(str(_ROOT / rel))
            keys = set(re.findall(r"(?<!\{)\{([a-z_]+)\}(?!\})", text))
            assert "campaign_status" in keys
            text.format_map({k: "" for k in keys})


# ---------------------------------------------------------------------------
# The verified record (19 Sep 2026 refresh)
# ---------------------------------------------------------------------------

class TestCuratedRecord:
    def test_defi_azimut_absence_is_a_note_not_a_position(self):
        d = _curated()
        azimut = next(c for c in d["countdowns"] if c["id"] == "defi_azimut")
        assert azimut["emira_entered"] is False and azimut.get("source")
        assert d["position_log"][-1]["date"] == "2026-09-02"  # no invented fix
        assert "not among the 14 IMOCA" in d["position_note"]["text"]

    def test_results_and_form(self):
        d = _curated()
        azimut = d["results"][0]
        assert azimut["event"].startswith("Défi Azimut") and azimut["podium"][0]["skipper"].startswith("Sam Goodchild")
        assert azimut["podium"][0]["note"].startswith("1d 14h 48m 21s")
        entries = {e["skipper"]: e for e in d["rdr_imoca_entries"]["entries"]}
        assert d["rdr_imoca_entries"]["total_registered"] == 22
        assert entries["Sam Goodchild"]["azimut_48h"] == "1st"
        assert entries["Scott Shawyer"]["azimut_48h"] == "did not sail"
        assert entries["Boris Herrmann"]["azimut_48h"] == "—"

    def test_dated_calendar_entries_carry_iso_windows_or_none(self):
        for e in _curated()["calendar"]:
            if "start" in e:
                dt.date.fromisoformat(e["start"]); dt.date.fromisoformat(e["end"])
                assert e["start"] <= e["end"]

    def test_standing_facts_and_field_guide_carry_the_result(self):
        facts = _read("shows/prompts/offshore_north_standing_facts.txt")
        guide = _read("shows/prompts/offshore_north_field_guide.txt")
        assert "EMIRA IV did NOT sail the Défi Azimut" in facts
        assert "22 IMOCA registered there as of 19 September 2026" in facts
        assert "won by Sam Goodchild" in guide and "32.1 knots" in guide
        assert "whether EMIRA IV sails it: confirm before use" not in guide

    def test_segment_bank_spec_is_the_class_draught_not_beam(self):
        bank = _read("shows/segments/offshore_north.json")
        assert "max beam 4.50 m" not in bank and "max draft 4.50 m" in bank


# ---------------------------------------------------------------------------
# The glossary page
# ---------------------------------------------------------------------------

class TestGlossaryPage:
    def test_data_shape(self):
        g = json.loads(_GLOSSARY.read_text(encoding="utf-8"))
        terms = [t for grp in g["groups"] for t in grp["terms"]]
        assert len(terms) >= 50
        for t in terms:
            for key in ("term", "gist", "body", "repeat", "keywords"):
                assert t.get(key), (t.get("term"), key)
            assert len(t["body"]) < 900, t["term"]
        names = [t["term"] for t in terms]
        assert len(names) == len(set(names))
        assert "Ocean Fifty" in names and "Vintage Multi and Vintage Mono" in names

    def test_generator_derives_the_archive_from_digests(self):
        import generate_html as gh

        aired = gh._offshore_north_plain_sailing()
        assert len(aired) >= 5
        assert [a["episode_num"] for a in aired] == sorted((a["episode_num"] for a in aired), reverse=True)
        ep5 = next(a for a in aired if a["episode_num"] == 5)
        assert ep5["at"] == "3:47" and ep5["audio_url"].endswith("#t=227")
        assert ep5["url"] == "blog/offshore_north/ep005.html"
        from engine.titles import PLAIN_SAILING_TITLE_MAX
        assert all(len(a["title"]) <= PLAIN_SAILING_TITLE_MAX for a in aired)

    def test_page_renders_and_is_wired(self, tmp_path, monkeypatch):
        import generate_html as gh

        out = gh.generate_offshore_north_glossary(dry_run=True)
        assert out is not None
        src = _read("generate_html.py")
        assert src.count("generate_offshore_north_glossary(dry_run=args.dry_run)") == 3
        assert '"offshore-north-glossary.html"]' in src  # sitemap
        assert "offshore-north-glossary.html" in _read("templates/show_page.html.j2")
        assert "offshore-north-glossary.html" in _read("templates/offshore_north_dashboard.html.j2")
        assert "offshore-north-glossary.html" in _read(".github/workflows/nightly-maintenance.yml")

    def test_rendered_page_carries_terms_and_archive(self):
        html = _read("offshore-north-glossary.html")
        assert html.count('class="on-term"') >= 50
        assert "Play from 3:47" in html
        assert "Heard on Ep" in html


# ---------------------------------------------------------------------------
# Dashboard v2 + blog panel
# ---------------------------------------------------------------------------

class TestDashboardV2:
    def test_fetch_script_has_a_press_rail_resolved_to_publishers(self):
        src = _read("scripts/fetch_offshore_north_dashboard.py")
        assert "def collect_press" in src and "resolve_google_news_url" in src
        assert '"press": press' in src
        # a dark press query keeps yesterday's rail (never shrinks the file)
        assert 'data["press"] = previous.get("press", [])' in src

    def test_press_parsing_drops_the_campaign_site_and_keeps_publishers(self, monkeypatch):
        import feedparser
        sys.path.insert(0, str(_ROOT / "scripts"))
        import fetch_offshore_north_dashboard as f

        feed = feedparser.parse(
            '<?xml version="1.0"?><rss version="2.0"><channel>'
            '<item><title>Collingwood man to brave Southern Ocean - CP24</title><link>https://www.cp24.com/x</link><pubDate>Tue, 01 Sep 2026 10:00:00 GMT</pubDate></item>'
            '<item><title>Thank you Canada - Canada Ocean Racing</title><link>https://www.canadaoceanracing.com/thank-you/</link><pubDate>Wed, 02 Sep 2026 10:00:00 GMT</pubDate></item>'
            "</channel></rss>"
        )
        monkeypatch.setattr(f, "_parse_feed", lambda url: feed)
        items = f.collect_press()
        assert [i["url"] for i in items] == ["https://www.cp24.com/x"]
        assert items[0]["outlet"] == "CP24" and items[0]["title"] == "Collingwood man to brave Southern Ocean"

    def test_template_v2_surfaces(self):
        tpl = _read("templates/offshore_north_dashboard.html.j2")
        assert 'id="onPress"' in tpl
        assert 'data-start="{{ e.get(\'start\', \'\') }}"' in tpl
        assert "azimut_48h" in tpl and "r.get('extra', [])" in tpl
        assert "position_note" in tpl

    def test_blog_posts_carry_the_companion_panel(self):
        from engine.blog import SHOW_RESOURCES, _show_resources

        assert _show_resources("tesla") == {}
        links = {l["href"] for l in SHOW_RESOURCES["offshore_north"]["links"]}
        assert {"offshore-north-dashboard.html", "offshore-north-glossary.html"} <= links
        assert "show_resources" in _read("templates/blog_post.html.j2")
        assert "Plain Sailing glossary" in _read("blog/offshore_north/ep005.html")


# ---------------------------------------------------------------------------
# Round 2 (same day): fleet guide, result-pending flag, cast, map, show strip
# ---------------------------------------------------------------------------

class TestRound2FleetAndRecord:
    def test_finished_race_without_a_result_is_flagged_not_licensed(self):
        """A countdown whose window has closed but whose results_key has no
        results entry must tell the writer the result is NOT on record."""
        import copy
        from engine.offshore_north_status import build_campaign_status

        d = copy.deepcopy(_curated())
        d["results"] = [r for r in d["results"] if r.get("key") != "defi_azimut_2026"]
        out = build_campaign_status(d, now=dt.datetime(2026, 9, 21, 13, tzinfo=dt.timezone.utc))
        assert "Défi Azimut-Lorient Agglomération (15 September 2026): FINISHED" in out
        assert "RESULT NOT YET ON RECORD" in out
        # with the result on record the flag is absent
        full = build_campaign_status(_curated(), now=dt.datetime(2026, 9, 21, 13, tzinfo=dt.timezone.utc))
        assert "RESULT NOT YET ON RECORD" not in full

    def test_record_links_countdowns_to_results_and_entries_to_the_register(self):
        d = _curated()
        keys = {r["key"] for r in d["results"]}
        assert "defi_azimut_2026" in keys and "ocean_race_atlantic_2026" in keys
        rdr = next(c for c in d["countdowns"] if c["id"] == "rdr_start")
        assert rdr["results_key"] == "route_du_rhum_2026" and "route_du_rhum_2026" not in keys
        entries = d["rdr_imoca_entries"]["entries"]
        slugs = [e.get("imoca_slug") for e in entries if e.get("imoca_slug")]
        assert len(slugs) >= 19 and len(slugs) == len(set(slugs))
        assert next(e for e in entries if e.get("canada"))["imoca_slug"] == "emira-iv"

    def test_map_markers_are_named_places_never_a_guessed_fix(self):
        d = _curated()
        for p in d["position_log"]:
            if "lat" in p:
                assert p.get("place") and "lon" in p, p["date"]
        # the 2 Sep "leaving Canada" post names no place -> no marker
        assert "lat" not in d["position_log"][-1]
        ports = {p["id"] for p in d["map"]["ports"]}
        for c in d["map"]["courses"]:
            assert c["from"] in ports and c["to"] in ports

    def test_cast_is_short_factual_and_sourced(self):
        cast = _curated()["cast"]
        assert 8 <= len(cast) <= 16
        for c in cast:
            assert c["name"] and c["flag"] and c["line"] and c["url"]
            assert len(c["line"]) < 320, c["name"]
        assert cast[0]["name"] == "Scott Shawyer"

    def test_imoca_boat_page_parser(self):
        sys.path.insert(0, str(_ROOT / "scripts"))
        import fetch_offshore_north_dashboard as f

        html = (
            '<h2 class="x">FRA 3</h2>'
            '<table><tr><th><span class="ProfileCard-label">Baptismal name</span></th><td>Charal</td></tr>'
            '<tr><th><span class="ProfileCard-label">Architect</span></th><td>Sam Manuard</td></tr>'
            '<tr><th><span class="ProfileCard-label">Construction</span></th><td>2022, CDK Technologies, Lorient</td></tr>'
            '<tr><th><span class="ProfileCard-label">Launch date</span></th><td>7/11/22</td></tr></table>'
            '<table><tr><th>Foils</th><td>Yes</td></tr><tr><th>Weight</th><td>8 tonnes</td></tr></table>'
            '<h2>Sailing Highlights</h2><div class="richtext"><strong>2026 : </strong> Défi Azimut - 3rd<br />'
            '<strong>2025 : </strong> Transat Café L\'OR - Winner<br /></div>'
        )
        out = f.parse_imoca_boat_page(html)
        assert out["architect"] == "Sam Manuard" and out["launch_date"] == "7/11/22"
        assert out["sail_number"] == "FRA 3" and out["foils"] == "Yes"
        assert out["highlights"] == ["2026: Défi Azimut - 3rd", "2025: Transat Café L'OR - Winner"]

    def test_fleet_keeps_previous_record_when_a_page_fails(self, monkeypatch):
        sys.path.insert(0, str(_ROOT / "scripts"))
        import fetch_offshore_north_dashboard as f

        monkeypatch.setattr(f, "_rdr_entries", lambda: [{"skipper": "A", "boat": "X", "imoca_slug": "x"}])

        class _Boom:
            def get(self, *a, **k):
                raise RuntimeError("down")

        monkeypatch.setitem(sys.modules, "requests", _Boom())
        prev = {"fleet": [{"slug": "x", "skipper": "A", "architect": "Y"}]}
        out = f.collect_fleet(prev)
        assert out[0]["architect"] == "Y" and out[0]["stale"] is True

    def test_show_page_carries_the_campaign_strip(self):
        import generate_html as gh

        strip = gh._offshore_north_campaign_strip()
        assert strip and strip["label"].startswith("Route du Rhum") and strip["fix_date"] == "2026-09-02"
        assert "campaign_strip" in _read("templates/show_page.html.j2")
        assert "onStripDays" in _read("offshore-north.html")

    def test_dashboard_template_round2_surfaces(self):
        tpl = _read("templates/offshore_north_dashboard.html.j2")
        for needle in ('id="onMap"', 'id="onFleet"', "on-cast", "result pending", "leaflet"):
            assert needle in tpl, needle
