#!/usr/bin/env python3
"""Generate multilingual (FR / RU / ES / ZH) audio tracks for episodes.

A post-hoc stage: it consumes a show's already-finalized English episode
artifacts (the ``*_tts.txt`` script + the summaries record + the ``.md``
digest for the hook) and, per language, translates the script via
``grok-latest``, renders it to MP3 with the operator's cloned Grok voice,
uploads the track to R2 alongside the English file, and records the track
(audio URL + translated title/description) in the show's summaries JSON.

English stays the canonical master + site fallback; translations are
derived artifacts surfaced on the website only (not the podcast RSS).

Usage
-----
    # Wire-up / proving runs
    python scripts/generate_translations.py tesla --languages fr --latest 1
    python scripts/generate_translations.py tesla --languages zh \
        --episode 511 --sample-zh          # ONE short ZH clip, then STOP

    # After listening to the ZH sample and approving it:
    python scripts/generate_translations.py tesla \
        --languages fr,ru,es,zh --latest 3 --zh-approved

Idempotent: a (episode, language) already present in the summaries record is
skipped unless ``--force``.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

from engine import tts, translate  # noqa: E402
from engine.config import load_config  # noqa: E402
from engine.storage import upload_to_r2  # noqa: E402
from engine.summaries_io import load_summaries, save_summaries  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(levelname)s %(message)s")
logger = logging.getLogger("generate_translations")


def _grok_api_key() -> str:
    key = (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Missing GROK_API_KEY (or XAI_API_KEY) in .env")
    return key


def _ffprobe_duration(target: str) -> Optional[float]:
    """Return media duration in seconds (works on a local path OR a URL)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", target],
            capture_output=True, text=True, timeout=120,
        )
        val = out.stdout.strip()
        return float(val) if val else None
    except Exception:  # noqa: BLE001 — best-effort, used only for reporting
        return None


def _find_episode_file(output_dir: Path, episode_num: int, suffix_glob: str) -> Optional[Path]:
    matches = sorted(output_dir.glob(f"*_Ep{episode_num:03d}_{suffix_glob}"))
    return matches[-1] if matches else None


def _english_hook(output_dir: Path, episode_num: int) -> str:
    """Best-effort: pull the episode hook from the digest .md for descriptions."""
    md = None
    for p in sorted(output_dir.glob(f"*_Ep{episode_num:03d}_*.md")):
        if not p.name.endswith("_tts.txt"):
            md = p
    if not md:
        return ""
    try:
        from engine.blog import extract_blog_metadata
        meta = extract_blog_metadata(md.read_text(encoding="utf-8"), "", md.name, md)
        return meta.get("hook", "") or ""
    except Exception:  # noqa: BLE001
        return ""


def _derive_track_key_url(english_audio_url: str, lang: str, public_base_url: str):
    """Return ``(remote_key, public_url)`` for the *lang* track.

    Derived from the English track's own URL so the translation lands in the
    exact same R2 prefix regardless of slug/audio_subdir nuances.
    """
    base = (public_base_url or "").rstrip("/")
    if base and english_audio_url.startswith(base + "/"):
        key = english_audio_url[len(base) + 1:]
    else:
        key = urlparse(english_audio_url).path.lstrip("/")
    if key.lower().endswith(".mp3"):
        key = key[:-4]
    remote_key = f"{key}.{lang}.mp3"
    public_url = f"{base}/{remote_key}" if base else remote_key
    return remote_key, public_url


def _select_records(records: List[dict], latest: int, episode: Optional[int]) -> List[dict]:
    """Pick target records: a specific --episode, else the latest N by number."""
    have_num = [r for r in records if isinstance(r.get("episode_num"), int)]
    if episode is not None:
        return [r for r in have_num if r["episode_num"] == episode]
    return sorted(have_num, key=lambda r: r["episode_num"], reverse=True)[:latest]


