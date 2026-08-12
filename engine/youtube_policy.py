"""Adaptive YouTube publishing policy — runtime resolution (July 2026).

The nightly ``scripts/update_youtube_policy.py`` turns ``api/youtube_stats.json``
(views-per-day velocity, per show x channel x kind) into per-channel publish
tiers in ``api/youtube_policy.json``. This module is the thin, pure runtime
side: consumers (``run_show._publish_youtube`` for EN + native-RU shows,
``engine.ru_dub`` for @NerraRU dubs) load the committed policy file and ask
"what should THIS show publish today?".

Design contract:
  - Pure + best-effort: no file is ever written here, nothing raises. A
    missing/unreadable policy file, an absent slug, or an opted-out show
    (``youtube.adaptive_publishing: false``) resolves to EXACT legacy YAML
    behavior (``applied: False``).
  - The policy only steers the publish VOLUME/FORMAT (long-form on/off,
    Shorts count). It never edits YAML and never touches audio — visual/
    metadata only, so it sits outside the landmine #17 A/B-listen gate.
  - Shorts never drop to 0: they are the cheapest probe and the only
    recovery signal for a show whose long-form is gated off.
"""

from __future__ import annotations

import datetime
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY_PATH = PROJECT_ROOT / "api" / "youtube_policy.json"

# Absolute ceiling on Shorts per episode, wherever the count comes from
# (policy band, YAML, or a caller's own arithmetic). It lives here because
# the plan contract lives here: run_show, engine.ru_dub and engine.lang_dub
# all consume the same plan and must agree on the bound.
#
# Before July 30 2026 each dub module carried its own ``min(2, ...)``
# literal. When the nightly policy gained a 3-Short band for the shows
# whose demand is an order of magnitude past the 2-Short bar, those
# literals would have discarded it silently — and the band's members are
# RU dubs, so the change would have been a total no-op on exactly the
# channel it was written for. One named constant instead.
#
# The bound is a guard against a runaway count (a mis-generated policy
# file, a YAML typo), not a target. What a show actually publishes is the
# policy's business; this only says no configuration may exceed it.
MAX_SHORTS_PER_EPISODE = 3


