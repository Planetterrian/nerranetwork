#!/usr/bin/env python3
"""Put chapters inside the episodes already published (Nov 11 2026).

From Nov 11 every new MP3 carries its chapters in its ID3 tag and every new
feed item lists them as ``0:00 Title`` lines (``engine.audio_chapters``).
The back catalogue on R2 was published before that, so in Apple Podcasts,
Overcast and Spotify none of it has chapters. This tool fixes the files
already out, from the ``chapters_epNNN.json`` each episode committed when
it was made.

Two passes, so the long one never holds a feed open:

``--embed`` (needs the R2 credentials; Actions "Embed Chapters in Published
Episodes"): for each feed item with a committed chapter list, pull the
published MP3 back from the bare R2 URL (never through the OP3 prefix: a
repair is not a listen), write the chapters into its ID3 tag with a stream
copy, and upload it to the SAME key. **The upload is refused unless the
decoded audio of the new file is bit-identical to the old one** (an MD5 of
the PCM) and the file reads back at least two chapters. A file that already
carries chapters is recorded and left alone. Results go to
``--results`` (JSON: feed, guid, key, new byte length).

``--feeds`` (no credentials; run on a fresh checkout of main just before
the commit): edits each feed item IN PLACE, as text: the enclosure's
``length`` follows the uploaded object (from ``--results``), and the
description and ``itunes:summary`` gain the ``Chapters:`` block after the
Sources line when they do not carry one. Nothing else in an item changes:
no URL, GUID, title, date or ordering. The record of what was embedded is
``digests/<dir>/mp3_chapters_log.json`` so a second run skips it.

Translated feeds (``*.fr.rss`` and the like) are never touched: their audio
is a separate synthesis and the English chapter times do not apply.

Dry run by default: both passes print what they would do.

    python scripts/embed_published_chapters.py --embed --show tesla --limit 5
    python scripts/embed_published_chapters.py --embed --all-shows --apply --results r.json
    python scripts/embed_published_chapters.py --feeds --all-shows --apply --results r.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.audio_chapters import (  # noqa: E402
    chapter_marks,
    chapter_timestamp_block,
    embed_chapters_in_mp3,
    read_mp3_chapters,
)
from engine.daily_edition import strip_op3  # noqa: E402

logger = logging.getLogger("embed_chapters")

#: The public host of the podcast-audio bucket; an enclosure anywhere else
#: is not ours to replace.
PUBLIC_HOST = "audio.nerranetwork.com"
PUBLIC_BASE_URL = f"https://{PUBLIC_HOST}"
DEFAULT_BUCKET = "podcast-audio"
LOG_NAME = "mp3_chapters_log.json"

#: Config files under shows/ that are not shows.
_NOT_SHOWS = {"network_meta", "pronunciation_map", "translation_overrides",
              "scaffold_pending"}


@dataclass(frozen=True)
class Feed:
    slug: str
    rss_path: Path
    digests_dir: Path
    language: str


def show_feeds(only: Optional[Iterable[str]] = None) -> List[Feed]:
    """Every English-or-native podcast feed with committed chapter lists:
    each show YAML's ``rss_file`` and Nerra Daily's (registry-only)."""
    from engine.config import load_config
    from engine.daily_edition import EDITIONS

    wanted = set(only) if only else None
    feeds: List[Feed] = []
    for path in sorted((ROOT / "shows").glob("*.yaml")):
        slug = path.stem
        if slug.startswith("_") or slug in _NOT_SHOWS:
            continue
        if wanted is not None and slug not in wanted:
            continue
        try:
            config = load_config(path)
        except Exception as exc:  # noqa: BLE001 — one bad YAML never stops the rest
            logger.warning("%s: config not loaded (%s), skipped", slug, exc)
            continue
        rss = ROOT / config.publishing.rss_file
        if rss.exists():
            feeds.append(Feed(slug, rss, ROOT / config.episode.output_dir,
                              str(config.publishing.rss_language or "en")))
    for lang, spec in EDITIONS.items():
        if wanted is not None and spec.r2_prefix not in wanted:
            continue
        rss = ROOT / spec.feed_file
        if rss.exists():
            feeds.append(Feed(spec.r2_prefix, rss, ROOT / spec.digest_dir, lang))
    return feeds


# ---------------------------------------------------------------------------
# The feed is the record of what was published
# ---------------------------------------------------------------------------

_ITEM_RE = re.compile(r"<item>.*?</item>", re.S)


def feed_items(rss_text: str) -> List[dict]:
    """``[{episode, guid, enclosure_url, key}]`` in feed order. ``key`` is the
    R2 object key, or "" when the enclosure is not on the public host."""
    out = []
    for item in _ITEM_RE.findall(rss_text):
        ep = re.search(r"<itunes:episode>(\d+)</itunes:episode>", item)
        guid = re.search(r"<guid[^>]*>(.*?)</guid>", item, re.S)
        enc = re.search(r'<enclosure\b[^>]*\burl="([^"]+)"', item)
        if not (ep and guid and enc):
            continue
        url = html.unescape(enc.group(1))
        bare = strip_op3(url)
        parsed = urlparse(bare)
        key = parsed.path.lstrip("/") if parsed.netloc == PUBLIC_HOST else ""
        out.append({"episode": int(ep.group(1)), "guid": guid.group(1).strip(),
                    "enclosure_url": url, "download_url": bare, "key": key})
    return out


def chapters_path(feed: Feed, episode: int) -> Path:
    return feed.digests_dir / f"chapters_ep{episode:03d}.json"


def read_log(feed: Feed) -> Dict[str, dict]:
    path = feed.digests_dir / LOG_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {e["guid"]: e for e in data if isinstance(e, dict) and e.get("guid")}


def write_log(feed: Feed, entries: Dict[str, dict]) -> None:
    path = feed.digests_dir / LOG_NAME
    rows = sorted(entries.values(), key=lambda e: (e.get("episode") or 0))
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


# ---------------------------------------------------------------------------
# Pass 1: the audio
# ---------------------------------------------------------------------------

def pcm_md5(path: Path) -> str:
    """MD5 of the decoded audio: what a listener hears, tags excluded."""
    return subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-map", "0:a", "-f", "md5", "-"],
        check=True, capture_output=True, text=True, timeout=900,
    ).stdout.strip()


class Refused(RuntimeError):
    """The re-tagged file is not safe to upload."""


def retag(src: Path, chapters: Path) -> int:
    """Embed *chapters* in *src* in place; raise :class:`Refused` unless the
    audio is bit-identical and at least two chapters read back."""
    before = pcm_md5(src)
    n = embed_chapters_in_mp3(src, chapters)
    if n < 2:
        raise Refused("no chapters were written")
    after = pcm_md5(src)
    if not before or before != after:
        raise Refused(f"decoded audio changed ({before} -> {after})")
    return n


def _upload(local: Path, key: str) -> str:
    from engine.storage import upload_to_r2

    return upload_to_r2(
        local, key,
        bucket=os.environ.get("R2_BUCKET", DEFAULT_BUCKET),
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        access_key=os.environ["R2_ACCESS_KEY_ID"],
        secret_key=os.environ["R2_SECRET_ACCESS_KEY"],
        public_base_url=PUBLIC_BASE_URL,
        content_type="audio/mpeg",
    )


def embed_pass(feeds: List[Feed], *, apply: bool, limit: int,
               episode: Optional[int], results_path: Optional[Path],
               budget_minutes: float = 0) -> int:
    """Pass 1. Stops starting new episodes after *budget_minutes* (0 = none)
    so the feed pass and the commit always get to run: what is left is
    picked up by the next run."""
    import time
    from engine.http_download import download_to

    if apply and not all(os.environ.get(k) for k in
                         ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")):
        logger.error("--apply needs R2_ENDPOINT_URL, R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY")
        return 2
    results: List[dict] = []
    counts: Dict[str, int] = {}
    done = 0
    deadline = time.monotonic() + budget_minutes * 60 if budget_minutes else None
    with tempfile.TemporaryDirectory(prefix="embed_chapters_") as tmp:
        work = Path(tmp)
        for feed in feeds:
            logged = read_log(feed)
            items = feed_items(feed.rss_path.read_text(encoding="utf-8"))
            for item in items:
                if episode is not None and item["episode"] != episode:
                    continue
                ch = chapters_path(feed, item["episode"])
                status = None
                if item["guid"] in logged:
                    status = "already_logged"
                elif not item["key"]:
                    status = "foreign_enclosure"
                elif len(chapter_marks(ch)) < 2:
                    status = "no_chapter_list"
                if status:
                    counts[status] = counts.get(status, 0) + 1
                    continue
                if (limit and done >= limit) or (
                        deadline and apply and time.monotonic() > deadline):
                    counts["left_for_next_run"] = counts.get("left_for_next_run", 0) + 1
                    continue
                done += 1
                label = f"{feed.slug} Ep{item['episode']}"
                if not apply:
                    logger.info("%s: would embed %d chapters in r2://%s (same key)",
                                label, len(chapter_marks(ch)), item["key"])
                    counts["planned"] = counts.get("planned", 0) + 1
                    continue
                local = work / Path(item["key"]).name
                try:
                    download_to(item["download_url"], local, label=label)
                    if len(read_mp3_chapters(local)) >= 2:
                        status = "had_chapters"
                    else:
                        n = retag(local, ch)
                        _upload(local, item["key"])
                        status = "embedded"
                        logger.info("%s: %d chapters embedded, uploaded to %s",
                                    label, n, item["key"])
                    results.append({
                        "slug": feed.slug, "episode": item["episode"],
                        "guid": item["guid"], "key": item["key"],
                        "length": local.stat().st_size, "status": status,
                    })
                except Refused as exc:
                    status = "refused"
                    logger.error("::error::%s: REFUSED, nothing uploaded: %s", label, exc)
                except Exception as exc:  # noqa: BLE001 — one file; the batch goes on
                    status = "failed"
                    logger.error("%s: failed, nothing uploaded: %s", label, exc)
                finally:
                    local.unlink(missing_ok=True)
                counts[status] = counts.get(status, 0) + 1
                if results_path:  # written as we go: a killed run keeps its uploads
                    results_path.write_text(json.dumps(results, indent=1) + "\n",
                                            encoding="utf-8")
    logger.info("EMBED_SUMMARY %s", " ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 1 if counts.get("refused") or counts.get("failed") else 0


# ---------------------------------------------------------------------------
# Pass 2: the feeds
# ---------------------------------------------------------------------------

def _with_block(desc_xml: str, block: str) -> str:
    """*desc_xml* (escaped element text) with the escaped *block* after its
    Sources line, else before its AI disclosure, else at the end."""
    from xml.sax.saxutils import escape

    esc = escape(block)
    lines = desc_xml.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("Sources:"):
            return "\n".join(lines[:i + 1] + ["", esc] + lines[i + 1:])
    marker = re.search(r"\n\n(AI Disclosure|Раскрытие)", desc_xml)
    if marker:
        return desc_xml[:marker.start()] + "\n\n" + esc + desc_xml[marker.start():]
    return desc_xml.rstrip() + "\n\n" + esc


#: A description that already lists chapter times (a line starting "0:00 ").
_HAS_BLOCK = re.compile(r"(^|\n)0:00 ")


def edit_item(item_xml: str, *, block: str, length: Optional[int]) -> str:
    out = item_xml
    if length:
        out = re.sub(r'(<enclosure\b[^>]*\blength=")\d*(")',
                     lambda m: f"{m.group(1)}{length}{m.group(2)}", out, count=1)
    if block:
        for tag in ("description", "itunes:summary"):
            def _sub(m, tag=tag):
                body = m.group(2)
                if _HAS_BLOCK.search(body):
                    return m.group(0)
                return f"{m.group(1)}{_with_block(body, block)}{m.group(3)}"
            out = re.sub(rf"(<{tag}>)(.*?)(</{tag}>)", _sub, out, count=1, flags=re.S)
    return out


def feeds_pass(feeds: List[Feed], *, apply: bool, results_path: Optional[Path]) -> int:
    results = []
    if results_path and results_path.exists():
        results = json.loads(results_path.read_text(encoding="utf-8") or "[]")
    by_guid = {r["guid"]: r for r in results}
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for feed in feeds:
        text = feed.rss_path.read_text(encoding="utf-8")
        notes = lengths = 0

        def _edit(m):
            nonlocal notes, lengths
            item = m.group(0)
            ep = re.search(r"<itunes:episode>(\d+)</itunes:episode>", item)
            guid = re.search(r"<guid[^>]*>(.*?)</guid>", item, re.S)
            if not (ep and guid):
                return item
            res = by_guid.get(guid.group(1).strip())
            length = res["length"] if res and res.get("status") == "embedded" else None
            block = chapter_timestamp_block(chapters_path(feed, int(ep.group(1))),
                                            language=feed.language)
            new = edit_item(item, block=block, length=length)
            if new != item:
                if length:
                    lengths += 1
                if block and _HAS_BLOCK.search(new) and not _HAS_BLOCK.search(item):
                    notes += 1
            return new

        new_text = _ITEM_RE.sub(_edit, text)
        logger.info("%s: %d item(s) gain show-note chapters, %d enclosure length(s) follow the re-tagged file",
                    feed.rss_path.name, notes, lengths)
        if not apply:
            continue
        if new_text != text:
            feed.rss_path.write_text(new_text, encoding="utf-8")
        mine = [r for r in results if r.get("slug") == feed.slug
                and r.get("status") in ("embedded", "had_chapters")]
        if mine:
            logged = read_log(feed)
            for r in mine:
                logged[r["guid"]] = {"episode": r["episode"], "guid": r["guid"],
                                     "key": r["key"], "status": r["status"],
                                     "length": r["length"], "at": now}
            write_log(feed, logged)
    if not apply:
        logger.info("DRY RUN: no feed written")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    which = ap.add_mutually_exclusive_group(required=True)
    which.add_argument("--embed", action="store_true", help="Pass 1: re-tag the MP3s on R2")
    which.add_argument("--feeds", action="store_true", help="Pass 2: edit the feeds")
    shows = ap.add_mutually_exclusive_group(required=True)
    shows.add_argument("--show", action="append", help="Show slug (repeatable); nerra_daily works")
    shows.add_argument("--all-shows", action="store_true")
    ap.add_argument("--episode", type=int, help="One episode number (with one --show)")
    ap.add_argument("--limit", type=int, default=0, help="Episodes re-tagged this run (0 = no cap)")
    ap.add_argument("--budget-minutes", type=float, default=0,
                    help="Stop starting new episodes after this long (0 = no budget)")
    ap.add_argument("--results", type=Path, help="JSON written by --embed, read by --feeds")
    ap.add_argument("--apply", action="store_true", help="Without it nothing is written")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        stream=sys.stdout)
    for noisy in ("engine.config", "botocore", "boto3", "s3transfer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    feeds = show_feeds(None if args.all_shows else args.show)
    if not feeds:
        logger.error("No feed matched")
        return 1
    if args.embed:
        return embed_pass(feeds, apply=args.apply, limit=args.limit,
                          episode=args.episode, results_path=args.results,
                          budget_minutes=args.budget_minutes)
    return feeds_pass(feeds, apply=args.apply, results_path=args.results)


if __name__ == "__main__":
    sys.exit(main())
