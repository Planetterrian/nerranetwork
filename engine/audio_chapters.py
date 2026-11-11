"""Chapters inside the published MP3, and as timestamps in the show notes.

Nov 11 2026. Every show has written ``chapters_epNNN.json`` since July and
linked it from the feed as ``<podcast:chapters>``; YouTube gets the same
list in its description and the blog prints it. But the MP3 itself carried
no chapters, and the apps most listeners use never read the JSON sidecar:
Apple Podcasts and Overcast read chapters only from the audio file's ID3
tag (``CHAP`` / ``CTOC`` frames), and Spotify only from timestamps in the
episode description. So in those apps no episode of any show ever had
chapters, while every surface the pipeline checked had them.

This module is the one owner of both shapes:

* :func:`embed_chapters_in_mp3` writes the chapter list into the MP3's
  ID3v2 tag with a stream COPY: the audio frames are bit-identical, only the
  tag changes. It runs on the finished file before the upload and the feed
  (both read its size). Any failure leaves the file exactly as it was.
* :func:`chapter_timestamp_block` renders ``0:00 Title`` lines for show
  notes, with YouTube's rules (first line at 0:00, nothing shorter than
  10 s), which are also the rules Spotify's description chapters follow.

Chapter text is metadata only: nothing here changes what a listener hears.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

logger = logging.getLogger(__name__)

#: ID3v2.3 is the version Apple Podcasts' own spec asks for, and every app
#: that reads CHAP frames reads it.
ID3V2_VERSION = "3"

ChapterSource = Union[str, Path, dict, Sequence[dict], None]


def chapter_marks(source: ChapterSource) -> List[Tuple[float, str]]:
    """``[(start_seconds, title), …]`` sorted by start, from a chapters JSON
    path, its parsed dict, or a bare list of chapter dicts. Entries without a
    readable start are skipped; an untitled one is numbered. ``[]`` when the
    source cannot be read."""
    data = source
    if isinstance(source, (str, Path)):
        try:
            data = json.loads(Path(source).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 — metadata only
            logger.debug("chapters unreadable (%s): %s", source, exc)
            return []
    items = data.get("chapters") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    marks: List[Tuple[float, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        start = item.get("startTime", item.get("start_time", item.get("start")))
        try:
            start_f = float(start)
        except (TypeError, ValueError):
            continue
        if start_f < 0:
            continue
        title = " ".join(str(item.get("title") or item.get("name") or "").split())
        marks.append((start_f, title or f"Chapter {len(marks) + 1}"))
    marks.sort(key=lambda m: m[0])
    return marks


def _ffmetadata_escape(text: str) -> str:
    """Escape the characters ffmetadata treats as syntax."""
    out = str(text or "")
    for ch in ("\\", "=", ";", "#"):
        out = out.replace(ch, "\\" + ch)
    return out.replace("\n", "\\\n")


def ffmetadata_text(marks: Sequence[Tuple[float, str]],
                    total_duration_s: float) -> str:
    """An ``;FFMETADATA1`` document with one ``[CHAPTER]`` per mark, or ``""``
    when fewer than two chapters fit inside *total_duration_s* (a single
    chapter spanning the episode is what every player shows anyway)."""
    if len(marks) < 2 or not total_duration_s or total_duration_s <= marks[-1][0]:
        return ""
    lines = [";FFMETADATA1"]
    kept = 0
    for i, (start_f, title) in enumerate(marks):
        end_f = marks[i + 1][0] if i + 1 < len(marks) else total_duration_s
        if end_f <= start_f:
            continue
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={int(round(start_f * 1000))}",
            f"END={int(round(end_f * 1000))}",
            f"title={_ffmetadata_escape(title)}",
        ]
        kept += 1
    return "\n".join(lines) + "\n" if kept >= 2 else ""


def _probe_duration(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            check=True, capture_output=True, text=True, timeout=60,
        ).stdout.strip()
        return float(out or 0.0)
    except Exception:  # noqa: BLE001
        return 0.0


def embed_chapters_cmd(mp3_in: Path, ffmeta: Path, mp3_out: Path) -> List[str]:
    """The ffmpeg command that copies *mp3_in*'s audio untouched into
    *mp3_out*, keeps its existing tags, and takes its chapters from *ffmeta*
    (never from the input, so a re-embed replaces rather than appends)."""
    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(mp3_in),
        "-f", "ffmetadata", "-i", str(ffmeta),
        "-map", "0:a",
        "-map_metadata", "0",
        "-map_chapters", "1",
        "-c", "copy",
        "-id3v2_version", ID3V2_VERSION,
        "-f", "mp3",
        str(mp3_out),
    ]


def embed_chapters_in_mp3(mp3_path: Union[str, Path], source: ChapterSource,
                          *, duration_s: Optional[float] = None) -> int:
    """Write *source*'s chapters into *mp3_path*'s ID3 tag, in place.

    Returns the number of chapters now in the file, or 0 when nothing was
    written (no chapters, fewer than two, an unreadable file, an ffmpeg
    failure, or a result whose duration does not match the original). On 0
    the file is untouched: a missing chapter list must never cost an episode.
    """
    mp3 = Path(mp3_path)
    if not mp3.is_file():
        return 0
    marks = chapter_marks(source)
    total = float(duration_s or 0.0) or _probe_duration(mp3)
    text = ffmetadata_text(marks, total)
    if not text:
        logger.info("MP3 chapters: nothing to embed in %s (%d marks)",
                    mp3.name, len(marks))
        return 0
    tmp_dir = tempfile.mkdtemp(prefix="mp3_chapters_", dir=str(mp3.parent))
    meta = Path(tmp_dir) / "chapters.ffmeta"
    out = Path(tmp_dir) / mp3.name
    try:
        meta.write_text(text, encoding="utf-8")
        subprocess.run(embed_chapters_cmd(mp3, meta, out), check=True,
                       capture_output=True, text=True, timeout=300)
        before = _probe_duration(mp3)
        after = _probe_duration(out)
        if not out.is_file() or out.stat().st_size == 0 or (
                before and abs(after - before) > 0.5):
            logger.warning("MP3 chapters: remux of %s looks wrong "
                           "(%.2fs -> %.2fs); file left as it was",
                           mp3.name, before, after)
            return 0
        written = len(read_mp3_chapters(out))
        if written < 2:
            logger.warning("MP3 chapters: %s carries %d chapters after the "
                           "remux; file left as it was", mp3.name, written)
            return 0
        os.replace(out, mp3)
        logger.info("MP3 chapters: %d chapters embedded in %s", written, mp3.name)
        return written
    except Exception as exc:  # noqa: BLE001 — metadata only, never blocks
        detail = getattr(exc, "stderr", "") or exc
        logger.warning("MP3 chapters not embedded in %s (non-fatal): %s",
                       mp3.name, str(detail)[-400:])
        return 0
    finally:
        for p in (meta, out):
            try:
                p.unlink()
            except OSError:
                pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass


def read_mp3_chapters(mp3_path: Union[str, Path]) -> List[dict]:
    """The chapters ffprobe reads from *mp3_path*: ``[{start, end, title}]``.
    ``[]`` when there are none or the probe fails."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_chapters", "-of", "json",
             str(mp3_path)],
            check=True, capture_output=True, text=True, timeout=60,
        ).stdout
        chapters = json.loads(out or "{}").get("chapters") or []
    except Exception:  # noqa: BLE001
        return []
    return [
        {"start": float(c.get("start_time") or 0.0),
         "end": float(c.get("end_time") or 0.0),
         "title": (c.get("tags") or {}).get("title", "")}
        for c in chapters
    ]


_NOTES_LABELS = {"en": "Chapters", "ru": "Главы", "fr": "Chapitres",
                 "es": "Capítulos"}


def chapter_timestamp_block(source: ChapterSource, *, language: str = "en",
                            with_label: bool = True) -> str:
    """``Chapters:`` followed by ``0:00 Title`` lines for show notes, or
    ``""`` when fewer than two chapters render. The lines follow YouTube's
    rules (first at 0:00, none under 10 s) through the one formatter the
    YouTube description already uses, so the two lists never disagree."""
    from engine.video_metadata import _format_chapter_block

    marks = chapter_marks(source)
    block = _format_chapter_block(
        [{"startTime": s, "title": t} for s, t in marks], language=language)
    if not block:
        return ""
    if not with_label:
        return block
    label = _NOTES_LABELS.get((language or "en").lower()[:2], "Chapters")
    return f"{label}:\n{block}"

