#!/usr/bin/env python3
"""Check each published episode against its show's must-haves — Daily Audit.

Nov 24 2026. SpaceX Ep165, Ep168 and Ep169 shipped without a share price
because the show's pre-fetch hook timed out and the run went on without
its data. The Grok read in ``review_episodes.py`` flagged SpaceX on six of
eight days that week and never named the gap; a hand review found it a
week later. Two instruments here, both reading only committed files:

* **Contracts** (``shows/contracts/must_haves.yaml``): per show, a closed
  list of facts every episode must carry, each a regex over the published
  digest. A ``page`` miss fails the step (``--strict``) the day it ships,
  like a stale feed; a ``warn`` miss is a ``::warning::``.
* **Counter flips**: a boolean counter in ``metrics_ep<N>.json`` that held
  one value on at least ``FLIP_SHARE`` of the show's previous
  ``FLIP_WINDOW`` episodes and holds the other today (``pre_fetch_hook_failed``
  false -> true, ``script_hook_orphaned`` false -> true). Listed, never
  paged: a flip can be good news (``digest_expansion_fired`` true -> false).

Output ``api/show_contracts.json`` (consumers: ``scripts/pick_review_target.py``
— ``misses_14d`` raises a show's review priority — and
``scripts/dispatch_quality_reviews.py``, which dispatches a review for a
show with a page-severity miss today). A show with no episode today is
absent from ``today``; a contract never reads a members-only episode.

Usage::

    python scripts/check_show_contracts.py --strict --out api/show_contracts.json
    python scripts/check_show_contracts.py --show spacex --history
    python scripts/check_show_contracts.py --date 2026-11-21 --dry-run
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONTRACTS_FILE = ROOT / "shows" / "contracts" / "must_haves.yaml"
SEVERITIES = ("page", "warn")
#: Episodes read for ``misses_14d`` and the ``--history`` table.
HISTORY_EPISODES = 14
#: Counter flips: the prior window and the share it must agree on.
FLIP_WINDOW = 14
FLIP_MIN_PRIOR = 7
FLIP_SHARE = 0.85

_EP_RE = re.compile(r"Ep(\d+)_(\d{8})\.md$")


def load_contracts(path: Path = CONTRACTS_FILE) -> Dict[str, List[Dict[str, Any]]]:
    """The contracts, validated: every pattern compiles, ids are unique per
    show, severity is page|warn. Raises ValueError on a bad file — a broken
    contract must fail CI, never silently pass every episode."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping of show slugs")
    out: Dict[str, List[Dict[str, Any]]] = {}
    for slug, lines in data.items():
        if not isinstance(lines, list) or not lines:
            raise ValueError(f"{slug}: must be a non-empty list of checks")
        seen = set()
        checks = []
        for line in lines:
            cid = str(line.get("id") or "").strip()
            if not cid or cid in seen:
                raise ValueError(f"{slug}: missing or duplicate id {cid!r}")
            seen.add(cid)
            severity = line.get("severity", "page")
            if severity not in SEVERITIES:
                raise ValueError(f"{slug}.{cid}: severity must be page|warn")
            if not line.get("what"):
                raise ValueError(f"{slug}.{cid}: needs a 'what' sentence")
            try:
                regex = re.compile(line["pattern"])
            except (KeyError, re.error) as exc:
                raise ValueError(f"{slug}.{cid}: bad pattern: {exc}") from exc
            checks.append({"id": cid, "what": line["what"], "regex": regex,
                           "severity": severity,
                           "unless_counter": line.get("unless_counter")})
        out[str(slug)] = checks
    return out


def _registry() -> Dict[str, Dict[str, Any]]:
    from review_episodes import SHOW_REGISTRY
    return SHOW_REGISTRY


def digest_files(root: Path, info: Dict[str, Any]) -> List[Tuple[int, str, Path]]:
    """``[(episode, YYYYMMDD, path)]`` for the show's published digests at
    the top level of its output dir (never ``members/``), oldest first."""
    out_dir = root / info["output_dir"]
    found = []
    for path in out_dir.glob(f"{info['prefix']}*.md"):
        m = _EP_RE.search(path.name)
        if m:
            found.append((int(m.group(1)), m.group(2), path))
    found.sort()
    return found


def load_counters(root: Path, info: Dict[str, Any], episode: int) -> Optional[Dict[str, Any]]:
    path = root / info["output_dir"] / f"metrics_ep{episode}.json"
    try:
        counters = json.loads(path.read_text(encoding="utf-8")).get("counters")
    except (OSError, ValueError, AttributeError):
        return None
    return counters if isinstance(counters, dict) else None


