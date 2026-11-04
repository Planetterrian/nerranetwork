"""What a room costs, written where the spend happens (Nov 3 2026).

Until this module existed the interview shows read $0.00 on Mission Control:
``common.llm()`` unpacked ``(text, _meta)`` and discarded the usage; the
Voice Agent minutes (Mira's live room, the two sessions of a rehearsal room,
her narration takes) were priced only in the rehearsal report; the room's
research lookups were counted by the Worker and never priced; nothing under
``digests/age_of_ai`` or ``digests/nerra_voices`` was a credit file. "Numbers
fail silently" — this show's numbers were not failing, they were absent.

The shape is the network's: one ``engine.tracking`` tracker per run, saved
through ``save_usage(filename=...)`` so ``scripts/generate_dashboard.py``'s
``aggregate_costs`` reads it like every other credit file.

* ``credit_usage_<date>_room_<run_id[:8]>.json`` — one per interview room,
  written by ``post_interview.py`` (the LLM passes it ran, the room's Voice
  Agent minutes, its research lookups) and extended by ``narrate.py`` (her
  narration takes). ``published`` is false when written; the nightly
  metrics builder sets it from ``interviews.status`` — never
  ``publish_episode.py`` — and the rollup counts a room as an episode only
  when it is true.
* ``credit_usage_<date>_rehearsal_<run_id[:8]>.json`` — one per rehearsal
  room (``rehearsal.py``), two sessions each. The rollup sums these under its
  own ``rehearsal`` line so a fixture room never reads as show cost.

The rate per Voice Agent minute has ONE owner, ``engine.tracking``
(``XAI_VOICE_COST_PER_MIN`` overrides it); the line is labelled
``estimated`` until the xAI invoice is read.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent.parent

logger = logging.getLogger("nerra_voices")

#: A rehearsal room runs Mira AND the fixture guest, two Voice Agent sessions.
REHEARSAL_SESSIONS_PER_ROOM = 2

_TRACKER: Optional[dict] = None


# ---------------------------------------------------------------------------
# The per-run tracker
# ---------------------------------------------------------------------------

def tracker(show_name: str = "") -> dict:
    """The process's one tracker (created on first use)."""
    global _TRACKER
    from engine.tracking import create_tracker
    if _TRACKER is None:
        _TRACKER = create_tracker(show_name or "Nerra Voices", 0)
    elif show_name and not _TRACKER.get("show"):
        _TRACKER["show"] = show_name
    return _TRACKER


def reset() -> None:
    """Forget the process tracker (tests, and a tool that runs several rooms)."""
    global _TRACKER
    _TRACKER = None


def _tokens(usage: Any, *names: str) -> int:
    for name in names:
        value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def normalise_meta(meta: Any) -> Optional[Dict[str, Any]]:
    """A ``grok_generate_text`` meta the tracker can read.

    ``digests/xai_grok.py`` returns the SDK's usage OBJECT on the Chat
    Completions path and no usage at all on the Responses path, while
    ``engine.tracking.record_llm_usage_from_meta`` requires a dict and
    otherwise returns False silently — the $0 path this closes. The usage
    becomes ``{prompt_tokens, completion_tokens, cached_tokens}``; a meta
    with no usable usage comes back without a ``usage`` key (recorded as
    nothing, never as a zero-token step).
    """
    if not isinstance(meta, dict):
        return None
    out = {k: v for k, v in meta.items() if k != "usage"}
    usage = meta.get("usage")
    if usage is None:
        return out
    prompt = _tokens(usage, "prompt_tokens", "input_tokens")
    completion = _tokens(usage, "completion_tokens", "output_tokens")
    cached = _tokens(usage, "cached_tokens")
    if not cached:
        details = (usage.get("prompt_tokens_details") if isinstance(usage, dict)
                   else getattr(usage, "prompt_tokens_details", None))
        if details is not None:
            cached = _tokens(details, "cached_tokens")
    if not (prompt or completion):
        return out
    out["usage"] = {"prompt_tokens": prompt, "completion_tokens": completion,
                    "cached_tokens": cached}
    return out


