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

#: Nov 1 2026: since Oct 21 the post prints the transcript of the EDIT
#: (``edit_transcript``), and the edit takes out more than the guest's cuts:
#: Michael Kamins' Ep15 lost a skipped question, a repeated answer and a
#: dropout, none of which he asked for, under a line saying the transcript
#: was the conversation "as it was recorded". The room transcript keeps the
#: old line.
EDIT_TRANSCRIPT_NOTE = (
    "The conversation as it plays in the episode, which is edited for length "
    "and flow, with every cut the guest asked for made. After editorial review "
    "the transcript was sent to {name} to approve, cut from or refuse before "
    "publication."
)

#: Nov 4 2026 (voices-7): a WebVTT cue from the edit transcript ends where
#: the next stamped line starts, but never later than this — a cut line's
#: gap would otherwise hang one speaker's words over the next one's.
VTT_CUE_MAX_SECONDS = 20.0
#: The last cue has no next line; it runs this long.
VTT_LAST_CUE_SECONDS = 6.0

#: Under this many words a bio is thin, and the About section prints the
#: facts the pipeline holds beside it (voices-7). A label ("WorkID talk")
#: or a bare URL is never printed as prose at all — engine.interviews
#: .is_guest_prose is the one test, here and on the page.
BIO_MIN_WORDS = 40

#: Podcasting 2.0 channel tags the interview feeds never carried (voices-7:
#: 0 podcast:transcript / person / funding tags on 19 items while every
#: run_show feed had them). The label is run_show's, verbatim.
FUNDING_LABEL = "Support the Nerra Network"

#: What the video index records as ``video_kind`` (voices-3 / youtube-8).
VIDEO_KIND_CAMERA = "camera"                   # the guest beside Mira, from the studio take
VIDEO_KIND_WAVEFORM = "waveform"               # the waveform over the cover: no camera on the record
VIDEO_KIND_CAMERA_MISSING = "camera_missing"   # a camera cut on the record that would not fetch: NO upload
#: The index's ``variant`` for a long uploaded with the title bundle, the
#: thumbnail and the chapter block, so the reach file reads before/after.
YOUTUBE_VARIANT = "interview_v2"
#: Mira's studio still: the thumbnail base when the guest's photo may not be used.
MIRA_STUDIO_STILL = ROOT / "assets" / "mira" / "mira-studio.jpg"
#: How much of the edit transcript the title bundle reads.
TITLE_BUNDLE_TRANSCRIPT_WORDS = 1500


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
    kept = supported_chapters(pkg.get("chapter_markers") or [],
                              (pkg.get("transcript_cleaned") or "").strip())
    return [{**ch, "title": _chapter_case(ch.get("title", ""))}
            if isinstance(ch, dict) else ch for ch in kept]


