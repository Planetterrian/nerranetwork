#!/usr/bin/env python3
"""Verify YouTube Analytics API + OAuth are live after operator re-auth.

Prints a human-readable report and a machine line ``STATUS=ok|fail|noop``
as the last stdout line (consumed by the verify workflow). Exit code is
always 0 so a dormant loop never red-X's Actions; failures are surfaced
via ``::error::`` annotations.

Usage::

    python scripts/verify_youtube_analytics.py --days 90
    python scripts/verify_youtube_analytics.py --days 90 --out api/youtube_stats.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
logger = logging.getLogger("verify_youtube_analytics")


def _secret_presence() -> dict:
    return {
        "YOUTUBE_CLIENT_ID": bool(os.environ.get("YOUTUBE_CLIENT_ID")),
        "YOUTUBE_CLIENT_SECRET": bool(os.environ.get("YOUTUBE_CLIENT_SECRET")),
        "YOUTUBE_REFRESH_TOKEN_EN": bool(os.environ.get("YOUTUBE_REFRESH_TOKEN_EN")),
        "YOUTUBE_REFRESH_TOKEN_RU": bool(os.environ.get("YOUTUBE_REFRESH_TOKEN_RU")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--out", default="api/youtube_stats.json")
    parser.add_argument("--digests", default="digests")
    args = parser.parse_args()

    presence = _secret_presence()
    logger.info("Secret presence: %s", presence)
    if not presence["YOUTUBE_CLIENT_ID"] or not presence["YOUTUBE_CLIENT_SECRET"]:
        print("::error::YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET missing")
        print("STATUS=fail")
        return 0
    if not presence["YOUTUBE_REFRESH_TOKEN_EN"]:
        print("::error::YOUTUBE_REFRESH_TOKEN_EN missing — re-run oauth bootstrap")
        print("STATUS=fail")
        return 0

    # Import after env check so a missing google lib still reports clearly.
    from scripts import fetch_youtube_analytics as fya  # type: ignore
    # Prefer loading the sibling module the same way tests do when package
    # import fails (scripts/ is not always a package).
    try:
        payload = fya.fetch(ROOT / args.digests, args.days)
    except Exception:
        import importlib.util
        path = ROOT / "scripts" / "fetch_youtube_analytics.py"
        spec = importlib.util.spec_from_file_location("fetch_youtube_analytics", path)
        fya = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(fya)
        payload = fya.fetch(ROOT / args.digests, args.days)

    if payload is None:
        print(
            "::error::YouTube Analytics returned no data. Likely causes: "
            "(1) YouTube Analytics API still disabled on the GCP project, "
            "(2) refresh token lacks yt-analytics.readonly — revoke + "
            "re-run scripts/youtube_oauth_bootstrap.py, "
            "(3) indexed videos have no watch data in the window yet. "
            "Check the WARNING lines above for the exact 403 reason."
        )
        print("STATUS=fail")
        return 0

    n_shows = len(payload.get("shows") or {})
    n_videos = sum(len(s.get("videos") or []) for s in payload["shows"].values())
    logger.info("OK — analytics for %d videos across %d shows", n_videos, n_shows)

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    logger.info("Wrote %s", out_path)

    # Distil per-show title hints (clean no-op when <4 rated videos/show).
    import importlib.util
    path = ROOT / "scripts" / "update_youtube_performance.py"
    spec = importlib.util.spec_from_file_location("update_youtube_performance", path)
    uyp = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(uyp)
    # update_youtube_performance.main reads --stats from argv; call the
    # file's entry helpers if exposed, else subprocess-style via main.
    old_argv = sys.argv
    try:
        sys.argv = ["update_youtube_performance.py", "--stats", str(out_path)]
        uyp.main()
    finally:
        sys.argv = old_argv

    hints = sorted(ROOT.glob("digests/*/youtube_performance.json"))
    logger.info("Performance hint files: %d", len(hints))
    for p in hints[:8]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            hint = (data.get("title_hint") or "").strip()
            logger.info("  %s: %s", p.parent.name,
                        (hint[:80] + "…") if len(hint) > 80 else (hint or "(empty — need ≥4 rated videos)"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("  %s unreadable: %s", p, exc)

    # Sample a few retention rows for the Actions log.
    samples = []
    for show, block in sorted(payload["shows"].items()):
        for v in (block.get("videos") or [])[:2]:
            samples.append(
                f"{show} ep{v.get('episode')} {v.get('kind')}: "
                f"{v.get('average_view_percentage')}% retention, "
                f"{v.get('views')} views"
            )
    for line in samples[:12]:
        logger.info("sample: %s", line)

    print(f"::notice::YouTube Analytics LIVE — {n_videos} videos / {n_shows} shows")
    print("STATUS=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
