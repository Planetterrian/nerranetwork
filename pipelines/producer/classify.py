"""Thread classification for the Producer inbox job.

Builds a compact prompt (latest inbound message + subject + sender,
truncated) from ``pipelines/producer/prompts/classify_pitch.txt`` and asks
Grok for STRICT JSON. The shape is validated by :func:`validate_classification`;
one strict retry on bad output, then the thread is marked low confidence
so policy holds it for Patrick instead of guessing.

Model: ALWAYS ``grok-latest``. The Producer never uses a version-pinned
Grok identifier (operator rule); the classification is a triage step, not
a published stage, so a floating alias is the right call here.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.voices.common import parse_json_lenient  # noqa: E402
from pipelines.producer.policy import daily_show_names  # noqa: E402

logger = logging.getLogger("nerra_producer.classify")

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "classify_pitch.txt"
PRODUCER_MODEL = "grok-latest"
MAX_BODY_CHARS = 3000

CATEGORIES = (
    "guest_pitch", "sponsor_or_sales", "platform_notice",
    "personal_or_business", "newsletter_or_noise", "guest_followup",
)
INTERVIEW_SHOWS = ("age_of_ai", "nerra_voices")
# slug -> display name for the daily shows a publicist may have pitched;
# edited in shows/_producer_policy.yaml (pitched_show_names).
DAILY_SHOWS: Dict[str, str] = daily_show_names()

REQUIRED_KEYS = {
    "category", "confidence", "guest_name", "guest_title_org",
    "publicist_name", "publicist_email", "topic_summary", "is_ai_related",
    "recommended_show", "pitched_show", "mentions_money_or_legal",
}

LOW_CONFIDENCE_FALLBACK: Dict[str, Any] = {
    "category": "personal_or_business",
    "confidence": 0.0,
    "guest_name": None,
    "guest_title_org": None,
    "publicist_name": None,
    "publicist_email": None,
    "topic_summary": "classifier returned invalid JSON twice",
    "is_ai_related": False,
    "recommended_show": None,
    "pitched_show": None,
    "mentions_money_or_legal": False,
}


class ClassificationError(ValueError):
    pass


def _opt_str(value: Any, key: str, limit: int = 300) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ClassificationError(f"{key} must be a string or null")
    value = " ".join(value.split())
    return value[:limit] or None


def validate_classification(obj: Any) -> Dict[str, Any]:
    """Return a normalised classification dict or raise ClassificationError."""
    if not isinstance(obj, dict):
        raise ClassificationError("classification must be a JSON object")
    missing = REQUIRED_KEYS - set(obj)
    if missing:
        raise ClassificationError(f"missing keys: {sorted(missing)}")
    cat = obj.get("category")
    if cat not in CATEGORIES:
        raise ClassificationError(f"bad category {cat!r}")
    conf = obj.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        raise ClassificationError("confidence must be a number")
    conf = float(conf)
    if not 0.0 <= conf <= 1.0:
        raise ClassificationError("confidence must be within 0..1")
    for key in ("is_ai_related", "mentions_money_or_legal"):
        if not isinstance(obj.get(key), bool):
            raise ClassificationError(f"{key} must be a boolean")
    summary = obj.get("topic_summary")
    if not isinstance(summary, str):
        raise ClassificationError("topic_summary must be a string")
    summary = " ".join(summary.split())[:200]
    rec = obj.get("recommended_show")
    if rec is not None and rec not in INTERVIEW_SHOWS:
        raise ClassificationError(f"bad recommended_show {rec!r}")
    pitched = obj.get("pitched_show")
    if pitched is not None:
        if not isinstance(pitched, str):
            raise ClassificationError("pitched_show must be a string or null")
        pitched = pitched.strip().lower()
        if pitched in INTERVIEW_SHOWS or pitched == "":
            pitched = None
        elif pitched not in DAILY_SHOWS:
            raise ClassificationError(f"bad pitched_show {pitched!r}")
    pub_email = _opt_str(obj.get("publicist_email"), "publicist_email")
    if pub_email is not None:
        pub_email = pub_email.lower()
        if "@" not in pub_email:
            pub_email = None
    out = {
        "category": cat,
        "confidence": conf,
        "guest_name": _opt_str(obj.get("guest_name"), "guest_name", 120),
        "guest_title_org": _opt_str(obj.get("guest_title_org"), "guest_title_org", 200),
        "publicist_name": _opt_str(obj.get("publicist_name"), "publicist_name", 120),
        "publicist_email": pub_email,
        "topic_summary": summary,
        "is_ai_related": bool(obj["is_ai_related"]),
        "recommended_show": rec,
        "pitched_show": pitched,
        "mentions_money_or_legal": bool(obj["mentions_money_or_legal"]),
    }
    # Routing rule: AI substance -> The Age of AI, everything else -> Nerra
    # Voices. The model is asked for it; we enforce it.
    if out["category"] in ("guest_pitch", "guest_followup"):
        out["recommended_show"] = "age_of_ai" if out["is_ai_related"] else "nerra_voices"
    else:
        out["recommended_show"] = None
    return out


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def latest_inbound(thread: Dict[str, Any], own_email: str) -> Optional[Dict[str, Any]]:
    """The most recent message NOT sent by the delegated user."""
    own = _own_set(own_email)
    for msg in reversed(thread.get("messages") or []):
        if (msg.get("from_email") or "").lower() not in own:
            return msg
    return None


def _own_set(own_email: str) -> set:
    """The delegated mailbox plus its send-as alias (GMAIL_SEND_AS)."""
    import os
    own = {(own_email or "").lower()}
    for key in ("GMAIL_SEND_AS", "GMAIL_DELEGATED_USER"):
        val = (os.environ.get(key) or "").strip().lower()
        if val:
            own.add(val)
    own.discard("")
    return own


def truncate(text: str, limit: int = MAX_BODY_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n[... truncated ...]"


def build_prompt(thread: Dict[str, Any], own_email: str) -> str:
    msg = latest_inbound(thread, own_email) or {}
    template = PROMPT_PATH.read_text(encoding="utf-8")
    subs = {
        "daily_show_list": ", ".join(f"{n} ({s})" for s, n in DAILY_SHOWS.items()),
        "daily_show_slugs": ", ".join(f'"{s}"' for s in DAILY_SHOWS),
        "sender": msg.get("from") or "(unknown)",
        "subject": thread.get("subject") or msg.get("subject") or "(no subject)",
        "message_count": str(len(thread.get("messages") or [])),
        "body": truncate(msg.get("body") or msg.get("snippet") or ""),
    }
    for key, value in subs.items():
        template = template.replace("{{" + key + "}}", str(value))
    return template


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _call_grok(prompt: str) -> str:
    """The only place the Producer talks to Grok. Always grok-latest."""
    from digests.xai_grok import grok_generate_text
    text, _meta = grok_generate_text(
        prompt=prompt, model=PRODUCER_MODEL, temperature=0.1,
        max_tokens=600, timeout_seconds=float(os.environ.get("NERRA_LLM_TIMEOUT_SECONDS", "180")),
    )
    return (text or "").strip()


_JSON_OBJ_RE = re.compile(r"\{.*\}", re.S)


def _parse(text: str) -> Any:
    try:
        return parse_json_lenient(text)
    except (ValueError, json.JSONDecodeError):
        m = _JSON_OBJ_RE.search(text or "")
        if not m:
            raise
        return json.loads(m.group(0))


def classify_thread(thread: Dict[str, Any], own_email: str) -> Dict[str, Any]:
    """Classify one Gmail thread. Never raises on model misbehaviour: after
    one strict retry the low-confidence fallback is returned so policy
    holds the thread for a human."""
    prompt = build_prompt(thread, own_email)
    attempts = [prompt,
                prompt + "\n\nYour previous answer was not valid JSON matching the "
                         "schema. Return ONLY the JSON object, with every key, "
                         "and nothing else."]
    last_err: Optional[Exception] = None
    for attempt, p in enumerate(attempts, 1):
        try:
            raw = _call_grok(p)
            result = validate_classification(_parse(raw))
            result["_attempts"] = attempt
            return result
        except (ClassificationError, ValueError, json.JSONDecodeError) as exc:
            last_err = exc
            logger.warning("classification attempt %d invalid for thread %s: %s",
                           attempt, thread.get("id"), exc)
    out = dict(LOW_CONFIDENCE_FALLBACK)
    out["topic_summary"] = f"classifier invalid twice: {last_err}"[:200]
    out["_attempts"] = len(attempts)
    return out
