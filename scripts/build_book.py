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


def _r2_upload(local: Path, key: str, content_type: str, *,
               private: bool = False) -> str:
    """Upload one artifact and return the reference the catalog records.

    The books keyspace spans TWO buckets, and which one a file lands in
    is a commercial decision, not a technical one:

    * **public** (``podcast-audio``, https://audio.nerranetwork.com) —
      ``cover.png`` and the sample EPUB. Marketing assets: the cover
      feeds /books.html, the sample is the email-capture lead magnet.
      These return ordinary https URLs.
    * **private** (``nerra-books``, no public hostname) — the full EPUB,
      the M4B, and the per-chapter narration masters. This is the PAID
      product. Buyers receive it from the store they bought it at
      (Payhip is merchant-of-record for direct sales); the network never
      serves it. These return an ``r2://bucket/key`` reference, which
      says where the master lives without implying anyone can fetch it.

    Until 2026-08-26 every artifact went to the public bucket and its URL
    was committed to ``books/catalog.json`` in a PUBLIC repo: 596
    objects, 3.1 GB, the entire paid catalogue free to anyone who opened
    the JSON. The lost sales are the smaller half. Amazon price-matches
    against a cheaper copy found elsewhere and then pays 70% of the
    MATCHED price, so one public master can zero out KDP royalties
    across every volume at once — which is why docs/books.md's first
    operating rule is never to undercut retail.
    """
    from engine.storage import upload_to_r2

    bucket = _books_private_bucket() if private else _books_bucket()
    url = upload_to_r2(
        local, key,
        bucket=bucket,
        endpoint_url=os.getenv("R2_ENDPOINT_URL", "").strip(),
        access_key=os.getenv("R2_ACCESS_KEY_ID", "").strip(),
        secret_key=os.getenv("R2_SECRET_ACCESS_KEY", "").strip(),
        # A private bucket has no public host; passing one would mint a
        # URL that 404s and read like a promise the bucket cannot keep.
        public_base_url="" if private else os.getenv(
            "R2_BOOKS_PUBLIC_BASE_URL",
            "https://audio.nerranetwork.com").strip(),
        content_type=content_type,
    )
    return f"r2://{bucket}/{key}" if private else url


def _have_r2() -> bool:
    return all(os.getenv(k, "").strip() for k in
               ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"))


def _unbuilt_volume_ids() -> list:
    """Volume configs whose catalog entry is absent or has no files."""
    import json
    built = {}
    catalog = ROOT / "books" / "catalog.json"
    if catalog.exists():
        for v in json.loads(catalog.read_text(encoding="utf-8")).get(
                "volumes", []):
            built[v.get("volume_id")] = bool(v.get("files"))
    return [p.stem for p in sorted((ROOT / "books" / "volumes").glob("*.yaml"))
            if not built.get(p.stem)]


def _r2_client():
    import boto3
    from botocore.config import Config as BotoConfig
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT_URL", "").strip(),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID", "").strip(),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", "").strip(),
        config=BotoConfig(signature_version="s3v4"),
    )


def _books_bucket() -> str:
    """Public bucket: covers and samples only."""
    return os.getenv("R2_BOOKS_BUCKET", "podcast-audio").strip()


def _books_private_bucket() -> str:
    """Private bucket holding the paid masters. Created 2026-08-26 with
    public access disabled; nothing serves out of it."""
    return os.getenv("R2_BOOKS_PRIVATE_BUCKET", "nerra-books").strip()


def _restore_audio_cache(volume, audio_dir: Path) -> int:
    """Pull previously narrated tracks (and their text-hash sidecars)
    down from R2 so a CI re-run resumes instead of re-billing TTS. The
    hash sidecar is what makes reuse safe: engine.audiobook regenerates
    any track whose narration text changed. Soft-fails to zero restores."""
    if not _have_r2():
        return 0
    prefix = f"{R2_BOOKS_PREFIX}/{volume.volume_id}/audio/"
    restored = 0
    try:
        s3 = _r2_client()
        paginator = s3.get_paginator("list_objects_v2")
        audio_dir.mkdir(parents=True, exist_ok=True)
        for page in paginator.paginate(Bucket=_books_private_bucket(),
                                       Prefix=prefix):
            for obj in page.get("Contents", []):
                name = obj["Key"].rsplit("/", 1)[-1]
                local = audio_dir / name
                if name.startswith("track_") and not local.exists():
                    s3.download_file(_books_private_bucket(),
                                     obj["Key"], str(local))
                    restored += 1
    except Exception as exc:  # noqa: BLE001 — cache is never build-fatal
        logger.warning("audio cache restore failed (continuing cold): %s",
                       exc)
    if restored:
        logger.info("audio cache: restored %d object(s) from R2", restored)
    return restored


