#!/usr/bin/env python3
"""Compute the adaptive YouTube publishing policy from real analytics.

Third layer of the recursive YouTube-feedback loop (after the title hints in
``scripts/update_youtube_performance.py``): reads the per-video analytics in
``api/youtube_stats.json`` and the PREVIOUS ``api/youtube_policy.json``
(hysteresis state), and writes a fresh ``api/youtube_policy.json`` with a
per-show x per-channel publish tier. Consumers
(``run_show._publish_youtube``, ``engine.ru_dub``) read the committed file
via ``engine.youtube_policy.resolve_publish_plan``.

Why velocity, not raw views: a single nightly snapshot can't diff views over
time, but ``views / days_since_publish`` (vpd) age-normalizes the snapshot so
a 3-day-old video with 30 views and a 10-day-old video with 100 views score
the same. Averaged over the trailing 14 days per show x channel x kind.

Tier rules (identical on both channels, each decided from ITS OWN data):
  - long-form on when ``long_vpd >= 1.0``
  - Shorts: ``short_vpd >= 4.0`` -> 2/episode, else 1. NEVER 0 — Shorts are
    the cheapest probe and the only recovery signal for a gated show.
  - Labels: A = long + 2 Shorts, B = long + 1, C = shorts-only,
    D = probe (shorts-only AND short_vpd < 0.5; same settings as C).

Hysteresis: the ACTIVE tier only flips after the same computed tier shows up
on 2 consecutive nightly runs — one viral Short (or one dead day) can't
whipsaw the publish shape. A kind with < 4 in-window videos is an
insufficient reading and HOLDS that dimension of the active tier (a
shorts-only show has no long-form data — that's not evidence its long-form
got worse).

Best-effort by contract: a missing stats file or unreadable previous policy
keeps the seeds and exits 0 (loud log, never a red nightly). The policy
never edits show YAMLs — ``youtube.adaptive_publishing: false`` pins a show
to YAML behavior regardless of what this file says.

Usage::

    python scripts/update_youtube_policy.py [--stats api/youtube_stats.json]
        [--out api/youtube_policy.json]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("update_youtube_policy")

# ---- Tunables -------------------------------------------------------------
WINDOW_DAYS = 14            # velocity window (days before the stats snapshot)
MIN_VIDEOS_CONFIDENT = 4    # per kind — below this, hold the active setting
# July 18 2026 (operator decision): the long-form floor is CHANNEL-specific.
# RU long-form earned 435 views across 68 videos (~9% retention) while RU
# Shorts carried 7,028 — an RU long_vpd of ~1.2 is noise, not
# product-market fit, so the RU channel must clear a higher bar to spend a
# daily long-form render. The MECHANISM (velocity + hysteresis + Monday
# probe) stays identical on both channels, so a show can always re-earn
# long-form through the weekly probe data.
LONG_VPD_FLOOR: Dict[str, float] = {"en": 1.0, "ru": 2.0, "fr": 2.0}
SHORT_VPD_PROBE = 0.5       # below this, shorts-only reads as "probe" (D)
STREAK_TO_FLIP = 2          # consecutive identical computed tiers to flip
# Stats older than this freeze the policy (loud ::warning::) instead of
# recomputing tiers from a frozen 14-day cohort every night.
STATS_MAX_AGE_DAYS = 3

# Shorts supply ladder: (min avg views/day, Shorts per episode), highest
# matching band wins. Below the lowest band, one Short — Shorts are NEVER
# zero, they are the recovery signal a cold show earns its way back with.
#
# July 30 2026: added the 3-Short band. Until then the ladder topped out
# at 2, so demonstrated demand spanning 13x got identical supply — RU
# spacex at 62.3 vpd and RU fascinating_frontiers at 60.5 were allotted
# the same two Shorts as RU modern_investing at 4.9 and EN
# fascinating_frontiers at 4.6. The threshold sits at 20 because the
# measured distribution has a clean gap there (a 4.6-8.0 cluster, then
# 23.6, then 60-62), so the new band selects exactly the shows whose
# demand is an order of magnitude past the 2-Short bar rather than
# splitting a crowded region.
#
# Deliberately stopping at 3, not 4: each additional Short comes from the
# next-best window the smart selector found, so the marginal clip is by
# construction weaker than the one before it. 3 is what the data
# supports; a 4th would be extrapolation. Headroom is not the limit —
# the RU channel runs ~7-8 uploads/day against the 30/day cadence
# ceiling (SAFE_DAILY_UPLOADS_PER_CHANNEL) and ~13k of 200k quota units,
# so this adds ~3 uploads/day to a channel with room for 20 more.
SHORT_VPD_BANDS: Tuple[Tuple[float, int], ...] = (
    (20.0, 3),
    (4.0, 2),
)
# Retained name for the 2-Short threshold — referenced by the drift
# guards and by docs/youtube_feedback_loop.md.
SHORT_VPD_TWO = 4.0


def shorts_for_vpd(short_vpd: float) -> int:
    """Shorts per episode earned by a measured views-per-day figure."""
    for floor, count in SHORT_VPD_BANDS:
        if short_vpd >= floor:
            return count
    return 1

# Tier label -> (publish_long_form, shorts_per_episode). C and D share
# settings — D is a reporting label ("shorts-only AND the shorts are cold").
TIER_SETTINGS: Dict[str, Tuple[bool, int]] = {
    "A": (True, 2),
    "B": (True, 1),
    "C": (False, 1),
    "D": (False, 1),
}

# Cold-start ACTIVE tiers, derived from the live api/youtube_stats.json on
# 2026-07-14 (14-day vpd per show x channel x kind at that date). RU longs
# are off everywhere: across the whole window RU long-form earned 59 views
# over 11 spacex longs while RU Shorts earned 2,513. dp_pod has no YouTube
# and is deliberately absent; a slug absent from the policy file resolves to
# legacy YAML behavior.
SEED_DATE = "2026-07-14"
SEED_TIERS: Dict[str, Dict[str, str]] = {
    "en": {
        "tesla": "A",
        "spacex": "A",
        "fascinating_frontiers": "A",
        "models_agents": "B",
        "models_agents_beginners": "B",
        "unintended_consequences": "B",
        "omni_view": "C",
        "planetterrian": "C",
        "env_intel": "C",
        "first_principles": "C",
        "modern_investing": "D",
    },
    "ru": {
        "tesla": "C",
        "spacex": "C",
        "fascinating_frontiers": "C",
        "modern_investing": "C",
        "finansy_prosto": "C",
        "privet_russian": "C",
    },
    # July 18 2026 — @NerraFR launch (engine.lang_dub). Seeded shorts-only
    # per the RU lesson (dubbed long-form earned ~9% retention while Shorts
    # carried the views); the Monday probe + velocity data let long-form
    # earn its way in. Same 2.0 long_vpd floor as RU (LONG_VPD_FLOOR).
    "fr": {
        "tesla": "C",
        "spacex": "C",
        "fascinating_frontiers": "C",
        "modern_investing": "C",
    },
}


def _parse_date(value: str) -> Optional[_dt.date]:
    try:
        return _dt.date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def collect_velocities(stats: dict) -> Dict[Tuple[str, str, str], List[float]]:
    """Per (slug, channel, kind): views-per-day for each in-window video.

    ``vpd = views / max(1, days_since_publish)`` where days are relative to
    the stats file's ``generated`` timestamp (the snapshot's own clock, so a
    stale stats file doesn't misread every video as older than it was
    measured). Only videos published within the trailing WINDOW_DAYS count.
    """
    generated = _parse_date(str(stats.get("generated") or ""))
    if generated is None:
        generated = _dt.datetime.now(_dt.timezone.utc).date()
    out: Dict[Tuple[str, str, str], List[float]] = {}
    for payload in (stats.get("shows") or {}).values():
        for v in (payload or {}).get("videos") or []:
            slug = v.get("show_slug") or ""
            kind = v.get("kind") or ""
            channel = (v.get("channel") or "en").lower()
            published = _parse_date(str(v.get("published") or ""))
            if not slug or kind not in ("long", "short") or published is None:
                continue
            days = (generated - published).days
            if days < 0 or days > WINDOW_DAYS:
                continue
            vpd = float(v.get("views") or 0) / max(1, days)
            out.setdefault((slug, channel, kind), []).append(vpd)
    return out


def _avg(values: List[float]) -> float:
    return sum(values) / len(values)


def compute_tier(
    long_vpds: List[float],
    short_vpds: List[float],
    active_tier: str,
    channel: str = "en",
) -> Tuple[str, Optional[float], Optional[float], str]:
    """Computed tier for one show x channel, holding insufficient dimensions.

    Returns ``(tier, long_vpd, short_vpd, reason)`` where a vpd is ``None``
    when that kind had fewer than MIN_VIDEOS_CONFIDENT in-window videos (the
    dimension then holds whatever the ACTIVE tier already says — no data is
    not evidence of decline, and a shorts-only show structurally has no
    long-form data).
    """
    active_long, active_shorts = TIER_SETTINGS.get(active_tier, (False, 1))
    long_floor = LONG_VPD_FLOOR.get((channel or "en").lower(),
                                    LONG_VPD_FLOOR["en"])

    long_vpd = _avg(long_vpds) if len(long_vpds) >= MIN_VIDEOS_CONFIDENT else None
    short_vpd = _avg(short_vpds) if len(short_vpds) >= MIN_VIDEOS_CONFIDENT else None

    publish_long = (long_vpd >= long_floor) if long_vpd is not None else active_long
    shorts = (shorts_for_vpd(short_vpd)
              if short_vpd is not None else active_shorts)

    reasons: List[str] = []
    if long_vpd is None:
        reasons.append(f"long held ({len(long_vpds)} videos < "
                       f"{MIN_VIDEOS_CONFIDENT} in {WINDOW_DAYS}d)")
    else:
        reasons.append(f"long_vpd {long_vpd:.2f} "
                       f"{'>=' if publish_long else '<'} {long_floor}")
    if short_vpd is None:
        reasons.append(f"shorts held ({len(short_vpds)} videos < "
                       f"{MIN_VIDEOS_CONFIDENT} in {WINDOW_DAYS}d)")
    else:
        reasons.append(f"short_vpd {short_vpd:.2f} -> {shorts} Short(s)")

    if publish_long:
        tier = "A" if shorts >= 2 else "B"
    elif short_vpd is not None and short_vpd < SHORT_VPD_PROBE:
        tier = "D"
    else:
        tier = "C"
    reason = f"computed {tier}: " + "; ".join(reasons) + "."
    return tier, long_vpd, short_vpd, reason


def advance_hysteresis(
    prev_entry: Optional[dict],
    computed: str,
    seed: str,
) -> Tuple[str, Optional[str], int]:
    """Advance the {active, pending, streak} state machine by one run.

    The ACTIVE tier flips only after the same computed tier appears on
    STREAK_TO_FLIP consecutive runs. First run (no previous entry): active
    starts at the seed and the computed tier begins its streak as pending.
    """
    if not isinstance(prev_entry, dict):
        active = seed
        if computed == active:
            return active, None, 0
        return active, computed, 1

    active = str(prev_entry.get("tier") or seed)
    if active not in TIER_SETTINGS:
        active = seed
    if computed == active:
        return active, None, 0
    prev_pending = prev_entry.get("pending")
    try:
        prev_streak = int(prev_entry.get("streak") or 0)
    except (TypeError, ValueError):
        prev_streak = 0
    streak = prev_streak + 1 if computed == prev_pending else 1
    if streak >= STREAK_TO_FLIP:
        return computed, None, 0
    return active, computed, streak


def build_policy(
    stats: Optional[dict],
    previous: Optional[dict],
    *,
    now_iso: Optional[str] = None,
) -> dict:
    """Compose the full policy document (pure — no I/O)."""
    velocities = collect_velocities(stats) if stats else {}
    prev_channels = (previous or {}).get("channels") or {}

    channels: Dict[str, Dict[str, dict]] = {}
    for channel, seeds in SEED_TIERS.items():
        prev_ch = prev_channels.get(channel) or {}
        # Seeds + anything the previous policy tracked (a slug removed from
        # the seeds keeps its earned state); stats-only slugs are NOT auto-
        # enrolled — absent slugs mean legacy YAML behavior by contract.
        slugs = sorted(set(seeds) | set(prev_ch))
        channels[channel] = {}
        for slug in slugs:
            seed = seeds.get(slug, "C")
            prev_entry = prev_ch.get(slug)
            long_vpds = velocities.get((slug, channel, "long"), [])
            short_vpds = velocities.get((slug, channel, "short"), [])
            if stats:
                active_for_hold = (
                    str(prev_entry.get("tier")) if isinstance(prev_entry, dict)
                    and prev_entry.get("tier") in TIER_SETTINGS else seed
                )
                computed, long_vpd, short_vpd, reason = compute_tier(
                    long_vpds, short_vpds, active_for_hold, channel)
            else:
                computed, long_vpd, short_vpd = seed, None, None
                reason = "no stats data — holding seed tier."
            active, pending, streak = advance_hysteresis(
                prev_entry, computed, seed)
            publish_long, shorts = TIER_SETTINGS[active]
            # July 22 2026: the Shorts COUNT follows the data, not the tier
            # letter. The 4-letter taxonomy pinned shorts-only (C) shows to
            # 1 Short via TIER_SETTINGS, silently discarding the computed
            # "-> 2 Short(s)" — RU spacex/tesla/FF sat at short_vpd 18-45
            # (the network's hottest surface) while shipping half the
            # allowed Shorts. The 14-day vpd average is already smoothed,
            # and a 1<->2 flip is cheap, so no extra hysteresis; a
            # data-thin dimension still holds the active tier's count.
            #
            # July 30 2026: this branch carried its OWN copy of the
            # threshold rule, so ``compute_tier`` logging "-> 3 Short(s)"
            # and the file recording 2 was possible — and was exactly what
            # happened on the first run after the 3-Short band landed.
            # Both now call ``shorts_for_vpd``, so the ladder is defined
            # once.
            if short_vpd is not None:
                shorts = shorts_for_vpd(short_vpd)
            # Asymmetric hysteresis on the COUNT (Aug 2026): the July 30
            # ladder added a 20 vpd -> 3 band, and a show oscillating
            # around a band edge toggled 2<->3 nightly — render cost,
            # upload cadence, and the marginal window's quality all
            # flapping with it. RAISING the count now needs the same
            # computed value on 2 consecutive runs (own pending/streak
            # pair, mirroring the tier state machine); LOWERING applies
            # immediately, matching resolve_publish_plan's rule that
            # cutting supply is always allowed.
            prev_shorts = None
            if isinstance(prev_entry, dict):
                try:
                    prev_shorts = int(
                        prev_entry.get("shorts_per_episode") or 0) or None
                except (TypeError, ValueError):
                    prev_shorts = None
            shorts_pending = shorts
            shorts_streak = 1
            if prev_shorts is not None and shorts > prev_shorts:
                prev_sp = prev_entry.get("shorts_pending")
                try:
                    prev_ss = int(prev_entry.get("shorts_streak") or 0)
                except (TypeError, ValueError):
                    prev_ss = 0
                shorts_streak = prev_ss + 1 if shorts == prev_sp else 1
                if shorts_streak < STREAK_TO_FLIP:
                    shorts = prev_shorts   # hold until the raise confirms
            channels[channel][slug] = {
                "tier": active,
                "publish_long_form": publish_long,
                "shorts_per_episode": shorts,
                "shorts_pending": shorts_pending,
                "shorts_streak": shorts_streak,
                "long_vpd": round(long_vpd, 3) if long_vpd is not None else None,
                "short_vpd": round(short_vpd, 3) if short_vpd is not None else None,
                "video_count_14d": len(long_vpds) + len(short_vpds),
                "computed": computed,
                "pending": pending,
                "streak": streak,
                "reason": reason,
            }
    return {
        "schema_version": 1,
        "generated": now_iso or _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "seed_date": SEED_DATE,
        "window_days": WINDOW_DAYS,
        "channels": channels,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", default="api/youtube_stats.json")
    parser.add_argument("--out", default="api/youtube_policy.json")
    args = parser.parse_args()

    stats_path = ROOT / args.stats
    out_path = ROOT / args.out

    stats: Optional[dict] = None
    if stats_path.exists():
        try:
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 — best-effort by contract
            logger.warning("Could not parse %s: %s — treating as no data",
                           stats_path, exc)
            stats = None
    else:
        logger.warning("No YouTube stats at %s — seeds/previous state only",
                       stats_path)

    if stats is None and out_path.exists():
        # No fresh data AND a policy already exists: leave it untouched so
        # a transient analytics outage can't advance/reset hysteresis.
        logger.warning("Keeping existing %s unchanged (no stats data)",
                       out_path)
        return 0

    # Staleness gate (Aug 2026): a stats file whose fetch silently died
    # keeps its old `generated` stamp, and because collect_velocities
    # dates the 14-day window off that stamp, the SAME frozen cohort
    # recomputed the same tier every night — with STREAK_TO_FLIP=2 that
    # is enough to flip a tier on day two of an outage and hold it
    # there. Treat stale stats like missing stats: freeze the policy
    # loudly instead of steering on dead data.
    if stats is not None and out_path.exists():
        try:
            # Freeze only when there is a VALID previous policy to keep —
            # a corrupt previous file still restarts from seeds below.
            json.loads(out_path.read_text(encoding="utf-8"))
            gen = str(stats.get("generated") or "")
            age = (_dt.datetime.now(_dt.timezone.utc)
                   - _dt.datetime.fromisoformat(gen))
            if age > _dt.timedelta(days=STATS_MAX_AGE_DAYS):
                print(f"::warning::youtube_stats.json is {age.days}d old — "
                      "keeping the existing publishing policy unchanged "
                      "until the analytics fetch recovers.", flush=True)
                logger.warning("Stats stale (%s old) — policy frozen", age)
                return 0
        except Exception:  # noqa: BLE001 — an unparseable stamp isn't fatal
            pass

    previous: Optional[dict] = None
    if out_path.exists():
        try:
            previous = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 — best-effort by contract
            logger.warning("Previous policy %s unreadable: %s — restarting "
                           "from seeds", out_path, exc)
            previous = None

    policy = build_policy(stats, previous)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(policy, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for channel, shows in policy["channels"].items():
        for slug, entry in shows.items():
            logger.info(
                "%s/%s: tier %s (computed %s, pending %s, streak %d) — %s",
                channel, slug, entry["tier"], entry["computed"],
                entry["pending"], entry["streak"], entry["reason"],
            )
    logger.info("Wrote %s", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
