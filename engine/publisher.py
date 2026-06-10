"""Publishing helpers for the podcast generation pipeline.

Provides:
  - update_rss_feed(): feedgen-based RSS feed creation/update with episode dedup
  - get_next_episode_number(): find the highest existing episode and return +1
  - save_summary_to_github_pages(): append episode summary to JSON for GitHub Pages
  - post_to_x(): post a tweet via tweepy (accepts credentials as params)
  - notify_directories(): ping podcast directories after feed update
  - generate_episode_thumbnail(): simple PIL-based thumbnail overlay
"""

import datetime
import fcntl
import json
import os
import logging
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Analytics prefix
# ---------------------------------------------------------------------------

def apply_op3_prefix(url: str, prefix_url: str = "https://op3.dev/e/") -> str:
    """Prepend the OP3 analytics prefix to an audio URL.

    For HTTPS URLs, the ``https://`` scheme is stripped before prepending.
    For HTTP URLs, the full original URL (with scheme) is appended.

    Example::

        >>> apply_op3_prefix("https://cdn.example.com/ep1.mp3")
        'https://op3.dev/e/cdn.example.com/ep1.mp3'
    """
    if url.startswith("https://"):
        return prefix_url + url[len("https://"):]
    if url.startswith("http://"):
        return prefix_url + url
    return prefix_url + url


# ---------------------------------------------------------------------------
# RSS feed helpers
# ---------------------------------------------------------------------------

def _markdown_to_rss_html(md: str) -> str:
    """Convert podcast-script markdown to lightly-formatted HTML
    suitable for ``<description>`` and ``<itunes:summary>``.

    Apple Podcasts and Spotify render the description with limited
    HTML support: paragraph wrapping, bold, italic, links, line breaks.
    They render markdown *literally* — `**HOOK:**` shows as
    asterisks, `## Top 10 News Items` shows as hash signs, which
    looks broken to anyone browsing on a podcast app. Operator caught
    this on the May 6 2026 audit (every show ships markdown into RSS).

    This helper:
      - strips block-level markdown (`#`, `>`, list markers)
      - converts inline `**bold**` → `<b>`, `*italic*` → `<i>`
      - converts `[label](url)` → `<a href="url">label</a>`
      - preserves paragraph structure (blank lines → `</p><p>`)
      - leaves bare URLs and ordinary punctuation alone

    Idempotent: HTML in, HTML out (the only inline-markdown patterns
    we replace don't appear inside attributes that we generate).
    """
    if not md:
        return ""
    import re as _re
    from engine.utils import strip_speech_tags as _strip_tags

    # Defense-in-depth: strip Grok TTS speech tags (``[breath]``,
    # ``<emphasis>``, etc.) before anything reaches Apple Podcasts /
    # Spotify show notes. The podcast script intentionally carries
    # these for the TTS path; readers should see clean prose.
    text = _strip_tags(md).strip()

    # Strip block-level headers and blockquotes; keep the text content.
    text = _re.sub(r"^[ \t]*#{1,6}[ \t]+", "", text, flags=_re.MULTILINE)
    text = _re.sub(r"^[ \t]*>[ \t]?", "", text, flags=_re.MULTILINE)
    # Convert list markers to bullet points (· keeps it readable in plain
    # podcast-app contexts that don't render <ul>).
    text = _re.sub(r"^[ \t]*[-*][ \t]+", "• ", text, flags=_re.MULTILINE)
    text = _re.sub(r"^[ \t]*\d+\.[ \t]+", "", text, flags=_re.MULTILINE)

    # Strip horizontal-rule markdown (━━━ runs and `---` lines).
    text = _re.sub(r"^[ \t]*[-—━_]{3,}[ \t]*$", "", text, flags=_re.MULTILINE)

    # Markdown links → real anchors.
    text = _re.sub(
        r"\[([^\]]+)\]\((https?://[^\)]+)\)",
        r'<a href="\2">\1</a>',
        text,
    )
    # Bold / italic. Order matters — handle ** before * so bold doesn't
    # eat the italic markers.
    text = _re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", text)
    text = _re.sub(
        r"(?<![*\w])\*([^*\n]+)\*(?!\w)",
        r"<i>\1</i>",
        text,
    )

    # Strip stray remaining single-asterisk artifacts (operator-caught:
    # malformed bold pairs left odd ``*`` characters in feed previews).
    text = text.replace("**", "")

    # Paragraph wrap. Collapse 3+ blank lines to 2, then split on \n\n.
    text = _re.sub(r"\n{3,}", "\n\n", text)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "\n\n".join(paragraphs)


def build_show_notes_footer(
    base_url: str,
    show_slug: str,
    episode_num: int,
    *,
    has_blog: bool,
    blog_path_prefix: str = "blog",
) -> str:
    """Build the website + per-episode blog-post footer appended to an RSS
    episode description, so listeners on Apple / Spotify / Amazon / YouTube
    can click back to the site for the full transcript and sources.

    Returns markdown (rendered to ``<a>`` anchors by
    :func:`_markdown_to_rss_html`):

      - a per-episode blog link (full show notes / transcript / sources) when
        ``has_blog`` is true (the show actually publishes a blog page for this
        episode — i.e. it is in ``NETWORK_SHOWS``), and
      - always the network home-page link.

    Returns ``""`` when ``base_url`` is empty so callers can append
    unconditionally without emitting a dangling footer.
    """
    site = (base_url or "").rstrip("/")
    if not site:
        return ""
    parts: list[str] = []
    if has_blog and show_slug:
        blog_url = (
            f"{site}/{blog_path_prefix.strip('/')}/{show_slug}/ep{episode_num:03d}.html"
        )
        parts.append(
            "📝 Full show notes, transcript & sources: "
            f"[read the episode page]({blog_url})"
        )
    domain = site.split("//", 1)[-1]
    parts.append(
        "🌐 Part of the Nerra Network — explore every show at "
        f"[{domain}]({site})."
    )
    return "\n\n".join(parts)


def _add_existing_entry_to_feed(fg, ep_data: dict, channel_image: str = "") -> None:
    """Re-add a parsed existing episode to the feed generator."""
    entry = fg.add_entry()
    entry.id(ep_data.get("guid", ""))
    entry.title(ep_data.get("title", ""))
    entry.description(ep_data.get("description", ""))

    if ep_data.get("pubDate"):
        try:
            if isinstance(ep_data["pubDate"], datetime.datetime):
                entry.pubDate(ep_data["pubDate"])
            else:
                entry.pubDate(parsedate_to_datetime(ep_data["pubDate"]))
        except Exception:
            pass

    if ep_data.get("enclosure"):
        enc = ep_data["enclosure"]
        entry.enclosure(
            url=enc.get("url", ""),
            type=enc.get("type", "audio/mpeg"),
            length=enc.get("length", "0"),
        )

    if ep_data.get("itunes_title"):
        entry.podcast.itunes_title(ep_data["itunes_title"])
    if ep_data.get("itunes_summary"):
        entry.podcast.itunes_summary(ep_data["itunes_summary"])
    if ep_data.get("itunes_duration"):
        entry.podcast.itunes_duration(ep_data["itunes_duration"])
    if ep_data.get("itunes_episode"):
        entry.podcast.itunes_episode(ep_data["itunes_episode"])
    if ep_data.get("itunes_season"):
        entry.podcast.itunes_season(ep_data["itunes_season"])
    if ep_data.get("itunes_episode_type"):
        entry.podcast.itunes_episode_type(ep_data["itunes_episode_type"])
    entry.podcast.itunes_explicit("no")
    if channel_image:
        entry.podcast.itunes_image(channel_image)


def _add_new_episode(
    fg,
    new_guid: str,
    episode_title: str,
    episode_description: str,
    episode_date: datetime.date,
    episode_num: int,
    mp3_filename: str,
    mp3_duration: float,
    mp3_path: Path,
    base_url: str,
    audio_subdir: str,
    audio_url: str,
    channel_image: str,
    format_duration_func,
) -> None:
    """Add the new episode entry to the feed generator."""
    entry = fg.add_entry()
    entry.id(new_guid)
    entry.title(episode_title)
    # Render the markdown digest to lightweight HTML before publishing
    # so Apple Podcasts / Spotify don't show literal ``**`` and ``##``
    # to listeners (operator caught this on May 6 2026 audit).
    rss_description = _markdown_to_rss_html(episode_description)
    entry.description(rss_description)

    if audio_url:
        mp3_url = audio_url
    else:
        mp3_url = f"{base_url}/{audio_subdir}/{mp3_filename}"
    entry.link(href=mp3_url)

    pub_date = datetime.datetime.combine(
        episode_date,
        datetime.time(8, 0, 0),
        tzinfo=datetime.timezone.utc,
    )
    entry.pubDate(pub_date)

    mp3_size = mp3_path.stat().st_size if mp3_path.exists() else 0
    entry.enclosure(url=mp3_url, type="audio/mpeg", length=str(mp3_size))

    entry.podcast.itunes_title(episode_title)
    entry.podcast.itunes_summary(rss_description)
    entry.podcast.itunes_duration(format_duration_func(mp3_duration))
    entry.podcast.itunes_episode(str(episode_num))
    entry.podcast.itunes_season("1")
    entry.podcast.itunes_episode_type("full")
    entry.podcast.itunes_explicit("no")
    if channel_image:
        entry.podcast.itunes_image(channel_image)


