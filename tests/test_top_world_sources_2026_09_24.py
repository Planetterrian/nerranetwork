"""Guards for the Top World Ep2 source repair (2026-09-24).

Omni View Top World News Ep2 shipped with NO Source line on any of its
eleven items — the grok-4.3 structural retry that replaced its grok-4.7
digest cited nothing — so the blog page's Sources list was empty and the
launch-cohort guard (every cohort show's latest digest carries >= 3 source
URLs) went red on main. The record is repaired FROM THE RECORD:
``scripts/backfill_sources_from_desks.py`` pairs each item with the same
story in the five desks' digests of that day or the show's own content
tracker (the URLs the run fetched), never from memory; and every Mira
cohort show now carries the ``items_without_source`` lint so the next
source-less digest rides the one-shot regeneration instead of shipping.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import scripts.backfill_sources_from_desks as bf

ROOT = Path(__file__).resolve().parent.parent
MIRA_COHORT = ["omni_view_europe", "omni_view_asia_pacific", "omni_view_africa_mideast",
               "omni_view_latam", "omni_view_north_america", "omni_view_world",
               "vancouver", "collingwood"]

DESK = (
    "# Omni View Europe\n> **hook**\n\n### Lead\n"
    "**Poland says fire at Starlink station is sabotage: BBC Europe**\n"
    "Body. Source: [bbc.com](https://www.bbc.com/news/articles/c1)\n\n"
    "### Across the Region\n"
    "**Russia Bombards Ukraine as 51 Nations Call for Ceasefire: UNITED24 Media**\n"
    "Body. Source: [united24media.com](https://united24media.com/war/51-nations)\n"
)
TOP = (
    "# Omni View Top World News\n> **hook**\n\n### The Ten\n"
    "**1. Russia Bombards Ukraine as 51 Nations Call for Ceasefire: UNITED24 Media**\n"
    "Ukraine faced a day-long barrage.\n\n"
    "**2. Ukrainians in UK fear cut to funds for Homes for Ukraine hosts: The Guardian World**\n"
    "The United Kingdom cut monthly payments to hosts.\n\n"
    "**3. A story nobody fetched: Some Outlet**\n"
    "Body without a match.\n\n"
    "**Both Sides: Should the White House restrict press access?**\n"
    "Arguments.\n"
)


def _tree(tmp_path: Path) -> Path:
    (tmp_path / "digests" / "omni_view_europe").mkdir(parents=True)
    (tmp_path / "digests" / "omni_view_europe" / "Omni_View_Europe_Ep002_20260924.md").write_text(DESK, encoding="utf-8")
    d = tmp_path / "digests" / "omni_view_world"
    d.mkdir(parents=True)
    (d / "Omni_View_World_Ep002_20260924.md").write_text(TOP, encoding="utf-8")
    (d / "omni_view_world_content_tracker.json").write_text(json.dumps({
        "episodes": [{"date": "2026-09-24", "headlines": ["unrelated digest headline"],
                      "urls": ["https://www.theguardian.com/world/2026/sep/24/uk-homes-for-ukraine-funding-cut-homeless",
                               "https://www.nytimes.com/live/2026/09/24/world/un-general-assembly-news"]}]}), encoding="utf-8")
    (d / "summaries_omni_view_world.json").write_text(json.dumps({"summaries": [
        {"episode_num": 2, "content": TOP}]}), encoding="utf-8")
    return tmp_path


class TestMatcher:
    def test_slug_titles_and_outlet_fit(self):
        assert bf.slug_title("https://www.theguardian.com/world/2026/sep/24/uk-homes-for-ukraine-funding-cut-homeless") \
            == "uk homes for ukraine funding cut homeless"
        assert bf.slug_title("https://www.bbc.co.uk/news/articles/cqevwm09w4xmo?x=1") == ""
        assert bf.outlet_fits_host("BBC World", "bbc.co.uk")
        assert bf.outlet_fits_host("Bloomberg Government News", "news.bgov.com")
        assert bf.outlet_fits_host("Yonhap", "en.yna.co.kr")
        assert not bf.outlet_fits_host("BBC World", "theguardian.com")
        assert bf.outlet_fits_host("", "anything.com")

    def test_an_item_naming_an_outlet_is_never_sourced_elsewhere(self):
        cands = [{"title": "white house press access judge order", "outlet": "", "host": "theguardian.com",
                  "url": "https://www.theguardian.com/x/white-house-press-access-judge-order", "desk": "t"}]
        assert bf.best_match("White House violated court order on press access", "BBC World", cands) is None
        assert bf.best_match("White House violated court order on press access", "", cands) is not None

    def test_a_tie_is_no_match(self):
        cands = [{"title": "senate iran war vote", "outlet": "", "host": "a.com", "url": "https://a.com/senate-iran-war-vote", "desk": "t"},
                 {"title": "senate iran war vote", "outlet": "", "host": "b.com", "url": "https://b.com/senate-iran-war-vote", "desk": "t"}]
        assert bf.best_match("Senate plans Iran war vote today", "", cands) is None

    def test_backfill_from_desks_and_tracker_leaves_the_unmatched_alone(self, tmp_path):
        root = _tree(tmp_path)
        rows = bf.process("omni_view_world", 2, apply=False, root=root)
        assert [bool(r["url"]) for r in rows] == [True, True, False]
        # dry run wrote nothing
        assert "Source:" not in (root / "digests/omni_view_world/Omni_View_World_Ep002_20260924.md").read_text()
        rows = bf.process("omni_view_world", 2, apply=True, root=root)
        text = (root / "digests/omni_view_world/Omni_View_World_Ep002_20260924.md").read_text(encoding="utf-8")
        assert "Source: [united24media.com](https://united24media.com/war/51-nations)" in text
        assert "Source: [theguardian.com](https://www.theguardian.com/world/2026/sep/24/uk-homes-for-ukraine-funding-cut-homeless)" in text
        assert text.count("Source:") == 2  # the unmatched item and Both Sides stay as they were
        summ = json.loads((root / "digests/omni_view_world/summaries_omni_view_world.json").read_text())
        assert summ["summaries"][0]["content"].count("Source:") == 2
        from engine.blog import _extract_source_urls
        assert len(_extract_source_urls(text)) == 2


class TestTheRecord:
    def test_top_world_ep2_carries_its_sources(self):
        from engine.blog import _extract_source_urls
        p = ROOT / "digests/omni_view_world/Omni_View_World_Ep002_20260924.md"
        if not p.exists():
            pytest.skip("committed digest not present")
        text = p.read_text(encoding="utf-8")
        urls = _extract_source_urls(text)
        assert len(urls) >= 9, urls
        # every Source is a publisher the run fetched or a desk cited — never x.com
        assert "x.com" not in " ".join(urls)
        summ = json.loads((ROOT / "digests/omni_view_world/summaries_omni_view_world.json").read_text(encoding="utf-8"))
        entry = next(e for e in summ["summaries"] if int(e.get("episode_num") or 0) == 2)
        assert entry["content"].count("Source:") == text.count("Source:")

    @pytest.mark.parametrize("slug", MIRA_COHORT)
    def test_every_mira_cohort_show_lints_source_less_items(self, slug):
        raw = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
        assert "items_without_source" in raw["digest_lints"], slug

    def test_the_lint_would_have_caught_the_source_less_digest(self):
        from engine.digest_lint import lint_items_without_source
        assert lint_items_without_source(TOP).note  # three items, none sourced
