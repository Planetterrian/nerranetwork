"""Nerra Producer — follow-up replies on threads we already answered.

Until September 2026 a publicist who wrote back ("which dates?", "yes,
send the link", "can you tell me more about the format?") was skipped:
the thread already had a ``guest_applications`` row, so the inbox job
filed the new message as processed and nobody answered. This module is
that missing conversation.

Flow (called from ``inbox.process_thread`` when the thread is already in
the DB and its newest message is inbound):

1. autoresponder / bounce → label, nothing else;
2. ask Grok (``grok-latest``) for an intent + Patrick-voice reply, with a
   fixed FAQ of facts it may use (``prompts/followup_reply.txt``);
3. ``ready_to_book`` → reply with the show's Cal.com link in-thread and
   flip the application to ``approved`` (no form needed — the Producer
   already stored bio/topics/links from the pitch);
   ``question`` / ``later`` → reply; ``decline`` → short thanks, row
   ``declined``; ``needs_patrick`` or low confidence → Gmail draft + hold
   label, surfaced in the daily digest;
4. bookkeeping on the row (``producer_followup_count``,
   ``producer_last_*``), and a cap: after four Producer replies in one
   thread everything further is held for Patrick.

Every send goes through the same voice guard as the invite: the sign-off
is normalised to "Sincerely, / Patrick" and any em dash is replaced.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.voices.common import parse_json_lenient, sb_update  # noqa: E402
from pipelines.voices.shows import get_show  # noqa: E402
from pipelines.producer import classify as _classify  # noqa: E402

logger = logging.getLogger("nerra_producer.followup")

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "followup_reply.txt"
INTENTS = ("ready_to_book", "question", "later", "decline", "needs_patrick", "auto_reply")
MAX_FOLLOWUPS_PER_THREAD = 4
MIN_CONFIDENCE = 0.7
MAX_THREAD_MESSAGES = 8
MAX_MESSAGE_CHARS = 1800

SIGN_OFF = "Sincerely,\n\nPatrick"


class FollowupError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Booking links (same secrets the Worker uses, mirrored into GitHub)
# ---------------------------------------------------------------------------

def booking_url(show_slug: str) -> str:
    slug = (show_slug or "age_of_ai").strip()
    if slug == "nerra_voices":
        url = os.environ.get("CALCOM_BOOKING_URL_NERRA_VOICES", "").strip()
        if url:
            return url
    return os.environ.get("CALCOM_BOOKING_URL", "").strip()


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def _render_thread(thread: Dict[str, Any], own_email: str) -> str:
    own = _classify._own_set(own_email)
    msgs = (thread.get("messages") or [])[-MAX_THREAD_MESSAGES:]
    out: List[str] = []
    for m in msgs:
        who = "OURS (Patrick)" if (m.get("from_email") or "").lower() in own else (m.get("from") or "unknown")
        body = _classify.truncate(m.get("body") or m.get("snippet") or "", MAX_MESSAGE_CHARS)
        body = _strip_quoted(body)
        out.append(f"--- From: {who} | {m.get('date') or ''}\n{body}")
    return "\n\n".join(out)


_QUOTE_RE = re.compile(r"\n(On .{5,120} wrote:|-----Original Message-----|From: .{3,120}\nSent: ).*",
                       re.S)


def _strip_quoted(body: str) -> str:
    """Drop the quoted history under a reply (keeps the prompt small and
    stops the model re-reading our own invite as if it were new)."""
    m = _QUOTE_RE.search(body)
    if m and body[:m.start()].strip():
        body = body[:m.start()]
    lines = [ln for ln in body.splitlines() if not ln.lstrip().startswith(">")]
    return "\n".join(lines).strip()


def build_prompt(thread: Dict[str, Any], app: Dict[str, Any], own_email: str,
                 policy: Any) -> str:
    show = get_show(app.get("show") or "nerra_voices")
    template = PROMPT_PATH.read_text(encoding="utf-8")
    pitched = policy.pitched_show_name(app.get("pitched_show")) if policy else ""
    subs = {
        "show_name": show.name,
        "show_blurb": policy.blurb(show.slug) if policy else "",
        "page_url": show.page_url,
        "apply_url": show.apply_url,
        "booking_url": booking_url(show.slug) or "(booking link unavailable, use needs_patrick)",
        "pitched_show_name": pitched,
        "thread": _render_thread(thread, own_email),
        "guest_name": app.get("name") or "the guest",
        "contact_name": app.get("publicist_name") or app.get("name") or "",
        "contact_email": app.get("publicist_email") or app.get("email") or "",
    }
    # Minimal jinja-ish conditional used by the prompt for the pitched show.
    if pitched:
        template = re.sub(r"\{% if pitched_show_name %\}(.*?)\{% endif %\}", r"\1", template, flags=re.S)
    else:
        template = re.sub(r"\{% if pitched_show_name %\}.*?\{% endif %\}", "", template, flags=re.S)
    for key, value in subs.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


# ---------------------------------------------------------------------------
# Model output
# ---------------------------------------------------------------------------

def validate_followup(obj: Any) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        raise FollowupError("must be a JSON object")
    intent = obj.get("intent")
    if intent not in INTENTS:
        raise FollowupError(f"bad intent {intent!r}")
    conf = obj.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= float(conf) <= 1:
        raise FollowupError("confidence must be a number in 0..1")
    reply = obj.get("reply_text")
    if reply is not None and not isinstance(reply, str):
        raise FollowupError("reply_text must be a string or null")
    summary = obj.get("summary")
    if not isinstance(summary, str):
        raise FollowupError("summary must be a string")
    reply = (reply or "").strip() or None
    if intent in ("ready_to_book", "question", "later", "decline") and not reply:
        raise FollowupError(f"intent {intent} requires reply_text")
    return {
        "intent": intent,
        "confidence": float(conf),
        "reply_text": reply,
        "summary": " ".join(summary.split())[:160],
    }


_SIGNOFF_RE = re.compile(
    r"\n\s*(sincerely|best|best regards|regards|thanks|thank you|cheers|warmly|kind regards)[,.]?\s*\n+\s*patrick(\s+novak)?\s*$",
    re.I)


def normalise_voice(text: str) -> str:
    """Patrick's voice guard: no em dashes, one canonical sign-off."""
    text = (text or "").replace(" — ", ", ").replace("—", ", ").replace("–", "-")
    text = text.replace("\r\n", "\n").rstrip()
    text = _SIGNOFF_RE.sub("", text).rstrip()
    return f"{text}\n\n{SIGN_OFF}\n"


