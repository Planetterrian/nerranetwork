#!/usr/bin/env python3
"""Export one volume's audiobook masters as a store-upload bundle (WO-15).

    python scripts/export_audiobook.py --volume unintended_consequences_collected

The paid audio masters live ONLY in the private ``nerra-books`` bucket
(see ``scripts/build_book.py::_r2_upload``), and the browser tooling that
fills in store forms cannot upload files over 10 MB — so the operator
uploads from a machine, and this script is how the files reach that
machine without ever touching a public hostname:

1. pull ``books/<id>/audio/track_*.mp3`` from the private bucket (or use
   a local build under ``outputs/books/<id>/audio/``),
2. add what Voices by INaudio wants beside the chapter files — a
   ``retail_sample.mp3`` (first ~3.5 minutes of chapter 1, after the
   opening credits, 1-second fade-out), the cover as a 3000×3000 square
   JPEG plus the 1600×2560 portrait, and a ``manifest.csv`` (track
   number, chapter title, duration, sha256) — and zip it all in order,
3. upload the zip to the PRIVATE bucket at
   ``books/<id>/export/<id>_audiobook_tracks.zip``,
4. mint S3-style presigned GET URLs (7 days — R2's maximum) for the zip
   and the M4B and write them to the run's ``$GITHUB_STEP_SUMMARY`` —
   and nowhere else: never the log, never a file in the repo, never the
   public bucket. The log carries sizes and checksums only, so the
   operator can verify the download.

The opening and closing credits stay separate files (track_000 and the
last track) — they are never baked into chapter 1 — and no narration
text is touched here (a text change re-bills TTS for that track).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import os
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_book as bb  # noqa: E402 — the private-bucket helpers
from engine.audio import get_audio_duration  # noqa: E402
from engine.audiobook import MP3_ARGS, narration_texts  # noqa: E402
from engine.book_compiler import (  # noqa: E402
    R2_BOOKS_PREFIX,
    collect_chapters,
    load_volume,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s",
                    stream=sys.stdout)
logger = logging.getLogger("export_audiobook")

#: R2 presigned URLs are capped at seven days.
PRESIGN_EXPIRES_SECONDS = 7 * 24 * 3600
#: Retail sample: INaudio accepts 1-5 minutes; 3.5 minutes of chapter 1.
SAMPLE_SECONDS = 210
SAMPLE_FADE_SECONDS = 1.0
SAMPLE_MIN_SECONDS = 60
#: INaudio cover: square, at least 2400 px.
SQUARE_COVER_PX = 3000
COVER_JPEG_QUALITY = 92


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_track_count(chapters) -> int:
    """Opening credits + one file per chapter + closing credits."""
    return len(chapters) + 2


def local_tracks(audio_dir: Path) -> List[Path]:
    return sorted(audio_dir.glob("track_*.mp3"))


def ensure_tracks(volume, audio_dir: Path, s3, *, expected: int) -> List[Path]:
    """The per-chapter masters, local or pulled from the PRIVATE bucket."""
    audio_dir.mkdir(parents=True, exist_ok=True)
    tracks = local_tracks(audio_dir)
    if len(tracks) >= expected:
        logger.info("audio: %d local track(s) under %s", len(tracks), audio_dir)
        return tracks
    if s3 is None:
        raise SystemExit(
            f"audio: {len(tracks)}/{expected} tracks under {audio_dir} and no "
            "R2 credentials to fetch the rest")
    bucket = bb._books_private_bucket()
    prefix = f"{R2_BOOKS_PREFIX}/{volume.volume_id}/audio/"
    pulled = 0
    for page in s3.get_paginator("list_objects_v2").paginate(
            Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            name = obj["Key"].rsplit("/", 1)[-1]
            if name.startswith("track_") and name.endswith(".mp3"):
                local = audio_dir / name
                if not local.exists():
                    s3.download_file(bucket, obj["Key"], str(local))
                    pulled += 1
    logger.info("audio: pulled %d track(s) from the private bucket", pulled)
    tracks = local_tracks(audio_dir)
    if len(tracks) != expected:
        raise SystemExit(
            f"audio: expected {expected} tracks (credits + {expected - 2} "
            f"chapters + credits), found {len(tracks)}")
    return tracks


def fetch_cover(volume, out_png: Path, catalog_path: Path) -> Path:
    """The composited 1600×2560 cover: local build output, else the
    public cover.png the catalog records (covers are marketing assets)."""
    local = bb.OUT_ROOT / volume.volume_id / "cover.png"
    if local.exists():
        return local
    import json
    import requests
    entry = next((v for v in json.loads(catalog_path.read_text("utf-8"))
                  .get("volumes", []) if v.get("volume_id") == volume.volume_id),
                 {})
    url = (entry.get("files") or {}).get("cover", "")
    if not url.startswith("http"):
        raise SystemExit(f"cover: no local cover.png and no public cover "
                         f"URL in the catalog for {volume.volume_id}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_png.write_bytes(r.content)
    return out_png


def square_cover_jpeg(cover_png: Path, out_jpg: Path,
                      px: int = SQUARE_COVER_PX) -> Path:
    """3000×3000 for INaudio: the portrait cover centred on a blurred,
    darkened enlargement of itself (the standard letterbox treatment —
    the art and the series typography survive untouched)."""
    from PIL import Image, ImageEnhance, ImageFilter

    cover = Image.open(cover_png).convert("RGB")
    ratio = max(px / cover.width, px / cover.height)
    bg = cover.resize((round(cover.width * ratio), round(cover.height * ratio)),
                      Image.LANCZOS)
    x0 = (bg.width - px) // 2
    y0 = (bg.height - px) // 2
    bg = bg.crop((x0, y0, x0 + px, y0 + px))
    bg = bg.filter(ImageFilter.GaussianBlur(px / 60))
    bg = ImageEnhance.Brightness(bg).enhance(0.55)
    fg_h = px
    fg_w = round(cover.width * fg_h / cover.height)
    fg = cover.resize((fg_w, fg_h), Image.LANCZOS)
    bg.paste(fg, ((px - fg_w) // 2, 0))
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out_jpg, "JPEG", quality=COVER_JPEG_QUALITY, optimize=True)
    return out_jpg


def portrait_cover_jpeg(cover_png: Path, out_jpg: Path) -> Path:
    from PIL import Image

    img = Image.open(cover_png).convert("RGB")
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_jpg, "JPEG", quality=COVER_JPEG_QUALITY, optimize=True)
    return out_jpg


def make_retail_sample(chapter_one: Path, out_mp3: Path) -> Tuple[Path, float]:
    """First ~3.5 minutes of chapter 1 (the file AFTER the opening
    credits) with a one-second fade-out, at the same 192k CBR 44.1 kHz
    the chapter files use."""
    duration = get_audio_duration(chapter_one) or 0.0
    length = min(float(SAMPLE_SECONDS), duration)
    if length < SAMPLE_MIN_SECONDS:
        raise SystemExit(
            f"retail sample: chapter 1 is {duration:.0f}s — INaudio wants a "
            f"1-5 minute sample; nothing to cut")
    fade_start = max(0.0, length - SAMPLE_FADE_SECONDS)
    cmd = [
        "ffmpeg", "-y", "-i", str(chapter_one), "-t", f"{length:.3f}",
        "-af", f"afade=t=out:st={fade_start:.3f}:d={SAMPLE_FADE_SECONDS}",
        "-codec:a", "libmp3lame", *MP3_ARGS, str(out_mp3),
    ]
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(cmd, check=True, capture_output=True)
    return out_mp3, length


def probe_codec(path: Path) -> Dict[str, str]:
    """sample rate / bit rate / channels of an MP3, via ffprobe."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=sample_rate,bit_rate,channels",
             "-of", "default=noprint_wrappers=1", str(path)],
            capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return {}
    return dict(line.split("=", 1) for line in out.strip().splitlines()
                if "=" in line)


