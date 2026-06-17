"""Reusable per-episode multilingual audio generation.

Shared core used by BOTH the manual driver (``scripts/generate_translations.py``)
and the daily pipeline's auto step (``run_show.py``). Given a finalized English
episode, it translates the script + metadata, renders each language to MP3 with
the cloned Grok voice, uploads to R2 alongside the English file, and records the
track on the episode (concurrency-safe upsert).

English stays the canonical master; translations are derived artifacts surfaced
on the website. See ``docs/multilingual.md``.
"""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from engine import translate, tts
from engine.storage import upload_to_r2
from engine.summaries_io import load_summaries, upsert_translation

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def grok_api_key() -> str:
    key = (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Missing GROK_API_KEY (or XAI_API_KEY)")
    return key


def resolve_multilingual_voice(config) -> str:
    """Voice ID for the translated tracks.

    Grok carries a single voice identity across languages, so by default the
    multilingual tracks reuse the show's EXISTING Grok voice (``tts.voice_id``,
    e.g. the operator's custom ``kdif6sqjcyiq``) — the host sounds like the
    operator in every language with no extra setup. The ``cloned_voice_env``
    env var (default ``GROK_CLONED_VOICE_ID``) is an optional override for
    pointing the translations at a different cloned voice; when it's unset the
    existing show voice is used. Returns "" only if neither is configured.
    """
    ml = getattr(config, "multilingual", None)
    env_name = (ml and ml.cloned_voice_env) or "GROK_CLONED_VOICE_ID"
    override = (os.getenv(env_name) or "").strip()
    return override or (getattr(config.tts, "voice_id", "") or "").strip()


def ffprobe_duration(target: str) -> Optional[float]:
    """Media duration in seconds (works on a local path OR a URL); None on error."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", target],
            capture_output=True, text=True, timeout=120,
        )
        val = out.stdout.strip()
        return float(val) if val else None
    except Exception:  # noqa: BLE001 — best-effort, reporting only
        return None


def find_tts_file(output_dir: Path, episode_num: int) -> Optional[Path]:
    matches = sorted(output_dir.glob(f"*_Ep{episode_num:03d}_*_tts.txt"))
    return matches[-1] if matches else None


def english_hook(output_dir: Path, episode_num: int) -> str:
    """Best-effort episode hook from the digest .md (for track descriptions)."""
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


def derive_track_key_url(english_audio_url: str, lang: str, public_base_url: str):
    """``(remote_key, public_url)`` for the *lang* track, derived from the
    English track's own URL so it lands in the same R2 prefix."""
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


def render_track(script_text: str, lang: str, voice_id: str, api_key: str,
                 out_path: Path, max_chars: int) -> None:
    tts.synthesize(
        script_text, voice_id, out_path,
        api_key=api_key, provider="grok",
        max_chars=max_chars, language_code=lang,
    )


def generate_for_episode(
    config,
    episode_num: int,
    languages: List[str],
    *,
    voice_id: str,
    api_key: str,
    force: bool = False,
    dry_run: bool = False,
) -> Dict[str, str]:
    """Generate the requested language tracks for one episode.

    Re-reads the summaries record fresh, finds the finalized ``_tts.txt``, and
    for each language translates → validates → TTS → uploads → upserts the
    track. Returns a ``{lang: status}`` map where status is one of
    ``done`` / ``skip`` / ``rejected`` / ``dryrun`` / ``no_audio_url``. A
    per-language failure never aborts the others.
    """
    output_dir = PROJECT_ROOT / config.episode.output_dir
    summaries_path = PROJECT_ROOT / config.publishing.summaries_json
    max_chars = config.tts.max_chars or tts.GROK_MAX_CHARS_PER_REQUEST

    _wrapper, records = load_summaries(summaries_path)
    rec = next((r for r in records if r.get("episode_num") == episode_num), None)
    if rec is None:
        logger.warning("multilingual: no summaries record for Ep%s", episode_num)
        return {}
    english_url = rec.get("audio_url", "")
    tts_file = find_tts_file(output_dir, episode_num)
    if not tts_file:
        logger.warning("multilingual: no _tts.txt for Ep%s in %s", episode_num, output_dir)
        return {}

    english_script = tts_file.read_text(encoding="utf-8").strip()
    en_title = rec.get("episode_title", "") or ""
    en_desc = english_hook(output_dir, episode_num) or en_title
    existing = rec.get("translations", {}) or {}

    results: Dict[str, str] = {}
    for lang in languages:
        if lang in existing and not force:
            results[lang] = "skip"
            continue
        try:
            translated = translate.translate_script(english_script, lang)
            t_title, t_desc = translate.translate_metadata(en_title, en_desc, lang)
        except translate.TranslationError as exc:
            logger.error("Ep%s [%s]: translation rejected — %s", episode_num, lang, exc)
            results[lang] = "rejected"
            continue

        if dry_run:
            results[lang] = "dryrun"
            continue
        if not english_url:
            logger.warning("Ep%s [%s]: no English audio_url — cannot place track", episode_num, lang)
            results[lang] = "no_audio_url"
            continue

        local_mp3 = output_dir / f"{tts_file.stem.replace('_tts', '')}.{lang}.mp3"
        render_track(translated, lang, voice_id, api_key, local_mp3, max_chars)
        dur = ffprobe_duration(str(local_mp3))
        try:
            size_bytes = local_mp3.stat().st_size
        except OSError:
            size_bytes = 0

        en_dur = ffprobe_duration(english_url)
        if en_dur and dur:
            logger.info("Ep%s LENGTH [%s]: %.0fs vs EN %.0fs (%+.0f%%)",
                        episode_num, lang, dur, en_dur, (dur - en_dur) / en_dur * 100.0)

        remote_key, public_url = derive_track_key_url(
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
                           episode_num, lang, local_mp3)

        upsert_translation(summaries_path, episode_num, lang, {
            "audio_url": public_url,
            "title": t_title,
            "description": t_desc,
            "duration_sec": round(dur, 1) if dur else 0,
            # Exact enclosure byte length for the per-language podcast feed
            # (engine.language_feeds). Falls back to a duration estimate for
            # records that predate this field.
            "bytes": size_bytes,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })
        results[lang] = "done"
        logger.info("Ep%s [%s]: done → %s", episode_num, lang, public_url)

    return results


def auto_generate_after_publish(config, episode_num: int) -> Dict[str, str]:
    """Daily-pipeline entry point: generate all configured languages for the
    just-published episode when the show opts into ``multilingual.auto``.

    Fully non-blocking and self-guarding — returns an empty map (never raises)
    when multilingual is disabled, ``auto`` is off, the cloned voice ID isn't
    set, or anything fails. The caller must treat translation as best-effort so
    it can never break the English publish.
    """
    ml = getattr(config, "multilingual", None)
    if not (ml and ml.enabled and getattr(ml, "auto", False)):
        return {}
    languages = list(ml.languages) or list(translate.supported_languages())
    voice_id = resolve_multilingual_voice(config)
    if not voice_id:
        logger.warning("multilingual auto: skipping Ep%s — no voice_id (set the "
                       "show's tts.voice_id or %s)", episode_num, ml.cloned_voice_env)
        return {}
    try:
        api_key = grok_api_key()
    except RuntimeError as exc:
        logger.warning("multilingual auto: skipping Ep%s — %s", episode_num, exc)
        return {}
    try:
        results = generate_for_episode(
            config, episode_num, languages, voice_id=voice_id, api_key=api_key,
        )
        done = sorted(k for k, v in results.items() if v == "done")
        logger.info("multilingual auto: Ep%s generated %s", episode_num, done or "nothing new")
        return results
    except Exception as exc:  # noqa: BLE001 — translation must never block publish
        logger.error("multilingual auto: Ep%s failed (non-fatal) — %s", episode_num, exc)
        return {}
