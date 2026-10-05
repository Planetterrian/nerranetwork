#!/usr/bin/env python3
"""Nightly re-verification of flagged claims (Oct 1 2026, flag mode).

``on_failure: flag`` publishes an episode with every ledger entry's status
VISIBLE instead of stripping the sentence or skipping the day — because the
model's training data lags the 24-hour cycle and a sourced, timely story is
exactly what the gate cannot vouch for on the day (a 403 from the
publisher, a paraphrased quote, a page that had not propagated yet). This
script is the second half of that policy: for every committed
``digests/**/*_claims.json`` whose digest date is within the last
``--days`` (default 7) and which carries an ``unverified_*`` entry that CAN
be re-checked (unreachable / not_found / quote_mismatch — never an
uncovered sentence, which has no url, or a malformed entry, which has no
quote), it re-runs the SAME mechanical check the gate ran
(``engine.claims.verify_claim_sources``: URL resolves, quote fuzzy-appears
at 0.9). A claim that now verifies becomes ``status: verified_later`` with
``verified_at`` and keeps its original failure in ``first_status``; the
gate's ``verified_count`` / ``flagged_count`` / ``flagged_sentences`` are
recomputed. A verified claim is NEVER downgraded. Idempotent: a second run
over the same files changes nothing.

Dry run by default (prints counts); ``--apply`` writes. Polite: one fetch
per URL, at least one second between requests to the same host, 20 s
timeout, and nothing here ever raises — a bad sidecar is logged and
skipped, a dead host is a still-unverified claim.

Usage:
    python scripts/reverify_claims.py                 # dry run, last 7 days
    python scripts/reverify_claims.py --apply --days 7
    python scripts/reverify_claims.py --show spacex --days 14
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine import claims as claims_mod  # noqa: E402

_SIDECAR_NAME_RE = re.compile(r"_Ep(\d+)_(\d{8})_claims\.json$")

#: Minimum gap between two requests to the same host.
HOST_PACING_SECONDS = 1.0
FETCH_TIMEOUT_SECONDS = 20


def sidecar_date(path: Path):
    """The digest DATE from the sidecar's filename, never the file mtime
    (a fresh checkout rewrites mtimes)."""
    import datetime as _dt
    m = _SIDECAR_NAME_RE.search(path.name)
    if not m:
        return None
    try:
        return _dt.datetime.strptime(m.group(2), "%Y%m%d").date()
    except ValueError:
        return None


def recent_sidecars(root: Path, days: int, today=None,
                    show: Optional[str] = None) -> List[Path]:
    import datetime as _dt
    today = today or _dt.date.today()
    cutoff = today - _dt.timedelta(days=days)
    out: List[Path] = []
    pattern = f"digests/{show}/*_claims.json" if show else "digests/**/*_claims.json"
    for p in sorted(root.glob(pattern)):
        d = sidecar_date(p)
        if d is None or d < cutoff or d > today:
            continue
        out.append(p)
    return out


def needs_reverify(payload: dict) -> bool:
    entries = payload.get("claims") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return False
    return any(
        isinstance(e, dict)
        and str(e.get("status") or "") in claims_mod.REVERIFIABLE_STATUSES
        for e in entries
    )


def make_paced_fetch(
    base_fetch: Optional[Callable[[str], Tuple[int, str]]] = None,
    pacing_seconds: float = HOST_PACING_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Callable[[str], Tuple[int, str]]:
    """Wrap a fetch with per-host pacing (>= *pacing_seconds* between two
    requests to one host) and a 20 s timeout. One fetch per URL per run."""
    last_hit: Dict[str, float] = {}
    cache: Dict[str, Tuple[int, str]] = {}

    def _default(url: str) -> Tuple[int, str]:
        import requests
        resp = requests.get(
            url, timeout=FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NerraSourceCheck/1.0)"},
            allow_redirects=True,
        )
        ctype = (resp.headers.get("content-type") or "").lower()
        if "html" in ctype or ctype.startswith("text/") or "xml" in ctype:
            return resp.status_code, resp.text
        return resp.status_code, ""

    fetch = base_fetch or _default

    def _paced(url: str) -> Tuple[int, str]:
        if url in cache:
            return cache[url]
        try:
            host = (urlsplit(url).netloc or "").lower()
        except ValueError:
            host = ""
        now = clock()
        wait = pacing_seconds - (now - last_hit.get(host, -1e9))
        if wait > 0:
            sleep(wait)
        try:
            result = fetch(url)
        finally:
            last_hit[host] = clock()
        cache[url] = result
        return result

    return _paced


def reverify_file(path: Path, fetch: Callable[[str], Tuple[int, str]],
                  today: Optional[str] = None, apply: bool = False) -> dict:
    """Re-verify one sidecar. Never raises."""
    rel = str(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"file": rel, "error": f"unreadable: {exc}", "candidates": 0,
                "verified_later": 0, "still_unverified": 0, "written": False}
    if not needs_reverify(payload):
        return {"file": rel, "candidates": 0, "verified_later": 0,
                "still_unverified": 0, "written": False}
    try:
        new, stats = claims_mod.reverify_ledger_payload(payload, fetch=fetch, today=today)
    except Exception as exc:  # noqa: BLE001
        return {"file": rel, "error": f"reverify failed: {exc}", "candidates": 0,
                "verified_later": 0, "still_unverified": 0, "written": False}
    written = False
    if apply and stats.get("changed"):
        try:
            path.write_text(
                json.dumps(new, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            written = True
        except Exception as exc:  # noqa: BLE001
            return {"file": rel, "error": f"write failed: {exc}", **stats,
                    "written": False}
    return {"file": rel, **stats, "written": written}


def run(root: Path, days: int, apply: bool, show: Optional[str] = None,
        fetch: Optional[Callable[[str], Tuple[int, str]]] = None,
        today=None) -> dict:
    files = recent_sidecars(root, days, today=today, show=show)
    paced = make_paced_fetch(fetch)
    stamp = today.isoformat() if today else None
    results = [reverify_file(p, paced, today=stamp, apply=apply) for p in files]
    totals = {
        "files_in_window": len(files),
        "files_with_candidates": sum(1 for r in results if r.get("candidates")),
        "candidates": sum(int(r.get("candidates") or 0) for r in results),
        "verified_later": sum(int(r.get("verified_later") or 0) for r in results),
        "still_unverified": sum(int(r.get("still_unverified") or 0) for r in results),
        "written": sum(1 for r in results if r.get("written")),
        "errors": sum(1 for r in results if r.get("error")),
    }
    return {"totals": totals, "results": results}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--days", type=int, default=7,
                    help="Re-verify sidecars whose digest date is within this many days (default 7)")
    ap.add_argument("--apply", action="store_true",
                    help="Write the updated sidecars (default: dry run, print counts)")
    ap.add_argument("--show", help="Only this show's digests directory (digests/<dir>)")
    ap.add_argument("--json", help="Write the full per-file report to this path")
    args = ap.parse_args(argv)

    try:
        report = run(PROJECT_ROOT, args.days, args.apply, show=args.show)
    except Exception as exc:  # noqa: BLE001 — never a red nightly
        print(f"::warning::reverify_claims: {exc}")
        return 0
    t = report["totals"]
    mode = "APPLY" if args.apply else "DRY RUN"
    print(
        f"[{mode}] {t['files_in_window']} sidecar(s) in the last {args.days} day(s); "
        f"{t['files_with_candidates']} with re-checkable claims; "
        f"{t['candidates']} claim(s) re-verified: {t['verified_later']} now verify "
        f"(verified_later), {t['still_unverified']} still unverified; "
        f"{t['written']} file(s) written, {t['errors']} error(s)"
    )
    for r in report["results"]:
        if r.get("error"):
            print(f"  [error] {r['file']}: {r['error']}")
        elif r.get("candidates"):
            print(f"  {r['file']}: {r['verified_later']}/{r['candidates']} verified later"
                  + (" (written)" if r.get("written") else ""))
    if args.json:
        try:
            Path(args.json).write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            print(f"::warning::reverify_claims: could not write {args.json}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
