"""Video pass from the Oct 18 2026 flagship rehearsals.

Three rehearsal renders (SpaceX Ep134, Tesla Ep638, FF Ep226) measured
frame by frame, then checked against the last week of committed episodes:

1. one picture held for 74 s on FF (a story's own image won every slot of
   its chapter, and the slot cap merged identical neighbours first);
2. fact-card labels that did not read ("Of U .S", "% means claims are
   already", "1 gigawatt / Hour");
3. 56 of 70 hook Shorts cut mid-sentence at a fixed 35 s;
4. Whisper's split tokens in the burned-in captions ("107 .6 % loss");
5. the outro card said "All 16 shows" (26 free shows);
6. the $0.28 hook motion clip ran with no same-show control;
7. Tesla/SpaceX rendered an Instagram/TikTok variant nothing ever posted.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from types import SimpleNamespace

import yaml

from engine import fact_cards as fc
from engine.scene_scheduler import _MAX_SLIDESHOW_SLOTS, _cap_slots, plan_chapter_schedule

ROOT = Path(__file__).resolve().parents[1]


def _chapters(*starts_titles):
    return [{"startTime": s, "title": t} for s, t in starts_titles]


def _runs(plan):
    runs = []
    for path, dur in plan:
        if runs and runs[-1][0] == path:
            runs[-1][1] += dur
        else:
            runs.append([path, dur])
    return runs


def _w(tokens, start=10.0, step=0.5):
    out, t = [], start
    for tok in tokens:
        out.append({"word": tok, "start": round(t, 2), "end": round(t + step, 2)})
        t += step
    return out


# ---------------------------------------------------------------------------
# 1. Long-form scene plan
# ---------------------------------------------------------------------------

class TestNoLongSinglePictureHolds:
    def _ff_shape(self):
        medal = Path("/s/medal.png")
        rocket = Path("/s/rocket.png")
        lib = [Path("/s/lib_astro.png"), Path("/s/lib_moon.png")]
        context = {
            medal: "Artemis astronauts receive the Hawking medal on stage",
            rocket: "Rocket booster on the launch pad at dawn",
            lib[0]: "Astronauts in white suits under studio lights",
            lib[1]: "The Moon over a quiet desert",
        }
        chapters = _chapters(
            (0.0, "Introduction"),
            (75.0, "Artemis crew receives Hawking medal"),
            (150.0, "Rocket launch window"),
        )
        return medal, rocket, lib, context, chapters

    def test_a_story_image_alternates_with_a_fitting_library_scene(self):
        medal, rocket, lib, context, chapters = self._ff_shape()
        plan = plan_chapter_schedule([medal, rocket], lib, chapters, 220.0,
                                     scene_context=context)
        t, chapter_two = 0.0, []
        for path, dur in plan:
            if 75.0 <= t < 150.0:
                chapter_two.append(path)
            t += dur
        assert medal in chapter_two
        for a, b in zip(chapter_two, chapter_two[1:]):
            assert a != b, "one picture held across two slots of its chapter"
        # The image of the OTHER story never fills in.
        assert rocket not in chapter_two

    def test_nothing_fits_the_image_still_holds(self):
        """Two stories, no library: the old rule stands (topical beats
        variety) — the guard is against an unrelated image, not repeats."""
        cyber = Path("/s/cybercab.png")
        star = Path("/s/starship.png")
        context = {cyber: "Cybercab robotaxi factory line",
                   star: "Starship on the launch pad"}
        chapters = _chapters((0.0, "Tesla Cybercab factory update"),
                             (20.0, "SpaceX Starship launch window"))
        plan = plan_chapter_schedule([cyber, star], [], chapters, 40.0,
                                     scene_context=context)
        assert [p for p, _ in plan] == [cyber, cyber, cyber, star, star, star]

    def test_the_cap_never_merges_into_a_run_when_another_merge_exists(self):
        a, b, c = Path("/a"), Path("/b"), Path("/c")
        # Before Oct 18 the shortest pair (b, a) merged first and left
        # a, b, b — a run of one picture the picker had just avoided.
        plan = [(a, 70.0), (b, 10.0), (a, 10.0), (c, 30.0), (b, 30.0)]
        out = _cap_slots(plan, max_slots=4)
        assert len(out) == 4
        assert abs(math.fsum(d for _, d in out) - 150.0) < 1e-9
        for (p, _), (q, _) in zip(out, out[1:]):
            assert p != q

    def test_long_episode_never_repeats_a_picture_back_to_back(self):
        """A 17-minute episode under the 36-slot cap averages ~29 s a slot;
        the plan this replaced held one picture 86 s on this shape."""
        pool = [Path(f"/fresh{i}.png") for i in range(4)]
        lib = [Path(f"/lib{i}.png") for i in range(3)]
        context = {p: f"story {i} topic" for i, p in enumerate(pool)}
        context.update({p: "network library scene" for p in lib})
        starts = [0, 60, 150, 250, 350, 450, 550, 650, 750, 900, 1000]
        chapters = _chapters(*[(float(s), f"Story {i} topic")
                               for i, s in enumerate(starts)])
        plan = plan_chapter_schedule(pool, lib, chapters, 1044.0,
                                     scene_context=context)
        assert len(plan) <= _MAX_SLIDESHOW_SLOTS
        assert len(_runs(plan)) == len(plan)
        assert max(d for _, d in plan) <= 75.0


# ---------------------------------------------------------------------------
# 2. Fact-card labels
# ---------------------------------------------------------------------------

def _cards(tokens):
    return fc.extract_fact_cards(_w(tokens), open_skip_s=0)


class TestFactCardsRead:
    def test_a_split_percent_sign_joins_the_figure(self):
        cards = _cards(["fell", "100", "%", "this", "quarter", "for", "the", "fleet."])
        assert cards and cards[0].figure == "100%"

    def test_compound_units_join_the_figure(self):
        for tokens, figure in (
            (["delivered", "1", "gigawatt", "hour", "of", "storage", "to", "Texas."], "1 GWh"),
            (["at", "230", "miles", "per", "hour", "on", "the", "track."], "230 mph"),
            (["at", "28,000", "km", "per", "hour", "in", "low", "orbit."], "28,000 km/h"),
            (["a", "1.7", "million", "square", "feet", "factory", "in", "Texas."], "1.7 million sq ft"),
            (["sits", "37", "million", "light", "-years", "away", "from", "Earth."], "37 million light-years"),
            (["a", "6.08", "million", "euros", "fine", "in", "Germany."], "6.08 million euros"),
        ):
            cards = _cards(tokens)
            assert cards and cards[0].figure == figure, (tokens, cards)

    def test_the_label_stops_at_its_clause(self):
        cards = _cards(["used", "1,680", "processors", "for", "59", "days,",
                        "yet", "advanced", "only", "a", "little."])
        assert cards and cards[0].label == "Processors for 59 days"

    def test_a_label_that_runs_into_a_credit_is_dropped(self):
        cards = _cards(["about", "1,181", "Universe", "Today", "reports", "here."])
        assert not cards or "Universe" not in cards[0].label

    def test_a_fragment_label_on_a_bare_number_drops_the_card(self):
        assert _cards(["the", "7,000", "of", "U", ".S", "drivers", "said", "so."]) == []

    def test_a_time_of_day_is_never_a_card(self):
        assert _cards(["at", "755", "in", "the", "evening", "Central", "Time."]) == []

    def test_a_unit_figure_stands_alone_when_its_label_does_not_read(self):
        cards = _cards(["the", "$5,000", "and", "the", "remaining", "balance", "later."])
        assert cards and cards[0].figure == "$5,000" and cards[0].label == ""

    def test_a_plural_noun_joins_a_bare_figure(self):
        cards = _cards(["about", "500", "repos", "and", "start", "large", "builds."])
        assert cards and cards[0].figure == "500 repos"

    def test_split_hyphens_and_percents_rejoin_inside_a_label(self):
        cards = _cards(["cut", "$4", "billion", "for", "end", "-to", "-end", "agent", "work."])
        assert cards and "end-to-end" in cards[0].label

    def test_a_percent_never_takes_a_count_noun(self):
        cards = _cards(["rose", "9.35%", "year", "over", "year", "in", "September."])
        assert cards and cards[0].figure == "9.35%"


# ---------------------------------------------------------------------------
# 3. Shorts end on a sentence
# ---------------------------------------------------------------------------

class TestShortsEndOnASentence:
    def test_the_short_ends_on_the_last_full_sentence(self):
        from engine.shorts_selector import SENTENCE_END_PAD_S, end_on_sentence
        words = [{"word": "first.", "start": 10.0, "end": 10.5},
                 {"word": "second.", "start": 31.0, "end": 31.6},
                 {"word": "cut", "start": 34.5, "end": 35.4}]
        assert end_on_sentence(words, 0.0, 35.0) == round(31.6 + SENTENCE_END_PAD_S, 2)

    def test_the_music_offset_moves_the_words(self):
        from engine.shorts_selector import SENTENCE_END_PAD_S, end_on_sentence
        words = [{"word": "done.", "start": 28.0, "end": 29.0}]
        assert end_on_sentence(words, 2.0, 35.0, audio_offset_s=2.0) == round(
            29.0 + SENTENCE_END_PAD_S, 2)

    def test_no_sentence_end_near_the_limit_keeps_the_full_length(self):
        from engine.shorts_selector import end_on_sentence
        words = [{"word": "early.", "start": 5.0, "end": 5.5}]
        assert end_on_sentence(words, 0.0, 35.0) == 35.0
        assert end_on_sentence([], 0.0, 35.0) == 35.0

    def test_run_show_ends_every_short_on_a_sentence_and_records_it(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        loop = src.index("for short_idx, (this_offset, this_hook, _fill_mode) in enumerate(shorts_plan):")
        assert "end_on_sentence(" in src[loop:loop + 1200]
        assert 'result["short_durations"]' in src
        pipe = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert '"short_durations"' in pipe


# ---------------------------------------------------------------------------
# 4. Captions rejoin Whisper's split tokens
# ---------------------------------------------------------------------------

class TestCaptionTokensRejoin:
    def test_merge_split_words(self):
        from engine.captions import merge_split_words
        words = [{"word": "a", "start": 0.0, "end": 0.2},
                 {"word": "107", "start": 0.2, "end": 0.5},
                 {"word": ".6", "start": 0.5, "end": 0.7},
                 {"word": "%", "start": 0.7, "end": 0.9},
                 {"word": "over", "start": 1.0, "end": 1.2},
                 {"word": "-the", "start": 1.2, "end": 1.3},
                 {"word": "-air", "start": 1.3, "end": 1.6}]
        out = merge_split_words(words)
        assert [w["word"] for w in out] == ["a", "107.6%", "over-the-air"]
        assert out[1]["start"] == 0.2 and out[1]["end"] == 0.9

    def test_a_standalone_dash_is_left_alone(self):
        from engine.captions import join_split_text
        assert join_split_text("a - b") == "a - b"
        assert join_split_text("14 ,371 units at 3.7 %") == "14,371 units at 3.7%"

    def test_the_chunker_merges_before_it_lays_out(self):
        from engine.captions import _chunk_words
        chunks = _chunk_words(
            [{"word": "107", "start": 0, "end": 1}, {"word": ".6", "start": 1, "end": 2}],
            max_chars=24, max_words_per_chunk=8)
        assert [w["word"] for c in chunks for w in c] == ["107.6"]


# ---------------------------------------------------------------------------
# 5. The outro card's show count
# ---------------------------------------------------------------------------

class TestOutroShowCount:
    def test_no_hardcoded_show_count(self):
        src = (ROOT / "engine" / "promo_card.py").read_text(encoding="utf-8")
        assert '"sub": "All 16 shows' not in src and "All {count} free shows" in src

    def test_the_count_comes_from_the_free_show_filter(self, monkeypatch):
        from engine import promo_card
        monkeypatch.setattr(promo_card, "free_show_count", lambda: 26)
        assert promo_card._texts("en")["sub"].startswith("All 26 free shows")
        monkeypatch.setattr(promo_card, "free_show_count", lambda: 0)
        assert promo_card._texts("en")["sub"].startswith("Every show")

    def test_a_workflow_refreshes_the_screenshots(self):
        wf = yaml.safe_load((ROOT / ".github" / "workflows" / "capture-site-screens.yml")
                            .read_text(encoding="utf-8"))
        steps = wf["jobs"]["capture"]["steps"]
        assert any("capture_site_screens.py" in str(s.get("run", "")) for s in steps)
        commit = [s for s in steps if "safe-commit-push" in str(s.get("uses", ""))]
        assert commit and commit[0]["with"]["add-paths"] == "assets/site_screens/*.png"


# ---------------------------------------------------------------------------
# 6. The motion clip runs on alternate days
# ---------------------------------------------------------------------------

def _motion_cfg(alternate=True):
    return SimpleNamespace(youtube=SimpleNamespace(
        hook_short_motion=True, hook_short_motion_alternate=alternate,
        hook_short_motion_seconds=4, hook_short_motion_max_cost_usd=0.30,
        hook_short_motion_budget_seconds=150.0))


class TestMotionClipAlternates:
    def test_odd_days_are_the_control(self, tmp_path):
        from engine import hook_short_motion as hm
        odd = next(dt.date(2026, 10, 19) + dt.timedelta(days=i) for i in range(2)
                   if (dt.date(2026, 10, 19) + dt.timedelta(days=i)).toordinal() % 2 == 1)
        out = hm.plan_hook_motion(_motion_cfg(), work_dir=tmp_path, episode_num=1,
                                  hook="A hook", episode_date=odd)
        assert out.control and not out.requested and out.clip_path is None
        assert out.variant == hm.VARIANT_CONTROL_STILLS
        assert hm.is_control_day(_motion_cfg(), odd + dt.timedelta(days=1)) is False

    def test_alternation_is_off_when_the_flag_is_off(self):
        from engine import hook_short_motion as hm
        assert hm.is_control_day(_motion_cfg(alternate=False), dt.date(2026, 10, 19)) is False
        assert hm.is_control_day(_motion_cfg(), None) is False

    def test_the_network_default_alternates_and_the_field_is_declared(self):
        raw = yaml.safe_load((ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert raw["youtube"]["hook_short_motion_alternate"] is True
        from engine.config import YouTubeConfig
        assert hasattr(YouTubeConfig(), "hook_short_motion_alternate")

    def test_run_show_passes_the_date_and_keeps_the_control_label(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "episode_date=today," in src
        assert "VARIANT_CONTROL_BROLL" in src and "VARIANT_CONTROL_STILLS" in src

    def test_dashboard_reads_motion_against_control(self, tmp_path):
        import importlib
        dash = importlib.import_module("scripts.generate_dashboard")
        vids = ([{"channel": "en", "variant": "motion_open", "views_by_age": {"3": 60}}] * 10
                + [{"channel": "en", "variant": "control_stills", "views_by_age": {"3": 40}}] * 10)
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "youtube_early_reach.json").write_text(
            json.dumps({"videos": vids}), encoding="utf-8")
        assert dash._hook_motion_ab_ratio(tmp_path) == 1.5
        (tmp_path / "api" / "youtube_early_reach.json").write_text(
            json.dumps({"videos": vids[:12]}), encoding="utf-8")
        assert dash._hook_motion_ab_ratio(tmp_path) is None


# ---------------------------------------------------------------------------
# 7. No social variant without the secrets to post it
# ---------------------------------------------------------------------------

class TestNoUnpostedSocialVariant:
    def test_a_social_variant_needs_a_posting_secret_in_some_workflow(self):
        workflows = " ".join(p.read_text(encoding="utf-8")
                             for p in (ROOT / ".github" / "workflows").glob("*.yml"))
        can_post = ("secrets.IG_ACCESS_TOKEN" in workflows
                    or "secrets.TIKTOK_ACCESS_TOKEN" in workflows)
        if can_post:
            return
        for path in (ROOT / "shows").glob("*.yaml"):
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            yt = raw.get("youtube") or {}
            assert not yt.get("multi_platform_enabled"), (
                f"{path.name} renders an Instagram/TikTok variant that no "
                "workflow can post")
