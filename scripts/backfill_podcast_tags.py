#!/usr/bin/env python3
"""One-shot: re-inject Podcasting 2.0 chapters / transcript URLs onto
historical RSS items.

Why this is needed
==================
``feedgen`` doesn't support the ``podcast:`` namespace, so the RSS
regen path in ``engine/publisher.py:update_rss_feed`` rebuilt every
feed from parsed itunes-namespace data only — silently dropping any
``<podcast:chapters>`` / ``<podcast:transcript>`` tag that earlier
runs had injected. The fix in ``engine.publisher`` now preserves
those tags going forward; this script does the one-time backfill so
historical episodes get them back.

For each ``*_podcast.rss`` (and ``podcast.rss`` for Tesla), walk every
``<item>``, derive the ``chapters_url`` / ``transcript_url`` from the
enclosure MP3 filename, check that the file exists locally, and
inject the matching ``<podcast:chapters>`` / ``<podcast:transcript>``
element if missing.
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
PODCAST_NS = "https://podcastindex.org/namespace/1.0"
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
BASE_URL = "https://nerranetwork.com"


# Map RSS path -> (digest_subdir, ep-num pattern in filename).
# Tesla uses ``podcast.rss`` (legacy); every other show uses
# ``<slug>_podcast.rss``.
SHOW_FEEDS: Dict[str, str] = {
    "podcast.rss": "tesla_shorts_time",
    "omni_view_podcast.rss": "omni_view",
    "fascinating_frontiers_podcast.rss": "fascinating_frontiers",
    "planetterrian_podcast.rss": "planetterrian",
    "env_intel_podcast.rss": "env_intel",
    "models_agents_podcast.rss": "models_agents",
    "models_agents_beginners_podcast.rss": "models_agents_beginners",
    "modern_investing_podcast.rss": "modern_investing",
    "finansy_prosto_podcast.rss": "finansy_prosto",
    "privet_russian_podcast.rss": "privet_russian",
    "unintended_consequences_podcast.rss": "unintended_consequences",
}


_EP_NUM_RE = re.compile(r"Ep(\d{3,4})", re.IGNORECASE)


def _enclosure_filename(item: ET.Element) -> Optional[str]:
    enc = item.find("enclosure")
    if enc is None:
        return None
    url = enc.get("url", "")
    if not url:
        return None
    return url.rsplit("/", 1)[-1]


def _derive_urls(
    enclosure_filename: str, digest_subdir: str
) -> Tuple[Optional[str], Optional[str]]:
    """Given an enclosure filename like ``Tesla_Shorts_Time_Pod_Ep464_20260506.mp3``
    and the digest subdirectory name, return ``(chapters_url, transcript_url)``
    if the files exist on disk. ``None`` for either side if the matching
    file isn't present.
    """
    if not enclosure_filename.endswith(".mp3"):
        return None, None
    base = enclosure_filename[:-4]  # strip `.mp3`

    # Episode number for the chapters_ep{NNN}.json file.
    m = _EP_NUM_RE.search(base)
    chapters_url: Optional[str] = None
    if m:
        ep_num = int(m.group(1))
        chapters_path = REPO / "digests" / digest_subdir / f"chapters_ep{ep_num:03d}.json"
        if chapters_path.exists():
            chapters_url = (
                f"{BASE_URL}/digests/{digest_subdir}/chapters_ep{ep_num:03d}.json"
            )

    # Transcript file shares the enclosure stem.
    transcript_path = REPO / "digests" / digest_subdir / f"{base}_transcript.json"
    transcript_url: Optional[str] = None
    if transcript_path.exists():
        transcript_url = (
            f"{BASE_URL}/digests/{digest_subdir}/{base}_transcript.json"
        )

    return chapters_url, transcript_url


def _backfill_feed(rss_path: Path, digest_subdir: str, dry_run: bool) -> dict:
    """Add missing podcast 2.0 tags to *rss_path* in place. Returns
    a stats dict for the caller to print."""
    stats = {"feed": rss_path.name, "items": 0, "chapters_added": 0, "transcripts_added": 0}
    if not rss_path.exists():
        stats["error"] = "missing"
        return stats

    ET.register_namespace("podcast", PODCAST_NS)
    ET.register_namespace("itunes", ITUNES_NS)
    ET.register_namespace("atom", "http://www.w3.org/2005/Atom")

    tree = ET.parse(str(rss_path))
    root = tree.getroot()

    # Strip any duplicate xmlns:podcast attribute so the output stays clean.
    for attr in list(root.attrib):
        if attr == "xmlns:podcast" or (
            attr.startswith("xmlns:") and root.attrib[attr] == PODCAST_NS
        ):
            del root.attrib[attr]

    channel = root.find("channel")
    if channel is None:
        stats["error"] = "no <channel>"
        return stats

    for item in channel.findall("item"):
        stats["items"] += 1
        filename = _enclosure_filename(item)
        if not filename:
            continue
        chapters_url, transcript_url = _derive_urls(filename, digest_subdir)

        if (
            chapters_url
            and item.find(f"{{{PODCAST_NS}}}chapters") is None
        ):
            el = ET.SubElement(item, f"{{{PODCAST_NS}}}chapters")
            el.set("url", chapters_url)
            el.set("type", "application/json+chapters")
            stats["chapters_added"] += 1

        if (
            transcript_url
            and item.find(f"{{{PODCAST_NS}}}transcript") is None
        ):
            el = ET.SubElement(item, f"{{{PODCAST_NS}}}transcript")
            el.set("url", transcript_url)
            el.set("type", "application/json")
            stats["transcripts_added"] += 1

    if not dry_run:
        tree.write(str(rss_path), xml_declaration=True, encoding="UTF-8")
    return stats


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would change without writing.")
    p.add_argument("--feed", default=None,
                   help="Limit backfill to a specific RSS filename.")
    args = p.parse_args()

    targets: Dict[str, str] = SHOW_FEEDS
    if args.feed:
        targets = {args.feed: SHOW_FEEDS.get(args.feed, "")}
        if not targets[args.feed]:
            print(f"Unknown feed: {args.feed}", file=sys.stderr)
            return 2

    total = {"items": 0, "chapters_added": 0, "transcripts_added": 0}
    for feed_name, digest_subdir in targets.items():
        rss_path = REPO / feed_name
        s = _backfill_feed(rss_path, digest_subdir, args.dry_run)
        if s.get("error"):
            print(f"  ⚠️  {feed_name}: {s['error']}")
            continue
        print(
            f"  {feed_name}: {s['items']} items "
            f"(+{s['chapters_added']} chapters, +{s['transcripts_added']} transcripts)"
        )
        for k in ("items", "chapters_added", "transcripts_added"):
            total[k] += s.get(k, 0)

    mode = "dry-run" if args.dry_run else "applied"
    print(
        f"\nTotals ({mode}): {total['items']} items scanned, "
        f"{total['chapters_added']} chapters added, "
        f"{total['transcripts_added']} transcripts added."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
