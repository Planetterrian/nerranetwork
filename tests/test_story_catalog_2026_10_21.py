"""Guards for the Oct 21 2026 story-catalog pass.

Review: docs/reviews/content_lake_and_story_catalog_2026_10_21.md;
docs: docs/story_catalog.md. The tracker records what AIRED; the content lake
stores aired items with story ids; the cross-show block names today's articles
a sibling show already told; the catalog (Supabase) copies the lake and keeps
the articles a run fetched; books refuse a chapter that still carries a
corrected error.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pytest

from engine import content_lake
from engine.aired_items import extract_aired_items, item_title, is_field_label
from engine.content_tracker import AIRED_SCHEMA, LISTED_URL_BLOCK_DAYS, ContentTracker
from engine.story_catalog import StoryAssigner, item_tokens, story_id_for

ROOT = Path(__file__).resolve().parent.parent

DIGEST = """# Test Show

> **SpaceX and Tesla boards study a merger of the two companies**

### Top News

1. **SpaceX and Tesla boards study a merger of the two companies: Reuters**
Both boards formed committees on Tuesday. Source: [reuters.com](https://www.reuters.com/a/merger)

2. **Starship Flight 15 targets a November catch attempt**
The tower will try to catch the ship. Source: https://www.nasaspaceflight.com/f15

**Why This Teaches:** A field label, not a story. Source: https://example.com/label

### Also Today

**Kenya confirms a second Ebola case: BBC** One sentence. Source: https://bbc.co.uk/ebola

### Sources

- [reuters.com](https://www.reuters.com/a/merger)
"""

OMNI = """# Omni View

### 1) Kenya confirms a second Ebola case inside quarantine

Health officials said Tuesday. Source: https://example.org/kenya
"""

ESSAY = """> **Wolves entering 29 Wisconsin counties cut deer-vehicle collisions by about 24 percent.**

## Segment 1 — The Setup

Wolves came back. See https://pnas.org/wolves
"""


def _days_ago(n: int) -> str:
    return (dt.date.today() - dt.timedelta(days=n)).isoformat()


# ----------------------------------------------------------- aired items --
class TestAiredItems:
    def test_numbered_bold_and_also_today_items_are_read(self):
        items = extract_aired_items(DIGEST)
        titles = [i.title for i in items]
        assert titles == [
            "SpaceX and Tesla boards study a merger of the two companies",
            "Starship Flight 15 targets a November catch attempt",
            "Kenya confirms a second Ebola case",
        ]
        assert [i.kind for i in items] == ["item", "item", "also_today"]
        assert items[0].urls == ["https://www.reuters.com/a/merger"]

    def test_a_field_label_is_not_a_story(self):
        assert is_field_label("**Why This Teaches:** The pick isolates a catalyst")
        assert not is_field_label("**Tesla wins a ruling in the Quebec fire case — Reuters:** text")

    def test_outlet_tail_is_stripped_from_titles(self):
        assert item_title("1. **Tesla wins a ruling in Quebec: Reuters**") == "Tesla wins a ruling in Quebec"

    def test_omni_view_heading_items(self):
        items = extract_aired_items(OMNI)
        assert len(items) == 1 and items[0].kind == "heading"
        assert items[0].title == "Kenya confirms a second Ebola case inside quarantine"

    def test_a_narrative_episode_is_one_essay(self):
        items = extract_aired_items(ESSAY)
        assert len(items) == 1 and items[0].kind == "essay"
        assert items[0].title.startswith("Wolves entering")

    def test_matches_story_item_count_on_committed_digests(self):
        from engine.digest_lint import story_item_count
        checked = 0
        for p in sorted(ROOT.glob("digests/*/*_Ep*_202610*.md"))[-80:]:
            if not re.search(r"_Ep\d+_\d{8}\.md$", p.name):
                continue
            text = p.read_text(encoding="utf-8")
            n = story_item_count(text)
            got = [i for i in extract_aired_items(text) if i.kind not in ("essay", "section")]
            # Field labels are the only items the count reads and we skip;
            # a one-story ``section`` (Oct 22) is outside what the count reads.
            assert len(got) <= n
            checked += 1
        assert checked >= 20


class TestOneStorySections:
    """Oct 22 2026: the lead "Top Story" and every deep dive were missing
    from the aired record, and a ``### 7) Country: headline`` heading was
    recorded as the country alone."""

    LEAD = """# Show
> **Frozen encoders match commercial Arabic speech recognition**
Intro paragraph that sets up the day.
---
### Top Story
Researchers tested a frozen audio encoder on Gulf Arabic speech and matched
commercial systems on character error rate across three public benchmarks,
using a reader of 22.6M parameters and no change to the encoder weights at all.
Source: [arxiv.org](https://arxiv.org/abs/1)
---
### Headlines
1. **Second story about chips: Reuters** - body text. Source: https://r.example/2
---
### The Teardown: When the Panel Gives the Count Back
A long explainer on substrate panels and the yield arithmetic behind them, told
as one story across several sentences so a listener hears the mechanism, the
numbers and why the supply chain cares about the count coming back to them.
---
### On the Calendar
October 30: an earnings call that matters, with more words to pass the floor of
forty words easily because a calendar is never a story of its own in this file.
---
### Things to Try This
- Try the released code on your own data and compare the error rates you see.
- Read the paper's appendix for the benchmark setup and the decoding details.
- Compare against a commercial service on the same clips, then share results.
"""

    def test_the_lead_section_is_recorded_under_the_hook(self):
        got = extract_aired_items(self.LEAD)
        lead = [i for i in got if i.section == "Top Story"]
        assert len(lead) == 1 and lead[0].kind == "section"
        assert lead[0].title.startswith("Frozen encoders match")
        assert lead[0].urls == ["https://arxiv.org/abs/1"]

    def test_a_deep_dive_takes_its_subtitle(self):
        got = {i.section: i for i in extract_aired_items(self.LEAD)}
        assert got["The Teardown"].title == "When the Panel Gives the Count Back"

    def test_structural_and_list_sections_are_not_stories(self):
        secs = {i.section for i in extract_aired_items(self.LEAD)}
        assert "On the Calendar" not in secs and "Things to Try This" not in secs

    def test_a_heading_item_keeps_its_whole_title(self):
        d = "# S\n> **Hook line here**\n### 7) Tanzania: Dodoma Extends Health Coverage to 111,515 Residents\nBody. Source: https://x.example/t\n"
        (item,) = extract_aired_items(d)
        assert item.kind == "heading"
        assert item.title.startswith("Tanzania: Dodoma Extends")

    def test_a_narrative_episode_is_still_one_essay(self):
        d = ("# UC\n> **India issued eighty million free gas connections**\n### Cold Open\n"
             + "Words " * 60 + "\n### The Case\n" + "More words " * 60 + "\n")
        got = extract_aired_items(d)
        assert [i.kind for i in got] == ["essay"]

    def test_the_lead_airs_in_todays_slate(self):
        p = ROOT / "digests/models_agents/Models_Agents_Ep211_20261022.md"
        if not p.exists():
            pytest.skip("slate file not in this checkout")
        assert any(i.section == "Top Story" for i in extract_aired_items(p.read_text(encoding="utf-8")))


# ------------------------------------------------------- content tracker --
class TestTrackerRecordsWhatAired:
    def test_a_draft_records_only_what_was_listed(self, tmp_path):
        t = ContentTracker("demo", tmp_path)
        t.record_episode(DIGEST, {}, record_aired=False,
                         source_articles=[{"url": "https://unused.example/a", "title": "Unused story"}])
        ep = t.data["episodes"][0]
        assert ep["headlines"] == [] and ep["urls"] == []
        assert ep["listed_urls"] == ["https://unused.example/a"]

    def test_the_final_digest_records_aired_stories_only(self, tmp_path):
        t = ContentTracker("demo", tmp_path)
        t.record_episode(DIGEST, {}, record_aired=True, source_articles=[
            {"url": "https://www.reuters.com/a/merger", "title": "Tesla, SpaceX form merger committees"},
            {"url": "https://unused.example/a", "title": "A story the episode never told"}])
        ep = t.data["episodes"][0]
        assert "https://www.reuters.com/a/merger" in ep["urls"]
        assert "https://unused.example/a" not in ep["urls"]
        assert ep["listed_urls"] == ["https://unused.example/a"]
        assert "Tesla, SpaceX form merger committees" in ep["headlines"]
        assert not any("never told" in h for h in ep["headlines"])

    def test_listed_urls_are_blocked_briefly_aired_urls_long(self, tmp_path):
        t = ContentTracker("demo", tmp_path, max_days=45)
        t.data["episodes"] = [
            {"date": _days_ago(1), "headlines": [], "urls": [], "listed_urls": ["https://x.example/recent"]},
            {"date": _days_ago(LISTED_URL_BLOCK_DAYS + 3), "headlines": [], "urls": [],
             "listed_urls": ["https://x.example/old"]},
            {"date": _days_ago(30), "headlines": [], "urls": ["https://x.example/aired"], "listed_urls": []},
        ]
        arts = [{"url": u, "title": f"Distinct title number {i} about something"}
                for i, u in enumerate(["https://x.example/recent", "https://x.example/old",
                                       "https://x.example/aired"])]
        kept = [a["url"] for a in t.filter_recent_articles(arts)]
        assert kept == ["https://x.example/old"]

    def test_a_pre_oct_21_tracker_migrates_once_from_the_digests(self, tmp_path):
        day = _days_ago(2)
        (tmp_path / f"Demo_Ep010_{day.replace('-', '')}.md").write_text(DIGEST, encoding="utf-8")
        legacy = {"show": "demo", "episodes": [
            {"date": day, "headlines": ["Listed headline that never aired at all"],
             "urls": ["https://www.reuters.com/a/merger", "https://unused.example/z"], "sections": {"x": "y"}},
            {"date": _days_ago(1), "headlines": ["Another listed one"], "urls": ["https://unused.example/q"]},
        ]}
        (tmp_path / "demo_content_tracker.json").write_text(json.dumps(legacy), encoding="utf-8")
        t = ContentTracker("demo", tmp_path, max_days=45)
        t.load()
        assert t.migrate_to_aired({}) is True
        first, second = t.data["episodes"]
        assert "https://www.reuters.com/a/merger" in first["urls"]
        assert first["listed_urls"] == ["https://unused.example/z"]
        assert first["sections"] == {"x": "y"}
        assert "Listed headline that never aired at all" not in first["headlines"]
        assert second["urls"] == [] and second["listed_urls"] == ["https://unused.example/q"]
        assert t.data["aired_schema"] == AIRED_SCHEMA
        assert t.migrate_to_aired({}) is False

    def test_a_new_tracker_starts_migrated(self, tmp_path):
        assert ContentTracker("demo", tmp_path).data["aired_schema"] == AIRED_SCHEMA


# ----------------------------------------------------------- story ids --
class TestStoryIds:
    def _assign(self, rows_by_date):
        a = StoryAssigner()
        out = {}
        for date in sorted(rows_by_date):
            rows = rows_by_date[date]
            for (key, *_), sid in zip(rows, a.assign(date, rows)):
                out[key] = sid
        return out

    def test_one_story_across_two_shows_and_two_days(self):
        t1 = item_tokens("SpaceX and Tesla committees study a merger of the companies")
        t2 = item_tokens("Tesla and SpaceX director committees study merger proposal")
        ids = self._assign({"2026-10-20": [("spacex:1:0", t1, "spacex")],
                            "2026-10-21": [("tesla:9:0", t2, "tesla")]})
        assert ids["spacex:1:0"] == ids["tesla:9:0"] == story_id_for("spacex:1:0")

    def test_unrelated_stories_stay_apart(self):
        ids = self._assign({"2026-10-21": [
            ("a:1:0", item_tokens("Kenya confirms a second Ebola case in quarantine"), "a"),
            ("b:1:0", item_tokens("Starship Flight 15 targets a November catch"), "b")]})
        assert ids["a:1:0"] != ids["b:1:0"]

    def test_spelled_numbers_never_make_a_story(self):
        assert item_tokens("Mortgage rate at seven point four five percent") & {"seven", "point", "percent"} == set()

    def test_an_essay_is_always_its_own_story(self):
        tok = item_tokens("Wolves cut deer collisions in Wisconsin counties")
        ids = self._assign({"2026-10-20": [("x:1:0", tok, "x", "item")],
                            "2026-10-21": [("uc:1:0", tok, "uc", "essay")]})
        assert ids["uc:1:0"] == story_id_for("uc:1:0")

    def test_observe_then_match_reuses_stored_ids(self):
        a = StoryAssigner()
        a.observe("2026-10-20", [("st_known", item_tokens("Starship Flight 15 targets a November catch"), "spacex")])
        assert a.match_story(item_tokens("SpaceX Starship Flight 15 catch slips to November"), "ff") == "st_known"


# ------------------------------------------------------------ the lake --
def _record(slug, ep, date, digest):
    return content_lake.EpisodeRecord(
        show_slug=slug, episode_num=ep, date=date, title="t", hook="h", digest_md=digest,
        podcast_script="", summary="", headlines=[], source_urls=[], entities=[], topics=[],
        word_count=1, show_name=slug.title(), language="en")


class TestLakeItems:
    def test_store_episode_fills_headlines_items_and_story_ids(self, tmp_path):
        db = tmp_path / "lake.db"
        content_lake.store_episode(_record("spacex", 1, "2026-10-20", DIGEST), db_path=db)
        content_lake.store_episode(_record("ff", 7, "2026-10-21", OMNI), db_path=db)
        assert content_lake.rebuild_story_ids(db_path=db) == 4
        eps = content_lake.query_all_shows_range("2026-10-01", "2026-10-31", db_path=db)
        assert any(e["headlines"] for e in eps)
        items = content_lake.query_items("2026-10-01", "2026-10-31", db_path=db)
        assert len(items) == 4 and all(i["story_id"] for i in items)
        assert content_lake.search_items('"Ebola"', db_path=db)
        sid = items[0]["story_id"]
        assert content_lake.story_timeline(sid, db_path=db)[0]["show_slug"] == "spacex"

    def test_incremental_assignment_matches_a_full_rebuild(self, tmp_path):
        db = tmp_path / "lake.db"
        content_lake.store_episode(_record("spacex", 1, "2026-10-20", DIGEST), db_path=db)
        content_lake.store_episode(_record("tesla", 2, "2026-10-21", DIGEST.replace("Reuters", "CNBC")), db_path=db)
        content_lake.rebuild_story_ids(db_path=db)
        full = {i["item_key"]: i["story_id"] for i in content_lake.query_items("2026-10-01", "2026-10-31", db_path=db)}
        content_lake.rebuild_story_ids(db_path=db, since="2026-10-21")
        inc = {i["item_key"]: i["story_id"] for i in content_lake.query_items("2026-10-01", "2026-10-31", db_path=db)}
        assert full == inc
        assert inc["tesla:2:0"] == inc["spacex:1:0"]


# ------------------------------------------------------ cross-show block --
class TestCrossShowBlock:
    def test_names_todays_articles_a_sibling_told_never_its_own(self, tmp_path):
        from engine.cross_show import NONE_TEXT, render_block, sibling_matches
        db = tmp_path / "lake.db"
        content_lake.store_episode(_record("spacex", 1, "2026-10-21", DIGEST), db_path=db)
        content_lake.rebuild_story_ids(db_path=db)
        arts = [{"title": "Unrelated: a new bakery opens downtown"},
                {"title": "Tesla and SpaceX boards study merger of the two companies"}]
        m = sibling_matches(arts, "tesla", dt.date(2026, 10, 21), db_path=db)
        assert [x["index"] for x in m] == [2] and m[0]["show_name"] == "Spacex"
        assert "this show's angle" in render_block(m)
        assert sibling_matches(arts, "spacex", dt.date(2026, 10, 21), db_path=db) == []
        assert render_block([]) == NONE_TEXT

    def test_the_block_never_asks_for_silence(self):
        from engine import cross_show
        src = Path(cross_show.__file__).read_text(encoding="utf-8")
        assert "avoid redundancy" not in cross_show.render_block([{"index": 1, "title": "t", "show_name": "S",
                                                                   "date": "2026-10-21", "told_as": "u"}])
        assert "never assume the listener heard" in src


# ------------------------------------------------------------- catalog --
class TestCatalog:
    def test_unconfigured_is_a_clean_no_op(self, monkeypatch):
        from engine import catalog
        for a, b in catalog._ENV_PAIRS:
            monkeypatch.delenv(a, raising=False)
            monkeypatch.delenv(b, raising=False)
        assert not catalog.configured()
        assert catalog.record_run(show_slug="x", episode_num=1, date="2026-10-21",
                                  fetched=[], listed=[]) == {"status": "unconfigured"}
        assert catalog.missed_stories(dt.date(2026, 10, 21)) == []

    def test_falls_back_to_the_names_the_workflows_already_pass(self, monkeypatch):
        from engine import catalog
        for a, b in catalog._ENV_PAIRS:
            monkeypatch.delenv(a, raising=False)
            monkeypatch.delenv(b, raising=False)
        monkeypatch.setenv("X_QUEUE_SUPABASE_URL", "https://p.supabase.co/")
        monkeypatch.setenv("X_QUEUE_SUPABASE_KEY", "k")
        assert catalog._db() == ("https://p.supabase.co", "k")

    def test_sync_upserts_with_merge_and_prunes_shrunk_episodes(self, tmp_path, monkeypatch):
        from engine import catalog
        db = tmp_path / "lake.db"
        content_lake.store_episode(_record("spacex", 1, "2026-10-21", DIGEST), db_path=db)
        content_lake.rebuild_story_ids(db_path=db)
        calls = []
        monkeypatch.setattr(catalog, "configured", lambda: True)
        monkeypatch.setattr(catalog, "_rest", lambda m, t, **k: calls.append((m, t, k)) or [])
        monkeypatch.setattr(catalog, "_show_dirs", lambda: {})
        counts = catalog.sync_from_lake(show="spacex", episode=1, db_path=db)
        assert counts["items"] == 3 and counts["episodes"] == 1
        posts = [(t, k["prefer"]) for m, t, k in calls if m == "POST"]
        assert ("catalog_items", "resolution=merge-duplicates,return=minimal") in posts
        deletes = [k["params"] for m, t, k in calls if m == "DELETE" and t == "catalog_items"]
        assert deletes == [{"episode_key": "eq.spacex:1", "position": "gte.3"}]

    def test_a_run_writes_its_links_by_patch_and_its_articles_after(self, tmp_path, monkeypatch):
        # Oct 22 2026: every run of the first slate failed here. An upsert is
        # an INSERT first, so a catalog_episodes row carrying only the page
        # and audio links broke NOT NULL (23502) and no article was written.
        from engine import catalog
        db = tmp_path / "lake.db"
        content_lake.store_episode(_record("spacex", 1, "2026-10-21", DIGEST), db_path=db)
        content_lake.rebuild_story_ids(db_path=db)
        calls = []

        def fake_rest(method, table, **k):
            calls.append((method, table, k))
            if method == "POST" and table == "catalog_episodes":
                for row in k["body"]:
                    if row.get("show_slug") is None or row.get("date") is None:
                        raise RuntimeError("POST catalog_episodes: HTTP 400 23502")
            return []

        monkeypatch.setattr(catalog, "configured", lambda: True)
        monkeypatch.setattr(catalog, "_rest", fake_rest)
        monkeypatch.setattr(catalog, "_show_dirs", lambda: {})
        out = catalog.record_run(
            show_slug="spacex", episode_num=1, date="2026-10-21", db_path=db,
            fetched=[{"url": "https://other.example/s", "title": "Starship Flight 15 aims for a tower catch",
                      "source_name": "Other"}],
            listed=[], page_url="https://nerranetwork.com/blog/spacex/ep001.html",
            audio_url="https://audio.nerranetwork.com/spacex/x.mp3")
        assert out["status"] == "ok", out
        patches = [k for m, t, k in calls if m == "PATCH" and t == "catalog_episodes"]
        assert patches and patches[0]["params"] == {"episode_key": "eq.spacex:1"}
        assert any(m == "POST" and t == "catalog_articles" for m, t, _ in calls)

    def test_one_failed_write_never_drops_the_articles(self, tmp_path, monkeypatch):
        from engine import catalog
        db = tmp_path / "lake.db"
        content_lake.store_episode(_record("spacex", 1, "2026-10-21", DIGEST), db_path=db)
        content_lake.rebuild_story_ids(db_path=db)
        posted = []

        def fake_rest(method, table, **k):
            if method == "PATCH":
                raise RuntimeError("PATCH catalog_episodes: HTTP 500")
            posted.append(table)
            return []

        monkeypatch.setattr(catalog, "configured", lambda: True)
        monkeypatch.setattr(catalog, "_rest", fake_rest)
        monkeypatch.setattr(catalog, "_show_dirs", lambda: {})
        out = catalog.record_run(
            show_slug="spacex", episode_num=1, date="2026-10-21", db_path=db,
            fetched=[{"url": "https://other.example/n", "title": "A bakery opens", "source_name": "L"}],
            listed=[], page_url="https://x/ep001.html")
        assert out["status"] == "partial" and out["errors"]
        assert "catalog_articles" in posted

    def test_upsert_never_sends_one_key_twice_in_a_statement(self, monkeypatch):
        # Oct 21 2026 first fill: Postgres refused a claims batch carrying one
        # key twice (21000) and every correction after it was never copied.
        from engine import catalog
        sent = []
        monkeypatch.setattr(catalog, "_rest", lambda m, t, **k: sent.append(k["body"]))
        rows = [{"claim_key": "a", "v": 1}, {"claim_key": "b", "v": 1}, {"claim_key": "a", "v": 2}]
        assert catalog.upsert("catalog_claims", rows, "claim_key") == 2
        body = [r for chunk in sent for r in chunk]
        assert sorted(r["claim_key"] for r in body) == ["a", "b"]
        assert {r["claim_key"]: r["v"] for r in body}["a"] == 2

    def test_a_ledger_repeating_an_id_keeps_both_claims(self, tmp_path):
        from engine import catalog
        d = tmp_path / "spacex"
        d.mkdir()
        (d / "SpaceX_Ep001_20261021_claims.json").write_text(json.dumps({"claims": [
            {"id": "c1", "claim": "one"}, {"id": "c1", "claim": "two"}]}), encoding="utf-8")
        ep = {"episode_key": "spacex:1", "show_slug": "spacex", "episode_num": 1, "date": "2026-10-21"}
        rows = catalog.claim_rows([ep], {"spacex": d})
        assert len(rows) == 2 and len({r["claim_key"] for r in rows}) == 2

    def test_article_rows_mark_aired_and_match_stories(self, tmp_path):
        from engine import catalog
        db = tmp_path / "lake.db"
        content_lake.store_episode(_record("spacex", 1, "2026-10-21", DIGEST), db_path=db)
        content_lake.rebuild_story_ids(db_path=db)
        rows = catalog.article_rows(show_slug="spacex", date="2026-10-21", db_path=db, fetched=[
            {"url": "https://www.reuters.com/a/merger?x=1", "title": "Merger", "source_name": "Reuters"},
            {"url": "https://other.example/s", "title": "Starship Flight 15 aims for a November tower catch",
             "source_name": "Other"},
            {"url": "https://other.example/n", "title": "A bakery opens downtown", "source_name": "Local"}],
            listed=[{"url": "https://other.example/s"}])
        by = {r["url"]: r for r in rows}
        assert by["https://www.reuters.com/a/merger?x=1"]["aired"] is True
        assert by["https://other.example/s"]["aired"] is False and by["https://other.example/s"]["story_id"]
        assert by["https://other.example/s"]["listed_shows"] == ["spacex"]
        assert by["https://other.example/n"]["story_id"] is None

    def test_missed_stories_need_three_outlets_and_no_aired_story(self):
        from engine import catalog
        t = sorted(item_tokens("Volcano erupts in Iceland forcing evacuation of town"))
        rows = [{"url": f"https://o{i}.example/v", "title": "Volcano erupts in Iceland", "outlet": f"Outlet {i}",
                 "aired": False, "story_id": None, "tokens": t, "shows": ["omni_view"], "listed_shows": [],
                 "last_seen": "2026-10-21"} for i in range(3)]
        rows.append({"url": "https://p.example/a", "title": "Covered", "outlet": "P", "aired": False,
                     "story_id": "st_x", "tokens": t, "shows": [], "listed_shows": [], "last_seen": "2026-10-21"})
        missed = catalog.missed_stories(dt.date(2026, 10, 21), rows=rows)
        assert len(missed) == 1 and len(missed[0]["outlets"]) == 3
        assert catalog.missed_stories(dt.date(2026, 10, 21), rows=rows[:2]) == []

    def test_a_correction_is_about_the_items_that_hold_its_text(self):
        from engine.catalog import correction_items
        items = [{"title": "A", "body": "the ship uses body flaps rather than engines"},
                 {"title": "B", "body": "unrelated"}]
        c = {"text": "x", "replacements": [{"find": "body flaps rather than engines", "replace": "engines"}]}
        assert correction_items(c, items) == [items[0]]
        assert correction_items({"text": "nothing in common here"}, items) == []


# --------------------------------------------------------------- books --
class TestBookCorrectionGate:
    def _volume(self, tmp_path, text):
        from engine.book_compiler import BookChapter, BookVolume
        (tmp_path / "Demo_Ep001_20261021.md").write_text(text, encoding="utf-8")
        vol = BookVolume(volume_id="v", show_slug="demo", show_name="Demo", volume_number=1,
                         title="T", episodes=[1], digest_dir=str(tmp_path))
        return vol, [BookChapter(number=1, episode_num=1, title="One")]

    def _corrections(self, tmp_path, entry):
        import yaml
        (tmp_path / "corrections.yaml").write_text(yaml.safe_dump([entry]), encoding="utf-8")

    def test_an_unapplied_text_correction_refuses_the_volume(self, tmp_path):
        from engine.book_compiler import validate_chapter_corrections
        vol, ch = self._volume(tmp_path, "The Apple II needed no extra hardware.")
        self._corrections(tmp_path, {"episode": 1, "date": "2026-10-21", "text": "wrong", "where": "both",
                                     "replacements": [{"find": "needed no extra hardware",
                                                       "replace": "needed an RF modulator"}]})
        with pytest.raises(ValueError, match="not applied"):
            validate_chapter_corrections(vol, ch)

    def test_a_text_correction_without_replacements_refuses_the_volume(self, tmp_path):
        from engine.book_compiler import validate_chapter_corrections
        vol, ch = self._volume(tmp_path, "Text.")
        self._corrections(tmp_path, {"episode": 1, "date": "2026-10-21", "text": "wrong", "where": "digest"})
        with pytest.raises(ValueError, match="no replacement text"):
            validate_chapter_corrections(vol, ch)

    def test_applied_and_audio_only_corrections_pass(self, tmp_path):
        from engine.book_compiler import validate_chapter_corrections
        vol, ch = self._volume(tmp_path, "The Apple II needed an RF modulator.")
        self._corrections(tmp_path, {"episode": 1, "date": "2026-10-21", "text": "wrong", "where": "both",
                                     "replacements": [{"find": "needed no extra hardware",
                                                       "replace": "needed an RF modulator"}]})
        validate_chapter_corrections(vol, ch)
        self._corrections(tmp_path, {"episode": 1, "date": "2026-10-21", "text": "4:53 pm", "where": "audio"})
        validate_chapter_corrections(vol, ch)

    def test_the_gate_runs_in_build_epub_and_live_volumes_pass(self):
        from engine import book_compiler as bc
        src = Path(bc.__file__).read_text(encoding="utf-8")
        body = src[src.index("def build_epub("):]
        assert "validate_chapter_corrections(volume, chapters)" in body[:4000]
        for v in sorted((ROOT / "books" / "volumes").glob("*.yaml")):
            vol = bc.load_volume(v)
            if vol.retired:
                continue
            bc.validate_chapter_corrections(vol, bc.collect_chapters(vol))


# ------------------------------------------------------------- wiring --
class TestWiring:
    SRC = (ROOT / "run_show.py").read_text(encoding="utf-8")

    def test_the_draft_is_recorded_as_listed_and_the_final_digest_as_aired(self):
        assert self.SRC.count("record_aired=False") == 2
        save = self.SRC.index('digest_md.write_text(_scrub(x_thread), encoding="utf-8")')
        aired = self.SRC.index("record_aired=True")
        assert save < aired < save + 1500

    def test_the_tracker_migrates_on_load(self):
        assert "content_tracker.migrate_to_aired(section_patterns)" in self.SRC

    def test_the_cross_show_block_reads_the_aired_stories(self):
        assert "from engine.cross_show import" in self.SRC
        assert "query_all_shows_range(cross_start" not in self.SRC

    def test_the_catalog_write_follows_the_audio_first_publish(self):
        cp = self.SRC.index("    _checkpoint_publish(args, metrics)\n")
        rr = self.SRC.index("_catalog.record_run(")
        assert cp < rr < cp + 2500
        assert self.SRC.index("_catalog_fetched = list(articles)") < self.SRC.index(
            "if len(articles) > MAX_ARTICLES_FOR_LLM:")

    def test_the_lake_write_records_aired_stories(self):
        assert "_headlines = aired_titles(x_thread)" in self.SRC
        assert "rebuild_story_ids(since=today.isoformat())" in self.SRC

    def test_workflows(self):
        wf = (ROOT / ".github/workflows/story-catalog.yml").read_text(encoding="utf-8")
        assert "secrets.VOICES_SUPABASE_URL" in wf and "secrets.VOICES_SUPABASE_SERVICE_KEY" in wf
        assert "backfill_content_lake.py" in wf and "api/story_catalog.json" in wf
        sp = (ROOT / ".github/workflows/produce-special.yml").read_text(encoding="utf-8")
        assert sp.index("backfill_content_lake.py") < sp.index("- name: Produce")

    def test_the_migration_keeps_every_table_service_role_only(self):
        sql = (ROOT / "supabase/migrations/20261021_story_catalog.sql").read_text(encoding="utf-8")
        tables = re.findall(r"create table if not exists public\.(catalog_\w+)", sql)
        assert len(tables) == 6
        for t in tables:
            assert f"alter table public.{t} enable row level security;" in sql
        assert "create policy" not in sql.lower()
