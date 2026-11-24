#!/usr/bin/env python3
"""The weekly review slate — one page a week for every open review PR.

Nov 24 2026 (register ``review-loop-automation-2026-11-24``, item 6). The
review agent opened a PR per show per run and the daily audit dispatched more
between runs; by Nov 24 nine sat open, each needing its own read, and they
were merged in one sitting as records. This script turns them into ONE slate:

* **Tier A (records only — ``docs/reviews/**``)** merges on its own here,
  with ``--apply``, once every changed ledger parses and no check failed.
  A records PR changes no show; leaving it open only stalls the rotation
  (``pick_review_target`` reads the merged ledger date).
* **Tier B (listen)** is listed with its rehearsal: "Ready for your listen"
  once a ``Run show`` rehearsal on its branch succeeded, else "Waiting on a
  rehearsal". Never merged here — the operator's listen is the merge.
* **Tier C (operator)** is listed for the operator. Never merged here.
* A PR open longer than ``STALE_DAYS`` is flagged, never closed.

The slate also carries the week's readout misses
(``api/register_readouts.json``) and must-have misses
(``api/show_contracts.json``), so the review loop's results and its open
work are read in one place. It is published as one rolling issue (label
``review-slate``) and the job summary.

Tiers: ``scripts/review_changes.tier_for_paths``. Usage::

    python scripts/review_slate.py              # dry run: print the slate
    python scripts/review_slate.py --apply      # merge tier A, publish the issue
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from review_changes import (  # noqa: E402
    TIER_LISTEN, TIER_NAMES, TIER_OPERATOR, TIER_RECORD, tier_for_paths)

BRANCH_PREFIX = "agent/review-"
STALE_DAYS = 21
SLATE_LABEL = "review-slate"
SLATE_TITLE = "Weekly review slate"
_GREEN = {"SUCCESS", "NEUTRAL", "SKIPPED"}
_RED = {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE", "ERROR"}

Runner = Callable[[List[str]], str]


def _gh(args: List[str]) -> str:
    proc = subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])} failed: {proc.stderr.strip()[-400:]}")
    return proc.stdout


def checks_state(rollup: List[Dict[str, Any]]) -> str:
    """``green`` / ``red`` / ``pending`` / ``none`` from a statusCheckRollup."""
    if not rollup:
        return "none"
    states = []
    for c in rollup:
        status = str(c.get("status") or "COMPLETED").upper()
        concl = str(c.get("conclusion") or c.get("state") or "").upper()
        if status != "COMPLETED" or concl in ("PENDING", "EXPECTED", ""):
            states.append("pending")
        elif concl in _RED:
            states.append("red")
        elif concl in _GREEN:
            states.append("green")
        else:
            states.append("red")
    if "red" in states:
        return "red"
    if "pending" in states:
        return "pending"
    return "green"


def ledgers_parse(paths: List[str], read: Callable[[str], str]) -> str:
    """'' when every changed ledger is valid YAML with a ``reviews`` list,
    else the first failure. *read* returns a file's text at the PR head."""
    for path in paths:
        if not (path.startswith("docs/reviews/ledger/") and path.endswith(".yaml")):
            continue
        try:
            data = yaml.safe_load(read(path))
        except Exception as exc:  # noqa: BLE001 — YAML error or a missing file
            return f"{path}: {str(exc).splitlines()[0][:160]}"
        if not isinstance(data, dict) or not isinstance(data.get("reviews"), list):
            return f"{path}: no reviews list"
    return ""


def classify(pr: Dict[str, Any], rehearsal: Optional[Dict[str, Any]],
             today: _dt.date) -> Dict[str, Any]:
    paths = [f.get("path", "") for f in pr.get("files") or []]
    tier = tier_for_paths(paths)
    created = str(pr.get("createdAt") or "")[:10]
    try:
        age = (today - _dt.date.fromisoformat(created)).days
    except ValueError:
        age = None
    checks = checks_state(pr.get("statusCheckRollup") or [])
    if tier == TIER_RECORD:
        bucket = "records"
    elif tier == TIER_LISTEN:
        ok = rehearsal and str(rehearsal.get("conclusion") or "").lower() == "success"
        bucket = "listen" if ok else "rehearsal"
    else:
        bucket = "operator"
    return {"number": pr.get("number"), "title": pr.get("title", ""),
            "url": pr.get("url", ""), "branch": pr.get("headRefName", ""),
            "tier": tier, "bucket": bucket, "checks": checks, "age_days": age,
            "stale": age is not None and age > STALE_DAYS, "paths": paths,
            "rehearsal": rehearsal}


def _rehearsal(branch: str, gh: Runner) -> Optional[Dict[str, Any]]:
    try:
        runs = json.loads(gh(["run", "list", "--workflow", "run-show.yml",
                              "--branch", branch, "--limit", "5",
                              "--json", "url,status,conclusion,createdAt"]) or "[]")
    except (RuntimeError, ValueError):
        return None
    return runs[0] if runs else None


def _read_at(branch: str) -> Callable[[str], str]:
    def read(path: str) -> str:
        subprocess.run(["git", "fetch", "-q", "--depth=1", "origin", branch],
                       cwd=ROOT, capture_output=True)
        proc = subprocess.run(["git", "show", f"FETCH_HEAD:{path}"],
                              cwd=ROOT, capture_output=True, text=True)
        if proc.returncode != 0:
            raise FileNotFoundError(path)
        return proc.stdout
    return read


