#!/usr/bin/env python3
"""Record what happened to closed review PRs — nightly.

The Show Review Agent opens every pass as a DRAFT PR on an
``agent/review-<slug>-<YYYYMMDD>`` branch; the operator's merge is the ship
gate. Between Oct 20 and Nov 3 2026 ten review PRs closed: 2 merged, 7
closed unmerged, 0 labelled — and the playbook said a closed-unmerged PR is
not automatically a rejection, so nothing was recorded either way and the
same proposals came back on the next pass.

This script closes that loop with ONE signal the operator gives in one
click, a label:

* a closed-unmerged ``agent/review-*`` PR with none of the labels
  ``rejected`` / ``superseded`` / ``stale`` gets ONE comment asking for the
  label (idempotent: the comment carries a marker and is never repeated);
* a PR labelled ``rejected`` has its proposed items appended to that
  target's ledger ``do_not_retry`` list by TEXT-SPLICE — the ledger writer's
  rule (``scripts/run_show_review.py::update_ledger``): never reserialize a
  ledger, three committed ones carry unquoted ``: `` inside list items.
  Idempotent: an item whose evidence already names the PR is not added twice;
* ``superseded`` (the content landed another way) and ``stale`` (an
  unmergeable branch, an API failure) leave the ideas live — nothing is
  written.

A closed PR WITHOUT a label is unknown; ``rejected`` is the signal. Merged
PRs are the rotation's business (the ledger entry they carry).

``gh`` is the only transport (``GH_TOKEN`` in Actions). The nightly runs it
with ``pull-requests: write``; ``--dry-run`` prints what it would do.

Usage::

    python scripts/review_pr_outcomes.py --dry-run
    python scripts/review_pr_outcomes.py --days 60
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from run_show_review import _indent, _list_indent, _yaml_block  # noqa: E402

#: The one signal. ``rejected`` writes do_not_retry; the other two record an
#: infrastructure close and leave the ideas live.
LABEL_REJECTED = "rejected"
OUTCOME_LABELS = (LABEL_REJECTED, "superseded", "stale")

#: Marker inside the ask-for-a-label comment, so it is posted once.
ASK_MARKER = "<!-- review-pr-outcomes:ask -->"

BRANCH_RE = re.compile(r"^agent/review-(?P<slug>.+)-(?P<date>\d{8})$")

#: The two proposal shapes ``run_show_review.build_pr_body`` writes:
#: ``**`file`** (kind) — rationale`` under the A/B-listen section and
#: ``- **`file`** (kind): rationale`` under the code/metadata section.
_PROPOSAL_AB_RE = re.compile(r"^\*\*`(?P<file>[^`]+)`\*\* \((?P<kind>[^)]*)\) — (?P<why>.+)$")
_PROPOSAL_SAFE_RE = re.compile(r"^- \*\*`(?P<file>[^`]+)`\*\* \((?P<kind>[^)]*)\): (?P<why>.+)$")

GhRunner = Callable[[List[str]], str]


def run_gh(args: List[str]) -> str:
    """``gh <args>`` → stdout. A failure prints gh's own stderr before raising
    (the Oct 18 lesson: a swallowed stderr costs the next person the cause)."""
    proc = subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"::warning::gh {' '.join(args[:3])} failed: "
              f"{(proc.stderr or proc.stdout).strip()[-600:]}")
        raise subprocess.CalledProcessError(proc.returncode, proc.args,
                                            output=proc.stdout, stderr=proc.stderr)
    return proc.stdout


def list_closed_review_prs(gh: GhRunner, days: int, limit: int = 200) -> List[Dict[str, Any]]:
    """Closed PRs on ``agent/review-*`` branches, closed in the last *days*."""
    raw = gh(["pr", "list", "--state", "closed", "--limit", str(limit), "--json",
              "number,title,headRefName,mergedAt,closedAt,labels,url,body"])
    try:
        rows = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    cutoff = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)
    out = []
    for pr in rows:
        if not isinstance(pr, dict) or not BRANCH_RE.match(str(pr.get("headRefName") or "")):
            continue
        closed = _parse_ts(pr.get("closedAt"))
        if closed is not None and closed < cutoff:
            continue
        out.append(pr)
    return out


def _parse_ts(value: Any) -> Optional[_dt.datetime]:
    if not value:
        return None
    try:
        return _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def pr_labels(pr: Dict[str, Any]) -> set[str]:
    out = set()
    for lab in pr.get("labels") or []:
        name = lab.get("name") if isinstance(lab, dict) else lab
        if name:
            out.add(str(name).strip().lower())
    return out


def pr_slug(pr: Dict[str, Any]) -> Optional[str]:
    m = BRANCH_RE.match(str(pr.get("headRefName") or ""))
    return m.group("slug") if m else None


def proposed_items(body: str) -> List[str]:
    """The PR body's proposed changes as one line each: ``file (kind): why``."""
    items: List[str] = []
    for line in (body or "").splitlines():
        s = line.strip()
        m = _PROPOSAL_AB_RE.match(s) or _PROPOSAL_SAFE_RE.match(s)
        if m:
            why = " ".join(m.group("why").split())
            items.append(f"{m.group('file')} ({m.group('kind')}): {why}")
    return items


