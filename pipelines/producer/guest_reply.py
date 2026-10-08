"""Nerra Producer — a guest writing back to Mira (Sept 28 2026).

On Sept 27 Dr. Elliot Justin answered Mira's prep brief with the point he
most wanted to make on the show. The inbox job did not recognise the thread
(its subject list had drifted from the brief's actual subject), classified
his message as a publicist's pitch *about Elliot Justin*, found him booked,
and sent him, from Patrick's address, "Thanks for the note about Elliot
Justin. Elliot is already booked with Mira...". Patrick had to apologise.

A guest replying to Mira is now recognised by who they are (their own
address on an application that has an interview) and by the thread (it
contains a message from Mira), never by subject line, and answered here:

* ``interview_input``  the substance is filed on the application
  (``guest_notes``), reaches Mira's interview prompt, and she says thank
  you and what she will do with it;
* ``question`` / ``reschedule`` / ``cancel``  a short answer from facts
  read off the rows (time, studio link, move-or-cancel link, booking link),
  never guessed;
* ``thanks`` / ``auto_reply``  labelled, no reply (no mail for the sake of
  mail);
* anything else, low confidence, a reply that fails the guard, or a fourth
  exchange in one thread  held: nothing is sent, and Patrick is emailed at
  once with what they said, why it was held and what Mira would have said.

Everything sent comes from Mira (pipelines/producer/mira_mail.py).
"""

from __future__ import annotations

import html as _html
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from pipelines.voices.common import (
    OPERATOR_EMAIL, mira_signature_text, sb_select, sb_update, send_email,
)
from pipelines.voices.shows import get_show
from pipelines.producer import classify as _classify

logger = logging.getLogger("nerra_producer.guest_reply")

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "guest_reply.txt")
INTENTS = ("interview_input", "question", "reschedule", "cancel", "thanks",
           "auto_reply", "needs_patrick")
REPLY_INTENTS = ("interview_input", "question", "reschedule", "cancel")
MIN_CONFIDENCE = 0.7
MAX_REPLY_CHARS = 1400
MAX_MIRA_REPLIES_PER_THREAD = 3
ALWAYS_ANSWER_INTENTS = ("reschedule", "cancel")   # the reply cap never holds these
APP_COLUMNS = ("id,name,email,phone,show,status,publicist_name,publicist_email,"
               "guest_notes,guest_agenda,desired_minutes")
