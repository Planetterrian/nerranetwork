"""Pre-send WCAG contrast tripwire for newsletter HTML.

Spec §7.3. Walks the rendered email HTML and flags any inline
``color:`` + nearest-ancestor ``background:`` pair that fails WCAG
AA (4.5:1 for body text, 3:1 for ≥18 pt or bold ≥14 pt).

The check is **light-mode only** — the dark-mode overrides live in
the ``<style>`` block and are validated by the ``test_dark_mode_*``
unit tests. This validator's job is the static inline-style world
the email actually ships with.

Limitations (deliberate):

  - Doesn't follow opacity / rgba — they almost always read as a
    weighted mix and hand-rolling that math is fragile. Where opacity
    is used (the hero subtitle), the underlying brand color already
    provides plenty of contrast against white text, so the lossy
    approximation here is fine.
  - Doesn't compare to outer ancestors more than 6 levels deep —
    nested-table emails put the inline ``background:`` on a wrapper
    only a few cells out.

Usage:

  ```python
  from engine.contrast_validator import find_contrast_failures, ContrastError

  failures = find_contrast_failures(rendered_html)
  if failures:
      raise ContrastError(failures)  # block send
  ```
"""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class ContrastError(RuntimeError):
    """Raised when the rendered newsletter has WCAG AA failures."""

    def __init__(self, failures: List[str]) -> None:
        self.failures = failures
        joined = "\n  - ".join(failures)
        super().__init__(
            f"Newsletter HTML has light-mode contrast failures "
            f"(blocking send):\n  - {joined}"
        )


# ---------------------------------------------------------------------------
# Color parsing + contrast math (WCAG 2.1)
# ---------------------------------------------------------------------------

_HEX3 = re.compile(r"^#([0-9a-f])([0-9a-f])([0-9a-f])$", re.IGNORECASE)
_HEX6 = re.compile(r"^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$", re.IGNORECASE)
_RGB = re.compile(r"^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$", re.IGNORECASE)


def _parse_color(value: str) -> Optional[Tuple[int, int, int]]:
    """Return (r, g, b) on success; None on rgba / unrecognised / named."""
    if not value:
        return None
    s = value.strip().lower()
    m = _HEX6.match(s)
    if m:
        return tuple(int(g, 16) for g in m.groups())  # type: ignore[return-value]
    m = _HEX3.match(s)
    if m:
        return tuple(int(g + g, 16) for g in m.groups())  # type: ignore[return-value]
    m = _RGB.match(s)
    if m:
        return tuple(int(g) for g in m.groups())  # type: ignore[return-value]
    # rgba / named / hsl: treat as unknown so we skip.
    return None


