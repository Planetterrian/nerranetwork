"""Drift guards for the July 2026 weekly-summary-segment restructure.

The full Sunday weekly-recap mode was retired: Sunday used to short-circuit
into a whole "week in review" episode (news fetch + daily digest skipped).
Now Sunday is a NORMAL daily episode that simply includes ONE short weekly-
summary segment. These guards pin the new contract:

  1. The daily-format validator now runs on Sunday runs (no ``is_weekly_recap``
     gate) — the Sunday digest IS a normal daily digest.
  2. The compact segment is appended to the PODCAST-ONLY digest copy
     (``clean_digest``), never to the published ``x_thread`` — so no
     host-instruction text leaks into the blog / RSS / newsletter.
  3. ``build_weekly_summary_segment`` grounds the host in the week's
     recurring threads and stays a SEGMENT, not a whole episode.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest


_ROOT = Path(__file__).resolve().parent.parent
_RUN_SHOW = _ROOT / "run_show.py"


def test_full_recap_mode_is_gone_from_run_show():
    """The retired full-recap machinery must not reappear: no
    ``is_weekly_recap`` short-circuit that skips the daily digest, and no
    ``build_weekly_recap_digest`` call. Sunday runs a normal daily digest."""
    source = _RUN_SHOW.read_text(encoding="utf-8")
    assert "build_weekly_recap_digest" not in source, (
        "run_show.py still calls the retired build_weekly_recap_digest — "
        "Sunday should generate a normal daily digest plus a segment."
    )
    # The daily validator must NOT be gated on a weekly-recap flag anymore.
    assert "not is_weekly_recap" not in source


def test_segment_appended_to_podcast_only_digest():
    """The segment must be appended to ``clean_digest`` (podcast-only), NOT to
    ``x_thread`` (the published digest) — otherwise host-instruction text would
    leak into the blog/RSS."""
    source = _RUN_SHOW.read_text(encoding="utf-8")
    assert "build_weekly_summary_segment" in source
    assert "clean_digest = clean_digest.rstrip()" in source
    assert 'metrics.record("weekly_summary_segment"' in source


def test_segment_stays_a_segment_not_an_episode():
    """The synthesised block must frame itself as a short segment layered onto
    a normal daily episode — today's news stays the main focus."""
    eps = [
        {"episode_num": 100, "date": "2026-05-04",
         "hook": "Lead story from earlier in the week.",
         "digest_md": "# Some Show\n\nBody one.\n\nBody two."},
        {"episode_num": 101, "date": "2026-05-05",
         "hook": "Second story from mid-week.",
         "digest_md": "# Some Show\n\nMid-week analysis."},
    ]
    from engine import weekly_recap
    with patch("engine.content_lake.query_show_range", return_value=eps):
        out = weekly_recap.build_weekly_summary_segment(
            "tesla", "Tesla Shorts Time", date(2026, 5, 10),
        )
    assert out is not None
    low = out.lower()
    assert "weekly summary segment" in low
    assert "week in review" in low
    assert "main focus" in low
    assert "segment, not the whole episode" in low
    # It must NOT recite a calendar date range or read URLs aloud.
    assert "2026-05-04 to 2026-05-10" not in out
    assert "never read urls aloud" in low
    # Both episode hooks feed the host's reference highlights.
    assert "Lead story from earlier in the week." in out
    assert "Second story from mid-week." in out


def test_segment_surfaces_recurring_threads():
    """Deterministic 'biggest events' signal: entities covered on 2+ days are
    surfaced to the host as the strongest segment candidates. Single-day
    entities are excluded."""
    eps = [
        {"episode_num": 1, "date": "2026-06-10", "hook": "h",
         "entities": ["Starship", "Artemis"], "digest_md": "# X\n\nb."},
        {"episode_num": 2, "date": "2026-06-11", "hook": "h",
         "entities": ["Starship", "NASA"], "digest_md": "# X\n\nb."},
        {"episode_num": 3, "date": "2026-06-12", "hook": "h",
         "entities": ["Starship", "NASA"], "digest_md": "# X\n\nb."},
    ]
    from engine import weekly_recap
    with patch("engine.content_lake.query_show_range", return_value=eps):
        out = weekly_recap.build_weekly_summary_segment("ff", "FF", date(2026, 6, 14))
    line = [ln for ln in out.splitlines() if "recurring threads" in ln.lower()]
    assert line, "recurring-threads grounding line missing"
    assert "Starship" in line[0] and "NASA" in line[0]  # 3x and 2x
    assert "Artemis" not in line[0]  # only 1x → excluded


def test_segment_returns_none_below_two_episodes():
    """One or zero episodes in the window → no segment (plain daily episode)."""
    from engine import weekly_recap
    with patch("engine.content_lake.query_show_range",
               return_value=[{"episode_num": 1, "date": "2026-05-01",
                              "hook": "solo", "digest_md": "b"}]):
        out = weekly_recap.build_weekly_summary_segment(
            "tesla", "Tesla Shorts Time", date(2026, 5, 3),
        )
    assert out is None


class TestSegmentIsRequiredLanguage:
    """Aug 27 2026: the segment instruction read as optional and the model
    ignored it on most Sundays (planetterrian: 5 of its last 6 —
    weekly_summary_segment_effective False while telemetry said appended).
    The block must state the segment is REQUIRED and demand an explicit
    week signpost in its first sentence."""

    def test_block_carries_required_and_signpost_language(self):
        import inspect
        from engine import weekly_recap
        src = inspect.getsource(weekly_recap.build_weekly_summary_segment)
        assert "REQUIRED" in src
        assert "incomplete" in src
        assert "Signpost" in src or "signpost" in src
