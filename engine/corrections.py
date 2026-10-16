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

Oct 16 2026 — a correction that carries ``replacements`` and/or ``headline``
is a **real amend**: :func:`apply_episode_amendments` rewrites the committed
digest, reader/TTS scripts, transcript surfaces and the RSS item so the
false claim is gone from the text a reader or feed consumer sees. The dated
Correction box still renders. Audio is never silently edited — ``where:
audio`` / ``both`` still means the spoken file needs
``scripts/resynthesize_episode.py``.

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

Loaders never raise: a malformed file logs a warning and reads as "no
corrections", because a build or a feed update must not fail over a trust
annotation. The amend path raises only on I/O the operator asked for.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

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
#: Hook / lead blockquote in a digest (``> **headline**``).
_HOOK_BLOCK_RE = re.compile(
    r"(^>\s*\*\*)(.*?)(\*\*\s*$)",
    re.MULTILINE,
)
#: Episode title lines inside an RSS ``<item>``.
_RSS_TITLE_RE = re.compile(
    r"(<(?:itunes:)?title>)(.*?)(</(?:itunes:)?title>)",
    re.DOTALL,
)


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
    # Oct 14 2026: a correction that retracts the episode's PREMISE (UC
    # Ep139 — the headline itself asserts the unsupported case) may amend
    # the headline: the page title gains a "Corrected:" prefix and the box
    # renders above it. The audio is still untouched until a resynthesize.
    out["amend_headline"] = bool(entry.get("amend_headline", False))
    # Oct 16 2026: optional new headline text (replaces the digest hook and
    # feed/page titles when amendments are applied). Empty = leave as-is
    # aside from the Corrected: prefix when amend_headline is set.
    headline = " ".join(str(entry.get("headline") or "").split())
    if headline:
        out["headline"] = headline
    replacements = _normalise_replacements(entry.get("replacements"), origin=origin,
                                           episode=episode)
    if replacements:
        out["replacements"] = replacements
    # Optional explicit pin: the episode whose show notes carried the
    # "Correction to episode N" line. Normally derived from the digest dates.
    if entry.get("noted_in") is not None:
        try:
            out["noted_in"] = int(entry["noted_in"])
        except (TypeError, ValueError):
            logger.warning("corrections: %s: episode %s: noted_in is not an integer",
                           origin, episode)
    return out


def _normalise_replacements(raw, *, origin: str, episode: int) -> List[Dict[str, str]]:
    """Validate ``replacements: [{find, replace}, ...]``; skip bad rows."""
    if not raw:
        return []
    if not isinstance(raw, list):
        logger.warning("corrections: %s: episode %s: replacements is not a list",
                       origin, episode)
        return []
    out: List[Dict[str, str]] = []
    for i, row in enumerate(raw):
        if not isinstance(row, dict):
            logger.warning("corrections: %s: episode %s: replacements[%s] not a mapping",
                           origin, episode, i)
            continue
        find = str(row.get("find") or "")
        replace = str(row.get("replace") if row.get("replace") is not None else "")
        if not find:
            logger.warning("corrections: %s: episode %s: replacements[%s] has empty find",
                           origin, episode, i)
            continue
        if find == replace:
            continue
        out.append({"find": find, "replace": replace})
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


# ---------------------------------------------------------------------------
# Text amendments — rewrite published surfaces so the false claim is gone
# ---------------------------------------------------------------------------


def has_text_amendments(entry: dict) -> bool:
    """True when *entry* carries a headline rewrite and/or find/replace pairs."""
    return bool(entry.get("headline") or entry.get("replacements"))


def apply_replacements(text: str, replacements: Sequence[Dict[str, str]]) -> Tuple[str, int]:
    """Apply find/replace pairs in order. Returns ``(new_text, n_hits)``."""
    if not text or not replacements:
        return text or "", 0
    hits = 0
    out = text
    for row in replacements:
        find = row.get("find") or ""
        if not find or find not in out:
            continue
        replace = row.get("replace") if row.get("replace") is not None else ""
        n = out.count(find)
        out = out.replace(find, replace)
        hits += n
    return out, hits