def build_manifest_rows(tracks: List[Path], titles: List[str]) -> List[dict]:
    rows = []
    for i, (path, title) in enumerate(zip(tracks, titles)):
        rows.append({
            "track": i,
            "file": path.name,
            "title": title,
            "duration_seconds": round(get_audio_duration(path) or 0.0, 3),
            "sha256": sha256_file(path),
        })
    return rows


def write_manifest(rows: List[dict], path: Path) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["track", "file", "title",
                                          "duration_seconds", "sha256"])
        w.writeheader()
        w.writerows(rows)
    return path


def readme_text(volume, rows: List[dict], sample_seconds: float) -> str:
    n = len(rows)
    return (
        f"{volume.full_title} — audiobook masters\n"
        f"Author: {volume.author}\n\n"
        f"track_000.mp3           opening credits (separate file)\n"
        f"track_001 … track_{n - 2:03d}  one file per chapter, in reading order\n"
        f"track_{n - 1:03d}.mp3           closing credits (separate file)\n"
        f"retail_sample.mp3       first {sample_seconds / 60:.1f} minutes of "
        "chapter 1 (after the credits), 1 s fade-out\n"
        f"cover.jpg               {SQUARE_COVER_PX}×{SQUARE_COVER_PX} square "
        "(Voices by INaudio)\n"
        "cover_portrait.jpg      1600×2560 portrait (the store/marketing cover)\n"
        "manifest.csv            track number, title, duration, sha256\n\n"
        "All MP3s: 192 kbps CBR, 44.1 kHz, mono. Digital narration — declare it "
        "on every store form (KDP AI questionnaire, Spotify/Findaway digital-"
        "narration box, Google Play declaration). Never Audible/ACX.\n"
    )


