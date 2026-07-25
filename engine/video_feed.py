"""Per-show **video podcast** RSS feeds (July 2026 pilot).

Why this exists
---------------
Apple relaunched video podcasts in February 2026 with an HLS-backed
experience — but that path is gated to a short list of hosting partners
(Acast, ART19, Omny, Simplecast et al.) behind an API-key workflow, and
Apple does not honour ``podcast:alternateEnclosure``. For a self-hoster
the only way into the Apple Podcasts video player is the original,
boring route: an ``<enclosure>`` pointing at an MP4. Apple's own guidance
is to publish the video edition as a **separate show** rather than mixing
formats in one feed.

That is exactly what this module builds: ``<show>_podcast.video.rss``
alongside the canonical ``<show>_podcast.rss``, listing the long-form
1920x1080 MP4s that the YouTube stage **already renders** for every
episode. The marginal cost of a video podcast is therefore one R2 upload
per episode and zero additional render time — the expensive artifact was
being deleted after upload (``run_show._publish_youtube``'s cleanup) and
is now kept and re-used.

Design (deliberately mirrors :mod:`engine.language_feeds`)
----------------------------------------------------------
* **Rebuilt fresh from the summaries JSON**, never by parsing the previous
  feed. Same contrast with :func:`engine.publisher.update_rss_feed`
  (incremental, preserves prior entries) — a full rebuild is idempotent
  and can be regenerated from committed state at any time.
* **Deterministic GUIDs** (``<prefix>-video-ep042-20260725``) so a rebuild
  never re-notifies subscribers or double-lists an episode. Note
  ``publisher.py`` appends ``%H%M%S%f`` to its GUIDs and is *not* stable
  that way; do not copy that here.
* **Churn suppression** — if the rendered feed differs from the file on
  disk only by ``<lastBuildDate>``, the write is skipped, so a nightly
  rebuild with no new episode produces no commit.
* **Never writes an empty feed.** No video episodes yet → returns None.

The audio feed is not touched by any of this, and no published audio
enclosure URL changes.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from engine.summaries_io import load_summaries

logger = logging.getLogger(__name__)

# Advisory enclosure length when an episode record predates the ``bytes``
# field. The long-form render is H.264 CRF 22 at 1080p30 over a slideshow,
# which measures out around 250 KB/s wall-clock. The enclosure length is
# advisory only (clients re-check on GET), so an estimate is the accepted
# fallback — same convention as engine.language_feeds._EST_BYTES_PER_SEC.
_EST_VIDEO_BYTES_PER_SEC = 250_000

# The MIME type Apple accepts for a self-hosted video episode. MOV
# (video/quicktime) and M4V (video/x-m4v) are also accepted; the network
# renders MP4 exclusively.
VIDEO_ENCLOSURE_TYPE = "video/mp4"


def video_feed_filename(audio_rss_file: str) -> str:
    """``spacex_podcast.rss`` -> ``spacex_podcast.video.rss``.

    Mirrors :func:`engine.language_feeds.feed_filename` so all derived
    feeds sit next to their master with a readable infix.
    """
    name = audio_rss_file
    if name.lower().endswith(".rss"):
        return f"{name[:-4]}.video.rss"
    return f"{name}.video.rss"


def video_r2_key(prefix: str, slug: str, filename: str) -> str:
    """R2 object key for a hosted episode video.

    Kept in its own ``video/`` keyspace (rather than beside the MP3s under
    ``<slug>/``) so the operator can point a storage lifecycle rule at
    video alone without touching the audio objects that every published
    RSS enclosure depends on.
    """
    return f"{prefix.strip('/')}/{slug}/{filename}"


def _records_with_video(records: List[dict], limit: int) -> List[dict]:
    """Episode records carrying a usable video track, newest first."""
    out: List[dict] = []
    for rec in records:
        track = rec.get("video") or {}
        if isinstance(track, dict) and track.get("url"):
            out.append(rec)
    out.sort(key=lambda r: r.get("episode_num") or 0, reverse=True)
    return out[:limit] if limit and limit > 0 else out


def _pub_datetime(rec: dict) -> _dt.datetime:
    """08:00 UTC on the episode date (matches the audio feed convention)."""
    raw = str(rec.get("date") or "").strip()
    try:
        d = _dt.date.fromisoformat(raw[:10])
    except ValueError:
        d = _dt.date.today()  # noqa: DTZ011 — episode dates are calendar dates
    return _dt.datetime.combine(d, _dt.time(8, 0, 0), tzinfo=_dt.timezone.utc)


def _enclosure_length(track: dict) -> str:
    raw = track.get("bytes")
    if isinstance(raw, int) and raw > 0:
        return str(raw)
    dur = track.get("duration_sec") or 0
    try:
        return str(int(float(dur) * _EST_VIDEO_BYTES_PER_SEC)) if dur else "0"
    except (TypeError, ValueError):
        return "0"


def _normalize_for_compare(feed_bytes: bytes) -> bytes:
    """Feed bytes with ``<lastBuildDate>`` blanked — see module docstring."""
    return re.sub(rb"<lastBuildDate>[^<]*</lastBuildDate>", b"", feed_bytes)


def _episode_description(rec: dict) -> str:
    """Prefer the stored show-notes body, fall back to the title."""
    for key in ("content", "summary"):
        val = rec.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return str(rec.get("episode_title") or "")


def build_video_feed(
    *,
    slug: str,
    summaries_path: Path,
    out_path: Path,
    guid_prefix: str,
    channel_title: str,
    channel_description: str,
    channel_link: str,
    channel_author: str,
    channel_email: str,
    channel_image: str = "",
    channel_category: str = "Technology",
    channel_subcategory: str = "",
    channel_language: str = "en-us",
    base_url: str = "https://nerranetwork.com",
    max_episodes: int = 30,
) -> Optional[Tuple[Path, int]]:
    """Write ``out_path`` as a video-podcast RSS feed for *slug*.

    Returns ``(out_path, episode_count)``, or ``None`` when the show has no
    episode carrying a ``video.url`` yet (no feed is written — an empty
    feed submitted to Apple is a rejected feed).

    Unlike the audio feed, enclosures are **not** OP3-prefixed: OP3 is an
    audio-download analytics service and its redirector is not a video CDN.
    Video play counts come from Apple Podcasts Connect instead.
    """
    from feedgen.feed import FeedGenerator

    from engine.audio import format_duration
    from engine.publisher import _inject_podcast_locked_tag, _markdown_to_rss_html

    _wrapper, records = load_summaries(summaries_path)
    targets = _records_with_video(records, max_episodes)
    if not targets:
        logger.info("[%s] no episodes with a video track — skipping video feed",
                    slug)
        return None

    fg = FeedGenerator()
    fg.load_extension("podcast")
    fg.title(channel_title)
    fg.description(channel_description)
    fg.language(channel_language)

    rss_self_url = f"{base_url.rstrip('/')}/{out_path.name}"
    fg.link(href="https://pubsubhubbub.appspot.com/", rel="hub")
    fg.link(href=rss_self_url, rel="self")
    fg.link(href=channel_link or base_url)
    fg.copyright(f"Copyright {_dt.date.today().year}")  # noqa: DTZ011
    fg.podcast.itunes_author(channel_author)
    fg.podcast.itunes_summary(channel_description)
    fg.podcast.itunes_owner(name=channel_author, email=channel_email)
    if channel_image:
        fg.podcast.itunes_image(channel_image)
    if channel_subcategory:
        fg.podcast.itunes_category({"cat": channel_category,
                                    "sub": channel_subcategory})
    else:
        fg.podcast.itunes_category(channel_category)
    fg.podcast.itunes_explicit("no")

    for rec in targets:
        track = rec["video"]
        num = int(rec.get("episode_num") or 0)
        pub = _pub_datetime(rec)
        # Deterministic + namespaced by "video" so it can never collide
        # with the audio feed's GUID for the same episode.
        guid = f"{guid_prefix}-video-ep{num:03d}-{pub:%Y%m%d}"

        # ``targets`` is newest-first; append (not feedgen's default
        # prepend) so the emitted order stays newest-first.
        fe = fg.add_entry(order="append")
        fe.id(guid)
        fe.guid(guid, permalink=False)
        title = rec.get("episode_title") or f"Episode {num}"
        desc = _episode_description(rec)
        fe.title(title)
        fe.description(_markdown_to_rss_html(desc))
        fe.enclosure(track["url"], _enclosure_length(track),
                     VIDEO_ENCLOSURE_TYPE)
        fe.published(pub)
        fe.podcast.itunes_title(title)
        fe.podcast.itunes_summary(desc)
        fe.podcast.itunes_episode(num)
        fe.podcast.itunes_episode_type("full")
        fe.podcast.itunes_explicit("no")
        dur = track.get("duration_sec")
        if dur:
            try:
                fe.podcast.itunes_duration(format_duration(float(dur)))
            except Exception as exc:  # noqa: BLE001 — duration is advisory
                logger.debug("[%s] ep%s duration %r unusable: %s",
                             slug, num, dur, exc)

    fg.lastBuildDate(_dt.datetime.now(_dt.timezone.utc))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".rss", dir=str(out_path.parent))
    os.close(tmp_fd)
    try:
        fg.rss_file(tmp_path, pretty=True)
        _inject_podcast_locked_tag(Path(tmp_path),
                                   channel_email or "patrick@planetterrian.com")
        if out_path.exists():
            new_bytes = Path(tmp_path).read_bytes()
            old_bytes = out_path.read_bytes()
            if _normalize_for_compare(new_bytes) == _normalize_for_compare(old_bytes):
                logger.info("[%s] %s unchanged (%d episodes) — skipping write",
                            slug, out_path.name, len(targets))
                return out_path, len(targets)
        os.replace(tmp_path, str(out_path))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    logger.info("[%s] wrote %s (%d video episodes)",
                slug, out_path.name, len(targets))
    return out_path, len(targets)


def build_video_feed_for_show(config, project_root: Path) -> Optional[Tuple[Path, int]]:
    """Resolve everything from a show's config and build its video feed.

    Returns ``None`` (and logs one line) when the show hasn't opted in or
    has no video episodes yet — a clean no-op is the contract for every
    optional surface in this repo.
    """
    vp = getattr(config, "video_podcast", None)
    if not (vp and vp.enabled):
        return None

    pub = config.publishing
    summaries_path = project_root / pub.summaries_json
    if not summaries_path.exists():
        logger.info("[%s] no summaries file — skipping video feed", config.slug)
        return None

    rss_file = vp.rss_file or video_feed_filename(pub.rss_file)
    title = f"{pub.rss_title or config.name}{vp.title_suffix}"
    return build_video_feed(
        slug=config.slug,
        summaries_path=summaries_path,
        out_path=project_root / rss_file,
        guid_prefix=pub.guid_prefix or config.slug,
        channel_title=title,
        channel_description=(vp.channel_description
                             or pub.rss_description
                             or config.description),
        channel_link=pub.rss_link or pub.base_url,
        channel_author=pub.rss_author or "Nerra Network",
        channel_email=pub.rss_email or "patrick@planetterrian.com",
        channel_image=vp.channel_image or pub.rss_image or "",
        channel_category=pub.rss_category or "Technology",
        channel_subcategory=pub.rss_subcategory or "",
        base_url=pub.base_url or "https://nerranetwork.com",
        max_episodes=vp.max_episodes,
    )


def upload_episode_video(local_mp4: Path, config) -> Optional[Dict[str, Any]]:
    """Upload one episode MP4 to R2 and return its track record.

    Returns ``{"url", "bytes", "filename"}`` or ``None`` — never raises.
    Called from the YouTube stage while the rendered MP4 is still on disk
    (it is deleted moments later), so a failure here must degrade to "no
    video episode today", never to a failed publish.

    Uses ``upload_to_r2`` directly rather than ``storage.upload_episode``
    because the latter hardcodes the ``<slug>/<name>`` audio keyspace and
    lets the content type default to ``audio/mpeg`` for non-.mp3 files —
    which would make Apple refuse the enclosure.
    """
    vp = getattr(config, "video_podcast", None)
    if not (vp and vp.enabled):
        return None
    storage = getattr(config, "storage", None)
    if not storage or getattr(storage, "provider", "") != "r2":
        logger.warning("[%s] video podcast enabled but storage.provider is not "
                       "r2 — no host for the MP4, skipping", config.slug)
        return None
    if not (local_mp4 and local_mp4.exists()):
        return None

    try:
        from engine.storage import upload_to_r2

        endpoint = os.getenv(storage.endpoint_env, "")
        access_key = os.getenv(storage.access_key_env, "")
        secret_key = os.getenv(storage.secret_key_env, "")
        if not (endpoint and access_key and secret_key):
            logger.warning("[%s] R2 credentials unset — skipping video upload",
                           config.slug)
            return None

        key = video_r2_key(vp.r2_prefix, config.slug, local_mp4.name)
        size = local_mp4.stat().st_size
        url = upload_to_r2(
            local_mp4, key,
            bucket=storage.bucket,
            endpoint_url=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            public_base_url=storage.public_base_url,
            content_type=VIDEO_ENCLOSURE_TYPE,
        )
        logger.info("[%s] uploaded episode video (%.1f MB) -> %s",
                    config.slug, size / 1e6, url)
        return {"url": url, "bytes": size, "filename": local_mp4.name}
    except Exception as exc:  # noqa: BLE001 — video is never publish-critical
        logger.warning("[%s] episode video upload failed (non-fatal): %s",
                       config.slug, exc)
        return None
