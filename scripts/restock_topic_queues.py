#!/usr/bin/env python3
"""Auto-restock narrative-show topic queues with Grok (July 24 2026).

The narrative shows (First Principles Daily, Unintended Consequences) are
topic-queue-driven — no news fetch. Their queues were restocked MANUALLY
during quality passes, and twice now a show has drifted to within days of
an empty queue (FPD was at ~1.3 weeks in June 2026 and back under 3 weeks
in July). An empty queue means `narrative_queue_empty` skips: the show
silently stops publishing.

This script closes the loop: for each registered show it computes the
runway (unproduced topics ÷ episodes per week) and, when it drops below
the trigger, asks Grok for enough NEW topics to refill to the target
runway. Generated topics are validated (schema, category, id/title dedupe
against the ENTIRE queue history including produced entries, near-duplicate
title similarity) and appended as ``produced: false`` entries — the same
shape the manual restocks used. Existing entries are NEVER modified.

Triggers sit comfortably ABOVE the drift-guard thresholds in
tests/test_network_quality_pass.py::TestNarrativeQueueRunway (3.0 / 4.0
weeks), so the alarm test only fires if this automation itself has been
broken for a week+.

Age of AI's queue is deliberately empty (its production runs through the
Nerra Voices interview pipeline; the empty queue makes an accidental
`run_show.py age_of_ai` a clean skip) — it is NOT registered here and must
never be restocked.

Usage::

    python scripts/restock_topic_queues.py                 # all shows, trigger-gated
    python scripts/restock_topic_queues.py --show first_principles
    python scripts/restock_topic_queues.py --dry-run       # print, write nothing
    python scripts/restock_topic_queues.py --force         # restock even above trigger
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-show restock configuration
# ---------------------------------------------------------------------------

@dataclass
class RestockConfig:
    slug: str
    queue_file: str                  # relative to repo root
    prompt_file: str                 # relative to repo root
    episodes_per_week: float
    trigger_weeks: float             # restock when runway < this
    target_weeks: float              # refill queue up to this runway
    allowed_categories: tuple
    # Categories that must BOTH stay stocked (FPD's concrete/opportunity
    # alternation). Empty = no balance requirement.
    balanced_categories: tuple = field(default_factory=tuple)
    max_new_per_run: int = 40        # runaway backstop


RESTOCK_CONFIGS = {
    "first_principles": RestockConfig(
        slug="first_principles",
        queue_file="shows/topic_queues/first_principles.yaml",
        prompt_file="shows/prompts/first_principles_restock.txt",
        episodes_per_week=7.0,
        trigger_weeks=4.0,           # alarm test fires at 3.0
        target_weeks=8.0,
        allowed_categories=("concrete_example", "opportunity_area"),
        balanced_categories=("concrete_example", "opportunity_area"),
    ),
    "unintended_consequences": RestockConfig(
        slug="unintended_consequences",
        queue_file="shows/topic_queues/unintended_consequences.yaml",
        prompt_file="shows/prompts/unintended_consequences_restock.txt",
        episodes_per_week=7.0,
        trigger_weeks=5.0,           # alarm test fires at 4.0
        target_weeks=8.0,
        allowed_categories=("classic", "tech", "policy", "medicine",
                            "infrastructure", "economics"),
    ),
}


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested)
# ---------------------------------------------------------------------------

def runway_weeks(unproduced_count: int, episodes_per_week: float) -> float:
    if episodes_per_week <= 0:
        return float("inf")
    return unproduced_count / episodes_per_week


def topics_needed(unproduced_count: int, cfg: RestockConfig) -> int:
    """How many new topics to reach the target runway (0 when above trigger)."""
    if runway_weeks(unproduced_count, cfg.episodes_per_week) >= cfg.trigger_weeks:
        return 0
    target = math.ceil(cfg.target_weeks * cfg.episodes_per_week)
    return min(max(target - unproduced_count, 0), cfg.max_new_per_run)


def slugify_id(title: str) -> str:
    """Queue-id from a title: lowercase, hyphenated, trimmed to ~5 words."""
    words = re.findall(r"[a-z0-9]+", title.lower())
    return "-".join(words[:5]) or "topic"


def _norm_title(title: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (title or "").lower()))


def title_too_similar(title: str, existing_norm_titles: list[str],
                      threshold: float = 0.6) -> bool:
    """Fuzzy near-duplicate check against every historical title."""
    try:
        from engine.utils import calculate_similarity
    except Exception:  # noqa: BLE001 — degrade to exact-match only
        calculate_similarity = None
    norm = _norm_title(title)
    if not norm:
        return True
    for other in existing_norm_titles:
        if norm == other:
            return True
        if calculate_similarity is not None and \
                calculate_similarity(norm, other) >= threshold:
            return True
    return False


def parse_topics_json(text: str) -> list[dict]:
    """Parse the model's JSON array, tolerating a fenced code block."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    # Tolerate prose around the array: take the outermost [ ... ].
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end <= start:
        raise ValueError("no JSON array found in model output")
    parsed = json.loads(text[start:end + 1])
    if not isinstance(parsed, list):
        raise TypeError("model output is not a JSON array")
    return [t for t in parsed if isinstance(t, dict)]


