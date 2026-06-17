"""Per-language podcast RSS feeds (June 2026 multilingual distribution).

Background
----------
The multilingual stage (``scripts/generate_translations.py`` +
``engine/translate.py``) renders alternate-language audio tracks of each
finalized English episode and records them on the show's summaries record
under ``translations[<lang>]`` (``audio_url`` / ``title`` / ``description`` /
``duration_sec``). Until now those tracks were surfaced on the website only
(the on-site language player) — never as a subscribable podcast feed.

This module emits a **standalone Apple/Spotify-ready RSS feed per
(show, language)** so each translation track is a real podcast episode in a
real feed: ``<show>_podcast.fr.rss`` next to the canonical English
``<show>_podcast.rss``. Each feed:

* carries a **translated channel title + description** (cached in
  ``digests/<slug>/channel_i18n.json`` so nightly rebuilds cost no Grok
  credits; falls back to an autonym-suffixed English title when no cache and
  no API key),
* declares the correct BCP-47 ``<language>`` so directories shelve it in the
  right locale,
* lists **only** the episodes that actually have a track in that language,
* uses a **stable, deterministic GUID** per (episode, language) so a rebuild
  never re-notifies subscribers or duplicates an episode.

Unlike ``engine.publisher.update_rss_feed`` (incremental, parses+preserves
the prior file per episode), these feeds are rebuilt **fresh from the
canonical summaries JSON** every run — they are fully regenerable, so the
build is idempotent and never depends on the previous feed file.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from engine.summaries_io import load_summaries

logger = logging.getLogger(__name__)

# BCP-47 code -> (autonym for the channel-title suffix, full locale tag for
# the RSS <language> element). Apple/Spotify shelve a feed by its <language>,
# so we emit a region-qualified tag rather than the bare subtag.
LANGUAGE_META: Dict[str, Tuple[str, str]] = {
    "fr": ("Français", "fr-fr"),
    "ru": ("Русский", "ru-ru"),
    "es": ("Español", "es-es"),
    "zh": ("中文", "zh-cn"),
}

# Advisory enclosure byte-length estimate when a track record predates the
# ``bytes`` field. The network encodes spoken-word+music VBR ~245 kbps
# (~30 KB/s); the enclosure length is advisory only, so an estimate is the
# standard fallback when the exact size is unknown.
_EST_BYTES_PER_SEC = 30_000


def supported_feed_languages() -> Tuple[str, ...]:
    return tuple(LANGUAGE_META.keys())


def language_autonym(lang: str) -> str:
    return LANGUAGE_META.get(lang, (lang, lang))[0]


def feed_locale(lang: str) -> str:
    return LANGUAGE_META.get(lang, (lang, lang))[1]


def feed_filename(english_rss_file: str, lang: str) -> str:
    """``spacex_podcast.rss`` + ``fr`` -> ``spacex_podcast.fr.rss``."""
    name = english_rss_file
    if name.lower().endswith(".rss"):
        return f"{name[:-4]}.{lang}.rss"
    return f"{name}.{lang}.rss"


# ---------------------------------------------------------------------------
# Channel-title/description i18n cache
# ---------------------------------------------------------------------------

def _channel_i18n_path(summaries_path: Path) -> Path:
    return Path(summaries_path).parent / "channel_i18n.json"


def load_channel_i18n(summaries_path: Path) -> Dict[str, dict]:
    path = _channel_i18n_path(summaries_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001 — best-effort cache
        logger.warning("Could not read channel i18n cache %s: %s", path, exc)
        return {}


def save_channel_i18n(summaries_path: Path, data: Dict[str, dict]) -> None:
    path = _channel_i18n_path(summaries_path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_channel_i18n(
    summaries_path: Path,
    lang: str,
    en_title: str,
    en_description: str,
    *,
    translate_fn: Optional[Callable[[str, str, str], Tuple[str, str]]] = None,
    refresh: bool = False,
) -> Tuple[str, str]:
    """Return ``(channel_title, channel_description)`` for *lang*.

    Uses the on-disk cache first. When the cache is missing for *lang* (or
    *refresh*) and a ``translate_fn`` is supplied, translates once and writes
    the cache. With no cache and no ``translate_fn`` it degrades to an
    autonym-suffixed English title + the English description, so a nightly
    rebuild with no Grok key still produces a valid, shippable feed.

    ``translate_fn`` has the shape ``(title, description, lang) ->
    (title, description)`` — i.e. ``engine.translate.translate_metadata``.
    """
    cache = load_channel_i18n(summaries_path)
    cached = cache.get(lang)
    if cached and not refresh and cached.get("title"):
        return cached["title"], cached.get("description") or en_description

    if translate_fn is not None:
        try:
            t_title, t_desc = translate_fn(en_title, en_description, lang)
            if t_title:
                cache[lang] = {
                    "title": t_title,
                    "description": t_desc,
                    "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                }
                save_channel_i18n(summaries_path, cache)
                return t_title, t_desc
        except Exception as exc:  # noqa: BLE001 — fall through to autonym
            logger.warning("Channel metadata translation (%s) failed: %s", lang, exc)

    # Deterministic fallback: keep the brand, signal the language.
    return f"{en_title} ({language_autonym(lang)})", en_description


# ---------------------------------------------------------------------------
# Feed construction
# ---------------------------------------------------------------------------

def _records_for_language(records: List[dict], lang: str) -> List[dict]:
    """Episode records that carry a usable track for *lang*, newest first."""
    out: List[dict] = []
    for rec in records:
        tr = (rec.get("translations") or {}).get(lang) or {}
        if tr.get("audio_url"):
            out.append(rec)
    out.sort(key=lambda r: r.get("episode_num") or 0, reverse=True)
    return out


def _pub_datetime(rec: dict) -> _dt.datetime:
    """08:00 UTC on the episode date (matches the English feed convention)."""
    raw = str(rec.get("date") or "").strip()
    try:
        d = _dt.date.fromisoformat(raw[:10])
    except ValueError:
        d = _dt.date.today()
    return _dt.datetime.combine(d, _dt.time(8, 0, 0), tzinfo=_dt.timezone.utc)


def _enclosure_length(track: dict) -> str:
    raw = track.get("bytes")
    if isinstance(raw, int) and raw > 0:
        return str(raw)
    dur = track.get("duration_sec") or 0
    try:
        return str(int(float(dur) * _EST_BYTES_PER_SEC)) if dur else "0"
    except (TypeError, ValueError):
        return "0"


def build_language_feed(
    *,
    slug: str,
    lang: str,
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
    base_url: str = "https://nerranetwork.com",
) -> Optional[Tuple[Path, int]]:
    """Write ``out_path`` as a podcast RSS feed of *lang* tracks.

    Returns ``(out_path, episode_count)`` on success, or ``None`` when the
    show has no episodes translated into *lang* yet (no feed is written —
    we never publish an empty feed).
    """
    from feedgen.feed import FeedGenerator

    from engine.audio import format_duration
    from engine.publisher import _inject_podcast_locked_tag, _markdown_to_rss_html

    if lang not in LANGUAGE_META:
        raise ValueError(f"Unsupported feed language {lang!r}")

    _wrapper, records = load_summaries(summaries_path)
    targets = _records_for_language(records, lang)
    if not targets:
        logger.info("[%s/%s] no translated episodes — skipping feed", slug, lang)
        return None

    fg = FeedGenerator()
    fg.load_extension("podcast")
    fg.title(channel_title)
    fg.description(channel_description)
    fg.language(feed_locale(lang))

    rss_self_url = f"{base_url.rstrip('/')}/{out_path.name}"
    fg.link(href="https://pubsubhubbub.appspot.com/", rel="hub")
    fg.link(href=rss_self_url, rel="self")
    fg.link(href=channel_link or base_url)
    fg.copyright(f"Copyright {_dt.date.today().year}")
    fg.podcast.itunes_author(channel_author)
    fg.podcast.itunes_summary(channel_description)
    fg.podcast.itunes_owner(name=channel_author, email=channel_email)
    if channel_image:
        fg.podcast.itunes_image(channel_image)
    if channel_subcategory:
        fg.podcast.itunes_category({"cat": channel_category, "sub": channel_subcategory})
    else:
        fg.podcast.itunes_category(channel_category)
    fg.podcast.itunes_explicit("no")

    for rec in targets:
        track = rec["translations"][lang]
        num = int(rec.get("episode_num") or 0)
        pub = _pub_datetime(rec)
        # Deterministic GUID: stable across rebuilds so subscribers are never
        # re-notified and the platform never double-lists the episode.
        guid = f"{guid_prefix}-{lang}-ep{num:03d}-{pub:%Y%m%d}"

        # ``targets`` is newest-first; append (not the feedgen default
        # prepend) so the emitted order stays newest-first like the
        # English feed and what podcast clients expect.
        fe = fg.add_entry(order="append")
        fe.id(guid)
        fe.guid(guid, permalink=False)
        title = track.get("title") or rec.get("episode_title") or f"Episode {num}"
        desc = track.get("description") or title
        fe.title(title)
        fe.description(_markdown_to_rss_html(desc))
        fe.enclosure(track["audio_url"], _enclosure_length(track), "audio/mpeg")
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
            except Exception:  # noqa: BLE001 — duration is advisory
                pass

    fg.lastBuildDate(_dt.datetime.now(_dt.timezone.utc))

    import os
    import tempfile

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".rss", dir=str(out_path.parent))
    os.close(tmp_fd)
    try:
        fg.rss_file(tmp_path, pretty=True)
        _inject_podcast_locked_tag(Path(tmp_path), channel_email or "patrick@planetterrian.com")
        os.replace(tmp_path, str(out_path))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    logger.info("[%s/%s] wrote %s (%d episodes)", slug, lang, out_path.name, len(targets))
    return out_path, len(targets)
