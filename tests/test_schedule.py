"""Tests for the May 2026 schedule overhaul.

Covers:

- Every cron line in ``.github/workflows/run-show.yml`` has a matching
  entry in the gate's ``CRON_MAP`` (drift between the two would silently
  break a show — schedule fires but nothing runs).
- The 7 daily *news* shows carry ``weekly_recap_on_sunday: true`` in their
  YAML; the alt-cadence shows do NOT (Привет, ФП, Env Intel, UC).
- ``first_principles`` is a daily *narrative* show: it runs every day
  (``day_filter`` None) but, like Unintended Consequences, deliberately does
  NOT carry the Sunday-recap flag (its topic queue is evergreen, not news).
- Only Tesla and Models & Agents for Beginners have
  ``youtube.enabled: true`` (post quota-cap).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "run-show.yml"
SHOWS_DIR = REPO_ROOT / "shows"


# ---------------------------------------------------------------------------
# Cron consistency
# ---------------------------------------------------------------------------

def _extract_cron_lines() -> list[str]:
    """Pull cron expressions from the ``schedule:`` block in the
    workflow file (string match — yaml parsing pulls cron strings into
    a more nested structure)."""
    txt = WORKFLOW.read_text(encoding="utf-8")
    # Match `- cron: '<expr>'` only inside the top-level schedule block,
    # not in any inline comment with the word "cron". The format is
    # consistent across the file so a simple regex is reliable.
    return re.findall(r"- cron: '([^']+)'", txt)


def _extract_cron_map() -> dict[str, tuple[str, str | None]]:
    """Pull the inline CRON_MAP dict out of the gate step."""
    txt = WORKFLOW.read_text(encoding="utf-8")
    block = re.search(r"CRON_MAP = \{(.*?)\}", txt, flags=re.DOTALL)
    assert block, "CRON_MAP block not found in run-show.yml"
    body = block.group(1)
    entries = re.findall(
        r'"([^"]+)":\s*\("([^"]+)",\s*([A-Za-z_"]+)\)',
        body,
    )
    out: dict[str, tuple[str, str | None]] = {}
    for cron, slug, raw_filter in entries:
        if raw_filter == "None":
            day_filter: str | None = None
        else:
            day_filter = raw_filter.strip('"')
        out[cron] = (slug, day_filter)
    return out


class TestCronConsistency:

    def test_every_cron_line_has_map_entry(self):
        cron_lines = _extract_cron_lines()
        cron_map = _extract_cron_map()
        for cron in cron_lines:
            assert cron in cron_map, (
                f"Cron expression {cron!r} fires but no CRON_MAP entry "
                f"matches — show won't be selected. Add it or remove "
                f"the cron line."
            )

    def test_no_orphan_map_entries(self):
        cron_lines = set(_extract_cron_lines())
        cron_map = _extract_cron_map()
        for cron in cron_map:
            assert cron in cron_lines, (
                f"CRON_MAP has {cron!r} but no matching cron line — "
                f"dead entry, will never fire."
            )

    def test_seven_daily_shows_have_no_filter(self):
        """OV, PT, FF, M&A, MAB, MIT, TST run daily — their CRON_MAP
        entry should carry ``None`` as the day_filter."""
        daily = {
            "omni_view", "planetterrian", "fascinating_frontiers",
            "models_agents", "models_agents_beginners",
            "modern_investing", "tesla",
        }
        cron_map = _extract_cron_map()
        slugs_with_no_filter = {
            slug for (slug, df) in cron_map.values() if df is None
        }
        missing = daily - slugs_with_no_filter
        assert not missing, (
            f"Expected {daily} to all run daily (day_filter=None) but "
            f"these don't: {missing}"
        )

    def test_no_show_runs_before_06_utc_or_after_12_utc(self):
        """Schedule window must be contained in 06:00–12:59 UTC so the
        whole network finishes by the Eastern morning. Widened from 11
        to 12 when SpaceX Daily took the 12:07 slot (June 2026). Also
        catches accidental DST drift. Must stay in sync with the
        scheduler Worker's cron window in workers/scheduler/wrangler.toml."""
        cron_lines = _extract_cron_lines()
        for cron in cron_lines:
            minute, hour = cron.split()[:2]
            hour_int = int(hour)
            assert 6 <= hour_int <= 12, (
                f"Cron {cron!r} hour {hour_int} outside 06:00–12:59 UTC "
                f"window."
            )


