"""Tests for :mod:`engine.scene_scheduler` — chapter-aware scene planning.

Pure-logic tests (no ffmpeg, no filesystem): the scheduler converts
(scene pools, chapters.json entries, audio length) into an explicit
``[(path, hold_seconds), …]`` plan, and (whisper words, Shorts window)
into sentence-snapped cut times. The uniform fallback must mirror the
legacy ``engine.video`` rotation math so shipping the scheduler with no
chapters available changes nothing.
"""

import math
from pathlib import Path

from engine.scene_scheduler import (
    _MAX_SLIDESHOW_SLOTS,
    plan_chapter_schedule,
    sentence_cut_times,
)


def _scenes(prefix: str, n: int):
    return [Path(f"/scenes/{prefix}{i}.png") for i in range(n)]


def _chapters(*starts_titles):
    return [{"startTime": s, "title": t} for s, t in starts_titles]


# ---------------------------------------------------------------------------
# Uniform fallback — must mirror the legacy engine.video rotation
# ---------------------------------------------------------------------------

class TestUniformFallback:
    def test_no_chapters_mirrors_legacy_rotation(self):
        """4 scenes over 360 s: legacy math says 90 s/scene > 15 s max
        hold → cycle to ceil(360/15) = 24 slots of 15 s, rotating
        through the pool in order. 24 is also the render-safe cap, so
        this case sits exactly on the boundary."""
        pool = _scenes("fresh", 4)
        plan = plan_chapter_schedule(pool, [], None, 360.0)
        assert len(plan) == 24
        assert len(plan) <= _MAX_SLIDESHOW_SLOTS
        assert all(abs(d - 15.0) < 1e-9 for _, d in plan)
        assert [p for p, _ in plan] == [pool[i % 4] for i in range(24)]
        assert abs(math.fsum(d for _, d in plan) - 360.0) < 1e-6

    def test_long_episode_uniform_plan_respects_slot_cap(self):
        """Ep537-class: 1044 s @ 15 s hold would be ~70 slots and timed
        out the pipeline. Cap stretches holds instead of exploding the
        ffmpeg input count."""
        pool = _scenes("fresh", 4)
        plan = plan_chapter_schedule(pool, [], None, 1044.0)
        assert len(plan) == _MAX_SLIDESHOW_SLOTS
        assert abs(math.fsum(d for _, d in plan) - 1044.0) < 1e-6
        # Holds stretch above the 15 s preference but stay finite.
        assert all(d >= 15.0 for _, d in plan)

    def test_no_cycling_when_even_split_fits(self):
        """10 scenes over 100 s → 10 s/scene ≤ 15 s: one slot per scene,
        no cycling — exactly the legacy behaviour."""
        pool = _scenes("fresh", 10)
        plan = plan_chapter_schedule(pool, [], [], 100.0)
        assert len(plan) == 10
        assert [p for p, _ in plan] == pool
        assert abs(math.fsum(d for _, d in plan) - 100.0) < 1e-6

    def test_single_chapter_falls_back_to_uniform(self):
        pool = _scenes("fresh", 4)
        chapters = _chapters((0.0, "Introduction"))
        plan = plan_chapter_schedule(pool, [], chapters, 360.0)
        uniform = plan_chapter_schedule(pool, [], None, 360.0)
        assert plan == uniform

    def test_whole_file_dict_accepted(self):
        """The scheduler accepts either the parsed ``chapters`` list or
        the whole chapters.json dict."""
        pool = _scenes("fresh", 3)
        wrapped = {"version": "1.2.0", "chapters": _chapters(
            (0.0, "Intro"), (30.0, "Body"), (60.0, "Closing"),
        )}
        bare = _chapters((0.0, "Intro"), (30.0, "Body"), (60.0, "Closing"))
        assert (plan_chapter_schedule(pool, [], wrapped, 90.0)
                == plan_chapter_schedule(pool, [], bare, 90.0))

    def test_empty_pool_returns_empty(self):
        assert plan_chapter_schedule([], [], None, 300.0) == []
        assert plan_chapter_schedule(None, None, None, 300.0) == []

    def test_zero_audio_returns_empty(self):
        assert plan_chapter_schedule(_scenes("f", 3), [], None, 0.0) == []


# ---------------------------------------------------------------------------
# Chapter-boundary alignment + subdivision bounds
# ---------------------------------------------------------------------------

