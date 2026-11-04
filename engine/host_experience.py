"""Host-experience lines are not content (Oct 30 2026, Offshore North).

From Ep006 the Offshore North prompts REQUIRED one line a week drawn from
the host's own life (the airline flight deck, a wing foil on Georgian Bay,
Lasers and Hobies, family charters), named in the brief as "Dan's lens". A
listener review of Ep011 ("The RORC Transatlantic pairs weather-routing
decisions across the North Atlantic with the same pressure systems I read
from the flight deck.") found them too brief and without context: they
confused people. The prompts no longer ask for them, and the network rule
for an instruction a model may keep following is code: this module removes
such a sentence from the digest and the script.

A sentence is a host-experience line when it speaks in the first person or
names Dan AND mentions one of his frames, or when it is the brief's
"Dan's lens" label. A ``Source:`` tail on the same line is kept, so an
item never loses its citation. Opt-in per show (``host_experience_filter``).

Nov 3 2026 (Env Intel): a second MODE, ``experience``. Env Intel's digest
prompt had asked for "the wisdom that comes from experience" and supplied
the line it wanted, and five of the last six episodes narrated an invented
consulting career in the first person to a professional audience — "The
mistake I see most often is…", "In my experience advising on these files",
"I've seen teams rely on these records" — from a host who is not an
environmental consultant and from no source. The prompt no longer asks;
this mode removes the sentence when the model writes one anyway. It is a
closed set of first-person PROFESSIONAL-EXPERIENCE shapes (a mistake the
host "sees", "in my experience", "I've seen", "my clients" / "my sites",
"told me early in my career"); an opinion ("What I find interesting",
"In my view"), a recommendation ("I'd recommend") and the network's spoken
disclosure ("synthesis of my voice — … my own") are never touched. A bare
"I" is never a cue: "Phase I ESA" carries one in every digest. Calibrated
on every committed Env Intel digest and script (``tests/
test_env_intel_sources_2026_11_03.py`` replays them) — re-run that sweep
before widening a pattern. ``host_experience_mode`` picks the mode;
``frames`` (the default) is the Offshore North path above, byte-identical.
"""

from __future__ import annotations

import re
from typing import Tuple

#: ``host_experience_mode`` values. ``frames``: Dan's frames + the "Dan's
#: lens" label (Offshore North). ``experience``: first-person professional
#: experience shapes (Env Intel).
HOST_EXPERIENCE_MODES = ("frames", "experience")

_PERSON_RE = re.compile(r"\b(?:I|I'm|I've|I'd|I'll|my|me|myself|Dan|Dan's)\b")
_FRAME_RE = re.compile(
    r"flight[- ]deck|cockpit|\b737\b|\bairline\b|\bpilot|\bI fly\b|\bI(?:'ve)? flown\b|"
    r"\bflying over\b|wing[- ]?foil|Georgian Bay|\bHobie|\bLasers?\b|bareboat|\bcharters?\b",
    re.IGNORECASE)
_LABEL_RE = re.compile(r"^\W*Dan(?:'s|’s)\s+lens\b", re.IGNORECASE)
_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=\S)")
_SOURCE_RE = re.compile(r"\s*\**Source:\**\s", re.IGNORECASE)

#: First-person professional-experience shapes (mode ``experience``). Every
#: alternative names the host as the one who saw, worked, advised or was
#: taught; none fires on "I" alone, on an opinion or on a recommendation.
_EXPERIENCE_RE = re.compile(
    # "The mistake I see most often is…", "The most common mistake I still
    # see in the field is…", "mistakes I keep running into".
    r"\bmistakes?\b[^.;:]{0,40}?\bI (?:still |keep |often |always )?"
    r"(?:see|saw|find|found|encounter|run into|come across|seeing|finding)\b"
    # "In my experience advising on these files", "in my twenty years".
    r"|\bin my (?:own )?(?:[\w-]+ )?(?:experience|practice|career|years?|time|work)\b"
    # "I've seen teams rely…", "I have worked on…", "I've used similar
    # insights…", "I've advised…", "I've audited / reviewed / signed off".
    r"|\bI(?:'ve| have|'d| had) (?:seen|watched|witnessed|worked|advised|audited|"
    r"reviewed|sampled|used|lost|spent|signed off|sat in|been on|been through)\b"
    # "every major project I see crossing desks", "sites I work on",
    # "clients I work with", "files I review".
    r"|\b(?:projects?|sites?|files?|clients?|teams?|submissions?|reports?|firms?)"
    r"\b[^.;:]{0,30}?\bI (?:see|saw|work|worked|advise|advised|serve|review|reviewed|"
    r"audit|audited|handle|handled)\b"
    # "my clients", "on my sites", "my own projects", "my field crews",
    # "early in my career", "my consulting practice".
    r"|\bmy (?:own )?(?:clients?|sites?|projects?|files?|teams?|crews?|"
    r"field (?:crews?|teams?|work)|consulting (?:work|practice)|practice|career)\b"
    # "here's something I wish someone had told me early in my career",
    # "a nuance I wish someone had drilled into me".
    r"|\b(?:told|taught|shown|drilled into|explained to) me\b"
    # "that I wish more junior practitioners understood".
    r"|\bI wish (?:more |every |all |the )?(?:junior|young|new|early-career)\b",
    re.IGNORECASE)


def is_experience_sentence(sentence: str) -> bool:
    """True for a first-person professional-experience claim (mode
    ``experience``): the host as the one who saw, worked or was taught."""
    s = (sentence or "").strip()
    return bool(s) and _EXPERIENCE_RE.search(s) is not None


def is_host_experience_sentence(sentence: str, mode: str = "frames") -> bool:
    s = (sentence or "").strip()
    if not s:
        return False
    if mode == "experience":
        return is_experience_sentence(s)
    if _LABEL_RE.search(s):
        return True
    return bool(_PERSON_RE.search(s) and _FRAME_RE.search(s))


def _split_source(line: str) -> Tuple[str, str]:
    m = _SOURCE_RE.search(line)
    if not m:
        return line, ""
    return line[:m.start()], line[m.start():].strip()


def strip_host_experience(text: str, mode: str = "frames") -> Tuple[str, int]:
    """Remove host-experience sentences. Returns ``(text, removed)``.

    Headings and fenced blocks are left alone. A line left with nothing but
    its ``Source:`` tail keeps the tail; a line left with nothing is dropped
    along with one blank line after it. ``mode`` is one of
    ``HOST_EXPERIENCE_MODES``; the default is the Offshore North path.
    """
    if mode not in HOST_EXPERIENCE_MODES:
        raise ValueError(
            f"host_experience_mode must be one of {HOST_EXPERIENCE_MODES}, got {mode!r}")
    if not text:
        return text, 0
    out: list = []
    removed = 0
    in_fence = False
    skip_blank = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            skip_blank = False
            continue
        if skip_blank and not line.strip():
            skip_blank = False
            continue
        skip_blank = False
        if in_fence or not line.strip() or line.lstrip().startswith("#"):
            out.append(line)
            continue
        indent = line[:len(line) - len(line.lstrip())]
        body, source = _split_source(line.strip())
        sentences = [s for s in _SENT_RE.split(body.strip()) if s]
        kept = [s for s in sentences if not is_host_experience_sentence(s, mode)]
        if len(kept) == len(sentences):
            out.append(line)
            continue
        removed += len(sentences) - len(kept)
        new = " ".join(kept + ([source] if source else [])).strip()
        if new:
            out.append(indent + new)
        else:
            skip_blank = True
    return "\n".join(out), removed
