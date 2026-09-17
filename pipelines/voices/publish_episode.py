#!/usr/bin/env python3
"""Publish an approved, produced interview episode
(nerra_voices_publish.yml) — The Age of AI or Nerra Voices, resolved per
interview from its ``show`` column.

Reuses the network's standard publish surface (engine.publisher /
generate_html): assign the sequential episode number, add the R2-hosted MP3
to the show's RSS feed, append the summaries JSON the site reads,
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
from typing import List
from pathlib import Path

import requests

from common import (  # noqa: E402
    ROOT, VoiceShow, logger, notify_operator, sb_select, sb_update, show_for,
    guest_links,
    guest_links_markdown,
)


def _next_episode_number(show: VoiceShow) -> int:
    summaries = show.summaries_path
    if not summaries.exists():
        return 1
    data = json.loads(summaries.read_text(encoding="utf-8")) or {}
    episodes = data.get("episodes") or data.get(show.slug) or []
    nums = [int(e.get("episode", 0)) for e in episodes if isinstance(e, dict)]
    return (max(nums) + 1) if nums else 1


def find_publishable() -> List[str]:
    """Interview ids that have cleared BOTH gates and are not yet published.

    Why a sweep exists (July 30 2026). Every other stage of this pipeline
    is automatic — firing is a 5-minute cron, post-processing runs off the
    hangup webhook — but publish was ``workflow_dispatch`` only, so the
    terminal step ran when a human remembered to enter an interview id.
    Gate 2 auto-approves a guest transcript after 7 days, so an episode
    can advance to ``approved`` with nobody watching and then sit.

    That is not hypothetical: the 2026-07-17 interview (24 minutes,
    recorded, produced, editorially reviewed, guest-approved) was still
    unpublished 13 days later, while the 2026-07-20 interview recorded
    three days AFTER it published normally because someone happened to
    dispatch that one.

    Publishing here does not bypass a human gate — it runs only for rows
    where both gates are already recorded as cleared, which is the same
    precondition the manual path enforces.
    """
    out: List[str] = []
    for interview in sb_select("interviews", "status=eq.approved"):
        iid = interview.get("id")
        if not iid:
            continue
        pkgs = sb_select("editorial_packages",
                         f"interview_id=eq.{iid}&status=eq.approved_by_guest")
        if pkgs:
            out.append(str(iid))
    return out


def episode_audio(run: dict) -> str:
    """The URL of the thing we are actually publishing.

    Sept 16 2026. This read ``recording_mixed_url``, which for every episode
    cut by the new pipeline is the RAW mix of the room — no introduction, no
    close, nothing edited out, and a quarter-gigabyte WAV. Dan Perra's
    episode was one approval away from going out as the unedited
    forty-seven-minute room with the false ending still in it. The assembled
    episode is recorded on the run row by assemble_edit; the older
    produce_episode path overwrites recording_mixed_url with its finished
    MP3, so that still counts. The raw mix never does.
    """
    tracks = (run.get("grok_session_log") or {}).get("tracks") or {}
    edit = str((tracks.get("edit") or {}).get("url") or "").strip()
    if edit:
        return edit
    url = str(run.get("recording_mixed_url") or "").strip()
    if url and not url.endswith("_mixed.wav"):
        return url
    raise RuntimeError(
        "no assembled episode on this run — publishing would ship the raw "
        "room. Run the assemble workflow for this interview first."
    )


def _bullets(text: str) -> str:
    """Free text from a guest, as markdown that keeps their own links."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip().lstrip("-*\u2022 ").strip()
        if line:
            out.append(f"- {line}")
    return "\n".join(out)


