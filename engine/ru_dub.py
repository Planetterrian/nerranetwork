"""Russian-dubbed YouTube videos for the English shows (@NerraRU).

The English shows already auto-generate a Russian *audio* track per episode
(``engine.multilingual`` → ``languages: [ru, …]``) which today only becomes an
R2 file + a per-language podcast RSS feed. This module turns that existing
Russian track into a **video** and uploads it to the @NerraRU YouTube channel,
reusing the episode's already-generated Grok scene images (pulled from the
gallery manifest's public R2 URLs — zero extra image-generation cost).

Design contract (mirrors every optional integration here):
  - Runs in the **decoupled multilingual workflow**, never the episode's
    critical path — so it cannot re-introduce the timeout/partial-publish
    landmine that decoupling exists to prevent.
  - Fully best-effort + self-guarding: returns a status dict, never raises.
    No-ops cleanly when the show hasn't opted in (``youtube.ru_dub_enabled``),
    the RU track doesn't exist yet, the @NerraRU credentials
    (``YOUTUBE_REFRESH_TOKEN_RU``) aren't set, or anything fails.
  - English upload + the RU podcast feed are completely unaffected.

See ``docs/ru_youtube_dubs.md``.
"""

from __future__ import annotations

import datetime
import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST = PROJECT_ROOT / "site" / "data" / "gallery-manifest.json"

# YouTube's hard title cap (chars) — the RU title + " #Shorts" must clear it.
_YT_TITLE_MAX = 100
_SHORTS_SUFFIX = " #Shorts"

# Leading "Эп. N:" / "Выпуск N:" episode-number label dropped when deriving the
# punchy Short title from the long title (the Short doesn't need the episode
# number in its ≤70-char headline).
_EP_PREFIX_RE = re.compile(
    r"^\s*(?:Эп\.?|Выпуск)\s*№?\s*\d+\s*[:：.\-—]\s*", re.IGNORECASE)

# Russian AI-voice disclosure appended to every RU description (same text the
# native RU shows speak; kept in sync with run_show._AI_DISCLOSURE_RU).
_AI_DISCLOSURE_RU = (
    "Дисклеймер об ИИ: подкаст курирует Патрик, "
    "а озвучка создаётся с помощью ИИ-синтеза голоса."
)

# Russian end-card call-to-action for the Shorts (parity with the EN
# "WATCH FULL EPISODE" / "Tap Subscribe ↗" card).
_RU_END_CARD_MAIN = "СМОТРЕТЬ ВЫПУСК"
_RU_END_CARD_SUB = "Подпишись ↗"


def _episode_id(episode_num: int) -> str:
    return f"ep{episode_num:03d}"


def _is_fresh_episode(date_str: str, *, today: Optional[datetime.date] = None) -> bool:
    """True when the episode aired today or yesterday (UTC).

    Used to decide whether a scene-less episode should be DEFERRED (fresh —
    the gallery-manifest rebuild simply hasn't caught up yet) or published
    with the cover anyway (old — no scenes are ever coming, and deferring
    forever would silently drop the episode). Unparsable/empty dates count
    as old so a malformed record still publishes rather than stalls.
    """
    try:
        ep_date = datetime.date.fromisoformat((date_str or "")[:10])
    except ValueError:
        return False
    now = today or datetime.datetime.now(datetime.timezone.utc).date()
    return datetime.timedelta(0) <= (now - ep_date) <= datetime.timedelta(days=1)


def _fresh_manifest_path(dest_dir: Path, *,
                         manifest_path: Path = _MANIFEST) -> Path:
    """Best-effort refresh of the gallery manifest from ``origin/main``.

    The RU-dub sweep runs from a checkout whose manifest can LAG the newest
    episode (the manifest is rebuilt by a separate workflow that commits to
    main after the episode publishes) — so a fresh episode's scenes exist on
    R2 + origin/main but not in this working tree. ``git fetch`` + ``git
    show origin/main:<manifest>`` pulls the newest committed copy into
    *dest_dir* without touching the working tree. Any failure (offline,
    shallow clone without the ref, corrupt blob) falls back to the
    checked-out file — never raises.
    """
    try:
        rel = manifest_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return manifest_path  # non-repo path (tests) — nothing to refresh
    try:
        subprocess.run(["git", "fetch", "origin", "main"],
                       cwd=PROJECT_ROOT, capture_output=True,
                       timeout=60, check=False)
        show = subprocess.run(["git", "show", f"origin/main:{rel}"],
                              cwd=PROJECT_ROOT, capture_output=True,
                              timeout=30, check=False)
        if show.returncode == 0 and show.stdout:
            import json
            json.loads(show.stdout)  # validate before trusting the blob
            fresh = Path(dest_dir) / "gallery-manifest.origin.json"
            fresh.write_bytes(show.stdout)
            logger.info("ru_dub: using origin/main gallery manifest")
            return fresh
        logger.info("ru_dub: origin/main manifest unavailable (rc=%s) — "
                    "using checked-out copy", show.returncode)
    except Exception as exc:  # noqa: BLE001 — refresh is best-effort
        logger.info("ru_dub: manifest refresh failed (%s) — "
                    "using checked-out copy", exc)
    return manifest_path


