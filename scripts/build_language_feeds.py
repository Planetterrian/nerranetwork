#!/usr/bin/env python3
"""Build per-language podcast RSS feeds for the multilingual shows.

For each multilingual-enabled show and each language that has at least one
translated episode track (recorded in the show's ``summaries_<slug>.json``),
emit a standalone Apple/Spotify-ready feed next to the English one:

    spacex_podcast.rss        (English, canonical — untouched)
    spacex_podcast.fr.rss     (French tracks only)
    spacex_podcast.es.rss     (Spanish tracks only)
    ...

The feeds are rebuilt **fresh from the canonical summaries JSON** every run
(idempotent), so this is safe to run nightly. Channel title/description are
translated **once** and cached in ``digests/<slug>/channel_i18n.json``; with
no Grok key set the build still produces valid feeds with an autonym-suffixed
English title.

Usage
-----
    python scripts/build_language_feeds.py --all
    python scripts/build_language_feeds.py spacex
    python scripts/build_language_feeds.py spacex --languages fr,es
    python scripts/build_language_feeds.py --all --refresh-channel-i18n
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:  # noqa: BLE001 — dotenv optional in CI
    pass

from engine import language_feeds  # noqa: E402
from engine.config import load_config  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_language_feeds")


def _discover_show_slugs() -> List[str]:
    slugs = []
    for path in sorted((PROJECT_ROOT / "shows").glob("*.yaml")):
        name = path.stem
        if name.startswith("_") or name in {"network_meta"}:
            continue
        slugs.append(name)
    return slugs


def _grok_available() -> bool:
    return bool((os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip())


def build_for_show(
    slug: str,
    languages: Optional[List[str]],
    *,
    refresh_channel_i18n: bool,
    allow_translate: bool,
) -> List[str]:
    """Build all enabled-language feeds for one show. Returns public URLs."""
    config = load_config(f"shows/{slug}.yaml")
    ml = getattr(config, "multilingual", None)
    if not (ml and ml.enabled):
        logger.info("[%s] multilingual disabled — skipping", slug)
        return []

    summaries_path = PROJECT_ROOT / config.publishing.summaries_json
    if not summaries_path.exists():
        logger.warning("[%s] no summaries file at %s — skipping", slug, summaries_path)
        return []

    langs = languages or list(ml.languages) or list(language_feeds.supported_feed_languages())
    langs = [c for c in langs if c in language_feeds.supported_feed_languages()]

    translate_fn = None
    if allow_translate and _grok_available():
        from engine.translate import translate_metadata

        translate_fn = translate_metadata

    base_url = config.publishing.base_url.rstrip("/")
    urls: List[str] = []
    for lang in langs:
        ch_title, ch_desc = language_feeds.resolve_channel_i18n(
            summaries_path,
            lang,
            config.publishing.rss_title,
            config.publishing.rss_description.strip(),
            translate_fn=translate_fn,
            refresh=refresh_channel_i18n,
        )
        out_path = PROJECT_ROOT / language_feeds.feed_filename(config.publishing.rss_file, lang)
        result = language_feeds.build_language_feed(
            slug=slug,
            lang=lang,
            summaries_path=summaries_path,
            out_path=out_path,
            guid_prefix=config.publishing.guid_prefix,
            channel_title=ch_title,
            channel_description=ch_desc,
            channel_link=config.publishing.rss_link,
            channel_author=config.publishing.rss_author,
            channel_email=config.publishing.rss_email,
            channel_image=config.publishing.rss_image,
            channel_category=config.publishing.rss_category,
            channel_subcategory=getattr(config.publishing, "rss_subcategory", ""),
            base_url=base_url,
        )
        if result:
            urls.append(f"{base_url}/{out_path.name}")
    return urls


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("show", nargs="?", help="Show slug (omit with --all)")
    ap.add_argument("--all", action="store_true", help="Build feeds for every multilingual show")
    ap.add_argument("--languages", default="", help="Comma list of BCP-47 codes to limit to")
    ap.add_argument(
        "--refresh-channel-i18n",
        action="store_true",
        help="Re-translate cached channel title/description (needs GROK_API_KEY)",
    )
    ap.add_argument(
        "--no-translate",
        action="store_true",
        help="Never call Grok; use cached channel i18n or the autonym fallback",
    )
    args = ap.parse_args()

    if not args.all and not args.show:
        ap.error("pass a show slug or --all")

    langs = [s.strip() for s in args.languages.split(",") if s.strip()] or None
    slugs = _discover_show_slugs() if args.all else [args.show]

    all_urls: List[str] = []
    for slug in slugs:
        try:
            all_urls.extend(
                build_for_show(
                    slug,
                    langs,
                    refresh_channel_i18n=args.refresh_channel_i18n,
                    allow_translate=not args.no_translate,
                )
            )
        except FileNotFoundError:
            logger.warning("[%s] config not found — skipping", slug)
        except Exception as exc:  # noqa: BLE001 — one show must not block the rest
            logger.error("[%s] feed build failed: %s", slug, exc)

    if all_urls:
        logger.info("=" * 64)
        logger.info("Built %d language feed(s):", len(all_urls))
        for url in all_urls:
            logger.info("  %s", url)
        logger.info("Submit each to Apple Podcasts Connect / Spotify for Podcasters.")
    else:
        logger.info("No language feeds built (no translated episodes yet).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