def ensure_booking_link(text: str, url: str) -> str:
    if not url or url in text:
        return text
    body, _, _ = text.rpartition("\n\nSincerely,")
    if not body:
        body = text.rstrip()
    return f"{body}\n\nHere is the booking link:\n{url}\n\n{SIGN_OFF}\n"


def _call_grok(prompt: str) -> str:
    from digests.xai_grok import grok_generate_text
    text, _meta = grok_generate_text(
        prompt=prompt, model=_classify.PRODUCER_MODEL, temperature=0.2,
        max_tokens=900, timeout_seconds=float(os.environ.get("NERRA_LLM_TIMEOUT_SECONDS", "180")),
    )
    return (text or "").strip()


def plan_followup(thread: Dict[str, Any], app: Dict[str, Any], own_email: str,
                  policy: Any) -> Dict[str, Any]:
    """Ask the model once (strict retry once); on failure hold for Patrick."""
    prompt = build_prompt(thread, app, own_email, policy)
    attempts = [prompt, prompt + "\n\nYour previous answer was not valid JSON matching the "
                                 "schema. Return ONLY the JSON object."]
    last: Optional[Exception] = None
    for p in attempts:
        try:
            raw = _call_grok(p)
            return validate_followup(_classify._parse(raw))
        except (FollowupError, ValueError, json.JSONDecodeError) as exc:
            last = exc
            logger.warning("follow-up plan invalid for thread %s: %s", thread.get("id"), exc)
    return {"intent": "needs_patrick", "confidence": 0.0, "reply_text": None,
            "summary": f"model output invalid twice: {last}"[:160]}


