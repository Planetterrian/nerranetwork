"""Producer policy: mode, hard exclusions, circuit breaker.

Loaded from ``shows/_producer_policy.yaml``; ``PRODUCER_MODE`` in the
environment overrides the yaml ``mode``. :func:`decide` is pure (a
classification + thread facts in, a :class:`Decision` out) so every rule
is unit-testable without Gmail or Grok.

Actions:

* ``send``   — reply in-thread with the guest invite (auto mode only)
* ``draft``  — hold for Patrick: Gmail draft of the invite when there is
               one to draft, plus a Slack hold note; thread labelled
* ``label``  — mark processed, no reply (platform notices, newsletters)
* ``skip``   — mark processed, no reply, no note (duplicates, follow-ups
               on threads we already answered)
* ``defer``  — per-run send cap reached: touch nothing, next tick retries
* ``none``   — mode off: touch nothing
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
POLICY_PATH = ROOT / "shows" / "_producer_policy.yaml"

MODES = ("auto", "draft", "off")
_DEFAULTS: Dict[str, Any] = {
    "mode": "auto",
    "min_confidence": 0.75,
    "max_sends_per_run": 25,
    "never_auto_reply_domains": [],
    "hold_categories": ["sponsor_or_sales", "personal_or_business"],
    "ignore_categories": ["platform_notice", "newsletter_or_noise"],
    "labels": {"processed": "Producer/Processed", "hold": "Producer/Hold"},
    "inbox_query": "newer_than:30d in:inbox",
    "show_blurbs": {},
    "pitched_show_names": {},
}


@lru_cache(maxsize=None)
def _load_yaml(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@dataclass(frozen=True)
class Policy:
    mode: str
    min_confidence: float
    max_sends_per_run: int
    never_auto_reply_domains: tuple
    hold_categories: tuple
    ignore_categories: tuple
    processed_label: str
    hold_label: str
    inbox_query: str
    show_blurbs: Dict[str, str] = field(default_factory=dict)
    pitched_show_names: Dict[str, str] = field(default_factory=dict)

    def blurb(self, show_slug: str) -> str:
        return self.show_blurbs.get(show_slug, "")

    def pitched_show_name(self, slug: Optional[str]) -> str:
        if not slug:
            return ""
        return self.pitched_show_names.get(slug, "")


def load_policy(path: Optional[Path] = None, env: Optional[Dict[str, str]] = None) -> Policy:
    env = os.environ if env is None else env
    cfg = dict(_DEFAULTS)
    cfg.update({k: v for k, v in _load_yaml(str(path or POLICY_PATH)).items() if v is not None})
    mode = (env.get("PRODUCER_MODE") or cfg.get("mode") or "auto").strip().lower()
    if mode not in MODES:
        raise ValueError(f"PRODUCER_MODE must be one of {MODES}, got {mode!r}")
    labels = dict(_DEFAULTS["labels"])
    labels.update(cfg.get("labels") or {})
    return Policy(
        mode=mode,
        min_confidence=float(cfg.get("min_confidence", 0.75)),
        max_sends_per_run=int(env.get("PRODUCER_MAX_SENDS") or cfg.get("max_sends_per_run", 25)),
        never_auto_reply_domains=tuple(
            d.strip().lower() for d in (cfg.get("never_auto_reply_domains") or []) if d),
        hold_categories=tuple(cfg.get("hold_categories") or []),
        ignore_categories=tuple(cfg.get("ignore_categories") or []),
        processed_label=labels["processed"],
        hold_label=labels["hold"],
        inbox_query=str(env.get("PRODUCER_INBOX_QUERY") or cfg.get("inbox_query")
                        or _DEFAULTS["inbox_query"]),
        show_blurbs=dict(cfg.get("show_blurbs") or {}),
        pitched_show_names=dict(cfg.get("pitched_show_names") or {}),
    )


def daily_show_names(path: Optional[Path] = None) -> Dict[str, str]:
    """slug -> display name for the daily shows a publicist may pitch."""
    return dict(_load_yaml(str(path or POLICY_PATH)).get("pitched_show_names") or {})


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Decision:
    action: str            # send | draft | label | skip | defer | none
    reason: str
    notify: bool = False   # post a Slack hold note
    draft_invite: bool = False  # there is an invite worth drafting


def sender_domain(addr: str) -> str:
    addr = (addr or "").strip().lower()
    return addr.rsplit("@", 1)[-1] if "@" in addr else ""


def domain_blocked(domain: str, blocked: tuple) -> bool:
    domain = (domain or "").lower()
    return any(domain == b or domain.endswith("." + b) for b in blocked)


def decide(classification: Dict[str, Any], *, policy: Policy,
           sender_email: str, already_replied: bool,
           already_in_db: bool, sends_so_far: int) -> Decision:
    """Pure policy. Hard exclusions always beat the mode."""
    if policy.mode == "off":
        return Decision("none", "mode=off")
    if already_in_db:
        return Decision("skip", "thread already has a guest_applications row")

    cat = classification.get("category")
    conf = float(classification.get("confidence") or 0.0)

    if cat in policy.ignore_categories:
        return Decision("label", f"category={cat}")

    if cat == "guest_followup":
        if already_replied:
            return Decision("skip", "guest_followup on a thread we already answered")
        return Decision("draft", "guest_followup on a thread we never answered",
                        notify=True, draft_invite=True)

    if cat in policy.hold_categories:
        return Decision("draft", f"category={cat} is held for Patrick", notify=True)

    # From here on: guest_pitch (any unknown category is treated as a hold).
    if cat != "guest_pitch":
        return Decision("draft", f"unhandled category={cat}", notify=True)

    if already_replied:
        return Decision("draft", "delegated user already replied in this thread (never double-reply)",
                        notify=True, draft_invite=True)
    if classification.get("mentions_money_or_legal"):
        return Decision("draft", "pitch mentions money or legal", notify=True, draft_invite=True)
    if conf < policy.min_confidence:
        return Decision("draft", f"confidence {conf:.2f} < {policy.min_confidence:.2f}",
                        notify=True, draft_invite=True)
    dom = sender_domain(sender_email)
    if domain_blocked(dom, policy.never_auto_reply_domains):
        return Decision("draft", f"sender domain {dom} is never auto-replied",
                        notify=True, draft_invite=True)
    if policy.mode == "draft":
        return Decision("draft", "mode=draft", notify=False, draft_invite=True)
    if sends_so_far >= policy.max_sends_per_run:
        # Circuit breaker: leave the thread untouched (no label, no row) so
        # the NEXT tick picks it up and sends — a backlog drains over a few
        # ticks instead of turning into a pile of drafts Patrick must send.
        return Decision("defer", f"max_sends_per_run={policy.max_sends_per_run} reached; "
                                 "left for the next tick")
    return Decision("send", "clean guest pitch", draft_invite=True)


def decision_log_line(thread_id: str, classification: Dict[str, Any],
                      decision: Decision) -> Dict[str, Any]:
    return {
        "thread_id": thread_id,
        "action": decision.action,
        "reason": decision.reason,
        "category": classification.get("category"),
        "confidence": classification.get("confidence"),
        "recommended_show": classification.get("recommended_show"),
        "pitched_show": classification.get("pitched_show"),
        "guest_name": classification.get("guest_name"),
    }


