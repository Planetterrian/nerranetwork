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

THE GUEST'S CUTS SHIP OR NOTHING DOES (Oct 21 2026). A guest marks the
passages they want out on the review page (``editorial_packages.
guest_redaction_windows``, on the room clock) and ``assemble_edit`` cuts them
from the file it builds, recording a fingerprint of the windows it applied on
``tracks.edit.windows_hash``. ``assert_windows_applied`` refuses to publish
when the package carries windows the shipped file was not built against — a
window marked after the edit, or an edit built before the review page could
store windows at all. The remedy is the assemble workflow, never a flag.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import os
import subprocess
import tempfile
from typing import List
from pathlib import Path

import requests

import html as _html

from common import (  # noqa: E402
    ROOT, VoiceShow, logger, notify_operator, sb_select, sb_update, show_for,
    guest_links,
    guest_links_markdown,
    send_email, mira_signature_html, kits_html, x_handle,
)
from profile_photo import ensure_photo  # noqa: E402


#: The line above every published transcript (Oct 7 2026). It said "reviewed
#: and approved by <guest> before release" on all nine interview posts, which
#: is stronger than gate 2: the guest gets a week to approve, cut from or
#: refuse the transcript, and silence publishes. Same terms as
#: engine.brand.interview_provenance.
TRANSCRIPT_NOTE = (
    "The conversation as it was recorded, with any cuts the guest asked for "
    "removed. After editorial review the transcript was sent to {name} to "
    "approve, cut from or refuse before publication."
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
        if not iid or interview.get("episode_number"):
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


def episode_video(run: dict | None, pkg: dict | None) -> str:
    """The video version to publish beside the audio, or "".

    Oct 28 2026. render_video.py cuts it from the guest's camera, following
    the edit frame for frame, and records which edit it follows. It is used
    only while that edit is still the one being published (a re-assembly
    after a guest's change needs a new cut), and never when the guest asked
    for audio only on the review page."""
    if pkg and pkg.get("guest_video_ok") is False:
        return ""
    edit = ((((run or {}).get("grok_session_log") or {}).get("tracks") or {})
            .get("edit") or {})
    url = str(edit.get("video_url") or "").strip()
    if not url or str(edit.get("video_of") or "") != str(edit.get("url") or ""):
        return ""
    return url


def episode_shorts(run: dict | None, pkg: dict | None) -> list:
    """The vertical Shorts cut from this edit (``[{"url", "start",
    "seconds", "title"}]``), or [] (Oct 28 2026). Same rules as the long
    form: never for a guest who asked for audio only, and only while the
    edit they were cut from is the one being published."""
    if pkg and pkg.get("guest_video_ok") is False:
        return []
    edit = ((((run or {}).get("grok_session_log") or {}).get("tracks") or {})
            .get("edit") or {})
    if not edit.get("url") or str(edit.get("shorts_of") or "") != str(edit.get("url")):
        return []
    return [s for s in edit.get("shorts") or []
            if isinstance(s, dict) and str(s.get("url") or "").startswith("http")]


#: X takes a video of up to 140 seconds on any account.
X_CLIP_MAX_SEC = 140.0
X_CLIP_DEFAULT_SEC = 60.0


def x_clip_window(pkg: dict, run: dict | None) -> tuple | None:
    """``(start, seconds)`` on the published file of the moment to post on X:
    the first clip suggestion, moved from the room's clock to the edit's."""
    clips = [c for c in (pkg.get("clip_suggestions") or [])
             if isinstance(c, dict) and c.get("start") is not None]
    if not clips:
        return None
    clip = clips[0]
    start, end = float(clip["start"]), clip.get("end")
    clock = ((((run or {}).get("grok_session_log") or {}).get("tracks") or {})
             .get("edit") or {}).get("clock")
    if clock:
        from edit_transcript import room_to_edit
        moved = room_to_edit(clock, start)
        moved_end = room_to_edit(clock, float(end)) if end is not None else None
        if moved is None:
            return None
        length = (moved_end - moved) if moved_end and moved_end > moved else X_CLIP_DEFAULT_SEC
        start = moved
    else:
        length = (float(end) - start) if end is not None and float(end) > start else X_CLIP_DEFAULT_SEC
    return max(0.0, start), min(X_CLIP_MAX_SEC, max(10.0, length))


def x_video_clip(video_url: str, window: tuple, out: Path) -> Path | None:
    """Cut the X clip from the video version (re-encoded, so it starts on
    the exact frame). Best-effort: None means a text post."""
    start, seconds = window
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-i", video_url,
                        "-t", f"{seconds:.2f}", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                        "-movflags", "+faststart", str(out)],
                       check=True, capture_output=True, timeout=900)
    except Exception:  # noqa: BLE001
        logger.exception("X clip not cut (non-fatal)")
        return None
    return out if out.exists() and out.stat().st_size > 10_000 else None


def assert_windows_applied(pkg: dict, run: dict) -> None:
    """Refuse to ship audio the guest's marked cuts were not applied to."""
    from edit_transcript import normalise_windows, windows_hash
    windows = normalise_windows((pkg or {}).get("guest_redaction_windows"))
    if not windows:
        return
    edit = ((run.get("grok_session_log") or {}).get("tracks") or {}).get("edit") or {}
    built_against = str(edit.get("windows_hash") or "")
    wanted = windows_hash(windows)
    if built_against == wanted:
        return
    why = (f"the guest marked {len(windows)} passage(s) to cut and the assembled "
           f"file was built against {'none of them' if not built_against else 'a different set'}"
           " — run the assemble workflow for this interview, then publish")
    try:
        notify_operator(f"Publish refused: {why}", critical=True)
    except Exception:  # noqa: BLE001
        logger.exception("could not notify the operator")
    raise RuntimeError(f"refusing to publish: {why}")