def validate_and_dedupe(
    candidates: list[dict],
    queue: list[dict],
    cfg: RestockConfig,
    needed: int,
) -> list[dict]:
    """Filter candidates to valid, novel entries in queue-file shape.

    Dedupe is against the ENTIRE queue (produced included — a show must
    never re-cover a produced topic) and against earlier candidates in the
    same batch. Never mutates ``queue``.
    """
    existing_ids = {e.get("id") for e in queue if isinstance(e, dict)}
    existing_titles = [_norm_title(e.get("title", ""))
                       for e in queue if isinstance(e, dict)]
    accepted: list[dict] = []
    for cand in candidates:
        if len(accepted) >= needed:
            break
        title = str(cand.get("title") or "").strip()
        brief = str(cand.get("brief") or "").strip()
        category = str(cand.get("category") or "").strip()
        if not title or len(brief) < 80:
            logger.info("Rejecting candidate (missing title / thin brief): %r", title[:60])
            continue
        if category not in cfg.allowed_categories:
            logger.info("Rejecting candidate (bad category %r): %r", category, title[:60])
            continue
        tid = slugify_id(title)
        if tid in existing_ids:
            logger.info("Rejecting candidate (duplicate id %s): %r", tid, title[:60])
            continue
        if title_too_similar(title, existing_titles):
            logger.info("Rejecting candidate (near-duplicate title): %r", title[:60])
            continue
        accepted.append({
            "id": tid,
            "title": title,
            "brief": brief,
            "category": category,
            "produced": False,
            "episode_number": None,
            "produced_date": None,
        })
        existing_ids.add(tid)
        existing_titles.append(_norm_title(title))
    return accepted


def build_prompt(cfg: RestockConfig, queue: list[dict], needed: int) -> str:
    """Render the show's restock prompt with queue history + counts."""
    template = (ROOT / cfg.prompt_file).read_text(encoding="utf-8")
    lines = []
    for e in queue:
        if isinstance(e, dict) and e.get("title"):
            state = "produced" if e.get("produced") else "queued"
            lines.append(f"- [{state}] ({e.get('category', '?')}) {e['title']}")
    balance = ""
    if cfg.balanced_categories:
        per = math.ceil(needed / len(cfg.balanced_categories))
        balance = (
            f"Balance the categories: roughly {per} topics for each of "
            f"{', '.join(cfg.balanced_categories)} (the show alternates "
            f"between them episode by episode)."
        )
    return (template
            .replace("{existing_topics}", "\n".join(lines))
            .replace("{needed}", str(needed))
            .replace("{category_guidance}", balance))


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------

def restock_show(cfg: RestockConfig, *, dry_run: bool, force: bool) -> dict:
    """Restock one show. Returns a result dict for the run summary."""
    queue_path = ROOT / cfg.queue_file
    data = yaml.safe_load(queue_path.read_text(encoding="utf-8")) or {}
    queue = data.get("queue") or []
    unproduced = sum(
        1 for e in queue if isinstance(e, dict) and not e.get("produced"))
    weeks = runway_weeks(unproduced, cfg.episodes_per_week)
    needed = topics_needed(unproduced, cfg)
    if force and needed == 0:
        needed = min(
            max(math.ceil(cfg.target_weeks * cfg.episodes_per_week) - unproduced, 0),
            cfg.max_new_per_run,
        )

    result = {"slug": cfg.slug, "unproduced": unproduced,
              "runway_weeks": round(weeks, 1), "needed": needed, "added": 0}
    if needed == 0:
        logger.info("%s: runway %.1f weeks (%d unproduced) — no restock needed",
                    cfg.slug, weeks, unproduced)
        return result

    logger.info("%s: runway %.1f weeks (%d unproduced) — requesting %d new topics",
                cfg.slug, weeks, unproduced, needed)

    # Ask for extras so validation losses don't leave us short.
    from engine.generator import _call_grok  # deferred: needs GROK_API_KEY
    prompt = build_prompt(cfg, queue, needed + max(4, needed // 3))
    text, _ = _call_grok(
        prompt,
        temperature=0.8,
        max_tokens=8000,
    )
    candidates = parse_topics_json(text)
    accepted = validate_and_dedupe(candidates, queue, cfg, needed)
    result["added"] = len(accepted)

    if not accepted:
        print(f"::warning::{cfg.slug}: restock produced 0 valid topics "
              f"(model returned {len(candidates)} candidates) — queue "
              f"unchanged at {weeks:.1f} weeks runway.", flush=True)
        return result

    if len(accepted) < needed:
        print(f"::warning::{cfg.slug}: restock added only {len(accepted)} of "
              f"{needed} requested topics after validation.", flush=True)

    for entry in accepted:
        logger.info("  + (%s) %s", entry["category"], entry["title"])

    if dry_run:
        logger.info("%s: dry-run — not writing %d topics", cfg.slug, len(accepted))
        return result

    queue.extend(accepted)
    data["queue"] = queue
    # Same write convention as engine.topic_queue.mark_topic_produced.
    with queue_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False,
                       default_flow_style=False, width=10000)
    new_weeks = runway_weeks(unproduced + len(accepted), cfg.episodes_per_week)
    logger.info("%s: queue restocked %d → %d unproduced (%.1f weeks runway)",
                cfg.slug, unproduced, unproduced + len(accepted), new_weeks)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Auto-restock narrative topic queues via Grok")
    parser.add_argument("--show", choices=sorted(RESTOCK_CONFIGS), help="Only this show")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="Restock to target even when above the trigger")
    args = parser.parse_args(argv)

    slugs = [args.show] if args.show else sorted(RESTOCK_CONFIGS)
    failures = 0
    for slug in slugs:
        cfg = RESTOCK_CONFIGS[slug]
        try:
            result = restock_show(cfg, dry_run=args.dry_run, force=args.force)
        except Exception as exc:
            failures += 1
            logger.exception("%s restock failed", slug)
            # Only escalate to ::error:: when the queue is ALREADY inside the
            # drift-guard alarm zone and we failed to refill it.
            print(f"::warning::{slug}: topic-queue restock failed: {exc}", flush=True)
            continue
        if result["needed"] and result["added"] == 0:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
