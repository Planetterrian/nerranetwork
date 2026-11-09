#!/usr/bin/env python3
"""Auto-restock a daily show's curriculum with Grok (Nov 9 2026).

Prediction Markets Daily's How It Works segment takes one subject a day
from ``shows/curricula/prediction_markets.yaml``. The curriculum was
hand-planned and hand-restocked, and on 2026-11-09 it drained to 20
unproduced subjects, one under the three-week floor in
``tests/test_launch_cohort_formats_2026_09_23.py::TestPredictionMarkets``,
which turned the ``curriculum`` check red on main and on every open PR.
The narrative topic queues had the same history until
``scripts/restock_topic_queues.py`` closed the loop in July; this script
is that loop for a curriculum.

What differs from a topic queue, and why it is a separate registry:

* A curriculum entry carries the research query the hook runs every day
  (``search`` for Crossref, ``arxiv``, ``require`` / ``exclude`` title
  filters; ``engine.research_papers.papers_for``). A subject joins the
  curriculum only when THAT query returns at least ``min_papers``
  abstracts, so a subject the episode could not source never takes a slot.
  The topic queues ground with a web search instead
  (``restock_topic_queues.ground_candidates``).
* Every brief carries the show's posture sentence and never a double
  quote (``tests/test_prediction_markets_2026_09_23.py::TestCurriculum``:
  a quoted line in a brief is the sentence the model reproduces). The
  posture sentence is appended in code when the model leaves it out.
* The health weeklies' curricula (Peptides, Longevity) are not registered:
  a weekly at 24+ subjects has six months of runway and its briefs carry a
  medical posture this prompt does not write.

Existing entries are NEVER modified; new ones are appended as
``produced: false`` and the unproduced tail is re-interleaved by category
(``engine.topic_queue.resequence_unproduced``, which every pick runs too).

Usage::

    python scripts/restock_curricula.py              # trigger-gated
    python scripts/restock_curricula.py --dry-run    # print, write nothing
    python scripts/restock_curricula.py --force      # restock above trigger
    python scripts/restock_curricula.py --check      # list thin queued subjects
"""

from __future__ import annotations

import argparse
import logging
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import yaml  # noqa: E402

import restock_topic_queues as rq  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class CurriculumConfig:
    slug: str
    queue_file: str                  # relative to repo root
    prompt_file: str                 # relative to repo root
    episodes_per_week: float
    trigger_weeks: float             # restock when runway < this
    target_weeks: float              # refill up to this runway
    allowed_categories: tuple
    posture: str                     # sentence every brief must carry
    default_exclude: tuple = ()      # title terms every entry excludes
    min_papers: int = 2              # abstracts papers_for must find
    max_new_per_run: int = 40        # runaway backstop
    # rq.build_prompt reads this; a curriculum has no alternation.
    balanced_categories: tuple = field(default_factory=tuple)


CURRICULUM_CONFIGS = {
    "prediction_markets": CurriculumConfig(
        slug="prediction_markets",
        queue_file="shows/curricula/prediction_markets.yaml",
        prompt_file="shows/prompts/prediction_markets_curriculum_restock.txt",
        episodes_per_week=7.0,       # daily show
        trigger_weeks=4.0,           # the alarm test fires under 21 (3.0 weeks)
        target_weeks=8.0,
        allowed_categories=("mechanism", "evidence", "risk", "theory",
                            "history", "research", "law", "regulation",
                            "people"),
        posture="Education only; never a recommendation, a pick or a strategy to follow.",
        default_exclude=("cortical",),
    ),
}

#: A brief states no measured figure: the episode takes its numbers from
#: the abstracts it reads (same rule as the narrative restock prompts).
_STATISTIC_RE = re.compile(r"\d\s*(%|percent\b|per cent\b)", re.I)


def _str_list(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v or "").strip()]


def with_posture(brief: str, posture: str) -> str:
    """The brief, ending on the show's posture sentence exactly once."""
    low = brief.lower()
    if "never" in low and ("recommendation" in low or "legal advice" in low):
        return brief
    return f"{brief.rstrip()} {posture}"


