"""Grok Imagine API wrapper for the YouTube long-form / Shorts pipeline.

Sibling to :mod:`engine.visual_assets` (the Pexels path). Operator-driven
opt-in via each show's ``youtube.image_provider`` config knob:

  ``pexels``  — existing free Pexels search (default)
  ``grok``    — generate fresh images per episode for long-form AND
                Shorts via Grok Imagine, prompted from the day's hook
  ``hybrid``  — Pexels for long-form, Grok for Shorts (cheaper test)

Pricing (verified May 2026, see CLAUDE.md landmine on this rollout):

  ``grok-imagine-image``       $0.02 / image  (300 req/min)
  ``grok-imagine-image-pro``   $0.07 / image  ( 30 req/min)

At 8 images per format × 2 formats × ~52 episodes/month for Tesla + MAB
(the only YouTube-enabled shows) the standard model lands at ~$17/mo.

Endpoint: ``POST https://api.x.ai/v1/images/generations`` — OpenAI-
compatible request shape. Reuses the existing ``GROK_API_KEY`` /
``XAI_API_KEY`` env var (no new auth surface).

Failure mode: best-effort. If the API call fails, the run-show pipeline
falls back to the show cover as a single scene — same graceful
behaviour as the Pexels path. The exception is logged and surfaced in
metrics.
"""

from __future__ import annotations

import base64
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Re-export Scene / SceneSet so the runner can hold a single result type
# regardless of which provider returned it.
from engine.visual_assets import Scene, SceneSet  # noqa: F401

logger = logging.getLogger(__name__)


GROK_IMAGINE_ENDPOINT = "https://api.x.ai/v1/images/generations"
DEFAULT_MODEL = "grok-imagine-image"
DEFAULT_TIMEOUT_S = 60

# Per-image USD cost. Keep in sync with the model identifier in
# ``MODEL_COST_USD`` so cost tracking stays accurate when the operator
# flips between standard and pro.
MODEL_COST_USD = {
    "grok-imagine-image": 0.02,
    "grok-imagine-image-pro": 0.07,
    # Aliases the operator might type in YAML.
    "grok-imagine-standard": 0.02,
    "grok-imagine-pro": 0.07,
}


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

# Headline-extractor regexes — one per markdown shape used across the
# network. Order matters: blockquote hooks first (they're the lead),
# then numbered list items, then numbered H3 sections.
_HEADLINE_PATTERNS = (
    # Tesla / FF / PT lead hook: ``> **Hook line.**``
    re.compile(r"^>\s*\*\*([^*\n]+)\*\*", re.MULTILINE),
    # Tesla / FF Top-N + X-Takeover items: ``1. **Headline**: ...``
    # also matches ``1. **Headline** - ...``.
    re.compile(r"^\s*\d+\.\s+\*\*([^*\n]+)\*\*", re.MULTILINE),
    # Omni View top stories: ``### 1) Headline`` / ``### 1. Headline``
    re.compile(r"^###\s+\d+[.)]\s+(.+?)\s*$", re.MULTILINE),
    # MAB / M&A item heads: ``**[Title]: source**``
    re.compile(r"\*\*\[([^\]\n]+)\]"),
)


