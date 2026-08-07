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

from engine.youtube_policy import MAX_SHORTS_PER_EPISODE

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


def _ru_long_description(config, ru_desc: str, *,
                         episode_num: int = 0,
                         kind: str = "long",
                         variant: str = "") -> str:
    """RU description with a funnel-tagged, Russian-language destination.

    Before July 2026 this linked the bare English homepage with no UTM:
    the network's highest-reach surface pointed at a page its audience
    could not read, and its traffic was unattributable. ``engine.funnel``
    resolves ``funnel.destinations.ru`` (the Russian landing page for
    shows in the pilot) and falls back to the show page for everyone
    else, so an un-piloted show's only change is that its clicks are now
    countable.
    """
    from engine import funnel as _funnel

    base_url = getattr(config.publishing, "base_url", "https://nerranetwork.com")
    dest = _funnel.destination_for(config, channel="ru") or base_url
    link = _funnel.episode_link(
        dest, getattr(config, "slug", ""), episode_num,
        channel="ru", kind=kind, variant=variant,
        placement=_funnel.PLACEMENT_DESCRIPTION,
    ) or dest
    lines = [ru_desc.strip(), "", f"🎧 Все выпуски по-русски: {link}",
             "", _AI_DISCLOSURE_RU]
    tags = _hashtags(config)
    if tags:
        lines += ["", tags]
    return "\n".join(lines).strip()


def _cap_title(title: str, limit: int = 95) -> str:
    # Word-boundary clip (engine.titles) — a mid-word slice on the dub
    # channels is the exact failure the one-title-policy pass removed
    # from every other surface.
    from engine.titles import clip_words

    return clip_words((title or "").strip(), limit)


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


# Function words that cannot end a headline. A word-boundary trim keeps
# words whole but is blind to whether the phrase it leaves behind is one —
# so it happily produces "...force les astronomes à #Shorts".
#
# Measured across every tracked Short: FR 26% of titles ended mid-clause,
# RU 5%, EN 1%. FR is worst because its Short title is cut from the
# translated LONG title at 70 chars, and French runs ~15-20% longer than
# the English it is translated from, so the cut lands inside a phrase far
# more often. EN is nearly clean because its Short titles are written whole
# by the title bundle rather than cut from anything.
#
# Per language, and a missing language is a no-op — a wrong stop-word list
# would mangle titles, so an unknown language keeps the plain word trim.
_DANGLING_TAIL = {
    "fr": (
        "de du des le la les un une à au aux en dans sur pour avec par "
        "que qui et ou est sont alors plus son sa ses leur leurs ce cette "
        "ces se ne pas comme mais donc car si quand dont où vers chez "
        "sous entre depuis après avant ainsi très bien encore"
    ),
    "ru": (
        "и в во на с со к ко о об от до по за из у для при над под про "
        "без через между что как же бы ли не но а или то это его её их "
        "свой своя свои чтобы уже ещё"
    ),
    "es": (
        "de del la el los las un una a al en con por para que quien y o "
        "es son pero su sus este esta estos como cuando donde sobre "
        "entre desde hasta más"
    ),
    "en": (
        "the a an and or of to in on at for with from by as is are was "
        "were that which its his her their this these but so than into "
        "over after before"
    ),
}
_DANGLING_RE = {
    code: re.compile(
        r"[\s,;:—-]+(?:" + "|".join(re.escape(w) for w in words.split()) + r")$",
        re.IGNORECASE | re.UNICODE,
    )
    for code, words in _DANGLING_TAIL.items()
}

# Never strip a headline below this fraction of its budget. A title that
# ends on a preposition is bad; a three-word title is worse.
_MIN_TRIM_RATIO = 0.55


