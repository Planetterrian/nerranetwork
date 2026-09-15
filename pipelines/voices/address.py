"""How a guest is addressed on air.

Sept 15 2026. Mira called Dr. Adrian Wolfberg "Adrian" for an hour. A
first name is right for most guests and wrong for a scholar being
interviewed about their field: the courtesy costs nothing and its absence
is the first thing that listener notices. So an earned doctorate or
professorship is honoured unless the guest tells us otherwise.

Where the honorific comes from, in order:
1. ``guest_applications.honorific`` — set by hand, and the last word. The
   empty string is a decision too: it means "use my first name", which is
   how a guest who says "please just call me Adrian" is recorded.
2. The letters after their name or in their title — PhD, Ph.D., DPhil,
   Sc.D., Ed.D., MD, DVM, or a leading Dr./Doctor/Professor/Prof.

``spoken`` is what Mira says out loud ("Doctor Wolfberg"), ``written`` is
what a transcript label or an email uses ("Dr. Wolfberg"). A guest with no
honorific keeps their first name in both, which is what every episode so
far has done.
"""

from __future__ import annotations

import re
from typing import Any, Dict

# Written form -> spoken form. Mira reads "Dr." correctly most of the time
# and "Doctor" every time, and the narration prompts are read aloud.
_SPOKEN = {"Dr.": "Doctor", "Prof.": "Professor"}

_DOCTORATES = re.compile(
    r"(?:^|[\s,(])(?:ph\.?\s?d|d\.?phil|sc\.?d|ed\.?d|dr\.?p\.?h|"
    r"m\.?d|d\.?v\.?m|d\.?d\.?s|psy\.?d|j\.?s\.?d)\b",
    re.IGNORECASE)
_PROFESSOR = re.compile(r"\b(?:professor|prof\.)\b", re.IGNORECASE)
_DOCTOR_PREFIX = re.compile(r"^\s*(?:dr\.?|doctor)\s+", re.IGNORECASE)


def honorific(app: Dict[str, Any]) -> str:
    """"Dr.", "Prof." or "" — the written honorific for this guest."""
    if app is None:
        return ""
    if "honorific" in app and app.get("honorific") is not None:
        return str(app.get("honorific") or "").strip()
    haystack = " ".join(str(app.get(k) or "") for k in ("name", "title", "bio"))
    if _PROFESSOR.search(haystack):
        return "Prof."
    if _DOCTOR_PREFIX.search(str(app.get("name") or "")) or _DOCTORATES.search(haystack):
        return "Dr."
    return ""


def surname(app: Dict[str, Any]) -> str:
    name = _DOCTOR_PREFIX.sub("", str((app or {}).get("name") or "").strip())
    # Drop trailing credentials so "Adrian Wolfberg, PhD" does not become
    # "Doctor PhD".
    name = re.split(r"\s*,\s*", name)[0].strip()
    parts = [p for p in name.split() if p]
    return parts[-1] if len(parts) > 1 else (parts[0] if parts else "")


def first_name(app: Dict[str, Any]) -> str:
    name = _DOCTOR_PREFIX.sub("", str((app or {}).get("name") or "").strip())
    parts = [p for p in re.split(r"\s*,\s*", name)[0].split() if p]
    return parts[0] if parts else "Guest"


def written(app: Dict[str, Any]) -> str:
    """"Dr. Wolfberg", or the first name when there is no honorific."""
    h = honorific(app)
    last = surname(app)
    return f"{h} {last}" if h and last else first_name(app)


def spoken(app: Dict[str, Any]) -> str:
    """"Doctor Wolfberg" — the form Mira says out loud."""
    h = honorific(app)
    last = surname(app)
    if not h or not last:
        return first_name(app)
    return f"{_SPOKEN.get(h, h)} {last}"


def address_rule(app: Dict[str, Any]) -> str:
    """One line of instruction for a prompt that will be read aloud."""
    if not honorific(app):
        return (f"Address the guest as {first_name(app)} — their first name, "
                "warmly and naturally.")
    return (f"Address the guest as {spoken(app)}. They hold a doctorate, so "
            f"use it: {spoken(app)} on first address and whenever you name "
            "them, and their first name ONLY if they invite you to. If they "
            "say to call them by their first name, do it from that moment on "
            "and do not make a thing of it.")
