"""Chapter-aware scene scheduling for the YouTube slideshow renderers.

WHY: the long-form slideshow historically cycled its Grok-Imagine scenes
on a uniform timer (``audio_duration / scene_count``, capped at the
15 s max hold), so scene changes landed at arbitrary moments — often
mid-sentence, and never aligned with the episode's actual structure.
Shorts were even blunter: a flat 7 s grid. The episode already ships a
``chapters_ep<NNN>.json`` (Podcasting 2.0 JSON Chapters — ``startTime``
seconds + ``title`` per entry) and a faster-whisper word-level
transcript, so the planning inputs for *editorial* scene timing exist
at zero extra cost.

This module is PURE PLANNING — no ffmpeg, no network, no filesystem
writes. It converts (scenes, chapters, audio length) into an explicit
``[(scene_path, hold_seconds), …]`` schedule and (words, window) into
sentence-snapped Shorts cut times. :mod:`engine.video` consumes the
plans (``build_long_form_video(scene_schedule=…)`` /
``build_short_video(scene_change_times=…)``); the gallery library
supplies the scene pools + per-scene context text. Keeping the logic
here makes it deterministic and unit-testable without rendering a
single frame.

Scheduling rules:

* Scene switches land ON chapter boundaries; a chapter longer than
  the max hold is subdivided into equal slots within
  ``[min_hold_s, max_hold_s]``.
* Scene choice per chapter scores case-insensitive token overlap
  between the chapter title and each scene's context text (prompt /
  caption). Fresh (this-episode) scenes win ties over library scenes;
  scenes already used in the plan take a reuse penalty so a big pool
  yields variety. Fully deterministic — stable index tie-break, no
  randomness.
* No chapters (or fewer than 2) falls back to the uniform plan that
  mirrors today's ``engine.video`` behaviour byte-for-byte in spirit:
  even split of the audio across the pool, capped at ``max_hold_s``,
  rotating through the pool.
"""

from __future__ import annotations

import logging
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# Legacy floor from engine.video.build_long_form_video — a very short
# episode doesn't whip through scenes faster than this.
_UNIFORM_MIN_HOLD_S = 8.0

# Flat Shorts pacing (engine.video._SHORT_SCENE_DURATION_SECONDS) used
# when a cadence gap contains no sentence-ending word to snap to.
_FLAT_FALLBACK_GAP_S = 7.0

# Scoring weights for scene selection. The fresh bonus is deliberately
# smaller than one token of title overlap (topical match beats
# freshness); the reuse penalty is larger than the fresh bonus so an
# unused library scene beats a reused fresh one (variety wins when the
# pool is big); the repeat penalty discourages the same image on two
# consecutive slots when any alternative exists.
_FRESH_BONUS = 0.25
_REUSE_PENALTY = 0.5
_REPEAT_PENALTY = 0.75

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SENTENCE_END_CHARS = (".", "!", "?")

# Chapter starts closer together than this collapse into one window —
# sub-second "chapters" would produce unwatchable flicker.
_MIN_CHAPTER_GAP_S = 1.0


def _tokenize(text: Optional[str]) -> frozenset:
    """Lower-cased alphanumeric token set for overlap scoring."""
    if not text:
        return frozenset()
    return frozenset(_TOKEN_RE.findall(text.lower()))


def _chapter_windows(
    chapters, audio_duration_s: float,
) -> Optional[List[Tuple[float, float, str]]]:
    """Normalize a parsed chapters.json list into ``(start, end, title)``
    windows partitioning ``[0, audio_duration_s]``.

    Accepts either the raw ``chapters`` list or the whole file dict
    (``{"version": …, "chapters": […]}``). Returns ``None`` when fewer
    than 2 usable chapters exist — the caller falls back to the uniform
    plan.
    """
    if isinstance(chapters, dict):
        chapters = chapters.get("chapters")
    entries: List[Tuple[float, str]] = []
    for ch in chapters or []:
        try:
            start = float(ch.get("startTime"))
        except (AttributeError, TypeError, ValueError):
            continue
        if not (0 <= start < audio_duration_s):
            continue
        entries.append((start, str(ch.get("title") or "")))
    entries.sort(key=lambda e: e[0])

    deduped: List[Tuple[float, str]] = []
    for start, title in entries:
        if deduped and start - deduped[-1][0] < _MIN_CHAPTER_GAP_S:
            continue
        deduped.append((start, title))
    if len(deduped) < 2:
        return None

    # The plan must cover the full audio: clamp the first chapter to 0,
    # or prepend an untitled window for any pre-chapter lead-in.
    if deduped[0][0] > 0.5:
        deduped.insert(0, (0.0, ""))
    else:
        deduped[0] = (0.0, deduped[0][1])

    windows: List[Tuple[float, float, str]] = []
    for i, (start, title) in enumerate(deduped):
        end = deduped[i + 1][0] if i + 1 < len(deduped) else audio_duration_s
        if end - start > 1e-6:
            windows.append((start, end, title))
    return windows or None