def extract_story_headlines(digest_text: str, max_count: int = 12) -> List[str]:
    """Pull per-story headlines out of an episode digest's markdown.

    Operator caught (Tesla YouTube long-form + Shorts, May 7 2026) every
    Grok-generated slide rendering the same headline as a text banner —
    because :func:`build_image_prompts` repeated the episode's lead hook
    in every prompt. Real episodes have 5–11 distinct stories; using each
    one as its own per-image context makes the slideshow visually
    diverse (and, paired with an explicit "no text" instruction, removes
    the duplicated banner).

    Recognises the markdown shapes used across the network:

      * Tesla / FF / PT lead-hook blockquote (``> **...**``)
      * Numbered bold list items (``1. **Headline**: ...``)
      * Numbered H3 sections (``### 1) Headline``)
      * MAB bracketed item titles (``**[Title]: source**``)

    Returns up to *max_count* distinct headlines in document order. Empty
    list if nothing matches — caller falls back to hook-only behaviour.
    """
    if not digest_text:
        return []

    headlines: List[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> bool:
        h = raw.strip().rstrip(":.,;").strip()
        # Drop obvious junk: too short, too long, or already seen
        # (case-insensitive — same story sometimes appears in two
        # sections with slight casing changes).
        key = h.lower()
        if 8 <= len(h) <= 200 and key not in seen:
            seen.add(key)
            headlines.append(h)
        return len(headlines) >= max_count

    for pattern in _HEADLINE_PATTERNS:
        for match in pattern.finditer(digest_text):
            if _add(match.group(1)):
                return headlines

    return headlines


def build_image_prompts(
    *,
    hook: str,
    image_queries: List[str],
    aspect: str = "16:9",
    count: int = 8,
    show_descriptor: str = "",
    per_scene_contexts: Optional[List[str]] = None,
) -> List[str]:
    """Build *count* image prompts that combine each query with a context.

    Image queries are the show's curated phrases (Tesla → "tesla
    factory", "tesla cybertruck on highway", etc.).

    *per_scene_contexts* (NEW, May 2026): when provided, each prompt
    uses its own per-scene context cycled from the list, so the
    slideshow shows a different story per slide instead of every slide
    repeating the episode's lead hook. ``run_show.py`` passes the output
    of :func:`extract_story_headlines` here. Falls back to *hook* for
    every prompt when *per_scene_contexts* is empty / None.

    Aspect is encoded in the prompt as a hint; Grok Imagine's actual
    output dimensions depend on the ``size`` parameter sent at the API
    layer, but including ``vertical 9:16 framing`` in the prompt
    nudges composition. ``show_descriptor`` is an optional one-liner
    (e.g. "high-energy news photo") that the show's prompt template
    may want to inject for tone consistency.
    """
    if not image_queries:
        return []

    is_vertical = aspect.startswith("9:") or aspect == "vertical"
    framing_hint = (
        "vertical 9:16 framing, single subject, mobile-first composition"
        if is_vertical
        else "wide cinematic 16:9 framing, photojournalism style"
    )
    # Operator caught: Grok Imagine renders any free-text "context" hint
    # as a banner / on-image text overlay. Telling it explicitly to
    # produce a clean image stops the headline appearing as a chyron
    # across every slide. This is a soft signal — Grok still occasionally
    # emits text, but compliance is dramatically better with the cue.
    no_text_hint = "clean photographic composition, no text or words rendered in the image"

    safe_hook = (hook or "").strip().rstrip(".")
    descriptor = (show_descriptor or "photorealistic news photo").strip()

    # Normalise per-scene contexts. Drop empties. If empty/missing, every
    # prompt uses the lone hook (legacy behaviour).
    contexts: List[str] = [
        c.strip().rstrip(".")
        for c in (per_scene_contexts or [])
        if c and c.strip()
    ]

    def _context_for(i: int) -> str:
        if contexts:
            return contexts[i % len(contexts)]
        return safe_hook

    prompts: List[str] = []

    # First pass: one image per query, up to count.
    for i, raw_query in enumerate(image_queries):
        if i >= count:
            break
        q = (raw_query or "").strip()
        if not q:
            continue
        parts = [q, descriptor, framing_hint, no_text_hint]
        ctx = _context_for(len(prompts))
        if ctx:
            parts.append(f"depicting: {ctx}")
        prompts.append(", ".join(parts))

    # Second pass: cycle queries until we hit count. Per-scene contexts
    # keep advancing through the headline list, so recycled queries still
    # produce different images.
    while 0 < len(prompts) < count:
        idx = len(prompts) % len(image_queries)
        q = (image_queries[idx] or "").strip()
        if not q:
            break
        parts = [q, descriptor, framing_hint, no_text_hint, f"variant {len(prompts) + 1}"]
        ctx = _context_for(len(prompts))
        if ctx:
            parts.append(f"depicting: {ctx}")
        prompts.append(", ".join(parts))

    return prompts


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------


class GrokImagineError(RuntimeError):
    """Raised on a non-recoverable Grok Imagine API failure."""


def _api_size_for_aspect(aspect: str) -> str:
    """Translate a human aspect string to the API's ``size`` parameter.

    xAI's ``/v1/images/generations`` expects an ``WIDTHxHEIGHT`` string
    similar to OpenAI's image API. The endpoint supports up to 2K
    resolution; we keep things modest at 1024×x for cost and speed
    (the YouTube slideshow downscales these anyway). Vertical Shorts
    use a portrait size matched to YouTube Shorts' 1080×1920 guidance.
    """
    if aspect.startswith("9:") or aspect == "vertical":
        return "1024x1792"
    if aspect == "1:1":
        return "1024x1024"
    return "1792x1024"


def _post_image_request(
    payload: dict,
    api_key: str,
    timeout_s: int,
) -> requests.Response:
    """One-shot POST. Caller decides whether to retry / fall back."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(
        GROK_IMAGINE_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=timeout_s,
    )


@retry(
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _request_one_image(
    prompt: str,
    *,
    api_key: str,
    model: str,
    size: str,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> bytes:
    """POST a single prompt to ``/v1/images/generations`` and return
    the raw image bytes. Wrapped in tenacity retry for transient
    network errors. Caller is responsible for swallowing
    ``GrokImagineError`` if it wants to fall back to a different
    provider.

    Resilient against the two most common 400-class request-format
    issues with xAI's image endpoint:

      - ``size`` parameter not accepted (some xAI image revisions only
        return a fixed 1024×1024 — when the first call fails with
        ``invalid request`` and ``size`` in the message, we retry
        without ``size``).
      - ``response_format`` not accepted (some endpoints only return
        URLs, not base64 — when the first call returns ``url`` data
        instead of ``b64_json`` we follow the URL and download).
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
        "response_format": "b64_json",
    }
    resp = _post_image_request(payload, api_key, timeout_s)

    # Retry without ``size`` if the API rejected it. Cover the two
    # plausible error shapes — error.message or top-level message.
    if resp.status_code == 400:
        body_text = resp.text.lower()
        if "size" in body_text or "invalid_request" in body_text:
            payload.pop("size", None)
            resp = _post_image_request(payload, api_key, timeout_s)

    if resp.status_code >= 400:
        # Surface the API error message; HTTP 4xx isn't retried by
        # tenacity (only RequestException) so a bad prompt fails fast.
        raise GrokImagineError(
            f"Grok Imagine HTTP {resp.status_code}: {resp.text[:300]}"
        )

    body = resp.json()
    try:
        first = body["data"][0]
    except (KeyError, IndexError) as exc:
        raise GrokImagineError(
            f"Grok Imagine response missing data: {body!r}"
        ) from exc

    # Prefer b64_json (single round-trip). Fall back to ``url`` if
    # the endpoint returned URLs instead — happens on some xAI
    # revisions that ignore ``response_format``.
    if "b64_json" in first and first["b64_json"]:
        return base64.b64decode(first["b64_json"])
    if "url" in first and first["url"]:
        url_resp = requests.get(first["url"], timeout=timeout_s)
        if url_resp.status_code >= 400:
            raise GrokImagineError(
                f"Grok Imagine URL fetch HTTP {url_resp.status_code}"
            )
        return url_resp.content

    raise GrokImagineError(
        f"Grok Imagine response had neither b64_json nor url: {first!r}"
    )


