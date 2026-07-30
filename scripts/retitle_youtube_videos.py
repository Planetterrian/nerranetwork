#!/usr/bin/env python3
"""Repair transcript-fragment titles on already-published videos.

Why this exists
---------------
Before the July 18 2026 title-bundle work, a Short's title was the raw
opening text of its clip. That shipped titles like::

    it's July 1st, 2026. Let's dive into today's Tesla news. Tesla plans
    to add 1000 #Shorts

    larger, higher thrust engine. And a quick market note, SPC-X closed
    at $157.54, #Shorts

Measured across every tracked upload: **11% of Shorts published before
2026-07-18 carry a fragment title, against 1% after** — the pipeline was
fixed forward, but the back catalogue was never repaired, and those
videos are still live, still indexed, and still the first thing a new
viewer sees on the channel page.

A contractor audit (2026-07-29) scored the channel's titles 20/100. Most
of that audit was boilerplate, but this part was right, and it is
mechanical to fix.

What it does
------------
Reads each show's ``digests/<slug>/youtube_videos.json`` index, finds
records whose stored title looks like a transcript fragment, rebuilds a
title from the episode's HOOK using the same ``_build_seo_title`` the
live pipeline uses, and writes it back via ``videos.update``.

Safety
------
* **Dry run by default.** ``--apply`` is required to write anything.
* The hook must produce a title that is itself clean — an episode whose
  hook is also a fragment is reported and skipped, never "fixed" into a
  second bad title.
* ``engine.youtube.update_video_title`` reads the existing snippet and
  changes only the title, so descriptions, tags and category survive.
* Quota: ~51 units per video changed (1 read + 50 write), well inside
  the 200k/day budget, but ``--limit`` bounds a first run anyway.

Usage::

    python scripts/retitle_youtube_videos.py                    # report
    python scripts/retitle_youtube_videos.py --show tesla       # one show
    python scripts/retitle_youtube_videos.py --apply --limit 25 # write
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("retitle")

# The title-bundle work landed here; anything published after it already
# gets an LLM-written title and is left alone unless --all is passed.
TITLE_FIX_DATE = "2026-07-18"

_SHORTS_SUFFIX = " #Shorts"

# Openers that betray a mid-sentence transcript slice rather than a title.
_FRAGMENT_OPENERS = (
    "it's", "let's", "and ", "but ", "so ", "that's", "we're", "you're",
    "this is", "there's", "here's", "now ", "then ", "plus ", "also ",
    "the kicker", "meanwhile", "okay", "alright", "well ",
)


def looks_like_fragment(title: str) -> bool:
    """True when *title* reads as a slice of speech, not a headline."""
    if not title:
        return False
    core = title.split("|")[0].replace(_SHORTS_SUFFIX, "").strip()
    if not core:
        return False
    # Starts lower-case: a headline never does.
    if core[:1].islower():
        return True
    low = core.lower()
    if low.startswith(_FRAGMENT_OPENERS):
        return True
    # Ends mid-number or mid-clause ("... plans to add 1000", "closed at
    # $157.54,").
    if re.search(r"[,;]$", core):
        return True
    if re.search(r"\b(?:to|of|the|a|an|and|at|for|with|from|in|on)$", low):
        return True
    return False


def _iter_records(show: Optional[str], channel: str = "en") -> List[Dict]:
    """Video records for ONE channel.

    Each channel keeps its own index — ``youtube_videos.json`` for the
    EN channel, ``youtube_videos.<lang>.json`` for each dub — and a
    video can only be updated with the credentials of the channel that
    owns it. Reading the wrong index would send EN video ids to the RU
    token and fail every call, so the channel selects the file.
    """
    channel = (channel or "en").strip().lower()
    pattern = ("*/youtube_videos.json" if channel == "en"
               else f"*/youtube_videos.{channel}.json")
    out: List[Dict] = []
    for path in sorted((REPO_ROOT / "digests").glob(pattern)):
        raw = json.loads(path.read_text(encoding="utf-8"))
        videos = raw.get("videos") if isinstance(raw, dict) else raw
        items = list(videos.values()) if isinstance(videos, dict) else (videos or [])
        for rec in items:
            if not isinstance(rec, dict):
                continue
            if show and rec.get("show_slug") != show:
                continue
            rec["_index_path"] = str(path)
            out.append(rec)
    return out


def _config_for(slug: str, cache: Dict) -> Optional[object]:
    if slug in cache:
        return cache[slug]
    from engine.config import load_config

    for candidate in (REPO_ROOT / "shows").glob("*.yaml"):
        if candidate.stem.startswith("_"):
            continue
        try:
            cfg = load_config(candidate)
        except Exception:  # noqa: BLE001
            continue
        if getattr(cfg, "slug", None) == slug:
            cache[slug] = cfg
            return cfg
    cache[slug] = None
    return None


def _episode_headlines(cfg, episode: int, cache: Dict) -> List[str]:
    """Story headlines from an episode's committed digest.

    A Short's own stored ``hook`` is the clip's opening speech — for the
    videos this script exists to repair, the hook IS the fragment, so it
    can never supply the replacement. The digest is the real source: it
    holds the episode's headline stories, which is what the title should
    have said in the first place. Several Shorts from one episode take
    DIFFERENT headlines, so the channel does not end up with four
    identically-titled clips.
    """
    key = (getattr(cfg, "slug", ""), episode)
    if key in cache:
        return cache[key]
    out: List[str] = []
    try:
        # The show's digest directory is the parent of its summaries
        # JSON — the config exposes that path, not the directory itself.
        summaries = str(getattr(cfg.publishing, "summaries_json", "") or "")
        out_dir = (REPO_ROOT / summaries).parent if summaries else None
        matches = sorted(out_dir.glob(f"*Ep{episode:03d}_*.md")) if out_dir and out_dir.is_dir() else []
        if matches:
            from engine.grok_imagine import extract_story_headlines

            text = matches[0].read_text(encoding="utf-8")
            out = [h for h in extract_story_headlines(text, max_count=8) if h]
    except Exception:  # noqa: BLE001 — a missing digest is not fatal
        out = []
    cache[key] = out
    return out


def plan(show: Optional[str], include_all: bool,
         channel: str = "en") -> List[Dict]:
    """Return the list of proposed retitles, newest first."""
    from engine.video_metadata import _build_seo_title

    cfg_cache: Dict = {}
    headline_cache: Dict = {}
    used_per_episode: Dict = {}
    proposals: List[Dict] = []
    for rec in _iter_records(show, channel):
        title = str(rec.get("title") or "")
        published = str(rec.get("published") or "")
        if not include_all and published >= TITLE_FIX_DATE:
            continue
        if not looks_like_fragment(title):
            continue
        slug = str(rec.get("show_slug") or "")
        cfg = _config_for(slug, cfg_cache)
        show_name = getattr(cfg, "name", "") or slug
        suffix = _SHORTS_SUFFIX if rec.get("kind") == "short" else ""

        source = ""
        hook = str(rec.get("hook") or "").strip()
        if hook and not looks_like_fragment(hook):
            source = hook
        elif cfg is not None and isinstance(rec.get("episode"), int):
            # Take the next unused headline for this episode so sibling
            # Shorts get distinct titles.
            ep = int(rec["episode"])
            heads = _episode_headlines(cfg, ep, headline_cache)
            taken = used_per_episode.setdefault((slug, ep), set())
            for idx, head in enumerate(heads):
                if idx in taken or looks_like_fragment(head):
                    continue
                taken.add(idx)
                source = head
                break

        if not source:
            proposals.append({**rec, "new_title": None,
                              "reason": "no clean hook or digest headline found"})
            continue
        new_title = _build_seo_title(source, show_name, suffix=suffix)
        if not new_title or new_title.strip() == title.strip():
            continue
        proposals.append({**rec, "new_title": new_title, "reason": ""})
    proposals.sort(key=lambda r: str(r.get("published") or ""), reverse=True)
    return proposals


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--show", help="restrict to one show slug")
    ap.add_argument("--apply", action="store_true",
                    help="actually write the new titles (default: report only)")
    ap.add_argument("--limit", type=int, default=0,
                    help="cap how many videos are changed in one run")
    ap.add_argument("--all", action="store_true",
                    help=f"include videos published on/after {TITLE_FIX_DATE}")
    ap.add_argument("--channel", default="en",
                    help="which channel's credentials to use (en/ru/fr)")
    args = ap.parse_args(argv)

    proposals = plan(args.show, args.all, args.channel)
    fixable = [p for p in proposals if p.get("new_title")]
    skipped = [p for p in proposals if not p.get("new_title")]

    print(f"{len(proposals)} fragment title(s) found — "
          f"{len(fixable)} fixable, {len(skipped)} need a human.\n")
    for p in fixable[: (args.limit or len(fixable))]:
        print(f"  {p.get('published','?')} {p.get('video_id','?')} "
              f"[{p.get('show_slug','?')}/{p.get('kind','?')}]")
        print(f"    old: {p['title']}")
        print(f"    new: {p['new_title']}")
    for p in skipped:
        print(f"  SKIP {p.get('video_id','?')} — {p['reason']}")
        print(f"    old: {p['title']}")

    if not args.apply:
        print("\nDry run — pass --apply to write these titles.")
        return 0
    if not fixable:
        print("\nNothing to write.")
        return 0

    from engine.youtube import get_channel_credentials_from_env, update_video_title

    creds = get_channel_credentials_from_env(args.channel)
    if creds is None:
        print(f"::warning::No YouTube credentials for channel "
              f"'{args.channel}' — nothing written.")
        return 0

    targets = fixable[: (args.limit or len(fixable))]
    changed = 0
    for p in targets:
        if update_video_title(credentials=creds, video_id=p["video_id"],
                              new_title=p["new_title"]):
            changed += 1
    print(f"\nRetitled {changed} of {len(targets)} video(s) "
          f"(~{changed * 51} quota units).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
