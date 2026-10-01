#!/usr/bin/env python3
"""Backfill WebVTT transcripts and the feed tags that point at them.

Oct 1 2026. Every feed item carried one ``<podcast:transcript>`` whose
URL was the raw faster-whisper JSON dump — a shape Apple Podcasts does
not ingest (SRT/VTT only) and that is not the Podcasting 2.0 JSON
transcript either, so the in-app transcript was absent on every show.
The live publish path now writes ``<prefix>_transcript.vtt`` beside the
JSON and emits a ``text/vtt`` tag first; this script brings the
committed back catalogue up to the same state:

1. for every ``digests/**/*_transcript.json`` with no sibling ``.vtt``,
   render the VTT from the SAME segments (``engine.transcripts.
   segments_to_vtt`` — same timebase as the JSON the chapters key on);
2. for every root audio feed (``podcast.rss`` + ``*_podcast.rss``; never
   the ``.fr/.ru/.es/.zh`` language feeds, ``.video.rss`` or the blog
   feeds), add a ``text/vtt`` tag beside every JSON transcript tag whose
   VTT now exists on disk, and the channel identity tags
   (``itunes:type``, ``podcast:guid``, the branded ``itunes:author``) —
   through the same injectors the live path uses, so a feed rebuilt
   tomorrow and a feed backfilled today are the same shape.

Idempotent. ``--dry-run`` is the default and prints counts; ``--apply``
writes. After every feed write the result is re-parsed with feedparser
and must keep its item count (and its parse status), or the original
bytes are restored and the run exits non-zero.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Set
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.publisher import (  # noqa: E402
    inject_channel_identity_tags,
    inject_vtt_transcript_tags,
)
from engine.transcripts import segments_to_vtt  # noqa: E402

# The dub tracks' Whisper JSON (``<stem>.ru_transcript.json``) is
# gitignored and never linked from a feed — not ours to render.
_LANG_TRANSCRIPT_RE = re.compile(r"\.[a-z]{2}_transcript\.json$")
_NON_AUDIO_FEED_RE = re.compile(r"\.(?:[a-z]{2}|video)\.rss$")


def transcript_jsons(digests_dir: Path) -> List[Path]:
    """Every episode transcript JSON under *digests_dir*, sorted."""
    return sorted(
        p for p in digests_dir.rglob("*_transcript.json")
        if not _LANG_TRANSCRIPT_RE.search(p.name)
    )


def vtt_path_for(json_path: Path) -> Path:
    return json_path.with_name(json_path.name[: -len(".json")] + ".vtt")


def render_vtt(json_path: Path) -> Optional[str]:
    """The VTT text for a transcript JSON, or None when it has no
    usable segment list (a truncated or foreign file is left alone)."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    segments = data.get("segments") if isinstance(data, dict) else None
    if not isinstance(segments, list):
        return None
    return segments_to_vtt(segments)


def root_audio_feeds(root: Path) -> List[Path]:
    """``podcast.rss`` + ``*_podcast.rss`` at the repo root — the audio
    feeds the shows publish; no language, video or blog feeds."""
    feeds = []
    for p in sorted(root.glob("*.rss")):
        if _NON_AUDIO_FEED_RE.search(p.name):
            continue
        if p.name == "podcast.rss" or p.name.endswith("_podcast.rss"):
            feeds.append(p)
    return feeds


def local_transcript_path(json_url: str, root: Path) -> Optional[Path]:
    """Map a feed's transcript URL to the committed file it names, which
    GitHub Pages serves from the same path under the site root."""
    rel = unquote(urlparse(json_url).path).lstrip("/")
    if not rel.startswith("digests/") or not rel.endswith("_transcript.json"):
        return None
    return root / rel


def vtt_url_resolver(
    root: Path, pending: Optional[Set[Path]] = None,
) -> Callable[[str], Optional[str]]:
    """Resolver for ``inject_vtt_transcript_tags``: a VTT URL for a JSON
    transcript URL whose VTT is on disk — or, on a dry run, in *pending*
    (the VTTs the apply would have written first)."""
    pending = pending or set()

    def resolve(json_url: str) -> Optional[str]:
        local = local_transcript_path(json_url, root)
        if local is None:
            return None
        vtt = vtt_path_for(local)
        if not vtt.exists() and vtt not in pending:
            return None
        return json_url[: -len(".json")] + ".vtt"
    return resolve


def _feed_shape(path: Path):
    import feedparser
    parsed = feedparser.parse(str(path))
    return len(parsed.entries), bool(parsed.bozo)


def backfill_feed(
    feed: Path, root: Path, *, apply: bool, pending: Optional[Set[Path]] = None,
) -> dict:
    """Run both injectors on *feed* (on a scratch copy unless *apply*).

    Returns ``{"vtt_tags": n, "identity": bool, "verified": bool}``.
    """
    resolver = vtt_url_resolver(root, pending)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / feed.name
        shutil.copyfile(feed, work)
        before = _feed_shape(work)
        vtt_tags = inject_vtt_transcript_tags(work, resolver)
        identity = inject_channel_identity_tags(work)
        after = _feed_shape(work)
        verified = after == before
        if apply and (vtt_tags or identity):
            if not verified:
                print(f"::error::{feed.name}: item count/parse status changed "
                      f"{before} -> {after}; feed left untouched")
            else:
                shutil.copyfile(work, feed)
    return {"vtt_tags": vtt_tags, "identity": identity, "verified": verified}


def backfill_vtts(jsons: Iterable[Path], *, apply: bool) -> dict:
    stats = {"existing": 0, "written": 0, "skipped": 0, "bytes": 0,
             "paths": set()}
    for json_path in jsons:
        vtt = vtt_path_for(json_path)
        if vtt.exists():
            stats["existing"] += 1
            continue
        text = render_vtt(json_path)
        if text is None:
            stats["skipped"] += 1
            print(f"  skip (no segments): {json_path}")
            continue
        stats["bytes"] += len(text.encode("utf-8"))
        stats["written"] += 1
        stats["paths"].add(vtt)
        if apply:
            vtt.write_text(text, encoding="utf-8")
    return stats


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="write VTTs and feeds")
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="report what would change (default)")
    ap.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    apply = bool(args.apply)
    root = args.root.resolve()
    label = "APPLY" if apply else "DRY RUN"

    jsons = transcript_jsons(root / "digests")
    vstats = backfill_vtts(jsons, apply=apply)
    print(
        f"[{label}] VTT: {len(jsons)} transcript JSONs — "
        f"{vstats['written']} written, {vstats['existing']} already present, "
        f"{vstats['skipped']} skipped, {vstats['bytes'] / 1e6:.1f} MB"
    )

    failed = 0
    total_tags = 0
    for feed in root_audio_feeds(root):
        res = backfill_feed(feed, root, apply=apply, pending=vstats["paths"])
        total_tags += res["vtt_tags"]
        if not res["verified"]:
            failed += 1
        flags = []
        if res["vtt_tags"]:
            flags.append(f"+{res['vtt_tags']} text/vtt tag(s)")
        if res["identity"]:
            flags.append("channel identity tags")
        if not res["verified"]:
            flags.append("VERIFY FAILED")
        print(f"[{label}] {feed.name}: {', '.join(flags) or 'unchanged'}")
    print(f"[{label}] feeds: {total_tags} text/vtt tag(s) across "
          f"{len(root_audio_feeds(root))} root audio feeds")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