def _amend_hook_blockquote(text: str, headline: str) -> Tuple[str, bool]:
    """Replace the digest's ``> **hook**`` with *headline*. Returns changed?"""
    if not headline or not text:
        return text, False

    def _sub(m: re.Match) -> str:
        return f"{m.group(1)}{headline}{m.group(3)}"

    new, n = _HOOK_BLOCK_RE.subn(_sub, text, count=1)
    return new, n > 0


def amend_text(text: str, entry: dict) -> Tuple[str, int]:
    """Apply one correction's headline + replacements to a text blob.

    Returns ``(new_text, change_count)`` where change_count sums replacement
    hits and a headline rewrite (1 if the hook block changed).
    """
    if not text:
        return text or "", 0
    total = 0
    out = text
    headline = (entry.get("headline") or "").strip()
    if headline:
        out, changed = _amend_hook_blockquote(out, headline)
        if changed:
            total += 1
        # Plain-text surfaces (tts/reader/transcript opener) often lead with
        # the old hook as the first non-empty line — rewrite that too when
        # the old line is still present and the new headline is not.
        if headline not in out:
            # Prefer replacing a known old hook if replacements already did;
            # otherwise leave line-1 alone (replacements handle phrasing).
            pass
    out, hits = apply_replacements(out, entry.get("replacements") or [])
    total += hits
    return out, total


def _episode_glob_files(show_dir: Path, episode: int) -> List[Path]:
    """Committed text surfaces for *episode* that amendments may rewrite."""
    show_dir = Path(show_dir)
    ep = int(episode)
    patterns = [
        f"*_Ep{ep:03d}_*.md",
        f"*_Ep{ep:03d}_*_reader.txt",
        f"*_Ep{ep:03d}_*_tts.txt",
        f"*_Ep{ep:03d}_*_transcript.txt",
        f"*_Ep{ep:03d}_*_transcript.vtt",
        f"*_Ep{ep:03d}_*.txt",  # fr/ru dubbed scripts (not transcript)
        f"*_Ep{ep:03d}_*_transcript.json",
        f"*_Ep{ep}_*.md",  # unpadded (rare)
    ]
    seen: set[Path] = set()
    out: List[Path] = []
    for pat in patterns:
        for path in sorted(show_dir.glob(pat)):
            name = path.name
            if "_claims" in name or name.endswith(".skip.json"):
                continue
            # Skip fr/ru transcript companions handled by the transcript patterns;
            # the broad *.txt already covers dubbed scripts.
            if path in seen:
                continue
            # Only keep language dub scripts from the broad txt glob when they
            # look like ``*.fr.txt`` / ``*.ru.txt`` (not reader/tts already listed).
            if pat.endswith("*.txt") and not any(
                name.endswith(s) for s in (
                    "_reader.txt", "_tts.txt", "_transcript.txt",
                    ".fr.txt", ".ru.txt", ".es.txt", ".zh.txt",
                )
            ):
                continue
            seen.add(path)
            out.append(path)
    chapters = show_dir / f"chapters_ep{ep:03d}.json"
    if chapters.is_file():
        out.append(chapters)
    return out