def _chapter_case(title) -> str:
    """A chapter title opens on a capital (Nov 1 2026: Ep15's list mixed
    "the document that decided…" with "Conflict as a source…", because a
    title lifted from the middle of Mira's question keeps its lower case).
    A word like "iPhone", lower then upper, is left as written."""
    t = str(title or "").strip()
    if len(t) > 1 and t[0].islower() and not t[1].isupper():
        return t[0].upper() + t[1:]
    return t


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
    thesis gives way, and ``engine.titles`` decides how (Nov 4 2026: its
    first clause, whole — six of nineteen titles had ended in an ellipsis
    because the whole sentence was clipped at a word). Nothing here
    splits the text itself.
    """
    from engine.titles import PODCAST_EPISODE_TITLE_MAX, clip_words, fit_first_clause

    label = f"Ep{episode_num}: {(guest or '').strip()}"
    thesis = (thesis or "").strip()
    if not thesis:
        return clip_words(label, PODCAST_EPISODE_TITLE_MAX)
    room = PODCAST_EPISODE_TITLE_MAX - len(label) - len(" — ")
    if room < 20:
        return clip_words(label, PODCAST_EPISODE_TITLE_MAX)
    return f"{label} — {fit_first_clause(thesis, room)}"


def application_topics(app: dict) -> list:
    """The guest's own topics from the application, as clean strings (the
    Worker stores a list; older rows a JSON string). Mirrors the parse in
    ``common.interview_subject``."""
    topics = (app or {}).get("topics")
    if isinstance(topics, str):
        try:
            topics = json.loads(topics)
        except ValueError:
            topics = [topics]
    if not isinstance(topics, list):
        return []
    out: list = []
    for t in topics:
        item = " ".join(str(t or "").split()).strip(" ;,.")
        if item and item != "[object Object]" and item.lower() not in {x.lower() for x in out}:
            out.append(item)
    return out[:5]


def transcript_segments(transcript: str) -> list:
    """The edit transcript's stamped lines as ``[{start, end, text}]`` for
    ``engine.transcripts.segments_to_vtt``: a cue runs to the next line's
    stamp, capped at :data:`VTT_CUE_MAX_SECONDS`; the last cue runs
    :data:`VTT_LAST_CUE_SECONDS`; the text names the speaker."""
    from edit_transcript import parse_lines
    lines = parse_lines(transcript or "")
    out = []
    for i, (start, who, text) in enumerate(lines):
        if not text:
            continue
        nxt = next((t for t, _w, _x in lines[i + 1:] if t > start), None)
        end = (start + VTT_LAST_CUE_SECONDS if nxt is None
               else min(nxt, start + VTT_CUE_MAX_SECONDS))
        out.append({"start": start, "end": end, "text": f"{who}: {text}"})
    return out


def transcript_vtt_path(show: VoiceShow, episode_num: int, when: dt.date) -> Path:
    """Beside the digest, named as the digest is, so the publish workflow's
    add-paths (``digests/<slug>/``) commit it with the post."""
    return (ROOT / show.audio_subdir
            / f"{show.episode_prefix}_Ep{episode_num:03d}_{when:%Y%m%d}.vtt")


def write_transcript_vtt(pkg: dict, show: VoiceShow, episode_num: int,
                         when: dt.date) -> Path | None:
    """The WebVTT of the EDIT transcript, or None when the package has none.

    Nov 4 2026 (voices-7). Every run_show feed has carried a text/vtt
    ``<podcast:transcript>`` since Oct 1; the two interview feeds carried
    none, on the one show whose whole value is words a listener may want
    to read. Only the edit transcript qualifies: it is on the published
    file's clock (edit_transcript.transcript_of_the_edit); the room's is
    on a clock nobody hears, and a VTT on the wrong clock is worse than
    none.
    """
    text = str((pkg or {}).get("edit_transcript") or "").strip()
    if not text:
        return None
    segments = transcript_segments(text)
    if not segments:
        return None
    from engine.transcripts import segments_to_vtt
    path = transcript_vtt_path(show, episode_num, when)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(segments_to_vtt(segments), encoding="utf-8")
    logger.info("transcript VTT written: %s (%d cues)", path.name, len(segments))
    return path


def transcript_vtt_url(show: VoiceShow, path: Path) -> str:
    """Where Pages serves the committed VTT (same shape run_show uses)."""
    return f"{show.base_url}/{show.audio_subdir}/{path.name}"


def feed_podcast_tags(show: VoiceShow, episode_num: int, vtt_path: Path | None,
                      host_name: str = "") -> dict:
    """The Podcasting 2.0 kwargs ``engine.publisher.update_rss_feed`` takes
    and run_show passes (run_show.py's feed call): the Support button, the
    host, and — when the edit transcript gave one — the transcript, as
    the page's section (text/html) and the VTT Apple reads."""
    from engine.brand import MIRA_HOST_NAME
    tags = {
        "funding_url": f"{show.base_url}/support.html",
        "funding_label": FUNDING_LABEL,
        "person_name": (host_name or "").strip() or MIRA_HOST_NAME,
        "person_url": f"{show.base_url}/mira.html",
    }
    if vtt_path is not None:
        tags["transcript_url"] = f"{show.post_url(episode_num)}#transcript"
        tags["transcript_vtt_url"] = transcript_vtt_url(show, vtt_path)
    return tags


def _host_name(cfg) -> str:
    """``publishing.host_name`` from the show YAML (both interview shows say
    Mira), the same field run_show reads for ``person_name``."""
    return str(getattr(getattr(cfg, "publishing", None), "host_name", "") or "").strip()


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
    # Oct 29 2026 (Michael Kamins): the post printed the ROOM's transcript,
    # so a question the guest skipped, a line the edit took out and Mira's
    # "you can hang up now" were all on the page of an episode that does not
    # contain them. The transcript of the edit is what listeners hear and
    # what the guest was sent to approve; the room's is the fallback for an
    # episode assembled before the edit had one.
    transcript = (pkg.get("edit_transcript") or pkg.get("transcript_cleaned") or "").strip()
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

    # Nov 4 2026 (voices-7): 8 of 18 About sections were under 25 words —
    # "WorkID talk", "longevityresearch.ca", a bare URL, or this function's
    # own placeholder sentence — because this printed ``bio or <placeholder>``.
    # Now: the bio only when it is the guest's own prose (a label is not a
    # biography, a URL is a link); beside a thin bio, the facts the pipeline
    # holds — the role line and the application's topics; the placeholder
    # only when there is nothing at all. Never a model-written bio.
    from engine.interviews import TOPICS_LINE_LABEL, is_guest_prose, _stray_link
    topics = application_topics(app)
    links = guest_links(app)
    bio_is_prose = is_guest_prose(bio)
    parts.append(f"### About {name}")
    if role:
        parts.append(f"**{role}**")
    if bio_is_prose:
        parts.append(bio)
    elif bio:
        stray = _stray_link(bio)
        if stray and stray["url"].lower() not in {l["url"].lower() for l in links}:
            links.append(stray)
    if len(bio.split()) < BIO_MIN_WORDS and topics:
        parts.append(f"**{TOPICS_LINE_LABEL}:** {'; '.join(topics)}")
    if not (role or bio_is_prose or topics):
        parts.append(f"{name} joined Mira for this conversation.")
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
        note = EDIT_TRANSCRIPT_NOTE if pkg.get("edit_transcript") else TRANSCRIPT_NOTE
        parts.append(note.format(name=name))
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


# Nov 1 2026: the review page asks the guest when they would come back
# (Worker ``handleGuestReviewSubmit``: ``guest_followup``, and a
# ``guest_return_requests`` row due that many months on). Michael Kamins chose
# "about six months" and the publish mail told him February 2027, three
# months, because it never read his answer. The guest's choice wins.
RETURN_MONTHS_BY_CHOICE = {"return_6": 6, "return_12": 12}


def _date_of(value) -> dt.date | None:
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def return_invitation_html(pkg: dict, when: dt.date) -> str:
    """The "I would like you back" paragraph, as the guest asked for it.

    No answer: the network default, ``RETURN_AFTER_MONTHS`` from ``when``.
    Six or twelve months: that month, counted from the day they chose it.
    Another time: no month, an offer to fix one. Nothing for now (or a
    redo): no invitation at all; they have already said."""
    e = _html.escape
    choice = str(pkg.get("guest_followup") or "").strip()
    if choice in ("none", "redo"):
        return ""
    if choice == "return_other":
        return ("<p>You said you would like to come back at another time. "
                "Reply with when suits you and I'll send the booking link "
                "nearer the time.</p>")
    months = RETURN_MONTHS_BY_CHOICE.get(choice)
    if months:
        month = return_month(_date_of(pkg.get("guest_followup_at")) or when, months)
        return (f"<p>And I would like you back. You said about "
                f"{'six months' if months == 6 else 'a year'}, so I have put "
                f"{e(month)} in the calendar for a second conversation, when there "
                "will be something to measure the first one against; I'll send the "
                "booking link nearer the time.</p>")
    month = return_month(when)
    return (f"<p>And I would like you back. I have put {e(month)} in the calendar for a "
            "second conversation, when there will be something to measure the first "
            "one against; reply with a yes and I'll send the booking link nearer the "
            "time.</p>")


def clip_link(pkg: dict, show: VoiceShow, episode_num: int,
              run: dict | None = None) -> tuple:
    """``(url, title)`` of a 60-second moment the guest can share: the first
    clip suggestion, as a deep link into the YouTube upload when the publish
    recorded one, else into the episode's post with a ``#t=`` offset.

    Oct 29 2026: the suggestion is on the room's clock and the link points
    into the published file, which opens on narration and has its pauses
    closed; the moment is moved to the edit's clock first (as the chapters
    and the X clip are), or the link lands minutes early."""
    clips = pkg.get("clip_suggestions") or []
    clip = next((c for c in clips if isinstance(c, dict) and c.get("start") is not None), None)
    if clip is None:
        return "", ""
    start = max(0, int(float(clip["start"])))
    clock = ((((run or {}).get("grok_session_log") or {}).get("tracks") or {})
             .get("edit") or {}).get("clock")
    if clock:
        from edit_transcript import room_to_edit
        moved = room_to_edit(clock, float(clip["start"]))
        if moved is not None:
            start = max(0, int(moved))
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
                    episode_num: int, when: dt.date | None = None,
                    run: dict | None = None, youtube: dict | None = None) -> tuple:
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
    clip_url, clip_title = clip_link(pkg, show, episode_num, run=run)
    if clip_url:
        parts.append("<p>A short moment to share, if you want one"
                     + (f" — <em>{e(clip_title)}</em>" if clip_title else "")
                     + f": {link(clip_url)}</p>")
    card = share_card_link(show, episode_num)
    if card:
        parts.append(f"<p>The episode's share card, for a post of your own: {link(card)}</p>")
    # Nov 4 2026: when the YouTube thumbnail carries the guest's own photo
    # (only ever with the review page's picture choice), the note says so
    # — a face at 1280x720 on a public video is a larger use than the
    # avatar on the post, and the guest hears it from us first.
    yt = youtube or {}
    if yt.get("thumbnail_base") == "guest_photo" and yt.get("video_id"):
        watch = f"https://www.youtube.com/watch?v={yt['video_id']}"
        parts.append("<p>On YouTube the episode's thumbnail uses your profile photo, "
                     "as you allowed on the review page: "
                     f"{link(watch)}. If you would rather it did not, reply and "
                     "I will change it the same day.</p>")
    invitation = return_invitation_html(pkg, when or dt.date.today())
    parts += [
        "<p>If anything on the page is wrong, a link, a title, a spelling, "
        "reply to this and I'll have it fixed the same day. If you post about it, "
        "send me the link and I'll share it on. The network is "
        f"{link(show.base_url)} and @planetterrian on X if you want to tag it.</p>",
    ] + ([invitation] if invitation else []) + [
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


def tell_the_guest(show: VoiceShow, app: dict, pkg: dict, episode_num: int,
                   run: dict | None = None, youtube: dict | None = None) -> None:
    """Send :func:`published_email` once; a failure never unpublishes anything."""
    if pkg.get("publish_package_sent_at"):
        logger.info("publish-day note already sent %s", pkg["publish_package_sent_at"])
        return
    subject, body = published_email(show, app, pkg, episode_num, run=run, youtube=youtube)
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

    # The show's full config: the distribution flags below, and the host
    # name the feed's <podcast:person> carries. None = distribution skipped.
    cfg = _show_config(show)
    # Nov 4 2026 (voices-7): the fifth instance of the bypass-run_show
    # class. The transcript VTT, the Support button and the host reach the
    # feed through the same kwargs run_show passes; the VTT is written
    # beside the digest BEFORE the feed so its item carries the tag from
    # the first build. A VTT failure costs the tag, never the episode.
    vtt_path = None
    try:
        vtt_path = write_transcript_vtt(pkg, show, episode_num, today)
    except Exception:  # noqa: BLE001 — the episode still publishes
        logger.exception("transcript VTT not written (non-fatal)")
    podcast_tags = feed_podcast_tags(show, episode_num, vtt_path,
                                     host_name=_host_name(cfg))

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
            # transcript_url / transcript_vtt_url / funding_url / person_name
            # (+ label, person_url): feed_podcast_tags, the one place they
            # are built for this path.
            **podcast_tags,
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
    maybe_send_newsletter(show, cfg, episode_num, today,
                          interview.get("episode_thesis") or "",
                          digest_path)
    yt_outcome: dict = {}
    long_id = maybe_publish_youtube(show, cfg, episode_num, today, title, description,
                                    audio_url, app.get("name") or "", video_url=video,
                                    pkg=pkg, app=app, photo=photo,
                                    thesis=interview.get("episode_thesis") or "",
                                    outcome=yt_outcome)
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
    tell_the_guest(show, app, pkg, episode_num, run=run, youtube=yt_outcome)
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
    # Nov 1 2026: an interview is a section of the next morning's Nerra Daily
    # email (engine/nerra_daily_email.py reads the published episode), not an
    # email of its own, unless the show keeps one (``delivery: own``).
    delivery = (getattr(cfg.newsletter, "delivery", "own") or "own").strip()
    if delivery != "own":
        logger.info("Newsletter for %s Ep%d goes out in the next Nerra Daily email.",
                    show.slug, episode_num)
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


def _head_status(url: str) -> int:
    """The HTTP status a HEAD of *url* answers, 0 when the request fails."""
    try:
        return int(requests.head(url, timeout=60, allow_redirects=True).status_code)
    except Exception:  # noqa: BLE001
        logger.warning("HEAD %s failed", url)
        return 0


def transcript_excerpt(pkg: dict | None, words: int = TITLE_BUNDLE_TRANSCRIPT_WORDS) -> str:
    """The first *words* of the edit transcript (else the room's), for the
    title bundle's content excerpt."""
    pkg = pkg or {}
    text = pkg.get("edit_transcript") or pkg.get("transcript_cleaned") or ""
    return " ".join(str(text).split()[:words])


def youtube_title_for(feed_title: str, guest_name: str, candidates: list) -> str:
    """The long-form's YouTube title (youtube-8 stage 1).

    The bundle's first candidate that fits ``engine.titles.YOUTUBE_TITLE_MAX``
    with the guest's name in it — a candidate without the name takes it as a
    prefix first — else the feed title, which carries the name by shape. The
    interview's value is the person, so a title without the guest never ships
    (guard: tests/test_age_of_ai_youtube_2026_11_03.py). engine.titles owns
    the limit; nothing here slices.
    """
    from engine.titles import YOUTUBE_TITLE_MAX, clip_words, fits
    guest = " ".join((guest_name or "").split())
    for cand in candidates or []:
        text = " ".join(str(cand or "").split())
        if not text:
            continue
        if guest and guest.lower() not in text.lower():
            text = f"{guest}: {text}"
        if fits(text, YOUTUBE_TITLE_MAX) and (not guest or guest.lower() in text.lower()):
            return text
    return clip_words(feed_title, YOUTUBE_TITLE_MAX)


def thumbnail_base_for(pkg: dict | None, photo: str, tmp: Path) -> tuple:
    """``(image path or None, "guest_photo" | "mira_studio")``.

    The guest's photo ONLY when the review-page choice allows a picture
    (``editorial_packages.guest_video_ok`` is True — the same choice that
    puts their camera in the video): a 1280x720 face on a monetized channel
    is a larger reuse than the 40 px avatar on the post, so the post's
    consent is not borrowed for it. Otherwise Mira's studio still.
    """
    if photo and (pkg or {}).get("guest_video_ok") is True:
        local = _download(str(photo), Path(tmp) / "guest_photo.img")
        if local is not None:
            return local, "guest_photo"
    return (MIRA_STUDIO_STILL if MIRA_STUDIO_STILL.exists() else None), "mira_studio"


def episode_thumbnail(show: VoiceShow, show_name: str, episode_num: int, when: dt.date,
                      guest_name: str, role: str, punch_text: str, base: Path,
                      tmp: Path) -> Path | None:
    """The 1280x720 thumbnail every other long-form carries, rendered by
    ``engine.publisher.generate_episode_thumbnail`` on *base* with the guest
    (and who they are) as its one line. Best-effort: None means the upload
    goes without one, as before."""
    from engine.publisher import generate_episode_thumbnail
    out = Path(tmp) / f"{show.episode_prefix}_Ep{episode_num:03d}_thumb.jpg"
    hook = f"{guest_name} — {role}" if role else guest_name
    try:
        path, _font = generate_episode_thumbnail(
            Path(base), episode_num=episode_num, date_str=f"{when:%B %-d, %Y}",
            output_path=out, hook=hook, show_name=show_name,
            punch_text=punch_text or "")
        return Path(path)
    except Exception as exc:  # noqa: BLE001 — the upload goes without a thumbnail
        logger.warning("::warning::thumbnail not rendered for %s Ep%d: %s",
                       show.slug, episode_num, exc)
        return None


def chapter_block_for(pkg: dict | None) -> str:
    """The ``0:00 Title`` block YouTube reads into the seek bar, from the
    chapters the transcript vouches for (the same list the post prints);
    "" when fewer than two render."""
    from engine.video_metadata import _format_chapter_block
    return _format_chapter_block(vouched_chapters(pkg or {}))


def maybe_publish_youtube(show: VoiceShow, cfg, episode_num: int, when: dt.date,
                          title: str, description: str, audio_url: str,
                          guest_name: str, video_url: str = "", *,
                          pkg: dict | None = None, app: dict | None = None,
                          photo: str = "", thesis: str = "",
                          outcome: dict | None = None) -> str:
    """Upload the episode's video to YouTube, if the show enables it.

    One long-form upload: the camera cut (the guest beside Mira) when the
    edit carries one, else the waveform over the cover. No dubs, no
    adaptive-policy tier — those live in run_show's YouTube stage and
    porting them is a larger job than this show needs to have a video
    presence. The upload is recorded in ``digests/<slug>/youtube_videos.json``,
    which the analytics fetcher, the adaptive policy and the subscriber
    tracker already glob.

    Nov 4 2026 (youtube-8 stage 1 + voices-3): the upload carries the
    packaging every other long-form has — a title from
    ``engine.youtube_titles.generate_title_bundle`` that keeps the guest's
    name, a 1280x720 thumbnail, the chapter block in the description — and
    the index row says which video shipped (``video_kind``) and that this
    packaging was on (``variant``). Three longs had gone up as the feed
    title over a waveform: 27 views, 1.5% watched.

    **A camera episode never ships the waveform.** When the edit's camera
    cut is on the record but its URL does not answer 200, nothing is
    uploaded (YouTube cannot replace a video's file later), the index gets
    no row, ``outcome["video_kind"]`` reads ``camera_missing`` and the
    operator is told. Before this the same case set ``render_locally`` and
    silently uploaded the waveform.

    *outcome*, when given, is filled with ``video_kind`` / ``video_id`` /
    ``title`` / ``thumbnail_base`` for the publish-day mail.
    """
    out = outcome if outcome is not None else {}
    if cfg is None or not getattr(getattr(cfg, "youtube", None), "enabled", False):
        return ""
    yt = cfg.youtube
    pkg = pkg or {}
    app = app or {}
    channel = getattr(yt, "channel", "en") or "en"
    show_name = getattr(cfg, "name", "") or show.name

    if video_url:
        # The video version (the guest beside Mira) for this edit.
        status = _head_status(video_url)
        if status != 200:
            logger.warning(
                "::warning::YouTube skipped for %s Ep%d: the edit's camera cut %s "
                "answered HTTP %s. A camera episode never ships the waveform — "
                "re-run the video cut for this interview, then upload by hand.",
                show.slug, episode_num, video_url, status)
            out.update({"video_kind": VIDEO_KIND_CAMERA_MISSING, "video_id": "",
                        "camera_status": status})
            try:
                notify_operator(show.slack(
                    f"Ep{episode_num}: the camera cut {video_url} answered HTTP "
                    f"{status}; YouTube skipped rather than ship the waveform."))
            except Exception:  # noqa: BLE001
                logger.exception("could not notify the operator")
            return ""
        video_kind = VIDEO_KIND_CAMERA
        render_locally = False
    else:
        # The waveform the produce step rendered, else one rendered here
        # (Oct 11 2026: the edit path never renders one, so the derived
        # URL 404'd on every publish and the show had uploaded nothing).
        video_kind = VIDEO_KIND_WAVEFORM
        video_url = waveform_video_url(audio_url)
        render_locally = not video_url
        if video_url and _head_status(video_url) != 200:
            logger.warning("No waveform video at %s — rendering one from the "
                           "episode audio", video_url)
            render_locally = True
    out["video_kind"] = video_kind

    try:
        from engine.funnel import PLACEMENT_DESCRIPTION, episode_link
        from engine.youtube import (
            add_video_to_playlist, get_channel_credentials_from_env,
            upload_video,
        )
        from engine.youtube_titles import generate_title_bundle
        from engine.utils import strip_speech_tags

        credentials = get_channel_credentials_from_env(channel)
        if credentials is None:
            logger.warning("::warning::YouTube skipped for %s Ep%d: no channel "
                           "credentials in the environment", show.slug, episode_num)
            return ""

        tags = list(getattr(yt, "tags", None) or [])[:15]
        # One Grok call: titles + the thumbnail's punch text. Never raises;
        # an empty bundle falls back to the feed title and no punch text.
        bundle = generate_title_bundle(
            hook=(thesis or "").strip() or title, digest_text=transcript_excerpt(pkg),
            show_name=show_name, episode_num=episode_num, keywords=tags,
            channel=channel, tracker=None,
        ) or {}
        yt_title = youtube_title_for(title, guest_name, bundle.get("titles") or [])

        # show.page_url is already absolute (shows.py builds it from the
        # registry). Every published link goes through engine.funnel — see
        # the standing rule at the top of CLAUDE.md.
        page = episode_link(
            show.page_url, show.slug, episode_num, kind="long",
            placement=PLACEMENT_DESCRIPTION,
        )
        body = strip_speech_tags(description or "").strip()
        chapters = chapter_block_for(pkg)
        full_description = "\n\n".join(x for x in (
            body,
            chapters,
            f"Full episode, transcript and every other show: {page}",
            f"{show_name} is hosted by Mira, an AI. Every episode says so, and "
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
            base, thumb_base = thumbnail_base_for(pkg, photo, Path(tmp))
            role = ", ".join(x for x in (app.get("title"), app.get("organization")) if x)
            thumbnail = (episode_thumbnail(show, show_name, episode_num, when, guest_name,
                                           role, bundle.get("punch_text") or "", base,
                                           Path(tmp))
                         if base is not None else None)
            result = upload_video(
                local,
                credentials=credentials,
                title=yt_title,
                description=full_description,
                tags=tags,
                category_id=int(getattr(yt, "category_id", 24) or 24),
                privacy_status=getattr(yt, "privacy_status", "public") or "public",
                thumbnail_path=thumbnail,
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
        thumbnail_base = thumb_base if thumbnail is not None else ""
        _record_youtube_video(show, episode_num, when, yt_title, video_id,
                              guest_name, channel, variant=YOUTUBE_VARIANT,
                              video_kind=video_kind, thumbnail_base=thumbnail_base)
        out.update({"video_id": video_id, "title": yt_title,
                    "thumbnail_base": thumbnail_base, "chapters": bool(chapters)})
        logger.info("YouTube: %s Ep%d uploaded as %s (%s, %s)",
                    show.slug, episode_num, video_id, video_kind, YOUTUBE_VARIANT)
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
                        f"{cfg.name} is hosted by Mira, an AI. Every guest is sent "
                        "their own transcript to approve, cut from or refuse before "
                        "it is published.",
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
                          channel: str, kind: str = "long", *,
                          variant: str = "", video_kind: str = "",
                          thumbnail_base: str = "") -> None:
    """Append to the per-show video index the rest of the network already reads.

    Nov 4 2026: a long also records ``variant`` (:data:`YOUTUBE_VARIANT`),
    ``video_kind`` (camera | waveform) and ``thumbnail_base``, so
    ``api/youtube_early_reach.json`` can read the camera cuts and the
    packaged uploads apart from the three waveform longs before them.
    Keys are written only when given, so a Short's row is unchanged."""
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
        **({"variant": variant} if variant else {}),
        **({"video_kind": video_kind} if video_kind else {}),
        **({"thumbnail_base": thumbnail_base} if thumbnail_base else {}),
    })
    index.parent.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                     encoding="utf-8")


