#!/usr/bin/env python3
"""Daily episode quality review.

Scans all episodes produced today, runs automated quality checks, and
optionally creates GitHub issues for problems found.

Usage:
    python review_episodes.py [--date YYYY-MM-DD] [--create-issues] [--show SLUG]

Checks performed:
    - Digest length (too short / too long)
    - Podcast script length vs target duration
    - Audio duration vs expectations
    - Repeated content across today's episodes
    - LLM artifacts leaked into scripts (URLs, metadata, template vars)
    - Missing required sections (per-show validation)
    - Pipeline errors (stages that failed in metrics)
    - Cross-episode duplicate stories (same-day)
    - AI review via Grok for content quality (optional, needs GROK_API_KEY)

Exit codes:
    0 — all episodes OK (or no episodes today)
    1 — critical issues found (episodes that should be considered for removal)
    2 — warnings only (fixable for future episodes)
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("review")

PROJECT_ROOT = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    show: str
    episode: int
    severity: str  # "critical", "warning", "info"
    title: str
    detail: str
    file_path: str = ""

    @property
    def label(self) -> str:
        return {
            "critical": "severity: critical",
            "warning": "severity: warning",
            "info": "severity: info",
        }.get(self.severity, "severity: info")


@dataclass
class EpisodeReview:
    show_slug: str
    show_name: str
    episode_num: int
    date: str
    digest_path: Optional[Path] = None
    tts_path: Optional[Path] = None
    metrics_path: Optional[Path] = None
    chapters_path: Optional[Path] = None
    digest_text: str = ""
    tts_text: str = ""
    metrics: dict = field(default_factory=dict)
    issues: List[Issue] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Show registry (maps slug -> config needed for review)
# ---------------------------------------------------------------------------

SHOW_REGISTRY = {
    "tesla": {
        "name": "Tesla Shorts Time",
        "output_dir": "digests/tesla_shorts_time",
        "prefix": "Tesla_Shorts_Time_Pod",
        "min_digest_chars": 3000,
        "max_digest_chars": 20000,
        "min_tts_words": 2200,
        "min_audio_s": 300,
        "max_audio_s": 1800,
        "required_sections": ["Top", "X Takeover", "First Principles"],
        # Schedule: "daily", "odd", "even", "weekday", "odd_weekday"
        "schedule": "daily",
    },
    "omni_view": {
        "name": "Omni View",
        "output_dir": "digests/omni_view",
        "prefix": "Omni_View_Ep",
        "min_digest_chars": 2000,
        "max_digest_chars": 30000,
        "min_tts_words": 1500,
        "min_audio_s": 240,
        "max_audio_s": 1500,
        "required_sections": [],
        "schedule": "odd",
    },
    "fascinating_frontiers": {
        "name": "Fascinating Frontiers",
        "output_dir": "digests/fascinating_frontiers",
        "prefix": "Fascinating_Frontiers_Ep",
        "min_digest_chars": 2000,
        "max_digest_chars": 18000,
        "min_tts_words": 1500,
        "min_audio_s": 240,
        "max_audio_s": 1500,
        "required_sections": [],
        "schedule": "even",
    },
    "planetterrian": {
        "name": "Planetterrian Daily",
        "output_dir": "digests/planetterrian",
        "prefix": "Planetterrian_Ep",
        "min_digest_chars": 2000,
        "max_digest_chars": 18000,
        "min_tts_words": 1500,
        "min_audio_s": 240,
        "max_audio_s": 1500,
        "required_sections": [],
        "schedule": "odd",
    },
    "env_intel": {
        "name": "Environmental Intelligence",
        "output_dir": "digests/env_intel",
        "prefix": "Env_Intel_Ep",
        "min_digest_chars": 2000,
        "max_digest_chars": 18000,
        "min_tts_words": 1500,
        "min_audio_s": 240,
        "max_audio_s": 1500,
        "required_sections": [],
        "schedule": "odd_weekday",
    },
    "models_agents": {
        "name": "Models & Agents",
        "output_dir": "digests/models_agents",
        "prefix": "Models_Agents_Ep",
        "min_digest_chars": 2000,
        "max_digest_chars": 18000,
        "min_tts_words": 1500,
        "min_audio_s": 240,
        "max_audio_s": 1500,
        "required_sections": [],
        "schedule": "odd",
    },
    "models_agents_beginners": {
        "name": "Models & Agents for Beginners",
        "output_dir": "digests/models_agents_beginners",
        "prefix": "MAB_Ep",
        "min_digest_chars": 2000,
        "max_digest_chars": 18000,
        "min_tts_words": 1100,
        "min_audio_s": 180,
        "max_audio_s": 1500,
        "required_sections": [],
        "schedule": "even",
    },
    "finansy_prosto": {
        "name": "Finansy Prosto",
        "output_dir": "digests/finansy_prosto",
        "prefix": "Finansy_Prosto_Ep",
        "min_digest_chars": 1500,
        "max_digest_chars": 18000,
        "min_tts_words": 800,
        "min_audio_s": 180,
        "max_audio_s": 1200,
        "required_sections": [],
        "schedule": "even",
    },
    "modern_investing": {
        "name": "Modern Investing Techniques",
        "output_dir": "digests/modern_investing",
        "prefix": "Modern_Investing",
        "min_digest_chars": 2500,
        "max_digest_chars": 20000,
        "min_tts_words": 2000,
        "min_audio_s": 300,
        "max_audio_s": 1800,
        "required_sections": ["Strategy Spotlight", "Practice Investment"],
        "schedule": "weekday",
    },
    "privet_russian": {
        "name": "Privet Russian",
        "output_dir": "digests/privet_russian",
        "prefix": "Privet_Russian_Ep",
        "min_digest_chars": 1500,
        "max_digest_chars": 18000,
        "min_tts_words": 800,
        "min_audio_s": 180,
        "max_audio_s": 1200,
        "required_sections": [],
        "schedule": "even",
    },
}


# ---------------------------------------------------------------------------
# Schedule helpers
# ---------------------------------------------------------------------------

def _should_run_on(schedule: str, target_date: datetime.date) -> bool:
    """Return True if *schedule* means the show should produce an episode on *target_date*."""
    day = target_date.day
    weekday = target_date.weekday()  # 0=Mon .. 6=Sun
    is_weekday = weekday < 5

    if schedule == "daily":
        return True
    if schedule == "odd":
        return day % 2 == 1
    if schedule == "even":
        return day % 2 == 0
    if schedule == "weekday":
        return is_weekday
    if schedule == "odd_weekday":
        return day % 2 == 1 and is_weekday
    return True  # unknown schedule → assume should run


def _read_skip_marker(output_dir: str, target_date: datetime.date) -> Optional[dict]:
    """Read a skip marker file if one exists for the given date.

    Skip markers are written by ``run_show.py`` when the pipeline exits early
    (exit code 2) due to insufficient articles, duplicate content, etc.
    """
    marker_path = PROJECT_ROOT / output_dir / f".skip_{target_date.strftime('%Y%m%d')}.json"
    if not marker_path.exists():
        return None
    try:
        return json.loads(marker_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read skip marker %s: %s", marker_path, exc)
        return None


def check_missed_episodes(
    target_date: datetime.date,
    found_episodes: List[EpisodeReview],
    show_filter: str = "",
) -> List[Issue]:
    """Detect shows that were scheduled to produce an episode but didn't.

    Returns a list of Issue objects for missing episodes.  If the pipeline
    intentionally skipped an episode (and left a skip marker file), the issue
    is reported as a *warning* instead of *critical* so the daily review can
    distinguish genuine failures from expected skips.
    """
    found_slugs = {ep.show_slug for ep in found_episodes}
    missed: List[Issue] = []

    for slug, info in SHOW_REGISTRY.items():
        if show_filter and slug != show_filter:
            continue
        schedule = info.get("schedule", "daily")
        if not _should_run_on(schedule, target_date):
            continue
        if slug in found_slugs:
            continue

        # Check for a skip marker — pipeline ran but intentionally skipped
        marker = _read_skip_marker(info["output_dir"], target_date)
        if marker:
            reason = marker.get("reason", "unknown")
            detail = marker.get("detail", "No detail provided.")
            missed.append(Issue(
                show=slug,
                episode=0,
                severity="warning",
                title=f"Skipped episode: {info['name']} ({reason})",
                detail=(
                    f"{info['name']} was scheduled on "
                    f"{target_date.isoformat()} (schedule: {schedule}) but the "
                    f"pipeline intentionally skipped this episode. "
                    f"Reason: {detail}"
                ),
            ))
        else:
            missed.append(Issue(
                show=slug,
                episode=0,
                severity="critical",
                title=f"Missed episode: {info['name']}",
                detail=(
                    f"{info['name']} was scheduled to produce an episode on "
                    f"{target_date.isoformat()} (schedule: {schedule}) but no output "
                    f"files were found in {info['output_dir']}/ and no skip marker "
                    f"was present. The pipeline may have failed or the workflow did "
                    f"not trigger."
                ),
            ))

    return missed


# ---------------------------------------------------------------------------
# Discovery: find today's episodes
# ---------------------------------------------------------------------------

def discover_episodes(target_date: datetime.date, show_filter: str = "") -> List[EpisodeReview]:
    """Find all episodes generated on *target_date*."""
    date_str = target_date.strftime("%Y%m%d")
    episodes: List[EpisodeReview] = []

    for slug, info in SHOW_REGISTRY.items():
        if show_filter and slug != show_filter:
            continue

        output_dir = PROJECT_ROOT / info["output_dir"]
        if not output_dir.exists():
            continue

        # Find digest .md files matching today's date
        for md_file in sorted(output_dir.glob(f"*{date_str}.md")):
            # Extract episode number from filename
            m = re.search(r"Ep(\d+)", md_file.name)
            if not m:
                continue
            ep_num = int(m.group(1))

            # Find companion files
            stem = md_file.stem  # e.g. Tesla_Shorts_Time_Pod_Ep414_20260322
            tts_file = output_dir / f"{stem}_tts.txt"
            metrics_file = output_dir / f"metrics_ep{ep_num:03d}.json"
            chapters_file = output_dir / f"chapters_ep{ep_num:03d}.json"

            review = EpisodeReview(
                show_slug=slug,
                show_name=info["name"],
                episode_num=ep_num,
                date=target_date.isoformat(),
                digest_path=md_file if md_file.exists() else None,
                tts_path=tts_file if tts_file.exists() else None,
                metrics_path=metrics_file if metrics_file.exists() else None,
                chapters_path=chapters_file if chapters_file.exists() else None,
            )

            if review.digest_path:
                review.digest_text = review.digest_path.read_text(encoding="utf-8")
            if review.tts_path:
                review.tts_text = review.tts_path.read_text(encoding="utf-8")
            if review.metrics_path:
                try:
                    review.metrics = json.loads(review.metrics_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass

            episodes.append(review)

    return episodes


# ---------------------------------------------------------------------------
# Automated checks
# ---------------------------------------------------------------------------

def check_digest_length(ep: EpisodeReview, info: dict) -> None:
    """Check digest is within expected length bounds."""
    if not ep.digest_text:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "critical",
            "Missing digest file",
            f"No digest .md found for {ep.show_name} Ep{ep.episode_num}",
        ))
        return

    chars = len(ep.digest_text)
    min_chars = info["min_digest_chars"]
    if chars < min_chars * 0.5:
        # Dangerously short — likely truncated or failed LLM response
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "critical",
            f"Digest too short ({chars} chars)",
            f"Digest is only {chars} characters (minimum: {min_chars}, critical below {int(min_chars*0.5)}). "
            f"The LLM likely returned a truncated or failed response.",
            file_path=str(ep.digest_path),
        ))
    elif chars < min_chars:
        # Below target but not catastrophically — may just be a concise episode
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "warning",
            f"Digest below target length ({chars} chars)",
            f"Digest is {chars} characters (target minimum: {min_chars}). "
            f"Episode may be shorter than usual.",
            file_path=str(ep.digest_path),
        ))
    elif chars > info["max_digest_chars"]:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "warning",
            f"Digest unusually long ({chars} chars)",
            f"Digest is {chars} characters (max expected: {info['max_digest_chars']}). "
            f"May contain duplicate content or LLM rambling.",
            file_path=str(ep.digest_path),
        ))


def check_tts_script(ep: EpisodeReview, info: dict) -> None:
    """Check podcast script quality."""
    if not ep.tts_text:
        # Not all shows generate a separate _tts.txt
        return

    words = len(ep.tts_text.split())
    min_words = info["min_tts_words"]

    if words < min_words * 0.5:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "critical",
            f"Podcast script dangerously short ({words} words)",
            f"Script has only {words} words (target: {min_words}+). "
            f"Episode will sound thin and rushed. Consider deletion.",
            file_path=str(ep.tts_path),
        ))
    elif words < min_words:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "warning",
            f"Podcast script below target ({words} words)",
            f"Script has {words} words (target: {min_words}+). "
            f"Episode may feel shorter than usual.",
            file_path=str(ep.tts_path),
        ))


def check_audio_duration(ep: EpisodeReview, info: dict) -> None:
    """Check audio duration from metrics."""
    duration = ep.metrics.get("counters", {}).get("audio_duration_s")
    if duration is None:
        return

    min_s = info["min_audio_s"]
    max_s = info["max_audio_s"]

    if duration < min_s * 0.5:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "critical",
            f"Audio extremely short ({duration:.0f}s)",
            f"Audio is only {duration:.0f}s ({duration/60:.1f} min). "
            f"Minimum is {min_s}s. Episode is likely broken or truncated.",
        ))
    elif duration < min_s:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "warning",
            f"Audio below minimum ({duration:.0f}s)",
            f"Audio is {duration:.0f}s ({duration/60:.1f} min), "
            f"below the {min_s}s minimum.",
        ))
    elif duration > max_s:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "warning",
            f"Audio unusually long ({duration:.0f}s)",
            f"Audio is {duration:.0f}s ({duration/60:.1f} min), "
            f"above the {max_s}s expected maximum.",
        ))


def check_pipeline_errors(ep: EpisodeReview) -> None:
    """Check for pipeline stage failures in metrics."""
    stages = ep.metrics.get("stages", [])
    for stage in stages:
        if not stage.get("success", True):
            error = stage.get("error", "unknown error")
            ep.issues.append(Issue(
                ep.show_slug, ep.episode_num, "critical",
                f"Pipeline stage failed: {stage['name']}",
                f"Stage '{stage['name']}' failed with: {error}",
            ))


def check_leaked_artifacts(ep: EpisodeReview) -> None:
    """Check for LLM artifacts that shouldn't appear in the podcast script."""
    text = ep.tts_text or ep.digest_text
    if not text:
        return

    # Patterns that indicate LLM/prompt leakage or metadata in TTS output
    artifact_patterns = [
        (r"https?://\S+", "URL leaked into script"),
        (r"\{[a-z_]+\}", "Unfilled template placeholder"),
        (r"(?i)word\s*count\s*[:：]", "Word count metadata in script"),
        (r"(?i)character\s*count\s*[:：]", "Character count metadata in script"),
        (r"(?i)^(RULES|NEVER INCLUDE|CONTENT FOCUS)\s*:", "Leaked prompt instructions"),
        (r"(?i)as an AI language model", "AI self-reference leaked"),
        (r"(?i)I('m| am) (an AI|a language model|ChatGPT|Claude)", "AI identity leaked"),
        (r"Source:\s*https?://", "Source URL in podcast script"),
        # Word count and timing targets that leak from prompt into spoken script
        (r"(?i)\b\d{3,4}\s+words?\b", "Word count target leaked into script"),
        (r"(?i)\b\d+\s*[-–]\s*\d+\s*(minute|second)s?\s+(of\s+audio|episode|podcast)\b",
         "Timing target leaked into script"),
        (r"(?i)producing\s+a\s+\d+", "Episode length target leaked into script"),
        (r"(?i)at\s+least\s+\d[\d,]*\s+words", "Minimum word count leaked into script"),
        (r"(?i)target:\s*\d+", "Target directive leaked into script"),
        # Bracketed section labels that should have been stripped
        (r"\[(?:Intro|Hook|Closing|Segment|Market Pulse|Strategy)\s*[-–—]",
         "Bracketed section label in script"),
    ]

    # Only check TTS text for spoken artifacts
    check_text = ep.tts_text if ep.tts_text else text
    for pattern, desc in artifact_patterns:
        matches = re.findall(pattern, check_text, re.MULTILINE)
        if matches:
            # URLs in digest are normal; only flag in TTS script
            if "URL" in desc and not ep.tts_text:
                continue
            sample = matches[0] if isinstance(matches[0], str) else matches[0]
            ep.issues.append(Issue(
                ep.show_slug, ep.episode_num, "warning",
                f"Artifact in script: {desc}",
                f"Found {len(matches)} occurrence(s) of: {desc}. "
                f"Sample: '{str(sample)[:100]}'",
            ))