def validate_candidates(candidates: list[dict], queue: list[dict],
                        cfg: CurriculumConfig) -> list[dict]:
    """Valid, novel candidates in curriculum-file shape, model order kept.

    Novelty is checked against the WHOLE curriculum (produced included) and
    earlier candidates in the batch. Never mutates ``queue``."""
    existing_ids = {e.get("id") for e in queue if isinstance(e, dict)}
    existing_titles = [rq._norm_title(e.get("title", ""))
                       for e in queue if isinstance(e, dict)]
    accepted: list[dict] = []
    for cand in candidates:
        title = str(cand.get("title") or "").strip()
        brief = re.sub(r"\s+", " ", str(cand.get("brief") or "")).strip()
        category = str(cand.get("category") or "").strip()
        search = str(cand.get("search") or "").strip()
        arxiv = str(cand.get("arxiv") or "").strip()
        require = _str_list(cand.get("require"))
        if not title or len(brief) < 80:
            logger.info("Rejecting (missing title / thin brief): %r", title[:60])
            continue
        if category not in cfg.allowed_categories:
            logger.info("Rejecting (bad category %r): %r", category, title[:60])
            continue
        if '"' in brief or '"' in title:
            logger.info("Rejecting (quoted line in brief): %r", title[:60])
            continue
        if _STATISTIC_RE.search(brief):
            logger.info("Rejecting (statistic in brief): %r", title[:60])
            continue
        if not search or not require or len(require) > 3:
            logger.info("Rejecting (no usable research query): %r", title[:60])
            continue
        tid = rq.slugify_id(title)
        if tid in existing_ids:
            logger.info("Rejecting (duplicate id %s): %r", tid, title[:60])
            continue
        if rq.title_too_similar(title, existing_titles):
            logger.info("Rejecting (near-duplicate title): %r", title[:60])
            continue
        exclude = list(cfg.default_exclude)
        for term in _str_list(cand.get("exclude")):
            if term not in exclude:
                exclude.append(term)
        entry = {"id": tid, "title": title,
                 "brief": with_posture(brief, cfg.posture),
                 "category": category, "search": search, "require": require}
        if exclude:
            entry["exclude"] = exclude
        if arxiv:
            entry["arxiv"] = arxiv
        entry["produced"] = False
        accepted.append(entry)
        existing_ids.add(tid)
        existing_titles.append(rq._norm_title(title))
    return accepted


def ground_in_papers(entries: list[dict], needed: int, *, papers=None,
                     min_papers: int = 2) -> list[dict]:
    """Keep entries whose OWN research query finds ``min_papers`` abstracts.

    This is the exact call the hook makes on the day the subject airs, so a
    subject kept here is one the episode can cite. A fetch failure drops
    the entry (unverified never joins)."""
    if papers is None:
        from engine.research_papers import papers_for as papers
    kept: list[dict] = []
    for entry in entries:
        if len(kept) >= needed:
            break
        try:
            found = papers(entry) or []
        except Exception as exc:  # noqa: BLE001
            logger.info("Rejecting (paper search failed: %s): %r", exc, entry["title"][:60])
            continue
        if len(found) < min_papers:
            logger.info("Rejecting (%d paper(s) found): %r", len(found), entry["title"][:60])
            continue
        logger.info("  grounded %r on %d paper(s), e.g. %s", entry["title"][:60],
                    len(found), found[0].get("url", ""))
        kept.append(entry)
    return kept


