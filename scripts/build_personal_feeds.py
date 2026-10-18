#!/usr/bin/env python3
"""Assemble every Nerra Personal subscriber's daily edition.

The paid-tier batch job (see ``docs/nerra_personal.md`` for the full
architecture + operator setup). Per run:

1. Pull active subscriber specs — from the Worker's admin endpoint
   (``--fetch``, bearer-auth via ``PERSONAL_ADMIN_TOKEN``) or a local
   JSON file (``--specs``). Specs carry token/shows/tier/name/city,
   never an email.
2. Trim each needed show's published episode ONCE into a shared per-day
   cache (the same promo-cut machinery Nerra Daily uses) — per-user cost
   is Mira's links plus a stream-copy concat, not per-user re-trims.
3. Per subscriber: Mira's personal links (grok-4.3, deterministic
   fallback), the local brief on the local tier (Open-Meteo weather +
   one web-search-grounded call, honest SKIP), TTS, splice, chapters.
4. Upload to R2 ``personal/<token>/`` (feed.rss + MP3 + episodes.json),
   prune past the 7-episode feed depth. Serving is Worker-gated by
   token, so a cancelled subscription loses access immediately.

PII rules: this process handles first names and cities. Run it on a
PRIVATE host (VPS cron or a private repo's Actions) — never in the
public repo's workflows — and it logs tokens truncated to 8 chars, never
names, cities, or spec contents.

Usage::

    python scripts/build_personal_feeds.py --fetch            # production
    python scripts/build_personal_feeds.py --specs specs.json --dry-run
    python scripts/build_personal_feeds.py --fetch --only <token> --replace
        # one subscriber, re-making today (the Worker's on-demand build)

On-demand builds (Sep 17 2026): the Worker dispatches this script for a
single subscriber at activation and from the account page's "Build my
edition now". ``--only`` restricts the run to that feed token;
``--replace`` lets it re-make a date that already exists (the row is
replaced, the new MP3 gets a ``_rN`` suffix so apps re-fetch, the old
file is deleted). Without ``--replace`` an existing date is a no-op,
which is what makes the scheduled sweeps safe to run after a dispatch.

Polish (same day): every segment is loudness-checked against the
network's -16 LUFS and statically corrected when a show drifts; a soft
chime precedes each of Mira's hand-offs; the feed carries the
subscriber's own artwork, timestamped episode notes naming the outlets
each brief credits, and JSON + VTT transcripts.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.access import parse_private_ref  # noqa: E402
from engine.daily_edition import (  # noqa: E402
    EDITIONS,
    Segment,
    discover_segments,
    find_promo_cut,
    load_transcript,
    mira_piece_cmd,
    parse_links_json,
    realign_handoffs,
    segment_trim_cmd,
)
from engine import personal_stories as pstories  # noqa: E402
from engine.personal_edition import (  # noqa: E402
    EditionContext,
    ensure_trim_mentions,
    MIRA_PERSONAL_DISCLOSURE,
    PERSONAL_R2_PREFIX,
    PersonalSpec,
    build_chapters,
    build_local_brief_prompt,
    build_markets_line,
    build_personal_feed_xml,
    build_personal_links_prompt,
    build_topics_prompt,
    brief_max_words,
    chapters_filename_for,
    cover_signature,
    ensure_weather_opener,
    episode_notes,
    fallback_personal_links,
    fetch_weather_line,
    measure_lufs,
    named_sources,
    needs_research_call,
    parse_local_brief,
    render_cover,
    segment_gain_cmd,
    segment_gain_db,
    sting_cmd,
    transcript_entries,
    transcript_filenames_for,
    transcript_json,
    transcript_vtt,
    wants_local_brief,
    personal_chapter_pieces,
    personal_episode_title,
    upgrade_nudge_line,
    validate_spec,
    wants_topics_brief,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s",
                    stream=sys.stdout)
logger = logging.getLogger("nerra_personal")

API_BASE = os.environ.get("PERSONAL_API_BASE", "https://api.nerranetwork.com")
LINKS_MODEL = os.environ.get("NERRA_DAILY_LINKS_MODEL", "grok-4.3")


# ---------------------------------------------------------------------------
# R2 (private personal bucket — read/write via boto3; never public URLs)
# ---------------------------------------------------------------------------

def _r2_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def _bucket() -> str:
    return os.environ.get("PERSONAL_R2_BUCKET", "nerra-personal")


def _r2_get_json(client, key: str) -> Optional[dict]:
    try:
        obj = client.get_object(Bucket=_bucket(), Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except Exception:  # noqa: BLE001 — absent state = first run for this user
        return None


def _r2_put(client, key: str, body: bytes, content_type: str) -> None:
    client.put_object(Bucket=_bucket(), Key=key, Body=body,
                      ContentType=content_type)


def _r2_delete(client, key: str) -> None:
    try:
        client.delete_object(Bucket=_bucket(), Key=key)
    except Exception:  # noqa: BLE001 — prune is best-effort
        logger.debug("prune failed for %s", key)


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------

def load_specs(args) -> List[PersonalSpec]:
    if args.specs:
        raw = json.loads(Path(args.specs).read_text(encoding="utf-8"))
    else:
        import requests

        token = os.environ.get("PERSONAL_ADMIN_TOKEN", "")
        if not token:
            # Raise, don't return []. An empty list flows into main()'s
            # "no active subscribers — nothing to do" and exits 0, so a
            # host that cannot authenticate looks exactly like a healthy
            # idle one — green run, zero output, no subscriber served.
            # The batch repo's first three scheduled runs (2026-08-24 to
            # 08-26) were green that way before the secret was set.
            raise SystemExit(
                "PERSONAL_ADMIN_TOKEN required for --fetch: refusing to "
                "report zero subscribers when the real answer is unknown"
            )
        resp = requests.get(
            f"{API_BASE}/api/admin/personal-specs",
            headers={"Authorization": f"Bearer {token}"}, timeout=60,
        )
        resp.raise_for_status()
        raw = resp.json().get("specs", [])
    specs = [s for s in (validate_spec(r) for r in raw) if s is not None]
    logger.info("specs: %d valid of %d", len(specs), len(raw))
    return specs


# ---------------------------------------------------------------------------
# Shared per-day segment cache
# ---------------------------------------------------------------------------

def build_segment_cache(
    needed: List[str],
    segments_by_slug: Dict[str, Segment],
    cache_dir: Path,
) -> Dict[str, Path]:
    """Download + promo-trim each show once; every subscriber splices the
    same files."""
    import requests

    cache_dir.mkdir(parents=True, exist_ok=True)
    out: Dict[str, Path] = {}
    for slug in needed:
        seg = segments_by_slug.get(slug)
        if seg is None:
            continue
        target = cache_dir / f"{slug}.mp3"
        # The promo cut comes from the committed transcript, so it is known
        # without the audio — and it must be on the segment even when the
        # cached file already exists: the edition's transcript stops there
        # (Oct 18 2026 — it was only ever a local here, so the cues of the
        # trimmed promo tail rode into every personal transcript).
        cut = None
        if seg.transcript_path:
            transcript = load_transcript(seg.transcript_path)
            hit = find_promo_cut(transcript) if transcript else None
            if hit:
                cut = hit["raw_seconds"] + seg.music_intro_offset
        seg.cut_final_seconds = cut
        if target.exists():
            out[slug] = target
            continue
        raw = cache_dir / f"{slug}.raw.mp3"
        try:
            private = parse_private_ref(seg.audio_url)
            if private:
                # A members-only episode has no public address: read it
                # from the private bucket with the builder's R2 credentials.
                bucket, key = private
                _r2_client().download_file(bucket, key, str(raw))
            else:
                with requests.get(seg.audio_url, stream=True, timeout=600) as resp:
                    resp.raise_for_status()
                    with raw.open("wb") as fh:
                        for chunk in resp.iter_content(1 << 16):
                            fh.write(chunk)
            _run(segment_trim_cmd(raw, target, cut), f"trim {slug}")
            _level_segment(slug, target)
            out[slug] = target
        except Exception as exc:  # noqa: BLE001 — one show never sinks the batch
            logger.warning("segment cache: %s failed (%s) — subscribers "
                           "lose this segment today", slug, exc)
        finally:
            raw.unlink(missing_ok=True)
    return out


def _level_segment(slug: str, target: Path) -> None:
    """Bring one cached segment to the network's -16 LUFS if its show
    drifted (static gain + true-peak limiter; see SEGMENT_TARGET_LUFS).
    Measured once per show per day, never per subscriber."""
    measured = measure_lufs(target)
    gain = segment_gain_db(measured)
    if not gain:
        logger.info("segment cache: %s at %s LUFS — in spec", slug,
                    "?" if measured is None else f"{measured:.1f}")
        return
    levelled = target.with_name(f"{slug}.level.mp3")
    try:
        _run(segment_gain_cmd(target, levelled, gain), f"level {slug}")
        levelled.replace(target)
        logger.info("segment cache: %s at %.1f LUFS — corrected %+.1f dB",
                    slug, measured, gain)
    except Exception as exc:  # noqa: BLE001 — the unlevelled segment still airs
        logger.warning("segment cache: %s level failed (%s) — as published",
                       slug, exc)
        levelled.unlink(missing_ok=True)


def ensure_sting(cache_dir: Path) -> Optional[Path]:
    """The transition chime, rendered once per run into the shared cache."""
    path = cache_dir / "sting.mp3"
    if path.exists():
        return path
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        _run(sting_cmd(path), "sting")
        return path
    except Exception as exc:  # noqa: BLE001 — no chime beats no edition
        logger.warning("sting: render failed (%s) — hand-offs without it", exc)
        return None


def _run(cmd: List[str], what: str) -> None:
    import subprocess

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{what} failed: {proc.stderr[-500:]}")


def _duration(path: Path) -> float:
    from engine.audio import get_audio_duration

    return float(get_audio_duration(path) or 0.0)


# ---------------------------------------------------------------------------
# Mira pieces
# ---------------------------------------------------------------------------

def _tts(text: str, dest: Path) -> None:
    from engine.tts import synthesize

    api_key = os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY") or ""
    if not api_key:
        raise RuntimeError("GROK_API_KEY required")
    synthesize(text, EDITIONS["en"].voice_id, dest, api_key=api_key,
               provider="grok", language_code="en")


def _mira_piece(text: str, name: str, workdir: Path,
                lead_in: Optional[Path] = None) -> Path:
    from engine.audio import concatenate_audio

    raw = workdir / f"{name}.raw.mp3"
    out = workdir / f"{name}.mp3"
    _tts(text, raw)
    _run(mira_piece_cmd(raw, out), f"process {name}")
    raw.unlink(missing_ok=True)
    if lead_in is not None:
        # Chime, breath, then Mira — one file so chapter math is unchanged.
        voiced = workdir / f"{name}.voice.mp3"
        out.replace(voiced)
        concatenate_audio([lead_in, voiced], out)
        voiced.unlink(missing_ok=True)
    return out


def generate_personal_links(
    spec: PersonalSpec, segments: List[Segment], target_date: dt.date,
    context: Optional[EditionContext] = None,
) -> dict:
    try:
        from digests.xai_grok import grok_generate_text

        handoff_count = max(0, len(segments) - 1)
        prompt = build_personal_links_prompt(ROOT, spec, segments, target_date,
                                             context)
        text, _meta = grok_generate_text(
            prompt=prompt, model=LINKS_MODEL, temperature=0.7,
            # Same budget as Nerra Daily's links call: a fixed 2,000 cut a
            # long lineup's reply short and sent it to the fallback.
            max_tokens=max(2500, 900 + 140 * handoff_count),
            timeout_seconds=600,
        )
        links = parse_links_json(text, handoff_count)
        if links:
            # Oct 17 2026: the count check passes a draft that skips one show
            # and pads the end, so every later handoff introduces the show
            # before the one that follows (Nerra Daily Ep049/055/057). The
            # repair Nerra Daily runs gives each segment its own handoff.
            links = realign_handoffs(links, segments)
            if links.get("_handoffs_realigned"):
                logger.warning("%s…: %d handoff(s) realigned to their segment",
                               spec.token[:8], links["_handoffs_realigned"])
            return links
        logger.warning("%s…: links unusable — fallback", spec.token[:8])
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s…: links failed (%s) — fallback",
                       spec.token[:8], exc)
    return fallback_personal_links(spec, segments, target_date, context)


def generate_local_brief(spec: PersonalSpec, target_date: dt.date,
                         city: Optional[str] = None) -> Optional[str]:
    """One city's brief (``city`` defaults to the primary)."""
    # Gate on the member's add-on toggles (Aug 30 2026): the brief runs
    # only when a location add-on is actually on — and tier is enforced
    # inside effective_addons(), so a base-tier spec can never buy a
    # local brief by writing addons into its record. Depth and city
    # count are tier-enforced the same way (validate_spec, Sep 13 2026).
    if not wants_local_brief(spec):
        return None
    city = city or spec.city
    try:
        weather = ""
        if "weather" in spec.effective_addons():
            weather = fetch_weather_line(spec, city=city)
        if not needs_research_call(spec):
            # Weather-only: measured data, no research sections — spoken
            # verbatim, no LLM call to pay for or to hallucinate.
            return weather or None
        from digests.xai_grok import grok_generate_text

        prompt = build_local_brief_prompt(ROOT, spec, target_date, weather,
                                          city=city)
        text, _meta = grok_generate_text(
            prompt=prompt, model=LINKS_MODEL, temperature=0.6,
            max_tokens=1200 if spec.depth > 1 else 800,
            timeout_seconds=600, enable_web_search=True,
        )
        brief = parse_local_brief(text, max_words=brief_max_words(spec.depth))
        return ensure_weather_opener(brief, weather)
    except Exception as exc:  # noqa: BLE001 — the brief never sinks the edition
        logger.info("%s…: local brief failed (%s) — skipped",
                    spec.token[:8], exc)
        return None