# ---------------------------------------------------------------------------
# RSS feed update
# ---------------------------------------------------------------------------

def update_rss_feed(
    rss_path: Path,
    episode_num: int,
    episode_title: str,
    episode_description: str,
    episode_date: datetime.date,
    mp3_filename: str,
    mp3_duration: float,
    mp3_path: Path,
    *,
    base_url: str = "https://nerranetwork.com",
    audio_url: Optional[str] = None,
    audio_subdir: str = "digests",
    channel_title: str = "Podcast",
    channel_link: str = "https://example.com",
    channel_description: str = "A podcast.",
    channel_language: str = "en-us",
    channel_author: str = "Patrick",
    channel_email: str = "contact@example.com",
    channel_image: str = "",
    channel_category: str = "Technology",
    channel_subcategory: str = "",
    channel_keywords: str = "",
    guid_prefix: str = "podcast",
    format_duration_func=None,
    chapters_url: Optional[str] = None,
    transcript_url: Optional[str] = None,
    funding_url: str = "",
    funding_label: str = "Support the show — free newsletter",
    person_name: str = "",
    person_url: str = "",
    person_img: str = "",
) -> Path:
    """Create or update an RSS feed with a new episode.

    Parses any existing RSS file to preserve previous episodes, deduplicates
    by episode number, adds the new episode, and writes back via feedgen.

    Parameters
    ----------
    rss_path:
        Path to the ``.rss`` file.
    episode_num, episode_title, episode_description, episode_date:
        Metadata for the new episode.
    mp3_filename:
        Filename of the audio file (used to build the enclosure URL).
    mp3_duration:
        Duration of the audio in seconds.
    mp3_path:
        Local path to the MP3 (used to read file size).
    base_url:
        GitHub raw content base URL.
    audio_url:
        If provided, used as the enclosure URL directly (e.g. from R2).
    audio_subdir:
        Subdirectory under *base_url* where audio lives (default ``"digests"``).
    channel_*:
        RSS channel-level metadata.
    guid_prefix:
        Prefix for episode GUID strings.
    format_duration_func:
        Optional callable ``(float) -> str`` for formatting duration.
        If ``None``, a simple ``HH:MM:SS`` formatter is used.

    Returns
    -------
    Path
        The *rss_path* that was written.
    """
    from feedgen.feed import FeedGenerator

    if format_duration_func is None:
        from engine.audio import format_duration
        format_duration_func = format_duration

    fg = FeedGenerator()
    fg.load_extension("podcast")

    # --- Parse existing episodes -------------------------------------------
    existing_episodes = []
    if rss_path.exists():
        try:
            tree = ET.parse(str(rss_path))
            root = tree.getroot()
            channel = root.find("channel")
            if channel is not None:
                for item in channel.findall("item"):
                    ep_data: dict = {}
                    for elem in item:
                        tag = elem.tag
                        if tag == "title":
                            ep_data["title"] = elem.text or ""
                        elif tag == "description":
                            ep_data["description"] = elem.text or ""
                        elif tag == "guid" and elem.text:
                            ep_data["guid"] = elem.text.strip()
                        elif tag == "pubDate":
                            ep_data["pubDate"] = elem.text or ""
                        elif tag == "enclosure":
                            ep_data["enclosure"] = {
                                "url": elem.get("url", ""),
                                "type": elem.get("type", "audio/mpeg"),
                                "length": elem.get("length", "0"),
                            }
                        elif tag == "{http://www.itunes.com/dtds/podcast-1.0.dtd}episode":
                            ep_data["itunes_episode"] = elem.text or ""
                        elif tag == "{http://www.itunes.com/dtds/podcast-1.0.dtd}duration":
                            ep_data["itunes_duration"] = elem.text or ""
                        elif tag == "{http://www.itunes.com/dtds/podcast-1.0.dtd}title":
                            ep_data["itunes_title"] = elem.text or ""
                        elif tag == "{http://www.itunes.com/dtds/podcast-1.0.dtd}summary":
                            ep_data["itunes_summary"] = elem.text or ""
                        elif tag == "{http://www.itunes.com/dtds/podcast-1.0.dtd}season":
                            ep_data["itunes_season"] = elem.text or ""
                        elif tag == "{http://www.itunes.com/dtds/podcast-1.0.dtd}episodeType":
                            ep_data["itunes_episode_type"] = elem.text or ""
                        elif tag == "{https://podcastindex.org/namespace/1.0}chapters":
                            # Preserve Podcasting 2.0 chapters URL across
                            # rebuilds. Without this every regen drops the
                            # tag from prior episodes — Apple Podcasts then
                            # shows chapters only on the latest episode.
                            url = elem.get("url", "")
                            if url:
                                ep_data["podcast_chapters_url"] = url
                                ep_data["podcast_chapters_type"] = elem.get(
                                    "type", "application/json+chapters"
                                )
                        elif tag == "{https://podcastindex.org/namespace/1.0}transcript":
                            # Same preservation logic as chapters — the
                            # operator caught Apple Podcasts dropping
                            # transcripts from every TST episode except
                            # the very latest after this regression.
                            url = elem.get("url", "")
                            if url:
                                ep_data["podcast_transcript_url"] = url
                                ep_data["podcast_transcript_type"] = elem.get(
                                    "type", "application/json"
                                )
                                lang = elem.get("language", "")
                                if lang:
                                    ep_data["podcast_transcript_language"] = lang
                    if ep_data.get("guid"):
                        existing_episodes.append(ep_data)
        except Exception as exc:
            # If the file looks like a real RSS with episodes but won't parse,
            # refuse to proceed — silently writing a fresh feed would drop all
            # historical episodes from subscribers' players.
            try:
                raw = rss_path.read_bytes()
            except OSError:
                raw = b""
            if b"<item" in raw or b"itunes:episode" in raw or b"<enclosure" in raw:
                raise RuntimeError(
                    f"Refusing to overwrite unparseable RSS with episode "
                    f"content ({rss_path}): {exc}. Manual review required "
                    f"to avoid wiping subscriber history."
                ) from exc
            logger.warning("Could not parse existing RSS feed: %s", exc)

    # --- Deduplicate by episode number ------------------------------------
    episodes_by_number: dict = {}
    for ep_data in existing_episodes:
        ep_num_str = ep_data.get("itunes_episode", "")
        if not ep_num_str:
            guid = ep_data.get("guid", "")
            match = re.search(r"ep(\d+)", guid)
            if match:
                ep_num_str = match.group(1)
                # Persist the derived number so _add_existing_entry_to_feed
                # re-emits <itunes:episode> on rewrite. Without this, a feed
                # imported without the tag would silently lose it on every
                # write, causing get_next_episode_number to reuse numbers.
                ep_data["itunes_episode"] = ep_num_str
        if ep_num_str:
            try:
                num = int(ep_num_str)
                if num not in episodes_by_number:
                    episodes_by_number[num] = ep_data
                else:
                    # Keep the one with the more recent pubDate (falls back
                    # to GUID suffix if pubDate is missing or unparseable).
                    old_pub = episodes_by_number[num].get("pubDate", "")
                    new_pub = ep_data.get("pubDate", "")
                    if old_pub and new_pub:
                        try:
                            from email.utils import parsedate_to_datetime
                            old_dt = parsedate_to_datetime(old_pub)
                            new_dt = parsedate_to_datetime(new_pub)
                            if new_dt > old_dt:
                                episodes_by_number[num] = ep_data
                            continue
                        except Exception:
                            pass
                    # Fallback: compare GUID timestamps
                    old_guid = episodes_by_number[num].get("guid", "")
                    new_guid = ep_data.get("guid", "")
                    old_ts = old_guid.split("-")[-1] if "-" in old_guid else "000000"
                    new_ts = new_guid.split("-")[-1] if "-" in new_guid else "000000"
                    if new_ts > old_ts:
                        episodes_by_number[num] = ep_data
            except ValueError:
                pass

    # --- Set channel metadata ---------------------------------------------
    fg.title(channel_title)
    fg.description(channel_description)
    fg.language(channel_language)

    # WebSub / PubSubHubbub: declare hub and self links so directories can
    # subscribe to push notifications when the feed is updated.
    rss_self_url = f"{base_url}/{rss_path.name}"
    fg.link(href="https://pubsubhubbub.appspot.com/", rel="hub")
    fg.link(href=rss_self_url, rel="self")
    # Main channel link MUST be set after self/hub links — feedgen uses the
    # last non-rel link for the RSS <link> element.
    fg.link(href=channel_link)
    fg.copyright(f"Copyright {datetime.date.today().year}")
    fg.podcast.itunes_author(channel_author)
    fg.podcast.itunes_summary(channel_description)
    fg.podcast.itunes_owner(name=channel_author, email=channel_email)
    if channel_image:
        fg.podcast.itunes_image(channel_image)
    if channel_subcategory:
        fg.podcast.itunes_category({"cat": channel_category, "sub": channel_subcategory})
    else:
        fg.podcast.itunes_category(channel_category)
    # ``itunes:keywords`` — Apple deprecated but Spotify / Pocket Casts /
    # Fountain / Podcast Index still index it. Cheap SEO. Operator
    # caught (May 6 2026 audit) every show shipping with no keywords.
    if channel_keywords:
        try:
            fg.podcast.itunes_keywords(channel_keywords)
        except Exception:  # pragma: no cover — older feedgen lacks setter
            # Newer feedgen versions also expose the keyword via the
            # generic ``meta`` extension; if both fail, the field is
            # optional anyway.
            pass
    fg.podcast.itunes_explicit("no")

    # --- Migrate legacy GitHub raw URLs to R2 CDN --------------------------
    _GITHUB_RAW_PREFIX = "https://raw.githubusercontent.com/Planetterrian/nerranetwork/main/"
    r2_base = "https://audio.nerranetwork.com"
    migrated_count = 0
    for ep_data in episodes_by_number.values():
        enc = ep_data.get("enclosure", {})
        enc_url = enc.get("url", "")
        if enc_url.startswith(_GITHUB_RAW_PREFIX):
            # Extract filename from old URL path, construct R2 URL
            old_path = enc_url[len(_GITHUB_RAW_PREFIX):]  # e.g. digests/FILE.mp3
            new_url = f"{r2_base}/{old_path}"
            enc["url"] = new_url
            migrated_count += 1
    if migrated_count:
        logger.info("Migrated %d episode URL(s) from GitHub raw to R2 CDN", migrated_count)

    # --- Build new episode metadata ----------------------------------------
    current_time_str = datetime.datetime.now().strftime("%H%M%S%f")
    new_guid = f"{guid_prefix}-ep{episode_num:03d}-{episode_date:%Y%m%d}-{current_time_str}"

    # --- Collect all episodes, then add in descending order ----------------
    # Podcast clients expect the newest episode first in the RSS feed.
    # Remove the episode being replaced, insert the new one, then sort.
    all_episodes: dict[int, dict] = {}
    for ep_num_key, ep_data in episodes_by_number.items():
        if ep_num_key == episode_num:
            logger.info("Replacing existing episode %s with new version", ep_num_key)
            continue
        if ep_data.get("guid") == new_guid:
            continue
        all_episodes[ep_num_key] = ep_data

    # Add existing episodes in descending episode number order (newest first)
    for ep_num_key in sorted(all_episodes.keys(), reverse=True):
        if ep_num_key > episode_num:
            _add_existing_entry_to_feed(fg, all_episodes[ep_num_key], channel_image)

    # --- Add the new episode (inserted at its correct position) -----------
    _add_new_episode(
        fg, new_guid, episode_title, episode_description, episode_date,
        episode_num, mp3_filename, mp3_duration, mp3_path, base_url,
        audio_subdir, audio_url, channel_image, format_duration_func,
    )

    # Add remaining existing episodes (those with lower episode numbers)
    for ep_num_key in sorted(all_episodes.keys(), reverse=True):
        if ep_num_key < episode_num:
            _add_existing_entry_to_feed(fg, all_episodes[ep_num_key], channel_image)

    fg.lastBuildDate(datetime.datetime.now(datetime.timezone.utc))

    # Atomic write: write to temp file, then rename to prevent corruption
    # from concurrent CI matrix jobs or pipeline crashes mid-write.
    import tempfile
    tmp_fd, tmp_path = tempfile.mkstemp(
        suffix=".rss", dir=str(rss_path.parent),
    )
    os.close(tmp_fd)
    try:
        fg.rss_file(tmp_path, pretty=True)

        # Post-process: add Podcasting 2.0 <podcast:chapters> to the new episode
        if chapters_url:
            _inject_chapters_tag(Path(tmp_path), new_guid, chapters_url)

        # Add <podcast:transcript> for Podcasting 2.0 support
        if transcript_url:
            _inject_transcript_tag(Path(tmp_path), new_guid, transcript_url)

        # Re-inject Podcasting 2.0 chapters/transcript tags for every
        # episode the operator already published. ``feedgen`` doesn't
        # know about the ``podcast:`` namespace, so each rebuild
        # silently dropped these tags from prior items — Apple Podcasts
        # then showed transcripts only on the latest episode (regression
        # caught in May 2026 by the operator). Parsed URLs come from the
        # existing-RSS pass at the top of update_rss_feed.
        _reinject_preserved_podcast_tags(
            Path(tmp_path), episodes_by_number, exclude_guid=new_guid,
        )

        # Add <podcast:locked> to prevent unauthorized feed imports
        _inject_podcast_locked_tag(
            Path(tmp_path),
            channel_email or "patrick@planetterrian.com",
        )

        # Add channel-level <podcast:funding> + <podcast:person>
        # (Podcasting 2.0 discovery/support surface; June 2026 growth
        # pass). No-ops when the args are empty so legacy callers are
        # byte-for-byte unaffected.
        _inject_channel_funding_person_tags(
            Path(tmp_path),
            funding_url=funding_url,
            funding_label=funding_label,
            person_name=person_name,
            person_url=person_url,
            person_img=person_img,
        )

        os.replace(tmp_path, str(rss_path))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    # Post-write validation: confirm Podcasting 2.0 tags we just injected
    # survived round-trip. Silent drops here degrade chapter/transcript
    # support on Apple/Overcast/Pocket Casts with no external signal.
    _validate_injected_tags(
        rss_path,
        new_guid,
        chapters_url=chapters_url,
        transcript_url=transcript_url,
        expect_locked=True,
        expect_funding=bool(funding_url),
        expect_person=bool(person_name),
    )

    logger.info("RSS feed updated: %s", rss_path)
    return rss_path


