#!/usr/bin/env python3
"""Turn YouTube analytics into per-show 'what's working' guidance.

Second half of the recursive YouTube-feedback loop: reads the analytics
``scripts/fetch_youtube_analytics.py`` wrote to ``api/youtube_stats.json``
and distils, per show, the angles/keywords that earned the best *retention*
(average view percentage — the strongest content-quality signal YouTube
exposes) into ``digests/<slug>/youtube_performance.json``.

The title generator (``engine.youtube_titles._performance_hint``) reads that
file and steers future titles toward what's landing. The signal is
TITLE-ONLY (visual metadata, no audio) so it sits outside the landmine #17
A/B-listen gate — the recursive improvement is safe to run automatically.

Clean no-op when ``api/youtube_stats.json`` is missing or empty (the loop is
dormant until the operator re-auths the analytics scope and data accrues).

Usage::

    python scripts/update_youtube_performance.py [--stats api/youtube_stats.json]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("update_youtube_performance")

# Need a few videos before retention numbers mean anything.
_MIN_VIDEOS = 4
# Content words to ignore when mining recurring keywords from titles.
_STOP = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "at", "by", "from", "as", "is", "are", "was", "this", "that",
    "how", "why", "what", "new", "now", "you", "your", "ep", "episode",
    "daily", "show", "could", "will", "can", "vs", "its",
    # Brand / format / calendar noise that was drowning real topics
    # (Tesla hint mined "shorts"/"time"/"july"/"2026" — July 2026 pack).
    "shorts", "short", "time", "podcast", "nerra", "network", "full",
    "watch", "video", "today", "tonight", "week", "month", "year",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "2024", "2025", "2026", "2027",
    # July 31 2026: plain function words that were passing the list and
    # shipping as "topics that retained best" ("while", "just").
    "while", "just", "about", "after", "over", "more", "been", "their",
    "them", "they", "were", "have", "has", "had", "not", "into", "than",
    "when", "where", "which", "there", "here", "some", "most", "also",
})

# Exemplar quality gate (July 31 2026): live performance files were
# quoting FRAGMENT titles ("prove adequate, the architecture could…")
# and DATE titles ("Today is July 16th, 2026") as high-retention
# exemplars — teaching the title generator the exact shapes the July 18
# title bundle exists to eliminate. A title is quotable only when it
# doesn't look like a transcript fragment or a dateline.
_BAD_EXEMPLAR = re.compile(
    r"(?:…|\.\.\.)\s*$"                       # trailing ellipsis = fragment
    r"|(?i:^\s*(?:today is|it's|its)\s)"      # dateline / spoken opener
    # Case-sensitivity is load-bearing on the next branch: a global
    # IGNORECASE made [a-z] match "T" and rejected every title.
    r"|^\s*[a-z]"                             # starts lowercase = mid-sentence
    r"|^\s*\S+\s*,"                           # "word," opener = clause tail
)


def _quotable(title: str) -> bool:
    t = (title or "").strip()
    return bool(t) and not _BAD_EXEMPLAR.search(t)


def _keywords(text: str) -> List[str]:
    toks = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]{2,}", (text or ""))
    return [t for t in toks if t.lower() not in _STOP]


def _build_hint(videos: List[dict], *, channel: str = "en",
                kind: str = "") -> str:
    """Compose a short natural-language steer from the best performers.

    ``channel`` selects EN (@NerraNetwork) or RU (@NerraRU) rows. Mixing
    channels skews the median and can quote the wrong language as exemplars.
    Rows without a ``channel`` field predate the split and count as EN.

    ``kind`` ("long" | "short" | "" for all) scopes the pool. July 31
    2026: the blended pool's "top quartile" was structurally all-Shorts
    (~42% retention vs ~10% long-form), so Shorts exemplars and a
    Shorts-inflated median were steering LONG-FORM titles too. Kinds are
    now mined separately and composed into a labeled hint.
    """
    channel = (channel or "en").lower()
    rated = [
        v for v in videos
        if v.get("average_view_percentage")
        and (v.get("channel") or "en").lower() == channel
        and (not kind or (v.get("kind") or "") == kind)
    ]
    if len(rated) < _MIN_VIDEOS:
        return ""
    # July 18 2026: rank by retention BLENDED with subscribers gained —
    # one subscriber ≈ 5 retention points (subs-gained is a small integer
    # on this channel; the multiplier makes a converting video outrank a
    # merely-watched one without letting a single sub dominate).
    rated.sort(
        key=lambda v: (
            float(v.get("average_view_percentage", 0) or 0)
            + 5.0 * float(v.get("subscribers_gained", 0) or 0)
        ),
        reverse=True,
    )
    top = rated[: max(3, len(rated) // 4)]  # top quartile (min 3)
    median_pct = sorted(v["average_view_percentage"] for v in rated)[len(rated) // 2]

    # Recurring keywords across the high-retention titles + hooks.
    counter: Counter = Counter()
    for v in top:
        for kw in _keywords(v.get("title", "")) + _keywords(v.get("hook", "")):
            counter[kw.lower()] += 1
    common = [w for w, c in counter.most_common(8) if c >= 2]

    parts: List[str] = []
    if common:
        parts.append(
            "Topics/keywords that retained best recently: "
            + ", ".join(common[:8]) + "."
        )
    # Show the operator/LLM 2-3 concrete high-retention titles as
    # exemplars — quotable ones only (no fragments/datelines: quoting a
    # broken title as an exemplar teaches the generator the exact shapes
    # the title bundle exists to eliminate).
    examples = [v["title"] for v in top if _quotable(v.get("title"))][:3]
    if examples:
        parts.append("Highest-retention titles so far: "
                     + " | ".join(f'"{t}"' for t in examples) + ".")
    # Subscriber-converting titles are the strongest possible exemplars.
    converters = [v["title"] for v in rated
                  if float(v.get("subscribers_gained", 0) or 0) > 0
                  and _quotable(v.get("title"))][:2]
    if converters:
        parts.append("Titles that converted subscribers: "
                     + " | ".join(f'"{t}"' for t in converters) + ".")
    parts.append(
        f"Median retention is {median_pct:.0f}% — beat it: keep the promise "
        "concrete and front-load the strongest entity."
    )
    return " ".join(parts)


def _compose_kind_hints(videos: List[dict], *, channel: str = "en") -> str:
    """Labeled per-kind hint: long-form and Shorts mined SEPARATELY.

    Falls back to the blended pool only when neither kind alone clears
    the minimum sample — small channels keep getting a hint, but a show
    with real data never has Shorts retention steering long-form titles
    again.
    """
    hint_long = _build_hint(videos, channel=channel, kind="long")
    hint_short = _build_hint(videos, channel=channel, kind="short")
    parts: List[str] = []
    if hint_long:
        parts.append("LONG-FORM: " + hint_long)
    if hint_short:
        parts.append("SHORTS: " + hint_short)
    if parts:
        return " ".join(parts)
    return _build_hint(videos, channel=channel)


def _show_search_terms(channels_block: Dict[str, dict],
                       videos: List[dict],
                       max_terms: int = 6) -> Dict[str, List[str]]:
    """The live YouTube search queries plausibly aimed at THIS show.

    The Analytics API reports search terms per CHANNEL, but a channel
    carries many shows — so a term is attributed to a show when it
    shares a meaningful token with the show's recent video titles/hooks.
    Deliberately conservative: an unmatched term is dropped rather than
    handed to every show on the channel. These are the literal queries
    already reaching the channel (EN measured 15% of views from search,
    2026-08-17) — the highest-value tag/title input there is.
    """
    import collections as _collections
    import re as _re

    # 2026-08-21 tightening. The original single-shared-token match let
    # (a) pure-numeric tokens attribute terms — "2026" appears in half the
    # catalog, so the Tesla firmware query "tesla update 2026.21.6" landed
    # in FASCINATING FRONTIERS' and ФИНАНСЫ ПРОСТО's tags — and (b) one
    # stray cross-show mention (a single FF hook naming Tesla) hand
    # another show's core entity over as a tag. Off-topic tags are the
    # "misleading metadata" shape YouTube demotes, on every upload, daily.
    def _tokens(text: str) -> set:
        return {t for t in _re.findall(r"[a-zа-яё0-9]+", str(text).lower())
                if len(t) >= 4 and not t.isdigit()}

    # Tesla-firmware-style version strings ("2026.21.6") are queries about
    # a software build, not a show — never a tag. Model-number queries
    # ("gemini 3.7 flash") survive: their version core has no 4-digit lead.
    _VERSIONY = _re.compile(r"\b\d{4}\.\d+(\.\d+)?\b")

    # Per-channel token counts: a term reported for channel X may only
    # match tokens from THIS show's channel-X videos (an RU query must not
    # ride an EN show's tags via its dub titles), and a token counts for
    # the show only when it recurs (>= 2 recent videos) — one stray
    # mention is not this show's subject.
    by_channel_videos: Dict[str, List[dict]] = _collections.defaultdict(list)
    for v in videos:
        by_channel_videos[(v.get("channel") or "en").lower()].append(v)
    per_channel: Dict[str, _collections.Counter] = _collections.defaultdict(
        _collections.Counter)
    for ch, vids in by_channel_videos.items():
        # Recency window PER CHANNEL — a flat videos[-40:] tail can be all
        # dub rows, starving the EN token set entirely.
        for v in vids[-40:]:
            for field in ("title", "hook"):
                per_channel[ch].update(_tokens(v.get(field) or ""))
    if not per_channel:
        return {}
    # Per-channel output: an RU query belongs on RU dub uploads only —
    # the flat list consumed by the EN metadata builders is the "en" key.
    out: Dict[str, List[str]] = {}
    for ch in sorted(per_channel):
        show_tokens = {t for t, n in per_channel[ch].items() if n >= 2}
        if not show_tokens:
            continue
        seen: set = set()
        terms: List[str] = []
        for row in (channels_block.get(ch) or {}).get("search_terms") or []:
            term = str(row.get("term") or "").strip().lower()
            if not term or term in seen or _VERSIONY.search(term):
                continue
            tt = _tokens(term)
            shared = tt & show_tokens
            # One shared common word is not attribution ("flash" put
            # Gemini queries on Fascinating Frontiers): a multi-word term
            # needs two shared tokens; a single-word term must be one of
            # the show's genuinely core tokens (>= 4 recent mentions).
            if len(tt) >= 2:
                ok = len(shared) >= 2
            else:
                ok = bool(tt) and per_channel[ch].get(next(iter(tt)), 0) >= 4
            if ok:
                seen.add(term)
                terms.append(term)
            if len(terms) >= max_terms:
                break
        if terms:
            out[ch] = terms
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", default="api/youtube_stats.json")
    args = parser.parse_args()

    stats_path = ROOT / args.stats
    if not stats_path.exists():
        logger.info("No YouTube stats at %s — nothing to do (clean no-op)",
                    stats_path)
        return 0
    try:
        _stats_doc = json.loads(stats_path.read_text(encoding="utf-8"))
        shows: Dict[str, dict] = _stats_doc.get("shows") or {}
        channels_block: Dict[str, dict] = _stats_doc.get("channels") or {}
    except Exception as exc:
        logger.warning("Could not parse %s: %s — skipping", stats_path, exc)
        return 0

    written = 0
    # Keys are the show output-dir names (e.g. "tesla_shorts_time"), so the
    # perf file lands next to that show's index file.
    for dir_name, payload in shows.items():
        videos = payload.get("videos") or []
        # Channel-generic hints (Aug 2026): the old two-way en/ru pair
        # meant FR rows — collected since the July index-glob fix — were
        # mined into nothing, and every future dub channel would silently
        # read the ENGLISH hint. One hint per channel present in the data.
        channels = sorted({(v.get("channel") or "en").lower()
                           for v in videos if isinstance(v, dict)})
        hints = {ch: _compose_kind_hints(videos, channel=ch)
                 for ch in channels}
        hint_en = hints.get("en", "")
        hint_ru = hints.get("ru", "")
        # Primary title_hint: EN for English shows; RU natives (finansy /
        # privet) often have only @NerraRU rows — fall back so they aren't
        # permanently hint-starved.
        hint = hint_en or hint_ru or next(
            (h for h in hints.values() if h), "")
        if not hint:
            logger.info("%s: too few rated videos (%d) — skipped",
                        dir_name, len(videos))
            continue
        out_dir = ROOT / "digests" / dir_name
        if not out_dir.exists():
            logger.info("%s: no output dir — skipped", dir_name)
            continue
        terms_by_channel = _show_search_terms(channels_block, videos)
        # Flat list = EN terms only: it feeds the EN upload tag builders
        # and the EN title prompt (RU queries were riding EN tags via the
        # dub titles — misleading-metadata shape, 2026-08-21 fix).
        matched_terms = terms_by_channel.get("en") or []
        if matched_terms:
            hint = (hint + "\nLIVE SEARCH QUERIES already reaching this "
                    "channel (fold the phrasing in when honest): "
                    + "; ".join(matched_terms))
        out = {
            "schema_version": 2,
            "generated": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "video_count": len(videos),
            "title_hint": hint,
            "search_terms": matched_terms,
            "search_terms_by_channel": terms_by_channel,
        }
        for ch, h in hints.items():
            out[f"title_hint_{ch}"] = h
        (out_dir / "youtube_performance.json").write_text(
            json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        written += 1
        logger.info("%s: wrote youtube_performance.json (en=%s ru=%s)",
                    dir_name, bool(hint_en), bool(hint_ru))

    logger.info("Updated YouTube performance for %d show(s)", written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