# ---------------------------------------------------------------------------
# Public fetch helper — mirrors visual_assets.fetch_scene_images
# ---------------------------------------------------------------------------


@dataclass
class GrokSceneResult:
    """Wraps a SceneSet plus the cost it incurred — kept separate so
    the runner can record cost into the metrics file without coupling
    it to the visual_assets layer (which has no concept of cost)."""

    scene_set: SceneSet
    cost_usd: float = 0.0
    images_generated: int = 0
    failures: List[str] = field(default_factory=list)


def fetch_scene_images_grok(
    *,
    work_dir: Path,
    episode_num: int,
    prompts: List[str],
    fallback_cover: Path,
    aspect: str = "16:9",
    label_suffix: str = "",
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None,
) -> GrokSceneResult:
    """Generate one image per prompt and persist to the per-episode
    scenes directory.

    ``label_suffix`` differentiates the cache directory between the
    long-form set and the Shorts set so they don't clobber each other:
    long-form goes to ``scenes_ep<NNN>/`` and Shorts to
    ``scenes_ep<NNN>_short/``.

    Returns a ``GrokSceneResult`` with a ``SceneSet`` (always at least
    one scene — falls back to *fallback_cover* on failure) plus the
    USD cost spent during generation. Per-image cost is taken from
    ``MODEL_COST_USD``; if the model identifier isn't recognised,
    cost is recorded as 0 and the operator should update the table.
    """
    if api_key is None:
        api_key = (
            os.getenv("GROK_API_KEY", "").strip()
            or os.getenv("XAI_API_KEY", "").strip()
        )

    out_dir = work_dir / f"scenes_ep{episode_num:03d}{label_suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not api_key:
        logger.info(
            "GROK_API_KEY/XAI_API_KEY not set — Grok Imagine path "
            "falling back to cover for ep%s%s",
            episode_num, label_suffix,
        )
        return GrokSceneResult(
            scene_set=SceneSet(
                scenes=[Scene(path=fallback_cover)],
                is_fallback=True,
            ),
        )

    if not prompts:
        logger.warning(
            "Grok Imagine called with no prompts for ep%s — falling back",
            episode_num,
        )
        return GrokSceneResult(
            scene_set=SceneSet(
                scenes=[Scene(path=fallback_cover)],
                is_fallback=True,
            ),
        )

    size = _api_size_for_aspect(aspect)
    per_image_cost = MODEL_COST_USD.get(model, 0.0)

    scenes: List[Scene] = []
    failures: List[str] = []
    images_generated = 0
    cost_usd = 0.0

    for idx, prompt in enumerate(prompts):
        out_path = out_dir / f"grok_{idx:02d}.jpeg"
        try:
            img_bytes = _request_one_image(
                prompt, api_key=api_key, model=model, size=size,
            )
            out_path.write_bytes(img_bytes)
            scenes.append(Scene(
                path=out_path,
                photographer="Grok Imagine (xAI)",
                photographer_url="https://x.ai/imagine",
            ))
            images_generated += 1
            cost_usd += per_image_cost
        except Exception as exc:
            # Best-effort: log and continue. As long as we end up with
            # at least 2 scenes the slideshow path stays useful.
            failures.append(f"prompt[{idx}]: {exc}")
            logger.warning(
                "Grok Imagine generation failed for ep%s prompt %d: %s",
                episode_num, idx, exc,
            )

    if not scenes:
        logger.warning(
            "Grok Imagine produced no images for ep%s%s — fallback to cover",
            episode_num, label_suffix,
        )
        return GrokSceneResult(
            scene_set=SceneSet(
                scenes=[Scene(path=fallback_cover)],
                is_fallback=True,
            ),
            cost_usd=round(cost_usd, 4),
            images_generated=images_generated,
            failures=failures,
        )

    logger.info(
        "Grok Imagine generated %d images for ep%s%s (cost=$%.2f)",
        images_generated, episode_num, label_suffix, cost_usd,
    )
    return GrokSceneResult(
        scene_set=SceneSet(scenes=scenes, is_fallback=False),
        cost_usd=round(cost_usd, 4),
        images_generated=images_generated,
        failures=failures,
    )