def _feed_item(rss_path: Path, episode_num: int) -> tuple:
    """``(guid, has_transcript_tag)`` of the feed item numbered *episode_num*
    (``<itunes:episode>``), or ``("", False)`` when the feed has none."""
    import xml.etree.ElementTree as ET
    itunes = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
    podcast = "{https://podcastindex.org/namespace/1.0}"
    if not rss_path.exists():
        return "", False
    channel = ET.parse(str(rss_path)).getroot().find("channel")
    for item in (channel.findall("item") if channel is not None else []):
        num = item.find(f"{itunes}episode")
        guid = item.find("guid")
        if num is None or guid is None or not guid.text:
            continue
        if str(num.text or "").strip() == str(episode_num):
            return guid.text.strip(), item.find(f"{podcast}transcript") is not None
    return "", False


def _summary_entry(show: VoiceShow, episode_num: int) -> dict | None:
    if not show.summaries_path.exists():
        return None
    data = json.loads(show.summaries_path.read_text(encoding="utf-8")) or {}
    return next((e for e in (data.get("episodes") or [])
                 if int(e.get("episode") or 0) == episode_num), None)


def vtt_backfill(slug: str = "") -> int:
    """Write the transcript VTT beside every PUBLISHED episode whose package
    carries an edit transcript, and put the transcript tags on that item in
    the feed (``VTT_BACKFILL=1``; one show with ``VOICES_SHOW``).

    Nov 4 2026 (voices-7). The feed's other items are untouched and no item
    moves; once an item carries the tags, ``update_rss_feed``'s preserved-tag
    pass keeps them through every later rebuild — it re-emits only what the
    feed already carries, which is why this has to inject the first copy.
    An episode whose package has no edit transcript (assembled before the
    edit had one, or on the produce path) is LISTED, never given a VTT on
    the room's clock. Rewriting those posts is the operator's
    ``refresh_post`` run per interview.
    """
    from shows import VOICE_SHOW_SLUGS, get_show
    from engine.publisher import _inject_transcript_tag
    written, tagged, skipped = 0, 0, []
    for s in ([slug] if slug else list(VOICE_SHOW_SLUGS)):
        show = get_show(s)
        host = _host_name(_show_config(show))
        rows = sb_select("interviews", f"status=eq.published&show=eq.{s}"
                                       "&episode_number=not.is.null"
                                       "&order=episode_number.asc")
        for interview in rows:
            num = int(interview.get("episode_number") or 0)
            pkgs = sb_select("editorial_packages",
                             f"interview_id=eq.{interview['id']}&status=eq.published"
                             "&order=created_at.desc&limit=1")
            pkg = pkgs[0] if pkgs else {}
            entry = _summary_entry(show, num)
            if not num or entry is None:
                skipped.append(f"{s} Ep{num}: no summaries record")
                continue
            when = dt.date.fromisoformat(str(entry["date"])[:10])
            path = write_transcript_vtt(pkg, show, num, when)
            if path is None:
                skipped.append(f"{s} Ep{num}: no edit transcript on the package")
                continue
            written += 1
            guid, has_tag = _feed_item(show.rss_path, num)
            if guid and not has_tag:
                tags = feed_podcast_tags(show, num, path, host_name=host)
                _inject_transcript_tag(show.rss_path, guid, tags["transcript_url"],
                                       transcript_vtt_url=tags["transcript_vtt_url"])
                tagged += 1
    logger.info("VTT backfill: %d written, %d feed item(s) tagged", written, tagged)
    for line in skipped:
        logger.warning("::warning::VTT backfill skipped %s", line)
    return 0


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
    # Nov 1 2026: and its chapters, which the post's list is drawn from.
    chapters = vouched_chapters(pkg) or entry.get("chapters") or []
    if (photo != entry.get("guest_photo", "") or links != entry.get("guest_links")
            or chapters != entry.get("chapters", [])):
        entry["guest_photo"] = photo
        entry["guest_links"] = links
        entry["chapters"] = chapters
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
    ``VTT_BACKFILL=1`` writes the transcript VTTs for every published
    episode that has an edit transcript (see :func:`vtt_backfill`).

    The sweep is what the scheduled workflow runs. It is idempotent —
    ``publish_one`` flips both rows to ``published``, so a second pass
    finds nothing — and one failing episode never blocks the others.
    """
    interview_id = os.environ.get("INTERVIEW_ID", "").strip()
    if os.environ.get("VTT_BACKFILL", "").strip() in ("1", "true"):
        return vtt_backfill(os.environ.get("VOICES_SHOW", "").strip())
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
