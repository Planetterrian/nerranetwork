"""Old posts stop being rewritten every day (Nov 3 2026).

``git log --since=2026-10-27 --until=2026-11-03 --name-only -- blog`` counted
32,647 ``blog/`` rewrites in seven days. Tesla's plain show commit fb848782e
touched 264 files, 258 of them old posts, and the only change in each was
the three "You Might Also Like" cards: ``_pick_cross_show_related`` sampled
the NEWEST cross-show posts whatever the post's own date, so every post in
the network changed every morning by design.

Now a post recommends its OWN WEEK (``post_date``: seven days before it to
one day after), the pool is the whole archive so an October post has
October to choose from, and the per-show regen after a show run renders
the newest posts only (``--latest``); the nightly's full rebuild stays the
path a template change reaches old posts by.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pytest

import generate_html as G

ROOT = Path(__file__).resolve().parent.parent
SMALL_SHOW = "offshore_north"  # a dozen committed episodes


def _row(slug: str, ep: int, day: str) -> dict:
    return {
        "show_slug": slug, "show_name": slug, "show_color": "#336699",
        "title": f"{slug} ep{ep}", "hook": f"{slug} hook {ep}",
        "episode_num": ep, "url": f"../../blog/{slug}/ep{ep:03d}.html",
        "date": day, "date_iso": day,
    }


def _pool(*, start: date, days: int = 60) -> list[dict]:
    """One post per show per day on four other shows, newest first."""
    rows = []
    for n in range(days):
        day = (start - timedelta(days=n)).isoformat()
        for slug in ("spacex", "omni_view", "models_agents", "planetterrian"):
            rows.append(_row(slug, 500 - n, day))
    return rows


def _iso(p: dict) -> date:
    return date.fromisoformat(p["date_iso"])


class TestAPostRecommendsItsOwnWeek:
    def test_every_pick_sits_inside_the_window(self):
        post_day = date(2026, 9, 15)
        picks = G._pick_cross_show_related(
            "tesla", _pool(start=date(2026, 10, 1)), seed="ep600",
            post_date=post_day.isoformat())
        assert len(picks) == 3
        lo = post_day - timedelta(days=G.RELATED_WINDOW_BEFORE_DAYS)
        hi = post_day + timedelta(days=G.RELATED_WINDOW_AFTER_DAYS)
        assert all(lo <= _iso(p) <= hi for p in picks), picks

    def test_a_post_dated_today_sees_only_a_day_around_it(self):
        today = date(2026, 10, 1)
        pool = _pool(start=today)
        picks = G._pick_cross_show_related("tesla", pool, seed="ep651",
                                           post_date=today.isoformat())
        assert picks and all(today - timedelta(days=7) <= _iso(p) <= today for p in picks)
        # The next morning's sibling episode is within a day: allowed.
        tomorrow = _row("spacex", 998, (today + timedelta(days=1)).isoformat())
        # Two days on is not — however new and however much the pool grows.
        later = _row("spacex", 999, (today + timedelta(days=2)).isoformat())
        picks = G._pick_cross_show_related("tesla", [later, tomorrow] + pool,
                                           seed="ep651", post_date=today.isoformat())
        assert all(p["episode_num"] != 999 for p in picks)
        assert all(_iso(p) <= today + timedelta(days=1) for p in picks)

    def test_the_curated_sibling_still_leads(self):
        curated = G.NETWORK_SHOWS["tesla"]["related_show"]
        pool = _pool(start=date(2026, 10, 1))
        pool.append(_row(curated, 7, "2026-09-14"))
        picks = G._pick_cross_show_related("tesla", pool, seed="ep600",
                                           post_date="2026-09-15")
        assert picks[0]["show_slug"] == curated

    def test_a_newer_episode_changes_nothing_older_than_a_day(self):
        """The whole point: the pool gaining this morning's episode leaves
        every post older than a day with the recommendations it had."""
        pool = _pool(start=date(2026, 10, 1))
        posts = {f"ep{600 + n}": (date(2026, 9, 29) - timedelta(days=n)).isoformat()
                 for n in range(40)}
        before = {stem: G._pick_cross_show_related("tesla", pool, seed=stem, post_date=d)
                  for stem, d in posts.items()}
        grown = [_row("spacex", 999, "2026-10-01"), _row("fascinating_frontiers", 300, "2026-10-01")] + pool
        after = {stem: G._pick_cross_show_related("tesla", grown, seed=stem, post_date=d)
                 for stem, d in posts.items()}
        assert before == after

    def test_nearest_first_the_day_before_ahead_of_the_day_after(self):
        """A weekday post with a dozen same-day siblings is drawn from its
        own day; the next morning's episodes, a day away, never re-draw it."""
        post_day = date(2026, 10, 6)
        shows = [f"show{i}" for i in range(14)]
        same_day = [_row(s, 10, post_day.isoformat()) for s in shows]
        day_before = [_row(s, 9, (post_day - timedelta(days=1)).isoformat()) for s in shows]
        first_render = day_before + same_day
        picks = G._pick_cross_show_related("tesla", first_render, seed="ep630",
                                           post_date=post_day.isoformat())
        assert all(_iso(p) == post_day for p in picks)
        next_morning = [_row(s, 11, (post_day + timedelta(days=1)).isoformat()) for s in shows]
        assert G._pick_cross_show_related("tesla", next_morning + first_render, seed="ep630",
                                          post_date=post_day.isoformat()) == picks
        # With fewer than a dozen on its own day the day before fills in
        # ahead of the day after.
        thin = day_before[:5] + same_day[:3] + next_morning[:5]
        ordered = G._contemporaneous(thin, post_day.isoformat())
        assert [_iso(p) for p in ordered[:8]] == [post_day] * 3 + [post_day - timedelta(days=1)] * 5

    def test_undated_call_keeps_the_old_behaviour(self):
        """tests/test_blog.py and test_capture_measurement call it with no
        date and undated rows; nothing there may move."""
        pool = _pool(start=date(2026, 10, 1))
        undated = [{"show_slug": "other", "n": i} for i in range(20)]
        assert (G._pick_cross_show_related("tesla", pool, seed="ep600")
                == G._pick_cross_show_related("tesla", pool, seed="ep600", post_date=""))
        picks = G._pick_cross_show_related("tesla", undated, seed="ep600")
        assert len(picks) == 3 and all(p["n"] < 12 for p in picks)

    def test_an_unparseable_date_keeps_the_old_behaviour(self):
        pool = _pool(start=date(2026, 10, 1))
        assert (G._pick_cross_show_related("tesla", pool, seed="ep600", post_date="October 6")
                == G._pick_cross_show_related("tesla", pool, seed="ep600"))

    def test_a_post_with_nothing_in_its_window_takes_what_came_before(self):
        pool = _pool(start=date(2026, 10, 1), days=10)  # Sep 22 .. Oct 1
        picks = G._pick_cross_show_related("tesla", pool, seed="ep700",
                                           post_date="2026-11-20")
        assert len(picks) == 3
        newest_twelve = {(p["show_slug"], p["episode_num"]) for p in pool[:12]}
        assert all((p["show_slug"], p["episode_num"]) in newest_twelve for p in picks)
        # The network's first posts have nothing before them: the nearest after.
        picks = G._pick_cross_show_related("tesla", pool, seed="ep001",
                                           post_date="2026-01-01")
        oldest_twelve = {(p["show_slug"], p["episode_num"]) for p in pool[-12:]}
        assert picks and all((p["show_slug"], p["episode_num"]) in oldest_twelve for p in picks)

    def test_undated_rows_are_never_placed_in_a_window(self):
        pool = _pool(start=date(2026, 10, 1)) + [{"show_slug": "spacex", "episode_num": 1, "date_iso": ""}]
        picks = G._pick_cross_show_related("tesla", pool, seed="ep600", post_date="2026-09-15")
        assert all(p.get("date_iso") for p in picks)