def generate_local_briefs(spec: PersonalSpec,
                          target_date: dt.date) -> List[Tuple[str, str]]:
    """(city, text) for every city that produced a brief, in the
    member's order. One Grok call per city."""
    out: List[Tuple[str, str]] = []
    for city in spec.cities:
        text = generate_local_brief(spec, target_date, city=city)
        if text:
            out.append((city, text))
    return out


def generate_topics_brief(spec: PersonalSpec,
                          target_date: dt.date) -> Optional[str]:
    """Mira's round-up on the member's own topics (PNN only — topics are
    empty on Personal by validation). One grounded Grok call."""
    if not wants_topics_brief(spec):
        return None
    try:
        from digests.xai_grok import grok_generate_text

        prompt = build_topics_prompt(ROOT, spec, target_date)
        text, _meta = grok_generate_text(
            prompt=prompt, model=LINKS_MODEL, temperature=0.6,
            max_tokens=1200, timeout_seconds=600, enable_web_search=True,
        )
        return parse_local_brief(text, max_words=90 * len(spec.topics) + 60)
    except Exception as exc:  # noqa: BLE001
        logger.info("%s…: topics brief failed (%s) — skipped",
                    spec.token[:8], exc)
        return None


def _transcript_pieces(spec, segments, durations, links, local_texts,
                       topics_text, markets_text, signoff_text, spans=None):
    """Splice order → (speaker, duration, text | None, transcript | None,
    cut) for transcript_entries. Mirrors the splice in build_for_spec.
    *spans* — per slug, the stretches trimmed out of that segment: its
    transcript and its promo-cut point move onto the trimmed timeline."""
    spans = spans or {}
    pieces = [("Mira", durations.get("intro", 0.0), links["intro"], None, None)]
    for i, (_city, text) in enumerate(local_texts, 1):
        pieces.append(("Mira", durations.get(f"local_{i}", 0.0), text, None, None))
    if topics_text:
        pieces.append(("Mira", durations.get("topics", 0.0), topics_text, None, None))
    if markets_text:
        pieces.append(("Mira", durations.get("markets", 0.0), markets_text, None, None))
    for i, seg in enumerate(segments):
        if i > 0:
            pieces.append(("Mira", durations.get(f"handoff_{i}", 0.0),
                           links["handoffs"][i - 1], None, None))
        transcript = load_transcript(seg.transcript_path) if seg.transcript_path else None
        removed = spans.get(seg.slug) or []
        pieces.append((seg.show_name, durations.get(f"seg_{seg.slug}", 0.0),
                       None, pstories.remap_transcript(transcript, removed),
                       pstories.remap_cut_point(seg.cut_final_seconds, removed)))
    pieces.append(("Mira", durations.get("signoff", 0.0), signoff_text, None, None))
    return pieces