def check_required_sections(ep: EpisodeReview, info: dict) -> None:
    """Check that required sections are present in the digest.

    Skips the check when the episode was produced in slow news mode, since
    slow news episodes use a different structure (evergreen segments) and
    aren't expected to have the same sections as regular episodes.
    """
    required = info.get("required_sections", [])
    if not required or not ep.digest_text:
        return

    # Skip for slow news episodes — different episode structure
    counters = ep.metrics.get("counters", {}) if ep.metrics else {}
    if counters.get("slow_news_mode"):
        return

    text_lower = ep.digest_text.lower()
    for section in required:
        if section.lower() not in text_lower:
            ep.issues.append(Issue(
                ep.show_slug, ep.episode_num, "warning",
                f"Missing section: {section}",
                f"Required section '{section}' not found in digest. "
                f"Episode may be missing expected content.",
            ))


def check_repetition(ep: EpisodeReview) -> None:
    """Check for excessive repetition within the episode."""
    text = ep.tts_text or ep.digest_text
    if not text:
        return

    words = text.split()
    if len(words) < 100:
        return

    from collections import Counter
    # Check 3-word phrases for repetition
    trigrams = [" ".join(words[i:i+3]).lower() for i in range(len(words) - 2)]
    counts = Counter(trigrams)

    # Skip common phrases, pronunciation expansions (single-letter words from
    # TTS abbreviation splitting like TFSA -> "t f s a"), and intentional
    # repetition in language-learning shows ("repeat after me", host-prefixed
    # variants like "olya: repeat after", and bilingual teaching patterns).
    skip_phrases = {
        "of the the", "in the the", "and the the", "the the the",
        "repeat after me", "repeat after me.", "repeat after me:",
    }
    # Patterns that indicate intentional pedagogical repetition, not LLM loops.
    # Covers host-prefixed variants (e.g. "olya: repeat after") and common
    # language-learning drill phrases.
    _PEDAGOGICAL_PATTERNS = [
        re.compile(r"^\w+: repeat"),             # "olya: repeat after"
        re.compile(r"^repeat after \w+"),          # "repeat after olya"
        re.compile(r"^let's practice"),            # "let's practice saying"
        re.compile(r"^now say"),                   # "now say it"
        re.compile(r"^try saying"),                # "try saying this"
        re.compile(r"^\w+: now let's"),            # "olya: now let's"
        re.compile(r"^\w+: давайте"),              # Russian: "let's"
        re.compile(r"^повторяйте за"),             # Russian: "repeat after"
        # Translation patterns — inherent to bilingual language-learning shows
        re.compile(r"^that means"),               # "that means [translation]"
        re.compile(r"^it means"),                 # "it means [translation]"
        re.compile(r"^\w+: that means"),          # "olya: that means"
        re.compile(r"^\w+: it means"),            # "olya: it means"
        re.compile(r"^means i am"),               # tail of "that means I am..."
        re.compile(r"^means the \w+"),            # tail of "that means the..."
    ]
    # Single-letter trigrams are TTS pronunciation splits (e.g. "f s d", "e s a").
    # Also match "the a i", "an a i", "your t f" — article/pronoun + split abbreviation.
    _SINGLE_LETTER_TRIGRAM = re.compile(r"^[a-z] [a-z] [a-z]$")
    _ABBREV_CONTEXT = re.compile(r"^(?:the|an|a|of|your|my|our|its|and) [a-z] [a-z]$")

    for phrase, count in counts.most_common(10):
        if phrase in skip_phrases:
            continue
        if _SINGLE_LETTER_TRIGRAM.match(phrase):
            continue
        if _ABBREV_CONTEXT.match(phrase):
            continue
        if any(p.match(phrase) for p in _PEDAGOGICAL_PATTERNS):
            continue
        if count >= 5:
            ep.issues.append(Issue(
                ep.show_slug, ep.episode_num, "warning",
                f"Excessive repetition: '{phrase}' ({count}x)",
                f"The phrase '{phrase}' appears {count} times, "
                f"suggesting possible LLM hallucination or loop.",
            ))
            break  # One is enough


