"""Oct 15 2026: @nerranetwork asks for follows, lightly, and the long-form
render is budgeted from what it measurably takes.

Follow ask: every network post had ended on one identical closer and none
asked anyone to follow. engine.x_post now rotates the closer and, on about
one post in four, swaps in a one-sentence follow ask. The ask is decided by
the calendar and the show's place in the posting order, never clips a hook,
and every closer list ends on the closer the posts used before. (Oct 17
2026: the posting order is the X slot order from engine.release_schedule;
tests/test_x_edition_slot_and_follow_phase_2026_10_17.py proves the
guarantee over 60 days.)

Render budget: Models & Agents Ep204 started a long-form render with 1,189 s
left after the commit reserve, rendered for 1,493 s, uploaded the long-form
to YouTube and died on the pipeline alarm before committing anything. The
guard had compared the time left with a fixed 600 s; renders take about
twice the audio length (median 1.91x, p90 2.05x over 60 renders, Oct 8-15).
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import yaml

from engine import x_post
from engine.video import (LONG_FORM_RENDER_SECONDS_PER_AUDIO_SECOND,
                          estimate_long_form_render_seconds)

ROOT = Path(__file__).resolve().parent.parent
START = dt.date(2026, 10, 15)
DAYS = [START + dt.timedelta(days=i) for i in range(56)]
DAILY = [s for s, wd in x_post.FOLLOW_ASK_ROSTER if wd is None]


def _asks(slug, day):
    return x_post.post_closers(slug, day)[0] in x_post.FOLLOW_ASK_CLOSERS


class TestRoster:
    def _network_clip_posters(self):
        out = set()
        for path in sorted((ROOT / "shows").glob("*.yaml")):
            if path.name.startswith("_"):
                continue
            pub = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("publishing") or {}
            if (pub.get("x_enabled") and str(pub.get("x_env_prefix", "")).strip() == "NERRANETWORK_X_"
                    and pub.get("x_post_format") == "clip"):
                out.add(path.stem)
        return out

    def test_every_network_clip_poster_is_on_the_roster(self):
        posters = self._network_clip_posters()
        assert posters, "no show posts to @nerranetwork through the clip path?"
        missing = posters - set(x_post._roster_slugs())
        assert not missing, (
            f"{sorted(missing)} post to @nerranetwork but are not in "
            "engine.x_post.FOLLOW_ASK_CADENCE — add each with its cadence; its "
            "place in the order comes from engine.release_schedule (Oct 17 2026)")

    def test_nerra_daily_is_on_the_roster(self):
        assert "nerra_daily" in x_post._roster_slugs()

    def test_weekly_shows_carry_their_cron_weekday(self):
        cron = (ROOT / ".github/workflows/run-show.yml").read_text(encoding="utf-8")
        names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for slug, wd in x_post.FOLLOW_ASK_ROSTER:
            m = re.search(rf'\("{slug}",\s*(None|"(\w+)")\)', cron)
            if slug == "nerra_daily":
                continue
            assert m, f"{slug} not found in run-show.yml CRON_MAP"
            expected = None if m.group(1) == "None" else names.index(m.group(2))
            assert wd == expected, f"{slug}: roster weekday {wd}, cron says {expected}"


class TestTheAskIsLight:
    def test_about_one_post_in_four_asks(self):
        for slug in DAILY:
            n = sum(_asks(slug, d) for d in DAYS)
            assert n == len(DAYS) // x_post.FOLLOW_ASK_EVERY, (slug, n)

    def test_a_daily_show_never_asks_two_days_running(self):
        for slug in DAILY:
            for a, b in zip(DAYS, DAYS[1:]):
                assert not (_asks(slug, a) and _asks(slug, b)), (slug, a)

    def test_posting_neighbours_never_ask_on_the_same_day(self):
        for day in DAYS:
            posting = [s for s, wd in x_post.FOLLOW_ASK_ROSTER
                       if wd is None or wd == day.weekday()]
            for a, b in zip(posting, posting[1:]):
                assert not (_asks(a, day) and _asks(b, day)), (day, a, b)

    def test_ask_lines_are_one_plain_sentence_with_the_episode_pointer(self):
        for line in x_post.FOLLOW_ASK_CLOSERS:
            low = line.lower()
            assert "follow" in low
            assert "bio" in low, "every ask still says where the episode is"
            assert "!" not in line and "please" not in low
            assert not re.search(r"https?://|\b[\w-]+\.(com|net|org|io|ai)\b", line)
            assert len(line) <= 90

    def test_closer_rotation_never_repeats_the_same_line_daily(self):
        lines = {x_post.post_closers("omni_view", d)[0] for d in DAYS[:12]}
        assert len(lines) >= 3

    def test_an_unlisted_show_keeps_the_old_closer(self):
        assert x_post.post_closers("age_of_ai", START) == (x_post.CLIP_CLOSER,)


class TestTheAskNeverCostsTheHook:
    def test_every_closer_list_ends_on_the_old_closer(self):
        for slug in x_post._roster_slugs():
            for day in DAYS[:8]:
                assert x_post.post_closers(slug, day)[-1] == x_post.CLIP_CLOSER

    def _ask_day(self, slug):
        return next(d for d in DAYS if _asks(slug, d))

    def test_a_hook_that_fits_carries_the_ask(self):
        day = self._ask_day("spacex")
        hook = "SpaceX is guaranteeing to cover any Grok Bot purchase errors to encourage wider use of the AI assistant for shopping."
        text = x_post.clip_post_text(label="🚀 SpaceX Daily", hook=hook, episode_num=131,
                                     closers=x_post.post_closers("spacex", day))
        assert x_post.has_follow_ask(text)
        assert hook in text

    def test_a_long_hook_drops_the_ask_and_stays_whole(self):
        day = self._ask_day("modern_investing")
        hook = ("Canadian investors can simplify their TFSA planning by contributing the "
                "$7,000 room earlier than December, even if the immediate tax saving is "
                "smaller, and a second sentence long enough to crowd the post.")[:175]
        before = x_post.clip_post_text(label="📈💰 Modern Investing Techniques", hook=hook,
                                       episode_num=200)
        after = x_post.clip_post_text(label="📈💰 Modern Investing Techniques", hook=hook,
                                      episode_num=200,
                                      closers=x_post.post_closers("modern_investing", day))
        assert not x_post.has_follow_ask(after)
        # the hook text is never shorter than it was with the old closer
        assert len(after.split("\n\n")[1]) >= len(before.split("\n\n")[1])
        assert len(after) <= x_post.CLIP_TEXT_MAX


class TestWiring:
    def test_run_show_passes_the_closers_and_records_the_ask(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "closers=post_closers(config.slug, today)" in src
        assert 'metrics.record("x_post_follow_ask", has_follow_ask(_x_text))' in src

    def test_nerra_daily_uses_the_edition_date(self):
        src = (ROOT / "scripts/build_daily_edition.py").read_text(encoding="utf-8")
        fn = src[src.index("def post_edition_to_x("):src.index("def main(")]
        assert "post_closers(" in fn and "spec.slug" in fn
        assert "day=target_date" in src

    def test_the_metric_is_registered(self):
        reg = yaml.safe_load((ROOT / "docs/experiments.yaml").read_text(encoding="utf-8"))
        entries = reg if isinstance(reg, list) else reg.get("experiments", [])
        ids = {e.get("id") for e in entries}
        assert "x-follow-ask-2026-10-15" in ids
        assert "long-form-render-budget-2026-10-15" in ids


class TestRenderBudget:
    def test_the_estimate_is_the_measured_ratio_with_a_floor(self):
        assert LONG_FORM_RENDER_SECONDS_PER_AUDIO_SECOND >= 2.05  # the measured p90
        assert estimate_long_form_render_seconds(0) == 600
        assert estimate_long_form_render_seconds(None) == 600
        assert estimate_long_form_render_seconds(200) == 600
        assert round(estimate_long_form_render_seconds(759)) == round(759 * LONG_FORM_RENDER_SECONDS_PER_AUDIO_SECOND)

    def test_models_agents_ep204_would_have_skipped_the_render(self):
        """1,189 s available after the reserve, 759 s of audio."""
        assert estimate_long_form_render_seconds(759) > 1189

    def test_run_show_guards_on_the_estimate(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        guard = src.split("_render_long = _policy_publish_long", 1)[1][:4000]
        assert "estimate_long_form_render_seconds(" in guard
        assert "floor_seconds=_LONG_FORM_RENDER_BUDGET_S" in guard
        assert "if _long_render_budget < _long_render_need:" in guard
        assert "LONG_FORM_RENDER_SECONDS_PER_AUDIO_SECOND" in src

    def test_the_need_is_on_the_metrics_allowlist(self):
        src = (ROOT / "engine/pipeline.py").read_text(encoding="utf-8")
        assert '"long_form_render_need_s"' in src