def write_episode_digest(show, episode_num: int, when: dt.date, title: str,
                         interview: dict, app: dict, pkg: dict,
                         audio_url: str) -> Path:
    """The episode's blog post, as the digest markdown every other show writes.

    Sept 17 2026. The interview shows bypass run_show, so they never wrote a
    digest and never got a post — an hour of somebody's expertise reached
    the site as one line in a summary list. generate_html.py already turns
    digests/<slug>/*.md into blog/<slug>/ep###.html; this writes the file it
    reads, so an interview episode gets the same page as everything else on
    the network, with the guest's own links on it.
    """
    thesis = (interview.get("episode_thesis") or "").strip()
    notes = (pkg.get("episode_notes") or "").strip()
    bio = (app.get("bio") or "").strip()
    materials = (pkg.get("guest_materials") or "").strip()
    transcript = (pkg.get("transcript_cleaned") or "").strip()
    name = app.get("name") or "our guest"
    role = ", ".join(x for x in (app.get("title"), app.get("organization")) if x)

    parts = [f"# {show.name}"]
    if thesis:
        parts.append(f"> **{thesis}**")
    parts.append(f"*Episode {episode_num} · {when:%B %-d, %Y}*")
    if notes:
        parts.append(f"**What You Need to Know:** {notes.splitlines()[0]}")
    parts.append("---")

    parts.append("### Listen")
    parts.append(f"[Listen to the full conversation]({audio_url})")
    parts.append("---")

    parts.append(f"### About {name}")
    if role:
        parts.append(f"**{role}**")
    parts.append(bio or f"{name} joined Mira for this conversation.")
    parts.append("---")

    body = "\n\n".join(notes.split("\n\n")[1:]).strip()
    if body:
        parts.append("### What we talked about")
        parts.append(body)
        parts.append("---")

    chapters = pkg.get("chapter_markers") or []
    if chapters:
        lines = []
        for ch in chapters:
            try:
                start = int(float(ch.get("start", 0)))
            except (TypeError, ValueError):
                start = 0
            lines.append(f"- **{start // 60:02d}:{start % 60:02d}** "
                         f"{str(ch.get('title', '')).strip()}")
        parts.append("### Chapters")
        parts.append("\n".join(lines))
        parts.append("---")

    links = guest_links(app)
    if links:
        parts.append(f"### Where to find {name}")
        parts.append("\n".join(f"- [{l['label']}]({l['url']})" for l in links))
        parts.append("---")

    if materials:
        parts.append("### What they wanted you to read next")
        parts.append(f"Sent by {name} when they approved this episode.")
        parts.append(_bullets(materials))
        parts.append("---")

    if transcript:
        parts.append("### Transcript")
        parts.append("The conversation as it was recorded, reviewed and "
                     f"approved by {name} before release.")
        parts.append(transcript)

    md = "\n\n".join(parts).rstrip() + "\n"
    path = (ROOT / "digests" / show.slug
            / f"{show.episode_prefix}_Ep{episode_num:03d}_{when:%Y%m%d}.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")
    logger.info("episode post written: %s (%d chars)", path.name, len(md))
    return path


