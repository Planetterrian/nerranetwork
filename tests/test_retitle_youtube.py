"""Drift guards for scripts/retitle_youtube_videos.py.

Before the July 18 2026 title-bundle work, a Short's title was the raw
opening text of its clip: "it's July 1st, 2026. Let's dive into today's
Tesla news. Tesla plans to add 1000 #Shorts". Measured across every
tracked upload, 11% of Shorts published before that date carry a
fragment title against 1% after — the pipeline was fixed forward and
the back catalogue was left broken, still live and still indexed.

The two things that must not regress:

* ``videos.update`` REPLACES the part it is given. A snippet carrying
  only a title would blank the description, tags and category of a live
  video, so the writer reads the current snippet first and changes one
  field. Losing that read-modify-write would silently strip metadata
  from every video the job touches.
* The replacement title cannot come from the Short's own stored hook —
  for exactly these videos the hook IS the fragment. It comes from the
  episode's digest headlines, one per Short, so sibling clips do not all
  land on the same title.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.retitle_youtube_videos import (  # noqa: E402
    TITLE_FIX_DATE,
    looks_like_fragment,
    plan,
)


class TestFragmentDetection:
    def test_real_broken_titles_are_caught(self):
        for title in (
            "it's July 1st, 2026. Let's dive into today's Tesla news. "
            "Tesla plans to add 1000 #Shorts",
            "seeking $417 million | Tesla Shorts Time #Shorts",
            "to $53,107. The year-over-year drop of 2.1% is the smallest #Shorts",
            "And a quick market note, SPCX is at $131.11, up 3.2%. #Shorts",
            "larger, higher thrust engine. And a quick market note, #Shorts",
        ):
            assert looks_like_fragment(title), title

    def test_real_good_titles_are_left_alone(self):
        for title in (
            "Tesla Hires 1000 at German Gigafactory",
            "Tesla Japan Stockpile Points to Stronger Q3",
            "Tesla shares climb to $411.84 after a $32 gain | Tesla Shorts Time #Shorts",
            "Пуск Starship отменён после четырёх отказов Raptor #Shorts",
            "NASA Reveals First Lunar Outpost Details",
        ):
            assert not looks_like_fragment(title), title

    def test_empty_is_not_a_fragment(self):
        assert not looks_like_fragment("")
        assert not looks_like_fragment("   ")


class TestPlan:
    def test_only_pre_fix_videos_by_default(self):
        """Post-July-18 uploads already get an LLM title — touching them
        would undo the good work, not repair anything."""
        for proposal in plan(None, include_all=False):
            assert str(proposal.get("published") or "") < TITLE_FIX_DATE

    def test_every_proposal_improves_on_the_original(self):
        for p in plan(None, include_all=False):
            new = p.get("new_title")
            if not new:
                continue
            assert new.strip() != p["title"].strip()
            assert not looks_like_fragment(new), new

    def test_shorts_keep_their_suffix(self):
        for p in plan(None, include_all=False):
            if p.get("kind") == "short" and p.get("new_title"):
                assert p["new_title"].endswith("#Shorts")

    def test_sibling_shorts_do_not_collide(self):
        """Several Shorts come from one episode; giving them all the same
        headline would trade one problem for another."""
        by_ep = {}
        for p in plan(None, include_all=False):
            if not p.get("new_title"):
                continue
            key = (p.get("show_slug"), p.get("episode"))
            by_ep.setdefault(key, []).append(p["new_title"])
        for key, titles in by_ep.items():
            assert len(titles) == len(set(titles)), f"duplicate titles for {key}"

    def test_dry_run_is_the_default(self):
        src = (REPO_ROOT / "scripts" / "retitle_youtube_videos.py").read_text(
            encoding="utf-8")
        assert '"--apply", action="store_true"' in src
        assert "Dry run — pass --apply to write these titles." in src


class TestUpdaterPreservesMetadata:
    def test_reads_before_it_writes(self):
        """The failure this guards is silent and total: a title-only
        snippet blanks the description and tags of a live video."""
        src = (REPO_ROOT / "engine" / "youtube.py").read_text(encoding="utf-8")
        body = src[src.index("def update_video_title"):]
        body = body[:body.index("\ndef ")]
        list_at = body.index("videos().list(")
        update_at = body.index("videos().update(")
        assert list_at < update_at, "must read the snippet before updating it"
        assert 'snippet["title"] = new_title' in body
        assert "categoryId" in body, "update requires categoryId"

    def test_skips_a_write_when_the_title_already_matches(self):
        src = (REPO_ROOT / "engine" / "youtube.py").read_text(encoding="utf-8")
        body = src[src.index("def update_video_title"):]
        body = body[:body.index("\ndef ")]
        assert "already correct — do not spend a write" in body

    def test_never_raises(self):
        src = (REPO_ROOT / "engine" / "youtube.py").read_text(encoding="utf-8")
        body = src[src.index("def update_video_title"):]
        body = body[:body.index("\ndef ")]
        assert "except HttpError" in body
        assert "except Exception" in body
