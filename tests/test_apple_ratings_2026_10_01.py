"""Apple Podcasts ratings read-back (Oct 1 2026).

The network has asked listeners to "rate us on Apple Podcasts" in every
outro since launch and read the result back nowhere. The fetcher reads
the PUBLIC show page (no auth, no paid API): the JSON-LD
``aggregateRating`` when the show has ratings, the page's serialised
``ratings`` metadata when it does not (that block states an explicit
zero). Contract pinned here:

* parsing of both live shapes (fixtures are trimmed copies of the real
  2026-10-01 pages for The Daily and Tesla Shorts Time);
* null, never 0, for a page that carries no rating block at all;
* a failed fetch keeps the previous reading tagged ``not_refreshed_this_run``;
* the per-show ``history`` is one entry per day, capped at 90;
* the nightly whitelist carries ``api/apple_ratings.json`` (the
  youtube_channel_history silent-drop class);
* the dashboard section's shape — per-show rating / count / 7-day delta,
  network totals, ``fmtOrDash`` semantics on the page.

No network call is made anywhere in this file.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts import fetch_apple_ratings as far  # noqa: E402
from scripts import generate_dashboard as gd  # noqa: E402


# A rated show: trimmed from podcasts.apple.com/us/podcast/the-daily/id1200361736
# as served on 2026-10-01. Apple labels the ratings count ``reviewCount``.
_RATED_PAGE = """<!DOCTYPE html><html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"CreativeWorkSeries","name":"The Daily",
 "url":"https://podcasts.apple.com/us/podcast/the-daily/id1200361736",
 "aggregateRating":{"@type":"AggregateRating","ratingValue":4.3,"reviewCount":105794,
   "itemReviewed":{"@type":"CreativeWorkSeries","name":"The Daily"}},
 "workExample":[]}
</script>
<script type="fastboot/shoebox" id="shoebox-media-api-cache-amp-podcasts">
{"metadata":[{"ratings":{"productId":"1200361736","ratingAverage":4.3,
 "totalNumberOfRatings":105794,"totalNumberOfReviews":0,"formattedCount":"106K",
 "ratingCounts":[77615,8620,5061,3974,10524],"$kind":"RatingsAndReviews","id":"RatingsAndReviews#57830"}},
 {"category":"Daily News"}]}
</script></head><body></body></html>"""

# An unrated show: trimmed from the Tesla Shorts Time page the same day —
# NO aggregateRating in the JSON-LD, and the metadata states zero.
_ZERO_PAGE = """<!DOCTYPE html><html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"CreativeWorkSeries","name":"Tesla Shorts Time",
 "url":"https://podcasts.apple.com/us/podcast/tesla-shorts-time/id1855142939","workExample":[]}
</script>
<script type="fastboot/shoebox">
{"metadata":[{"ratings":{"productId":"1855142939","ratingAverage":0,"totalNumberOfRatings":0,
 "totalNumberOfReviews":0,"formattedCount":"0","ratingCounts":[0,0,0,0,0],
 "$kind":"RatingsAndReviews","id":"RatingsAndReviews#57943"}},{"category":"Technology"}]}