def _subdivide(length: float, max_hold_s: float, min_hold_s: float) -> List[float]:
    """Split a chapter into equal slots within ``[min_hold_s, max_hold_s]``.

    A chapter shorter than ``min_hold_s`` is one slot of its full length
    (the boundary alignment matters more than the floor). When the two
    bounds conflict (pathological ``min > max/2`` configs), the min
    hold wins — a slightly-long hold beats a flickering one.
    """
    n = max(1, math.ceil(length / max_hold_s))
    while n > 1 and length / n < min_hold_s:
        n -= 1
    return [length / n] * n


def _pick_scene(
    pool: Sequence[Path],
    fresh: frozenset,
    context: Dict[Path, frozenset],
    title_tokens: frozenset,
    use_counts: Dict[Path, int],
    last_pick: Optional[Path],
) -> Path:
    """Deterministically pick the best scene for one slot."""
    best_path = pool[0]
    best_key: Optional[Tuple[float, int]] = None
    for idx, path in enumerate(pool):
        score = float(len(title_tokens & context.get(path, frozenset())))
        if path in fresh:
            score += _FRESH_BONUS
        score -= _REUSE_PENALTY * use_counts[path]
        if path == last_pick:
            score -= _REPEAT_PENALTY
        key = (-score, idx)  # stable: index breaks exact ties
        if best_key is None or key < best_key:
            best_key = key
            best_path = path
    return best_path


def _uniform_plan(
    pool: Sequence[Path], audio_duration_s: float, max_hold_s: float,
) -> List[Tuple[Path, float]]:
    """The no-chapters fallback — mirrors today's uniform rotation in
    ``engine.video.build_long_form_video``: even split of the audio
    across the pool (floor 8 s), cycling the pool so no image holds
    longer than ``max_hold_s``.
    """
    hold = max(_UNIFORM_MIN_HOLD_S, audio_duration_s / len(pool))
    slots: List[Path] = list(pool)
    if hold > max_hold_s and len(pool) > 1:
        target = math.ceil(audio_duration_s / max_hold_s)
        slots = [pool[i % len(pool)] for i in range(target)]
        hold = max(_UNIFORM_MIN_HOLD_S, audio_duration_s / len(slots))
    plan = [(path, hold) for path in slots]
    # Last slot absorbs float rounding so the cumulative plan sums to
    # the audio length. When the 8 s floor made the plan overshoot
    # (very short audio), leave it — the composite's -shortest trims,
    # exactly as the legacy renderer behaves.
    diff = audio_duration_s - math.fsum(d for _, d in plan)
    if plan and plan[-1][1] + diff >= 1.0:
        plan[-1] = (plan[-1][0], plan[-1][1] + diff)
    return plan


