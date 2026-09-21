"""One owner for what an interview episode *is*.

The Age of AI and Nerra Voices do not run through ``run_show.py``. Their
digests are written by ``pipelines/voices/`` and have a shape no news show
has: a named human being, a one-line identifier for them, a link to their own
work, and a transcript the guest personally approved. Until 2026-09-21 the
website knew none of that.

What a visitor actually got was the generic news-show blog layout applied to
an interview: the ``<h1>`` was the digest's 200-character thesis sentence, the
``<h2>`` under it was the show's own name, the guest's name first appeared as
an ``<h4>`` about a third of the way down, and the "Listen" section was a bare
text link — ``extract_blog_metadata`` never finds an ``audio_url`` for these
episodes, so **no interview post on the site had a player at all**. Six
published conversations with real people, and nothing above the fold said who
any of them were or let you hear them.

This module reads the structure back out of the committed digest so the
templates can lead with it. It is deliberately a READER, not a writer: it
parses what ``pipelines/voices/`` already commits and never asks the pipeline
to emit anything new, so it works retroactively on all six published episodes
and cannot break a publish.

Two rules for anyone extending it:

* **A section that is missing is missing.** Every field degrades to empty and
  the templates gate on it. Ep001 predates the current digest shape and has no
  markdown file at all; a parser that raised on it would take the whole blog
  build down.
* **The guest's own words are never reformatted here.** The transcript block
  is handed through untouched. It is the thing the guest read and approved,
  and "we tidied it in rendering" is not a sentence this show can afford.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

#: The shows whose digests carry a guest. Both are Nerra Voices pipeline
#: shows; both run the two human gates named in ``engine.brand``. A news show
#: must never be added here — its digest has no guest to lead with, and the
#: interview layout would render an empty identity block above the fold.
INTERVIEW_SHOW_SLUGS = ("age_of_ai", "nerra_voices")

#: Digest section headings the parser understands, as written by
#: ``pipelines/voices/``. Matched case-insensitively and by prefix, because
#: three of them carry the guest's name ("About Hogan Shrum").
_SECTION_LISTEN = "listen"
_SECTION_ABOUT = "about "
_SECTION_TALKING = "what we talked about"
_SECTION_LINKS = "where to find "
_SECTION_TRANSCRIPT = "transcript"

_HEADING_RE = re.compile(r"^#{2,4}\s+(.+?)\s*$", re.M)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BOLD_LINE_RE = re.compile(r"^\*\*(.+?)\*\*\s*$", re.M)
_BULLET_RE = re.compile(r"^[-*]\s+(.+?)\s*$", re.M)


def is_interview_show(slug: str) -> bool:
    """True when *slug* publishes interviews rather than a news digest."""
    return slug in INTERVIEW_SHOW_SLUGS


def _sections(md_text: str) -> list:
    """Split *md_text* into ``(heading, body)`` pairs, in document order.

    Text before the first ``##`` heading is returned under the empty heading,
    which is where the hook and the "What You Need to Know" paragraph live.
    """
    out = []
    matches = list(_HEADING_RE.finditer(md_text))
    if not matches:
        return [("", md_text)]
    if matches[0].start() > 0:
        out.append(("", md_text[: matches[0].start()]))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        out.append((m.group(1).strip(), md_text[m.end():end]))
    return out


def _first_audio_url(text: str) -> str:
    """The first link in *text* that points at an audio file we host."""
    for _label, url in _MD_LINK_RE.findall(text):
        if url.endswith((".mp3", ".m4a", ".wav")):
            return url
    return ""


def _strip_rules(text: str) -> str:
    """Drop markdown horizontal rules and collapse blank runs."""
    text = re.sub(r"^\s*---+\s*$", "", text, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _stray_link(text: str) -> Optional[dict]:
    """*text* as a link, when a link is the only thing it contains.

    Returns ``None`` for real prose — including prose that merely mentions a
    URL, which stays prose.
    """
    stripped = text.strip()
    if not stripped:
        return None
    md = _MD_LINK_RE.fullmatch(stripped)
    if md:
        return {"label": md.group(1).strip(), "url": md.group(2)}
    if re.fullmatch(r"https?://\S+", stripped):
        return {"label": _link_label(stripped), "url": stripped}
    return None


def _link_label(url: str) -> str:
    """A readable label for a bare URL: its host, without ``www.``."""
    host = re.sub(r"^https?://", "", url).split("/")[0]
    return host[4:] if host.startswith("www.") else host


def parse_interview_digest(md_text: str) -> dict:
    """Read the interview structure out of one committed digest.

    Every key is always present. Missing sections give empty values rather
    than absent keys, so a template can gate on truthiness without ever
    hitting an undefined.
    """
    result = {
        "guest_name": "",
        "guest_identifier": "",
        "guest_blurb": "",
        "audio_url": "",
        "takeaway": "",
        "talking_points": [],
        "guest_links": [],
        "has_transcript": False,
    }

    for heading, body in _sections(md_text):
        low = heading.lower()

        if not heading:
            # The preamble: the blockquoted hook, the episode line, and the
            # "What You Need to Know" paragraph that is this show's version
            # of a standfirst.
            m = re.search(
                r"\*\*What You Need to Know:\*\*\s*(.+?)(?:\n\s*\n|\Z)",
                body, re.S,
            )
            if m:
                result["takeaway"] = " ".join(m.group(1).split())

        elif low == _SECTION_LISTEN:
            result["audio_url"] = _first_audio_url(body)

        elif low.startswith(_SECTION_ABOUT):
            # "### About Hogan Shrum" → the name; the bold line under it is
            # the one-line identifier ("Co-Founder, PIPPA"); the prose after
            # it is the blurb.
            result["guest_name"] = heading[len(_SECTION_ABOUT):].strip()
            bold = _BOLD_LINE_RE.search(body)
            if bold:
                result["guest_identifier"] = bold.group(1).strip()
            prose = _BOLD_LINE_RE.sub("", body)
            prose = _strip_rules(prose)
            # Some digests put nothing in this section but the guest's own
            # URL (Ep006 is a bare link to a team page). That is a link, not
            # a biography: rendering it as prose puts a naked URL in the
            # identity block above the fold. Keep it as a link instead.
            stray = _stray_link(prose)
            if stray:
                result["guest_links"].append(stray)
            elif prose:
                result["guest_blurb"] = " ".join(prose.split())

        elif low == _SECTION_TALKING:
            result["talking_points"] = [
                " ".join(b.split()) for b in _BULLET_RE.findall(body)
            ]

        elif low.startswith(_SECTION_LINKS):
            seen = {item["url"] for item in result["guest_links"]}
            for label, url in _MD_LINK_RE.findall(body):
                if url in seen:
                    continue
                seen.add(url)
                result["guest_links"].append(
                    {"label": label.strip(), "url": url})
            if not result["guest_name"]:
                result["guest_name"] = heading[len(_SECTION_LINKS):].strip()

        elif low == _SECTION_TRANSCRIPT:
            result["has_transcript"] = bool(_strip_rules(body))

    return result


def episode_record(summaries_path, episode_num: int) -> dict:
    """The committed summaries record for one episode, or ``{}``.

    ``pipelines/voices/`` writes ``guest``, ``guest_links``, ``audio_url`` and
    ``chapters`` here, and it is the authority for all four: the record is
    what the RSS item was built from. (The ``age_of_ai/raw/<uuid>_edit.mp3``
    keys look like editorial masters and are not — they are the published
    enclosures for Ep003-006, OP3-prefixed in the feed. Do not "clean them
    up": rewriting a live enclosure re-downloads the episode for every
    subscriber.)
    """
    path = Path(summaries_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    episodes = data.get("episodes") if isinstance(data, dict) else data
    if not isinstance(episodes, list):
        return {}
    for record in episodes:
        if isinstance(record, dict) and record.get("episode") == episode_num:
            return record
    return {}


def interview_context(
    md_text: str,
    slug: str,
    episode_num: int,
    summaries_path: Optional[str] = None,
) -> dict:
    """Everything the interview templates need for one episode.

    Returns ``{}`` for a non-interview show, so a caller can attach the result
    unconditionally and every other show renders byte-identically.

    The summaries record wins over the digest wherever both carry the same
    fact, because the record is what the feed was built from.
    """
    if not is_interview_show(slug):
        return {}

    ctx = parse_interview_digest(md_text or "")
    record = episode_record(summaries_path, episode_num) if summaries_path else {}

    if record.get("guest"):
        ctx["guest_name"] = record["guest"]
    if record.get("audio_url"):
        ctx["audio_url"] = record["audio_url"]
    if record.get("guest_links"):
        # The record's shape is a list of dicts already; keep the digest's
        # links when it is empty, which is what Ep002/003 have.
        links = [
            {"label": (item.get("label") or item.get("title") or item.get("url", "")),
             "url": item.get("url", "")}
            for item in record["guest_links"]
            if isinstance(item, dict) and item.get("url")
        ]
        if links:
            ctx["guest_links"] = links

    ctx["chapters"] = record.get("chapters") or []
    ctx["episode_num"] = episode_num
    ctx["run_time"] = _run_time(ctx["chapters"])
    return ctx


def _run_time(chapters) -> str:
    """Human running time from the last chapter's end, or "".

    The summaries record carries no duration field, but its chapter markers
    are built from the finished audio, so the final ``end`` is the episode
    length. A malformed or empty chapter list gives "" and the template
    simply omits the figure — a wrong running time is worse than none.
    """
    if not isinstance(chapters, list) or not chapters:
        return ""
    try:
        seconds = int(max(float(c.get("end", 0)) for c in chapters
                          if isinstance(c, dict)))
    except (TypeError, ValueError):
        return ""
    if seconds < 60:
        return ""
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes} min"
    hours, rem = divmod(minutes, 60)
    return f"{hours} hr {rem} min" if rem else f"{hours} hr"


#: The digest sections the interview layout promotes above the fold. Leaving
#: them in the body too would print the guest's name, their links and the
#: talking points twice on the same page.
_PROMOTED_SECTIONS = (
    _SECTION_LISTEN,
    _SECTION_ABOUT,
    _SECTION_TALKING,
    _SECTION_LINKS,
)


def _is_promoted(heading: str) -> bool:
    low = heading.lower()
    return any(
        low == name if not name.endswith(" ") else low.startswith(name)
        for name in _PROMOTED_SECTIONS
    )


def interview_body_markdown(md_text: str) -> str:
    """*md_text* with the promoted sections and the redundant preamble gone.

    What is left is the part the hero does not carry: the transcript, plus any
    section a future digest adds that this module does not know about — an
    unrecognised heading is KEPT, so a new section shows up on the page
    looking plain rather than vanishing silently.

    The preamble goes because every line of it is already above the fold in a
    better place: the ``# The Age of AI`` heading is the show name (which the
    page says three times already), the blockquoted hook is the standfirst,
    and the episode line is the meta bar.
    """
    kept = []
    for heading, body in _sections(md_text):
        if not heading:
            continue  # the preamble — hook, episode line, "What You Need to Know"
        if _is_promoted(heading):
            continue
        kept.append(f"### {heading}\n{body}")
    return _strip_rules("\n\n".join(kept))


def guest_name_for(summaries_path, episode_num: int) -> str:
    """The guest on *episode_num*, or "" when unknown.

    Used for the previous/next links, which otherwise read "Episode 3" — a
    label that tells a reader nothing about whether they want to click it.
    On an interview show the guest IS the episode.
    """
    if not summaries_path or episode_num is None:
        return ""
    return (episode_record(summaries_path, episode_num) or {}).get("guest", "")


def interview_episode_cards(
    slug: str,
    summaries_path,
    digest_dir=None,
    limit: int = 0,
) -> list:
    """The show's episodes as guest cards, newest first.

    This is what an interview show's archive rail should carry. The generic
    rail is built from the RSS ``<title>``, which on these shows is the
    digest's whole thesis sentence — 200 characters of abstract prose with
    the guest's name buried in the middle of it. A visitor scanning for
    somebody they recognise has nothing to scan.

    The summaries record is the spine (it is what the feed was built from);
    the digest supplies the one-line identifier, which the record does not
    carry. A missing digest costs that episode its identifier and nothing
    else — Ep001 has no markdown file and still renders.
    """
    if not is_interview_show(slug):
        return []

    path = Path(summaries_path)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    episodes = data.get("episodes") if isinstance(data, dict) else data
    if not isinstance(episodes, list):
        return []

    identifiers = {}
    if digest_dir:
        for md_path in Path(digest_dir).glob("*.md"):
            m = re.search(r"_Ep(\d+)_", md_path.name)
            if not m:
                continue
            try:
                parsed = parse_interview_digest(
                    md_path.read_text(encoding="utf-8"))
            except OSError:
                continue
            identifiers[int(m.group(1))] = parsed

    cards = []
    for record in episodes:
        if not isinstance(record, dict):
            continue
        num = record.get("episode")
        parsed = identifiers.get(num, {})
        cards.append({
            "episode": num,
            "guest": record.get("guest") or parsed.get("guest_name", ""),
            "identifier": parsed.get("guest_identifier", ""),
            "date": _display_date(record.get("date", "")),
            "audio_url": record.get("audio_url", ""),
            "run_time": _run_time(record.get("chapters") or []),
            "takeaway": parsed.get("takeaway", ""),
            "hook": record.get("hook", ""),
            "post_url": f"blog/{slug}/ep{num:03d}.html" if isinstance(num, int) else "",
        })

    cards.sort(key=lambda c: c["episode"] if isinstance(c["episode"], int) else 0,
               reverse=True)
    return cards[:limit] if limit else cards


def _display_date(value: str) -> str:
    """``2026-09-21`` -> ``Sep 21, 2026``; anything else is passed through.

    The summaries record stores ISO dates and the rest of the site renders
    long form. A card that shows one raw ISO date among long-form siblings
    reads like a bug on a page whose whole job is looking finished.
    """
    from datetime import datetime

    value = (value or "").strip()
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return value
    # Built by hand rather than with %-d, which is a glibc extension and
    # raises on Windows.
    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}"
