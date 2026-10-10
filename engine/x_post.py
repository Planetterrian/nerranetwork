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
from pathlib import Path
from typing import Optional, Sequence, Tuple

from engine.titles import X_TEASER_TEXT_MAX, clip_words

logger = logging.getLogger(__name__)

#: The network account (@nerranetwork). Since Oct 10 2026 every show except
#: Tesla Shorts Time posts here; ``X_`` stays @teslashortstime (Tesla only)
#: and ``PLANETTERRIAN_X_`` is no longer used by any show.
NETWORK_X_ENV_PREFIX = "NERRANETWORK_X_"

_SUFFIXES = ("CONSUMER_KEY", "CONSUMER_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET")


def x_credentials(env_prefix: str) -> dict:
    """The four tweepy credentials under *env_prefix*, or ``{}`` if any is unset."""
    prefix = env_prefix or ""
    values = {k.lower(): os.getenv(f"{prefix}{k}", "").strip() for k in _SUFFIXES}
    return values if all(values.values()) else {}


#: The last line of a no-link post (Oct 10 2026). No URL and no bare
#: domain: X links either, and a linked post costs $0.20 instead of $0.015.
CLIP_CLOSER = "Full episode: link in bio, or search Nerra Network in your podcast app."
#: X counts emoji as two characters; stay clear of the 280 limit.
CLIP_TEXT_MAX = 270


def clip_post_text(*, label: str, hook: str, episode_num: Optional[int] = None,
                   closer: str = CLIP_CLOSER, limit: int = CLIP_TEXT_MAX) -> str:
    """``<label> · Ep N`` / the episode hook / the closer, with no link.

    The hook is what makes each post different from yesterday's; X's
    automation rules forbid near-identical posts, and its spam policy calls
    out accounts that mostly post links without commentary.
    """
    from engine.x_media import strip_links
    head = " ".join((label or "").split())
    if episode_num:
        head = f"{head} · Ep {int(episode_num)}"
    body = " ".join(strip_links(hook).split())
    budget = limit - len(head) - len(closer) - 4
    if body and budget > 20:
        body = clip_words(body, budget)
    elif budget <= 20:
        body = ""
    return "\n\n".join(p for p in (head, body, closer) if p)


def post_media(*, env_prefix: str, text: str, media_paths: Sequence,
               label: str) -> Tuple[bool, str, str, str]:
    """Post *text* with the first of *media_paths* that uploads.

    Returns ``(posted, reason, url, media_path)``. ``reason`` is ``""`` when
    the post carried media (``media_path`` says which), ``no_media`` when
    every upload failed and the text went alone, ``no_credentials`` or
    ``post_failed`` when nothing posted.
    """
    creds = x_credentials(env_prefix)
    if not creds:
        logger.warning("X post skipped for %s: no %s* credentials in the "
                       "environment", label, env_prefix or "<empty prefix>")
        return False, "no_credentials", "", ""
    from engine.x_media import upload_media
    media_id, used = None, ""
    for path in media_paths or ():
        if path and Path(path).is_file():
            media_id = upload_media(path, creds)
            if media_id:
                used = str(path)
                break
    try:
        from engine.publisher import post_to_x
        url = post_to_x(text, media_ids=[media_id] if media_id else None, **creds)
    except Exception as exc:  # noqa: BLE001 — the episode is already published
        logger.warning("X post failed for %s (non-fatal): %s", label, exc)
        return False, "post_failed", "", ""
    if not url:
        return False, "post_failed", "", ""
    logger.info("Posted %s to X%s: %s", label,
                f" with {Path(used).name}" if used else " (text only)", url)
    return True, ("" if media_id else "no_media"), url, used


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