def _persist_audio_cache(volume, audio_dir: Path) -> None:
    """Push narrated tracks + hash sidecars to R2. Doubles as the
    per-chapter MP3 delivery for audiobook-store submission (Spotify's
    ingest wants chapterized MP3s — they live at
    books/<id>/audio/track_NNN.mp3 in the PRIVATE bucket, and are handed
    to an aggregator by upload, never by URL)."""
    if not _have_r2() or not audio_dir.exists():
        return
    try:
        for f in sorted(audio_dir.glob("track_*")):
            ctype = "audio/mpeg" if f.suffix == ".mp3" else "text/plain"
            _r2_upload(
                f, f"{R2_BOOKS_PREFIX}/{volume.volume_id}/audio/{f.name}",
                ctype, private=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("audio cache persist failed (tracks stay local "
                       "only): %s", exc)


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
    ap.add_argument("--cover-variant", default="",
                    help="Override the volume's cover_variant for local "
                    "iteration. The value that ships MUST end up committed "
                    "as cover_variant: in the volume YAML — the shipped "
                    "cover has to be reproducible from the repo.")
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
    if args.build_planned:
        # A volume config with no artifacts in the catalog is pending work
        # regardless of WHEN it was planned. Without this, planner mode
        # only ever built volumes created in the same run — the first
        # live dispatch (2026-08-22) went green in 70 s having built
        # nothing, and the monthly cron would have no-opped forever.
        pending = _unbuilt_volume_ids()
        if pending:
            logger.info("planner mode: %d committed volume(s) have no "
                        "built artifacts: %s", len(pending), pending)
            to_build.extend(pending)
    if args.volume:
        to_build.append(args.volume)
    # Dedup, order-preserving (a just-planned volume is also "unbuilt").
    to_build = list(dict.fromkeys(to_build))
    if not to_build:
        if args.build_planned:
            logger.info("planner mode: every committed volume is built "
                        "and cataloged — nothing to do")
        else:
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
        return chapter_images, cover_art, generated, 0.0, []
    if not (volume.image_model and volume.chapter_art_style):
        logger.info("book art: no image_model/style in series config — "
                    "skipping")
        return chapter_images, cover_art, generated, 0.0, []
    if not api_key:
        logger.warning("book art: no GROK_API_KEY — text-only build")
        return chapter_images, cover_art, generated, 0.0, []

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
        if not raw:  # one retry — transient API failures are common enough
            raw = generate_art(prompt, api_key=api_key,
                               model=volume.image_model,
                               size=CHAPTER_ART_SIZE)
        if not raw:
            continue  # soft: this chapter ships without art (reported below)
        jpeg = to_chapter_jpeg(raw)
        cached.write_bytes(jpeg)
        chapter_images[ch.number] = jpeg
        generated += 1
        upload_book_image_to_gallery(
            raw, volume, prompt=prompt, model=volume.image_model,
            intended_use="book_chapter", chapter=ch)

    # Cache keys on the variant: a bumped cover_variant must never be
    # served the previous variant's cached image.
    _variant = str(getattr(args, "cover_variant", "") or
                   volume.cover_variant or "").strip()
    _suffix = f"_v{_variant}" if _variant else ""
    cover_cache = art_dir / f"cover_art{_suffix}.png"
    if cover_cache.exists() and cover_cache.stat().st_size > 0:
        cover_art = cover_cache.read_bytes()
    elif volume.cover_art_style:
        prompt = cover_art_prompt(volume.cover_art_style, volume, chapters,
                                  variant=_variant)
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
    missing = [c.number for c in chapters if c.number not in chapter_images]
    if missing:
        # Loud but non-fatal — the first live build shipped 19/20
        # illustrated with zero report. The ::warning:: renders as a GitHub
        # Actions annotation; the catalog records it durably (see caller).
        print(f"::warning::book art: volume {volume.volume_id} chapters "
              f"WITHOUT illustration after retry: {missing}")
    return chapter_images, cover_art, generated, cost, missing


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
    chapter_images, cover_art, images_generated, images_cost, art_missing = (
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
            "chapters_missing_art": art_missing,
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
            audio_dir = out_dir / "audio"
            if not args.no_upload:
                _restore_audio_cache(volume, audio_dir)
            tracks = synthesize_tracks(
                volume, chapters, audio_dir,
                api_key=api_key, voice_id=voice_id,
            )
            if not args.no_upload:
                _persist_audio_cache(volume, audio_dir)
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
            epub, f"{prefix}/{epub.name}", "application/epub+zip",
            private=True)
        entry["files"]["sample_epub"] = _r2_upload(
            sample, f"{prefix}/{sample.name}", "application/epub+zip")
        entry["files"]["cover"] = _r2_upload(
            cover, f"{prefix}/cover.png", "image/png")
        if m4b:
            entry["files"]["m4b"] = _r2_upload(
                m4b, f"{prefix}/{m4b.name}", "audio/mp4", private=True)
        logger.info("uploaded %d artifacts to R2 under %s/",
                    len(entry["files"]), prefix)

    # A CI build that was SUPPOSED to upload but produced no files is a
    # failure, not a green run — the "Verify book integrity" step used to
    # pass on a zero-output run because it only exercised the compiler.
    if not args.no_upload and _have_r2() and not entry["files"].get("epub"):
        logger.error("build produced no uploaded EPUB for %s — failing "
                     "instead of cataloging an empty volume",
                     volume.volume_id)
        return 1

    if entry["files"]:
        update_catalog(entry)
        logger.info("catalog updated: books/catalog.json")
    else:
        # A build with nothing uploaded (--no-upload dry run, or missing
        # R2 creds) must not clobber a previously published entry: the
        # catalog records what SHIPPED, and a local rebuild of vol1 once
        # replaced its live files block with an empty one.
        logger.info("catalog NOT updated — no uploaded artifacts "
                    "(local artifacts remain under outputs/books/)")
    print(json.dumps({k: entry[k] for k in
                      ("volume_id", "chapters", "word_count", "files",
                       "audiobook")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
