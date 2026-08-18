#!/usr/bin/env python3
"""Build one anthology volume: EPUB + cover + (optionally) audiobook,
upload the artifacts to R2, and record the volume in books/catalog.json.

    python scripts/build_book.py --volume uc_vol1
    python scripts/build_book.py --volume uc_vol1 --skip-audio   # ebook only
    python scripts/build_book.py --volume uc_vol1 --no-upload    # local build

Build products land in outputs/books/<volume_id>/ (gitignored — R2 is the
durable store, key prefix books/<volume_id>/). The committed outputs are
books/catalog.json and, on the next site regen, books.html.

Cost profile: the EPUB is free (deterministic transform of committed
digests). The audiobook narrates through Grok TTS at roughly $4 for a
50-chapter volume — printed as an estimate and gated behind
--max-tts-cost-usd so a config mistake cannot burn a real budget.

Run from the "Build Book" GitHub Actions workflow for real builds (the
TTS + R2 credentials live there); a local run without credentials still
produces the EPUB and cover.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.audiobook import (  # noqa: E402
    build_m4b,
    estimate_tts_cost_usd,
    narration_texts,
    synthesize_tracks,
    total_duration_seconds,
)
from engine.book_art import (  # noqa: E402
    COVER_ART_SIZE,
    CHAPTER_ART_SIZE,
    chapter_art_prompt,
    cover_art_prompt,
    generate_art,
    model_cost_usd,
    to_chapter_jpeg,
    upload_book_image_to_gallery,
)
from engine.book_compiler import (  # noqa: E402
    R2_BOOKS_PREFIX,
    build_epub,
    collect_chapters,
    generate_cover,
    load_volume,
    plan_next_volumes,
    update_catalog,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s",
                    stream=sys.stdout)
logger = logging.getLogger("build_book")

OUT_ROOT = ROOT / "outputs" / "books"


def _r2_upload(local: Path, key: str, content_type: str) -> str:
    from engine.storage import upload_to_r2

    return upload_to_r2(
        local, key,
        # Same bucket + public host the podcast enclosures use, but under
        # the books/ keyspace — never inside a show's audio prefix.
        bucket=os.getenv("R2_BOOKS_BUCKET", "podcast-audio").strip(),
        endpoint_url=os.getenv("R2_ENDPOINT_URL", "").strip(),
        access_key=os.getenv("R2_ACCESS_KEY_ID", "").strip(),
        secret_key=os.getenv("R2_SECRET_ACCESS_KEY", "").strip(),
        public_base_url=os.getenv(
            "R2_BOOKS_PUBLIC_BASE_URL",
            "https://audio.nerranetwork.com").strip(),
        content_type=content_type,
    )


def _have_r2() -> bool:
    return all(os.getenv(k, "").strip() for k in
               ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--volume",
                    help="volume id (books/volumes/<id>.yaml)")
    ap.add_argument("--plan-series", action="append", default=[],
                    metavar="SERIES",
                    help="run the volume planner for this series "
                         "(books/series/<slug>.yaml) before building; "
                         "repeatable. With --build-planned, newly planned "
                         "volumes are built too.")
    ap.add_argument("--build-planned", action="store_true",
                    help="build every volume the planner just created")
    ap.add_argument("--skip-audio", action="store_true",
                    help="build the ebook only")
    ap.add_argument("--skip-images", action="store_true",
                    help="skip Grok Imagine chapter/cover art")
    ap.add_argument("--no-upload", action="store_true",
                    help="skip R2 upload even if credentials are present")
    ap.add_argument("--max-tts-cost-usd", type=float, default=10.0,
                    help="refuse to narrate past this estimate (default 10)")
    ap.add_argument("--max-image-cost-usd", type=float, default=5.0,
                    help="refuse to generate art past this estimate "
                         "(default 5)")
    args = ap.parse_args()

    to_build = []
    for series_slug in args.plan_series:
        planned = plan_next_volumes(series_slug)
        logger.info("series %s: planned %d new volume(s)", series_slug,
                    len(planned))
        if args.build_planned:
            to_build.extend(p.stem for p in planned)
    if args.volume:
        to_build.append(args.volume)
    if not to_build:
        logger.info("nothing to build")
        return 0

    for volume_id in to_build:
        rc = _build_one(volume_id, args)
        if rc != 0:
            return rc
    return 0


def _generate_book_art(volume, chapters, out_dir, api_key, args):
    """Chapter illustrations + cover art via Grok Imagine; every image
    also lands in the show's public gallery. Returns
    (chapter_images, cover_art_bytes, images_generated, cost_usd)."""
    chapter_images, cover_art, generated = {}, None, 0
    if args.skip_images:
        logger.info("book art: skipped (--skip-images)")
        return chapter_images, cover_art, generated, 0.0
    if not (volume.image_model and volume.chapter_art_style):
        logger.info("book art: no image_model/style in series config — "
                    "skipping")
        return chapter_images, cover_art, generated, 0.0
    if not api_key:
        logger.warning("book art: no GROK_API_KEY — text-only build")
        return chapter_images, cover_art, generated, 0.0

    per_image = model_cost_usd(volume.image_model)
    est = per_image * (len(chapters) + 1)
    logger.info("book art: %d images on %s, estimated $%.2f",
                len(chapters) + 1, volume.image_model, est)
    if est > args.max_image_cost_usd:
        logger.error("book art: estimate $%.2f exceeds --max-image-cost-usd "
                     "%.2f — refusing", est, args.max_image_cost_usd)
        raise SystemExit(1)

    art_dir = out_dir / "art"
    art_dir.mkdir(parents=True, exist_ok=True)
    for ch in chapters:
        cached = art_dir / f"chapter_{ch.number:03d}.jpg"
        if cached.exists() and cached.stat().st_size > 0:
            chapter_images[ch.number] = cached.read_bytes()
            continue
        prompt = chapter_art_prompt(volume.chapter_art_style, ch)
        raw = generate_art(prompt, api_key=api_key,
                           model=volume.image_model, size=CHAPTER_ART_SIZE)
        if not raw:
            continue  # soft: this chapter ships without art
        jpeg = to_chapter_jpeg(raw)
        cached.write_bytes(jpeg)
        chapter_images[ch.number] = jpeg
        generated += 1
        upload_book_image_to_gallery(
            raw, volume, prompt=prompt, model=volume.image_model,
            intended_use="book_chapter", chapter=ch)

    cover_cache = art_dir / "cover_art.png"
    if cover_cache.exists() and cover_cache.stat().st_size > 0:
        cover_art = cover_cache.read_bytes()
    elif volume.cover_art_style:
        prompt = cover_art_prompt(volume.cover_art_style, volume, chapters)
        cover_art = generate_art(prompt, api_key=api_key,
                                 model=volume.image_model,
                                 size=COVER_ART_SIZE)
        if cover_art:
            cover_cache.write_bytes(cover_art)
            generated += 1
            upload_book_image_to_gallery(
                cover_art, volume, prompt=prompt, model=volume.image_model,
                intended_use="book_cover")

    cost = generated * per_image
    logger.info("book art: %d generated ($%.2f), %d chapters illustrated",
                generated, cost, len(chapter_images))
    return chapter_images, cover_art, generated, cost


def _build_one(volume_id: str, args) -> int:
    vol_path = ROOT / "books" / "volumes" / f"{volume_id}.yaml"
    if not vol_path.exists():
        logger.error("no such volume config: %s", vol_path)
        return 1
    volume = load_volume(vol_path)
    out_dir = OUT_ROOT / volume.volume_id
    out_dir.mkdir(parents=True, exist_ok=True)

    chapters = collect_chapters(volume)
    words = sum(c.word_count for c in chapters)
    logger.info("volume %s: %d chapters, %d words",
                volume.volume_id, len(chapters), words)

    api_key = (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
               or "").strip()
    chapter_images, cover_art, images_generated, images_cost = (
        _generate_book_art(volume, chapters, out_dir, api_key, args))

    cover = generate_cover(volume, out_dir / "cover.png",
                           art_bytes=cover_art)
    epub = build_epub(volume, chapters, out_dir / f"{volume.volume_id}.epub",
                      cover_png=cover, chapter_images=chapter_images)

    # Free sample: the first chapter as its own mini-EPUB, for the site's
    # Books page (email capture's lead magnet).
    sample = build_epub(
        volume, chapters[:1],
        out_dir / f"{volume.volume_id}_sample.epub", cover_png=cover,
        chapter_images={1: chapter_images[1]} if 1 in chapter_images else None,
    )

    entry = {
        "volume_id": volume.volume_id,
        "show_slug": volume.show_slug,
        "show_name": volume.show_name,
        "volume_number": volume.volume_number,
        "title": volume.title,
        "full_title": volume.full_title,
        "subtitle": volume.subtitle,
        "author": volume.author,
        "description": volume.description,
        "language": volume.language,
        "chapters": len(chapters),
        "episodes": volume.episodes,
        "word_count": words,
        "price_usd": volume.price_usd,
        "buy_links": {k: v for k, v in volume.buy_links.items() if v},
        "built_date": date.today().isoformat(),
        "images": {
            "chapters_illustrated": len(chapter_images),
            "generated": images_generated,
            "model": volume.image_model,
            "estimated_cost_usd": round(images_cost, 2),
        },
        "files": {},
        "audiobook": None,
    }

    m4b = None
    if args.skip_audio:
        logger.info("audiobook: skipped (--skip-audio)")
    else:
        if not api_key:
            logger.warning("audiobook: no GROK_API_KEY — skipping narration "
                           "(ebook still built)")
        else:
            texts = [t for _, t in narration_texts(volume, chapters)]
            est = estimate_tts_cost_usd(texts)
            logger.info("audiobook: %d tracks, estimated TTS cost $%.2f",
                        len(texts), est)
            if est > args.max_tts_cost_usd:
                logger.error("audiobook: estimate $%.2f exceeds "
                             "--max-tts-cost-usd %.2f — refusing",
                             est, args.max_tts_cost_usd)
                return 1
            voice_id = os.getenv("BOOK_VOICE_ID", "kdif6sqjcyiq").strip()
            tracks = synthesize_tracks(
                volume, chapters, out_dir / "audio",
                api_key=api_key, voice_id=voice_id,
            )
            m4b = build_m4b(volume, tracks,
                            out_dir / f"{volume.volume_id}.m4b",
                            cover_png=cover)
            entry["audiobook"] = {
                "duration_seconds": round(total_duration_seconds(tracks)),
                "tracks": len(tracks),
                "estimated_tts_cost_usd": round(est, 2),
            }

    if args.no_upload or not _have_r2():
        if not args.no_upload:
            logger.warning("R2 credentials not set — artifacts stay local "
                           "under %s", out_dir)
    else:
        prefix = f"{R2_BOOKS_PREFIX}/{volume.volume_id}"
        entry["files"]["epub"] = _r2_upload(
            epub, f"{prefix}/{epub.name}", "application/epub+zip")
        entry["files"]["sample_epub"] = _r2_upload(
            sample, f"{prefix}/{sample.name}", "application/epub+zip")
        entry["files"]["cover"] = _r2_upload(
            cover, f"{prefix}/cover.png", "image/png")
        if m4b:
            entry["files"]["m4b"] = _r2_upload(
                m4b, f"{prefix}/{m4b.name}", "audio/mp4")
        logger.info("uploaded %d artifacts to R2 under %s/",
                    len(entry["files"]), prefix)

    update_catalog(entry)
    logger.info("catalog updated: books/catalog.json")
    print(json.dumps({k: entry[k] for k in
                      ("volume_id", "chapters", "word_count", "files",
                       "audiobook")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
