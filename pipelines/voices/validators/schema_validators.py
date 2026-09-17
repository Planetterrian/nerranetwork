"""Output-schema validators for the 8 editorial LLM passes (spec §7).

Each pass gets one validator; a failed validation triggers exactly one
strict retry in post_interview.py, after which the failure surfaces to
Patrick for a manual draft. Validators raise ``ValueError`` with a message
the retry prompt can quote.
"""

from __future__ import annotations

import re
from typing import Any, Optional

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


# A two-track call is labelled MIRA:/GUEST:; a three-track call with the
# co-host in the room is labelled by name — "Mira:", "Patrick:", "John:" —
# because that is what the cleaning prompt asks for. Demanding the literal
# "GUEST:" failed every co-hosted interview twice and stored an empty
# transcript: John Capobianco's guest-review page went out with nothing to
# read on it (Sept 15 2026). What matters is that speaker labels survived,
# Mira is one of them, and somebody else is too.
_LABEL = re.compile(r"^\s*(?:\[\d{1,2}:\d{2}\]\s*)?([A-Z][A-Za-z.'\- ]{0,24}):",
                    re.MULTILINE)


_STAMP = re.compile(r"\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]")


def last_stamp_seconds(text: str) -> Optional[int]:
    """The last [mm:ss] or [h:mm:ss] timestamp in a transcript, in seconds."""
    last = None
    for m in _STAMP.finditer(text or ""):
        h, mm, ss = m.groups()
        last = (int(h) * 3600 + int(mm) * 60 + int(ss)) if ss else (int(h) * 60 + int(mm))
    return last


def validate_transcript_cleaned(value: Any, raw: Optional[str] = None) -> None:
    _require(isinstance(value, str), "expected plain text")
    _require(len(value.split()) >= 200,
             "cleaned transcript under 200 words — looks truncated")
    # Sept 17 2026: four episodes went out with the cleaned transcript
    # stopping at the model's output cap, around minute 25 of a 45-minute
    # conversation, and the guest review page showed half the interview.
    # The cleaned copy has to reach the end of the raw one.
    if raw:
        end_raw, end_clean = last_stamp_seconds(raw), last_stamp_seconds(value)
        if end_raw is not None:
            _require(end_clean is not None and end_clean >= end_raw - 90,
                     f"cleaned transcript ends at {end_clean}s but the raw one "
                     f"runs to {end_raw}s — truncated")
    labels = {m.group(1).strip().lower() for m in _LABEL.finditer(value)}
    _require("mira" in labels,
             "cleaned transcript must keep the speaker labels, Mira's included")
    _require(len(labels) >= 2,
             "cleaned transcript has only one speaker label — the guest's "
             "lines must keep theirs (GUEST: or their first name)")


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


def validate_pass_output(field: str, value: Any, raw: Optional[str] = None) -> None:
    validator = _VALIDATORS.get(field)
    if validator is None:
        raise ValueError(f"no validator registered for pass {field!r}")
    if field == "transcript_cleaned":
        validator(value, raw)
    else:
        validator(value)
