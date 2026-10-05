"""Offshore North hooks — recursive narrative memory (Aug 2026 field review).

Thin wrapper over engine.show_memory; see shows/hooks/models_agents.py.
The show's spine is a two-year longitudinal story (the first Canadian
campaign to finish the Vendée Globe, 12 Nov 2028) — the exact shape the
show_memory engine chronicles.
"""

from __future__ import annotations

from engine import show_memory

_SLUG = "offshore_north"


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    ctx = dict(show_memory.memory_pre_fetch(config, _SLUG) or {})
    # Sep 19 2026: the dated CAMPAIGN STATUS block, computed from the same
    # verified record the public dashboard bakes in (last known position
    # and its age, race states by today's date, results on record, the
    # Route du Rhum entry, the countdown). Both prompts reference
    # {campaign_status}; run_show / engine.pipeline default it to "" so
    # a failure here degrades to the pre-Sep-19 prompt, never a KeyError.
    # Oct 4 2026: the position comes from the team's YB tracker, read FRESH
    # at episode time (the committed rail can be a day old), and the fix is
    # also handed over as a source article so the claims gate can verify
    # the position sentence against the copy this run holds.
    tracker = _fresh_tracker()
    try:
        from engine.offshore_north_status import campaign_status_from_files

        ctx["campaign_status"] = campaign_status_from_files(tracker=tracker)
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning(
            "Offshore North campaign status skipped (non-fatal): %s", exc
        )
        ctx["campaign_status"] = ""
    articles = _source_articles(tracker)
    if articles:
        ctx["articles"] = articles
    return ctx


#: How far back each kind of Instagram account is read for an episode: the
#: campaign posts rarely, so it gets the same 30 days as its feeds
#: (``window_hours: 720``); the class and race accounts post daily, so a
#: weekly show reads one week of them.
_IG_CAMPAIGN_DAYS = 30
_IG_OTHER_DAYS = 8
_IG_MAX_ARTICLES = 8


def _curated() -> dict:
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent.parent / "site" / "data" / "offshore_north_dashboard.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _fresh_tracker():
    try:
        from engine.yb_tracker import fetch_summary

        cfg = (_curated().get("campaign") or {}).get("tracker") or {}
        if not cfg.get("keyword"):
            return None
        return fetch_summary(cfg["keyword"], places=cfg.get("places") or [])
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning("Offshore North tracker read failed (non-fatal): %s", exc)
        return None


def _source_articles(tracker) -> list:
    """The tracker fix + recent Instagram captions as hook articles."""
    import datetime as _dt
    import logging

    log = logging.getLogger(__name__)
    out: list = []
    today = _dt.datetime.now(_dt.timezone.utc).date()
    try:
        from engine.yb_tracker import tracker_article

        art = tracker_article(tracker, today) if tracker else None
        if art:
            out.append(art)
    except Exception as exc:  # noqa: BLE001
        log.warning("Offshore North tracker article skipped: %s", exc)
    try:
        from engine.instagram_source import fetch_recent, handles_from_follow, post_articles

        curated = _curated()
        handles = handles_from_follow(curated.get("follow"))
        campaign = {h.lower() for h in ((curated.get("campaign") or {}).get("instagram_handles") or [])}
        posts = fetch_recent([h for h in handles if h.lower() in campaign],
                             since_days=_IG_CAMPAIGN_DAYS)
        posts += fetch_recent([h for h in handles if h.lower() not in campaign],
                              since_days=_IG_OTHER_DAYS)
        posts.sort(key=lambda p: p["timestamp"], reverse=True)
        out.extend(post_articles(posts)[:_IG_MAX_ARTICLES])
    except Exception as exc:  # noqa: BLE001
        log.warning("Offshore North Instagram source skipped: %s", exc)
    return out


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    show_memory.memory_post_generate(config, _SLUG, digest_text or "", episode_num or 0)
    _refresh_dashboard_data()


def _refresh_dashboard_data() -> None:
    """Rewrite ``api/offshore_north_dashboard.json`` after every episode
    (Sep 14 2026): the campaign dashboard's live half — latest team posts
    with excerpts, the newest dated position fix, offshore headlines. The
    Tesla/SpaceX pattern: the show hook writes the same-origin file,
    run-show.yml commits it, the page reads it. Best-effort by contract —
    a failed refresh keeps the previous file and never touches the run.
    """
    try:
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent.parent
        scripts_dir = root / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        import fetch_offshore_north_dashboard as _dash  # noqa: WPS433

        _dash.main(["--out", str(root / "api" / "offshore_north_dashboard.json")])
    except Exception as exc:  # noqa: BLE001 — never block an episode
        import logging

        logging.getLogger(__name__).warning(
            "Offshore North dashboard data refresh failed (non-fatal): %s", exc
        )
