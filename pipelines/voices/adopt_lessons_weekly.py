"""Decide weekly, not per tape (Oct 21 2026 review, §7.4).

The grading pass after each interview PROPOSES lessons; this pass, once a
week (Monday, or by hand), reads every room of the week — its grade, its
audio metrics, its proposals — and decides. Rules that bind:

* at most ``MAX_ADOPT_PER_WEEK`` lessons adopted, positive ("do X"), each
  with an evidence row and, where one fits, the metric that will show it
  working;
* a lesson is retired when the metric that motivated it has been green for
  ``GREEN_ROOMS`` consecutive rooms (the review's own targets, in
  ``audio_metrics.TARGETS``) — never for being old, never to make room;
* a proposal that restates a standing lesson is merged, not adopted twice;
* a proposal for a fault the room now enforces in code (one question per
  turn, no second sign-off, not re-asking, overlap) is dropped with a note:
  a rule she breaks three times is a room defect, not a prompt defect;
* one Grok call at most, to choose among the week's proposals; everything
  else is deterministic. With fewer proposals than the cap, no call.

Prints a summary and tells the operator on Slack what changed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from typing import Any, Dict, List, Optional

import audio_metrics
from common import (
    llm, logger, notify_operator, parse_json_lenient, sb_select, sb_update,
)
from learning import (
    NETWORK, _already_says_it, adopt_lessons, retire_lessons,
)

MAX_ADOPT_PER_WEEK = 6
GREEN_ROOMS = 3
WEEK = dt.timedelta(days=7)

#: Proposals about what the room enforces are dropped, not adopted. The
#: shapes are described, never quoted, so this list can never seed a tic.
ROOM_ENFORCED = re.compile(
    r"(one question (at a time|per turn)|stop (talking|speaking) after|"
    r"sign[- ]?off|hang up|end of the recording|re-?ask|ask(ed)? (it |the same|twice)|"
    r"talk(ing)? over|speak(ing)? over|interrupt|lightning[- ]round|closing round)",
    re.I)

#: An instruction is written in the positive when it opens on what to do.
NEGATIVE_OPEN = re.compile(r"^\s*(never|don'?t|do not|stop|avoid|no )", re.I)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _since(now: dt.datetime) -> str:
    return (now - WEEK).isoformat()


def week_rooms(show_slug: str, now: Optional[dt.datetime] = None) -> List[dict]:
    """The week's graded rooms with their metrics, newest last."""
    now = now or _now()
    grades = sb_select("episode_grades",
                       f"show=eq.{show_slug}&created_at=gte.{_since(now)}"
                       "&order=created_at.asc&limit=40") or []
    rooms = []
    for g in grades:
        metrics = sb_select("episode_metrics",
                            f"interview_id=eq.{g['interview_id']}&limit=1") or []
        rooms.append({"grade": g, "metrics": metrics[0] if metrics else {}})
    return rooms


def recent_metrics(show_slug: str, limit: int = GREEN_ROOMS) -> List[dict]:
    """The last ``limit`` graded rooms' metrics, newest first, any week."""
    grades = sb_select("episode_grades",
                       f"show=eq.{show_slug}&order=created_at.desc&limit={limit}") or []
    out = []
    for g in grades:
        rows = sb_select("episode_metrics",
                         f"interview_id=eq.{g['interview_id']}&limit=1") or []
        out.append(rows[0] if rows else {})
    return out


def proposals(show_slug: str, now: Optional[dt.datetime] = None) -> List[dict]:
    now = now or _now()
    return sb_select("show_lessons",
                     f"status=eq.proposed&show=in.({show_slug},{NETWORK})"
                     f"&created_at=gte.{_since(now)}&order=created_at.asc&limit=60") or []


def active(show_slug: str) -> List[dict]:
    return sb_select("show_lessons",
                     f"status=eq.active&show=in.({show_slug},{NETWORK})"
                     "&order=decided_at.asc&limit=60") or []


def positive(lesson: str) -> str:
    """A lesson opens on what to do. One that opens on a ban is kept but
    flagged; the chooser is asked to rephrase, and if it cannot the line is
    adopted as written rather than lost."""
    return lesson.strip()


def triage(items: List[dict], standing: List[dict]) -> Dict[str, List[dict]]:
    """Split proposals into room-enforced (drop), duplicates (merge) and
    candidates, deterministically."""
    out: Dict[str, List[dict]] = {"drop": [], "merge": [], "candidates": []}
    existing = [str(r.get("lesson") or "") for r in standing]
    for item in items:
        lesson = str(item.get("lesson") or "").strip()
        if not lesson:
            out["drop"].append(item)
            continue
        if ROOM_ENFORCED.search(lesson):
            out["drop"].append(item)
            continue
        if _already_says_it(lesson, existing):
            out["merge"].append(item)
            continue
        existing.append(lesson)
        out["candidates"].append(item)
    return out


