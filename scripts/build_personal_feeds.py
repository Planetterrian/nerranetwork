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
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.daily_edition import (  # noqa: E402
    EDITIONS,
    Segment,
    discover_segments,
    find_promo_cut,
    load_transcript,
    mira_piece_cmd,
    parse_links_json,
    segment_trim_cmd,
)
from engine.personal_edition import (  # noqa: E402
    MIRA_PERSONAL_DISCLOSURE,
    PERSONAL_R2_PREFIX,
    PersonalSpec,
    build_chapters,
    build_local_brief_prompt,
    build_markets_line,
    build_personal_feed_xml,
    build_personal_links_prompt,
    fallback_personal_links,
    fetch_weather_line,
    needs_research_call,
    parse_local_brief,
    wants_local_brief,
    personal_chapter_pieces,
    personal_episode_title,
    validate_spec,
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
        if target.exists():
            out[slug] = target
            continue
        raw = cache_dir / f"{slug}.raw.mp3"
        try:
            with requests.get(seg.audio_url, stream=True, timeout=600) as resp:
                resp.raise_for_status()
                with raw.open("wb") as fh:
                    for chunk in resp.iter_content(1 << 16):
                        fh.write(chunk)
            cut = None
            if seg.transcript_path:
                transcript = load_transcript(seg.transcript_path)
                hit = find_promo_cut(transcript) if transcript else None
                if hit:
                    cut = hit["raw_seconds"] + seg.music_intro_offset
            _run(segment_trim_cmd(raw, target, cut), f"trim {slug}")
            out[slug] = target
        except Exception as exc:  # noqa: BLE001 — one show never sinks the batch
            logger.warning("segment cache: %s failed (%s) — subscribers "
                           "lose this segment today", slug, exc)
        finally:
            raw.unlink(missing_ok=True)
    return out


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


def _mira_piece(text: str, name: str, workdir: Path) -> Path:
    raw = workdir / f"{name}.raw.mp3"
    out = workdir / f"{name}.mp3"
    _tts(text, raw)
    _run(mira_piece_cmd(raw, out), f"process {name}")
    raw.unlink(missing_ok=True)
    return out


def generate_personal_links(
    spec: PersonalSpec, segments: List[Segment], target_date: dt.date,
) -> dict:
    try:
        from digests.xai_grok import grok_generate_text

        prompt = build_personal_links_prompt(ROOT, spec, segments, target_date)
        text, _meta = grok_generate_text(
            prompt=prompt, model=LINKS_MODEL, temperature=0.7,
            max_tokens=2000, timeout_seconds=600,
        )
        links = parse_links_json(text, max(0, len(segments) - 1))
        if links:
            return links
        logger.warning("%s…: links unusable — fallback", spec.token[:8])
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s…: links failed (%s) — fallback",
                       spec.token[:8], exc)
    return fallback_personal_links(spec, segments, target_date)