def check_cross_episode_duplicates(episodes: List[EpisodeReview]) -> None:
    """Check for duplicate stories across different shows on the same day."""
    if len(episodes) < 2:
        return

    # Extract headlines from each episode
    ep_headlines: dict[str, list[str]] = {}
    for ep in episodes:
        if not ep.digest_text:
            continue
        headlines = []
        for line in ep.digest_text.splitlines():
            line = line.strip()
            # Match numbered items or ### headers
            m = re.match(r"(?:\d+\.\s+\*{0,2})(.+?)(?:\*{0,2}\s*[—–-]|\s*$)", line)
            if m and len(m.group(1)) > 20:
                headlines.append(m.group(1).strip().lower())
            elif line.startswith("### ") and len(line) > 10:
                headlines.append(line[4:].strip().lower())
        ep_headlines[f"{ep.show_slug}:{ep.episode_num}"] = headlines

    # Simple overlap detection (word-based)
    keys = list(ep_headlines.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            h1 = ep_headlines.get(keys[i], [])
            h2 = ep_headlines.get(keys[j], [])
            duplicates = []
            for a in h1:
                a_words = set(a.split())
                for b in h2:
                    b_words = set(b.split())
                    if len(a_words) < 4 or len(b_words) < 4:
                        continue
                    overlap = len(a_words & b_words) / max(len(a_words | b_words), 1)
                    if overlap > 0.6:
                        duplicates.append((a[:60], b[:60]))

            if len(duplicates) >= 3:
                slug_i = keys[i].split(":")[0]
                ep_i = int(keys[i].split(":")[1])
                slug_j = keys[j].split(":")[0]
                for ep in episodes:
                    if ep.show_slug == slug_i and ep.episode_num == ep_i:
                        ep.issues.append(Issue(
                            ep.show_slug, ep.episode_num, "info",
                            f"Significant story overlap with {slug_j}",
                            f"Found {len(duplicates)} overlapping stories with {slug_j}. "
                            f"Example: '{duplicates[0][0]}...'",
                        ))
                        break


# ---------------------------------------------------------------------------
# Additional quality checks
# ---------------------------------------------------------------------------

def check_transition_duplication(ep: EpisodeReview) -> None:
    """Detect duplicate transition sentences (line N ends with same sentence that line N+1 starts with).

    This is the TST Ep419 bug pattern: the LLM writes a transition tease at the
    end of one paragraph, then repeats it verbatim as the opener of the next.
    """
    text = ep.tts_text or ep.digest_text
    if not text:
        return

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return

    def _normalize(s: str) -> str:
        # Strip host prefixes and whitespace
        s = re.sub(r"^(?:Host|Olya|Patrick)\s*:\s*", "", s, flags=re.IGNORECASE)
        return s.lower().strip()

    def _sentence_words(s: str) -> set:
        return set(re.findall(r"\b[a-z]+\b", s.lower()))

    dup_count = 0
    for i in range(len(lines) - 1):
        line_a = _normalize(lines[i])
        line_b = _normalize(lines[i + 1])
        if not line_a or not line_b:
            continue

        words_a = _sentence_words(line_a)
        words_b = _sentence_words(line_b)
        if len(words_a) < 4 or len(words_b) < 4:
            continue

        # Case 1: entire line is near-duplicate (high word overlap).
        # Use Jaccard similarity but also check containment — if the shorter
        # line's words are almost entirely in the longer line, it's a dup
        # even if the longer line adds extra words.
        intersection = words_a & words_b
        union = words_a | words_b
        jaccard = len(intersection) / max(len(union), 1)
        smaller = min(len(words_a), len(words_b))
        containment = len(intersection) / max(smaller, 1)
        if jaccard >= 0.75 or (containment >= 0.85 and len(intersection) >= 5):
            dup_count += 1
            continue

        # Case 2: line A ends with a sentence that matches line B's opening
        sentences_a = re.split(r'(?<=[.!?])\s+', line_a)
        if len(sentences_a) >= 2:
            last_sent = sentences_a[-1]
            last_words = _sentence_words(last_sent)
            # Compare last sentence of A to full line B (or first sentence of B)
            sentences_b = re.split(r'(?<=[.!?])\s+', line_b)
            first_b_words = _sentence_words(sentences_b[0])
            if len(last_words) >= 4 and len(first_b_words) >= 4:
                sent_overlap = len(last_words & first_b_words) / max(len(last_words | first_b_words), 1)
                if sent_overlap >= 0.70:
                    dup_count += 1

    if dup_count >= 2:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "warning",
            f"Duplicate transitions ({dup_count} instances)",
            f"Found {dup_count} consecutive line pairs with near-duplicate content. "
            f"The LLM is repeating transition sentences across paragraph boundaries.",
            file_path=str(ep.tts_path or ep.digest_path or ""),
        ))
    elif dup_count == 1:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "info",
            "Possible duplicate transition (1 instance)",
            "One consecutive line pair has near-duplicate content.",
            file_path=str(ep.tts_path or ep.digest_path or ""),
        ))