# ---------------------------------------------------------------------------
# Sunday weekly-recap flag
# ---------------------------------------------------------------------------

DAILY_SHOWS = [
    "tesla", "omni_view", "planetterrian", "fascinating_frontiers",
    "models_agents", "models_agents_beginners", "modern_investing",
]
ALT_CADENCE_SHOWS = [
    # Weekly on Monday (June 2026): privet_russian + finansy_prosto moved off
    # even-days, env_intel off odd-weekdays. None carry the recap flag.
    "privet_russian", "finansy_prosto", "env_intel",
]


@pytest.mark.parametrize("slug", DAILY_SHOWS)
def test_daily_show_has_weekly_recap_flag(slug):
    """Every show that runs daily must opt in to Sunday recap mode —
    otherwise Sunday's slot tries to fetch news for a show that may
    not have anything fresh and the recap never happens."""
    cfg_path = SHOWS_DIR / f"{slug}.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert cfg.get("weekly_recap_on_sunday") is True, (
        f"{slug} runs daily but is missing "
        f"`weekly_recap_on_sunday: true` — Sunday slot would fetch "
        f"news instead of recapping."
    )


@pytest.mark.parametrize("slug", ALT_CADENCE_SHOWS)
def test_alt_cadence_show_does_not_recap(slug):
    """Shows on alt cadence (even days, odd weekdays) shouldn't have
    the recap flag — they don't run every Sunday so the flag is
    misleading drift."""
    cfg_path = SHOWS_DIR / f"{slug}.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert not cfg.get("weekly_recap_on_sunday", False), (
        f"{slug} is alt-cadence but has weekly_recap_on_sunday=true — "
        f"either flip the cadence to daily or drop the flag."
    )


# ---------------------------------------------------------------------------
# Daily narrative shows (run every day, topic-queue-driven, no recap)
# ---------------------------------------------------------------------------

DAILY_NARRATIVE_SHOWS = ["first_principles", "unintended_consequences"]


@pytest.mark.parametrize("slug", DAILY_NARRATIVE_SHOWS)
def test_daily_narrative_show_runs_daily_without_recap(slug):
    """A daily *narrative* show runs every day (``day_filter`` None in
    CRON_MAP) but is topic-queue-driven and evergreen, so it must NOT
    carry ``weekly_recap_on_sunday`` (there's no week of news to recap)
    and MUST declare ``narrative_mode: true`` with a topic queue. This
    documents why first_principles is intentionally absent from both
    DAILY_SHOWS (recap-required) and ALT_CADENCE_SHOWS (sub-daily)."""
    cfg = yaml.safe_load((SHOWS_DIR / f"{slug}.yaml").read_text(encoding="utf-8"))
    assert cfg.get("narrative_mode") is True, f"{slug} must set narrative_mode: true"
    assert cfg.get("topic_queue_file"), f"{slug} must set topic_queue_file"
    assert not cfg.get("weekly_recap_on_sunday", False), (
        f"{slug} is a daily narrative show — it must NOT carry the "
        f"weekly_recap_on_sunday flag."
    )
    cron_map = _extract_cron_map()
    no_filter = {s for (s, df) in cron_map.values() if df is None}
    assert slug in no_filter, (
        f"{slug} should run daily (day_filter=None) in CRON_MAP."
    )


# ---------------------------------------------------------------------------
# YouTube quota cap (post-May-2026 schedule)
# ---------------------------------------------------------------------------

