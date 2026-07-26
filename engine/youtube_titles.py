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


def _performance_hint(perf_dir: Optional[Path], *, channel: str = "en") -> str:
    """A one-paragraph 'what's been working' steer from past YouTube
    retention, or "" when there's no data yet.

    Read from ``<perf_dir>/youtube_performance.json`` — *perf_dir* is the
    show's own output dir (slug != dir for some shows, e.g. tesla →
    digests/tesla_shorts_time), written by
    ``scripts/update_youtube_performance.py``. Prefers channel-scoped
    hints (``title_hint_en`` / ``title_hint_ru``) when present, else the
    primary ``title_hint``. Pure best-effort — title-only, no audio impact.
    """
    if not perf_dir:
        return ""
    try:
        import json
        path = Path(perf_dir) / "youtube_performance.json"
        if not path.exists():
            return ""
        data = json.loads(path.read_text(encoding="utf-8"))
        channel = (channel or "en").lower()
        keyed = (
            data.get("title_hint_ru") if channel == "ru"
            else data.get("title_hint_en")
        )
        hint = (keyed or data.get("title_hint") or "").strip()
        return ("\nWHAT'S WORKING (from this show's recent YouTube retention — "
                "lean toward these angles/keywords if they fit honestly):\n"
                f"{hint}\n") if hint else ""
    except Exception:
        return ""


def generate_youtube_titles(
    *,
    hook: str,
    digest_text: str,
    show_name: str,
    episode_num: int,
    keywords: Optional[List[str]] = None,
    n: int = 3,
    model: str = "grok-4.3",
    perf_dir: Optional[Path] = None,
    channel: str = "en",
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
                "performance_hint": _performance_hint(
                    perf_dir, channel=channel),
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


_BUNDLE_PROMPT_PATH = (
    _REPO_ROOT / "shows" / "prompts" / "_shared" / "youtube_title_bundle.txt"
)
# Punch text renders HUGE on the thumbnail — keep it short and honest.
PUNCH_TEXT_MAX_CHARS = 26
SHORT_TITLE_MAX_CHARS = 70


def _clean_punch(text: str) -> str:
    """Normalize the thumbnail punch text; '' when unusable."""
    t = _clean_title(text).upper()
    # Punch is display text, not a sentence — strip trailing punctuation.
    t = t.strip().rstrip(".!,;:")
    words = t.split()
    if not (1 < len(words) <= 4):
        return ""
    if len(t) > PUNCH_TEXT_MAX_CHARS:
        return ""
    # Never ship the generic hype words the prompt bans.
    banned = {"BREAKING", "SHOCKING", "NEWS", "UNBELIEVABLE"}
    if set(words) & banned and len(words) <= 2:
        return ""
    return t


def generate_title_bundle(
    *,
    hook: str,
    digest_text: str,
    show_name: str,
    episode_num: int,
    keywords: Optional[List[str]] = None,
    n: int = 3,
    model: str = "grok-4.3",
    perf_dir: Optional[Path] = None,
    short_window_texts: Optional[List[str]] = None,
    channel: str = "en",
) -> dict:
    """One Grok call → long-form titles + thumbnail punch + Short titles.

    July 18 2026: extends the optimized-titles call (same cost — still one
    call per episode) to also return a 2-4 word ALL-CAPS thumbnail "punch
    text" (the big-text CTR lever) and a punchy ≤60-char title per Short
    window (Shorts previously shipped raw transcript opening text as their
    headline).

    Returns ``{"titles": [...], "punch_text": str, "short_titles": [...]}``
    — every field may be empty; callers fall back exactly as before
    (hook-based long title, legacy hook thumbnail, opening-text Short
    titles). Never raises, never blocks an upload.
    """
    empty = {"titles": [], "punch_text": "", "short_titles": []}
    windows = [w.strip() for w in (short_window_texts or []) if w and w.strip()]
    try:
        from engine.generator import _call_grok, load_prompt

        window_lines = "\n".join(
            f"{i + 1}. \"{w[:200]}\"" for i, w in enumerate(windows)
        ) or "(none)"
        prompt = load_prompt(
            str(_BUNDLE_PROMPT_PATH),
            {
                "show_name": show_name or "",
                "episode_num": episode_num,
                "hook": (hook or "").strip(),
                "keywords": ", ".join(keywords or []),
                "digest_excerpt": (digest_text or "")[:2000],
                "performance_hint": _performance_hint(
                    perf_dir, channel=channel),
                "short_windows": window_lines,
                "n": n,
            },
        )
        text, _meta = _call_grok(
            prompt,
            model=model,
            temperature=0.8,
            max_tokens=500,
        )
    except Exception as exc:  # noqa: BLE001 — never block an upload
        logger.warning("YouTube title bundle generation failed: %s", exc)
        return empty

    titles: List[str] = []
    punch = ""
    short_titles: dict = {}
    seen: set = set()
    for raw in (text or "").splitlines():
        line = raw.strip()
        m = re.match(r"^(TITLE|PUNCH|SHORT(\d+))\s*:\s*(.+)$", line,
                     flags=re.IGNORECASE)
        if not m:
            continue
        label = m.group(1).upper()
        value = m.group(3).strip()
        if label == "TITLE":
            cleaned = _clean_title(value)
            key = cleaned.lower()
            if (cleaned and len(cleaned) <= YOUTUBE_TITLE_HARD_MAX
                    and key not in seen and len(titles) < n):
                seen.add(key)
                titles.append(cleaned)
        elif label == "PUNCH" and not punch:
            punch = _clean_punch(value)
        else:  # SHORTn
            idx = int(m.group(2)) - 1
            cleaned = _clean_title(value)
            if cleaned and 0 <= idx < max(len(windows), 1):
                short_titles[idx] = cleaned[:SHORT_TITLE_MAX_CHARS].strip()

    return {
        "titles": titles,
        "punch_text": punch,
        "short_titles": [short_titles.get(i, "") for i in
                         range(len(windows))],
    }


def best_youtube_title(
    *,
    hook: str,
    digest_text: str,
    show_name: str,
    episode_num: int,
    keywords: Optional[List[str]] = None,
    model: str = "grok-4.3",
    perf_dir: Optional[Path] = None,
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
        perf_dir=perf_dir,
    )
    return cands[0] if cands else None
