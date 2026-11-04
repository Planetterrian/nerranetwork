#!/usr/bin/env python3
"""Mira's rooms into ``api/voices_metrics.json`` (Nov 3 2026).

The interview shows were the one part of the network the operator could not
read from Mission Control: the guest survey (the show's headline number),
the grades, the eight audio measures, the yield (61 real bookings: published
20, cancelled 17, missed 3, no-show 1 — a hand query) and the cost of a room
lived only in the nerra-voices Supabase or nowhere. This writes them, once a
night, into one committed file the dashboard's "Mira's rooms" card, the
register metrics (``voices_survey_mean_30d``, ``voices_pacing_grade_median_5``,
``voices_cost_per_room_usd``) and ``scripts/review_snapshot.py`` read.

Per voices show (``pipelines/voices/shows.VOICE_SHOW_SLUGS``):

* ``survey`` — answered, mean, share rated 4 or 5, and the last 30 days'
  ratings (``editorial_packages.survey_rating`` joined to ``interviews.show``);
* ``grades`` — the last ten graded rooms (overall, pacing, warmth) and
  ``audio`` — the medians of ``audio_metrics.COLUMNS`` over those rooms;
* ``yield`` — per calendar month of ``scheduled_at``: booked, published,
  cancelled (with counts BY REASON TEXT — a verdict on whose side a
  cancellation fell is not a thing this file says), missed, no_show,
  archived, other. Rehearsals and sessions that are not interviews are
  excluded;
* ``room_to_publish_days`` — median days from the room to the committed
  digest's date, by episode number;
* ``guest_mix`` — null until ``guest_applications.guest_kind`` exists;
* ``cost`` — the last ten ``credit_usage_*_room_*.json`` totals and their
  median (``pipelines/voices/costs.py`` writes them; the Voice Agent rate is
  an estimate until the invoice is read).

**Null, never 0, where a table could not be read** — the table is named in
``unreadable``. With credentials but an unreachable Supabase every table is
null and the exit code is 0 (the nightly never fails on this). With NO
credentials an existing file is left untouched (the member-metrics rule: a
host that cannot authenticate must not look like a show with no rooms).

It also sets ``published: true`` on each room credit file whose interview
is published — the ONE writer of that flag, never ``publish_episode.py`` —
which is what lets the cost rollup count the room as an episode.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "pipelines" / "voices"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

GRADE_ROOMS = 10
COST_ROOMS = 10
SURVEY_WINDOW_DAYS = 30
YIELD_MONTHS = 6
#: Statuses a real booking can end in, and how they are counted.
YIELD_STATUSES = ("published", "cancelled", "missed", "no_show", "archived")
DEFAULT_OUT = "api/voices_metrics.json"

Rows = Optional[List[Dict[str, Any]]]


def _log(msg: str) -> None:
    print(f"voices_metrics: {msg}", file=sys.stderr)


def credentials_present() -> bool:
    """Map the nightly's VOICES_SUPABASE_* names onto the Voices client's."""
    url = os.environ.get("VOICES_SUPABASE_URL") or os.environ.get("SUPABASE_URL") or ""
    key = (os.environ.get("VOICES_SUPABASE_SERVICE_KEY")
           or os.environ.get("SUPABASE_SERVICE_KEY") or "")
    if url and key:
        os.environ["SUPABASE_URL"] = url
        os.environ["SUPABASE_SERVICE_KEY"] = key
        return True
    return False


class Reader:
    """One Supabase read per table; a failure makes the table unreadable."""

    def __init__(self, select: Optional[Callable[[str, str], List[Dict[str, Any]]]] = None):
        self._select = select
        self.unreadable: List[str] = []
        self.read_any = False

    def rows(self, table: str, query: str) -> Rows:
        try:
            if self._select is None:
                from common import sb_select  # type: ignore
                self._select = sb_select
            out = self._select(table, query)
            self.read_any = True
            return list(out or [])
        except Exception as exc:  # noqa: BLE001 — unreadable, never a crash
            _log(f"{table} unreadable: {type(exc).__name__}: {str(exc)[:160]}")
            if table not in self.unreadable:
                self.unreadable.append(table)
            return None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _parse(value: Any) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[len(ordered) // 2], 2)


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_real_interview(iv: Dict[str, Any]) -> bool:
    kind = (iv.get("session_kind") or "interview")
    return kind == "interview" and (iv.get("status") or "") != "rehearsal"


def reason_label(text: Any) -> str:
    """Counts by reason TEXT, never a verdict. The Worker writes two shapes
    (``reschedule requested: …``, ``cancelled in Cal.com: …``); anything
    else is its own first line, clipped."""
    s = " ".join(str(text or "").split()).strip()
    if not s:
        return "no reason given"
    low = s.lower()
    for prefix in ("reschedule requested", "cancelled in cal.com"):
        if low.startswith(prefix):
            return prefix
    return low[:60]


def digest_publish_date(ddir: Path, episode_number: Any) -> Optional[dt.date]:
    """The committed digest's date for an episode (``*_Ep015_20261101.md``)."""
    try:
        num = int(episode_number)
    except (TypeError, ValueError):
        return None
    if not ddir.exists():
        return None
    for path in sorted(ddir.glob(f"*_Ep{num:03d}_*.md")):
        m = re.search(r"_Ep\d+_(\d{4})(\d{2})(\d{2})\.md$", path.name)
        if m:
            try:
                return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# per-show blocks
