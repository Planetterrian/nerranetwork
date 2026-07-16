"""Thin Voximplant Management API wrapper for the Nerra Voices pipeline.

Covers exactly what fire_interviews.py and the deploy tooling need:

* ``start_interview_scenario(run_id)`` — StartScenarios with the interview
  run id as customData (the scenario pulls everything else from Supabase).
* ``upload_scenario(path)`` — create/update the scenario source (deploy).
* ``set_application_secrets(...)`` — store SUPABASE_SERVICE_KEY /
  XAI_API_KEY as application custom data the scenario reads via
  ``Application.customData()``.

Auth: account-level API key (VOXIMPLANT_ACCOUNT_ID + VOXIMPLANT_API_KEY env
vars), per https://voximplant.com/docs/references/httpapi. All calls raise
``VoximplantError`` on non-success so callers fail loud.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.voximplant.com/platform_api"

# Names must match what's provisioned in the Voximplant panel (phase 1).
APPLICATION_NAME = os.environ.get("VOXIMPLANT_APP_NAME", "nerra-voices")
RULE_NAME = os.environ.get("VOXIMPLANT_RULE_NAME", "age-of-ai-interview")
SCENARIO_NAME = "age_of_ai_interview"
_SCENARIO_PATH = (Path(__file__).resolve().parent.parent
                  / "scenarios" / "age_of_ai_interview.js")


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


def upload_scenario(path: Path,
                    scenario_name: str = SCENARIO_NAME,
                    supabase_url: Optional[str] = None,
                    supabase_service_key: Optional[str] = None,
                    xai_api_key: Optional[str] = None) -> Dict[str, Any]:
    """Create or update the scenario source from *path* (deploy step).

    ``__SUPABASE_URL__``, ``__SUPABASE_SERVICE_KEY__`` and
    ``__XAI_API_KEY__`` in the source are substituted here so the committed
    scenario never carries a project-specific hostname or secrets. The
    secrets live only in the deployed copy inside the Voximplant account.

    (July 2026: replaces the application-custom-data secret design —
    VoxEngine has no ``Application.customData()`` and the Management API's
    ``SetApplicationInfo`` accepts no ``application_custom_data`` param;
    both were written from spec, not live docs.)
    """
    source = path.read_text(encoding="utf-8")
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

    try:
        return _call("SetScenarioInfo",
                     required_scenario_name=scenario_name,
                     scenario_script=source)
    except VoximplantError:
        # First deploy: the scenario doesn't exist yet.
        return _call("AddScenario",
                     scenario_name=scenario_name,
                     scenario_script=source)


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
