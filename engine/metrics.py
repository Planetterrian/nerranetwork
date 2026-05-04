"""Pipeline observability — stage timing, cost tracking, and structured metrics.

Records per-stage duration and cost data for each episode run. Metrics are
saved as a JSON file alongside episode output for post-hoc analysis.

Usage:
    from engine.metrics import PipelineMetrics

    metrics = PipelineMetrics("tesla", 42)
    with metrics.stage("fetch"):
        articles = fetch_rss_articles(...)
    with metrics.stage("generate_digest"):
        digest = generate_digest(...)
    metrics.record("article_count", len(articles))
    metrics.save(output_dir)
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StageMetric:
    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_s: float = 0.0
    success: bool = True
    error: str = ""


@dataclass
class PipelineMetrics:
    """Collects timing and metadata for a single pipeline run."""

    show_slug: str
    episode_num: int
    stages: List[StageMetric] = field(default_factory=list)
    counters: Dict[str, Any] = field(default_factory=dict)
    _current_stage: Optional[StageMetric] = field(default=None, repr=False)

    @contextmanager
    def stage(self, name: str):
        """Context manager to time a pipeline stage.

        Usage::

            with metrics.stage("tts_synthesis"):
                synthesize(...)
        """
        metric = StageMetric(name=name, start_time=time.monotonic())
        self._current_stage = metric
        try:
            yield metric
            metric.success = True
        except Exception as exc:
            metric.success = False
            metric.error = str(exc)[:200]
            raise
        finally:
            metric.end_time = time.monotonic()
            metric.duration_s = round(metric.end_time - metric.start_time, 2)
            self.stages.append(metric)
            self._current_stage = None
            logger.info(
                "[metrics] %s.%s: %.1fs %s",
                self.show_slug,
                name,
                metric.duration_s,
                "OK" if metric.success else f"FAILED ({metric.error[:60]})",
            )

    def record(self, key: str, value: Any) -> None:
        """Record an arbitrary counter or metadata value."""
        self.counters[key] = value

    def total_duration(self) -> float:
        """Sum of all stage durations."""
        return round(sum(s.duration_s for s in self.stages), 2)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metrics to a JSON-compatible dict.

        ``metrics_schema_version`` is bumped whenever the dict shape
        evolves (new top-level fields, renamed fields, type changes
        on existing fields). Dashboard/backfill code can apply
        backward-compatibility transforms based on this value.

        Schema history:
        - 1 (May 2026, Phase 3.5 of the audit): introduces this field.
          Top-level keys: show_slug, episode_num, total_duration_s,
          stages[], counters{}. Per-stage: name, duration_s, success,
          optional error.
        """
        return {
            "metrics_schema_version": 1,
            "show_slug": self.show_slug,
            "episode_num": self.episode_num,
            "total_duration_s": self.total_duration(),
            "stages": [
                {
                    "name": s.name,
                    "duration_s": s.duration_s,
                    "success": s.success,
                    **({"error": s.error} if s.error else {}),
                }
                for s in self.stages
            ],
            "counters": self.counters,
        }

    def save(self, output_dir: Path) -> Path:
        """Write metrics JSON to the output directory."""
        path = output_dir / f"metrics_ep{self.episode_num:03d}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        logger.info("Pipeline metrics saved: %s (total %.1fs)", path.name, self.total_duration())
        return path

    def summary(self) -> str:
        """One-line summary for logging."""
        parts = [f"{s.name}={s.duration_s:.1f}s" for s in self.stages]
        return f"[{self.show_slug} ep{self.episode_num}] total={self.total_duration():.1f}s | " + " | ".join(parts)