class TestRenderingTwiceWithAGrownPool:
    def test_posts_older_than_the_new_episode_are_byte_identical(self, tmp_path):
        pool = G._cross_show_pool()
        assert pool
        one = tmp_path / "one"
        G.generate_blog_posts(SMALL_SHOW, output_dir=one, cross_show_posts=pool)
        newest = max(p["date_iso"] for p in pool if p["date_iso"])
        new_day = (date.fromisoformat(newest) + timedelta(days=2)).isoformat()
        grown = [_row("spacex", 9999, new_day)] + pool
        two = tmp_path / "two"
        G.generate_blog_posts(SMALL_SHOW, output_dir=two, cross_show_posts=grown)
        files = sorted((one / "blog" / SMALL_SHOW).glob("ep*.html"))
        assert files
        for f in files:
            assert f.read_bytes() == (two / "blog" / SMALL_SHOW / f.name).read_bytes(), f.name


class TestThePoolIsTheArchive:
    def test_rows_keep_their_shape_and_order(self):
        pool = G._cross_show_pool()
        assert pool
        for row in pool[:50]:
            assert {"show_slug", "show_name", "show_color", "title", "hook",
                    "episode_num", "url", "date", "date_iso"} <= set(row)
            assert re.fullmatch(r"\.\./\.\./blog/[a-z0-9_]+/ep\d{3}\.html", row["url"])
        assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", p["date_iso"]) for p in pool if p["date_iso"])
        dates = [p["date_iso"] for p in pool]
        assert dates == sorted(dates, reverse=True)

    def test_it_reaches_back_past_the_last_six_with_one_row_per_episode(self):
        pool = G._cross_show_pool()
        per_show = Counter(p["show_slug"] for p in pool)
        assert per_show["tesla"] > 6, "the pool is the last six again — an October post has no October"
        keys = [(p["show_slug"], p["episode_num"]) for p in pool]
        assert len(keys) == len(set(keys))

    def test_the_walk_never_reads_a_members_episode(self, tmp_path, monkeypatch):
        """The Oct 13 gated-shows rule: a consumer that globs a show's
        digests must skip members/."""
        show_dir = tmp_path / "digests" / G._SHOW_DIRS["tesla"]
        (show_dir / "members").mkdir(parents=True)
        body = ("# Tesla Shorts Time\n**Date:** {date}\n\n> **A hook sentence for the card.**\n\n"
                "### Top News\n1. **An item** — Outlet\n   One sentence. Source: https://example.com/a\n")
        (show_dir / "Tesla_Shorts_Time_Pod_Ep001_20260101.md").write_text(
            body.format(date="January 01, 2026"), encoding="utf-8")
        (show_dir / "members" / "Tesla_Shorts_Time_Pod_Ep002_20260102.md").write_text(
            body.format(date="January 02, 2026"), encoding="utf-8")
        monkeypatch.setattr(G, "ROOT", tmp_path)
        pool = G._cross_show_pool()
        assert {(p["show_slug"], p["episode_num"]) for p in pool} == {("tesla", 1)}
        assert pool[0]["date_iso"] == "2026-01-01"


