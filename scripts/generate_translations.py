#!/usr/bin/env python3
"""Generate multilingual (FR / RU / ES / ZH) audio tracks for episodes.

A post-hoc driver over ``engine.multilingual``: it consumes a show's
already-finalized English episode artifacts (the ``*_tts.txt`` script + the
summaries record + the ``.md`` digest hook) and, per language, translates the
script via ``grok-latest``, renders it with the cloned Grok voice, uploads the
track to R2 alongside the English file, and records it on the episode.

English stays the canonical master + site fallback; translations are derived
artifacts surfaced on the website. The same per-episode core runs automatically
in the daily pipeline (``run_show.py``) for shows with ``multilingual.auto``.

Usage
-----
    python scripts/generate_translations.py tesla --languages fr --latest 1
    python scripts/generate_translations.py tesla --languages zh --episode 511 --sample-zh
    python scripts/generate_translations.py <show> --languages fr,ru,es,zh --latest 3 --zh-approved

Idempotent: a (episode, language) already present is skipped unless ``--force``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

from engine import multilingual, translate, tts  # noqa: E402
from engine.config import load_config  # noqa: E402
from engine.summaries_io import load_summaries  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(levelname)s %(message)s")
logger = logging.getLogger("generate_translations")

# Grok TTS list price (~$4.20 / 1M chars) for the up-front projection.
_TTS_USD_PER_MILLION = 4.20


def _select_records(records: List[dict], latest: int, episode: Optional[int]) -> List[dict]:
    have_num = [r for r in records if isinstance(r.get("episode_num"), int)]
    if episode is not None:
        return [r for r in have_num if r["episode_num"] == episode]
    return sorted(have_num, key=lambda r: r["episode_num"], reverse=True)[:latest]


def _resolve_languages(args, config) -> List[str]:
    if args.languages:
        langs = [s.strip() for s in args.languages.split(",") if s.strip()]
    elif getattr(config, "multilingual", None) and config.multilingual.languages:
        langs = list(config.multilingual.languages)
    else:
        langs = list(translate.supported_languages())
    unknown = [code for code in langs if code not in translate.supported_languages()]
    if unknown:
        raise SystemExit(f"Unsupported language(s): {unknown}; "
                         f"supported: {translate.supported_languages()}")
    return langs


def _log_cost_projection(targets, languages, output_dir, force) -> None:
    total_chars, tracks = 0, 0
    for rec in targets:
        tf = multilingual.find_tts_file(output_dir, rec.get("episode_num"))
        if not tf:
            continue
        n = len(tf.read_text(encoding="utf-8"))
        existing = rec.get("translations", {}) or {}
        for lang in languages:
            if lang in existing and not force:
                continue
            total_chars += n
            tracks += 1
    if not tracks:
        return
    cost = total_chars / 1_000_000 * _TTS_USD_PER_MILLION
    logger.info("Projection: %d track(s), ~%s TTS chars, ~$%.2f Grok TTS "
                "(+ translation LLM tokens). --dry-run previews without spending.",
                tracks, f"{total_chars:,}", cost)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("show", help="Show slug (e.g. tesla)")
    ap.add_argument("--languages", default="", help="Comma list of BCP-47 codes (fr,ru,es,zh)")
    ap.add_argument("--latest", type=int, default=3, help="Translate the latest N episodes")
    ap.add_argument("--episode", type=int, default=None, help="Translate one specific episode number")
    ap.add_argument("--force", action="store_true", help="Regenerate even if a track exists")
    ap.add_argument("--sample-zh", action="store_true",
                    help="Render ONE short ZH clip from the latest episode, then STOP")
    ap.add_argument("--zh-approved", action="store_true",
                    help="Confirm you've listened to a ZH sample — required to batch ZH manually")
    ap.add_argument("--sample-chars", type=int, default=900, help="Char budget for --sample-zh clip")
    ap.add_argument("--dry-run", action="store_true", help="Translate only; no TTS/upload/record")
    args = ap.parse_args()

    config = load_config(f"shows/{args.show}.yaml")
    ml = getattr(config, "multilingual", None)
    if not (ml and ml.enabled) and not args.languages:
        raise SystemExit(
            f"Multilingual audio is not enabled for '{args.show}'. Enable it in "
            "the show YAML (multilingual.enabled: true) or pass --languages."
        )
    output_dir = PROJECT_ROOT / config.episode.output_dir
    summaries_path = PROJECT_ROOT / config.publishing.summaries_json
    languages = _resolve_languages(args, config)
    # Reuses the show's existing Grok voice (tts.voice_id) by default; the
    # GROK_CLONED_VOICE_ID env var is an optional override.
    voice_id_resolved = multilingual.resolve_multilingual_voice(config)

    _wrapper, records = load_summaries(summaries_path)
    targets = _select_records(records, args.latest, args.episode)
    if not targets:
        logger.error("No matching episode records in %s", summaries_path)
        return 1

    # ----- ZH STOP checkpoint -----------------------------------------
    if args.sample_zh:
        api_key = multilingual.grok_api_key()
        voice_id = voice_id_resolved
        if not voice_id:
            raise SystemExit("No voice_id: set the show's tts.voice_id or GROK_CLONED_VOICE_ID")
        ep = targets[0]["episode_num"]
        tf = multilingual.find_tts_file(output_dir, ep)
        if not tf:
            logger.error("No _tts.txt for Ep%s in %s", ep, output_dir)
            return 1
        snippet = tf.read_text(encoding="utf-8").strip()[: args.sample_chars]
        logger.info("ZH SAMPLE: localizing first ~%d chars of Ep%s", args.sample_chars, ep)
        zh_text = translate.translate_script(snippet, "zh")
        sample_mp3 = output_dir / f"{tf.stem.replace('_tts', '')}.zh.sample.mp3"
        multilingual.render_track(zh_text, "zh", voice_id, api_key, sample_mp3,
                                  config.tts.max_chars or tts.GROK_MAX_CHARS_PER_REQUEST)
        dur = multilingual.ffprobe_duration(str(sample_mp3))
        logger.info("=" * 60)
        logger.info("ZH SAMPLE READY: %s (%.1fs) — LISTEN before batch ZH. Re-run "
                    "with --zh-approved if it sounds right.", sample_mp3, dur or 0.0)
        logger.info("=" * 60)
        return 0

    if "zh" in languages and not args.zh_approved and not args.dry_run:
        logger.warning("ZH requested without --zh-approved. Skipping Chinese this run. "
                       "Run --sample-zh first, listen, then re-run with --zh-approved.")
        languages = [code for code in languages if code != "zh"]
        if not languages:
            return 0

    _log_cost_projection(targets, languages, output_dir, args.force)
    api_key = multilingual.grok_api_key()
    if not args.dry_run and not voice_id_resolved:
        raise SystemExit("No voice_id: set the show's tts.voice_id or GROK_CLONED_VOICE_ID")
    voice_id = "" if args.dry_run else voice_id_resolved

    any_done = False
    for rec in targets:
        ep = rec["episode_num"]
        logger.info("Ep%s: generating %s …", ep, languages)
        results = multilingual.generate_for_episode(
            config, ep, languages,
            voice_id=voice_id or "", api_key=api_key,
            force=args.force, dry_run=args.dry_run,
        )
        if any(v == "done" for v in results.values()):
            any_done = True

    if not any_done and not args.dry_run:
        logger.info("Nothing new generated (all requested tracks already present).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