def check_slow_news_leakage(ep: EpisodeReview) -> None:
    """Detect leaked slow-news-day language in episode text.

    Slow news episodes should be indistinguishable from normal episodes.
    """
    text = ep.tts_text or ep.digest_text
    if not text:
        return

    leakage_patterns = [
        (r"(?i)\bslow\s+news\s+day\b", "slow news day"),
        (r"(?i)\bslow\s+news\s+edition\b", "slow news edition"),
        (r"(?i)\blighter\s+(?:than\s+usual|news\s+day)\b", "lighter than usual"),
        (r"(?i)\bfewer\s+stories?\s+than\s+usual\b", "fewer stories than usual"),
        (r"(?i)\bnews\s+is\s+(?:slow|light|quiet)\b", "news is slow/light/quiet"),
        (r"(?i)\bnot\s+(?:much|a\s+lot\s+of)\s+news\b", "not much news"),
        (r"(?i)\bquiet\s+news\s+day\b", "quiet news day"),
        (r"(?i)\[Slow\s+News", "[Slow News label"),
    ]

    for pattern, desc in leakage_patterns:
        matches = re.findall(pattern, text)
        if matches:
            ep.issues.append(Issue(
                ep.show_slug, ep.episode_num, "warning",
                f"Slow news language leaked: '{desc}'",
                f"Episode contains '{desc}' language ({len(matches)} occurrence(s)). "
                f"Slow news episodes should not reveal they are slow news days.",
                file_path=str(ep.tts_path or ep.digest_path or ""),
            ))
            break  # One is enough


def check_intro_outro(ep: EpisodeReview) -> None:
    """Verify that the podcast script has both an intro and closing section."""
    text = ep.tts_text
    if not text:
        return

    text_lower = text.lower()
    words = text.split()
    if len(words) < 50:
        return  # Too short to meaningfully check

    # Check that the script starts with a proper intro.
    # NOTE: The TTS text has "Host:" prefixes stripped by clean_podcast_script()
    # (they're not meant to be spoken), so we check for intro patterns instead.
    first_lines = text_lower[:500]
    intro_patterns = [
        r"welcome to", r"thanks? for tuning", r"thanks? for joining",
        r"good (morning|afternoon|evening)", r"episode\s+\w+",
        r"it'?s\s+(january|february|march|april|may|june|july|august|september|october|november|december)",
        r"i'?m\s+(patrick|olya)", r"добро пожаловать", r"привет",
        r"здравствуйте", r"let'?s\s+dive",
    ]
    has_intro = any(re.search(p, first_lines) for p in intro_patterns)
    if not has_intro:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "info",
            "Script may be missing intro greeting",
            "The first 500 characters don't contain a recognizable intro pattern "
            "(e.g. 'Welcome to', 'Thanks for tuning in', host name). "
            "The episode may start abruptly.",
            file_path=str(ep.tts_path),
        ))

    # Check last 500 chars for closing indicators
    last_text = text_lower[-500:]
    closing_indicators = [
        "tomorrow", "next episode", "next time", "see you",
        "until then", "that's it for", "that's all for",
        "thanks for listening", "thanks for tuning",
        "до свидания", "до встречи", "до завтра",
        "subscribe", "follow",
    ]
    has_closing = any(ind in last_text for ind in closing_indicators)
    if not has_closing:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "info",
            "Script may be missing closing section",
            "No closing indicators found in the last 500 characters. "
            "Episode may end abruptly without a proper sign-off.",
            file_path=str(ep.tts_path),
        ))


def check_pipeline_metrics(ep: EpisodeReview) -> None:
    """Check pipeline performance metrics for anomalies."""
    if not ep.metrics:
        return

    counters = ep.metrics.get("counters", {})
    stages = ep.metrics.get("stages", [])

    # Check for excessive LLM retries
    retry_stages = [s for s in stages if "retry" in s.get("name", "").lower()]
    if len(retry_stages) >= 3:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "warning",
            f"Excessive LLM retries ({len(retry_stages)} retry stages)",
            f"The pipeline required {len(retry_stages)} retry stages, "
            f"indicating the LLM struggled to produce acceptable output. "
            f"This may indicate prompt issues or model degradation.",
        ))

    # Check total pipeline duration
    total_duration = counters.get("total_duration_s")
    if total_duration and total_duration > 2400:  # 40 minutes
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "warning",
            f"Pipeline unusually slow ({total_duration:.0f}s)",
            f"Total pipeline took {total_duration:.0f}s ({total_duration/60:.1f} min). "
            f"Normal is under 30 minutes. Check for LLM timeouts or TTS issues.",
        ))

    # Check if slow_news_mode was active — informational
    slow_news = counters.get("slow_news_mode")
    if slow_news:
        trigger = counters.get("slow_news_trigger", "unknown")
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "info",
            f"Slow news mode active (trigger: {trigger})",
            f"This episode was produced in slow news mode (trigger: {trigger}). "
            f"Verify it sounds natural and doesn't reveal the slow news status.",
        ))

    # Check article count — too few may indicate feed issues
    article_count = counters.get("article_count")
    if article_count is None:
        article_count = counters.get("articles_fetched")
    if article_count is not None and article_count == 0:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "warning",
            "Zero articles fetched",
            "The pipeline fetched zero articles. RSS feeds may be down "
            "or the news sources may have changed their format.",
        ))
    elif article_count is not None and article_count <= 2:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "info",
            f"Very few articles fetched ({article_count})",
            f"Only {article_count} article(s) were available. Content may be thin.",
        ))

    # Grok Imagine generated 0 images while the show was opted in.
    # Operator caught (TST Ep465, May 6 2026) the slideshow silently
    # falling back to the cover when the API rejected the ``size``
    # parameter. The fix landed in PR #322; this check makes any
    # future failure mode (auth lapse, rate limit, model retirement)
    # surface as a daily-review warning instead of needing a manual
    # log dive.
    image_provider = (counters.get("image_provider") or "pexels").lower()
    if image_provider in ("grok", "hybrid"):
        gen_count = counters.get("grok_images_generated")
        if isinstance(gen_count, int) and gen_count == 0:
            failures = counters.get("grok_image_failures") or []
            sample = failures[0] if failures else "(no failure detail)"
            ep.issues.append(Issue(
                ep.show_slug, ep.episode_num, "warning",
                "Grok Imagine produced 0 images (slideshow fell back to cover)",
                f"The show is configured with image_provider={image_provider!r} "
                f"but the Grok Imagine API generated 0 images on this run, so "
                f"the YouTube long-form / Shorts slideshow used only the show "
                f"cover. First failure: {sample}. Check engine.grok_imagine "
                f"logs and the API response shape.",
            ))

    # YouTube upload failures — long-form is the larger surface so a
    # silent failure there matters. ``youtube_long_error`` / `_short_error`
    # are surfaced into metrics by ``_publish_youtube`` so the operator
    # gets daily visibility without log-diving. Operator caught the
    # ``invalidDescription`` regression (May 2026) on a manual metrics
    # check; this check makes it automatic.
    for kind in ("long", "short"):
        err = counters.get(f"youtube_{kind}_error")
        if not err:
            continue
        msg = err.get("message", "")[:200] if isinstance(err, dict) else str(err)[:200]
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "warning",
            f"YouTube {kind}-form upload failed",
            f"The {kind}-form video upload failed: {msg}. Check the "
            f"engine.youtube logs for the full stack trace and the YouTube "
            f"Data API quota dashboard.",
        ))


def check_story_duplication(ep: EpisodeReview) -> None:
    """Detect the same story being told twice within a single episode.

    Uses proper-noun signal extraction to find non-adjacent paragraphs
    covering the same topic.
    """
    text = ep.tts_text or ep.digest_text
    if not text:
        return

    # Split into paragraph blocks (separated by blank lines or host prefixes)
    blocks = re.split(r"\n\s*\n|\n(?=(?:Host|Olya|Patrick)\s*:)", text, flags=re.IGNORECASE)
    blocks = [b.strip() for b in blocks if len(b.strip()) > 100]

    if len(blocks) < 3:
        return

    # Extract proper noun signals from each block
    def _extract_signals(block: str) -> set:
        # Remove host prefixes
        clean = re.sub(r"^(?:Host|Olya|Patrick)\s*:\s*", "", block, flags=re.IGNORECASE | re.MULTILINE)
        # Find multi-word proper noun phrases (consecutive capitalized words)
        phrases = set()
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", clean):
            phrase = m.group(1)
            # Skip generic phrases
            if phrase.lower() not in {"the united states", "new york", "first principles"}:
                phrases.add(phrase.lower())
        # Find individual proper nouns (single capitalized words, 4+ chars)
        for m in re.finditer(r"\b([A-Z][a-z]{3,})\b", clean):
            word = m.group(1).lower()
            if word not in {"this", "that", "host", "today", "here", "well",
                           "just", "first", "they", "their", "there", "these",
                           "before", "after", "about", "also", "still", "really",
                           "episode", "podcast", "next", "last", "meanwhile"}:
                phrases.add(word)
        return phrases

    block_signals = [_extract_signals(b) for b in blocks]

    # Compare non-adjacent blocks (skip intro [0] and outro [-1])
    dup_pairs = 0
    for i in range(1, len(blocks) - 1):
        for j in range(i + 2, len(blocks) - 1):
            if not block_signals[i] or not block_signals[j]:
                continue
            overlap = block_signals[i] & block_signals[j]
            union = block_signals[i] | block_signals[j]
            if len(overlap) >= 3 and len(overlap) / max(len(union), 1) >= 0.5:
                dup_pairs += 1

    if dup_pairs >= 2:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "warning",
            f"Possible story duplication ({dup_pairs} block pairs)",
            f"Found {dup_pairs} pairs of non-adjacent paragraph blocks with "
            f"high proper-noun overlap. The same story may be covered twice.",
            file_path=str(ep.tts_path or ep.digest_path or ""),
        ))


