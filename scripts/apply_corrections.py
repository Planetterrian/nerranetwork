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
    apply_replacements,
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


#: The interview shows keep a content-lake row per episode
#: (``episode_records``) that Mira reads back to the next guest.
INTERVIEW_SHOWS = ("age_of_ai", "nerra_voices")
#: The text columns of an episode record a correction can reach.
RECORD_TEXT_FIELDS = ("summary", "claims", "predictions", "quotes",
                      "follow_ups", "unanswered")


def amend_record_fields(record: dict, entries: list) -> tuple[dict, int]:
    """Pure: the changed text columns of one ``episode_records`` row after
    every entry's ``replacements``, and the hit count. Headlines are not
    applied (a record has no title)."""
    replacements = [r for c in entries for r in (c.get("replacements") or [])]
    hits = 0

    def walk(obj):
        nonlocal hits
        if isinstance(obj, str):
            new, n = apply_replacements(obj, replacements)
            hits += n
            return new
        if isinstance(obj, list):
            return [walk(v) for v in obj]
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        return obj

    patch = {}
    for field in RECORD_TEXT_FIELDS:
        if field not in record:
            continue
        before = hits
        new = walk(record[field])
        if hits > before:
            patch[field] = new
    return patch, hits


def amend_episode_record(slug: str, episode: int, entries: list, *, apply: bool) -> int:
    """Carry the correction into the interview's ``episode_records`` row.

    Nov 4 2026: Michael Kamins' Pyvot correction reached the package and the
    post but not ``episode_records``, whose summary, claims and predictions
    still said "Pivot" — the record Mira quotes to the next guest. Returns
    the hit count; a missing Supabase configuration is logged, never fatal,
    and leaves the record for a run that has it."""
    if slug not in INTERVIEW_SHOWS:
        return 0
    try:
        sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
        from common import sb_select, sb_update
        interviews = sb_select("interviews", f"show=eq.{slug}&episode_number=eq.{episode}"
                                             "&select=id&limit=1")
        if not interviews and slug == "age_of_ai":
            # Rows from before the show column default to The Age of AI.
            interviews = sb_select("interviews", f"show=is.null&episode_number=eq.{episode}"
                                                 "&select=id&limit=1")
        if not interviews:
            logger.warning("episode record: no interview for %s Ep%s", slug, episode)
            return 0
        records = sb_select("episode_records",
                            f"interview_id=eq.{interviews[0]['id']}"
                            "&select=id," + ",".join(RECORD_TEXT_FIELDS))
    except Exception as exc:  # noqa: BLE001 — the text surfaces are already done
        logger.warning("episode record NOT amended (%s): %s", type(exc).__name__, exc)
        return 0
    total = 0
    for record in records:
        patch, hits = amend_record_fields(record, entries)
        total += hits
        if patch:
            logger.info("  episode_records %s: %s hit(s) in %s", record["id"], hits,
                        ", ".join(patch))
            if apply:
                sb_update("episode_records", f"id=eq.{record['id']}", patch)
    return total


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
    record_hits = amend_episode_record(args.show, args.episode, amending, apply=args.apply)
    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info(
        "%s ep %s: %s hits across %s file(s)",
        mode, args.episode, report["hits"], len(report["files_touched"]),
    )
    for path in report["files_touched"]:
        logger.info("  %s", path)
    if record_hits:
        logger.info("%s ep %s: %s hit(s) in the episode record", mode, args.episode, record_hits)

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