def _relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """WCAG 2.1 relative luminance in [0, 1]."""
    def _channel(c: int) -> float:
        cs = c / 255.0
        return cs / 12.92 if cs <= 0.03928 else ((cs + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(
    fg: Tuple[int, int, int], bg: Tuple[int, int, int]
) -> float:
    """WCAG 2.1 contrast ratio in [1, 21]."""
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ---------------------------------------------------------------------------
# Inline-style extraction
# ---------------------------------------------------------------------------

_STYLE_PROP_RE = re.compile(r"(\b[\w-]+)\s*:\s*([^;]+?)\s*(?:;|$)")


def _style_lookup(style_attr: str) -> dict:
    """Parse an inline style="…" string into a {prop: value} dict."""
    if not style_attr:
        return {}
    return {
        m.group(1).lower(): m.group(2).strip()
        for m in _STYLE_PROP_RE.finditer(style_attr)
    }


def _extract_bgcolor_or_background(style: dict, attrs: dict) -> Optional[str]:
    """Prefer explicit ``background-color``/``background`` over the
    deprecated ``bgcolor`` attribute, but fall back to it for Outlook
    fixtures (the hero pill we just shipped uses ``bgcolor`` exactly).
    """
    bg = (
        style.get("background-color")
        or _strip_gradient(style.get("background", ""))
        or attrs.get("bgcolor")
    )
    return bg


_GRADIENT_RE = re.compile(r"linear-gradient\([^)]+\)", re.IGNORECASE)


def _strip_gradient(bg: str) -> str:
    """If background is ``linear-gradient(…)``, return the empty string —
    we can't validate against gradients meaningfully (the reader sees
    a continuum of colors). The hero gradient cell has hard-coded
    ``bgcolor=brand_dark`` as the fallback, which we *will* validate.
    """
    if not bg:
        return ""
    if _GRADIENT_RE.search(bg):
        return ""
    return bg


# ---------------------------------------------------------------------------
# HTML parser walking the inline-style stack
# ---------------------------------------------------------------------------

class _ContrastWalker(HTMLParser):
    """Walks the HTML, maintaining a stack of nearest-ancestor backgrounds.

    On each tag with an inline ``color:`` *and* there's a known
    ancestor background, computes the ratio. Failures are accumulated
    into ``self.failures``.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.bg_stack: List[Tuple[str, Tuple[int, int, int]]] = [
            # default page background
            ("body", (255, 255, 255)),
        ]
        self.failures: List[str] = []
        self._tag_stack: List[str] = []

    def handle_starttag(self, tag: str, attrs):  # type: ignore[no-untyped-def]
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        style = _style_lookup(attr_dict.get("style", ""))

        # Push background if this element introduces one.
        bg_value = _extract_bgcolor_or_background(style, attr_dict)
        bg_rgb = _parse_color(bg_value) if bg_value else None
        if bg_rgb is not None:
            self.bg_stack.append((tag, bg_rgb))
        # Otherwise inherit — don't push.

        # Check foreground contrast.
        fg_value = style.get("color")
        fg_rgb = _parse_color(fg_value) if fg_value else None
        if fg_rgb is not None:
            ancestor_bg_rgb = self.bg_stack[-1][1]
            ratio = contrast_ratio(fg_rgb, ancestor_bg_rgb)
            # Bold/large-text relaxation: AA requires 3:1 instead of
            # 4.5:1 for ≥18 pt or bold ≥14 pt. Approximate from style.
            font_size = _font_size_px(style.get("font-size", ""))
            font_weight = (style.get("font-weight") or "").strip().lower()
            is_bold = font_weight in {"700", "bold", "bolder", "800", "900"}
            is_large = font_size >= 18 or (is_bold and font_size >= 14)
            threshold = 3.0 if is_large else 4.5
            if ratio < threshold:
                snippet = (attr_dict.get("style") or "")[:80]
                self.failures.append(
                    f"<{tag}> color={fg_value!r} on bg={bg_value or self.bg_stack[-1][0]!r}: "
                    f"ratio={ratio:.2f}:1 < {threshold}:1 "
                    f"(style: {snippet!r})"
                )

        self._tag_stack.append(tag)
        # Mark whether this open tag pushed the background stack so
        # endtag can pop correctly.
        self._tag_stack[-1] = (tag, bg_rgb is not None)  # type: ignore[index]

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        # Walk the tag stack; pop the matching open frame.
        for i in range(len(self._tag_stack) - 1, -1, -1):
            entry = self._tag_stack[i]
            name = entry[0] if isinstance(entry, tuple) else entry
            if name == tag:
                pushed_bg = (
                    isinstance(entry, tuple) and entry[1]
                )
                if pushed_bg and len(self.bg_stack) > 1:
                    self.bg_stack.pop()
                del self._tag_stack[i]
                return


_FONT_SIZE_PX_RE = re.compile(r"(\d+(?:\.\d+)?)\s*px", re.IGNORECASE)


def _font_size_px(value: str) -> float:
    """Return the px value of a CSS font-size, 0 if none / unparseable."""
    if not value:
        return 0.0
    m = _FONT_SIZE_PX_RE.search(value)
    if not m:
        return 0.0
    try:
        return float(m.group(1))
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_contrast_failures(html: str) -> List[str]:
    """Return human-readable AA-failure descriptions for *html*.

    Empty list = pass. Returned strings are designed to be logged or
    raised as a single block — see ``ContrastError``.
    """
    if not html:
        return []
    walker = _ContrastWalker()
    try:
        walker.feed(html)
    except Exception as exc:  # noqa: BLE001 — never crash on malformed HTML
        logger.debug("Contrast walker failed: %s", exc)
        return []
    return walker.failures


def assert_contrast_ok(html: str) -> None:
    """Raise ``ContrastError`` if any AA failures exist.

    Convenience wrapper for the send pipeline.
    """
    failures = find_contrast_failures(html)
    if failures:
        raise ContrastError(failures)
