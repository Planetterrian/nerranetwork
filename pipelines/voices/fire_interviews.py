#!/usr/bin/env python3
"""Interview firing cron (nerra_voices_fire_interview.yml, every 5 min).

Two duties per tick:

1. **T-2h SMS reminder** — interviews ~2h out get one SMS from Mira's
   caller ID (``reminder_sent_at`` guards the once-only).
2. **Fire** — interviews whose ``scheduled_at`` falls inside the next
   5-minute window: compile Mira's system prompt from the brief, create the
   ``interview_runs`` row, and start the Voximplant scenario with the run id
   as customData.

GitHub cron is best-effort (spec §5.2 note): the firing window is computed
here as [now - grace, now + 5 min] so a delayed tick still fires anything
it missed, and the ``interview_runs`` uniqueness check keeps a double tick
from double-calling the guest.
"""

from __future__ import annotations

import datetime as dt
import json
import os

from common import (  # noqa: E402
    ROOT, load_prompt, logger, notify_operator, sb_insert, sb_select,
    sb_update,
)

FIRE_WINDOW_AHEAD_MIN = 5
FIRE_GRACE_BEHIND_MIN = 10   # cron drift tolerance — never leave a guest waiting
REMINDER_AHEAD = (dt.timedelta(minutes=105), dt.timedelta(minutes=135))

MIRA_TOOLS = [
    {
        "type": "function",
        "name": "nerra_episode_lookup",
        "description": (
            "Look up the 3 most recent Nerra Network episodes covering a "
            "given topic. Use this when you want to reference what other "
            "Nerra shows have covered on the guest's topic."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "show_filter": {"type": "string",
                                "description": "optional show id"},
            },
            "required": ["topic"],
        },
    },
    {
        "type": "function",
        "name": "guest_brief_lookup",
        "description": (
            "Pull the pre-interview research brief on the current guest. "
            "Use this to refresh your memory mid-interview on a specific "
            "topic they wanted to discuss."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "section": {"type": "string",
                            "enum": ["bio", "topics", "past_work",
                                     "predictions"]},
            },
        },
    },
    {
        "type": "function",
        "name": "fact_check_claim",
        "description": (
            "Verify a specific factual claim the guest just made via web "
            "search. Use sparingly — only when the claim is checkable and "
            "verification adds value to the conversation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "context": {"type": "string",
                            "description": "what the guest was discussing"},
            },
            "required": ["claim"],
        },
    },
]


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(t: dt.datetime) -> str:
    # Z suffix, not +00:00: these strings go raw into PostgREST query
    # strings, where an unencoded "+" is decoded as a space → 400 (this
    # crashed every fire cron tick until July 17 2026).
    return t.isoformat().replace("+00:00", "Z")


def compile_mira_prompt(interview: dict, app: dict, brief: dict) -> str:
    questions = brief.get("likely_questions") or []
    q_text = "\n".join(f"- {q.get('question', q) if isinstance(q, dict) else q}"
                       for q in questions)
    return load_prompt(
        "mira_system_prompt.txt",
        guest_name=app["name"],
        guest_title=app.get("title", ""),
        guest_organization=app.get("organization", ""),
        episode_thesis=interview.get("episode_thesis")
        or brief.get("episode_thesis_draft", ""),
        guest_brief=brief.get("bio_research", ""),
        likely_questions=q_text,
    )


def send_reminders() -> None:
    lo, hi = _now() + REMINDER_AHEAD[0], _now() + REMINDER_AHEAD[1]
    due = sb_select(
        "interviews",
        "status=eq.briefed&reminder_sent_at=is.null"
        f"&scheduled_at=gte.{_iso(lo)}&scheduled_at=lte.{_iso(hi)}",
    )
    for interview in due:
        try:
            app_rows = sb_select("guest_applications",
                                 f"id=eq.{interview['application_id']}")
            phone = (app_rows[0].get("phone") or "").strip() if app_rows else ""
            if not phone:
                logger.warning("Interview %s: no phone — reminder skipped",
                               interview["id"])
                continue
            from voximplant.api_clients.voximplant_client import send_sms
            caller_id = interview.get("caller_id") or os.environ.get(
                "VOXIMPLANT_CALLER_ID", "")
            send_sms(
                phone,
                "Mira here, from The Age of AI (Nerra Network). Your "
                "interview starts in about two hours — I'll be calling you "
                f"from this number ({caller_id}). Find a quiet spot and "
                "we'll make something great. — Mira",
                source_number=caller_id or None,
            )
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"reminder_sent_at": _iso(_now())})
            logger.info("Reminder SMS sent for interview %s", interview["id"])
        except Exception:  # noqa: BLE001 — a reminder failure must not stop firing
            logger.exception("Reminder failed for %s (non-fatal)",
                             interview["id"])