def _bullets(text: str) -> str:
    """Free text from a guest, as markdown that keeps their own links."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip().lstrip("-*\u2022 ").strip()
        if line:
            out.append(f"- {line}")
    return "\n".join(out)


def on_the_edit_clock(pkg: dict, run: dict | None) -> dict:
    """The package with its chapter marks moved from the room's clock to the
    published file's (Oct 27 2026, Glenn Broder: written on the room's clock,
    every mark of his would have pointed up to three minutes late). The
    assembler records the clock beside the edit it built; without one the
    marks stand as written."""
    clock = ((((run or {}).get("grok_session_log") or {}).get("tracks") or {})
             .get("edit") or {}).get("clock")
    chapters = pkg.get("chapter_markers")
    if not clock or not chapters:
        return pkg
    from edit_transcript import chapters_on_edit_clock
    moved = chapters_on_edit_clock(chapters, clock)
    logger.info("chapters on the edit's clock: %s",
                [(c.get("start"), c.get("title")) for c in moved])
    return {**pkg, "chapter_markers": moved}


def vouched_chapters(pkg: dict) -> list:
    """The package's chapter markers that its own transcript can vouch for.

    Oct 9 2026. The Sep 22 pass removed three fabricated chapter lists (a
    film studio banning AI storyboards, on episodes whose guests never
    mentioned one) from the committed record and gated the PAGE through
    ``engine.interviews.supported_chapters`` — but the lists stayed in
    ``editorial_packages.chapter_markers``, and a re-publish of Ep7 on Oct 8
    wrote the storyboard list straight back into its digest, which turned
    main red on the guard. The gate now runs where the record is written:
    the transcript vouches for the list, or there is no list.
    """
    from engine.interviews import supported_chapters
    return supported_chapters(pkg.get("chapter_markers") or [],
                              (pkg.get("transcript_cleaned") or "").strip())


def notes_lede(notes: str) -> str:
    """The first line of the episode notes that says something.

    The notes pass sometimes opens on a bare heading ("Episode Summary",
    "## Summary"), and the post printed it as the episode's one-line
    summary (Oct 2026). Headings, label-only lines and blanks are skipped.
    """
    for line in (notes or "").splitlines():
        s = line.strip().lstrip("#").strip().strip("*").strip()
        if not s:
            continue
        if len(s.split()) <= 3 and not re.search(r"[.!?]$", s):
            continue  # a heading or a label, not a sentence
        return s
    return ""


def interview_episode_title(episode_num: int, guest: str, thesis: str) -> str:
    """``Ep<n>: <guest> — <thesis>``, guaranteed to fit the feed's title cap.

    The thesis is a full sentence and Ep5–Ep11 shipped 220–254-character
    titles that Apple, Spotify and YouTube (which ingests the feed) each
    cut mid-word. The label and the guest's name are kept whole; only the
    thesis is clipped, at a word boundary, by ``engine.titles``.
    """
    from engine.titles import PODCAST_EPISODE_TITLE_MAX, clip_words

    label = f"Ep{episode_num}: {(guest or '').strip()}"
    thesis = (thesis or "").strip()
    if not thesis:
        return clip_words(label, PODCAST_EPISODE_TITLE_MAX)
    room = PODCAST_EPISODE_TITLE_MAX - len(label) - len(" — ")
    if room < 20:
        return clip_words(label, PODCAST_EPISODE_TITLE_MAX)
    return f"{label} — {clip_words(thesis, room)}"


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
    lede = notes_lede(notes)
    if lede:
        parts.append(f"**What You Need to Know:** {lede}")
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
    # The notes pass ends with a "Find <name>:" block of bare URLs for the
    # feed. The post has its own "Where to find" section with real links,
    # and the bare copy rendered as plain text above it (Adrian Wolfberg's
    # page, Sept 18 2026), so it is dropped here.
    body = re.sub(r"\n+Find [^\n]*:\n(?:[^\n]*https?://[^\n]*\n?)+\s*$", "", body).strip()
    if body:
        parts.append("### What we talked about")
        parts.append(body)
        parts.append("---")

    chapters = vouched_chapters(pkg)
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
        # The review form keeps materials whatever the guest decided, so the
        # line says where they came from, not that the guest approved.
        parts.append(f"Sent by {name} with their transcript review.")
        parts.append(_bullets(materials))
        parts.append("---")

    if transcript:
        parts.append("### Transcript")
        # Gate 2 as built (engine.brand.interview_provenance): the guest is
        # SENT the transcript to approve, cut from or refuse, and seven days
        # of silence also publishes — so this never says "approved by".
        parts.append(TRANSCRIPT_NOTE.format(name=name))
        parts.append(transcript)

    md = "\n\n".join(parts).rstrip() + "\n"
    path = (ROOT / "digests" / show.slug
            / f"{show.episode_prefix}_Ep{episode_num:03d}_{when:%Y%m%d}.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")
    logger.info("episode post written: %s (%d chars)", path.name, len(md))
    return path


RETURN_AFTER_MONTHS = 3   # "would you come back": a date, not a sentiment


def return_month(when: dt.date, months: int = RETURN_AFTER_MONTHS) -> str:
    """``"January 2027"``: the month the guest is invited back for."""
    m = when.month - 1 + months
    year = when.year + m // 12
    return dt.date(year, m % 12 + 1, 1).strftime("%B %Y")


def clip_link(pkg: dict, show: VoiceShow, episode_num: int) -> tuple:
    """``(url, title)`` of a 60-second moment the guest can share: the first
    clip suggestion, as a deep link into the YouTube upload when the publish
    recorded one, else into the episode's post with a ``#t=`` offset."""
    clips = pkg.get("clip_suggestions") or []
    clip = next((c for c in clips if isinstance(c, dict) and c.get("start") is not None), None)
    if clip is None:
        return "", ""
    start = max(0, int(float(clip["start"])))
    title = str(clip.get("title") or "").strip()
    index = ROOT / show.audio_subdir / "youtube_videos.json"
    try:
        for v in (json.loads(index.read_text(encoding="utf-8")).get("videos") or []):
            if isinstance(v, dict) and v.get("episode") == episode_num and v.get("video_id"):
                return f"https://www.youtube.com/watch?v={v['video_id']}&t={start}s", title
    except (OSError, ValueError):
        pass
    return f"{show.post_url(episode_num)}#t={start}", title


