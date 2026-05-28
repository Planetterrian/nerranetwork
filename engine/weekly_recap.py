"""Sunday weekly-recap digest synthesis.

When a daily show ticks on a Sunday with ``weekly_recap_on_sunday: true``
in its YAML, the runner short-circuits the news-fetch + daily-digest
stages and instead asks this module to produce a digest-shaped
markdown blob synthesised from the past 7 days of that show's
episodes. The rest of the pipeline (podcast script generation, TTS,
publish) runs unchanged on this synthetic digest.

Why digest-shaped, not direct podcast-script: the existing podcast
prompt knows how to turn a digest into ~15-minute spoken narration.
Re-using that path keeps the recap feel consistent with daily
episodes rather than introducing a parallel "weekly podcast" prompt
ladder for every show. Per-show flavour can still be added by
appending a brief "RECAP MODE" instruction to the podcast prompt
when the runner detects Sunday — but the v1 cut keeps prompts
unchanged.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def build_weekly_recap_digest(
    show_slug: str,
    show_name: str,
    week_ending: date,
) -> Optional[str]:
    """Build a digest-shaped markdown summary of the past 7 days for
    *show_slug*. Returns ``None`` if the content lake has fewer than
    two episodes in window (recap with one or zero episodes is not
    meaningful — the runner falls back to a normal daily fetch).

    The output is intentionally minimal and uses the same surface
    structure as a daily digest (title heading, hook, "Top Stories"
    list with title + summary per item) so the existing podcast
    prompt can ingest it without any branching.
    """
    try:
        from engine.content_lake import query_show_range
    except Exception as exc:  # pragma: no cover — content lake optional in tests
        logger.warning(
            "weekly_recap: content lake unavailable (%s) — falling back",
            exc,
        )
        return None

    start_date = (week_ending - timedelta(days=6)).isoformat()
    end_date = week_ending.isoformat()

    try:
        episodes = query_show_range(show_slug, start_date, end_date) or []
    except Exception as exc:  # pragma: no cover
        logger.warning("weekly_recap: query_show_range failed (%s)", exc)
        return None

    if len(episodes) < 2:
        logger.info(
            "weekly_recap: only %d episode(s) in window for %s — falling back",
            len(episodes), show_slug,
        )
        return None

    # Sort by date ascending so the recap reads chronologically.
    episodes = sorted(
        episodes,
        key=lambda ep: (ep.get("date") or "", ep.get("episode_num") or 0),
    )

    # Headline: the most recent hook is usually the freshest, but
    # listeners benefit from a recap-flavoured one-liner that signals
    # this isn't a normal daily.
    week_label = f"{start_date} to {end_date}"
    title = f"# {show_name} — Weekly Recap"
    hook = (
        f"**HOOK:** Looking back at {len(episodes)} episodes from "
        f"{week_label} — the stories that mattered, what we learned, "
        f"and what to watch next."
    )

    # Each episode contributes a "Top Story" entry. We use the
    # episode's own hook + the first paragraph of its digest_md so
    # the LLM sees coherent prose, not a bag of bullet points.
    items: list[str] = []
    for idx, ep in enumerate(episodes, start=1):
        ep_num = ep.get("episode_num") or "?"
        ep_date = ep.get("date") or ""
        ep_hook = (ep.get("hook") or "").strip()
        digest_md = (ep.get("digest_md") or "").strip()

        # Pull the first 2 substantive paragraphs of the canonical
        # digest as the body — caps each entry around ~1000 chars
        # so the synthesised digest stays under the LLM context
        # window even with a full 7-episode week.
        paragraphs = [p.strip() for p in digest_md.split("\n\n") if p.strip()]
        # Skip leading metadata paragraphs (title heading, **HOOK:**
        # label, **Date:** line, TSLA price line) that aren't prose.
        body_paragraphs: list[str] = []
        for p in paragraphs:
            if (
                p.startswith("#")
                or p.startswith(("**HOOK:", "**Date:", "**Дата:",
                                 "**REAL-TIME TSLA price:", "**TSLA today:",
                                 "**Theme:", "**Тема:", "**ЗАГОЛОВОК:"))
            ):
                continue
            body_paragraphs.append(p)
            if len(body_paragraphs) >= 2:
                break
        body = "\n\n".join(body_paragraphs)[:1000]

        title_line = ep_hook or f"Episode {ep_num}"
        items.append(
            f"{idx}. **From Ep {ep_num} ({ep_date}): {title_line}**\n"
            f"   {body}"
        )

    recap = "\n\n".join([
        title,
        hook,
        "━━━━━━━━━━━━━━━━━━━━",
        "### This Week's Top Stories",
        *items,
        "━━━━━━━━━━━━━━━━━━━━",
        "## Recap framing for the host",
        (
            "This is a Sunday weekly recap. The host should weave the "
            "stories above into a single coherent narrative — not a "
            "list of news items. Group related threads, call out the "
            "most consequential development of the week, draw forward "
            "connections (\"what to watch next week\"), and end with "
            "one practical takeaway listeners can use. Keep the same "
            "voice and pacing as a daily episode."
        ),
    ])

    # TST-specific enhancement: inject narrative memory framing when available.
    # This is intentionally best-effort (the narrative tracker lives in the
    # gitignored content lake + digests/ on the runner). If anything fails we
    # just ship the plain recap.
    if show_slug == "tesla":
        try:
            from engine import tesla_memory
            from pathlib import Path as _Path
            tracker = tesla_memory.load_narrative_tracker(
                _Path("digests/tesla_shorts_time")
            )
            narrative_block = tesla_memory.build_narrative_status_block(tracker)
            if narrative_block:
                recap += (
                    "\n\n" + narrative_block +
                    "\n\nUse the narrative status above to highlight meaningful "
                    "progress or open questions across the week."
                )
        except Exception:
            pass

    return recap
