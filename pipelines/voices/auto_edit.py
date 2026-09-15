#!/usr/bin/env python3
"""Cut the episode without being asked (Sept 15 2026).

Every episode so far has been produced because somebody remembered to ask
for it. The interview ends, the transcript lands, and then a human decides
where it starts, where it ends, what to drop, and what Mira should say at
either end. Those are real editorial judgements, but they are judgements
made from the transcript, and the transcript is right here.

So this runs straight after post-interview processing, in the same job, and
writes three things:

* ``narration/<slug>.json`` — Mira's introduction and close, written from
  what the guest actually said.
* ``edl/<slug>.json`` — where the conversation starts, where it ends, and
  which stretches come out, each with a reason.
* an ``episode_records`` row — the content lake. What the guest claimed,
  what they predicted and by when, what we never got to ask. Every guest so
  far has asked to come back in six months; this is what makes that worth
  doing, because the next conversation can open with "last time you said".

The files land on the runner and the next two steps of the same workflow
read them, so nothing needs committing. The decisions are also stored in
``episode_edits``, which is what an explanation or a re-run reads.

    python pipelines/voices/auto_edit.py <interview_run_id>
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from address import spoken as spoken_address  # noqa: E402
from common import (  # noqa: E402
    guest_links, llm, load_prompt, logger, parse_json_lenient, sb_insert,
    sb_select, sb_update, show_for,
)

NARRATION_DIR = Path(__file__).parent / "narration"
EDL_DIR = Path(__file__).parent / "edl"

# How much slack to leave around a cut so a word is never clipped.
EDGE_PAD_SEC = 0.6
# A gap has to be worth the seam. Below this, leave it in — a cut you can
# hear is worse than two seconds of nothing.
MIN_DROP_SEC = 25.0


def _slug(name: str, when: dt.date) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", (name or "guest").lower()).strip("_")
    return f"{base}_{when:%Y_%m_%d}"


def _ours(slug: str) -> bool:
    """True when the EDL of this name was written by a previous auto cut."""
    try:
        rows = sb_select("episode_edits", f"slug=eq.{slug}&select=generated_by")
        return bool(rows) and rows[0].get("generated_by") == "auto_edit"
    except Exception:  # noqa: BLE001
        return False


def _leg_offset(run: dict, role: str = "guest") -> float:
    """Seconds between the room opening and the guest leg we are cutting.

    The EDL addresses the guest's own recording, whose clock starts when he
    joined; the transcript is on the room's clock. When someone rejoins, the
    two differ by minutes (John Capobianco: 428 seconds), which is the
    difference between an episode and a shuffled one.
    """
    try:
        from post_interview import duration_seconds, room_offsets  # noqa: F401
    except Exception:  # noqa: BLE001
        return 0.0
    log = run.get("grok_session_log") or {}
    tracks = (log.get("tracks") or {}).get("durations") or {}
    seconds = tracks.get(role)
    offsets = room_offsets(run, {role: seconds} if seconds else None)
    return float(offsets.get(role, 0.0))


def _context(run_id: str) -> dict:
    runs = sb_select("interview_runs", f"id=eq.{run_id}")
    if not runs:
        raise SystemExit(f"no interview_runs row {run_id}")
    run = runs[0]
    interview = sb_select("interviews", f"id=eq.{run['interview_id']}")[0]
    app = sb_select("guest_applications", f"id=eq.{interview['application_id']}")[0]
    pkgs = sb_select("editorial_packages",
                     f"interview_run_id=eq.{run_id}&order=created_at.desc")
    if not pkgs:
        raise SystemExit(f"no editorial package for run {run_id} — has "
                         "post_interview.py finished?")
    return {"run": run, "interview": interview, "app": app, "package": pkgs[0]}


def _previous(app: dict) -> str:
    """What this guest said last time, when there was a last time."""
    email = (app.get("email") or "").lower()
    if not email:
        return ""
    rows = sb_select("episode_records",
                     f"guest_email=eq.{email}&order=created_at.desc&limit=3")
    if not rows:
        return ""
    out = []
    for row in rows:
        out.append(f"- {row.get('recorded_on')}: {row.get('summary', '')}")
        for pred in (row.get("predictions") or [])[:4]:
            out.append(f"    predicted: {pred.get('prediction')} "
                       f"(by {pred.get('due_on')})")
    return "THIS GUEST HAS BEEN ON BEFORE:\n" + "\n".join(out)


def plan(ctx: dict) -> dict:
    run, interview, app, package = (ctx["run"], ctx["interview"],
                                    ctx["app"], ctx["package"])
    show = show_for(interview, app)
    transcript = package.get("transcript_raw") or ""
    if len(transcript) < 2000:
        raise SystemExit("transcript too short to cut from")
    raw = llm(
        load_prompt("auto_edit.txt", show=show,
                    guest_name=app.get("name", ""),
                    guest_address=spoken_address(app),
                    guest_title=app.get("title", ""),
                    guest_organization=app.get("organization", "") or "",
                    guest_bio=app.get("bio", "") or "",
                    guest_links="\n".join(f"- {l['label']}: {l['url']}"
                                          for l in guest_links(app)) or "(none)",
                    cohost_name=(run.get("cohost_name")
                                 or interview.get("cohost_name") or "Patrick Novak"),
                    episode_thesis=interview.get("episode_thesis", "") or "",
                    previous=_previous(app),
                    transcript=transcript),
        temperature=0.4, max_tokens=6000,
    )
    out = parse_json_lenient(raw)
    if not isinstance(out, dict) or "intro" not in out or "outro" not in out:
        raise SystemExit("auto_edit pass did not return intro and outro")
    return out


def build(run_id: str) -> dict:
    ctx = _context(run_id)
    run, interview, app = ctx["run"], ctx["interview"], ctx["app"]
    decided = plan(ctx)

    recorded = (run.get("created_at") or "")[:10] or dt.date.today().isoformat()
    when = dt.date.fromisoformat(recorded)
    slug = _slug(app.get("name", ""), when)
    # A hand-written edit in the repo is somebody's judgement and outranks
    # this one. Never overwrite it — cut alongside it and let a human choose.
    if (EDL_DIR / f"{slug}.json").exists() and not _ours(slug):
        slug = f"{slug}_auto"
        logger.info("a hand-written edit already exists — cutting as %s", slug)
    offset = _leg_offset(run)

    # Room clock -> the guest leg's own clock, which is what the EDL addresses.
    def leg(t: float) -> float:
        return max(0.0, float(t) - offset)

    start = leg(float(decided.get("start_sec") or 0.0)) + EDGE_PAD_SEC
    end = leg(float(decided["end_sec"]))
    drops = []
    for d in decided.get("drop") or []:
        a, b = leg(float(d["from_sec"])), leg(float(d["to_sec"]))
        if b - a >= MIN_DROP_SEC and start < a < b < end:
            drops.append({"from": a, "to": b, "why": d.get("why", "")})
    drops.sort(key=lambda d: d["from"])

    cuts = [{"from": "narration:intro"}, {"gap": 0.7}]
    at = start
    for d in drops:
        cuts.append({"from": "run:guest", "balance": True, "voice_match": "right",
                     "start": round(at, 1), "end": round(d["from"], 1),
                     "note": f"to {d['from']:.0f}s: {d['why']}"})
        cuts.append({"gap": 0.4})
        at = d["to"]
    cuts.append({"from": "run:guest", "balance": True, "voice_match": "right",
                 "start": round(at, 1), "end": round(end, 1),
                 "note": decided.get("end_why", "")})
    cuts += [{"gap": 0.7}, {"from": "narration:outro"}]

    narration = {
        "show": show_for(interview, app).slug,
        "voice": run.get("voice_preset") or "ara",
        "note": f"Written by auto_edit from the {app.get('name')} interview.",
        "segments": [{"id": "intro", "text": decided["intro"]},
                     {"id": "outro", "text": decided["outro"]}],
    }
    edl = {
        "show": show_for(interview, app).slug,
        "interview_id": interview["id"],
        "run_id": run["id"],
        "narration": slug,
        "note": decided.get("rationale", ""),
        "cuts": cuts,
    }

    NARRATION_DIR.mkdir(parents=True, exist_ok=True)
    EDL_DIR.mkdir(parents=True, exist_ok=True)
    (NARRATION_DIR / f"{slug}.json").write_text(
        json.dumps(narration, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (EDL_DIR / f"{slug}.json").write_text(
        json.dumps(edl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("cut %s: %.0fs to %.0fs, %d stretch(es) dropped",
                slug, start, end, len(drops))

    existing = sb_select("episode_edits", f"slug=eq.{slug}&select=id")
    row = {"slug": slug, "interview_id": interview["id"],
           "interview_run_id": run["id"], "narration": narration, "edl": edl,
           "rationale": decided.get("rationale", "")}
    if existing:
        sb_update("episode_edits", f"id=eq.{existing[0]['id']}", row)
    else:
        sb_insert("episode_edits", row)

    _remember(ctx, decided, when)
    return {"slug": slug, "cuts": len(cuts), "drops": len(drops)}


def _remember(ctx: dict, decided: dict, when: dt.date) -> None:
    """The content lake row. Written even if nothing else here works out."""
    run, interview, app = ctx["run"], ctx["interview"], ctx["app"]
    predictions = []
    for p in decided.get("predictions") or []:
        months = p.get("horizon_months")
        due = None
        if isinstance(months, (int, float)) and months > 0:
            due = (when + dt.timedelta(days=int(months) * 30)).isoformat()
        predictions.append({"prediction": p.get("prediction"),
                            "horizon_months": months, "due_on": due,
                            "quote": p.get("quote")})
    row = {
        "show": show_for(interview, app).slug,
        "interview_id": interview["id"],
        "interview_run_id": run["id"],
        "application_id": app.get("id"),
        "guest_name": app.get("name"),
        "guest_email": (app.get("email") or "").lower(),
        "recorded_on": when.isoformat(),
        "summary": decided.get("summary", ""),
        "claims": decided.get("claims") or [],
        "predictions": predictions,
        "unanswered": decided.get("unanswered") or [],
        "follow_ups": decided.get("follow_ups") or [],
        "quotes": decided.get("quotes") or [],
        "topics": app.get("topics") or [],
        "links": app.get("links") or {},
    }
    try:
        # One record per interview, not one per cut. Sept 15 2026: re-cutting
        # Vincent Rylan's episode to see what the machine would do wrote a
        # second record of the same conversation. A guest quoted back to
        # themselves from two slightly different versions of what they said is
        # worse than not being quoted at all.
        existing = sb_select("episode_records",
                             f"interview_run_id=eq.{run['id']}&select=id")
        if existing:
            sb_update("episode_records", f"id=eq.{existing[0]['id']}", row)
            logger.info("content lake: updated this interview's record")
        else:
            sb_insert("episode_records", row)
        logger.info("content lake: %d claims, %d predictions, %d follow-ups",
                    len(decided.get("claims") or []), len(predictions),
                    len(decided.get("follow_ups") or []))
    except Exception:  # noqa: BLE001
        logger.exception("could not write the episode record — continuing")


# common.py sends logging to STDOUT, and this script's stdout is a contract:
# the workflow reads a JSON object from it to learn the slug and hand it to
# the narrate and assemble steps. Every log line landed in that JSON and the
# parse failed, so twice now (Dan Perra, Sept 15 2026) the episode was cut,
# written to the database — and then the job died before Mira recorded a
# word, with the cut stranded on a runner that was about to be destroyed.
# Logs go to stderr here, and the result is written to a file as well, so
# the hand-off does not depend on stdout staying clean.
RESULT_PATH = os.environ.get("AUTO_EDIT_RESULT", "cut.json")


def _logs_to_stderr() -> None:
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout:
            handler.setStream(sys.stderr)


def main() -> int:
    _logs_to_stderr()
    if len(sys.argv) < 2:
        raise SystemExit("usage: auto_edit.py <interview_run_id>")
    result = build(sys.argv[1])
    payload = json.dumps(result)
    try:
        Path(RESULT_PATH).write_text(payload + "\n", encoding="utf-8")
    except Exception:  # noqa: BLE001 — stdout is still there
        logger.exception("could not write %s", RESULT_PATH)
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
