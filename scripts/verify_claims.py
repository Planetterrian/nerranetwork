#!/usr/bin/env python3
"""Verify committed episode claim ledgers against their sources.

The in-pipeline gate (``engine.claims.run_source_integrity_gate``, wired
into ``run_show.py`` before the digest save and before TTS) is what blocks a
fabricated citation from publishing. This CLI is the same gate pointed at
COMMITTED episodes, for three jobs:

* audit — re-verify published ledgers (sources rot; a URL that resolved at
  publish time can die, and the show notes still cite it);
* CI / workflow use — ``--strict`` exits non-zero when anything fails, so a
  workflow step can hard-fail on regression;
* exposure — episodes with no ledger sidecar are reported lint-only (their
  citation-shaped sentences are unverifiable by definition).

Checks per claim (design doc §2.2): the ``source_url`` must resolve (HTTP
200, non-empty body); the ``supporting_quote`` must actually appear in the
fetched source (normalised whitespace, fuzzy >= 0.9); the ``episode_span``
must appear in the digest. HTTP fetches + string matching only — no model
calls.

Usage:
    python scripts/verify_claims.py unintended_consequences            # latest episode
    python scripts/verify_claims.py unintended_consequences --latest 5
    python scripts/verify_claims.py --all --latest 3
    python scripts/verify_claims.py <slug> --episode 71
    python scripts/verify_claims.py --all --strict --no-fetch          # offline: anchoring + lint only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine import claims as claims_mod  # noqa: E402
from engine.config import discover_show_slugs, load_config  # noqa: E402

_DIGEST_NAME_RE = re.compile(r"_Ep(\d+)_(\d{8})\.md$")


def digest_files_for_show(slug: str) -> list[Path]:
    try:
        config = load_config(PROJECT_ROOT / "shows" / f"{slug}.yaml")
        out_dir = PROJECT_ROOT / config.episode.output_dir
    except Exception:
        out_dir = PROJECT_ROOT / "digests" / slug
    if not out_dir.is_dir():
        return []
    files = [p for p in out_dir.glob("*.md") if _DIGEST_NAME_RE.search(p.name)]

    def _key(p: Path):
        m = _DIGEST_NAME_RE.search(p.name)
        return (int(m.group(2)), int(m.group(1)))

    return sorted(files, key=_key)


def verify_episode(digest_path: Path, *, fetch_sources: bool) -> dict:
    text = digest_path.read_text(encoding="utf-8", errors="replace")
    sidecar = claims_mod.claims_sidecar_path(digest_path)
    ledger = claims_mod.load_ledger(digest_path) if sidecar.exists() else None

    gate = claims_mod.run_source_integrity_gate(
        text, ledger, verify_sources=fetch_sources,
    )
    return {
        "digest": str(digest_path.relative_to(PROJECT_ROOT)),
        "sidecar": sidecar.exists(),
        "passed": gate.passed,
        "summary": gate.summary(),
        "report": gate.to_report(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("show", nargs="?", help="Show slug (or use --all)")
    ap.add_argument("--all", action="store_true", help="Every show")
    ap.add_argument("--episode", type=int, help="Specific episode number")
    ap.add_argument("--latest", type=int, default=1,
                    help="How many most-recent episodes per show (default 1)")
    ap.add_argument("--no-fetch", action="store_true",
                    help="Skip HTTP source checks (anchoring + lint only)")
    ap.add_argument("--strict", action="store_true",
                    help="Exit non-zero if any checked episode fails")
    ap.add_argument("--json", help="Write full results to this JSON path")
    args = ap.parse_args()

    if not args.show and not args.all:
        ap.error("give a show slug or --all")
    slugs = discover_show_slugs() if args.all else [args.show]

    results = []
    failed = 0
    for slug in slugs:
        files = digest_files_for_show(slug)
        if args.episode is not None:
            files = [
                p for p in files
                if int(_DIGEST_NAME_RE.search(p.name).group(1)) == args.episode
            ]
        else:
            files = files[-args.latest:]
        for path in files:
            res = verify_episode(path, fetch_sources=not args.no_fetch)
            results.append(res)
            flag = "PASS" if res["passed"] else "FAIL"
            ledger = "ledger" if res["sidecar"] else "NO-LEDGER"
            print(f"[{flag}] [{ledger}] {res['digest']} — {res['summary']}")
            if not res["passed"]:
                failed += 1
                rep = res["report"]
                for v in rep["failed_verifications"]:
                    print(f"    claim {v['id']}: {v['reason']} ({v['url']})")
                for u in rep["uncovered_shapes"]:
                    print(f"    uncovered {u['match']!r}: {u['sentence'][:120]}")
                for e in rep["shape_errors"]:
                    print(f"    malformed: {e}")

    print(f"\n{len(results)} episode(s) checked, {failed} failed")
    if args.json:
        Path(args.json).write_text(
            json.dumps(results, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return 1 if (args.strict and failed) else 0


if __name__ == "__main__":
    sys.exit(main())
