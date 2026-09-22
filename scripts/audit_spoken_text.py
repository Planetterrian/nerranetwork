#!/usr/bin/env python3
"""Audit committed episodes with the spoken-text gate (calibration tool).

Runs ``engine.spoken_text_gate.check_transcript_files`` over every
committed ``*_tts.txt`` + ``*_transcript.json`` pair and prints, per
show, the distribution of both measures and every episode the gate
would fail. This is how Tesla Ep605's leak was confirmed unique across
1,709 committed pairs (2026-09-14) and how the thresholds were set;
re-run it BEFORE moving ``DEFAULT_MIN_OPENING_MATCH`` or
``DEFAULT_MAX_UNMATCHED_RUN`` — the legit maximum since June 2026 is
the number that decides whether a threshold is safe, not a single
episode.

No model calls, no network; ~6 s over the whole corpus.

Usage:
    python scripts/audit_spoken_text.py                  # since 2026-06-01
    python scripts/audit_spoken_text.py --since 20260901 # narrower window
    python scripts/audit_spoken_text.py --show tesla_shorts_time --top 10
    python scripts/audit_spoken_text.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.spoken_text_gate import check_transcript_files  # noqa: E402

RU_SHOWS = {"finansy_prosto", "privet_russian"}
_DATE_RE = re.compile(r"_(\d{8})")


def _pairs(since: str, show: str | None):
    for tts in sorted((ROOT / "digests").glob("*/*_tts.txt")):
        show_dir = tts.parent.name
        if show and show_dir != show:
            continue
        m = _DATE_RE.search(tts.stem)
        date = m.group(1) if m else "00000000"
        if date < since:
            continue
        base = tts.with_name(tts.name[: -len("_tts.txt")])
        json_path = base.with_name(base.name + "_transcript.json")
        txt_path = base.with_name(base.name + "_transcript.txt")
        if not json_path.exists() and not txt_path.exists():
            continue
        yield show_dir, base.name, date, tts, json_path, txt_path


_LANG_RE = re.compile(r"\.([a-z]{2})_transcript\.(json|txt)$")


def _dub_pairs(since: str, show: str | None):
    """``<stem>.<lang>.txt`` + ``<stem>.<lang>_transcript.{json,txt}`` pairs
    written by the multilingual sweep (Sep 22 2026) — the calibration set
    for the dub spoken-text gate. The JSON is gitignored, so on a fresh
    checkout the plain transcript carries the comparison."""
    seen = set()
    for tr in sorted((ROOT / "digests").glob("*/*_transcript.*")):
        m = _LANG_RE.search(tr.name)
        if not m:
            continue
        lang = m.group(1)
        show_dir = tr.parent.name
        if show and show_dir != show:
            continue
        base_name = tr.name[: -len(f".{lang}_transcript.{m.group(2)}")]
        key = (show_dir, base_name, lang)
        if key in seen:
            continue
        seen.add(key)
        d = _DATE_RE.search(base_name)
        date = d.group(1) if d else "00000000"
        if date < since:
            continue
        script = tr.parent / f"{base_name}.{lang}.txt"
        if not script.exists():
            continue
        json_path = tr.parent / f"{base_name}.{lang}_transcript.json"
        txt_path = tr.parent / f"{base_name}.{lang}_transcript.txt"
        yield show_dir, f"{base_name}.{lang}", date, script, json_path, txt_path, lang


def _pct(values, q):
    if not values:
        return 0
    values = sorted(values)
    return values[min(len(values) - 1, int(q * len(values)))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--since", default="20260601", help="YYYYMMDD lower bound")
    ap.add_argument("--show", help="Only this show directory")
    ap.add_argument("--top", type=int, default=15, help="Worst-N per measure")
    ap.add_argument("--json", help="Write per-episode rows to this file")
    ap.add_argument("--dubs", action="store_true",
                    help="Audit the translated tracks (<stem>.<lang>.txt vs "
                         "<stem>.<lang>_transcript.*) instead of the English scripts")
    args = ap.parse_args()

    rows = []
    if args.dubs:
        pairs = _dub_pairs(args.since, args.show)
    else:
        pairs = ((s, n, d, t, j, x, ("ru" if s in RU_SHOWS else "en"))
                 for s, n, d, t, j, x in _pairs(args.since, args.show))
    for show, name, date, tts, json_path, txt_path, language in pairs:
        script = tts.read_text(encoding="utf-8", errors="replace")
        report = check_transcript_files(script, json_path, txt_path)
        if report.spoken_words < 50:
            continue
        rows.append({
            "show": show, "episode": name, "date": date,
            "language": language,
            "passed": report.passed, "reasons": list(report.reasons),
            "opening_match": report.opening_match,
            "longest_unmatched_run": report.longest_unmatched_run,
            "unmatched_position": report.unmatched_position,
            "unmatched_snippet": report.unmatched_snippet,
            "segments_dropped": report.segments_dropped,
            "loops_collapsed": report.loops_collapsed,
        })

    if not rows:
        print("no transcript pairs found")
        return 0

    by_show = defaultdict(list)
    for r in rows:
        by_show[r["show"]].append(r)
    print(f"pairs={len(rows)} since={args.since}")
    print(f"{'show':26} {'n':>4} {'open_min':>8} {'open_p5':>7} | {'run_max':>7} {'run_p99':>7} {'run_med':>7} | fails")
    for show, rs in sorted(by_show.items()):
        opens = [r["opening_match"] for r in rs]
        runs = [r["longest_unmatched_run"] for r in rs]
        fails = sum(1 for r in rs if not r["passed"])
        print(
            f"{show:26} {len(rs):4} {min(opens):8.2f} {_pct(opens, 0.05):7.2f} | "
            f"{max(runs):7} {_pct(runs, 0.99):7} {_pct(runs, 0.5):7} | {fails}"
        )

    en = [r for r in rows if r["language"] == "en"]
    print(f"\n== English: worst opening_match (top {args.top}) ==")
    for r in sorted(en, key=lambda r: r["opening_match"])[: args.top]:
        print(f"  {r['opening_match']:.2f} run={r['longest_unmatched_run']:3} {r['show']}/{r['episode']}")
    print(f"\n== English: longest unmatched runs (top {args.top}) ==")
    for r in sorted(en, key=lambda r: -r["longest_unmatched_run"])[: args.top]:
        print(
            f"  run={r['longest_unmatched_run']:3} open={r['opening_match']:.2f} "
            f"{r['show']}/{r['episode']} @{r['unmatched_position']:.0%} :: {r['unmatched_snippet'][:60]}"
        )
    failed = [r for r in rows if not r["passed"]]
    print(f"\n== gate FAILS ({len(failed)}) ==")
    for r in failed:
        print(f"  [{r['language']}] {r['show']}/{r['episode']} {r['reasons']} open={r['opening_match']:.2f} run={r['longest_unmatched_run']}")

    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