def choose(candidates: List[dict], rooms: List[dict],
           cap: int = MAX_ADOPT_PER_WEEK) -> List[dict]:
    """At most ``cap`` lessons, positive. One model call when there is a
    choice to make; none when every candidate fits."""
    if not candidates:
        return []
    if len(candidates) <= cap and all(not NEGATIVE_OPEN.match(str(c.get("lesson") or ""))
                                      for c in candidates):
        return candidates
    summary = json.dumps([{
        "grade": (r["grade"] or {}).get("overall"),
        "why": (r["grade"] or {}).get("why"),
        "metrics": {k: (r["metrics"] or {}).get(k) for k in audio_metrics.COLUMNS},
    } for r in rooms], ensure_ascii=False)
    listed = json.dumps([{"id": c.get("id"), "lesson": c.get("lesson"),
                          "evidence": c.get("evidence"), "metric": c.get("metric"),
                          "category": c.get("category")} for c in candidates],
                        ensure_ascii=False)
    prompt = (
        "You are deciding, once a week, which proposed standing instructions an "
        "AI interview host called Mira will carry into her next interviews. "
        "Below are this week's rooms with their grades and audio measurements, "
        "then the proposals the grading passes made.\n\n"
        f"ROOMS:\n{summary}\n\nPROPOSALS:\n{listed}\n\n"
        f"Choose at most {cap}. Prefer the ones whose fault the measurements show "
        "and that would change what she DOES next time. Rewrite each chosen lesson "
        "so it opens on what to do (never on 'never', 'don't', 'stop' or 'avoid'), "
        "stays one sentence, names no guest and quotes no line. Keep its id. "
        "Return ONE JSON array of {\"id\": ..., \"lesson\": ...} and nothing else."
    )
    try:
        chosen = parse_json_lenient(llm(prompt, temperature=0.2, max_tokens=1200)) or []
    except Exception:  # noqa: BLE001 — the deterministic answer stands
        logger.exception("weekly chooser failed; adopting the first candidates")
        chosen = []
    by_id = {str(c.get("id")): c for c in candidates}
    out: List[dict] = []
    for row in chosen if isinstance(chosen, list) else []:
        if not isinstance(row, dict):
            continue
        base = by_id.get(str(row.get("id")))
        if not base:
            continue
        text = str(row.get("lesson") or base.get("lesson") or "").strip()
        if not text or NEGATIVE_OPEN.match(text):
            text = str(base.get("lesson") or "").strip()
        out.append({**base, "lesson": text})
        if len(out) >= cap:
            break
    if not out:
        out = candidates[:cap]
    return out


def retire_by_metric(show_slug: str, standing: List[dict],
                     latest: List[dict]) -> List[dict]:
    """Lessons whose metric has been green for the last GREEN_ROOMS rooms."""
    retired: List[dict] = []
    if len(latest) < GREEN_ROOMS:
        return retired
    for row in standing:
        metric = str(row.get("metric") or "").strip()
        if not metric:
            continue
        verdicts = [audio_metrics.is_green(metric, m) for m in latest[:GREEN_ROOMS]]
        if all(v is True for v in verdicts):
            retired.append(row)
    return retired


def run(show_slug: str, dry_run: bool = False, now: Optional[dt.datetime] = None) -> Dict[str, Any]:
    now = now or _now()
    rooms = week_rooms(show_slug, now)
    standing = active(show_slug)
    latest = recent_metrics(show_slug)
    items = proposals(show_slug, now)
    split = triage(items, standing)
    chosen = choose(split["candidates"], rooms)
    to_retire = retire_by_metric(show_slug, standing, latest)

    report = {
        "show": show_slug, "rooms": len(rooms), "proposed": len(items),
        "dropped_room_enforced": len(split["drop"]), "merged": len(split["merge"]),
        "adopted": [c.get("lesson") for c in chosen],
        "retired": [r.get("lesson") for r in to_retire],
    }
    if dry_run:
        logger.info("[dry run] %s", json.dumps(report, ensure_ascii=False, indent=1))
        return report

    for item in split["drop"]:
        sb_update("show_lessons", f"id=eq.{item['id']}",
                  {"status": "dropped", "decided_at": now.isoformat(),
                   "decided_by": "weekly",
                   "decision_note": "the room enforces this in code; not a prompt lesson"})
    for item in split["merge"]:
        sb_update("show_lessons", f"id=eq.{item['id']}",
                  {"status": "merged", "decided_at": now.isoformat(),
                   "decided_by": "weekly",
                   "decision_note": "restates a standing lesson"})
    adopted = adopt_lessons(
        show_slug, "", [
            {"lesson": c.get("lesson"), "category": c.get("category"),
             "evidence": c.get("evidence"), "metric": c.get("metric"),
             "scope": "this_show" if c.get("show") == show_slug else "all_shows"}
            for c in chosen],
        decided_by="weekly", note=f"adopted by the weekly pass of {now.date().isoformat()}")
    for c in chosen:
        sb_update("show_lessons", f"id=eq.{c['id']}",
                  {"status": "merged", "decided_at": now.isoformat(),
                   "decided_by": "weekly", "decision_note": "adopted (see the active copy)"})
    # Anything left proposed from this week was not chosen: say so, so the
    # queue never silently fills.
    chosen_ids = {str(c.get("id")) for c in chosen}
    for item in split["candidates"]:
        if str(item.get("id")) not in chosen_ids:
            sb_update("show_lessons", f"id=eq.{item['id']}",
                      {"status": "dropped", "decided_at": now.isoformat(),
                       "decided_by": "weekly",
                       "decision_note": "not among the week's six"})
    retire_lessons([str(r.get("id")) for r in to_retire],
                   f"its metric was green for {GREEN_ROOMS} rooms")
    report["adopted_rows"] = len(adopted)
    logger.info("%s", json.dumps(report, ensure_ascii=False, indent=1))
    notify_operator(
        f"Weekly lessons ({show_slug}): {len(rooms)} room(s), {len(items)} proposed, "
        f"{len(adopted)} adopted, {len(to_retire)} retired by metric, "
        f"{len(split['drop'])} dropped as room-enforced, {len(split['merge'])} merged.")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--show", action="append", default=None,
                    help="show slug (repeatable); default: every voice show")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    slugs = args.show
    if not slugs:
        from shows import all_shows
        slugs = [s.slug for s in all_shows()]
    for slug in slugs:
        try:
            run(slug, dry_run=args.dry_run)
        except Exception:  # noqa: BLE001 — one show never blocks the other
            logger.exception("weekly pass failed for %s", slug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