</script></head><body></body></html>"""

# A page with no rating block of either shape (a blocked/odd render).
_NO_BLOCK_PAGE = """<html><head><script type="application/ld+json">
{"@type":"CreativeWorkSeries","name":"Something"}</script></head><body>hi</body></html>"""

_NOW = _dt.datetime(2026, 10, 1, 16, 45, tzinfo=_dt.timezone.utc)


class TestParsing:
    def test_rated_page_reads_ld_json(self):
        out = far.parse_apple_ratings(_RATED_PAGE)
        assert out["rating_value"] == 4.3
        assert out["rating_count"] == 105794, "Apple's reviewCount IS the ratings count"
        assert out["review_count"] == 0, "written reviews come from the metadata block"
        assert out["source"] == "ld_json"

    def test_unrated_page_is_a_measured_zero_not_null(self):
        out = far.parse_apple_ratings(_ZERO_PAGE)
        assert out["rating_count"] == 0
        assert out["rating_value"] is None, "an average of nothing is not 0.0"
        assert out["source"] == "page_metadata"

    def test_no_rating_block_is_null_never_zero(self):
        out = far.parse_apple_ratings(_NO_BLOCK_PAGE)
        assert out == {"rating_value": None, "rating_count": None,
                       "review_count": None, "source": None}
        assert far.parse_apple_ratings("") == out

    def test_ratingcount_key_is_honoured_when_present(self):
        page = ('<script type="application/ld+json">{"@type":"CreativeWorkSeries",'
                '"aggregateRating":{"ratingValue":"4.8","ratingCount":"12"}}</script>')
        out = far.parse_apple_ratings(page)
        assert out["rating_value"] == 4.8 and out["rating_count"] == 12

    def test_malformed_ld_json_does_not_raise(self):
        page = '<script type="application/ld+json">{not json</script>' + _ZERO_PAGE
        out = far.parse_apple_ratings(page)
        assert out["rating_count"] == 0 and out["source"] == "page_metadata"


class TestBuildRatings:
    _TARGETS = [
        {"slug": "tesla", "apple_url": "https://podcasts.apple.com/us/podcast/id1"},
        {"slug": "spacex", "apple_url": "https://podcasts.apple.com/us/podcast/id2"},
        {"slug": "dp_pod", "apple_url": "https://podcasts.apple.com/us/podcast/id3"},
    ]

    def test_writes_null_not_zero_and_keeps_previous_on_failure(self):
        pages = {"id1": _RATED_PAGE, "id2": _NO_BLOCK_PAGE, "id3": None}
        previous = {"shows": {"dp_pod": {
            "apple_url": "https://podcasts.apple.com/us/podcast/id3",
            "rating_value": 5.0, "rating_count": 3, "review_count": 1,
            "source": "ld_json", "fetched_at": "2026-09-30T16:45:00+00:00",
            "history": [{"date": "2026-09-30", "rating_value": 5.0, "rating_count": 3}],
        }}}
        slept = []
        stats = far.build_ratings(
            self._TARGETS, previous,
            fetch=lambda url: pages[url.rsplit("/", 1)[-1]],
            sleep=slept.append, pause=1.5, now=_NOW)

        assert stats["fetched_at"] == _NOW.isoformat()
        shows = stats["shows"]
        assert shows["tesla"]["rating_value"] == 4.3
        assert shows["tesla"]["rating_count"] == 105794
        assert shows["tesla"]["history"] == [
            {"date": "2026-10-01", "rating_value": 4.3, "rating_count": 105794}]
        # No rating block → null, never 0, and the note says why.
        assert shows["spacex"]["rating_value"] is None
        assert shows["spacex"]["rating_count"] is None
        assert shows["spacex"]["note"] == far.NO_RATING_BLOCK_NOTE
        # Failed fetch → previous reading kept, flagged, history unchanged.
        assert shows["dp_pod"]["not_refreshed_this_run"] is True
        assert shows["dp_pod"]["rating_count"] == 3
        assert shows["dp_pod"]["history"] == previous["shows"]["dp_pod"]["history"]
        assert "not_refreshed_this_run" not in shows["tesla"]
        # Politeness: a pause between shows, never before the first.
        assert slept == [1.5, 1.5]

    def test_failed_fetch_with_no_previous_is_flagged_not_fabricated(self):
        stats = far.build_ratings(self._TARGETS[:1], None, fetch=lambda u: None,
                                  sleep=lambda s: None, now=_NOW)
        entry = stats["shows"]["tesla"]
        assert entry["rating_count"] is None and entry["rating_value"] is None
        assert entry["not_refreshed_this_run"] is True
        assert entry["history"] == []

    def test_history_is_one_entry_per_day_capped_at_90(self):
        start = _dt.date(2026, 1, 1)
        history = [{"date": (start + _dt.timedelta(days=i)).isoformat(),
                    "rating_value": 4.0, "rating_count": i} for i in range(120)]
        previous = {"shows": {"tesla": {"history": history}}}
        # Same-day rerun: the day's entry is REPLACED, not duplicated.
        today = start + _dt.timedelta(days=119)
        now = _dt.datetime.combine(today, _dt.time(12), tzinfo=_dt.timezone.utc)
        stats = far.build_ratings(self._TARGETS[:1], previous,
                                  fetch=lambda u: _RATED_PAGE,
                                  sleep=lambda s: None, now=now)
        hist = stats["shows"]["tesla"]["history"]
        assert len(hist) == far.HISTORY_MAX == 90
        assert [h["date"] for h in hist] == sorted(h["date"] for h in hist)
        assert hist[-1] == {"date": today.isoformat(), "rating_value": 4.3,
                            "rating_count": 105794}
        assert sum(1 for h in hist if h["date"] == today.isoformat()) == 1

    def test_fetch_page_never_raises(self, monkeypatch):
        import requests as _requests

        def _boom(*a, **k):
            raise _requests.exceptions.ConnectionError("down")
        monkeypatch.setattr(_requests, "get", _boom)
        assert far.fetch_page("https://podcasts.apple.com/us/podcast/id1") is None

        class _Resp:
            status_code = 403
            text = "blocked"
        monkeypatch.setattr(_requests, "get", lambda *a, **k: _Resp())
        assert far.fetch_page("https://podcasts.apple.com/us/podcast/id1") is None

    def test_fetch_page_sends_browser_ua_and_timeout(self, monkeypatch):
        import requests as _requests
        seen = {}

        class _Resp:
            status_code = 200
            text = _ZERO_PAGE

        def _get(url, headers=None, timeout=None):
            seen.update({"ua": (headers or {}).get("User-Agent"), "timeout": timeout})
            return _Resp()
        monkeypatch.setattr(_requests, "get", _get)
        assert far.fetch_page("https://podcasts.apple.com/x") == _ZERO_PAGE
        assert seen["ua"].startswith("Mozilla/5.0") and "python" not in seen["ua"].lower()
        assert seen["timeout"] == 20

    def test_targets_cover_every_show_with_an_apple_page(self):
        """Registry string or YAML apple_show_id — the way the site resolves it."""
        targets = {t["slug"]: t["apple_url"] for t in far.rating_targets()}
        assert targets["tesla"].endswith("/id1855142939")
        assert "spacex" in targets, "spacex has only a YAML apple_show_id"
        assert all(u.startswith("https://podcasts.apple.com/") for u in targets.values())
        # The September cohort has no Apple page yet (never submitted).
        assert "ai_chips" not in targets

    def test_main_writes_file_with_mocked_fetch(self, tmp_path, monkeypatch):
        monkeypatch.setattr(far, "rating_targets", lambda: self._TARGETS[:1])
        monkeypatch.setattr(far, "fetch_page", lambda url: _RATED_PAGE)
        out = tmp_path / "apple_ratings.json"
        assert far.main(["--out", str(out), "--pause", "0"]) == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert set(data) == {"fetched_at", "shows"}
        assert data["shows"]["tesla"]["rating_count"] == 105794


class TestNightlyWiring:
    def test_fetch_step_and_whitelist(self):
        wf = (_ROOT / ".github" / "workflows" / "nightly-maintenance.yml").read_text(
            encoding="utf-8")
        assert "python scripts/fetch_apple_ratings.py --out api/apple_ratings.json" in wf
        assert wf.index("fetch_apple_ratings.py") < wf.index("generate_dashboard.py --out"), (
            "ratings must be fetched before the dashboard build consumes them")
        # The silent-drop class: a generated path missing from add-paths is
        # rebuilt nightly and thrown away (youtube_channel_history, 4 runs).
        assert "            api/apple_ratings.json\n" in wf

    def test_documented_in_analytics_contract(self):
        doc = (_ROOT / "docs" / "analytics.md").read_text(encoding="utf-8")
        assert "`api/apple_ratings.json`" in doc
        assert "fetch_apple_ratings.py" in doc


def _seed(tmp_path: Path, shows: dict, fetched_at: str = "2026-10-01T16:45:00+00:00") -> Path:
    (tmp_path / "api").mkdir(exist_ok=True)
    (tmp_path / "api" / "apple_ratings.json").write_text(
        json.dumps({"fetched_at": fetched_at, "shows": shows}), encoding="utf-8")
    return tmp_path


class TestDashboardSection:
    def test_absent_file_is_not_configured(self, tmp_path):
        assert gd.build_apple_ratings_section(tmp_path) == {"configured": False}

    def test_shape_and_delta(self, tmp_path):
        hist = lambda pairs: [  # noqa: E731
            {"date": d, "rating_value": v, "rating_count": c} for d, v, c in pairs]
        root = _seed(tmp_path, {
            "tesla": {"apple_url": "u1", "rating_value": 4.8, "rating_count": 12,
                      "review_count": 2, "source": "ld_json",
                      "fetched_at": "2026-10-01T16:45:00+00:00",
                      "history": hist([("2026-09-20", 4.7, 7), ("2026-09-24", 4.8, 9),
                                       ("2026-09-26", 4.8, 10), ("2026-10-01", 4.8, 12)])},
            "spacex": {"apple_url": "u2", "rating_value": 5.0, "rating_count": 4,
                       "review_count": 0, "source": "ld_json",
                       "fetched_at": "2026-10-01T16:45:00+00:00",
                       "history": hist([("2026-10-01", 5.0, 4)])},
            "dp_pod": {"apple_url": "u3", "rating_value": None, "rating_count": 0,
                       "review_count": 0, "source": "page_metadata",
                       "fetched_at": "2026-10-01T16:45:00+00:00",
                       "history": hist([("2026-09-20", None, 0), ("2026-10-01", None, 0)])},
            "age_of_ai": {"apple_url": "u4", "rating_value": None, "rating_count": None,
                          "review_count": None, "source": None, "fetched_at": None,
                          "history": [], "not_refreshed_this_run": True},
        })
        sec = gd.build_apple_ratings_section(root)
        assert sec["configured"] is True
        per = sec["per_show"]
        assert set(per) == {"tesla", "spacex", "dp_pod", "age_of_ai"}
        # Delta reads the NEWEST history entry at least 7 days old (09-24 → 9).
        assert per["tesla"] == {
            "apple_url": "u1", "rating": 4.8, "count": 12, "review_count": 2,
            "count_delta_7d": 3, "source": "ld_json",
            "fetched_at": "2026-10-01T16:45:00+00:00",
            "not_refreshed_this_run": False, "measured": True}
        assert per["spacex"]["count_delta_7d"] is None, "one day of history is no delta"
        assert per["dp_pod"]["count"] == 0 and per["dp_pod"]["rating"] is None
        assert per["dp_pod"]["count_delta_7d"] == 0, "a measured zero moving to zero is 0"
        # Unmeasured stays null everywhere and is named.
        assert per["age_of_ai"]["count"] is None and per["age_of_ai"]["measured"] is False
        assert per["age_of_ai"]["not_refreshed_this_run"] is True
        net = sec["network"]
        assert net["shows_with_url"] == 4
        assert net["shows_measured"] == 3
        assert net["shows_rated"] == 2
        assert net["shows_unmeasured"] == ["age_of_ai"]
        assert net["rating_count_total"] == 16
        assert net["weighted_rating"] == round((4.8 * 12 + 5.0 * 4) / 16, 2)
        assert net["count_delta_7d_total"] == 3
        assert net["count_delta_7d_shows"] == 2

    def test_nothing_measured_is_null_not_zero(self, tmp_path):
        root = _seed(tmp_path, {
            "tesla": {"apple_url": "u", "rating_value": None, "rating_count": None,
                      "review_count": None, "source": None, "history": []}})
        net = gd.build_apple_ratings_section(root)["network"]
        assert net["rating_count_total"] is None
        assert net["weighted_rating"] is None
        assert net["count_delta_7d_total"] is None

    def test_wired_into_the_dashboard_and_the_page(self):
        src = (_ROOT / "scripts" / "generate_dashboard.py").read_text(encoding="utf-8")
        assert '"apple_ratings": build_apple_ratings_section(root)' in src
        html = (_ROOT / "management.html").read_text(encoding="utf-8")
        assert "data.apple_ratings" in html
        assert 'sectionCard("Apple ratings"' in html
        # Never fabricate a zero: the tile reads through the absence-preserving formatter.
        block = html[html.index('sectionCard("Apple ratings"'):]
        block = block[:block.index("// Unit economics")]
        assert "fmtOrDash(net.rating_count_total)" in block
        assert "fmtOrDash(v.count)" in block


@pytest.mark.parametrize("latest,count,history,expected", [
    (None, 5, [], None),
    (_dt.date(2026, 10, 1), None, [{"date": "2026-09-20", "rating_count": 1}], None),
    (_dt.date(2026, 10, 1), 5, [{"date": "2026-09-30", "rating_count": 1}], None),
    (_dt.date(2026, 10, 1), 5, [{"date": "2026-09-24", "rating_count": 1},
                                {"date": "2026-09-10", "rating_count": 0}], 4),
    (_dt.date(2026, 10, 1), 5, [{"date": "2026-09-24", "rating_count": None}], None),
])
def test_count_delta_rules(latest, count, history, expected):
    assert gd._apple_count_delta(history, latest, count) == expected