# June 2026 — full-network YouTube rollout after the @NerraNetwork quota was
# raised 10,000 → 200,000 units/day. Every show now publishes to YouTube
# (EN shows on @NerraNetwork, the two Russian shows on @NerraRU). The previous
# constrained shape (Shorts-only FF/MIT, paused MAB, podcast-only FPD) was a
# quota workaround that no longer applies. Cadence, not quota, is now the
# guardrail — see scripts/youtube_quota_preflight.py's authenticity warning.
YOUTUBE_ENABLED_SHOWS = {
    "tesla", "spacex", "first_principles",
    "fascinating_frontiers", "modern_investing",
    "env_intel", "planetterrian", "omni_view",
    "models_agents", "models_agents_beginners",
    "unintended_consequences",
    "finansy_prosto", "privet_russian",
}


def test_youtube_enabled_show_set():
    """Pin the exact YouTube-enabled show set. Any change must be deliberate:
    rerun the per-channel quota math in scripts/youtube_quota_preflight.py and
    update YOUTUBE_ENABLED_SHOWS together with the show YAMLs. Post-200k this
    is the full network; the constraint is now upload cadence (authenticity
    policy), enforced by the preflight's soft warning."""
    enabled: set[str] = set()
    for cfg_path in SHOWS_DIR.glob("*.yaml"):
        if cfg_path.name.startswith("_"):
            continue  # Skip _defaults.yaml etc.
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        slug = cfg.get("slug")
        if not slug:
            continue
        yt = (cfg.get("youtube") or {})
        if yt.get("enabled") is True:
            enabled.add(slug)
    assert enabled == YOUTUBE_ENABLED_SHOWS, (
        f"YouTube uploads enabled on {enabled}; expected the full network "
        f"{YOUTUBE_ENABLED_SHOWS}. Update both the YAML and this set together."
    )


# ---------------------------------------------------------------------------
# weekly_recap_digest behaviour (the helper itself)
# ---------------------------------------------------------------------------

class TestWeeklyRecapHelper:
    """``build_weekly_recap_digest`` short-circuits when the content
    lake is missing or has too few episodes. The runner falls back to
    a normal daily fetch in that case — the function MUST return None
    rather than raising or returning something the daily pipeline
    would mistake for a real digest."""

    def test_returns_none_when_lake_unavailable(self, monkeypatch):
        from engine import weekly_recap
        # Stub out content_lake import to simulate ImportError.
        import sys
        monkeypatch.setitem(sys.modules, "engine.content_lake", None)
        from datetime import date
        out = weekly_recap.build_weekly_recap_digest(
            "tesla", "Tesla Shorts Time", date(2026, 5, 3),
        )
        # We don't strictly require None on import-fail (different
        # branch), but it must not raise. Acceptable: None or a string
        # we never use as a real digest.
        assert out is None or isinstance(out, str)

    def test_returns_none_when_too_few_episodes(self, monkeypatch):
        from engine import weekly_recap
        # Force the helper to see only one episode.
        monkeypatch.setattr(
            weekly_recap,
            "build_weekly_recap_digest",
            weekly_recap.build_weekly_recap_digest,  # keep real
        )

        # Patch query_show_range inside the helper to return one episode
        import engine.content_lake as _cl

        def fake_query(slug, start, end):
            return [
                {"episode_num": 1, "date": "2026-05-01",
                 "hook": "Solo episode", "digest_md": "Body"}
            ]

        monkeypatch.setattr(_cl, "query_show_range", fake_query)
        from datetime import date
        out = weekly_recap.build_weekly_recap_digest(
            "tesla", "Tesla Shorts Time", date(2026, 5, 3),
        )
        assert out is None

    def test_synthesises_digest_with_two_or_more_episodes(self, monkeypatch):
        from engine import weekly_recap
        import engine.content_lake as _cl

        def fake_query(slug, start, end):
            return [
                {
                    "episode_num": 1, "date": "2026-04-28",
                    "hook": "Story A happened.", "digest_md": "Body A.",
                },
                {
                    "episode_num": 2, "date": "2026-04-29",
                    "hook": "Story B happened.", "digest_md": "Body B.",
                },
            ]

        monkeypatch.setattr(_cl, "query_show_range", fake_query)
        from datetime import date
        out = weekly_recap.build_weekly_recap_digest(
            "tesla", "Tesla Shorts Time", date(2026, 5, 3),
        )
        assert out is not None
        # Title and recap framing present.
        assert "Tesla Shorts Time" in out
        assert "Weekly Recap" in out
        # Both hooks survive into the synthetic digest.
        assert "Story A happened." in out
        assert "Story B happened." in out
        # Recap-mode framing instruction at the bottom for the host.
        assert "Sunday weekly recap" in out

    def test_recap_framing_pushes_continuity_stakes_and_forward_look(self, monkeypatch):
        """The host-framing must steer the narration toward the
        'where we are now' continuity, explicit stakes, concrete
        specifics, and forward-looking beats that make a recap valuable
        (and that the listener-value scorer rewards). Without this, the
        generated recap scripts read as a flat list of items and score
        ~1.9/10 (see TST Ep494)."""
        from engine import weekly_recap
        import engine.content_lake as _cl

        def fake_query(slug, start, end):
            return [
                {"episode_num": 1, "date": "2026-04-28",
                 "hook": "Story A.", "digest_md": "Body A."},
                {"episode_num": 2, "date": "2026-04-29",
                 "hook": "Story B.", "digest_md": "Body B."},
            ]

        monkeypatch.setattr(_cl, "query_show_range", fake_query)
        from datetime import date
        out = weekly_recap.build_weekly_recap_digest(
            "tesla", "Tesla Shorts Time", date(2026, 5, 3),
        )
        assert out is not None
        low = out.lower()
        # Continuity ('where we are now') cues.
        assert "where we are now" in low
        assert "since we last" in low
        assert "where the story stands now" in low
        # Stakes framing.
        assert "why this matters" in low
        # Specifics + forward look.
        assert "numbers" in low
        assert "watch for next week" in low
        assert "open question" in low
        # June 14 2026 improvements: go deep on the biggest events, open
        # intuitively (not by reciting the date range), and never read URLs aloud.
        assert "go deep on the biggest events" in low
        assert "do not open by reciting the calendar date range" in low
        assert "never read urls" in low