def record_llm(step: str, meta: Any, *, into: Optional[dict] = None) -> bool:
    """Record one ``common.llm()`` call. Never raises."""
    from engine.tracking import record_llm_usage_from_meta
    try:
        return record_llm_usage_from_meta(into if into is not None else tracker(),
                                          step, normalise_meta(meta))
    except Exception as exc:  # noqa: BLE001 — accounting never breaks a call
        logger.warning("LLM usage accounting failed for %s (non-fatal): %s", step, exc)
        return False


def _drain_search_usage(into: dict) -> None:
    """The Responses-API searches ``xai_grok`` accumulated for this process
    (``web_search=True`` calls), priced per call like run_show does."""
    try:
        from digests.xai_grok import drain_search_usage
        from engine.tracking import record_search_usage
        usage = drain_search_usage()
        if usage.get("calls"):
            record_search_usage(into, calls=usage["calls"], sources=usage.get("sources", 0),
                                prompt_tokens=usage.get("input_tokens", 0),
                                completion_tokens=usage.get("output_tokens", 0),
                                model="grok-4.3")
    except Exception:  # noqa: BLE001
        logger.debug("search usage drain failed", exc_info=True)


# ---------------------------------------------------------------------------
# Credit files
# ---------------------------------------------------------------------------

def digests_dir(show: Any) -> Path:
    sub = getattr(show, "audio_subdir", None) or f"digests/{getattr(show, 'slug', 'age_of_ai')}"
    return ROOT / sub


def room_credit_filename(date: str, run_id: str) -> str:
    return f"credit_usage_{date}_room_{str(run_id)[:8]}.json"


def rehearsal_credit_filename(date: str, run_id: str) -> str:
    return f"credit_usage_{date}_rehearsal_{str(run_id)[:8]}.json"


def find_room_credit_file(show: Any, run_id: str) -> Optional[Path]:
    """The room's file whatever day it was written (a narration re-run can
    land days after the room)."""
    ddir = digests_dir(show)
    if not ddir.exists():
        return None
    found = sorted(ddir.glob(f"credit_usage_*_room_{str(run_id)[:8]}.json"))
    return found[-1] if found else None


def _save(t: dict, out_dir: Path, filename: str) -> Optional[Path]:
    from engine.tracking import save_usage
    out_dir.mkdir(parents=True, exist_ok=True)
    return save_usage(t, out_dir, filename=filename)