def share_card_link(show: VoiceShow, episode_num: int) -> str:
    try:
        from engine.share_cards import episode_card_url
        return episode_card_url(ROOT / show.audio_subdir, episode_num) or ""
    except Exception:  # noqa: BLE001
        return ""


def published_email(show: VoiceShow, app: dict, pkg: dict,
                    episode_num: int, when: dt.date | None = None) -> tuple:
    """Subject and body of the note the guest gets when their episode is out.

    Sept 20 2026. John Capobianco's team asked twice where the episode would
    live and what to share, and the answer was written by hand after the
    publish. The guest gave an hour; the least the publish owes them is the
    link, the same day, with every link they gave us shown back to them so
    they can see it landed. Their publicist, if they have one, is copied.
    """
    from engine import brand as _brand
    e = _html.escape
    name = str(app.get("name") or "").strip()
    first = name.split()[0] if name else "there"
    post = show.post_url(episode_num)
    links = guest_links(app)
    materials = [ln.strip().lstrip("-*• ").strip()
                 for ln in str(pkg.get("guest_materials") or "").splitlines()
                 if ln.strip()]

    def link(url: str) -> str:
        return f'<a href="{e(url)}">{e(url)}</a>'

    where = [f"the show page, {link(show.page_url)}"]
    if show.apple_url:
        where.append(f"Apple Podcasts, {link(show.apple_url)}")
    if show.spotify_url:
        where.append(f"Spotify, {link(show.spotify_url)}")
    where_txt = (", ".join(where[:-1]) + " and " + where[-1]) if len(where) > 1 else where[0]

    parts = [
        f"<p>Hi {e(first)},</p>",
        f"<p>Your episode is out. It is Episode {int(episode_num)} of {e(show.name)}, "
        f"and the post with the player, the transcript and your links is here:</p>",
        f"<p>{link(post)}</p>",
        "<p>If that page is not there the moment you click, give it a few "
        "minutes; it goes up with the site build that follows this note.</p>",
        f"<p>It is also in the podcast feed, so it is on {where_txt}, "
        f"as the apps pick it up over the next day or so.</p>",
    ]
    if links:
        parts.append("<p>Where to find you, as it appears on the post:</p><ul>"
                     + "".join(f"<li>{e(l['label'])}: {link(l['url'])}</li>" for l in links)
                     + "</ul>")
    if materials:
        parts.append("<p>And the reading you asked us to point people at:</p><ul>"
                     + "".join(f"<li>{_md_link_html(m)}</li>" for m in materials)
                     + "</ul>")
    # Oct 21 2026: what a guest tells people about is the thing they can
    # share in one tap. A sixty-second moment, the card, and a date.
    clip_url, clip_title = clip_link(pkg, show, episode_num)
    if clip_url:
        parts.append("<p>A short moment to share, if you want one"
                     + (f" — <em>{e(clip_title)}</em>" if clip_title else "")
                     + f": {link(clip_url)}</p>")
    card = share_card_link(show, episode_num)
    if card:
        parts.append(f"<p>The episode's share card, for a post of your own: {link(card)}</p>")
    month = return_month(when or dt.date.today())
    parts += [
        "<p>If anything on the page is wrong, a link, a title, a spelling, "
        "reply to this and I'll have it fixed the same day. If you post about it, "
        "send me the link and I'll share it on. The network is "
        f"{link(show.base_url)} and @planetterrian on X if you want to tag it.</p>",
        f"<p>And I would like you back. I have put {e(month)} in the calendar for a "
        "second conversation, when there will be something to measure the first "
        "one against; reply with a yes and I'll send the booking link nearer the "
        "time.</p>",
        # Oct 21 2026 (operator): the two kits, last and in one paragraph.
        # The media kit is what a guest's publicist asks for next; the
        # sponsorship kit is an offer, never a pitch, and the interview
        # shows themselves carry no sponsor. Oct 24 2026: the same words
        # as every other guest mail (engine.brand.KITS_COPY, "share").
        kits_html("share", show),
        "<p>Thank you again for the conversation.</p>",
        mira_signature_html(show),
    ]
    subject = f"Your {show.short_label} episode is live: Ep{int(episode_num)}"
    return subject, "".join(parts)


