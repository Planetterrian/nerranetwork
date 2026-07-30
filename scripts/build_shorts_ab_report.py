#!/usr/bin/env python3
"""Score the Shorts motion A/B — api/shorts_ab.json.

Reads the arm each published Short actually shipped with (recorded by
``engine.shorts_ab`` into the per-show video index, carried through by
``scripts/fetch_youtube_analytics.py``) and reports the two arms side by
side on the metrics that matter for a Short:

    views                 did the algorithm push it
    average_view_percentage  did people watch it   <- the strongest signal
    subscribers_gained    did it convert
    sessions              did it send anyone to the site (from api/funnel.json)

Three things this report refuses to do, because an A/B that flatters is
worse than no A/B:

  * **Call a winner early.** Every comparison is reported with a 95%
    confidence interval on the difference (Welch, unequal variances). If
    that interval contains zero, the verdict is ``no_measurable_difference``
    — not "the treatment is ahead".
  * **Count a fallback as treatment.** A Short that intended to be video
    and shipped as stills was recorded as stills at publish time, so it
    lands in the control arm where it belongs.
  * **Mix in videos that were never eligible.** Shorts published before
    the experiment carry no ``variant`` at all and are excluded, not
    silently treated as control.

Usage::

    python scripts/build_shorts_ab_report.py             # write api/shorts_ab.json
    python scripts/build_shorts_ab_report.py --dry-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.shorts_ab import VARIANT_GROK_VIDEO, VARIANT_STILLS  # noqa: E402

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(levelname)s %(message)s")
log = logging.getLogger("shorts_ab_report")

SCHEMA_VERSION = 1

# Below this many Shorts per arm, no comparison is reported at all. The
# experiment ships one treatment Short a day, so this is ~2 weeks — long
# enough that a single viral Short cannot decide the result.
MIN_PER_ARM = 14

# Metrics compared, and whether more is better (all of these: yes).
_METRICS = (
    ("views", "views"),
    ("average_view_percentage", "average_view_percentage"),
    ("subscribers_gained", "subscribers_gained"),
)


def _mean(values: Sequence[float]) -> Optional[float]:
    return (sum(values) / len(values)) if values else None


def _variance(values: Sequence[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    m = sum(values) / len(values)
    return sum((v - m) ** 2 for v in values) / (len(values) - 1)


def welch_difference(treatment: Sequence[float],
                     control: Sequence[float]) -> Dict[str, Any]:
    """Difference of means with a 95% CI (Welch, unequal variances).

    A confidence interval rather than a p-value on purpose: the decision
    here is "is the effect big enough to be worth ~$32/month", and an
    interval answers that directly while a bare p-value does not.
    ``1.96`` is the normal approximation — with n around 14-30 per arm
    that is slightly optimistic, which is why ``MIN_PER_ARM`` gates the
    comparison and the verdict language stays conservative.
    """
    n_t, n_c = len(treatment), len(control)
    m_t, m_c = _mean(treatment), _mean(control)
    if m_t is None or m_c is None or n_t < 2 or n_c < 2:
        return {"difference": None, "ci95": None, "verdict": "insufficient_data"}
    v_t, v_c = _variance(treatment) or 0.0, _variance(control) or 0.0
    se = math.sqrt(v_t / n_t + v_c / n_c)
    diff = m_t - m_c
    if se == 0:
        # Zero variance in both arms: the difference is exact, and a CI
        # of width zero is the honest description of that.
        return {
            "difference": round(diff, 3),
            "ci95": [round(diff, 3), round(diff, 3)],
            "relative_pct": (round(100.0 * diff / m_c, 2) if m_c else None),
            "verdict": ("treatment_better" if diff > 0
                        else "control_better" if diff < 0
                        else "no_measurable_difference"),
        }
    lo, hi = diff - 1.96 * se, diff + 1.96 * se
    if lo <= 0 <= hi:
        verdict = "no_measurable_difference"
    elif lo > 0:
        verdict = "treatment_better"
    else:
        verdict = "control_better"
    return {
        "difference": round(diff, 3),
        "ci95": [round(lo, 3), round(hi, 3)],
        "relative_pct": (round(100.0 * diff / m_c, 2) if m_c else None),
        "verdict": verdict,
    }


def _collect_videos() -> List[dict]:
    """Every analytics row that carries an experiment arm."""
    stats = _ROOT / "api" / "youtube_stats.json"
    try:
        payload = json.loads(stats.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        log.warning("cannot read %s: %s", stats, exc)
        return []
    rows = []
    for block in (payload.get("shows") or {}).values():
        for video in (block or {}).get("videos") or []:
            variant = (video.get("variant") or "").strip()
            if variant in (VARIANT_STILLS, VARIANT_GROK_VIDEO):
                rows.append(video)
    return rows


def _arm_summary(videos: Sequence[dict]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"n": len(videos)}
    for label, field in _METRICS:
        values = [float(v.get(field) or 0.0) for v in videos]
        out[label] = {
            "mean": (round(_mean(values), 3) if values else None),
            "total": round(sum(values), 3) if values else 0,
            "median": (round(sorted(values)[len(values) // 2], 3)
                       if values else None),
        }
    return out


def _episode_cost(slug: str) -> Optional[float]:
    """What the experiment has actually spent, from the episode metrics.

    Read rather than assumed: the projected ~$1.05/episode is what the
    config allows, not what the clips cost after fallbacks.
    """
    total = 0.0
    seen = 0
    for path in sorted((_ROOT / "digests" / slug).glob("metrics_ep*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        # ``metrics.record`` writes into ``counters``; only fall back to
        # the top level so a future schema change cannot silently zero
        # the spend line (reading the wrong level would report $0 spent
        # on an experiment that is in fact billing every day).
        if not isinstance(data, dict):
            continue
        block = (data.get("counters") or {}).get("shorts_ab") \
            or data.get("shorts_ab")
        if isinstance(block, dict) and "cost_usd" in block:
            total += float(block.get("cost_usd") or 0.0)
            seen += 1
    return round(total, 4) if seen else None


def build() -> Dict[str, Any]:
    videos = _collect_videos()
    by_variant: Dict[str, List[dict]] = defaultdict(list)
    by_show: Dict[str, Dict[str, List[dict]]] = defaultdict(
        lambda: defaultdict(list))
    for video in videos:
        by_variant[video["variant"]].append(video)
        by_show[video.get("show_slug") or "?"][video["variant"]].append(video)

    treatment = by_variant.get(VARIANT_GROK_VIDEO, [])
    control = by_variant.get(VARIANT_STILLS, [])

    comparisons: Dict[str, Any] = {}
    enough = len(treatment) >= MIN_PER_ARM and len(control) >= MIN_PER_ARM
    if enough:
        for label, field in _METRICS:
            comparisons[label] = welch_difference(
                [float(v.get(field) or 0.0) for v in treatment],
                [float(v.get(field) or 0.0) for v in control],
            )

    # Site sessions per arm — the funnel's own read on the experiment,
    # independent of YouTube's numbers (campaign ids carry the variant).
    sessions_by_variant = {}
    try:
        funnel = json.loads(
            (_ROOT / "api" / "funnel.json").read_text(encoding="utf-8"))
        sessions_by_variant = (
            ((funnel.get("stages") or {}).get("click") or {})
            .get("by_variant") or {}
        )
    except Exception:  # noqa: BLE001 — funnel.json is optional here
        sessions_by_variant = {}

    shows = sorted({v.get("show_slug") for v in videos if v.get("show_slug")})
    status = (
        "ready" if enough else
        "collecting" if videos else
        "not_started"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(
            timespec="seconds"),
        "status": status,
        "min_per_arm": MIN_PER_ARM,
        "shows": shows,
        "arms": {
            VARIANT_GROK_VIDEO: _arm_summary(treatment),
            VARIANT_STILLS: _arm_summary(control),
        },
        "comparisons": comparisons,
        "sessions_by_variant": sessions_by_variant,
        "spend_usd": {slug: _episode_cost(slug) for slug in shows},
        "by_show": {
            slug: {variant: _arm_summary(rows)
                   for variant, rows in sorted(arms.items())}
            for slug, arms in sorted(by_show.items())
        },
        "notes": [
            f"No comparison is reported until BOTH arms reach "
            f"{MIN_PER_ARM} Shorts.",
            "A Short that intended the video arm but fell back to stills "
            "is counted as stills — it is what shipped.",
            "Shorts published before the experiment carry no variant and "
            "are excluded entirely.",
            "'no_measurable_difference' means the 95% interval on the "
            "difference contains zero, not that the arms are equal.",
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(_ROOT / "api" / "shorts_ab.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    data = build()
    if args.dry_run:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    log.info("wrote %s (status=%s, treatment n=%d, control n=%d)",
             out, data["status"],
             data["arms"][VARIANT_GROK_VIDEO]["n"],
             data["arms"][VARIANT_STILLS]["n"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
