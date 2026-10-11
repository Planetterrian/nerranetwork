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


def _brief_tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2}


def dedupe_briefs(briefs: Sequence[str], *, threshold: float = 0.8) -> List[str]:
    """Drop a brief that repeats an earlier one (exact, or >= *threshold*
    token overlap of the shorter brief).

    Oct 11 2026: Omni View Ep202 rendered "Collapsed concrete apartment
    blocks…" twice per aspect and Tesla Ep631 three near-identical rows of
    humanoid robots — two stories about one event become two copies of one
    picture. Order is kept; the first telling wins.
    """
    out: List[str] = []
    kept: List[set] = []
    for raw in briefs or []:
        t = (raw or "").strip()
        if not t:
            continue
        toks = _brief_tokens(t)
        dup = False
        for k in kept:
            small = min(len(toks), len(k)) or 1
            if toks == k or len(toks & k) / small >= threshold:
                dup = True
                break
        if not dup:
            out.append(t)
            kept.append(toks)
    return out


_SECTION_RE = re.compile(r"^#{2,3}\s+(.+?)\s*$")
_SKIP_SECTIONS = re.compile(
    r"\b(closing|teaser|sources?|what you need to know|wyntk|before we go|"
    r"quick hits|also today|on the (horizon|calendar)|the tape|market watch|"
    r"portfolio|week in review|listener)\b", re.I)


def essay_section_leads(digest_text: str, *, max_n: int = 4) -> List[str]:
    """First prose sentence of each essay-shaped digest section.

    Story headlines come only from numbered items, so a digest carrying two
    items and three essays (SpaceX Ep127: Engineering Deep Dive, AI &
    Compute, Community Buzz) produced two briefs and the image set was
    padded with static keywords. A section whose body opens on prose — not
    a numbered or bulleted list — contributes its first sentence.
    """
    leads: List[str] = []
    lines = (digest_text or "").splitlines()
    i = 0
    while i < len(lines) and len(leads) < max_n:
        m = _SECTION_RE.match(lines[i].strip())
        i += 1
        if not m or _SKIP_SECTIONS.search(m.group(1)):
            continue
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines):
            break
        body = lines[i].strip()
        if (not body or body.startswith(("#", "-", "*", ">", "|"))
                or re.match(r"^\d+[.)]\s", body)):
            continue
        body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)
        body = re.sub(r"[*_`]", "", body)
        first = re.split(r"(?<=[.!?])\s", body, maxsplit=1)[0].strip()
        if 6 <= len(first.split()) <= 40:
            leads.append(first)
    return leads


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


def _style_feedback_line(feedback: Optional[dict]) -> str:
    """One sentence, or "" — what has held this show's viewers.

    Shape only: the phrases are the report's own mined style tags, so
    the line carries no quotable specimen scene.
    """
    if not isinstance(feedback, dict):
        return ""
    fav = [str(t).strip() for t in (feedback.get("favoured") or []) if str(t).strip()][:2]
    avo = [str(t).strip() for t in (feedback.get("avoided") or []) if str(t).strip()][:2]
    if not fav and not avo:
        return ""
    parts = []
    if fav:
        parts.append(f"scenes with {' and '.join(fav)} have held this show's viewers")
    if avo:
        parts.append(f"scenes with {' and '.join(avo)} have not")
    return " Audience note: " + "; ".join(parts) + "."


def generate_scene_briefs(
    headlines: Sequence[str],
    *,
    hook: str = "",
    show_name: str = "",
    show_descriptor: str = "",
    max_n: int = 8,
    model: str = "grok-4.3",
    enabled: bool = True,
    style_feedback: Optional[dict] = None,
    tracker: Optional[dict] = None,
) -> List[str]:
    """One concrete visual scene brief per story, in story order.

    *tracker* (Oct 2 2026): the episode's credit tracker; when given, the
    one Grok call is recorded as the ``scene_briefs`` step. ``None`` is
    byte-identical to the pre-pass behaviour (the call ran unrecorded).

    Falls back to :func:`deterministic_briefs` on any failure, refusal,
    malformed output, or when *enabled* is False. Returns at most
    *max_n* briefs; ``[]`` only when there are no usable headlines at
    all (caller then keeps the legacy image_queries prompts).

    ``style_feedback`` (Sep 22 2026 — ``engine.gallery_library.
    style_feedback_for``): ``{"favoured": [...], "avoided": [...]}``
    renders ONE audience-note sentence into the prompt; ``None`` (the
    default, and any empty feedback) leaves the prompt byte-identical.
    """
    stories = [str(h).strip() for h in (headlines or []) if str(h).strip()]
    if hook and hook.strip() and hook.strip() not in stories:
        stories = [hook.strip()] + stories
    stories = stories[:max(1, min(int(max_n), _MAX_BRIEFS))]
    if not stories:
        return []
    fallback = deterministic_briefs(stories, max_n=len(stories))
    if not enabled:
        return dedupe_briefs(fallback)

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
        f"subject matter faithful to the story's actual topic."
        f"{_style_feedback_line(style_feedback)}\n\n"
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
        # Record BEFORE parsing: a response the parser rejects was billed.
        from engine.tracking import record_llm_usage_from_meta
        record_llm_usage_from_meta(tracker, "scene_briefs", _meta)
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
        briefs = dedupe_briefs(briefs)
        logger.info("scene briefs: %d model-written for %s", len(briefs),
                    show_name or "show")
        return briefs
    except Exception as exc:  # noqa: BLE001 — briefs are best-effort
        logger.warning("scene briefs: model path failed (%s) — "
                       "deterministic fallback (%d)", exc, len(fallback))
        return dedupe_briefs(fallback)
