#!/usr/bin/env python3
"""Validate a show is ready for its first production run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def validate(slug: str) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []

    yaml_path = ROOT / "shows" / f"{slug}.yaml"
    if not yaml_path.exists():
        errors.append(f"Missing {yaml_path}")
        return errors

    from engine.config import load_config

    try:
        cfg = load_config(yaml_path)
    except Exception as exc:
        errors.append(f"Config load failed: {exc}")
        return errors

    for label, path_str in [
        ("digest prompt", cfg.llm.digest_prompt_file),
        ("podcast prompt", cfg.llm.podcast_prompt_file),
        ("system prompt", cfg.llm.system_prompt_file),
    ]:
        if path_str and not (ROOT / path_str).exists():
            errors.append(f"Missing {label}: {path_str}")

    if not cfg.sources and not getattr(cfg, "narrative_mode", False):
        errors.append("No RSS sources (add feeds or enable narrative_mode)")

    queries = list(getattr(cfg.youtube, "image_queries", None) or [])
    if len(queries) < 3:
        warnings.append(
            "youtube.image_queries has fewer than 3 entries "
            "(required if YouTube is ever enabled)"
        )

    meta_path = ROOT / "shows" / "network_meta.yaml"
    if meta_path.exists():
        import yaml
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        if slug not in meta and slug not in _builtin_slugs():
            warnings.append(
                f"{slug} not in shows/network_meta.yaml — "
                "run scaffold_show or add website registry entry"
            )

    cover = ROOT / "assets" / "covers" / f"{slug.replace('_', '-')}.jpg"
    if not cover.exists():
        warnings.append(f"Cover art missing: {cover}")

    pending = ROOT / "shows" / "scaffold_pending.yaml"
    if pending.exists():
        import yaml
        data = yaml.safe_load(pending.read_text(encoding="utf-8")) or {}
        for entry in data.get("cron_entries", []):
            if entry.get("slug") == slug:
                warnings.append(
                    "Cron not applied yet — paste line from scaffold_pending.yaml "
                    "into .github/workflows/run-show.yml CRON_MAP"
                )

    if errors:
        return errors
    return warnings


def _builtin_slugs() -> set[str]:
    from generate_html import NETWORK_SHOWS
    return set(NETWORK_SHOWS.keys())


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("slug")
    args = p.parse_args()
    issues = validate(args.slug)
    if not issues:
        print(f"OK: {args.slug} is ready for --test and first production run.")
        return 0
    fatal = [i for i in issues if i.startswith("Missing") or "failed" in i or "No RSS" in i]
    for msg in issues:
        label = "ERROR" if msg in fatal or "Missing" in msg else "WARN"
        print(f"{label}: {msg}")
    return 1 if fatal else (0 if not issues else 0)


if __name__ == "__main__":
    raise SystemExit(main())