class TestChapterAlignment:
    def test_scene_switches_land_on_chapter_boundaries(self):
        """Chapters at 0/30/60 over 90 s of audio: the cumulative plan
        must pass EXACTLY through 30 and 60 — that's the whole point of
        the scheduler."""
        pool = _scenes("fresh", 5)
        chapters = _chapters((0.0, "Intro"), (30.0, "Deep Dive"),
                             (60.0, "Closing"))
        plan = plan_chapter_schedule(pool, [], chapters, 90.0)
        cumulative = set()
        acc = 0.0
        for _, dur in plan:
            acc += dur
            cumulative.add(round(acc, 6))
        assert 30.0 in cumulative
        assert 60.0 in cumulative
        assert abs(math.fsum(d for _, d in plan) - 90.0) < 1e-6

    def test_long_chapter_subdivides_within_bounds(self):
        """A 40 s opening chapter subdivides with the ACCELERATING-OPEN
        max hold (July 31 2026 — D1: windows starting < 60 s clamp to
        8 s) → 5 equal 8 s slots. Every slot stays within
        [min_hold, effective max]."""
        pool = _scenes("fresh", 6)
        chapters = _chapters((0.0, "Intro"), (40.0, "Closing"))
        plan = plan_chapter_schedule(pool, [], chapters, 55.0,
                                     max_hold_s=15.0, min_hold_s=6.0)
        # First chapter (40 s, start < 60 s) contributes 5 slots of 8 s.
        first_five = [d for _, d in plan[:5]]
        assert all(abs(d - 8.0) < 1e-9 for d in first_five)
        for _, dur in plan:
            assert dur <= 15.0 + 1e-9
            assert dur >= 6.0 - 1e-9
        assert abs(math.fsum(d for _, d in plan) - 55.0) < 1e-6

    def test_sixteen_second_chapter_splits_into_two_eights(self):
        pool = _scenes("fresh", 4)
        chapters = _chapters((0.0, "Intro"), (16.0, "Closing"))
        plan = plan_chapter_schedule(pool, [], chapters, 32.0)
        assert abs(plan[0][1] - 8.0) < 1e-9
        assert abs(plan[1][1] - 8.0) < 1e-9

    def test_chapter_shorter_than_min_hold_gets_single_full_slot(self):
        """Boundary alignment beats the floor: a 4 s teaser chapter is
        one 4 s slot, not merged into a neighbour."""
        pool = _scenes("fresh", 4)
        chapters = _chapters((0.0, "Intro"), (20.0, "Teaser"),
                             (24.0, "Closing"))
        plan = plan_chapter_schedule(pool, [], chapters, 36.0,
                                     max_hold_s=15.0, min_hold_s=6.0)
        assert any(abs(d - 4.0) < 1e-9 for _, d in plan)

    def test_leading_gap_before_first_chapter_is_covered(self):
        """chapters.json occasionally starts a few seconds in; the plan
        must still cover from t=0."""
        pool = _scenes("fresh", 4)
        chapters = _chapters((5.0, "Intro"), (25.0, "Closing"))
        plan = plan_chapter_schedule(pool, [], chapters, 40.0)
        assert abs(math.fsum(d for _, d in plan) - 40.0) < 1e-6

    def test_long_episode_chapter_plan_respects_slot_cap(self):
        """Ep537 shape: ~11 chapters over ~17 min at 15 s hold → 70+
        slots uncapped. Cap merges adjacent slots; duration sum and
        chapter-boundary coverage survive."""
        pool = _scenes("fresh", 4)
        # 11 chapter anchors across 1044 s (mirrors auto-segmented Ep537).
        starts = [0, 60, 150, 250, 350, 450, 550, 650, 750, 900, 1000]
        chapters = _chapters(*[(float(s), f"Ch{i}") for i, s in enumerate(starts)])
        plan = plan_chapter_schedule(pool, [], chapters, 1044.0,
                                     max_hold_s=15.0, min_hold_s=6.0)
        assert len(plan) <= _MAX_SLIDESHOW_SLOTS
        assert len(plan) >= 2
        assert abs(math.fsum(d for _, d in plan) - 1044.0) < 1e-6
        # Uncapped would be ceil(1044/15) ≈ 70; prove the cap fired.
        uncapped_floor = math.ceil(1044.0 / 15.0)
        assert uncapped_floor > _MAX_SLIDESHOW_SLOTS
        assert len(plan) < uncapped_floor


# ---------------------------------------------------------------------------
# Accelerating open (July 31 2026 — D1)
# ---------------------------------------------------------------------------


