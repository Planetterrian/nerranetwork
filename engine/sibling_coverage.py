"""What a sister show already covered — data-side overlap guard (Sep 2026).

Three of the Sep 2026 new shows share a beat edge with an existing daily:
AI Chips & Data Centres with Models & Agents, MAG 7 Daily with Tesla Shorts
Time, Longevity Weekly with Planetterrian Daily. The plan
(docs/new_shows_plan_2026_09_22.md §1, "same-day sibling overlap") says the
boundary is written into the prompts AND enforced data-side where a
mechanism exists. This is the mechanism: the sister show's recent digest
headlines, handed to the new show's digest prompt as update-don't-retell
notes. It reads COMMITTED digests only (no LLM, no network), and never
raises — a missing directory is an empty block.

Same pattern as engine/story_recurrence.py and dp_pod's sibling-digest
context, narrower: headlines and dates only, because the writer needs to
know what was covered, not to be handed the prose to paraphrase.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent

_DATE_RE = re.compile(r"_(\d{8})\.md$")
# Item headings in committed digests: a whole-line bold heading, or a
# numbered/### heading. The trailing ": Outlet" is dropped.
_BOLD_HEADING_RE = re.compile(r"^\*\*(?!HOOK|Date|What You Need)(.+?)\*\*\s*$")
_HASH_HEADING_RE = re.compile(r"^#{3,4}\s+(?:\d+\)\s*)?(.+?)\s*$")
_SECTION_WORDS = {
    "top story", "top news", "model updates", "agent & tool developments",
    "practical & community", "things to try this week", "on the horizon",
    "community buzz", "the counterpoint", "market watch",
}


def _headline(raw: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", raw)   # flatten links
    # The outlet is the LAST ": "-separated part; a headline may contain one.
    text = text.rsplit(": ", 1)[0] if ": " in text else text
    return text.strip(" *:—-")


def recent_headlines(
    sibling_dir: str,
    *,
    days: int,
    today: _dt.date | None = None,
    max_items: int = 30,
    root: Path | None = None,
) -> List[Tuple[str, str]]:
    """(date, headline) pairs from the sibling's digests in the last *days*."""
    base = (root or ROOT) / sibling_dir
    if not base.is_dir():
        return []
    today = today or _dt.date.today()
    cutoff = today - _dt.timedelta(days=days)
    out: List[Tuple[str, str]] = []
    for md in sorted(base.glob("*.md"), reverse=True):
        m = _DATE_RE.search(md.name)
        if not m:
            continue
        try:
            d = _dt.datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            continue
        if d < cutoff or d > today:
            continue
        try:
            lines = md.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            hit = _BOLD_HEADING_RE.match(line) or _HASH_HEADING_RE.match(line)
            if not hit:
                continue
            head = _headline(hit.group(1))
            if len(head) < 12 or head.lower() in _SECTION_WORDS:
                continue
            if head.lower().startswith(("under the hood", "science deep dive",
                                        "engineering deep dive", "first principles")):
                continue
            out.append((d.isoformat(), head))
            if len(out) >= max_items:
                return out
    return out


def sibling_block(
    sibling_name: str,
    sibling_dir: str,
    *,
    days: int,
    lens: str,
    today: _dt.date | None = None,
    root: Path | None = None,
) -> str:
    """A prompt block listing what the sister show already told listeners.

    ``lens`` is one sentence saying what THIS show may still add — the
    boundary, stated as a rule, never as an example sentence to copy.
    """
    items = recent_headlines(sibling_dir, days=days, today=today, root=root)
    if not items:
        return ""
    lines = [
        f"### ALREADY COVERED BY {sibling_name.upper()} (sister show, last {days} "
        "day(s)) — instruction, do not include in output",
        f"Listeners of both shows heard these already. {lens} Never retell one of "
        "these as news; if today's articles carry a genuinely new fact about one, "
        "lead with that new fact.",
    ]
    lines += [f"- {d}: {h}" for d, h in items]
    return "\n".join(lines)