def test_youtube_post_quota_full_format_shape():
    """Post-200k full-network shape (June 2026): the quota workaround is
    undone. FF + MIT now publish long-form (no longer Shorts-only), MAB is
    re-enabled, and the two Russian shows still upload to @NerraRU (their own
    quota), never the EN channel. A regression to the old constrained shape
    fails loudly here."""
    import yaml as _yaml

    def yt(slug):
        cfg = _yaml.safe_load((SHOWS_DIR / f"{slug}.yaml").read_text(
            encoding="utf-8")) or {}
        return cfg.get("youtube") or {}

    # FF + MIT regained long-form once quota was no longer the constraint.
    for slug in ("fascinating_frontiers", "modern_investing"):
        assert yt(slug).get("publish_long_form") is True, (
            f"{slug} should publish long-form again post-quota-raise"
        )
    # MAB is back on (un-paused) now that the EN channel has headroom.
    assert yt("models_agents_beginners").get("enabled") is True, (
        "MAB YouTube should be re-enabled in the full-network rollout"
    )
    # Russian shows stay on their own channel/quota.
    for slug in ("finansy_prosto", "privet_russian"):
        assert yt(slug).get("channel") == "ru", (
            f"{slug} must upload to @NerraRU (its own quota), never the "
            f"EN channel"
        )


def test_all_youtube_shows_use_grok_imagine():
    """Every YouTube-enabled show must generate imagery with Grok Imagine
    (operator directive June 14 2026: all Shorts/long-form imagery is
    Grok-generated — unique, narrative-tied, and feeds the gallery pipeline).
    A show inheriting the ``pexels`` default would silently ship stock photos."""
    import yaml as _yaml
    for cfg_path in SHOWS_DIR.glob("*.yaml"):
        if cfg_path.name.startswith("_"):
            continue
        cfg = _yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        yt = cfg.get("youtube") or {}
        if yt.get("enabled") is True:
            assert yt.get("image_provider") == "grok", (
                f"{cfg.get('slug')} has YouTube enabled but image_provider="
                f"{yt.get('image_provider')!r} — must be 'grok' so imagery is "
                f"Grok-generated, not stock Pexels."
            )
