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

# ---------------------------------------------------------------------------
# Closers and the follow ask (Oct 15 2026, operator-directed).
#
# Every @nerranetwork post had ended on the same closer, and none ever asked
# anyone to follow. Now the closer rotates among a few phrasings, and about
# one post in four swaps it for a short follow ask. Rules that bind:
#   * the ask is light: one sentence, no "please", no exclamation, no claim
#     the account cannot keep, and every ask still says where the episode is;
#   * it is never the reason a hook gets clipped: when the hook does not fit
#     whole beside an ask, the post takes a plain closer that day;
#   * which posts ask is decided by the calendar and the show's place in the
#     posting order (FOLLOW_ASK_ROSTER), so two asks never sit next to each
#     other in the feed and a daily show asks once every four days;
#   * a plain day rotates the closer's wording but falls back to the old
#     closer whenever the longer phrasing would clip the hook.
# Each line says only what is true of the account: it posts one story from
# each new episode, through the day, from shows across the network.
# ---------------------------------------------------------------------------
PLAIN_CLOSERS = (
    CLIP_CLOSER,
    "Listen to the full episode: link in bio, or find Nerra Network in any podcast app.",
    "The full episode is in your podcast app under Nerra Network, or via the link in bio.",
)
FOLLOW_ASK_CLOSERS = (
    "Follow along for more from across the network. Full episode: link in bio.",
    "Worth a minute? Follow for the next one. Full episode: link in bio.",
    "We post one story from each new episode here. Follow along; full episode in bio.",
    "If you enjoyed this, a follow brings the next one to your feed. Full episode: link in bio.",
)
#: One post in this many carries the ask.
FOLLOW_ASK_EVERY = 4

#: Shows that post to @nerranetwork through the clip path, in the order their
#: posts reach the queue (their run_show slot; Nerra Daily last). A weekly
#: show names its weekday (Monday = 0) and only counts on that day. A show
#: missing here never asks; tests/test_x_follow_ask_2026_10_15.py fails CI
#: when a show posts to the network account and is not listed.
FOLLOW_ASK_ROSTER = (
    ("omni_view", None),
    ("planetterrian", None),
    ("fascinating_frontiers", None),
    ("models_agents", None),
    ("env_intel", 0),
    ("modern_investing", None),
    ("first_principles", None),
    ("unintended_consequences", None),
    ("spacex", None),
    ("ai_chips", None),
    ("offshore_north", 0),
    ("collingwood", 4),
    ("mag7", None),
    ("longevity", 2),
    ("peptides", 3),
    ("prediction_markets", None),
    ("vancouver", None),
    ("nerra_daily", None),
)


def _roster_slugs() -> list:
    return [slug for slug, _wd in FOLLOW_ASK_ROSTER]


def post_closers(show_slug: str, day) -> Tuple[str, ...]:
    """The closers for *show_slug*'s post on *day*, in preference order.

    A show's place in the FULL roster (weekly shows included, whether or not
    they post that day) fixes its phase, so a daily show asks every
    ``FOLLOW_ASK_EVERY`` days and neighbours in the posting order never ask
    on the same day. On an ask day the list opens with a follow ask; every
    list ends on :data:`CLIP_CLOSER`, so a hook that fit before this change
    still fits. :func:`clip_post_text` takes the first closer the whole hook
    fits beside.
    """
    ordinal = day.toordinal()
    roster = _roster_slugs()
    if show_slug not in roster:
        return (CLIP_CLOSER,)
    idx = roster.index(show_slug)
    plain = PLAIN_CLOSERS[(ordinal + idx) % len(PLAIN_CLOSERS)]
    if (ordinal + idx) % FOLLOW_ASK_EVERY:
        return tuple(dict.fromkeys((plain, CLIP_CLOSER)))
    ask = FOLLOW_ASK_CLOSERS[(ordinal // FOLLOW_ASK_EVERY + idx) % len(FOLLOW_ASK_CLOSERS)]
    shortest = min(FOLLOW_ASK_CLOSERS, key=len)
    return tuple(dict.fromkeys((ask, shortest, plain, CLIP_CLOSER)))


def has_follow_ask(text: str) -> bool:
    """True when *text* ends on one of the follow-ask closers."""
    return any((text or "").rstrip().endswith(c) for c in FOLLOW_ASK_CLOSERS)


def clip_post_text(*, label: str, hook: str, episode_num: Optional[int] = None,
                   closer: str = CLIP_CLOSER, limit: int = CLIP_TEXT_MAX,
                   closers: Optional[Sequence[str]] = None) -> str:
    """``<label> · Ep N`` / the episode hook / the closer, with no link.

    The hook is what makes each post different from yesterday's; X's
    automation rules forbid near-identical posts, and its spam policy calls
    out accounts that mostly post links without commentary.

    *closers* (Oct 15 2026) is a preference list: the first closer the
    whole hook fits beside is used, and the last one is used regardless
    (clipping the hook as before). Without it, *closer* is the only option.
    """
    from engine.x_media import strip_links
    head = " ".join((label or "").split())
    if episode_num:
        head = f"{head} · Ep {int(episode_num)}"
    body = " ".join(strip_links(hook).split())
    options = [c for c in (closers or ()) if c] or [closer]
    chosen = options[-1]
    for candidate in options[:-1]:
        if len(body) <= limit - len(head) - len(candidate) - 4:
            chosen = candidate
            break
    budget = limit - len(head) - len(chosen) - 4
    if body and budget > 20:
        body = clip_words(body, budget)
    elif budget <= 20:
        body = ""
    return "\n\n".join(p for p in (head, body, chosen) if p)


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
