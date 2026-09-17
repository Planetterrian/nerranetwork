#!/usr/bin/env python3
"""Run the transcript-cleaning pass again for one editorial package.

Sept 17 2026. The cleaning pass was capped at 6,000 output tokens and every
episode longer than twenty-five minutes shipped with a cleaned transcript
that simply stopped: Dan's published page, Dr. Wolfberg's review page,
Sheldon's package. The pass is fixed; this re-runs it for a package that
already exists without re-running the mix, the recogniser or the other
seven passes.

    python pipelines/voices/reclean_transcript.py <editorial_packages.id>
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    cohost_name, guest_links_markdown, llm, load_prompt, sb_select, sb_update,
)
from shows import show_for  # noqa: E402
from validators.schema_validators import validate_pass_output  # noqa: E402

logger = logging.getLogger("nerra.voices.reclean")


def reclean(package_id: str) -> str:
    pkgs = sb_select("editorial_packages", f"id=eq.{package_id}")
    if not pkgs:
        raise SystemExit(f"no package {package_id}")
    pkg = pkgs[0]
    transcript = pkg.get("transcript_raw") or ""
    if not transcript.strip():
        raise SystemExit("package has no raw transcript to clean")
    interview = sb_select("interviews", f"id=eq.{pkg['interview_id']}")[0]
    app = sb_select("guest_applications", f"id=eq.{interview['application_id']}")[0]
    show = show_for(interview, app)
    prompt = load_prompt(
        "editorial_passes/01_clean_transcript.txt", show=show,
        guest_name=app["name"], guest_title=app.get("title", ""),
        guest_organization=app.get("organization", ""),
        guest_links=guest_links_markdown(app, "Their links") or "(none given)",
        episode_thesis=interview.get("episode_thesis", ""),
        transcript=transcript, cleaned_transcript=transcript,
        cohost_name=cohost_name())
    budget = max(6000, min(32000, len(transcript) // 2))
    error = None
    for attempt in range(2):
        text = llm(prompt + ("" if not error else
                             f"\n\nSTRICT RETRY: your previous output failed validation "
                             f"({error}). Output the WHOLE transcript, nothing else."),
                   temperature=0.3, max_tokens=budget)
        try:
            validate_pass_output("transcript_cleaned", text, raw=transcript)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            logger.warning("attempt %d invalid: %s", attempt + 1, exc)
            continue
        sb_update("editorial_packages", f"id=eq.{package_id}",
                  {"transcript_cleaned": text})
        logger.info("package %s: cleaned transcript replaced (%d -> %d chars)",
                    package_id, len(pkg.get("transcript_cleaned") or ""), len(text))
        return text
    raise SystemExit(f"cleaning failed twice: {error}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    reclean(sys.argv[1])
