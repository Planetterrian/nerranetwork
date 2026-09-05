"""Output-schema validators for the 8 editorial LLM passes (spec §7).

Each pass gets one validator; a failed validation triggers exactly one
strict retry in post_interview.py, after which the failure surfaces to
Patrick for a manual draft. Validators raise ``ValueError`` with a message
the retry prompt can quote.
"""

from __future__ import annotations

from typing import Any

# Show slugs the classifier may target (cross-show callouts / show fits).
# The two Mira-hosted interview shows are legitimate targets of each other
# (an Age of AI episode may call out Nerra Voices and vice versa) — the
# prompts don't offer a show its own slug, so self-callouts don't arise.
KNOWN_SHOWS = {
    "tesla", "omni_view", "fascinating_frontiers", "planetterrian",
    "env_intel", "models_agents", "models_agents_beginners",
    "finansy_prosto", "modern_investing", "privet_russian",
    "unintended_consequences", "first_principles", "spacex", "dp_pod",
    "age_of_ai", "nerra_voices",
}


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def validate_transcript_cleaned(value: Any) -> None:
    _require(isinstance(value, str), "expected plain text")
    _require(len(value.split()) >= 200,
             "cleaned transcript under 200 words — looks truncated")
    _require("MIRA:" in value and "GUEST:" in value,
             "cleaned transcript must keep MIRA:/GUEST: speaker labels")


def validate_chapter_markers(value: Any) -> None:
    _require(isinstance(value, list) and value, "expected a non-empty JSON array")
    last_start = -1.0
    for i, ch in enumerate(value):
        _require(isinstance(ch, dict), f"chapter {i} is not an object")
        for key in ("start", "title"):
            _require(key in ch, f"chapter {i} missing {key!r}")
        start = float(ch["start"])
        _require(start >= 0, f"chapter {i} start is negative")
        _require(start >= last_start, f"chapter {i} starts before chapter {i-1}")
        _require(str(ch["title"]).strip() != "", f"chapter {i} title empty")
        last_start = start


def validate_episode_notes(value: Any) -> None:
    _require(isinstance(value, str), "expected plain text")
    words = len(value.split())
    _require(100 <= words <= 900,
             f"episode notes {words} words — expected 100-900")


def validate_topical_show_fits(value: Any) -> None:
    _require(isinstance(value, list), "expected a JSON array of show slugs")
    unknown = [s for s in value if s not in KNOWN_SHOWS]
    _require(not unknown, f"unknown show slugs: {unknown} (valid: {sorted(KNOWN_SHOWS)})")


def validate_clip_suggestions(value: Any) -> None:
    _require(isinstance(value, list), "expected a JSON array")
    for i, clip in enumerate(value):
        _require(isinstance(clip, dict), f"clip {i} is not an object")
        for key in ("start", "end", "title", "why"):
            _require(key in clip, f"clip {i} missing {key!r}")
        _require(float(clip["end"]) > float(clip["start"]),
                 f"clip {i} end <= start")
        length = float(clip["end"]) - float(clip["start"])
        _require(10 <= length <= 180,
                 f"clip {i} is {length:.0f}s — expected 10-180s")


def validate_social_copy(value: Any) -> None:
    _require(isinstance(value, dict), "expected a JSON object")
    for platform in ("twitter", "linkedin", "instagram"):
        _require(platform in value and str(value[platform]).strip(),
                 f"missing/empty {platform!r} copy")
    _require(len(str(value["twitter"])) <= 280,
             "twitter copy exceeds 280 characters")


def validate_cross_show_callouts(value: Any) -> None:
    _require(isinstance(value, dict), "expected a JSON object keyed by show slug")
    unknown = [s for s in value if s not in KNOWN_SHOWS]
    _require(not unknown, f"unknown show slugs: {unknown}")
    for show, text in value.items():
        _require(isinstance(text, str) and 20 <= len(text) <= 400,
                 f"callout for {show!r} must be a 20-400 char string")


def validate_newsletter_draft(value: Any) -> None:
    _require(isinstance(value, str), "expected plain text/markdown")
    words = len(value.split())
    _require(200 <= words <= 1500,
             f"newsletter draft {words} words — expected 200-1500")


_VALIDATORS = {
    "transcript_cleaned": validate_transcript_cleaned,
    "chapter_markers": validate_chapter_markers,
    "episode_notes": validate_episode_notes,
    "topical_show_fits": validate_topical_show_fits,
    "clip_suggestions": validate_clip_suggestions,
    "social_copy": validate_social_copy,
    "cross_show_callouts": validate_cross_show_callouts,
    "newsletter_draft": validate_newsletter_draft,
}


def validate_pass_output(field: str, value: Any) -> None:
    validator = _VALIDATORS.get(field)
    if validator is None:
        raise ValueError(f"no validator registered for pass {field!r}")
    validator(value)