# ---------------------------------------------------------------------------
# Decision + action
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def decide_followup(plan: Dict[str, Any], app: Dict[str, Any], *, mode: str,
                    inbound_auto: bool) -> Dict[str, Any]:
    """Pure: plan + row facts → {action: send|draft|label|skip, reason,
    status_patch}. ``send`` only in auto mode."""
    if mode == "off":
        return {"action": "skip", "reason": "mode=off"}
    if inbound_auto or plan["intent"] == "auto_reply":
        return {"action": "label", "reason": "autoresponder / bounce"}
    count = int(app.get("producer_followup_count") or 0)
    if count >= MAX_FOLLOWUPS_PER_THREAD:
        return {"action": "draft", "reason": f"{count} Producer replies already in this thread"}
    if plan["intent"] == "needs_patrick" or not plan.get("reply_text"):
        return {"action": "draft", "reason": plan.get("summary") or "needs Patrick"}
    if plan["confidence"] < MIN_CONFIDENCE:
        return {"action": "draft", "reason": f"confidence {plan['confidence']:.2f} < {MIN_CONFIDENCE:.2f}"}
    if (app.get("status") or "") in ("declined", "lapsed") and plan["intent"] != "ready_to_book":
        return {"action": "draft", "reason": f"row is {app.get('status')}; re-opening needs Patrick"}
    patch: Dict[str, Any] = {}
    if plan["intent"] == "ready_to_book":
        patch["status"] = "approved"
    elif plan["intent"] == "decline":
        patch["status"] = "declined"
        patch["producer_closed_reason"] = "declined"
    elif plan["intent"] == "later":
        # Push the chase job out: they said they'd come back to us.
        patch["chased_at"] = _now()
    action = "send" if mode == "auto" else "draft"
    return {"action": action, "reason": f"intent={plan['intent']}", "status_patch": patch}


def handle_followup(*, thread: Dict[str, Any], inbound: Dict[str, Any],
                    app: Dict[str, Any], gmail: Any, policy: Any,
                    dry_run: bool) -> Dict[str, Any]:
    """Run the whole follow-up path for one thread. Returns a log line."""
    own = gmail.user
    inbound_auto = bool(inbound.get("auto_submitted"))
    plan = ({"intent": "auto_reply", "confidence": 1.0, "reply_text": None,
             "summary": "autoresponder"} if inbound_auto
            else plan_followup(thread, app, own, policy))
    decision = decide_followup(plan, app, mode=policy.mode, inbound_auto=inbound_auto)
    line = {
        "thread_id": thread["id"], "kind": "followup", "action": decision["action"],
        "reason": decision["reason"], "intent": plan["intent"],
        "confidence": plan["confidence"], "summary": plan["summary"],
        "application_id": app.get("id"), "guest_name": app.get("name"),
        "subject": thread.get("subject"), "from": inbound.get("from_email"),
    }
    reply_kwargs = dict(
        thread_id=thread["id"],
        to=inbound.get("from") or inbound.get("from_email", ""),
        subject=thread.get("subject") or inbound.get("subject", ""),
        in_reply_to=inbound.get("message_id", ""),
        references=inbound.get("references", ""),
    )
    body = ""
    if plan.get("reply_text"):
        body = normalise_voice(plan["reply_text"])
        if plan["intent"] == "ready_to_book":
            body = ensure_booking_link(body, booking_url(app.get("show") or ""))

    patch: Dict[str, Any] = {"producer_last_inbound_at": _now()}
    if decision["action"] == "send":
        gmail.send_reply(body_text=body, **reply_kwargs)
        patch.update(decision.get("status_patch") or {})
        patch["producer_followup_count"] = int(app.get("producer_followup_count") or 0) + 1
        patch["producer_last_outbound_at"] = _now()
        patch["producer_action"] = "followup_sent"
        patch["producer_acted_at"] = _now()
    elif decision["action"] == "draft":
        if body:
            gmail.create_draft(body_text=body, **reply_kwargs)
            line["draft_created"] = True
        gmail.add_label(thread["id"], policy.hold_label)
        patch["producer_action"] = "followup_held"
        patch["producer_acted_at"] = _now()
    # label / skip: nothing to write beyond the inbound timestamp

    if not dry_run and app.get("id"):
        try:
            sb_update("guest_applications", f"id=eq.{app['id']}", patch)
        except Exception as exc:  # noqa: BLE001 — bookkeeping never blocks the reply
            logger.warning("follow-up row update failed (non-fatal): %s", exc)
    elif dry_run:
        logger.info("[dry-run] would patch application %s: %s", app.get("id"),
                    json.dumps(patch, default=str))
    if decision["action"] != "skip":
        gmail.add_label(thread["id"], policy.processed_label)
    return line
