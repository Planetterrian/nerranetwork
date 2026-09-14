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
    return show_memory.memory_pre_fetch(config, _SLUG)


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
