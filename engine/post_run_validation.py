"""Post-run validation for the podcast generation pipeline.

Checks that a completed pipeline run produced valid, publishable output:
  - MP3 exists and has reasonable size/duration
  - RSS feed is valid XML with the new episode
  - Digest markdown has content

Called from run_show.py after the pipeline completes.
"""

import logging
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when post-run validation detects a critical issue."""


def validate_mp3(mp3_path: Path, min_bytes: int = 100_000, min_duration: float = 30.0) -> bool:
    """Check that an MP3 file exists, has reasonable size, and minimum duration.

    Parameters
    ----------
    mp3_path:
        Path to the MP3 file.
    min_bytes:
        Minimum file size in bytes (default 100KB — anything smaller
        is likely corrupt or truncated).
    min_duration:
        Minimum duration in seconds (default 30s).

    Returns
    -------
    bool
        True if validation passes, False otherwise.
    """
    if not mp3_path.exists():
        logger.error("MP3 file does not exist: %s", mp3_path)
        return False

    size = mp3_path.stat().st_size
    if size < min_bytes:
        logger.error(
            "MP3 file is suspiciously small (%d bytes < %d minimum): %s",
            size, min_bytes, mp3_path,
        )
        return False

    # Check duration via ffprobe if available
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(mp3_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            if duration < min_duration:
                logger.error(
                    "MP3 duration too short (%.1fs < %.1fs minimum): %s",
                    duration, min_duration, mp3_path,
                )
                return False
            logger.info("MP3 validated: %s (%.1fs, %d bytes)", mp3_path.name, duration, size)
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as exc:
        logger.debug("ffprobe not available or failed: %s — skipping duration check", exc)

    # ffprobe unavailable — size check alone is sufficient
    logger.info("MP3 validated (size only): %s (%d bytes)", mp3_path.name, size)
    return True


def validate_rss(rss_path: Path, expected_episode_num: Optional[int] = None) -> bool:
    """Validate that an RSS feed is well-formed XML and contains expected content.

    Parameters
    ----------
    rss_path:
        Path to the RSS file.
    expected_episode_num:
        If provided, checks that this episode number exists in the feed.

    Returns
    -------
    bool
        True if validation passes.
    """
    if not rss_path.exists():
        logger.error("RSS file does not exist: %s", rss_path)
        return False

    try:
        tree = ET.parse(str(rss_path))
        root = tree.getroot()
    except ET.ParseError as exc:
        logger.error("RSS feed is not valid XML: %s — %s", rss_path, exc)
        return False

    channel = root.find("channel")
    if channel is None:
        logger.error("RSS feed has no <channel> element: %s", rss_path)
        return False

    items = channel.findall("item")
    if not items:
        logger.warning("RSS feed has no episodes: %s", rss_path)
        return True  # Not necessarily an error for a new show

    if expected_episode_num is not None:
        ns = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
        found = False
        for item in items:
            ep_el = item.find(f"{ns}episode")
            if ep_el is not None and ep_el.text:
                try:
                    if int(ep_el.text) == expected_episode_num:
                        found = True
                        break
                except ValueError:
                    pass
        if not found:
            logger.error(
                "RSS feed does not contain expected episode %d: %s",
                expected_episode_num, rss_path,
            )
            return False

    logger.info("RSS validated: %s (%d episodes)", rss_path.name, len(items))
    return True


def _item_sort_key(item) -> tuple:
    """Newest-first ordering key for an RSS <item>: (pubDate epoch,
    itunes:episode). Missing / unparseable values sort as oldest."""
    from email.utils import parsedate_to_datetime
    stamp = 0.0
    pub = item.findtext("pubDate") or ""
    if pub:
        try:
            stamp = parsedate_to_datetime(pub).timestamp()
        except Exception:
            stamp = 0.0
    ep = 0
    ep_text = item.findtext("{http://www.itunes.com/dtds/podcast-1.0.dtd}episode") or ""
    try:
        ep = int(ep_text.strip() or 0)
    except ValueError:
        ep = 0
    return (stamp, ep)


def validate_enclosure_reachability(
    rss_path: Path,
    *,
    sample_count: int = 3,
    timeout: int = 8,
) -> bool:
    """HEAD-check the newest *sample_count* enclosure URLs in an RSS feed.

    Returns True if all checked URLs respond 2xx/3xx, False if any are
    unreachable.  Skips silently if ``requests`` is not installed or if
    the RSS has no enclosures.
    """
    try:
        import requests as _req
    except ImportError:
        logger.debug("requests not installed — skipping enclosure reachability check")
        return True

    try:
        tree = ET.parse(str(rss_path))
    except Exception:
        return True  # malformed RSS is caught by validate_rss; don't double-report

    items = tree.getroot().findall(".//item")
    dated = []  # (sort_key, position, url)
    for pos, item in enumerate(items):
        enc = item.find("enclosure")
        if enc is None:
            continue
        url = enc.get("url", "")
        if not url:
            continue
        dated.append((_item_sort_key(item), pos, url))
    if not dated:
        return True

    headers = {"User-Agent": "NerraPipelineValidator/1.0"}
    all_ok = True
    # Sep 4 2026: pick the NEWEST items by pubDate / itunes:episode, never
    # by document position. The sampler used to take urls[-N:] on the
    # assumption that feeds were oldest-first; once update_rss_feed
    # started serializing newest-first (the feedgen order fix) the tail
    # became the OLDEST three items — Planetterrian Ep011-013 from Dec
    # 2025, whose audio was deleted on purpose — and Ep173 failed
    # post-run validation after publishing cleanly.
    dated.sort(key=lambda t: (t[0], -t[1]), reverse=True)
    sample = [url for _k, _p, url in dated[:sample_count]]
    for url in sample:
        try:
            resp = _req.head(url, headers=headers, timeout=timeout, allow_redirects=True)
            if 200 <= resp.status_code < 400:
                logger.info("Enclosure reachable (%d): %s", resp.status_code, url)
            else:
                logger.error(
                    "Enclosure UNREACHABLE (%d): %s — listeners will get a broken link",
                    resp.status_code, url,
                )
                all_ok = False
        except Exception as exc:
            logger.error("Enclosure UNREACHABLE (error): %s — %s", url, exc)
            all_ok = False

    return all_ok


def validate_digest(digest_text: str, show_name: str, min_chars: int = 200) -> bool:
    """Validate that the digest text is non-empty and has sufficient content.

    Returns
    -------
    bool
        True if validation passes.
    """
    if not digest_text or not digest_text.strip():
        logger.error("Digest is empty for '%s'", show_name)
        return False

    char_count = len(digest_text.strip())
    if char_count < min_chars:
        logger.warning(
            "Digest for '%s' is very short (%d chars, expected >%d)",
            show_name, char_count, min_chars,
        )
        return False

    logger.info("Digest validated: '%s' (%d chars)", show_name, char_count)
    return True


def run_post_validation(
    *,
    mp3_path: Optional[Path] = None,
    rss_path: Optional[Path] = None,
    digest_text: Optional[str] = None,
    show_name: str = "unknown",
    episode_num: Optional[int] = None,
) -> bool:
    """Run all applicable post-run validations.

    Returns True if all checks pass, False if any fail. Logs all
    issues but does not raise — the caller decides how to handle
    validation failures.
    """
    all_passed = True

    if digest_text is not None:
        if not validate_digest(digest_text, show_name):
            all_passed = False

    if mp3_path is not None:
        if not validate_mp3(mp3_path):
            all_passed = False

    if rss_path is not None:
        if not validate_rss(rss_path, expected_episode_num=episode_num):
            all_passed = False
        elif not validate_enclosure_reachability(rss_path):
            all_passed = False

    if all_passed:
        logger.info("Post-run validation PASSED for '%s' episode %s", show_name, episode_num)
    else:
        logger.error("Post-run validation FAILED for '%s' episode %s", show_name, episode_num)

    return all_passed
