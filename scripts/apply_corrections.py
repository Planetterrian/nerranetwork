#!/usr/bin/env python3
"""Apply text amendments from a show's ``corrections.yaml`` to committed surfaces.

A correction that carries ``replacements`` and/or ``headline`` rewrites the
digest, reader/TTS scripts, transcripts, chapters JSON, summaries and the
podcast RSS item so the false claim is gone from every text surface. The
dated Correction box still renders from the same YAML. Audio is never
edited here — use ``scripts/resynthesize_episode.py`` when ``where`` is
``audio`` or ``both``.

Dry-run by default. ``--apply`` writes.

Usage:
    python scripts/apply_corrections.py --show unintended_consequences --episode 139
    python scripts/apply_corrections.py --show tesla --episode 634 --apply
    python scripts/apply_corrections.py --show tesla --episode 634 --apply --regen-blog
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.corrections import (  # noqa: E402
    apply_episode_amendments,
    corrections_for,
    has_text_amendments,
    load_corrections,
)

logger = logging.getLogger("apply_corrections")


def _show_dir_and_rss(slug: str):
    """Resolve digest dir + podcast RSS path(s) for a registry slug."""
    from engine.config import load_config

    yaml_path = ROOT / "shows" / f"{slug}.yaml"
    if not yaml_path.is_file():
        digests = ROOT / "digests" / slug
        if digests.is_dir():
            return digests, []
        raise SystemExit(f"Unknown show slug: {slug}")

    config = load_config(yaml_path)
    digests = ROOT / config.episode.output_dir
    rss = []
    feed = getattr(config.publishing, "rss_file", "") or ""
    if feed:
        rss.append(ROOT / feed)
    for alias in getattr(config.publishing, "rss_aliases", None) or []:
        rss.append(ROOT / alias)
    blog_rss = ROOT / f"blog_{slug}.rss"
    if blog_rss.is_file():
        rss.append(blog_rss)
    for cand in (
        ROOT / f"{slug}_podcast.rss",
        ROOT / "podcast.rss" if slug == "tesla" else None,
    ):
        if cand and cand.is_file() and cand not in rss:
            rss.append(cand)
    return digests, [p for p in rss if p.is_file()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", required=True, help="Show slug (YAML name)")
    parser.add_argument("--episode", type=int, required=True)
    parser.add_argument("--apply", action="store_true",
                        help="Write changes (default is dry-run)")
    parser.add_argument("--regen-blog", action="store_true",
                        help="After apply, regenerate the episode blog page")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    show_dir, rss_paths = _show_dir_and_rss(args.show)
    entries = corrections_for(show_dir, args.episode)
    if not entries:
        logger.error("No correction filed for %s ep %s in %s",
                     args.show, args.episode, show_dir)
        return 1
    amending = [c for c in entries if has_text_amendments(c)]
    if not amending:
        logger.error(
            "Correction(s) exist for ep %s but none carry replacements/headline. "
            "Add those fields to corrections.yaml (see docs/corrections.md).",
            args.episode,
        )
        return 1

    report = apply_episode_amendments(
        show_dir,
        args.episode,
        dry_run=not args.apply,
        rss_paths=rss_paths,
    )
    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info(
        "%s ep %s: %s hits across %s file(s)",
        mode, args.episode, report["hits"], len(report["files_touched"]),
    )
    for path in report["files_touched"]:
        logger.info("  %s", path)

    if args.apply and args.regen_blog:
        logger.info("Regenerating blog posts for %s…", args.show)
        from generate_html import generate_blog_posts
        generate_blog_posts(args.show)

    if not args.apply:
        logger.info("Re-run with --apply to write. Audio needs resynthesize separately.")
    return 0 if report["hits"] or not amending else 0


if __name__ == "__main__":
    # Silence unused import warning for load_corrections in type checkers
    _ = load_corrections
    raise SystemExit(main())
