"""Mira's outbox for the Nerra Producer (Sept 28 2026).

Until now the Producer replied from Patrick's mailbox, signed "Patrick", and
on Sept 27 it answered a booked guest, Dr. Elliot Justin, as if he were a
publicist pitching himself ("Thanks for the note about Elliot Justin").
Nothing automated is signed Patrick any more: everything the Producer sends
comes from Mira, by name, and anything signed Patrick is something Patrick
wrote.

* **Sending** goes through the same transactional path as the rest of Mira's
  mail (Resend, ``From: Mira <mira@nerranetwork.com>``), as a plain-text reply
  that threads with the message it answers (In-Reply-To / References), with
  Patrick copied at both addresses. The copy to patrick@planetterrian.com is
  what keeps the conversation in the Producer's inbox.
* **Drafts** (anything held for Patrick) are written into Mira's own mailbox
  when the service account can open it, so a held reply is sent from her,
  not from him. When it cannot, nothing is drafted and the hold note to
  Patrick carries the suggested text instead.
"""

from __future__ import annotations

import base64
import logging
from email.message import EmailMessage
from typing import Any, Optional

from pipelines.voices.common import mira_from, send_email

logger = logging.getLogger("nerra_producer.mira_mail")


def reply_subject(subject: str) -> str:
    subject = (subject or "").strip()
    return subject if subject.lower().startswith("re:") else (f"Re: {subject}" if subject else "Re:")


def references_for(in_reply_to: str, references: str) -> str:
    return " ".join(x for x in [(references or "").strip(), (in_reply_to or "").strip()] if x)


class MiraMailer:
    def __init__(self, *, dry_run: bool = False, drafts_service: Any = None) -> None:
        self.dry_run = dry_run
        self.drafts_service = drafts_service
        self.sent: list = []     # what went out this run (tests, run log)

    @classmethod
    def from_env(cls, *, dry_run: bool = False, drafts_service: Any = None) -> "MiraMailer":
        return cls(dry_run=dry_run, drafts_service=drafts_service)

    def send(self, *, to: str, subject: str, body_text: str,
             in_reply_to: str = "", references: str = "") -> Optional[str]:
        subject = reply_subject(subject)
        headers = {"In-Reply-To": (in_reply_to or "").strip(),
                   "References": references_for(in_reply_to, references)}
        record = {"to": to, "subject": subject, "body": body_text, "headers": headers}
        self.sent.append(record)
        if self.dry_run:
            logger.info("[dry-run] Mira would send to %s: %s", to, subject)
            return None
        send_email(to, subject, "", cc_operator=True, text_body=body_text,
                   headers=headers)
        logger.info("Mira sent to %s: %s", to, subject)
        return "sent"

    def draft(self, *, to: str, subject: str, body_text: str,
              in_reply_to: str = "", references: str = "") -> Optional[str]:
        """A held reply, drafted in Mira's mailbox; None when that mailbox is
        not reachable (the hold note then carries the text)."""
        if self.dry_run or self.drafts_service is None:
            if self.drafts_service is None:
                logger.info("No draft for %s: Mira's mailbox not connected", to)
            return None
        msg = EmailMessage()
        msg.set_content(body_text, subtype="plain", charset="utf-8", cte="8bit")
        msg["From"] = mira_from()
        msg["To"] = to
        msg["Subject"] = reply_subject(subject)
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
        refs = references_for(in_reply_to, references)
        if refs:
            msg["References"] = refs
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
        try:
            resp = self.drafts_service.users().drafts().create(
                userId="me", body={"message": {"raw": raw}}).execute()
            return resp.get("id")
        except Exception as exc:  # noqa: BLE001 — the hold note still has the text
            logger.warning("draft in Mira's mailbox failed: %s", exc)
            return None