def gallery_images_for_episode(
    show_slug: str, episode_num: int, *,
    intended_use: str = "segment_card",
    manifest_path: Path = _MANIFEST,
) -> List[str]:
    """Public R2 URLs of this episode's scene images, in document order.

    Filters the committed gallery manifest by ``show_slug`` + ``episode_id``
    + ``intended_use`` (``segment_card`` = the 16:9 long-form scenes;
    ``social`` = the 9:16 Shorts scenes). Empty list when the manifest has no
    entry yet (the manifest rebuild can lag the newest episode —
    ``publish_ru_dub`` defers a FRESH scene-less episode as ``no_scenes_yet``
    so a later sweep retries with the real scenes; genuinely old episodes
    fall back to the cover image).
    """
    import json
    try:
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.info("ru_dub: gallery manifest unreadable (%s) — no scenes", exc)
        return []
    eid = _episode_id(episode_num)
    urls: List[str] = []
    for img in data.get("images", []):
        if (img.get("show_slug") == show_slug
                and (img.get("episode_id") or "").lower() == eid
                and img.get("intended_use") == intended_use
                and img.get("original_url")):
            urls.append(img["original_url"])
    return urls


def _download_images(urls: List[str], dest_dir: Path) -> List[Path]:
    """Best-effort download of *urls* → dest_dir. Skips any that fail.

    Routed through ``engine.gallery_library._download_entry`` so the
    public-CDN → authenticated-R2 fallback (the gallery.nerranetwork.com
    403-from-CI failure mode, Tesla Ep537) protects the RU dub scenes too.
    """
    from engine import gallery_library
    paths: List[Path] = []
    for url in urls:
        try:
            p = gallery_library._download_entry({"original_url": url}, dest_dir)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ru_dub: failed to fetch scene %s: %s", url, exc)
            p = None
        if p is not None:
            paths.append(p)
    return paths


def _resolve_ru_audio(config, episode_num: int, rec: dict,
                      ru_track: dict, dest_dir: Path) -> Optional[Path]:
    """Local path to the RU mp3 — the freshly-rendered local file if present,
    else downloaded from the track's R2 ``audio_url``."""
    output_dir = PROJECT_ROOT / config.episode.output_dir
    local = sorted(output_dir.glob(f"*_Ep{episode_num:03d}_*.ru.mp3"))
    if local:
        return local[-1]
    url = ru_track.get("audio_url", "")
    if not url:
        return None
    try:
        import requests
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        p = dest_dir / f"ru_audio_ep{episode_num:03d}.mp3"
        p.write_bytes(resp.content)
        return p
    except Exception as exc:  # noqa: BLE001
        logger.warning("ru_dub: could not fetch RU audio %s: %s", url, exc)
        return None


def _cover_path(config) -> Optional[Path]:
    cands = [
        PROJECT_ROOT / "assets" / "covers" / f"{config.slug.replace('_', '-')}.jpg",
        PROJECT_ROOT / "assets" / "covers" / f"{config.slug}.jpg",
    ]
    rss_image = getattr(config.publishing, "rss_image", "") or ""
    base = rss_image.rstrip("/").rsplit("/", 1)[-1]
    if base:
        cands.append(PROJECT_ROOT / "assets" / "covers" / base)
    return next((c for c in cands if c.exists()), None)


def _hashtags(config) -> str:
    tags = [t for t in (getattr(config, "keywords", []) or [])][:3]
    parts = []
    for t in tags:
        cleaned = "".join(ch for ch in t.title() if ch.isalnum())
        if cleaned:
            parts.append("#" + cleaned)
    return " ".join(parts)