# ---------------------------------------------------------------------------

def survey_block(packages: Rows, show_of: Optional[Dict[str, str]], slug: str,
                 now: dt.datetime) -> Optional[Dict[str, Any]]:
    if packages is None or show_of is None:
        return None
    since = now - dt.timedelta(days=SURVEY_WINDOW_DAYS)
    ratings: List[int] = []
    recent: List[int] = []
    for row in packages:
        if show_of.get(str(row.get("interview_id"))) != slug:
            continue
        rating = _num(row.get("survey_rating"))
        if rating is None:
            continue
        ratings.append(int(rating))
        answered = _parse(row.get("survey_answered_at"))
        if answered and answered >= since:
            recent.append(int(rating))
    return {
        "answered": len(ratings),
        "mean": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "share_4_plus": round(sum(1 for r in ratings if r >= 4) / len(ratings), 2) if ratings else None,
        "answered_30d": len(recent),
        "mean_30d": round(sum(recent) / len(recent), 2) if recent else None,
        "ratings_30d": recent,
    }


def grades_block(grades: Rows, slug: str) -> Optional[List[Dict[str, Any]]]:
    if grades is None:
        return None
    rows = [g for g in grades if (g.get("show") or "") == slug]
    rows.sort(key=lambda g: str(g.get("created_at") or ""), reverse=True)
    return [{
        "date": str(g.get("created_at") or "")[:10],
        "interview_id": g.get("interview_id"),
        "overall": _num(g.get("overall")),
        "pacing": _num(g.get("pacing")),
        "warmth": _num(g.get("warmth")),
    } for g in rows[:GRADE_ROOMS]]