class TestAcceleratingOpen:
    def test_slots_starting_in_first_minute_hold_at_most_eight_seconds(self):
        """The first minute is where long-form retention is decided
        (10.7% EN median). Chapter windows starting < 60 s subdivide at
        an 8 s max hold — ~2x the scene-change rate — before the plan
        settles into the normal 6-15 s cruise."""
        pool = _scenes("fresh", 6)
        chapters = _chapters((0.0, "Intro"), (30.0, "Body"),
                             (90.0, "Deep Dive"))
        # 4 + 8 + 10 = 22 slots — under the 24-slot cap, so the merge
        # never coarsens the opening (an over-cap plan may: the ffmpeg
        # input cap outranks the pacing preference by design — see
        # test_open_acceleration_respects_slot_cap).
        plan = plan_chapter_schedule(pool, [], chapters, 240.0,
                                     max_hold_s=15.0, min_hold_s=6.0)
        acc = 0.0
        for _, dur in plan:
            if acc < 60.0 - 1e-9:
                assert dur <= 8.0 + 1e-9, (
                    f"slot starting at {acc:.1f}s holds {dur:.1f}s "
                    f"(> 8 s inside the first minute)"
                )
            acc += dur
        assert abs(math.fsum(d for _, d in plan) - 240.0) < 1e-6

    def test_cruise_holds_return_after_the_first_minute(self):
        """Chapters starting past 60 s keep the normal max hold — the
        acceleration is an OPENING treatment, not a global re-pace."""
        pool = _scenes("fresh", 6)
        chapters = _chapters((0.0, "Intro"), (60.0, "Body"))
        plan = plan_chapter_schedule(pool, [], chapters, 120.0,
                                     max_hold_s=15.0, min_hold_s=6.0)
        # The [60, 120) window subdivides at max_hold 15 → 4 x 15 s.
        tail = [d for _, d in plan[-4:]]
        assert all(abs(d - 15.0) < 1e-9 for d in tail)

    def test_open_acceleration_respects_slot_cap(self):
        """More opening slots must never push the plan past the ffmpeg
        input cap — the existing merge absorbs the extra slots."""
        from engine.scene_scheduler import _MAX_SLIDESHOW_SLOTS
        pool = _scenes("fresh", 4)
        starts = [0, 20, 40, 60, 150, 250, 350, 450, 550, 650, 750, 900]
        chapters = _chapters(*[(float(s), f"Ch{i}")
                               for i, s in enumerate(starts)])
        plan = plan_chapter_schedule(pool, [], chapters, 1044.0,
                                     max_hold_s=15.0, min_hold_s=6.0)
        assert len(plan) <= _MAX_SLIDESHOW_SLOTS
        assert abs(math.fsum(d for _, d in plan) - 1044.0) < 1e-6

    def test_chapter_boundaries_still_hit_exactly(self):
        """The opening acceleration subdivides WITHIN windows, so the
        cumulative plan still passes exactly through every boundary."""
        pool = _scenes("fresh", 5)
        chapters = _chapters((0.0, "Intro"), (30.0, "Deep Dive"),
                             (60.0, "Closing"))
        plan = plan_chapter_schedule(pool, [], chapters, 90.0)
        cumulative = set()
        acc = 0.0
        for _, dur in plan:
            acc += dur
            cumulative.add(round(acc, 6))
        assert 30.0 in cumulative
        assert 60.0 in cumulative


# ---------------------------------------------------------------------------
# Scene selection — token overlap, fresh tie-break, reuse variety
# ---------------------------------------------------------------------------

class TestSceneSelection:
    def test_token_overlap_picks_topical_scene_per_chapter(self):
        cyber = Path("/scenes/cybercab.png")
        star = Path("/scenes/starship.png")
        context = {
            cyber: "Cybercab robotaxi rolling off the factory line",
            star: "Starship stacked on the launch pad at Boca Chica",
        }
        chapters = _chapters(
            (0.0, "Tesla Cybercab factory update"),
            (20.0, "SpaceX Starship launch window"),
        )
        plan = plan_chapter_schedule([cyber, star], [], chapters, 40.0,
                                     scene_context=context)
        # 2 chapters × 20 s, both inside the accelerating-open window
        # (D1: max hold 8 s) → 3 slots each of ~6.67 s; the topical
        # scene still wins every slot of its own chapter.
        assert [p for p, _ in plan] == [cyber, cyber, cyber, star, star, star]

    def test_fresh_scene_wins_tie_over_library(self):
        fresh = _scenes("fresh", 1)
        library = _scenes("lib", 2)
        chapters = _chapters((0.0, "Intro"), (12.0, "Closing"))
        plan = plan_chapter_schedule(fresh, library, chapters, 24.0)
        assert plan[0][0] == fresh[0]

    def test_reuse_penalty_yields_rotation_variety(self):
        """With a context-less pool of 3, the plan should rotate
        through all three scenes with no back-to-back repeat. (D1: both
        chapters start < 60 s, so they subdivide at the 8 s opening max
        hold → 6 slots each = 12 picks.)"""
        pool = _scenes("fresh", 3)
        chapters = _chapters((0.0, "Intro"), (45.0, "Closing"))
        plan = plan_chapter_schedule(pool, [], chapters, 90.0)
        picks = [p for p, _ in plan]
        assert len(picks) == 12
        assert set(picks) == set(pool)
        for a, b in zip(picks, picks[1:]):
            assert a != b, f"back-to-back repeat of {a}"

    def test_deterministic(self):
        pool = _scenes("fresh", 4)
        library = _scenes("lib", 3)
        context = {pool[1]: "battery pack close-up",
                   library[0]: "gigafactory aerial view"}
        chapters = _chapters((0.0, "Battery day recap"),
                             (30.0, "Gigafactory expansion"),
                             (60.0, "Closing"))
        first = plan_chapter_schedule(pool, library, chapters, 90.0,
                                      scene_context=context)
        second = plan_chapter_schedule(pool, library, chapters, 90.0,
                                       scene_context=context)
        assert first == second

    def test_string_paths_accepted(self):
        """The gallery library may hand over str paths; they normalize
        to Path in the plan."""
        plan = plan_chapter_schedule(["/scenes/a.png", "/scenes/b.png"],
                                     [], None, 30.0)
        assert all(isinstance(p, Path) for p, _ in plan)