def load_policy(path: Optional[Path] = None) -> Optional[dict]:
    """Read + minimally validate the committed policy file.

    Returns ``None`` on any problem (missing file, bad JSON, wrong shape) —
    the caller falls through to legacy YAML behavior. Never raises: the
    policy layer must not be able to break a publish.
    """
    policy_path = Path(path) if path is not None else DEFAULT_POLICY_PATH
    try:
        data = json.loads(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.info("yt policy: %s not found — legacy YAML behavior",
                    policy_path)
        return None
    except Exception as exc:  # noqa: BLE001 — best-effort by contract
        logger.warning("yt policy: %s unreadable (%s) — legacy YAML behavior",
                       policy_path, exc)
        return None
    if not isinstance(data, dict) or not isinstance(data.get("channels"), dict):
        logger.warning("yt policy: %s has no channels map — legacy YAML "
                       "behavior", policy_path)
        return None
    return data


def resolve_publish_plan(
    policy: Optional[dict],
    *,
    slug: str,
    channel: str,
    yaml_publish_long: bool,
    yaml_shorts: int,
    smart_mode: bool,
    adaptive_enabled: bool,
    probe_today: Optional["datetime.date"] = None,
    force_long: bool = False,
) -> Dict[str, object]:
    """Resolve the effective publish plan for one show on one channel.

    Returns ``{"publish_long": bool, "shorts": int, "tier": str,
    "applied": bool, "reason": str}``. ``applied`` is False whenever the
    plan is a straight echo of the YAML inputs (no policy file, slug not
    in the policy, or the show opted out via
    ``youtube.adaptive_publishing: false``) — that case is byte-for-byte
    legacy behavior by contract.

    Rules when the policy applies:
      - ``publish_long`` comes from the policy tier (both directions —
        a tier promotion can turn long-form back on for a YAML
        shorts-only show; the opt-out flag exists to pin YAML behavior).
      - ``force_long`` (Aug 2026, operator-directed dub long-form
        probe) pins ``publish_long`` True AFTER policy resolution while
        leaving the Shorts count/supply ladder untouched — the existing
        shorts system keeps running exactly as the policy decides. Wired
        from ``youtube.dub_force_long_channels`` in the show YAML.
      - ``shorts`` is the policy value with a hard probe floor of 1
        (Shorts are the recovery signal — never 0), and RAISING above the
        YAML count requires ``shorts_start_mode: smart`` (the multi-Short
        path needs the top-N window selector). Lowering is always allowed.
    """
    # Clamp the YAML value too: the no-policy / adaptive-off paths return
    # this verbatim and run_show has no bound of its own, so a YAML
    # `shorts_per_episode: 10` would previously ship 10 Shorts whenever
    # the policy file was missing or the show opted out of adaptation.
    yaml_shorts_floor = min(
        MAX_SHORTS_PER_EPISODE, max(1, int(yaml_shorts or 1))
    )
    plan: Dict[str, object] = {
        "publish_long": bool(yaml_publish_long),
        "shorts": yaml_shorts_floor,
        "tier": "",
        "applied": False,
        "reason": "",
    }
    if not adaptive_enabled or not isinstance(policy, dict):
        return plan
    entry = (
        (policy.get("channels") or {})
        .get((channel or "en").lower(), {})
        .get(slug)
    )
    if not isinstance(entry, dict):
        return plan

    try:
        shorts = max(1, int(entry.get("shorts_per_episode", yaml_shorts_floor) or 1))
    except (TypeError, ValueError):
        shorts = yaml_shorts_floor
    if shorts > yaml_shorts_floor and not smart_mode:
        # Multi-Shorts requires the smart selector (run_show falls back to
        # a single Short without it anyway) — don't raise past the YAML.
        shorts = yaml_shorts_floor
    if shorts > MAX_SHORTS_PER_EPISODE:
        # Enforced here rather than per-consumer: run_show takes
        # plan["shorts"] verbatim and had no bound of its own, so a
        # mis-generated policy file could have asked it for any number.
        logger.warning(
            "yt policy: %s/%s asked for %d Shorts — clamping to %d",
            channel, slug, shorts, MAX_SHORTS_PER_EPISODE,
        )
        shorts = MAX_SHORTS_PER_EPISODE

    publish_long = bool(entry.get("publish_long_form", yaml_publish_long))
    reason = str(entry.get("reason") or "")
    if (not publish_long and yaml_publish_long
            and _is_probe_day(probe_today, slug=slug, channel=channel)):
        # Weekly long-form probe: a Shorts-only show produces no long-form
        # analytics, so without this it could never re-earn its long-form
        # (a one-way door). One probe long per week generates the data the
        # nightly tier computation needs to promote it back. Sharded per
        # show so the probes don't all land on the same UTC Monday.
        publish_long = True
        reason = (reason + " | " if reason else "") + "weekly long-form probe"

    if force_long and not publish_long:
        publish_long = True
        reason = (reason + " | " if reason else "") + \
            "operator long-form override (dub_force_long_channels)"

    plan.update(
        publish_long=publish_long,
        shorts=shorts,
        tier=str(entry.get("tier") or ""),
        applied=True,
        reason=reason,
    )
    return plan


def _is_probe_day(today: Optional["datetime.date"],
                  slug: str = "", channel: str = "en") -> bool:
    """True on this show's weekly long-form probe day.

    Sharded deterministically by (channel, slug) so every gated show
    doesn't probe on the same UTC Monday — the synchronized probe was a
    weekly render/Grok/upload spike on one day, and every probe competed
    with every other probe for the same day's browse surface. A show
    without a slug keeps the legacy Monday.
    """

    day = today or datetime.datetime.now(datetime.timezone.utc).date()
    if not slug:
        return day.weekday() == 0
    digest = hashlib.sha1(f"{channel}/{slug}".encode("utf-8")).hexdigest()
    return day.weekday() == int(digest, 16) % 7
