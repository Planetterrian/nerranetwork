"""Nerra Producer — inbox job.

    python -m pipelines.producer.inbox [--dry-run] [--limit N]

For every unprocessed Gmail thread (no ``Producer/Processed`` label, last
30 days, in inbox):

1. skip if ``guest_applications`` already has this ``email_thread_id``;
2. classify the latest inbound message with Grok (``grok-latest``);
3. run the policy (mode + hard exclusions) to get a decision;
4. act: send the in-thread invite / draft it / label only / skip;
5. upsert the ``guest_applications`` row (source=email, status=invited);
6. label the thread processed (plus ``Producer/Hold`` when held).

One thread's failure never aborts the run: errors are collected, reported
to Slack, and the exit code is non-zero only when more than half of the
threads failed. ``--dry-run`` reads everything and writes nothing (no
sends, drafts, labels, or DB rows). Mode ``off`` exits before touching
Gmail at all.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.voices.common import (  # noqa: E402
    notify_operator, sb_insert, sb_select, sb_update, show_email_context,
)
from pipelines.voices.shows import get_show  # noqa: E402
from pipelines.producer import classify as _classify  # noqa: E402
from pipelines.producer.gmail_client import GmailClient  # noqa: E402
from pipelines.producer.policy import (  # noqa: E402
    Decision, Policy, decide, decision_log_line, load_policy,
)

logger = logging.getLogger("nerra_producer.inbox")
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s %(levelname)s %(message)s")

TEMPLATES = ROOT / "templates" / "email"
INVITE_TEMPLATE = "producer_guest_invite.j2"
HOLD_TEMPLATE = "producer_hold_note.j2"
JOB = "inbox"


# ---------------------------------------------------------------------------
# Rendering (plain text: NO autoescape, unlike common.render_email)
# ---------------------------------------------------------------------------

def render_text(template_name: str, show: Optional[str] = None, **context: Any) -> str:
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=False,
                      keep_trailing_newline=True)
    merged: Dict[str, Any] = show_email_context(show) if show else {}
    merged.update(context)
    return env.get_template(template_name).render(**merged)


def first_name(full: Optional[str]) -> str:
    full = " ".join((full or "").replace(",", " ").split())
    if not full:
        return ""
    token = full.split()[0].strip("\"'")
    if "@" in token or len(token) < 2:
        return ""
    return token


def invite_context(classification: Dict[str, Any], sender_name: str,
                   policy: Policy) -> Dict[str, Any]:
    show_slug = classification.get("recommended_show") or "nerra_voices"
    show = get_show(show_slug)
    guest = classification.get("guest_name") or "your guest"
    publicist = first_name(classification.get("publicist_name"))
    if not publicist:
        candidate = first_name(sender_name)
        if candidate and candidate.lower() != first_name(guest).lower():
            publicist = candidate
    return {
        "show_slug": show.slug,
        "publicist_first_name": publicist or "There",
        "guest_name": guest,
        "show_name": show.name,
        "show_blurb": policy.blurb(show.slug),
        "apply_url": show.apply_url,
        "pitched_show_name": policy.pitched_show_name(classification.get("pitched_show")),
    }


def render_invite(classification: Dict[str, Any], sender_name: str,
                  policy: Policy) -> str:
    ctx = invite_context(classification, sender_name, policy)
    return render_text(INVITE_TEMPLATE, ctx["show_slug"], **ctx)


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

def application_exists(thread_id: str) -> bool:
    rows = sb_select("guest_applications",
                     f"email_thread_id=eq.{thread_id}&select=id")
    return bool(rows)


def application_row(*, thread: Dict[str, Any], inbound: Dict[str, Any],
                    classification: Dict[str, Any], action: str) -> Dict[str, Any]:
    show_slug = classification.get("recommended_show") or "nerra_voices"
    sender_name = inbound.get("from_name") or inbound.get("from_email") or "unknown"
    clean = {k: v for k, v in classification.items() if not k.startswith("_")}
    return {
        "name": classification.get("guest_name") or sender_name,
        "email": classification.get("publicist_email") or inbound.get("from_email") or "",
        "organization": classification.get("guest_title_org"),
        "show": show_slug,
        "status": "invited",
        "source": "email",
        "pitched_show": classification.get("pitched_show"),
        "publicist_name": classification.get("publicist_name") or (
            sender_name if classification.get("guest_name") else None),
        "publicist_email": classification.get("publicist_email") or inbound.get("from_email"),
        "pitch_summary": classification.get("topic_summary"),
        "producer_classification": clean,
        "producer_action": action,
        "producer_acted_at": _now(),
        "email_thread_id": thread["id"],
        "referrer": f"producer:{thread['id']}",
        "notes": f"Producer inbox: {thread.get('subject') or ''}"[:500],
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunLog:
    """One ``producer_runs`` row per tick; no-op in dry-run."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.id: Optional[str] = None
        self.decisions: List[Dict[str, Any]] = []

    def start(self, notes: str = "") -> None:
        if not self.enabled:
            return
        try:
            row = sb_insert("producer_runs", {"job": JOB, "notes": notes})
            self.id = row.get("id")
        except Exception as exc:  # noqa: BLE001 — observability must not block
            logger.warning("producer_runs insert failed (non-fatal): %s", exc)

    def record(self, line: Dict[str, Any]) -> None:
        self.decisions.append(line)
        logger.info("decision %s", json.dumps(line, default=str))

    def finish(self, summary: Dict[str, Any], errors: List[Dict[str, Any]]) -> None:
        if not self.enabled or not self.id:
            return
        try:
            sb_update("producer_runs", f"id=eq.{self.id}", {
                "finished_at": _now(),
                "messages_seen": summary["seen"],
                "messages_acted": summary["sent"] + summary["drafted"],
                "drafts_created": summary["drafted"],
                "sent": summary["sent"],
                "errors": errors or None,
                "notes": json.dumps({"summary": summary, "decisions": self.decisions},
                                    default=str),
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("producer_runs update failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Per-thread processing
# ---------------------------------------------------------------------------

def already_replied(thread: Dict[str, Any], own_email: str) -> bool:
    own = (own_email or "").lower()
    return any((m.get("from_email") or "").lower() == own
               for m in thread.get("messages") or [])


def process_thread(thread_id: str, *, gmail: GmailClient, policy: Policy,
                   run: RunLog, summary: Dict[str, Any],
                   dry_run: bool) -> Dict[str, Any]:
    thread = gmail.get_thread(thread_id)
    inbound = _classify.latest_inbound(thread, gmail.user)
    if inbound is None:
        # Only our own messages in the thread: nothing to answer.
        decision = Decision("skip", "no inbound message in thread")
        classification: Dict[str, Any] = {"category": None, "confidence": None}
    else:
        in_db = False
        if not dry_run or os.environ.get("SUPABASE_URL"):
            try:
                in_db = application_exists(thread_id)
            except Exception as exc:  # noqa: BLE001
                if dry_run:
                    logger.warning("[dry-run] duplicate check skipped: %s", exc)
                else:
                    raise
        if in_db:
            classification = {"category": None, "confidence": None}
            decision = decide(classification, policy=policy,
                              sender_email=inbound.get("from_email", ""),
                              already_replied=False, already_in_db=True,
                              sends_so_far=summary["sent"])
        else:
            classification = _classify.classify_thread(thread, gmail.user)
            decision = decide(
                classification, policy=policy,
                sender_email=inbound.get("from_email", ""),
                already_replied=already_replied(thread, gmail.user),
                already_in_db=False, sends_so_far=summary["sent"],
            )

    line = decision_log_line(thread_id, classification, decision)
    line["subject"] = thread.get("subject")
    line["from"] = (inbound or {}).get("from_email")

    if decision.action in ("none", "defer"):
        if decision.action == "defer":
            summary["deferred"] = summary.get("deferred", 0) + 1
        run.record(line)
        return line

    invite_body = ""
    if decision.draft_invite and inbound is not None:
        invite_body = render_invite(classification, inbound.get("from_name", ""), policy)

    reply_kwargs = dict(
        thread_id=thread_id,
        to=(inbound or {}).get("from") or (inbound or {}).get("from_email", ""),
        subject=thread.get("subject") or (inbound or {}).get("subject", ""),
        in_reply_to=(inbound or {}).get("message_id", ""),
        references=(inbound or {}).get("references", ""),
    )

    draft_created = False
    if decision.action == "send":
        gmail.send_reply(body_text=invite_body, **reply_kwargs)
        summary["sent"] += 1
        summary["by_show"][classification["recommended_show"]] = (
            summary["by_show"].get(classification["recommended_show"], 0) + 1)
        line["show"] = classification["recommended_show"]
    elif decision.action == "draft":
        if invite_body:
            gmail.create_draft(body_text=invite_body, **reply_kwargs)
            draft_created = True
        summary["drafted"] += 1
        gmail.add_label(thread_id, policy.hold_label)
        if decision.notify:
            show_slug = classification.get("recommended_show")
            note = render_text(
                HOLD_TEMPLATE,
                reason=decision.reason,
                category=classification.get("category"),
                confidence=float(classification.get("confidence") or 0.0),
                guest_name=classification.get("guest_name"),
                recommended_show_name=get_show(show_slug).name if show_slug else "",
                sender=(inbound or {}).get("from", ""),
                subject=thread.get("subject", ""),
                topic_summary=classification.get("topic_summary", ""),
                draft_created=draft_created,
                thread_url=thread.get("url", ""),
            )
            if dry_run:
                logger.info("[dry-run] would post Slack hold note:\n%s", note)
            else:
                notify_operator(note)
    else:
        summary["skipped"] += 1

    # DB row for anything that produced an invite (sent or drafted).
    if decision.action in ("send", "draft") and decision.draft_invite and inbound is not None:
        action_word = "sent" if decision.action == "send" else "drafted"
        row = application_row(thread=thread, inbound=inbound,
                              classification=classification, action=action_word)
        if dry_run:
            logger.info("[dry-run] would insert guest_applications row: %s",
                        json.dumps({k: row[k] for k in ("name", "email", "show", "status",
                                                        "pitched_show", "email_thread_id")}))
        else:
            sb_insert("guest_applications", row)
            line["application"] = True

    gmail.add_label(thread_id, policy.processed_label)
    run.record(line)
    return line


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run_inbox(*, gmail: Optional[GmailClient] = None, policy: Optional[Policy] = None,
              dry_run: bool = False, limit: int = 50) -> Dict[str, Any]:
    policy = policy or load_policy()
    summary: Dict[str, Any] = {"mode": policy.mode, "dry_run": dry_run, "seen": 0,
                               "sent": 0, "drafted": 0, "skipped": 0, "failed": 0,
                               "by_show": {}, "errors": []}
    if policy.mode == "off":
        logger.info("PRODUCER_MODE=off: inbox job does nothing")
        return summary

    gmail = gmail or GmailClient.from_env(dry_run=dry_run,
                                          processed_label=policy.processed_label)
    run = RunLog(enabled=not dry_run)
    run.start(notes=f"mode={policy.mode} limit={limit}")

    thread_ids = gmail.list_unprocessed_threads(policy.inbox_query, max_results=limit)
    summary["seen"] = len(thread_ids)
    logger.info("Producer inbox: %d unprocessed thread(s), mode=%s, dry_run=%s",
                len(thread_ids), policy.mode, dry_run)

    for tid in thread_ids:
        try:
            process_thread(tid, gmail=gmail, policy=policy, run=run,
                           summary=summary, dry_run=dry_run)
        except Exception as exc:  # noqa: BLE001 — one thread never aborts the run
            logger.exception("thread %s failed: %s", tid, exc)
            summary["failed"] += 1
            summary["errors"].append({"thread_id": tid, "error": f"{type(exc).__name__}: {exc}"[:500]})

    run.finish(summary, summary["errors"])

    by = summary["by_show"]
    text = (f"Producer inbox: {summary['seen']} seen, {summary['sent']} invited "
            f"(age_of_ai {by.get('age_of_ai', 0)} / nerra_voices {by.get('nerra_voices', 0)}), "
            f"{summary['drafted']} drafted, {summary['skipped']} skipped")
    if summary["failed"]:
        text += f", {summary['failed']} FAILED"
    if dry_run:
        text = "[dry-run] " + text
    logger.info(text)
    if not dry_run:
        notify_operator(text, critical=bool(summary["failed"]))
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Nerra Producer inbox job")
    ap.add_argument("--dry-run", action="store_true",
                    help="read Gmail and classify, but never send/draft/label/write")
    ap.add_argument("--limit", type=int, default=int(os.environ.get("PRODUCER_LIMIT", "50")),
                    help="max threads per run")
    args = ap.parse_args(argv)
    summary = run_inbox(dry_run=args.dry_run, limit=max(1, args.limit))
    seen = summary["seen"]
    if seen and summary["failed"] * 2 > seen:
        logger.error("More than half of the threads failed: %s", summary["errors"])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