def _md_link_html(line: str) -> str:
    """One guest-materials line, ``[label](url)`` or a bare URL, as HTML."""
    e = _html.escape
    m = re.match(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", line.strip())
    if m:
        return f'{e(m.group(1))}: <a href="{e(m.group(2))}">{e(m.group(2))}</a>'
    return re.sub(r"(https?://[^\s<>\"')\]]+)",
                  lambda u: f'<a href="{e(u.group(1))}">{e(u.group(1))}</a>',
                  e(line))


def fill_social_links(pkg: dict, url: str) -> None:
    """Put the episode's address into the package's launch copy, where the
    social pass wrote {episode_url} (Oct 27 2026). Never raises."""
    try:
        copy = pkg.get("social_copy")
        if not isinstance(copy, dict) or not url:
            return
        filled = {k: (str(v).replace("{episode_url}", url) if isinstance(v, str) else v)
                  for k, v in copy.items()}
        if filled != copy:
            sb_update("editorial_packages", f"id=eq.{pkg['id']}", {"social_copy": filled})
    except Exception:  # noqa: BLE001 — the episode is out either way
        logger.exception("social copy links not filled (non-fatal)")


def tell_the_guest(show: VoiceShow, app: dict, pkg: dict, episode_num: int) -> None:
    """Send :func:`published_email` once; a failure never unpublishes anything."""
    if pkg.get("publish_package_sent_at"):
        logger.info("publish-day note already sent %s", pkg["publish_package_sent_at"])
        return
    subject, body = published_email(show, app, pkg, episode_num)
    to = str(app.get("email") or "").strip()
    cc = [str(app.get("publicist_email") or "").strip()]
    try:
        send_email(to, subject, body, cc_operator=True, cc=cc)
        try:
            sb_update("editorial_packages", f"id=eq.{pkg['id']}",
                      {"publish_package_sent_at":
                       dt.datetime.now(dt.timezone.utc).isoformat()})
        except Exception:  # noqa: BLE001
            logger.exception("publish_package_sent_at not stamped (non-fatal)")
    except Exception:  # noqa: BLE001 — the episode is out; the note can be resent
        logger.exception("published email to %s not sent", to)
        notify_operator(show.slack(
            f"Ep{episode_num} is out but the guest email to {to} failed; "
            f"send them {show.post_url(episode_num)} by hand"))


def publish_one(interview_id: str) -> int:
    interview = sb_select("interviews", f"id=eq.{interview_id}")[0]
    if interview.get("status") != "approved":
        raise RuntimeError(
            f"interview {interview_id} is {interview.get('status')!r} — "
            "publish requires status 'approved' (both gates cleared + produced)"
        )
    # Oct 8 2026: a number means it went out already, whatever the status
    # says (a late produce step once wrote "approved" back over "published").
    if interview.get("episode_number"):
        raise RuntimeError(
            f"interview {interview_id} was already published as "
            f"Ep{interview['episode_number']}; use refresh_post to update it")
    app = sb_select("guest_applications",
                    f"id=eq.{interview['application_id']}")[0]
    pkg = sb_select("editorial_packages",
                    f"interview_id=eq.{interview_id}"
                    f"&status=eq.approved_by_guest")[0]
    run = sb_select("interview_runs",
                    f"id=eq.{pkg['interview_run_id']}")[0]
    pkg = on_the_edit_clock(pkg, run)
    show = show_for(interview, app)

    assert_windows_applied(pkg, run)
    audio_url = episode_audio(run)

    episode_num = _next_episode_number(show)
    today = dt.date.today()
    title = interview_episode_title(episode_num, app["name"],
                                    interview.get("episode_thesis") or show.name)
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
            # Item <link> = the episode page podcast apps open as "episode
            # website" (run_show has passed it since Sep 4 2026; this path
            # bypasses run_show and kept the MP3 — Oct 8 2026 review).
            episode_page_url=(
                f"https://nerranetwork.com/blog/{show.slug}/ep{episode_num:03d}.html"),
        )

    # Oct 25 2026: the photo from the guest's public profile, beside their
    # name on the post. Found when the application was screened; looked for
    # once more here if it was not. Never stops the publish.
    photo = ensure_photo(app) or ""
    video = episode_video(run, pkg)

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
        "guest_photo": photo,
        "chapters": vouched_chapters(pkg),
        # Oct 28 2026: the video version, played on the episode's page.
        **({"video_url": video} if video else {}),
    })
    summaries_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # The episode's own post, written before the site is regenerated so the
    # generator picks it up in the same pass.
    digest_path = None
    try:
        digest_path = write_episode_digest(show, episode_num, today, title,
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

    # Distribution beyond the feed, gated on the show's own YAML and strictly
    # after the episode is recorded as published: the audio in the feed is the
    # product, and a failed email or upload must never cost the episode or
    # make the sweep re-publish it.
    cfg = _show_config(show)
    maybe_send_newsletter(show, cfg, episode_num, today,
                          interview.get("episode_thesis") or "",
                          digest_path)
    long_id = maybe_publish_youtube(show, cfg, episode_num, today, title, description,
                                    audio_url, app.get("name") or "", video_url=video)
    shorts = episode_shorts(run, pkg)
    maybe_publish_shorts(show, cfg, episode_num, today, shorts,
                         app.get("name") or "", long_video_id=long_id or "")
    maybe_post_x(show, cfg, episode_num, title, mention=x_handle(app),
                 video_url=video, clip=x_clip_window(pkg, run) if video else None,
                 short_url=shorts[0]["url"] if shorts else "")

    notify_operator(show.slack(
        f"Ep{episode_num} PUBLISHED: {app['name']} — RSS updated, "
        f"site regenerated. {audio_url}"
    ))
    logger.info("Published episode %d (%s)", episode_num, app["name"])
    # The site is regenerated in this run but the workflow commits and
    # deploys it after this script returns, so the page may lag the email by
    # a few minutes. The link is right; the guest will not race it.
    tell_the_guest(show, app, pkg, episode_num)
    fill_social_links(pkg, show.post_url(episode_num))
    return 0


# ---------------------------------------------------------------------------
# Distribution beyond RSS (Sep 2026)
# ---------------------------------------------------------------------------
#
# The interview shows bypass ``run_show.py``, which is where every other show's
# newsletter send and YouTube upload live. So ``newsletter.enabled`` and
# ``youtube.enabled`` in shows/age_of_ai.yaml were read by NOTHING: flipping
# them looked like enabling distribution and did nothing at all. That is the
# same class as the OP3-prefix hole above — a show that skips run_show gets
# none of run_show's publish surface unless this file asks for it.
#
# Both paths below are BEST-EFFORT and gated on the show's own YAML, so:
#   * the flags the operator flips are the flags the code reads;
#   * a failure can never unpublish or block an episode that is already in the
#     feed (the audio is the product);
#   * a show with the flags off is byte-identical to before.


def _show_config(show: VoiceShow):
    """The show's full ShowConfig, or ``None`` if it cannot be loaded.

    This pipeline deliberately does not load the show-config stack for its
    core path — the VoiceShow registry is thinner and enough for RSS. It is
    loaded here so that the distribution flags have exactly one home: the
    show YAML every other show is configured from.
    """
    try:
        from engine.config import load_config
        return load_config(ROOT / "shows" / f"{show.slug}.yaml")
    except Exception:  # noqa: BLE001 — distribution is optional, publishing is not
        logger.exception("could not load shows/%s.yaml (distribution skipped)",
                         show.slug)
        return None


def maybe_send_newsletter(show: VoiceShow, cfg, episode_num: int,
                          when: dt.date, hook: str, digest_path: Path) -> None:
    """Email the episode to the show's subscribers, if the show enables it.

    Reuses ``engine.newsletter.send_show_newsletter`` — the same function every
    other show uses — so the interview shows get the scaffold sanitizer, the
    contrast check, the subject-line builder and the 20-hour double-send guard
    without a second implementation. The digest written moments ago is the
    body, which is why this runs after :func:`write_episode_digest`.
    """
    if cfg is None or not getattr(getattr(cfg, "newsletter", None), "enabled", False):
        return
    if not digest_path or not digest_path.exists():
        logger.warning("::warning::newsletter skipped for %s Ep%d: no digest at %s",
                       show.slug, episode_num, digest_path)
        return
    try:
        from engine.newsletter import send_show_newsletter
        email_id = send_show_newsletter(
            digest_path.read_text(encoding="utf-8"),
            cfg,
            episode_num,
            when.isoformat(),
            hook=hook,
        )
        if email_id:
            logger.info("Newsletter sent for %s Ep%d (%s)",
                        show.slug, episode_num, email_id)
        else:
            logger.info("Newsletter not sent for %s Ep%d "
                        "(not configured, or a guard declined)",
                        show.slug, episode_num)
    except Exception:  # noqa: BLE001 — the episode is already published
        logger.exception("newsletter failed for %s Ep%d (non-fatal)",
                         show.slug, episode_num)


def maybe_post_x(show: VoiceShow, cfg, episode_num: int, title: str,
                 mention: str = "", video_url: str = "",
                 clip: tuple | None = None, short_url: str = "") -> None:
    """Post the episode's title and page link to X, if the show enables it.

    Oct 9 2026: ``publishing.x_enabled`` / ``x_env_prefix`` on the show YAML
    were read by nothing here — the interview shows bypass run_show, where
    every other show's X post lives (the same hole the newsletter and
    YouTube flags had until Sep 20). ``engine.x_post`` reads the four
    ``<prefix>*`` credentials; unset is a logged skip, never a failure.

    Oct 25 2026: ``mention`` is the guest's X handle from their application
    (the form tells them their account is tagged when the episode posts).
    """
    pub = getattr(cfg, "publishing", None) if cfg is not None else None
    if pub is None or not getattr(pub, "x_enabled", False):
        return
    try:
        from engine.funnel import PLACEMENT_BODY, SOURCE_X, episode_link
        from engine.x_post import post_teaser
        link = episode_link(show.post_url(episode_num), show.slug, episode_num,
                            kind="episode", placement=PLACEMENT_BODY,
                            source=SOURCE_X)
        label = f"{show.name} Ep{episode_num}"
        env_prefix = getattr(pub, "x_env_prefix", "") or ""
        posted, reason = False, ""
        # Oct 28 2026: with a video version, the post carries a moment of it:
        # the first vertical Short (captioned, made for a phone) when one was
        # cut, else the same moment cut from the long form.
        if short_url or (video_url and clip):
            from engine.x_post import post_media, teaser_text
            with tempfile.TemporaryDirectory(prefix=f"{show.slug}_x_") as tmp:
                cut = (_download(short_url, Path(tmp) / "short.mp4") if short_url else None)
                if cut is None and video_url and clip:
                    cut = x_video_clip(video_url, clip, Path(tmp) / "moment.mp4")
                if cut is not None:
                    posted, reason, _url, _used = post_media(
                        env_prefix=env_prefix, text=teaser_text(title, link, mention),
                        media_paths=[cut], label=label)
        if not posted and reason != "no_media":
            posted, reason = post_teaser(
                env_prefix=env_prefix, title=title, link=link, label=label,
                mention=mention,
            )
        if not posted:
            logger.warning("::warning::X post for %s Ep%d did not go out (%s)",
                           show.slug, episode_num, reason)
    except Exception:  # noqa: BLE001 — the episode is already published
        logger.exception("X post failed for %s Ep%d (non-fatal)", show.slug, episode_num)


def waveform_video_url(audio_url: str) -> str:
    """Where the produce step put this episode's waveform MP4.

    ``produce_episode.py`` renders ``<name>.mp4`` beside ``<name>.mp3`` and
    uploads them to ``show.r2_key(name)`` and ``show.r2_key("video", name)``
    respectively — but it only ever put the video URL in an email, so there is
    no row to read it from. The key convention is the contract, so the URL is
    derived from the audio URL and then HEAD-checked: the video is best-effort
    in produce too, and an episode with no video must simply skip YouTube.
    """
    if not audio_url.endswith(".mp3"):
        return ""
    head, _, filename = audio_url.rpartition("/")
    if not head or not filename:
        return ""
    return f"{head}/video/{filename[:-4]}.mp4"


def render_episode_video(show: VoiceShow, audio_url: str, out: Path,
                         guest_name: str) -> "Path | None":
    """Download the published MP3 and render the waveform MP4 beside it.

    Same renderer and cover the produce step uses
    (``audio.waveform_video.render``). Best-effort: any failure logs a
    ``::warning::`` and returns None, so YouTube is skipped and the episode
    — already in the feed — is untouched.
    """
    try:
        from audio.waveform_video import render as render_waveform

        mp3 = out.with_suffix(".mp3")
        with requests.get(audio_url, stream=True, timeout=1800) as resp:
            resp.raise_for_status()
            with mp3.open("wb") as fh:
                for chunk in resp.iter_content(1 << 16):
                    fh.write(chunk)
        cover = show.cover_path
        return render_waveform(
            mp3, out,
            cover_image=cover if cover.exists() else None,
            title=f"{guest_name} — {show.name}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("::warning::YouTube skipped for %s: waveform render "
                       "failed (%s)", show.slug, exc)
        return None


def maybe_publish_youtube(show: VoiceShow, cfg, episode_num: int, when: dt.date,
                          title: str, description: str, audio_url: str,
                          guest_name: str, video_url: str = "") -> str:
    """Upload the episode's waveform video to YouTube, if the show enables it.

    Deliberately minimal: one long-form upload of the video the produce step
    already rendered and paid for. No Shorts, no dubs, no adaptive-policy tier
    — those live in run_show's YouTube stage and porting them is a much larger
    job than this show needs to have a video presence. The upload is recorded
    in ``digests/<slug>/youtube_videos.json``, which is the file the analytics
    fetcher, the adaptive policy and the subscriber tracker already glob, so
    the episode shows up in the feedback loop without any further wiring.
    """
    if cfg is None or not getattr(getattr(cfg, "youtube", None), "enabled", False):
        return ""
    yt = cfg.youtube
    # Oct 28 2026: the video version (the guest beside Mira) when there is
    # one for this edit; else the waveform video, as before.
    video_url = video_url or waveform_video_url(audio_url)
    # Oct 11 2026: render here when the produce step left no video. The
    # edit path (assemble_edit — every ``_edit_`` episode, Ep5 onward)
    # never renders one, so the derived URL 404'd on every publish and the
    # show had uploaded NOTHING since YouTube was switched on (Sep 20): no
    # digests/age_of_ai/youtube_videos.json exists.
    render_locally = not video_url
    if video_url:
        try:
            probe = requests.head(video_url, timeout=60, allow_redirects=True)
            if probe.status_code != 200:
                logger.warning("No waveform video at %s (HTTP %s) — rendering "
                               "one from the episode audio", video_url,
                               probe.status_code)
                render_locally = True
        except Exception:  # noqa: BLE001
            logger.warning("HEAD %s failed — rendering the waveform video "
                           "from the episode audio", video_url)
            render_locally = True

    try:
        from engine.funnel import PLACEMENT_DESCRIPTION, episode_link
        from engine.youtube import (
            add_video_to_playlist, get_channel_credentials_from_env,
            upload_video,
        )
        from engine.utils import strip_speech_tags

        credentials = get_channel_credentials_from_env(
            getattr(yt, "channel", "en") or "en")
        if credentials is None:
            logger.warning("::warning::YouTube skipped for %s Ep%d: no channel "
                           "credentials in the environment", show.slug, episode_num)
            return ""

        # show.page_url is already absolute (shows.py builds it from the
        # registry). Every published link goes through engine.funnel — see
        # the standing rule at the top of CLAUDE.md.
        page = episode_link(
            show.page_url, show.slug, episode_num, kind="long",
            placement=PLACEMENT_DESCRIPTION,
        )
        body = strip_speech_tags(description or "").strip()
        full_description = "\n\n".join(x for x in (
            body,
            f"Full episode, transcript and every other show: {page}",
            f"{cfg.name} is hosted by Mira, an AI. Every episode says so, and "
            "every guest is sent their own transcript to approve, cut from or "
            "refuse before it is published.",
        ) if x)

        with tempfile.TemporaryDirectory(prefix=f"{show.slug}_yt_") as tmp:
            local = Path(tmp) / f"{show.episode_prefix}_Ep{episode_num:03d}.mp4"
            if render_locally:
                local = render_episode_video(show, audio_url, local, guest_name)
                if local is None:
                    return ""
            else:
                with requests.get(video_url, stream=True, timeout=1800) as resp:
                    resp.raise_for_status()
                    with local.open("wb") as fh:
                        for chunk in resp.iter_content(1 << 16):
                            fh.write(chunk)
            result = upload_video(
                local,
                credentials=credentials,
                title=title,
                description=full_description,
                tags=list(getattr(yt, "tags", None) or [])[:15],
                category_id=int(getattr(yt, "category_id", 24) or 24),
                privacy_status=getattr(yt, "privacy_status", "public") or "public",
                contains_synthetic_media=True,
            )
        video_id = getattr(result, "video_id", "") or ""
        if not video_id:
            logger.warning("::warning::YouTube upload returned no video id for "
                           "%s Ep%d", show.slug, episode_num)
            return ""
        playlist = getattr(yt, "podcast_playlist_id", "") or ""
        if playlist:
            try:
                add_video_to_playlist(video_id, playlist, credentials=credentials)
            except Exception:  # noqa: BLE001 — the video is up either way
                logger.exception("playlist add failed for %s (non-fatal)", video_id)
        _record_youtube_video(show, episode_num, when, title, video_id,
                              guest_name, getattr(yt, "channel", "en") or "en")
        logger.info("YouTube: %s Ep%d uploaded as %s",
                    show.slug, episode_num, video_id)
        return video_id
    except Exception:  # noqa: BLE001 — the episode is already published
        logger.exception("YouTube upload failed for %s Ep%d (non-fatal)",
                         show.slug, episode_num)
        return ""


def _download(url: str, dest: Path) -> "Path | None":
    """``url`` saved at ``dest``, or None."""
    try:
        with requests.get(url, stream=True, timeout=1800) as resp:
            resp.raise_for_status()
            with dest.open("wb") as fh:
                for chunk in resp.iter_content(1 << 16):
                    fh.write(chunk)
    except Exception:  # noqa: BLE001 — every caller has a way on without it
        logger.exception("could not fetch %s", url)
        return None
    return dest if dest.exists() and dest.stat().st_size > 10_000 else None


def short_title(short: dict, guest_name: str, show_name: str) -> str:
    """A Short's YouTube title: its moment's headline (else the guest's
    name and the show's), with ``#Shorts``, inside the title limit
    (engine.titles owns it)."""
    from engine.titles import YOUTUBE_TITLE_MAX, clip_words
    head = str(short.get("title") or "").strip() or f"{guest_name} on {show_name}"
    return f"{clip_words(head, YOUTUBE_TITLE_MAX - len(' #Shorts'))} #Shorts"


def maybe_publish_shorts(show: VoiceShow, cfg, episode_num: int, when: dt.date,
                         shorts: list, guest_name: str, long_video_id: str = "") -> int:
    """Upload the episode's vertical Shorts (Oct 28 2026), if the show
    enables YouTube. The first goes public now; the rest are scheduled at the
    channel's next Shorts slots (engine.shorts_stagger, the network's own
    rule), so one episode's moments spread through the day. Each links the
    full conversation and says the host is an AI. Recorded as ``kind:
    short`` in the video index. Returns how many went up; never raises."""
    if not shorts or cfg is None or not getattr(getattr(cfg, "youtube", None), "enabled", False):
        return 0
    yt = cfg.youtube
    done = 0
    try:
        from engine.funnel import PLACEMENT_DESCRIPTION, episode_link
        from engine.shorts_stagger import resolve_slot_hours, stagger_publish_times
        from engine.youtube import get_channel_credentials_from_env, upload_video
        channel = getattr(yt, "channel", "en") or "en"
        credentials = get_channel_credentials_from_env(channel)
        if credentials is None:
            logger.warning("::warning::Shorts skipped for %s Ep%d: no channel "
                           "credentials in the environment", show.slug, episode_num)
            return 0
        page = episode_link(show.page_url, show.slug, episode_num, kind="short",
                            placement=PLACEMENT_DESCRIPTION)
        later = stagger_publish_times(dt.datetime.now(dt.timezone.utc), len(shorts) - 1,
                                      slot_hours=resolve_slot_hours(yt, channel))
        full = (f"https://www.youtube.com/watch?v={long_video_id}" if long_video_id else page)
        with tempfile.TemporaryDirectory(prefix=f"{show.slug}_shorts_") as tmp:
            for k, short in enumerate(shorts):
                try:
                    local = _download(short["url"], Path(tmp) / f"short{k + 1}.mp4")
                    if local is None:
                        continue
                    title = short_title(short, guest_name, cfg.name)
                    description = "\n\n".join((
                        f"{guest_name} on {cfg.name}, episode {episode_num}.",
                        f"The full conversation: {full}",
                        f"Every show: {page}",
                        f"{cfg.name} is hosted by Mira, an AI. Every guest approves "
                        "their own transcript before it is published.",
                        "#Shorts #AI #podcast",
                    ))
                    result = upload_video(
                        local, credentials=credentials, title=title,
                        description=description,
                        tags=list(getattr(yt, "tags", None) or [])[:15],
                        category_id=int(getattr(yt, "category_id", 24) or 24),
                        privacy_status="private" if k else
                        (getattr(yt, "privacy_status", "public") or "public"),
                        contains_synthetic_media=True,
                        publish_at=later[k - 1] if k else None,
                    )
                    video_id = getattr(result, "video_id", "") or ""
                    if not video_id:
                        continue
                    when_public = (later[k - 1].date() if k else when)
                    _record_youtube_video(show, episode_num, when_public, title, video_id,
                                          guest_name, channel, kind="short")
                    done += 1
                    logger.info("YouTube Short %d for %s Ep%d: %s%s", k + 1, show.slug,
                                episode_num, video_id,
                                f" (public {later[k - 1]:%Y-%m-%d %H:%M} UTC)" if k else "")
                except Exception:  # noqa: BLE001 — one Short never stops the next
                    logger.exception("Short %d failed for %s Ep%d (non-fatal)",
                                     k + 1, show.slug, episode_num)
    except Exception:  # noqa: BLE001 — the episode is already published
        logger.exception("Shorts failed for %s Ep%d (non-fatal)", show.slug, episode_num)
    return done


def _record_youtube_video(show: VoiceShow, episode_num: int, when: dt.date,
                          title: str, video_id: str, guest_name: str,
                          channel: str, kind: str = "long") -> None:
    """Append to the per-show video index the rest of the network already reads."""
    index = ROOT / show.audio_subdir / "youtube_videos.json"
    data = {"schema_version": 2, "videos": []}
    if index.exists():
        try:
            data = json.loads(index.read_text(encoding="utf-8")) or data
        except json.JSONDecodeError:
            logger.warning("::warning::%s is not valid JSON — starting a new index",
                           index)
    videos = data.setdefault("videos", [])
    if any(v.get("video_id") == video_id for v in videos if isinstance(v, dict)):
        return
    videos.append({
        "video_id": video_id,
        "show_slug": show.slug,
        "episode": episode_num,
        "kind": kind,
        "title": title,
        "hook": guest_name,
        "published": when.isoformat(),
        "watch_url": f"https://www.youtube.com/watch?v={video_id}",
        "channel": channel,
    })
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                     encoding="utf-8")


