"""Guards for the YouTube audience demographics + geography fetch.

Added July 30 2026 after the operator read these off a phone screenshot
and asked two questions the repo could not answer: is the near-total
male skew real, and is the zero-under-25 figure real or an artifact?

The strategically interesting cut is **Shorts vs long-form**, which
Studio does not offer. Shorts skew young almost everywhere, so a channel
whose Shorts don't is a different situation from one whose long-form
drags the average up. The Analytics API has no Shorts dimension, so the
split comes from filtering the report on our own index's ``kind``.

Everything here is best-effort by contract: demographics are a reporting
nicety and must never take down the nightly analytics fetch.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _module():
    spec = importlib.util.spec_from_file_location(
        "fya_demo", ROOT / "scripts" / "fetch_youtube_analytics.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Reports:
    def __init__(self, payloads, boom=False):
        self.payloads, self.boom, self.calls = payloads, boom, []

    def query(self, **kw):
        self.calls.append(kw)
        self._kw = kw
        return self

    def execute(self):
        if self.boom:
            raise RuntimeError("403 insufficient permissions")
        return self.payloads.get(self._kw.get("dimensions"), {})


class _Service:
    def __init__(self, payloads, boom=False):
        self._r = _Reports(payloads, boom)

    def reports(self):
        return self._r


_DEMO = {
    "ageGroup,gender": {
        "columnHeaders": [{"name": "ageGroup"}, {"name": "gender"},
                          {"name": "viewerPercentage"}],
        "rows": [["age65-", "male", 32.7], ["age55-64", "male", 23.6],
                 ["age45-54", "male", 19.6], ["age25-34", "female", 0.5]],
    },
    "country": {
        "columnHeaders": [{"name": "country"}, {"name": "views"},
                          {"name": "estimatedMinutesWatched"}],
        "rows": [["US", 5081, 900.0], ["JP", 470, 60.0], ["CA", 429, 55.0]],
    },
}


class TestViewerPercentages:
    def test_age_labels_are_stripped_of_the_api_prefix(self):
        m = _module()
        rows = m._viewer_percentages(_Service(_DEMO), "2026-07-02", "2026-07-29")
        assert {r["age"] for r in rows} == {"65-", "55-64", "45-54", "25-34"}

    def test_a_video_filter_is_sent_when_ids_are_given(self):
        """This is what produces the Shorts-vs-long split."""
        m = _module()
        svc = _Service(_DEMO)
        m._viewer_percentages(svc, "2026-07-02", "2026-07-29",
                              video_ids=["a", "b", "c"])
        assert svc.reports().calls[-1]["filters"] == "video==a,b,c"

    def test_the_filter_list_is_bounded(self):
        # An unbounded id list would 400 the whole report on a big channel.
        m = _module()
        svc = _Service(_DEMO)
        m._viewer_percentages(svc, "2026-07-02", "2026-07-29",
                              video_ids=[f"v{i}" for i in range(500)])
        sent = svc.reports().calls[-1]["filters"].split("==")[1].split(",")
        assert len(sent) == m._DEMO_FILTER_MAX

    def test_a_failure_is_an_empty_list_not_an_exception(self):
        m = _module()
        assert m._viewer_percentages(_Service({}, boom=True), "a", "b") == []

    def test_geography_failure_is_also_contained(self):
        m = _module()
        assert m._geography(_Service({}, boom=True), "a", "b") == []


class TestSummary:
    def test_marginals_match_the_studio_screenshot(self):
        m = _module()
        rows = m._viewer_percentages(_Service(_DEMO), "a", "b")
        s = m._summarise_demographics(rows)
        # 23.6 + 32.7 from the operator's 2026-07-29 screenshot.
        assert s["pct_55_plus"] == pytest.approx(56.3, abs=0.05)
        assert s["pct_under_25"] == 0
        assert s["by_gender"]["female"] == pytest.approx(0.5)

    def test_empty_input_summarises_to_nothing_not_to_zeros(self):
        # "not measured" and "measured as zero" must stay distinguishable.
        assert _module()._summarise_demographics([]) == {}


class TestGeography:
    def test_shares_are_labelled_as_of_listed_countries(self):
        """The API returns a top-N, so a share of it is NOT a share of
        all views. The key name has to say so — the operator's own
        screenshot listed ten countries summing to ~52%."""
        m = _module()
        rows = m._geography(_Service(_DEMO), "a", "b")
        assert all("pct_of_listed" in r for r in rows)
        assert sum(r["pct_of_listed"] for r in rows) == pytest.approx(100, abs=0.1)


class TestDashboardSurface:
    def test_absent_stats_report_not_configured(self, tmp_path):
        sys.path.insert(0, str(ROOT / "scripts"))
        from generate_dashboard import build_audience_section

        out = build_audience_section(tmp_path)
        assert out["youtube_audience"]["configured"] is False

    def test_demographics_reach_the_dashboard(self, tmp_path):
        import json

        sys.path.insert(0, str(ROOT / "scripts"))
        from generate_dashboard import build_audience_section

        api = tmp_path / "api"
        api.mkdir()
        (api / "youtube_stats.json").write_text(json.dumps({
            "generated": "2026-07-30T18:00:00Z",
            "channels": {"en": {
                "demographics": {
                    "window_days": 28,
                    "summary": {"pct_55_plus": 56.3, "pct_under_25": 0.0,
                                "by_gender": {"male": 99.5, "female": 0.5}},
                    "short_summary": {"pct_under_25": 12.0},
                },
                "geography": [{"country": "US", "views": 5081,
                               "pct_of_listed": 70.0}],
            }},
        }))
        out = build_audience_section(tmp_path)["youtube_audience"]
        assert out["configured"] is True
        en = out["channels"]["en"]
        assert en["summary"]["pct_55_plus"] == 56.3
        # The Shorts split is the whole point of the fetch.
        assert en["short_summary"]["pct_under_25"] == 12.0
        # ...and long-form is ABSENT rather than zeroed when unmeasured.
        assert "long_summary" not in en
        assert "signed-in" in out["note"]
