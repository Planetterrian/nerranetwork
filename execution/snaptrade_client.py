"""Thin, defensive wrapper around the SnapTrade Python SDK.

Phase 1 (read-only) of docs/mit_snaptrade_live_trading_plan.md. There is
deliberately NO order-placing method here — trading code arrives in a
later phase behind its own risk layer.

Configuration comes from four environment variables (dashboard → API
Keys for the first two; ``scripts/snaptrade_setup.py`` mints the last
two once):

- ``SNAPTRADE_CLIENT_ID``
- ``SNAPTRADE_CONSUMER_KEY``
- ``SNAPTRADE_USER_ID``
- ``SNAPTRADE_USER_SECRET``

The SDK (``pip install snaptrade-python-sdk``) is imported lazily so the
podcast pipeline never needs it installed. Responses are normalized to
plain dicts/lists via ``_body`` because SDK versions differ in whether
they return a wrapped response object or raw data.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_ENV_KEYS = (
    "SNAPTRADE_CLIENT_ID",
    "SNAPTRADE_CONSUMER_KEY",
    "SNAPTRADE_USER_ID",
    "SNAPTRADE_USER_SECRET",
)


def is_configured() -> bool:
    """True when all four SnapTrade env vars are non-empty."""
    return all(os.environ.get(k, "").strip() for k in _ENV_KEYS)


def missing_config() -> list[str]:
    return [k for k in _ENV_KEYS if not os.environ.get(k, "").strip()]


def _sdk():
    """Import and construct the SDK client (lazy; clear error if absent)."""
    try:
        from snaptrade_client import SnapTrade
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "snaptrade-python-sdk is not installed. "
            "Run: pip install snaptrade-python-sdk"
        ) from exc
    return SnapTrade(
        client_id=os.environ["SNAPTRADE_CLIENT_ID"],
        consumer_key=os.environ["SNAPTRADE_CONSUMER_KEY"],
    )


def _user_kwargs() -> dict:
    return {
        "user_id": os.environ["SNAPTRADE_USER_ID"],
        "user_secret": os.environ["SNAPTRADE_USER_SECRET"],
    }


def _body(resp):
    """Normalize SDK responses across versions (``.body``/``.data``/raw)."""
    for attr in ("body", "data", "parsed"):
        value = getattr(resp, attr, None)
        if value is not None:
            return value
    return resp


def register_user(user_id: str) -> dict:
    """Register a SnapTrade user; returns {userId, userSecret}.

    One-time operation — the secret is only returned once. Requires only
    the two API-key env vars.
    """
    snaptrade = _sdk()
    resp = snaptrade.authentication.register_snap_trade_user(user_id=user_id)
    return dict(_body(resp))


def connection_portal_url(broker: str | None = None,
                          connection_type: str = "trade") -> str:
    """Return a login URL for the hosted Connection Portal.

    ``connection_type='trade'`` requests read+trade scope up front so a
    later phase doesn't force a reconnection; pass ``'read'`` to be
    conservative. ``broker`` (e.g. ``WEALTHSIMPLETRADE``) preselects an
    institution when given; omitted, the portal shows the picker.
    """
    snaptrade = _sdk()
    kwargs = dict(_user_kwargs(), connection_type=connection_type)
    if broker:
        kwargs["broker"] = broker
    resp = snaptrade.authentication.login_snap_trade_user(**kwargs)
    body = _body(resp)
    url = body.get("redirectURI") if isinstance(body, dict) else None
    if not url:
        raise RuntimeError(f"Unexpected login response shape: {body!r}")
    return url


def list_connections() -> list[dict]:
    """Brokerage authorizations (one per connected institution)."""
    snaptrade = _sdk()
    resp = snaptrade.connections.list_brokerage_authorizations(**_user_kwargs())
    return list(_body(resp) or [])


def list_accounts() -> list[dict]:
    """All accounts across the user's connections."""
    snaptrade = _sdk()
    resp = snaptrade.account_information.list_user_accounts(**_user_kwargs())
    return list(_body(resp) or [])


def account_positions(account_id: str) -> list[dict]:
    snaptrade = _sdk()
    resp = snaptrade.account_information.get_user_account_positions(
        account_id=account_id, **_user_kwargs())
    return list(_body(resp) or [])


def account_balances(account_id: str) -> list[dict]:
    snaptrade = _sdk()
    resp = snaptrade.account_information.get_user_account_balance(
        account_id=account_id, **_user_kwargs())
    return list(_body(resp) or [])


def recent_orders(account_id: str) -> list[dict]:
    snaptrade = _sdk()
    resp = snaptrade.account_information.get_user_account_orders(
        account_id=account_id, **_user_kwargs())
    return list(_body(resp) or [])
