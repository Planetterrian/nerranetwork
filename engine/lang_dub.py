"""Generalized language-dubbed YouTube videos (July 2026 — first language: FR).

The multilingual system already generates translated *audio* tracks per
episode (``engine.multilingual`` → ``.fr.mp3`` / ``.es.mp3`` / … on R2 with
per-language RSS feeds). ``engine.ru_dub`` proved the video layer for Russian
(@NerraRU): turn the existing track into a video, reuse the episode's Grok
scene images (zero image cost), upload to a language-specific channel.

This module is the GENERALIZED engine for every language after Russian.
Design (mirrors the show-memory precedent: Tesla kept its bespoke
``engine/tesla_memory.py`` while ``engine/show_memory.py`` generalized the
pattern for the other shows):

  - ``engine.ru_dub`` stays UNTOUCHED and keeps serving @NerraRU — it is
    proven, drift-guarded, and the operator asked that nothing break. A
    future cleanup could fold RU onto this engine once it has weeks of
    parity in production.
  - Language-NEUTRAL machinery (manifest refresh, scene lookup/download,
    cover resolution, EN-optimized-title lookup, clause-aware title
    trimming) is IMPORTED from ``engine.ru_dub`` — one implementation, no
    drift.
  - Everything language-SPECIFIC lives in a ``DubLanguage`` spec. Adding a
    future language = one registry entry + ``youtube.dub_languages: [xx]``
    in the show YAML + a ``YOUTUBE_REFRESH_TOKEN_XX`` secret + the channel
    seeded in ``scripts/update_youtube_policy.py``.

Contract (identical to ru_dub): runs in the decoupled multilingual workflow,
never the episode critical path; fully best-effort (returns a status dict,
never raises); no-ops cleanly when the show hasn't opted in
(``youtube.dub_languages``), the track doesn't exist, or the channel token
(``YOUTUBE_REFRESH_TOKEN_<CH>``) is unset — which is how the FR pipeline
shipped dormant. **@NerraFR has been live since 2026-07-21**; a future
language stays a clean no-op until its own channel and secret exist.
"""

from __future__ import annotations

import logging
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from engine.youtube_policy import MAX_SHORTS_PER_EPISODE
from engine.ru_dub import (  # language-neutral helpers — single source
    PROJECT_ROOT,
    _cap_title,
    _cover_path,
    _download_images,
    _en_optimized_long_title,
    _fresh_manifest_path,
    _hashtags,
    _is_fresh_episode,
    _clause_trim,
    gallery_images_for_episode,
)

logger = logging.getLogger(__name__)

_YT_TITLE_MAX = 100
_SHORTS_SUFFIX = " #Shorts"


@dataclass(frozen=True)
class DubLanguage:
    """Everything language-specific about one dubbed-channel pipeline."""

    code: str                 # multilingual track code, e.g. "fr"
    channel: str              # policy/credentials channel key (usually == code)
    name: str                 # English name, for logs/prompts
    channel_handle: str       # e.g. "@NerraFR" (docs/logs only)
    whisper_language: str     # Whisper language for Short captions
    default_language: str     # YouTube snippet.defaultLanguage
    disclosure: str           # AI-voice disclosure line for descriptions
    end_card_main: str        # Shorts end-card CTA
    end_card_sub: str
    comment_full_episode: str  # "{url}" placeholder; funnel comment on Shorts
    second_short_tail: str    # appended when a 2nd Short needs a fallback title
    # Leading episode-label to strip when deriving the Short title
    ep_prefix_re: re.Pattern = field(
        default_factory=lambda: re.compile(
            r"^\s*(?:Ep\.?|Episode)\s*#?\s*\d+\s*[:：.\-—]\s*", re.IGNORECASE))