def _ensure_cover(client, spec: PersonalSpec, state: dict, prefix: str) -> bool:
    """Upload the subscriber's artwork when it is missing or their name /
    city changed. Returns whether a cover exists for the feed to point at.
    Mutates state["cover_signature"] so the caller persists it."""
    sig = cover_signature(spec)
    if state.get("cover_signature") == sig:
        return True
    out = Path(tempfile.mkdtemp(prefix="np_cover_")) / "cover.jpg"
    try:
        if not render_cover(spec, ROOT / "assets" / "covers" / "nerra-daily.jpg", out):
            return bool(state.get("cover_signature"))
        _r2_put(client, f"{prefix}/cover.jpg", out.read_bytes(), "image/jpeg")
        state["cover_signature"] = sig
        logger.info("%s…: cover rendered", spec.token[:8])
        return True
    except Exception as exc:  # noqa: BLE001
        logger.info("%s…: cover skipped (%s)", spec.token[:8], exc)
        return bool(state.get("cover_signature"))
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)


# ---------------------------------------------------------------------------
# Personalization (Oct 18 2026) — deterministic, no model or search call
# ---------------------------------------------------------------------------

#: Per run, per show: the segment's stories (chapters, headlines, digest
#: units, transcript) and its pauses. Computed once and shared by every
#: member, like the segment cache itself.
_STORIES: Dict[str, "pstories.SegmentStories"] = {}
_SILENCES: Dict[str, List[Tuple[float, float]]] = {}

