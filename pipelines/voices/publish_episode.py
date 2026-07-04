#!/usr/bin/env python3
"""Publish an approved, produced Age of AI episode
(nerra_voices_publish.yml).

Reuses the network's standard publish surface (engine.publisher /
generate_html): assign the sequential episode number, add the R2-hosted MP3
to age_of_ai_podcast.rss, append the summaries JSON the site reads,
regenerate the show pages, and mark the interview ``published``. The
episode MP3 is already in R2 (produce step) — nothing binary lands in git,
per landmine #1/#2.

Run from a checkout with commit rights (the workflow commits the RSS +
summaries + regenerated pages the same way run-show.yml does).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import tempfile
from pathlib import Path

import requests

from common import (  # noqa: E402
    ROOT, SHOW_NAME, logger, notify_operator, sb_select, sb_update,
)


def _next_episode_number() -> int:
    summaries = ROOT / "digests" / "age_of_ai" / "summaries_age_of_ai.json"
    if not summaries.exists():
        return 1
    data = json.loads(summaries.read_text(encoding="utf-8")) or {}
    episodes = data.get("episodes") or data.get("age_of_ai") or []
    nums = [int(e.get("episode", 0)) for e in episodes if isinstance(e, dict)]
    return (max(nums) + 1) if nums else 1


def main() -> int:
    interview_id = os.environ.get("INTERVIEW_ID", "").strip()
    if not interview_id:
        raise RuntimeError("INTERVIEW_ID env var is required")
    interview = sb_select("interviews", f"id=eq.{interview_id}")[0]
    if interview.get("status") != "approved":
        raise RuntimeError(
            f"interview {interview_id} is {interview.get('status')!r} — "
            "publish requires status 'approved' (both gates cleared + produced)"
        )
    app = sb_select("guest_applications",
                    f"id=eq.{interview['application_id']}")[0]
    pkg = sb_select("editorial_packages",
                    f"interview_id=eq.{interview_id}"
                    f"&status=eq.approved_by_guest")[0]
    run = sb_select("interview_runs",
                    f"id=eq.{pkg['interview_run_id']}")[0]

    audio_url = run.get("recording_mixed_url")  # final episode MP3 (produce step)
    if not audio_url:
        raise RuntimeError("no final episode URL on the run row")

    episode_num = _next_episode_number()
    today = dt.date.today()
    title = f"Ep{episode_num}: {app['name']} — {interview.get('episode_thesis') or 'The Age of AI'}"
    description = pkg.get("episode_notes") or interview.get("episode_thesis") or ""

    # Duration + file size need the real file — fetch headers/bytes to tmp.
    with tempfile.TemporaryDirectory(prefix="aoa_publish_") as tmp:
        local_mp3 = Path(tmp) / f"Age_of_AI_Ep{episode_num:03d}_{today:%Y%m%d}.mp3"
        with requests.get(audio_url, stream=True, timeout=900) as resp:
            resp.raise_for_status()
            with local_mp3.open("wb") as fh:
                for chunk in resp.iter_content(1 << 16):
                    fh.write(chunk)
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(local_mp3)],
            check=True, capture_output=True, text=True, timeout=120,
        )
        duration = float(probe.stdout.strip() or 0.0)

        from engine.publisher import update_rss_feed
        update_rss_feed(
            ROOT / "age_of_ai_podcast.rss",
            episode_num, title, description, today,
            local_mp3.name, duration, local_mp3,
            audio_url=audio_url,
            audio_subdir="digests/age_of_ai",
            channel_title=SHOW_NAME,
            channel_link="https://nerranetwork.com/age-of-ai.html",
            channel_description=(
                "The interview show where the roles are reversed: Mira, an "
                "AI, calls real people and asks the questions — live, on "
                "the record."
            ),
            channel_author="Nerra Network",
            channel_email="patrick@planetterrian.com",
            channel_image="https://nerranetwork.com/assets/covers/age-of-ai.jpg",
            channel_category="Society & Culture",
            channel_subcategory="Personal Journals",
            channel_keywords=("AI, artificial intelligence, interviews, "
                              "future of work, technology and society"),
            guid_prefix="age-of-ai",
        )

    # Summaries JSON (site + dashboards read this shape network-wide).
    summaries_path = ROOT / "digests" / "age_of_ai" / "summaries_age_of_ai.json"
    summaries_path.parent.mkdir(parents=True, exist_ok=True)
    data = {"episodes": []}
    if summaries_path.exists():
        data = json.loads(summaries_path.read_text(encoding="utf-8")) or {"episodes": []}
    data.setdefault("episodes", []).append({
        "episode": episode_num,
        "date": today.isoformat(),
        "title": title,
        "hook": interview.get("episode_thesis") or "",
        "summary": description,
        "audio_url": audio_url,
        "guest": app["name"],
        "chapters": pkg.get("chapter_markers") or [],
    })
    summaries_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Regenerate the show pages so the episode appears on the site.
    subprocess.run(
        ["python", "generate_html.py", "--show", "age_of_ai"],
        cwd=ROOT, check=True, timeout=600,
    )

    sb_update("interviews", f"id=eq.{interview_id}",
              {"status": "published", "episode_number": episode_num})
    sb_update("editorial_packages", f"id=eq.{pkg['id']}",
              {"status": "published"})

    notify_operator(
        f"Age of AI Ep{episode_num} PUBLISHED: {app['name']} — RSS updated, "
        f"site regenerated. {audio_url}"
    )
    logger.info("Published episode %d (%s)", episode_num, app["name"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
