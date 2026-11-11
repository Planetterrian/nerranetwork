#!/usr/bin/env python3
"""Give the published interview episodes their ``<podcast:chapters>``.

Nov 11 2026. The Age of AI and Nerra Voices feeds never carried chapters:
the vouched list reached each post and YouTube, never a podcast app.
``pipelines/voices/publish_episode.py`` now writes ``chapters_epNNN.json``
and passes ``chapters_url`` for every NEW episode; this one-off writes the
same file for the episodes already out, from the list their summaries
entry carries (``vouched_chapters`` output, written at publish/refresh, so
the transcript-vouches rule holds), and adds the tag to their feed items.

Nothing else in an item changes: no enclosure, GUID, title or description.
The feed rebuild re-injects existing ``podcast:`` tags (publisher
``_reinject_preserved_podcast_tags``), so the tags survive the next publish.

Dry run by default; ``--apply`` writes.

    python scripts/backfill_interview_chapters.py [--apply]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))

#: (feed, digest dir, summaries file) per interview show.
SHOWS = (
    ("age_of_ai_podcast.rss", "digests/age_of_ai", "summaries_age_of_ai.json"),
    ("nerra_voices_podcast.rss", "digests/nerra_voices",
     "summaries_nerra_voices.json"),
)
BASE_URL = "https://nerranetwork.com"


def _items_by_episode(feed_text: str) -> dict:
    out = {}
    for item in re.findall(r"<item>(.*?)</item>", feed_text, re.S):
        ep = re.search(r"<itunes:episode>(\d+)</itunes:episode>", item)
        guid = re.search(r"<guid[^>]*>(.*?)</guid>", item, re.S)
        if ep and guid:
            out[int(ep.group(1))] = (guid.group(1).strip(),
                                     "podcast:chapters" in item)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    from engine.publisher import _inject_chapters_tag
    from engine.audio_chapters import chapter_marks

    for feed_name, digest_dir, summaries_name in SHOWS:
        feed = ROOT / feed_name
        summaries = ROOT / digest_dir / summaries_name
        if not (feed.exists() and summaries.exists()):
            print(f"{feed_name}: missing feed or summaries, skipped")
            continue
        items = _items_by_episode(feed.read_text(encoding="utf-8"))
        episodes = json.loads(summaries.read_text(encoding="utf-8")).get("episodes") or []
        for entry in episodes:
            num = entry.get("episode")
            if not isinstance(num, int) or num not in items:
                continue
            guid, tagged = items[num]
            marks = chapter_marks([
                {"start": c.get("start"), "title": c.get("title")}
                for c in entry.get("chapters") or [] if isinstance(c, dict)])
            if len(marks) < 2:
                print(f"{feed_name} Ep{num}: fewer than two chapters, skipped")
                continue
            name = f"chapters_ep{num:03d}.json"
            path = ROOT / digest_dir / name
            url = f"{BASE_URL}/{digest_dir}/{name}"
            print(f"{feed_name} Ep{num}: {len(marks)} chapters"
                  f"{' (tag already present)' if tagged else ''}")
            if not args.apply:
                continue
            if not path.exists():
                data = {"version": "1.2.0",
                        "chapters": [{"startTime": round(s, 1), "title": t}
                                     for s, t in marks]}
                if entry.get("title"):
                    data["title"] = entry["title"]
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False)
                                + "\n", encoding="utf-8")
            if not tagged:
                _inject_chapters_tag(feed, guid, url)
    if not args.apply:
        print("dry run: nothing written (pass --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
