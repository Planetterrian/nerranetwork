#!/usr/bin/env python3
"""Re-synthesize a PUBLISHED episode's audio from its committed script.

The repair path for the Tesla Ep605 class of defect (2026-09-14): the
text we sent was correct, the audio was not. Grok TTS read its own
server-side text-normalizer's reasoning aloud for the first 45 seconds
in place of the hook and the identity line. The committed ``_tts.txt``
was clean, so the episode's content was never lost — only its audio.

Editing such an episode does not work, because the leak REPLACED
content rather than adding it: cutting it leaves the episode opening
mid-sentence with no hook and no show name. Re-running the same text
through the same synthesis is the only repair that yields a correct
episode, and the marginal cost is one TTS call.

What this does, in order:

1. Resolves the episode's committed artifacts (script, digest) by show
   and episode number.
2. Reads the CURRENT committed transcript through the spoken-text gate
   and reports it, so the operator sees the "before" reading.
3. Synthesizes the committed script through the exact call
   ``run_show`` makes (same voice, wrap, normalization, chunk budget).
4. Transcribes the new audio and runs the spoken-text gate on it. A
   failure retries synthesis once; a second failure ABORTS. **This tool
   can never publish audio it has not verified** — that is the whole
   point of it existing.
5. Mixes with the show's music, checks the minimum-duration floor,
   recomputes chapters from the committed script, and rewrites the
   transcript files (the committed ones describe the bad audio).
6. Uploads to the SAME R2 key, so the podcast enclosure URL does not
   change and no subscriber is re-pointed.
7. Replaces the episode's RSS item in place, preserving its published
   title and description and correcting only duration and byte length.

Dry run by default. ``--apply`` is required for any write, upload or
feed edit.

Usage:
    python scripts/resynthesize_episode.py --show tesla --episode 605
    python scripts/resynthesize_episode.py --show tesla --episode 605 --apply

Run it from Actions ("Re-synthesize Episode"), not a laptop: the Grok
and R2 credentials live there.

**What this tool deliberately does NOT do.** YouTube cannot replace a
video's file, so a repaired episode's videos must be deleted and
re-uploaded by hand; the Apple video feed's MP4 and any Nerra Daily
edition that spliced the episode carry the old audio too. The run
prints exactly which of those exist for the episode so none is missed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger("resynthesize")

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


# ---------------------------------------------------------------------------
# Artifact resolution
# ---------------------------------------------------------------------------

@dataclass
class EpisodeArtifacts:
    """Every committed path a repair touches, resolved from one episode."""

    slug: str
    episode_num: int
    date_str: str            # YYYYMMDD
    prefix: str              # e.g. Tesla_Shorts_Time_Pod_Ep605_20260914
    digests_dir: Path
    script_path: Path        # *_tts.txt — the text that WAS sent to TTS
    digest_path: Path        # *.md — supplies chapter story headlines
    raw_mp3: Path
    final_mp3: Path
    chapters_path: Path
    transcript_txt: Path
    transcript_json: Path

    @property
    def r2_key(self) -> str:
        """The object key ``engine.storage.upload_episode`` will write.

        Kept as a property so the same-key invariant is assertable and
        testable without performing an upload. Changing an R2 audio key
        breaks every existing subscriber (CLAUDE.md, RSS Feeds).
        """
        return f"{self.slug}/{self.final_mp3.name}"


def resolve_artifacts(config, episode_num: int,
                      date_str: Optional[str] = None) -> EpisodeArtifacts:
    """Locate a published episode's committed artifacts.

    ``date_str`` (YYYYMMDD) disambiguates the rare case of two episodes
    sharing a number; normally it is discovered from the script file.
    """
    digests_dir = ROOT / config.episode.output_dir
    pattern = f"{config.episode.prefix}_Ep{episode_num:03d}_"
    suffix = f"{date_str}_tts.txt" if date_str else "*_tts.txt"
    matches = sorted(digests_dir.glob(pattern + suffix))
    if not matches:
        raise FileNotFoundError(
            f"No committed script for {config.slug} Ep{episode_num} at "
            f"{digests_dir}/{pattern}{suffix}. The repair needs the text "
            "that was sent to TTS; without it there is nothing to re-run."
        )
    if len(matches) > 1:
        raise ValueError(
            f"{len(matches)} scripts match Ep{episode_num}: "
            f"{[m.name for m in matches]}. Pass --date YYYYMMDD."
        )

    script_path = matches[0]
    prefix = script_path.name[: -len("_tts.txt")]
    found_date = re.search(r"_(\d{8})$", prefix)
    resolved_date = found_date.group(1) if found_date else (date_str or "")

    return EpisodeArtifacts(
        slug=config.slug,
        episode_num=episode_num,
        date_str=resolved_date,
        prefix=prefix,
        digests_dir=digests_dir,
        script_path=script_path,
        digest_path=digests_dir / f"{prefix}.md",
        raw_mp3=digests_dir / f"{prefix}_raw.mp3",
        final_mp3=digests_dir / f"{prefix}.mp3",
        chapters_path=digests_dir / f"chapters_ep{episode_num:03d}.json",
        transcript_txt=digests_dir / f"{prefix}_transcript.txt",
        transcript_json=digests_dir / f"{prefix}_transcript.json",
    )


# ---------------------------------------------------------------------------
# Synthesis + verification
# ---------------------------------------------------------------------------

def synthesize_script(config, script: str, out_mp3: Path, api_key: str) -> None:
    """Synthesize *script* exactly as ``run_show`` does.

    Single-voice and two-host dialogue are both supported. Section-TTS
    is refused rather than approximated: it is off network-wide, and
    silently synthesizing a section-TTS show down the single-call path
    would ship audio that differs from its siblings (landmine #17).
    """
    if getattr(config.tts, "use_section_tts", False):
        raise NotImplementedError(
            f"{config.slug} has tts.use_section_tts enabled. This tool "
            "re-synthesizes via the single-call path only; repairing a "
            "section-TTS show would change its sound. Extend the tool "
            "before using it here."
        )

    provider = (config.tts.provider or "grok").lower()

    if config.tts.dialogue_mode and provider == "grok":
        from engine.tts_dialogue import parse_dialogue_turns, synthesize_dialogue
        voices = config.tts.dialogue_voices or {}
        if not parse_dialogue_turns(script, voices):
            raise ValueError(
                f"{config.slug} is a dialogue show but the committed script "
                f"carries no {sorted(voices)} speaker labels. Repairing it "
                "single-voice would change who speaks; aborting."
            )
        synthesize_dialogue(
            script, voices, out_mp3,
            api_key=api_key,
            max_chars=config.tts.max_chars,
            language_code=config.tts.language_code,
            pause_ms=config.tts.dialogue_pause_ms,
            speed=getattr(config.tts, "speed", 1.0) or 1.0,
        )
        return

    from engine.tts import synthesize
    synthesize(
        script, config.tts.voice_id, out_mp3,
        api_key=api_key, provider=provider,
        max_chars=config.tts.max_chars,
        model_id=config.tts.model,
        stability=config.tts.stability,
        similarity_boost=config.tts.similarity_boost,
        style=config.tts.style,
        language_code=config.tts.language_code,
        speed=config.tts.speed,
        apply_text_normalization=config.tts.apply_text_normalization,
        speech_wrap_open=config.tts.speech_wrap_open,
        speech_wrap_close=config.tts.speech_wrap_close,
    )


def transcribe(config, art: EpisodeArtifacts, audio: Path, out_dir: Path):
    """Whisper transcript of *audio*, written under *out_dir*."""
    from engine.transcripts import generate_transcript
    lang = "ru" if config.slug in ("finansy_prosto", "privet_russian") else "en"
    return generate_transcript(
        audio, out_dir, art.prefix,
        model_size=config.tts.whisper_model, language=lang,
        vocabulary=[config.name, *config.keywords],
    )


def gate_report(config, script: str, transcript_result):
    """Run the spoken-text gate on a fresh transcript."""
    from engine.spoken_text_gate import check_transcript_files
    return check_transcript_files(
        script,
        transcript_result.json_path,
        transcript_result.txt_path,
        min_opening_match=float(getattr(
            config.tts, "spoken_text_gate_min_opening_match", 0.5)),
        max_unmatched_run=int(getattr(
            config.tts, "spoken_text_gate_max_unmatched_run", 40)),
    )


def read_committed_gate(config, art: EpisodeArtifacts):
    """The gate's reading of the CURRENTLY published audio.

    This is the "before" number: it is what makes the repair's effect
    legible in the run log, and it is how an operator confirms they are
    repairing the episode they meant to.
    """
    if not art.transcript_json.exists() and not art.transcript_txt.exists():
        return None
    from engine.spoken_text_gate import check_transcript_files
    return check_transcript_files(
        art.script_path.read_text(encoding="utf-8"),
        art.transcript_json,
        art.transcript_txt,
    )


# ---------------------------------------------------------------------------
# Mix + chapters
# ---------------------------------------------------------------------------

def mix_episode(config, raw_mp3: Path, final_mp3: Path) -> float:
    """Mix voice with the show's music exactly as ``run_show`` does."""
    from engine.audio import get_audio_duration, mix_with_music, normalize_voice

    music_path = ROOT / config.audio.music_file if config.audio.music_file else None
    if music_path and music_path.exists():
        bg = (ROOT / config.audio.background_music_file
              if config.audio.background_music_file else None)
        mix_with_music(
            raw_mp3, music_path, final_mp3,
            intro_duration=int(config.audio.intro_duration),
            overlap_duration=int(config.audio.overlap_duration),
            fade_duration=int(config.audio.fade_duration),
            outro_duration=int(config.audio.outro_duration),
            intro_volume=config.audio.intro_volume,
            overlap_volume=config.audio.overlap_volume,
            fade_volume=config.audio.fade_volume,
            outro_volume=config.audio.outro_volume,
            voice_intro_delay=config.audio.voice_intro_delay,
            background_music_path=bg,
            outro_crossfade=config.audio.outro_crossfade,
            outro_fade_out_duration=getattr(
                config.audio, "outro_fade_out_duration", 6.0),
            denoise=config.audio.voice_denoise,
        )
    else:
        if music_path:
            logger.warning("Music file not found: %s — voice only", music_path)
        normalize_voice(raw_mp3, final_mp3, denoise=config.audio.voice_denoise)

    return get_audio_duration(final_mp3) or 0.0


def rebuild_chapters(config, art: EpisodeArtifacts, script: str,
                     audio_duration: float) -> Optional[List]:
    """Recompute chapter timestamps against the repaired audio.

    Titles come from the same committed script and digest the published
    ones did, so they reproduce exactly; only the timings move with the
    new duration. Verified against Ep605's published chapters.
    """
    if not (config.chapters.enabled and config.chapters.section_markers):
        return None
    from engine.chapters import calculate_timestamps, parse_chapters

    headlines: List[str] = []
    if art.digest_path.exists():
        try:
            from engine.grok_imagine import extract_story_headlines
            headlines = extract_story_headlines(
                art.digest_path.read_text(encoding="utf-8"), max_count=12)
        except Exception as exc:  # noqa: BLE001 — headlines are best-effort
            logger.warning("Story-headline extraction failed: %s", exc)

    chapters = parse_chapters(
        script, config.chapters.section_markers,
        show_name=config.name, story_headlines=headlines,
        known_sections_only=getattr(config.chapters, "known_sections_only", False),
    )
    if not chapters or audio_duration <= 0:
        return None
    offset = config.audio.voice_intro_delay + config.audio.intro_duration
    calculate_timestamps(chapters, audio_duration, music_intro_offset=offset)
    return chapters


def published_chapter_titles(path: Path) -> List[str]:
    """Chapter titles as currently committed (for a drift comparison)."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = data.get("chapters") if isinstance(data, dict) else data
    return [c.get("title", "") for c in items] if isinstance(items, list) else []


# ---------------------------------------------------------------------------
# RSS
# ---------------------------------------------------------------------------

def read_published_item(rss_path: Path, episode_num: int) -> Optional[dict]:
    """Title and description of the episode's existing feed item.

    A repair corrects duration and byte length. Everything a listener
    reads was right the whole time, so it is carried over verbatim
    rather than regenerated.
    """
    if not rss_path.exists():
        return None
    try:
        root = ET.parse(rss_path).getroot()
    except ET.ParseError as exc:
        logger.warning("Could not parse %s: %s", rss_path.name, exc)
        return None
    for item in root.iter("item"):
        num = item.find(f"{{{ITUNES_NS}}}episode")
        if num is None or (num.text or "").strip() != str(episode_num):
            continue
        title = item.findtext("title") or ""
        desc = item.findtext("description") or ""
        return {"title": title.strip(), "description": desc}
    return None


def refresh_rss_item(config, art: EpisodeArtifacts, audio_duration: float,
                     published: dict) -> None:
    """Replace the episode's feed item with corrected audio metadata."""
    from engine.audio import format_duration
    from engine.publisher import apply_op3_prefix, update_rss_feed

    rss_path = ROOT / config.publishing.rss_file
    raw_url = (f"{config.publishing.base_url}/"
               f"{config.publishing.audio_subdir}/{art.final_mp3.name}")
    audio_url = (apply_op3_prefix(raw_url, config.analytics.prefix_url)
                 if config.analytics.enabled else raw_url)

    chapters_url = transcript_url = None
    if art.chapters_path.exists():
        chapters_url = (f"{config.publishing.base_url}/"
                        f"{config.publishing.audio_subdir}/{art.chapters_path.name}")
    if art.transcript_json.exists():
        transcript_url = (f"{config.publishing.base_url}/"
                          f"{config.publishing.audio_subdir}/{art.transcript_json.name}")

    episode_date = dt.datetime.strptime(art.date_str, "%Y%m%d").date()

    update_rss_feed(
        rss_path=rss_path,
        episode_num=art.episode_num,
        episode_title=published["title"],
        episode_description=published["description"],
        episode_date=episode_date,
        mp3_filename=art.final_mp3.name,
        mp3_duration=audio_duration,
        mp3_path=art.final_mp3,
        base_url=config.publishing.base_url,
        audio_subdir=config.publishing.audio_subdir,
        channel_title=config.publishing.rss_title,
        channel_link=config.publishing.rss_link,
        channel_description=config.publishing.rss_description,
        channel_language=config.publishing.rss_language,
        channel_author=config.publishing.rss_author,
        channel_email=config.publishing.rss_email,
        channel_image=config.publishing.rss_image,
        channel_category=config.publishing.rss_category,
        channel_subcategory=getattr(config.publishing, "rss_subcategory", ""),
        channel_category2=getattr(config.publishing, "rss_category2", ""),
        channel_subcategory2=getattr(config.publishing, "rss_subcategory2", ""),
        channel_keywords=getattr(config.publishing, "rss_keywords", ""),
        guid_prefix=config.publishing.guid_prefix,
        format_duration_func=format_duration,
        audio_url=audio_url,
        chapters_url=chapters_url,
        transcript_url=transcript_url,
    )


# ---------------------------------------------------------------------------
# Follow-up surfaces this tool cannot repair
# ---------------------------------------------------------------------------

def defect_window(script: str, transcript_json: Path) -> Optional[tuple]:
    """Seconds spanned by the longest passage the script does not contain.

    The same alignment the spoken-text gate performs, with the spoken
    words kept attached to their Whisper timings, so a repair can say
    WHICH derived clips overlap the defect instead of condemning all of
    them. Returns ``(start_s, end_s)``, or None when nothing is wrong.
    """
    import difflib

    from engine.spoken_text_gate import (
        MAX_WORDS_PER_SECOND,
        UNMATCHED_RUN_BRIDGE,
        load_segments,
        normalize_words,
    )

    segments = load_segments(transcript_json)
    if not segments:
        return None

    timed: List[tuple] = []  # (token, start, end)
    for seg in segments:
        try:
            start = float(seg.get("start", 0.0))
            end = float(seg.get("end", 0.0))
        except (TypeError, ValueError):
            continue
        seg_tokens = normalize_words(str(seg.get("text", "")))
        if not seg_tokens:
            continue
        span = end - start
        if span > 0 and len(seg_tokens) / span > MAX_WORDS_PER_SECOND:
            continue  # Whisper hallucination — the gate drops these too
        words = seg.get("words") or []
        if len(words) == len(seg_tokens):
            for tok, w in zip(seg_tokens, words):
                timed.append((tok, float(w.get("start", start)),
                              float(w.get("end", end))))
        else:
            step = span / max(1, len(seg_tokens))
            for i, tok in enumerate(seg_tokens):
                timed.append((tok, start + i * step, start + (i + 1) * step))

    if not timed:
        return None

    spoken = [t[0] for t in timed]
    matcher = difflib.SequenceMatcher(None, normalize_words(script), spoken,
                                      autojunk=False)
    best = cur = 0
    best_start = cur_start = None
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            if (j2 - j1) <= UNMATCHED_RUN_BRIDGE and cur > 0:
                cur += j2 - j1
                continue
            if cur > best:
                best, best_start = cur, cur_start
            cur, cur_start = 0, None
        else:
            if cur_start is None:
                cur_start = j1
            cur += j2 - j1
    if cur > best:
        best, best_start = cur, cur_start
    if not best or best_start is None:
        return None
    last = min(best_start + best, len(timed)) - 1
    return (round(timed[best_start][1], 2), round(timed[last][2], 2))


def manual_followups(art: EpisodeArtifacts, config=None,
                     window: Optional[tuple] = None) -> List[str]:
    """Surfaces carrying the old audio that a human has to handle.

    YouTube cannot replace a video's file and the daily edition splices
    published audio at build time, so a repair has to name them or a bad
    copy stays live. It names only what is actually affected:

    * The show's OWN-language videos come from this episode's audio, so
      the long form always is. A Short is only affected when its clip
      overlaps the defect — Ep605's second Short opens past the three
      minute mark and is clean, and deleting it would be pure loss.
    * The RU/FR dub videos are rendered from a SEPARATE synthesis of the
      translated script. An English-audio defect cannot reach them, so
      they are reported as unaffected rather than listed for deletion.
    """
    notes: List[str] = []
    clip_seconds = float(getattr(
        getattr(config, "youtube", None), "short_duration_seconds", 35.0) or 35.0)

    offsets: List[float] = []
    metrics_path = art.digests_dir / f"metrics_ep{art.episode_num:03d}.json"
    if metrics_path.exists():
        try:
            counters = json.loads(
                metrics_path.read_text(encoding="utf-8")).get("counters", {})
            raw = counters.get("shorts_start_offsets") or []
            offsets = [float(x) for x in raw]
        except (OSError, ValueError, TypeError):
            offsets = []

    path = art.digests_dir / "youtube_videos.json"
    if path.exists():
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            entries = []
        rows = entries if isinstance(entries, list) else entries.get("videos", [])
        shorts_seen = 0
        for v in rows:
            if not isinstance(v, dict) or str(v.get("episode")) != str(art.episode_num):
                continue
            kind = v.get("kind", "?")
            label = f"{kind} {v.get('video_id', '?')} ({v.get('title', '')[:56]})"

            if kind != "short":
                notes.append(f"YouTube: delete + re-upload {label} — the whole "
                             "episode, so it carries the defect")
                continue

            start = None
            if v.get("window") == "hook_open":
                start = 0.0
            elif shorts_seen < len(offsets):
                start = offsets[shorts_seen]
            shorts_seen += 1

            if window is None or start is None:
                notes.append(f"YouTube: CHECK {label} — cannot tell whether its "
                             "clip overlaps the defect; listen before deciding")
            elif start < window[1] and (start + clip_seconds) > window[0]:
                notes.append(f"YouTube: delete + re-upload {label} — its clip at "
                             f"{start:.0f}s overlaps the defect")
            else:
                notes.append(f"YouTube: KEEP {label} — its clip at {start:.0f}s is "
                             "outside the defect and its audio is fine")

    for dub, channel in (("youtube_videos.ru.json", "@NerraRU"),
                         ("youtube_videos.fr.json", "@NerraFR")):
        dub_path = art.digests_dir / dub
        if not dub_path.exists():
            continue
        try:
            entries = json.loads(dub_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows = entries if isinstance(entries, list) else entries.get("videos", [])
        count = sum(1 for v in rows if isinstance(v, dict)
                    and str(v.get("episode")) == str(art.episode_num))
        if count:
            notes.append(
                f"YouTube {channel}: {count} video(s) UNAFFECTED — dubs are a "
                "separate synthesis of the translated script, so this defect "
                "cannot appear in them. Do not delete them."
            )

    summaries = sorted(art.digests_dir.glob("summaries_*.json"))
    for path in summaries:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for entry in (data.get("summaries") or []):
            if str(entry.get("episode_num")) != str(art.episode_num):
                continue
            if entry.get("video"):
                notes.append(
                    "Apple video feed: re-upload the long-form MP4 at "
                    f"{entry['video'].get('url', '?')} — it carries the old audio"
                )

    daily = ROOT / "digests" / "nerra_daily"
    if daily.exists() and art.date_str:
        iso = f"{art.date_str[:4]}-{art.date_str[4:6]}-{art.date_str[6:]}"
        for md in daily.glob("*.md"):
            if art.date_str in md.name and iso:
                notes.append(
                    f"Nerra Daily {md.stem}: spliced this episode's audio; "
                    "rebuild that edition to pick up the repair"
                )
                break
    return notes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--show", required=True, help="Show slug (e.g. tesla)")
    ap.add_argument("--episode", type=int, required=True, help="Episode number")
    ap.add_argument("--date", help="YYYYMMDD, only if the number is ambiguous")
    ap.add_argument("--apply", action="store_true",
                    help="Perform the repair. Without it, nothing is written.")
    ap.add_argument("--skip-upload", action="store_true",
                    help="Build and verify locally; do not touch R2 or the feed.")
    ap.add_argument("--retries", type=int, default=1,
                    help="Synthesis retries when the gate fails (default 1)")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    from engine.config import load_config
    try:
        config = load_config(ROOT / "shows" / f"{args.show}.yaml")
        art = resolve_artifacts(config, args.episode, args.date)
    except (FileNotFoundError, ValueError) as exc:
        # Operator-facing tool: a wrong show or episode is a typo, not a
        # crash. Say what is wrong and exit.
        logger.error("%s", exc)
        return 1
    script = art.script_path.read_text(encoding="utf-8")

    logger.info("Repairing %s Ep%s (%s)", config.name, art.episode_num, art.date_str)
    logger.info("  script:  %s (%d chars)", art.script_path.name, len(script))
    logger.info("  R2 key:  %s  (unchanged — subscribers keep their link)", art.r2_key)

    before = read_committed_gate(config, art)
    window = None
    if before is not None:
        logger.info("  published audio: %s", before.summary())
        if before.passed:
            logger.warning(
                "The published audio already PASSES the spoken-text gate. "
                "Re-synthesizing is still possible, but confirm this is the "
                "episode you meant to repair."
            )
        else:
            window = defect_window(script, art.transcript_json)
            if window and "opening_mismatch" in before.reasons:
                # The longest CONTIGUOUS run can start after the real
                # damage does, because stray words inside a leak ("the",
                # "text", "same") align by chance. When the gate says the
                # opening did not match, the opening is damaged, so the
                # window starts at zero. A clip is deleted on this
                # judgement, so it errs toward flagging.
                window = (0.0, window[1])
            if window:
                logger.info("  defect spans %.1fs-%.1fs of the published audio",
                            *window)

    for note in manual_followups(art, config, window):
        logger.info("  follow-up: %s", note)

    if not args.apply:
        logger.info(
            "DRY RUN — nothing written. Re-run with --apply to synthesize, "
            "verify, upload to the same key and refresh the feed."
        )
        return 0

    api_key = (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()
    if not api_key:
        logger.error("GROK_API_KEY / XAI_API_KEY is not set — cannot synthesize.")
        return 1

    # --- synthesize + verify -------------------------------------------------
    report = None
    for attempt in range(1, args.retries + 2):
        logger.info("Synthesizing (attempt %d) ...", attempt)
        synthesize_script(config, script, art.raw_mp3, api_key)

        result = transcribe(config, art, art.raw_mp3, art.digests_dir)
        if result is None:
            logger.error(
                "No transcript produced, so the new audio cannot be verified. "
                "Refusing to publish unverified audio."
            )
            return 1
        report = gate_report(config, script, result)
        logger.info("  %s", report.summary())
        if report.passed:
            break
        if attempt > args.retries:
            logger.error(
                "::error::Re-synthesis still does not match the script after "
                "%d attempt(s): %s. Nothing uploaded.", attempt, report.summary(),
            )
            return 1
        logger.warning("Gate failed — re-synthesizing.")

    # --- mix + duration floor ------------------------------------------------
    audio_duration = mix_episode(config, art.raw_mp3, art.final_mp3)
    logger.info("Mixed: %s (%.0fs)", art.final_mp3.name, audio_duration)

    floor = config.min_audio_duration
    if floor and audio_duration < floor:
        logger.error(
            "::error::Repaired audio is %.0fs, under the %ds floor — not "
            "publishing it.", audio_duration, floor,
        )
        return 1

    # --- chapters ------------------------------------------------------------
    chapters = rebuild_chapters(config, art, script, audio_duration)
    if chapters:
        from engine.chapters import write_chapters_json
        was = published_chapter_titles(art.chapters_path)
        now = [c.title for c in chapters]
        if was and was != now:
            logger.warning(
                "Chapter titles changed during repair (%s -> %s). Timestamps "
                "were expected to move; titles were not.", was, now,
            )
        title_hook = chapters[0].title if chapters else ""
        write_chapters_json(
            chapters, art.chapters_path,
            episode_title=f"Ep {art.episode_num}: {title_hook}",
        )
        logger.info("Chapters rewritten: %s", art.chapters_path.name)

    # --- spend ---------------------------------------------------------------
    try:
        from engine.tracking import create_tracker, record_tts_usage, save_usage
        tracker = create_tracker(f"{config.name} (repair)", art.episode_num)
        record_tts_usage(tracker, len(script), provider=config.tts.provider)
        save_usage(tracker, art.digests_dir)
    except Exception as exc:  # noqa: BLE001 — accounting never blocks a repair
        logger.warning("Could not record repair spend: %s", exc)

    if args.skip_upload:
        logger.info("--skip-upload: local artifacts rebuilt; R2 and feed untouched.")
        return 0

    # --- upload to the SAME key ---------------------------------------------
    from engine.storage import upload_episode
    url = upload_episode(art.final_mp3, config)
    if not url:
        logger.error(
            "::error::R2 upload failed or storage is unconfigured. The feed "
            "still points at the OLD audio; not touching it."
        )
        return 1
    logger.info("Uploaded to %s", url)

    # --- feed ----------------------------------------------------------------
    published = read_published_item(ROOT / config.publishing.rss_file, art.episode_num)
    if published:
        refresh_rss_item(config, art, audio_duration, published)
        logger.info("RSS item refreshed (duration + byte length).")
    else:
        logger.warning(
            "Ep%s has no item in %s — audio replaced, feed left alone.",
            art.episode_num, config.publishing.rss_file,
        )

    logger.info("Repair complete. Remaining manual work:")
    for note in manual_followups(art, config, window) or ["(none found)"]:
        logger.info("  - %s", note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