# The registry. Russian deliberately ABSENT — @NerraRU runs on the proven
# bespoke ``engine.ru_dub`` (see module docstring). Add future languages
# here.
DUB_LANGUAGES: Dict[str, DubLanguage] = {
    "fr": DubLanguage(
        code="fr",
        channel="fr",
        name="French",
        channel_handle="@NerraFR",
        whisper_language="fr",
        default_language="fr",
        disclosure=(
            "Divulgation IA : le podcast est préparé par Patrick ; "
            "la voix est générée par synthèse vocale IA."
        ),
        end_card_main="VOIR L'ÉPISODE",
        end_card_sub="Abonnez-vous ↗",
        comment_full_episode=(
            "▶ Épisode complet : {url}\n"
            "🔔 Abonnez-vous — nouveaux épisodes chaque jour"
        ),
        second_short_tail=" — encore un moment",
        ep_prefix_re=re.compile(
            r"^\s*(?:Ép\.?|Épisode|Ep\.?)\s*#?\s*\d+\s*[:：.\-—]\s*",
            re.IGNORECASE),
    ),
}


def dub_languages_for(config) -> List[str]:
    """The registry languages this show opts into via
    ``youtube.dub_languages`` (unknown codes are ignored with a warning —
    a typo must not crash a sweep)."""
    yt = getattr(config, "youtube", None)
    wanted = [str(c).lower() for c in
              (getattr(yt, "dub_languages", None) or [])]
    out = []
    for code in wanted:
        if code in DUB_LANGUAGES:
            out.append(code)
        elif code == "ru":
            # RU is handled by engine.ru_dub — silently skip here so a
            # future YAML consolidation can list it without double-publish.
            continue
        else:
            logger.warning("lang_dub: unknown dub language %r in %s — "
                           "skipped (registry: %s)", code,
                           getattr(config, "slug", "?"),
                           sorted(DUB_LANGUAGES))
    return out


def _playlist_id(config, lang: DubLanguage) -> str:
    yt = getattr(config, "youtube", None)
    mapping = getattr(yt, "dub_playlist_ids", None) or {}
    return str(mapping.get(lang.code, "") or "").strip()


def _long_description(config, desc: str, lang: DubLanguage) -> str:
    base_url = getattr(config.publishing, "base_url",
                       "https://nerranetwork.com")
    lines = [desc.strip(), "", f"🎧 {base_url}", "", lang.disclosure]
    tags = _hashtags(config)
    if tags:
        lines += ["", tags]
    return "\n".join(lines).strip()


def _translate_title(en_title: str, lang: DubLanguage) -> str:
    """Best-effort translation of the EN optimized YouTube title.

    ``translate_metadata`` falls back to the English input on failure. For
    non-Latin scripts (RU/ZH) an echo is detectable by script; for Latin
    targets (FR/ES) the echo check is "result differs from the input" —
    an untranslated echo means no usable translation, and we never ship an
    English title on a language channel. Returns "" on any failure so the
    caller keeps the translated-hook title.
    """
    en_title = (en_title or "").strip()
    if not en_title:
        return ""
    try:
        from engine import translate
        out, _desc = translate.translate_metadata(en_title, "", lang.code)
        out = (out or "").strip()
        if out and out.lower() != en_title.lower():
            return out
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning("lang_dub[%s]: title translation failed (%s)",
                       lang.code, exc)
    return ""


def _short_title(long_title: str, lang: DubLanguage, *,
                 body_limit: int = 70) -> str:
    """Distinct, punchy Short title derived from the language long title."""
    body = lang.ep_prefix_re.sub("", (long_title or "").strip()).strip()
    body = body.rstrip("…").rstrip()
    ceiling = min(body_limit, _YT_TITLE_MAX - len(_SHORTS_SUFFIX))
    # Clause-aware, not just word-aware: 26% of published FR Short titles
    # ended on a dangling preposition or article because a French
    # translation of an English long title routinely overruns 70 chars.
    body = _clause_trim(body, ceiling, lang.code)
    return f"{body}{_SHORTS_SUFFIX}".strip()


