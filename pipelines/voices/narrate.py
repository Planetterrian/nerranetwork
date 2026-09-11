"""Synthesize a set of narration segments in Mira's voice and put them in R2.

Why this exists (Sept 11 2026): produce_episode writes and voices narration
as one automatic pass over an approved package. That is right for the normal
path and useless when an episode needs a hand-written pickup — a proper
introduction for a guest, a closing summary replacing a fumbled goodbye.
This takes a JSON file of segments, voices them, and uploads them, so the
words can be written and reviewed like words instead of being a side effect
of a production run.

    pipelines/voices/narration/<slug>.json
      { "show": "age_of_ai",
        "segments": [ {"id": "intro", "text": "..."}, ... ] }

Each segment lands at <r2_prefix>/narration/<slug>/<id>.mp3 and its public
URL is printed. Re-running overwrites, so a rewrite is just a re-run.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from common import ROOT, logger, r2_upload  # noqa: E402
from shows import get_show  # noqa: E402

NARRATION_DIR = Path(__file__).parent / "narration"


def narrate(slug: str) -> dict:
    spec_path = NARRATION_DIR / f"{slug}.json"
    if not spec_path.exists():
        raise SystemExit(f"no narration spec at {spec_path}")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    show = get_show(spec.get("show") or "age_of_ai")
    segments = spec.get("segments") or []
    if not segments:
        raise SystemExit("spec has no segments")

    from audio.generate_narration import synthesize_segments

    out: dict = {}
    with tempfile.TemporaryDirectory() as tmp:
        paths = synthesize_segments(segments, Path(tmp))
        for seg_id, mp3 in paths.items():
            url = r2_upload(mp3, show.r2_key("narration", slug, f"{seg_id}.mp3"))
            out[seg_id] = url
            logger.info("narration %s -> %s", seg_id, url)
    return out


if __name__ == "__main__":
    slug = os.environ.get("NARRATION_SLUG") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not slug:
        raise SystemExit("NARRATION_SLUG (or argv[1]) required")
    for seg_id, url in narrate(slug).items():
        print(f"{seg_id}\t{url}")
