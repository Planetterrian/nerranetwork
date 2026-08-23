#!/usr/bin/env python3
"""Soften unverifiable citation-shaped phrases in already-published digests.

Backfill step of the source-integrity plan (Aug 2026). The 1,500-episode
back catalogue was published with no claim ledger, so its citation-shaped
sentences ("a 1962 paper in *Nature* warned…") assert provenance nothing can
verify. This tool replaces the DATED-ARTIFACT shape — the demonstrated
fabrication template — with the general form, deterministically, without
re-researching anything. It removes false provenance; it does not fix wrong
facts (§5 of the design doc).

Deliberately conservative:

* Only the dated-artifact constructions are auto-rewritten (past-tense verbs
  are number-invariant in English, so the rewrite is always grammatical).
* Every other citation shape (``internal documents``, ``researchers
  found``, ``estimates from``…) is FLAGGED for manual review, never
  auto-rewritten — some of those are real and famous (tobacco litigation
  documents), and blind softening would make true material vaguer.
* DRY RUN by default; ``--apply`` is required to write (the
  retitle_youtube_videos convention — this rewrites published content, so
  the plan is reviewable before anything changes).

Propagation: blog HTML regenerates from digests via the nightly
``--blogs`` step and future book builds re-parse digests, so edits reach
those surfaces automatically. Already-shipped RSS item descriptions and
synthesized audio do NOT regenerate — softening changes the written
record going forward, not the archive audio.

Usage:
    python scripts/soften_citations.py                     # plan, all shows
    python scripts/soften_citations.py unintended_consequences
    python scripts/soften_citations.py --apply unintended_consequences
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.claims import find_citation_shapes  # noqa: E402

_DIGEST_NAME_RE = re.compile(r"_Ep\d+_\d{8}\.md$")

_ARTIFACT = r"(?:study|paper|report|memo|survey|analysis|bulletin|note)"
# Optional "in <Venue>" tail: short, capitalised, stops before punctuation.
_VENUE = r"(?:\s+(?:published\s+|appearing\s+)?in\s+(?:the\s+)?[A-Z][\w'’.&-]*(?:\s+[A-Z][\w'’.&-]*){0,4})?"
_PAST_VERB = (
    r"(warned|found|showed|noted|estimated|documented|concluded|"
    r"suggested|argued|cautioned|predicted|linked|described)"
)

# The dated-artifact template — the demonstrated fabrication shape. The
# year and venue are exactly the unverifiable specificity being removed;
# the past-tense verb carries over unchanged (number-invariant), so the
# general form is always grammatical.
_SOFTEN_RULES = [
    (
        re.compile(
            r"\b[Aa]ccording to a \d{4} " + _ARTIFACT + _VENUE,
        ),
        "by later accounts",
    ),
    (
        re.compile(
            r"\b[Aa] \d{4} " + _ARTIFACT + _VENUE + r"\s+(?:had\s+)?"
            + _PAST_VERB + r"\b",
        ),
        r"contemporary accounts \1",
    ),
]


def _match_case(replacement: str, original: str) -> str:
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def soften_text(text: str):
    """Return (softened_text, applied: list, flagged: list)."""
    applied = []

    def _sub(rule_re: re.Pattern, template: str, t: str) -> str:
        def repl(m: re.Match) -> str:
            new = m.expand(template) if "\\" in template else template
            new = _match_case(new, m.group(0))
            applied.append({"from": m.group(0), "to": new})
            return new
        return rule_re.sub(repl, t)

    out = text
    for rule_re, template in _SOFTEN_RULES:
        out = _sub(rule_re, template, out)

    # Anything citation-shaped that survives is a manual-review flag.
    flagged = find_citation_shapes(out)
    return out, applied, flagged


def iter_digests(digests_root: Path, only_show: str | None):
    for path in sorted(digests_root.rglob("*.md")):
        if not _DIGEST_NAME_RE.search(path.name):
            continue
        show = path.parent.name if path.parent != digests_root else "(legacy flat)"
        if only_show and show != only_show:
            continue
        yield show, path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("show", nargs="?", help="Limit to one show slug")
    ap.add_argument("--digests", default=str(PROJECT_ROOT / "digests"))
    ap.add_argument("--apply", action="store_true",
                    help="Write the rewrites (default: dry-run plan only)")
    args = ap.parse_args()

    total_applied = total_flagged = files_changed = 0
    for show, path in iter_digests(Path(args.digests), args.show):
        text = path.read_text(encoding="utf-8", errors="replace")
        softened, applied, flagged = soften_text(text)
        if applied:
            files_changed += 1
            total_applied += len(applied)
            print(f"\n{path.relative_to(PROJECT_ROOT)}")
            for a in applied:
                print(f"  - {a['from']!r}\n    -> {a['to']!r}")
            if args.apply:
                path.write_text(softened, encoding="utf-8")
        if flagged:
            total_flagged += len(flagged)
            if applied or args.show:
                for f in flagged:
                    print(f"  ! manual review [{f['match']}]: "
                          f"{f['sentence'][:110]}")

    mode = "APPLIED" if args.apply else "DRY RUN — nothing written"
    print(
        f"\n{mode}: {total_applied} rewrite(s) in {files_changed} file(s); "
        f"{total_flagged} citation shape(s) left flagged for manual review."
    )
    if not args.apply and total_applied:
        print("Re-run with --apply to write. Blog HTML picks the edits up "
              "on the next nightly --blogs regen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
