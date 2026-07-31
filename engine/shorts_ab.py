"""Shorts motion A/B — stills vs Grok Imagine video, same episode.

The question
-----------
Every Short the network ships is a Ken Burns pan over Grok Imagine
*stills*. Nobody knows whether real generated *motion* converts better,
because the two treatments have never run against each other: the
hybrid clip pilot of June 2026 was a LONG-FORM experiment, it ran on a
different surface from the Shorts, and it was retired on cost (~1/3 clip
success, ~$0.35/ep, and a render that crowded the 40-minute pipeline
timeout) before anything about Shorts conversion was learned.

This module answers it properly, on the show with the strongest visual
material and two Shorts a day: **SpaceX Daily ships Short #1 exactly as
it does today (stills, the control) and Short #2 over generated video
(the treatment)**, from the same episode, same audio window logic, same
channel, same day. Confounders that would wreck a between-episode or
between-channel comparison — news cycle, upload time, thumbnail luck,
audience mix — apply equally to both arms.

Why this is not the retired pilot
---------------------------------
Three differences, all of them load-bearing:

1. **Scope.** A 35-second Short needs ~3 clips, not a 12-minute
   slideshow. The clip step is bounded by
   ``shorts_ab_budget_seconds`` and runs AFTER the audio has already
   published, so an overrun costs a render, never an episode.
2. **A hard cost ceiling.** ``shorts_ab_max_cost_usd`` is checked
   before every request, so the experiment cannot silently become the
   ~$50/episode line item that got full Grok Video switched off.
3. **Honest fallback.** If fewer than ``shorts_ab_min_clips`` land, the
   Short ships as STILLS and is recorded as ``stills`` with a
   ``fallback_reason``. A two-clip loop dressed up as the video arm
   would poison the comparison it exists to make — a treatment arm that
   quietly contains control episodes is worse than no experiment.

Contract: pure best-effort and visual-only. No API key, a network
failure, or a budget stop returns the stills variant; nothing here can
block a publish, and nothing here touches audio (outside the landmine
#17 A/B-listen gate).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)

# The two arms. These strings are written into the video index, carried
# through YouTube analytics, and parsed back out of GA4 campaign ids —
# ``engine.funnel`` normalises them the same way, so keep them
# ``[a-z0-9_]``.
VARIANT_STILLS = "stills"
VARIANT_GROK_VIDEO = "grok_video"

VARIANTS = (VARIANT_STILLS, VARIANT_GROK_VIDEO)


@dataclass
class ShortVariant:
    """What one Short actually shipped as.

    ``variant`` is the truth (what the viewer saw); ``intended`` is what
    the plan asked for. They differ exactly when a fallback fired, and
    ``fallback_reason`` says why.
    """

    index: int
    variant: str = VARIANT_STILLS
    intended: str = VARIANT_STILLS
    fallback_reason: str = ""
    clip_paths: List[Path] = field(default_factory=list)
    clips_requested: int = 0
    cost_usd: float = 0.0

    @property
    def is_fallback(self) -> bool:
        return self.variant != self.intended

    def as_metric(self) -> dict:
        return {
            "index": self.index,
            "variant": self.variant,
            "intended": self.intended,
            "fallback_reason": self.fallback_reason,
            "clips": len(self.clip_paths),
            "clips_requested": self.clips_requested,
            "cost_usd": round(self.cost_usd, 4),
        }


def is_enabled(config) -> bool:
    """True when this show opts into the Shorts motion experiment."""
    yt = getattr(config, "youtube", None)
    return bool(getattr(yt, "shorts_ab_enabled", False))


def plan_variants(config, shorts_count: int) -> List[str]:
    """The INTENDED variant for each Short index, control-first.

    Returns all-``stills`` (i.e. today's behaviour, byte for byte) when
    the experiment is off, when the show ships a single Short, or when
    the configured video indexes fall outside the plan — an experiment
    that turned every Short into the treatment arm would have no
    control, so index 0 is always kept on stills.
    """
    count = max(0, int(shorts_count or 0))
    plan = [VARIANT_STILLS] * count
    if not is_enabled(config) or count < 2:
        return plan

    yt = config.youtube
    raw = getattr(yt, "shorts_ab_video_indexes", None) or []
    for value in raw:
        try:
            idx = int(value)
        except (TypeError, ValueError):
            continue
        if idx <= 0 or idx >= count:
            # 0 is the reserved control; out-of-range means the policy
            # lowered the Shorts count today and there is no such Short.
            continue
        plan[idx] = VARIANT_GROK_VIDEO
    return plan


def _clip_contexts(config, hook: str, scene_prompts: Optional[Sequence[str]],
                   count: int) -> List[str]:
    """Per-clip subject text — CONCRETE scenes, never news headlines.

    The first cut of this passed the episode's extracted headlines
    straight through, and the operator's verdict on the resulting Short
    was "pretty bad video content and pretty nonsensical". That is the
    predictable outcome: a headline like "Rocket Lab's purchase of
    Aridium for $8bn brings L-band spectrum holdings under one roof" has
    no depictable content, so a text-to-video model renders an
    incoherent approximation of a financial abstraction.

    A video model needs a *physical scene*. The show YAML already
    curates exactly that for the still pipeline —
    ``youtube.image_queries`` ("Falcon 9 rocket night launch", "Raptor
    engine static fire") — chosen precisely because unguided queries
    produced garbage (landmine #14, where raw ``keywords`` sent Pexels
    looking for fashion models). Those subjects are the right input
    here too, and reusing them keeps the video arm visually consistent
    with the stills arm it is being compared against.

    The episode hook is used only as a last resort, and the raw
    headlines are no longer used at all.
    """
    queries: List[str] = []
    yt = getattr(config, "youtube", None)
    if yt is not None:
        queries = [str(q).strip() for q in
                   (getattr(yt, "image_queries", None) or []) if str(q).strip()]
    if not queries:
        # No curated subjects: fall back to the scene prompts (already
        # image-generation phrasing) and only then to the hook.
        queries = [c for c in (scene_prompts or []) if (c or "").strip()]
    if not queries and hook:
        queries = [hook]
    if not queries:
        return []
    return [queries[i % len(queries)] for i in range(max(1, count))]


def build_variant(
    config,
    *,
    index: int,
    intended: str,
    work_dir: Path,
    episode_num: int,
    hook: str = "",
    scene_prompts: Optional[Sequence[str]] = None,
    spent_usd: float = 0.0,
) -> ShortVariant:
    """Produce the assets for one Short's variant. Never raises.

    *spent_usd* is what the experiment has already spent on this episode;
    the per-episode ceiling is enforced against it BEFORE any request is
    made, so a multi-Short plan can't overshoot by racing itself.
    """
    result = ShortVariant(index=index, intended=intended, variant=intended)
    if intended != VARIANT_GROK_VIDEO:
        return result

    def _fall_back(reason: str) -> ShortVariant:
        result.variant = VARIANT_STILLS
        # Clear any clips already attached: run_show passes
        # result.clip_paths into build_short_video, and the hybrid render
        # fires on >= 2 usable clips — so a "not enough clips" fallback
        # that kept 2 paths would RECORD stills while SHIPPING video,
        # the disguised-arm case this module's contract forbids.
        result.clip_paths = []
        result.fallback_reason = reason
        logger.warning(
            "Shorts A/B: Short #%d falls back to stills (%s) — the "
            "experiment records the arm it ACTUALLY shipped",
            index + 1, reason,
        )
        return result

    # Config reads are guarded: a malformed YAML value must degrade this
    # ONE Short to the control arm, not raise out of the publish loop and
    # cost the whole Short.
    yt = config.youtube
    try:
        count = max(1, int(getattr(yt, "shorts_ab_clips", 3) or 3))
        seconds = max(2, int(getattr(yt, "shorts_ab_clip_seconds", 5) or 5))
        resolution = str(getattr(yt, "shorts_ab_resolution", "720p") or "720p")
        budget_s = float(getattr(yt, "shorts_ab_budget_seconds", 420.0) or 420.0)
        max_cost = float(getattr(yt, "shorts_ab_max_cost_usd", 1.25) or 1.25)
        # Floor 2, not 1: the hybrid renderer requires >= 2 usable clips
        # (engine/video.py) — a min_clips of 1 would record grok_video
        # and then ship stills when a single clip landed.
        min_clips = max(2, int(getattr(yt, "shorts_ab_min_clips", 2) or 2))
    except (TypeError, ValueError) as exc:
        return _fall_back(f"malformed shorts_ab config: {exc}")

    # Cost gate first: cheapest possible check, and the one that keeps
    # the retired-pilot failure from repeating.
    try:
        from engine.grok_video import VIDEO_COST_USD
        per_second = float(VIDEO_COST_USD.get(resolution, 0.07))
    except Exception:  # noqa: BLE001
        per_second = 0.07
    projected = per_second * seconds * count
    if spent_usd + projected > max_cost:
        return _fall_back(
            f"cost ceiling (${spent_usd:.2f} spent + ${projected:.2f} "
            f"projected > ${max_cost:.2f})"
        )

    try:
        from engine.grok_video_clips import generate_short_clips
    except Exception as exc:  # noqa: BLE001
        return _fall_back(f"clip module unavailable: {exc}")

    try:
        clip_set = generate_short_clips(
            work_dir=work_dir,
            episode_num=episode_num,
            contexts=_clip_contexts(config, hook, scene_prompts, count),
            hook=hook,
            show_config=config,
            count=count,
            seconds=seconds,
            resolution=resolution,
            # Vertical: a 16:9 clip letterboxed into a Short would be a
            # worse-looking treatment arm than the control, which would
            # measure the crop rather than the motion.
            aspect="9:16",
            budget_s=budget_s,
        )
    except Exception as exc:  # noqa: BLE001 — never block a publish
        return _fall_back(f"clip generation raised: {exc}")

    result.clips_requested = count
    result.cost_usd = float(getattr(clip_set, "total_cost_usd", 0.0) or 0.0)
    paths = [Path(p) for p in getattr(clip_set, "paths", []) or []]
    paths = [p for p in paths if p.exists() and p.stat().st_size > 0]
    result.clip_paths = paths

    if len(paths) < min_clips:
        return _fall_back(
            f"only {len(paths)}/{count} clip(s) usable, need {min_clips}"
        )

    logger.info(
        "Shorts A/B: Short #%d ships the %s arm (%d clip(s), $%.2f)",
        index + 1, VARIANT_GROK_VIDEO, len(paths), result.cost_usd,
    )
    return result


def summarize(variants: Sequence[ShortVariant]) -> dict:
    """Compact per-episode record for the metrics file / dashboard."""
    shipped = [v.variant for v in variants]
    return {
        "variants": shipped,
        "intended": [v.intended for v in variants],
        "fallbacks": sum(1 for v in variants if v.is_fallback),
        "clips_used": sum(len(v.clip_paths) for v in variants),
        "cost_usd": round(sum(v.cost_usd for v in variants), 4),
        "detail": [v.as_metric() for v in variants],
    }