#: Mira's pieces as the links prompt sizes them (words): intro, each
#: handoff, sign-off + disclosure — the length estimate before TTS.
_MIRA_WORDS = {"intro": 110, "handoff": 45, "signoff": 95}


def _stories_for(seg: Segment, path: Path) -> "pstories.SegmentStories":
    key = f"{seg.slug}:{seg.episode_num}:{path}"
    if key not in _STORIES:
        transcript = load_transcript(seg.transcript_path) if seg.transcript_path else None
        _STORIES[key] = pstories.segment_stories(
            seg, ROOT, cut_seconds=seg.cut_final_seconds,
            duration=_duration(path), transcript=transcript,
            private=bool(parse_private_ref(seg.audio_url)))
    return _STORIES[key]


def _silences_for(slug: str, path: Path) -> List[Tuple[float, float]]:
    key = f"{slug}:{path}"
    if key not in _SILENCES:
        _SILENCES[key] = pstories.detect_cut_silences(path)
    return _SILENCES[key]


def plan_personalization(
    spec: PersonalSpec,
    segments: List[Segment],
    cache: Dict[str, Path],
    past_rows: List[dict],
    target_date: dt.date,
    episode_num: int,
    extra_mira_words: int = 0,
) -> Tuple[EditionContext, List["pstories.Cut"], List["pstories.SegmentStories"]]:
    """Everything personal about today's edition, before any audio is made:
    what this listener already heard, which stories two of their shows both
    tell, what their settings trim, where their own subjects are, and the
    length estimate. Logs counts only — never the profile, a name or a city."""
    stories = [_stories_for(seg, cache[seg.slug]) for seg in segments]
    memory = (pstories.memory_notes(stories, past_rows, target_date)
              if episode_num > 1 else [])
    threads = pstories.week_threads(stories, past_rows, target_date)
    repeats = pstories.cross_repeats(stories)

    cuts: List[pstories.Cut] = []
    refused: Dict[str, int] = {}
    if spec.skip_repeats and repeats:
        silences = {s.slug: _silences_for(s.slug, cache[s.slug]) for s in stories
                    if any(r.later == s.slug for r in repeats)}
        cuts, why = pstories.plan_repeat_cuts(stories, repeats, silences)
        for _r, reason in why:
            refused[reason] = refused.get(reason, 0) + 1
    n = len(segments)
    words = (_MIRA_WORDS["intro"] + _MIRA_WORDS["handoff"] * max(0, n - 1)
             + _MIRA_WORDS["signoff"] + extra_mira_words)
    overhead = pstories.estimate_mira_seconds(words, n + 1)
    content = sum(s.duration for s in stories)
    if spec.target_minutes:
        target = spec.target_minutes * 60.0
        if overhead + content - sum(c.seconds for c in cuts) > target:
            silences = {s.slug: _silences_for(s.slug, cache[s.slug]) for s in stories}
            cuts += pstories.plan_length_cuts(stories, target, overhead, silences,
                                              already=cuts)
    context = EditionContext(
        edition_number=episode_num, memory=memory, week_threads=threads,
        target_minutes=spec.target_minutes,
        weekday=target_date.weekday(), overhead_seconds=overhead,
        repeat_objects=repeats)
    logger.info(
        "%s…: personal — memory %d, threads %d, repeats %d, planned trims %d%s",
        spec.token[:8], len(memory), len(threads), len(repeats), len(cuts),
        (" refused " + ", ".join(f"{k}: {v}" for k, v in sorted(refused.items())))
        if refused else "")
    return context, cuts, stories


