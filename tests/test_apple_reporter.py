"""Drift guards for Apple's official listening reports.

Fixtures below are the **verbatim bytes** of real downloads pulled on 28
July 2026 (``ApplePodcasts_ShowListening_93825591_20260727.txt.gz`` and
its worldwide twin), not a hand-written approximation. Two properties of
that real data are load-bearing and easy to break:

* **Absence is not zero.** Rows exist only for shows with activity that
  day — two rows for a thirty-show network. Reporting the other
  twenty-eight as ``0`` reproduces the silent-zero bug fixed in the
  cookie path a week before this landed.
* **Blank is not zero.** Apple suppresses a metric it will not disclose.
  In the same file Tesla Shorts Time has 38 plays and a *blank* engaged
  listener count while SpaceX Daily has 22 plays and 7. Parsing blank
  as 0 invents a precise-looking falsehood.
"""

from __future__ import annotations

import gzip

import pytest

from engine.apple_reporter import (  # noqa: E402
    SHOW_REPORT,
    SHOW_REPORT_WORLDWIDE,
    ReporterResult,
    ShowListening,
    aggregate_by_show,
    fetch_report_http,
    parse_show_listening,
)

_WORLDWIDE_HEADER = (
    "Channel Identifier\tChannel Name\tShow Identifier\tShow Name\t"
    "Total Listening Hours\tSubscriber Listening Hours\t"
    "Non-Subscriber Listening Hours\tConnected Listening Hours\t"
    "Total Listeners\tSubscribed Listeners\tNon-Subscribed Listeners\t"
    "Connected Listeners\tTotal Engaged Listeners\t"
    "Subscribed Engaged Listeners\tNon-Subscribed Engaged Listeners\t"
    "Connected Engaged Listeners\tTotal Plays\tSubscriber Plays\t"
    "Non-Subscriber Plays\tConnected Plays\n"
)
# Tesla's engaged-listener cell is empty here. That is the real file.
WORLDWIDE = _WORLDWIDE_HEADER + (
    "\t\t1855142939\tTesla Shorts Time\t1.38\t\t1.38\t\t6\t\t6\t\t\t\t\t\t38\t\t38\t\n"
    "\t\t1896920957\tSpaceX Daily\t1.28\t\t1.28\t\t10\t\t10\t\t7\t\t7\t\t22\t\t22\t\n"
)

STOREFRONT = (
    "Store Front Name\t" + _WORLDWIDE_HEADER
).replace("Channel Identifier", "Channel Identifier", 1) + (
    "US\t\t\t1896920957\tSpaceX Daily\t1.02\t\t1.02\t\t8\t\t8\t\t5\t\t5\t\t19\t\t19\t\n"
)


class TestParsingRealReports:
    def test_worldwide_schema_has_no_storefront_column(self):
        rows = parse_show_listening(WORLDWIDE.encode())
        assert len(rows) == 2
        assert all(r.storefront == "" for r in rows)

    def test_storefront_schema_carries_the_storefront(self):
        rows = parse_show_listening(STOREFRONT.encode())
        assert len(rows) == 1
        assert rows[0].storefront == "US"

    def test_columns_are_resolved_by_name_not_position(self):
        """The two schemas differ by one leading column. Position-based
        parsing would silently shift every metric by one."""
        world = {r.show_id: r for r in parse_show_listening(WORLDWIDE.encode())}
        store = {r.show_id: r for r in parse_show_listening(STOREFRONT.encode())}
        assert world["1896920957"].plays == 22
        assert store["1896920957"].plays == 19

    def test_gzip_is_transparent(self):
        assert (parse_show_listening(gzip.compress(WORLDWIDE.encode()))
                == parse_show_listening(WORLDWIDE.encode()))

    def test_show_identifier_matches_the_configured_apple_show_id(self):
        """The join key. These are the real IDs in shows/tesla.yaml and
        shows/spacex.yaml."""
        ids = {r.show_id for r in parse_show_listening(WORLDWIDE.encode())}
        assert ids == {"1855142939", "1896920957"}

    def test_header_only_file_is_empty_not_an_error(self):
        assert parse_show_listening(_WORLDWIDE_HEADER.encode()) == []

    def test_empty_input_is_empty(self):
        assert parse_show_listening(b"") == []

    def test_unrecognised_header_yields_nothing_rather_than_garbage(self):
        assert parse_show_listening(b"Some\tOther\tColumns\n1\t2\t3\n") == []


