"""Nerra Producer — chase job (daily).

    python -m pipelines.producer.chase [--dry-run] [--limit N]

Email-sourced applications the Producer invited but never heard back on
get two gentle nudges in the same Gmail thread, then the row lapses:

* day 5 after the invite  → ``producer_chase_1.j2`` (chase_count 0 → 1)
* day 12 (7 days later)   → ``producer_chase_2.j2`` (chase_count 1 → 2)
* day 22 (10 days later)  → status ``lapsed`` (``producer_closed_reason``
                             = ``no_reply``), no email

A reply of any kind resets the clock: the inbox job's follow-up path
handles it, and the ``later`` intent stamps ``chased_at`` so this job
waits a full cycle before nudging again. Before sending, the thread is
re-read from Gmail: if its newest message is inbound (a reply the inbox
job has not processed yet) or an autoresponder, nothing is sent.

Runs in the same modes as the inbox job (``PRODUCER_MODE``): ``auto``
sends, ``draft`` creates Gmail drafts, ``off`` does nothing.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.voices.common import sb_insert, sb_select, sb_update  # noqa: E402
from pipelines.voices.shows import get_show  # noqa: E402
from pipelines.producer import classify as _classify  # noqa: E402
from pipelines.producer.gmail_client import GmailClient  # noqa: E402
from pipelines.producer.inbox import first_name, newest_is_inbound, render_text  # noqa: E402
from pipelines.producer.policy import Policy, load_policy  # noqa: E402

logger = logging.getLogger("nerra_producer.chase")
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s %(levelname)s %(message)s")

JOB = "chase"
FIRST_CHASE_AFTER_DAYS = 5
SECOND_CHASE_AFTER_DAYS = 7
LAPSE_AFTER_DAYS = 10
TEMPLATES = {1: "producer_chase_1.j2", 2: "producer_chase_2.j2"}
COLUMNS = ("id,name,email,show,status,source,publicist_name,publicist_email,"
           "producer_action,producer_acted_at,producer_last_inbound_at,"
           "producer_last_outbound_at,chase_count,chased_at,email_thread_id")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def next_step(app: Dict[str, Any], now: Optional[datetime] = None) -> Optional[str]:
    """Pure: 'chase1' | 'chase2' | 'lapse' | None for one row."""
    now = now or _now()
    if (app.get("status") or "") != "invited" or (app.get("source") or "") != "email":
        return None
    if not app.get("email_thread_id"):
        return None
    if app.get("producer_action") not in ("sent", "followup_sent", "chase_sent"):
        return None  # drafted invites were never actually sent
    count = int(app.get("chase_count") or 0)
    # The clock runs from our most recent message to them (invite,
    # follow-up answer or previous nudge). A reply that arrived after it
    # belongs to the inbox job's follow-up path, never to a nudge.
    ours = [d for d in (_ts(app.get("chased_at")), _ts(app.get("producer_last_outbound_at")),
                        _ts(app.get("producer_acted_at"))) if d]
    if not ours:
        return None
    anchor = max(ours)
    theirs = _ts(app.get("producer_last_inbound_at"))
    if theirs and theirs > anchor:
        return None
    age = now - anchor
    if count == 0 and age >= timedelta(days=FIRST_CHASE_AFTER_DAYS):
        return "chase1"
    if count == 1 and age >= timedelta(days=SECOND_CHASE_AFTER_DAYS):
        return "chase2"
    if count >= 2 and age >= timedelta(days=LAPSE_AFTER_DAYS):
        return "lapse"
    return None


def candidates(limit: int = 200) -> List[Dict[str, Any]]:
    return sb_select("guest_applications",
                     f"status=eq.invited&source=eq.email&select={COLUMNS}"
                     f"&order=producer_acted_at.asc&limit={limit}")


def chase_body(app: Dict[str, Any], step: int) -> str:
    show = get_show(app.get("show") or "nerra_voices")
    name = first_name(app.get("publicist_name")) or first_name(app.get("name")) or "There"
    return render_text(TEMPLATES[step], show.slug, first_name=name,
                       guest_name=app.get("name") or "your guest", show_name=show.name)


def process(app: Dict[str, Any], *, gmail: GmailClient, policy: Policy,
            dry_run: bool, summary: Dict[str, Any]) -> Dict[str, Any]:
    step = next_step(app)
    line = {"application_id": app["id"], "guest_name": app.get("name"),
            "thread_id": app.get("email_thread_id"), "step": step, "action": "none"}
    if step is None:
        return line
    thread = gmail.get_thread(app["email_thread_id"])
    if newest_is_inbound(thread, gmail.user):
        line["action"] = "skip"
        line["reason"] = "newest message is inbound; inbox job owns it"
        return line
    if step == "lapse":
        line["action"] = "lapse"
        if not dry_run:
            sb_update("guest_applications", f"id=eq.{app['id']}", {
                "status": "lapsed", "producer_closed_reason": "no_reply",
                "producer_acted_at": _now().isoformat()})
        summary["lapsed"] += 1
        return line
    n = 1 if step == "chase1" else 2
    inbound = _classify.latest_inbound(thread, gmail.user) or {}
    last = (thread.get("messages") or [{}])[-1]
    body = chase_body(app, n)
    kwargs = dict(
        thread_id=thread["id"],
        to=inbound.get("from") or app.get("publicist_email") or app.get("email") or "",
        subject=thread.get("subject") or "",
        in_reply_to=last.get("message_id", ""),
        references=last.get("references", "") or last.get("message_id", ""),
    )
    if not kwargs["to"]:
        line["action"] = "skip"
        line["reason"] = "no recipient"
        return line
    if policy.mode == "auto":
        gmail.send_reply(body_text=body, **kwargs)
        line["action"] = "sent"
        summary["sent"] += 1
        patch = {"chase_count": n, "chased_at": _now().isoformat(),
                 "producer_action": "chase_sent",
                 "producer_last_outbound_at": _now().isoformat()}
    else:
        gmail.create_draft(body_text=body, **kwargs)
        line["action"] = "drafted"
        summary["drafted"] += 1
        patch = {"chase_count": n, "chased_at": _now().isoformat(),
                 "producer_action": "chase_drafted"}
    if not dry_run:
        sb_update("guest_applications", f"id=eq.{app['id']}", patch)
    return line


def run_chase(*, gmail: Optional[GmailClient] = None, policy: Optional[Policy] = None,
              dry_run: bool = False, limit: int = 30) -> Dict[str, Any]:
    policy = policy or load_policy()
    summary: Dict[str, Any] = {"mode": policy.mode, "dry_run": dry_run, "considered": 0,
                               "sent": 0, "drafted": 0, "lapsed": 0, "failed": 0,
                               "errors": [], "decisions": []}
    if policy.mode == "off":
        logger.info("PRODUCER_MODE=off: chase job does nothing")
        return summary
    gmail = gmail or GmailClient.from_env(dry_run=dry_run, processed_label=policy.processed_label)
    run_id = None
    if not dry_run:
        try:
            run_id = sb_insert("producer_runs", {"job": JOB, "notes": f"mode={policy.mode}"}).get("id")
        except Exception as exc:  # noqa: BLE001
            logger.warning("producer_runs insert failed (non-fatal): %s", exc)
    acted = 0
    for app in candidates():
        if acted >= limit:
            break
        summary["considered"] += 1
        try:
            line = process(app, gmail=gmail, policy=policy, dry_run=dry_run, summary=summary)
        except Exception as exc:  # noqa: BLE001
            logger.exception("chase failed for %s: %s", app.get("id"), exc)
            summary["failed"] += 1
            summary["errors"].append({"application_id": app.get("id"),
                                      "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        if line["action"] != "none":
            summary["decisions"].append(line)
            logger.info("chase %s", json.dumps(line, default=str))
        if line["action"] in ("sent", "drafted", "lapse"):
            acted += 1
    if run_id:
        try:
            sb_update("producer_runs", f"id=eq.{run_id}", {
                "finished_at": _now().isoformat(),
                "messages_seen": summary["considered"],
                "messages_acted": summary["sent"] + summary["drafted"] + summary["lapsed"],
                "drafts_created": summary["drafted"], "sent": summary["sent"],
                "errors": summary["errors"] or None,
                "notes": json.dumps({"summary": {k: v for k, v in summary.items() if k != "decisions"},
                                     "decisions": summary["decisions"]}, default=str)})
        except Exception as exc:  # noqa: BLE001
            logger.warning("producer_runs update failed (non-fatal): %s", exc)
    logger.info("Producer chase: %d considered, %d nudged, %d drafted, %d lapsed, %d failed",
                summary["considered"], summary["sent"], summary["drafted"],
                summary["lapsed"], summary["failed"])
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Nerra Producer chase job")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=int(os.environ.get("PRODUCER_CHASE_LIMIT", "30")))
    args = ap.parse_args(argv)
    summary = run_chase(dry_run=args.dry_run, limit=max(1, args.limit))
    return 1 if summary["failed"] and summary["failed"] * 2 > max(1, summary["considered"]) else 0


if __name__ == "__main__":
    sys.exit(main())