def finish_context(context: EditionContext, stories: List["pstories.SegmentStories"],
                   kept: List["pstories.Cut"], spec: Optional[PersonalSpec] = None,
                   spans: Optional[Dict[str, List[Tuple[float, float]]]] = None,
                   ) -> EditionContext:
    """Fill in what depends on the cuts that actually rendered: the trims
    Mira must name, the repeat notes for every retelling still in the
    audio, the interest pointers (never to a trimmed story) and the length
    estimate."""
    by_slug = {s.slug: s for s in stories}
    if spec is not None:
        context.highlights = pstories.interest_highlights(
            stories, spec.topics, spec.profile, spans or {})
        logger.info("%s…: personal — %d trim(s) rendered, %d highlight(s)",
                    spec.token[:8], len(kept), len(context.highlights))
    context.trims = [
        {"slug": c.slug, "show": by_slug[c.slug].show_name, "title": c.title,
         "reason": c.reason, "earlier_show": c.earlier_show,
         "url": by_slug[c.slug].full_episode_url, "seconds": round(c.seconds, 1)}
        for c in kept]
    trimmed = {(c.slug, c.title) for c in kept}
    context.repeats = [
        f'{r.later_show} comes back to "{r.later_text}" — {r.earlier_show} '
        f'told it earlier today ("{r.earlier_text}").'
        for r in context.repeat_objects
        if not (r.chapter is not None and (r.later, r.chapter.title) in trimmed)
    ][:pstories.MAX_REPEAT_NOTES]
    content = sum(s.duration for s in stories) - sum(c.seconds for c in kept)
    context.estimated_minutes = round((context.overhead_seconds + content) / 60.0, 1)
    return context