def check_content_freshness(episodes: List[EpisodeReview], target_date: datetime.date) -> None:
    """Check for signs of content repetition and stale content using metrics.

    Flags episodes where:
    - cross_episode_repeats is high (content tracker found many recent duplicates)
    - slow_news_mode triggered for 3+ consecutive days (chronic staleness)
    - The same hook/lead story appeared in consecutive episodes
    """
    for ep in episodes:
        counters = ep.metrics.get("counters", {}) if ep.metrics else {}

        # High cross-episode repeats means the LLM is recycling stories
        repeats = counters.get("cross_episode_repeats", 0)
        if repeats >= 5:
            ep.issues.append(Issue(
                ep.show_slug, ep.episode_num, "warning",
                f"High cross-episode repetition ({repeats} stories)",
                f"The content tracker found {repeats} stories in this episode that were "
                f"already covered in recent episodes. This indicates the show may be "
                f"repeating content across days. Check that {{recent_content_summary}} is "
                f"wired into the digest prompt (shows/prompts/{{slug}}_digest.txt) and "
                f"that the content tracker JSON is being updated correctly.\n"
                f"  Config: shows/{ep.show_slug}.yaml\n"
                f"  Prompt: shows/prompts/{ep.show_slug}_digest.txt\n"
                f"  Tracker: digests/{ep.show_slug}/{ep.show_slug}_content_tracker.json",
            ))

        # Check for chronic slow news mode by looking at recent metrics
        if counters.get("slow_news_mode"):
            output_dir = SHOW_REGISTRY.get(ep.show_slug, {}).get("output_dir", "")
            if output_dir:
                metrics_dir = PROJECT_ROOT / output_dir
                recent_slow = 0
                for d in range(1, 6):
                    prev_date = target_date - datetime.timedelta(days=d)
                    # Find any metrics file for that date
                    for mf in metrics_dir.glob(f"metrics_ep*.json"):
                        try:
                            m = json.loads(mf.read_text())
                            if m.get("counters", {}).get("slow_news_mode"):
                                recent_slow += 1
                                break
                        except Exception:
                            pass
                if recent_slow >= 3:
                    ep.issues.append(Issue(
                        ep.show_slug, ep.episode_num, "warning",
                        f"Chronic slow news mode ({recent_slow + 1} recent episodes)",
                        f"This show has been in slow news mode for {recent_slow + 1} of "
                        f"the last {recent_slow + 1} episodes. This may indicate stale RSS "
                        f"sources, an overly aggressive content tracker, or insufficient "
                        f"source diversity. Consider:\n"
                        f"  - Running a feed audit: python scripts/audit_feeds.py\n"
                        f"  - Adding more RSS sources to shows/{ep.show_slug}.yaml\n"
                        f"  - Expanding slow news segments: shows/segments/{ep.show_slug}.json\n"
                        f"  - Checking content tracker cooldown settings",
                    ))


# ---------------------------------------------------------------------------
# AI-powered review (optional, uses Grok)
# ---------------------------------------------------------------------------

# Known TTS phonetic artifacts — LLM-generated respellings intended as
# pronunciation hints.  These are cosmetic issues in the transcript copy,
# NOT factual errors in the audio (ElevenLabs pronounces the correct
# spelling correctly even when the transcript uses a phonetic form).
KNOWN_TTS_ARTIFACTS = {
    "nassa": "NASA",
    "nay-toe": "NATO",
    "nay toe": "NATO",
    "star-mer": "Starmer",
    "star mer": "Starmer",
    "chwen": "Qwen",
    "chwen three": "Qwen 3",
    "en-vidia": "Nvidia",
    "open-ay-eye": "OpenAI",
}


def flag_tts_artifacts(transcript_text: str) -> List[Dict]:
    """Identify likely TTS pronunciation artifacts in transcript text.

    Returns a list of ``{type, found, correct_spelling, severity}`` dicts.
    Reported at ``info`` severity so they surface in the review log without
    inflating the factual-error / warning counts.
    """
    found: List[Dict] = []
    if not transcript_text:
        return found
    lowered = transcript_text.lower()
    for artifact, correct in KNOWN_TTS_ARTIFACTS.items():
        if artifact in lowered:
            found.append({
                "type": "tts_artifact",
                "found": artifact,
                "correct_spelling": correct,
                "severity": "info",
            })
    return found


def check_tts_artifacts(ep: EpisodeReview) -> None:
    """Report TTS phonetic artifacts as info-level issues on the episode."""
    text = ep.tts_text or ep.digest_text or ""
    artifacts = flag_tts_artifacts(text)
    for art in artifacts:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "info",
            "TTS phonetic artifact",
            f"transcript contains '{art['found']}' (likely phonetic spelling of '{art['correct_spelling']}') — "
            f"cosmetic issue only, audio pronunciation is unaffected",
        ))


def _load_reviewer_settings(show_slug: str) -> tuple[str, int, float]:
    """Return (model, max_tokens, temperature) for reviewing this show.

    Reads the show's YAML so the reviewer inherits ``llm.reviewer_*`` from
    ``shows/_defaults.yaml`` (or any per-show override). Falls back to
    the historical hardcoded values if the config can't be loaded.
    """
    default_model = "grok-4-1-fast-non-reasoning"
    default_tokens = 1500
    default_temp = 0.3
    try:
        from engine.config import load_config
        cfg = load_config(PROJECT_ROOT / "shows" / f"{show_slug}.yaml")
        llm = cfg.llm
        return (
            getattr(llm, "reviewer_model", "") or default_model,
            int(getattr(llm, "reviewer_max_tokens", 0) or default_tokens),
            float(getattr(llm, "reviewer_temperature", 0.0) or default_temp),
        )
    except Exception:
        return default_model, default_tokens, default_temp