def _clause_trim(text: str, limit: int, lang: str = "") -> str:
    """``_word_trim`` that also refuses to end on a dangling function word.

    Trailing function words are peeled off one at a time — a cut can leave
    two ("... de la"), and removing only the last still ends on a
    preposition. Peeling stops at ``_MIN_TRIM_RATIO`` of the limit so a
    phrase made mostly of short words cannot be eaten down to nothing.
    """
    trimmed = _word_trim(text, limit)
    pattern = _DANGLING_RE.get((lang or "").strip().lower())
    if pattern is None:
        return trimmed
    # Floor against the ACTUAL text length, not the budget: a title that
    # arrives already shorter than 55% of the limit (e.g. 31 chars vs a
    # 70-char budget) previously started below the floor, so the peel
    # loop never ran and the dangling "à"/"de" tail — the exact defect
    # this function exists to remove — survived untouched.
    floor = max(1, int(min(len(trimmed), limit) * _MIN_TRIM_RATIO))
    while len(trimmed) > floor:
        shorter = pattern.sub("", trimmed).rstrip(" ,.:;—-…")
        if shorter == trimmed:
            break
        trimmed = shorter
    return trimmed


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
            yaml_shorts=1,            # policy may raise (cap: MAX_SHORTS_PER_EPISODE)
            # July 18 2026: the RU Short path genuinely runs the smart
            # selector on its own RU transcript, so the policy is allowed
            # to raise the Shorts count (RU Shorts are the network's
            # best-performing format — spacex-RU short_vpd 30 — and the
            # old smart_mode=False silently capped every RU show at 1).
            smart_mode=True,
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
    body = _clause_trim(body, ceiling, "ru")
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
                    description=_ru_long_description(
                        config, ru_desc,
                        episode_num=episode_num, kind="long"),
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

        # --- Shorts (best-effort; failure never blocks the long-form result) ---
        # July 18 2026: multiple Shorts per episode when the policy asks
        # (RU Shorts are the network's best-performing format). Window
        # selection = top-N with fill on the RU transcript; each Short is
        # its own try/except so a second-Short failure never costs the
        # first.
        #
        # July 30 2026: the local cap was `min(2, ...)`, which silently
        # discarded whatever the policy computed above it. That mattered
        # the moment the policy gained a 3-Short band, because the shows
        # in that band are RU spacex / RU fascinating_frontiers / RU tesla
        # — this path exactly. The bound now comes from
        # MAX_SHORTS_PER_EPISODE so raising a policy band raises the
        # supply, and the ceiling is one named constant rather than a
        # literal buried in two dub modules.
        if build_short and getattr(yt, "publish_shorts", True):
            ru_shorts = max(1, min(MAX_SHORTS_PER_EPISODE,
                                   int(plan.get("shorts", 1) or 1)))
            short_scenes = []
            try:
                short_scenes = _download_images(short_urls, tmp) if short_urls else []
            except Exception as exc:  # noqa: BLE001
                logger.warning("ru_dub: scene download failed (%s)", exc)
            short_dur = float(getattr(yt, "short_duration_seconds", 35.0))
            base_offset = float(getattr(yt, "shorts_start_offset", 0.0) or 0.0)

            # Transcribe once; select up to ru_shorts windows. Parity with
            # the EN shorts: Russian Whisper word timestamps → smart
            # engaging-beat starts + per-word Cyrillic ASS captions.
            # Every piece is best-effort — a Short still ships without them.
            tr_json = None
            windows: list = []
            try:
                from engine.transcripts import generate_transcript
                from engine.shorts_selector import pick_top_n_engaging_windows
                from engine.audio import get_audio_duration
                tr = generate_transcript(
                    audio, tmp, f"ru_ep{episode_num:03d}", language="ru")
                if tr and tr.json_path.exists():
                    tr_json = tr.json_path
                    total_dur = get_audio_duration(audio) or 0.0
                    windows = pick_top_n_engaging_windows(
                        tr_json, n=ru_shorts,
                        audio_offset=base_offset,
                        audio_duration=total_dur,
                        window_duration=short_dur,
                        min_start_final=base_offset,
                        fill_to_n=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ru_dub: RU transcript/selection failed (%s) — "
                               "voice-start short without captions", exc)

            # Hook-first (July 31 2026 operator directive, all channels):
            # Short #1 is the dub's opening hook sequence — the RU/FR
            # track translates the same cold-open script, so t~=0 is the
            # hook there too. Smart windows fill the remaining slots.
            if bool(getattr(yt, "shorts_first_is_hook", True)):
                from engine.shorts_selector import hook_first_windows
                windows = hook_first_windows(
                    list(windows or []), n=max(1, ru_shorts),
                    hook_start=base_offset, window_duration=short_dur,
                )

            # Plan: (offset, opening_text, window_label) per Short; legacy
            # single voice-start fallback when the selector yields nothing.
            if windows:
                short_plan = [
                    (w.start_seconds, (w.opening_text or "").strip(),
                     ("hook_open" if w.score == float("inf")
                      else "qualified" if getattr(w, "qualified", True)
                      else "filled"))
                    for w in windows[:ru_shorts]
                ]
            else:
                short_plan = [(base_offset, "", "legacy_fallback")]

            # End-card CTA (Russian) — shared across Shorts; reuse the RU
            # long-form thumbnail.
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

            # Staggered Shorts (Aug 2026): Short #1 publishes now; later
            # Shorts upload private with publishAt at the RU audience's
            # evening slots. Failure = legacy publish-all-now.
            _stagger_times: list = []
            if len(short_plan) > 1 and bool(
                getattr(yt, "shorts_stagger_enabled", False)
            ):
                try:
                    from engine.shorts_stagger import (
                        resolve_slot_hours,
                        stagger_publish_times,
                    )
                    import datetime as _sdt
                    _stagger_times = stagger_publish_times(
                        _sdt.datetime.now(_sdt.timezone.utc),
                        len(short_plan) - 1,
                        slot_hours=resolve_slot_hours(yt, "ru"),
                    )
                    logger.info(
                        "ru_dub: Shorts stagger — #1 now, %d scheduled at %s",
                        len(_stagger_times),
                        ", ".join(t.strftime("%Y-%m-%dT%H:%MZ")
                                  for t in _stagger_times))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("ru_dub: stagger scheduling failed — all "
                                   "Shorts publish immediately: %s", exc)
                    _stagger_times = []

            short_urls_out: list = []
            for short_idx, (start_offset, opening_text,
                            window_label) in enumerate(short_plan):
                try:
                    suffix = "" if short_idx == 0 else f"_{short_idx + 1}"
                    short_mp4 = tmp / f"ru_short_ep{episode_num:03d}{suffix}.mp4"

                    ass_path = None
                    if tr_json is not None:
                        try:
                            from engine.captions import transcript_to_ass_window
                            ass_candidate = (
                                tmp / f"ru_short_ep{episode_num:03d}{suffix}.ass")
                            transcript_to_ass_window(
                                tr_json, ass_candidate,
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
                            logger.warning(
                                "ru_dub: ASS captions failed for short %d "
                                "(%s)", short_idx + 1, exc)

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

                    # Titles: Short #1 keeps the optimized-derived headline;
                    # Short #2 leads with ITS window's opening text (already
                    # Russian — it's the RU transcript) so the two Shorts
                    # are genuinely distinct in the feed.
                    if short_idx == 0 or not opening_text:
                        short_title = _ru_short_title(ru_title)
                        if short_idx > 0:
                            short_title = _ru_short_title(
                                ru_title, body_limit=58) + " — ещё момент"
                    else:
                        # Aug 2026: the 2nd/3rd Short's window opening is a
                        # mid-sentence slice by construction, so first ask
                        # Grok for a complete headline from that excerpt
                        # (engine.translate.headline_from_excerpt — grounded
                        # in the excerpt only, never-invent). Any failure
                        # falls back to the legacy clause-trim so a Short
                        # never ships untitled. Title-only metadata.
                        _limit = min(70, _YT_TITLE_MAX - len(_SHORTS_SUFFIX))
                        body = ""
                        try:
                            from engine.translate import headline_from_excerpt
                            body = headline_from_excerpt(
                                opening_text, "ru", max_chars=_limit)
                        except Exception:  # noqa: BLE001
                            body = ""
                        if body:
                            body = _clause_trim(body, _limit, "ru")
                        else:
                            # Legacy clause-aware trim of the raw excerpt.
                            body = _clause_trim(
                                opening_text.rstrip("…").rstrip(),
                                _limit, "ru")
                        short_title = f"{body}{_SHORTS_SUFFIX}".strip()

                    _publish_at = (
                        _stagger_times[short_idx - 1]
                        if short_idx >= 1
                        and (short_idx - 1) < len(_stagger_times)
                        else None
                    )
                    sup = upload_video(
                        short_mp4, credentials=creds,
                        title=short_title,
                        description=_ru_long_description(
                            config, ru_desc,
                            episode_num=episode_num, kind="short"),
                        tags=list(getattr(config, "keywords", []) or []),
                        category_id=int(getattr(yt, "category_id", 28)),
                        default_language="ru",
                        privacy_status=getattr(yt, "privacy_status", "public"),
                        publish_at=_publish_at)
                    short_urls_out.append(sup.watch_url)
                    # July 18 2026 (operator-approved): RU funnel comment.
                    # A Russian Short must never link an English video, so
                    # the long-form link is used only when a RU long-form
                    # actually shipped this run.
                    #
                    # July 2026 pilot fix: @NerraRU sits on a shorts-only
                    # tier for most shows (RU long-form was demoted after
                    # ~9% retention), so `long_url` is empty on nearly
                    # every run — which meant the network's highest-reach
                    # surface posted NO comment at all on most days. When
                    # there is no RU long-form, the comment now carries the
                    # show's Russian landing page instead of nothing.
                    if bool(getattr(yt, "auto_comment", True)):
                        try:
                            from engine.youtube import post_video_comment
                            from engine import funnel as _funnel

                            if long_url:
                                _text = ("▶ Полный выпуск: " + long_url
                                         + "\n🔔 Подпишитесь — новые выпуски "
                                           "каждый день")
                            else:
                                _dest = _funnel.episode_link(
                                    _funnel.destination_for(
                                        config, channel="ru"),
                                    getattr(config, "slug", ""), episode_num,
                                    channel="ru", kind="short",
                                    placement=_funnel.PLACEMENT_COMMENT,
                                )
                                _text = (
                                    "▶ Полный выпуск и все эпизоды "
                                    "по-русски: " + _dest
                                    + "\n🔔 Подпишитесь — новые выпуски "
                                      "каждый день"
                                ) if _dest else ""
                            if _text and _publish_at is not None:
                                # Can't comment on a private (scheduled)
                                # video — queue for the post-publish sweep.
                                from engine.shorts_stagger import queue_comment
                                queue_comment(
                                    PROJECT_ROOT / config.episode.output_dir,
                                    video_id=sup.video_id, channel="ru",
                                    text=_text, publish_at=_publish_at)
                            elif _text:
                                post_video_comment(
                                    credentials=creds,
                                    video_id=sup.video_id,
                                    text=_text)
                        except Exception:  # noqa: BLE001
                            pass
                    # Record the title the Short actually shipped with
                    # (distinct, "#Shorts"-suffixed) — the index previously
                    # recorded the long-form title, hiding what @NerraRU
                    # really displayed.
                    record_video(
                        video_id=sup.video_id, show_slug=config.slug,
                        episode=episode_num, kind="short", title=short_title,
                        hook=ru_title,
                        # Scheduled Shorts go public at publishAt — record
                        # that date so policy vpd math stays honest.
                        published=(f"{_publish_at:%Y-%m-%d}"
                                   if _publish_at else date_str),
                        watch_url=sup.watch_url,
                        channel="ru",
                        window=window_label,
                        index_path=PROJECT_ROOT / config.episode.output_dir
                        / "youtube_videos.ru.json")
                    pl = (getattr(yt, "ru_podcast_playlist_id", None) or "").strip()
                    if pl:
                        try:
                            add_video_to_playlist(credentials=creds,
                                                  video_id=sup.video_id,
                                                  playlist_id=pl)
                        except Exception:  # noqa: BLE001
                            pass
                    # Under a shorts-only policy the Short IS the
                    # deliverable — its successful upload marks the episode
                    # done (no-op when the long-form already set it).
                    result["status"] = "done"
                except Exception as exc:  # noqa: BLE001
                    logger.warning("ru_dub: Short %d failed for Ep%s "
                                   "(non-fatal): %s",
                                   short_idx + 1, episode_num, exc)
                    result["short_error"] = str(exc)

            if short_urls_out:
                result["short_url"] = short_urls_out[0]
                result["short_urls"] = short_urls_out

    return result
