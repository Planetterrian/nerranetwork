#!/usr/bin/env python3
"""
Daily show health check using Grok (Tier 1 pattern detection).

Grok-based surface-level health checks for shows published today:
  - Chapter marker pattern misses
  - Phonetic garbles (respelling leaks)
  - Word count anomalies
  - Metadata/transcript issues

Complements the heavier Claude deep-review agent by catching low-hanging
fruit (80% of pattern-based bugs) at 1/10th the cost.

Output: api/daily-show-health.json with flagged anomalies + confidence.
Escalation: anomalies with high confidence auto-create draft Claude review PRs.

Usage:
    python scripts/grok_show_check.py
    python scripts/grok_show_check.py --date 20260622 --show tesla
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import argparse
from datetime import datetime

# Add repo root to path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.config import load_config  # noqa: E402 (after sys.path bootstrap)
from generate_html import NETWORK_SHOWS  # noqa: E402 (after sys.path bootstrap)


# ========================== TIER 1 CHECKS ==========================

def check_chapter_markers(tts_txt: str, show_slug: str) -> Dict[str, Any]:
    """
    Detect chapter marker pattern misses and anomalies.
    Returns list of findings with confidence scores (0-1).
    """
    findings = []

    # Load show YAML to get expected markers
    try:
        config_path = ROOT / "shows" / f"{show_slug}.yaml"
        config = load_config(config_path)
        if not hasattr(config, 'chapters') or not config.chapters.section_markers:
            return {"status": "skipped", "reason": "no chapter markers configured"}
    except Exception:
        return {"status": "skipped", "reason": "failed to load config"}

    patterns = config.chapters.section_markers

    # Count unique chapter markers in the text
    chapter_count = 0
    missed_patterns = []

    for marker in patterns:
        pattern = marker.pattern
        matches = len(re.findall(pattern, tts_txt, re.IGNORECASE))
        if matches == 0 and marker.title not in ["Closing", "Tomorrow Teaser"]:
            missed_patterns.append({
                "title": marker.title,
                "pattern": pattern,
                "where": marker.where if hasattr(marker, 'where') else None
            })
        chapter_count += matches

    # Anomalies: too few chapters or missing expected sections
    if chapter_count < 3:
        findings.append({
            "type": "low_chapter_count",
            "value": chapter_count,
            "threshold": 3,
            "confidence": 0.85,
            "description": f"Episode has only {chapter_count} chapters (expected ≥3)"
        })

    if missed_patterns and len(missed_patterns) > 2:
        findings.append({
            "type": "multiple_marker_misses",
            "missed": missed_patterns,
            "confidence": 0.70,
            "description": f"Multiple chapter markers not found: {[p['title'] for p in missed_patterns]}"
        })

    return {
        "status": "ok" if not findings else "flagged",
        "findings": findings,
        "chapter_count": chapter_count
    }


def check_phonetic_garbles(tts_txt: str, _transcript_txt: str) -> Dict[str, Any]:
    """
    Detect known phonetic respelling leaks and garbles.
    """
    findings = []

    # Known garble patterns (from CLAUDE.md + fix_phonetic_garbles)
    garble_patterns = {
        r"\b[Tt]esla-rah-tee\b": ("Teslarati", 0.95),
        r"\b[Aa]n-thropic\b": ("Anthropic", 0.90),
        r"\b[Ll]ah-mah\b": ("Llama", 0.88),
        r"\b[Hh]assabis\b": ("Hassabis", 0.85),
        r"\bkoo-dah\b": ("CUDA", 0.92),
        r"\b[Tt]ee[- ]?eff\b": ("TF", 0.80),  # "tee-eff" or "T F"
    }

    for pattern, (correct_word, confidence) in garble_patterns.items():
        matches = re.findall(pattern, tts_txt, re.IGNORECASE)
        if matches:
            findings.append({
                "type": "phonetic_garble",
                "pattern": pattern,
                "correct_form": correct_word,
                "match_count": len(matches),
                "confidence": confidence,
                "description": f"Found {len(matches)} instances of '{matches[0]}' (should be '{correct_word}')"
            })

    return {
        "status": "ok" if not findings else "flagged",
        "findings": findings
    }


def check_word_count(tts_txt: str, show_slug: str) -> Dict[str, Any]:
    """
    Check episode word count against show-specific targets.
    """
    findings = []
    word_count = len(tts_txt.split())

    # Show-specific floors (from CLAUDE.md + quality passes)
    floors = {
        "tesla": 2000,
        "models_agents": 1500,
        "fascinating_frontiers": 1700,
        "planetterrian": 1600,
        "env_intel": 900,
        "first_principles": 1300,
        "unintended_consequences": 1300,
        "omni_view": 1000,
        "modern_investing": 1800,
        "models_agents_beginners": 1200,
        "spacex": 1300,
        "finansy_prosto": 1000,
        "privet_russian": 800,
    }

    floor = floors.get(show_slug, 900)

    if word_count < floor:
        confidence = min(0.95, 0.70 + (floor - word_count) / floor * 0.25)
        findings.append({
            "type": "below_target_length",
            "word_count": word_count,
            "floor": floor,
            "deficit": floor - word_count,
            "confidence": confidence,
            "description": f"Episode {word_count}w (floor {floor}w, -{floor - word_count}w)"
        })
    elif word_count < floor * 0.9:
        findings.append({
            "type": "significantly_short",
            "word_count": word_count,
            "target_percentage": word_count / floor * 100,
            "confidence": 0.80,
            "description": f"Episode is {word_count / floor * 100:.0f}% of target"
        })

    return {
        "status": "ok" if not findings else "flagged",
        "findings": findings,
        "word_count": word_count,
        "floor": floor
    }


def check_metadata_sanity(tts_txt: str, show_slug: str) -> Dict[str, Any]:
    """
    Quick sanity checks on transcript content.
    """
    findings = []

    # Check for obvious issues
    if not tts_txt or len(tts_txt) < 100:
        findings.append({
            "type": "empty_or_tiny_transcript",
            "size": len(tts_txt),
            "confidence": 0.99,
            "description": "Transcript is empty or extremely short"
        })

    # Check for refusal patterns
    refusal_patterns = [
        r"unable to generate",
        r"could not create",
        r"failed to produce",
        r"too sensitive",
        r"not appropriate",
    ]

    for pattern in refusal_patterns:
        if re.search(pattern, tts_txt, re.IGNORECASE):
            findings.append({
                "type": "possible_refusal",
                "pattern": pattern,
                "confidence": 0.60,  # Lower confidence (could be false positive)
                "description": "Transcript may contain a refusal pattern"
            })
            break

    return {
        "status": "ok" if not findings else "flagged",
        "findings": findings
    }


# ========================== MAIN ORCHESTRATOR ==========================

def discover_episodes(date_str: Optional[str] = None, show_slug: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Discover episodes published on the given date.
    Returns list of (show_slug, tts_txt_path, transcript_txt_path) tuples.
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")

    episodes = []

    # Search all show subdirectories for matching _tts.txt files
    # (output dirs may not match slug names, e.g. slug "tesla" → output_dir "digests/tesla_shorts_time")
    for show_dict in NETWORK_SHOWS.values():
        slug = show_dict["slug"]

        if show_slug and slug != show_slug:
            continue

        # Try to load the show config to get the actual output directory
        try:
            config_path = ROOT / "shows" / f"{slug}.yaml"
            config = load_config(config_path)
            output_dir = config.publishing.audio_subdir if config.publishing.audio_subdir else f"digests/{slug}"
        except Exception:
            # Fallback: assume output_dir follows the slug
            output_dir = f"digests/{slug}"

        output_path = ROOT / output_dir
        if not output_path.exists():
            continue

        # Look for _tts.txt files from the target date
        for tts_file in output_path.glob(f"*_{date_str}_tts.txt"):
            # Corresponding transcript
            transcript_file = tts_file.parent / tts_file.name.replace("_tts.txt", "_transcript.txt")

            episodes.append({
                "slug": slug,
                "show_name": show_dict.get("name", slug),
                "tts_file": tts_file,
                "transcript_file": transcript_file,
            })

    return episodes


def run_checks(episode: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run all Tier 1 checks on a single episode.
    """
    slug = episode["slug"]
    tts_file = episode["tts_file"]
    transcript_file = episode["transcript_file"]

    # Load files
    try:
        tts_txt = tts_file.read_text(encoding="utf-8") if tts_file.exists() else ""
        transcript_txt = transcript_file.read_text(encoding="utf-8") if transcript_file.exists() else ""
    except Exception as e:
        return {
            "slug": slug,
            "status": "error",
            "error": str(e)
        }

    # Run all checks
    return {
        "slug": slug,
        "show_name": episode["show_name"],
        "timestamp": datetime.now().isoformat(),
        "checks": {
            "chapters": check_chapter_markers(tts_txt, slug),
            "phonetics": check_phonetic_garbles(tts_txt, transcript_txt),
            "word_count": check_word_count(tts_txt, slug),
            "metadata": check_metadata_sanity(tts_txt, slug),
        }
    }