def check_text(checks: List[Dict[str, Any]], text: str,
               counters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One result per check: ``ok`` True/False, or ``skipped`` with why."""
    results = []
    for c in checks:
        gate = c.get("unless_counter")
        if gate and counters and counters.get(gate):
            results.append({"id": c["id"], "ok": None, "skipped": f"{gate} set"})
            continue
        results.append({"id": c["id"], "ok": bool(c["regex"].search(text)),
                        "what": c["what"], "severity": c["severity"]})
    return results


def counter_flips(history: List[Optional[Dict[str, Any]]],
                  today: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Boolean counters whose value today is the opposite of what the prior
    episodes agreed on. *history* is the prior episodes' counters, oldest
    first; an episode with no metrics file is left out of the vote."""
    if not today:
        return []
    prior = [c for c in history[-FLIP_WINDOW:] if c]
    if len(prior) < FLIP_MIN_PRIOR:
        return []
    flips = []
    for key, value in sorted(today.items()):
        if not isinstance(value, bool):
            continue
        votes = [c.get(key) for c in prior]
        agree = sum(1 for v in votes if v is (not value))
        if agree / len(prior) >= FLIP_SHARE:
            flips.append({"counter": key, "usual": not value, "today": value,
                          "agreeing": f"{agree}/{len(prior)}"})
    return flips


def build_report(root: Path, contracts: Dict[str, List[Dict[str, Any]]],
                 registry: Dict[str, Dict[str, Any]], date: _dt.date,
                 only: str = "") -> Dict[str, Any]:
    stamp = date.strftime("%Y%m%d")
    shows: Dict[str, Any] = {}
    page: List[str] = []
    warn: List[str] = []
    for slug, info in registry.items():
        if only and slug != only:
            continue
        files = digest_files(root, info)
        if not files:
            continue
        checks = contracts.get(slug)
        entry: Dict[str, Any] = {}
        if checks:
            misses_14d = 0
            for ep, _d, path in files[-HISTORY_EPISODES:]:
                res = check_text(checks, path.read_text(encoding="utf-8", errors="replace"),
                                 load_counters(root, info, ep))
                misses_14d += sum(1 for r in res if r["ok"] is False
                                  and r["severity"] == "page")
            entry["misses_14d"] = misses_14d
        todays = [(ep, path) for ep, d, path in files if d == stamp]
        episodes = []
        for ep, path in todays:
            counters = load_counters(root, info, ep)
            row: Dict[str, Any] = {"episode": ep, "digest": str(path.relative_to(root))}
            if checks:
                res = check_text(checks, path.read_text(encoding="utf-8", errors="replace"), counters)
                row["checks"] = res
                for r in res:
                    if r["ok"] is False:
                        line = f"{slug} Ep{ep}: missing — {r['what']} ({r['id']})"
                        (page if r["severity"] == "page" else warn).append(line)
            prior_eps = [e for e, _d, _p in files if e < ep][-FLIP_WINDOW:]
            row["counter_flips"] = counter_flips(
                [load_counters(root, info, e) for e in prior_eps], counters)
            episodes.append(row)
        if episodes:
            entry["today"] = episodes
        if entry:
            shows[slug] = entry
    return {
        "generated": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": date.isoformat(),
        "contracts": "shows/contracts/must_haves.yaml",
        "history_episodes": HISTORY_EPISODES,
        "page": page,
        "warn": warn,
        "shows": shows,
        "consumers": ["scripts/pick_review_target.py (misses_14d)",
                      "scripts/dispatch_quality_reviews.py (page)",
                      "tests/test_review_loop_automation_2026_11_24.py"],
    }


def print_history(root: Path, contracts, registry, slug: str) -> None:
    info = registry[slug]
    checks = contracts.get(slug) or []
    for ep, d, path in digest_files(root, info)[-HISTORY_EPISODES:]:
        res = check_text(checks, path.read_text(encoding="utf-8", errors="replace"),
                         load_counters(root, info, ep))
        cells = " ".join(f"{r['id']}={'skip' if r['ok'] is None else ('ok' if r['ok'] else 'MISS')}"
                         for r in res)
        print(f"{slug} Ep{ep} {d}  {cells}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today, Eastern)")
    parser.add_argument("--show", default="")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--history", action="store_true",
                        help="print the last 14 episodes' results for --show")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 on a page-severity miss today")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    contracts = load_contracts(root / "shows" / "contracts" / "must_haves.yaml")
    registry = _registry()
    if args.history:
        if not args.show:
            print("--history needs --show", file=sys.stderr)
            return 2
        print_history(root, contracts, registry, args.show)
        return 0
    if args.date:
        date = _dt.date.fromisoformat(args.date)
    else:
        from review_episodes import network_today
        date = network_today()

    doc = build_report(root, contracts, registry, date, args.show)
    for line in doc["page"]:
        print(f"::error::Must-have missing: {line}")
    for line in doc["warn"]:
        print(f"::warning::Must-have missing: {line}")
    for slug, entry in doc["shows"].items():
        for ep in entry.get("today", []):
            for f in ep.get("counter_flips", []):
                print(f"{slug} Ep{ep['episode']}: {f['counter']} is {f['today']} "
                      f"(was {f['usual']} on {f['agreeing']} prior episodes)")
    if not doc["page"] and not doc["warn"]:
        print(f"Must-haves: every checked episode on {doc['date']} carries them.")
    if not args.dry_run:
        out = args.out or (root / "api" / "show_contracts.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {out}")
    return 1 if (args.strict and doc["page"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
