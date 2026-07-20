"""Shared plumbing for the Nerra Voices (The Age of AI) pipelines.

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
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger("nerra_voices")
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s %(levelname)s %(message)s")

SHOW_SLUG = "age_of_ai"
SHOW_NAME = "The Age of AI"
EPISODE_URL_BASE = "https://nerranetwork.com/blog/age_of_ai"


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

FROM_EMAIL = os.environ.get("VOICES_FROM_EMAIL", "mira@nerranetwork.com")


OPERATOR_EMAIL = os.environ.get("OPERATOR_EMAIL", "patricknovak1@gmail.com")


def send_email(to: str, subject: str, html_body: str,
               cc_operator: bool = False) -> None:
    """Send mail as Mira. ``cc_operator=True`` copies Patrick — the July
    2026 oversight process: Mira runs guest comms, the operator sees
    everything without being in the critical path."""
    resend_key = os.environ.get("RESEND_API_KEY", "")
    postmark_token = os.environ.get("POSTMARK_TOKEN", "")
    payload: dict = {"from": FROM_EMAIL, "to": [to],
                     "subject": subject, "html": html_body}
    if cc_operator and to.lower() != OPERATOR_EMAIL.lower():
        payload["cc"] = [OPERATOR_EMAIL]
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
                  "Subject": subject, "HtmlBody": html_body},
            timeout=30,
        )
    else:
        raise RuntimeError(
            "Neither RESEND_API_KEY nor POSTMARK_TOKEN is set — cannot send "
            f"email to {to!r} ({subject!r})"
        )
    resp.raise_for_status()
    logger.info("Email sent to %s: %s", to, subject)


def render_email(template_name: str, **context: Any) -> str:
    """Render a templates/email/*.j2 template with jinja2."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(
        loader=FileSystemLoader(str(ROOT / "templates" / "email")),
        autoescape=select_autoescape(["html", "j2"]),
    )
    return env.get_template(template_name).render(**context)


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


def load_prompt(template: str, **subs: Any) -> str:
    """Load pipelines/voices/prompts/<template> and substitute {{token}} vars.

    First param is deliberately NOT called ``name``: callers pass a
    ``name=<guest name>`` substitution kwarg, which collided with the old
    positional param and made every generate_brief call a TypeError
    (latent since launch — surfaced July 17 2026 on the first real brief).
    """
    text = (Path(__file__).parent / "prompts" / template).read_text(encoding="utf-8")
    for key, value in subs.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


# ---------------------------------------------------------------------------
# R2 storage (env-driven wrapper over engine.storage.upload_to_r2)
# ---------------------------------------------------------------------------

def r2_upload(local_path: Path, remote_key: str) -> str:
    """Upload to the network's R2 audio bucket; returns the public URL.

    Uses the same env vars as the show pipeline (R2_* — see
    docs/env_var_inventory.md). VOICES_R2_BUCKET overrides the bucket for
    raw-interview segregation if the operator wants one.
    """
    from engine.storage import upload_to_r2
    # Env names follow the NETWORK standard (R2_ACCESS_KEY_ID /
    # R2_SECRET_ACCESS_KEY — see docs/env_var_inventory.md and the existing
    # GitHub secrets); the launch code invented R2_ACCESS_KEY/R2_SECRET_KEY
    # names that exist nowhere, which failed the first real post-interview
    # run (July 17 2026). Old names kept as fallbacks. Bucket/public-base
    # default to the network audio bucket like shows/_defaults.yaml.
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
    return upload_to_r2(
        Path(local_path), remote_key,
        bucket=bucket, endpoint_url=endpoint,
        access_key=access, secret_key=secret,
        public_base_url=(os.environ.get("R2_PUBLIC_BASE_URL", "")
                         or "https://audio.nerranetwork.com"),
    )


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
