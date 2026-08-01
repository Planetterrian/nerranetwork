"""Composition layer wiring gallery reuse + chapter-aware scenes into run_show.

WHY this module exists: the June 2026 visual-reuse engine layer
(:mod:`engine.gallery_library` for pulling already-paid-for Grok Imagine
scenes back down from R2, :mod:`engine.scene_scheduler` for chapter-aligned
scene timing, and the ``scene_schedule`` / ``broll_clips`` /
``scene_change_times`` render hooks on :mod:`engine.video`) is deliberately
made of small orthogonal pieces. Composing them inline in
``run_show.py:_publish_youtube`` would add ~150 lines to a function that is
already the monolith's worst offender — so the composition lives here, where
it is unit-testable without rendering a frame, and run_show only makes one
call per surface (long-form plan / per-Short extras / recap pool / degraded
fallback).

Contract (identical to the gallery library's): every public function is
best-effort and NEVER raises. Any internal failure logs a warning and
returns the "legacy" shape — ``scene_schedule=None`` / ``scene_paths=None``
/ empty lists — so the caller's byte-for-byte legacy render path takes over
and a publish is never blocked by an optional visual upgrade.

All behaviour is config-gated on the ``youtube:`` knobs added in the same
pass (``gallery_blend_enabled``, ``chapter_aligned_scenes``,
``recap_reuse_scenes``, ``gallery_fallback_enabled``,
``shorts_sentence_cuts``, ``evergreen_broll`` — defaults on). None of this
touches audio, so the whole system sits outside the landmine-#17 A/B gate.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

# Matches engine.video._MAX_BROLL_CLIPS — requesting more would just be
# truncated by the renderer, and the download cost is per-clip.
_BROLL_LIMIT = 3

# Weekly recaps pull a bigger pool than the daily blend: a ~15-min recap at
# the 15 s max hold has ~60 slots, so more distinct images = less repetition.
_RECAP_POOL_LIMIT = 24


def _yt(config) -> Any:
    return getattr(config, "youtube", None)


def _flag(config, name: str, default: bool = True) -> bool:
    return bool(getattr(_yt(config), name, default))


def _paths(items: Optional[Sequence]) -> List[Path]:
    return [Path(p) for p in (items or [])]


def _dedup(*lists: Sequence[Path]) -> List[Path]:
    seen: set = set()
    out: List[Path] = []
    for lst in lists:
        for p in lst:
            p = Path(p)
            if p not in seen:
                seen.add(p)
                out.append(p)
    return out


def _load_chapters(chapters_path) -> Optional[list]:
    """Parsed chapters list from a Podcasting-2.0 chapters.json; None if
    missing/corrupt. Accepts the whole-file dict or a bare list."""
    if not chapters_path:
        return None
    try:
        p = Path(chapters_path)
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — chapters are optional input
        logger.warning("visual_reuse: unreadable chapters at %s: %s",
                       chapters_path, exc)
        return None
    chapters = data.get("chapters") if isinstance(data, dict) else data
    return chapters if isinstance(chapters, list) else None


def _usable_chapter_count(chapters: Optional[list],
                          audio_duration_s: float) -> int:
    """How many chapter entries the scheduler could actually anchor on.

    Mirrors the scheduler's own filter (numeric ``startTime`` inside the
    audio) so we can decide UP FRONT whether a chapter-aligned schedule is
    meaningful — with <2 anchors the scheduler degrades to the uniform plan
    anyway, and we'd rather report ``mode="uniform"`` honestly than ship a
    schedule that is uniform in disguise.
    """
    starts = []
    for ch in chapters or []:
        try:
            start = float(ch.get("startTime"))
        except (AttributeError, TypeError, ValueError):
            continue
        if 0 <= start < audio_duration_s:
            starts.append(start)
    return len(set(starts))


def load_transcript_words(transcript_path) -> List[dict]:
    """Flatten a faster-whisper transcript JSON into one word list.

    The per-word dicts (``word`` / ``start`` / ``end``) are exactly what
    :func:`engine.scene_scheduler.sentence_cut_times` consumes. Older
    episodes transcribed without ``word_timestamps=True`` have no ``words``
    arrays — those (and any parse failure) return ``[]`` so the caller
    simply skips sentence cuts. Never raises.
    """
    try:
        p = Path(transcript_path)
        data = json.loads(p.read_text(encoding="utf-8"))
        words: List[dict] = []
        for seg in (data.get("segments") or []) if isinstance(data, dict) else []:
            for w in seg.get("words") or []:
                if isinstance(w, dict):
                    words.append(w)
        return words
    except Exception as exc:  # noqa: BLE001 — cuts are optional garnish
        logger.warning("visual_reuse: could not load transcript words from "
                       "%s: %s", transcript_path, exc)
        return []


def long_form_visual_plan(
    config,
    *,
    show_slug: str,
    episode_id: str,
    hook: str,
    fresh_scenes: Optional[Sequence[Path]],
    chapters_path,
    audio_duration_s: float,
    digests_dir,
    cache_dir: Optional[Path] = None,
    fresh_scene_context: Optional[Dict[Path, str]] = None,
    blend_library: Optional[bool] = None,
) -> Dict[str, Any]:
    """Plan the long-form slideshow visuals for one episode.

    Returns a dict the caller can pass straight through to
    ``engine.video.build_long_form_video``:

    * ``scene_schedule`` — explicit ``[(path, hold_s), …]`` plan when
      ``chapter_aligned_scenes`` is on AND the episode has ≥2 usable
      chapters; ``None`` otherwise (legacy uniform rendering).
    * ``scene_paths`` — the blended fresh + library pool (best-first),
      or ``None`` when the pool has <2 images (legacy cover path).
    * ``broll_clips`` — local evergreen clips (``evergreen_broll``; a
      no-op until the operator publishes ``broll.json``), or ``None``.
    * ``fresh_count`` / ``library_count`` / ``mode`` — observability
      (``mode`` ∈ chapter_schedule | uniform | library_fallback | cover).

    ``fresh_scene_context`` maps this episode's scene paths to their Grok
    Imagine prompts so chapter-title scoring can pick topical images;
    library context comes from the manifest. ``blend_library`` overrides
    the ``gallery_blend_enabled`` config gate (the recap path passes
    ``False`` because its pool IS library imagery already).

    Best-effort: any failure returns the legacy shape (no schedule, no
    extra scenes) with a logged warning. Never raises.
    """
    fresh = _paths(fresh_scenes)
    legacy = {
        "scene_schedule": None,
        "broll_clips": None,
        "scene_paths": None,
        "fresh_count": len(fresh),
        "library_count": 0,
        "mode": "uniform" if len(fresh) >= 2 else "cover",
    }
    try:
        out = dict(legacy)
        chapters = _load_chapters(chapters_path)
        context_text = " ".join(
            [hook or ""] + [str(c.get("title") or "") for c in chapters or []]
        ).strip()

        manifest: Optional[dict] = None
        library: List[Path] = []
        do_blend = (_flag(config, "gallery_blend_enabled")
                    if blend_library is None else bool(blend_library))
        if do_blend:
            from engine.gallery_library import load_manifest, select_library_scenes
            manifest = load_manifest()
            limit = int(getattr(_yt(config), "gallery_blend_max_long", 8) or 0)
            library = select_library_scenes(
                show_slug,
                aspect="16:9",
                exclude_episode_id=episode_id,
                context_text=context_text,
                limit=limit,
                manifest=manifest,
                cache_dir=cache_dir,
            )
        out["library_count"] = len(library)

        if _flag(config, "evergreen_broll"):
            from engine.gallery_library import select_broll_clips
            # episode_seed rotates the pool per episode — without it
            # every episode shipped the same first clips regardless of
            # how large the pool grew.
            broll = select_broll_clips(
                show_slug, digests_dir=Path(digests_dir),
                limit=int(getattr(_yt(config), "broll_clips_per_episode",
                                  _BROLL_LIMIT) or _BROLL_LIMIT),
                cache_dir=cache_dir,
                episode_seed=f"{show_slug}:{episode_id}",
            )
            out["broll_clips"] = broll or None

        pool = _dedup(fresh, library)
        if len(pool) < 2:
            out["mode"] = "cover"
            return out
        out["scene_paths"] = pool
        out["mode"] = "uniform" if len(fresh) >= 2 else "library_fallback"

        if (
            _flag(config, "chapter_aligned_scenes")
            and audio_duration_s and audio_duration_s > 0
            and _usable_chapter_count(chapters, float(audio_duration_s)) >= 2
        ):
            scene_context: Dict[Path, str] = {
                Path(k): str(v) for k, v in (fresh_scene_context or {}).items()
            }
            if library:
                from engine.gallery_library import scene_context_map
                scene_context.update(scene_context_map(manifest or {}, library))
            from engine.scene_scheduler import plan_chapter_schedule
            schedule = plan_chapter_schedule(
                fresh, library, chapters, float(audio_duration_s),
                scene_context=scene_context,
            )
            if len(schedule) >= 2:
                out["scene_schedule"] = schedule
                if len(fresh) >= 2:
                    out["mode"] = "chapter_schedule"
        logger.info(
            "visual_reuse: long-form plan for %s %s — mode=%s fresh=%d "
            "library=%d broll=%d slots=%s",
            show_slug, episode_id, out["mode"], len(fresh), len(library),
            len(out["broll_clips"] or []),
            len(out["scene_schedule"]) if out["scene_schedule"] else "-",
        )
        return out
    except Exception as exc:  # noqa: BLE001 — never block a publish
        logger.warning(
            "visual_reuse: long-form visual plan failed for %s %s: %s — "
            "falling back to legacy visuals", show_slug, episode_id, exc,
        )
        return legacy


def short_visual_extras(
    config,
    *,
    show_slug: str,
    episode_id: str,
    fresh_short_scenes: Optional[Sequence[Path]],
    transcript_words: Optional[Sequence[dict]],
    window_start_s: float,
    clip_duration_s: float,
    cache_dir: Optional[Path] = None,
    context_text: str = "",
    blend_library: Optional[bool] = None,
) -> Dict[str, Any]:
    """Per-Short visual upgrades: blended 9:16 pool + sentence-snapped cuts.

    * ``scene_paths`` — fresh vertical scenes + up to
      ``gallery_blend_max_short`` library 9:16 scenes ranked against the
      Short's hook; ``None`` when the blended pool has <2 images (the
      caller keeps its legacy scene handling).
    * ``scene_change_times`` — cut times relative to the clip start, from
      :func:`engine.scene_scheduler.sentence_cut_times`
      (``shorts_sentence_cuts`` gate); ``None`` when disabled or no word
      data exists (legacy flat 7 s grid).

    ``window_start_s`` must be on the SAME timeline as the transcript
    words (the caller subtracts the music-intro offset, exactly as the
    captions path does). Best-effort; never raises.
    """
    fresh = _paths(fresh_short_scenes)
    legacy = {
        "scene_paths": None,
        "scene_change_times": None,
        "fresh_count": len(fresh),
        "library_count": 0,
    }
    try:
        out = dict(legacy)
        library: List[Path] = []
        do_blend = (_flag(config, "gallery_blend_enabled")
                    if blend_library is None else bool(blend_library))
        if do_blend:
            from engine.gallery_library import select_library_scenes
            limit = int(getattr(_yt(config), "gallery_blend_max_short", 4) or 0)
            library = select_library_scenes(
                show_slug,
                aspect="9:16",
                exclude_episode_id=episode_id,
                context_text=context_text,
                limit=limit,
                cache_dir=cache_dir,
            )
        out["library_count"] = len(library)
        pool = _dedup(fresh, library)
        if len(pool) >= 2:
            out["scene_paths"] = pool

        if _flag(config, "shorts_sentence_cuts") and transcript_words:
            from engine.scene_scheduler import sentence_cut_times
            cuts = sentence_cut_times(
                list(transcript_words), float(window_start_s),
                float(clip_duration_s),
            )
            out["scene_change_times"] = cuts or None
        return out
    except Exception as exc:  # noqa: BLE001 — never block a publish
        logger.warning(
            "visual_reuse: Shorts visual extras failed for %s %s: %s — "
            "falling back to legacy visuals", show_slug, episode_id, exc,
        )
        return legacy


def recap_scene_pool(
    config,
    *,
    show_slug: str,
    episode_id: str,
    end_date: str,
    cache_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """The Sunday-recap scene pool: this week's imagery in both aspects.

    A weekly recap synthesises its digest from the past 7 days of episodes
    — the matching imagery already exists in the gallery, so regenerating
    with Grok Imagine would pay twice for pictures of the same stories.
    Returns ``{"long": [16:9 paths], "short": [9:16 paths], "enabled": bool}``;
    the caller only skips generation when BOTH aspects have ≥2 images
    (below that, generating fresh scenes as today is the better episode).
    Gated on ``recap_reuse_scenes``. Best-effort; never raises.
    """
    out: Dict[str, Any] = {"long": [], "short": [], "enabled": False}
    try:
        if not _flag(config, "recap_reuse_scenes"):
            return out
        out["enabled"] = True
        from engine.gallery_library import collect_week_scenes
        for key, aspect in (("long", "16:9"), ("short", "9:16")):
            out[key] = collect_week_scenes(
                show_slug,
                aspect=aspect,
                end_date=end_date,
                exclude_episode_id=episode_id,
                cache_dir=cache_dir,
                limit=_RECAP_POOL_LIMIT,
            )
        logger.info(
            "visual_reuse: recap pool for %s %s — %d long / %d short scenes",
            show_slug, episode_id, len(out["long"]), len(out["short"]),
        )
        return out
    except Exception as exc:  # noqa: BLE001 — never block a publish
        logger.warning(
            "visual_reuse: recap scene pool failed for %s %s: %s — "
            "generating scenes as usual", show_slug, episode_id, exc,
        )
        return {"long": [], "short": [], "enabled": False}


def fallback_scene_pool(
    config,
    *,
    show_slug: str,
    episode_id: str,
    cache_dir: Optional[Path] = None,
    limit: int = 6,
    aspect: str = "16:9",
    context_text: str = "",
) -> List[Path]:
    """Library scenes for the degraded (<2 fresh scenes) case.

    When Grok Imagine has a bad day (bad key / rate limit / model outage)
    the slideshow used to degrade straight to the static cover. The show's
    own historical imagery is strictly better than a static cover, so this
    pulls the most relevant library scenes instead. Gated on
    ``gallery_fallback_enabled``. Returns ``[]`` when disabled, when the
    gallery has nothing for the show (e.g. Pexels-only shows), or on any
    failure — the caller then degrades to the cover exactly as before.
    """
    try:
        if not _flag(config, "gallery_fallback_enabled"):
            return []
        from engine.gallery_library import select_library_scenes
        return select_library_scenes(
            show_slug,
            aspect=aspect,
            exclude_episode_id=episode_id,
            context_text=context_text,
            limit=limit,
            cache_dir=cache_dir,
        )
    except Exception as exc:  # noqa: BLE001 — never block a publish
        logger.warning(
            "visual_reuse: fallback scene pool failed for %s %s: %s",
            show_slug, episode_id, exc,
        )
        return []
