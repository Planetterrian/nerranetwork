"""YouTube + X review (Oct 24 2026) — docs/reviews/youtube_x_review_2026_10_24.md.

The decline was measured first: a YouTube Shorts-feed distribution step on
Sep 15-16 that hit @NerraRU (-65% feed traffic, watch-through flat), a faded
EN breakout, and one pipeline-owned content effect (EN long-form retention).
These guards pin the pipeline defects the review found in code — all
render / metadata, no audio.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import video_metadata as vm  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# D1 — a sub-10 s chapter ANYWHERE voids the block
# ---------------------------------------------------------------------------

class TestChapterBlockMergesShortChapters:
    def test_a_later_sub_10s_chapter_is_merged_into_the_run(self):
        # Tesla's real shape: "Tomorrow Teaser" 8 s before "Closing" on every
        # episode — 141 of the last 400 committed chapter files carried a
        # later gap under 10 s and YouTube ignored the whole list.
        chapters = [
            {"title": "Top Stories", "startTime": 12},
            {"title": "Deep Dive", "startTime": 300},
            {"title": "Tomorrow Teaser", "startTime": 376},
            {"title": "Closing", "startTime": 384},
        ]
        lines = vm._format_chapter_block(chapters).splitlines()
        starts = [int(line.split(" ", 1)[0].replace(":", "")) for line in lines]
        assert lines == ["0:00 Intro", "0:12 Top Stories", "5:00 Deep Dive",
                         "6:24 Closing"]
        assert len(starts) == len(set(starts))

    def test_every_rendered_gap_is_at_least_ten_seconds(self):
        chapters = [{"title": f"c{i}", "startTime": s}
                    for i, s in enumerate([0, 4, 9, 15, 22, 24, 40, 47, 49, 120])]
        lines = vm._format_chapter_block(chapters).splitlines()

        def _secs(stamp):
            parts = [int(p) for p in stamp.split(":")]
            out = 0
            for p in parts:
                out = out * 60 + p
            return out

        starts = [_secs(line.split(" ", 1)[0]) for line in lines]
        assert starts[0] == 0
        assert all(b - a >= 10 for a, b in zip(starts, starts[1:])), lines

    def test_the_zero_anchor_keeps_its_title(self):
        # The 0:00 chapter must stay at 0:00, so a chapter inside its first
        # ten seconds is dropped rather than moving the anchor.
        chapters = [
            {"title": "Cold Open", "startTime": 0},
            {"title": "Hook", "startTime": 5},
            {"title": "Main", "startTime": 120},
        ]
        assert vm._format_chapter_block(chapters).splitlines() == [
            "0:00 Cold Open", "2:00 Main"]

    def test_a_list_that_merges_to_one_chapter_renders_nothing(self):
        chapters = [
            {"title": "A", "startTime": 0},
            {"title": "B", "startTime": 6},
        ]
        assert vm._format_chapter_block(chapters) == ""

    def test_committed_chapter_files_render_valid_blocks(self):
        # Replay on the real data: every committed chapter list that renders
        # renders with no gap under ten seconds.
        import json
        files = sorted(ROOT.glob("digests/*/chapters_ep*.json"))[-150:]
        checked = 0
        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            chapters = data.get("chapters") if isinstance(data, dict) else data
            block = vm._format_chapter_block(chapters or [])
            if not block:
                continue
            starts = []
            for line in block.splitlines():
                parts = [int(p) for p in line.split(" ", 1)[0].split(":")]
                total = 0
                for p in parts:
                    total = total * 60 + p
                starts.append(total)
            assert all(b - a >= 10 for a, b in zip(starts, starts[1:])), path
            checked += 1
        assert checked > 0


# ---------------------------------------------------------------------------
# D3 — the long-form description
# ---------------------------------------------------------------------------

def _config():
    return SimpleNamespace(
        slug="tesla", name="Tesla Shorts Time", keywords=["tesla", "tsla"],
        publishing=SimpleNamespace(
            rss_title="Tesla Shorts Time Daily",
            rss_link="https://nerranetwork.com/tesla.html",
            base_url="https://nerranetwork.com",
            rss_image="",
        ),
        youtube=SimpleNamespace(
            default_language="en", category_id=28, channel="en",
            tags=["tesla", "ev"],
            synthetic_disclosure="AI Disclosure: synthesized voice.",
            description_prompt_file="shows/prompts/youtube_description_intro.txt",
            pinned_comment_template="",
            privacy_status="public", enabled=True,
        ),
        funnel=SimpleNamespace(enabled=True, destinations={}),
    )


def _description(hook="NHTSA tells Tesla to pull the Cybercab lighting kit"):
    meta = vm.build_long_form_metadata(
        _config(), episode_num=644, today_str="October 24, 2026", hook=hook,
        digest_text="Tesla pulled the kit after a letter.\n\nSecond paragraph.",
        audio_url="https://audio.nerranetwork.com/tesla/ep644.mp3",
    )
    return meta["description"]


class TestLongFormDescription:
    def test_hook_appears_once(self):
        hook = "NHTSA tells Tesla to pull the Cybercab lighting kit"
        desc = _description(hook)
        assert desc.count(hook) == 1, desc

    def test_youtube_subscribe_is_the_second_paragraph(self):
        desc = _description()
        paragraphs = desc.split("\n\n")
        assert paragraphs[1].startswith("🔔 Subscribe"), paragraphs[:3]
        assert "sub_confirmation=1" in paragraphs[1]

    def test_the_website_link_appears_once_and_is_tagged(self):
        desc = _description()
        site_lines = [line for line in desc.splitlines()
                      if "nerranetwork.com/tesla.html" in line]
        assert len(site_lines) == 1, site_lines
        assert "utm_campaign=nn-tesla-en-long-ep644" in site_lines[0]

    def test_no_operator_note_reaches_the_viewer(self):
        assert "Suggested pinned comment" not in _description()

    def test_template_carries_no_hook_placeholder(self):
        text = (ROOT / "shows/prompts/youtube_description_intro.txt").read_text(
            encoding="utf-8")
        assert "{hook}" not in text

    def test_a_show_template_that_opens_on_the_hook_is_deduped(self, tmp_path):
        prompt = tmp_path / "intro.txt"
        prompt.write_text("{hook}\n\nMore about Ep {episode_num}.", encoding="utf-8")
        cfg = _config()
        cfg.youtube.description_prompt_file = str(prompt)
        meta = vm.build_long_form_metadata(
            cfg, episode_num=3, today_str="October 24, 2026",
            hook="A hook with a figure of 12 percent", digest_text="x", audio_url="")
        assert meta["description"].count("A hook with a figure of 12 percent") == 1
        assert "More about Ep 3." in meta["description"]


# ---------------------------------------------------------------------------
# X teaser links go through engine.funnel
# ---------------------------------------------------------------------------

class TestXTeaserLinksAreTagged:
    @pytest.mark.parametrize("slug,name", [
        ("tesla", "Tesla Shorts Time"),
        ("omni_view", "Omni View"),
        ("fascinating_frontiers", "Fascinating Frontiers"),
        ("planetterrian", "Planetterrian Daily"),
        ("modern_investing", "Modern Investing Techniques"),
        ("unintended_consequences", "Unintended Consequences"),
    ])
    def test_every_teaser_link_carries_the_episode_campaign(self, slug, name):
        import run_show

        cfg = SimpleNamespace(slug=slug, name=name,
                              publishing=SimpleNamespace(x_teaser_template=""))
        teaser = run_show._build_teaser(
            cfg, 80, "October 24, 2026", {"hook": "A hook for the test."})
        urls = re.findall(r"https?://\S+", teaser)
        assert urls, teaser
        for url in urls:
            assert "utm_source=x" in url, url
            assert "utm_medium=social" in url, url
            assert f"utm_campaign=nn-{slug}-en-post-ep080" in url, url
        assert any(f"/blog/{slug}/ep080.html" in u for u in urls), urls

    def test_run_show_hand_builds_no_blog_url(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        body = src[src.index("def _build_teaser("):src.index("def _build_cross_promo_reply(")]
        assert "https://nerranetwork.com/blog/" not in body

    def test_the_campaign_round_trips(self):
        from engine import funnel
        import run_show

        url = run_show._x_episode_link("spacex", 137)
        campaign = re.search(r"utm_campaign=([^&]+)", url).group(1)
        parsed = funnel.parse_campaign_id(campaign)
        assert parsed is not None
        assert (parsed.show, parsed.kind, parsed.episode) == ("spacex", "post", 137)


# ---------------------------------------------------------------------------
# Retention by age in the early-reach file
# ---------------------------------------------------------------------------

def _row(vid, published, views, avp=None, avd=None):
    row = {"video_id": vid, "published": published, "views": views,
           "channel": "en", "kind": "long", "show_slug": "tesla",
           "window": "", "subscribers_gained": 0}
    if avp is not None:
        row["average_view_percentage"] = avp
    if avd is not None:
        row["average_view_duration_s"] = avd
    return row


def _stats(generated, rows):
    return {"generated": generated + "T19:00:00+00:00",
            "shows": {"x": {"videos": rows}}}


class TestEarlyReachRecordsRetentionByAge:
    def test_avp_and_avd_are_recorded_at_each_age_first_observation_wins(self):
        tr = _load("ter_ytx", "scripts/track_early_reach.py")
        reach = tr.load_reach(Path("/nonexistent/x.json"))
        tr.merge_snapshot(reach, _stats("2026-10-10", [_row("a", "2026-10-07", 40, 1.6, 9)]))
        tr.merge_snapshot(reach, _stats("2026-10-10", [_row("a", "2026-10-07", 99, 9.9, 99)]))
        tr.merge_snapshot(reach, _stats("2026-10-14", [_row("a", "2026-10-07", 80, 7.8, 42.6)]))
        rec = reach["videos"]["a"]
        assert rec["avp_by_age"] == {"3": 1.6, "7": 7.8}
        assert rec["avd_by_age"] == {"3": 9, "7": 42}
        assert rec["views_by_age"] == {"3": 40, "7": 80}

    def test_a_row_without_retention_records_none_and_an_old_record_survives(self):
        tr = _load("ter_ytx2", "scripts/track_early_reach.py")
        reach = {"videos": {"a": {"published": "2026-10-07", "channel": "en",
                                  "kind": "long", "show": "tesla", "window": "",
                                  "variant": "", "views_by_age": {"3": 40},
                                  "subs_by_age": {"3": 0}}}}
        tr.merge_snapshot(reach, _stats("2026-10-14", [_row("a", "2026-10-07", 80)]))
        rec = reach["videos"]["a"]
        assert rec["views_by_age"] == {"3": 40, "7": 80}
        assert "avp_by_age" not in rec


# ---------------------------------------------------------------------------
# D4 — the long-form probe can promote
# ---------------------------------------------------------------------------

class TestLongProbeCanPromote:
    def test_two_probe_longs_clearing_the_floor_turn_long_on(self):
        mod = _load("uyp_ytx", "scripts/update_youtube_policy.py")
        tier, long_vpd, _s, reason = mod.compute_tier([2.5, 1.5], [5.0] * 4, "C", "en")
        assert tier == "A" and long_vpd == 2.0
        assert "probe" in reason

    def test_probe_longs_under_the_floor_hold(self):
        mod = _load("uyp_ytx2", "scripts/update_youtube_policy.py")
        tier, long_vpd, _s, reason = mod.compute_tier([0.5, 0.4, 0.9], [5.0] * 4, "C", "en")
        assert tier == "C" and long_vpd is None
        assert "held" in reason

    def test_the_probe_rule_never_demotes_a_show_whose_long_is_on(self):
        mod = _load("uyp_ytx3", "scripts/update_youtube_policy.py")
        tier, long_vpd, *_ = mod.compute_tier([0.1, 0.1, 0.1], [5.0] * 4, "A", "en")
        assert tier == "A" and long_vpd is None

    def test_the_probe_reads_the_channel_floor(self):
        mod = _load("uyp_ytx4", "scripts/update_youtube_policy.py")
        # RU long floor is 2.0 — 1.5 vpd promotes on EN and not on RU.
        tier_en, *_ = mod.compute_tier([1.5, 1.5], [5.0] * 4, "C", "en")
        tier_ru, *_ = mod.compute_tier([1.5, 1.5], [5.0] * 4, "C", "ru")
        assert tier_en == "A" and tier_ru == "C"