def write_room_credit_file(show: Any, run: Dict[str, Any], *,
                           interview: Optional[Dict[str, Any]] = None,
                           published: bool = False,
                           into: Optional[dict] = None) -> Optional[Path]:
    """One credit file for an interview room: the LLM passes this process
    ran, the room's Voice Agent minutes (one session — the guest is a
    browser), and its research lookups. Never raises."""
    try:
        from engine.tracking import record_search_usage, record_voice_agent_usage
        t = into if into is not None else tracker(getattr(show, "name", ""))
        t["show"] = getattr(show, "name", "") or t.get("show") or "Nerra Voices"
        t["kind"] = "room"
        t["published"] = bool(published)
        log = run.get("grok_session_log") if isinstance(run.get("grok_session_log"), dict) else {}
        try:
            duration = float(run.get("duration_sec") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        lookups = int(log.get("research_lookups") or 0)
        t["room"] = {
            "run_id": run.get("id"),
            "interview_id": run.get("interview_id") or (interview or {}).get("id"),
            "session_kind": run.get("session_kind") or (interview or {}).get("session_kind") or "interview",
            "duration_sec": int(duration),
            "research_lookups": lookups,
        }
        if duration > 0:
            record_voice_agent_usage(t, duration / 60.0, sessions=1)
        if lookups:
            record_search_usage(t, calls=lookups, sources=0)
        _drain_search_usage(t)
        existing = find_room_credit_file(show, str(run.get("id") or ""))
        filename = existing.name if existing else room_credit_filename(t["date"], str(run.get("id") or ""))
        path = _save(t, digests_dir(show), filename)
        if path:
            logger.info("room credit file written: %s", path)
        return path
    except Exception:  # noqa: BLE001 — accounting never fails an episode
        logger.exception("room credit file not written (non-fatal)")
        return None


def update_credit_file(path: Path, mutate: Callable[[dict], None]) -> Optional[Path]:
    """Re-open a saved tracker, change it, save it again (totals recomputed)."""
    try:
        t = json.loads(path.read_text(encoding="utf-8"))
        mutate(t)
        return _save(t, path.parent, path.name)
    except Exception:  # noqa: BLE001
        logger.exception("credit file %s not updated (non-fatal)", path)
        return None


def add_narration_usage(show: Any, run_id: str, *, minutes: float = 0.0,
                        sessions: int = 0, tts_chars: int = 0) -> Optional[Path]:
    """Mira's narration for the episode of ``run_id``: Voice Agent takes
    (minutes and sessions) on the agent path, Grok TTS characters on the
    fallback path. Lands on the room's file; a room with no file yet (a
    narration re-run on another day) gets one. Never raises."""
    if not run_id:
        logger.info("no INTERVIEW_RUN_ID — narration usage not recorded")
        return None
    from engine.tracking import record_tts_usage, record_voice_agent_usage

    def mutate(t: dict) -> None:
        if minutes or sessions:
            record_voice_agent_usage(t, minutes, sessions=sessions)
        if tts_chars:
            record_tts_usage(t, int(tts_chars), provider="grok")
        narration = t.setdefault("narration", {"minutes": 0.0, "takes": 0, "tts_chars": 0})
        narration["minutes"] = round(float(narration.get("minutes", 0.0) or 0.0) + float(minutes or 0.0), 2)
        narration["takes"] = int(narration.get("takes", 0) or 0) + int(sessions or 0)
        narration["tts_chars"] = int(narration.get("tts_chars", 0) or 0) + int(tts_chars or 0)

    try:
        existing = find_room_credit_file(show, run_id)
        if existing:
            return update_credit_file(existing, mutate)
        from engine.tracking import create_tracker
        t = create_tracker(getattr(show, "name", "") or "Nerra Voices", 0)
        t["kind"] = "room"
        t["published"] = False
        t["room"] = {"run_id": run_id}
        mutate(t)
        return _save(t, digests_dir(show), room_credit_filename(t["date"], run_id))
    except Exception:  # noqa: BLE001
        logger.exception("narration usage not recorded (non-fatal)")
        return None


def write_rehearsal_credit_file(show: Any, record: Dict[str, Any], *,
                                sessions_per_room: int = REHEARSAL_SESSIONS_PER_ROOM) -> Optional[Path]:
    """One credit file per rehearsal room from the numbers the rehearsal
    already computes (``room_log.length_min`` × two sessions). Never raises."""
    try:
        from engine.tracking import create_tracker, record_voice_agent_usage
        run_id = str(record.get("run_id") or "")
        if not run_id:
            return None
        length = float((record.get("room_log") or {}).get("length_min") or 0.0)
        t = create_tracker(getattr(show, "name", "") or "Nerra Voices", 0)
        measured = str(record.get("measured_at") or "")[:10]
        if len(measured) == 10:
            t["date"] = measured
        t["kind"] = "rehearsal"
        t["published"] = False
        t["rehearsal"] = {
            "run_id": run_id, "arm": record.get("arm"), "fixture": record.get("fixture"),
            "planned_minutes": record.get("planned_minutes"), "length_min": length,
            "sessions_per_room": int(sessions_per_room),
        }
        if length > 0:
            record_voice_agent_usage(t, length * sessions_per_room, sessions=sessions_per_room)
        return _save(t, digests_dir(show), rehearsal_credit_filename(t["date"], run_id))
    except Exception:  # noqa: BLE001
        logger.exception("rehearsal credit file not written (non-fatal)")
        return None
