"""The transcript of the EDIT, and the guest's cuts applied to it (Oct 21 2026).

Two promises the show makes to a guest were kept by hand until now:

* "You approve what publishes." The review page showed the ROOM's transcript
  while the published audio was the edit of it, so the text a guest signed
  off carried lines the edit had removed, and timestamps that pointed at a
  recording nobody would hear. ``transcript_of_the_edit`` walks the EDL in
  running order with the real duration of every piece and re-stamps each
  surviving line on the edit's own clock; narration reads as
  ``Mira (narration)``.
* "Cut anything from it." The guest's cut requests were free text on the
  package and ``produce_episode`` applied them to a file ``publish_episode``
  never ships. ``apply_windows`` splits the conversation cuts of an EDL around
  every window the guest marked, on the clock the EDL addresses, so the file
  the assembler builds — the one that publishes — carries none of it.

Both are pure functions of the EDL so they can be tested without audio.
The clocks:

* ``room`` — the transcript's clock (``[mm:ss]`` from the room opening).
* ``leg`` — the clock the EDL's conversation cuts address: the room clock
  minus ``room_offset_sec`` (auto_edit's ``_leg_offset``; 0 once every track
  is placed on the room's clock, which is the usual case since Sept 2026).
* ``edit`` — the published file's clock, which only the assembler knows,
  because narration lengths are measured after they are synthesised.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

_LINE = re.compile(r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*([^:]+):\s*(.*)$")
_CONVERSATION = ("run:", "track:", "mix:")

# A window the guest marks is widened by this much either side so the edge of
# a word never survives (the same pad the cutter leaves around a seam).
WINDOW_PAD_SEC = 0.35


def _is_conversation(cut: dict) -> bool:
    return (str(cut.get("from", "")).startswith(_CONVERSATION)
            or bool(cut.get("balance")))


def parse_lines(transcript: str) -> List[Tuple[float, str, str]]:
    """``[(room_sec, who, text)]`` for every stamped line."""
    out = []
    for raw in (transcript or "").splitlines():
        m = _LINE.match(raw.strip())
        if not m:
            continue
        h, mm, ss, who, text = m.groups()
        at = (int(h) * 3600 + int(mm) * 60 + int(ss)) if ss else (int(h) * 60 + int(mm))
        out.append((float(at), who.strip(), text.strip()))
    return out


def stamp(seconds: float) -> str:
    s = max(0, int(round(seconds)))
    if s >= 3600:
        return f"[{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}]"
    return f"[{s // 60:02d}:{s % 60:02d}]"


# ---------------------------------------------------------------------------
# The guest's windows
# ---------------------------------------------------------------------------

def normalise_windows(windows: Any) -> List[Dict[str, Any]]:
    """The guest's cut windows as ``[{start_sec, end_sec, line}]`` on the room
    clock, sorted, merged where they touch, anything unusable dropped.

    The Worker stores what the guest clicked; a window with no numbers (a
    free-text note) is not a window and stays Patrick's to resolve, as the
    produce path has always said."""
    rows = []
    for w in windows or []:
        if not isinstance(w, dict):
            continue
        try:
            a = float(w.get("start_sec", w.get("start")))
            b = float(w.get("end_sec", w.get("end")))
        except (TypeError, ValueError):
            continue
        if not (b > a >= 0):
            continue
        rows.append({"start_sec": a, "end_sec": b, "line": str(w.get("line") or "")})
    rows.sort(key=lambda w: w["start_sec"])
    merged: List[Dict[str, Any]] = []
    for w in rows:
        if merged and w["start_sec"] <= merged[-1]["end_sec"] + WINDOW_PAD_SEC:
            merged[-1]["end_sec"] = max(merged[-1]["end_sec"], w["end_sec"])
            if w["line"] and w["line"] not in merged[-1]["line"]:
                merged[-1]["line"] = (merged[-1]["line"] + " / " + w["line"]).strip(" /")
        else:
            merged.append(dict(w))
    return merged


def windows_hash(windows: Any) -> str:
    """A stable fingerprint of the windows an edit was built against.

    ``publish_episode`` compares the package's current windows with the one
    the assembler recorded on the shipped file: a guest who marks a cut after
    the edit was built must never have the older file publish. Empty windows
    hash to ``""`` so an edit built before any were marked reads as "none".
    """
    rows = normalise_windows(windows)
    if not rows:
        return ""
    body = json.dumps([[round(w["start_sec"], 2), round(w["end_sec"], 2)] for w in rows])
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]


def apply_windows(cuts: List[dict], windows: Any,
                  room_offset_sec: float = 0.0) -> Tuple[List[dict], int]:
    """Split every conversation cut around the guest's windows.

    Returns ``(cuts, applied)`` where *applied* counts the windows that
    touched audio the edit was going to keep. A window inside a stretch the
    edit had already dropped costs nothing and is still "applied": the
    published file carries none of it either way. A ``gap`` is placed where a
    window splits a cut so the seam breathes like the cutter's own.
    """
    rows = normalise_windows(windows)
    if not rows or not cuts:
        return list(cuts), 0
    leg_windows = [(max(0.0, w["start_sec"] - room_offset_sec - WINDOW_PAD_SEC),
                    max(0.0, w["end_sec"] - room_offset_sec + WINDOW_PAD_SEC), w)
                   for w in rows]
    out: List[dict] = []
    touched = set()
    for cut in cuts:
        if not _is_conversation(cut) or cut.get("start") is None or cut.get("end") is None:
            out.append(cut)
            continue
        pieces = [(float(cut["start"]), float(cut["end"]))]
        for a, b, w in leg_windows:
            nxt = []
            for s, e in pieces:
                if b <= s or a >= e:
                    nxt.append((s, e))
                    continue
                touched.add(id(w))
                if a > s:
                    nxt.append((s, a))
                if b < e:
                    nxt.append((b, e))
            pieces = nxt
        if not pieces:
            # The whole cut was inside a window: it goes, and so does the gap
            # the cutter put after it (the next entry), if any.
            continue
        for i, (s, e) in enumerate(pieces):
            if i:
                out.append({"gap": 0.4})
            piece = {**cut, "start": round(s, 2), "end": round(e, 2)}
            if i:
                piece["note"] = "after a passage the guest asked to have out"
            # A mute inside the removed span no longer has anything to mute.
            if piece.get("mute"):
                piece["mute"] = [m for m in piece["mute"]
                                 if s <= float(m["from"]) and float(m["to"]) <= e]
                if not piece["mute"]:
                    piece.pop("mute")
            out.append(piece)
    # Two gaps in a row (a cut removed entirely) collapse to one.
    cleaned: List[dict] = []
    for c in out:
        if c.get("gap") is not None and cleaned and cleaned[-1].get("gap") is not None:
            cleaned[-1] = {"gap": max(float(cleaned[-1]["gap"]), float(c["gap"]))}
            continue
        cleaned.append(c)
    # Every window either touched kept audio or fell inside a drop; both mean
    # the published file carries none of it.
    return cleaned, len(rows)


# ---------------------------------------------------------------------------
# The transcript of the edit
# ---------------------------------------------------------------------------

def transcript_of_the_edit(transcript: str, cuts: List[dict],
                           durations: Iterable[float],
                           room_offset_sec: float = 0.0,
                           narration: Optional[Dict[str, str]] = None,
                           header: str = "") -> str:
    """Re-stamp the room's transcript on the edit's clock.

    ``durations`` is the measured length of each entry of ``cuts`` in order
    (a gap's is its own value; a narration piece's is what the synthesis
    produced). A room line survives when its stamp falls inside a kept
    conversation span; it is re-stamped at ``edit_clock + (room - span
    start)``. Narration entries render as ``Mira (narration):`` with the
    segment's text when ``narration`` carries it (``{"intro": text, ...}``).
    """
    lines = parse_lines(transcript)
    durs = [float(d) for d in durations]
    if len(durs) != len(cuts):
        raise ValueError(f"{len(cuts)} cuts but {len(durs)} durations")
    out: List[str] = []
    if header:
        out.append(header.rstrip())
    clock = 0.0
    for cut, dur in zip(cuts, durs):
        if cut.get("gap") is not None:
            clock += dur
            continue
        ref = str(cut.get("from", ""))
        if ref.startswith("narration:"):
            seg = ref.split(":", 1)[1]
            text = (narration or {}).get(seg, "")
            if text:
                out.append(f"{stamp(clock)} Mira (narration): {text}")
            clock += dur
            continue
        if _is_conversation(cut) and cut.get("start") is not None and cut.get("end") is not None:
            s = float(cut["start"]) + room_offset_sec
            e = float(cut["end"]) + room_offset_sec
            # Oct 23 2026, Stan Lewis. The assembler closes every pause over
            # a second (GAP_TRIM), so a 30-minute span can come out at 24.
            # Stamped at "room minus span start", his last line before the
            # cut read 30:37 and the first line after it 24:52: the
            # transcript he was asked to approve ran backwards. Spread the
            # span over the time it actually takes in the edit.
            scale = min(1.0, dur / (e - s)) if e > s else 1.0
            removed = cut.get("_gaps_removed")
            for at, who, text in lines:
                if s <= at < e:
                    # Oct 27 2026: when the assembler says which silences it
                    # took out, place each line exactly; otherwise spread.
                    rel = (_map_rel(at - s, removed) if removed is not None
                           else (at - s) * scale)
                    out.append(f"{stamp(clock + rel)} {who}: {text}")
            clock += dur
            continue
        clock += dur
    return "\n".join(out).strip() + ("\n" if out else "")


# ---------------------------------------------------------------------------
# The edit's clock (Oct 27 2026)
# ---------------------------------------------------------------------------
#
# Glenn Broder's chapters were written on the room's clock and would have been
# published as they were: his episode opens with fifty seconds of cold open and
# introduction in place of the room's first forty-five, and the assembler takes
# the long silences out of the conversation, so by the end every chapter mark
# pointed nearly three minutes late. The assembler now records which silences
# it removed from each piece (close_gaps), and the clock below maps any moment
# of the room to the moment of the published file that carries it.

def _map_rel(rel: float, removed) -> float:
    """Seconds into a piece's source -> seconds into the piece as built, given
    the ``[[from, to], ...]`` stretches the assembler took out of it."""
    shift = 0.0
    for a, b in sorted(removed or []):
        if rel < a:
            break
        if rel < b:              # inside a removed silence: where it was closed
            return a - shift
        shift += b - a
    return rel - shift


def edit_clock(cuts: List[dict], durations: Iterable[float],
               room_offset_sec: float = 0.0) -> List[List[float]]:
    """``[[room_from, room_to, edit_from], ...]`` (a fourth number is a scale
    when the piece's silences were closed without a record of where): every
    stretch of the room that is in the edit, and where it starts in the edit."""
    durs = [float(d) for d in durations]
    out: List[List[float]] = []
    clock = 0.0
    for cut, dur in zip(cuts, durs):
        if (cut.get("gap") is None and _is_conversation(cut)
                and cut.get("start") is not None and cut.get("end") is not None):
            s = float(cut["start"]) + room_offset_sec
            e = float(cut["end"]) + room_offset_sec
            removed = cut.get("_gaps_removed")
            if removed is not None:
                u, shift = 0.0, 0.0
                for a, b in sorted(removed):
                    if a > u:
                        out.append([round(s + u, 2), round(s + a, 2), round(clock + u - shift, 2)])
                    shift += b - a
                    u = b
                if e - s > u:
                    out.append([round(s + u, 2), round(e, 2), round(clock + u - shift, 2)])
            elif e > s:
                scale = min(1.0, dur / (e - s))
                seg = [round(s, 2), round(e, 2), round(clock, 2)]
                if scale < 0.999:
                    seg.append(round(scale, 4))
                out.append(seg)
        clock += dur
    return out


def room_to_edit(clock: List[List[float]], t: float) -> Optional[float]:
    """Where moment ``t`` of the room is in the edit. A moment the edit
    dropped (a closed silence, a cut) maps to whatever comes next; a moment
    the edit holds twice (a cold-open clip that is also in the conversation)
    maps to the longer stretch, the conversation."""
    best = None
    for seg in clock or []:
        a, b, ea = float(seg[0]), float(seg[1]), float(seg[2])
        sc = float(seg[3]) if len(seg) > 3 else 1.0
        if a <= t < b and (best is None or b - a > best[0]):
            best = (b - a, ea + (t - a) * sc)
    if best is not None:
        return best[1]
    after = [seg for seg in clock or [] if float(seg[0]) >= t]
    if not after:
        return None
    nxt = min(after, key=lambda seg: (float(seg[0]), -(float(seg[1]) - float(seg[0]))))
    return float(nxt[2])


def chapters_on_edit_clock(chapters, clock: List[List[float]]) -> list:
    """Chapter marks written on the room's clock, moved to the edit's. The
    first chapter starts the episode (it carries the cold open and the
    introduction); a chapter whose start the edit dropped moves to what
    follows; a chapter that would not start after the one before goes."""
    if not isinstance(chapters, list) or not chapters or not clock:
        return chapters if isinstance(chapters, list) else []
    end = max(float(seg[2]) + (float(seg[1]) - float(seg[0])) * (float(seg[3]) if len(seg) > 3 else 1.0)
              for seg in clock)
    out: List[dict] = []
    for i, ch in enumerate(chapters):
        if not isinstance(ch, dict):
            continue
        try:
            t = float(ch.get("start", 0))
        except (TypeError, ValueError):
            continue
        at = 0.0 if not out else room_to_edit(clock, t)
        if at is None or (out and at <= out[-1]["start"] + 5):
            continue
        out.append({**ch, "start": round(at)})
    for a, b in zip(out, out[1:]):
        a["end"] = b["start"]
    if out:
        out[-1]["end"] = round(end)
    return out



_STAMP = re.compile(r"^\[?\s*(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?:\.\d+)?\s*\]?$")


def stamp_seconds(value) -> Optional[float]:
    """Seconds from "16:04", "[16:04]", "1:02:33" or a number; None if neither."""
    if isinstance(value, (int, float)):
        return float(value)
    m = _STAMP.match(str(value or "").strip())
    if not m:
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None
    h, mm, ss = m.groups()
    return float(int(h or 0) * 3600 + int(mm) * 60 + int(ss))


def normalise_chapters(chapters, transcript: str = "") -> list:
    """Chapter marks as numbers of seconds on the room's clock, in order, the
    first at 0, each ending where the next starts. The chapter pass is asked
    for the opening line's [MM:SS] stamp as written (Oct 27 2026): asked for
    seconds, the auto edit read Glenn Broder's 16:00.9 as 1600.9 seconds. A
    number past the end of the transcript is read as minutes and seconds."""
    if not isinstance(chapters, list):
        return chapters
    last = max((at for at, _w, _t in parse_lines(transcript)), default=None)
    out = []
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        at = stamp_seconds(ch.get("start"))
        if at is None:
            continue
        if last is not None and at > last + 60 and at >= 100 and int(at) % 100 < 60:
            at = float(int(at) // 100 * 60 + int(at) % 100) + (at - int(at))
        out.append({**ch, "start": round(at)})
    out.sort(key=lambda c: c["start"])
    dedup = []
    for ch in out:
        if dedup and ch["start"] <= dedup[-1]["start"]:
            continue
        dedup.append(ch)
    if dedup:
        dedup[0]["start"] = 0
    for a, b in zip(dedup, dedup[1:]):
        a["end"] = b["start"]
    if dedup:
        dedup[-1]["end"] = round(last) if last is not None else dedup[-1].get("end", dedup[-1]["start"])
    return dedup
