"""Gmail access for the Nerra Producer.

Authentication is a Google service account with domain-wide delegation
impersonating the operator's Workspace mailbox:

* ``GMAIL_SERVICE_ACCOUNT_JSON`` — the service-account key file CONTENTS
  (the JSON text, not a path), stored as a GitHub secret;
* ``GMAIL_DELEGATED_USER`` — the mailbox to act as (default
  ``patrick@planetterrian.com``).

Scope is ``gmail.modify`` (read, label, send, draft). Every network call
goes through :class:`GmailClient`, which wraps a ``googleapiclient``
service object; tests hand it a fake service instead. ``dry_run=True``
makes every write (send, draft, label) a logged no-op while reads keep
working, so a dry run against the real inbox shows exactly what would
happen.
"""

from __future__ import annotations

import base64
import email.utils
import json
import logging
import os
import re
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

logger = logging.getLogger("nerra_producer.gmail")

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
DEFAULT_DELEGATED_USER = "patrick@planetterrian.com"
PROCESSED_LABEL = "Producer/Processed"
DEFAULT_QUERY = "newer_than:30d in:inbox"


def delegated_user() -> str:
    """The Workspace mailbox the service account impersonates.

    patrick@planetterrian.com is a send-as alias on the patrick@avvizo.com
    mailbox, so in production GMAIL_DELEGATED_USER=patrick@avvizo.com and
    GMAIL_SEND_AS=patrick@planetterrian.com (the From: on every reply).
    """
    return (os.environ.get("GMAIL_DELEGATED_USER", "") or DEFAULT_DELEGATED_USER).strip()


def send_as_address() -> str:
    """The From: address for replies (a configured send-as alias, or the mailbox)."""
    return (os.environ.get("GMAIL_SEND_AS", "") or delegated_user()).strip()


def own_addresses() -> tuple:
    """Every address that counts as 'us' when reading a thread."""
    return tuple({delegated_user().lower(), send_as_address().lower()})


