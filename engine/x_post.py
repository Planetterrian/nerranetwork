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
from datetime import date as _date_type
from pathlib import Path
from typing import Optional, Sequence, Tuple

from engine.release_schedule import x_posting_order
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
#     X POSTING ORDER — its X slot rank in engine.release_schedule (Oct 17
#     2026: the order had been a hand-kept roster, which stopped matching the
#     posting order when the network moved to Eastern time). A daily show
#     asks every FOLLOW_ASK_EVERY days; two posts next to each other in the
#     day's feed never ask on the same day; a weekly show asks once in each
#     block of four of its weekdays, on a day neither neighbour asks;
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

#: Every show that posts to @nerranetwork through the clip path, plus Nerra
#: Daily, with its cadence: ``None`` = daily, else the weekday it posts
#: (Monday = 0, from run-show.yml's CRON_MAP). Membership and cadence only —
#: the ORDER is the X slot order (engine.release_schedule.x_posting_order).
#: A show missing here never asks; tests/test_x_follow_ask_2026_10_15.py
#: fails CI when a show posts to the network account and is not listed.
FOLLOW_ASK_CADENCE = {
    "nerra_daily": None,
    "spacex": None,
    "mag7": None,
    "modern_investing": None,
    "omni_view": None,
    "prediction_markets": None,
    "models_agents": None,
    "ai_chips": None,
    "fascinating_frontiers": None,
    "planetterrian": None,
    "unintended_consequences": None,
    "first_principles": None,
    "env_intel": 0,
    "offshore_north": 0,
    "longevity": 2,
    "peptides": 3,
    "collingwood": 4,
    "vancouver": None,
}

#: ``(slug, weekday)`` in X posting order — derived, never hand-ordered.
FOLLOW_ASK_ROSTER = tuple(
    (slug, FOLLOW_ASK_CADENCE[slug]) for slug in x_posting_order(FOLLOW_ASK_CADENCE))


def _roster_slugs() -> list:
    return [slug for slug, _wd in FOLLOW_ASK_ROSTER]


def _daily_slugs() -> list:
    return [slug for slug, wd in FOLLOW_ASK_ROSTER if wd is None]


def _posters_on(day) -> list:
    """The roster shows that post on *day*, in posting order."""
    return [slug for slug, wd in FOLLOW_ASK_ROSTER if wd is None or wd == day.weekday()]


def _daily_asks(slug: str, day) -> bool:
    """A daily show's phase is its rank among the daily posters: consecutive
    daily posters are one phase apart, so they never ask on the same day."""
    return (day.toordinal() + _daily_slugs().index(slug)) % FOLLOW_ASK_EVERY == 0


def _weekly_ask_day(slug: str, day):
    """The date in *day*'s block of four weeks on which weekly *slug* asks.

    The first of its four weekdays in the block on which no posting
    neighbour asks: a daily neighbour by its phase, an EARLIER weekly
    neighbour by its own choice (a later one avoids this one). A daily
    neighbour asks on one of the four days and an earlier weekly on one, so
    a day is always left.
    """
    wd = FOLLOW_ASK_CADENCE[slug]
    week = (day.toordinal() - 1) // 7          # ordinal 1 is a Monday
    first = week - week % FOLLOW_ASK_EVERY
    for w in range(first, first + FOLLOW_ASK_EVERY):
        cand = _date_type.fromordinal(1 + 7 * w + wd)
        posters = _posters_on(cand)
        i = posters.index(slug)
        blocked = False
        for j in (i - 1, i + 1):
            if not 0 <= j < len(posters):
                continue
            other = posters[j]
            if FOLLOW_ASK_CADENCE[other] is None:
                blocked = blocked or _daily_asks(other, cand)
            elif j < i:
                blocked = blocked or _weekly_ask_day(other, cand) == cand
        if not blocked:
            return cand
    return None


def asks_for_follow(show_slug: str, day) -> bool:
    """True when *show_slug*'s post on *day* opens its closer list on an ask."""
    if show_slug not in FOLLOW_ASK_CADENCE:
        return False
    wd = FOLLOW_ASK_CADENCE[show_slug]
    if wd is None:
        return _daily_asks(show_slug, day)
    if day.weekday() != wd:
        return False
    return _weekly_ask_day(show_slug, day) == day


def post_closers(show_slug: str, day) -> Tuple[str, ...]:
    """The closers for *show_slug*'s post on *day*, in preference order.

    On an ask day (:func:`asks_for_follow`) the list opens with a follow
    ask; every list ends on :data:`CLIP_CLOSER`, so a hook that fit before
    this change still fits. :func:`clip_post_text` takes the first closer
    the whole hook fits beside.
    """
    if show_slug not in FOLLOW_ASK_CADENCE:
        return (CLIP_CLOSER,)
    ordinal = day.toordinal()
    idx = _roster_slugs().index(show_slug)
    plain = PLAIN_CLOSERS[(ordinal + idx) % len(PLAIN_CLOSERS)]
    if not asks_for_follow(show_slug, day):
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


def post_video_reply(*, env_prefix: str, text: str, video_path, subtitles_path="",
                     in_reply_to: str, label: str) -> Tuple[bool, str, str]:
    """Post a full-episode video as a reply to *in_reply_to* (Oct 17 2026).

    Returns ``(posted, reason, url)``. Unlike :func:`post_media` it never
    falls back to text: a reply that says "the full episode" with no
    episode in it is worse than no reply. ``reason`` is ``""`` or
    ``no_subtitles`` on success; ``no_credentials``, ``upload_failed`` or
    ``post_failed`` otherwise.
    """
    creds = x_credentials(env_prefix)
    if not creds:
        return False, "no_credentials", ""
    from engine.x_media import LONG_STATUS_TIMEOUT_S, add_subtitles, upload_media
    media_id = upload_media(video_path, creds, status_timeout=LONG_STATUS_TIMEOUT_S, timeout=300)
    if not media_id:
        return False, "upload_failed", ""
    note = ""
    if subtitles_path and Path(subtitles_path).is_file():
        sub_id = upload_media(subtitles_path, creds)
        if not (sub_id and add_subtitles(media_id, sub_id, creds)):
            note = "no_subtitles"
    else:
        note = "no_subtitles"
    try:
        from engine.publisher import post_to_x
        url = post_to_x(text, media_ids=[media_id], in_reply_to_tweet_id=in_reply_to, **creds)
    except Exception as exc:  # noqa: BLE001
        logger.warning("X full-episode reply failed for %s: %s", label, exc)
        return False, "post_failed", ""
    if not url:
        return False, "post_failed", ""
    logger.info("Posted the full %s under its post: %s", label, url)
    return True, note, url


def long_form_reply_text(label: str, episode_num: int) -> str:
    """The reply's one line. No link: a post with a URL costs $0.20."""
    return f"The full episode: {label}, episode {int(episode_num)}."


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
