"""Give already-published interview episodes their YouTube video (Oct 11 2026).

The Age of AI turned YouTube on on 2026-09-20 and uploaded nothing: the
publisher looked for a waveform MP4 the edit path never rendered, so every
publish since logged "no waveform video" and skipped. From Oct 11 the
publisher renders the video itself when none exists
(``publish_episode.render_episode_video``). This script runs that same path
for the episodes published before the fix.

Dry run by default — it prints the plan and uploads nothing. ``--apply``
uploads. An episode already in ``digests/<slug>/youtube_videos.json`` is
skipped, so a re-run never double-posts. Run it from Actions
("Nerra Voices — backfill YouTube videos"), where the channel token lives.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

from common import ROOT, logger  # noqa: E402
from shows import get_show  # noqa: E402
from publish_episode import (  # noqa: E402
    _show_config, interview_episode_title, maybe_publish_youtube, notes_lede,
)


def uploaded_episodes(show) -> set:
    """Episode numbers already recorded in the show's YouTube index."""
    path = ROOT / show.audio_subdir / "youtube_videos.json"  # where _record_youtube_video writes
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — no index yet means nothing uploaded
        return set()
    rows = data.get("videos", data) if isinstance(data, dict) else data
    out = set()
    for row in rows or []:
        try:
            out.add(int(row.get("episode_num") or row.get("episode") or 0))
        except (TypeError, ValueError, AttributeError):
            continue
    return out


def thesis_from_digest(show, episode_num: int) -> str:
    """The episode thesis: the digest's opening blockquote."""
    for path in sorted((ROOT / "digests" / show.slug).glob(f"*_Ep{episode_num:03d}_*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^>\s*\*\*(.+?)\*\*\s*$", line.strip())
            if m:
                return m.group(1).strip()
    return ""


def plan(show) -> list:
    """Published episodes with no video, oldest first."""
    data = json.loads(show.summaries_path.read_text(encoding="utf-8"))
    done = uploaded_episodes(show)
    rows = []
    for ep in data.get("episodes", []):
        try:
            n = int(ep.get("episode") or ep.get("episode_num") or 0)
        except (TypeError, ValueError):
            continue
        if n <= 0 or n in done or not ep.get("audio_url"):
            continue
        guest = str(ep.get("guest") or "").strip()
        thesis = thesis_from_digest(show, n) or str(ep.get("hook") or "")
        rows.append({
            "episode": n,
            "date": str(ep.get("date") or ""),
            "guest": guest,
            "title": interview_episode_title(n, guest or show.name, thesis),
            "description": str(ep.get("summary") or ""),
            "audio_url": str(ep["audio_url"]),
        })
    return sorted(rows, key=lambda r: r["episode"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--show", required=True, help="show slug, e.g. the interview show to backfill")
    ap.add_argument("--episodes", default="",
                    help="comma-separated episode numbers (default: every missing one)")
    ap.add_argument("--apply", action="store_true", help="upload (default is a dry run)")
    args = ap.parse_args(argv)

    show = get_show(args.show)
    rows = plan(show)
    if args.episodes.strip():
        wanted = {int(x) for x in args.episodes.split(",") if x.strip()}
        rows = [r for r in rows if r["episode"] in wanted]
    if not rows:
        print("Nothing to backfill: every published episode has a video recorded.")
        return 0
    for r in rows:
        print(f"Ep{r['episode']:>3} {r['date']}  {r['title']}")
    if not args.apply:
        print(f"\nDry run: {len(rows)} episode(s) would be rendered and uploaded. "
              "Re-run with --apply.")
        return 0

    cfg = _show_config(show)
    if cfg is None or not getattr(getattr(cfg, "youtube", None), "enabled", False):
        print(f"{show.slug}: youtube.enabled is off in its YAML — nothing uploaded.")
        return 1
    before = uploaded_episodes(show)
    for r in rows:
        when = dt.date.fromisoformat(r["date"]) if r["date"] else dt.date.today()
        logger.info("Backfilling Ep%d", r["episode"])
        maybe_publish_youtube(show, cfg, r["episode"], when, r["title"],
                              notes_lede(r["description"]) or r["description"],
                              r["audio_url"], r["guest"])
    added = sorted(uploaded_episodes(show) - before)
    print(f"Uploaded {len(added)} of {len(rows)}: {added}")
    return 0 if len(added) == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
