"""One place that decides how long a title may be, and where to cut it.

Every surface the network publishes to enforces its own limit, and each
one truncates differently and silently:

* **YouTube** hard-caps titles at 100 characters. When a podcast RSS item
  is longer, YouTube ingests it anyway and *rewrites* the title, cutting
  mid-word: ``"Ep 133: Virtual reality experiments show how artificial
  light at night changes how coral reef fis..."``. It emails the channel
  owner afterwards saying "no action is required from you". Between June
  and July 2026 that happened on every show in the network, repeatedly.
* **Google Search** renders roughly 60 characters of a ``<title>``.
* **Apple Podcasts** and most players clamp episode titles in the UI.

The failure mode is always the same: something downstream chops a
sentence in the middle of a word and we find out from an email, or not
at all. Fixing it per-surface is how it got this way — ``engine.blog``
sliced ``hook[:100]``, ``engine.video_metadata._truncate`` sliced
``text[:max_len - 3]``, and ``run_show`` built ``f"Ep {n}: {hook}"`` with
no cap at all. Three different bugs, one shape.

So the rule lives here, once. Surfaces import a limit and a function;
they do not implement clipping themselves. A new surface adds its limit
to this module, which is also the place to look when a platform changes
its rules.
"""

from __future__ import annotations

__all__ = [
    "YOUTUBE_TITLE_MAX",
    "PODCAST_EPISODE_TITLE_MAX",
    "WEB_TITLE_LEAD_MAX",
    "NEWSLETTER_SUBJECT_MAX",
    "ELLIPSIS",
    "clip_words",
    "episode_title",
    "fits",
]

# --- Limits -----------------------------------------------------------

#: YouTube rejects/rewrites video titles beyond this. Hard platform cap.
YOUTUBE_TITLE_MAX = 100

#: Podcast RSS ``<item><title>``. Same 100 as YouTube ON PURPOSE: YouTube
#: ingests the podcast feed directly, so the feed is a YouTube surface
#: whether or not we think of it that way. This is the limit that was
#: missing and that YouTube was silently enforcing for us.
PODCAST_EPISODE_TITLE_MAX = 100

#: Lead portion of an HTML ``<title>`` before the episode/brand tail.
#: Google renders ~60 chars total; this leaves room for " — EpN | Show"
#: while keeping the first words — the ones that get read — intact.
WEB_TITLE_LEAD_MAX = 62

#: Email clients truncate subject lines around here on mobile.
NEWSLETTER_SUBJECT_MAX = 78

ELLIPSIS = "…"

# Trailing characters that read as debris once the tail is gone.
_TRAILING = " \t\n.,;:!?-–—‐"

#: Characters we are willing to break a title at, best-first.
_BREAK_CHARS = (" ", "-", "–", "—", "/")


# --- Core -------------------------------------------------------------

def clip_words(text: str, limit: int, *, ellipsis: str = ELLIPSIS) -> str:
    """Clip *text* to at most *limit* characters, never mid-word.

    The returned string — ellipsis included — is guaranteed to be
    ``<= limit``. That guarantee is the point: callers pass a platform
    cap straight in and the result is always safe to publish.

    Cuts at the last boundary that fits — space, hyphen, dash or slash.
    The ONLY case that can still split a word is when the first word
    alone overruns the budget, because then no boundary exists.

    >>> clip_words("a much longer sentence than fits here", 20)
    'a much longer…'
    >>> clip_words("short", 20)
    'short'
    """
    text = (text or "").strip()
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text

    budget = limit - len(ellipsis)
    if budget <= 0:
        return text[:limit]

    cut = text[:budget]
    # Break at the last boundary that fits. Hyphens and slashes count:
    # "1.6-trillion-parameter" reads fine cut to "1.6-trillion", and
    # without them a short first word followed by a long compound
    # ("A 1.6-trillion-parameter model") had no usable space boundary and
    # fell through to a mid-word cut.
    boundary = max(cut.rfind(c) for c in _BREAK_CHARS)
    if boundary > 0:
        cut = cut[:boundary]
    # boundary <= 0 means the first word alone overruns the budget — there
    # is genuinely nowhere to break, so the hard cut stands. That is the
    # only path that can split a word.
    return cut.rstrip(_TRAILING) + ellipsis


def fits(text: str, limit: int) -> bool:
    """True when *text* needs no clipping for *limit*."""
    return len((text or "").strip()) <= limit


def episode_title(
    hook: str,
    episode_num,
    *,
    prefix: str = "Ep",
    limit: int = PODCAST_EPISODE_TITLE_MAX,
    fallback: str = "",
) -> str:
    """Build ``"Ep 133: <hook>"`` guaranteed to fit *limit*.

    The episode label is never sacrificed — it is how listeners and the
    feed itself identify the episode — so the hook absorbs the clipping.
    Falls back to *fallback* (typically ``"<Show> - Episode N - <date>"``)
    when there is no hook, and that fallback is clipped too rather than
    trusted.

    *prefix* is a parameter because the Russian shows label episodes
    ``"Выпуск"``; the arithmetic has to use the real prefix length, not
    an assumed English one.
    """
    label = f"{prefix} {episode_num}:"
    hook = (hook or "").strip()

    if not hook:
        return clip_words(fallback, limit) if fallback else clip_words(label.rstrip(":"), limit)

    room = limit - len(label) - 1  # the space after the colon
    if room <= 0:
        # Pathological limit; keep the identifier, drop the hook.
        return clip_words(label.rstrip(":"), limit)

    return f"{label} {clip_words(hook, room)}"