def _validate_injected_tags(
    rss_path: Path,
    new_guid: str,
    *,
    chapters_url: str,
    transcript_url: str,
    expect_locked: bool,
    expect_funding: bool = False,
    expect_person: bool = False,
) -> None:
    """Parse the final RSS and log ERROR if expected Podcasting 2.0 tags are missing."""
    PODCAST_NS = "https://podcastindex.org/namespace/1.0"
    try:
        tree = ET.parse(str(rss_path))
        root = tree.getroot()
        channel = root.find("channel")
        if channel is None:
            logger.error("RSS validation: <channel> missing in %s", rss_path)
            return

        if expect_locked and channel.find(f"{{{PODCAST_NS}}}locked") is None:
            logger.error(
                "RSS validation: <podcast:locked> missing after injection "
                "(%s). Feed imports are not protected.", rss_path,
            )

        if expect_funding and channel.find(f"{{{PODCAST_NS}}}funding") is None:
            logger.error(
                "RSS validation: <podcast:funding> missing after injection "
                "(%s).", rss_path,
            )
        if expect_person and channel.find(f"{{{PODCAST_NS}}}person") is None:
            logger.error(
                "RSS validation: <podcast:person> missing after injection "
                "(%s).", rss_path,
            )

        if chapters_url or transcript_url:
            target_item = None
            for item in channel.findall("item"):
                guid_el = item.find("guid")
                if (
                    guid_el is not None
                    and guid_el.text
                    and guid_el.text.strip() == new_guid
                ):
                    target_item = item
                    break
            if target_item is None:
                logger.error(
                    "RSS validation: new episode <item guid=%s> not found in %s",
                    new_guid, rss_path,
                )
                return
            if chapters_url and target_item.find(f"{{{PODCAST_NS}}}chapters") is None:
                logger.error(
                    "RSS validation: <podcast:chapters> missing for %s after "
                    "injection — chapter markers will not appear in players.",
                    new_guid,
                )
            if transcript_url and target_item.find(f"{{{PODCAST_NS}}}transcript") is None:
                logger.error(
                    "RSS validation: <podcast:transcript> missing for %s after "
                    "injection — transcript links will not appear in players.",
                    new_guid,
                )
    except Exception as exc:
        logger.error("RSS validation pass failed for %s: %s", rss_path, exc)


def _inject_podcast_locked_tag(rss_path: Path, owner_email: str) -> None:
    """Add ``<podcast:locked>`` to the RSS channel element.

    Prevents unauthorized feed imports on supporting platforms.
    Idempotent — skips if the tag already exists.
    """
    PODCAST_NS = "https://podcastindex.org/namespace/1.0"

    try:
        ET.register_namespace("podcast", PODCAST_NS)
        ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        ET.register_namespace("atom", "http://www.w3.org/2005/Atom")

        tree = ET.parse(str(rss_path))
        root = tree.getroot()

        for attr in list(root.attrib):
            if attr == "xmlns:podcast" or (
                attr.startswith("xmlns:") and root.attrib[attr] == PODCAST_NS
            ):
                del root.attrib[attr]

        channel = root.find("channel")
        if channel is None:
            return

        # Skip if already present
        existing = channel.find(f"{{{PODCAST_NS}}}locked")
        if existing is not None:
            return

        locked_el = ET.SubElement(channel, f"{{{PODCAST_NS}}}locked")
        locked_el.set("owner", owner_email)
        locked_el.text = "yes"

        tree.write(str(rss_path), xml_declaration=True, encoding="UTF-8")
        logger.info("Injected <podcast:locked> tag")

    except Exception as exc:
        logger.error("Failed to inject <podcast:locked> tag: %s", exc)


