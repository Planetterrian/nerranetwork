"""Thin Voximplant Management API wrapper for the Nerra Voices pipeline.

Covers exactly what fire_interviews.py and the deploy tooling need:

* ``start_interview_scenario(run_id)`` — StartScenarios with the interview
  run id as customData (the scenario pulls everything else from Supabase).
* ``upload_scenario(path)`` — create/update the scenario source (deploy).
* ``set_application_secrets(...)`` — store SUPABASE_SERVICE_KEY /
  XAI_API_KEY as application custom data the scenario reads via
  ``Application.customData()``.
* ``add_user(...)`` / ``list_users()`` — Voximplant application users
  (Phase 2 co-host: the ``host`` user is created once at bootstrap).

Auth: account-level API key (VOXIMPLANT_ACCOUNT_ID + VOXIMPLANT_API_KEY env
vars), per https://voximplant.com/docs/references/httpapi. All calls raise
``VoximplantError`` on non-success so callers fail loud.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.voximplant.com/platform_api"

# Names must match what's provisioned in the Voximplant panel (phase 1).
APPLICATION_NAME = os.environ.get("VOXIMPLANT_APP_NAME", "nerra-voices")
RULE_NAME = os.environ.get("VOXIMPLANT_RULE_NAME", "age-of-ai-interview")
SCENARIO_NAME = "age_of_ai_interview"
# Rehearsal harness (Oct 21 2026): a second scenario that plays a past guest
# into an interview room so a change to Mira's room is measured before a real
# person hears it (docs/age_of_ai_rehearsal.md). Its rule's pattern never
# matches an inbound call; it exists so StartScenarios can name it.
FIXTURE_SCENARIO_NAME = "age_of_ai_fixture_guest"
FIXTURE_RULE_NAME = os.environ.get("VOXIMPLANT_FIXTURE_RULE_NAME", "age-of-ai-fixture-guest")
FIXTURE_RULE_PATTERN = r"^fixture-guest-never-dialled$"
# Candidate rooms (Oct 22 2026): the rehearsal harness can only measure the
# scenario that is deployed, so a change to the room's own code could not be
# rehearsed before every guest got it. A branch's interview scenario is
# uploaded beside the live one under its own name, with its own room prefix
# and rule, and the fixture guest calls into "candroom-<run id>" instead of
# "room-<run id>". The live scenario, its rule and every real guest's room are
# untouched; the candidate is only ever reached by a rehearsal.
CANDIDATE_SCENARIO_NAME = "age_of_ai_interview_candidate"
CANDIDATE_ROOM_PREFIX = "candroom-"
CANDIDATE_ROOM_RULE_NAME = os.environ.get("VOXIMPLANT_CANDIDATE_RULE_NAME", "age-of-ai-candidate-room")
# Oct 23 2026: a person can join a candidate room too. The studio page with
# ?room=candidate dials CANDIDATE_STUDIO_NUMBER instead of "mira"; the
# candidate scenario answers it as a participant session (any destination
# that is not its room prefix) and bridges them into "candroom-<run id>".
# Only a rehearsal invite (rehearsal.py invite) carries that link.
CANDIDATE_STUDIO_NUMBER = "mira-candidate"
CANDIDATE_ROOM_RULE_PATTERN = r"^(candroom-.*|mira-candidate)$"
_ROOM_PREFIX_LINE = 'const ROOM_PREFIX = "room-";'
# xAI Voice Agent model for Mira. Oct 15 2026: pinned to `grok-voice-3.0`
# (released Oct 14 2026; the `grok-voice-latest` alias moved to it the same
# day and `grok-voice-2.0` is deprecated). xAI's own guidance is to pin a
# versioned name in production, and the network's rule since the Aug 18
# translation incident is that a published stage never rides a floating
# alias — the alias is how a vendor release changes shipped audio unseen.
# The next version is adopted here, after a rehearsal, never by the alias.
# Override with the GROK_VOICE_MODEL repo variable.
DEFAULT_GROK_VOICE_MODEL = os.environ.get(
    "GROK_VOICE_MODEL", "").strip() or "grok-voice-3.0"
# xAI Voice Agent max session duration, minutes (console → Realtime API →
# Rate limits). The scenario hands over to a fresh session before this.
DEFAULT_GROK_SESSION_MAX_MIN = "30"
_SCENARIO_PATH = (Path(__file__).resolve().parent.parent
                  / "scenarios" / "age_of_ai_interview.js")
_FIXTURE_SCENARIO_PATH = (Path(__file__).resolve().parent.parent
                          / "scenarios" / "age_of_ai_fixture_guest.js")


class VoximplantError(RuntimeError):
    pass


def _auth() -> Dict[str, str]:
    account_id = os.environ.get("VOXIMPLANT_ACCOUNT_ID", "").strip()
    api_key = os.environ.get("VOXIMPLANT_API_KEY", "").strip()
    if not account_id or not api_key:
        raise VoximplantError(
            "VOXIMPLANT_ACCOUNT_ID / VOXIMPLANT_API_KEY env vars are required"
        )
    return {"account_id": account_id, "api_key": api_key}


def _call(method: str, **params: Any) -> Dict[str, Any]:
    payload = {**_auth(), **params}
    resp = requests.post(f"{API_BASE}/{method}", data=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise VoximplantError(f"{method}: {data['error']}")
    return data


def start_interview_scenario(run_id: str,
                             rule_name: str = RULE_NAME) -> Dict[str, Any]:
    """Fire the interview scenario for one interview_runs row.

    Returns the StartScenarios response (contains media_session_access_url
    and call session info the caller records on the run row).
    """
    result = _call(
        "StartScenarios",
        rule_name=rule_name,
        application_name=APPLICATION_NAME,
        script_custom_data=json.dumps({"run_id": run_id}),
    )
    logger.info("Voximplant scenario fired for run %s: %s", run_id, result)
    return result


def start_room_probe(run_id: str, clip_url: str,
                     rule_name: str = RULE_NAME) -> Dict[str, Any]:
    """Diagnostics (Sept 9 2026): start a PROBE session for an interview run
    — a synthetic participant that joins the room and plays ``clip_url``
    into it (see probeSession in the scenario). The room's scenario_trace
    then shows whether the mixer and Mira heard it."""
    return _call(
        "StartScenarios",
        rule_name=rule_name,
        application_name=APPLICATION_NAME,
        script_custom_data=json.dumps({"run_id": run_id, "probe": True, "clip": clip_url}),
    )


def start_narration_take(take_id: str, text: str, voice: str = "ara",
                         rule_name: str = RULE_NAME,
                         audio_rate: int | None = None) -> Dict[str, Any]:
    """Start a session in which Mira READS one paragraph of a scripted pickup
    (see narrationSession in the scenario, Sept 11 2026).

    One paragraph per session: Voximplant tears down a session with no call
    after 60 seconds, and a two-minute introduction does not fit in that. The
    scenario reports the recording URL to the Worker, which writes it onto the
    narration_takes row this ``take_id`` names.
    """
    return _call(
        "StartScenarios",
        rule_name=rule_name,
        application_name=APPLICATION_NAME,
        script_custom_data=json.dumps({
            "narrate": True, "take_id": take_id, "text": text, "voice": voice,
            # PCM output rate for this read (see audioOutputFormat in the
            # scenario). None = whatever the module negotiates today.
            "audio_rate": int(audio_rate) if audio_rate else None,
        }),
    )


def start_fixture_guest(run_id: str, *, persona: str, voice: str = "sal",
                        minutes: int = 10, speaks_first: bool = False,
                        fixture_id: str = "", guest_name: str = "",
                        cough_clip: Optional[str] = None,
                        silence_ms: Optional[int] = None,
                        beats: Optional[List[Dict[str, Any]]] = None,
                        room_prefix: str = "room-",
                        rule_name: str = FIXTURE_RULE_NAME) -> Dict[str, Any]:
    """Send the FIXTURE GUEST into an interview room (rehearsal harness).

    Starts ``age_of_ai_fixture_guest.js`` on its own rule with the persona
    and the scheduled behaviours in customData; the fixture then places the
    same callConference a human leg does, so the room session starts (or
    admits it) exactly as it would for a person. ``persona`` is rendered by
    ``pipelines/voices/rehearsal.py`` and is the only large field.
    """
    if not persona or not persona.strip():
        raise VoximplantError("a fixture guest needs a persona")
    custom: Dict[str, Any] = {
        "run_id": run_id, "fixture": True, "fixture_id": fixture_id,
        "guest_name": guest_name, "persona": persona, "voice": voice,
        "minutes": int(minutes), "speaks_first": bool(speaks_first),
    }
    if cough_clip:
        custom["cough_clip"] = cough_clip
    if silence_ms:
        custom["silence_ms"] = int(silence_ms)
    if beats:
        custom["beats"] = beats
    if room_prefix not in ("room-", CANDIDATE_ROOM_PREFIX):
        raise VoximplantError(f"unknown room prefix {room_prefix!r}")
    if room_prefix != "room-":
        custom["room_prefix"] = room_prefix
    result = _call(
        "StartScenarios",
        rule_name=rule_name,
        application_name=APPLICATION_NAME,
        script_custom_data=json.dumps(custom),
    )
    logger.info("fixture guest %s started for run %s", fixture_id or "?", run_id)
    return result


def upload_scenario(path: Path,
                    scenario_name: str = SCENARIO_NAME,
                    supabase_url: Optional[str] = None,
                    supabase_service_key: Optional[str] = None,
                    xai_api_key: Optional[str] = None,
                    room_prefix: Optional[str] = None) -> Dict[str, Any]:
    """Create or update the scenario source from *path* (deploy step).

    ``__SUPABASE_URL__``, ``__SUPABASE_SERVICE_KEY__``, ``__XAI_API_KEY__``
    and ``__GROK_VOICE_MODEL__`` in the source are substituted here so the committed
    scenario never carries a project-specific hostname or secrets. The
    secrets live only in the deployed copy inside the Voximplant account.

    (July 2026: replaces the application-custom-data secret design —
    VoxEngine has no ``Application.customData()`` and the Management API's
    ``SetApplicationInfo`` accepts no ``application_custom_data`` param;
    both were written from spec, not live docs.)
    """
    source = path.read_text(encoding="utf-8")
    if room_prefix:
        source = candidate_source(source, room_prefix)
    supabase_url = supabase_url or os.environ.get("SUPABASE_URL", "").strip()
    if not supabase_url:
        raise VoximplantError("SUPABASE_URL required to deploy the scenario")
    source = source.replace("__SUPABASE_URL__", supabase_url.rstrip("/"))

    service_key = (supabase_service_key
                   or os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
                   or os.environ.get("VOICES_SUPABASE_SERVICE_KEY", "").strip())
    xai_key = (xai_api_key
               or os.environ.get("XAI_API_KEY", "").strip()
               or os.environ.get("GROK_API_KEY", "").strip())
    if not service_key or not xai_key:
        raise VoximplantError(
            "SUPABASE_SERVICE_KEY and XAI_API_KEY/GROK_API_KEY are required "
            "to deploy the scenario (deploy-time secret substitution)")
    source = source.replace("__SUPABASE_SERVICE_KEY__", service_key)
    source = source.replace("__XAI_API_KEY__", xai_key)

    # Voice Agent model (Sept 10 2026): the Voximplant connector defaults to
    # xAI's DEPRECATED `grok-voice-fast-1.0`; when xAI stopped serving it,
    # every interview died with a bare WebSocket 1011. Always deploy an
    # explicit model. Override with the GROK_VOICE_MODEL repo variable.
    voice_model = (os.environ.get("GROK_VOICE_MODEL", "").strip()
                   or DEFAULT_GROK_VOICE_MODEL)
    source = source.replace("__GROK_VOICE_MODEL__", voice_model)
    # Session relay: xAI kills one Voice Agent session at this many minutes
    # (30 on Tier 3). The room hands over to a fresh session 4 min before,
    # so a 45-minute interview survives. Lower it to rehearse a hand-over.
    session_max = (os.environ.get("GROK_SESSION_MAX_MIN", "").strip()
                   or DEFAULT_GROK_SESSION_MAX_MIN)
    source = source.replace("__GROK_SESSION_MAX_MIN__", str(session_max))
    # Request signing (Oct 21 2026): when VOICES_WEBHOOK_SECRET is set the
    # room signs every request it makes to the Worker (X-Voices-Signature,
    # hex HMAC-SHA256 of the body) and the Worker, deployed with the same
    # secret, refuses unsigned ones. Unset leaves the placeholder, which the
    # scenario reads as "send no header".
    webhook_secret = os.environ.get("VOICES_WEBHOOK_SECRET", "").strip()
    if webhook_secret:
        source = source.replace("__VOICES_WEBHOOK_SECRET__", webhook_secret)
    print(f"scenario deploys with Grok voice model {voice_model}, "
          f"session cap {session_max} min", flush=True)

    try:
        return _call("SetScenarioInfo",
                     required_scenario_name=scenario_name,
                     scenario_script=source)
    except VoximplantError:
        # First deploy: the scenario doesn't exist yet.
        return _call("AddScenario",
                     scenario_name=scenario_name,
                     scenario_script=source)


def candidate_source(source: str, room_prefix: str = CANDIDATE_ROOM_PREFIX) -> str:
    """The interview scenario's source with its room prefix changed, so the
    copy answers only ``<prefix><run id>`` calls. Refuses when the prefix line
    is not there exactly once (a candidate that still answered ``room-`` calls
    would be a second live scenario)."""
    if source.count(_ROOM_PREFIX_LINE) != 1:
        raise VoximplantError("interview scenario has no single ROOM_PREFIX line to retarget")
    if room_prefix == "room-" or not room_prefix.endswith("-"):
        raise VoximplantError(f"bad candidate room prefix {room_prefix!r}")
    return source.replace(_ROOM_PREFIX_LINE, f'const ROOM_PREFIX = "{room_prefix}";')


def upload_candidate_scenario(path: Optional[Path] = None) -> Dict[str, Any]:
    """Upload THIS checkout's interview scenario as the rehearsal candidate
    (same deploy-time substitutions, its own name and room prefix). The live
    ``age_of_ai_interview`` is never touched."""
    return upload_scenario(path or _SCENARIO_PATH, scenario_name=CANDIDATE_SCENARIO_NAME,
                           room_prefix=CANDIDATE_ROOM_PREFIX)


def upload_fixture_scenario(path: Optional[Path] = None) -> Dict[str, Any]:
    """Deploy the fixture-guest scenario with the same deploy-time
    substitutions as the interview scenario (same placeholders, same
    secrets, same pinned voice model)."""
    return upload_scenario(path or _FIXTURE_SCENARIO_PATH,
                           scenario_name=FIXTURE_SCENARIO_NAME)


def set_application_secrets(supabase_service_key: str,
                            xai_api_key: str) -> Dict[str, Any]:
    """Deploy/refresh scenario secrets (kept for the documented call
    pattern). Secrets are substituted into the scenario source at deploy
    time, so this simply re-runs :func:`upload_scenario` with them."""
    return upload_scenario(
        _SCENARIO_PATH,
        supabase_service_key=supabase_service_key,
        xai_api_key=xai_api_key,
    )


def add_user(user_name: str, user_display_name: str, user_password: str,
             application_name: str = APPLICATION_NAME) -> Dict[str, Any]:
    """Create a Voximplant application user (Management API ``AddUser``).

    Phase 2 co-host (docs/cohost_phase2_contract.md): the ``host`` user is
    created ONCE at operator bootstrap, alongside the existing ``guest``
    user, and its credentials go into the Worker as
    ``VOX_HOST_USER`` / ``VOX_HOST_PASSWORD``. The scenario dials it with
    ``VoxEngine.callUser({username: host, ...})`` so Patrick's studio page
    (logged in via the Web SDK) rings and auto-answers. Re-running this for
    an existing user raises ``VoximplantError`` (the API rejects the
    duplicate) — check :func:`list_users` first if you need idempotence.

    Returns the AddUser response (``{"result": 1, "user_id": ...}``).
    """
    if not user_name or not user_password:
        raise VoximplantError("user_name and user_password are required")
    if len(user_password) < 6:
        raise VoximplantError("Voximplant user passwords must be at least 6 characters")
    result = _call(
        "AddUser",
        user_name=user_name,
        user_display_name=user_display_name or user_name,
        user_password=user_password,
        application_name=application_name,
    )
    logger.info("Voximplant user %s created in %s: %s", user_name,
                application_name, result)
    return result


def list_users(application_name: str = APPLICATION_NAME) -> List[Dict[str, Any]]:
    """List the application's users (Management API ``GetUsers``).

    Returns the ``result`` list (``user_name``, ``user_display_name``,
    ``user_id``, ``user_active`` ...). Used by the bootstrap to check
    whether ``guest`` / ``host`` already exist before :func:`add_user`.
    """
    data = _call("GetUsers", application_name=application_name)
    return list(data.get("result") or [])


def send_sms(dest_number: str, text: str,
             source_number: Optional[str] = None) -> Dict[str, Any]:
    """Interview-reminder SMS (spec timeline: T-2h). Uses Mira's caller ID
    by default so the guest recognizes the number that will call them."""
    source = source_number or os.environ.get("VOXIMPLANT_CALLER_ID", "").strip()
    if not source:
        raise VoximplantError("source number required for SMS (VOXIMPLANT_CALLER_ID)")
    return _call("SendSmsMessage",
                 source=source,
                 destination=dest_number,
                 sms_body=text[:640])


# ---------------------------------------------------------------------------
# Studio users: derived passwords, one source of truth (Sept 9 2026)
# ---------------------------------------------------------------------------
# Dan Perra's live interview: the browser studio could not sign in because
# the Worker's VOX_GUEST_PASSWORD and the `guest` user's password in
# Voximplant had been typed on different days and did not match. Nobody
# should ever type these. Both sides now DERIVE the password from the
# ADMIN_TOKEN they already share (HMAC-SHA256, hex, plus a suffix that
# satisfies Voximplant's letters+digits rule), and the deploy workflow
# pushes the derived value onto the users with SetUserInfo. The Worker's
# studio-auth computes the same value (workers/voices/src/index.ts,
# studioPassword()). Change ADMIN_TOKEN → rerun the deploy workflow.

# Room model (Sept 9 2026): every participant — the co-host included —
# signs in as the shared `guest` user; the role travels in the call's
# X-Role header. The `host` user is kept in sync too so old links and the
# Web SDK auto-answer path keep working, but nothing depends on it.
STUDIO_USERS = {"guest": "Age of AI Guest", "host": "Patrick (co-host)"}


def derive_studio_password(user_name: str, admin_token: Optional[str] = None) -> str:
    """Deterministic per-user password from the shared ADMIN_TOKEN.

    Must stay byte-for-byte identical to ``studioPassword()`` in the
    Worker: ``hex(HMAC_SHA256(admin_token, "nerra-studio:" + user))[:32] + "Aa1"``.
    """
    import hashlib
    import hmac
    token = (admin_token if admin_token is not None else os.environ.get("ADMIN_TOKEN", "")).strip()
    if not token:
        raise VoximplantError("ADMIN_TOKEN is required to derive studio passwords")
    digest = hmac.new(token.encode("utf-8"), f"nerra-studio:{user_name}".encode("utf-8"),
                      hashlib.sha256).hexdigest()
    return digest[:32] + "Aa1"


def sync_studio_users(application_name: str = APPLICATION_NAME,
                      admin_token: Optional[str] = None) -> Dict[str, str]:
    """Create-or-update the ``guest`` and ``host`` users with their derived
    passwords (Management API ``SetUserInfo``, ``AddUser`` when missing).
    Returns {user: "updated"|"created"}. Never logs the passwords."""
    existing = {u.get("user_name") for u in list_users(application_name)}
    out: Dict[str, str] = {}
    for user, display in STUDIO_USERS.items():
        password = derive_studio_password(user, admin_token)
        if user in existing:
            _call("SetUserInfo", user_name=user, application_name=application_name,
                  user_password=password, user_active=True)
            out[user] = "updated"
        else:
            _call("AddUser", user_name=user, user_display_name=display,
                  user_password=password, application_name=application_name,
                  user_active=True)
            out[user] = "created"
        logger.info("studio user %s %s (password derived from ADMIN_TOKEN)", user, out[user])
    return out


# ---------------------------------------------------------------------------
# Session logs (Sept 9 2026): read the scenario's Logger output after a run
# ---------------------------------------------------------------------------

def recent_session_logs(hours: float = 2.0, limit: int = 5,
                        application_name: str = APPLICATION_NAME) -> List[Dict[str, Any]]:
    """The last ``limit`` call sessions of the application with their
    VoxEngine log text (Management API ``GetCallHistory`` → ``log_file_url``).
    Used by the "Voximplant session logs" workflow so a failed rehearsal can
    be read from GitHub without panel access."""
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc)
    fmt = "%Y-%m-%d %H:%M:%S"
    data = _call("GetCallHistory", application_name=application_name,
                 from_date=(now - _dt.timedelta(hours=hours)).strftime(fmt),
                 to_date=now.strftime(fmt), count=limit, with_calls="true",
                 with_records="true", desc_order="true")
    out: List[Dict[str, Any]] = []
    for sess in data.get("result") or []:
        entry = {
            "session_id": sess.get("call_session_history_id"),
            "start": sess.get("start_date"), "duration": sess.get("duration"),
            "calls": [{"direction": c.get("direction"), "remote": c.get("remote_number"),
                       "duration": c.get("duration"), "successful": c.get("successful")}
                      for c in sess.get("calls") or []],
            "log": "",
        }
        url = sess.get("log_file_url")
        if url:
            try:
                resp = requests.get(url, timeout=60)
                # The whole log: the workflow saves it as an artifact. A tail
                # cut at 60 kB had kept only the last two minutes of a
                # fifteen-minute rehearsal (Oct 22 2026), and the opening is
                # usually where the fault is.
                entry["log"] = resp.text
            except Exception as exc:  # noqa: BLE001
                entry["log"] = f"(log fetch failed: {exc})"
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Routing rules (Sept 9 2026): the interview room
# ---------------------------------------------------------------------------
# Every participant session joins its interview with
# VoxEngine.callConference("room-<run_id>", ...). Voximplant routes that
# call through the application's rules like any other and merges all calls
# with the same conference id into ONE session — the room. The rule below
# makes sure "room-*" lands on the interview scenario and is evaluated
# before any catch-all rule (rules match in order; ReorderRules puts it
# first).

ROOM_RULE_NAME = os.environ.get("VOXIMPLANT_ROOM_RULE_NAME", "age-of-ai-room")
ROOM_RULE_PATTERN = r"^room-.*"


def list_rules(application_name: str = APPLICATION_NAME) -> List[Dict[str, Any]]:
    """The application's routing rules (Management API ``GetRules``), in
    evaluation order — ``rule_name``, ``rule_pattern``, ``rule_id``, ``scenarios``."""
    data = _call("GetRules", application_name=application_name, with_scenarios="true")
    return list(data.get("result") or [])


def ensure_room_rule(application_name: str = APPLICATION_NAME,
                     scenario_name: str = SCENARIO_NAME,
                     rule_name: str = ROOM_RULE_NAME,
                     pattern: str = ROOM_RULE_PATTERN) -> Dict[str, Any]:
    """Create the room rule if missing and move it to the top of the rule
    list. Idempotent; returns {"rule_id", "created", "reordered", "rules"}
    where ``rules`` is the final ordered [(name, pattern)] list."""
    rules = list_rules(application_name)
    existing = next((r for r in rules if r.get("rule_name") == rule_name), None)
    created = False
    if existing is None:
        res = _call("AddRule", application_name=application_name,
                    rule_name=rule_name, rule_pattern=pattern,
                    scenario_name=scenario_name)
        rule_id = res.get("rule_id")
        created = True
        logger.info("Voximplant rule %s (%s) created: %s", rule_name, pattern, res)
        rules = list_rules(application_name)
    else:
        rule_id = existing.get("rule_id")
        # The panel stores the pattern without a leading ^ (it anchors
        # itself); compare normalised so a no-op deploy stays a no-op.
        if str(existing.get("rule_pattern") or "").lstrip("^") != pattern.lstrip("^"):
            _call("SetRuleInfo", rule_id=rule_id, rule_pattern=pattern)
            logger.info("Voximplant rule %s pattern set to %s", rule_name, pattern)
    order = [r.get("rule_id") for r in rules]
    reordered = False
    if order and order[0] != rule_id and rule_id in order:
        order.remove(rule_id)
        order.insert(0, rule_id)
        _call("ReorderRules", rule_id=";".join(str(i) for i in order))
        reordered = True
        rules = list_rules(application_name)
    return {
        "rule_id": rule_id, "created": created, "reordered": reordered,
        "rules": [(r.get("rule_name"), r.get("rule_pattern")) for r in rules],
    }


def ensure_fixture_rule(application_name: str = APPLICATION_NAME,
                        scenario_name: str = FIXTURE_SCENARIO_NAME,
                        rule_name: str = FIXTURE_RULE_NAME,
                        pattern: str = FIXTURE_RULE_PATTERN) -> Dict[str, Any]:
    """Create the fixture-guest rule if missing (rehearsal harness).

    A StartScenarios call names a RULE, and a rule names a scenario, so the
    fixture scenario needs one. Its pattern can never match an inbound call
    (nothing dials ``fixture-guest-never-dialled``) and it is never moved to
    the top: the room rule keeps its place. Idempotent."""
    rules = list_rules(application_name)
    existing = next((r for r in rules if r.get("rule_name") == rule_name), None)
    if existing is not None:
        return {"rule_id": existing.get("rule_id"), "created": False}
    res = _call("AddRule", application_name=application_name,
                rule_name=rule_name, rule_pattern=pattern,
                scenario_name=scenario_name)
    logger.info("Voximplant rule %s (%s) created for %s: %s", rule_name, pattern,
                scenario_name, res)
    return {"rule_id": res.get("rule_id"), "created": True}


def ensure_candidate_room_rule(application_name: str = APPLICATION_NAME,
                               scenario_name: str = CANDIDATE_SCENARIO_NAME,
                               rule_name: str = CANDIDATE_ROOM_RULE_NAME,
                               pattern: str = CANDIDATE_ROOM_RULE_PATTERN) -> Dict[str, Any]:
    """Create the candidate-room rule if missing and keep it second, right
    after the live room rule, so no catch-all rule can take a candidate call
    and the live room rule is never displaced. Its pattern matches only
    ``candroom-*`` (the fixture guest) and ``mira-candidate`` (a person
    joining from a rehearsal invite's studio link)."""
    rules = list_rules(application_name)
    existing = next((r for r in rules if r.get("rule_name") == rule_name), None)
    created = False
    if existing is None:
        res = _call("AddRule", application_name=application_name,
                    rule_name=rule_name, rule_pattern=pattern,
                    scenario_name=scenario_name)
        rule_id = res.get("rule_id")
        created = True
        logger.info("Voximplant rule %s (%s) created: %s", rule_name, pattern, res)
        rules = list_rules(application_name)
    else:
        rule_id = existing.get("rule_id")
        if str(existing.get("rule_pattern") or "").lstrip("^") != pattern.lstrip("^"):
            _call("SetRuleInfo", rule_id=rule_id, rule_pattern=pattern)
            logger.info("Voximplant rule %s pattern set to %s", rule_name, pattern)
    order = [r.get("rule_id") for r in rules]
    room = next((r.get("rule_id") for r in rules if r.get("rule_name") == ROOM_RULE_NAME), None)
    want = 1 if room is not None and order and order[0] == room else 0
    reordered = False
    if rule_id in order and order.index(rule_id) != want:
        order.remove(rule_id)
        order.insert(want, rule_id)
        _call("ReorderRules", rule_id=";".join(str(i) for i in order))
        reordered = True
    return {"rule_id": rule_id, "created": created, "reordered": reordered}
