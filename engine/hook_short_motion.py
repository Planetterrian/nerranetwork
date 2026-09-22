"""Bounded real-motion retry on the hook Short (Sep 22 2026).

WHY: the Shorts motion A/B stalled at n=4 and the long-form clip pilot
was retired (~1/3 clip success at ~$0.35 an episode, a render that
crowded the pipeline timeout), so every Short on the flagships opens on
a Ken Burns still. This is the smallest honest retry: ONE ~4 s Grok
video clip on the HOOK Short of the three flagships (the Short that
earns 22-30 views against 6 for the second window), so the Short opens
on motion, and stills from the clip onward.

The whole contract is that a failed treatment can never masquerade as a
treatment: the cost gate runs BEFORE any request, the clip step has its
own wall-clock budget under the pipeline's, a shortfall records
``hook_stills`` with the reason, and a show whose b-roll pool already
opened the Short records ``broll_open`` — never the A/B's ``"stills"``
label, which ``scripts/build_shorts_ab_report.py`` sweeps up fail-open.
The three labels land on the video index (``variant``) and ride into
``api/youtube_early_reach.json`` so the age-matched reach can be sliced
by arm at the readout. Never raises; disabled is a no-op that never
imports the generator.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

VARIANT_MOTION_OPEN = "motion_open"
VARIANT_HOOK_STILLS = "hook_stills"
VARIANT_BROLL_OPEN = "broll_open"
VARIANTS = (VARIANT_MOTION_OPEN, VARIANT_BROLL_OPEN, VARIANT_HOOK_STILLS)

#: The pipeline must have at least this much wall-clock left before the
#: clip step is attempted — the Shorts render, upload and commit follow.
PIPELINE_BUDGET_FLOOR_S = 300.0
#: Still hold once the opening clip has played, matching the flat Shorts
#: pace (engine.video._SHORT_SCENE_DURATION_SECONDS) so a one-clip hybrid
#: does not park on a single still for the remaining ~30 s.
STILL_MAX_HOLD_S = 7.0

_MOTION_SUFFIX = ", gentle camera motion, no text, no captions, no logos"


@dataclass
class HookMotion:
    """What the hook Short actually opened on, and what it cost."""

    clip_path: Optional[Path] = None
    variant: str = VARIANT_HOOK_STILLS
    fallback_reason: str = ""
    cost_usd: float = 0.0
    seconds: int = 0
    requested: bool = False

    def as_metric(self) -> dict:
        return {
            "hook_short_motion": self.variant,
            "hook_short_motion_cost_usd": round(float(self.cost_usd), 4),
            "hook_short_motion_reason": self.fallback_reason,
        }


def is_enabled(config) -> bool:
    """True when this show opts into the hook-Short motion retry."""
    yt = getattr(config, "youtube", None)
    return bool(getattr(yt, "hook_short_motion", False))


def motion_prompt(scene_brief: str, hook: str) -> str:
    """The clip prompt: the hook Short's own scene brief, plus motion."""
    subject = " ".join(str(scene_brief or hook or "").split()).rstrip(".")
    return f"{subject}{_MOTION_SUFFIX}"


def plan_hook_motion(
    config,
    *,
    work_dir: Path,
    episode_num: int,
    scene_brief: str = "",
    hook: str = "",
    budget_s: Optional[float] = None,
    spent_usd: float = 0.0,
    pipeline_budget_left_s: Optional[float] = None,
) -> HookMotion:
    """Try for ONE opening clip on the hook Short. Never raises.

    Order of gates, cheapest first: disabled → nothing to film →
    pipeline budget floor → cost ceiling (computed from the price table,
    BEFORE any request) → the request itself under its own wall-clock
    budget. Every shortfall returns ``hook_stills`` with the reason.
    """
    result = HookMotion()
    if not is_enabled(config):
        result.fallback_reason = "disabled"
        return result

    def _stills(reason: str) -> HookMotion:
        result.clip_path = None
        result.variant = VARIANT_HOOK_STILLS
        result.fallback_reason = reason
        logger.warning(
            "Hook Short motion: stills (%s) — the index records the arm "
            "that actually shipped", reason,
        )
        return result

    if not (scene_brief or hook):
        return _stills("no scene brief and no hook to film")

    yt = config.youtube
    try:
        seconds = max(2, min(int(getattr(yt, "hook_short_motion_seconds", 4) or 4), 8))
        max_cost = float(getattr(yt, "hook_short_motion_max_cost_usd", 0.30) or 0.30)
        clip_budget = float(
            budget_s if budget_s is not None
            else (getattr(yt, "hook_short_motion_budget_seconds", 150.0) or 150.0)
        )
    except (TypeError, ValueError) as exc:
        return _stills(f"malformed hook_short_motion config: {exc}")
    result.seconds = seconds

    if (pipeline_budget_left_s is not None
            and float(pipeline_budget_left_s) < PIPELINE_BUDGET_FLOOR_S):
        return _stills(
            f"pipeline budget {float(pipeline_budget_left_s):.0f}s under the "
            f"{PIPELINE_BUDGET_FLOOR_S:.0f}s floor"
        )

    # Cost gate BEFORE any import of the generator or any request.
    try:
        from engine.grok_video import VIDEO_COST_USD
        per_second = float(VIDEO_COST_USD.get("720p", 0.07))
    except Exception:  # noqa: BLE001
        per_second = 0.07
    projected = per_second * seconds
    if float(spent_usd) + projected > max_cost:
        return _stills(
            f"cost ceiling (${float(spent_usd):.2f} spent + ${projected:.2f} "
            f"projected > ${max_cost:.2f})"
        )

    try:
        from engine.grok_video_clips import generate_short_clips
    except Exception as exc:  # noqa: BLE001
        return _stills(f"clip module unavailable: {exc}")

    result.requested = True
    try:
        clip_set = generate_short_clips(
            work_dir=Path(work_dir) / "hook_motion",
            episode_num=int(episode_num),
            contexts=[scene_brief or hook],
            hook=hook,
            show_config=config,
            count=1,
            seconds=seconds,
            resolution="720p",
            aspect="9:16",
            budget_s=clip_budget,
            prompt_override=motion_prompt(scene_brief, hook),
        )
    except Exception as exc:  # noqa: BLE001 — never block a publish
        return _stills(f"clip generation raised: {exc}")

    result.cost_usd = float(getattr(clip_set, "total_cost_usd", 0.0) or 0.0)
    paths = [Path(p) for p in getattr(clip_set, "paths", []) or []]
    paths = [p for p in paths if p.exists() and p.stat().st_size > 0]
    if not paths:
        failures = list(getattr(clip_set, "failures", []) or [])
        return _stills(failures[0] if failures else "no clip landed in budget")

    result.clip_path = paths[0]
    result.variant = VARIANT_MOTION_OPEN
    logger.info(
        "Hook Short motion: opening on a %ds clip ($%.2f)",
        seconds, result.cost_usd,
    )
    return result
