"""DP Pod goes weekly, and a segment that vanishes is caught by code.

**The cadence.** Operator-directed 2026-09-21: one episode every Monday,
was daily. The show was at 60 downloads/30d and 3 in its last complete week,
and three prompt passes had improved its copy without moving a listener, so
it trades volume for one episode worth showing up for.

A cadence lives in six places that must agree, and the interesting failure
is not the cron — it is everything downstream that still believes the old
one. The July-18 P0 was exactly this: ``review_episodes.py`` thought
env_intel ran on odd weekdays while production was Monday-only, so the audit
flagged a phantom missed episode every non-Monday AND dispatched an
off-schedule run through the retry path.

**The segment.** The Lever is absent from Ep066, Ep068, Ep072 and Ep073, and
present in all 37 digests before the 2026-09-04 lever pass. The prompt has
said "REQUIRED SECTIONS, in this order (never omit any)" throughout, which
is the point: this show's own history says an instruction the model breaks
gets fixed data-side. Two mechanical layers now catch it, and neither
touches a prompt — so neither is landmine #17.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def _cron_map() -> dict:
    """slug -> (cron, day_filter) parsed from the production workflow."""
    wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(
        encoding="utf-8")
    block = re.search(r"CRON_MAP = \{(.*?)\n              \}", wf, re.S).group(1)
    out = {}
    for m in re.finditer(
            r'"([^"]+)":\s*\("([a-z0-9_]+)",\s*(None|"[a-z_]+")\)', block):
        out[m.group(2)] = (m.group(1), m.group(3).strip('"').replace("None", ""))
    return out


class TestDpPodIsWeekly:
    def test_the_cron_fires_on_monday_and_the_filter_agrees(self):
        cron, day_filter = _cron_map()["dp_pod"]
        assert cron.endswith(" 1"), f"cron {cron!r} is not Monday-pinned"
        assert day_filter == "monday", (
            "the day-filter guard must also hold, so a GitHub cron that "
            "fires late on another day is dropped")

    def test_the_scheduler_worker_agrees(self):
        """The Worker dispatches to the minute; drift means two runs a week
        or none."""
        src = (ROOT / "workers" / "scheduler" / "src" / "index.ts").read_text(
            encoding="utf-8")
        row = re.search(r'\[\s*9,\s*46,\s*"dp_pod",\s*([^\]]+)\]', src)
        assert row, "dp_pod is not in the Worker SLOTS table"
        assert '"monday"' in row.group(1)

    def test_the_audit_believes_the_same_cadence(self):
        """The July-18 P0 shape: an audit that believes a stale cadence
        flags phantom missed episodes AND dispatches off-schedule runs."""
        import review_episodes

        assert review_episodes.SHOW_REGISTRY["dp_pod"]["schedule"] == "monday"

    def test_the_rss_freshness_limit_allows_a_full_week(self):
        """At the daily 96h limit a healthy weekly feed pages every week."""
        wf = (ROOT / ".github" / "workflows" / "daily-audit.yml").read_text(
            encoding="utf-8")
        m = re.search(r'"dp_pod_podcast\.rss":\s*\([^,]+,\s*(\d+)\)', wf)
        assert m, "dp_pod is not in the audit's RSS freshness map"
        assert int(m.group(1)) >= 192, (
            f"limit is {m.group(1)}h — under a week between episodes")

    def test_nerra_daily_stops_waiting_for_it_six_days_a_week(self):
        """The edition's ready gate waits on every EXPECTED show. Left out
        of ``monday_only`` it would hold the edition to the 12:00 force hour
        every Tuesday through Sunday, which is the UC gate-block shape."""
        from engine.daily_edition import EDITIONS

        spec = EDITIONS["en"]
        assert "dp_pod" in spec.monday_only
        assert "dp_pod" in spec.lineup, "it still closes the Monday edition"

    def test_it_is_alt_cadence_not_daily_in_the_schedule_tests(self):
        import tests.test_schedule as sched

        assert "dp_pod" in sched.ALT_CADENCE_SHOWS
        assert "dp_pod" not in sched.DAILY_SHOWS

    def test_it_does_not_carry_the_sunday_recap_flag(self):
        cfg = yaml.safe_load(
            (ROOT / "shows" / "dp_pod.yaml").read_text(encoding="utf-8"))
        assert cfg.get("weekly_summary_segment") is False


class TestNoSurfaceStillSaysDaily:
    """A listener reads the cadence off the show page and the feed.

    Asserted as a property over the strings a reader actually sees, not by
    pinning one phrase, so a rewording cannot make it pass while lying.
    """

    #: Shows whose cron carries a Monday day-filter, plus what their public
    #: strings must not claim.
    _DAILY_WORDS = ("daily", "every day", "each day", "ежедневн")

    def test_every_monday_only_show_says_so(self):
        import generate_html as G

        for slug, (_cron, day_filter) in _cron_map().items():
            if day_filter != "monday":
                continue
            schedule = G.NETWORK_SHOWS[slug]["schedule"].lower()
            assert "week" in schedule or "monday" in schedule, (
                f"{slug}: cron is Monday-only but the site says "
                f"{schedule!r} — the homepage card, show page and explore "
                "filter all read this string")

    def test_no_monday_only_feed_description_promises_a_daily_show(self):
        for slug, (_cron, day_filter) in _cron_map().items():
            if day_filter != "monday":
                continue
            path = ROOT / "shows" / f"{slug}.yaml"
            if not path.exists():
                continue
            cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
            text = str(cfg.get("publishing", {}).get("rss_description", "")
                       or "").lower()
            for word in self._DAILY_WORDS:
                assert word not in text, (
                    f"{slug}'s feed description says {word!r} but it "
                    "publishes on Mondays — this is the text Apple and "
                    "Spotify show")

    def test_a_show_with_no_day_filter_is_not_advertised_as_weekdays_only(self):
        """Unintended Consequences said "Weekdays" and published all seven."""
        import generate_html as G

        for slug, (_cron, day_filter) in _cron_map().items():
            if day_filter:
                continue
            schedule = G.NETWORK_SHOWS[slug]["schedule"].lower()
            assert "weekday" not in schedule and "week" not in schedule, (
                f"{slug}: the cron has no day-filter, so it runs all seven "
                f"days, but the site says {schedule!r}")


class TestAMissingSegmentIsStructural:
    def test_the_gate_acts_on_an_absent_section(self):
        """An EMPTY section spent the corrective regeneration; an ABSENT one
        sailed through. A section that is not there guts the podcast at
        least as thoroughly as one that is there and empty."""
        from run_show import _empty_mandatory_section_issues as gate

        assert gate(["Section 'The Lever' is missing from digest"])
        assert gate(["Section 'First Principles': 0 items (minimum 1)"])

    def test_a_soft_shortfall_is_still_not_structural(self):
        """Widening the gate must not make it fire on a formatting mismatch."""
        from run_show import _empty_mandatory_section_issues as gate

        assert gate(["Section 'Top 12 News Items' has only 8 items (minimum 10)"]) == []
        assert gate(["Section 'X': 3 items (maximum 2)"]) == []

    def test_dp_pod_has_a_validation_config_at_all(self):
        """It had none, which is why nothing noticed the show had stopped
        carrying one of its own segments."""
        from engine.validation import SHOW_VALIDATION_CONFIGS

        assert "dp_pod" in SHOW_VALIDATION_CONFIGS

    def test_the_spine_segments_are_all_mandatory(self):
        from engine.validation import SHOW_VALIDATION_CONFIGS

        names = {s.name for s in SHOW_VALIDATION_CONFIGS["dp_pod"]().sections}
        assert {"The Positive Papers", "Think Positive", "The Lever",
                "Do Positive Dispatch"} <= names

    @pytest.mark.parametrize("filename,missing", [
        ("DP_Pod_Ep072_20260919.md", {"The Lever"}),
        ("DP_Pod_Ep068_20260915.md", {"Think Positive", "The Lever"}),
    ])
    def test_it_finds_the_real_defects(self, filename, missing):
        """Scored against the episodes that actually shipped without them."""
        from engine.validation import SHOW_VALIDATION_CONFIGS, check_item_counts

        path = ROOT / "digests" / "dp_pod" / filename
        if not path.exists():
            pytest.skip(f"{filename} not committed")
        issues = check_item_counts(
            path.read_text(encoding="utf-8"),
            SHOW_VALIDATION_CONFIGS["dp_pod"]().sections)
        found = {re.search(r"Section '([^']+)'", i).group(1) for i in issues}
        assert found == missing

    def test_it_passes_a_healthy_episode(self):
        """A detector that fires on everything is not a detector."""
        from engine.validation import SHOW_VALIDATION_CONFIGS, check_item_counts

        digests = sorted((ROOT / "digests" / "dp_pod").glob("DP_Pod_Ep*.md"))
        healthy = [p for p in digests if "### The Lever" in
                   p.read_text(encoding="utf-8")]
        assert healthy, "no healthy DP Pod digest to check against"
        for path in healthy[-6:]:
            assert check_item_counts(
                path.read_text(encoding="utf-8"),
                SHOW_VALIDATION_CONFIGS["dp_pod"]().sections) == [], (
                f"{path.name} has every segment but was flagged")
