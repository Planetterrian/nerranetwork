#!/usr/bin/env python3
"""Validate a podcast show configuration and prompts for quality issues.

Catches the kinds of problems that made early shows mediocre:
- Wrong/missing TTS settings
- Thin prompts without quality gates
- Missing rejection criteria
- Generic audience definitions
- Uncustomized template placeholders

Usage:
    python validate_show.py <show_slug>
    python validate_show.py env_intel
    python validate_show.py --all           # Validate all shows
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SHOWS_DIR = PROJECT_ROOT / "shows"


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

class ValidationResult:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passes: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def ok(self, msg: str) -> None:
        self.passes.append(msg)

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def print_report(self, show_name: str) -> None:
        print(f"\n{'=' * 60}")
        print(f"  Validation Report: {show_name}")
        print(f"{'=' * 60}")

        for msg in self.passes:
            print(f"  [PASS] {msg}")
        for msg in self.warnings:
            print(f"  [WARN] {msg}")
        for msg in self.errors:
            print(f"  [FAIL] {msg}")

        total = len(self.passes) + len(self.warnings) + len(self.errors)
        print(f"\n  {len(self.passes)}/{total} passed, "
              f"{len(self.warnings)} warnings, {len(self.errors)} errors")

        if self.passed:
            print("\n  RESULT: PASS — show is ready for test run")
            print(f"  Next: python run_show.py <slug> --test")
        else:
            print("\n  RESULT: FAIL — fix errors before running")

        print()


def validate_yaml(yaml_path: Path, result: ValidationResult) -> dict | None:
    """Validate the YAML config file."""
    if not yaml_path.exists():
        result.error(f"Config file missing: {yaml_path}")
        return None

    try:
        import yaml
        with open(yaml_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        result.error(f"YAML parse error: {e}")
        return None

    result.ok(f"Config parses: {yaml_path.name}")

    # Check for uncustomized placeholders
    text = yaml_path.read_text()
    placeholders = re.findall(r"\{[A-Z_]{3,}\}", text)
    if placeholders:
        result.error(f"Uncustomized placeholders in YAML: {set(placeholders)}")
    else:
        result.ok("No uncustomized placeholders")

    # Check required top-level keys
    for key in ["name", "slug", "sources", "llm", "tts", "publishing", "episode"]:
        if key not in config:
            result.error(f"Missing required key: {key}")

    # Sources
    sources = config.get("sources", [])
    if len(sources) < 5:
        result.error(f"Only {len(sources)} RSS sources — need at least 10-15 for reliable daily content")
    elif len(sources) < 12:
        result.warn(f"Only {len(sources)} RSS sources — 12-20 recommended for consistent content")
    else:
        result.ok(f"{len(sources)} RSS sources configured")

    # Check for example.com placeholder URLs
    for s in sources:
        url = s.get("url", "")
        if "example.com" in url:
            result.error(f"Placeholder URL still present: {url}")
            break

    # Keywords
    keywords = config.get("keywords", [])
    if len(keywords) < 10:
        result.error(f"Only {len(keywords)} keywords — need at least 20-30 for good filtering")
    elif len(keywords) < 25:
        result.warn(f"Only {len(keywords)} keywords — 30-60 recommended")
    else:
        result.ok(f"{len(keywords)} keywords configured")

    # TTS settings
    tts = config.get("tts", {})
    voice_id = tts.get("voice_id", "")
    known_voices = {"dTrBzPvD2GpAqkk1MUzA", "ns7MjJ6c8tJKnvw7U6sN"}
    if voice_id not in known_voices:
        result.warn(f"Unknown voice ID: {voice_id} — verify it works with ElevenLabs")
    else:
        result.ok(f"Voice ID: {voice_id}")

    stability = tts.get("stability", 0)
    if stability < 0.35:
        result.error(f"TTS stability={stability} — too low, will sound robotic. Use 0.50-0.70.")
    elif stability < 0.50:
        result.warn(f"TTS stability={stability} — on the low side. 0.55-0.70 recommended.")
    else:
        result.ok(f"TTS stability={stability}")

    style = tts.get("style", 0)
    if style < 0.3:
        result.error(f"TTS style={style} — too low, will sound monotone/flat. Use 0.70-0.90.")
    elif style < 0.6:
        result.warn(f"TTS style={style} — low expressiveness. 0.70-0.90 recommended.")
    else:
        result.ok(f"TTS style={style}")

    similarity = tts.get("similarity_boost", 0)
    if similarity < 0.7:
        result.warn(f"TTS similarity_boost={similarity} — 0.85-0.95 recommended")
    else:
        result.ok(f"TTS similarity_boost={similarity}")

    # LLM
    llm = config.get("llm", {})
    model = llm.get("model", "")
    if "grok" not in model:
        result.warn(f"Non-standard model: {model}")
    else:
        result.ok(f"LLM model: {model}")

    # Episode output dir
    episode = config.get("episode", {})
    output_dir = episode.get("output_dir", "")
    if output_dir:
        full_path = PROJECT_ROOT / output_dir
        if not full_path.exists():
            result.warn(f"Output directory does not exist: {output_dir} — will be created on first run")
        else:
            result.ok(f"Output directory exists: {output_dir}")

    # publishing.rss_link — the <link> every podcast app and YouTube shows
    # as "the show's website". fascinating_frontiers pointed at
    # /fascinating_frontiers.html (underscores) while the generated page
    # is /fascinating-frontiers.html (hyphens), so that link 404'd in
    # every directory for months and showed up in Search Console. The
    # slug uses underscores and the page name uses hyphens, so this is an
    # easy one to get wrong again — check the file actually exists.
    publishing = config.get("publishing", {})
    rss_link = (publishing.get("rss_link") or "").strip()
    if rss_link:
        rel = rss_link.split("nerranetwork.com/", 1)[-1].split("?", 1)[0]
        target = PROJECT_ROOT / rel
        if rel and not target.is_file():
            hint = ""
            alt = PROJECT_ROOT / rel.replace("_", "-")
            if alt.is_file():
                hint = f" — did you mean /{rel.replace('_', '-')}?"
            result.error(f"publishing.rss_link 404s: {rss_link}{hint}")
        else:
            result.ok(f"rss_link resolves: /{rel}")

    return config


def validate_prompt(
    prompt_path: Path,
    prompt_type: str,
    result: ValidationResult,
) -> None:
    """Validate a digest or podcast prompt file for quality indicators."""
    if not prompt_path.exists():
        result.error(f"{prompt_type} prompt missing: {prompt_path}")
        return

    text = prompt_path.read_text()
    lines = text.strip().splitlines()
    line_count = len(lines)
    word_count = len(text.split())

    # Size checks
    if prompt_type == "Digest":
        if line_count < 30:
            result.error(f"{prompt_type} prompt is only {line_count} lines — too thin for quality output. "
                         "Aim for 60-120 lines with detailed section instructions.")
        elif line_count < 60:
            result.warn(f"{prompt_type} prompt is {line_count} lines — consider adding more detail. "
                        "The best prompts are 80-120 lines.")
        else:
            result.ok(f"{prompt_type} prompt: {line_count} lines, {word_count} words")
    else:  # Podcast
        if line_count < 25:
            result.error(f"{prompt_type} prompt is only {line_count} lines — too thin. "
                         "Aim for 50-80 lines with section timing and delivery instructions.")
        elif line_count < 45:
            result.warn(f"{prompt_type} prompt is {line_count} lines — consider adding more detail.")
        else:
            result.ok(f"{prompt_type} prompt: {line_count} lines, {word_count} words")

    # Check for remaining template instructions
    if "TEMPLATE INSTRUCTIONS" in text:
        result.error(f"{prompt_type} prompt still has template instruction block — "
                     "customize and delete it before first episode")

    # Check for uncustomized placeholders
    placeholders = re.findall(r"\{[A-Z_]{3,}\}", text)
    # Filter out legitimate template vars
    legit = {
        "{EXACT", "{URL", "{EXACT URL", "{SHOW_NAME", "{EPISODE_PREFIX",
    }
    suspicious = [p for p in placeholders if not any(p.startswith(l) for l in legit)]
    if suspicious:
        result.error(f"{prompt_type} prompt has uncustomized placeholders: {set(suspicious)}")

    # Quality indicator: audience definition
    text_lower = text.lower()
    has_audience = any(term in text_lower for term in [
        "audience", "reader", "listener", "professional", "they want",
        "they need", "their work", "their practice",
    ])
    if has_audience:
        result.ok(f"{prompt_type} prompt defines audience")
    else:
        result.warn(f"{prompt_type} prompt has no clear audience definition — "
                    "adding one dramatically improves output quality")

    # Quality indicator: rejection criteria
    has_rejection = any(term in text_lower for term in [
        "reject", "do not include", "exclude", "skip", "never pad",
        "do not use", "avoid including",
    ])
    if prompt_type == "Digest":
        if has_rejection:
            result.ok(f"{prompt_type} prompt has rejection criteria")
        else:
            result.error(f"{prompt_type} prompt has NO rejection criteria — "
                         "without these, the AI will pad with low-quality filler")

    # Quality indicator: "so what" / actionability
    has_so_what = any(term in text_lower for term in [
        "so what", "action", "implication", "means for", "practical",
        "this week", "concrete",
    ])
    if has_so_what:
        result.ok(f"{prompt_type} prompt emphasizes actionability")
    else:
        result.warn(f"{prompt_type} prompt doesn't emphasize actionability — "
                    "add 'so what' requirements for each item")

    # Quality indicator: anti-filler instructions
    has_anti_filler = any(term in text_lower for term in [
        "no filler", "no padding", "no vague", "be specific", "be direct",
        "skip it entirely", "shorter briefing",
    ])
    if has_anti_filler:
        result.ok(f"{prompt_type} prompt has anti-filler instructions")
    else:
        result.warn(f"{prompt_type} prompt lacks anti-filler instructions — "
                    "AI tends to pad without explicit 'no filler' rules")

    # Podcast-specific checks
    if prompt_type == "Podcast":
        # Check for timing targets
        has_timing = any(term in text_lower for term in [
            "seconds", "minute", "90-120", "60-90", "30-45",
        ])
        if has_timing:
            result.ok(f"{prompt_type} prompt has section timing targets")
        else:
            result.warn(f"{prompt_type} prompt has no timing targets — "
                        "sections will be unbalanced without time guidance")

        # Check for host persona
        has_persona = any(term in text_lower for term in [
            "host:", "persona", "experience", "authority", "expert",
        ])
        if has_persona:
            result.ok(f"{prompt_type} prompt defines host persona")
        else:
            result.error(f"{prompt_type} prompt has no host persona — "
                         "this makes the podcast sound generic and robotic")

        # Check for speaker prefix instruction
        has_prefix = 'start every line with "host:"' in text_lower or "host:" in text_lower
        if has_prefix:
            result.ok(f"{prompt_type} prompt uses 'Host:' prefix for script lines")
        else:
            result.warn(f"{prompt_type} prompt should instruct AI to use 'Host:' prefix")

        # Check that no personal names are used for host
        # Common pattern: "Patrick" was hardcoded in early shows
        name_pattern = re.search(r"(?i)\bI'm\s+[A-Z][a-z]+\b", text)
        if name_pattern:
            result.warn(f"{prompt_type} prompt may have a hardcoded host name: '{name_pattern.group()}' — "
                        "use generic 'Host:' prefix instead")


def validate_show(slug: str) -> bool:
    """Run all validation checks for a show. Returns True if passed."""
    result = ValidationResult()

    yaml_path = SHOWS_DIR / f"{slug}.yaml"
    config = validate_yaml(yaml_path, result)

    if config:
        llm = config.get("llm", {})

        digest_file = llm.get("digest_prompt_file", f"shows/prompts/{slug}_digest.txt")
        digest_path = PROJECT_ROOT / digest_file
        validate_prompt(digest_path, "Digest", result)

        podcast_file = llm.get("podcast_prompt_file", f"shows/prompts/{slug}_podcast.txt")
        podcast_path = PROJECT_ROOT / podcast_file
        validate_prompt(podcast_path, "Podcast", result)

    show_name = config.get("name", slug) if config else slug
    result.print_report(show_name)

    return result.passed


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python validate_show.py <show_slug>")
        print("       python validate_show.py --all")
        print()
        print("Available shows:")
        for p in sorted(SHOWS_DIR.glob("*.yaml")):
            if p.name != "show_template.yaml":
                print(f"  {p.stem}")
        sys.exit(1)

    if sys.argv[1] == "--all":
        slugs = [p.stem for p in sorted(SHOWS_DIR.glob("*.yaml"))]
        all_passed = True
        for slug in slugs:
            if not validate_show(slug):
                all_passed = False
        sys.exit(0 if all_passed else 1)
    else:
        slug = sys.argv[1]
        passed = validate_show(slug)
        sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
