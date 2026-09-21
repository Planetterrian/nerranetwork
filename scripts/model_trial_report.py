#!/usr/bin/env python3
"""Score a staged model change on latency and run-success.

``docs/model_upgrade_playbook.md`` exists because the 2026-08-18 grok-4.6
flip took down 7 of 12 shows the next morning, and the post-mortem's sharpest
line is this: the registered revert triggers watched hallucination rate,
reviewer flags and fetch tool-calls, and **nobody watched latency**. The
failure that actually fired was operational.

So this is the instrument the next upgrade is read on. It answers rule 2 of
the playbook — "gate on latency before quality" — from the only longitudinal,
committed record the repo keeps of how long a stage took: every show's
``digests/<slug>/metrics_ep*.json``, which carries a ``stages`` list of
``{name, duration_s, success}``.

**It reads, it never writes.** A trial's verdict has to be reproducible from
the repo at any later date, by anyone, without a live API key.

**Dating an episode.** The metrics file is named for its episode number and
carries no date, so the date comes from the sibling digest markdown
(``Omni_View_Ep182_20260921.md``). That is committed alongside it and cannot
drift from it, which a file mtime can and does — every one of these files was
rewritten by the last checkout.

What it reports, per show and per stage: sample size, p50/p95/max duration,
and the share of the per-request timeout the p95 consumes. What it GATES on
is the playbook's own arithmetic:

* p95 of any LLM stage must stay under 50% of ``NERRA_LLM_TIMEOUT_SECONDS``
  (default 300 s). A slower model is not disqualified, but then the timeout
  moves in the same PR and the whole envelope is recomputed.
* no stage may regress its p95 by more than ``--max-p95-regression`` percent
  against the baseline window.
* run success must not fall.

Exit code 1 when the gate fails, so a workflow step can stop a widening.

Usage::

    python scripts/model_trial_report.py --since 2026-09-22
    python scripts/model_trial_report.py --since 2026-09-22 --shows omni_view
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

#: The per-request timeout the envelope is built on. The playbook's rule 3
#: chain is: this x 3 tenacity attempts < PIPELINE_TIMEOUT_SECONDS < the CI
#: step kill. Read from the environment so a PR that raises it is scored
#: against its own value.
DEFAULT_TIMEOUT_S = float(os.environ.get("NERRA_LLM_TIMEOUT_SECONDS", "300"))

#: Playbook rule 2: p95 under half the request timeout. Above this a stage
#: has no headroom for the variance a real morning produces.
P95_TIMEOUT_SHARE_LIMIT = 0.50

#: Stages whose duration is dominated by an LLM call. Others (render, fetch)
#: are reported but never gate a MODEL trial — they are not the model's.
_LLM_STAGE_PREFIXES = (
    "generate_digest",
    "generate_podcast_script",
    "synth",
    "claim_repair",
    "script_rewrite",
)

_EP_RE = re.compile(r"metrics_ep(\d+)\.json$")
_DIGEST_DATE_RE = re.compile(r"_Ep0*(\d+)_(\d{8})")


def _is_llm_stage(name: str) -> bool:
    return any(name.startswith(p) for p in _LLM_STAGE_PREFIXES)


def _episode_dates(show_dir: Path) -> Dict[int, _dt.date]:
    """episode number -> date, from the committed digest filenames.

    Never file mtime: a fresh checkout rewrites every mtime in the repo, so
    an mtime-dated report silently reads as "everything happened today".
    """
    out: Dict[int, _dt.date] = {}
    for path in show_dir.glob("*.md"):
        m = _DIGEST_DATE_RE.search(path.name)
        if not m:
            continue
        try:
            date = _dt.datetime.strptime(m.group(2), "%Y%m%d").date()
        except ValueError:
            continue
        num = int(m.group(1))
        # A re-run writes a second file for one episode; the later date wins,
        # which is the run that actually shipped.
        if num not in out or date > out[num]:
            out[num] = date
    return out


def collect(show_dir: Path) -> List[dict]:
    """Every committed episode's stage timings, dated. Unreadable files are
    skipped rather than fatal — one bad JSON must not void a trial."""
    dates = _episode_dates(show_dir)
    rows = []
    for path in sorted(show_dir.glob("metrics_ep*.json")):
        m = _EP_RE.search(path.name)
        if not m:
            continue
        num = int(m.group(1))
        date = dates.get(num)
        if date is None:
            continue  # no dated digest beside it: cannot place it in a window
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        stages = data.get("stages")
        if not isinstance(stages, list):
            continue
        rows.append({
            "episode": num,
            "date": date,
            "stages": [s for s in stages if isinstance(s, dict)],
            "total_duration_s": data.get("total_duration_s"),
        })
    return rows


def _pct(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    # Nearest-rank: with the sample sizes a 3-day trial produces, an
    # interpolated percentile invents precision the data does not have.
    idx = min(len(ordered) - 1, max(0, int(round(q * len(ordered))) - 1))
    return ordered[idx]


def summarise(rows: List[dict]) -> Dict[str, dict]:
    """stage name -> {n, p50, p95, max, failures}."""
    by_stage: Dict[str, List[float]] = {}
    failures: Dict[str, int] = {}
    for row in rows:
        for stage in row["stages"]:
            name = stage.get("name") or "?"
            duration = stage.get("duration_s")
            if isinstance(duration, (int, float)):
                by_stage.setdefault(name, []).append(float(duration))
            if stage.get("success") is False:
                failures[name] = failures.get(name, 0) + 1
    return {
        name: {
            "n": len(vals),
            "p50": _pct(vals, 0.50),
            "p95": _pct(vals, 0.95),
            "max": max(vals),
            "failures": failures.get(name, 0),
        }
        for name, vals in sorted(by_stage.items())
    }


def _fmt(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:7.1f}"


def report(
    shows: List[str],
    since: _dt.date,
    baseline_days: int,
    timeout_s: float,
    max_p95_regression_pct: float,
) -> int:
    baseline_start = since - _dt.timedelta(days=baseline_days)
    failures: List[str] = []
    any_trial_data = False

    print(f"Model trial report — trial from {since}, "
          f"baseline {baseline_start}..{since - _dt.timedelta(days=1)}")
    print(f"Request timeout {timeout_s:.0f}s; p95 must stay under "
          f"{timeout_s * P95_TIMEOUT_SHARE_LIMIT:.0f}s "
          f"({P95_TIMEOUT_SHARE_LIMIT:.0%} of it)\n")

    for slug in shows:
        show_dir = REPO_ROOT / "digests" / slug
        if not show_dir.is_dir():
            continue
        rows = collect(show_dir)
        if not rows:
            continue
        base = summarise([r for r in rows if baseline_start <= r["date"] < since])
        trial = summarise([r for r in rows if r["date"] >= since])
        if not trial:
            continue
        any_trial_data = True

        print(f"=== {slug}")
        print(f"    {'stage':34} {'n':>3} {'p50':>8} {'p95':>8} {'max':>8}"
              f"   {'baseline p95':>12}  {'Δp95':>7}")
        for name, stats in trial.items():
            b = base.get(name)
            delta = ""
            if b and b["p95"] and stats["p95"]:
                change = (stats["p95"] - b["p95"]) / b["p95"] * 100.0
                delta = f"{change:+6.0f}%"
                if _is_llm_stage(name) and change > max_p95_regression_pct:
                    failures.append(
                        f"{slug}/{name}: p95 {stats['p95']:.0f}s is "
                        f"{change:+.0f}% against a {b['p95']:.0f}s baseline "
                        f"(limit +{max_p95_regression_pct:.0f}%)")
            print(f"    {name:34} {stats['n']:>3} {_fmt(stats['p50'])} "
                  f"{_fmt(stats['p95'])} {_fmt(stats['max'])}   "
                  f"{_fmt(b['p95']) if b else '           —'}  {delta:>7}")

            if _is_llm_stage(name) and stats["p95"] is not None:
                share = stats["p95"] / timeout_s
                if share > P95_TIMEOUT_SHARE_LIMIT:
                    failures.append(
                        f"{slug}/{name}: p95 {stats['p95']:.0f}s is "
                        f"{share:.0%} of the {timeout_s:.0f}s request "
                        "timeout — no headroom (playbook rule 2)")
            if stats["failures"]:
                failures.append(
                    f"{slug}/{name}: {stats['failures']} failed stage(s) "
                    "in the trial window")
        print()

    if not any_trial_data:
        print("No committed episodes on or after the trial date yet — "
              "nothing to score. This is the expected answer on day zero.")
        return 0

    if failures:
        print("GATE: FAIL")
        for line in failures:
            print(f"  - {line}")
        print("\nDo not widen. Revert is one line in shows/_defaults.yaml "
              "(playbook rule 5).")
        return 1

    print("GATE: PASS — latency and run-success are within the envelope.")
    print("Latency is necessary and not sufficient: read quality before "
          "widening (playbook rule 2), and A/B-listen anything that changed "
          "spoken prose (landmine #17).")
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True,
                        help="Trial start date, YYYY-MM-DD.")
    parser.add_argument("--baseline-days", type=int, default=14)
    parser.add_argument("--shows", default="",
                        help="Comma-separated slugs; default is every show "
                             "with committed metrics.")
    parser.add_argument("--timeout-seconds", type=float,
                        default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--max-p95-regression-pct", type=float, default=50.0,
                        help="How much slower an LLM stage's p95 may get "
                             "before the gate fails.")
    args = parser.parse_args(argv)

    try:
        since = _dt.date.fromisoformat(args.since)
    except ValueError:
        print(f"--since must be YYYY-MM-DD, got {args.since!r}",
              file=sys.stderr)
        return 2

    if args.shows.strip():
        shows = [s.strip() for s in args.shows.split(",") if s.strip()]
    else:
        shows = sorted(
            p.name for p in (REPO_ROOT / "digests").iterdir()
            if p.is_dir() and any(p.glob("metrics_ep*.json"))
        )

    return report(shows, since, args.baseline_days, args.timeout_seconds,
                  args.max_p95_regression_pct)


if __name__ == "__main__":
    raise SystemExit(main())