def _amend_json_blob(raw: str, entry: dict) -> Tuple[str, int]:
    """Amend string values inside a JSON document (transcript / chapters)."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return apply_replacements(raw, entry.get("replacements") or [])

    hits = 0
    headline = (entry.get("headline") or "").strip()
    replacements = entry.get("replacements") or []

    def _walk(obj):
        nonlocal hits
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                if isinstance(v, str):
                    new, n = apply_replacements(v, replacements)
                    if n:
                        obj[k] = new
                        hits += n
                    elif headline and k == "title":
                        m = re.match(r"^(Ep\s+\d+:\s*)(.*)$", v)
                        if m and m.group(2).strip() and m.group(2).strip() != headline:
                            obj[k] = m.group(1) + headline
                            hits += 1
                else:
                    _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(data)
    if hits == 0:
        return raw, 0
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n", hits


def _amend_file(path: Path, entry: dict, *, dry_run: bool) -> int:
    """Rewrite one surface file. Returns change count (0 = untouched)."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("corrections: could not read %s: %s", path, exc)
        return 0
    if path.suffix == ".json":
        new, hits = _amend_json_blob(raw, entry)
    else:
        new, hits = amend_text(raw, entry)
    if hits <= 0 or new == raw:
        return 0
    if not dry_run:
        path.write_text(new, encoding="utf-8")
    return hits


def _rss_item_slices(rss_text: str, episode: int) -> List[Tuple[int, int]]:
    """Byte ranges of ``<item>…</item>`` blocks for this episode only.

    Matches the item's own identity (``itunes:episode``, ``/epN.html`` link,
    or a title that opens ``Ep N:``) — never a "Correction to episode N"
    line carried in a *later* episode's description.
    """
    ranges: List[Tuple[int, int]] = []
    ep = int(episode)
    for m in re.finditer(r"<item\b.*?</item>", rss_text, re.DOTALL | re.IGNORECASE):
        block = m.group(0)
        if re.search(
            rf"<itunes:episode>\s*0*{ep}\s*</itunes:episode>",
            block,
            re.I,
        ):
            ranges.append((m.start(), m.end()))
            continue
        if re.search(rf"/ep0*{ep}\.html\b", block, re.I):
            ranges.append((m.start(), m.end()))
            continue
        if re.search(rf"<title>\s*Ep\s+0*{ep}\s*:", block, re.I):
            ranges.append((m.start(), m.end()))
            continue
    return ranges


def amend_rss_feed(rss_path: Union[str, Path], episode: int, entry: dict,
                   *, dry_run: bool = False) -> int:
    """Rewrite title/description text inside the RSS item for *episode*."""
    path = Path(rss_path)
    if not path.is_file():
        return 0
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("corrections: could not read RSS %s: %s", path, exc)
        return 0
    slices = _rss_item_slices(raw, episode)
    if not slices:
        return 0
    headline = (entry.get("headline") or "").strip()
    replacements = entry.get("replacements") or []
    total = 0
    pieces: List[str] = []
    cursor = 0
    for start, end in slices:
        pieces.append(raw[cursor:start])
        block = raw[start:end]
        new_block, hits = apply_replacements(block, replacements)
        if headline:
            def _title_sub(m: re.Match) -> str:
                inner = m.group(2)
                # Keep "Ep N: " prefix when present.
                em = re.match(r"(Ep\s+\d+:\s*)(.*)", inner, re.I)
                if em:
                    return f"{m.group(1)}{em.group(1)}{headline}{m.group(3)}"
                return f"{m.group(1)}{headline}{m.group(3)}"
            new_block, n_title = _RSS_TITLE_RE.subn(_title_sub, new_block)
            hits += n_title
            # Description often opens with <b>hook</b>
            bold_re = re.compile(r"(<b>)(.*?)(</b>)", re.IGNORECASE | re.DOTALL)

            def _bold_sub(m: re.Match) -> str:
                inner = m.group(2)
                if any(r["find"] in inner for r in replacements) or (
                    len(inner) > 40 and headline not in inner
                ):
                    # Only rewrite the first bold if it looks like the hook.
                    return f"{m.group(1)}{headline}{m.group(3)}"
                return m.group(0)

            new_block, n_bold = bold_re.subn(_bold_sub, new_block, count=1)
            hits += n_bold
        total += hits
        pieces.append(new_block)
        cursor = end
    pieces.append(raw[cursor:])
    if total <= 0:
        return 0
    if not dry_run:
        path.write_text("".join(pieces), encoding="utf-8")
    return total