def fire_due_interviews() -> int:
    lo = _now() - dt.timedelta(minutes=FIRE_GRACE_BEHIND_MIN)
    hi = _now() + dt.timedelta(minutes=FIRE_WINDOW_AHEAD_MIN)
    # status=in.(briefed,scheduled): short-notice bookings (inside the daily
    # prep cron's 12-36h lookahead) arrive still `scheduled` with no brief —
    # they get an inline brief below instead of silently never firing
    # (July 2026: booking opened to 24/7 with 15-min notice).
    due = sb_select(
        "interviews",
        f"status=in.(briefed,scheduled)"
        f"&scheduled_at=gte.{_iso(lo)}&scheduled_at=lte.{_iso(hi)}",
    )
    failures = 0
    for interview in due:
        # Idempotency: a delayed/parallel tick must not double-call.
        if sb_select("interview_runs",
                     f"interview_id=eq.{interview['id']}&status=neq.failed"):
            logger.info("Interview %s already has an active run — skipping",
                        interview["id"])
            continue
        try:
            app = sb_select("guest_applications",
                            f"id=eq.{interview['application_id']}")[0]
            brief_rows = sb_select("interview_briefs",
                                   f"interview_id=eq.{interview['id']}")
            if not brief_rows:
                # Short-notice booking: the daily prep cron never saw this
                # interview. Generate the brief inline (same code path as
                # the T-1d workflow) so Mira still calls; the guest gets
                # the prep email immediately instead of a day ahead.
                from generate_briefs import email_brief_to_guest, generate_brief
                logger.warning(
                    "Interview %s due with no brief (short-notice booking) — "
                    "generating inline", interview["id"])
                brief = generate_brief(interview, app)
                try:
                    email_brief_to_guest(interview, app, brief)
                except Exception:  # noqa: BLE001 — email is best-effort here
                    logger.exception("Inline brief email failed (non-fatal)")
                sb_update("interviews", f"id=eq.{interview['id']}",
                          {"status": "briefed",
                           "episode_thesis": brief["episode_thesis_draft"]})
            else:
                brief = brief_rows[0]
            phone = (app.get("phone") or "").strip()
            if not phone:
                raise RuntimeError("guest has no phone number on file")
            caller_id = interview.get("caller_id") or os.environ.get(
                "VOXIMPLANT_CALLER_ID", "")
            if not caller_id:
                raise RuntimeError("no caller_id (set VOXIMPLANT_CALLER_ID)")

            run = sb_insert("interview_runs", {
                "interview_id": interview["id"],
                "mira_system_prompt": compile_mira_prompt(interview, app, brief),
                "voice_preset": "ara",
                "tools": MIRA_TOOLS,
                "guest_phone": phone,
                "caller_id": caller_id,
                "scheduled_for": interview["scheduled_at"],
            })

            from voximplant.api_clients.voximplant_client import (
                start_interview_scenario,
            )
            result = start_interview_scenario(run["id"])
            sb_update("interview_runs", f"id=eq.{run['id']}", {
                "status": "fired",
                "fired_at": _iso(_now()),
                "voximplant_session_id": json.dumps(
                    result.get("result", result))[:512],
            })
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"status": "in_progress"})
            logger.info("Fired interview %s (run %s) for %s",
                        interview["id"], run["id"], app["name"])
        except Exception as exc:  # noqa: BLE001
            failures += 1
            logger.exception("Firing failed for interview %s", interview["id"])
            sb_update("interviews", f"id=eq.{interview['id']}",
                      {"status": "failed"})
            notify_operator(
                f"Age of AI: interview {interview['id']} FAILED to fire: {exc}",
                critical=True,
            )
    return failures


def main() -> int:
    send_reminders()
    return 1 if fire_due_interviews() else 0


if __name__ == "__main__":
    raise SystemExit(main())
