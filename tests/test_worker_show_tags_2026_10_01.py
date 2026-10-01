"""The Worker's newsletter-tag allow-list is read from the TypeScript as
text (no workflow runs vitest). Oct 1 2026: thirteen show pages offered a
per-show subscribe tag that `SHOW_NEWSLETTER_TAGS` silently dropped."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NON_SHOW = {"_defaults", "_blocked_sources", "pronunciation_map", "network_meta",
            "scaffold_pending", "translation_overrides", "_trading_policy"}


def _worker_tags() -> set[str]:
    src = (ROOT / "workers" / "gallery" / "src" / "handlers.ts").read_text(encoding="utf-8")
    block = src.split("const SHOW_NEWSLETTER_TAGS = new Set([", 1)[1].split("]);", 1)[0]
    block = re.sub(r"//[^\n]*", "", block)
    return set(re.findall(r'"([^"]+)"', block))


def test_every_show_yaml_newsletter_tag_is_in_the_worker_set():
    tags = _worker_tags()
    missing = []
    for path in sorted((ROOT / "shows").glob("*.yaml")):
        if path.stem in NON_SHOW or path.stem.startswith("_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        tag = ((data.get("newsletter") or {}).get("tag") or "").strip()
        if tag and tag not in tags:
            missing.append((path.stem, tag))
    assert not missing, f"show tags the Worker would drop: {missing}"
