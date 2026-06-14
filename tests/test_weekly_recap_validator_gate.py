"""Drift guard for the May 10 2026 weekly-recap-overwrite bug.

Operator caught (Sunday May 10) six of seven recap-eligible shows
shipping daily-format episodes despite their metrics correctly
reporting ``weekly_recap_mode: True``. Root cause:

  1. ``run_show.py`` built the recap digest via ``build_weekly_recap_digest``.
  2. It then ran the daily-format validator
     (``engine.validation.validate_digest``) against the recap content.
  3. The daily validator rejected the recap because it expected
     daily-format sections like ``Top 10 News Items``,
     ``Tesla First Principles``, etc. — sections the recap shape
     doesn't carry.
  4. The retry path called ``generate_digest`` which fetched TODAY's
     news and wrote a daily digest, OVERWRITING the synthesised recap.
  5. The metric ``weekly_recap_mode: True`` stayed set from before
     the overwrite, so observability lied about what shipped.

Fix: gate the validator on ``not is_weekly_recap``. Recaps have
their own fixed shape (``This Week's Top Stories``) and shouldn't be
shape-checked by the daily validator.

This test pins the gate in ``run_show.py`` source. A future "let's
revalidate everything" refactor that drops the gate will trip this
test.
"""

from __future__ import annotations

from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parent.parent
_RUN_SHOW = _ROOT / "run_show.py"


def test_validator_block_gated_on_not_weekly_recap():
    """The daily-format validator must be skipped in recap mode.

    Without the gate, ``build_weekly_recap_digest`` output was being
    overwritten by ``generate_digest`` on Sundays — six of seven
    recap-eligible shows shipped daily content on May 10 2026.
    """
    source = _RUN_SHOW.read_text(encoding="utf-8")
    # The gate must reference both the validator factory AND the
    # ``is_weekly_recap`` flag so a daily-format check doesn't fire
    # on a recap digest. (May 2026: the gate also carries a trailing
    # ``and not is_deep_dive`` so standalone deep-dive episodes — which
    # have their own non-daily shape — skip the daily validator too. We
    # match the prefix so either tail is accepted.)
    assert "if _val_factory and not is_weekly_recap" in source, (
        "Daily-format validator block in run_show.py must be gated on "
        "``not is_weekly_recap``. Without the gate, recap digests get "
        "overwritten with daily content on Sundays. See May 10 2026 "
        "incident comment in run_show.py:7b."
    )


def test_recap_digest_has_recap_shape_not_daily():
    """The synthesised recap digest must have the ``Weekly Recap``
    title heading and ``This Week's Top Stories`` section — those
    are the markers the daily validator would flag as missing
    daily sections, which is why the gate is necessary."""
    from unittest.mock import patch
    from datetime import date
    from engine import weekly_recap

    fake_episodes = [
        {
            "episode_num": 100,
            "date": "2026-05-04",
            "hook": "Lead story from earlier in the week.",
            "digest_md": "# Some Show\n\nBody paragraph one.\n\nBody paragraph two.",
        },
        {
            "episode_num": 101,
            "date": "2026-05-05",
            "hook": "Second story from mid-week.",
            "digest_md": "# Some Show\n\nMid-week analysis.\n\nMore mid-week analysis.",
        },
    ]

    with patch("engine.content_lake.query_show_range", return_value=fake_episodes):
        out = weekly_recap.build_weekly_recap_digest(
            "tesla", "Tesla Shorts Time", date(2026, 5, 10),
        )

    assert out is not None
    # Recap-shaped header — distinct from daily.
    assert "— Weekly Recap" in out
    # Recap-shaped section — distinct from "Top 10 News Items".
    assert "This Week's Top Stories" in out
    # Hook is recap-flavoured but INTUITIVE — it must not recite the calendar
    # date range (operator feedback June 14 2026: the old "Looking back at N
    # episodes from <start> to <end>" read like a database query).
    assert "Looking back at" not in out
    assert "2026-05-04 to 2026-05-10" not in out
    assert "**HOOK:**" in out and "biggest developments" in out


def _build_sourced_recap():
    """Helper: build a recap from episodes that carry inline source citations
    plus a fresh-news article, mirroring the real daily-digest shape."""
    from unittest.mock import patch
    from datetime import date
    from engine import weekly_recap

    eps = [
        {"episode_num": 98, "date": "2026-06-11", "hook": "Ancient quasar",
         "digest_md": "# FF\n\n1. **Quasar**\n   Existed 12.9 Gyr ago. "
                      "Source: [space.com](https://www.space.com/quasar)"},
        {"episode_num": 99, "date": "2026-06-12", "hook": "Orbital data centers",
         "digest_md": "# FF\n\n1. **Orbital DCs**\n   Bright moving sources. "
                      "Source: [spacenews.com](https://spacenews.com/dc)"},
    ]
    arts = [{"title": "New exoplanet found", "url": "https://phys.org/exo",
             "source": "phys.org"}]
    with patch("engine.content_lake.query_show_range", return_value=eps):
        return weekly_recap.build_weekly_recap_digest(
            "fascinating_frontiers", "Fascinating Frontiers",
            date(2026, 6, 14), articles=arts,
        )


def test_recap_preserves_source_links_and_sources_section():
    """Transparent sourcing: the recap must keep markdown source citations and
    emit a '## Sources' block (June 14 2026 — the unsourced Sunday-blog fix).
    The prior behaviour collapsed links to dead text, so the blog/summary/RSS
    rendered no clickable sources. This guard blocks that regression."""
    out = _build_sourced_recap()
    # Inline citations preserved (not collapsed to plain text).
    assert "[space.com](https://www.space.com/quasar)" in out
    assert "[spacenews.com](https://spacenews.com/dc)" in out
    # A deduplicated Sources section exists as the final block.
    assert "## Sources" in out
    sources_block = out.split("## Sources", 1)[1]
    assert "https://www.space.com/quasar" in sources_block
    assert "https://spacenews.com/dc" in sources_block


def test_recap_surfaces_fresh_news_with_sources():
    """The weekly recap can break new ground: fresh, not-yet-covered news is
    surfaced (with its source link) instead of only rehashing the week."""
    out = _build_sourced_recap()
    assert "Fresh this week" in out
    assert "New exoplanet found" in out
    assert "https://phys.org/exo" in out  # carried into the Sources block too


def test_republished_recap_keeps_sources_without_scaffold_leak():
    """Mirror run_show.py's recap republish: header + clean spoken script +
    the scaffold's '## Sources' tail. The blog renders THIS, so the Sources
    must survive while the host-framing / narrative-memory scaffold must not."""
    scaffold = _build_sourced_recap()
    assert "## Sources" in scaffold
    sources_tail = "\n\n## Sources" + scaffold.split("## Sources", 1)[1].rstrip()
    published = "# Fascinating Frontiers — Weekly Recap\n\nClean narration, no urls." + sources_tail
    # Sources reach the published digest…
    assert "[space.com](https://www.space.com/quasar)" in published
    # …without leaking the host-only scaffold.
    assert "Recap framing for the host" not in published
    assert "GO DEEP ON THE BIGGEST EVENTS" not in published
    assert "NARRATIVE MEMORY" not in published


def test_run_show_republish_carries_sources_tail():
    """Pin the run_show.py republish step that lifts the Sources block onto the
    published recap digest — without it, the blog loses all source links."""
    source = _RUN_SHOW.read_text(encoding="utf-8")
    assert 'x_thread.split("## Sources", 1)' in source
    assert "_sources_tail" in source