class TestBlankIsNotZero:
    """The single most important property in this module."""

    def test_suppressed_metric_parses_as_none(self):
        tesla = [r for r in parse_show_listening(WORLDWIDE.encode())
                 if r.show_id == "1855142939"][0]
        assert tesla.engaged_listeners is None
        assert tesla.plays == 38, "a real number beside the blank one"

    def test_suppressed_metric_is_omitted_from_the_dict_entirely(self):
        """So a consumer cannot read it as 0 by accident — the key is
        absent, which forces the caller to handle 'not measured'."""
        tesla = [r for r in parse_show_listening(WORLDWIDE.encode())
                 if r.show_id == "1855142939"][0]
        assert "engaged_listeners" not in tesla.as_dict()
        assert tesla.as_dict()["plays"] == 38

    def test_a_reported_zero_is_preserved_as_zero(self):
        """Blank and an explicit 0 mean different things and must not be
        collapsed into each other."""
        row = _WORLDWIDE_HEADER + (
            "\t\t111\tZero Show\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\t0\t\n")
        parsed = parse_show_listening(row.encode())[0]
        assert parsed.plays == 0
        assert parsed.as_dict()["plays"] == 0

    def test_hours_stay_float_and_counts_stay_int(self):
        spacex = [r for r in parse_show_listening(WORLDWIDE.encode())
                  if r.show_id == "1896920957"][0]
        assert isinstance(spacex.listening_hours, float)
        assert isinstance(spacex.plays, int)


class TestAggregation:
    def test_storefront_rows_sum_per_show(self):
        rows = [
            ShowListening("1", plays=10, listeners=3, listening_hours=1.5,
                          storefront="US"),
            ShowListening("1", plays=4, listeners=2, listening_hours=0.5,
                          storefront="CA"),
        ]
        merged = aggregate_by_show(rows)["1"]
        assert merged.plays == 14
        assert merged.listeners == 5
        assert merged.listening_hours == 2.0

    def test_all_blank_stays_none_rather_than_becoming_zero(self):
        rows = [ShowListening("1", storefront="US"),
                ShowListening("1", storefront="CA")]
        assert aggregate_by_show(rows)["1"].plays is None

    def test_one_reported_value_among_blanks_survives(self):
        rows = [ShowListening("1", storefront="US"),
                ShowListening("1", plays=7, storefront="CA")]
        assert aggregate_by_show(rows)["1"].plays == 7

    def test_shows_stay_separate(self):
        merged = aggregate_by_show(parse_show_listening(WORLDWIDE.encode()))
        assert set(merged) == {"1855142939", "1896920957"}
        assert merged["1855142939"].plays == 38


class TestHttpTransportFailsSoftly:
    """Analytics must degrade, never raise into a publish."""

    def test_missing_token_is_an_error_not_an_exception(self):
        out = fetch_report_http(access_token="", account="1", vendor="9",
                                date="20260727")
        assert not out.ok and "token" in out.error

    def test_unreachable_endpoint_is_captured(self):
        out = fetch_report_http(
            access_token="x", account="1", vendor="9", date="20260727",
            sales_url="http://127.0.0.1:9/nope", timeout=2)
        assert not out.ok and out.error

    def test_result_defaults_are_safe(self):
        result = ReporterResult(report_type=SHOW_REPORT, date="20260727")
        assert result.ok and result.rows == []


class TestReportTypeSpellings:
    """Apple's names are case-sensitive and a typo returns a bare
    'Invalid report type'. Verified against real successful downloads."""

    @pytest.mark.parametrize("name,expected", [
        (SHOW_REPORT, "apShowListening"),
        (SHOW_REPORT_WORLDWIDE, "apShowListeningWorldwide"),
    ])
    def test_exact_spelling(self, name, expected):
        assert name == expected