def amend_summaries(show_dir: Union[str, Path], episode: int, entry: dict,
                    *, dry_run: bool = False) -> int:
    """Rewrite ``episode_title`` / ``content`` in the show's summaries JSON."""
    show_dir = Path(show_dir)
    hits = 0
    for path in sorted(show_dir.glob("summaries_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("corrections: could not read %s: %s", path, exc)
            continue
        rows = data.get("summaries") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            continue
        changed = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                num = int(row.get("episode_num") or row.get("episode") or -1)
            except (TypeError, ValueError):
                continue
            if num != int(episode):
                continue
            for key in ("episode_title", "content", "title", "hook"):
                val = row.get(key)
                if not isinstance(val, str) or not val:
                    continue
                new, n = amend_text(val, entry)
                if n and new != val:
                    # episode_title is often "Ep N: hook…" — prefer headline
                    headline = (entry.get("headline") or "").strip()
                    if key == "episode_title" and headline:
                        m = re.match(r"^(Ep\s+\d+:\s*)(.*)$", val)
                        if m:
                            new = m.group(1) + headline
                            # Re-apply replacements in case headline still
                            # needs them (usually headline is already final).
                            new, _ = apply_replacements(new, entry.get("replacements") or [])
                    row[key] = new
                    hits += max(n, 1)
                    changed = True
        if changed and not dry_run:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    return hits


def _current_digest_hook(show_dir: Path, episode: int) -> str:
    """The ``> **hook**`` text on the committed digest, or ``""``."""
    for path in sorted(show_dir.glob(f"*_Ep{int(episode):03d}_*.md")):
        if "_claims" in path.name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        m = _HOOK_BLOCK_RE.search(text)
        if m:
            return m.group(2).strip()
    return ""


def apply_episode_amendments(
    show_dir: Union[str, Path],
    episode: int,
    *,
    dry_run: bool = False,
    rss_paths: Optional[Sequence[Union[str, Path]]] = None,
) -> Dict:
    """Apply every amending correction filed against *episode* to disk.

    Rewrites digest / reader / TTS / transcript / chapters / summaries and
    any RSS paths supplied. Idempotent when find-strings are already gone.
    Returns a report dict: ``{files_touched, hits, corrections, dry_run}``.
    """
    show_dir = Path(show_dir)
    entries = [c for c in corrections_for(show_dir, episode) if has_text_amendments(c)]
    report: Dict = {
        "episode": int(episode),
        "dry_run": bool(dry_run),
        "corrections": len(entries),
        "files_touched": [],
        "hits": 0,
    }
    if not entries:
        return report
    # Merge replacements in filing order; last headline wins.
    merged: Dict = {"replacements": [], "headline": ""}
    for c in entries:
        merged["replacements"].extend(c.get("replacements") or [])
        if c.get("headline"):
            merged["headline"] = c["headline"]
        merged["amend_headline"] = bool(c.get("amend_headline"))

    # When a new headline is set, also replace the committed hook string on
    # plain-text surfaces (tts/reader/transcript openers have no blockquote).
    new_headline = (merged.get("headline") or "").strip()
    if new_headline:
        old_hook = _current_digest_hook(show_dir, episode)
        if old_hook and old_hook != new_headline:
            merged["replacements"] = [
                {"find": old_hook, "replace": new_headline},
                *merged["replacements"],
            ]

    for path in _episode_glob_files(show_dir, episode):
        n = _amend_file(path, merged, dry_run=dry_run)
        if n:
            report["files_touched"].append(str(path))
            report["hits"] += n

    n_sum = amend_summaries(show_dir, episode, merged, dry_run=dry_run)
    if n_sum:
        report["hits"] += n_sum
        report["files_touched"].append("summaries_*.json")

    for rss in rss_paths or []:
        n = amend_rss_feed(rss, episode, merged, dry_run=dry_run)
        if n:
            report["hits"] += n
            report["files_touched"].append(str(rss))

    return report