def ai_review_episode(ep: EpisodeReview) -> None:
    """Use Grok to review episode quality. Requires GROK_API_KEY."""
    api_key = (os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY") or "").strip()
    if not api_key:
        return

    text = ep.tts_text or ep.digest_text
    if not text:
        return

    # Truncate to avoid massive prompts — the AI reviewer only needs enough
    # text to assess quality, not the full transcript.  Truncate at a
    # sentence boundary to avoid mid-word cuts that confuse the reviewer.
    _REVIEW_CHAR_LIMIT = 12000
    _was_truncated = len(text) > _REVIEW_CHAR_LIMIT
    if _was_truncated:
        # Find the last sentence-ending punctuation before the limit
        truncated = text[:_REVIEW_CHAR_LIMIT]
        for end_char in [". ", ".\n", "! ", "!\n", "? ", "?\n"]:
            last_pos = truncated.rfind(end_char)
            if last_pos > _REVIEW_CHAR_LIMIT * 0.8:  # Don't cut too aggressively
                truncated = truncated[:last_pos + 1]
                break
        text = truncated + "\n\n[END OF REVIEW EXCERPT — full episode continues beyond this point]"

    prompt = (
        f"You are a podcast quality reviewer. Review this episode of '{ep.show_name}' "
        f"(Episode {ep.episode_num}, {ep.date}).\n\n"
        f"IMPORTANT CONTEXT: Today's date is {ep.date}. This is a valid, real date. "
        f"Do NOT flag the date itself as a factual error. These episodes are AI-generated "
        f"daily podcasts — the date and year are correct by definition.\n\n"
        f"CURRENT-REALITY GROUNDING (as of 2026): use these as your reference point "
        f"when judging factual accuracy. Do NOT flag any of the following as errors:\n"
        f"- US President: Donald Trump (inaugurated January 2025 for his second term)\n"
        f"- US Vice President: JD Vance\n"
        f"- UK Prime Minister: Keir Starmer (Labour)\n"
        f"- Canadian Prime Minister: check the episode content — leadership changed in 2025\n"
        f"Focus factual checks on VERIFIABLE content claims: numerical figures, scientific "
        f"facts, company/product details, dates of events, corporate announcements. Political "
        f"figures in their actual current roles are not errors. If a claim simply contradicts "
        f"your pre-2024 training data but is consistent with current 2026 reality, do NOT "
        f"flag it.\n\n"
        f"{'NOTE: The text below is a REVIEW EXCERPT that ends with [END OF REVIEW EXCERPT]. The full episode is LONGER than what you see here. Do NOT flag the episode as incomplete or abruptly ending. ONLY flag INCOMPLETE if the content itself contains obvious signs of being cut off mid-sentence within the body of the text.' if _was_truncated else ''}\n\n"
        f"TEXT:\n{text}\n\n"
        f"Check for these specific problems and rate each YES or NO:\n"
        f"1. FACTUAL_ERRORS: Are there obvious factual errors or contradictions? "
        f"(Do NOT flag the episode date or year as an error.)\n"
        f"2. INCOHERENT: Are there sections that don't make sense or seem garbled?\n"
        f"3. REPETITIVE: Are stories or paragraphs repeated verbatim or near-verbatim?\n"
        f"4. OFF_TOPIC: Is significant content unrelated to the show's topic?\n"
        f"5. TONE_BREAK: Are there abrupt tone shifts or inappropriate language?\n"
        f"6. INCOMPLETE: Does the episode feel like it ends abruptly or is missing sections?\n"
        f"7. QUALITY_SCORE: Rate overall quality 1-10 (1=terrible, 10=perfect)\n\n"
        f"Format your response EXACTLY like this (one per line):\n"
        f"FACTUAL_ERRORS: YES/NO — [brief explanation if YES]\n"
        f"INCOHERENT: YES/NO — [brief explanation if YES]\n"
        f"REPETITIVE: YES/NO — [brief explanation if YES]\n"
        f"OFF_TOPIC: YES/NO — [brief explanation if YES]\n"
        f"TONE_BREAK: YES/NO — [brief explanation if YES]\n"
        f"INCOMPLETE: YES/NO — [brief explanation if YES]\n"
        f"QUALITY_SCORE: [1-10]\n"
        f"SUMMARY: [1-2 sentence overall assessment]\n"
    )

    reviewer_model, reviewer_max_tokens, reviewer_temperature = _load_reviewer_settings(ep.show_slug)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1", timeout=120)
        resp = client.chat.completions.create(
            model=reviewer_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=reviewer_temperature,
            max_tokens=reviewer_max_tokens,
        )
        review_text = resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("AI review failed for %s Ep%d: %s", ep.show_slug, ep.episode_num, exc)
        return

    # Parse AI review
    quality_score = 0
    m = re.search(r"QUALITY_SCORE:\s*(\d+)", review_text)
    if m:
        quality_score = int(m.group(1))

    summary_m = re.search(r"SUMMARY:\s*(.+)", review_text)
    summary = summary_m.group(1).strip() if summary_m else ""

    # Flag critical AI findings
    critical_checks = ["FACTUAL_ERRORS", "INCOHERENT", "REPETITIVE"]
    for check in critical_checks:
        m = re.search(rf"{check}:\s*YES\s*[—–-]\s*(.+)", review_text)
        if m:
            severity = "critical" if check in ("INCOHERENT", "REPETITIVE") else "warning"
            ep.issues.append(Issue(
                ep.show_slug, ep.episode_num, severity,
                f"AI review: {check.replace('_', ' ').title()}",
                m.group(1).strip(),
            ))

    warning_checks = ["OFF_TOPIC", "TONE_BREAK", "INCOMPLETE"]
    for check in warning_checks:
        m = re.search(rf"{check}:\s*YES\s*[—–-]\s*(.+)", review_text)
        if m:
            ep.issues.append(Issue(
                ep.show_slug, ep.episode_num, "warning",
                f"AI review: {check.replace('_', ' ').title()}",
                m.group(1).strip(),
            ))

    if quality_score > 0 and quality_score <= 3:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "critical",
            f"AI quality score: {quality_score}/10",
            f"Grok rated this episode {quality_score}/10. {summary}",
        ))
    elif quality_score > 0 and quality_score <= 5:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "warning",
            f"AI quality score: {quality_score}/10",
            f"Grok rated this episode {quality_score}/10. {summary}",
        ))
    elif quality_score > 0:
        ep.issues.append(Issue(
            ep.show_slug, ep.episode_num, "info",
            f"AI quality score: {quality_score}/10",
            summary,
        ))


# ---------------------------------------------------------------------------
# GitHub issue creation
# ---------------------------------------------------------------------------

