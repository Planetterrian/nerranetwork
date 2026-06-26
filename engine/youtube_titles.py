"""LLM-optimized YouTube titles — separate from the spoken episode hook.

The pipeline historically reused the spoken hook verbatim as the YouTube title
(``engine.video_metadata._build_seo_title``). That hook is written for the ear
(it opens the audio), not for the YouTube search/browse surface. This module
generates a click-optimized title (front-loaded keywords, curiosity gap,
honest specificity) via one cheap Grok call, returning best-first candidates so
the runner can ship the top one and stash the rest as A/B "Test & Compare"
variants for the operator.

Design contract:
  - Pure best-effort. Any failure (no API key, network, refusal, empty output)
    returns an empty list; callers fall back to the hook-based title. This
    NEVER raises and NEVER blocks an upload.
  - Touches only metadata (title text), never audio — so it is outside the
    landmine #17 A/B-listen gate.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PROMPT_PATH = _REPO_ROOT / "shows" / "prompts" / "_shared" / "youtube_title.txt"

# YouTube's hard cap is 100 chars; we aim well under so the title isn't
# truncated mid-word in search/browse. Candidates longer than the hard cap
# are dropped (the LLM was asked to stay ≤90).
YOUTUBE_TITLE_HARD_MAX = 100


def _clean_title(line: str) -> str:
    """Strip the formatting noise an LLM tends to wrap a title line in."""
    t = line.strip()
    # Drop leading list markers / numbering: "1.", "1)", "-", "*", "•".
    t = re.sub(r"^\s*(?:\d+[.)]|[-*•])\s*", "", t)
    # Strip surrounding quotes/backticks.
    t = t.strip().strip('"“”‘’`').strip()
    # Drop a leading "Title:" label if the model added one.
    t = re.sub(r"^(?:title|option|candidate)\s*\d*\s*[:\-]\s*", "", t,
               flags=re.IGNORECASE)
    # YouTube rejects < and > in titles; markdown bold/italic are noise.
    t = t.replace("<", "").replace(">", "")
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
    t = re.sub(r"[#]+", "", t)  # no hashtags in the title itself
    return t.strip()


def generate_youtube_titles(
    *,
    hook: str,
    digest_text: str,
    show_name: str,
    episode_num: int,
    keywords: Optional[List[str]] = None,
    n: int = 3,
    model: str = "grok-4.3",
) -> List[str]:
    """Return up to *n* click-optimized title candidates, best first.

    Returns ``[]`` on any failure — callers must fall back gracefully.
    """
    try:
        from engine.generator import _call_grok, load_prompt

        prompt = load_prompt(
            str(_PROMPT_PATH),
            {
                "show_name": show_name or "",
                "episode_num": episode_num,
                "hook": (hook or "").strip(),
                "keywords": ", ".join(keywords or []),
                "digest_excerpt": (digest_text or "")[:2000],
                "n": n,
            },
        )
        text, _meta = _call_grok(
            prompt,
            model=model,
            temperature=0.8,
            max_tokens=400,
        )
    except Exception as exc:  # noqa: BLE001 — never block an upload
        logger.warning("YouTube title generation failed: %s", exc)
        return []

    candidates: List[str] = []
    seen: set[str] = set()
    for line in (text or "").splitlines():
        cleaned = _clean_title(line)
        if not cleaned or len(cleaned) > YOUTUBE_TITLE_HARD_MAX:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(cleaned)
        if len(candidates) >= n:
            break
    return candidates


def best_youtube_title(
    *,
    hook: str,
    digest_text: str,
    show_name: str,
    episode_num: int,
    keywords: Optional[List[str]] = None,
    model: str = "grok-4.3",
) -> Optional[str]:
    """Convenience: the single best candidate, or ``None`` on failure."""
    cands = generate_youtube_titles(
        hook=hook,
        digest_text=digest_text,
        show_name=show_name,
        episode_num=episode_num,
        keywords=keywords,
        n=1,
        model=model,
    )
    return cands[0] if cands else None
