"""Recognise "the account is out of money" and stop early.

On 28 July 2026 the xAI account crossed its monthly spending limit
mid-run. Chat completions succeeded at 10:15, TTS returned 403 at
10:18, and the pipeline died at the synthesis step — *after* fetching
100 articles, generating a digest, expanding it, generating a podcast
script, and retrying that script for length. Every show in the matrix
did the same: paid for the whole generation stage, then failed on the
last API call before audio.

The pre-flight ping already talks to the same billing account, so the
second and every subsequent show could have known immediately. It
didn't, because the ping treats any failure as a warning and continues
— correct for a network blip or a model-id typo, wrong for a hard
billing stop, where continuing guarantees spending more money to reach
the same failure.

This module is the distinction between those two. It is deliberately
narrow: a credit stop is unambiguous in the response body, and
everything else stays a warning, because a false positive here would
cancel a whole day of episodes over a transient error.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Matched against the provider's response body, not the status code —
# 403 alone is ambiguous (it also covers a revoked key or a voice the
# account cannot use, both of which are worth failing differently).
#
# xAI's wording, verbatim from the 28 July 2026 incident:
#   "Your team fae4735c-... has either used all available credits or
#    reached its monthly spending limit. To continue making API
#    requests, please purchase more credits or raise your spending
#    limit."
_QUOTA_PATTERNS = (
    r"used all available credits",
    r"monthly spending limit",
    r"purchase more credits",
    r"raise your spending limit",
    r"insufficient(?:_|\s)credits?",
    r"quota exceeded",
    r"billing (?:hard )?limit",
    r"exceeded your current quota",
)
_QUOTA_RE = re.compile("|".join(_QUOTA_PATTERNS), re.IGNORECASE)


def is_quota_exhausted(error: object) -> bool:
    """True when *error* says the account is out of credit.

    Accepts an exception or a string. Deliberately does NOT key on the
    403 status: a revoked API key is also a 403 and wants a different
    response from the operator, and treating every 403 as a billing
    stop would cancel a day of episodes over a bad key.
    """
    if error is None:
        return False
    text = str(error)
    body = getattr(error, "body", None)
    if body:
        text = f"{text}\n{body}"
    return bool(_QUOTA_RE.search(text))


def quota_message(provider: str = "xAI", error: Optional[object] = None) -> str:
    """Operator-facing explanation. Says what to do, not just what broke."""
    lines = [
        f"{provider} reports the account is out of credit or has hit its "
        f"spending limit.",
        "",
        "This is a billing stop, not a code failure — every show will fail "
        "at the same point until it is lifted.",
        "",
        "  1. console.x.ai -> Billing: add credits, or raise the monthly "
        "spending limit.",
        "  2. Re-run the failed shows from the Actions tab.",
        "",
        "Stopping now rather than continuing: the fetch and generation "
        "stages cost real money and would only reach the same failure at "
        "the audio step.",
    ]
    if error is not None:
        lines += ["", f"Provider said: {str(error)[:300]}"]
    return "\n".join(lines)
