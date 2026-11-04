#!/usr/bin/env python3
"""Read the experiments register on the reading side — nightly.

``docs/experiments.yaml`` is the discipline "know your readout date before
you ship". By the Nov 3 2026 review it held 194 entries, 118 of them
``reading``/``decide`` and 74 past their readout — the oldest due Oct 15 —
and the dashboard rendered the overdue count as one warning string nothing
acted on. The three readouts that would have changed a decision that month
(the grok-4.6 latency gate, hook-leads-body, Also Today) sat past their
dates until a reader computed them by hand.

This script is the machine on the reading side. For every ``reading`` /
``decide`` entry whose readout date has arrived it prints, and writes to
``api/register_readouts.json``:

* ``with_metric`` — the entry names a live metric the dashboard computes:
  the LIVE value (``scripts.generate_dashboard._experiment_live_metrics``)
  beside ``baseline`` and ``target``, so the readout is one glance;
* ``needs_human_read`` — no metric: the ``target`` text, the
  ``readout_plan`` when the entry has one, and the days overdue.

It also lists, under ``notes_not_experiments``, every entry shipped on or
after ``REGISTER_READABLE_SINCE`` that carries neither a computable metric
nor ``criteria`` plus a ``readout_plan`` naming the file or command that
answers it — the CI rule in ``tests/test_dashboard_growth.py`` binds those
(an entry with neither is a note, not an experiment).

**It reads; the only thing it writes is its own JSON.** It never edits the
register: a readout the script drafts is a DRAFT the next review confirms
(the judgement is human), and the outcome goes into the register by hand.

``--strict`` exits 1 when any entry is ``STRICT_OVERDUE_DAYS`` (14) or more
days past its readout with neither an ``outcome`` nor a ``metric`` — the
nightly step turns that into a ``::warning::``; the file is written either
way.

Consumers: the Mission Control card "Readouts due" (``management.html``
fetches ``api/register_readouts.json``), and
``tests/test_review_loop_2026_11_03.py``.

Usage::

    python scripts/readout_register.py
    python scripts/readout_register.py --strict --out api/register_readouts.json
    python scripts/readout_register.py --today 2026-11-04 --dry-run
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

#: The statuses whose readout can be due. ``done`` is the record.
OPEN_STATUSES = ("reading", "decide")

#: ``--strict`` fails on an entry this many days past its readout with
#: neither an ``outcome`` nor a ``metric``.
STRICT_OVERDUE_DAYS = 14

#: The CI rule's effective date: an entry SHIPPED on or after this date must
#: carry a computable ``metric`` OR ``criteria`` plus a ``readout_plan``.
#: Every entry the six-month review registered on 2026-11-03 carries one or
#: the other; entries before it are never a defect.
REGISTER_READABLE_SINCE = _dt.date(2026, 11, 3)

#: Key under which the register carries a readout's conclusion. An entry
#: with an outcome is read — it may stay ``reading`` while the register's
#: owner moves it to ``done``.
OUTCOME_KEYS = ("outcome", "interim")


def _as_date(value: Any) -> Optional[_dt.date]:
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    try:
        return _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def load_register(path: Path) -> List[Dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = data.get("experiments") if isinstance(data, dict) else data
    return [e for e in (entries or []) if isinstance(e, dict) and e.get("id")]


def has_outcome(entry: Dict[str, Any]) -> bool:
    return any(_text(entry.get(k)) for k in OUTCOME_KEYS)


def readability_defect(entry: Dict[str, Any], computable: Iterable[str],
                       since: _dt.date = REGISTER_READABLE_SINCE) -> Optional[str]:
    """Why an entry shipped on/after *since* is a note, not an experiment.

    None when the entry is readable: it names a ``metric`` the dashboard
    computes, or it carries ``criteria`` AND a ``readout_plan`` naming the
    file or command that answers it. Entries shipped before *since* are
    never a defect (the rule binds new entries only).
    """
    shipped = _as_date(entry.get("shipped"))
    if shipped is None or shipped < since:
        return None
    metric = _text(entry.get("metric"))
    if metric:
        if metric in set(computable):
            return None
        return f"names metric {metric!r} the dashboard does not compute"
    if _text(entry.get("criteria")) and _text(entry.get("readout_plan")):
        return None
    missing = [k for k in ("criteria", "readout_plan") if not _text(entry.get(k))]
    return ("no metric and no " + " + ".join(missing)
            + " — a note, not an experiment")


def build_readouts(entries: List[Dict[str, Any]], live: Dict[str, Any],
                   today: _dt.date) -> Dict[str, Any]:
    """The readout record: due entries split by whether a machine can read them."""
    with_metric: List[Dict[str, Any]] = []
    needs_human: List[Dict[str, Any]] = []
    strict_failures: List[str] = []
    notes_not_experiments: List[Dict[str, Any]] = []
    computable = set(live.keys())

    for e in entries:
        defect = readability_defect(e, computable)
        if defect:
            notes_not_experiments.append({
                "id": e["id"], "shipped": str(e.get("shipped")), "defect": defect})

        status = str(e.get("status") or "reading")
        if status not in OPEN_STATUSES:
            continue
        readout = _as_date(e.get("readout"))
        if readout is None or readout > today:
            continue
        days_overdue = (today - readout).days
        row: Dict[str, Any] = {
            "id": e["id"],
            "title": _text(e.get("title")),
            "area": e.get("area"),
            "status": status,
            "shipped": str(e.get("shipped")),
            "readout": readout.isoformat(),
            "days_overdue": days_overdue,
            "baseline": e.get("baseline"),
            "target": _text(e.get("target")) or None,
            "criteria": _text(e.get("criteria")) or None,
            "outcome": (_text(e.get("outcome")) or _text(e.get("interim")) or None),
        }
        metric = _text(e.get("metric"))
        if metric:
            row["metric"] = metric
            # None is "unmeasured" — never a fake zero (the funnel's rule).
            row["live"] = live.get(metric)
            with_metric.append(row)
        else:
            row["readout_plan"] = _text(e.get("readout_plan")) or None
            needs_human.append(row)
        if days_overdue >= STRICT_OVERDUE_DAYS and not metric and not has_outcome(e):
            strict_failures.append(e["id"])

    key = lambda r: (-r["days_overdue"], r["id"])  # noqa: E731
    with_metric.sort(key=key)
    needs_human.sort(key=key)
    due = with_metric + needs_human
    return {
        "generated": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "today": today.isoformat(),
        "register": "docs/experiments.yaml",
        "strict_overdue_days": STRICT_OVERDUE_DAYS,
        "due_count": len(due),
        # Same definition as growth.experiments.overdue_count on the
        # dashboard: readout strictly before today.
        "overdue_count": sum(1 for r in due if r["days_overdue"] > 0),
        "with_metric_count": len(with_metric),
        "needs_human_read_count": len(needs_human),
        "strict_failures": strict_failures,
        "with_metric": with_metric,
        "needs_human_read": needs_human,
        "readable_rule_since": REGISTER_READABLE_SINCE.isoformat(),
        "notes_not_experiments": notes_not_experiments,
        "consumers": ["management.html (Readouts due)",
                      "tests/test_review_loop_2026_11_03.py"],
    }


def live_metrics(root: Path) -> Dict[str, Any]:
    """The dashboard's closed vocabulary of live metrics, read the same way
    the Levers card reads it. Imported lazily — the generator pulls in the
    whole engine."""
    from scripts.generate_dashboard import _experiment_live_metrics
    return _experiment_live_metrics(root)


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    return _text(value)[:60]


def print_report(doc: Dict[str, Any]) -> None:
    print(f"Register readouts — {doc['today']}: {doc['due_count']} due "
          f"({doc['with_metric_count']} with a live metric, "
          f"{doc['needs_human_read_count']} need a human read); "
          f"{doc['overdue_count']} past their date.\n")
    if doc["with_metric"]:
        print("WITH A LIVE METRIC (live · baseline · target)")
        for r in doc["with_metric"]:
            print(f"  {r['id']:52} +{r['days_overdue']:>3}d  {r['metric']}: "
                  f"live {_fmt(r['live'])} · baseline {_fmt(r['baseline'])} · "
                  f"target {_fmt(r['target'])}")
        print()
    if doc["needs_human_read"]:
        print("NEEDS A HUMAN READ (days overdue · target)")
        for r in doc["needs_human_read"]:
            flag = " [outcome drafted]" if r.get("outcome") else ""
            plan = "  plan: " + _fmt(r["readout_plan"]) if r.get("readout_plan") else ""
            print(f"  {r['id']:52} +{r['days_overdue']:>3}d  {_fmt(r['target'])}"
                  f"{plan}{flag}")
        print()
    if doc["notes_not_experiments"]:
        print(f"SHIPPED ON/AFTER {doc['readable_rule_since']} WITH NO READOUT PATH "
              "(a note, not an experiment)")
        for r in doc["notes_not_experiments"]:
            print(f"  {r['id']:52} {r['defect']}")
        print()
    if doc["strict_failures"]:
        print(f"STRICT: {len(doc['strict_failures'])} entr"
              f"{'y' if len(doc['strict_failures']) == 1 else 'ies'} >= "
              f"{doc['strict_overdue_days']} days past readout with neither "
              f"outcome nor metric: {', '.join(doc['strict_failures'])}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--register", type=Path, default=None,
                        help="docs/experiments.yaml (default: under --root)")
    parser.add_argument("--out", type=Path, default=None,
                        help="JSON path (default: <root>/api/register_readouts.json)")
    parser.add_argument("--today", default=None, help="YYYY-MM-DD (tests)")
    parser.add_argument("--strict", action="store_true",
                        help=f"exit 1 when an entry is >= {STRICT_OVERDUE_DAYS} days "
                             "past readout with neither outcome nor metric")
    parser.add_argument("--dry-run", action="store_true", help="print only")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    register = args.register or (root / "docs" / "experiments.yaml")
    out = args.out or (root / "api" / "register_readouts.json")
    today = _as_date(args.today) if args.today else _dt.date.today()
    if today is None:
        print(f"--today must be YYYY-MM-DD, got {args.today!r}", file=sys.stderr)
        return 2

    entries = load_register(register)
    doc = build_readouts(entries, live_metrics(root), today)
    print_report(doc)
    if not args.dry_run:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2, ensure_ascii=False, default=str) + "\n",
                       encoding="utf-8")
        print(f"wrote {out}")
    if args.strict and doc["strict_failures"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