def restock_curriculum(cfg: CurriculumConfig, *, dry_run: bool, force: bool,
                       root: Path = ROOT, generate=None, papers=None) -> dict:
    path = root / cfg.queue_file
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    queue = data.get("queue") or []
    unproduced = sum(1 for e in queue if isinstance(e, dict) and not e.get("produced"))
    weeks = rq.runway_weeks(unproduced, cfg.episodes_per_week)
    needed = rq.topics_needed(unproduced, cfg)
    if force and needed == 0:
        needed = min(max(math.ceil(cfg.target_weeks * cfg.episodes_per_week) - unproduced, 0),
                     cfg.max_new_per_run)
    result = {"slug": cfg.slug, "unproduced": unproduced,
              "runway_weeks": round(weeks, 1), "needed": needed, "added": 0}
    if needed == 0:
        logger.info("%s: runway %.1f weeks (%d unproduced) — no restock needed",
                    cfg.slug, weeks, unproduced)
        return result

    logger.info("%s: runway %.1f weeks (%d unproduced) — requesting %d new subjects",
                cfg.slug, weeks, unproduced, needed)
    # Extras: the paper check drops more candidates than the web search does.
    prompt = rq.build_prompt(cfg, queue, needed + max(6, needed // 2))
    candidates, model = (generate or rq.generate_candidates)(prompt)
    result["model"] = model
    valid = validate_candidates(candidates, queue, cfg)
    accepted = ground_in_papers(valid, needed, papers=papers, min_papers=cfg.min_papers)
    result["added"] = len(accepted)

    if not accepted:
        print(f"::warning::{cfg.slug}: curriculum restock produced 0 grounded "
              f"subjects (model returned {len(candidates)}, {len(valid)} valid) — "
              f"curriculum unchanged at {weeks:.1f} weeks.", flush=True)
        return result
    if len(accepted) < needed:
        print(f"::warning::{cfg.slug}: curriculum restock added only "
              f"{len(accepted)} of {needed} subjects after validation.", flush=True)
    for entry in accepted:
        logger.info("  + (%s) %s", entry["category"], entry["title"])
    if dry_run:
        logger.info("%s: dry-run — not writing %d subjects", cfg.slug, len(accepted))
        return result

    queue.extend(accepted)
    rq.resequence_unproduced(queue)
    data["queue"] = queue
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False,
                       default_flow_style=False, width=10000)
    logger.info("%s: curriculum restocked %d → %d unproduced (%.1f weeks)", cfg.slug,
                unproduced, unproduced + len(accepted),
                rq.runway_weeks(unproduced + len(accepted), cfg.episodes_per_week))
    return result


def check_curriculum(cfg: CurriculumConfig, *, root: Path = ROOT, papers=None) -> list[str]:
    """Ids of UNPRODUCED subjects whose own query finds fewer than
    ``min_papers`` abstracts (read-only; for a hand restock's review)."""
    if papers is None:
        from engine.research_papers import papers_for as papers
    data = yaml.safe_load((root / cfg.queue_file).read_text(encoding="utf-8")) or {}
    thin = []
    for e in data.get("queue") or []:
        if not isinstance(e, dict) or e.get("produced"):
            continue
        try:
            n = len(papers(e) or [])
        except Exception:  # noqa: BLE001
            n = 0
        logger.info("  %d paper(s): %s", n, e.get("id"))
        if n < cfg.min_papers:
            thin.append(str(e.get("id")))
    return thin


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Auto-restock show curricula via Grok")
    parser.add_argument("--show", choices=sorted(CURRICULUM_CONFIGS))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--check", action="store_true",
                        help="Read-only: list queued subjects their own query cannot source")
    args = parser.parse_args(argv)
    if args.check:
        thin = []
        for slug in [args.show] if args.show else sorted(CURRICULUM_CONFIGS):
            for tid in check_curriculum(CURRICULUM_CONFIGS[slug]):
                print(f"::warning::{slug}: queued subject {tid} finds under "
                      f"{CURRICULUM_CONFIGS[slug].min_papers} papers", flush=True)
                thin.append(tid)
        return 0
    failures = 0
    for slug in [args.show] if args.show else sorted(CURRICULUM_CONFIGS):
        try:
            result = restock_curriculum(CURRICULUM_CONFIGS[slug],
                                        dry_run=args.dry_run, force=args.force)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            logger.exception("%s curriculum restock failed", slug)
            print(f"::warning::{slug}: curriculum restock failed: {exc}", flush=True)
            continue
        if result["needed"] and result["added"] == 0:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