def build_service(delegated: Optional[str] = None):
    """Build a Gmail API service impersonating the delegated user.

    Isolated so the rest of the module (and every test) never touches
    google-auth; :meth:`GmailClient.from_env` is the only caller.
    """
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    raw = os.environ.get("GMAIL_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise RuntimeError("GMAIL_SERVICE_ACCOUNT_JSON env var is required")
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    creds = creds.with_subject(delegated or delegated_user())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


# ---------------------------------------------------------------------------
# MIME helpers (pure)
# ---------------------------------------------------------------------------

def _b64url_decode(data: str) -> bytes:
    data = data.replace("-", "+").replace("_", "/")
    data += "=" * (-len(data) % 4)
    return base64.b64decode(data)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _header(headers: List[Dict[str, str]], name: str) -> str:
    for h in headers or []:
        if (h.get("name") or "").lower() == name.lower():
            return h.get("value") or ""
    return ""


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", text)
    text = _TAG_RE.sub(" ", text)
    import html as _html
    text = _html.unescape(text)
    text = _WS_RE.sub(" ", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def extract_body(payload: Dict[str, Any]) -> str:
    """Best plain-text rendering of a message payload (text/plain preferred,
    text/html stripped as a fallback)."""
    plain: List[str] = []
    html: List[str] = []

    def walk(part: Dict[str, Any]) -> None:
        mime = (part.get("mimeType") or "").lower()
        data = ((part.get("body") or {}).get("data")) or ""
        if data and mime == "text/plain":
            plain.append(_b64url_decode(data).decode("utf-8", "replace"))
        elif data and mime == "text/html":
            html.append(_b64url_decode(data).decode("utf-8", "replace"))
        for sub in part.get("parts") or []:
            walk(sub)

    walk(payload or {})
    if plain:
        return "\n".join(plain).strip()
    if html:
        return html_to_text("\n".join(html)).strip()
    return ""


def parse_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    payload = msg.get("payload") or {}
    headers = payload.get("headers") or []
    from_raw = _header(headers, "From")
    from_name, from_addr = email.utils.parseaddr(from_raw)
    return {
        "id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "label_ids": list(msg.get("labelIds") or []),
        "from": from_raw,
        "from_name": from_name,
        "from_email": from_addr.lower(),
        "to": _header(headers, "To"),
        "date": _header(headers, "Date"),
        "internal_date": int(msg.get("internalDate") or 0),
        "subject": _header(headers, "Subject"),
        "message_id": _header(headers, "Message-ID") or _header(headers, "Message-Id"),
        "in_reply_to": _header(headers, "In-Reply-To"),
        "references": _header(headers, "References"),
        "body": extract_body(payload),
        "snippet": msg.get("snippet") or "",
    }


def build_reply_mime(*, sender: str, to: str, subject: str, body_text: str,
                     in_reply_to: str = "", references: str = "") -> str:
    """Plain-text reply MIME, base64url-encoded for the Gmail API."""
    msg = EmailMessage()
    # 8bit keeps the body readable in the raw MIME (no base64 blob for a
    # plain-text note); lines stay far below the 998-char limit.
    msg.set_content(body_text, subtype="plain", charset="utf-8", cte="8bit")
    msg["From"] = sender
    msg["To"] = to
    if subject and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    msg["Subject"] = subject or "Re:"
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    refs = " ".join(x for x in [references.strip(), in_reply_to.strip()] if x)
    if refs:
        msg["References"] = refs
    return _b64url_encode(msg.as_bytes())


def thread_url(thread_id: str) -> str:
    return f"https://mail.google.com/mail/u/0/#all/{thread_id}"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class GmailClient:
    def __init__(self, service: Any, user: Optional[str] = None,
                 *, dry_run: bool = False,
                 processed_label: str = PROCESSED_LABEL) -> None:
        self.service = service
        self.user = user or delegated_user()
        # From: on replies — the send-as alias when configured, else the mailbox.
        self.send_as = (os.environ.get("GMAIL_SEND_AS", "") or self.user).strip()
        self.dry_run = dry_run
        self.processed_label = processed_label
        self._label_ids: Dict[str, str] = {}

    @classmethod
    def from_env(cls, *, dry_run: bool = False,
                 processed_label: str = PROCESSED_LABEL) -> "GmailClient":
        user = delegated_user()
        return cls(build_service(user), user, dry_run=dry_run,
                   processed_label=processed_label)

    # -- labels ------------------------------------------------------------

    def _users(self):
        return self.service.users()

    def label_id(self, name: str, create: bool = True) -> Optional[str]:
        """Resolve a label name to its id, creating the label when missing
        (never creates in dry-run; returns None then)."""
        if name in self._label_ids:
            return self._label_ids[name]
        resp = self._users().labels().list(userId="me").execute()
        for lab in resp.get("labels") or []:
            if lab.get("name") == name:
                self._label_ids[name] = lab["id"]
                return lab["id"]
        if not create:
            return None
        if self.dry_run:
            logger.info("[dry-run] would create Gmail label %r", name)
            return None
        created = self._users().labels().create(userId="me", body={
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }).execute()
        self._label_ids[name] = created["id"]
        logger.info("Created Gmail label %r (%s)", name, created["id"])
        return created["id"]

    def add_label(self, thread_id: str, label: Optional[str] = None) -> None:
        label = label or self.processed_label
        if self.dry_run:
            logger.info("[dry-run] would label thread %s with %r", thread_id, label)
            return
        lid = self.label_id(label, create=True)
        self._users().threads().modify(
            userId="me", id=thread_id, body={"addLabelIds": [lid]},
        ).execute()

    # -- reading -----------------------------------------------------------

    def list_unprocessed_threads(self, query: str = DEFAULT_QUERY,
                                 max_results: int = 50) -> List[str]:
        """Thread ids matching ``query`` that do not carry the processed
        label. Newest first (Gmail's default ordering)."""
        # The label is created lazily on first write; if it does not exist
        # yet nothing is processed, so the exclusion is a no-op.
        q = f"-label:{self.processed_label} {query}".strip()
        ids: List[str] = []
        page_token = None
        while len(ids) < max_results:
            req = self._users().threads().list(
                userId="me", q=q, maxResults=min(100, max_results - len(ids)),
                pageToken=page_token,
            )
            resp = req.execute()
            for t in resp.get("threads") or []:
                ids.append(t["id"])
                if len(ids) >= max_results:
                    break
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return ids

    def get_thread(self, thread_id: str) -> Dict[str, Any]:
        raw = self._users().threads().get(
            userId="me", id=thread_id, format="full").execute()
        messages = [parse_message(m) for m in raw.get("messages") or []]
        messages.sort(key=lambda m: m.get("internal_date") or 0)
        subject = next((m["subject"] for m in messages if m.get("subject")), "")
        return {"id": raw.get("id") or thread_id, "subject": subject,
                "messages": messages, "url": thread_url(thread_id)}

    # -- writing -----------------------------------------------------------

    def send_reply(self, thread_id: str, to: str, subject: str, body_text: str,
                   in_reply_to: str = "", references: str = "") -> Optional[str]:
        raw = build_reply_mime(sender=self.send_as, to=to, subject=subject,
                               body_text=body_text, in_reply_to=in_reply_to,
                               references=references)
        if self.dry_run:
            logger.info("[dry-run] would SEND reply in thread %s to %s", thread_id, to)
            return None
        resp = self._users().messages().send(
            userId="me", body={"raw": raw, "threadId": thread_id}).execute()
        logger.info("Sent reply in thread %s to %s (message %s)",
                    thread_id, to, resp.get("id"))
        return resp.get("id")

    def create_draft(self, thread_id: str, to: str, subject: str, body_text: str,
                     in_reply_to: str = "", references: str = "") -> Optional[str]:
        raw = build_reply_mime(sender=self.send_as, to=to, subject=subject,
                               body_text=body_text, in_reply_to=in_reply_to,
                               references=references)
        if self.dry_run:
            logger.info("[dry-run] would DRAFT reply in thread %s to %s", thread_id, to)
            return None
        resp = self._users().drafts().create(
            userId="me",
            body={"message": {"raw": raw, "threadId": thread_id}}).execute()
        logger.info("Created draft in thread %s to %s (draft %s)",
                    thread_id, to, resp.get("id"))
        return resp.get("id")
