"""Omni View Top World News hooks (docs/new_shows_plan_2026_09_22.md §4.8).

Runs after the five regional desks. pre_fetch reads TODAY's committed desk
digests (a desk that skipped or has not published is simply absent — the
Nerra Daily pattern) and supplies:

- hook ARTICLES for each desk's Lead and first Across the Region item:
  headline + the ORIGINAL publisher URL and nothing else. No desk prose goes
  into an article, so the full-text fetch reads the publisher's page and the
  claims gate verifies against it — never against a sibling digest.
- a ranking note (hook_context) listing every desk item with the desk's
  one-paragraph summary: what each region led with today. It says plainly
  that facts come from the numbered articles only.

Without desk data Top World is still a valid show on its own world feeds.
Memory is off (the desks carry the arcs). Every step is non-fatal.
"""

from __future__ import annotations

import datetime as _dt
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.omni_desks import DESKS, desk_items

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Desk items per desk that become hook articles (Lead + first regional
#: item). run_show caps hook articles at 12 (MAX_HOOK_ARTICLES_FOR_LLM).
ARTICLES_PER_DESK = 2


def todays_desk_digests(root: Path, date: _dt.date) -> List[Tuple[object, str]]:
    """(desk, digest text) for every desk that published on *date*."""
    stamp = date.strftime("%Y%m%d")
    out = []
    for d in DESKS:
        ddir = root / "digests" / d.slug
        if (ddir / f".skip_{stamp}.json").exists():
            continue
        hits = sorted(ddir.glob(f"{d.prefix}_Ep*_{stamp}.md"))
        if not hits:
            continue
        try:
            out.append((d, hits[-1].read_text(encoding="utf-8")))
        except OSError:
            continue
    return out


def intake_line(desks_live: int, desks_total: int) -> str:
    """The sentence the digest's WYNTK ends on — data-side, never typed.

    Top World is assembled from whichever desks published before it ran
    (plan §3.9 "intake honesty"): the reader is told how many, in the
    show's own words, and the number is the count of desk digests read."""
    if desks_live <= 0:
        return "This edition was drawn from the world feeds alone; no regional desk had published by press time."
    if desks_live >= desks_total:
        return f"This edition draws on all {desks_total} Omni View regional desks."
    return (f"This edition draws on {desks_live} of the {desks_total} Omni View regional desks "
            "live by press time.")


def edition_note(date: _dt.date) -> str:
    """Saturday is the single-story edition (The Intelligence's weekend
    shape, plan §2k); every other day is The Ten. The model never reads a
    calendar — the hook says which edition today is."""
    if date.weekday() == 5:
        return ("### EDITION (instruction — do not include in output)\n"
                "Today is Saturday: the single-story edition. Under `### The Ten` write "
                "ONE story — the week's most consequential — in 350-500 words with the "
                "week's context from the articles above, then Both Sides and Progress "
                "Watch as usual. No list of ten today.")
    return ("### EDITION (instruction — do not include in output)\n"
            "Today is a weekday edition: The Ten, ranked, items one to five developed "
            "and six to ten one sentence each.")


def build_payload(root: Path, date: _dt.date) -> Dict[str, object]:
    articles: List[Dict[str, str]] = []
    lines: List[str] = []
    live = todays_desk_digests(root, date)
    desks_live = 0
    for d, text in live:
        items = desk_items(text)
        if not items:
            continue
        desks_live += 1
        lines.append(f"{d.region}:")
        for n, it in enumerate(items):
            lines.append(f"- [{it['section']}] {it['title']} — {it['summary']} ({it['url']})")
            if n < ARTICLES_PER_DESK:
                articles.append({
                    "title": it["title"],
                    "url": it["url"],
                    "source_name": it["outlet"] or d.name,
                    "published_date": date.isoformat(),
                })
    intake = intake_line(desks_live, len(DESKS))
    metrics = {"desks_live_at_publish": desks_live, "desks_total": len(DESKS)}
    if not lines:
        note = (
            "### TODAY'S REGIONAL DESKS (instruction — do not include in output)\n"
            "No regional desk had published when this edition was assembled. The "
            "intake line for the end of What You Need to Know is, copied as given: "
            + intake + "\n\n" + edition_note(date)
        )
        return {"articles": [], "hook_context": note, "metrics": metrics}
    note = (
        "### TODAY'S REGIONAL DESKS (instruction — do not include in output)\n"
        "The Omni View regional desks published these today. Use them to judge "
        "what matters most in each region and to RANK The Ten. Every fact you "
        "write comes from the numbered articles above (the desks' leading "
        "stories are among them under their original publisher URLs); a "
        "detail that appears only in this note is left out.\n" + "\n".join(lines)
        + "\n\nThe intake line for the end of What You Need to Know is, copied as given: "
        + intake + "\n\n" + edition_note(date)
    )
    return {"articles": articles, "hook_context": note, "metrics": metrics}


def pre_fetch(config, *, episode_num=None, today_str=None,
              _root: Optional[Path] = None, _date: Optional[_dt.date] = None) -> dict:
    try:
        return build_payload(_root or PROJECT_ROOT,
                             _date or _dt.datetime.now(_dt.timezone.utc).date())
    except Exception as exc:  # noqa: BLE001 — never block a run
        logger.warning("omni_view_world: desk read failed (non-fatal): %s", exc)
        return {"hook_context": ""}


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    return None