def refresh_post(interview_id: str) -> int:
    """Rewrite a PUBLISHED episode's post and site pages from the package as
    it is now, keeping its episode number, date and audio.

    Sept 17 2026: Dan Perra's page went out with half a transcript (the
    cleaning pass was capped) and no post (the post-writer came after his
    publish). Running publish again is refused — and would hand him a new
    episode number and a duplicate feed entry, which is how Ep2 was once
    published twice. This touches the digest and the generated pages only:
    nothing is uploaded, the RSS feed is left alone, no row changes state.
    """
    interview = sb_select("interviews", f"id=eq.{interview_id}")[0]
    if interview.get("status") != "published":
        raise RuntimeError(
            f"interview {interview_id} is {interview.get('status')!r} — "
            "refresh is for episodes that are already published")
    app = sb_select("guest_applications",
                    f"id=eq.{interview['application_id']}")[0]
    pkg = sb_select("editorial_packages",
                    f"interview_id=eq.{interview_id}&status=eq.published"
                    "&order=created_at.desc&limit=1")[0]
    runs = sb_select("interview_runs", f"id=eq.{pkg.get('interview_run_id')}")
    pkg = on_the_edit_clock(pkg, runs[0] if runs else None)
    show = show_for(interview, app)
    episode_num = int(interview.get("episode_number") or 0)
    data = {"episodes": []}
    if show.summaries_path.exists():
        data = json.loads(show.summaries_path.read_text(encoding="utf-8")) or {}
    entry = next((e for e in (data.get("episodes") or [])
                  if int(e.get("episode") or 0) == episode_num), None)
    if not episode_num or entry is None:
        raise RuntimeError(f"no published record of Ep{episode_num} for "
                           f"{app['name']} in {show.summaries_path}")
    # Oct 25 2026: a refresh also brings the record's links and photo up to
    # date, which is how an episode published before then gets its photo.
    photo = ensure_photo(app) or entry.get("guest_photo") or ""
    links = guest_links(app) or entry.get("guest_links") or []
    if photo != entry.get("guest_photo", "") or links != entry.get("guest_links"):
        entry["guest_photo"] = photo
        entry["guest_links"] = links
        show.summaries_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    when = dt.date.fromisoformat(str(entry["date"])[:10])
    write_episode_digest(show, episode_num, when, entry["title"],
                         interview, app, pkg, entry["audio_url"])
    subprocess.run(
        ["python", "generate_html.py", "--show", show.slug, "--blogs"],
        cwd=ROOT, check=True, timeout=1200,
    )
    logger.info("Refreshed the post and pages for Ep%d (%s); feed untouched",
                episode_num, app["name"])
    return 0


def main() -> int:
    """``INTERVIEW_ID`` publishes one episode; without it, sweep.
    ``REFRESH_POST=1`` with an ``INTERVIEW_ID`` rewrites an already
    published episode's post and pages instead (see :func:`refresh_post`).

    The sweep is what the scheduled workflow runs. It is idempotent —
    ``publish_one`` flips both rows to ``published``, so a second pass
    finds nothing — and one failing episode never blocks the others.
    """
    interview_id = os.environ.get("INTERVIEW_ID", "").strip()
    if interview_id and os.environ.get("REFRESH_POST", "").strip() in ("1", "true"):
        return refresh_post(interview_id)
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