def apply_cuts(cuts: List["pstories.Cut"], cache: Dict[str, Path],
               stories: List["pstories.SegmentStories"], workdir: Path,
               ) -> Tuple[Dict[str, Path], Dict[str, List[Tuple[float, float]]], List["pstories.Cut"]]:
    """Render each trimmed segment for this member (the shared cached file
    is never touched). A failed render drops that segment's cuts — the
    whole episode airs and nothing claims a trim that did not happen."""
    paths = {slug: p for slug, p in cache.items()}
    spans: Dict[str, List[Tuple[float, float]]] = {}
    kept: List[pstories.Cut] = []
    by_slug = {s.slug: s for s in stories}
    for slug in sorted({c.slug for c in cuts}):
        removed = pstories.removed_spans(cuts, slug)
        out = workdir / f"{slug}.trimmed.mp3"
        dur = by_slug[slug].duration
        try:
            _run(pstories.cut_segment_cmd(cache[slug], out,
                                          pstories.keep_ranges(dur, removed), dur),
                 f"trim repeats {slug}")
        except Exception as exc:  # noqa: BLE001 — the whole episode still airs
            logger.warning("trim render failed for %s (%s) — segment airs whole", slug, exc)
            continue
        paths[slug] = out
        spans[slug] = removed
        kept.extend(c for c in cuts if c.slug == slug)
    return paths, spans, kept


# ---------------------------------------------------------------------------
# Per-subscriber build
# ---------------------------------------------------------------------------