def create_github_issue(
    target_date: str,
    episodes: List[EpisodeReview],
    critical_only: bool = False,
    missed_issues: Optional[List[Issue]] = None,
) -> Optional[str]:
    """Create a GitHub issue summarizing today's review.

    Returns the issue URL on success, None if no issues to report or gh fails.
    """
    all_issues: List[Issue] = list(missed_issues or [])
    for ep in episodes:
        all_issues.extend(ep.issues)

    if critical_only:
        all_issues = [i for i in all_issues if i.severity == "critical"]

    if not all_issues:
        return None

    critical = [i for i in all_issues if i.severity == "critical"]
    warnings = [i for i in all_issues if i.severity == "warning"]
    infos = [i for i in all_issues if i.severity == "info"]

    # Build issue title
    n_shows = len(set(i.show for i in all_issues))
    if critical:
        title = f"Daily Review {target_date}: {len(critical)} critical issue(s) across {n_shows} show(s)"
    else:
        title = f"Daily Review {target_date}: {len(warnings)} warning(s) across {n_shows} show(s)"

    # Separate missed/skipped episode issues from per-episode issues
    _missed = [i for i in all_issues if i.episode == 0 and "Missed episode" in i.title]
    _skipped = [i for i in all_issues if i.episode == 0 and "Skipped episode" in i.title]
    _missed_shows = {i.show for i in _missed} | {i.show for i in _skipped}

    # Build issue body
    body_lines = [
        f"## Daily Episode Review — {target_date}\n",
        f"**Episodes reviewed:** {len(episodes)}",
    ]
    if _missed:
        body_lines.append(f"**Missed episodes:** {len(_missed)} show(s) failed to produce output")
    if _skipped:
        body_lines.append(f"**Skipped episodes:** {len(_skipped)} show(s) intentionally skipped")
    body_lines.append(
        f"**Issues found:** {len(critical)} critical, {len(warnings)} warning(s), {len(infos)} info\n"
    )

    # Missed episodes section (before the episodes table)
    if _missed:
        body_lines.append("### Missed Episodes\n")
        body_lines.append(
            "These shows were scheduled to produce an episode today but no output was found:\n"
        )
        for issue in _missed:
            show_name = SHOW_REGISTRY.get(issue.show, {}).get("name", issue.show)
            body_lines.append(f"- **{show_name}** (`{issue.show}`): {issue.detail}")
        body_lines.append("")

    # Skipped episodes section
    if _skipped:
        body_lines.append("### Skipped Episodes\n")
        body_lines.append(
            "These shows ran but intentionally skipped episode production:\n"
        )
        for issue in _skipped:
            show_name = SHOW_REGISTRY.get(issue.show, {}).get("name", issue.show)
            body_lines.append(f"- **{show_name}** (`{issue.show}`): {issue.detail}")
        body_lines.append("")

    # Episodes summary table
    body_lines.append("### Episodes Reviewed\n")
    body_lines.append("| Show | Episode | Issues |")
    body_lines.append("|------|---------|--------|")
    for ep in episodes:
        n_crit = sum(1 for i in ep.issues if i.severity == "critical")
        n_warn = sum(1 for i in ep.issues if i.severity == "warning")
        status = ""
        if n_crit:
            status = f"{n_crit} critical"
        if n_warn:
            status += f"{', ' if status else ''}{n_warn} warning(s)"
        if not status:
            status = "OK"
        body_lines.append(f"| {ep.show_name} | Ep{ep.episode_num:03d} | {status} |")

    # Critical issues (exclude missed episodes — they have their own section)
    _ep_critical = [i for i in critical if i not in _missed]
    if _ep_critical:
        body_lines.append("\n### Critical Issues\n")
        body_lines.append("These episodes may need to be removed from the RSS feed:\n")
        for issue in _ep_critical:
            body_lines.append(f"- **[{issue.show} Ep{issue.episode:03d}]** {issue.title}")
            body_lines.append(f"  {issue.detail}")

    # Warnings
    if warnings:
        body_lines.append("\n### Warnings\n")
        body_lines.append("Issues to address in future episodes:\n")
        for issue in warnings:
            body_lines.append(f"- **[{issue.show} Ep{issue.episode:03d}]** {issue.title}")
            body_lines.append(f"  {issue.detail}")

    # Info
    if infos:
        body_lines.append("\n### Info\n")
        for issue in infos:
            body_lines.append(f"- **[{issue.show} Ep{issue.episode:03d}]** {issue.title}")
            body_lines.append(f"  {issue.detail}")

    body_lines.append(f"\n---\n*Auto-generated by `review_episodes.py`*")

    body = "\n".join(body_lines)

    # Assign labels
    labels = ["automated-review"]
    if critical:
        labels.append("severity: critical")
    if warnings:
        labels.append("severity: warning")

    # Ensure labels exist (auto-create if missing)
    _label_colors = {
        "automated-review": "c5def5",
        "severity: critical": "d73a4a",
        "severity: warning": "fbca04",
    }
    for label in labels:
        try:
            subprocess.run(
                ["gh", "label", "create", label, "--color", _label_colors.get(label, "ededed"), "--force"],
                capture_output=True, text=True, timeout=10,
            )
        except Exception:
            pass  # Best-effort; issue creation will still work without labels

    # Create via gh CLI
    label_args = " ".join(f'--label "{l}"' for l in labels)
    try:
        result = subprocess.run(
            [
                "gh", "issue", "create",
                "--title", title,
                "--body", body,
                *[arg for l in labels for arg in ("--label", l)],
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            logger.info("Created GitHub issue: %s", url)
            return url
        else:
            logger.warning("gh issue create failed: %s", result.stderr.strip())
            return None
    except FileNotFoundError:
        logger.warning("gh CLI not found — skipping issue creation")
        return None
    except Exception as exc:
        logger.warning("Failed to create GitHub issue: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Auto-close stale missed-episode issues
# ---------------------------------------------------------------------------

# Issue title shapes created by ``create_github_issue``:
#   ``Daily Review YYYY-MM-DD: N critical issue(s) across M show(s)``
#   ``Daily Review YYYY-MM-DD: N warning(s) across M show(s)``
_DAILY_TITLE_RE = re.compile(
    r"^Daily Review (\d{4}-\d{2}-\d{2}): \d+ "
    r"(?:critical issue|warning)\(s\) across \d+ show\(s\)"
)

# Body shape used by ``create_github_issue`` for missed-episode lines:
#   ``- **Show Name** (`slug`): detail text...``
# Captures the slug — matching only when the show was reported as missed
# (not just any boldface mention).
_MISSED_SHOW_RE = re.compile(r"^- \*\*[^*]+\*\* \(`([^`]+)`\):", re.MULTILINE)


def _has_per_episode_findings(body: str) -> bool:
    """Heuristic: did the issue body include any per-episode rows?

    The Episodes Reviewed section uses a markdown table; an issue with no
    per-episode findings has the header row but no data rows. We look for
    a row that starts with ``| `` and is not the header / separator.
    """
    in_episodes_section = False
    for line in body.splitlines():
        stripped = line.strip()
        if "Episodes Reviewed" in stripped:
            in_episodes_section = True
            continue
        if in_episodes_section and stripped.startswith("|"):
            # Skip header (`| Show | …`) and divider (`|---|---|---|`).
            if stripped.startswith("| Show ") or set(stripped) <= set("|-: "):
                continue
            return True
    return False


def close_resolved_missed_episode_issues(today: datetime.date) -> int:
    """Close prior daily-review issues whose missed shows have since shipped.

    Operator caught (May 7 2026) issue #330 staying open after the
    underlying infrastructure bug was fixed and tomorrow's runs would
    have re-shipped the missed shows. Manual issue cleanup is busywork;
    auto-close keeps the issue queue meaningful.

    Conservative gates:
      * Title must match the daily-review template.
      * Issue must be from a date strictly BEFORE *today* — never auto-
        close today's issue (today's review is happening now).
      * Body must have NO per-episode findings (only missed-episode lines).
        Per-episode issues might still need human action even if the show
        replayed; leave them.
      * Every missed slug listed in the body must now have at least one
        ``*{date}.md`` file in its output directory (i.e. the run replayed).

    Returns the number of issues closed.
    """
    if not subprocess:  # pragma: no cover — defensive
        return 0

    try:
        # gh issue list returns JSON with at most 30 issues by default.
        # We only need open daily-review issues, so the label filter
        # keeps the page small.
        result = subprocess.run(
            [
                "gh", "issue", "list",
                "--state", "open",
                "--label", "automated-review",
                "--json", "number,title,body,createdAt",
                "--limit", "50",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(
                "gh issue list failed (auto-close skipped): %s",
                result.stderr.strip()[:200],
            )
            return 0
        items = json.loads(result.stdout or "[]")
    except FileNotFoundError:
        logger.info("gh CLI not found — skipping auto-close.")
        return 0
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        logger.warning("Auto-close lookup failed: %s", exc)
        return 0

    closed = 0
    for issue in items:
        title = issue.get("title") or ""
        match = _DAILY_TITLE_RE.match(title)
        if not match:
            continue

        # Only consider issues from BEFORE today.
        try:
            issue_date = datetime.date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if issue_date >= today:
            continue

        body = issue.get("body") or ""
        if _has_per_episode_findings(body):
            continue  # Real per-episode finding survives — don't close.

        missed_slugs = _MISSED_SHOW_RE.findall(body)
        if not missed_slugs:
            continue  # Nothing concrete to verify — leave it.

        # Did every missed slug now produce output for its date?
        date_str = match.group(1).replace("-", "")
        all_replayed = True
        for slug in missed_slugs:
            info = SHOW_REGISTRY.get(slug)
            if not info:
                all_replayed = False
                break
            output_dir = PROJECT_ROOT / info["output_dir"]
            if not list(output_dir.glob(f"*{date_str}.md")):
                all_replayed = False
                break

        if not all_replayed:
            continue

        number = issue.get("number")
        comment = (
            f"Auto-closing — every missed show ({', '.join(missed_slugs)}) "
            f"on {match.group(1)} now has output committed to "
            f"`digests/<slug>/`. Resolved by replay or infrastructure fix."
        )
        try:
            close_result = subprocess.run(
                [
                    "gh", "issue", "close", str(number),
                    "--reason", "completed",
                    "--comment", comment,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if close_result.returncode == 0:
                logger.info("Auto-closed resolved issue #%s (%s)", number, match.group(1))
                closed += 1
            else:
                logger.warning(
                    "gh issue close failed for #%s: %s",
                    number, close_result.stderr.strip()[:200],
                )
        except Exception as exc:  # pragma: no cover — best-effort
            logger.warning("Failed to close issue #%s: %s", number, exc)

    if closed:
        logger.info("Auto-closed %d stale missed-episode issue(s)", closed)
    return closed


# ---------------------------------------------------------------------------
# Claude Code output format
# ---------------------------------------------------------------------------

def format_for_claude(
    target_date: str,
    episodes: List[EpisodeReview],
    missed_issues: Optional[List[Issue]] = None,
) -> str:
    """Format review results as a prompt you can paste directly into Claude Code.

    Groups issues by type with file paths and actionable instructions.
    """
    missed_issues = missed_issues or []
    all_issues: List[tuple[EpisodeReview, Issue]] = []
    for ep in episodes:
        for issue in ep.issues:
            all_issues.append((ep, issue))

    if not all_issues and not missed_issues:
        return (
            f"# Episode Review — {target_date}\n\n"
            f"All {len(episodes)} episodes passed review. No issues found."
        )

    critical = [(ep, i) for ep, i in all_issues if i.severity == "critical"]
    warnings = [(ep, i) for ep, i in all_issues if i.severity == "warning"]
    _missed_critical = [i for i in missed_issues if i.severity == "critical"]
    _missed_warnings = [i for i in missed_issues if i.severity == "warning"]

    lines = [
        f"Fix the following issues found by the daily episode review for {target_date}.",
        f"There are {len(critical) + len(_missed_critical)} critical and "
        f"{len(warnings) + len(_missed_warnings)} warning-level issues.",
        "",
    ]

    # Missed episodes section (genuine failures — no skip marker)
    if _missed_critical:
        lines.append("## Missed Episodes")
        lines.append("")
        for issue in _missed_critical:
            show_name = SHOW_REGISTRY.get(issue.show, {}).get("name", issue.show)
            lines.append(f"- **[CRITICAL] {show_name}** — {issue.detail}")
        lines.append("")
        lines.append(
            "Investigate the CI workflow logs for the above shows to determine "
            "why they failed. Check GitHub Actions run history, RSS feed health, "
            "and news source availability."
        )
        lines.append("")

    # Skipped episodes section (intentional skips — skip marker present)
    if _missed_warnings:
        lines.append("## Skipped Episodes")
        lines.append("")
        for issue in _missed_warnings:
            show_name = SHOW_REGISTRY.get(issue.show, {}).get("name", issue.show)
            lines.append(f"- **[WARNING] {show_name}** — {issue.detail}")
        lines.append("")

    # Group by issue type for efficient fixing
    issue_groups: dict[str, list[tuple[EpisodeReview, Issue]]] = {}
    for ep, issue in all_issues:
        if issue.severity == "info":
            continue
        key = issue.title.split(":")[0].strip() if ":" in issue.title else issue.title
        # Normalize similar titles
        if "word count" in key.lower() or "artifact" in key.lower():
            key = "LLM artifacts leaked into scripts"
        elif "missing section" in key.lower():
            key = "Missing required sections"
        elif "repetition" in key.lower():
            key = "Excessive repetition"
        elif "too short" in key.lower() or "below target" in key.lower() or "dangerously short" in key.lower():
            key = "Script/digest too short"
        elif "too long" in key.lower() or "unusually long" in key.lower():
            key = "Digest too long"
        elif "pipeline" in key.lower():
            key = "Pipeline failures"
        elif "audio" in key.lower():
            key = "Audio duration issues"
        elif "AI quality" in key.lower() or "AI review" in key.lower():
            key = "AI review findings"
        issue_groups.setdefault(key, []).append((ep, issue))

    for group_name, items in issue_groups.items():
        lines.append(f"## {group_name}")
        lines.append("")

        for ep, issue in items:
            severity_tag = "CRITICAL" if issue.severity == "critical" else "WARNING"
            lines.append(f"- **[{severity_tag}] {ep.show_name} Ep{ep.episode_num:03d}**")
            lines.append(f"  {issue.detail}")

            # Add file path for direct editing
            if issue.file_path:
                lines.append(f"  File: `{issue.file_path}`")
            elif ep.tts_path and ("script" in issue.title.lower() or "artifact" in issue.title.lower()):
                lines.append(f"  File: `{ep.tts_path}`")
            elif ep.digest_path:
                lines.append(f"  File: `{ep.digest_path}`")
            lines.append("")

    # Add context about what these episodes are
    lines.append("## Episodes reviewed")
    lines.append("")
    for ep in episodes:
        n_issues = len([i for i in ep.issues if i.severity != "info"])
        status = f"{n_issues} issue(s)" if n_issues else "OK"
        duration = ep.metrics.get("counters", {}).get("audio_duration_s")
        dur_str = f", {duration:.0f}s audio" if duration else ""
        lines.append(f"- {ep.show_name} Ep{ep.episode_num:03d} ({ep.date}{dur_str}): {status}")

    lines.append("")
    lines.append("## Fix Instructions")
    lines.append("")
    lines.append("For each issue above:")
    lines.append("1. Read the file listed for that issue")
    lines.append("2. Determine if the content is salvageable or needs regeneration")
    lines.append("3. For **LLM artifacts** (word counts, timing targets, section labels): "
                 "Edit the TTS script to remove the leaked text, then check if the same "
                 "pattern exists in the show's podcast prompt (shows/prompts/{slug}_podcast.txt) "
                 "and add it to the PRODUCTION NOTES 'do not include' list if missing")
    lines.append("4. For **cross-episode repetition**: Verify that {recent_content_summary} "
                 "is present in the show's digest prompt (shows/prompts/{slug}_digest.txt). "
                 "If missing, add it near the freshness instructions section")
    lines.append("5. For **broken RSS sources**: Remove the dead URL from the show's YAML "
                 "config (shows/{slug}.yaml) and add it to shows/_blocked_sources.yaml")
    lines.append("6. For **missed episodes**: Check GitHub Actions workflow logs for the "
                 "show's cron trigger. Common causes: pipeline timeout, LLM refusal, "
                 "repetition detector false positive, broken RSS sources")
    lines.append("7. For **critical quality issues** (score <=3, incoherent, extremely short): "
                 "Consider removing the episode from the RSS feed using edit-rss-episode.py")
    lines.append("")
    lines.append("Key files:")
    lines.append("- Show configs: shows/*.yaml")
    lines.append("- Digest prompts: shows/prompts/*_digest.txt")
    lines.append("- Podcast prompts: shows/prompts/*_podcast.txt")
    lines.append("- Content tracker: digests/{slug}/{slug}_content_tracker.json")
    lines.append("- Slow news segments: shows/segments/{slug}.json")
    lines.append("- Blocked sources: shows/_blocked_sources.yaml")
    lines.append("- Pipeline code: run_show.py, engine/generator.py, engine/validation.py")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_review(
    target_date: datetime.date,
    create_issues: bool = False,
    show_filter: str = "",
    output_format: str = "log",
) -> int:
    """Run the full review pipeline. Returns exit code."""
    logger.info("=== Episode Review for %s ===", target_date.isoformat())

    # Close any stale "missed episode" issues from prior days where the
    # affected shows have since shipped output. Operator caught (May 7
    # 2026) the queue accumulating issues that were resolved the next
    # morning; humans don't need to chase the cleanup. Best-effort —
    # failures here never block the actual review.
    if create_issues and not show_filter:
        try:
            close_resolved_missed_episode_issues(target_date)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("Auto-close encountered an error: %s", exc)

    episodes = discover_episodes(target_date, show_filter)

    # --- Missed episode detection ---
    missed_issues = check_missed_episodes(target_date, episodes, show_filter)
    if missed_issues:
        for issue in missed_issues:
            if issue.severity == "critical":
                logger.error("[CRITICAL] %s: %s", issue.title, issue.detail)
            else:
                logger.warning("[%s] %s: %s", issue.severity.upper(), issue.title, issue.detail)

    if not episodes and not missed_issues:
        logger.info("No episodes found for %s (and none expected)", target_date.isoformat())
        return 0

    logger.info("Found %d episode(s) to review", len(episodes))

    # Run all automated checks
    for ep in episodes:
        info = SHOW_REGISTRY.get(ep.show_slug, {})
        logger.info("Reviewing %s Ep%03d ...", ep.show_name, ep.episode_num)

        check_digest_length(ep, info)
        check_tts_script(ep, info)
        check_audio_duration(ep, info)
        check_pipeline_errors(ep)
        check_leaked_artifacts(ep)
        check_required_sections(ep, info)
        check_repetition(ep)
        check_transition_duplication(ep)
        check_slow_news_leakage(ep)
        check_intro_outro(ep)
        check_pipeline_metrics(ep)
        check_story_duplication(ep)
        check_tts_artifacts(ep)

    # Cross-episode checks
    check_cross_episode_duplicates(episodes)
    check_content_freshness(episodes, target_date)

    # Optional AI review
    if os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY"):
        for ep in episodes:
            ai_review_episode(ep)
    else:
        logger.info("Skipping AI review (no GROK_API_KEY)")

    # Report
    total_critical = sum(1 for i in missed_issues if i.severity == "critical")
    total_warnings = sum(1 for i in missed_issues if i.severity == "warning")
    for ep in episodes:
        n_crit = sum(1 for i in ep.issues if i.severity == "critical")
        n_warn = sum(1 for i in ep.issues if i.severity == "warning")
        n_info = sum(1 for i in ep.issues if i.severity == "info")
        total_critical += n_crit
        total_warnings += n_warn

        if ep.issues:
            logger.info(
                "%s Ep%03d: %d critical, %d warning(s), %d info",
                ep.show_name, ep.episode_num, n_crit, n_warn, n_info,
            )
            for issue in ep.issues:
                level = {"critical": logging.ERROR, "warning": logging.WARNING, "info": logging.INFO}
                logger.log(level.get(issue.severity, logging.INFO),
                           "  [%s] %s: %s", issue.severity.upper(), issue.title, issue.detail)
        else:
            logger.info("%s Ep%03d: OK", ep.show_name, ep.episode_num)

    # Claude Code output
    if output_format == "claude":
        print("\n" + "=" * 72)
        print("COPY BELOW THIS LINE INTO CLAUDE CODE")
        print("=" * 72 + "\n")
        print(format_for_claude(target_date.isoformat(), episodes, missed_issues))
        print("\n" + "=" * 72)
        print("COPY ABOVE THIS LINE INTO CLAUDE CODE")
        print("=" * 72)

    # Create GitHub issue if requested
    if create_issues:
        has_actionable = any(
            i.severity in ("critical", "warning")
            for ep in episodes for i in ep.issues
        ) or bool(missed_issues)
        if has_actionable:
            create_github_issue(target_date.isoformat(), episodes, missed_issues=missed_issues)
        else:
            logger.info("No actionable issues — skipping GitHub issue creation")

    # Summary
    n_missed = sum(1 for i in missed_issues if i.severity == "critical")
    n_skipped = sum(1 for i in missed_issues if i.severity == "warning")
    parts = [f"{len(episodes)} episode(s)"]
    if n_missed:
        parts.append(f"{n_missed} missed")
    if n_skipped:
        parts.append(f"{n_skipped} skipped")
    parts.extend([f"{total_critical} critical", f"{total_warnings} warning(s)"])
    logger.info("=== Review complete: %s ===", ", ".join(parts))

    if total_critical > 0:
        return 1
    elif total_warnings > 0:
        return 2
    return 0


def main():
    parser = argparse.ArgumentParser(description="Daily episode quality review")
    parser.add_argument(
        "--date",
        type=lambda s: datetime.date.fromisoformat(s),
        default=datetime.date.today(),
        help="Date to review (YYYY-MM-DD, default: today)",
    )
    parser.add_argument(
        "--create-issues",
        action="store_true",
        help="Create GitHub issues for problems found",
    )
    parser.add_argument(
        "--show",
        default="",
        help="Review only a specific show (slug)",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=["log", "claude"],
        default="log",
        help="Output format: 'log' (default) or 'claude' (paste-ready prompt for Claude Code)",
    )
    args = parser.parse_args()

    sys.exit(run_review(args.date, args.create_issues, args.show, args.output_format))


if __name__ == "__main__":
    main()