def build_zip(out_zip: Path, tracks: List[Path], extras: List[Tuple[str, Path]],
              readme: str) -> Path:
    """Tracks in order, stored (already compressed), then the extras."""
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w") as z:
        for p in tracks:
            z.write(p, p.name, compress_type=zipfile.ZIP_STORED)
        for arcname, p in extras:
            comp = (zipfile.ZIP_STORED if p.suffix.lower() in (".mp3", ".jpg")
                    else zipfile.ZIP_DEFLATED)
            z.write(p, arcname, compress_type=comp)
        z.writestr("README.txt", readme, compress_type=zipfile.ZIP_DEFLATED)
    return out_zip


def presign(s3, bucket: str, key: str,
            expires: int = PRESIGN_EXPIRES_SECONDS) -> str:
    """S3-style presigned GET on the PRIVATE bucket. The returned string
    is a secret for its lifetime — it goes to the step summary only."""
    return s3.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires)


def write_step_summary(summary_path: Path, volume, items: List[dict],
                       expires_at: datetime) -> None:
    """The ONLY place a presigned URL is written."""
    lines = [
        f"## Audiobook export — {volume.full_title}",
        "",
        "Download from this page into `~/Downloads` and verify each sha256 "
        "before uploading to a store. Links expire "
        f"**{expires_at:%Y-%m-%d %H:%M UTC}** (R2's 7-day maximum).",
        "",
        "| File | Size | sha256 | Download |",
        "|---|---|---|---|",
    ]
    for it in items:
        lines.append(
            f"| `{it['name']}` | {it['bytes'] / 2**20:.1f} MB | "
            f"`{it['sha256']}` | [download]({it['url']}) |")
    lines += ["", "Digital narration — declare it on every store form. "
              "Never Audible/ACX. Never re-host these files at a public URL."]
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_export(volume_id: str, *, work_dir: Optional[Path] = None,
               s3=None, upload: bool = True,
               summary_path: Optional[Path] = None,
               catalog_path: Optional[Path] = None) -> dict:
    """Build the bundle; upload + presign when *upload* and *s3* are given.

    Returns a report dict with sizes and checksums (never URLs)."""
    vol_path = ROOT / "books" / "volumes" / f"{volume_id}.yaml"
    if not vol_path.exists():
        raise SystemExit(f"no such volume config: {vol_path}")
    volume = load_volume(vol_path)
    chapters = collect_chapters(volume)
    titles = [t for t, _ in narration_texts(volume, chapters)]
    expected = expected_track_count(chapters)

    work_dir = Path(work_dir or bb.OUT_ROOT / volume_id / "export")
    audio_dir = bb.OUT_ROOT / volume_id / "audio"
    tracks = ensure_tracks(volume, audio_dir, s3, expected=expected)
    if len(tracks) != expected:
        raise SystemExit(f"audio: expected {expected} tracks, found "
                         f"{len(tracks)} under {audio_dir}")
    if titles[0] != "Opening Credits" or titles[-1] != "Closing Credits":
        raise SystemExit("credits must be the first and last tracks")

    codec = probe_codec(tracks[1])
    if codec and (codec.get("sample_rate") != "44100"
                  or codec.get("bit_rate") not in ("192000", "")):
        logger.warning("audio: chapter files are %s — INaudio wants 192 kbps "
                       "CBR 44.1 kHz", codec)

    cover_png = fetch_cover(volume, work_dir / "cover_source.png",
                            catalog_path or ROOT / "books" / "catalog.json")
    cover_sq = square_cover_jpeg(cover_png, work_dir / "cover.jpg")
    cover_pt = portrait_cover_jpeg(cover_png, work_dir / "cover_portrait.jpg")
    sample, sample_len = make_retail_sample(
        tracks[1], work_dir / "retail_sample.mp3")

    rows = build_manifest_rows(tracks, titles)
    rows.append({"track": "sample", "file": sample.name,
                 "title": f"Retail sample — {titles[1]}",
                 "duration_seconds": round(get_audio_duration(sample) or 0.0, 3),
                 "sha256": sha256_file(sample)})
    manifest = write_manifest(rows, work_dir / "manifest.csv")

    out_zip = work_dir / f"{volume_id}_audiobook_tracks.zip"
    build_zip(out_zip, tracks, [
        (sample.name, sample), ("cover.jpg", cover_sq),
        ("cover_portrait.jpg", cover_pt), ("manifest.csv", manifest),
    ], readme_text(volume, rows[:-1], sample_len))

    report = {
        "volume_id": volume_id,
        "tracks": len(tracks),
        "chapters": len(chapters),
        "zip": out_zip.name,
        "zip_bytes": out_zip.stat().st_size,
        "zip_sha256": sha256_file(out_zip),
        "sample_seconds": round(sample_len, 1),
        "uploaded": False,
        "presigned": 0,
    }
    logger.info("export: %s — %d tracks (credits + %d chapters + credits) + "
                "retail sample %.0fs + 2 covers + manifest; zip %.1f MB "
                "sha256 %s", out_zip.name, len(tracks), len(chapters),
                sample_len, report["zip_bytes"] / 2**20, report["zip_sha256"])

    if not (upload and s3 is not None):
        logger.info("export: no upload (dry run) — bundle at %s", out_zip)
        return report

    bucket = bb._books_private_bucket()
    zip_key = f"{R2_BOOKS_PREFIX}/{volume_id}/export/{out_zip.name}"
    bb._r2_upload(out_zip, zip_key, "application/zip", private=True)
    report["uploaded"] = True

    m4b_key = f"{R2_BOOKS_PREFIX}/{volume_id}/{volume_id}.m4b"
    m4b_local = work_dir / f"{volume_id}.m4b"
    s3.download_file(bucket, m4b_key, str(m4b_local))
    report["m4b_bytes"] = m4b_local.stat().st_size
    report["m4b_sha256"] = sha256_file(m4b_local)
    logger.info("export: %s %.1f MB sha256 %s", m4b_local.name,
                report["m4b_bytes"] / 2**20, report["m4b_sha256"])

    items = [
        {"name": out_zip.name, "bytes": report["zip_bytes"],
         "sha256": report["zip_sha256"],
         "url": presign(s3, bucket, zip_key)},
        {"name": m4b_local.name, "bytes": report["m4b_bytes"],
         "sha256": report["m4b_sha256"],
         "url": presign(s3, bucket, m4b_key)},
    ]
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=PRESIGN_EXPIRES_SECONDS)
    if summary_path is None:
        logger.warning("export: no step summary file — presigned URLs were "
                       "minted but NOT written anywhere (set "
                       "GITHUB_STEP_SUMMARY or --summary-file)")
    else:
        write_step_summary(Path(summary_path), volume, items, expires_at)
        report["presigned"] = len(items)
        logger.info("export: %d presigned link(s) written to the step "
                    "summary; they expire %s", len(items),
                    expires_at.strftime("%Y-%m-%d %H:%M UTC"))
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--volume", required=True,
                    help="volume id (books/volumes/<id>.yaml)")
    ap.add_argument("--no-upload", action="store_true",
                    help="build the bundle locally; skip R2 upload + links")
    ap.add_argument("--summary-file", default=os.getenv("GITHUB_STEP_SUMMARY"),
                    help="where the presigned links go (default: "
                         "$GITHUB_STEP_SUMMARY; the ONLY sink for them)")
    ap.add_argument("--work-dir", default="",
                    help="scratch/output dir (default outputs/books/<id>/export)")
    args = ap.parse_args()

    s3 = bb._r2_client() if (bb._have_r2() and not args.no_upload) else None
    if not args.no_upload and s3 is None:
        logger.warning("export: R2 credentials not set — building the bundle "
                       "only")
    report = run_export(
        args.volume,
        work_dir=Path(args.work_dir) if args.work_dir else None,
        s3=s3, upload=not args.no_upload,
        summary_path=Path(args.summary_file) if args.summary_file else None,
    )
    for k, v in report.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
