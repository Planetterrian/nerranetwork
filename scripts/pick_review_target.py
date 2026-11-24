#!/usr/bin/env python3
"""Pick the next target for the automated show-review agent.

Reads docs/reviews/review_state.yaml (the rotation ROSTER + seed dates)
and prints the least-recently-reviewed target slug (ties broken
alphabetically, so the choice is deterministic). Targets with an in-flight
review PR are passed via --exclude so the same show isn't reviewed twice
while the operator considers the first PR.

July 21 2026: the effective last-reviewed date is the NEWER of the state
file's seed date and the latest entry date in the target's ledger
(docs/reviews/ledger/<slug>.yaml). Review PRs previously advanced the
shared state file themselves, and any two concurrently-open review PRs
conflicted on that block every time (PRs #845/#856). The ledger entry each
PR already carries IS the rotation advance — merging the PR advances the
rotation with no shared-file write. review_state.yaml only needs editing
when a show is added to (or removed from) the rotation.

Ledger dates are read by regex, not yaml.safe_load — three committed
ledgers contain unquoted ": " inside list items and must never be
reserialized (see CLAUDE.md, review-agent section).

Nov 3 2026: a target listed under ``rotation_only:`` in the state file is
dated by the state file and the review AGENT'S OWN ledger entries only —
the entries ``run_show_review.py`` writes, which carry ``generated_by`` —
never by a slate review's entry. Every slate review appends to the network
ledger, so under the plain max() rule ``network`` read as reviewed on
2026-10-14 (a slate pass) while the agent — the only thing that writes
``scored_prior_predictions`` — was weeks from reaching it; its ledger held
70 pending predictions of 94 and three empty scored blocks. The agent's own
pass still advances the rotation through the entry it lands, with no
state-file write.

Nov 24 2026: the pick is ranked by AUDIENCE times PROBLEM, not by date
alone. The date rule spent the week of Nov 16 on Prediction Markets (154
downloads in 30 days) and the Africa & Middle East desk (3) while SpaceX
(5,918, ~40% of the network) and Tesla (2,221; audit score flat at 6.3
since August) waited. ``rank_targets`` scores each eligible target

    priority = (AUDIENCE_FLOOR + share of 30-day downloads)
               * weeks since its last review (capped at 13)
               * (1 + score drop vs its own prior weeks
                    + half its shortfall under TARGET_SCORE
                    + CONTRACT_MISS_WEIGHT * must-have misses in 14 days)

from the committed ``api/op3_stats.json``, ``api/editorial_score_history.json``
and ``api/show_contracts.json``. A target reviewed in the last
``MIN_GAP_DAYS`` waits; one unreviewed for ``MAX_GAP_DAYS`` goes first
whatever its audience, so a small show is still reached. A missing file is
a missing signal (the factor is neutral), never a zero. Without signals
(``--plain``, or a caller passing none) the pick is the old date rule.

Exit codes: 0 = slug printed, 2 = no eligible target (all excluded).

Usage:
    python scripts/pick_review_target.py
    python scripts/pick_review_target.py --exclude tesla network
"""

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / "docs" / "reviews" / "review_state.yaml"

#: Weight every target carries before its audience share, so a show with no
#: measured downloads is reachable by staleness and problems alone.
AUDIENCE_FLOOR = 0.03
#: The cross-cutting ``network`` target has no feed; it is weighted as one
#: large show.
NETWORK_WEIGHT = 0.3
#: A target reviewed this recently waits (its last review's PR is still
#: settling); one unreviewed this long goes first.
MIN_GAP_DAYS = 7
MAX_GAP_DAYS = 90
#: Staleness stops growing after this many weeks.
MAX_WEEKS = 13
#: The audit score a show is held to; the shortfall under it is a problem.
TARGET_SCORE = 7.0
#: Episodes in the "recent" window and the "prior" window of the audit score.
RECENT_EPISODES = 7
PRIOR_EPISODES = 21
CONTRACT_MISS_WEIGHT = 0.5

_LEDGER_DATE_RE = re.compile(r"^\s*-\s*date:\s*['\"]?(\d{4}-\d{2}-\d{2})['\"]?\s*$", re.M)


def _latest_ledger_date(ledger_dir: Path, slug: str) -> str:
    """Newest entry date in the slug's ledger, or "" when absent."""
    path = ledger_dir / f"{slug}.yaml"
    if not path.exists():
        return ""
    dates = _LEDGER_DATE_RE.findall(path.read_text(encoding="utf-8"))
    return max(dates) if dates else ""


_AGENT_ENTRY_RE = re.compile(r"^\s*generated_by:", re.M)


def _latest_agent_ledger_date(ledger_dir: Path, slug: str) -> str:
    """Newest date of an entry the review AGENT wrote (``generated_by:``,
    stamped by ``run_show_review.update_ledger``), or "" when none. A slate
    review's hand-written entry carries no such key and does not count."""
    path = ledger_dir / f"{slug}.yaml"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    dates = []
    starts = [m.start() for m in _LEDGER_DATE_RE.finditer(text)]
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        if _AGENT_ENTRY_RE.search(text, start, end):
            dates.append(_LEDGER_DATE_RE.match(text, start).group(1))
    return max(dates) if dates else ""


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_signals(root: Path = ROOT) -> dict:
    """The committed signals the ranking reads. Each key is absent when its
    file is unreadable — a missing signal, never a zero."""
    signals: dict = {}
    op3 = _load_json(root / "api" / "op3_stats.json")
    if isinstance(op3, dict) and isinstance(op3.get("shows"), dict):
        downloads = {slug: v.get("downloads_30d") for slug, v in op3["shows"].items()
                     if isinstance(v, dict) and isinstance(v.get("downloads_30d"), (int, float))}
        total = sum(downloads.values())
        if total > 0:
            signals["share"] = {slug: n / total for slug, n in downloads.items()}
    hist = _load_json(root / "api" / "editorial_score_history.json")
    if isinstance(hist, dict) and isinstance(hist.get("rows"), list):
        by_show: dict = {}
        for row in sorted(hist["rows"], key=lambda r: (str(r.get("date")), r.get("episode") or 0)):
            score = row.get("score")
            if isinstance(score, (int, float)) and not isinstance(score, bool) and row.get("show"):
                by_show.setdefault(row["show"], []).append(float(score))
        signals["scores"] = by_show
    contracts = _load_json(root / "api" / "show_contracts.json")
    if isinstance(contracts, dict) and isinstance(contracts.get("shows"), dict):
        signals["contract_misses"] = {
            slug: v.get("misses_14d") for slug, v in contracts["shows"].items()
            if isinstance(v, dict) and isinstance(v.get("misses_14d"), int)}
    return signals


