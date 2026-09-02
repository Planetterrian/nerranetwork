"""Story-driven scene briefs for episode imagery (Sep 2026).

WHY: every Grok Imagine prompt used to LEAD with one of the show's static
``image_queries`` ("cybertruck", "tesla supercharger", …) and tack the
day's headline on as an 8-word tail — so a Tesla episode about FSD v14
and Q3 deliveries shipped the same four generic pictures as every other
episode, and the library blend then padded the slideshow with older
copies of the same generic pictures. Viewers said the imagery didn't
match what was being said. They were right.

This module turns the episode's actual stories into concrete,
photographable scene briefs — one per story/chapter — and those briefs
LEAD the prompts. One small Grok text call per episode (the same model
family as the digest; ~$0.005) writes the briefs; a deterministic
fallback (headline → visual subject phrase) keeps the pipeline running
with zero LLM dependency when the call fails, refuses, or is disabled.

Contract:
  - Briefs are VISUAL descriptions of a literal scene, never captions:
    no on-image text, no numbers rendered as text, no logos. The
    subject of each brief is the story it belongs to.
  - Output order == input story order, so scene i belongs to story i
    and the chapter scheduler's context map keys on that.
  - Never raises. ``[]`` means "use the legacy image_queries prompts".
"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)

# Hard bounds on what a brief may look like — a caption-length line is a
# text-banner risk (July 2026: Grok painted the headline as chyron text).
_MIN_WORDS = 6
_MAX_WORDS = 32
_MAX_BRIEFS = 12

# Words that mean the model is describing a title card, not a scene.
_TEXTY = re.compile(
    r"\b(headline|caption|title card|chyron|banner|logo|text overlay|"
    r"typography|infographic|chart with numbers|watermark)\b", re.I)


def _clean_brief(raw: str) -> str:
    t = re.sub(r"\s+", " ", str(raw or "")).strip().strip('"“”').strip()
    t = t.rstrip(".;,")
    return t


def _brief_ok(t: str) -> bool:
    n = len(t.split())
    return _MIN_WORDS <= n <= _MAX_WORDS and not _TEXTY.search(t)


def deterministic_briefs(
    headlines: Sequence[str], *, hook: str = "", max_n: int = _MAX_BRIEFS,
) -> List[str]:
    """LLM-free briefs: the visual-subject phrase of each headline.

    Weaker than the model-written briefs (a headline names an event,
    not a picture) but strictly better than a static keyword, and it is
    what ships whenever the model path is off or fails.
    """
    from engine.grok_imagine import _visual_subject_phrase

    out: List[str] = []
    seen: set = set()
    for h in list(headlines or []) + ([hook] if hook else []):
        s = _visual_subject_phrase(h, max_words=10)
        key = s.lower()
        if len(s.split()) >= 3 and key not in seen:
            seen.add(key)
            out.append(s)
        if len(out) >= max_n:
            break
    return out


def _parse_json_array(text: str) -> Optional[list]:
    """Tolerant JSON-array extraction (models wrap arrays in prose/fences)."""
    if not text:
        return None
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def generate_scene_briefs(
    headlines: Sequence[str],
    *,
    hook: str = "",
    show_name: str = "",
    show_descriptor: str = "",
    max_n: int = 8,
    model: str = "grok-4.3",
    enabled: bool = True,
) -> List[str]:
    """One concrete visual scene brief per story, in story order.

    Falls back to :func:`deterministic_briefs` on any failure, refusal,
    malformed output, or when *enabled* is False. Returns at most
    *max_n* briefs; ``[]`` only when there are no usable headlines at
    all (caller then keeps the legacy image_queries prompts).
    """
    stories = [str(h).strip() for h in (headlines or []) if str(h).strip()]
    if hook and hook.strip() and hook.strip() not in stories:
        stories = [hook.strip()] + stories
    stories = stories[:max(1, min(int(max_n), _MAX_BRIEFS))]
    if not stories:
        return []
    fallback = deterministic_briefs(stories, max_n=len(stories))
    if not enabled:
        return fallback

    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(stories))
    prompt = (
        f"You are the picture editor for \"{show_name or 'a daily news podcast'}\". "
        f"House visual style: {show_descriptor or 'photorealistic editorial photography'}.\n\n"
        f"For EACH story below, write ONE concrete, literal, photographable "
        f"scene that a viewer would immediately recognise as being about "
        f"that story — the specific object, place, machine, person-at-work, "
        f"or moment the story is about, with a setting, a time of day or "
        f"lighting, and a camera angle. {_MIN_WORDS}-{_MAX_WORDS} words each. "
        f"Rules: describe only things that can be photographed; no text, "
        f"numbers, logos, charts, captions or signage in the scene; no "
        f"people's faces as the subject unless the story is about a "
        f"person; never invent facts beyond the story line; keep the "
        f"subject matter faithful to the story's actual topic.\n\n"
        f"Stories:\n{numbered}\n\n"
        f"Return ONLY a JSON array of {len(stories)} strings, in the same "
        f"order, nothing else."
    )
    try:
        from engine.generator import _call_grok

        text, _meta = _call_grok(
            prompt, model=model, temperature=0.6,
            max_tokens=120 * len(stories) + 200,
        )
        data = _parse_json_array(text)
        if not data:
            raise ValueError("no JSON array in scene-brief response")
        briefs: List[str] = []
        for i, item in enumerate(data[:len(stories)]):
            t = _clean_brief(item if isinstance(item, str) else "")
            if _brief_ok(t):
                briefs.append(t)
            elif i < len(fallback):
                briefs.append(fallback[i])   # per-slot fallback keeps order
        # Pad with deterministic briefs if the model returned fewer.
        while len(briefs) < len(stories) and len(briefs) < len(fallback):
            briefs.append(fallback[len(briefs)])
        if len(briefs) < max(2, len(stories) // 2):
            raise ValueError("too few usable briefs")
        logger.info("scene briefs: %d model-written for %s", len(briefs),
                    show_name or "show")
        return briefs
    except Exception as exc:  # noqa: BLE001 — briefs are best-effort
        logger.warning("scene briefs: model path failed (%s) — "
                       "deterministic fallback (%d)", exc, len(fallback))
        return fallback
