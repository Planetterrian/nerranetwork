"""Runtime guards for the unofficial cookie-auth analytics connectors.

The Spotify and Apple creator dashboards ship no official API, so the
network reads them through the community ``spotifyconnector`` /
``appleconnector`` packages (see ``docs/analytics.md``). Both embed a
fixed retry loop with *unbounded* exponential backoff: on a failing
endpoint they sleep 4s, 8s, 16s, 32s, 64s before giving up.

That is fine when a failure is transient. It is pathological when the
failure is **stable** — and for these platforms it usually is. A show
whose feed is registered but has no plays yet answers ``500`` on
``/metadata`` and ``/aggregate`` every single night. Measured
2026-07-25: 18 of 24 registered Spotify feeds were in that state,
~32 failing endpoints × ~124s of backoff each, so the nightly fetch
step ran for well over an hour before the rest of maintenance could
start. Nothing surfaced it, because the output JSON only records the
final error — never the wall-clock cost of getting there.

Two guards, both used by the fetchers:

``clamp_connector_retries``
    Rewrites the connector module's retry constants in place so a dead
    endpoint costs seconds, not minutes. Defensive by contract: a
    package upgrade that renames or drops the constants is a silent
    no-op, never a crash.

``FetchBudget``
    A wall-clock backstop. Whatever the retry constants end up being,
    the fetch stops and reports partial results once the budget is
    spent — so a future upstream behaviour change can never again turn
    one nightly step into an hours-long stall.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def clamp_connector_retries(
    module: Any,
    *,
    attempts_attr: str,
    delay_attr: str,
    attempts: int,
    delay_base: float,
) -> dict[str, Any]:
    """Bound a connector module's retry budget, in place.

    ``spotifyconnector`` and ``appleconnector`` both read module-level
    constants inside their request loop, so assigning to them is enough
    — there is no per-instance knob to pass.

    Returns a dict describing what was applied (empty values when an
    attribute is absent), so callers can log the effective settings
    rather than assume them.
    """
    applied: dict[str, Any] = {}
    for attr, value in ((attempts_attr, attempts), (delay_attr, delay_base)):
        if hasattr(module, attr):
            setattr(module, attr, value)
            applied[attr] = value
    return applied


@dataclass
class FetchBudget:
    """Wall-clock budget for a multi-show fetch loop.

    ``seconds <= 0`` disables the budget entirely (never exhausted),
    which is what a caller passes when it wants the legacy
    run-until-done behaviour.
    """

    seconds: float
    _started: float = field(default_factory=time.monotonic)

    @classmethod
    def from_env(cls, name: str, default: float) -> "FetchBudget":
        return cls(seconds=_env_float(name, default))

    def elapsed(self) -> float:
        return time.monotonic() - self._started

    def remaining(self) -> float:
        if self.seconds <= 0:
            return float("inf")
        return self.seconds - self.elapsed()

    def exhausted(self) -> bool:
        return self.remaining() <= 0


__all__ = [
    "FetchBudget",
    "clamp_connector_retries",
    "_env_float",
    "_env_int",
]