def generate_local_brief(spec: PersonalSpec,
                         target_date: dt.date) -> Optional[str]:
    # Gate on the member's add-on toggles (Aug 30 2026): the brief runs
    # only when a location add-on is actually on — and tier is enforced
    # inside effective_addons(), so a base-tier spec can never buy a
    # local brief by writing addons into its record.
    if not wants_local_brief(spec):
        return None
    try:
        weather = ""
        if "weather" in spec.effective_addons():
            weather = fetch_weather_line(spec)
        if not needs_research_call(spec):
            # Weather-only: measured data, no research sections — spoken
            # verbatim, no LLM call to pay for or to hallucinate.
            return weather or None
        from digests.xai_grok import grok_generate_text

        prompt = build_local_brief_prompt(ROOT, spec, target_date, weather)
        text, _meta = grok_generate_text(
            prompt=prompt, model=LINKS_MODEL, temperature=0.6,
            max_tokens=800, timeout_seconds=600, enable_web_search=True,
        )
        return parse_local_brief(text)
    except Exception as exc:  # noqa: BLE001 — the brief never sinks the edition
        logger.info("%s…: local brief failed (%s) — skipped",
                    spec.token[:8], exc)
        return None


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
) -> bool:
    from engine.audio import concatenate_audio

    state_key = f"{PERSONAL_R2_PREFIX}/{spec.token}/episodes.json"
    state = (_r2_get_json(client, state_key) or {}) if client else {}
    episodes: List[dict] = state.get("episodes", [])
    if any(e.get("date") == target_date.isoformat() for e in episodes):
        logger.info("%s…: already built today", spec.token[:8])
        return True

    segments = [segments_by_slug[s] for s in spec.shows
                if s in segments_by_slug and s in cache]
    if len(segments) < 2:
        logger.warning("%s…: only %d segment(s) available — skipped today",
                       spec.token[:8], len(segments))
        return False

    workdir = Path(tempfile.mkdtemp(prefix=f"np_{spec.token[:8]}_"))
    try:
        links = generate_personal_links(spec, segments, target_date)
        local_text = generate_local_brief(spec, target_date)
        markets_text = ""
        if "markets" in spec.effective_addons():
            markets_text = build_markets_line(ROOT)

        durations: Dict[str, float] = {}
        intro = _mira_piece(links["intro"], "intro", workdir)
        durations["intro"] = _duration(intro)
        local_piece = None
        if local_text:
            local_piece = _mira_piece(local_text, "local", workdir)
            durations["local"] = _duration(local_piece)
        markets_piece = None
        if markets_text:
            markets_piece = _mira_piece(markets_text, "markets", workdir)
            durations["markets"] = _duration(markets_piece)
        handoffs = []
        for i, text in enumerate(links["handoffs"], 1):
            piece = _mira_piece(text, f"handoff_{i}", workdir)
            durations[f"handoff_{i}"] = _duration(piece)
            handoffs.append(piece)
        signoff = _mira_piece(
            f"{links['signoff']} {MIRA_PERSONAL_DISCLOSURE}",
            "signoff", workdir)
        durations["signoff"] = _duration(signoff)
        for seg in segments:
            durations[f"seg_{seg.slug}"] = _duration(cache[seg.slug])

        splice: List[Path] = [intro]
        if local_piece:
            splice.append(local_piece)
        if markets_piece:
            splice.append(markets_piece)
        for i, seg in enumerate(segments):
            if i > 0:
                splice.append(handoffs[i - 1])
            splice.append(cache[seg.slug])
        splice.append(signoff)

        # Chapter math mirrors the splice: handoff i leads segment i.
        durations_for_chapters = dict(durations)
        for i in range(1, len(segments)):
            durations_for_chapters[f"handoff_{i}"] = durations.get(
                f"handoff_{i}", 0.0)

        filename = f"Nerra_Personal_{target_date:%Y%m%d}.mp3"
        final = workdir / filename
        concatenate_audio(splice, final)
        total = _duration(final)
        title = personal_episode_title(target_date, segments)
        logger.info("%s…: %0.1f min, %d segments%s", spec.token[:8],
                    total / 60, len(segments),
                    " + local brief" if local_piece else "")
        if dry_run or client is None:
            return True

        episode_num = 1 + max(
            (int(e.get("episode_num", 0)) for e in episodes), default=0)
        row = {
            "episode_num": episode_num,
            "date": target_date.isoformat(),
            "title": title,
            "description": "Your personal Nerra edition: "
                           + ", ".join(s.show_name for s in segments),
            "filename": filename,
            "duration_seconds": round(total, 1),
            "bytes": final.stat().st_size,
        }
        episodes.append(row)
        from engine.personal_edition import prune_episode_state

        episodes, dropped = prune_episode_state(episodes)
        prefix = f"{PERSONAL_R2_PREFIX}/{spec.token}"
        _r2_put(client, f"{prefix}/{filename}", final.read_bytes(),
                "audio/mpeg")
        chapters = build_chapters(
            personal_chapter_pieces(spec, segments, durations_for_chapters),
            title)
        _r2_put(client, f"{prefix}/chapters_{target_date:%Y%m%d}.json",
                json.dumps(chapters).encode("utf-8"), "application/json")
        _r2_put(client, state_key,
                json.dumps({"episodes": episodes}).encode("utf-8"),
                "application/json")
        _r2_put(client, f"{prefix}/feed.rss",
                build_personal_feed_xml(spec, episodes).encode("utf-8"),
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
    args = parser.parse_args()

    if not args.specs and not args.fetch:
        parser.error("one of --specs / --fetch is required")

    target_date = (dt.date.fromisoformat(args.date) if args.date
                   else dt.datetime.now(dt.timezone.utc).date())
    specs = load_specs(args)
    if not specs:
        logger.info("no active subscribers — nothing to do")
        return 0

    all_segments, _missing = discover_segments(
        EDITIONS["en"], ROOT, target_date)
    segments_by_slug = {s.slug: s for s in all_segments}
    needed = sorted({slug for spec in specs for slug in spec.shows})
    cache_root = Path(tempfile.gettempdir()) / f"np_cache_{target_date:%Y%m%d}"
    cache = build_segment_cache(needed, segments_by_slug, cache_root)

    client = None if args.dry_run else _r2_client()
    built = sum(
        1 for spec in specs
        if build_for_spec(spec, target_date, segments_by_slug, cache,
                          client, dry_run=args.dry_run)
    )
    logger.info("built %d/%d personal editions for %s",
                built, len(specs), target_date)
    return 0 if built or not specs else 1


if __name__ == "__main__":
    raise SystemExit(main())