def audio_block(reader: Reader, graded: Optional[List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """Medians of audio_metrics.COLUMNS over the graded rooms."""
    if graded is None:
        return None
    ids = [str(g["interview_id"]) for g in graded if g.get("interview_id")]
    if not ids:
        return {"rooms": 0, "basis_audio": 0, "medians": {}}
    from audio_metrics import COLUMNS  # type: ignore
    select = ",".join(("interview_id",) + tuple(COLUMNS))
    rows = reader.rows("episode_metrics", f"select={select}&interview_id=in.({','.join(ids)})")
    if rows is None:
        return None
    medians: Dict[str, Any] = {}
    for col in COLUMNS:
        if col == "metrics_basis":
            continue
        if col == "closing_round_complete":
            seen = [bool(r.get(col)) for r in rows if r.get(col) is not None]
            medians["closing_round_complete_share"] = (
                round(sum(seen) / len(seen), 2) if seen else None)
            continue
        values = [v for v in (_num(r.get(col)) for r in rows) if v is not None]
        medians[col] = _median(values)
    return {
        "rooms": len(rows),
        "basis_audio": sum(1 for r in rows if r.get("metrics_basis") == "audio"),
        "medians": medians,
    }


def yield_block(interviews: Rows, slug: str, now: dt.datetime) -> Optional[Dict[str, Any]]:
    if interviews is None:
        return None
    months: Dict[str, Dict[str, Any]] = {}
    for iv in interviews:
        if (iv.get("show") or "") != slug or not is_real_interview(iv):
            continue
        when = _parse(iv.get("scheduled_at")) or _parse(iv.get("created_at"))
        if not when:
            continue
        key = when.strftime("%Y-%m")
        m = months.setdefault(key, {
            "booked": 0, "published": 0, "cancelled": 0, "cancelled_by_reason": {},
            "missed": 0, "no_show": 0, "archived": 0, "other": 0})
        m["booked"] += 1
        status = str(iv.get("status") or "")
        if status in YIELD_STATUSES:
            m[status] += 1
            if status == "cancelled":
                label = reason_label(iv.get("cancel_reason"))
                m["cancelled_by_reason"][label] = m["cancelled_by_reason"].get(label, 0) + 1
        else:
            m["other"] += 1
    keys = sorted(months)[-YIELD_MONTHS:]
    return {"current_month": now.strftime("%Y-%m"),
            "months": {k: months[k] for k in keys}}


def room_to_publish_block(interviews: Rows, slug: str, ddir: Path) -> Optional[Dict[str, Any]]:
    if interviews is None:
        return None
    days: List[float] = []
    for iv in interviews:
        if (iv.get("show") or "") != slug or iv.get("status") != "published":
            continue
        room = _parse(iv.get("scheduled_at"))
        published = digest_publish_date(ddir, iv.get("episode_number"))
        if room and published:
            days.append(float((published - room.date()).days))
    return {"median": _median(days), "n": len(days)}


def cost_block(ddir: Path) -> Dict[str, Any]:
    """The room credit files on disk (never a Supabase read)."""
    rooms: List[Dict[str, Any]] = []
    if ddir.exists():
        for path in sorted(ddir.glob("credit_usage_*_room_*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            total = _num(data.get("total_estimated_cost_usd"))
            if total is None:
                continue
            agent = ((data.get("services") or {}).get("voice_agent") or {})
            rooms.append({
                "run_id": (data.get("room") or {}).get("run_id"),
                "interview_id": (data.get("room") or {}).get("interview_id"),
                "date": data.get("date") or "",
                "total_usd": round(total, 4),
                "voice_agent_minutes": _num(agent.get("minutes")),
                "published": data.get("published") is True,
                "file": path.name,
            })
    rooms.sort(key=lambda r: (r["date"], r["file"]), reverse=True)
    recent = rooms[:COST_ROOMS]
    return {
        "rooms_costed": len(rooms),
        "median_usd": _median([r["total_usd"] for r in recent]),
        "rooms": recent,
        "rate_basis": "estimated",
    }


def mark_published_rooms(ddir: Path, interviews: Rows) -> int:
    """Set ``published: true`` on room credit files whose interview is
    published. The one writer of the flag; a file is rewritten only when
    the flag changes."""
    if interviews is None or not ddir.exists():
        return 0
    published_ids = {str(iv.get("id")) for iv in interviews if iv.get("status") == "published"}
    changed = 0
    for path in sorted(ddir.glob("credit_usage_*_room_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        interview_id = str((data.get("room") or {}).get("interview_id") or "")
        if not interview_id or interview_id not in published_ids or data.get("published") is True:
            continue
        data["published"] = True
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        changed += 1
    return changed


# ---------------------------------------------------------------------------
# the file
# ---------------------------------------------------------------------------

def build(root: Path, *, now: Optional[dt.datetime] = None, reader: Optional[Reader] = None,
          credentials: bool = True, previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from shows import VOICE_SHOW_SLUGS, get_show  # type: ignore
    now = now or dt.datetime.now(dt.timezone.utc)
    reader = reader or Reader()
    interviews: Rows = None
    packages: Rows = None
    grades: Rows = None
    guest_kind_exists = False
    if credentials:
        interviews = reader.rows(
            "interviews",
            "select=id,show,status,scheduled_at,created_at,session_kind,cancel_reason,"
            "episode_number&order=scheduled_at.desc.nullslast&limit=2000")
        packages = reader.rows(
            "editorial_packages",
            "select=interview_id,survey_rating,survey_answered_at"
            "&survey_rating=not.is.null&order=survey_answered_at.desc&limit=500")
        grades = reader.rows(
            "episode_grades",
            "select=interview_id,show,overall,pacing,warmth,created_at"
            "&order=created_at.desc&limit=200")
        # guest_mix waits for a guest_kind column; a probe that fails is the
        # column's absence, not an unreadable table.
        probe = Reader(reader._select)
        guest_kind_exists = probe.rows("guest_applications", "select=guest_kind&limit=1") is not None
        if probe.read_any:
            reader.read_any = True
    show_of = ({str(iv.get("id")): (iv.get("show") or "") for iv in interviews}
               if interviews is not None else None)

    shows: Dict[str, Any] = {}
    for slug in VOICE_SHOW_SLUGS:
        show = get_show(slug)
        ddir = root / show.audio_subdir
        graded = grades_block(grades, slug)
        marked = mark_published_rooms(ddir, interviews)
        if marked:
            _log(f"{slug}: {marked} room credit file(s) marked published")
        shows[slug] = {
            "name": show.name,
            "survey": survey_block(packages, show_of, slug, now),
            "grades": graded,
            "audio": audio_block(reader, graded),
            "yield": yield_block(interviews, slug, now),
            "room_to_publish_days": room_to_publish_block(interviews, slug, ddir),
            "guest_mix": None,
            "guest_mix_note": ("guest_applications.guest_kind exists; the mix is not computed yet"
                               if guest_kind_exists else
                               "null until guest_applications.guest_kind exists"),
            "cost": cost_block(ddir),
            "rooms_published": (sum(1 for iv in interviews
                                    if (iv.get("show") or "") == slug and iv.get("status") == "published")
                                if interviews is not None else None),
        }
    first = (previous or {}).get("first_generated_at") if isinstance(previous, dict) else None
    return {
        "generated_at": now.isoformat(),
        "first_generated_at": first or now.isoformat(),
        "source": "nerra-voices Supabase (interviews, editorial_packages, episode_grades, "
                  "episode_metrics) + digests/<show>/credit_usage_*_room_*.json",
        "credentials": bool(credentials),
        "supabase_read": bool(credentials and reader.read_any),
        "unreadable": list(reader.unreadable),
        "rules": "null where a table could not be read, never 0; the Voice Agent rate is "
                 "estimated until the xAI invoice is read; cancellations are counted by "
                 "reason text, never judged",
        "shows": shows,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    out = (ROOT / args.out).resolve()
    previous = None
    if out.exists():
        try:
            previous = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = None
    creds = credentials_present()
    if not creds and previous is not None:
        _log("no VOICES_SUPABASE_URL / VOICES_SUPABASE_SERVICE_KEY — existing file left untouched")
        return 0
    if not creds:
        _log("no VOICES_SUPABASE_URL / VOICES_SUPABASE_SERVICE_KEY — writing the file with "
             "every table null (the room credit files on disk are still read)")
    data = build(ROOT, credentials=creds, previous=previous)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    unreadable = data.get("unreadable") or []
    shown = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    _log(f"wrote {shown} — {len(data['shows'])} show(s)"
         + (f"; unreadable: {', '.join(unreadable)}" if unreadable else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