def already_asked(gh: GhRunner, number: int) -> bool:
    raw = gh(["pr", "view", str(number), "--json", "comments", "--jq",
              "[.comments[].body] | join(\"\\n\")"])
    return ASK_MARKER in (raw or "")


def ask_comment(pr: Dict[str, Any]) -> str:
    return (
        f"{ASK_MARKER}\n"
        "This review PR closed without merging and carries no outcome label, so "
        "the review loop cannot learn from it either way.\n\n"
        f"Add ONE label so the nightly `scripts/review_pr_outcomes.py` can record it:\n"
        f"- `{LABEL_REJECTED}` — the proposals were considered and declined: each "
        f"proposed item goes into `docs/reviews/ledger/{pr_slug(pr) or '<slug>'}.yaml` "
        "`do_not_retry` and is never re-proposed without an argument that the "
        "evidence no longer applies;\n"
        "- `superseded` — the content landed another way; the ideas stay live;\n"
        "- `stale` — an infrastructure close (unmergeable branch, API failure); the "
        "ideas stay live.\n\n"
        "A closed PR without a label is unknown; `rejected` is the signal."
    )


def existing_do_not_retry_text(path: Path) -> str:
    """The ledger's do_not_retry block as text (for the idempotency check)."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    m = re.search(r"(?m)^do_not_retry:.*$", text)
    return text[m.start():] if m else ""


def append_do_not_retry(path: Path, items: List[Dict[str, str]]) -> int:
    """Splice *items* (``{idea, evidence}``) onto the ledger's do_not_retry
    list. Every byte outside the spliced lines is unchanged. Returns the
    number of items written (0 when nothing new)."""
    if not items:
        return 0
    if not path.exists():
        path.write_text(_yaml_block({"reviews": [], "do_not_retry": items}), encoding="utf-8")
        return len(items)
    text = path.read_text(encoding="utf-8")
    block = _indent(_yaml_block(items), _list_indent(text, "do_not_retry"))
    m = re.search(r"(?m)^do_not_retry:.*$", text)
    if m is None:
        text = text.rstrip("\n") + "\n" + "do_not_retry:\n" + block
    elif re.match(r"do_not_retry:\s*\[\s*\]\s*$", m.group(0)):
        tail = text[m.end():]
        text = (text[: m.start()] + "do_not_retry:\n" + block.rstrip("\n")
                + ("\n" + tail.lstrip("\n") if tail.strip() else "\n"))
    else:
        # do_not_retry is the ledger's last top-level key — append to it.
        text = text.rstrip("\n") + "\n" + block
    path.write_text(text, encoding="utf-8")
    return len(items)


def record_rejection(pr: Dict[str, Any], ledger_dir: Path, today: _dt.date) -> Dict[str, Any]:
    """Append the PR's proposed items to the slug's ledger do_not_retry."""
    slug = pr_slug(pr)
    number = int(pr.get("number"))
    result: Dict[str, Any] = {"pr": number, "slug": slug, "action": "rejected", "added": 0}
    if not slug:
        result["note"] = "branch name did not carry a slug"
        return result
    path = ledger_dir / f"{slug}.yaml"
    marker = f"PR #{number}"
    # Whole number only: "PR #100" must not read as recorded because
    # "PR #1000" is.
    if re.search(rf"PR #{number}(?!\d)", existing_do_not_retry_text(path)):
        result["note"] = "already recorded"
        return result
    items = proposed_items(str(pr.get("body") or ""))
    closed = (_parse_ts(pr.get("closedAt")) or _dt.datetime.combine(
        today, _dt.time(), tzinfo=_dt.timezone.utc)).date().isoformat()
    evidence = (f"{marker} ({pr.get('url') or pr.get('headRefName')}) closed unmerged "
                f"{closed} with the label '{LABEL_REJECTED}' (recorded "
                f"{today.isoformat()} by scripts/review_pr_outcomes.py)")
    if not items:
        items = [f"every proposal in review PR #{number}: {pr.get('title') or ''}".strip()]
    result["added"] = append_do_not_retry(
        path, [{"idea": idea, "evidence": evidence} for idea in items])
    result["ledger"] = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    return result


def process(gh: GhRunner, ledger_dir: Path, days: int, today: _dt.date,
            dry_run: bool = False) -> List[Dict[str, Any]]:
    outcomes: List[Dict[str, Any]] = []
    for pr in list_closed_review_prs(gh, days):
        number = int(pr.get("number"))
        if pr.get("mergedAt"):
            outcomes.append({"pr": number, "slug": pr_slug(pr), "action": "merged"})
            continue
        labels = pr_labels(pr) & set(OUTCOME_LABELS)
        if LABEL_REJECTED in labels:
            if dry_run:
                outcomes.append({"pr": number, "slug": pr_slug(pr), "action": "rejected",
                                 "would_add": proposed_items(str(pr.get("body") or ""))})
            else:
                outcomes.append(record_rejection(pr, ledger_dir, today))
            continue
        if labels:
            outcomes.append({"pr": number, "slug": pr_slug(pr),
                             "action": sorted(labels)[0], "note": "ideas stay live"})
            continue
        if already_asked(gh, number):
            outcomes.append({"pr": number, "slug": pr_slug(pr), "action": "unlabelled",
                             "note": "label already requested"})
            continue
        if not dry_run:
            gh(["pr", "comment", str(number), "--body", ask_comment(pr)])
        outcomes.append({"pr": number, "slug": pr_slug(pr), "action": "unlabelled",
                         "note": "asked for a label" + (" (dry run)" if dry_run else "")})
    return outcomes


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--days", type=int, default=60,
                        help="Only PRs closed in the last N days (default 60).")
    parser.add_argument("--ledger-dir", type=Path,
                        default=ROOT / "docs" / "reviews" / "ledger")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the outcomes; post no comment, write no ledger.")
    args = parser.parse_args(argv)

    try:
        outcomes = process(run_gh, args.ledger_dir, args.days, _dt.date.today(),
                           dry_run=args.dry_run)
    except subprocess.CalledProcessError:
        print("::warning::review_pr_outcomes: gh failed — nothing recorded this run")
        return 0
    for o in outcomes:
        print(json.dumps(o, ensure_ascii=False))
    print(f"review PR outcomes: {len(outcomes)} closed review PR(s) read; "
          f"{sum(1 for o in outcomes if o.get('added'))} ledger write(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