def publish_one(interview_id: str) -> int:
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
    show = show_for(interview, app)

    audio_url = episode_audio(run)

    episode_num = _next_episode_number(show)
    today = dt.date.today()
    title = f"Ep{episode_num}: {app['name']} — {interview.get('episode_thesis') or show.name}"
    description = pkg.get("episode_notes") or interview.get("episode_thesis") or ""
    # The guest gave us an hour; the least the episode owes them is a working
    # link. The notes pass is asked for this block too, so only add it here if
    # the model left it out — belt and braces, because the feed and the site
    # both read this one string and a missing link cannot be fixed after the
    # episode ships.
    links_block = guest_links_markdown(app)
    if links_block:
        have = {l["url"].lower() for l in guest_links(app)}
        if not any(u in description.lower() for u in have):
            description = (description.rstrip() + "\n\n" + links_block).strip()

    # Duration + file size need the real file — fetch headers/bytes to tmp.
    with tempfile.TemporaryDirectory(prefix=f"{show.slug}_publish_") as tmp:
        local_mp3 = (Path(tmp)
                     / f"{show.episode_prefix}_Ep{episode_num:03d}_{today:%Y%m%d}.mp3")
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

        # OP3 analytics prefix. Every other show gets this from its
        # run_show/pipeline publish path; the interview shows bypass run_show, so
        # without it the feed's enclosures are unprefixed and its
        # downloads never reach api/op3_stats.json (Ep001 shipped that
        # way — its URL is deliberately left alone, since rewriting a
        # published enclosure re-downloads the episode for every
        # subscriber). New episodes are counted from here on.
        # (Uses apply_op3_prefix's default, which a drift guard pins to
        # shows/_defaults.yaml's analytics.prefix_url — this pipeline
        # deliberately doesn't load the show-config stack.)
        from engine.publisher import apply_op3_prefix, update_rss_feed
        feed_audio_url = apply_op3_prefix(audio_url)

        # Channel metadata comes from shows/<slug>.yaml publishing: via the
        # VoiceShow registry — the same values run_show would use.
        update_rss_feed(
            show.rss_path,
            episode_num, title, description, today,
            local_mp3.name, duration, local_mp3,
            audio_url=feed_audio_url,
            audio_subdir=show.audio_subdir,
            channel_title=show.name,
            channel_link=show.rss_link or show.page_url,
            channel_description=show.rss_description,
            channel_author=show.rss_author,
            channel_email=show.rss_email,
            channel_image=show.rss_image,
            channel_category=show.rss_category,
            channel_subcategory=show.rss_subcategory,
            channel_keywords=show.rss_keywords,
            guid_prefix=show.guid_prefix,
        )

    # Summaries JSON (site + dashboards read this shape network-wide).
    summaries_path = show.summaries_path
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
        "guest_links": guest_links(app),
        "chapters": pkg.get("chapter_markers") or [],
    })
    summaries_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # The episode's own post, written before the site is regenerated so the
    # generator picks it up in the same pass.
    try:
        write_episode_digest(show, episode_num, today, title,
                             interview, app, pkg, audio_url)
    except Exception:  # noqa: BLE001 — the episode still publishes
        logger.exception("episode post not written (non-fatal)")

    # Regenerate the show pages so the episode appears on the site.
    # --blogs is what turns the digest above into blog/<slug>/ep###.html and
    # refreshes the show's blog index. Without it the episode's post is
    # written and never rendered.
    subprocess.run(
        ["python", "generate_html.py", "--show", show.slug, "--blogs"],
        cwd=ROOT, check=True, timeout=1200,
    )

    sb_update("interviews", f"id=eq.{interview_id}",
              {"status": "published", "episode_number": episode_num})
    sb_update("editorial_packages", f"id=eq.{pkg['id']}",
              {"status": "published"})

    notify_operator(show.slack(
        f"Ep{episode_num} PUBLISHED: {app['name']} — RSS updated, "
        f"site regenerated. {audio_url}"
    ))
    logger.info("Published episode %d (%s)", episode_num, app["name"])
    return 0


def main() -> int:
    """``INTERVIEW_ID`` publishes one episode; without it, sweep.

    The sweep is what the scheduled workflow runs. It is idempotent —
    ``publish_one`` flips both rows to ``published``, so a second pass
    finds nothing — and one failing episode never blocks the others.
    """
    interview_id = os.environ.get("INTERVIEW_ID", "").strip()
    if interview_id:
        return publish_one(interview_id)

    pending = find_publishable()
    if not pending:
        logger.info("No episodes awaiting publish (clean no-op).")
        return 0
    logger.warning(
        "::warning::%d interview episode(s) had cleared both gates and were "
        "not published: %s", len(pending), ", ".join(pending))
    failures = 0
    for iid in pending:
        try:
            publish_one(iid)
        except Exception as exc:  # noqa: BLE001 — one bad row must not block the rest
            failures += 1
            logger.error("publish failed for %s: %s", iid, exc)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