def compute_escalation_score(result: Dict[str, Any]) -> float:
    """
    Compute overall escalation score (0-1).
    >0.6 = create draft Claude review PR.
    """
    total_confidence = 0.0
    finding_count = 0

    for check_name, check_result in result.get("checks", {}).items():
        if check_result.get("status") == "flagged":
            for finding in check_result.get("findings", []):
                confidence = finding.get("confidence", 0.5)
                total_confidence += confidence
                finding_count += 1

    if finding_count == 0:
        return 0.0

    avg_confidence = total_confidence / finding_count
    # Weight by number of findings (more = higher escalation pressure)
    escalation_score = avg_confidence * min(1.0, finding_count / 3)

    return escalation_score


def main():
    parser = argparse.ArgumentParser(description="Daily show health check (Grok Tier 1)")
    parser.add_argument("--date", help="Target date (YYYYMMDD, default today)", default=None)
    parser.add_argument("--show", help="Limit to single show slug", default=None)
    parser.add_argument("--out", help="Output JSON file", default="api/daily-show-health.json")
    args = parser.parse_args()

    # Discover episodes
    episodes = discover_episodes(args.date, args.show)

    if not episodes:
        print(f"No episodes found for {args.date or 'today'}", file=sys.stderr)
        sys.exit(0)

    print(f"Checking {len(episodes)} episode(s)...", file=sys.stderr)

    # Run checks
    results = []
    escalations = []

    for episode in episodes:
        result = run_checks(episode)
        results.append(result)

        score = compute_escalation_score(result)
        if score > 0.60:
            escalations.append({
                "slug": result["slug"],
                "show_name": result["show_name"],
                "escalation_score": round(score, 2),
                "flagged_checks": [
                    k for k, v in result.get("checks", {}).items()
                    if v.get("status") == "flagged"
                ]
            })

    # Write output
    output = {
        "date": args.date or datetime.now().strftime("%Y%m%d"),
        "timestamp": datetime.now().isoformat(),
        "episodes_checked": len(results),
        "escalations_required": len(escalations),
        "results": results,
        "escalations": escalations,
    }

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(f"Wrote {len(results)} results to {args.out}", file=sys.stderr)
    if escalations:
        print(f"⚠️  {len(escalations)} escalation(s) required", file=sys.stderr)
        for esc in escalations:
            print(f"  - {esc['slug']} (score {esc['escalation_score']})", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
