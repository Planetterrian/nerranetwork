"""Launch-cohort PR C (2026-09-23): the nine hand-launched shows go on the
clock, all 13 join the cross-promo rotation, and /mira.html says Mira reads
the news. Pins the plan §6 slots across every place a cadence lives and the
additive surfaces, so a partial revert fails CI.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
TS = (ROOT / "workers" / "scheduler" / "src" / "index.ts").read_text(encoding="utf-8")
AUDIT = (ROOT / ".github" / "workflows" / "daily-audit.yml").read_text(encoding="utf-8")

#: Plan §6 slots (UTC hour, minute, day filter) for the nine.
SLOTS = {
    "omni_view_asia_pacific": (6, 16, None),
    "omni_view_africa_mideast": (6, 31, None),
    "omni_view_europe": (6, 46, None),
    "collingwood": (10, 7, "friday"),
    "omni_view_north_america": (10, 16, None),
    "omni_view_latam": (10, 31, None),
    "prediction_markets": (11, 16, None),
    "omni_view_world": (11, 31, None),
    "vancouver": (12, 16, None),
}
COHORT = tuple(SLOTS) + ("ai_chips", "mag7", "peptides", "longevity")


def _cron_map():
    out = {}
    for m in re.finditer(r'"(\d+) (\d+) \* \* ([*\d])":\s*\("(\w+)",\s*(?:"(\w+)"|None)\)', WF):
        minute, hour, _dow, show, flt = m.groups()
        out[show] = (int(hour), int(minute), flt)
    return out


class TestTheNineAreScheduled:
    def test_cron_map_carries_the_plan_slots(self):
        cron_map = _cron_map()
        for show, slot in SLOTS.items():
            assert cron_map.get(show) == slot, (show, cron_map.get(show))

    def test_each_slot_has_a_github_cron_line(self):
        for show, (h, m, flt) in SLOTS.items():
            dow = {"friday": "5"}.get(flt, "*")
            assert f"- cron: '{m} {h} * * {dow}'" in WF, show

    def test_worker_slots_mirror_the_gate(self):
        for show, (h, m, flt) in SLOTS.items():
            flt_ts = f'"{flt}"' if flt else "null"
            assert re.search(rf'\[{h}, {m},\s*"{show}",\s*{flt_ts}\]', TS), show

    def test_collingwood_first_run_agrees_everywhere(self):
        assert '"collingwood": "2026-10-02"' in WF
        assert 'collingwood: "2026-10-02"' in TS
        import review_episodes as re_mod
        assert re_mod.SHOW_REGISTRY["collingwood"]["first_run"] == "2026-10-02"
        # The Friday before that date is a known no-op — Ep1 was hand-made on
        # Wednesday the 23rd from a 192-hour window.
        assert not re_mod._scheduled_on(re_mod.SHOW_REGISTRY["collingwood"], _dt.date(2026, 9, 25))
        assert re_mod._scheduled_on(re_mod.SHOW_REGISTRY["collingwood"], _dt.date(2026, 10, 2))

    def test_top_world_runs_after_every_desk(self):
        cron_map = _cron_map()
        world = cron_map["omni_view_world"][:2]
        for desk in ("omni_view_europe", "omni_view_asia_pacific", "omni_view_africa_mideast",
                     "omni_view_latam", "omni_view_north_america"):
            assert cron_map[desk][:2] < world, desk

    def test_dispatch_all_names_every_cohort_show(self):
        m = re.search(r'if dispatch_show == "all":\s*shows = \[([^\]]+)\]', WF)
        assert m
        listed = set(re.findall(r'"(\w+)"', m.group(1)))
        assert set(COHORT) <= listed

    def test_prelaunch_set_is_empty_and_registry_has_them(self):
        import review_episodes as re_mod
        assert re_mod.PRELAUNCH_SLUGS == frozenset()
        for show, (_h, _m, flt) in SLOTS.items():
            info = re_mod.SHOW_REGISTRY[show]
            assert info["schedule"] == (flt or "daily"), show
            assert (ROOT / info["output_dir"]).is_dir(), show
        assert re_mod.CATCH_UP_MAX_PER_RUN >= 16

    def test_audit_feeds_carry_the_nine(self):
        for show, (_h, _m, flt) in SLOTS.items():
            m = re.search(rf'"{show}_podcast\.rss": \("[^"]+", (\d+)\)', AUDIT)
            assert m, show
            limit = int(m.group(1))
            assert limit >= 192 if flt else limit <= 120, (show, limit)

    def test_directory_submission_lists_the_nine(self):
        src = (ROOT / "scripts" / "submit_to_directories.py").read_text(encoding="utf-8")
        for show in SLOTS:
            assert f'("{show}", ' in src, show


class TestCrossPromoAndMiraPage:
    def test_all_thirteen_are_appended_to_the_pool(self):
        from engine.network_promo import ENGLISH_ORDER, ENGLISH_SHOWS
        assert ENGLISH_ORDER.index("offshore_north") < ENGLISH_ORDER.index("ai_chips")
        for slug in COHORT:
            assert slug in ENGLISH_SHOWS, slug
            assert "&" not in ENGLISH_SHOWS[slug]["spoken_name"]
            assert (ROOT / "shows" / f"{slug}.yaml").exists()

    def test_an_established_show_can_plug_a_new_one(self):
        from engine.network_promo import build_network_promo
        seen = set()
        for offset in range(30):
            promo = build_network_promo("tesla", _dt.date(2026, 9, 24) + _dt.timedelta(days=offset), 600)
            for slug in COHORT:
                from engine.network_promo import ENGLISH_SHOWS
                if ENGLISH_SHOWS[slug]["spoken_name"] in promo:
                    seen.add(slug)
        assert len(seen) >= 6, seen

    def test_brand_lists_the_news_shows_apart_from_the_claim_trio(self):
        from engine.brand import MIRA_NEWS_SHOW_SLUGS, MIRA_SHOW_SLUGS
        assert MIRA_SHOW_SLUGS == ("nerra_daily", "age_of_ai", "nerra_voices")
        assert set(MIRA_NEWS_SHOW_SLUGS) == {
            "omni_view_world", "omni_view_north_america", "omni_view_europe",
            "omni_view_asia_pacific", "omni_view_africa_mideast", "omni_view_latam",
            "vancouver", "collingwood",
        }
        assert not set(MIRA_NEWS_SHOW_SLUGS) & set(MIRA_SHOW_SLUGS)

    def test_mira_page_renders_the_news_section(self, tmp_path):
        import generate_html as gh
        gh.generate_mira_page(output_dir=tmp_path)
        html = (tmp_path / "mira.html").read_text(encoding="utf-8")
        assert 'id="mira-reads-the-news"' in html
        assert "Omni View Top World News" in html and "Vancouver Daily News" in html
        # The claim section is untouched: still three claim paragraphs' worth
        # of trio cards above the news section.
        assert html.index("Three jobs, one host") < html.index("Mira also reads the news")


class TestFirstRunNoteOnTheShowPage:
    def test_note_only_while_the_date_is_ahead(self):
        import generate_html as gh
        cfg = {"first_run": "2026-10-02"}
        assert gh._first_run_note(cfg, today=_dt.date(2026, 9, 24)) == \
            "First scheduled episode: Friday, October 2, 2026"
        assert gh._first_run_note(cfg, today=_dt.date(2026, 10, 2)) == ""
        assert gh._first_run_note({}, today=_dt.date(2026, 9, 24)) == ""

    def test_collingwood_registry_carries_the_date(self):
        import generate_html as gh
        assert gh.NETWORK_SHOWS["collingwood"].get("first_run") == "2026-10-02"

    def test_template_renders_it(self):
        tpl = (ROOT / "templates" / "show_page.html.j2").read_text(encoding="utf-8")
        assert "{% if first_run_note %}" in tpl


class TestNoSurfaceStillSaysPreLaunch:
    def test_claude_md_table_has_no_prelaunch_row(self):
        md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        for line in md.splitlines():
            if line.startswith("|") and "pre-launch" in line:
                raise AssertionError(line)

    def test_registry_schedule_strings_match_the_slots(self):
        meta = yaml.safe_load((ROOT / "shows" / "network_meta.yaml").read_text(encoding="utf-8"))
        shows = meta.get("shows", meta)
        for show, (_h, _m, flt) in SLOTS.items():
            sched = str(shows[show].get("schedule", ""))
            if flt:
                assert "Friday" in sched, (show, sched)
            else:
                assert sched.startswith("Daily"), (show, sched)
