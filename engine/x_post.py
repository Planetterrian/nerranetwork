"""One X post for a publisher that bypasses run_show (Oct 9 2026).

Nerra Daily and the interview shows publish outside ``run_show.py``, where
every other show's X post lives, so turning X on for them meant giving
each a poster. This is that poster: one teaser (the episode title and a
funnel-tagged link to its page), credentials read from ``<prefix>*`` env
vars exactly as run_show reads them, and an OUTCOME the caller records.
A missing credential is a logged skip (``no_credentials``), never a
failure — the episode is already in its feed by the time this runs.
"""
from __future__ import annotations

import logging
import os
from typing import Tuple

from engine.titles import X_TEASER_TEXT_MAX, clip_words

logger = logging.getLogger(__name__)

#: The network account (@nerranetwork) posts by hand today; these are the
#: secret names that turn the two bypass publishers on. Deliberately not
#: ``X_`` (that app is @teslashortstime) or ``PLANETTERRIAN_X_``.
NETWORK_X_ENV_PREFIX = "NERRANETWORK_X_"

_SUFFIXES = ("CONSUMER_KEY", "CONSUMER_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET")


def x_credentials(env_prefix: str) -> dict:
    """The four tweepy credentials under *env_prefix*, or ``{}`` if any is unset."""
    prefix = env_prefix or ""
    values = {k.lower(): os.getenv(f"{prefix}{k}", "").strip() for k in _SUFFIXES}
    return values if all(values.values()) else {}


def teaser_text(title: str, link: str) -> str:
    """``<title>\n\n<link>`` with the title clipped to the X text budget."""
    head = clip_words(" ".join((title or "").split()), X_TEASER_TEXT_MAX)
    return f"{head}\n\n{link}".strip()


def post_teaser(*, env_prefix: str, title: str, link: str,
                label: str) -> Tuple[bool, str]:
    """Post one teaser. Returns ``(posted, reason)``.

    ``reason`` is ``""`` on success, ``no_credentials`` when the prefix is
    unset, ``post_failed`` when X refused or the call raised.
    """
    creds = x_credentials(env_prefix)
    if not creds:
        logger.warning("X post skipped for %s: no %s* credentials in the "
                       "environment", label, env_prefix or "<empty prefix>")
        return False, "no_credentials"
    try:
        from engine.publisher import post_to_x
        url = post_to_x(
            teaser_text(title, link),
            consumer_key=creds["consumer_key"],
            consumer_secret=creds["consumer_secret"],
            access_token=creds["access_token"],
            access_token_secret=creds["access_token_secret"],
        )
    except Exception as exc:  # noqa: BLE001 — the episode is already published
        logger.warning("X post failed for %s (non-fatal): %s", label, exc)
        return False, "post_failed"
    if not url:
        logger.warning("X post failed for %s (non-fatal): X returned no URL", label)
        return False, "post_failed"
    logger.info("Posted %s to X: %s", label, url)
    return True, ""
