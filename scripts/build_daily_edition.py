#!/usr/bin/env python3
"""Assemble and publish one Nerra Daily edition episode.

Splices the day's already-published English episode MP3s (downloaded back
from R2) into a single combined episode with Mira's host links between
them, then publishes it through the network's standard virtual-show
surface (RSS via ``engine.publisher.update_rss_feed``, summaries JSON,
chapters JSON, digest markdown -> blog, ``generate_html`` pages). See
``engine/daily_edition.py`` for the design rules and
``docs/nerra_daily.md`` for the operational contract.

Cost profile per episode: one small Grok call (link writing), a few
thousand characters of Grok TTS for Mira, ffmpeg CPU, one R2 upload.
No show content is regenerated.

Usage (workflow runs the first form):

    python scripts/build_daily_edition.py --edition en --when-ready
    python scripts/build_daily_edition.py --edition en --date 2026-08-21 --force
    python scripts/build_daily_edition.py --edition en --dry-run

Exit codes: 0 = published, already published, or cleanly waiting
(--when-ready); 1 = a real failure.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.daily_edition import (  # noqa: E402
    EditionSpec,
    MIRA_AI_DISCLOSURE,
    Segment,
    aoai_new_episode,
    build_chapters,
    build_digest_md,
    build_edition_metrics,
    build_find_prompt,
    build_links_prompt,
    daily_title,
    edition,
    expected_slugs,
    fallback_links,
    feed_description,
    find_promo_cut,
    load_transcript,
    mira_piece_cmd,
    parse_find_text,
    parse_links_json,
    segment_trim_cmd,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s",
                    stream=sys.stdout)
logger = logging.getLogger("nerra_daily")

#: After this UTC hour the gate stops waiting for missing shows and builds
#: with whatever published (a show that legitimately skipped its day would
#: otherwise hold the edition hostage forever). 12:00 UTC (was 14:00,
#: Aug 2026 "land by 6am Pacific" pass): with the ~30 min build, a
#: force-built edition lands ~12:40 UTC = 5:40am PDT / 4:40am PST — the
#: old 14:00 hour put straggler days at ~8am PT. The trade (a show
#: publishing 12:00-14:00 UTC now misses the edition) is measured by
#: metrics_ep*.json ``missing_expected``; revisit the hour on that data.
#: Punctual force trigger: workers/scheduler dispatches nerra-daily.yml
#: at 12:07 UTC; the 12:23 GitHub sweep is the delayed fallback.
FORCE_BUILD_UTC_HOUR = 12

LINKS_MODEL = os.environ.get("NERRA_DAILY_LINKS_MODEL", "grok-4.3")


def _summaries_path(spec: EditionSpec) -> Path:
    return ROOT / spec.digest_dir / f"summaries_{spec.slug}.json"


def _already_published(spec: EditionSpec, target_date: dt.date) -> bool:
    path = _summaries_path(spec)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        return False
    return any(
        e.get("date") == target_date.isoformat()
        for e in data.get("summaries", [])
        if isinstance(e, dict)
    )


def _append_summary(
    spec: EditionSpec,
    target_date: dt.date,
    content: str,
    episode_num: int,
    episode_title: str,
    audio_url: str,
) -> None:
    """Standard wrapped summaries shape (newest first, 30-entry cap), with
    the entry dated to the EDITION date — that date is the build's
    idempotency key, so it must never drift to a rerun's wall clock (which
    is why this does not reuse ``save_summary_to_github_pages``)."""
    path = _summaries_path(spec)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"podcast": spec.name, "summaries": []}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("summaries"), list):
                data = loaded
        except (OSError, json.JSONDecodeError):
            logger.warning("rewriting unreadable summaries file %s", path)
    data["summaries"].insert(0, {
        "date": target_date.isoformat(),
        "datetime": dt.datetime.now().isoformat(),
        "content": content,
        "episode_num": episode_num,
        "episode_title": episode_title,
        "audio_url": audio_url,
        "rss_url": f"https://nerranetwork.com/{spec.feed_file}",
    })
    data["summaries"] = data["summaries"][:30]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                    encoding="utf-8")


def _annotate(kind: str, message: str) -> None:
    """GitHub Actions annotation. Workflow commands must START the line,
    so this bypasses the logger (whose format prefixes the level name and
    would make GitHub ignore the command) — the backfill_content_lake
    convention."""
    print(f"::{kind}::{message}", flush=True)
    (logger.error if kind == "error" else logger.warning)(message)


def _run(cmd: List[str], what: str) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{what} failed: {proc.stderr[-800:]}")


def _download(url: str, dest: Path) -> None:
    import requests

    with requests.get(url, stream=True, timeout=600) as resp:
        resp.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in resp.iter_content(1 << 16):
                fh.write(chunk)


def _generate_links(
    spec: EditionSpec,
    segments: List[Segment],
    target_date: dt.date,
    aoai_today: Optional[dict],
    tracker: Optional[dict],
    *,
    skip_llm: bool,
) -> tuple:
    """Returns ``(links, source)`` where source is ``"llm"`` or
    ``"fallback"`` — recorded in the edition metrics so a quietly failing
    LLM (every day on announcer lines) is visible, not just logged."""
    handoff_count = max(0, len(segments) - 1)
    if not skip_llm:
        try:
            from digests.xai_grok import grok_generate_text

            prompt = build_links_prompt(spec, ROOT, segments, target_date, aoai_today)
            text, meta = grok_generate_text(
                prompt=prompt, model=LINKS_MODEL, temperature=0.7,
                max_tokens=2500, timeout_seconds=600,
            )
            if tracker is not None:
                usage = (meta or {}).get("usage")
                from engine.tracking import record_llm_usage
                record_llm_usage(
                    tracker, "edition_links_generation",
                    int(getattr(usage, "prompt_tokens", 0) or 0),
                    int(getattr(usage, "completion_tokens", 0) or 0),
                    model=str((meta or {}).get("model") or LINKS_MODEL),
                )
            links = parse_links_json(text, handoff_count)
            if links:
                return links, "llm"
            _annotate("warning", "Nerra Daily link generation returned an "
                                 "unusable shape — using the deterministic fallback")
        except Exception as exc:  # noqa: BLE001 — links must never sink the edition
            _annotate("warning", f"Nerra Daily link generation failed ({exc}) "
                                 "— using the deterministic fallback")
    return fallback_links(spec, segments, target_date), "fallback"


def _generate_daily_find(
    spec: EditionSpec,
    segments: List[Segment],
    target_date: dt.date,
    tracker: Optional[dict],
) -> Optional[str]:
    """Mira's field note: one web-search-grounded item of her own for the
    episode midpoint. Best-effort — None (skip the segment) on any
    failure or an honest SKIP from the model; never fabricated filler."""
    if not spec.daily_find or not spec.find_prompt_file:
        return None
    try:
        from digests.xai_grok import drain_search_usage, grok_generate_text

        prompt = build_find_prompt(spec, ROOT, segments, target_date)
        text, meta = grok_generate_text(
            prompt=prompt, model=LINKS_MODEL, temperature=0.7,
            max_tokens=900, timeout_seconds=600, enable_web_search=True,
        )
        if tracker is not None:
            from engine.tracking import record_llm_usage, record_search_usage

            usage = (meta or {}).get("usage")
            record_llm_usage(
                tracker, "edition_find_generation",
                int(getattr(usage, "prompt_tokens", 0) or 0),
                int(getattr(usage, "completion_tokens", 0) or 0),
                model=str((meta or {}).get("model") or LINKS_MODEL),
            )
            search = drain_search_usage()
            if search.get("calls"):
                record_search_usage(
                    tracker,
                    calls=search.get("calls", 0),
                    sources=search.get("sources", 0),
                    prompt_tokens=search.get("input_tokens", 0),
                    completion_tokens=search.get("output_tokens", 0),
                    model=LINKS_MODEL,
                )
        find_text = parse_find_text(text)
        if find_text is None:
            logger.info("field note skipped today (model returned SKIP or "
                        "an unusable shape)")
        return find_text
    except Exception as exc:  # noqa: BLE001 — the field note never sinks the edition
        logger.warning("field-note generation failed (%s) — segment skipped", exc)
        return None


def _tts_mira(spec: EditionSpec, text: str, dest: Path, tracker: Optional[dict]) -> Path:
    from engine.tts import synthesize

    api_key = os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY") or ""
    if not api_key:
        raise RuntimeError("GROK_API_KEY / XAI_API_KEY required for Mira TTS")
    # Positional (text, voice_id, output_path) — voice_id as kwarg TypeErrors.
    synthesize(text, spec.voice_id, dest, api_key=api_key,
               provider="grok", language_code=spec.language)
    if tracker is not None:
        from engine.tracking import record_tts_usage
        record_tts_usage(tracker, len(text), provider="grok")
    return dest


def build_edition(
    spec: EditionSpec,
    target_date: dt.date,
    *,
    skip_llm: bool = False,
    dry_run: bool = False,
) -> int:
    from engine.audio import concatenate_audio, get_audio_duration
    from engine.daily_edition import discover_lineup
    from engine.publisher import (
        apply_op3_prefix,
        get_next_episode_number,
        update_rss_feed,
    )
    from engine.titles import clip_words
    from engine.tracking import create_tracker, save_usage

    lineup = discover_lineup(spec, ROOT, target_date)
    segments, missing, skipped = lineup.segments, lineup.missing, lineup.skipped
    if skipped:
        logger.info("building without show(s) that skipped today: %s",
                    ", ".join(f"{s['slug']} ({s['reason']})" for s in skipped))
    if missing:
        # Loud: an expected show absent at build time means the published
        # edition is INCOMPLETE for the day even though the build succeeds
        # (Offshore North published 17:04 on 2026-08-24, after the 15:07
        # force-build — the Monday edition shipped without it). The
        # annotation + the metrics record make the miss countable.
        _annotate("warning",
                  f"building the {target_date} edition WITHOUT expected "
                  f"show(s): {', '.join(missing)} — they had not published "
                  "at build time")
    if len(segments) < spec.min_segments:
        _annotate("error",
                  f"only {len(segments)} segment(s) available for "
                  f"{target_date} — refusing to publish below the "
                  f"{spec.min_segments}-segment floor")
        return 1
    logger.info("lineup today (%d segments): %s", len(segments),
                ", ".join(s.slug for s in segments))

    digest_dir = ROOT / spec.digest_dir
    digest_dir.mkdir(parents=True, exist_ok=True)
    feed_path = ROOT / spec.feed_file
    episode_num = get_next_episode_number(feed_path, digest_dir)
    aoai_today = aoai_new_episode(ROOT, target_date)
    tracker = create_tracker(spec.name, episode_num)

    workdir = Path(tempfile.mkdtemp(prefix=f"{spec.slug}_"))
    try:
        # --- Segments FIRST (before any LLM/TTS spend): download, locate
        # the promo cut, trim + re-encode. A failing segment (404 on a
        # fallback audio_url after an R2 upload failure, a transient CDN
        # error) is DROPPED loudly rather than sinking the whole edition —
        # Mira's links are written afterward against the survivors, so the
        # rundown she speaks always matches what actually spliced.
        pieces: List[Path] = []
        chapter_pieces: List[tuple] = []
        survivors: List[Segment] = []
        dropped: List[str] = []
        for seg in segments:
            raw = workdir / f"raw_{seg.slug}.mp3"
            trimmed = workdir / f"seg_{seg.slug}.mp3"
            try:
                _download(seg.audio_url, raw)
                cut_final = None
                if seg.transcript_path:
                    transcript = load_transcript(seg.transcript_path)
                    hit = find_promo_cut(transcript) if transcript else None
                    if hit:
                        cut_final = hit["raw_seconds"] + seg.music_intro_offset
                        seg.cut_kind = hit["kind"]
                if cut_final is None:
                    logger.warning("no promo cut found for %s Ep%s — segment "
                                   "ships whole (plug included)",
                                   seg.slug, seg.episode_num)
                _run(segment_trim_cmd(raw, trimmed, cut_final),
                     f"trim/encode {seg.slug}")
            except Exception as exc:  # noqa: BLE001 — one segment never sinks the day
                _annotate("warning",
                          f"segment {seg.slug} Ep{seg.episode_num} dropped "
                          f"from the edition: {exc}")
                dropped.append(seg.slug)
                continue
            finally:
                raw.unlink(missing_ok=True)
            seg.cut_final_seconds = cut_final
            seg.duration_seconds = get_audio_duration(trimmed) or 0.0
            survivors.append(seg)
            pieces.append(trimmed)

        segments = survivors
        if len(segments) < spec.min_segments:
            _annotate("error",
                      f"only {len(segments)} segment(s) assembled for "
                      f"{target_date} — below the {spec.min_segments}-segment "
                      "floor; not publishing")
            return 1

        links, links_source = _generate_links(spec, segments, target_date,
                                              aoai_today, tracker,
                                              skip_llm=skip_llm)

        # --- Mira's links: TTS + normalize to the segment format.
        def mira(name: str, text: str) -> Path:
            raw = workdir / f"mira_{name}_raw.mp3"
            out = workdir / f"mira_{name}.mp3"
            try:
                _tts_mira(spec, text, raw, tracker)
            except RuntimeError:
                if not dry_run:
                    raise
                # Dry runs without credentials still validate the full
                # splice: stand in 2 s of near-silence per link (pure
                # digital silence makes loudnorm/lame degenerate).
                _run(["ffmpeg", "-y", "-f", "lavfi",
                      "-i", "anoisesrc=r=44100:c=pink:a=0.005", "-t", "2",
                      "-ac", "2", "-c:a", "libmp3lame", "-q:a", "2", str(raw)],
                     f"placeholder noise {name}")
            _run(mira_piece_cmd(raw, out), f"process mira {name}")
            raw.unlink(missing_ok=True)
            return out

        intro_piece = mira("intro", links["intro"])
        handoff_pieces = [
            mira(f"handoff_{i}", text)
            for i, text in enumerate(links["handoffs"], 1)
        ]
        signoff_piece = mira(
            "signoff", f"{links['signoff']} {MIRA_AI_DISCLOSURE}")

        # Mira's field note — her own web-grounded discovery, spoken at
        # the episode midpoint under its own chapter (skipped cleanly on
        # any failure).
        find_text = None if skip_llm else _generate_daily_find(
            spec, segments, target_date, tracker)
        find_piece = mira("find", find_text) if find_text else None
        find_before = max(1, len(segments) // 2) if find_piece else None

        # --- Splice order: intro, seg1, handoff1, seg2, ... segN, signoff,
        # with the field note between the two segments at the midpoint.
        # Chapters: each show's chapter opens on the handoff that introduces
        # it, so skipping to a chapter always lands on Mira setting it up.
        splice: List[Path] = [intro_piece]
        chapter_pieces.append((
            f"Welcome from {spec.host}",
            get_audio_duration(intro_piece) or 0.0,
        ))
        for i, seg in enumerate(segments):
            if find_before == i:
                splice.append(find_piece)
                chapter_pieces.append((
                    f"{spec.host}'s field note",
                    get_audio_duration(find_piece) or 0.0,
                ))
            lead = 0.0
            if i > 0:
                handoff = handoff_pieces[i - 1]
                splice.append(handoff)
                lead = get_audio_duration(handoff) or 0.0
            splice.append(pieces[i])
            chapter_pieces.append((
                clip_words(f"{seg.show_name} — {seg.hook or seg.episode_title}", 100),
                lead + (seg.duration_seconds or 0.0),
            ))
        splice.append(signoff_piece)
        chapter_pieces.append(
            ("Sign-off", get_audio_duration(signoff_piece) or 0.0))

        mp3_name = f"{spec.episode_prefix}_Ep{episode_num:03d}_{target_date:%Y%m%d}.mp3"
        final_mp3 = workdir / mp3_name
        concatenate_audio(splice, final_mp3)
        duration = get_audio_duration(final_mp3) or 0.0
        title = daily_title(episode_num, target_date, segments,
                            links.get("title", ""))
        chapters = build_chapters(chapter_pieces, title)
        logger.info("assembled %s: %.1f min, %d segments, title=%r",
                    mp3_name, duration / 60, len(segments), title)

        if dry_run:
            plan = {
                "episode_num": episode_num,
                "title": title,
                "duration_seconds": round(duration, 1),
                "segments": [
                    {"slug": s.slug, "episode": s.episode_num,
                     "cut_final_seconds": s.cut_final_seconds,
                     "cut_kind": s.cut_kind or "none",
                     "duration_seconds": round(s.duration_seconds or 0, 1)}
                    for s in segments
                ],
                "links": links,
                "links_source": links_source,
                "field_note": find_text,
                "show_notes": feed_description(spec, segments, target_date,
                                               chapters, find_text),
            }
            print(json.dumps(plan, indent=2, ensure_ascii=False))
            return 0

        # --- Publish: R2 -> feed -> chapters -> summaries -> digest/blog.
        from engine.storage import upload_to_r2

        r2_url = upload_to_r2(
            final_mp3, f"{spec.r2_prefix}/{mp3_name}",
            bucket=os.environ.get("R2_BUCKET", "podcast-audio"),
            endpoint_url=os.environ["R2_ENDPOINT_URL"],
            access_key=os.environ["R2_ACCESS_KEY_ID"],
            secret_key=os.environ["R2_SECRET_ACCESS_KEY"],
            public_base_url=os.environ.get(
                "R2_PUBLIC_BASE_URL", "https://audio.nerranetwork.com"),
            content_type="audio/mpeg",
        )

        chapters_path = digest_dir / f"chapters_ep{episode_num:03d}.json"
        chapters_path.write_text(
            json.dumps(chapters, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")

        digest_md = build_digest_md(
            spec, ROOT, episode_num, target_date, segments, links, aoai_today,
            find_text=find_text)
        md_path = digest_dir / f"{spec.episode_prefix}_Ep{episode_num:03d}_{target_date:%Y%m%d}.md"
        md_path.write_text(digest_md, encoding="utf-8")

        update_rss_feed(
            feed_path, episode_num, title,
            # Show notes carry every chapter's start time (apps linkify
            # H:MM:SS) and Mira's field note in full — Sep 3 2026 review.
            feed_description(spec, segments, target_date, chapters, find_text),
            target_date, mp3_name, duration, final_mp3,
            audio_url=apply_op3_prefix(r2_url),
            audio_subdir=spec.digest_dir,
            channel_title=spec.name,
            channel_link=f"https://nerranetwork.com/{spec.show_page}",
            channel_description=spec.channel_description,
            channel_language="en-us" if spec.language == "en" else spec.language,
            channel_author="Nerra Network",
            channel_email="patrick@planetterrian.com",
            channel_image=spec.cover_url,
            channel_category=spec.channel_category,
            channel_subcategory=spec.channel_subcategory,
            channel_keywords=spec.channel_keywords,
            guid_prefix=spec.guid_prefix,
            chapters_url=f"https://nerranetwork.com/{spec.digest_dir}/{chapters_path.name}",
            funding_url="https://nerranetwork.com/support.html",
            funding_label="Support the Nerra Network",
            # Mira is the host in Podcasting 2.0 apps' credits/discovery
            # (podcast:person) — the channel carried funding but no host.
            person_name=spec.host,
            person_url="https://nerranetwork.com/age-of-ai.html",
            person_img=spec.cover_url,
        )

        _append_summary(spec, target_date, digest_md, episode_num, title, r2_url)
        save_usage(tracker, digest_dir)

        metrics = build_edition_metrics(
            episode_num, target_date, duration, segments,
            links_source=links_source,
            field_note_included=bool(find_text),
            missing_expected=missing,
            dropped=dropped,
            links=links,
            skipped_today=skipped,
        )
        (digest_dir / f"metrics_ep{episode_num:03d}.json").write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")

        # Show page + summaries page + blog post for the day.
        proc = subprocess.run(
            [sys.executable, "generate_html.py", "--show", spec.slug, "--blogs"],
            cwd=ROOT, capture_output=True, text=True, timeout=900)
        if proc.returncode != 0:
            _annotate("warning", "page regeneration failed (episode is "
                                 "published; nightly will repair): "
                                 + proc.stderr[-500:])

        logger.info("published %s Ep%d (%s) -> %s",
                    spec.name, episode_num, title, r2_url)
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", default="en")
    parser.add_argument("--date", default="",
                        help="Edition date YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--when-ready", action="store_true",
                        help="Gate mode: exit 0 quietly unless every expected "
                             "show has published (or the force hour passed)")
    parser.add_argument("--force", action="store_true",
                        help="Build now with whatever segments exist")
    parser.add_argument("--skip-llm", action="store_true",
                        help="Use the deterministic fallback links (no Grok call)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Assemble locally and print the plan; publish nothing")
    args = parser.parse_args()

    spec = edition(args.edition)
    target_date = (dt.date.fromisoformat(args.date) if args.date
                   else dt.datetime.now(dt.timezone.utc).date())

    if _already_published(spec, target_date) and not args.dry_run:
        logger.info("%s already published for %s — nothing to do",
                    spec.name, target_date)
        return 0

    if args.when_ready and not args.force:
        from engine.daily_edition import discover_lineup

        # A show with a committed .skip_<date>.json is NOT in ``missing``:
        # it has told the network it will not publish, so the gate builds
        # without it instead of holding every listener to the force hour
        # (UC's claims-gate block on 2026-09-03 cost the edition four hours).
        lineup = discover_lineup(spec, ROOT, target_date)
        segments, missing = lineup.segments, lineup.missing
        if lineup.skipped:
            logger.info("not waiting for skipped show(s): %s",
                        ", ".join(s["slug"] for s in lineup.skipped))
        now_utc = dt.datetime.now(dt.timezone.utc)
        past_force_hour = (target_date < now_utc.date()
                           or now_utc.hour >= FORCE_BUILD_UTC_HOUR)
        if missing and not past_force_hour:
            logger.info("waiting: %d/%d expected shows published (missing: %s)",
                        len(segments), len(expected_slugs(spec, target_date)),
                        ", ".join(missing))
            return 0
        if len(segments) < spec.min_segments and not past_force_hour:
            logger.info("waiting: only %d segment(s) so far", len(segments))
            return 0

    return build_edition(spec, target_date,
                         skip_llm=args.skip_llm, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
