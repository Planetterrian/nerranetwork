#!/usr/bin/env python3
"""Join gallery images with YouTube retention — the imagery data flywheel.

The gallery manifest (``site/data/gallery-manifest.json``) knows which Grok
Imagine images went into which episode's video; the YouTube analytics
fetcher (``scripts/fetch_youtube_analytics.py`` → ``api/youtube_stats.json``)
knows each video's ``averageViewPercentage`` (retention — the strongest
public content-quality signal). Neither side alone can answer "which imagery
styles keep viewers watching?" — this script joins them into
``api/gallery_retention.json`` so the dashboard (and a future
image-prompt feedback loop, mirroring the title-hint loop in
``scripts/update_youtube_performance.py``) can rank image tags by the mean
retention of the videos they appeared in.

Join strategy: an image's ``youtube_video_id`` wins when present (the
sidecar field exists but uploads happen before the video id is known, so it
is usually empty); otherwise the image joins on
``(show_slug, episode number, kind)`` — ``segment_card`` (16:9) images pair
with the ``long`` upload, ``social`` (9:16) with the ``short``.

Per-show summary: top/bottom tags by mean retention, only for tags backed by
at least ``--min-videos`` (default 3) distinct videos — below that the mean
is noise.

Clean no-op by convention: when the manifest or the analytics file is
missing/empty, the output is written with an empty ``shows`` map (never an
error), so the nightly workflow can run this unconditionally.

Usage::

    python scripts/build_gallery_retention.py                    # write api/gallery_retention.json
    python scripts/build_gallery_retention.py --dry-run          # print, no write
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT = _SCRIPT_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("build_gallery_retention")

# Manifest intended_use → youtube_videos kind. Only these two uses appear in
# rendered videos; thumbnails/variants/other are skipped (no watch-time to
# attribute).
_USE_TO_KIND = {"segment_card": "long", "social": "short"}

# Tags that appear on virtually every image (slug, provider, use) carry no
# imagery-style signal and would dominate every summary.
_GENERIC_TAGS = frozenset({"grok-imagine", "segment_card", "social",
                           "thumbnail_variant"})

# Sep 22 2026: the prompt boilerplate every image carries, excluded from
# the style tags by NAME (not only by document frequency): the 9:16
# framing hint rides on every Short, Shorts hold ~60% against ~15% on
# long-form, so pooled over both kinds "vertical 9:16 framing" was every
# show's top tag and "wide cinematic 16:9 framing" its bottom — a
# measurement of the KIND, not of the imagery.
_BY_KIND_MIN_VIDEOS = 10
# Boilerplate from RETIRED prompt shapes still in the manifest (the
# committed images go back to May 2026): the pre-Sep no-text chunk, the
# June quality cue, and the descriptor default. Read on the real
# manifest 2026-09-22 — each ranked as a "style" on a flagship.
_LEGACY_BOILERPLATE = frozenset({
    "clean photographic composition", "ultra-detailed", "cinematic",
    "photorealistic news photo", "photorealistic editorial photography",
})
# The legacy prompt scaffold leaked its own label into the phrases
# ("visual subject: title" — the SpaceX placeholder-headline bug).
_SCAFFOLD_PREFIXES = ("visual subject:", "depicting:")


def _style_boilerplate() -> frozenset:
    phrases = set(_LEGACY_BOILERPLATE)
    try:
        from engine.grok_imagine import (FRAMING_HINT_VERTICAL, FRAMING_HINT_WIDE,
                                         NO_TEXT_HINT, QUALITY_HINT)
    except Exception:  # noqa: BLE001 — the join must not depend on the engine
        return frozenset(phrases)
    for hint in (FRAMING_HINT_VERTICAL, FRAMING_HINT_WIDE, QUALITY_HINT, NO_TEXT_HINT):
        phrases.update(_prompt_phrases(hint))
        # The first comma chunk of a hint can run past the phrase cap
        # ("clean photographic composition with ZERO text ..."); older
        # prompts split it shorter, so exclude its leading words too.
        for chunk in hint.split(","):
            words = chunk.lower().split()
            if len(words) > _MAX_PHRASE_WORDS:
                phrases.add(" ".join(words[:3]))
    return frozenset(phrases)


_STYLE_BOILERPLATE: frozenset = frozenset()


def _load_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — absent data = clean no-op
        logger.info("Unreadable %s (%s) — treating as absent", path, exc)
        return None
    return data if isinstance(data, dict) else None


def _episode_number(episode_id: str) -> Optional[int]:
    """``ep051`` → 51 (the manifest form); bare digits also accepted."""
    m = re.search(r"(\d+)", str(episode_id or ""))
    return int(m.group(1)) if m else None


def _index_videos(stats: dict) -> tuple:
    """Index analytics rows by video_id and by (slug, episode, kind)."""
    by_id: Dict[str, dict] = {}
    by_key: Dict[tuple, dict] = {}
    for show in (stats.get("shows") or {}).values():
        for v in (show or {}).get("videos") or []:
            vid = v.get("video_id")
            if not vid:
                continue
            by_id[vid] = v
            slug = v.get("show_slug") or ""
            episode = v.get("episode")
            kind = v.get("kind") or ""
            if slug and episode is not None and kind:
                # First writer wins — multi-Shorts episodes upload several
                # ``short`` rows; attributing the 9:16 set to the first is
                # the stable, deterministic choice.
                by_key.setdefault((slug, int(episode), kind), v)
    return by_id, by_key


_MAX_PHRASE_WORDS = 4
_BOILERPLATE_DOC_FREQ = 0.5  # phrase in >50% of a show's images = boilerplate


def _prompt_phrases(prompt: str) -> List[str]:
    """Comma-split a Grok-Imagine prompt into normalized style phrases."""
    out: List[str] = []
    for chunk in (prompt or "").split(","):
        phrase = " ".join(chunk.lower().split())
        if not phrase or len(phrase.split()) > _MAX_PHRASE_WORDS:
            continue
        # A 1-2 char "phrase" carries no style information — the Aug 27
        # 2026 report ranked the literal tag "x" (from "X platform" /
        # "x.com" prompt fragments) as spacex's TOP retention tag.
        if len(phrase) < 3:
            continue
        out.append(phrase)
    return out


def build_style_tag_index(manifest: Optional[dict]) -> Dict[str, frozenset]:
    """Per-show boilerplate phrase sets, mined from prompt document frequency.

    July 18 2026: the manifest ``tags`` arrays carry only boilerplate
    (slug + 'social' + 'grok-imagine'), so the old join produced EMPTY tag
    summaries — the retention loop collected data but labeled nothing.
    The real style signal is the ``prompt`` field. Phrases appearing in
    more than half of a show's images (the shared descriptor suffix like
    "cinematic", "ultra-detailed", "wide cinematic 16:9 framing") are
    boilerplate and excluded, with no hand-curated stoplist to maintain.
    """
    counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals: Dict[str, int] = defaultdict(int)
    for entry in (manifest or {}).get("images") or []:
        slug = entry.get("show_slug") or ""
        if not slug:
            continue
        totals[slug] += 1
        for phrase in set(_prompt_phrases(entry.get("prompt") or "")):
            counts[slug][phrase] += 1
    boilerplate: Dict[str, frozenset] = {}
    for slug, phrases in counts.items():
        total = max(1, totals[slug])
        boilerplate[slug] = frozenset(
            p for p, c in phrases.items()
            if c / total > _BOILERPLATE_DOC_FREQ
        )
    return boilerplate


def _style_tags(entry: dict, boilerplate: frozenset) -> List[str]:
    """Distinctive style tags for one image: prompt phrases minus
    boilerplate (document-frequency AND the named prompt hints), plus
    any non-generic manifest tags."""
    slug = entry.get("show_slug") or ""
    tags = [p for p in _prompt_phrases(entry.get("prompt") or "")
            if p not in boilerplate and p not in _STYLE_BOILERPLATE
            and p != slug and not p.startswith(_SCAFFOLD_PREFIXES)]
    for t in entry.get("tags") or []:
        if t and t != slug and t not in _GENERIC_TAGS and t not in tags:
            tags.append(t)
    return tags


def _rank_tags(per_tag: Dict[str, Dict[str, float]], min_videos: int) -> List[dict]:
    ranked: List[dict] = []
    for tag, vids in per_tag.items():
        if len(vids) < max(1, int(min_videos)):
            continue
        ranked.append({
            "tag": tag,
            "videos": len(vids),
            "mean_retention": round(sum(vids.values()) / len(vids), 2),
        })
    ranked.sort(key=lambda r: (-r["mean_retention"], r["tag"]))
    return ranked


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    vals = sorted(values)
    n = len(vals)
    mid = n // 2
    return round(vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2.0, 2)


def build(manifest: Optional[dict], stats: Optional[dict],
          *, min_videos: int = 3,
          min_videos_kind: int = _BY_KIND_MIN_VIDEOS) -> dict:
    """Compose the retention join. Empty ``shows`` when either side is absent.

    Sep 22 2026: the legacy per-show summary POOLS long-form and Shorts
    (kept, flagged ``pooled: true`` — the dashboard card reads it) and a
    ``by_kind`` block ranks tags WITHIN each kind with ``min_videos_kind``
    distinct videos per tag. Only ``by_kind`` feeds the ranking prior and
    the scene-brief style feedback (engine.gallery_library).
    """
    global _STYLE_BOILERPLATE
    _STYLE_BOILERPLATE = _style_boilerplate()
    payload = {
        "schema_version": 2,
        "generated": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "shows": {},
    }
    if not manifest or not stats:
        return payload

    by_id, by_key = _index_videos(stats)
    if not by_id:
        return payload

    boilerplate_by_show = build_style_tag_index(manifest)
    shows: Dict[str, dict] = {}
    # tag → list of (video_id, retention) per show, deduped by video so a
    # 4-image episode doesn't count its one video 4 times per tag.
    tag_videos: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
        lambda: defaultdict(dict))
    # Per kind: show → kind → tag → {video_id: retention}, and the
    # per-kind video retention list for the kind's median.
    kind_tag_videos: Dict[str, Dict[str, Dict[str, Dict[str, float]]]] = (
        defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
    kind_videos: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(
        lambda: defaultdict(dict))

    for entry in manifest.get("images") or []:
        slug = entry.get("show_slug") or ""
        image_id = entry.get("image_id") or ""
        if not slug or not image_id:
            continue
        kind = _USE_TO_KIND.get(entry.get("intended_use") or "")
        video = by_id.get(entry.get("youtube_video_id") or "")
        if video is None and kind:
            episode = _episode_number(entry.get("episode_id") or "")
            if episode is not None:
                video = by_key.get((slug, episode, kind))
        if video is None:
            continue
        retention = float(video.get("average_view_percentage") or 0.0)
        tags = _style_tags(entry, boilerplate_by_show.get(slug, frozenset()))
        shows.setdefault(slug, {"images": {}, "summary": {}})
        video_kind = str(video.get("kind") or kind or "")
        shows[slug]["images"][image_id] = {
            "video_id": video.get("video_id"),
            "averageViewPercentage": retention,
            "episode_id": entry.get("episode_id") or "",
            "kind": video_kind,
            "tags": tags,
        }
        for tag in tags:
            tag_videos[slug][tag][video["video_id"]] = retention
            if video_kind:
                kind_tag_videos[slug][video_kind][tag][video["video_id"]] = retention
        if video_kind:
            kind_videos[slug][video_kind][video["video_id"]] = retention

    for slug, per_tag in tag_videos.items():
        ranked = _rank_tags(per_tag, min_videos)
        shows[slug]["summary"] = {
            "min_videos": int(min_videos),
            # Long-form and Shorts pooled — the two kinds' baselines
            # differ ~4x, so this ranks the KIND as much as the imagery.
            "pooled": True,
            "top_tags": ranked[:5],
            "bottom_tags": sorted(
                ranked, key=lambda r: (r["mean_retention"], r["tag"])
            )[:5],
        }
        by_kind: Dict[str, dict] = {}
        for video_kind, per_kind_tag in kind_tag_videos.get(slug, {}).items():
            kranked = _rank_tags(per_kind_tag, min_videos_kind)
            by_kind[video_kind] = {
                "min_videos": int(min_videos_kind),
                "videos": len(kind_videos[slug][video_kind]),
                "median_retention": _median(
                    list(kind_videos[slug][video_kind].values())),
                "top_tags": kranked[:5],
                "bottom_tags": sorted(
                    kranked, key=lambda r: (r["mean_retention"], r["tag"])
                )[:5],
            }
        shows[slug]["summary"]["by_kind"] = by_kind

    payload["shows"] = shows
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="site/data/gallery-manifest.json")
    parser.add_argument("--stats", default="api/youtube_stats.json")
    parser.add_argument("--out", default="api/gallery_retention.json")
    parser.add_argument("--min-videos", type=int, default=3,
                        help="Minimum distinct videos behind a tag before "
                             "its mean retention enters the summary")
    parser.add_argument("--min-videos-kind", type=int, default=_BY_KIND_MIN_VIDEOS,
                        help="Minimum distinct videos behind a tag WITHIN one "
                             "kind (long | short) for the by_kind summary")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = build(
        _load_json(_ROOT / args.manifest),
        _load_json(_ROOT / args.stats),
        min_videos=args.min_videos,
        min_videos_kind=args.min_videos_kind,
    )
    n_images = sum(len(s["images"]) for s in payload["shows"].values())
    logger.info("Joined %d gallery images with retention across %d shows",
                n_images, len(payload["shows"]))
    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False)[:4000])
        return 0

    out_path = _ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Wrote %s", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
