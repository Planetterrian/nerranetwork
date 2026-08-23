#!/usr/bin/env python3
"""Measure citation-shaped-language exposure across the published corpus.

Step 1 of the source-integrity plan (Aug 2026): before deciding what to do
about episodes published without a claim ledger, measure how much
citation-shaped language (the fabrication signature — see
``engine.claims.CITATION_SHAPE_PATTERNS``) each show actually carries.
Deterministic regex counting over the committed digest ``.md`` files — no
model calls, cheap enough to run any time.

Usage:
    python scripts/measure_citation_exposure.py                # console table
    python scripts/measure_citation_exposure.py --top 20       # worst episodes
    python scripts/measure_citation_exposure.py --json out.json
    python scripts/measure_citation_exposure.py --report docs/citation_exposure_YYYY_MM_DD.md

The per-show ranking (highest shapes-per-episode first) is the triage order
for the backfill: shows asserting few specifics carry little risk; the
narrative essay shows are where softening / re-sourcing effort goes first.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.claims import find_citation_shapes  # noqa: E402

# Digest files only: Prefix_EpNNN_YYYYMMDD.md — transcripts, _tts snapshots
# and claims sidecars are downstream copies of the same text.
_DIGEST_NAME_RE = re.compile(r"_Ep\d+_\d{8}\.md$")


def iter_digest_files(digests_root: Path):
    for path in sorted(digests_root.rglob("*.md")):
        if _DIGEST_NAME_RE.search(path.name):
            yield path


def measure(digests_root: Path) -> dict:
    per_show: dict = defaultdict(lambda: {
        "episodes": 0, "episodes_with_shapes": 0, "shapes": 0,
        "pattern_counts": Counter(), "worst": [],
    })
    episodes = []
    for path in iter_digest_files(digests_root):
        show = path.parent.name if path.parent != digests_root else "(legacy flat)"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        findings = find_citation_shapes(text)
        stats = per_show[show]
        stats["episodes"] += 1
        if findings:
            stats["episodes_with_shapes"] += 1
            stats["shapes"] += len(findings)
            for f in findings:
                stats["pattern_counts"][f["pattern"]] += 1
            episodes.append({
                "file": str(path.relative_to(digests_root.parent)),
                "show": show,
                "shapes": len(findings),
                "matches": sorted({f["match"] for f in findings}),
            })
    episodes.sort(key=lambda e: -e["shapes"])
    result = {"shows": {}, "episodes": episodes}
    for show, stats in per_show.items():
        eps = stats["episodes"]
        result["shows"][show] = {
            "episodes": eps,
            "episodes_with_shapes": stats["episodes_with_shapes"],
            "shapes_total": stats["shapes"],
            "shapes_per_episode": round(stats["shapes"] / eps, 2) if eps else 0,
            "pattern_counts": dict(stats["pattern_counts"].most_common()),
        }
    return result


def render_table(result: dict) -> str:
    rows = sorted(
        result["shows"].items(),
        key=lambda kv: -kv[1]["shapes_per_episode"],
    )
    lines = [
        f"{'show':<28} {'eps':>5} {'w/shapes':>9} {'shapes':>7} {'per-ep':>7}",
        "-" * 60,
    ]
    total_eps = total_shapes = total_with = 0
    for show, s in rows:
        lines.append(
            f"{show:<28} {s['episodes']:>5} {s['episodes_with_shapes']:>9} "
            f"{s['shapes_total']:>7} {s['shapes_per_episode']:>7.2f}"
        )
        total_eps += s["episodes"]
        total_shapes += s["shapes_total"]
        total_with += s["episodes_with_shapes"]
    lines.append("-" * 60)
    per_ep = total_shapes / total_eps if total_eps else 0
    lines.append(
        f"{'TOTAL':<28} {total_eps:>5} {total_with:>9} "
        f"{total_shapes:>7} {per_ep:>7.2f}"
    )
    return "\n".join(lines)


def render_report(result: dict, top: int) -> str:
    from datetime import date
    rows = sorted(
        result["shows"].items(), key=lambda kv: -kv[1]["shapes_per_episode"],
    )
    out = [
        "# Citation-shape exposure across the published corpus",
        "",
        f"Measured {date.today().isoformat()} by "
        "`scripts/measure_citation_exposure.py` — deterministic regex counts "
        "of citation-shaped constructions "
        "(`engine.claims.CITATION_SHAPE_PATTERNS`, the fabrication "
        "signature) over every committed digest `.md`. A count is EXPOSURE, "
        "not a verdict: each match is a sentence asserting provenance that "
        "no ledger backs, which may be true, stale, or invented — "
        "unverifiable either way.",
        "",
        "This ranking is the triage order for the backfill "
        "(soften-in-place / re-source / regenerate — operator decision per "
        "show).",
        "",
        "| Show | Episodes | With shapes | Shapes | Per episode |",
        "|---|---:|---:|---:|---:|",
    ]
    for show, s in rows:
        out.append(
            f"| {show} | {s['episodes']} | {s['episodes_with_shapes']} | "
            f"{s['shapes_total']} | {s['shapes_per_episode']:.2f} |"
        )
    out += ["", f"## Highest-exposure episodes (top {top})", ""]
    for ep in result["episodes"][:top]:
        matches = ", ".join(f"`{m}`" for m in ep["matches"][:6])
        out.append(f"- **{ep['file']}** — {ep['shapes']} ({matches})")
    out += [
        "",
        "## Pattern breakdown (network-wide)",
        "",
    ]
    pattern_totals: Counter = Counter()
    for s in result["shows"].values():
        pattern_totals.update(s["pattern_counts"])
    for pat, n in pattern_totals.most_common():
        out.append(f"- `{pat}` — {n}")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--digests", default=str(PROJECT_ROOT / "digests"))
    ap.add_argument("--top", type=int, default=15,
                    help="How many worst episodes to list")
    ap.add_argument("--json", help="Write full results to this JSON path")
    ap.add_argument("--report", help="Write a markdown report to this path")
    args = ap.parse_args()

    result = measure(Path(args.digests))
    print(render_table(result))
    print()
    for ep in result["episodes"][: args.top]:
        print(f"  {ep['shapes']:>3}  {ep['file']}")

    if args.json:
        Path(args.json).write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nJSON written: {args.json}")
    if args.report:
        Path(args.report).write_text(
            render_report(result, args.top) + "\n", encoding="utf-8",
        )
        print(f"Report written: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