def _inject_channel_funding_person_tags(
    rss_path: Path,
    *,
    funding_url: str = "",
    funding_label: str = "Support the show — free newsletter",
    person_name: str = "",
    person_url: str = "",
    person_img: str = "",
) -> None:
    """Add channel-level ``<podcast:funding>`` + ``<podcast:person>`` tags.

    Podcasting 2.0 surfaces these in supporting apps (Podcast Addict,
    Fountain, Podverse, …): funding renders as a support/subscribe button,
    person feeds host-based discovery and credits. Like the other
    ``podcast:`` tags, feedgen can't emit them, so this post-processes the
    XML on every rebuild (the feed is fully rewritten each episode).

    Idempotent — skips tags that already exist. Empty args are a no-op so
    legacy callers are byte-for-byte unaffected.
    """
    if not funding_url and not person_name:
        return

    PODCAST_NS = "https://podcastindex.org/namespace/1.0"

    try:
        ET.register_namespace("podcast", PODCAST_NS)
        ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        ET.register_namespace("atom", "http://www.w3.org/2005/Atom")

        tree = ET.parse(str(rss_path))
        root = tree.getroot()

        for attr in list(root.attrib):
            if attr == "xmlns:podcast" or (
                attr.startswith("xmlns:") and root.attrib[attr] == PODCAST_NS
            ):
                del root.attrib[attr]

        channel = root.find("channel")
        if channel is None:
            return

        changed = False

        if funding_url and channel.find(f"{{{PODCAST_NS}}}funding") is None:
            funding_el = ET.SubElement(channel, f"{{{PODCAST_NS}}}funding")
            funding_el.set("url", funding_url)
            funding_el.text = funding_label or "Support the show"
            changed = True

        if person_name and channel.find(f"{{{PODCAST_NS}}}person") is None:
            person_el = ET.SubElement(channel, f"{{{PODCAST_NS}}}person")
            person_el.set("role", "host")
            if person_url:
                person_el.set("href", person_url)
            if person_img:
                person_el.set("img", person_img)
            person_el.text = person_name
            changed = True

        if changed:
            tree.write(str(rss_path), xml_declaration=True, encoding="UTF-8")
            logger.info("Injected <podcast:funding>/<podcast:person> tags")

    except Exception as exc:
        logger.error("Failed to inject funding/person tags: %s", exc)


def _inject_chapters_tag(rss_path: Path, guid: str, chapters_url: str) -> None:
    """Add a Podcasting 2.0 ``<podcast:chapters>`` tag to an RSS episode.

    Feedgen doesn't support the ``podcast`` namespace natively, so we
    post-process the XML to insert the tag into the matching ``<item>``.
    """
    PODCAST_NS = "https://podcastindex.org/namespace/1.0"

    try:
        # Register namespace prefixes before parsing so serialization uses
        # clean prefixes and declares xmlns automatically.
        ET.register_namespace("podcast", PODCAST_NS)
        ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        ET.register_namespace("atom", "http://www.w3.org/2005/Atom")

        tree = ET.parse(str(rss_path))
        root = tree.getroot()

        # Remove any manually-set xmlns:podcast attribute to avoid
        # duplicating the declaration that ET.register_namespace handles.
        for attr in list(root.attrib):
            if attr == "xmlns:podcast" or (
                attr.startswith("xmlns:") and root.attrib[attr] == PODCAST_NS
            ):
                del root.attrib[attr]

        # Find the item with the matching GUID
        channel = root.find("channel")
        if channel is None:
            return

        for item in channel.findall("item"):
            guid_el = item.find("guid")
            if guid_el is not None and guid_el.text and guid_el.text.strip() == guid:
                chapters_el = ET.SubElement(item, f"{{{PODCAST_NS}}}chapters")
                chapters_el.set("url", chapters_url)
                chapters_el.set("type", "application/json+chapters")
                break

        tree.write(str(rss_path), xml_declaration=True, encoding="UTF-8")
        logger.info("Injected <podcast:chapters> for %s", guid)

    except Exception as exc:
        logger.error("Failed to inject <podcast:chapters> tag: %s", exc)


def _inject_transcript_tag(rss_path: Path, guid: str, transcript_url: str) -> None:
    """Add a Podcasting 2.0 ``<podcast:transcript>`` tag to an RSS episode."""
    PODCAST_NS = "https://podcastindex.org/namespace/1.0"

    try:
        ET.register_namespace("podcast", PODCAST_NS)
        ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        ET.register_namespace("atom", "http://www.w3.org/2005/Atom")

        tree = ET.parse(str(rss_path))
        root = tree.getroot()

        for attr in list(root.attrib):
            if attr == "xmlns:podcast" or (
                attr.startswith("xmlns:") and root.attrib[attr] == PODCAST_NS
            ):
                del root.attrib[attr]

        channel = root.find("channel")
        if channel is None:
            return

        for item in channel.findall("item"):
            guid_el = item.find("guid")
            if guid_el is not None and guid_el.text and guid_el.text.strip() == guid:
                transcript_el = ET.SubElement(item, f"{{{PODCAST_NS}}}transcript")
                transcript_el.set("url", transcript_url)
                if transcript_url.endswith(".json"):
                    transcript_el.set("type", "application/json")
                else:
                    transcript_el.set("type", "text/plain")
                break

        tree.write(str(rss_path), xml_declaration=True, encoding="UTF-8")
        logger.info("Injected <podcast:transcript> for %s", guid)

    except Exception as exc:
        logger.error("Failed to inject <podcast:transcript> tag: %s", exc)


def _reinject_preserved_podcast_tags(
    rss_path: Path,
    episodes_by_number: dict,
    *,
    exclude_guid: str = "",
) -> None:
    """Walk every parsed episode in *episodes_by_number* and re-emit its
    Podcasting 2.0 ``<podcast:chapters>`` / ``<podcast:transcript>`` tags
    onto the matching ``<item>`` in *rss_path*.

    Single-pass batch version of ``_inject_chapters_tag`` /
    ``_inject_transcript_tag`` so a 100+ episode feed isn't re-parsed
    once per episode. *exclude_guid* skips the episode just published —
    its tags were already injected upstream and re-emitting would
    duplicate them.
    """
    PODCAST_NS = "https://podcastindex.org/namespace/1.0"

    # Build a guid → preserved-tag-data map. Episodes that didn't have
    # the tags in the parsed feed simply contribute no entry, which means
    # nothing happens for them. Skip the just-published episode.
    by_guid: dict = {}
    for ep_data in episodes_by_number.values():
        guid = (ep_data.get("guid") or "").strip()
        if not guid or guid == exclude_guid:
            continue
        chapters_url = ep_data.get("podcast_chapters_url")
        transcript_url = ep_data.get("podcast_transcript_url")
        if not chapters_url and not transcript_url:
            continue
        by_guid[guid] = ep_data

    if not by_guid:
        return

    try:
        ET.register_namespace("podcast", PODCAST_NS)
        ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        ET.register_namespace("atom", "http://www.w3.org/2005/Atom")

        tree = ET.parse(str(rss_path))
        root = tree.getroot()

        # Strip any duplicate xmlns:podcast attributes that ET would
        # otherwise emit twice on serialization.
        for attr in list(root.attrib):
            if attr == "xmlns:podcast" or (
                attr.startswith("xmlns:") and root.attrib[attr] == PODCAST_NS
            ):
                del root.attrib[attr]

        channel = root.find("channel")
        if channel is None:
            return

        injected = 0
        for item in channel.findall("item"):
            guid_el = item.find("guid")
            if guid_el is None or not guid_el.text:
                continue
            ep_data = by_guid.get(guid_el.text.strip())
            if not ep_data:
                continue

            chapters_url = ep_data.get("podcast_chapters_url")
            if chapters_url and item.find(f"{{{PODCAST_NS}}}chapters") is None:
                el = ET.SubElement(item, f"{{{PODCAST_NS}}}chapters")
                el.set("url", chapters_url)
                el.set(
                    "type",
                    ep_data.get(
                        "podcast_chapters_type", "application/json+chapters"
                    ),
                )

            transcript_url = ep_data.get("podcast_transcript_url")
            if transcript_url and item.find(f"{{{PODCAST_NS}}}transcript") is None:
                el = ET.SubElement(item, f"{{{PODCAST_NS}}}transcript")
                el.set("url", transcript_url)
                el.set(
                    "type",
                    ep_data.get("podcast_transcript_type", "application/json"),
                )
                lang = ep_data.get("podcast_transcript_language")
                if lang:
                    el.set("language", lang)

            injected += 1

        tree.write(str(rss_path), xml_declaration=True, encoding="UTF-8")
        logger.info(
            "Re-injected Podcasting 2.0 tags for %d preserved episode(s)",
            injected,
        )

    except Exception as exc:
        logger.error("Failed to re-inject preserved podcast tags: %s", exc)


# ---------------------------------------------------------------------------
# Episode numbering
# ---------------------------------------------------------------------------

