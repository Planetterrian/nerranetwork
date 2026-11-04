"""The email can be judged (Nov 3 2026).

On Nov 2 ``api/buttondown_stats.json`` read ``sends 0`` and Mission Control
showed NOTHING for the network's one email: the tile rendered only
``if (bd.configured && nd.sends)``. The register entry for the email carried no
metric, the dashboard computed none, the newsletter had no series at all
("the list grew by two" was read off a ledger note), and the per-email
analytics the nightly fetched were read by the tile alone. Now:

* ``scripts/fetch_buttondown_stats.py`` appends ONE row a night to
  ``api/buttondown_history.json`` (never rewriting an earlier date's row; a
  same-day re-run fills in only what it read) and owns the readers;
* the audience headline carries an ``email`` block and the daily line says it;
* four register metrics are live (``email_recipients_last``,
  ``email_open_rate_7d`` over the last seven SENDS' summed recipients with the
  30-recipient floor, ``email_click_sessions_28d``,
  ``email_subscribers_delta_7d``);
* the Mission Control tile is never hidden — a dash, never 0;
* the ``network`` review target's snapshot prints an Email line.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import scripts.fetch_buttondown_stats as F  # noqa: E402
from scripts import build_audience_headline as AH  # noqa: E402
from scripts import generate_dashboard as gd  # noqa: E402

TAGS = ["Tesla Shorts Time", "nerra-daily-weekly", "nerra-member", "personal-interest"]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _send(when: str, recipients=14, opens=6, clicks=2, unsubs=0, eid=None) -> dict:
    return {"id": eid or f"em_{when}", "kind": "nerra_daily", "publish_date": when,
            "recipients": recipients, "opens": opens, "clicks": clicks,
            "unsubscriptions": unsubs, "slug": f"nerra-daily-{when[:10]}"}


# ---------------------------------------------------------------------------
# 1. The nightly history: one row a night, earlier rows never rewritten
# ---------------------------------------------------------------------------

class TestTheNightlyHistory:
    def _run(self, monkeypatch, out: Path, *, count: int, emails):
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "key")
        monkeypatch.setattr(F, "fetch_subscriber_count", lambda key: count)
        monkeypatch.setattr(F, "fetch_tag_counts",
                            lambda key: {"nerra-member": 3, "Tesla Shorts Time": 2})
        monkeypatch.setattr(F, "count_tags_from_subscribers", lambda key: None)
        monkeypatch.setattr(F, "fetch_recent_emails", lambda key: emails)
        monkeypatch.setattr(F, "history_tags", lambda root=None: list(TAGS))
        assert F.main(["--out", str(out)]) == 0

    def test_two_runs_on_one_day_append_exactly_one_row_and_keep_the_earlier_ones(
            self, tmp_path, monkeypatch):
        out = tmp_path / "buttondown_stats.json"
        hist = tmp_path / F.HISTORY_NAME
        today = dt.datetime.now(dt.timezone.utc).date()
        earlier = [
            {"date": (today - dt.timedelta(days=d)).isoformat(), "subscriber_count": 10 + d,
             "tag_counts": None, "nerra_daily": None}
            for d in (9, 8, 1)
        ]
        hist.write_text(json.dumps({"rows": earlier}), encoding="utf-8")

        sends = [_send(f"{today.isoformat()}T12:00:00Z")]
        self._run(monkeypatch, out, count=14, emails=sends)
        self._run(monkeypatch, out, count=15, emails=None)   # same day, email read failed

        rows = json.loads(hist.read_text(encoding="utf-8"))["rows"]
        assert rows[:3] == earlier, "an earlier date's row was rewritten"
        todays = [r for r in rows if r["date"] == today.isoformat()]
        assert len(rows) == 4 and len(todays) == 1
        row = todays[0]
        assert row["subscriber_count"] == 15                     # the newer read wins
        assert row["nerra_daily"]["last_recipients"] == 14       # a refused read never blanks
        assert row["tag_counts"] == {"Tesla Shorts Time": 2, "nerra-daily-weekly": 0,
                                     "nerra-member": 3, "personal-interest": 0}

    def test_the_default_history_sits_beside_the_stats_file(self, tmp_path, monkeypatch):
        out = tmp_path / "nested" / "b.json"
        self._run(monkeypatch, out, count=14, emails=[])
        assert (out.parent / F.HISTORY_NAME).exists()

    def test_dry_run_writes_no_history(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "key")
        monkeypatch.setattr(F, "fetch_subscriber_count", lambda key: 14)
        monkeypatch.setattr(F, "fetch_tag_counts", lambda key: {})
        monkeypatch.setattr(F, "count_tags_from_subscribers", lambda key: None)
        monkeypatch.setattr(F, "fetch_recent_emails", lambda key: None)
        out = tmp_path / "b.json"
        assert F.main(["--out", str(out), "--dry-run"]) == 0
        assert not (tmp_path / F.HISTORY_NAME).exists()

    def test_a_refused_subscriber_read_writes_no_row(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "key")
        monkeypatch.setattr(F, "fetch_subscriber_count", lambda key: None)
        F.main(["--out", str(tmp_path / "b.json")])
        assert not (tmp_path / F.HISTORY_NAME).exists()

    def test_an_unreadable_history_is_left_alone(self, tmp_path):
        hist = tmp_path / F.HISTORY_NAME
        hist.write_text("{not json", encoding="utf-8")
        assert F.append_history(hist, {"date": "2026-11-03", "subscriber_count": 14}) is False
        assert hist.read_text(encoding="utf-8") == "{not json"

    def test_a_tag_is_zero_only_when_the_counts_were_read(self):
        read = F.history_row({"fetched_at": "2026-11-03T23:46:00+00:00", "subscriber_count": 14,
                              "tag_counts": {"nerra-member": 3}}, TAGS)
        assert read["date"] == "2026-11-03"
        assert read["tag_counts"]["nerra-daily-weekly"] == 0
        assert read["nerra_daily"] is None                       # emails unread: null
        empty = F.history_row({"fetched_at": "2026-11-03T23:46:00+00:00", "subscriber_count": 14,
                               "tag_counts": {}}, TAGS)
        assert empty["tag_counts"] is None                       # empty beside a list: unread
        warned = F.history_row({"fetched_at": "2026-11-03", "subscriber_count": 14,
                                "tag_counts": {"x": 1}, "attribution_warning": "…"}, TAGS)
        assert warned["tag_counts"] is None
        unread = F.history_row({"fetched_at": "2026-11-03", "subscriber_count": 14}, TAGS)
        assert unread["tag_counts"] is None

    def test_the_tag_list_covers_the_email_and_the_two_choices(self):
        from engine import nerra_daily_email as nde
        tags = F.history_tags(ROOT)
        for tag in (nde.MEMBER_TAG, nde.GALLERY_TAG, nde.PAID_TAG,
                    nde.WEEKLY_ONLY_TAG, "personal-interest"):
            assert tag in tags
        assert set(nde.email_show_tags(ROOT).values()) <= set(tags)

    def test_importing_the_fetcher_configures_no_logging(self):
        src = _read("scripts/fetch_buttondown_stats.py")
        assert src.index("logging.basicConfig") > src.index("def main(")


class TestSubscribersDelta:
    ROWS = [{"date": "2026-10-25", "subscriber_count": 12},
            {"date": "2026-10-27", "subscriber_count": 14},
            {"date": "2026-11-02", "subscriber_count": 15},
            {"date": "2026-11-03", "subscriber_count": 16}]

    def test_against_the_newest_row_a_week_older(self):
        assert F.subscribers_delta(self.ROWS, as_of=dt.date(2026, 11, 3)) == 2

    def test_null_never_zero_when_the_history_is_too_young_or_stale(self):
        assert F.subscribers_delta(self.ROWS[2:], as_of=dt.date(2026, 11, 3)) is None
        assert F.subscribers_delta(self.ROWS, as_of=dt.date(2026, 11, 20)) is None
        assert F.subscribers_delta([], as_of=dt.date(2026, 11, 3)) is None
        assert F.subscribers_delta(None, as_of=dt.date(2026, 11, 3)) is None


# ---------------------------------------------------------------------------
# 2. The audience headline carries the email
# ---------------------------------------------------------------------------

TODAY = dt.date(2026, 11, 3)


def _seed(root: Path, *, stats: dict | None = None, rows: list | None = None) -> Path:
    (root / "api").mkdir(parents=True, exist_ok=True)
    (root / "digests").mkdir(exist_ok=True)
    if stats is not None:
        (root / "api" / "buttondown_stats.json").write_text(json.dumps(stats), encoding="utf-8")
    if rows is not None:
        (root / "api" / F.HISTORY_NAME).write_text(json.dumps({"rows": rows}), encoding="utf-8")
    return root


def _fixture_stats() -> dict:
    fresh = _send("2026-11-03T12:00:00Z", recipients=14, opens=6, clicks=None, unsubs=None)
    old = _send("2026-10-24T12:00:00Z", recipients=12, opens=9, clicks=4, unsubs=1)
    return {"fetched_at": "2026-11-03T23:46:00+00:00", "subscriber_count": 16,
            "emails": [old, fresh, {"kind": "show", "recipients": 3, "opens": 3,
                                    "publish_date": "2026-11-03T13:00:00Z"}]}


class TestTheHeadlineCarriesTheEmail:
    def test_fixture_history_gives_the_delta_and_unread_fields_stay_null(self, tmp_path):
        root = _seed(tmp_path, stats=_fixture_stats(), rows=[
            {"date": "2026-10-26", "subscriber_count": 14},
            {"date": "2026-11-03", "subscriber_count": 16}])
        doc = AH.build_headline(root, today=TODAY)
        em = doc["network"]["email"]
        assert em == {"subscribers": 16, "subscribers_delta_7d": 2, "last_recipients": 14,
                      "sends_7d": 1, "opens_7d": 6, "clicks_7d": None,
                      "unsubscribes_7d": None}
        assert "email" in doc["definitions"]
        line = AH.headline_line(doc)
        assert "newsletter: 16 (+2 7d)" in line
        assert "email: last send 14 recipients, 7d 6 opens / — clicks / — unsubscribes" in line

    def test_nothing_read_is_null_everywhere_never_zero(self, tmp_path):
        doc = AH.build_headline(_seed(tmp_path), today=TODAY)
        em = doc["network"]["email"]
        assert all(v is None for v in em.values()), em
        assert "email: sends unread" in AH.headline_line(doc)

    def test_a_read_with_no_send_says_so(self, tmp_path):
        stats = {"fetched_at": "2026-11-03T23:46:00+00:00", "subscriber_count": 14, "emails": []}
        doc = AH.build_headline(_seed(tmp_path, stats=stats), today=TODAY)
        em = doc["network"]["email"]
        assert em["sends_7d"] == 0 and em["opens_7d"] is None and em["last_recipients"] is None
        assert "email: no send read in 7d" in AH.headline_line(doc)


# ---------------------------------------------------------------------------
# 3. The register metrics
# ---------------------------------------------------------------------------

KEYS = ("email_recipients_last", "email_open_rate_7d", "email_click_sessions_28d",
        "email_subscribers_delta_7d")


class TestTheRegisterMetrics:
    def _stats(self, per_send: int, n: int = 8) -> dict:
        sends = [_send(f"2026-10-{20 + i:02d}T12:00:00Z", recipients=per_send, opens=2)
                 for i in range(n)]
        return {"fetched_at": "2026-11-03T23:46:00+00:00", "subscriber_count": 16,
                "emails": sends}

    def test_the_rate_is_null_under_thirty_summed_recipients(self, tmp_path):
        m = gd._email_live_metrics(_seed(tmp_path, stats=self._stats(4)))
        assert m["email_open_rate_7d"] is None                   # 7 sends x 4 = 28
        assert m["email_recipients_last"] == 4

    def test_the_rate_is_over_the_last_seven_sends_summed(self, tmp_path):
        stats = self._stats(5)
        stats["emails"][0]["recipients"] = 500                   # the 8th-newest send: outside
        m = gd._email_live_metrics(_seed(tmp_path, stats=stats))
        assert m["email_open_rate_7d"] == round(14 / 35, 3)

    def test_a_send_with_unread_opens_is_left_out_of_both_sums(self):
        sends = [_send("2026-11-03T12:00:00Z", recipients=40, opens=None),
                 _send("2026-11-02T12:00:00Z", recipients=30, opens=12)]
        assert F.open_rate_last_sends(sends) == 0.4
        assert F.open_rate_last_sends(None) is None

    def test_clicks_come_from_the_funnel_and_unread_is_null(self, tmp_path):
        root = _seed(tmp_path, stats=self._stats(5))
        assert gd._email_live_metrics(root)["email_click_sessions_28d"] is None
        funnel = {"stages": {"click": {"configured": True, "email": {"sessions_28d": 0}}}}
        (root / "api" / "funnel.json").write_text(json.dumps(funnel), encoding="utf-8")
        assert gd._email_live_metrics(root)["email_click_sessions_28d"] == 0   # a measured zero
        funnel["stages"]["click"]["configured"] = False
        (root / "api" / "funnel.json").write_text(json.dumps(funnel), encoding="utf-8")
        assert gd._email_live_metrics(root)["email_click_sessions_28d"] is None

    def test_the_delta_is_anchored_on_the_read(self, tmp_path):
        root = _seed(tmp_path, stats=self._stats(5), rows=[
            {"date": "2026-10-27", "subscriber_count": 13},
            {"date": "2026-11-03", "subscriber_count": 16}])
        assert gd._email_live_metrics(root)["email_subscribers_delta_7d"] == 3
        assert gd.build_audience_section(root)["newsletter"]["subscribers_delta_7d"] == 3

    def test_nothing_read_is_null_for_all_four(self, tmp_path):
        m = gd._email_live_metrics(_seed(tmp_path))
        assert all(m[k] is None for k in KEYS), m

    def test_the_four_keys_are_live_metrics(self):
        computable = gd._experiment_live_metrics(ROOT)
        for k in KEYS:
            assert k in computable
            assert computable[k] is None or isinstance(computable[k], (int, float))


# ---------------------------------------------------------------------------
# 4. The tile is never hidden
# ---------------------------------------------------------------------------

class TestTheTileIsNeverHidden:
    def _tile(self) -> str:
        src = _read("management.html")
        start = src.index("// Nov 2026: the one network email.")
        return src[start:src.index('statTile("Image library"', start)]

    def test_no_condition_hides_the_tile(self):
        src = _read("management.html")
        assert "if (bd.configured && nd.sends)" not in src
        tile = self._tile()
        assert "if (" not in tile
        assert 'tiles.appendChild(statTile("Nerra Daily email"' in tile

    def test_every_number_is_a_dash_when_unread(self):
        tile = self._tile()
        assert "fmt(nd." not in tile
        for key in ("nd.last_recipients", "nd.opens", "nd.clicks", "nd.sends"):
            assert f"fmtOrDash({key})" in tile
        assert '"no send read yet"' in tile
        assert '"Buttondown not configured"' in tile

    def test_the_subscriber_delta_is_printed_with_a_dash(self):
        tile = self._tile()
        assert "bd.subscribers_delta_7d" in tile
        assert 'subsDelta == null ? "—"' in tile


# ---------------------------------------------------------------------------
# 5. The network review target's snapshot reads it
# ---------------------------------------------------------------------------

class TestTheNetworkSnapshot:
    def test_the_network_target_prints_an_email_line(self, tmp_path):
        from scripts import review_snapshot as RS
        root = _seed(tmp_path, stats=_fixture_stats(), rows=[
            {"date": "2026-10-26", "subscriber_count": 14},
            {"date": "2026-11-03", "subscriber_count": 16}])
        records = root / "digests" / "nerra_daily" / "email"
        records.mkdir(parents=True)
        (records / "2026-11-02.json").write_text(json.dumps({"date": "2026-11-02"}))
        (records / "2026-11-03.json").write_text(json.dumps({
            "date": "2026-11-03",
            "archive_url": "https://buttondown.com/nerranetwork/archive/nerra-daily-2026-11-03/"}))
        snap = RS.network_snapshot(root)
        line = [ln for ln in snap.splitlines() if ln.startswith("- Email (Nerra Daily):")]
        assert len(line) == 1
        assert "recipients" in line[0] and "opens" in line[0] and "clicks" in line[0]
        assert "subscribers 16" in line[0]
        assert "archive https://buttondown.com/nerranetwork/archive/nerra-daily-2026-11-03/" in line[0]

    def test_a_marker_without_an_archive_url_prints_a_dash(self):
        from scripts import review_snapshot as RS
        line = RS.email_line({}, {"date": "2026-11-02"})
        assert line.endswith("archive —") and "last send — recipients" in line

    def test_the_real_network_target_renders(self):
        from scripts import review_snapshot as RS
        snap = RS.build_snapshot("network")
        assert snap.startswith("# Review snapshot: network")
        assert "## Email" in snap and "- Email (Nerra Daily):" in snap

    def test_nerra_daily_is_not_invented_as_a_target(self):
        state = _read("docs/reviews/review_state.yaml")
        assert "\n  nerra_daily:" not in state

    def test_the_scheduled_network_review_reads_the_snapshot(self):
        import run_show_review as R
        context = R.gather_network_context()
        assert "## DETERMINISTIC SNAPSHOT" in context
        assert "- Email (Nerra Daily):" in context


# ---------------------------------------------------------------------------
# 6. The nightly commits the history
# ---------------------------------------------------------------------------

class TestTheNightlyCommitsTheHistory:
    def test_the_history_is_on_the_add_paths_whitelist(self):
        wf = _read(".github/workflows/nightly-maintenance.yml")
        assert "            api/buttondown_history.json\n" in wf.split("add-paths: |", 1)[1]

    def test_the_fetch_runs_before_the_headline_and_the_dashboard(self):
        wf = _read(".github/workflows/nightly-maintenance.yml")
        fetch = wf.index("python scripts/fetch_buttondown_stats.py")
        assert fetch < wf.index("python scripts/build_audience_headline.py")
        assert fetch < wf.index("python scripts/generate_dashboard.py --out")

    def test_the_contract_names_the_file(self):
        doc = _read("docs/analytics.md")
        assert "`api/buttondown_history.json`" in doc


@pytest.mark.parametrize("key", KEYS)
def test_each_key_is_named_in_the_dashboard_source(key):
    assert f'"{key}"' in _read("scripts/generate_dashboard.py")
