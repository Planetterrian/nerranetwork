"""Nerra Producer — daily summary email to Patrick.

    python -m pipelines.producer.digest [--dry-run] [--hours 24]

Patrick has no Slack, so this is the Producer's one operator channel:
a single HTML email (Resend, from Mira's address) to ``OPERATOR_EMAIL``
covering the last 24 hours — invitations sent, follow-ups answered,
booking links sent, interviews booked, nudges, lapses, errors, and
everything held for him with a Gmail link to the draft. Reads
``producer_runs`` (the inbox/chase jobs' decision logs), ``guest_applications``
and ``interviews``; writes nothing except a ``producer_runs`` row of
job ``review`` so the send itself is on record.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.voices.common import (  # noqa: E402
    OPERATOR_EMAIL, render_email, sb_insert, sb_select, send_email,
)
from pipelines.voices.shows import get_show  # noqa: E402
from pipelines.producer.gmail_client import thread_url  # noqa: E402

logger = logging.getLogger("nerra_producer.digest")
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s %(levelname)s %(message)s")

JOB = "review"
BRAND = "#0F766E"


def _iso(dt: datetime) -> str:
    """UTC timestamp for a PostgREST filter. Must not contain '+': an
    unencoded '+00:00' becomes a space in the query string and PostgREST
    answers 400 (first digest run, Sept 7 2026)."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _show_name(slug: Optional[str]) -> str:
    try:
        return get_show(slug or "age_of_ai").name
    except Exception:  # noqa: BLE001
        return slug or "Age of AI"


def _decisions(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in runs:
        try:
            notes = json.loads(r.get("notes") or "{}")
        except (TypeError, ValueError):
            continue
        for d in notes.get("decisions") or []:
            d = dict(d)
            d["_job"] = r.get("job")
            out.append(d)
    return out


def collect(since: datetime, until: Optional[datetime] = None) -> Dict[str, Any]:
    until = until or datetime.now(timezone.utc)
    runs = sb_select("producer_runs",
                     f"started_at=gte.{_iso(since)}&job=in.(inbox,chase)&order=started_at.asc&limit=200")
    decisions = _decisions(runs)
    apps = sb_select("guest_applications",
                     f"producer_acted_at=gte.{_iso(since)}&source=eq.email"
                     "&select=id,name,show,status,pitched_show,producer_action,producer_acted_at,"
                     "email_thread_id,publicist_name,producer_closed_reason&order=producer_acted_at.desc&limit=200")
    booked = sb_select("interviews",
                       f"created_at=gte.{_iso(since)}&select=id,scheduled_at,show,"
                       "guest_applications(name)&order=scheduled_at.asc&limit=50")
    invited_total = sb_select("guest_applications", "status=eq.invited&source=eq.email&select=id")
    approved_total = sb_select("guest_applications", "status=eq.approved&select=id")
    scheduled_total = sb_select("interviews", "status=in.(scheduled,briefed)&select=id")

    invited = [{"name": a.get("name"), "show": _show_name(a.get("show")),
                "pitched": a.get("pitched_show") or "", "url": thread_url(a.get("email_thread_id") or "")}
               for a in apps if a.get("producer_action") == "sent"]
    approved = [{"name": a.get("name"), "show": _show_name(a.get("show")),
                 "url": thread_url(a.get("email_thread_id") or "")}
                for a in apps if a.get("status") == "approved" and a.get("producer_action") == "followup_sent"]
    held = []
    for d in decisions:
        if d.get("action") != "draft":
            continue
        held.append({
            "subject": d.get("subject") or "", "guest": d.get("guest_name") or "",
            "sender": d.get("from") or "", "reason": d.get("summary") or d.get("reason") or "",
            "url": thread_url(d.get("thread_id") or ""),
        })
    errors: List[str] = []
    for r in runs:
        for e in (r.get("errors") or []):
            errors.append(f"{r.get('job')}: {e.get('thread_id') or e.get('application_id') or ''} {e.get('error') or ''}".strip())
    booked_rows = []
    for b in booked:
        app = b.get("guest_applications") or {}
        when = (b.get("scheduled_at") or "")[:16].replace("T", " ") + " UTC"
        booked_rows.append({"name": app.get("name") or "guest", "show": _show_name(b.get("show")), "when": when})
    followups = sum(1 for d in decisions if d.get("kind") == "followup" and d.get("action") == "send")
    stats = {
        "invited": len(invited), "followups": followups, "approved": len(approved),
        "booked": len(booked_rows),
        "chased": sum(1 for d in decisions if d.get("_job") == "chase" and d.get("action") == "sent"),
        "lapsed": sum(1 for d in decisions if d.get("_job") == "chase" and d.get("action") == "lapse"),
        "held": len(held), "errors": len(errors), "runs": len(runs),
        "invited_total": len(invited_total), "approved_total": len(approved_total),
        "scheduled_total": len(scheduled_total),
    }
    return {"stats": stats, "invited": invited, "approved": approved, "held": held,
            "booked": booked_rows, "errors": errors[:20], "since": since, "until": until}


def render(data: Dict[str, Any]) -> str:
    day = data["until"].astimezone(timezone(timedelta(hours=-7))).strftime("%A, %B %-d")
    return render_email("producer_daily_digest.j2", "nerra_voices", day=day, s=data["stats"],
                        held=data["held"], booked=data["booked"], approved=data["approved"],
                        invited=data["invited"], errors=data["errors"], brand=BRAND)


def subject_line(stats: Dict[str, Any]) -> str:
    bits = [f"{stats['invited']} invited", f"{stats['approved']} booking links",
            f"{stats['booked']} booked"]
    if stats["held"]:
        bits.append(f"{stats['held']} waiting on you")
    if stats["errors"]:
        bits.append(f"{stats['errors']} errors")
    return "Nerra Producer daily: " + ", ".join(bits)


def run_digest(*, hours: int = 24, dry_run: bool = False, to: Optional[str] = None) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    data = collect(since)
    html = render(data)
    subject = subject_line(data["stats"])
    recipient = to or OPERATOR_EMAIL
    if dry_run:
        logger.info("[dry-run] would email %s: %s\n%s", recipient, subject, html[:1500])
    else:
        send_email(recipient, subject, html)
        try:
            sb_insert("producer_runs", {"job": JOB, "finished_at": _iso(datetime.now(timezone.utc)),
                                        "notes": json.dumps({"to": recipient, "subject": subject,
                                                             "stats": data["stats"]})})
        except Exception as exc:  # noqa: BLE001
            logger.warning("producer_runs insert failed (non-fatal): %s", exc)
    logger.info("digest: %s", subject)
    return {"subject": subject, "stats": data["stats"], "html": html}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Nerra Producer daily digest")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--to", default=None)
    args = ap.parse_args(argv)
    run_digest(hours=args.hours, dry_run=args.dry_run, to=args.to)
    return 0


if __name__ == "__main__":
    sys.exit(main())