def problem_factor(slug: str, signals: dict) -> float:
    """1 + score drop + half the shortfall under TARGET_SCORE + contract
    misses. 1.0 (neutral) when nothing is known about the show."""
    factor = 1.0
    scores = (signals.get("scores") or {}).get(slug) or []
    if len(scores) >= RECENT_EPISODES:
        recent = scores[-RECENT_EPISODES:]
        prior = scores[-(RECENT_EPISODES + PRIOR_EPISODES):-RECENT_EPISODES]
        recent_mean = sum(recent) / len(recent)
        if len(prior) >= RECENT_EPISODES:
            factor += max(0.0, sum(prior) / len(prior) - recent_mean)
        factor += max(0.0, TARGET_SCORE - recent_mean) / 2
    misses = (signals.get("contract_misses") or {}).get(slug)
    if misses:
        factor += CONTRACT_MISS_WEIGHT * misses
    return factor


def rank_targets(dates: dict[str, str], signals: dict,
                 today: _dt.date) -> list[tuple[str, float, str]]:
    """``[(slug, priority, why)]``, best first. Targets inside MIN_GAP_DAYS
    are left out; any past MAX_GAP_DAYS outrank every other (oldest first)."""
    shares = signals.get("share") or {}
    ranked = []
    for slug, last in dates.items():
        try:
            days = (today - _dt.date.fromisoformat(str(last)[:10])).days
        except ValueError:
            days = MAX_GAP_DAYS
        if days < MIN_GAP_DAYS:
            continue
        if slug == "network":
            weight = NETWORK_WEIGHT
        else:
            weight = AUDIENCE_FLOOR + shares.get(slug, 0.0)
        weeks = min(days, MAX_WEEKS * 7) / 7
        problem = problem_factor(slug, signals)
        priority = weight * weeks * problem
        if days >= MAX_GAP_DAYS:
            priority = 1000.0 + days
        why = (f"last {last} ({days} d), audience weight {weight:.2f}, "
               f"problem x{problem:.2f}")
        ranked.append((slug, round(priority, 4), why))
    ranked.sort(key=lambda r: (-r[1], r[0]))
    return ranked


def effective_dates(state_path: Path, excludes: set[str],
                    ledger_dir: Path | None = None) -> dict[str, str]:
    """Each eligible target's last-reviewed date (state seed or ledger)."""
    if ledger_dir is None:
        ledger_dir = state_path.parent / "ledger"
    data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    targets = data.get("targets") or {}
    rotation_only = set(data.get("rotation_only") or [])
    return {
        slug: max(str(last_reviewed),
                  (_latest_agent_ledger_date if slug in rotation_only
                   else _latest_ledger_date)(ledger_dir, slug))
        for slug, last_reviewed in targets.items()
        if slug not in excludes
    }


def pick_ranked(state_path: Path, excludes: set[str], signals: dict,
                today: _dt.date, ledger_dir: Path | None = None) -> str | None:
    ranked = rank_targets(effective_dates(state_path, excludes, ledger_dir),
                          signals, today)
    return ranked[0][0] if ranked else None


def pick_target(state_path: Path, excludes: set[str],
                ledger_dir: Path | None = None) -> str | None:
    if ledger_dir is None:
        ledger_dir = state_path.parent / "ledger"
    data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    targets = data.get("targets") or {}
    rotation_only = set(data.get("rotation_only") or [])
    candidates = {
        slug: max(str(last_reviewed),
                  (_latest_agent_ledger_date if slug in rotation_only
                   else _latest_ledger_date)(ledger_dir, slug))
        for slug, last_reviewed in targets.items()
        if slug not in excludes
    }
    if not candidates:
        return None
    # ISO dates sort correctly as strings; alphabetical slug tie-break.
    return min(candidates.items(), key=lambda kv: (kv[1], kv[0]))[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--exclude", nargs="*", default=[])
    parser.add_argument("--plain", action="store_true",
                        help="the old least-recently-reviewed rule, no signals")
    parser.add_argument("--today", default=None, help="YYYY-MM-DD (tests)")
    parser.add_argument("--explain", action="store_true",
                        help="print the ranking to stderr")
    args = parser.parse_args()

    if args.plain:
        slug = pick_target(args.state, set(args.exclude))
    else:
        today = _dt.date.fromisoformat(args.today) if args.today else _dt.date.today()
        ranked = rank_targets(effective_dates(args.state, set(args.exclude)),
                              load_signals(), today)
        if args.explain:
            for r_slug, prio, why in ranked:
                print(f"{r_slug:28} {prio:9.3f}  {why}", file=sys.stderr)
        slug = ranked[0][0] if ranked else None
    if slug is None:
        print("no eligible review target (all excluded)", file=sys.stderr)
        return 2
    print(slug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
