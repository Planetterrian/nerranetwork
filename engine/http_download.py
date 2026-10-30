"""One bounded, visible way to pull a published file back down.

Oct 30 2026: Nerra Daily Ep069 (Oct 28) spent 81 minutes with no log line
between choosing its lineup and calling the links model; every other build
that week took about six. The segment loop downloaded each show's MP3 with
``requests.get(stream=True, timeout=600)`` — a READ timeout, so a CDN that
trickles a few bytes every few minutes never trips it — and logged nothing
per segment, so the stall could not even be located. The edition published
at 12:17 UTC instead of 06:50 ET and its X post went to the 12:30 slot.

:func:`download_to` gives every such pull a wall-clock deadline per attempt,
a short read timeout for a dead socket, a few attempts, and one log line per
file with its size and time. Nerra Daily and Nerra Personal both use it.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

#: Connect and per-read timeouts (seconds). A read that waits longer than
#: this for the next chunk is a dead socket.
CONNECT_TIMEOUT_S = 20
READ_TIMEOUT_S = 60
#: Wall-clock limit for ONE attempt. A 25 MB episode arrives in a few
#: seconds from R2; five minutes is a trickle, never a slow good transfer.
ATTEMPT_DEADLINE_S = 300
ATTEMPTS = 3
RETRY_PAUSE_S = 5
_CHUNK = 1 << 16

_sleep = time.sleep
_clock = time.monotonic


class DownloadTooSlow(RuntimeError):
    """An attempt ran past :data:`ATTEMPT_DEADLINE_S`."""


def _attempt(requests_mod, url: str, part: Path, deadline_s: float) -> int:
    started = _clock()
    written = 0
    with requests_mod.get(url, stream=True,
                          timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S)) as resp:
        resp.raise_for_status()
        with part.open("wb") as fh:
            for chunk in resp.iter_content(_CHUNK):
                if chunk:
                    fh.write(chunk)
                    written += len(chunk)
                if _clock() - started > deadline_s:
                    raise DownloadTooSlow(
                        f"{written} bytes in {deadline_s:.0f} s — abandoned")
    return written


def download_to(url: str, dest: Path, *, label: str = "",
                deadline_s: float = ATTEMPT_DEADLINE_S,
                attempts: int = ATTEMPTS) -> int:
    """Download *url* to *dest*; returns the byte count.

    Each attempt writes a ``.part`` file and is abandoned past *deadline_s*;
    a 4xx is an answer and raises at once. The last failure is re-raised.
    """
    import requests

    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    name = label or dest.name
    last: Exception = RuntimeError("no attempt made")
    for attempt in range(1, max(1, attempts) + 1):
        if attempt > 1:
            _sleep(RETRY_PAUSE_S * (attempt - 1))
        started = _clock()
        try:
            size = _attempt(requests, url, part, deadline_s)
        except requests.HTTPError as exc:
            status = getattr(exc.response, "status_code", None) or 0
            part.unlink(missing_ok=True)
            if 400 <= status < 500:
                raise
            last = exc
        except Exception as exc:  # noqa: BLE001 — transport, trickle: try again
            part.unlink(missing_ok=True)
            last = exc
        else:
            part.replace(dest)
            logger.info("downloaded %s: %.1f MB in %.1f s (attempt %d)",
                        name, size / 1e6, _clock() - started, attempt)
            return size
        logger.warning("download %s attempt %d/%d failed after %.0f s: %s",
                       name, attempt, attempts, _clock() - started, last)
    raise last