def merge_records(item: Dict[str, Any], gh: Runner,
                  read: Callable[[str], str]) -> str:
    """Merge one tier-A PR. Returns '' on success, else why it was held."""
    if item["checks"] in ("red", "pending"):
        return f"checks {item['checks']}"
    why = ledgers_parse(item["paths"], read)
    if why:
        return f"ledger does not parse: {why}"
    try:
        gh(["pr", "ready", str(item["number"])])
        gh(["pr", "merge", str(item["number"]), "--squash", "--delete-branch"])
    except RuntimeError as exc:
        return str(exc)
    return ""


def _load(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def render(items: List[Dict[str, Any]], merged: List[Dict[str, Any]],
           held: List[Dict[str, Any]], root: Path, today: _dt.date) -> str:
    def line(i: Dict[str, Any]) -> str:
        extra = [f"checks {i['checks']}", f"{i['age_days']} d open"]
        if i.get("rehearsal"):
            extra.append(f"[rehearsal]({i['rehearsal'].get('url', '')}) "
                         f"{i['rehearsal'].get('conclusion') or i['rehearsal'].get('status')}")
        if i.get("held"):
            extra.append(f"held: {i['held']}")
        flag = " — **stale**" if i["stale"] else ""
        return f"- [#{i['number']}]({i['url']}) {i['title']} ({', '.join(extra)}){flag}"

    out = [f"# {SLATE_TITLE} — {today.isoformat()}", "",
           "Generated by `scripts/review_slate.py`. Tiers: A record (merged here "
           "once its ledger parses), B listen (merge after hearing the rehearsal), "
           "C operator. Rules: docs/REVIEW_AGENT.md, \"Merge tiers\".", ""]
    sections = [
        ("Ready for your listen (tier B, rehearsal done)",
         [i for i in items if i["bucket"] == "listen"]),
        ("Waiting on a rehearsal (tier B)",
         [i for i in items if i["bucket"] == "rehearsal"]),
        ("For the operator (tier C)", [i for i in items if i["bucket"] == "operator"]),
        ("Records held (tier A)", held),
        ("Merged this run (tier A, records only)", merged),
    ]
    for title, rows in sections:
        out.append(f"## {title}")
        out.extend(line(i) for i in rows) if rows else out.append("None.")
        out.append("")

    readouts = _load(root / "api" / "register_readouts.json")
    out.append("## Readouts that missed their target")
    misses = readouts.get("misses") or []
    if misses:
        out.extend(f"- {m}" if isinstance(m, str) else
                   f"- `{m.get('id')}`: {m.get('live')} vs `{m.get('target_rule')}`"
                   for m in misses)
    else:
        out.append("None scored a miss." if readouts else "Register readout not read.")
    out.append("")

    contracts = _load(root / "api" / "show_contracts.json")
    out.append("## Must-haves missed (last audit)")
    page = (contracts.get("page") or []) + (contracts.get("warn") or [])
    out.extend(f"- {p}" for p in page) if page else out.append(
        "None." if contracts else "Must-have report not read.")
    out.append("")
    return "\n".join(out)


def publish_issue(body: str, gh: Runner) -> None:
    found = json.loads(gh(["issue", "list", "--label", SLATE_LABEL, "--state", "open",
                           "--json", "number", "--limit", "1"]) or "[]")
    path = ROOT / ".review_slate.md"
    path.write_text(body, encoding="utf-8")
    try:
        if found:
            gh(["issue", "edit", str(found[0]["number"]), "--body-file", str(path)])
        else:
            try:
                gh(["label", "create", SLATE_LABEL, "--color", "5319e7",
                    "--description", "The weekly review slate"])
            except RuntimeError:
                pass  # already exists
            gh(["issue", "create", "--title", SLATE_TITLE, "--label", SLATE_LABEL,
                "--body-file", str(path)])
    finally:
        path.unlink(missing_ok=True)


def build(gh: Runner = _gh, apply: bool = False, today: Optional[_dt.date] = None,
          root: Path = ROOT, read_at: Callable[[str], Callable[[str], str]] = _read_at
          ) -> Dict[str, Any]:
    today = today or _dt.date.today()
    prs = json.loads(gh(["pr", "list", "--state", "open", "--limit", "100", "--json",
                         "number,title,url,headRefName,isDraft,createdAt,files,"
                         "statusCheckRollup"]) or "[]")
    items = []
    for pr in prs:
        if not str(pr.get("headRefName", "")).startswith(BRANCH_PREFIX):
            continue
        branch = pr["headRefName"]
        items.append(classify(pr, _rehearsal(branch, gh), today))
    merged, held = [], []
    for i in [i for i in items if i["bucket"] == "records"]:
        if not apply:
            i["held"] = "dry run"
            held.append(i)
            continue
        why = merge_records(i, gh, read_at(i["branch"]))
        if why:
            i["held"] = why
            held.append(i)
        else:
            merged.append(i)
    rest = [i for i in items if i["bucket"] != "records"]
    body = render(rest, merged, held, root, today)
    return {"items": items, "merged": merged, "held": held, "body": body}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true",
                        help="merge tier-A records PRs and publish the slate issue")
    args = parser.parse_args(argv)
    doc = build(apply=args.apply)
    print(doc["body"])
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(doc["body"] + "\n")
    if args.apply:
        publish_issue(doc["body"], _gh)
    counts = {t: sum(1 for i in doc["items"] if i["tier"] == t)
              for t in (TIER_RECORD, TIER_LISTEN, TIER_OPERATOR)}
    print(f"slate: {len(doc['items'])} open review PRs "
          + ", ".join(f"{TIER_NAMES[t]} {n}" for t, n in counts.items())
          + f"; merged {len(doc['merged'])}, held {len(doc['held'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