def build_for_spec(
    spec: PersonalSpec,
    target_date: dt.date,
    segments_by_slug: Dict[str, Segment],
    cache: Dict[str, Path],
    client,
    *,
    dry_run: bool,
    replace: bool = False,
    sting: Optional[Path] = None,
) -> bool:
    from engine.audio import concatenate_audio

    state_key = f"{PERSONAL_R2_PREFIX}/{spec.token}/episodes.json"
    state = (_r2_get_json(client, state_key) or {}) if client else {}
    episodes: List[dict] = state.get("episodes", [])
    date_iso = target_date.isoformat()
    previous = [e for e in episodes if e.get("date") == date_iso]
    if previous and not replace:
        logger.info("%s…: already built today", spec.token[:8])
        return True
    # A replaced day keeps its episode number and GUID (no duplicate in
    # the app) but gets a fresh filename so cached audio is re-fetched.
    revision = 1 + max((int(e.get("revision", 0)) for e in previous), default=0)
    if previous:
        episodes = [e for e in episodes if e.get("date") != date_iso]
        logger.info("%s…: replacing today's edition (revision %d)",
                    spec.token[:8], revision)

    segments = [segments_by_slug[s] for s in spec.shows
                if s in segments_by_slug and s in cache]
    if len(segments) < 2:
        logger.warning("%s…: only %d segment(s) available — skipped today",
                       spec.token[:8], len(segments))
        return False

    episode_num = (int(previous[0].get("episode_num", 0)) if previous
                   else 1 + max((int(e.get("episode_num", 0))
                                 for e in episodes), default=0))
    workdir = Path(tempfile.mkdtemp(prefix=f"np_{spec.token[:8]}_"))
    try:
        # The researched pieces come first now (Oct 18 2026): their length
        # feeds the edition's length estimate, and nothing in the links
        # call depends on them.
        local_texts = generate_local_briefs(spec, target_date)
        topics_text = generate_topics_brief(spec, target_date)
        markets_text = ""
        if "markets" in spec.effective_addons():
            markets_text = build_markets_line(ROOT)
        extra_words = sum(len(t.split()) for _c, t in local_texts) + len(
            (topics_text or "").split()) + len(markets_text.split())

        # Personalization — deterministic, no model call: memory, repeats,
        # trims, interests. The audio trims render before the links so a
        # failed render never leaves Mira naming a trim that did not happen.
        context, planned, stories = plan_personalization(
            spec, segments, cache, episodes, target_date, episode_num, extra_words)
        seg_paths, spans, kept = apply_cuts(planned, cache, stories, workdir)
        context = finish_context(context, stories, kept, spec, spans)

        links = generate_personal_links(spec, segments, target_date, context)
        links = ensure_trim_mentions(links, segments, context.trims,
                                     spec.target_minutes)

        durations: Dict[str, float] = {}
        intro = _mira_piece(links["intro"], "intro", workdir)
        durations["intro"] = _duration(intro)
        local_pieces: List[Path] = []
        for i, (_city, text) in enumerate(local_texts, 1):
            piece = _mira_piece(text, f"local_{i}", workdir)
            durations[f"local_{i}"] = _duration(piece)
            local_pieces.append(piece)
        topics_piece = None
        if topics_text:
            topics_piece = _mira_piece(topics_text, "topics", workdir)
            durations["topics"] = _duration(topics_piece)
        markets_piece = None
        if markets_text:
            markets_piece = _mira_piece(markets_text, "markets", workdir)
            durations["markets"] = _duration(markets_piece)
        handoffs = []
        for i, text in enumerate(links["handoffs"], 1):
            piece = _mira_piece(text, f"handoff_{i}", workdir, lead_in=sting)
            durations[f"handoff_{i}"] = _duration(piece)
            handoffs.append(piece)
        nudge = upgrade_nudge_line(spec, target_date, bool(local_pieces))
        signoff_text = " ".join(x for x in (links["signoff"], nudge,
                                            MIRA_PERSONAL_DISCLOSURE) if x)
        signoff = _mira_piece(signoff_text, "signoff", workdir, lead_in=sting)
        durations["signoff"] = _duration(signoff)
        for seg in segments:
            durations[f"seg_{seg.slug}"] = _duration(seg_paths[seg.slug])

        splice: List[Path] = [intro]
        splice.extend(local_pieces)
        if topics_piece:
            splice.append(topics_piece)
        if markets_piece:
            splice.append(markets_piece)
        for i, seg in enumerate(segments):
            if i > 0:
                splice.append(handoffs[i - 1])
            splice.append(seg_paths[seg.slug])
        splice.append(signoff)

        # Chapter math mirrors the splice: handoff i leads segment i; each
        # segment's own chapters after its lead become navigable chapters,
        # on the trimmed timeline.
        durations_for_chapters = dict(durations)
        for i in range(1, len(segments)):
            durations_for_chapters[f"handoff_{i}"] = durations.get(
                f"handoff_{i}", 0.0)
        subchapters = {st.slug: pstories.segment_subchapters(st, spans.get(st.slug, []))
                       for st in stories}

        filename = (f"Nerra_Personal_{target_date:%Y%m%d}"
                    + (f"_r{revision}" if previous else "") + ".mp3")
        final = workdir / filename
        concatenate_audio(splice, final)
        total = _duration(final)
        title = personal_episode_title(target_date, segments)
        logger.info("%s…: %0.1f min%s, %d segments%s%s%s", spec.token[:8],
                    total / 60,
                    f" (asked for {spec.target_minutes})" if spec.target_minutes else "",
                    len(segments),
                    f" + {len(local_pieces)} local brief(s)" if local_pieces else "",
                    " + topics" if topics_piece else "",
                    f", {len(kept)} trim(s) {sum(c.seconds for c in kept):.0f}s" if kept else "")
        if dry_run or client is None:
            keep = os.environ.get("NP_KEEP_DIR")
            if keep:
                # Operator inspection of a dry run: the edition, its
                # chapters and transcripts, nothing uploaded.
                dest = Path(keep) / spec.token[:8]
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copy2(final, dest / filename)
                pieces = personal_chapter_pieces(spec, segments, durations_for_chapters,
                                                 subchapters)
                (dest / "chapters.json").write_text(
                    json.dumps(build_chapters(pieces, title), indent=1))
                cues = transcript_entries(_transcript_pieces(
                    spec, segments, durations, links, local_texts, topics_text,
                    markets_text, signoff_text, spans))
                (dest / "transcript.vtt").write_text(transcript_vtt(cues))
                logger.info("%s…: dry-run artifacts kept in %s", spec.token[:8], dest)
            return True

        chapter_pieces = personal_chapter_pieces(spec, segments,
                                                 durations_for_chapters, subchapters)
        chapters = build_chapters(chapter_pieces, title)
        # Outlets each brief credits by name → the episode notes.
        sources: Dict[str, List[str]] = {}
        for (city, text) in local_texts:
            sources[f"Your {city} brief"] = named_sources(text)
        if topics_text:
            sources["Your topics"] = named_sources(topics_text)
        description, notes_html = episode_notes(
            spec, chapters["chapters"], sources_by_chapter=sources,
            segments=segments, trims=context.trims)
        cues = transcript_entries(_transcript_pieces(
            spec, segments, durations, links, local_texts, topics_text,
            markets_text, signoff_text, spans))
        tr_json_name, tr_vtt_name = transcript_filenames_for(date_iso)
        row = {
            "episode_num": episode_num,
            "date": date_iso,
            "title": title,
            "description": description,
            "notes_html": notes_html,
            "filename": filename,
            "duration_seconds": round(total, 1),
            "bytes": final.stat().st_size,
            "built_at": dt.datetime.now(dt.timezone.utc).isoformat(
                timespec="seconds").replace("+00:00", "Z"),
            "revision": revision if previous else 0,
            "transcripts": [tr_json_name, tr_vtt_name],
            # Edition memory (Oct 18 2026): what this edition carried, so
            # tomorrow's Mira knows what the listener already heard. Public
            # episode text only; capped by engine.personal_stories.
            "contents": pstories.edition_contents(stories),
            "trimmed": [{"slug": t["slug"], "title": t["title"],
                         "reason": t["reason"]} for t in context.trims],
        }
        episodes.append(row)
        from engine.personal_edition import prune_episode_state

        episodes, dropped = prune_episode_state(episodes)
        dropped.extend(str(e.get("filename")) for e in previous
                       if e.get("filename") and e.get("filename") != filename)
        prefix = f"{PERSONAL_R2_PREFIX}/{spec.token}"
        has_cover = _ensure_cover(client, spec, state, prefix)
        _r2_put(client, f"{prefix}/{filename}", final.read_bytes(),
                "audio/mpeg")
        _r2_put(client, f"{prefix}/{chapters_filename_for(date_iso)}",
                json.dumps(chapters).encode("utf-8"), "application/json")
        _r2_put(client, f"{prefix}/{tr_json_name}",
                json.dumps(transcript_json(cues)).encode("utf-8"),
                "application/json")
        _r2_put(client, f"{prefix}/{tr_vtt_name}",
                transcript_vtt(cues).encode("utf-8"), "text/vtt")
        _r2_put(client, state_key,
                json.dumps({"episodes": episodes,
                            "cover_signature": state.get("cover_signature", "")}
                           ).encode("utf-8"),
                "application/json")
        _r2_put(client, f"{prefix}/feed.rss",
                build_personal_feed_xml(spec, episodes, cover=has_cover)
                .encode("utf-8"),
                "application/rss+xml")
        for old in dropped:
            _r2_delete(client, f"{prefix}/{old}")
        return True
    except Exception as exc:  # noqa: BLE001 — one subscriber never sinks the batch
        logger.error("%s…: build failed: %s", spec.token[:8], exc)
        return False
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specs", default="",
                        help="Local JSON file of subscriber specs")
    parser.add_argument("--fetch", action="store_true",
                        help="Fetch specs from the Worker admin endpoint")
    parser.add_argument("--date", default="",
                        help="Edition date YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Assemble but upload nothing")
    parser.add_argument("--only", default="",
                        help="Build one subscriber (feed token) — the "
                             "Worker's on-demand path")
    parser.add_argument("--replace", action="store_true",
                        help="Re-make the date even if it was already built")
    args = parser.parse_args()

    if not args.specs and not args.fetch:
        parser.error("one of --specs / --fetch is required")

    target_date = (dt.date.fromisoformat(args.date) if args.date
                   else dt.datetime.now(dt.timezone.utc).date())
    specs = load_specs(args)
    if args.only:
        specs = [s for s in specs if s.token == args.only.strip().lower()]
        if not specs:
            logger.error("--only: no active subscriber with that token")
            return 1
    if not specs:
        logger.info("no active subscribers — nothing to do")
        return 0

    # Sep 24 2026: the member vocabulary is wider than the Nerra Daily
    # lineup (engine.personal_edition.PERSONAL_EXTRA_SHOW_SLUGS), so the
    # discovery runs on the widened spec; the Daily's own spec is unchanged.
    from engine.personal_edition import personal_edition_spec
    # Oct 13 2026: members-only episodes (engine.access) are discovered too
    # — they exist for exactly these editions.
    all_segments, _missing = discover_segments(
        personal_edition_spec(), ROOT, target_date, include_members=True)
    segments_by_slug = {s.slug: s for s in all_segments}
    needed = sorted({slug for spec in specs for slug in spec.shows})
    cache_root = Path(tempfile.gettempdir()) / f"np_cache_{target_date:%Y%m%d}"
    cache = build_segment_cache(needed, segments_by_slug, cache_root)

    sting = ensure_sting(cache_root)

    client = None if args.dry_run else _r2_client()
    built = sum(
        1 for spec in specs
        if build_for_spec(spec, target_date, segments_by_slug, cache,
                          client, dry_run=args.dry_run,
                          replace=args.replace, sting=sting)
    )
    logger.info("built %d/%d personal editions for %s",
                built, len(specs), target_date)
    return 0 if built or not specs else 1


if __name__ == "__main__":
    raise SystemExit(main())
