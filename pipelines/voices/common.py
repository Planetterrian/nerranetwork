"""Shared plumbing for the Mira-hosted interview pipelines (The Age of AI,
Nerra Voices).

Every pipeline script imports this first. It provides:

* repo-root sys.path bootstrap (so ``engine.*`` and ``digests.xai_grok``
  import from a checkout regardless of CWD);
* a minimal Supabase REST client (service key; PostgREST conventions);
* transactional email via Resend or Postmark (whichever env var is set —
  spec §11.5 leaves the pick to the operator);
* Slack notification via the existing NOTIFICATION_WEBHOOK_URL pattern
  (falls back to SLACK_WEBHOOK);
* an LLM text call routed through the repo's shared Grok helper.

All functions fail loud (raise) unless documented otherwise — the GitHub
Actions job failing IS the alert channel for pipeline breakage.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Registry import goes through the repo-root namespace path, NOT a bare
# ``import shows``: the repo already has a top-level ``shows/`` package
# (``shows.hooks.*``) and a bare import would shadow one or the other
# depending on sys.path order.
from pipelines.voices.shows import (  # noqa: E402,F401
    DEFAULT_SHOW, VoiceShow, get_show, show_for,
)

logger = logging.getLogger("nerra_voices")
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s %(levelname)s %(message)s")

# Deprecated (September 2026): the pipeline is show-generic now — resolve
# the show per row with ``show_for(interview, app)``. Kept only so any
# out-of-tree import of the old constant keeps working; it is the DEFAULT
# show's name, never the current row's.
SHOW_NAME = get_show(DEFAULT_SHOW).name

ShowRef = Union[str, VoiceShow, None]


def resolve_show(show: ShowRef = None) -> VoiceShow:
    """Accept a slug, a :class:`VoiceShow`, or ``None`` (→ default show)."""
    if isinstance(show, VoiceShow):
        return show
    return get_show(show)


# ---------------------------------------------------------------------------
# Supabase REST (PostgREST) client
# ---------------------------------------------------------------------------

def _sb_base() -> str:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not url:
        raise RuntimeError("SUPABASE_URL env var is required")
    return url + "/rest/v1"


def _sb_headers(*, prefer: str = "") -> Dict[str, str]:
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_KEY env var is required")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def sb_select(table: str, query: str = "") -> List[Dict[str, Any]]:
    """``query`` is a raw PostgREST query string, e.g.
    ``status=eq.pending&scheduled_for=lte.2026-07-04T18:00:00Z``."""
    url = f"{_sb_base()}/{table}"
    if query:
        url += f"?{query}"
    resp = requests.get(url, headers=_sb_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def sb_insert(table: str, row: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(
        f"{_sb_base()}/{table}",
        headers=_sb_headers(prefer="return=representation"),
        json=row, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()[0]


def sb_update(table: str, query: str, patch: Dict[str, Any]) -> List[Dict[str, Any]]:
    resp = requests.patch(
        f"{_sb_base()}/{table}?{query}",
        headers=_sb_headers(prefer="return=representation"),
        json=patch, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Email (Resend or Postmark — spec §11.5)
# ---------------------------------------------------------------------------

# `or` rather than a default argument, deliberately. Sept 15 2026: the
# assemble workflow passes OPERATOR_EMAIL from a repository secret that was
# never set, so the env var existed and was empty — os.environ.get returned
# "" and the default never applied. Resend was handed {"to": [""]} and
# answered 422, which is how two finished episodes ended up with nobody
# told about either of them.
FROM_EMAIL = os.environ.get("VOICES_FROM_EMAIL") or "mira@nerranetwork.com"


OPERATOR_EMAIL = os.environ.get("OPERATOR_EMAIL") or "patricknovak1@gmail.com"
# Sept 21 2026: Mira runs the correspondence end to end and Patrick reads it
# at both addresses — the Gmail he lives in and the Planetterrian one that is
# archived with the rest of the business. Every cc_operator=True mail goes to
# both, so "copy Patrick" cannot quietly mean one of them.
OPERATOR_CC = [a.strip() for a in (
    os.environ.get("OPERATOR_CC") or "patrick@planetterrian.com").split(",")
    if a.strip()]

# Phase 2 co-host (Sept 2026): Patrick sits in the room as co-host on
# every Mira interview. His display name lives in ONE env var so the
# prompt, the transcript labels and the editorial passes all agree.
COHOST_NAME_DEFAULT = "Patrick Novak"


def to_e164(raw: str, default_country: str = "1") -> str:
    """Normalise a human-typed phone number to E.164, or "" if unusable.

    Sept 10 2026 (Matt Davis): guests type their number however they like —
    his was stored as "7737240695". Voximplant answered every send with
    "'destination' parameter is invalid" (code 423), so his reminder SMS
    never went out AND the automatic phone fallback would have failed too.
    Nothing normalised the number between the application form and the API.
    """
    digits = re.sub(r"[^\d+]", "", str(raw or "").strip())
    if not digits:
        return ""
    if digits.startswith("+"):
        rest = re.sub(r"\D", "", digits[1:])
        return ("+" + rest) if 8 <= len(rest) <= 15 else ""
    digits = re.sub(r"\D", "", digits)
    if len(digits) == 10:                       # 7737240695 → +17737240695
        return "+" + default_country + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    # 00-prefixed international (0044…) or a plain international number.
    if digits.startswith("00") and 10 <= len(digits) <= 17:
        return "+" + digits[2:]
    return "+" + digits if 8 <= len(digits) <= 15 else ""


def operator_phone() -> str:
    """E.164 operator number for the host-link SMS (empty = no SMS)."""
    return to_e164(os.environ.get("OPERATOR_PHONE", ""))


def cohost_name() -> str:
    """Full co-host name for prompts/emails (env COHOST_NAME)."""
    return os.environ.get("COHOST_NAME", "").strip() or COHOST_NAME_DEFAULT


def cohost_label() -> str:
    """First name — the transcript speaker label (``Patrick:``)."""
    return cohost_name().split()[0]


def package_review_token(package_id: str, admin_token: Optional[str] = None) -> str:
    """Per-package gate-1 token; safe to put in an email.

    Must stay byte-for-byte identical to ``packageReviewToken()`` in the
    Worker: ``hex(HMAC_SHA256(admin_token, "nerra-review:" + id))[:40]``.
    It opens exactly one editorial package and grants nothing else.
    """
    import hashlib
    import hmac
    token = (admin_token if admin_token is not None
             else os.environ.get("ADMIN_TOKEN", "")).strip()
    if not token:
        raise RuntimeError("ADMIN_TOKEN is required to derive review tokens")
    digest = hmac.new(token.encode("utf-8"),
                      f"nerra-review:{package_id}".encode("utf-8"),
                      hashlib.sha256).hexdigest()
    return digest[:40]


# Something between us and Gmail decodes our HTML as quoted-printable
# without our ever having encoded it, so an "=" inside a link is eaten
# together with the two characters after it: "?interview=89fbb824..."
# arrived as "?interview\ufffdfbb824...", and "?token=09447945..." as
# "?token<TAB>447945...". Every link with a query string has been broken
# in Patrick's inbox since the start. An HTML numeric entity survives that
# decode untouched and the browser turns it back into "=" when the link is
# clicked, so we spell "=" that way inside URLs and nowhere else.
_URL_IN_HTML = re.compile(r"https?://[^\s\"'<>]+")


def email_safe_html(html: str) -> str:
    return _URL_IN_HTML.sub(lambda m: m.group(0).replace("=", "&#61;"), html or "")


def send_email(to: str, subject: str, html_body: str,
               cc_operator: bool = False, cc: Optional[List[str]] = None) -> None:
    """Send mail as Mira. ``cc_operator=True`` copies Patrick — the July
    2026 oversight process: Mira runs guest comms, the operator sees
    everything without being in the critical path. ``cc`` copies anyone
    else (a publicist, say); empties and duplicates are dropped."""
    to = (to or "").strip()
    if "@" not in to:
        # Better to say which address is missing than to let the provider
        # answer 422 about a payload nobody can see.
        raise RuntimeError(
            f"refusing to send {subject!r}: recipient is {to!r}. Check "
            "OPERATOR_EMAIL — an empty repository secret reads as an empty "
            "string, not as unset.")
    resend_key = os.environ.get("RESEND_API_KEY", "")
    postmark_token = os.environ.get("POSTMARK_TOKEN", "")
    html_body = email_safe_html(html_body)
    payload: dict = {"from": FROM_EMAIL, "to": [to],
                     "subject": subject, "html": html_body}
    copies: List[str] = []
    if cc_operator:
        copies.append(OPERATOR_EMAIL)
        copies.extend(OPERATOR_CC)
    for addr in cc or []:
        addr = (addr or "").strip()
        if "@" in addr and addr.lower() != to.lower() \
                and addr.lower() not in {c.lower() for c in copies}:
            copies.append(addr)
    copies = [c for c in copies if c.lower() != to.lower()]
    if copies:
        payload["cc"] = copies
    if resend_key:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_key}"},
            json=payload,
            timeout=30,
        )
    elif postmark_token:
        resp = requests.post(
            "https://api.postmarkapp.com/email",
            headers={"X-Postmark-Server-Token": postmark_token,
                     "Content-Type": "application/json"},
            json={"From": FROM_EMAIL, "To": to,
                  "Subject": subject, "HtmlBody": html_body,
                  **({"Cc": ", ".join(copies)} if copies else {})},
            timeout=30,
        )
    else:
        raise RuntimeError(
            "Neither RESEND_API_KEY nor POSTMARK_TOKEN is set — cannot send "
            f"email to {to!r} ({subject!r})"
        )
    resp.raise_for_status()
    logger.info("Email sent to %s: %s", to, subject)


def show_email_context(show: ShowRef = None,
                       interview_id: str = "") -> Dict[str, Any]:
    """The show-branding variables every ``templates/email/voices_*.j2``
    template reads: show_name, show_short_label, brand_color, studio_url,
    apply_url, page_url, sign_off (+ show_slug, closing_question)."""
    s = resolve_show(show)
    return {
        "show_slug": s.slug,
        "show_name": s.name,
        "show_short_label": s.short_label,
        "brand_color": s.brand_color,
        "studio_url": s.studio_url(interview_id or ""),
        "apply_url": s.apply_url,
        "page_url": s.page_url,
        "sign_off": s.sign_off,
        "closing_question": s.closing_question,
    }


def render_email(template_name: str, show: ShowRef = None,
                 **context: Any) -> str:
    """Render a templates/email/*.j2 template with jinja2.

    ``show`` (slug or :class:`VoiceShow`; ``None`` → the default show)
    injects the show branding fields — see :func:`show_email_context`.
    Explicit kwargs win over the injected fields. ``interview_id`` in the
    context is used to build a per-interview ``studio_url``.
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(
        loader=FileSystemLoader(str(ROOT / "templates" / "email")),
        autoescape=select_autoescape(["html", "j2"]),
    )
    merged = show_email_context(show, str(context.get("interview_id") or ""))
    merged.update(context)
    return env.get_template(template_name).render(**merged)


# ---------------------------------------------------------------------------
# Slack / operator notification
# ---------------------------------------------------------------------------

def notify_operator(text: str, *, critical: bool = False) -> None:
    """Best-effort Slack ping (never raises — the pipeline result matters
    more than the ping)."""
    url = (os.environ.get("SLACK_WEBHOOK", "")
           or os.environ.get("NOTIFICATION_WEBHOOK_URL", ""))
    if not url:
        logger.warning("No Slack webhook configured — notification dropped: %s", text)
        return
    prefix = ":rotating_light: " if critical else ":studio_microphone: "
    try:
        requests.post(url, json={"text": prefix + text}, timeout=15).raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Slack notify failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------

def llm(prompt: str, *, temperature: float = 0.5, max_tokens: int = 3500,
        web_search: bool = False) -> str:
    from digests.xai_grok import grok_generate_text
    text, _meta = grok_generate_text(
        prompt=prompt, temperature=temperature, max_tokens=max_tokens,
        enable_web_search=web_search,
    )
    return (text or "").strip()


def show_prompt_subs(show: ShowRef = None) -> Dict[str, str]:
    """The show tokens every prompt may use: {{show_name}}, {{show_slug}},
    {{show_short_label}}, {{show_premise}}, {{opening_line}},
    {{closing_question}} — plus the Phase 2 co-host tokens {{cohost_name}}
    (always filled) and {{cohost_block}} (empty unless the caller passes
    the block; see fire_interviews.compile_mira_prompt)."""
    s = resolve_show(show)
    return {
        "show_name": s.name,
        "show_slug": s.slug,
        "show_short_label": s.short_label,
        "show_premise": s.premise,
        "opening_line": s.opening_line,
        "closing_question": s.closing_question,
        "cohost_name": cohost_name(),
        "cohost_block": "",
    }


def load_prompt(template: str, show: ShowRef = None, **subs: Any) -> str:
    """Load pipelines/voices/prompts/<template> and substitute {{token}} vars.

    ``show`` (slug or :class:`VoiceShow`; ``None`` → the default show)
    picks the per-show override via :meth:`VoiceShow.prompt_path` (falls
    back to the shared prompt) and pre-fills the show tokens from
    :func:`show_prompt_subs`. Explicit ``subs`` win over those.

    First param is deliberately NOT called ``name``: callers pass a
    ``name=<guest name>`` substitution kwarg, which collided with the old
    positional param and made every generate_brief call a TypeError
    (latent since launch — surfaced July 17 2026 on the first real brief).
    """
    s = resolve_show(show)
    text = s.prompt_path(template).read_text(encoding="utf-8")
    merged: Dict[str, Any] = dict(show_prompt_subs(s))
    merged.update(subs)
    for key, value in merged.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


# ---------------------------------------------------------------------------
# R2 storage (env-driven wrapper over engine.storage.upload_to_r2)
# ---------------------------------------------------------------------------

def _r2_config() -> Dict[str, str]:
    """Bucket + credentials shared by upload/download/read.

    Env names follow the NETWORK standard (R2_ACCESS_KEY_ID /
    R2_SECRET_ACCESS_KEY — see docs/env_var_inventory.md and the existing
    GitHub secrets); the launch code invented R2_ACCESS_KEY/R2_SECRET_KEY
    names that exist nowhere, which failed the first real post-interview
    run (July 17 2026). Old names kept as fallbacks. Bucket/public-base
    default to the network audio bucket like shows/_defaults.yaml.
    """
    bucket = (os.environ.get("VOICES_R2_BUCKET", "")
              or os.environ.get("R2_BUCKET", "")
              or "podcast-audio")
    endpoint = os.environ.get("R2_ENDPOINT_URL", "")
    access = (os.environ.get("R2_ACCESS_KEY_ID", "")
              or os.environ.get("R2_ACCESS_KEY", ""))
    secret = (os.environ.get("R2_SECRET_ACCESS_KEY", "")
              or os.environ.get("R2_SECRET_KEY", ""))
    if not all([bucket, endpoint, access, secret]):
        raise RuntimeError(
            "R2 env vars missing (R2_ENDPOINT_URL/R2_ACCESS_KEY_ID/"
            "R2_SECRET_ACCESS_KEY) — cannot store interview audio"
        )
    return {"bucket": bucket, "endpoint": endpoint,
            "access": access, "secret": secret}


def _r2_client():
    """boto3 S3 client with the same credentials/config as
    ``engine.storage.upload_to_r2`` (which builds its own per call)."""
    import boto3
    from botocore.config import Config as BotoConfig
    cfg = _r2_config()
    return boto3.client(
        "s3",
        endpoint_url=cfg["endpoint"],
        aws_access_key_id=cfg["access"],
        aws_secret_access_key=cfg["secret"],
        config=BotoConfig(signature_version="s3v4",
                          retries={"max_attempts": 3, "mode": "adaptive"}),
    ), cfg["bucket"]


def r2_upload(local_path: Path, remote_key: str) -> str:
    """Upload to the network's R2 audio bucket; returns the public URL.

    Uses the same env vars as the show pipeline (R2_* — see
    docs/env_var_inventory.md). VOICES_R2_BUCKET overrides the bucket for
    raw-interview segregation if the operator wants one.
    """
    from engine.storage import upload_to_r2
    cfg = _r2_config()
    return upload_to_r2(
        Path(local_path), remote_key,
        bucket=cfg["bucket"], endpoint_url=cfg["endpoint"],
        access_key=cfg["access"], secret_key=cfg["secret"],
        public_base_url=(os.environ.get("R2_PUBLIC_BASE_URL", "")
                         or "https://audio.nerranetwork.com"),
    )


def r2_download(remote_key: str, local_path: Path) -> Path:
    """Download one R2 object (by KEY, not URL) to ``local_path``.

    Phase 2 co-host: the studio page's local browser recording lands in R2
    via the Worker's ``VOICES_R2`` binding (bucket ``podcast-audio``, keys
    ``<r2_prefix>/local/<run_id>/<role>/<seq>.webm``); the objects are not
    necessarily public, so the pipeline reads them with its own
    credentials. Raises on a missing key (callers decide the fallback).
    """
    s3, bucket = _r2_client()
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading r2://%s/%s → %s", bucket, remote_key, local_path.name)
    s3.download_file(bucket, remote_key, str(local_path))
    return local_path


def r2_read_json(remote_key: str) -> Optional[Any]:
    """Read + parse a JSON object from R2; ``None`` when the key is absent
    (a local-recording manifest that never got written = no upload-done)."""
    s3, bucket = _r2_client()
    try:
        obj = s3.get_object(Bucket=bucket, Key=remote_key)
    except Exception as exc:  # noqa: BLE001 — NoSuchKey and friends
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if code in ("NoSuchKey", "404", "NotFound") or "NoSuchKey" in str(exc):
            return None
        raise
    return json.loads(obj["Body"].read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

def new_review_token() -> str:
    import secrets
    return secrets.token_urlsafe(32)


def parse_json_lenient(text: str) -> Any:
    """Parse LLM JSON output, tolerating a fenced code block wrapper."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return json.loads(text)


# ---------------------------------------------------------------------------
# Show memory (July 24 2026) — the interview shows run OUTSIDE run_show,
# so the network's digest-driven narrative memory never fires for them.
# This is their memory surface: the committed episode record, injected
# into brief / thesis / narration prompts so each show behaves like a
# chronicle (continuity, callbacks, no retreading) instead of isolated
# one-offs. Memory is PER SHOW — an Age of AI brief never sees Nerra
# Voices episodes and vice versa.
# ---------------------------------------------------------------------------

def episode_memory_block(limit: int = 10, show: ShowRef = None) -> str:
    """Published-episode memory for prompt injection ({{show_memory}}).

    Reads the show's committed summaries JSON
    (:attr:`VoiceShow.summaries_path`, e.g.
    ``digests/age_of_ai/summaries_age_of_ai.json``) — the durable record of
    what the show has already aired (guest, date, episode framing). Returns
    a labeled block, or ``""`` when no episodes exist yet / on any failure
    — memory must never block an interview.
    """
    try:
        path = resolve_show(show).summaries_path
        if not path.exists():
            return ""
        data = json.loads(path.read_text(encoding="utf-8"))
        episodes = data.get("episodes") or data.get("summaries") or []
        rows = []
        for ep in episodes:
            if not isinstance(ep, dict):
                continue
            num = ep.get("episode") or ep.get("episode_num")
            title = (ep.get("title") or ep.get("hook") or "").strip()
            date = str(ep.get("date") or "")[:10]
            if num and title:
                rows.append((int(num), date, title))
        if not rows:
            return ""
        rows.sort(reverse=True)
        lines = [f"- Ep{n} ({d}): {t}" for n, d, t in rows[:limit]]
        return (
            "THE SHOW'S CHRONICLE SO FAR (episodes already published — do "
            "not retread ground these covered, and never restate an "
            "existing episode's angle as a thesis; a brief, respectful "
            "callback to an earlier episode is welcome when this guest's "
            "world genuinely connects to one):\n" + "\n".join(lines)
        )
    except Exception as exc:  # noqa: BLE001 — memory must never block
        logger.warning("episode_memory_block failed (non-fatal): %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Guest links
#
# A guest's own links are the one thing an episode can give back to them, and
# until Sept 13 2026 they were collected on the application, handed to the
# research pass, and then dropped. They reach the show notes, the feed, the
# site and Mira's sign-off now, which means they have to survive the two
# shapes the column is actually written in: {"raw": "a.com, b.com"} from the
# apply form, and {"urls": [...]} from the producer inbox. Older rows may
# also carry the documented {"website": ..., "twitter": ...} shape.

_LINK_LABELS = {
    "website": "Website", "site": "Website", "homepage": "Website",
    "product": "Product", "app": "App", "demo": "Demo", "docs": "Docs",
    "twitter": "X", "x": "X", "linkedin": "LinkedIn", "github": "GitHub",
    "youtube": "YouTube", "substack": "Substack", "blog": "Blog",
    "scholar": "Google Scholar", "company": "Company",
    "instagram": "Instagram", "tiktok": "TikTok", "facebook": "Facebook",
    "threads": "Threads", "bluesky": "Bluesky", "bsky": "Bluesky",
    "company_linkedin": "LinkedIn (company)", "book": "Book",
}
_SOCIAL_HOSTS = ("twitter.com", "x.com", "linkedin.com", "facebook.com",
                 "instagram.com", "threads.net", "bsky.app", "mastodon",
                 "tiktok.com", "youtube.com")


_HANDLE_HOSTS = {"twitter": "https://x.com/", "x": "https://x.com/",
                 "github": "https://github.com/",
                 "instagram": "https://instagram.com/"}


def _clean_url(value: Any, hint: str = "") -> str:
    text = str(value or "").strip().strip(",;")
    if text.startswith("@") and hint.lower() in _HANDLE_HOSTS:
        return _HANDLE_HOSTS[hint.lower()] + text[1:]
    if not text or " " in text.strip():
        text = text.split()[0] if text.split() else ""
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        if "." not in text or text.startswith("@"):
            return ""
        text = "https://" + text
    return text.rstrip("/.,")


def _label_for(url: str, hint: str = "") -> str:
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()
    if hint:
        # A guest's own site is best announced as its domain: "gopippa.ai"
        # tells a listener where they are going; "Website" does not.
        if hint.lower() in ("website", "site", "homepage"):
            return host
        return _LINK_LABELS.get(hint.lower(), hint.replace("_", " ").title())
    # Match whole host labels, not substrings: "example.com" contains "x"
    # and was being announced to listeners as the guest's X profile.
    parts = host.split(".")
    for key, label in _LINK_LABELS.items():
        if key in parts:
            return label
    return host


def guest_links(app: Dict[str, Any]) -> List[Dict[str, str]]:
    """The guest's links as ``[{"label": ..., "url": ...}]``, de-duplicated.

    Their own site comes first — a listener who follows one link should land
    on the thing the guest controls, not on a social profile.
    """
    raw = app.get("links") or {}
    found: List[Dict[str, str]] = []
    if isinstance(raw, str):
        raw = {"raw": raw}
    if isinstance(raw, list):
        raw = {"urls": raw}
    if not isinstance(raw, dict):
        return []
    for key, value in raw.items():
        values = value if isinstance(value, (list, tuple)) else [value]
        if key in ("raw", "urls", "links"):
            values = [part for item in values
                      for part in re.split(r"[,\n]+", str(item or ""))]
            key = ""
        for item in values:
            url = _clean_url(item, key)
            if url:
                found.append({"label": _label_for(url, key), "url": url})
    seen, out = set(), []
    for link in found:
        if link["url"].lower() in seen:
            continue
        seen.add(link["url"].lower())
        out.append(link)
    out.sort(key=lambda l: any(h in l["url"].lower() for h in _SOCIAL_HOSTS))
    return out


def guest_links_markdown(app: Dict[str, Any], heading: str = "") -> str:
    """A links block for show notes, the feed and the site, or ``""``.

    Markdown, because the site renders it through linkify and every podcast
    client shows the bare URL harmlessly if it does not.
    """
    links = guest_links(app)
    if not links:
        return ""
    who = app.get("organization") or app.get("name") or "the guest"
    head = heading or f"Find {who}"
    lines = [f"- {l['label']}: {l['url']}" for l in links]
    return f"{head}:\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# What the show itself has learned
#
# Sept 15 2026. episode_memory_block reads the PUBLISHED summaries file, which
# gives titles and dates — enough not to retread an angle, and nothing Mira can
# actually say out loud. A host three episodes in should be able to put one
# guest's answer to the next one: John Capobianco built an agent that cannot
# write to a network without a human ticket, and Vincent Rylan spent his
# interview describing the pressure that removes exactly that gate. Neither of
# them knows the other said it. That connection is the show's own contribution
# and it is the thing only this host can make.

CARRY_LIMIT = 6


def show_insights(show: ShowRef = None, exclude_email: str = "",
                  limit: int = CARRY_LIMIT) -> List[Dict[str, Any]]:
    """Quotable things previous guests said, newest first.

    ``exclude_email`` drops this guest's own earlier appearances — those
    belong in their brief as a follow-up, not here as someone else's view.
    """
    slug = resolve_show(show).slug
    try:
        rows = sb_select(
            "episode_records",
            f"show=eq.{slug}&order=recorded_on.desc&limit={max(limit * 2, 8)}")
    except Exception:  # noqa: BLE001 — memory never blocks an interview
        logger.exception("show insights unavailable (non-fatal)")
        return []
    out: List[Dict[str, Any]] = []
    skip = (exclude_email or "").strip().lower()
    for row in rows or []:
        if skip and (row.get("guest_email") or "").lower() == skip:
            continue
        quotes = row.get("quotes") or []
        claims = row.get("claims") or []
        best = None
        if quotes and isinstance(quotes[0], dict):
            best = {"text": quotes[0].get("text"), "why": quotes[0].get("why")}
        elif claims and isinstance(claims[0], dict):
            best = {"text": claims[0].get("quote") or claims[0].get("claim"),
                    "why": claims[0].get("claim")}
        if not best or not best.get("text"):
            continue
        out.append({
            "guest": row.get("guest_name") or "a previous guest",
            "recorded_on": str(row.get("recorded_on") or "")[:10],
            "summary": row.get("summary") or "",
            "quote": best["text"],
            "why": best.get("why") or "",
            "predictions": [p for p in (row.get("predictions") or [])
                            if isinstance(p, dict) and p.get("prediction")][:2],
        })
        if len(out) >= limit:
            break
    return out


def carry_the_show_block(show: ShowRef = None, exclude_email: str = "") -> str:
    """The block that lets Mira bring one guest's answer to the next guest."""
    rows = show_insights(show, exclude_email=exclude_email)
    if not rows:
        return ""
    lines = ["WHAT THIS SHOW HAS LEARNED SO FAR (from guests who came before "
             "this one — real people, real words, and yours to use):"]
    for row in rows:
        lines.append(f"\n{row['guest']} ({row['recorded_on']}): {row['summary']}")
        lines.append(f'  In their words: "{row["quote"]}"')
        for pred in row["predictions"]:
            lines.append(f"  They predicted: {pred.get('prediction')}"
                         + (f" (by {pred['due_on']})" if pred.get("due_on") else ""))
    lines.append(
        "\nUSE ONE OF THESE, ONCE, WHERE IT GENUINELY BELONGS. Not as trivia "
        "and not to show that you remember — put a previous guest's answer to "
        "THIS guest, in their own area, and ask what they make of it. "
        "Name the person. Quote them accurately or not at all. If nothing above "
        "genuinely connects to this conversation, say nothing — "
        "a forced callback is worse than none, and there will be a better "
        "one next time."
        "\n\nHOW TO SAY IT. The callback is a QUESTION and it stands alone. "
        "One sentence of who said what, then the question, then silence: "
        "\"Vincent Rylan, a novelist, told me nobody can opt out of the race "
        "because opting out only decides who the winner is not. Is he "
        "right?\" Then stop. Do not put it after a recap of what this guest "
        "just said, do not add a second question, and do not answer it "
        "yourself. On Sept 15 2026 you stacked a three-sentence summary, a "
        "quote and a question into one turn, and Dr. Wolfberg had to ask "
        "whether that was a question to him. If the guest asks that, it "
        "was not clear: re-ask it in one short sentence.")
    return "\n".join(lines)