def plan_chapter_schedule(
    fresh_scenes: Optional[Sequence[Path]],
    library_scenes: Optional[Sequence[Path]],
    chapters,
    audio_duration_s: float,
    *,
    max_hold_s: float = 15.0,
    min_hold_s: float = 6.0,
    scene_context: Optional[Dict[Path, str]] = None,
) -> List[Tuple[Path, float]]:
    """Plan the long-form slideshow as ``[(scene_path, hold_seconds), …]``.

    Parameters
    ----------
    fresh_scenes:
        This episode's Grok-Imagine scenes (preferred on score ties).
    library_scenes:
        Evergreen scenes from the gallery library (tie-break losers).
    chapters:
        The parsed ``chapters_ep<NNN>.json`` list (each entry carries
        ``startTime`` seconds + ``title``; the whole file dict is also
        accepted). ``None`` / empty / fewer than 2 chapters falls back
        to the uniform rotation plan.
    audio_duration_s:
        Final mixed episode length; the plan's cumulative durations sum
        to ~this (last slot absorbs rounding).
    max_hold_s, min_hold_s:
        Subdivision bounds — chapters longer than ``max_hold_s`` split
        into equal slots no shorter than ``min_hold_s``.
    scene_context:
        Optional ``{path: prompt/caption text}`` used for the
        title-overlap scoring; scenes without context score 0 overlap.
    """
    seen = set()
    pool: List[Path] = []
    fresh_list: List[Path] = []
    for raw in list(fresh_scenes or []):
        path = Path(raw)
        if path not in seen:
            seen.add(path)
            pool.append(path)
            fresh_list.append(path)
    for raw in list(library_scenes or []):
        path = Path(raw)
        if path not in seen:
            seen.add(path)
            pool.append(path)

    if not pool or not audio_duration_s or audio_duration_s <= 0:
        return []
    audio_duration_s = float(audio_duration_s)
    fresh = frozenset(fresh_list)

    context: Dict[Path, frozenset] = {}
    for key, value in (scene_context or {}).items():
        context[Path(key)] = _tokenize(value)

    windows = _chapter_windows(chapters, audio_duration_s)
    if windows is None:
        logger.debug(
            "scene_scheduler: no usable chapters — uniform fallback "
            "(%d scenes, %.1fs)", len(pool), audio_duration_s,
        )
        return _uniform_plan(pool, audio_duration_s, max_hold_s)

    plan: List[Tuple[Path, float]] = []
    use_counts: Dict[Path, int] = {path: 0 for path in pool}
    last_pick: Optional[Path] = None
    for start, end, title in windows:
        title_tokens = _tokenize(title)
        for slot_duration in _subdivide(end - start, max_hold_s, min_hold_s):
            pick = _pick_scene(
                pool, fresh, context, title_tokens, use_counts, last_pick,
            )
            plan.append((pick, slot_duration))
            use_counts[pick] += 1
            last_pick = pick

    diff = audio_duration_s - math.fsum(d for _, d in plan)
    if plan and plan[-1][1] + diff >= 1.0:
        plan[-1] = (plan[-1][0], plan[-1][1] + diff)
    logger.debug(
        "scene_scheduler: %d chapter windows → %d slots over %.1fs",
        len(windows), len(plan), audio_duration_s,
    )
    return plan


def sentence_cut_times(
    words: Optional[Sequence[dict]],
    window_start_s: float,
    duration_s: float,
    *,
    min_gap_s: float = 5.0,
    max_gap_s: float = 9.0,
) -> List[float]:
    """Sentence-snapped Shorts scene-change times, RELATIVE to clip start.

    ``words`` is the faster-whisper per-word list already used by
    :func:`engine.captions.transcript_to_ass_window` — dicts carrying
    ``word`` (token, may include leading space + trailing punctuation),
    ``start`` and ``end`` (seconds on the same timeline as
    ``window_start_s``; the caller applies any music-intro audio offset
    before handing the words over, same contract as the captions path).

    Walks the clip in ``[min_gap_s, max_gap_s]`` steps; each cut snaps
    to the sentence-ending word (``.``/``!``/``?`` suffix) nearest the
    middle of the allowed band, so scene changes land between sentences
    instead of mid-word. A band with no sentence end falls back to the
    legacy flat 7 s pace for that step. No cut is ever placed within
    ``min_gap_s`` of the clip end — the last scene always gets a full
    hold before the end-card takes over.
    """
    if not duration_s or duration_s <= 0:
        return []
    duration_s = float(duration_s)
    window_start_s = float(window_start_s)

    ends: List[float] = []
    for w in words or []:
        token = (w.get("word") or "").strip()
        if not token or not token.endswith(_SENTENCE_END_CHARS):
            continue
        try:
            rel = float(w["end"]) - window_start_s
        except (KeyError, TypeError, ValueError):
            continue
        if 0.0 < rel < duration_s:
            ends.append(rel)
    ends.sort()

    flat_gap = min(max(_FLAT_FALLBACK_GAP_S, min_gap_s), max_gap_s)
    limit = duration_s - min_gap_s  # end guard: no cut beyond this
    cuts: List[float] = []
    last = 0.0
    while True:
        lo = last + min_gap_s
        hi = last + max_gap_s
        if lo > limit:
            break
        band_hi = min(hi, limit)
        candidates = [e for e in ends if lo <= e <= band_hi]
        if candidates:
            mid = (lo + hi) / 2.0
            cut = min(candidates, key=lambda e: (abs(e - mid), e))
        else:
            cut = last + flat_gap
            if cut > limit:
                break
        cuts.append(round(cut, 3))
        last = cut
    return cuts