def get_next_episode_number(
    rss_path: Path,
    digests_dir: Path,
    mp3_glob_pattern: str = "*_Ep*.mp3",
) -> int:
    """Find the highest existing episode number and return ``max + 1``.

    Checks both the RSS feed (``<itunes:episode>`` tags) and the file
    system (MP3 filenames matching *mp3_glob_pattern*).
    """
    max_episode = 0

    # Check RSS feed
    if rss_path.exists():
        try:
            tree = ET.parse(str(rss_path))
            root = tree.getroot()
            channel = root.find("channel")
            if channel is not None:
                ns = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
                for item in channel.findall("item"):
                    ep_el = item.find(f"{ns}episode")
                    if ep_el is not None and ep_el.text:
                        try:
                            max_episode = max(max_episode, int(ep_el.text))
                            continue
                        except ValueError:
                            pass
                    # Fallback: derive from GUID (e.g. "tesla-ep042-20260419-...").
                    # Without this, a feed entry missing <itunes:episode> is
                    # invisible to numbering and will be silently overwritten
                    # by the next run.
                    guid_el = item.find("guid")
                    if guid_el is not None and guid_el.text:
                        match = re.search(r"ep(\d+)", guid_el.text)
                        if match:
                            try:
                                max_episode = max(max_episode, int(match.group(1)))
                            except ValueError:
                                pass
        except Exception as exc:
            # Refuse to restart numbering when an RSS with real episode
            # content won't parse — doing so would overwrite Ep 1's audio
            # in R2 and dupe GUIDs for every subscriber.
            try:
                raw = rss_path.read_bytes()
            except OSError:
                raw = b""
            if b"<item" in raw or b"itunes:episode" in raw:
                raise RuntimeError(
                    f"Refusing to compute next episode number from "
                    f"unparseable RSS with episode content ({rss_path}): "
                    f"{exc}. Manual review required."
                ) from exc
            logger.warning("Could not parse RSS feed for episode number: %s", exc)

    # Scan MP3 filenames
    for mp3_file in digests_dir.glob(mp3_glob_pattern):
        match = re.search(r"Ep(\d+)", mp3_file.name)
        if match:
            try:
                max_episode = max(max_episode, int(match.group(1)))
            except ValueError:
                pass

    next_ep = max_episode + 1
    logger.info("Next episode number: %d (highest existing: %d)", next_ep, max_episode)
    return next_ep


# ---------------------------------------------------------------------------
# GitHub Pages summary saving
# ---------------------------------------------------------------------------

