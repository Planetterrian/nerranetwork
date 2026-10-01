"""Corrections: one file per show, read by every surface that promises one.

The AI-disclosure and editorial pages have promised since May 2026 that
"substantive corrections are noted in the next episode's show notes", and
the FAQ that "we correct errors in the blog article". Until 2026-10-01
nothing in the repository could make either sentence true: there was no
place to file a correction, so no surface could render one. This module is
that place.

The record is ``digests/<show_dir>/corrections.yaml`` — a plain list the
operator edits by hand (``docs/corrections.md`` says how)::

    - episode: 117
      date: 2026-10-01
      text: The booster flew its 23rd mission, not its 32nd.
      where: digest        # digest | audio | both

Three readers, one file:

* ``engine.blog`` prints a dated Correction box at the top of the affected
  episode's page (:func:`corrections_for`);
* ``engine.show_notes`` adds the correction to the corrected episode's RSS
  description on its next feed rebuild AND carries a one-line
  "Correction to episode N" in the NEXT episode's show notes
  (:func:`corrections_to_carry`), which is the sentence the policy pages
  promise;
* a recent-corrections view for any trust surface (:func:`recent_corrections`).

Audio is never edited silently. A correction entry describes what was wrong
and where; if the spoken episode has to change, the repair tool is
``scripts/resynthesize_episode.py`` (CLAUDE.md landmine #25), which
re-synthesizes the whole episode to the same R2 key and refuses to ship audio
the spoken-text gate has not passed. ``where: audio`` records that the audio
was wrong — it does not clip anything.

Everything here is read-only and never raises: a malformed file logs a
warning and reads as "no corrections", because a build or a feed update must
not fail over a trust annotation.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)

#: The file an operator edits, inside the show's digest directory.
CORRECTIONS_FILENAME = "corrections.yaml"

#: Where the error was. ``digest`` = the written article / show notes were
#: wrong (the audio did not carry it); ``audio`` = the spoken episode was
#: wrong; ``both`` = both carried it. Anything else is normalised to
#: ``digest`` with a warning rather than rejected.
WHERE_VALUES = ("digest", "audio", "both")

_DIGEST_STEM_RE = re.compile(r"_Ep(\d{1,4})_(\d{8})(?:[._]|$)")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def corrections_path(show_dir: Union[str, Path]) -> Path:
    """``digests/<show_dir>`` -> its ``corrections.yaml``."""
    return Path(show_dir) / CORRECTIONS_FILENAME


def _normalise(entry: dict, *, origin: str) -> Optional[Dict]:
    """One validated correction, or ``None`` (logged) when it cannot be used."""
    if not isinstance(entry, dict):
        logger.warning("corrections: %s: entry is not a mapping: %r", origin, entry)
        return None
    try:
        episode = int(entry.get("episode"))
    except (TypeError, ValueError):
        logger.warning("corrections: %s: entry has no integer episode: %r", origin, entry)
        return None
    raw_date = entry.get("date")
    if isinstance(raw_date, (date, datetime)):
        date_str = raw_date.strftime("%Y-%m-%d")
    else:
        date_str = str(raw_date or "").strip()
    if not _DATE_RE.match(date_str):
        logger.warning("corrections: %s: episode %s has no YYYY-MM-DD date: %r",
                       origin, episode, raw_date)
        return None
    text = " ".join(str(entry.get("text") or "").split())
    if not text:
        logger.warning("corrections: %s: episode %s has no text", origin, episode)
        return None
    where = str(entry.get("where") or "digest").strip().lower()
    if where not in WHERE_VALUES:
        logger.warning("corrections: %s: episode %s: unknown where=%r, using 'digest'",
                       origin, episode, where)
        where = "digest"
    out = {"episode": episode, "date": date_str, "text": text, "where": where}
    # Optional explicit pin: the episode whose show notes carried the
    # "Correction to episode N" line. Normally derived from the digest dates.
    if entry.get("noted_in") is not None:
        try:
            out["noted_in"] = int(entry["noted_in"])
        except (TypeError, ValueError):
            logger.warning("corrections: %s: episode %s: noted_in is not an integer",
                           origin, episode)
    return out


def load_corrections(show_dir: Union[str, Path]) -> List[Dict]:
    """Every valid correction in the show's file, oldest filing first.

    Missing file = ``[]``. A file that is not a YAML list, or an entry that
    fails validation, is logged and skipped — never raised.
    """
    path = corrections_path(show_dir)
    if not path.is_file():
        return []
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — a trust annotation never breaks a build
        logger.warning("corrections: could not read %s: %s", path, exc)
        return []
    if data is None:
        return []
    if isinstance(data, dict) and isinstance(data.get("corrections"), list):
        data = data["corrections"]
    if not isinstance(data, list):
        logger.warning("corrections: %s is not a list", path)
        return []
    out = [c for c in (_normalise(e, origin=str(path)) for e in data) if c]
    out.sort(key=lambda c: (c["date"], c["episode"]))
    return out


def corrections_for(show_dir: Union[str, Path], episode: int) -> List[Dict]:
    """The corrections filed AGAINST *episode* (what its page and its own
    show notes print)."""
    try:
        ep = int(episode)
    except (TypeError, ValueError):
        return []
    return [c for c in load_corrections(show_dir) if c["episode"] == ep]


def recent_corrections(show_dir: Union[str, Path], days: int = 30,
                       today: Optional[date] = None) -> List[Dict]:
    """Corrections filed in the last *days* days, newest first."""
    today = today or date.today()
    floor = (today - timedelta(days=max(int(days), 0))).strftime("%Y-%m-%d")
    out = [c for c in load_corrections(show_dir) if c["date"] >= floor]
    out.sort(key=lambda c: (c["date"], c["episode"]), reverse=True)
    return out


def digest_dates(show_dir: Union[str, Path]) -> Dict[int, str]:
    """``{episode: 'YYYY-MM-DD'}`` from the committed digest filenames.

    The filename date is the publish date (``Show_Ep117_20261001.md``); when
    an episode has two files the later date wins, which matches how the
    blog deduplicates them. Never raises.
    """
    out: Dict[int, str] = {}
    try:
        for md in Path(show_dir).glob("*_Ep*_*.md"):
            m = _DIGEST_STEM_RE.search(md.name)
            if not m:
                continue
            ep = int(m.group(1))
            d = m.group(2)
            iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            if iso > out.get(ep, ""):
                out[ep] = iso
    except Exception as exc:  # noqa: BLE001
        logger.warning("corrections: could not index digests in %s: %s", show_dir, exc)
    return out


def corrections_to_carry(show_dir: Union[str, Path], episode: int,
                         episode_date: Optional[str] = None) -> List[Dict]:
    """The corrections *episode*'s show notes must carry as "Correction to
    episode N" — the next-episode promise, made true.

    A correction filed on date D against episode E is carried by the FIRST
    episode numbered above E whose publish date is on or after D. At publish
    time that is decided from the digest filenames already on disk (the
    digest is saved before the feed is written; *episode_date* is used for
    the episode being published when its file is not there yet, defaulting
    to today). An entry with an explicit ``noted_in`` is carried by exactly
    that episode. A correction is never carried by the episode it corrects,
    and never by more than one episode.
    """
    try:
        ep = int(episode)
    except (TypeError, ValueError):
        return []
    filed = [c for c in load_corrections(show_dir) if c["episode"] < ep]
    if not filed:
        return []
    dates = digest_dates(show_dir)
    if ep not in dates:
        dates[ep] = (episode_date or date.today().strftime("%Y-%m-%d"))
    out = []
    for c in filed:
        if "noted_in" in c:
            if c["noted_in"] == ep:
                out.append(c)
            continue
        own = dates.get(ep, "")
        if own < c["date"]:
            continue  # this episode went out before the correction was filed
        # Any episode between the corrected one and this one that already
        # published on/after the filing date carried it first.
        earlier = [n for n, d in dates.items()
                   if c["episode"] < n < ep and d >= c["date"]]
        if earlier:
            continue
        out.append(c)
    return out
