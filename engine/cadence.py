"""One owner for the word a surface uses for a show's cadence.

Oct 1 2026: the Shorts funnel comment said "Subscribe for daily episodes"
on every show and the X follow line said "for daily episodes" — on The DP
Pod (Monday), Peptides (Thursday), Longevity (Wednesday), Collingwood
(Friday) and Offshore North (Monday) that is a promise the show does not
keep. The registry ``schedule`` string (``shows/network_meta.yaml``) is the
public cadence (CLAUDE.md: it is one of the six places a cadence lives);
``engine.blog.next_episode_placeholder`` already reads it for the blog.
"""
from __future__ import annotations

_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def cadence_adjective(schedule: str) -> str:
    """"daily" / "weekly" / "new" from a registry schedule string, never a
    cadence the string does not support."""
    sched = (schedule or "").strip().lower()
    if not sched:
        return "new"
    if sched.startswith("daily") or sched.startswith("every day"):
        return "daily"
    if "weekly" in sched or any(d in sched for d in _DAYS):
        return "weekly"
    if "weekday" in sched:
        return "weekday"
    return "new"


def schedule_for_slug(slug: str) -> str:
    """The registry schedule string for a show, "" when unknown."""
    try:
        from generate_html import NETWORK_SHOWS  # type: ignore
        return str((NETWORK_SHOWS.get(slug) or {}).get("schedule") or "")
    except Exception:  # noqa: BLE001 — the registry is a site-layer import
        return ""


def episodes_phrase(slug: str) -> str:
    """"daily episodes" / "weekly episodes" / "new episodes"."""
    return f"{cadence_adjective(schedule_for_slug(slug))} episodes"


__all__ = ["cadence_adjective", "schedule_for_slug", "episodes_phrase"]