# ---------------------------------------------------------------------------
# sentence_cut_times — snap Shorts cuts to sentence ends
# ---------------------------------------------------------------------------

def _word(token, start, end):
    return {"word": token, "start": start, "end": end}


class TestSentenceCutTimes:
    def test_snaps_to_sentence_ends_within_cadence(self):
        """Absolute word times, window at 10 s: sentence ends at rel
        6.8 / 14.0 / 21.5 each fall inside the rolling [5, 9] band and
        become the cuts."""
        words = [
            _word(" Tesla", 12.0, 12.4),          # no punctuation — ignored
            _word(" ahead.", 16.4, 16.8),          # rel 6.8
            _word(" then", 20.0, 20.3),
            _word(" done.", 23.5, 24.0),           # rel 14.0
            _word(" wow!", 31.0, 31.5),            # rel 21.5
            _word(" tail?", 38.0, 38.6),           # rel 28.6 — beyond end guard
        ]
        cuts = sentence_cut_times(words, 10.0, 30.0)
        assert cuts == [6.8, 14.0, 21.5]

    def test_prefers_sentence_end_nearest_band_middle(self):
        """Two sentence ends inside one band: pick the one closest to
        the band midpoint (7 s into the gap), not simply the first."""
        words = [
            _word(" early.", 4.9, 5.2),
            _word(" late.", 6.5, 6.9),
        ]
        cuts = sentence_cut_times(words, 0.0, 20.0)
        assert cuts[0] == 6.9

    def test_flat_grid_fallback_when_no_sentence_ends(self):
        """No sentence-ending words at all → the legacy flat 7 s grid."""
        words = [_word(" and", i * 1.0, i * 1.0 + 0.4) for i in range(30)]
        assert sentence_cut_times(words, 0.0, 30.0) == [7.0, 14.0, 21.0]
        assert sentence_cut_times(None, 0.0, 30.0) == [7.0, 14.0, 21.0]

    def test_gap_without_sentence_end_uses_flat_step(self):
        """First band snaps to a sentence; the next band has no
        sentence end so it advances by the flat 7 s step."""
        words = [_word(" go.", 6.5, 6.9)]
        cuts = sentence_cut_times(words, 0.0, 20.0)
        assert cuts == [6.9, 13.9]

    def test_never_cuts_within_min_gap_of_clip_end(self):
        cuts = sentence_cut_times([], 0.0, 20.0, min_gap_s=5.0)
        assert cuts, "expected at least one flat-grid cut"
        assert all(c <= 20.0 - 5.0 for c in cuts)
        # A sentence end just before the clip end must not become a cut.
        words = [_word(" end.", 16.0, 16.5)]
        cuts = sentence_cut_times(words, 0.0, 20.0, min_gap_s=5.0)
        assert 16.5 not in cuts
        assert all(c <= 15.0 for c in cuts)

    def test_times_are_relative_to_clip_start(self):
        words = [_word(" mark.", 106.2, 106.5)]
        cuts = sentence_cut_times(words, 100.0, 30.0)
        assert cuts[0] == 6.5

    def test_zero_duration_returns_empty(self):
        assert sentence_cut_times([], 0.0, 0.0) == []

    def test_malformed_words_are_skipped(self):
        words = [
            {"word": " ok."},                       # no timestamps
            {"word": None, "start": 1, "end": 2},   # no token
            _word(" fine.", 6.6, 6.9),
        ]
        cuts = sentence_cut_times(words, 0.0, 20.0)
        assert cuts[0] == 6.9
