"""Oct 4 2026 — Offshore North: the YB tracker fix, the Instagram source,
and five editorial rules from the operator.

Rules (operator, 4 Oct 2026):
1. The boat is based in Gosport, UK (Portsmouth Harbour) — never Brittany.
2. A position always carries its date and its source.
3. The fix comes from the YB tracker each week; older than 7 days = "last
   seen <date>", never the present tense.
4. Never "training solo in Europe": the tracker shows one outing since 4 Sep.
5. Route du Rhum: "aiming to start" — not on the official entry list yet.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import instagram_source as ig  # noqa: E402
from engine import yb_tracker as yb  # noqa: E402

UTC = dt.timezone.utc
GOSPORT = {"name": "Gosport, UK (Portsmouth Harbour)", "lat": 50.796, "lon": -1.116, "radius_km": 2}


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _curated() -> dict:
    return json.loads(_read("site/data/offshore_north_dashboard.json"))


def _fix(day: int, hour: int, lat: float, lon: float, month: int = 9) -> dict:
    return {"at": dt.datetime(2026, month, day, hour, tzinfo=UTC), "lat": lat, "lon": lon}


def _track() -> list:
    """Delivery at sea → Gosport on 4 Sep → one Channel outing 17 Sep → berth."""
    fixes = [_fix(d, h, 49.0 + d * 0.01, -10.0 + d * 0.3, month=8)
             for d in range(25, 31) for h in (0, 12)]
    fixes += [_fix(4, 21, 50.7963, -1.1160)]
    fixes += [_fix(d, 12, 50.7962, -1.1160) for d in range(5, 17)]
    fixes += [_fix(17, 15, 50.7370, -1.0690), _fix(17, 19, 50.2280, -1.7090),
              _fix(17, 23, 50.7480, -1.0850)]
    fixes += [_fix(d, 12, 50.7962, -1.1160) for d in range(18, 31)]
    fixes += [_fix(4, 16, 50.7962, -1.1160, month=10)]
    return fixes


# ---------------------------------------------------------------------------
# The tracker
# ---------------------------------------------------------------------------

class TestYbTracker:
    def test_parses_the_api_shape(self):
        payload = {"positions": [{"at": 1791144398518, "t": 50.79, "g": -1.11, "id": 1},
                                 {"at": "bad"}, {"at": 1789642821000, "t": 50.7, "g": -1.1}]}
        fixes = yb.parse_positions(payload)
        assert len(fixes) == 2 and fixes[0]["at"] < fixes[1]["at"]

    def test_rolling_window_is_chosen_by_name(self):
        events = [{"id": 1, "name": "Training", "endTime": 2},
                  {"id": 9, "name": "Last 30 days", "endTime": 1}]
        assert yb._rolling_event_id(events) == 9

    def test_summary_finds_arrival_berth_and_the_one_outing(self):
        s = yb.summarise(_track(), keyword="emira4", places=[GOSPORT])
        assert s["latest"]["place"] == GOSPORT["name"]
        assert s["arrived"] == "2026-09-04"
        assert len(s["outings"]) == 1
        out = s["outings"][0]
        assert out["date"] == "2026-09-17" and out["max_km"] > 60
        assert s["url"] == "https://my.yb.tl/emira4"

    def test_a_place_is_named_only_when_the_record_names_it(self):
        s = yb.summarise(_track(), keyword="emira4", places=[])
        assert s["latest"]["place"] == ""
        sentence = yb.position_sentence(s, dt.date(2026, 10, 4))
        assert "50.80°N, 1.12°W" in sentence and "Gosport" not in sentence

    @pytest.mark.parametrize("today,present", [
        (dt.date(2026, 10, 4), True), (dt.date(2026, 10, 11), True),
        (dt.date(2026, 10, 12), False), (dt.date(2026, 11, 1), False),
    ])
    def test_present_tense_only_inside_seven_days(self, today, present):
        s = yb.summarise(_track(), keyword="emira4", places=[GOSPORT])
        sentence = yb.position_sentence(s, today)
        assert "4 October 2026" in sentence and "YB tracker" in sentence  # date + source
        if present:
            assert sentence.startswith("As of 4 October 2026")
        else:
            assert "last seen" in sentence and " is " not in sentence.split(",")[0]
        assert yb.STALE_DAYS == 7

    def test_the_fix_is_a_verifiable_source_article(self):
        s = yb.summarise(_track(), keyword="emira4", places=[GOSPORT])
        art = yb.tracker_article(s, dt.date(2026, 10, 4))
        assert art["url"] == "https://my.yb.tl/emira4" and art["exempt_stale"] is True
        assert "Gosport" in art["content_text"] and "1 (17 September 2026" in art["content_text"]
        from engine.hook_articles import normalize_hook_articles

        assert normalize_hook_articles([art])[0]["content_text"] == art["content_text"]

    def test_network_failure_is_none_never_raises(self, monkeypatch):
        class _Boom:
            def get(self, *a, **k):
                raise RuntimeError("down")

        assert yb.fetch_summary("emira4", session=_Boom()) is None


# ---------------------------------------------------------------------------
# Instagram: text and links only, read-only credentials
# ---------------------------------------------------------------------------

class TestInstagramSource:
    def test_no_credentials_is_a_clean_no_op(self, monkeypatch):
        monkeypatch.delenv(ig.TOKEN_ENV, raising=False)
        monkeypatch.delenv(ig.USER_ID_ENV, raising=False)
        assert ig.fetch_recent(["Canada_Ocean_Racing"]) == []

    def test_never_requests_a_media_url(self, monkeypatch):
        monkeypatch.setenv(ig.TOKEN_ENV, "t")
        monkeypatch.setenv(ig.USER_ID_ENV, "1")
        seen = {}

        class _Resp:
            status_code = 200

            def json(self):
                return {"business_discovery": {"username": "Canada_Ocean_Racing", "media": {"data": [
                    {"caption": "Back in Gosport after a Channel run.", "permalink": "https://www.instagram.com/p/A/",
                     "timestamp": "2026-10-03T10:00:00+0000", "media_type": "IMAGE"}]}}}

        class _Session:
            def get(self, url, params=None, timeout=None):
                seen.update(params or {})
                return _Resp()

        posts = ig.fetch_recent(["Canada_Ocean_Racing"], session=_Session(),
                                now=dt.datetime(2026, 10, 4, tzinfo=UTC))
        assert "media_url" not in seen["fields"] and "media_url" not in ig.MEDIA_FIELDS
        assert posts and posts[0]["permalink"] == "https://www.instagram.com/p/A/"
        assert "media_url" not in posts[0]

    def test_read_credentials_never_share_the_publisher_names(self):
        assert ig.TOKEN_ENV == "INSTAGRAM_GRAPH_TOKEN" and ig.USER_ID_ENV == "INSTAGRAM_GRAPH_USER_ID"
        src = _read("engine/instagram_source.py")
        assert 'os.getenv("IG_ACCESS_TOKEN' not in src
        for wf in (".github/workflows/run-show.yml", ".github/workflows/nightly-maintenance.yml"):
            assert "INSTAGRAM_GRAPH_TOKEN: ${{ secrets.INSTAGRAM_GRAPH_TOKEN }}" in _read(wf)

    def test_handles_come_from_the_record(self):
        handles = ig.handles_from_follow(_curated()["follow"])
        assert handles[0] == "Canada_Ocean_Racing"
        assert {"imocaglobeseries", "route_du_rhum", "vendeeglobe"} <= set(handles)
        assert _curated()["campaign"]["instagram_handles"] == ["Canada_Ocean_Racing"]

    def test_posts_become_cited_articles(self):
        arts = ig.post_articles([
            {"account": "route_du_rhum", "caption": "J-28 before the start. #RouteDuRhum",
             "permalink": "https://www.instagram.com/p/B/", "timestamp": "2026-10-04T08:00:00+00:00"},
            {"account": "x", "caption": "", "permalink": "https://www.instagram.com/p/C/",
             "timestamp": "2026-10-04T08:00:00+00:00"},
        ])
        assert len(arts) == 1
        assert arts[0]["url"] == "https://www.instagram.com/p/B/"
        assert arts[0]["source_name"] == "Instagram @route_du_rhum"
        assert arts[0]["title"] == "J-28 before the start."


# ---------------------------------------------------------------------------
# The record, the status block, the hook
# ---------------------------------------------------------------------------

class TestRecordAndStatus:
    def test_record_carries_the_tracker_and_gosport(self):
        d = _curated()
        tr = d["campaign"]["tracker"]
        assert tr["keyword"] == "emira4" and tr["places"][0]["name"].startswith("Gosport")
        dated = {p["date"]: p for p in d["position_log"]}
        assert "Gosport" in dated["2026-09-04"]["text"] and "Gosport" in dated["2026-10-04"]["text"]
        assert "Channel" in dated["2026-09-17"]["text"]
        for p in ("2026-09-04", "2026-09-17", "2026-10-04"):
            assert dated[p]["url"] == "https://my.yb.tl/emira4"

    def test_rhum_entry_is_aiming_to_start(self):
        d = _curated()
        assert d["rhum_entry"]["status"] == "aiming_to_start"
        rdr = next(c for c in d["countdowns"] if c["id"] == "rdr_start")
        assert rdr["emira_entered"] is None and "aiming to start" in rdr["emira_entry_text"]
        assert "aiming to start" in rdr["sub"]
        can = next(e for e in d["rdr_imoca_entries"]["entries"] if e.get("canada"))
        assert can["official"] is False
        assert not any("EMIRA IV entered" in c.get("label", "") for c in d["calendar"])

    def test_status_block_leads_with_the_tracker(self):
        from engine.offshore_north_status import build_campaign_status

        s = yb.summarise(_track(), keyword="emira4", places=[GOSPORT])
        fresh = build_campaign_status(_curated(), tracker=s,
                                      now=dt.datetime(2026, 10, 4, 18, tzinfo=UTC))
        assert "LAST KNOWN POSITION — YB TRACKER, newest fix 2026-10-04" in fresh
        assert "alongside in Gosport" in fresh and "https://my.yb.tl/emira4" in fresh
        assert "OUTINGS ON THE TRACKER" in fresh and "training solo in Europe" in fresh
        assert "AIMING TO START" in fresh and "IS on the list" not in fresh
        stale = build_campaign_status(_curated(), tracker=s,
                                      now=dt.datetime(2026, 10, 20, tzinfo=UTC))
        assert 'say "last seen 4 October 2026"' in stale

    def test_hook_hands_over_the_fix_and_instagram(self, monkeypatch):
        sys.path.insert(0, str(ROOT / "shows"))
        import importlib

        hook = importlib.import_module("hooks.offshore_north")
        summary = yb.summarise(_track(), keyword="emira4", places=[GOSPORT])
        monkeypatch.setattr(hook, "_fresh_tracker", lambda: summary)
        monkeypatch.setattr(ig, "fetch_recent", lambda handles, **k: [
            {"account": h, "caption": f"Post from {h}.", "permalink": f"https://www.instagram.com/p/{h}/",
             "timestamp": "2026-10-03T10:00:00+00:00"} for h in handles])
        monkeypatch.setattr(hook.show_memory, "memory_pre_fetch", lambda *a, **k: {})
        ctx = hook.pre_fetch(object())
        assert "Gosport" in ctx["campaign_status"]
        urls = [a["url"] for a in ctx["articles"]]
        assert urls[0] == "https://my.yb.tl/emira4"
        assert "https://www.instagram.com/p/Canada_Ocean_Racing/" in urls


# ---------------------------------------------------------------------------
# The prompts and the page
# ---------------------------------------------------------------------------

class TestEditorialRules:
    def test_standing_facts(self):
        f = _read("shows/prompts/offshore_north_standing_facts.txt")
        assert "based in Gosport, UK (Portsmouth Harbour)" in f
        assert "NOT in Brittany and NOT in Lorient" in f
        assert '"last seen [date]"' in f and "my.yb.tl/emira4" in f
        assert "Never say Scott is \"training solo in Europe\"" in f
        assert "AIMING TO START" in f and "Entry CONFIRMED" not in f
        assert "French base is NOT confirmed" not in f

    def test_digest_and_podcast_rules(self):
        d = _read("shows/prompts/offshore_north_digest.txt")
        p = _read("shows/prompts/offshore_north_podcast.txt")
        assert "in Lorient]" not in d  # the quotable example that named a French base
        assert '"last seen"' in d and "seven days" in d and "Gosport" in d
        assert '"last seen"' in p and "never described as training" in p

    def test_field_guide_says_aiming_to_start(self):
        g = _read("shows/prompts/offshore_north_field_guide.txt")
        assert "Scott Shawyer is aiming to start" in g and "Scott Shawyer is entered" not in g

    def test_dashboard_reads_the_tracker_and_embeds_on_request(self):
        t = _read("templates/offshore_north_dashboard.html.j2")
        assert "data.tracker" in t and "ageDays <= 7" in t and "'Last seen '" in t
        assert 'id="onInstagram"' in t and "instagram.com/embed.js" in t
        # the embed script is only added inside the click handler
        click = t.index("igBtn.addEventListener('click'")
        assert t.index("instagram.com/embed.js") > click
        assert "#onInstagramPanel [hidden] { display:none !important; }" in t