def save_summary_to_github_pages(
    summary_text: str,
    summaries_json_path: Path,
    podcast_name: str,
    *,
    episode_num: Optional[int] = None,
    episode_title: Optional[str] = None,
    audio_url: Optional[str] = None,
    rss_url: Optional[str] = None,
    max_summaries: int = 30,
) -> Optional[Path]:
    """Append an episode summary to the GitHub Pages JSON file.

    The file stores the most recent *max_summaries* entries (newest first).
    Returns the path to the JSON file on success, ``None`` on error.
    """
    try:
        now = datetime.datetime.now()
        entry = {
            "date": now.strftime("%Y-%m-%d"),
            "datetime": now.isoformat(),
            "content": summary_text,
            "episode_num": episode_num,
            "episode_title": episode_title,
            "audio_url": audio_url,
            "rss_url": rss_url,
        }

        if summaries_json_path.exists():
            # Atomic read-modify-write under a single exclusive lock to
            # prevent data loss if another process writes concurrently.
            with open(summaries_json_path, "r+", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    data = json.load(f)
                    # Handle malformed files (e.g. bare array instead of wrapped object)
                    if not isinstance(data, dict) or "summaries" not in data:
                        existing = data if isinstance(data, list) else []
                        data = {"podcast": podcast_name, "summaries": existing}
                    data["summaries"].insert(0, entry)
                    data["summaries"] = data["summaries"][:max_summaries]
                    f.seek(0)
                    f.truncate()
                    json.dump(data, f, indent=2, ensure_ascii=False)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        else:
            data = {"podcast": podcast_name, "summaries": [entry]}
            data["summaries"] = data["summaries"][:max_summaries]
            with open(summaries_json_path, "w", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        logger.info("Summary saved to GitHub Pages JSON: %s", summaries_json_path)
        return summaries_json_path

    except Exception as exc:
        logger.error("Failed to save summary to GitHub Pages: %s", exc)
        return None


# ---------------------------------------------------------------------------
# X / Twitter posting
# ---------------------------------------------------------------------------

def _describe_x_error(exc: Exception) -> str:
    """Build a detailed, single-line description of a tweepy / X API error.

    tweepy's ``HTTPException`` subclasses (``Forbidden`` / ``Unauthorized`` /
    ``TooManyRequests`` / …) carry the X API's structured error detail on
    ``.api_messages`` / ``.api_codes`` / ``.api_errors`` and the raw response
    body on ``.response.text``. A bare ``str(exc)`` is often just
    ``"403 Forbidden"``, which hides *why* X refused — duplicate content, an
    app without write permission, or a free-tier posting cap are all 403s
    with very different fixes. Surface whatever detail is available.

    Best-effort — never raises (it runs inside an error handler).
    """
    parts = [f"{type(exc).__name__}: {exc}"]
    try:
        for attr in ("api_codes", "api_messages", "api_errors"):
            val = getattr(exc, attr, None)
            if val:
                parts.append(f"{attr}={val}")
        resp = getattr(exc, "response", None)
        body = getattr(resp, "text", None) if resp is not None else None
        if body:
            parts.append(f"body={str(body)[:500]}")
    except Exception:  # noqa: BLE001 — diagnostics must never raise
        pass
    return " | ".join(parts)


def post_to_x(
    text: str,
    *,
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
) -> Optional[str]:
    """Post a tweet and return the tweet URL, or ``None`` on failure.

    Credentials are accepted as explicit parameters so the caller (or
    config system) decides which env vars to read.
    """
    try:
        import tweepy

        client = tweepy.Client(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        response = client.create_tweet(text=text)
        tweet_id = response.data["id"]
        tweet_url = f"https://x.com/i/status/{tweet_id}"
        logger.info("Tweet posted: %s", tweet_url)
        return tweet_url

    except Exception as exc:
        # Surface the X API's structured reason (duplicate content vs.
        # missing app write-permission vs. free-tier cap are all 403s).
        logger.error("X post failed: %s", _describe_x_error(exc))
        return None


# ---------------------------------------------------------------------------
# Directory notifications (WebSub / PubSubHubbub, Podcast Index, Ping-O-Matic)
# ---------------------------------------------------------------------------

def notify_directories(rss_url: str, show_name: str = "Podcast") -> dict:
    """Notify podcast directories that a feed has been updated.

    Called after a new episode is published and the RSS feed is regenerated.
    All pings are best-effort — failures are logged but never raise.

    Returns a dict of ``{service_name: success_bool}`` results.
    """
    import requests

    results = {}

    # 1. PubSubHubbub / WebSub — used by Google Podcasts, Podcast Index, etc.
    try:
        resp = requests.post(
            "https://pubsubhubbub.appspot.com/",
            data={"hub.mode": "publish", "hub.url": rss_url},
            timeout=15,
        )
        results["pubsubhubbub"] = resp.status_code == 204
        if resp.status_code == 204:
            logger.info("[%s] PubSubHubbub notified successfully", show_name)
        else:
            logger.warning("[%s] PubSubHubbub returned %s", show_name, resp.status_code)
    except Exception as e:
        logger.warning("[%s] PubSubHubbub notification failed: %s", show_name, e)
        results["pubsubhubbub"] = False

    # 2. Podcast Index — historically pinged directly via
    # ``api.podcastindex.org/api/1.0/hub/pubnotify``, but Podcast Index
    # deprecated that endpoint in favour of relying on the WebSub hub
    # (Step 1 above already notifies Google's pubsubhubbub.appspot.com,
    # which Podcast Index subscribes to). The direct call now returns
    # HTTP 403 on every run — see TST Ep465 log (May 6 2026) and
    # countless prior episodes. Skipping the direct call removes the
    # noise; Podcast Index still picks up the feed via WebSub
    # (typically within minutes of PubSubHubbub publish).
    results["podcast_index"] = "via_websub"

    # 3. Ping-O-Matic — notifies multiple blog/podcast search engines at once
    try:
        import xmlrpc.client
        server = xmlrpc.client.ServerProxy("http://rpc.pingomatic.com/")
        resp = server.weblogUpdates.ping(show_name, rss_url)
        results["pingomatic"] = resp.get("flerror", True) is False
        if results["pingomatic"]:
            logger.info("[%s] Ping-O-Matic notified successfully", show_name)
        else:
            logger.warning("[%s] Ping-O-Matic reported error: %s", show_name, resp)
    except Exception as e:
        logger.warning("[%s] Ping-O-Matic notification failed: %s", show_name, e)
        results["pingomatic"] = False

    successes = sum(1 for v in results.values() if v)
    logger.info("[%s] Directory notifications: %s/%s succeeded", show_name, successes, len(results))

    return results


# ---------------------------------------------------------------------------
# Episode thumbnail
# ---------------------------------------------------------------------------

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:\\Windows\\Fonts\\arialbd.ttf",
)


def _load_font(size: int):
    """Return a usable bold sans-serif font at the requested size.

    Tries DejaVu Sans Bold (shipped on Ubuntu / GitHub Actions runners
    by default) first, then falls back through common platform-specific
    paths, then PIL's default bitmap font.
    """
    from PIL import ImageFont

    for candidate in _FONT_CANDIDATES:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except (IOError, OSError):
                continue
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int) -> list:
    """Greedy word-wrap that respects the rendered pixel width."""
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = font.getbbox(candidate)
        width = bbox[2] - bbox[0]
        if width <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_episode_thumbnail(
    base_image_path: Path,
    episode_num: int,
    date_str: str,
    output_path: Path,
    *,
    hook: str = "",
    show_name: str = "",
    size: tuple = (1280, 720),
) -> tuple[Path, int | None]:
    """Returns (thumbnail_path, hook_font_size_used or None)."""
    """Render an episode thumbnail by overlaying text on the show cover.

    Output is a JPEG at YouTube's recommended 1280x720 thumbnail spec by
    default. The cover is scaled-and-cropped to fill the frame, darkened
    for legibility, then overlaid with the show name (top-left), the
    headline ``hook`` (large, centred), and an "Ep N — date" footer.

    Parameters
    ----------
    base_image_path:
        Source cover image (e.g. ``assets/covers/<show>.jpg``).
    episode_num:
        Episode number for the footer line.
    date_str:
        Pre-formatted date string for the footer line.
    output_path:
        Output file path. Suffix ``.jpg``/``.jpeg`` writes JPEG (what
        YouTube prefers); anything else writes PNG.
    hook:
        Optional one-line headline. Wrapped to fit and rendered as the
        dominant text. When empty, only the show name + footer appear.
    show_name:
        Optional small label rendered top-left.
    size:
        Output ``(width, height)`` in pixels.
    """
    from PIL import Image, ImageDraw, ImageEnhance

    width, height = size
    img = Image.open(base_image_path).convert("RGB")

    # Scale-and-crop the cover to fill the output frame (no letterboxing).
    src_ratio = img.width / img.height
    dst_ratio = width / height
    if src_ratio > dst_ratio:
        new_h = height
        new_w = int(round(height * src_ratio))
    else:
        new_w = width
        new_h = int(round(width / src_ratio))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    img = img.crop((left, top, left + width, top + height))

    # Darken so white text reads cleanly.
    img = ImageEnhance.Brightness(img).enhance(0.55)

    draw = ImageDraw.Draw(img)
    margin = max(32, width // 32)

    if show_name:
        label_font = _load_font(max(28, width // 32))
        draw.text((margin, margin), show_name, font=label_font,
                  fill=(255, 255, 255))

    if hook:
        clean_hook = hook.strip()
        # Safety cap — anything longer than 220 chars is almost
        # certainly an LLM run-on; truncate to keep the auto-fit loop
        # from producing illegible 5-line micro-text on a thumbnail.
        # The hook is also the first paragraph of the script; the
        # extra context is preserved on the actual show notes / RSS.
        if len(clean_hook) > 220:
            clean_hook = clean_hook[:217].rstrip() + "…"
        # Auto-shrink-to-fit. Operator caught (May 2026) hooks like
        # "Tesla is hiring engineers to build a wireless Battery
        # Management System for Cybercab that removes heavy wiring"
        # rendering as 5+ lines on Shorts (1080×1920) and clipping
        # against the top of the safe area at the legacy fixed
        # 77 px size. Instead of clipping or hard-truncating mid-word,
        # we shrink the font until the wrapped block fits inside the
        # text-safe area (60 % of frame height — leaves room for the
        # show label at top and the footer at bottom). The descent
        # cap on font size also keeps the smallest legible reading
        # at ~32 px which is readable on a phone preview thumbnail.
        max_text_width = width - 2 * margin
        # Leave 20 % top + 20 % bottom for show label / footer breathing
        # room. The hook block can fill the central 60 %.
        max_block_h = int(height * 0.60)
        max_lines = 4 if height >= width else 3
        # Try sizes from the YouTube-preferred large size all the way
        # down to a hard floor. The fall-through floor (32 px) is set
        # so even on a runaway-long hook the text is still readable
        # on a 320-px-wide YouTube mobile preview tile.
        max_font = max(56, width // 14)
        min_font = max(32, width // 24)
        font_size = max_font
        lines: list = []
        line_h = 0
        while font_size >= min_font:
            hook_font = _load_font(font_size)
            lines = _wrap_text(clean_hook, hook_font, max_text_width)
            ascent_descent = hook_font.getbbox("Ay")
            line_h = (ascent_descent[3] - ascent_descent[1]) + 12
            block_h = line_h * len(lines)
            if block_h <= max_block_h and len(lines) <= max_lines:
                break
            # Shrink by 8 px per pass — fine-grained enough to find a
            # good fit without spending many PIL renders on a single
            # thumbnail (hot path during YouTube publish).
            font_size -= 8
        else:
            # We hit the floor and still don't fit. Render at the
            # floor; visual review will catch any pathological case
            # and the operator can hand-edit the hook in the YAML
            # rather than ship a bad thumbnail.
            hook_font = _load_font(min_font)
            lines = _wrap_text(clean_hook, hook_font, max_text_width)
            ascent_descent = hook_font.getbbox("Ay")
            line_h = (ascent_descent[3] - ascent_descent[1]) + 12
        block_h = line_h * len(lines)
        y = (height - block_h) // 2
        for line in lines:
            bbox = hook_font.getbbox(line)
            line_w = bbox[2] - bbox[0]
            x = (width - line_w) // 2
            draw.text((x, y), line, font=hook_font, fill=(255, 255, 255))
            y += line_h

    footer_font = _load_font(max(28, width // 32))
    footer = f"Ep {episode_num} — {date_str}" if date_str else f"Ep {episode_num}"
    footer_bbox = footer_font.getbbox(footer)
    footer_h = footer_bbox[3] - footer_bbox[1]
    draw.text((margin, height - margin - footer_h), footer,
              font=footer_font, fill=(255, 255, 255))

    suffix = output_path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        img.save(output_path, "JPEG", quality=88, optimize=True)
    else:
        img.save(output_path, "PNG")
    # Return the final hook font size used by autofit so callers can record
    # the decision for observability of the May 2026 thumbnail improvements.
    final_hook_font = font_size if 'font_size' in locals() else None
    return output_path, final_hook_font


def generate_shorts_thumbnail(
    base_image_path: Path,
    episode_num: int,
    date_str: str,
    output_path: Path,
    *,
    hook: str = "",
    show_name: str = "",
) -> Path:
    """Render a 1080×1920 vertical thumbnail for YouTube Shorts."""
    return generate_episode_thumbnail(
        base_image_path,
        episode_num,
        date_str,
        output_path,
        hook=hook,
        show_name=show_name,
        size=(1080, 1920),
    )


def generate_shorts_end_card(
    long_form_thumbnail_path: Path,
    output_path: Path,
    *,
    show_name: str = "",
    main_text: str = "WATCH FULL EPISODE",
    sub_text: str = "Tap Subscribe ↗",
    size: tuple = (1080, 1920),
) -> Path:
    """Render the 1080×1920 PNG end-card overlay for a Shorts MP4.

    The drawn card composites the long-form 1280×720 thumbnail into
    the upper third of a dark vertical frame, then layers a big
    headline ("WATCH FULL EPISODE") + cyan sub-line ("Tap Subscribe
    ↗") + a small ``nerranetwork.com`` footer below it. The output
    is a PNG (transparent background pixels would be wasted — the
    image fills the whole frame), used as an ffmpeg overlay input
    on the Shorts MP4 during the last 3 seconds in
    ``engine.video._short_form_filter_graph``.

    This is the visual upgrade over the drawtext-only end card
    shipped in PR #417: viewers see what the actual long-form
    episode looks like, which is significantly more compelling
    than a text-only "WATCH FULL EPISODE" prompt.

    Falls back to a text-only render when ``long_form_thumbnail_path``
    is missing or fails to load (defensive: thumbnail generation can
    fail upstream and we want the end card to still ship).
    """
    from PIL import Image, ImageDraw

    width, height = size
    # Solid dark background — matches the existing drawtext end card's
    # 78%-opaque black panel but goes full opaque (no need to see the
    # slideshow behind a PNG overlay).
    bg = Image.new("RGB", (width, height), (11, 15, 26))  # --nn-bg

    # Crop the long-form thumbnail into the upper third. Long-form
    # thumbs are 1280×720 (16:9). Scale to 1080 wide → 1080×608.
    # Centre vertically inside a 1080×~720 slot at y≈300..1020.
    thumb_section_top = int(height * 0.16)   # y ≈ 307
    thumb_section_h = int(height * 0.38)     # h ≈ 730
    try:
        thumb = Image.open(long_form_thumbnail_path).convert("RGB")
        # Scale-to-fit (preserve aspect, fit inside thumb_section).
        src_ratio = thumb.width / thumb.height
        target_w = width
        target_h = int(round(target_w / src_ratio))
        if target_h > thumb_section_h:
            target_h = thumb_section_h
            target_w = int(round(target_h * src_ratio))
        thumb = thumb.resize((target_w, target_h), Image.LANCZOS)
        thumb_x = (width - target_w) // 2
        thumb_y = thumb_section_top + (thumb_section_h - target_h) // 2
        bg.paste(thumb, (thumb_x, thumb_y))
        # Subtle 4-px white frame around the thumbnail so it reads as
        # a "tap me" target rather than blending into the background.
        ImageDraw.Draw(bg).rectangle(
            (thumb_x - 4, thumb_y - 4,
             thumb_x + target_w + 4, thumb_y + target_h + 4),
            outline=(255, 255, 255), width=4,
        )
    except (FileNotFoundError, OSError) as exc:
        logger.warning(
            "Shorts end card: long-form thumbnail unavailable (%s) — "
            "rendering text-only card. (%s)",
            long_form_thumbnail_path, exc,
        )
        # No thumbnail to paste — the rest of the card still renders.

    draw = ImageDraw.Draw(bg)

    # Optional show pill at the very top (mirrors the brand pill on
    # the Shorts MP4 above the slideshow).
    if show_name:
        show_font = _load_font(36)
        sw_bbox = show_font.getbbox(show_name)
        show_w = sw_bbox[2] - sw_bbox[0]
        draw.text(
            ((width - show_w) // 2, int(height * 0.07)),
            show_name, font=show_font, fill=(232, 236, 244),
        )

    # Main CTA headline — same fontsize as the drawtext end card so
    # the visual jump from PNG → drawtext fallback isn't jarring.
    main_y = int(height * 0.62)
    main_font = _load_font(88)
    mw_bbox = main_font.getbbox(main_text)
    main_w = mw_bbox[2] - mw_bbox[0]
    main_x = (width - main_w) // 2
    # Subtle drop shadow + outline for legibility on the dark BG.
    draw.text((main_x + 3, main_y + 3), main_text, font=main_font,
              fill=(0, 0, 0))
    draw.text((main_x, main_y), main_text, font=main_font,
              fill=(255, 255, 255))

    # Sub-line in Nerra cyan (#00D4FF) — matches the per-word caption
    # highlight from PR #415 + the drawtext sub-line from PR #417.
    sub_y = int(height * 0.74)
    sub_font = _load_font(56)
    sw2_bbox = sub_font.getbbox(sub_text)
    sub_w = sw2_bbox[2] - sw2_bbox[0]
    sub_x = (width - sub_w) // 2
    draw.text((sub_x + 2, sub_y + 2), sub_text, font=sub_font,
              fill=(0, 0, 0))
    draw.text((sub_x, sub_y), sub_text, font=sub_font,
              fill=(0, 212, 255))

    # Footer with the network URL — small + muted so it doesn't
    # compete with the CTA above. Sits clear of the Shorts URL pill
    # at y≈1820 by living at y≈1870.
    footer_y = int(height * 0.93)
    footer_font = _load_font(32)
    footer_text = "nerranetwork.com"
    fw_bbox = footer_font.getbbox(footer_text)
    footer_w = fw_bbox[2] - fw_bbox[0]
    draw.text(
        ((width - footer_w) // 2, footer_y),
        footer_text, font=footer_font, fill=(139, 143, 174),  # --nn-text-muted
    )

    bg.save(output_path, format="PNG", optimize=True)
    return output_path


# ---------------------------------------------------------------------------
# Digest formatting for X posting
# ---------------------------------------------------------------------------

def format_digest_for_x(digest: str) -> str:
    """Format a digest for X posting by stripping markdown formatting.

    Removes headers, bold markers, and markdown link syntax while preserving
    the actual content text and URLs. Suitable for shows with simple formatting
    needs (FF, PT). For TST's emoji-rich version, use ``format_tst_digest_for_x``.
    """
    formatted = digest

    # Remove markdown headers but keep text
    formatted = re.sub(r'^#+\s+', '', formatted, flags=re.MULTILINE)

    # Convert markdown bold to plain text
    formatted = re.sub(r'\*\*(.*?)\*\*', r'\1', formatted)

    # Extract URLs from markdown links
    formatted = re.sub(r'\[([^\]]+)\]\((https?://[^\)]+)\)', r'\2', formatted)

    # Remove excessive blank lines
    formatted = re.sub(r'\n{3,}', '\n\n', formatted)

    return formatted.strip()


def format_tst_digest_for_x(digest: str, *, max_chars: int = 25000) -> str:
    """Format a Tesla Shorts Time digest for X with emojis and visual polish.

    Uses a structured pipeline approach instead of ad-hoc regex:
      1. Clean markdown & extract URLs
      2. Apply section header emojis via lookup table
      3. Ensure podcast link
      4. Number news items with emoji bullets
      5. Insert section separators
      6. Strip leaked instruction text
      7. Final cleanup & truncation
    """
    PODCAST_URL = "https://podcasts.apple.com/us/podcast/tesla-shorts-time/id1855142939"
    EMOJI_NUMBERS = [
        "1\ufe0f\u20e3", "2\ufe0f\u20e3", "3\ufe0f\u20e3", "4\ufe0f\u20e3",
        "5\ufe0f\u20e3", "6\ufe0f\u20e3", "7\ufe0f\u20e3", "8\ufe0f\u20e3",
        "9\ufe0f\u20e3", "\U0001f51f",
    ]

    # Section header mapping: (markdown pattern, emoji replacement)
    SECTION_HEADERS = [
        (r"^#{1,3}\s*Tesla Shorts Time\s*$",  "\U0001f697\u26a1 **Tesla Shorts Time**"),
        (r"^#{1,3}\s*Top 10 News Items",       "\U0001f4f0 **Top 10 News Items**"),
        (r"^#{1,3}\s*Tesla X Takeover:?",       "\U0001f399\ufe0f **Tesla X Takeover:**"),
        (r"^#{1,3}\s*Short Spot",               "\U0001f4c9 **Short Spot**"),
        (r"^#{1,3}\s*Short Squeeze",            "\U0001f4c8 **Short Squeeze**"),
        (r"^#{1,3}\s*Daily Challenge",          "\U0001f4aa **Daily Challenge**"),
        (r"^#{1,3}\s*First Principles",         "\U0001f9e0 **First Principles**"),
        (r"^#{1,3}\s*Market Movers",            "\U0001f4ca **Market Movers**"),
    ]

    # Metadata line emoji mapping
    METADATA_EMOJIS = [
        (r"\*\*Date:\*\*",                 "\U0001f4c5 **Date:**"),
        (r"\*\*REAL-TIME TSLA price:\*\*", "\U0001f4b0 **REAL-TIME TSLA price:**"),
        (r"\*\*Inspiration Quote:\*\*",    "\u2728 **Inspiration Quote:**"),
    ]

    # Leaked instruction patterns to strip
    INSTRUCTION_PATTERNS = [
        r"\U0001f3af\s*TODAY'S FOCUS:.*",
        r"\*\*TOP 5 TESLA X POSTS FROM.*?:\*\*",
        r"Using your knowledge.*",
        r"For each post:.*",
        r"\(use actual post URLs.*?\)",
        r"\(if you can find them.*?\)",
        r"\(format as shown\)",
        r"\*\*OVERALL WEEKLY SENTIMENT.*?:\*\*",
        r"Provide a.*?summary.*",
        r"Is the sentiment.*",
        r"What are the main topics.*",
        r"What's their perspective.*",
        r"\[Repeat for.*?\]",
        r"\[ACTUAL_POST_ID\]",
        r"\[POST_ID\]",
        r"\U0001f6a8\s*CRITICAL:.*",
        r"CRITICAL:.*?COMPLETELY (?:DIFFERENT|NEW).*",
        r"Use (?:a )?DIFFERENT.*",
        r"(?:Avoid|Do NOT|Never) repeat.*",
    ]

    # --- Step 1: Apply section header emojis ---
    text = digest
    for pattern, replacement in SECTION_HEADERS:
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE)

    # --- Step 2: Apply metadata emojis ---
    for pattern, replacement in METADATA_EMOJIS:
        text = re.sub(pattern, replacement, text)

    # --- Step 3: Ensure podcast link ---
    podcast_link_line = f"\U0001f399\ufe0f **Tesla Shorts Time Daily Podcast Link:** {PODCAST_URL}"

    # Remove any malformed/incomplete podcast link lines
    lines = text.split("\n")
    lines = [
        line for line in lines
        if not (
            ("podcast" in line.lower() or "\U0001f399\ufe0f" in line)
            and PODCAST_URL not in line
            and "Tesla X Takeover" not in line  # Don't strip X Takeover section
        )
    ]
    text = "\n".join(lines)

    # Insert podcast link after price line (or date line, or header)
    if PODCAST_URL not in text:
        lines = text.split("\n")
        insert_pos = None
        for i, line in enumerate(lines):
            if "TSLA price" in line or "\U0001f4b0" in line:
                insert_pos = i + 1
                break
            if "Date:" in line and insert_pos is None:
                insert_pos = i + 1
        if insert_pos is None:
            insert_pos = min(2, len(lines))
        lines[insert_pos:insert_pos] = ["", podcast_link_line, ""]
        text = "\n".join(lines)

    # --- Step 4: Number news items with emoji bullets ---
    news_header_match = re.search(
        r"(\U0001f4f0 \*\*Top 10 News Items\*\*.*?)(?=\U0001f4c9|\U0001f399\ufe0f \*\*Tesla X|\u2501\u2501|\Z)",
        text, re.DOTALL,
    )
    if news_header_match:
        section = news_header_match.group(1)
        for i in range(1, 11):
            section = re.sub(
                rf"^(\s*){i}\.\s+",
                lambda m, idx=i: m.group(1) + EMOJI_NUMBERS[idx - 1] + " ",
                section, flags=re.MULTILINE,
            )
        text = text[:news_header_match.start()] + section + text[news_header_match.end():]

    # --- Step 5: Insert section separators ---
    # Add separator before each major section emoji
    section_markers = [
        "\U0001f4f0 **Top 10 News Items**",
        "\U0001f399\ufe0f **Tesla X Takeover:**",
        "\U0001f4c9 **Short Spot**",
        "\U0001f4c8 **Short Squeeze**",
        "\U0001f4aa **Daily Challenge**",
        "\u2728 **Inspiration Quote:**",
        "\U0001f9e0 **First Principles**",
        "\U0001f4ca **Market Movers**",
    ]
    for marker in section_markers:
        if marker in text:
            # Replace any whitespace before the marker with separator
            text = re.sub(
                r"\n\s*\n\s*" + re.escape(marker),
                "\n\n" + "\u2501" * 20 + "\n\n" + marker,
                text,
            )

    # --- Step 6: Strip leaked instruction text ---
    for pattern in INSTRUCTION_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

    # Strip placeholder/dead X URLs
    text = re.sub(r"Post:\s*https?://x\.com/[^\s]+/status/\[[^\]]+\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Post:\s*https?://x\.com/[^\s]+/status/[^\d/][^\s]*", "", text, flags=re.IGNORECASE)

    # --- Step 7: Extract URLs from markdown links ---
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r"\2", text)
    text = re.sub(r"\[(https?://[^\]]+)\]", r"\1", text)
    text = re.sub(r"(https?://x\.com/[^\s\)\]]+)[\)\]]+", r"\1", text)

    # Remove code blocks
    text = re.sub(r"```[^`]*```", "", text, flags=re.DOTALL)

    # --- Step 8: Final cleanup ---
    # Normalize whitespace per line
    lines = text.split("\n")
    lines = ["" if line.strip() == "" else re.sub(r"[ \t]{2,}", " ", line) for line in lines]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Ensure a nice ending — check the last content line (ignoring
    # the podcast link line which is always a URL)
    content_lines = [
        line for line in text.split("\n")
        if line.strip() and PODCAST_URL not in line
    ]
    last_content_char = content_lines[-1].strip()[-1] if content_lines else ""
    if last_content_char not in "!?.":
        last_text = " ".join(content_lines[-3:]).strip()
        if not any(w in last_text.lower() for w in ["feedback", "dm", "accelerating", "electric", "mission"]):
            text += "\n\n\u26a1 Keep accelerating!"

    # Enforce character limit
    if len(text) > max_chars:
        logger.warning("Formatted digest is %d characters, truncating to %d", len(text), max_chars)
        truncate_at = text[:max_chars - 100].rfind("\n\n")
        if truncate_at > max_chars * 0.8:
            text = text[:truncate_at] + "\n\n... (content truncated for length)"
        else:
            text = text[:max_chars - 50] + "\n\n... (truncated for length)"

    return text


# ---------------------------------------------------------------------------
# Scan existing episode MP3 files
# ---------------------------------------------------------------------------

def scan_existing_episodes_from_files(
    digests_dir: Path,
    base_url: str,
    *,
    mp3_glob: str = "*_Ep*_*.mp3",
    filename_pattern: str = r".*_Ep(\d+)_(\d{8})",
    audio_subdir: str = "digests",
    get_audio_duration_func=None,
) -> list:
    """Scan for existing episode MP3 files and return episode data.

    Parameters
    ----------
    digests_dir:
        Directory containing the MP3 files.
    base_url:
        GitHub raw content base URL for constructing download URLs.
    mp3_glob:
        Glob pattern to find MP3 files in *digests_dir*.
    filename_pattern:
        Regex to extract ``(episode_num, date_str)`` groups from filenames.
        The date group is expected in ``%Y%m%d`` format.
    audio_subdir:
        Path segment appended to *base_url* for the episode URL.
    get_audio_duration_func:
        Optional callable ``(Path) -> float`` for reading audio duration.
        Defaults to ``engine.audio.get_audio_duration``.

    Returns
    -------
    list[dict]
        Sorted by episode number (ascending).  Each dict has keys:
        ``episode_num``, ``date``, ``filename``, ``path``, ``size``,
        ``duration``, ``url``.
    """
    if get_audio_duration_func is None:
        from engine.audio import get_audio_duration as _gad
        get_audio_duration_func = _gad

    import datetime as _dt

    episodes: list = []
    compiled_pattern = re.compile(filename_pattern)

    for mp3_file in digests_dir.glob(mp3_glob):
        match = compiled_pattern.match(mp3_file.name)
        if match:
            try:
                ep_num = int(match.group(1))
                date_str = match.group(2)
                episode_date = _dt.datetime.strptime(date_str, "%Y%m%d").date()

                file_size = mp3_file.stat().st_size if mp3_file.exists() else 0
                duration = get_audio_duration_func(mp3_file) or 0.0

                episodes.append({
                    "episode_num": ep_num,
                    "date": episode_date,
                    "filename": mp3_file.name,
                    "path": mp3_file,
                    "size": file_size,
                    "duration": duration,
                    "url": f"{base_url}/{audio_subdir}/{mp3_file.name}",
                })
            except (ValueError, Exception) as exc:
                logger.warning("Could not parse episode from file %s: %s", mp3_file.name, exc)

    return sorted(episodes, key=lambda x: x["episode_num"])


# ---------------------------------------------------------------------------
# Blog RSS feed
# ---------------------------------------------------------------------------

def update_blog_rss(
    rss_path: Path,
    posts: list,
    *,
    channel_title: str = "Blog",
    channel_link: str = "https://nerranetwork.com",
    channel_description: str = "Blog posts from podcast episodes.",
    channel_language: str = "en-us",
    channel_image: str = "",
    base_url: str = "https://nerranetwork.com",
    blog_path_prefix: str = "blog",
    show_slug: str = "",
    sort_by_date: bool = False,
) -> Path:
    """Write a blog RSS feed (no audio enclosures).

    Uses plain XML generation (no feedgen dependency).

    When *sort_by_date* is True, posts are sorted by ``date_obj`` instead
    of ``episode_num``.  Use this for the network-wide aggregated RSS.
    """
    from email.utils import format_datetime as _format_dt
    from xml.sax.saxutils import escape as _esc

    if sort_by_date:
        sorted_posts = sorted(
            posts,
            key=lambda p: p.get("date_obj") or datetime.datetime.min,
            reverse=True,
        )
    else:
        sorted_posts = sorted(posts, key=lambda p: p.get("episode_num", 0), reverse=True)
    entries = sorted_posts[:50]

    items_xml = []
    for post in entries:
        ep_num = post.get("episode_num", 0)
        slug = post.get("show_slug", show_slug)
        blog_url = f"{base_url}/{blog_path_prefix}/{slug}/ep{ep_num:03d}.html"

        title = _esc(post.get("title", f"Episode {ep_num}"))
        description = _esc(post.get("hook", ""))

        pub_date_str = ""
        if not post.get("date_obj"):
            logger.warning("Blog post '%s' (ep%d) missing date — no pubDate in RSS",
                           post.get("title", "?"), post.get("episode_num", 0))
        if post.get("date_obj"):
            dt = post["date_obj"]
            try:
                dt_utc = datetime.datetime(dt.year, dt.month, dt.day,
                                           tzinfo=datetime.timezone.utc)
                pub_date_str = _format_dt(dt_utc, usegmt=True)
            except Exception:
                pass

        item = f"""    <item>
      <title>{title}</title>
      <link>{_esc(blog_url)}</link>
      <guid isPermaLink="true">{_esc(blog_url)}</guid>
      <description>{description}</description>"""
        if pub_date_str:
            item += f"\n      <pubDate>{pub_date_str}</pubDate>"
        item += "\n    </item>"
        items_xml.append(item)

    # Build date for lastBuildDate
    now_str = _format_dt(datetime.datetime.now(datetime.timezone.utc), usegmt=True)

    image_xml = ""
    if channel_image:
        img_url = f"{base_url}/{channel_image}" if not channel_image.startswith("http") else channel_image
        image_xml = f"""
    <image>
      <url>{_esc(img_url)}</url>
      <title>{_esc(channel_title)}</title>
      <link>{_esc(channel_link)}</link>
    </image>"""

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{_esc(channel_title)}</title>
    <link>{_esc(channel_link)}</link>
    <description>{_esc(channel_description)}</description>
    <language>{channel_language}</language>
    <lastBuildDate>{now_str}</lastBuildDate>
    <generator>Nerra Network Blog Generator</generator>
    <atom:link href="{_esc(base_url)}/{_esc(str(rss_path.name))}" rel="self" type="application/rss+xml"/>{image_xml}
{chr(10).join(items_xml)}
  </channel>
</rss>
"""

    rss_path.parent.mkdir(parents=True, exist_ok=True)
    # Scrub lone UTF-16 surrogates the LLM occasionally emits — see
    # engine.utils.strip_lone_surrogates. Without this, a single bad
    # code point in a blog hook would abort RSS feed regeneration.
    from engine.utils import strip_lone_surrogates as _scrub
    rss_path.write_text(_scrub(rss_xml), encoding="utf-8")
    logger.info("Blog RSS written: %s (%d entries)", rss_path, len(entries))
    return rss_path