def _policy_plan(config, lang: DubLanguage) -> Dict[str, object]:
    """Adaptive-publishing decision for this show on the language channel.

    New channels are seeded SHORTS-ONLY in ``scripts/update_youtube_policy``
    (the RU lesson: dubbed long-form earned ~9% retention while Shorts
    carried all the views) — the Monday probe + velocity data let long-form
    earn its way in. Best-effort: any failure resolves to shorts-only-with-
    long (legacy) so a policy problem can never block a dub."""
    legacy: Dict[str, object] = {"publish_long": True, "shorts": 1,
                                 "tier": "", "applied": False, "reason": ""}
    try:
        from engine.youtube_policy import load_policy, resolve_publish_plan
        return resolve_publish_plan(
            load_policy(PROJECT_ROOT / "api" / "youtube_policy.json"),
            slug=config.slug,
            channel=lang.channel,
            yaml_publish_long=True,
            yaml_shorts=1,            # policy may raise (capped at 2 below)
            smart_mode=True,          # Shorts run the smart selector on the
                                      # language transcript (RU parity)
            adaptive_enabled=bool(getattr(
                getattr(config, "youtube", None), "adaptive_publishing", True,
            )),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("lang_dub[%s]: policy resolution failed (%s) — "
                       "legacy behavior", lang.code, exc)
        return legacy


def index_path(config, lang_code: str) -> Path:
    return (PROJECT_ROOT / config.episode.output_dir
            / f"youtube_videos.{lang_code}.json")


def _resolve_audio(config, episode_num: int, track: dict,
                   lang: DubLanguage, dest_dir: Path) -> Optional[Path]:
    """Local path to the language mp3 — fresh local render if present, else
    downloaded from the track's R2 ``audio_url``."""
    output_dir = PROJECT_ROOT / config.episode.output_dir
    local = sorted(output_dir.glob(
        f"*_Ep{episode_num:03d}_*.{lang.code}.mp3"))
    if local:
        return local[-1]
    url = track.get("audio_url", "")
    if not url:
        return None
    try:
        import requests
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        p = dest_dir / f"{lang.code}_audio_ep{episode_num:03d}.mp3"
        p.write_bytes(resp.content)
        return p
    except Exception as exc:  # noqa: BLE001
        logger.warning("lang_dub[%s]: could not fetch audio %s: %s",
                       lang.code, url, exc)
        return None


def publish_lang_dub(
    config, episode_num: int, lang_code: str, *,
    build_short: bool = True,
    dry_run: bool = False,
) -> Dict[str, object]:
    """Build + upload the language-dubbed long-form (and Shorts) for one
    episode. Returns a status dict; never raises. Mirrors
    ``engine.ru_dub.publish_ru_dub`` exactly, parameterized by language."""
    result: Dict[str, object] = {"status": "skip", "lang": lang_code}
    lang = DUB_LANGUAGES.get((lang_code or "").lower())
    if lang is None:
        result["status"] = "unknown_language"
        return result
    yt = getattr(config, "youtube", None)
    if lang.code not in dub_languages_for(config):
        return result
    ml = getattr(config, "multilingual", None)
    if not (ml and ml.enabled and lang.code in (ml.languages or [])):
        result["status"] = f"no_{lang.code}_lang"
        return result

    # The audio track must already exist (the multilingual sweep makes it).
    from engine.summaries_io import load_summaries
    summaries_path = PROJECT_ROOT / config.publishing.summaries_json
    try:
        _w, records = load_summaries(summaries_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("lang_dub[%s]: cannot read summaries: %s",
                       lang.code, exc)
        return result
    rec = next((r for r in records
                if r.get("episode_num") == episode_num), None)
    if not rec:
        result["status"] = "no_record"
        return result
    track = (rec.get("translations", {}) or {}).get(lang.code)
    if not track:
        result["status"] = f"no_{lang.code}_track"
        return result

    title = _cap_title(track.get("title")
                       or rec.get("episode_title") or "")
    # Prefer the EN *optimized* YouTube long-form title translated to the
    # target language (RU parity — the translated hook ships mid-sentence-
    # truncated; the optimized title is a complete keyword-led line).
    en_long_title = _en_optimized_long_title(config, episode_num)
    if en_long_title:
        opt = _translate_title(en_long_title, lang)
        if opt:
            title = _cap_title(opt)
    desc = track.get("description") or title

    plan = _policy_plan(config, lang)
    publish_long = bool(plan.get("publish_long", True))
    if not publish_long:
        result["policy_long_skipped"] = True
        result["policy_tier"] = str(plan.get("tier") or "")
        if not (build_short and getattr(yt, "publish_shorts", True)):
            result["status"] = "policy_skip"
            return result

    if dry_run:
        result.update(status="dryrun", title=title,
                      short_title=_short_title(title, lang),
                      policy_long=publish_long)
        return result

    from engine.youtube import get_channel_credentials_from_env
    creds = get_channel_credentials_from_env(lang.channel)
    if creds is None:
        # Dormant until the operator adds YOUTUBE_REFRESH_TOKEN_<CH>.
        result["status"] = f"no_{lang.channel}_credentials"
        return result

    cover = _cover_path(config)
    if cover is None:
        logger.warning("lang_dub[%s]: no cover art for %s — skip",
                       lang.code, config.slug)
        result["status"] = "no_cover"
        return result

    # Scene availability gate (RU parity): refresh the manifest from
    # origin/main; defer a FRESH scene-less episode rather than shipping a
    # cover-only dub.
    date_str = (rec.get("date") or "")[:10]
    with tempfile.TemporaryDirectory() as mtd:
        manifest_path = _fresh_manifest_path(Path(mtd))
        long_urls = gallery_images_for_episode(
            config.slug, episode_num, intended_use="segment_card",
            manifest_path=manifest_path)
        short_urls = gallery_images_for_episode(
            config.slug, episode_num, intended_use="social",
            manifest_path=manifest_path)
    if len(long_urls) < 2 and _is_fresh_episode(date_str):
        logger.info("lang_dub[%s]: %s Ep%s has %d scene(s) and is fresh — "
                    "deferring until the manifest catches up",
                    lang.code, config.slug, episode_num, len(long_urls))
        result["status"] = "no_scenes_yet"
        result["scene_count"] = len(long_urls)
        return result

    from engine.video import build_long_form_video, build_short_video
    from engine.youtube import (add_video_to_playlist, post_video_comment,
                                upload_video)
    from engine.youtube_index import record_video

    idx_path = index_path(config, lang.code)
    playlist = _playlist_id(config, lang)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        audio = _resolve_audio(config, episode_num, track, lang, tmp)
        if audio is None:
            result["status"] = f"no_{lang.code}_audio"
            return result

        long_scenes = (_download_images(long_urls, tmp)
                       if (long_urls and publish_long) else [])

        # Long-form thumbnail — generated even under a shorts-only policy
        # (the Short's end-card reuses it). Legacy hook rendering (no punch
        # text — punch is EN-only for now; see the July 18 growth pass).
        try:
            from engine.publisher import generate_episode_thumbnail
            thumb = tmp / f"{lang.code}_thumb.jpg"
            generate_episode_thumbnail(
                cover, episode_num, date_str, thumb,
                hook=title, show_name=config.name)
            thumb_path = thumb if thumb.exists() else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("lang_dub[%s]: thumbnail failed (%s)",
                           lang.code, exc)
            thumb_path = None

        # --- Long-form render + upload (policy-gated) ---
        long_url = ""
        if not publish_long:
            logger.warning(
                "lang_dub[%s]: yt policy — %s tier %s: long-form skipped "
                "(Short still publishes)",
                lang.code, config.slug, plan.get("tier") or "?")
            result["status"] = "policy_long_skipped"
        else:
            long_mp4 = tmp / f"{lang.code}_long_ep{episode_num:03d}.mp4"
            try:
                build_long_form_video(
                    audio, cover, long_mp4,
                    scene_paths=(long_scenes
                                 if len(long_scenes) >= 2 else None),
                    show_name=config.name)
            except Exception as exc:  # noqa: BLE001
                logger.error("lang_dub[%s]: long render failed Ep%s: %s",
                             lang.code, episode_num, exc)
                result["status"] = "render_failed"
                return result
            try:
                up = upload_video(
                    long_mp4, credentials=creds,
                    title=title,
                    description=_long_description(config, desc, lang),
                    tags=list(getattr(config, "keywords", []) or []),
                    category_id=int(getattr(yt, "category_id", 28)),
                    default_language=lang.default_language,
                    privacy_status=getattr(yt, "privacy_status", "public"),
                    thumbnail_path=thumb_path,
                )
                long_url = up.watch_url
                result["long_url"] = long_url
                record_video(
                    video_id=up.video_id, show_slug=config.slug,
                    episode=episode_num, kind="long", title=title,
                    hook=title, published=date_str, watch_url=long_url,
                    channel=lang.channel, index_path=idx_path)
                if playlist:
                    try:
                        add_video_to_playlist(credentials=creds,
                                              video_id=up.video_id,
                                              playlist_id=playlist)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("lang_dub[%s]: playlist add "
                                       "failed: %s", lang.code, exc)
            except Exception as exc:  # noqa: BLE001
                logger.error("lang_dub[%s]: long upload failed Ep%s: %s",
                             lang.code, episode_num, exc)
                result["status"] = "upload_failed"
                return result
            result["status"] = "done"

        # --- Shorts (best-effort; RU parity incl. the July 18 multi-Short
        # + fill-to-requested behavior) ---
        if build_short and getattr(yt, "publish_shorts", True):
            # Bound from the shared plan contract, not a local literal —
            # see MAX_SHORTS_PER_EPISODE in engine.youtube_policy.
            n_shorts = max(1, min(MAX_SHORTS_PER_EPISODE,
                                  int(plan.get("shorts", 1) or 1)))
            short_scenes: List[Path] = []
            try:
                short_scenes = (_download_images(short_urls, tmp)
                                if short_urls else [])
            except Exception as exc:  # noqa: BLE001
                logger.warning("lang_dub[%s]: scene download failed (%s)",
                               lang.code, exc)
            short_dur = float(getattr(yt, "short_duration_seconds", 35.0))
            base_offset = float(getattr(yt, "shorts_start_offset", 0.0) or 0.0)

            tr_json = None
            windows: list = []
            try:
                from engine.audio import get_audio_duration
                from engine.shorts_selector import (
                    pick_top_n_engaging_windows,
                )
                from engine.transcripts import generate_transcript
                tr = generate_transcript(
                    audio, tmp, f"{lang.code}_ep{episode_num:03d}",
                    language=lang.whisper_language)
                if tr and tr.json_path.exists():
                    tr_json = tr.json_path
                    total_dur = get_audio_duration(audio) or 0.0
                    windows = pick_top_n_engaging_windows(
                        tr_json, n=n_shorts,
                        audio_offset=base_offset,
                        audio_duration=total_dur,
                        window_duration=short_dur,
                        min_start_final=base_offset,
                        fill_to_n=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("lang_dub[%s]: transcript/selection failed "
                               "(%s) — voice-start short without captions",
                               lang.code, exc)

            if windows:
                short_plan = [(w.start_seconds,
                               (w.opening_text or "").strip())
                              for w in windows[:n_shorts]]
            else:
                short_plan = [(base_offset, "")]

            end_card_png = None
            try:
                from engine.publisher import generate_shorts_end_card
                if thumb_path is not None:
                    ec = tmp / f"{lang.code}_endcard_ep{episode_num:03d}.png"
                    generate_shorts_end_card(
                        thumb_path, ec, show_name=config.name,
                        main_text=lang.end_card_main,
                        sub_text=lang.end_card_sub)
                    if ec.exists():
                        end_card_png = ec
            except Exception as exc:  # noqa: BLE001
                logger.warning("lang_dub[%s]: end-card failed (%s)",
                               lang.code, exc)

            short_urls_out: List[str] = []
            for short_idx, (start_offset, opening_text) in enumerate(
                    short_plan):
                try:
                    suffix = "" if short_idx == 0 else f"_{short_idx + 1}"
                    short_mp4 = (tmp / f"{lang.code}_short_ep"
                                       f"{episode_num:03d}{suffix}.mp4")

                    ass_path = None
                    if tr_json is not None:
                        try:
                            from engine.captions import (
                                transcript_to_ass_window,
                            )
                            cand = (tmp / f"{lang.code}_short_ep"
                                          f"{episode_num:03d}{suffix}.ass")
                            transcript_to_ass_window(
                                tr_json, cand,
                                window_start_seconds=start_offset,
                                window_duration_seconds=short_dur,
                                audio_offset_seconds=0.0)
                            if (cand.exists() and cand.stat().st_size > 0
                                    and "Dialogue:" in cand.read_text(
                                        encoding="utf-8",
                                        errors="replace")):
                                ass_path = cand
                                result["short_captions"] = "ass"
                        except Exception as exc:  # noqa: BLE001
                            logger.warning(
                                "lang_dub[%s]: captions failed for short "
                                "%d (%s)", lang.code, short_idx + 1, exc)

                    build_short_video(
                        audio, cover, short_mp4,
                        start_offset=start_offset,
                        duration=short_dur,
                        hook=title,
                        scene_paths=(short_scenes
                                     if len(short_scenes) >= 2 else None),
                        show_name=config.name,
                        subtitles_path=ass_path,
                        end_card=True,
                        end_card_main_text=lang.end_card_main,
                        end_card_sub_text=lang.end_card_sub,
                        end_card_image_path=end_card_png)

                    if short_idx == 0 or not opening_text:
                        st = _short_title(title, lang)
                        if short_idx > 0:
                            st = (_short_title(title, lang, body_limit=52)
                                  + lang.second_short_tail)
                    else:
                        # Clause-aware: this branch titles the 2nd/3rd Short
                        # from its window's opening speech, which is a
                        # mid-sentence slice to begin with — a plain word
                        # trim lands on a dangling article even more often
                        # than the long-title path does.
                        body = _clause_trim(
                            opening_text.rstrip("…").rstrip(),
                            min(70, _YT_TITLE_MAX - len(_SHORTS_SUFFIX)),
                            lang.code)
                        st = f"{body}{_SHORTS_SUFFIX}".strip()

                    sup = upload_video(
                        short_mp4, credentials=creds,
                        title=st,
                        description=_long_description(config, desc, lang),
                        tags=list(getattr(config, "keywords", []) or []),
                        category_id=int(getattr(yt, "category_id", 28)),
                        default_language=lang.default_language,
                        privacy_status=getattr(yt, "privacy_status",
                                               "public"))
                    short_urls_out.append(sup.watch_url)
                    record_video(
                        video_id=sup.video_id, show_slug=config.slug,
                        episode=episode_num, kind="short", title=st,
                        hook=title, published=date_str,
                        watch_url=sup.watch_url,
                        channel=lang.channel, index_path=idx_path)
                    if playlist:
                        try:
                            add_video_to_playlist(credentials=creds,
                                                  video_id=sup.video_id,
                                                  playlist_id=playlist)
                        except Exception:  # noqa: BLE001
                            pass
                    # Funnel comment — only when a language long exists
                    # this run (never link a different-language video).
                    if long_url and bool(getattr(yt, "auto_comment", True)):
                        try:
                            post_video_comment(
                                credentials=creds,
                                video_id=sup.video_id,
                                text=lang.comment_full_episode.format(
                                    url=long_url))
                        except Exception:  # noqa: BLE001
                            pass
                    result["status"] = "done"
                except Exception as exc:  # noqa: BLE001
                    logger.warning("lang_dub[%s]: Short %d failed Ep%s "
                                   "(non-fatal): %s", lang.code,
                                   short_idx + 1, episode_num, exc)
                    result["short_error"] = str(exc)

            if short_urls_out:
                result["short_url"] = short_urls_out[0]
                result["short_urls"] = short_urls_out

    return result