class TestTheIncrementalRender:
    def _episodes(self):
        from engine.blog import extract_blog_metadata
        digest_dir = ROOT / "digests" / G._SHOW_DIRS.get(SMALL_SHOW, SMALL_SHOW)
        eps = set()
        for md in digest_dir.glob("*.md"):
            meta = extract_blog_metadata(md.read_text(encoding="utf-8"), SMALL_SHOW, md.name, file_path=md)
            eps.add(meta["episode_num"])
        return sorted(eps)

    def test_latest_renders_the_newest_posts_and_the_one_before(self, tmp_path):
        eps = self._episodes()
        assert len(eps) >= 4
        results = G.generate_blog_posts(SMALL_SHOW, output_dir=tmp_path,
                                        cross_show_posts=[], latest=2)
        expected = eps[-3:]
        assert sorted(m["episode_num"] for m, _ in results) == expected
        written = sorted(p.name for p in (tmp_path / "blog" / SMALL_SHOW).glob("ep*.html"))
        assert written == [f"ep{e:03d}.html" for e in expected]
        # The neighbour is rendered because its next-episode link changed.
        oldest = (tmp_path / "blog" / SMALL_SHOW / f"ep{expected[0]:03d}.html").read_text(encoding="utf-8")
        assert f"ep{expected[1]:03d}.html" in oldest

    def test_without_latest_every_post_renders(self, tmp_path):
        eps = self._episodes()
        results = G.generate_blog_posts(SMALL_SHOW, output_dir=tmp_path, cross_show_posts=[])
        assert sorted(m["episode_num"] for m, _ in results) == eps

    def test_the_flag_reaches_the_per_show_branch(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert '"--latest"' in src
        assert "latest=args.latest" in src

    def test_both_call_sites_pass_the_posts_date_and_keep_the_seed(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        body = src.split("def generate_blog_posts(", 1)[1].split("\ndef ", 1)[0]
        assert 'seed=meta["_md_path"].stem' in body
        assert 'post_date=meta.get("date_iso", "")' in body
        blog = (ROOT / "engine" / "blog.py").read_text(encoding="utf-8")
        assert 'post_date=metadata.get("date_iso", "")' in blog

    @pytest.mark.parametrize("workflow, show_expr", [
        ("run-show.yml", r"\$\{\{ matrix\.show \}\}"),
        ("render-video.yml", r'"\$\{\{ inputs\.show \}\}"'),
        ("multilingual.yml", r'"\$\{\{ matrix\.show \}\}"'),
    ])
    def test_the_per_episode_regens_render_the_latest_three(self, workflow, show_expr):
        text = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
        assert re.search(r"generate_html\.py --show " + show_expr + r" --blogs --latest 3\b", text), workflow

    def test_the_nightly_full_rebuild_stays_full(self):
        nightly = (ROOT / ".github" / "workflows" / "nightly-maintenance.yml").read_text(encoding="utf-8")
        assert re.search(r'generate_html\.py --show "\$slug" --blogs', nightly)
        assert "--latest" not in nightly