UPCOMING = ("scheduled", "briefed")
RECORDED = ("in_progress", "completed", "editorial_review", "guest_review", "on_hold",
            "approved")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(iso: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def when_text(iso: Any, guest_tz: Optional[str] = None) -> str:
    from pipelines.voices.common import pacific_time
    return pacific_time(iso, guest_tz)


def first_name(name: Optional[str]) -> str:
    from pipelines.producer.inbox import first_name as _fn
    text = re.sub(r"^(?:(?:dr|doctor|prof|professor|mr|mrs|ms|mx)\.?\s+)+", "",
                  (name or "").strip(), flags=re.I)
    return _fn(text) or "there"


# ---------------------------------------------------------------------------
# Who is writing
# ---------------------------------------------------------------------------

def interviews_for(app_id: str) -> List[Dict[str, Any]]:
    return sb_select("interviews",
                     f"application_id=eq.{app_id}&select=id,status,scheduled_at,show,"
                     "call_mode,manage_token,cancel_reason,guest_timezone&order=scheduled_at.desc")


def find_guest(sender_email: str) -> Optional[Dict[str, Any]]:
    """The guest behind an address: their own application (or, failing that,
    the one application this address represents as publicist) that has an
    interview or was approved. None for anyone else."""
    addr = (sender_email or "").strip().lower()
    if "@" not in addr:
        return None
    q = quote(addr, safe="@.")
    for field, role in (("email", "guest"), ("publicist_email", "publicist")):
        rows = sb_select("guest_applications",
                         f"{field}=ilike.{q}&status=neq.withdrawn&select={APP_COLUMNS}"
                         "&order=created_at.desc")
        found = []
        for app in rows:
            ivs = interviews_for(app["id"])
            if ivs or app.get("status") == "approved":
                found.append({"app": app, "interviews": ivs, "role": role})
        if len(found) == 1 or (found and role == "guest"):
            return found[0]
        if len(found) > 1:
            # A publicist with several guests: which one this is about is a
            # question for a person, not a guess.
            return {"app": None, "interviews": [], "role": "publicist_ambiguous",
                    "candidates": [f["app"].get("name") for f in found]}
    return None


def thread_has_mira(thread: Dict[str, Any]) -> bool:
    from pipelines.producer.gmail_client import mira_mailbox
    mira = mira_mailbox()
    return any((m.get("from_email") or "").lower() == mira for m in thread.get("messages") or [])


# ---------------------------------------------------------------------------
# Facts, read off the rows
# ---------------------------------------------------------------------------

def booking_url(show_slug: str) -> str:
    from pipelines.producer.followup import booking_url as _b
    return _b(show_slug)


def facts_for(guest: Dict[str, Any]) -> Dict[str, Any]:
    """What Mira may say, and the only links she may use."""
    app = guest["app"]
    ivs = guest.get("interviews") or []
    show = get_show((ivs[0].get("show") if ivs else None) or app.get("show") or "age_of_ai")
    now = datetime.now(timezone.utc)
    # Oct 2 2026: an interview that started a few minutes ago is still the
    # one to help with (Jason Fishman wrote eight minutes in and the facts
    # said he had nothing booked).
    soon_past = now - timedelta(minutes=LIVE_BEHIND_MIN)
    upcoming = next((iv for iv in reversed(ivs) if iv.get("status") in UPCOMING + ("in_progress",)
                     and (_parse(iv.get("scheduled_at")) or now) > soon_past), None)
    latest = ivs[0] if ivs else None
    lines: List[str] = []
    links: List[str] = [show.page_url, show.base_url]
    if upcoming:
        studio = f"{show.studio_url(upcoming['id'])}&role=guest"
        standing = f"booked for {when_text(upcoming.get('scheduled_at'), upcoming.get('guest_timezone'))}, not yet recorded"
        lines.append(f"- The interview is on {when_text(upcoming.get('scheduled_at'), upcoming.get('guest_timezone'))}. "
                     f"It lasts about {app.get('desired_minutes') or 45} minutes.")
        if (upcoming.get("call_mode") or "webrtc") == "webrtc":
            lines.append(f"- Their personal studio link (it opens ten minutes before the start): {studio}")
            lines.append(f"- The 30-second microphone and headphones test, any time before: {studio}&test=1")
            lines.append("- Join from a computer with headphones or earbuds. If the computer gives "
                         "trouble, they can open the same link in their phone's browser with earbuds "
                         "in (far better sound than a call); a call from you, via the studio's "
                         "'Have Mira call my phone' button, is the last resort.")
            links += [studio, f"{studio}&test=1"]
        else:
            lines.append("- You will call their phone at that time.")
        if upcoming.get("manage_token"):
            manage = f"https://api.nerranetwork.com/voices/manage/{quote(upcoming['manage_token'], safe='')}"
            lines.append(f"- To move or cancel, one tap: {manage}")
            links.append(manage)
        lines.append("- About a day before, they receive a short brief with the themes you plan to explore.")
    elif latest and latest.get("status") in RECORDED and _redo_agreed(latest["id"]):
        standing = ("they asked to record the interview again and that was agreed; the first "
                    "recording will not be published")
        lines.append("- The first recording will not be published. A new interview has been "
                     "agreed and will be set up around the subject and points they sent.")
        url = booking_url(show.slug)
        if url:
            lines.append(f"- They can book the new interview here: {url}")
            links.append(url)
    elif latest and latest.get("status") in RECORDED:
        standing = f"interview recorded ({latest.get('status')}); the episode is in production or review"
        lines.append("- The interview is recorded. They will get (or have had) an email with a link "
                     "to hear the episode and approve it before it publishes.")
    elif latest and latest.get("status") == "published":
        standing = "their episode is published"
        lines.append("- Their episode is published on the show page.")
    elif latest and latest.get("status") in ("cancelled", "missed", "failed"):
        standing = (f"their last interview did not happen ({latest.get('status')}"
                    f"{': ' + str(latest.get('cancel_reason'))[:120] if latest.get('cancel_reason') else ''}); "
                    "they are welcome to book again")
        url = booking_url(show.slug)
        if url:
            lines.append(f"- They can book a new time here: {url}")
            links.append(url)
    else:
        standing = "approved to be a guest, not yet booked"
        url = booking_url(show.slug)
        if url:
            lines.append(f"- They can pick a time here, booking with their own email address: {url}")
            links.append(url)
    agenda = app.get("guest_agenda") if isinstance(app.get("guest_agenda"), dict) else {}
    if agenda.get("points"):
        lines.append("- The points they asked you to cover in the interview (already on file): "
                     + " | ".join(str(x) for x in agenda["points"][:8]))
    return {"show": show, "standing": standing, "facts": "\n".join(lines) or "- (none)",
            "links": [l for l in links if l], "upcoming": upcoming}


def _redo_agreed(interview_id: str) -> bool:
    try:
        rows = sb_select("editorial_packages",
                         f"interview_id=eq.{interview_id}&guest_followup=eq.redo&select=id&limit=1")
    except Exception:  # noqa: BLE001 — unknown means no
        return False
    return bool(rows)


# ---------------------------------------------------------------------------
# The model, and the guard on what it writes
# ---------------------------------------------------------------------------

class GuestReplyError(ValueError):
    pass


def build_prompt(thread: Dict[str, Any], guest: Dict[str, Any], facts: Dict[str, Any],
                 own_email: str) -> str:
    from pipelines.producer.followup import _render_thread
    app = guest["app"]
    subs = {
        "show_name": facts["show"].name,
        "guest_name": app.get("name") or "the guest",
        "guest_first": first_name(app.get("name")),
        "guest_email": app.get("email") or "",
        "standing": facts["standing"] + (" (this message is from their publicist or assistant)"
                                         if guest.get("role") == "publicist" else ""),
        "facts": facts["facts"],
        "thread": _render_thread(thread, own_email),
    }
    text = open(PROMPT_PATH, encoding="utf-8").read()
    for k, v in subs.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def validate(obj: Any) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        raise GuestReplyError("must be a JSON object")
    intent = obj.get("intent")
    if intent not in INTENTS:
        raise GuestReplyError(f"bad intent {intent!r}")
    conf = obj.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= float(conf) <= 1:
        raise GuestReplyError("confidence must be a number in 0..1")
    reply = obj.get("reply_text")
    if reply is not None and not isinstance(reply, str):
        raise GuestReplyError("reply_text must be a string or null")
    note = obj.get("interview_note")
    if note is not None and not isinstance(note, str):
        raise GuestReplyError("interview_note must be a string or null")
    agenda = obj.get("agenda")
    if agenda is not None:
        if not isinstance(agenda, dict):
            raise GuestReplyError("agenda must be an object or null")
        pts = agenda.get("points") or []
        if not isinstance(pts, list) or not all(isinstance(x, str) for x in pts):
            raise GuestReplyError("agenda.points must be a list of strings")
        topic = agenda.get("topic")
        agenda = {"topic": (" ".join(topic.split())[:500] if isinstance(topic, str) else None),
                  "points": [" ".join(x.split())[:400] for x in pts if x.strip()][:8]}
        if not agenda["topic"] and not agenda["points"]:
            agenda = None
    reply = (reply or "").strip() or None
    if intent not in REPLY_INTENTS:
        reply = None
    elif not reply:
        raise GuestReplyError(f"intent {intent} requires reply_text")
    return {"intent": intent, "confidence": float(conf), "reply_text": reply,
            "interview_note": (note or "").strip()[:900] or None,
            "agenda": agenda,
            "summary": " ".join(str(obj.get("summary") or "").split())[:160]}


_URL = re.compile(r"https?://[^\s<>\"')\]]+")
_BANNED = (re.compile(r"thanks for the note about", re.I),
           re.compile(r"^\s*(sincerely|best|regards|cheers)[,.]?\s*$", re.I | re.M),
           re.compile(r"\bpatrick\s*$", re.I))


def guard(reply: str, allowed_links: List[str]) -> str:
    """Why a reply must not go out as written, or "" when it may."""
    if len(reply) > MAX_REPLY_CHARS:
        return f"reply is {len(reply)} characters"
    if not reply.lower().startswith("hi "):
        return "reply does not open with the guest's name"
    for url in _URL.findall(reply):
        url = url.rstrip(".,;:")
        if not any(url == a or url.startswith(a) and a.startswith("http") and
                   url[len(a):len(a) + 1] in ("", "&", "?", "/", "#") for a in allowed_links):
            return f"reply contains a link that is not on file: {url[:80]}"
    for pat in _BANNED:
        if pat.search(reply):
            return f"reply has a form we never send ({pat.pattern[:40]})"
    return ""


def finish(reply: str, show_slug: str) -> str:
    text = reply.replace(" — ", ", ").replace("—", ", ").replace("–", "-").replace("\r\n", "\n").strip()
    return f"{text}\n\n{mira_signature_text(show_slug)}\n"


def _call_grok(prompt: str) -> str:
    from digests.xai_grok import grok_generate_text
    text, _meta = grok_generate_text(
        prompt=prompt, model=_classify.PRODUCER_MODEL, temperature=0.2, max_tokens=900,
        timeout_seconds=float(os.environ.get("NERRA_LLM_TIMEOUT_SECONDS", "180")))
    return (text or "").strip()


def plan(thread: Dict[str, Any], guest: Dict[str, Any], facts: Dict[str, Any],
         own_email: str) -> Dict[str, Any]:
    prompt = build_prompt(thread, guest, facts, own_email)
    last: Optional[Exception] = None
    for p in (prompt, prompt + "\n\nYour previous answer was not valid JSON matching the "
                               "schema. Return ONLY the JSON object."):
        try:
            return validate(_classify._parse(_call_grok(p)))
        except (GuestReplyError, ValueError, json.JSONDecodeError) as exc:
            last = exc
            logger.warning("guest-reply plan invalid for thread %s: %s", thread.get("id"), exc)
    return {"intent": "needs_patrick", "confidence": 0.0, "reply_text": None,
            "interview_note": None, "agenda": None,
            "summary": f"model output invalid twice: {last}"[:160]}


# ---------------------------------------------------------------------------
# Acting
# ---------------------------------------------------------------------------

def mira_replies_in(thread: Dict[str, Any], own_email: str) -> int:
    own = _classify._own_set(own_email)
    msgs = thread.get("messages") or []
    first_guest = next((i for i, m in enumerate(msgs)
                        if (m.get("from_email") or "").lower() not in own), len(msgs))
    return sum(1 for m in msgs[first_guest:] if (m.get("from_email") or "").lower() in own)


def file_note(app: Dict[str, Any], text: str, thread_id: str, dry_run: bool) -> None:
    notes = app.get("guest_notes") if isinstance(app.get("guest_notes"), list) else []
    if any((n or {}).get("thread_id") == thread_id and (n or {}).get("text") == text for n in notes):
        return
    notes = (notes + [{"at": _now(), "text": text, "thread_id": thread_id,
                       "source": "email"}])[-12:]
    if dry_run:
        logger.info("[dry-run] would file a note for %s: %s", app.get("name"), text[:120])
        return
    sb_update("guest_applications", f"id=eq.{app['id']}", {"guest_notes": notes})
    app["guest_notes"] = notes


def file_agenda(app: Dict[str, Any], agenda: Dict[str, Any], dry_run: bool) -> None:
    """The guest's own subject and points (Sept 29 2026, Chad Law). New
    points replace old ones; a topic is kept unless a new one is given."""
    old = app.get("guest_agenda") if isinstance(app.get("guest_agenda"), dict) else {}
    new = {"topic": agenda.get("topic") or old.get("topic"),
           "points": agenda.get("points") or old.get("points") or [],
           "updated_at": _now(), "source": "email"}
    if dry_run:
        logger.info("[dry-run] would file an agenda for %s: %s", app.get("name"), new)
        return
    sb_update("guest_applications", f"id=eq.{app['id']}", {"guest_agenda": new})
    app["guest_agenda"] = new


def tell_patrick(*, guest_name: str, show_name: str, inbound: Dict[str, Any],
                 reason: str, suggestion: str, thread_url: str, dry_run: bool) -> None:
    """Held: nothing went to the guest, so Patrick hears about it now, not in
    tomorrow's digest."""
    import html as _h
    said = _classify.truncate(inbound.get("body") or inbound.get("snippet") or "", 1500)
    from pipelines.producer.followup import _strip_quoted
    said = _strip_quoted(said)
    body = (f"<p>Hi Patrick,</p><p>{_h.escape(guest_name)} wrote to me about {_h.escape(show_name)} "
            f"and I have not answered, because {_h.escape(reason)}.</p>"
            f"<p><strong>What they wrote:</strong></p>"
            f"<blockquote style=\"border-left:3px solid #cbd5e0;margin:0;padding:.2em 1em;color:#2d3748\">"
            f"{_h.escape(said).replace(chr(10), '<br>')}</blockquote>")
    if suggestion:
        body += ("<p><strong>What I would have said:</strong></p>"
                 "<blockquote style=\"border-left:3px solid #cbd5e0;margin:0;padding:.2em 1em;color:#2d3748\">"
                 f"{_h.escape(suggestion).replace(chr(10), '<br>')}</blockquote>")
    body += (f"<p>Reply to them yourself, or tell me what to say. "
             f"<a href=\"{_h.escape(thread_url)}\">Open the thread</a>.</p><p>Mira</p>")
    if dry_run:
        logger.info("[dry-run] would email Patrick: %s held (%s)", guest_name, reason)
        return
    try:
        from pipelines.producer import inbox as _inbox
        _inbox.notify_operator(f"{guest_name} replied to one of Mira's emails and is held for "
                               f"Patrick: {reason}. {thread_url}")
    except Exception:  # noqa: BLE001 — Slack is a nicety
        pass
    try:
        send_email(OPERATOR_EMAIL, f"{guest_name} wrote to me: needs you", body)
    except Exception as exc:  # noqa: BLE001 — the digest still lists it
        logger.warning("hold email to Patrick failed: %s", exc)


# Oct 2 2026. Jonathan Bautista ("im in the room but no one is joining?")
# and Jason Fishman ("Says waiting for others to join. I am in") wrote during
# their slots. Both were held for Patrick, and Jason's reached him thirteen
# minutes later. A guest who can't get in during their slot is answered at
# once, from facts, without waiting on a model: the studio link, the steps,
# the phone's browser, and the call as the last resort.
LIVE_BEHIND_MIN = 60
LIVE_AHEAD_MIN = 20
_LIVE_TROUBLE = re.compile(
    r"(waiting for (others|someone|you|the host|mira)|no ?one (is )?(here|joining|joined|there|in)"
    r"|nobody|can'?t (join|get in|connect|hear|find)|cannot (join|connect|get in)|unable to (join|connect)"
    r"|(isn'?t|is not|not|doesn'?t) work|\bi'?m in\b|\bi am in\b|\bin the room\b|where are you"
    r"|are you (there|coming)|still waiting|i'?m here|i am here|i'?m (ready|waiting)|i am (ready|waiting))",
    re.I)
_QUOTE_START = re.compile(r"^(on .+wrote:|-{2,}\s*original message|from:\s|>)", re.I | re.M)


def live_interview(guest: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    for iv in (guest or {}).get("interviews") or []:
        at = _parse(iv.get("scheduled_at"))
        if (iv.get("status") in UPCOMING + ("in_progress",) and at
                and now - timedelta(minutes=LIVE_BEHIND_MIN) <= at <= now + timedelta(minutes=LIVE_AHEAD_MIN)):
            return iv
    return None


def own_words(body: str) -> str:
    """The guest's message without the quoted email underneath it."""
    m = _QUOTE_START.search(body or "")
    return (body[:m.start()] if m else (body or ""))[:800]


def live_trouble_reply(app: Dict[str, Any], iv: Dict[str, Any], show: Any) -> str:
    studio = f"{show.studio_url(iv['id'])}&role=guest"
    if (iv.get("call_mode") or "webrtc") != "webrtc":
        return (f"Hi {first_name(app.get('name'))},\n\nThank you, I'm calling your phone for our "
                f"interview, so please keep it nearby. If you'd rather join from your computer, "
                f"here's your studio link: {studio}\n\nI'm here and ready.")
    return (
        f"Hi {first_name(app.get('name'))},\n\nI'm here and ready, and I'm sorry for the trouble. "
        "If you're in a video room from a calendar invite, that isn't my studio, so we can't meet "
        f"there. Here's your personal studio link:\n{studio}\n\n"
        "1. Open it on your computer, headphones on.\n"
        "2. Press Check my microphone and read the sentence out loud until it says Sounds good.\n"
        "3. Press Join your interview. You're in when you hear me say hello.\n\n"
        "If your computer gives you trouble, open the same link in your phone's browser with "
        "earbuds in. It sounds far better than a phone call. As a last resort, the studio's "
        "Have Mira call my phone button has me calling you straight away.")


def handle_guest_reply(*, thread: Dict[str, Any], inbound: Dict[str, Any],
                       guest: Optional[Dict[str, Any]], gmail: Any, policy: Any,
                       dry_run: bool) -> Dict[str, Any]:
    line: Dict[str, Any] = {"thread_id": thread["id"], "kind": "guest_reply",
                            "subject": thread.get("subject"), "from": inbound.get("from_email")}
    app = (guest or {}).get("app")
    show_name = "the show"
    from pipelines.producer.inbox import newest_is_inbound
    if not newest_is_inbound(thread, gmail.user):
        # Someone on our side (Patrick by hand, or Mira) has already answered
        # after their last message: never answer twice.
        line.update(action="label", reason="already answered in the thread")
        gmail.add_label(thread["id"], policy.processed_label)
        return line
    if inbound.get("auto_submitted"):
        line.update(action="label", reason="autoresponder")
        gmail.add_label(thread["id"], policy.processed_label)
        return line
    if not app:
        why = ("they wrote into one of my threads but I can't tell which guest it is about"
               + (f" ({', '.join(guest.get('candidates') or [])})" if guest and guest.get("candidates") else ""))
        line.update(action="draft", reason=why)
        gmail.add_label(thread["id"], policy.hold_label)
        tell_patrick(guest_name=inbound.get("from_name") or inbound.get("from_email") or "Someone",
                     show_name=show_name, inbound=inbound, reason=why, suggestion="",
                     thread_url=thread.get("url", ""), dry_run=dry_run)
        gmail.add_label(thread["id"], policy.processed_label)
        return line
    facts = facts_for(guest)
    show = facts["show"]
    line.update(guest_name=app.get("name"), application_id=app.get("id"), show=show.slug)

    live = live_interview(guest)
    if (live and policy.mode == "auto"
            and _LIVE_TROUBLE.search(own_words(inbound.get("body") or ""))
            and mira_replies_in(thread, gmail.user) < MAX_MIRA_REPLIES_PER_THREAD + 2):
        body = finish(live_trouble_reply(app, live, show), show.slug)
        gmail.send_reply(body_text=body, thread_id=thread["id"],
                         to=inbound.get("from") or inbound.get("from_email", ""),
                         subject=thread.get("subject") or inbound.get("subject", ""),
                         in_reply_to=inbound.get("message_id", ""),
                         references=inbound.get("references", ""))
        gmail.add_label(thread["id"], policy.processed_label)
        line.update(action="send", intent="live_join_help", reason="guest can't get in during their slot")
        try:
            send_email(OPERATOR_EMAIL, f"{app.get('name') or 'A guest'} couldn't get into the studio",
                       f"<p>Hi Patrick,</p><p>{_html.escape(app.get('name') or 'A guest')} wrote during their interview "
                       f"slot that they couldn't get in, so I answered straight away with their studio "
                       f"link and the steps. I'll keep an eye out; if they still aren't in a few minutes "
                       f"after the start, you'll get the usual email with a one-click phone switch.</p>"
                       f"<p>What they wrote: <em>{_html.escape(own_words(inbound.get('body') or '')[:400])}</em></p><p>Mira</p>")
        except Exception as exc:  # noqa: BLE001 — the guest has their answer
            logger.warning("live-help note to Patrick failed: %s", exc)
        return line
    p = plan(thread, guest, facts, gmail.user)
    line.update(intent=p["intent"], confidence=p["confidence"], summary=p["summary"])

    if p.get("agenda"):
        try:
            file_agenda(app, p["agenda"], dry_run)
            line["agenda_filed"] = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("filing the guest agenda failed: %s", exc)
    if p["intent"] == "interview_input" and (p.get("interview_note") or not p.get("agenda")):
        note = p.get("interview_note") or _classify.truncate(inbound.get("body") or "", 900)
        try:
            file_note(app, note, thread["id"], dry_run)
            line["note_filed"] = True
        except Exception as exc:  # noqa: BLE001 — the reply still goes; Patrick is told
            logger.warning("filing the guest note failed: %s", exc)

    reason = ""
    body = ""
    if p["intent"] in ("thanks", "auto_reply") and p["confidence"] >= MIN_CONFIDENCE:
        line.update(action="label", reason=f"intent={p['intent']}; nothing to answer")
        gmail.add_label(thread["id"], policy.processed_label)
        return line
    if p["intent"] not in REPLY_INTENTS:
        reason = p["summary"] or "it needs a person"
    elif p["confidence"] < MIN_CONFIDENCE:
        reason = f"I was only {p['confidence']:.0%} sure what they wanted"
    elif policy.mode != "auto":
        reason = f"the Producer is in {policy.mode} mode"
    # Oct 7 2026 (Dr. Jason Shumard): his team wrote on Oct 5 that he could
    # not make Oct 7 and asked to move it. Mira had already answered three
    # times in that thread (the sound note, a confirmation), so she held the
    # reply for Patrick, and nobody answered for two days; the studio would
    # have opened for a guest who had told us he was not coming. A guest who
    # needs to move or cancel always gets the way to do it.
    elif (p["intent"] not in ALWAYS_ANSWER_INTENTS
          and mira_replies_in(thread, gmail.user) >= MAX_MIRA_REPLIES_PER_THREAD):
        reason = "I have already answered three times in this thread"
    else:
        reason = guard(p["reply_text"] or "", facts["links"])
    if p.get("reply_text"):
        body = finish(p["reply_text"], show.slug)

    kwargs = dict(thread_id=thread["id"],
                  to=inbound.get("from") or inbound.get("from_email", ""),
                  subject=thread.get("subject") or inbound.get("subject", ""),
                  in_reply_to=inbound.get("message_id", ""),
                  references=inbound.get("references", ""))
    if not reason:
        gmail.send_reply(body_text=body, **kwargs)
        line.update(action="send", reason=f"intent={p['intent']}")
    else:
        if body:
            line["draft_created"] = bool(gmail.create_draft(body_text=body, **kwargs))
        gmail.add_label(thread["id"], policy.hold_label)
        line.update(action="draft", reason=reason)
        tell_patrick(guest_name=app.get("name") or "A guest", show_name=show.name,
                     inbound=inbound, reason=reason, suggestion=body,
                     thread_url=thread.get("url", ""), dry_run=dry_run)
    gmail.add_label(thread["id"], policy.processed_label)
    return line