def _render_track(
    script_text: str, lang: str, voice_id: str, api_key: str,
    out_path: Path, max_chars: int,
) -> None:
    tts.synthesize(
        script_text, voice_id, out_path,
        api_key=api_key, provider="grok",
        max_chars=max_chars, language_code=lang,
    )


def _resolve_languages(args, config) -> List[str]:
    if args.languages:
        langs = [s.strip() for s in args.languages.split(",") if s.strip()]
    elif getattr(config, "multilingual", None) and config.multilingual.languages:
        langs = list(config.multilingual.languages)
    else:
        langs = list(translate.supported_languages())
    unknown = [l for l in langs if l not in translate.supported_languages()]
    if unknown:
        raise SystemExit(f"Unsupported language(s): {unknown}; "
                         f"supported: {translate.supported_languages()}")
    return langs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("show", help="Show slug (e.g. tesla)")
    ap.add_argument("--languages", default="", help="Comma list of BCP-47 codes (fr,ru,es,zh)")
    ap.add_argument("--latest", type=int, default=3, help="Translate the latest N episodes")
    ap.add_argument("--episode", type=int, default=None, help="Translate one specific episode number")
    ap.add_argument("--force", action="store_true", help="Re-generate even if a track already exists")
    ap.add_argument("--sample-zh", action="store_true",
                    help="Render ONE short ZH clip from the latest episode, then STOP (no upload/record)")
    ap.add_argument("--zh-approved", action="store_true",
                    help="Confirm you've listened to a ZH sample — required to batch ZH")
    ap.add_argument("--sample-chars", type=int, default=900, help="Char budget for --sample-zh clip")
    ap.add_argument("--dry-run", action="store_true", help="Translate only; no TTS/upload/record")
    args = ap.parse_args()

    config = load_config(f"shows/{args.show}.yaml")
    ml = getattr(config, "multilingual", None)
    if not (ml and ml.enabled) and not args.languages:
        raise SystemExit(
            f"Multilingual audio is not enabled for '{args.show}'. "
            "Enable it in the show YAML (multilingual.enabled: true) or pass "
            "--languages to override for a one-off run."
        )
    output_dir = PROJECT_ROOT / config.episode.output_dir
    summaries_path = PROJECT_ROOT / config.publishing.summaries_json
    languages = _resolve_languages(args, config)
    voice_env = (getattr(config, "multilingual", None) and config.multilingual.cloned_voice_env) \
        or "GROK_CLONED_VOICE_ID"
    max_chars = config.tts.max_chars or tts.GROK_MAX_CHARS_PER_REQUEST

    wrapper, records = load_summaries(summaries_path)
    targets = _select_records(records, args.latest, args.episode)
    if not targets:
        logger.error("No matching episode records in %s", summaries_path)
        return 1

    # ----- ZH STOP checkpoint -----------------------------------------
    if args.sample_zh:
        api_key = _grok_api_key()
        voice_id = tts.get_cloned_voice_id(voice_env)
        rec = targets[0]
        ep = rec["episode_num"]
        tts_file = _find_episode_file(output_dir, ep, "*_tts.txt")
        if not tts_file:
            logger.error("No _tts.txt for Ep%s in %s", ep, output_dir)
            return 1
        english_script = tts_file.read_text(encoding="utf-8").strip()
        snippet = english_script[: args.sample_chars]
        logger.info("ZH SAMPLE: localizing first ~%d chars of Ep%s", args.sample_chars, ep)
        zh_text = translate.translate_script(snippet, "zh")
        sample_mp3 = output_dir / f"{tts_file.stem.replace('_tts', '')}.zh.sample.mp3"
        _render_track(zh_text, "zh", voice_id, api_key, sample_mp3, max_chars)
        dur = _ffprobe_duration(str(sample_mp3))
        logger.info("=" * 64)
        logger.info("ZH SAMPLE READY: %s (%.1fs)", sample_mp3, dur or 0.0)
        logger.info("LISTEN before batch-generating Chinese. Cloned English")
        logger.info("voices can produce flat/incorrect Mandarin tones. If it")
        logger.info("sounds right, re-run with --zh-approved.")
        logger.info("=" * 64)
        return 0

    if "zh" in languages and not args.zh_approved and not args.dry_run:
        logger.warning("ZH requested without --zh-approved. Skipping Chinese this run.")
        logger.warning("Run:  python scripts/generate_translations.py %s "
                       "--languages zh --episode %s --sample-zh", args.show, targets[0]["episode_num"])
        logger.warning("listen, then re-run with --zh-approved to include ZH.")
        languages = [l for l in languages if l != "zh"]
        if not languages:
            return 0

    api_key = _grok_api_key()
    voice_id = None if args.dry_run else tts.get_cloned_voice_id(voice_env)

    # Length-calibration reporting: first rendered track per language.
    reported_langs: set = set()
    changed = False

    for rec in targets:
        ep = rec["episode_num"]
        english_url = rec.get("audio_url", "")
        tts_file = _find_episode_file(output_dir, ep, "*_tts.txt")
        if not tts_file:
            logger.warning("Ep%s: no _tts.txt found in %s — skipping", ep, output_dir)
            continue
        english_script = tts_file.read_text(encoding="utf-8").strip()
        en_title = rec.get("episode_title", "") or ""
        en_desc = _english_hook(output_dir, ep) or en_title
        translations: Dict[str, dict] = rec.setdefault("translations", {})

        for lang in languages:
            if lang in translations and not args.force:
                logger.info("Ep%s [%s]: already present — skipping (use --force)", ep, lang)
                continue
            logger.info("Ep%s [%s]: translating script…", ep, lang)
            translated = translate.translate_script(english_script, lang)
            t_title, t_desc = translate.translate_metadata(en_title, en_desc, lang)

            if args.dry_run:
                logger.info("Ep%s [%s]: DRY-RUN — %d chars, title=%r",
                            ep, lang, len(translated), t_title[:60])
                continue

            if not english_url:
                logger.warning("Ep%s [%s]: record has no audio_url — cannot place track; skipping",
                               ep, lang)
                continue

            local_mp3 = output_dir / f"{tts_file.stem.replace('_tts', '')}.{lang}.mp3"
            _render_track(translated, lang, voice_id, api_key, local_mp3, max_chars)
            dur = _ffprobe_duration(str(local_mp3))

            # Length calibration vs English (first track per language only).
            if lang not in reported_langs:
                reported_langs.add(lang)
                en_dur = _ffprobe_duration(english_url)
                if en_dur and dur:
                    delta = (dur - en_dur) / en_dur * 100.0
                    logger.info("LENGTH [%s]: %.0fs vs EN %.0fs (%+.0f%%)",
                                lang, dur, en_dur, delta)
                else:
                    logger.info("LENGTH [%s]: %.0fs (EN duration unavailable for compare)",
                                lang, dur or 0.0)

            remote_key, public_url = _derive_track_key_url(
                english_url, lang, config.storage.public_base_url)
            endpoint = os.getenv(config.storage.endpoint_env, "").strip()
            access_key = os.getenv(config.storage.access_key_env, "").strip()
            secret_key = os.getenv(config.storage.secret_key_env, "").strip()
            if all([endpoint, access_key, secret_key]):
                upload_to_r2(
                    local_mp3, remote_key,
                    bucket=config.storage.bucket,
                    endpoint_url=endpoint, access_key=access_key, secret_key=secret_key,
                    public_base_url=config.storage.public_base_url,
                )
            else:
                logger.warning("Ep%s [%s]: R2 creds unset — track left local at %s",
                               ep, lang, local_mp3)

            translations[lang] = {
                "audio_url": public_url,
                "title": t_title,
                "description": t_desc,
                "duration_sec": round(dur, 1) if dur else 0,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            changed = True
            logger.info("Ep%s [%s]: done → %s", ep, lang, public_url)

    if changed and not args.dry_run:
        save_summaries(summaries_path, wrapper, records)
        logger.info("Updated summaries: %s", summaries_path)
    elif not changed:
        logger.info("Nothing to do (all requested tracks already present).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