def _ru_long_description(config, ru_desc: str) -> str:
    base_url = getattr(config.publishing, "base_url", "https://nerranetwork.com")
    lines = [ru_desc.strip(), "", f"🎧 {base_url}", "", _AI_DISCLOSURE_RU]
    tags = _hashtags(config)
    if tags:
        lines += ["", tags]
    return "\n".join(lines).strip()


def _cap_title(title: str, limit: int = 95) -> str:
    title = (title or "").strip()
    return title if len(title) <= limit else title[: limit - 1].rstrip() + "…"


def _has_cyrillic(text: str) -> bool:
    return any("Ѐ" <= c <= "ӿ" for c in (text or ""))


def _en_optimized_long_title(config, episode_num: int) -> str:
    """The EN long-form YouTube title recorded for this episode.

    Read from the show's own EN ``youtube_videos.json`` index — the ``title``
    on the ``long`` record is the LLM-*optimized* YouTube title (or the SEO
    title where a show has ``optimized_titles`` off), a COMPLETE, non-truncated
    line unlike the mid-sentence spoken hook. Returns "" when the index is
    absent/unreadable or has no long record for the episode (best-effort: the
    caller keeps its legacy hook-based title)."""
    import json
    idx = PROJECT_ROOT / config.episode.output_dir / "youtube_videos.json"
    try:
        data = json.loads(idx.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — best-effort lookup
        return ""
    best = ""
    for v in data.get("videos", []):
        if (v.get("episode") == episode_num and v.get("kind") == "long"
                and v.get("title")):
            best = str(v["title"]).strip()  # newest matching row wins
    return best


def _translate_title_to_ru(en_title: str) -> str:
    """Best-effort Russian translation of a short YouTube title.

    Cheap: a title-only Grok call via the shared ``engine.translate`` helper —
    NOT a re-translation of the whole script. ``translate_metadata`` falls back
    to the English input on failure, so a result with no Cyrillic is treated as
    "no translation" (we never want an English title on @NerraRU). Returns ""
    on any failure so the caller keeps the legacy hook-based title."""
    en_title = (en_title or "").strip()
    if not en_title:
        return ""
    try:
        from engine import translate
        ru_title, _desc = translate.translate_metadata(en_title, "", "ru")
        ru_title = (ru_title or "").strip()
        if ru_title and _has_cyrillic(ru_title):
            return ru_title
    except Exception as exc:  # noqa: BLE001 — title translation is best-effort
        logger.warning("ru_dub: title translation failed (%s) — using hook", exc)
    return ""


def _word_trim(text: str, limit: int) -> str:
    """Trim *text* to <= *limit* chars on a WORD boundary (never mid-word).

    No trailing ellipsis — the Short appends " #Shorts", and "…" + "#Shorts"
    reads awkwardly. Trailing punctuation left by the cut is stripped."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text.rstrip(" ,.:;—-…")
    cut = text[:limit]
    if " " in cut:
        cut = cut[:cut.rfind(" ")]  # break before the partial last word
    return cut.rstrip(" ,.:;—-…")


def _policy_plan(config) -> Dict[str, object]:
    """Adaptive-publishing decision for this show on the RU channel.

    Reads the committed ``api/youtube_policy.json`` (rebuilt nightly from
    real per-video velocity by ``scripts/update_youtube_policy.py``) via
    ``engine.youtube_policy``. RU long-form dubs earn almost nothing while
    RU Shorts carry all the views (July 2026 analytics), so the policy can
    gate the expensive long-form render+upload off while the Short still
    ships. Best-effort: any failure resolves to the legacy always-long
    behavior. Tests monkeypatch this hook for determinism.
    """
    legacy: Dict[str, object] = {"publish_long": True, "shorts": 1,
                                 "tier": "", "applied": False, "reason": ""}
    try:
        from engine.youtube_policy import load_policy, resolve_publish_plan
        return resolve_publish_plan(
            load_policy(PROJECT_ROOT / "api" / "youtube_policy.json"),
            slug=config.slug,
            channel="ru",
            yaml_publish_long=True,   # legacy ru_dub always built the long
            yaml_shorts=1,            # ru_dub builds at most one Short
            smart_mode=False,
            adaptive_enabled=bool(getattr(
                getattr(config, "youtube", None), "adaptive_publishing", True,
            )),
        )
    except Exception as exc:  # noqa: BLE001 — policy must never block a dub
        logger.warning("ru_dub: policy resolution failed (%s) — legacy "
                       "behavior", exc)
        return legacy


def _ru_short_title(long_title: str, *, body_limit: int = 70) -> str:
    """A distinct, punchy Short title derived from the RU long title.

    Drops the "Эп. N:" episode prefix, word-boundary-trims the body to a short
    headline (never mid-word, no trailing "…"), and appends " #Shorts" — always
    within YouTube's 100-char cap. Distinct from the long title (at minimum by
    the suffix; usually also by the dropped prefix + trim)."""
    body = _EP_PREFIX_RE.sub("", (long_title or "").strip()).strip()
    body = body.rstrip("…").rstrip()
    ceiling = min(body_limit, _YT_TITLE_MAX - len(_SHORTS_SUFFIX))
    body = _word_trim(body, ceiling)
    return f"{body}{_SHORTS_SUFFIX}".strip()


def publish_ru_dub(
    config, episode_num: int, *,
    build_short: bool = True,
    dry_run: bool = False,
) -> Dict[str, object]:
    """Build + upload the Russian-dubbed long-form (and optional Short) for
    one episode of an English show. Returns a status dict; never raises."""
    result: Dict[str, object] = {"status": "skip"}
    yt = getattr(config, "youtube", None)
    if not (yt and getattr(yt, "ru_dub_enabled", False)):
        return result
    ml = getattr(config, "multilingual", None)
    if not (ml and ml.enabled and "ru" in (ml.languages or [])):
        result["status"] = "no_ru_lang"
        return result

    # The RU audio track must already exist (the multilingual sweep makes it).
    from engine.summaries_io import load_summaries
    summaries_path = PROJECT_ROOT / config.publishing.summaries_json
    try:
        _w, records = load_summaries(summaries_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ru_dub: cannot read summaries: %s", exc)
        return result
    rec = next((r for r in records if r.get("episode_num") == episode_num), None)
    if not rec:
        result["status"] = "no_record"
        return result
    ru_track = (rec.get("translations", {}) or {}).get("ru")
    if not ru_track:
        result["status"] = "no_ru_track"  # translation hasn't run yet
        return result

    ru_title = _cap_title(ru_track.get("title") or rec.get("episode_title") or "")
    # Prefer the EN *optimized* YouTube long-form title (translated to Russian)
    # over the raw hook the translation step produced — the hook is written for
    # the ear and ships mid-sentence-truncated (…), while the optimized title is
    # a complete, keyword-front-loaded line (EN long-form parity). Best-effort:
    # any lookup/translation failure keeps the legacy ru_title.
    en_long_title = _en_optimized_long_title(config, episode_num)
    if en_long_title:
        ru_opt = _translate_title_to_ru(en_long_title)
        if ru_opt:
            ru_title = _cap_title(ru_opt)
    ru_desc = ru_track.get("description") or ru_title

    # Adaptive publishing policy: channels.ru[slug] can gate the long-form
    # dub off (shorts-only tier). The Short is still produced — audio +
    # scenes + thumbnail are shared work; only the long-form ffmpeg render
    # and its upload are skipped.
    plan = _policy_plan(config)
    publish_long = bool(plan.get("publish_long", True))
    if not publish_long:
        result["policy_long_skipped"] = True
        result["policy_tier"] = str(plan.get("tier") or "")
        if not (build_short and getattr(yt, "publish_shorts", True)):
            logger.info("ru_dub: yt policy gates long-form off and the Short "
                        "is disabled — nothing to publish for %s Ep%s",
                        config.slug, episode_num)
            result["status"] = "policy_skip"
            return result

    # Dry-run is creds-independent so the operator can preview the resolved
    # RU title before doing the @NerraRU OAuth.
    if dry_run:
        result.update(status="dryrun", title=ru_title,
                      short_title=_ru_short_title(ru_title),
                      policy_long=publish_long)
        return result

    from engine.youtube import get_channel_credentials_from_env
    creds = get_channel_credentials_from_env("ru")
    if creds is None:
        result["status"] = "no_ru_credentials"  # YOUTUBE_REFRESH_TOKEN_RU unset
        return result

    cover = _cover_path(config)
    if cover is None:
        logger.warning("ru_dub: no cover art for %s — skip", config.slug)
        result["status"] = "no_cover"
        return result

    # Scene availability gate. The checked-out manifest lags the newest
    # episode (rebuilt by a separate workflow), so refresh from origin/main
    # first; if a FRESH episode still has <2 long-form scenes, defer instead
    # of shipping a cover-only dub — the recording sweep (publish_ru_dubs)
    # marks it not-done so the next sweep retries once the manifest catches
    # up. Old scene-less episodes still publish with the cover (no scenes
    # are ever coming for them).
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
        logger.info("ru_dub: %s Ep%s has %d gallery scene(s) and is fresh — "
                    "deferring until the manifest rebuild catches up",
                    config.slug, episode_num, len(long_urls))
        result["status"] = "no_scenes_yet"
        result["scene_count"] = len(long_urls)
        return result

    from engine.video import build_long_form_video, build_short_video
    from engine.youtube import upload_video, add_video_to_playlist
    from engine.youtube_index import record_video

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        audio = _resolve_ru_audio(config, episode_num, rec, ru_track, tmp)
        if audio is None:
            result["status"] = "no_ru_audio"
            return result

        # Reuse the episode's already-generated 16:9 scene images (zero
        # cost; URLs resolved above from the refreshed manifest). Skipped
        # under a shorts-only policy — the long render they feed won't run.
        long_scenes = (_download_images(long_urls, tmp)
                       if (long_urls and publish_long) else [])

        # --- Long-form thumbnail ---
        # Generated even under a shorts-only policy: the Short's end-card
        # CTA reuses it as its base image.
        try:
            from engine.publisher import generate_episode_thumbnail
            thumb = tmp / "ru_thumb.jpg"
            generate_episode_thumbnail(
                cover, episode_num, date_str, thumb,
                hook=ru_title, show_name=config.name)
            thumb_path = thumb if thumb.exists() else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("ru_dub: thumbnail failed (%s) — uploading without", exc)
            thumb_path = None

        # --- Long-form render + upload (policy-gated) ---
        long_url = ""
        if not publish_long:
            logger.warning(
                "ru_dub: yt policy — %s RU tier %s: long-form render+upload "
                "skipped (Short still publishes)",
                config.slug, plan.get("tier") or "?")
            # Not "done" yet: the Short below is now the deliverable, so
            # only its successful upload flips the status (a failed Short
            # keeps the episode not-done and the next sweep retries it —
            # safe, since no duplicate long can result).
            result["status"] = "policy_long_skipped"
        else:
            long_mp4 = tmp / f"ru_long_ep{episode_num:03d}.mp4"
            try:
                build_long_form_video(
                    audio, cover, long_mp4,
                    scene_paths=long_scenes if len(long_scenes) >= 2 else None,
                    show_name=config.name)
            except Exception as exc:  # noqa: BLE001
                logger.error("ru_dub: long-form render failed for Ep%s: %s",
                             episode_num, exc)
                result["status"] = "render_failed"
                return result

            try:
                up = upload_video(
                    long_mp4, credentials=creds,
                    title=ru_title,
                    description=_ru_long_description(config, ru_desc),
                    tags=list(getattr(config, "keywords", []) or []),
                    category_id=int(getattr(yt, "category_id", 28)),
                    default_language="ru",
                    privacy_status=getattr(yt, "privacy_status", "public"),
                    thumbnail_path=thumb_path,
                )
                long_url = up.watch_url
                result["long_url"] = long_url
                record_video(
                    video_id=up.video_id, show_slug=config.slug, episode=episode_num,
                    kind="long", title=ru_title, hook=ru_title, published=date_str,
                    watch_url=long_url, channel="ru",
                    index_path=PROJECT_ROOT / config.episode.output_dir
                    / "youtube_videos.ru.json")
                pl = (getattr(yt, "ru_podcast_playlist_id", None) or "").strip()
                if pl:
                    try:
                        add_video_to_playlist(credentials=creds,
                                              video_id=up.video_id, playlist_id=pl)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("ru_dub: playlist add failed: %s", exc)
                else:
                    logger.info("ru_dub: no ru_podcast_playlist_id — skipped playlist")
            except Exception as exc:  # noqa: BLE001
                logger.error("ru_dub: long-form upload failed for Ep%s: %s",
                             episode_num, exc)
                result["status"] = "upload_failed"
                return result

            result["status"] = "done"

        # --- Short (best-effort; failure never blocks the long-form result) ---
        if build_short and getattr(yt, "publish_shorts", True):
            try:
                short_scenes = _download_images(short_urls, tmp) if short_urls else []
                short_mp4 = tmp / f"ru_short_ep{episode_num:03d}.mp4"
                short_dur = float(getattr(yt, "short_duration_seconds", 55.0))

                # Parity with the EN shorts: transcribe the RU dub audio
                # (Russian Whisper, word timestamps) → smart engaging-beat
                # start + Russian burned-in per-word captions. DejaVu Sans
                # (the caption font) covers Cyrillic. Every piece is
                # best-effort — the short still ships without them.
                start_offset = float(getattr(yt, "shorts_start_offset", 0.0) or 0.0)
                ass_path = None
                try:
                    from engine.transcripts import generate_transcript
                    from engine.captions import transcript_to_ass_window
                    from engine.shorts_selector import pick_engaging_window
                    from engine.audio import get_audio_duration
                    tr = generate_transcript(
                        audio, tmp, f"ru_ep{episode_num:03d}", language="ru")
                    if tr and tr.json_path.exists():
                        total_dur = get_audio_duration(audio) or 0.0
                        win = pick_engaging_window(
                            tr.json_path, audio_offset=start_offset,
                            audio_duration=total_dur, window_duration=short_dur,
                            min_start_final=start_offset)
                        if win is not None:
                            start_offset = win.start_seconds
                        ass_candidate = tmp / f"ru_short_ep{episode_num:03d}.ass"
                        transcript_to_ass_window(
                            tr.json_path, ass_candidate,
                            window_start_seconds=start_offset,
                            window_duration_seconds=short_dur,
                            audio_offset_seconds=0.0)
                        if (ass_candidate.exists()
                                and ass_candidate.stat().st_size > 0
                                and "Dialogue:" in ass_candidate.read_text(
                                    encoding="utf-8", errors="replace")):
                            ass_path = ass_candidate
                            result["ru_short_captions"] = "ass"
                except Exception as exc:  # noqa: BLE001
                    logger.warning("ru_dub: RU transcript/captions failed (%s) — "
                                   "short without captions", exc)

                # End-card CTA (Russian) — reuse the RU long-form thumbnail.
                end_card_png = None
                try:
                    from engine.publisher import generate_shorts_end_card
                    if thumb_path is not None:
                        ec = tmp / f"ru_short_ep{episode_num:03d}_endcard.png"
                        generate_shorts_end_card(
                            thumb_path, ec, show_name=config.name,
                            main_text=_RU_END_CARD_MAIN, sub_text=_RU_END_CARD_SUB)
                        if ec.exists():
                            end_card_png = ec
                except Exception as exc:  # noqa: BLE001
                    logger.warning("ru_dub: end-card render failed (%s)", exc)

                build_short_video(
                    audio, cover, short_mp4,
                    start_offset=start_offset,
                    duration=short_dur,
                    hook=ru_title,
                    scene_paths=short_scenes if len(short_scenes) >= 2 else None,
                    show_name=config.name,
                    subtitles_path=ass_path,
                    end_card=True,
                    end_card_main_text=_RU_END_CARD_MAIN,
                    end_card_sub_text=_RU_END_CARD_SUB,
                    end_card_image_path=end_card_png)
                short_title = _ru_short_title(ru_title)
                sup = upload_video(
                    short_mp4, credentials=creds,
                    title=short_title,
                    description=_ru_long_description(config, ru_desc),
                    tags=list(getattr(config, "keywords", []) or []),
                    category_id=int(getattr(yt, "category_id", 28)),
                    default_language="ru",
                    privacy_status=getattr(yt, "privacy_status", "public"))
                result["short_url"] = sup.watch_url
                # Record the title the Short actually shipped with (distinct,
                # "#Shorts"-suffixed) — the index previously recorded the
                # long-form title, hiding what @NerraRU really displayed.
                record_video(
                    video_id=sup.video_id, show_slug=config.slug,
                    episode=episode_num, kind="short", title=short_title,
                    hook=ru_title, published=date_str, watch_url=sup.watch_url,
                    channel="ru",
                    index_path=PROJECT_ROOT / config.episode.output_dir
                    / "youtube_videos.ru.json")
                pl = (getattr(yt, "ru_podcast_playlist_id", None) or "").strip()
                if pl:
                    try:
                        add_video_to_playlist(credentials=creds,
                                              video_id=sup.video_id, playlist_id=pl)
                    except Exception:  # noqa: BLE001
                        pass
                # Under a shorts-only policy the Short IS the deliverable —
                # its successful upload marks the episode done (no-op when
                # the long-form already set it).
                result["status"] = "done"
            except Exception as exc:  # noqa: BLE001
                logger.warning("ru_dub: Short failed for Ep%s (non-fatal): %s",
                               episode_num, exc)
                result["short_error"] = str(exc)

    return result
