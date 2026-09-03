"""Video assembly helpers for the YouTube publishing pipeline.

Two builders share one visual recipe so every show looks like part
of the same network without per-show artwork:

  - **Background**: either the show cover (single Ken Burns image) or
    a pre-rendered slideshow MP4 of Pexels photos cycling every ~12 s
    (long-form) / ~7 s (Shorts). Slideshow uses
    :mod:`engine.visual_assets`; without ``PEXELS_API_KEY`` we
    silently fall back to the static cover.
  - **Brand pill**: ``Nerra Network`` PNG (rendered once with
    Pillow). Top-left long-form, top-right Shorts. AI-narration
    disclosure stays in the description footer + the
    ``containsSyntheticMedia`` API flag — no on-screen reminder.
  - **First-seconds burn-in**: long-form fades in/out a centered
    AI-disclosure line for the first 4 s. Shorts (with a hook) burn
    the headline for the first 3 s.
  - **Captions** (long-form only): when a transcript SRT is supplied,
    ffmpeg's ``subtitles`` filter burns synchronized captions near
    the bottom edge with a semi-transparent backdrop for legibility.

Earlier revisions overlaid a ``showcqt`` audio spectrum band on both
formats. For speech-heavy podcasts the spectrum read as multicolour
static and dominated the visual; it was removed in favour of letting
the slideshow + Ken Burns + captions carry the visual interest.

The encoder profile uses ``-g 60 -keyint_min 60 -sc_threshold 0
-force_key_frames`` to force a keyframe every 2 s; without this,
x264 produced a single IDR at t=0 and YouTube's transcoder rejected
the rendition with "video can't play".
"""

from __future__ import annotations

import json
import logging
import math
import os
import subprocess
import zlib
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# Visual-era counter (July 31 2026 render pass). Bumped whenever the
# shipped look changes materially (grade chain, KB vocabulary, caption
# treatment, hook titles) so analytics can segment retention by visual
# era. Recorded as the ``render_look_version`` metric alongside
# ``visual_mode`` in run_show.
RENDER_LOOK_VERSION = 2


def _run_ffmpeg(cmd: List[str], *, label: str) -> None:
    """Run ffmpeg and attach stderr to the raised error for CI debugging."""
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        if len(stderr) > 2000:
            stderr = stderr[-2000:]
        raise RuntimeError(
            f"{label} failed (exit {exc.returncode}): {stderr or '(no stderr)'}"
        ) from exc


# ---------------------------------------------------------------------------
# Encoding profile
# ---------------------------------------------------------------------------

_VIDEO_ENCODE: List[str] = [
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-preset", "medium",
    "-crf", "22",
    "-profile:v", "high",
    "-level", "4.1",
    "-g", "60",
    "-keyint_min", "60",
    "-sc_threshold", "0",
    "-force_key_frames", "expr:gte(t,n_forced*2)",
    # Ceiling, not a target. Measured episodes land around 2.0 Mbps
    # total, so this never binds in normal operation — it exists so a
    # pathological scene (heavy grain, a near-noise still) cannot
    # produce a 600 MB enclosure that Apple times out fetching. CRF
    # remains the quality control.
    "-maxrate", "4M",
    "-bufsize", "8M",
]

# Fast profile for the STAGE-1 slideshow, which is an *intermediate* file —
# stage 2 (the composite) re-encodes it with the full _VIDEO_ENCODE profile, so
# stage-1 quality barely reaches the final pixels. Using a fast preset here cut
# the slideshow render from ~10 min toward ~2-3 min on Tesla/SpaceX, which is
# the main reason those clip-era runs crept toward the 40-min pipeline timeout.
# No keyframe args needed (it's not the delivered file). June 2026 render pass.
#
# July 2026: CRF 20 -> 16. Every delivered pixel goes through two lossy
# encodes — CRF 20 here, then CRF 22 in the composite — and the errors
# compound. CRF 16 is close enough to transparent that stage 2 becomes
# effectively the only quality-determining pass, which is what the
# ``-crf 22`` above is tuned for. The intermediate is deleted minutes
# later, so the only cost is scratch disk and a little encode time; the
# preset stays ``veryfast`` precisely because that is where the render
# minutes are, not in the CRF.
_VIDEO_ENCODE_FAST: List[str] = [
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-preset", "veryfast",
    "-crf", "16",
]

_AUDIO_ENCODE: List[str] = [
    "-c:a", "aac",
    "-b:a", "192k",
    "-ar", "44100",
    "-ac", "2",
]


# ---------------------------------------------------------------------------
# Font + drawtext helpers
# ---------------------------------------------------------------------------

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)


def _find_font() -> str:
    """Return the path of an installed bold sans-serif font."""
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return _FONT_CANDIDATES[0]


def _drawtext_escape(value: str) -> str:
    """Escape a string for ffmpeg ``drawtext text=`` value.

    The text= value gets embedded inside a single-quoted region of
    a ``-filter_complex`` graph. ffmpeg's filter_complex parser:

      * Treats ``\\`` as a literal backslash.
      * **Inside a single-quoted region, backslash is LITERAL** —
        not an escape character. So ``\\'`` inside ``'...'`` is read
        as ``\\`` (literal backslash) followed by ``'`` which CLOSES
        the quoted region.
      * **Terminates the quoted region on a literal line feed** —
        which means a real newline character in our wrapped Shorts
        caption truncates the text= value mid-string and the rest of
        the filter graph parses as garbage.

    Operator caught two breakages from this:

      * Tesla Ep466 (May 8 2026): wrapped 4-line hook contained real
        ``\\n`` newlines inside ``text='...'``. ffmpeg saw the first
        newline, closed the quoted region, choked on the rest. Fixed
        by escaping real newlines to literal ``\\n`` (drawtext's
        post-parse text-expansion recognises ``\\n`` as a line break).
      * Tesla Ep469 (May 11 2026): wrapped hook "Tesla's
        zero-intervention…" contained ``'`` inside ``text='...'``.
        The ``\\'`` escape WAS being applied but inside a quoted
        region ``\\`` is literal, so ffmpeg saw ``\\`` + ``'`` and
        the apostrophe terminated the quote — same failure as the
        newline case.

    Fix for apostrophes: replace straight ``'`` with the typographic
    apostrophe ``’`` (U+2019). It's not a quote character to
    ffmpeg's parser so no escaping is needed AND it renders more
    professionally as burned-in caption text. The TTS path is
    unaffected because it uses different escaping for the spoken
    script.

    Order matters: escape backslashes FIRST so the new escapes don't
    get re-escaped on the way out.
    """
    return (
        value.replace("\\", "\\\\")
             .replace(":", r"\:")
             .replace("'", "’")        # straight apostrophe → curly (U+2019)
             .replace("%", r"\%")
             .replace("\n", r"\n")
    )


def _subtitles_path_escape(p: str) -> str:
    """Escape a path for use inside the ffmpeg ``subtitles`` filter.

    ``subtitles`` uses ``:`` as its option separator, so any colons
    in the path (notably the C: drive on Windows or any odd Linux
    paths) need backslash escaping. Single quotes are wrapped at the
    surrounding ``'…'`` so we escape those too.
    """
    return (
        p.replace("\\", "/")
         .replace(":", r"\:")
         .replace("'", r"\'")
    )


def _wrap_caption(text: str, max_chars_per_line: int = 26,
                  max_lines: int = 4) -> str:
    """Greedy word-wrap for a Shorts caption, capped at *max_lines*.

    May 8 2026: bumped defaults from ``22 × 3`` (66-char budget) to
    ``26 × 4`` (104-char budget). Operator caught Tesla Ep466's
    91-char hook ("California regulators just disclosed the Tesla
    Semi's battery sizes at 822 kWh and 548 kWh.") truncating to
    "...batter…" mid-word. The 9:16 1920-pixel vertical Shorts
    canvas has plenty of room for 4 lines at 64 px (≈ 304 px stack);
    ``y=240`` start position still leaves the brand pill above and
    plenty of clear space below."""
    if not text:
        return ""
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars_per_line or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) >= max_lines and len(" ".join(lines).split()) < len(words):
        last = lines[-1]
        if not last.endswith("..."):
            lines[-1] = (last[: max_chars_per_line - 3].rstrip() + "...") \
                if len(last) > max_chars_per_line - 3 else last + "..."
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Auto-fit hook overlay
# ---------------------------------------------------------------------------
#
# The 0–3 s hook overlay on a Shorts MP4 used to render at a fixed
# fontsize=44 with a char-based word wrap (26 chars × 4 lines). Tesla
# hooks > ~104 chars truncated with "..." at the end of line 4 —
# operator caught this on Ep466 ("California regulators just
# disclosed the Tesla Semi's battery sizes at 822 kWh and 548 kWh.").
#
# This helper applies the same shrink-to-fit pattern the thumbnail
# renderer uses (engine.publisher.generate_episode_thumbnail). The
# default size stays at 44 — preserving the May 2026 operator
# preference for a non-dominant hook — and only shrinks when keeping
# 44 would truncate. Pixel-based wrap via PIL ImageFont gives an
# accurate fit on the actual frame width (1080 px on Shorts) instead
# of the conservative char-budget approximation.


def _pixel_wrap_lines(
    text: str, font, max_width: int, max_lines: int,
) -> tuple[list[str], bool]:
    """Greedy word-wrap by rendered pixel width.

    Returns ``(lines, fits)``. ``fits`` is True when every word in
    ``text`` made it into the returned lines (no truncation).
    """
    words = text.split()
    if not words:
        return [], True
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = (" ".join(current + [word])) if current else word
        try:
            bbox = font.getbbox(candidate)
            line_px = bbox[2] - bbox[0]
        except Exception:  # pragma: no cover — font getbbox edge case
            line_px = len(candidate) * (font.size // 2)
        if line_px <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    used = " ".join(lines).split()
    fits = len(used) == len(words)
    return lines, fits


def autofit_hook_overlay(
    hook: str,
    *,
    frame_width: int = 1080,
    safe_margin: int = 80,
    max_lines: int = 4,
    font_path: Optional[str] = None,
    candidates: tuple[int, ...] = (44, 40, 36, 32),
) -> tuple[int, str]:
    """Pick the largest font size from ``candidates`` where ``hook``
    fits inside ``frame_width - 2*safe_margin`` and ``max_lines``.

    Returns ``(fontsize, wrapped_text)``. ``wrapped_text`` joins
    lines with ``\\n`` — the format ``_drawtext_escape`` understands
    and the existing caller uses unchanged.

    The candidate list starts at the legacy default 44 so the
    common case (typical-length hooks) preserves the existing
    visual exactly. Only hooks that would truncate at 44 drop to
    40, then 36, then 32 — each step a meaningful enough size
    change that the operator can tell at a glance which path the
    auto-fit took.

    Falls back to the char-based ``_wrap_caption`` (with a leading
    fontsize of 44) when Pillow isn't available — the
    pre-Phase-1 behaviour, defensive against an unexpected import
    environment.
    """
    if not hook:
        return candidates[0], ""
    try:
        from PIL import ImageFont
    except ImportError:  # pragma: no cover — PIL is a hard dep
        return candidates[0], _wrap_caption(hook)
    if font_path is None:
        font_path = _find_font()
    max_width = frame_width - 2 * safe_margin
    last_lines: list[str] = []
    last_size = candidates[-1]
    for size in candidates:
        try:
            font = ImageFont.truetype(font_path, size)
        except (OSError, IOError):  # pragma: no cover — font missing
            return size, _wrap_caption(hook)
        lines, fits = _pixel_wrap_lines(hook, font, max_width, max_lines)
        if fits:
            return size, "\n".join(lines)
        last_lines = lines
        last_size = size
    # Floor: ship at the smallest size even if it truncates.
    # Append an explicit ellipsis on the last line so the truncation
    # is visible to the viewer rather than feeling like a cut-off bug.
    if last_lines and not last_lines[-1].endswith("..."):
        last_lines[-1] = last_lines[-1].rstrip(",.; ") + "..."
    return last_size, "\n".join(last_lines)


# ---------------------------------------------------------------------------
# Brand pill PNGs
# ---------------------------------------------------------------------------
#
# Operator (May 8 2026) asked for branded corner overlays on YouTube
# videos: the show name + logo in one corner, ``nerranetwork.com`` in
# another, so listeners always know what they're watching and where
# to find it. The legacy ``_make_brand_pill`` rendered a single
# "Nerra Network" pill with no per-show identity.
#
# New shape: ``_make_brand_pill(output_path, text=...)`` accepts any
# text, so callers can render either a per-show pill (e.g.
# ``Tesla Shorts Time``) or the canonical ``nerranetwork.com`` pill.
# The default text stays "Nerra Network" so existing call sites keep
# working unchanged.

_BRAND_PILL_TEXT = "Nerra Network"
_NETWORK_URL_PILL_TEXT = "nerranetwork.com"


# Nerra cyan (#00D4FF) — the caption-highlight accent colour, reused
# as a 2 px left-edge accent inside the pill for brand cohesion.
_PILL_ACCENT_RGBA = (0, 212, 255, 235)
# Width of the visible accent strip at DELIVERY size (px). Rendered at
# 2x supersample, so the internal clip is twice this.
_PILL_ACCENT_WIDTH = 6


def _make_brand_pill(output_path: Path,
                     *, text: str = _BRAND_PILL_TEXT,
                     width: int = 220, height: int = 60) -> Path:
    """Render a rounded-rect brand pill as an RGBA PNG. Idempotent.

    *text* is the displayed string. Width auto-fits via font shrink
    (font tries 30 → 12 px until the text fits with a 32 px side
    margin). Show names up to ~30 chars fit comfortably at the
    default 220 × 60; longer names get the smaller font, still
    legible against the cover background.

    July 31 2026 (B5): rendered at 2x and LANCZOS-downscaled for
    supersampled text edges, plus a 2 px Nerra-cyan left-edge accent
    inside the rounded rect. The cache is path-keyed, so the version
    lives in the FILENAMES the builders use (``_show_pill_v2_*`` /
    ``_url_pill_v2`` / ``_brand_pill_v3``) — a persistent work dir
    regenerates rather than reusing a stale 1x pill.
    """
    if output_path.exists():
        return output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    from PIL import Image, ImageDraw, ImageFont

    # 2x supersample: every geometry/font value below is doubled, then
    # the finished pill is LANCZOS-downscaled to the requested size.
    w2, h2 = width * 2, height * 2
    img = Image.new("RGBA", (w2, h2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = h2 // 2
    draw.rounded_rectangle(
        [(0, 0), (w2 - 1, h2 - 1)],
        radius=radius,
        fill=(0, 0, 0, 140),
    )

    # Cyan left-edge accent: a rounded rect with the same geometry,
    # clipped to the leftmost strip so only the leading edge shows.
    accent = Image.new("RGBA", (w2, h2), (0, 0, 0, 0))
    ImageDraw.Draw(accent).rounded_rectangle(
        [(0, 0), (w2 - 1, h2 - 1)],
        radius=radius,
        fill=_PILL_ACCENT_RGBA,
    )
    accent_strip = accent.crop((0, 0, _PILL_ACCENT_WIDTH * 2, h2))
    img.alpha_composite(accent_strip, (0, 0))

    font_path = _find_font()
    font = None
    # Wider top range than legacy (was 22 → 12) to accommodate longer
    # show names that previously got clamped to the smallest font even
    # when more horizontal room was available. Doubled for the 2x
    # canvas (56 → 24 ≙ 28 → 12 at delivery size), stepping by 2 so
    # the delivery-size ladder is unchanged.
    for size in range(56, 23, -2):
        try:
            candidate = ImageFont.truetype(font_path, size)
        except (IOError, OSError):
            continue
        bbox = candidate.getbbox(text)
        if bbox[2] - bbox[0] <= w2 - 64:
            font = candidate
            break
    if font is None:
        font = ImageFont.load_default()

    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (w2 - text_w) // 2 - bbox[0]
    y = (h2 - text_h) // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 235))

    img = img.resize((width, height), Image.LANCZOS)
    img.save(output_path, "PNG")
    return output_path


def _make_show_pill(show_name: str, output_path: Path,
                    *, width: int = 320, height: int = 60) -> Path:
    """Render a per-show branded pill. Wider default (320) so longer
    show names fit at a readable font size. Used in conjunction with
    ``_make_url_pill`` for two-corner network branding."""
    return _make_brand_pill(output_path, text=show_name,
                            width=width, height=height)


def _make_url_pill(output_path: Path,
                   *, width: int = 260, height: int = 60) -> Path:
    """Render the ``nerranetwork.com`` corner pill that points listeners
    at the network homepage. Companion to ``_make_show_pill``."""
    return _make_brand_pill(output_path, text=_NETWORK_URL_PILL_TEXT,
                            width=width, height=height)


# ---------------------------------------------------------------------------
# Slideshow renderer (stage 1)
# ---------------------------------------------------------------------------

# Each photo holds for ~12 s on long-form — long enough to read the
# spectrum + caption but short enough that the video keeps moving.
# Shorts use a faster pace (~7 s/scene) so a 55 s clip sees ~8 scene
# changes; static photos for 12 s on a phone scroll feel like
# nothing's happening.
_SCENE_DURATION_SECONDS = 12.0
_SHORT_SCENE_DURATION_SECONDS = 7.0

# Longest a single still may hold before the scene list is cycled to bring in
# fresh visual rhythm. Lowered 25 → 15 s (June 2026 motion pass): YouTube's
# 2025-2026 policy + retention data both penalise long static holds, so cycling
# the existing Grok images more often adds rhythm at zero extra image cost. The
# Ken-Burns zoom + slideshow crossfades keep each hold watchable (the hybrid
# Grok video clips were retired June 29 2026 — images-only pipeline).
# Visual-only — no audio impact.
#
# Paired with engine.scene_scheduler._MAX_SLIDESHOW_SLOTS: a long episode at
# 15 s/hold would otherwise ask for 60–70+ ffmpeg inputs (Ep537 timeout).
# The cycling path below clamps to that shared cap so holds stretch instead.
_MAX_SCENE_HOLD_S = 15.0


# Crossfade between scenes for a more dynamic, modern slideshow (June 2026
# visual pass — replaces hard cuts). Rotating tasteful transition types add
# variety at zero cost. Set to 0.0 to disable (plain hard cuts). The render
# path falls back to hard-cut concat if the xfade chain ever fails, so this
# can never make a render fail outright.
_SLIDESHOW_XFADE_S = 0.6
# A2 (Aug 2026, un-held when the motion A/B was formally ended): the
# transition treatment SPLITS by format. A 0.6 s dissolve reads cinematic
# on a 12-29 s long-form hold but eats 10-15% of a 4-8 s Shorts segment
# and reads slow against short-form editing grammar — Shorts join on a
# fast 0.25 s crossfade instead (still softer than a hard cut, so the
# slideshow never looks broken).
_SHORTS_XFADE_S = 0.25
# dissolve/fadeblack were removed from the rotation (Aug 2026): ffmpeg's
# dissolve is a random per-pixel threshold — on photographic stills it
# reads as a burst of noise, and it is the worst possible input for the
# x264 maxrate ceiling; fadeblack dips to black mid-episode, which reads
# as an unintended cut on a continuous slideshow.
_XFADE_TRANSITIONS = [
    "fade", "smoothleft", "fade", "circleopen", "smoothright", "fade",
]

# Ken Burns geometry (July 2026 sharpness pass).
#
# The source stills are the constraint. Grok Imagine returns 1792x1024
# for 16:9, which is *below* the 1920x1080 delivery frame, so every
# pixel shipped is already an upsample before the zoom adds more. The
# old numbers — pre-scale 1.15 (2208px) with a zoom to 1.12 — pushed
# the worst case to about 1.38x.
#
# Two changes, both conservative:
#
# * ``_ZOOM_MAX`` 1.12 -> 1.09. Less magnification at the top of each
#   scene's window, and less per-frame motion, which also matters for
#   file size: continuous sub-pixel zoom defeats inter-frame prediction,
#   so the encoder spends real bitrate re-describing a still photo.
# * Lanczos on the pre-scale. ffmpeg's default is bicubic, which is
#   noticeably softer on upsamples. Lanczos costs CPU only.
#
# The 1.15 pre-scale itself is deliberately kept. Working above the
# output resolution is what hides ``zoompan``'s integer-pixel stepping;
# dropping to 1.0 would sharpen the still frame and introduce visible
# judder in the motion, which is the worse trade on a slideshow.
_PRESCALE = 2.0
_ZOOM_MAX = 1.09

# ---------------------------------------------------------------------------
# Network color grade (July 31 2026 render pass — C1)
# ---------------------------------------------------------------------------
# One gentle chain applied wherever the composite forms its ``[bg]``
# (long-form both branches, Shorts, and the fused single-pass graph) so
# every Grok Imagine scene on the network shares a unified, produced
# look instead of shipping raw flat pixels:
#
#   * ``eq``       — gentle contrast/saturation lift + tiny gamma dip;
#     Grok stills ship flat.
#   * ``vignette`` — soft default vignette (angle=PI/5): depth + an
#     eye-to-center pull that unifies mismatched scenes.
#   * ``gradfun``  — de-bands the gradient skies that slow Ken Burns
#     zooms make shimmer.
#
# Deliberately NO ``noise`` grain: grain fights the encoder (the 4 Mbps
# ``-maxrate`` ceiling in ``_VIDEO_ENCODE`` exists precisely for
# near-noise pathologies). The chain is applied ONCE per delivered
# pixel — at composite/[bg] time, never inside the stage-1 slideshow —
# so the two-stage path cannot double-grade.
_GRADE_CHAIN = (
    "eq=contrast=1.05:saturation=1.08:gamma=0.98,"
    "vignette=angle=PI/5,"
    "gradfun=3.5:8"
)

# Shorts-only output sharpen (C2). The 9:16 Grok sources come back
# below delivery resolution, so every vertical pixel shipped is an
# upsample; lanczos preserves detail but a mild luma-only unsharp
# restores perceived crispness on phone screens. Amount stays at 0.5 —
# halos appear above ~0.8. Long-form skips this (the 2.0 prescale +
# lanczos was measured as the knee there).
_SHORTS_SHARPEN = "unsharp=5:5:0.5:5:5:0.0"

# ---------------------------------------------------------------------------
# Ken Burns (July 30 2026 motion pass — measured, not guessed)
# ---------------------------------------------------------------------------
# Three defects were found by rendering the shipping filter graph at
# 1920x1080 and measuring frames. All three are fixed by
# ``_ken_burns_chain`` below; the numbers are from that A/B on a 12 s
# scene (the long-form default):
#
# 1. THE MOTION STOPPED. The zoom was a fixed per-frame increment against
#    a cap: ``min(zoom+0.0006,1.09)``. That reaches the cap after
#    (1.09-1.0)/0.0006 = 150 frames = 5.0 s at 30 fps, and then the image
#    is perfectly static for the rest of the scene. Measured: **57.1% of
#    a 12 s scene was a frozen still**, and worse on longer holds (10 s of
#    a 15 s ``_MAX_SCENE_HOLD_S`` hold). Now the zoom is normalised to the
#    segment: it runs from 1.0 to _ZOOM_MAX across exactly the scene's own
#    frame count, so it never freezes and never depends on hold length.
#    Measured after: **0.0% frozen**.
#
# 2. THE ZOOM ANCHORED TO THE TOP-LEFT CORNER. ``zoompan``'s x and y
#    default to "0" (confirmed against ffmpeg 7.0's own
#    ``-h filter=zoompan``), and this pipeline never set them — so every
#    scene on the network zoomed into its top-left corner, sliding the
#    subject down and right. Measured drift of a dead-centre subject over
#    one scene: 0.044 of frame width. Now the anchor is expressed
#    explicitly. Measured after: **0.000**.
#
# 3. JUDDER — one frame in three was IDENTICAL. ``zoompan`` computes x/y
#    in integer source pixels, so at a 1.15x pre-scale a slow zoom often
#    doesn't advance a whole pixel between frames, and the motion stutters
#    at an effective ~20 fps inside a 30 fps video. Raising the pre-scale
#    gives sub-pixel headroom. Measured judder (coefficient of variation
#    of per-frame change, lower is smoother): 1.15x -> 0.391,
#    2.0x -> 0.221, 3.0x -> 0.101, against render cost +17% and +121%.
#    2.0x is the knee and is what ``_PRESCALE`` now is.
#
# Deliberately NOT eased. A smoothstep ramp reads better in theory, but
# its slow start/end re-introduce exactly the sub-pixel stepping of (3):
# measured 0.8% frozen and CV 0.271 against linear's 0.0% and 0.221, for
# more render time. Constant velocity is also what documentary Ken Burns
# actually uses.
#
# Render-only: no audio path is touched, so this sits outside the
# landmine #17 A/B-listen gate.

# Gentle, deterministic move per scene index — varied enough not to feel
# mechanical, never so much that it draws attention to itself. Index, not
# randomness, so a re-render of the same episode is identical.
#
# July 31 2026 (A1): widened from 4 to 8 moves. The FIRST FOUR entries
# are the legacy vocabulary in the legacy order — the Shorts motion A/B
# control arm renders with ``extended=False`` which indexes only into
# that prefix, so the ordering here is load-bearing. The new moves
# reuse the same feasible-window travel math; the diagonals ramp BOTH
# cx and cy (each axis is independently bounded, so feasibility holds).
_KB_MOVES = ("in_centre", "out_centre", "in_pan_x", "out_pan_y",
             "in_pan_y", "out_pan_x", "in_pan_xy", "out_pan_xy")
# How many of the leading moves make up the legacy (pre-A1) vocabulary.
_KB_LEGACY_MOVE_COUNT = 4

# Per-slot zoom amplitude alternation (A1) — rhythm without randomness.
# 1.12 was the pre-July-2026 network value, so sharpness at that
# ceiling is a known-acceptable quantity; 1.06 is a calmer breath
# between the stronger pushes. The legacy path stays pinned at
# ``_ZOOM_MAX`` (1.09).
_KB_ZOOM_AMPLITUDES = (1.06, 1.09, 1.12)
# Duration-adaptive Ken Burns (Aug 2026): amplitude per second of hold,
# with floor/ceiling. 0.006/s x 15 s = 0.09 — the historical middle rung,
# so the common case is unchanged; longer holds travel proportionally
# further instead of slowing to sub-perceptual drift.
_KB_AMP_PER_SECOND = 0.006
_KB_AMP_MIN = 0.04
_KB_AMP_MAX = 0.24


def _kb_seed_from_stem(stem) -> int:
    """Deterministic per-episode Ken Burns seed from an output filename.

    CRC32 of the stem — stable across processes and re-renders of the
    same episode (unlike ``hash()``, which is salted per interpreter),
    varied across episodes/files, and no date/random involvement so a
    re-render is byte-identical.
    """
    return zlib.crc32(str(stem).encode("utf-8")) & 0xFFFFFFFF


def _ken_burns(frames: int, move: str, *,
               zoom_max: float = _ZOOM_MAX,
               ease: str = "linear") -> Tuple[str, str, str]:
    """Return ``(z, x, y)`` zoompan expressions for one scene.

    *frames* is the scene's own output frame count, which is what makes
    the motion duration-independent: a 4 s scene and a 15 s scene both
    travel the full zoom range over their own length.

    ``ease="out"`` (Aug 2026 — E1 punch-ins, un-held when the motion
    A/B was formally ended) front-loads the travel: progress runs
    ``p*(2-p)`` instead of linear, so ~75% of the move lands in the
    first half of the segment and then settles — the short-form
    "punch-in" cut. Same total travel, same clamps; only the velocity
    profile changes, so the feasibility math below is untouched.
    """
    n = max(2, int(frames))
    # Normalised progress 0..1 across this scene, in OUTPUT frames.
    p = f"(min(on/{n - 1},1))"
    if ease == "out":
        p = f"({p}*(2-{p}))"
    amp = round(zoom_max - 1.0, 6)

    if move.startswith("out"):
        z = f"({zoom_max}-{amp}*{p})"
    else:
        z = f"(1+{amp}*{p})"

    # Pan amplitude is bounded by the zoom's feasible window: at zoom z
    # the visible-window CENTRE can only sit in [1/(2z), 1-1/(2z)], i.e.
    # +/-(1-1/z)/2 around 0.5 — which is 0 at zoom 1.0 and only ~0.041 at
    # 1.09. The previous fixed 0.42→0.58 sweep (+/-0.08) exceeded that for
    # roughly the first and last 40% of every pan scene; zoompan clamps
    # x/y, so those phases rendered as edge-anchored zooms (a milder
    # reprise of the corner-drift defect this function was written to
    # fix). The pan now ramps from centre exactly as fast as the growing
    # zoom makes room: in-pans start centred and drift as they tighten,
    # out-pans return to centre as they widen, and the requested centre
    # stays inside the feasible window for every frame.
    # FLOOR to 6 decimals (not round): rounding up by half an ulp can
    # push the requested centre a hair past the feasible window at
    # p=1, where zoompan clamps — flooring keeps every frame strictly
    # inside. (The legacy 1.09 value is identical either way, so the
    # A/B control arm's graph is unchanged.)
    travel = math.floor(((1.0 - 1.0 / zoom_max) / 2.0) * 1e6) / 1e6
    ramp_in = f"(0.5+{travel}*{p})"          # centre → offset as zoom tightens
    ramp_out = f"(0.5+{travel}-{travel}*{p})"  # offset → centre as zoom widens
    if move == "in_pan_x":
        cx, cy = ramp_in, "0.5"
    elif move == "out_pan_y":
        cx, cy = "0.5", ramp_out
    elif move == "in_pan_y":
        cx, cy = "0.5", ramp_in
    elif move == "out_pan_x":
        cx, cy = ramp_out, "0.5"
    elif move == "in_pan_xy":
        cx, cy = ramp_in, ramp_in
    elif move == "out_pan_xy":
        cx, cy = ramp_out, ramp_out
    else:
        cx, cy = "0.5", "0.5"

    # Anchor is the centre POINT of the visible window, so the framing
    # stays put (or travels deliberately) instead of drifting to a corner.
    return z, f"iw*{cx}-(iw/zoom/2)", f"ih*{cy}-(ih/zoom/2)"


def _ken_burns_chain(src: str, out_label: str, *, frames: int, index: int,
                     width: int, height: int, fps: int,
                     prescale: float = _PRESCALE,
                     trim_seconds: Optional[float] = None,
                     kb_seed: int = 0,
                     kb_extended: bool = True,
                     ease: str = "linear",
                     closing_beat: bool = False) -> str:
    """The full scale -> crop -> zoompan chain for one still.

    ``kb_extended=True`` (July 31 2026, A1) uses the widened 8-move
    vocabulary offset by ``kb_seed`` (per-episode, derived from the
    output filename stem) and alternates the zoom amplitude per slot
    (1.06 / 1.09 / 1.12). ``kb_extended=False`` reproduces the legacy
    behaviour byte-for-byte — first 4 moves in index order at
    ``_ZOOM_MAX``, seed ignored — which the Shorts motion A/B control
    arm depends on (upgrading the control mid-flight would bias the
    experiment).
    """
    pre_w, pre_h = int(width * prescale), int(height * prescale)
    if kb_extended:
        move = _KB_MOVES[(index + kb_seed) % len(_KB_MOVES)]
        ladder = _KB_ZOOM_AMPLITUDES[
            (index + kb_seed) % len(_KB_ZOOM_AMPLITUDES)] - 1.0
        if trim_seconds and trim_seconds > 0:
            # Duration-adaptive amplitude (Aug 2026): a fixed amplitude
            # means perceived velocity is inversely proportional to hold
            # length — a 4 s Shorts segment moved at ~2.3%/s while a
            # post-cap 29 s hold crawls at ~0.3%/s (functionally the
            # frozen still the motion pass exists to eliminate). Scale
            # the zoom range with the hold so travel speed stays in a
            # visible band; the ladder survives as a ±1/3 rhythm
            # multiplier (0.006/s reproduces the 1.09 middle rung at
            # the historical 15 s hold exactly). Floor keeps short
            # segments calm; ceiling keeps long holds from swimming.
            rel = ladder / 0.09
            amp = min(_KB_AMP_MAX,
                      max(_KB_AMP_MIN, _KB_AMP_PER_SECOND * trim_seconds * rel))
            zoom_max = round(1.0 + amp, 4)  # clean float repr in the graph
        else:
            zoom_max = 1.0 + ladder
    else:
        # Legacy mode stays byte-pinned (Shorts motion A/B control arm).
        move = _KB_MOVES[index % _KB_LEGACY_MOVE_COUNT]
        zoom_max = _ZOOM_MAX
    if closing_beat and kb_extended:
        # D2 (long-form ending beat): the FINAL scene always settles on
        # a slow centred push-in at a gentle amplitude — the episode
        # visually comes to rest before the outro card fades in, instead
        # of ending mid-pan on whatever the rotation happened to deal.
        move = "in_centre"
        zoom_max = min(zoom_max, 1.06)
    z, x, y = _ken_burns(frames, move, zoom_max=zoom_max,
                         ease=ease if kb_extended else "linear")
    chain = (
        f"{src}"
        f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase"
        f":{_SCALE_FLAGS},"
        f"crop={pre_w}:{pre_h},setsar=1,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}"
        f":s={width}x{height}:fps={fps}"
    )
    if trim_seconds is not None:
        chain += f",trim=duration={trim_seconds:.2f},setpts=PTS-STARTPTS"
    return chain + out_label

# ffmpeg's default scaler is bicubic. Lanczos preserves noticeably more
# detail when upsampling, which is the only regime this pipeline is ever
# in (see above).
_SCALE_FLAGS = "flags=lanczos"


def _slideshow_filter_graph(scene_count: int, *,
                            scene_duration: float = _SCENE_DURATION_SECONDS,
                            scene_durations: Optional[Sequence[float]] = None,
                            width: int = 1920, height: int = 1080,
                            fps: int = 30,
                            crossfade: float = _SLIDESHOW_XFADE_S,
                            kb_seed: int = 0,
                            kb_extended: bool = True,
                            input_map: Optional[Sequence[int]] = None) -> str:
    """Build the filter_complex for a Ken Burns slideshow.

    Each scene gets a 1.00 → 1.12 zoom over its window. When *crossfade* > 0
    and there are ≥2 scenes, consecutive scenes are joined with a rotating
    ``xfade`` transition (more dynamic than the old hard cut); otherwise scenes
    are hard-cut via ``concat``. Each scene clip is rendered ``scene_duration +
    crossfade`` long so the xfade overlap doesn't shorten the per-scene visible
    time, and the xfade offset for scene k is ``k * scene_duration`` — keeping
    total runtime ≈ ``scene_count * scene_duration`` (slightly longer, never
    shorter, than the audio it backs).

    ``scene_durations`` (June 2026 chapter-aware pass) gives each scene its
    OWN visible duration — the vehicle for chapter-aligned scene switches
    planned by :mod:`engine.scene_scheduler`. Scene ``i`` is rendered
    ``scene_durations[i] + crossfade`` long, and the xfade offset for join
    ``k`` generalizes to the cumulative visible time ``sum(durations[:k])``
    (with per-clip length ``d_k + crossfade`` this IS the standard xfade
    chaining formula ``sum(clip_lens[:k]) - k*crossfade``). A uniform
    durations list reproduces the legacy graph exactly (``math.fsum`` of
    ``k`` equal floats rounds identically to ``k * scene_duration``); the
    hard-cut ``concat`` fallback likewise honours per-scene durations via
    each clip's own ``trim``.
    """
    if scene_durations is not None and len(scene_durations) != scene_count:
        raise ValueError(
            f"scene_durations length {len(scene_durations)} != "
            f"scene_count {scene_count}"
        )
    if input_map is not None and len(input_map) != scene_count:
        raise ValueError(
            f"input_map length {len(input_map)} != scene_count {scene_count}"
        )
    use_xfade = crossfade and crossfade > 0 and scene_count >= 2
    xfade_pad = crossfade if use_xfade else 0.0
    durs: List[float] = (
        [float(d) for d in scene_durations]
        if scene_durations is not None
        else [scene_duration] * scene_count
    )

    chains: List[str] = []

    # Input dedup (Aug 2026): a cycled plan used to open the SAME 4-8
    # image files once per slot — 24+ demuxers/decoders/input buffers of
    # identical pixels, the actual mechanism behind the Ep537 input
    # blowup the slot cap papered over. With ``input_map`` (slot ->
    # unique ffmpeg input index), each unique file is one ``-i`` and a
    # ``split`` fans its frames out to the per-slot Ken Burns chains
    # (zoompan pulls lazily, so each branch still only decodes a frame
    # or two). ``None`` keeps the legacy one-input-per-slot graph
    # byte-for-byte.
    if input_map is not None:
        from collections import Counter

        counts = Counter(input_map)
        for j in sorted(set(input_map)):
            k = counts[j]
            if k > 1:
                outs = "".join(f"[in{j}c{m}]" for m in range(k))
                chains.append(f"[{j}:v]split={k}{outs}")
        _consumed: dict = {}

        def _src(i: int) -> str:
            j = input_map[i]
            if counts[j] == 1:
                return f"[{j}:v]"
            m = _consumed.get(j, 0)
            _consumed[j] = m + 1
            return f"[in{j}c{m}]"
    else:
        def _src(i: int) -> str:
            return f"[{i}:v]"

    is_vertical = height > width
    for i in range(scene_count):
        clip_len = durs[i] + xfade_pad
        frames_per_scene = max(2, round(clip_len * fps))
        chains.append(_ken_burns_chain(
            _src(i), f"[s{i}]",
            frames=frames_per_scene, index=i,
            width=width, height=height, fps=fps,
            trim_seconds=clip_len,
            kb_seed=kb_seed, kb_extended=kb_extended,
            # E1: alternate Shorts segments punch in (ease-out travel —
            # ~75% of the move in the first half, then settle); long-form
            # keeps the linear drift.
            ease=("out" if is_vertical and i % 2 == 1 else "linear"),
            # D2: the final LONG-FORM scene settles on a gentle centred
            # push-in before the outro card fades in.
            closing_beat=(not is_vertical and i == scene_count - 1
                          and scene_count >= 2),
        ))

    if not use_xfade:
        concat_in = "".join(f"[s{i}]" for i in range(scene_count))
        chains.append(f"{concat_in}concat=n={scene_count}:v=1:a=0[v]")
        return ";".join(chains)

    # Chain xfades: [s0][s1]->[x1], [x1][s2]->[x2], ... last -> [v].
    prev = "[s0]"
    for k in range(1, scene_count):
        trans = _XFADE_TRANSITIONS[(k - 1) % len(_XFADE_TRANSITIONS)]
        offset = (
            k * scene_duration if scene_durations is None
            else math.fsum(durs[:k])
        )
        out = "[v]" if k == scene_count - 1 else f"[x{k}]"
        chains.append(
            f"{prev}[s{k}]xfade=transition={trans}"
            f":duration={crossfade:.2f}:offset={offset:.2f}{out}"
        )
        prev = out
    return ";".join(chains)


def _dedupe_scene_inputs(
    scene_paths: Sequence[Path],
) -> Tuple[List[Path], List[int]]:
    """Collapse a (cycled) slot list to unique ffmpeg inputs.

    Returns ``(unique_paths, input_map)`` where ``input_map[slot]`` is the
    index into ``unique_paths``. A cycled 24-slot plan over 4 images
    becomes 4 inputs instead of 24 demuxers of identical pixels.
    """
    unique: List[Path] = []
    index_of: dict = {}
    input_map: List[int] = []
    for p in scene_paths:
        key = str(p)
        if key not in index_of:
            index_of[key] = len(unique)
            unique.append(p)
        input_map.append(index_of[key])
    return unique, input_map


def _slideshow_cmd(scene_paths: Sequence[Path], output: Path,
                   *, scene_duration: float = _SCENE_DURATION_SECONDS,
                   scene_durations: Optional[Sequence[float]] = None,
                   width: int = 1920, height: int = 1080,
                   fps: int = 30,
                   crossfade: float = _SLIDESHOW_XFADE_S,
                   kb_seed: int = 0,
                   kb_extended: bool = True) -> List[str]:
    """ffmpeg command for stage 1 (slideshow render).

    *width* and *height* default to 1920x1080 for the long-form path;
    pass 1080x1920 for the vertical Shorts variant. Uses the fast encode
    profile (this is an intermediate re-encoded by stage 2).

    ``scene_durations`` gives each scene its own visible duration (the
    chapter-aware schedule path); each looped image input's ``-t`` then
    covers its OWN clip length instead of the shared uniform one. A
    uniform list reproduces the legacy command exactly.
    """
    use_xfade = crossfade and crossfade > 0 and len(scene_paths) >= 2
    input_pad = (crossfade if use_xfade else 0.0) + 0.5
    durs: List[float] = (
        [float(d) for d in scene_durations]
        if scene_durations is not None
        else [scene_duration] * len(scene_paths)
    )
    unique_inputs, input_map = _dedupe_scene_inputs(scene_paths)
    # Each unique input's -t must cover its LONGEST consumer slot.
    input_t = {}
    for i, j in enumerate(input_map):
        input_t[j] = max(input_t.get(j, 0.0), durs[i] + input_pad)
    inputs: List[str] = []
    for j, path in enumerate(unique_inputs):
        inputs.extend([
            "-loop", "1",
            "-framerate", str(fps),
            "-t", f"{input_t[j]:.2f}",
            "-i", str(path),
        ])
    return [
        "ffmpeg", "-y", "-threads", "0",
        *inputs,
        "-filter_complex",
        _slideshow_filter_graph(len(scene_paths),
                                scene_duration=scene_duration,
                                scene_durations=scene_durations,
                                width=width, height=height, fps=fps,
                                crossfade=crossfade,
                                kb_seed=kb_seed, kb_extended=kb_extended,
                                input_map=input_map),
        "-map", "[v]",
        "-r", str(fps),
        *_VIDEO_ENCODE_FAST,
        "-an",
        # No +faststart: this is a local intermediate (decoded by stage 2,
        # then deleted) — relocating the moov atom is a full second pass
        # over the file for a player that will never stream it.
        str(output),
    ]


def _render_slideshow(scene_paths: Sequence[Path], output: Path,
                      *, scene_duration: float = _SCENE_DURATION_SECONDS,
                      scene_durations: Optional[Sequence[float]] = None,
                      width: int = 1920, height: int = 1080,
                      fps: int = 30,
                      kb_seed: int = 0,
                      kb_extended: bool = True,
                      crossfade: float = _SLIDESHOW_XFADE_S) -> Path:
    """Render the stage-1 slideshow MP4. Idempotent (skips if output exists).

    Tries the crossfade graph first; if ffmpeg rejects it for any reason,
    retries once with plain hard-cut concat so a transition bug can never
    block a render (worst case = the pre-June-2026 hard-cut look). The
    retry also catches the ``RuntimeError`` that :func:`_run_ffmpeg` wraps
    around ffmpeg failures (June 2026 fix — the original
    ``CalledProcessError``-only clause never matched the wrapped error,
    so the documented hard-cut fallback couldn't actually fire).
    """
    if output.exists():
        return output
    # Render to a temp name + atomic replace: a run killed mid-encode
    # (pipeline timeout) used to leave a truncated MP4 that the
    # ``output.exists()`` guard above happily reused on the next run —
    # with ``-shortest``, the delivered episode silently truncated to
    # the broken intermediate's length.
    tmp_output = output.with_name(output.stem + ".part" + output.suffix)
    tmp_output.unlink(missing_ok=True)
    logger.info("Rendering slideshow (%d scenes, %dx%d, crossfade=%.1fs) → %s",
                len(scene_paths), width, height, _SLIDESHOW_XFADE_S, output.name)
    try:
        cmd = _slideshow_cmd(scene_paths, tmp_output,
                             scene_duration=scene_duration,
                             scene_durations=scene_durations,
                             width=width, height=height, fps=fps,
                             crossfade=crossfade,
                             kb_seed=kb_seed, kb_extended=kb_extended)
        _run_ffmpeg(cmd, label="slideshow render (crossfade)")
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        logger.warning(
            "Crossfade slideshow render failed (%s) — retrying with hard cuts.",
            exc,
        )
        tmp_output.unlink(missing_ok=True)
        cmd = _slideshow_cmd(scene_paths, tmp_output,
                             scene_duration=scene_duration,
                             scene_durations=scene_durations,
                             width=width, height=height, fps=fps,
                             crossfade=0.0,
                             kb_seed=kb_seed, kb_extended=kb_extended)
        _run_ffmpeg(cmd, label="slideshow render (hard cut fallback)")
    os.replace(tmp_output, output)
    return output


# ---------------------------------------------------------------------------
# Hybrid slideshow (stills + short video clips) — Phase-4 motion upgrade
# ---------------------------------------------------------------------------

def _hybrid_filter_graph(visuals: Sequence[tuple], *,
                         width: int = 1920, height: int = 1080,
                         fps: int = 30,
                         kb_seed: int = 0,
                         kb_extended: bool = True) -> str:
    """filter_complex mixing Ken-Burns stills with native video clips.

    *visuals* is an ordered list of ``(path, is_video, duration)`` tuples.
    Image segments get the same duration-normalised, centred Ken Burns as
    the pure slideshow (``_ken_burns_chain``); video segments are
    scaled/cropped to fill the frame and play their own frames (trimmed to
    *duration*). Everything is normalised to ``fps`` + SAR 1 so the final
    ``concat`` is seamless.
    """
    chains: List[str] = []
    for i, (_path, is_video, duration) in enumerate(visuals):
        if is_video:
            chains.append(
                f"[{i}:v]"
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},setsar=1,fps={fps},"
                f"trim=duration={float(duration):.2f},setpts=PTS-STARTPTS"
                f"[s{i}]"
            )
        else:
            # Same duration-normalised, centred Ken Burns as the pure
            # slideshow — the stills between clips used to freeze after
            # 5 s and drift to the top-left exactly like every other one.
            frames = max(2, round(float(duration) * fps))
            chains.append(_ken_burns_chain(
                f"[{i}:v]", f"[s{i}]",
                frames=frames, index=i,
                width=width, height=height, fps=fps,
                trim_seconds=float(duration),
                kb_seed=kb_seed, kb_extended=kb_extended,
            ))
    concat_in = "".join(f"[s{i}]" for i in range(len(visuals)))
    chains.append(f"{concat_in}concat=n={len(visuals)}:v=1:a=0[v]")
    return ";".join(chains)


def _hybrid_slideshow_cmd(visuals: Sequence[tuple], output: Path, *,
                          width: int = 1920, height: int = 1080,
                          fps: int = 30,
                          kb_seed: int = 0,
                          kb_extended: bool = True) -> List[str]:
    """ffmpeg command for a stills+clips hybrid slideshow."""
    inputs: List[str] = []
    for path, is_video, duration in visuals:
        if is_video:
            # Input-level -t as well as the graph's trim: without it
            # ffmpeg decodes the WHOLE source, which is free for a 5 s
            # generated clip and ruinous for a 40-minute NASA master.
            inputs.extend(["-t", f"{float(duration):.2f}", "-i", str(path)])
        else:
            inputs.extend([
                "-loop", "1",
                "-framerate", str(fps),
                "-t", f"{float(duration) + 0.5:.2f}",
                "-i", str(path),
            ])
    return [
        "ffmpeg", "-y", "-threads", "0",
        *inputs,
        "-filter_complex",
        _hybrid_filter_graph(visuals, width=width, height=height, fps=fps,
                             kb_seed=kb_seed, kb_extended=kb_extended),
        "-map", "[v]",
        "-r", str(fps),
        # FAST profile: this file is a stage-1 intermediate that stage 2
        # re-encodes at delivery quality — paying preset medium + crf 22
        # here compounded generation loss AND wall-clock for a file that
        # is deleted minutes later (_slideshow_cmd already used FAST).
        *_VIDEO_ENCODE_FAST,
        "-an",
        str(output),
    ]


def _render_hybrid_slideshow(visuals: Sequence[tuple], output: Path, *,
                             width: int = 1920, height: int = 1080,
                             fps: int = 30,
                             kb_seed: int = 0,
                             kb_extended: bool = True) -> Path:
    """Render the stage-1 hybrid (stills + clips) MP4. Idempotent."""
    if output.exists():
        return output
    # Same anti-partial-file guard as _render_slideshow: never let a
    # truncated intermediate from a killed run satisfy the exists() check.
    tmp_output = output.with_name(output.stem + ".part" + output.suffix)
    tmp_output.unlink(missing_ok=True)
    cmd = _hybrid_slideshow_cmd(visuals, tmp_output,
                                width=width, height=height, fps=fps,
                                kb_seed=kb_seed, kb_extended=kb_extended)
    n_clips = sum(1 for _p, is_v, _d in visuals if is_v)
    logger.info("Rendering hybrid slideshow (%d segments, %d clips, %dx%d) → %s",
                len(visuals), n_clips, width, height, output.name)
    _run_ffmpeg(cmd, label="hybrid slideshow render")
    os.replace(tmp_output, output)
    return output


def _build_hybrid_sequence(scene_paths: Sequence[Path],
                           clip_paths: Sequence[Path],
                           clip_durations: Sequence[float],
                           *, audio_duration_s: float,
                           max_scene_hold_s: float = _MAX_SCENE_HOLD_S) -> List[tuple]:
    """Interleave video clips among (cycled) stills.

    Stills share the audio time NOT consumed by clips, cycled so no still
    holds longer than *max_scene_hold_s*. Clips are spread across the timeline
    (first clip opens the episode). Returns the ordered ``(path, is_video,
    duration)`` visual list.
    """
    import math

    stills = list(scene_paths)
    clip_total = float(sum(clip_durations))
    remaining = max(0.0, audio_duration_s - clip_total)
    if not stills:
        return [(p, True, float(d)) for p, d in zip(clip_paths, clip_durations)]

    if remaining > 0:
        hold = max(6.0, remaining / len(stills))
        if hold > max_scene_hold_s and len(stills) > 1:
            # Clamp to the same slot ceiling as _uniform_slideshow_plan —
            # this third copy of the cycling rule was never brought in
            # line when Ep537's 74 uncapped slots timed out the pipeline,
            # so a long episode with clips could still ask ffmpeg for
            # ~70 inputs on the hybrid path.
            from engine.scene_scheduler import _MAX_SLIDESHOW_SLOTS

            target = max(len(stills), math.ceil(remaining / max_scene_hold_s))
            target = min(target, _MAX_SLIDESHOW_SLOTS)
            stills = [stills[i % len(stills)] for i in range(target)]
            hold = max(6.0, remaining / len(stills))
    else:
        hold = _SCENE_DURATION_SECONDS

    n_clips = len(clip_paths)
    visuals: List[tuple] = []
    if n_clips == 0:
        return [(s, False, hold) for s in stills]
    # Spread clips: roughly one every `step` stills, first clip at the open.
    step = max(1, len(stills) // n_clips)
    ci = 0
    for j, s in enumerate(stills):
        if ci < n_clips and j % step == 0:
            visuals.append((clip_paths[ci], True, float(clip_durations[ci])))
            ci += 1
        visuals.append((s, False, hold))
    while ci < n_clips:  # any leftover clips tail the sequence
        visuals.append((clip_paths[ci], True, float(clip_durations[ci])))
        ci += 1
    return visuals


# Evergreen-B-roll cap: more than ~3 clips per episode stops feeling like
# accent motion and starts fighting the chapter-aligned still rhythm.
_MAX_BROLL_CLIPS = 3

# ...and the same logic bounds each clip's LENGTH. The pool was built
# around the recovered Grok Video clips (~5 s each), so nothing bounded
# the per-clip segment — the interleaver simply used each file's full
# duration. The first real-footage pool (Aug 2026: NASA launch views,
# 229 s - 2442 s per file) would therefore have asked for ~72 minutes of
# b-roll inside a ~10 minute episode, collapsing every still to its 1 s
# floor and making ffmpeg decode 40-minute inputs. A pool clip is an
# ACCENT: it is trimmed to at most this many seconds.
_MAX_BROLL_SEGMENT_S = 8.0


def _interleave_broll_into_schedule(
    schedule: Sequence[Tuple[Path, float]],
    clip_paths: Sequence[Path],
    clip_durations: Sequence[float],
) -> List[tuple]:
    """Interleave B-roll clips among the SCHEDULED stills.

    Counterpart of :func:`_build_hybrid_sequence` for the chapter-aware
    path: the stills keep their planned ORDER (so scene topicality still
    tracks the chapters) but their holds shrink proportionally to make
    room for the clips, keeping total runtime ≈ the scheduled total
    (which the scheduler pinned to the audio length). Clips are spread
    at roughly even positions, first clip at the open — same placement
    rhythm as the uniform hybrid path.
    """
    total = math.fsum(d for _, d in schedule)
    clip_total = math.fsum(float(d) for d in clip_durations)
    factor = (max(0.0, total - clip_total) / total) if total > 0 else 1.0
    stills = [(path, max(1.0, dur * factor)) for path, dur in schedule]

    n_clips = len(clip_paths)
    if n_clips == 0:
        return [(path, False, dur) for path, dur in stills]
    visuals: List[tuple] = []
    step = max(1, len(stills) // n_clips)
    ci = 0
    for j, (path, dur) in enumerate(stills):
        if ci < n_clips and j % step == 0:
            visuals.append((clip_paths[ci], True, float(clip_durations[ci])))
            ci += 1
        visuals.append((path, False, dur))
    while ci < n_clips:
        visuals.append((clip_paths[ci], True, float(clip_durations[ci])))
        ci += 1
    return visuals


def _probe_video_duration(path: Path, fallback: float) -> float:
    """Seconds of a video file, or *fallback* when ffprobe can't say.

    Generated clips do not always come back at the requested length, and
    a wrong duration here would desync every later segment in the
    hybrid, so the real file is measured rather than trusted.
    """
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.strip()
        value = float(out)
        if value > 0:
            return value
    except Exception:  # noqa: BLE001 — probing is advisory
        pass
    return max(0.5, float(fallback))


def _build_short_hybrid_sequence(
    scene_paths: Sequence[Path],
    clip_paths: Sequence[Path],
    *,
    duration: float,
    nominal_clip_seconds: float = 5.0,
    min_still_hold_s: float = 2.0,
) -> List[tuple]:
    """Lay out one Short's background as clips interleaved with stills.

    Returns the ``(path, is_video, seconds)`` list
    :func:`_render_hybrid_slideshow` consumes, summing to *duration*
    exactly so the background needs no looping.

    Shape: **open on a clip** (the first second of a Short decides
    whether it is watched at all, and motion is the thing being tested),
    then alternate still / clip. Clips keep their own measured length;
    the stills share whatever time is left. When the clips alone already
    cover the Short, the last one is trimmed to fit rather than dropped.
    """
    clips = [Path(p) for p in clip_paths if Path(p).exists()]
    stills = [Path(p) for p in scene_paths if Path(p).exists()]
    if not clips:
        raise ValueError("no usable clips for the hybrid Shorts background")

    # Accent clamp, mirroring the long-form _MAX_BROLL_SEGMENT_S: without
    # a per-clip cap, one long stock master (NASA b-roll runs 229-2442 s)
    # probed at `min(clip_len, duration)` and consumed the ENTIRE Short —
    # 33 s of one continuous stock clip, zero of the episode's paid
    # imagery. 6 s reads as an accent at Shorts pace.
    _max_seg = min(6.0, float(duration))
    measured = [
        min(_probe_video_duration(c, nominal_clip_seconds), _max_seg)
        for c in clips
    ]

    # Trim the clip list to what actually fits, leaving room for at least
    # one still between clips when stills exist.
    reserve = min_still_hold_s * min(len(stills), max(0, len(clips) - 1))
    budget = max(0.0, float(duration) - reserve)
    kept: List[tuple] = []
    used = 0.0
    for clip, secs in zip(clips, measured):
        if used >= budget:
            break
        secs = min(secs, budget - used)
        if secs < 1.0:
            break
        kept.append((clip, secs))
        used += secs
    if not kept:
        # Every clip was squeezed out — one clip capped at the Short's
        # length still beats raising and losing the render.
        kept = [(clips[0], min(measured[0], float(duration)))]
        used = kept[0][1]

    remaining = max(0.0, float(duration) - used)
    n_gaps = len(kept) if stills else 0
    # A still after each clip, including a tail still after the last one,
    # so the Short never ends mid-motion on a hard cut to the end card.
    hold = (remaining / n_gaps) if n_gaps else 0.0

    visuals: List[tuple] = []
    for i, (clip, secs) in enumerate(kept):
        visuals.append((clip, True, secs))
        if n_gaps and hold > 0:
            visuals.append((stills[i % len(stills)], False, hold))

    if not n_gaps and remaining > 0:
        # No stills available: stretch the final clip's slot instead of
        # leaving the tail black.
        path, secs = visuals[-1][0], visuals[-1][2] + remaining
        visuals[-1] = (path, True, secs)

    # Guarantee the sum is exact — accumulated float error over a dozen
    # segments would otherwise leave a few frames of black at the end.
    total = math.fsum(d for _p, _v, d in visuals)
    if visuals and abs(total - duration) > 1e-6:
        path, is_video, secs = visuals[-1]
        visuals[-1] = (path, is_video, max(0.5, secs + (duration - total)))
    return visuals


def _short_segment_durations(cut_times: Sequence[float],
                             duration: float,
                             *, min_segment_s: float = 0.5) -> List[float]:
    """Turn Shorts scene-change times into per-segment durations.

    ``cut_times`` are seconds relative to the clip start (the
    :func:`engine.scene_scheduler.sentence_cut_times` contract). Cuts
    are sorted, deduped, and dropped when they'd create a segment
    shorter than *min_segment_s* or land within *min_segment_s* of the
    clip end. The last segment runs to the clip end, so the durations
    always sum to *duration* exactly. Returns ``[]`` when no usable cut
    survives — the caller keeps the legacy flat-pace path.
    """
    cuts: List[float] = []
    last = 0.0
    for t in sorted(float(t) for t in cut_times or []):
        if t - last < min_segment_s:
            continue
        if t > duration - min_segment_s:
            break
        cuts.append(t)
        last = t
    if not cuts:
        return []
    durations: List[float] = []
    prev = 0.0
    for t in cuts:
        durations.append(t - prev)
        prev = t
    durations.append(duration - prev)
    return durations


# ---------------------------------------------------------------------------
# Long-form filter graph (stage 2)
# ---------------------------------------------------------------------------

# Force-style for the long-form burn-in subtitles. ASS color format
# is &HAABBGGRR (alpha is "amount of transparency" — 0x00 is opaque,
# 0xFF is transparent).
#
# May 2026 history (operator-driven iteration):
#   * First pass: ``MarginV=120`` was meant to put text in the bottom
#     third (y > 720). With Alignment=2 + a 2-line cue, the bottom of
#     the text sat at y≈960 — technically inside the bottom third but
#     still looked "mid-frame" on a YouTube player whose chrome
#     overlays the lower 80 px. ``FontSize=18`` also read as too small
#     in side-by-side reviews.
#   * Second pass (this comment block): drop the baseline to
#     ``MarginV=50`` so the text sits flush with the bottom area of
#     the video (text bottom ≈ y=1030, comfortably above YouTube's
#     auto-fading progress-bar HUD), and bump ``FontSize`` 18 → 22
#     for readability on phones and tablets. Operator caught the
#     long-form cues being too small + too high to read as a proper
#     burned-in transcript.
#
# Outline-only (``BorderStyle=1`` + ``Outline=3`` + ``Shadow=1``) is
# unchanged from the first pass — keeps the slideshow imagery
# visible behind the words.
# July 2026 legibility pass: FontSize 22 -> 26.
#
# A caveat worth recording, because it is the trap here. These numbers
# are NOT pixels. ffmpeg's ``subtitles`` filter renders SRT through
# libass with the ASS default script resolution (``PlayResY=288``), so
# every size is scaled by ``1080/288 = 3.75``. FontSize=22 is therefore
# about 82 px on screen — roughly 7.6% of frame height, already
# comfortably readable, not the ~2% a naive reading suggests. An
# earlier draft of this change assumed pixels and went to 32, which
# rendered at ~120 px and swallowed the lower third of the frame.
#
# 26 (~98 px) is a real improvement on a phone without the captions
# becoming the subject of the video. The comparison was rendered at 22,
# 26, 28 and 32 before picking.
#
# Deliberately NOT switched to the Shorts' ``BorderStyle=3`` card: on a
# 16:9 slideshow the card would band across imagery that is the whole
# point of the video, whereas a 9:16 Short is mostly empty anyway.
# Outline-only keeps the picture visible behind the words.
_SUBTITLES_FORCE_STYLE = (
    "FontName=DejaVu Sans,"
    "FontSize=26,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "BackColour=&H00000000,"
    "BorderStyle=1,"
    "Outline=3,"
    "Shadow=1,"
    "Alignment=2,"
    "MarginV=50"
)


# Force-style for the Shorts (1080x1920 vertical) burn-in subtitles.
#
# May 2026 upgrade (operator: "transcript should look visually good"):
# moved from outline-only at FontSize=34 to a TikTok-style "subtitle
# card" — bigger, bolder text on a semi-transparent rounded-feel box
# that always reads against busy Grok-Imagine backgrounds:
#
#   * FontSize 34 → 48. Modern YouTube Shorts auto-captions sit
#     around this size; phones held at 5-10 cm need it.
#   * Bold=-1 (ASS "true"). Heavier strokes survive over photos.
#   * BorderStyle 1 → 3 (opaque box). Combined with a translucent
#     BackColour (&H80 alpha = 50 % opaque black), the cue sits in
#     a card rather than relying purely on outline to read against
#     bright imagery. Way more legible on phones.
#   * MarginV 300 → 340. Larger card needs more clearance from the
#     URL pill (y ≈ 1820) at the bottom; 340 places the card top
#     at ~y≈1480, still firmly in the bottom third and below the
#     hook overlay (which fades after 3 s).
#   * Outline kept at 3 so the text has a hairline contour even
#     where the card edges meet bright pixels. Shadow dropped to
#     0 since the box already separates text from the image.
#
# Vertical frame is narrower (1080 vs 1920); the matching wrap in
# ``captions.transcript_to_srt_window`` was tightened from
# ``wrap_max_chars=32`` / ``wrap_max_lines=3`` to ``24`` / ``2`` so
# the larger card holds at most 2 lines of ~24 chars each — fits
# inside ~960 px wide at FontSize=48 with comfortable side margins
# and never stretches taller than the available clearance.
_SHORTS_SUBTITLES_FORCE_STYLE = (
    "FontName=DejaVu Sans,"
    "FontSize=48,"
    "Bold=-1,"
    "PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,"
    "BackColour=&H80000000,"
    "BorderStyle=3,"
    "Outline=3,"
    "Shadow=0,"
    "Alignment=2,"
    "MarginV=340"
)


def _shorts_subtitle_style(margin_v: Optional[int] = None) -> str:
    """Shorts caption ``force_style``, optionally overriding ``MarginV`` (px
    from the bottom edge).

    The default 340 is tuned for YouTube Shorts. Instagram Reels / TikTok draw
    their caption + CTA UI over the bottom ~16% of the frame, so the social
    variant lifts captions higher (a larger MarginV) to keep them readable.
    """
    if margin_v is None:
        return _SHORTS_SUBTITLES_FORCE_STYLE
    return _SHORTS_SUBTITLES_FORCE_STYLE.replace("MarginV=340", f"MarginV={int(margin_v)}")


# Long-form opening hook title (July 31 2026 — B4). The July 30
# retention pass made the AUDIO open on its hook; the VIDEO first
# seconds were still a photo + two pills. This stage burns the hook as
# an on-screen title for the first ~4 s so the viewer READS the hook
# while the cold open SPEAKS it. Alpha ramps in over 0.3 s and out over
# the last 0.6 s (ending t=4) instead of popping.
_LONG_HOOK_ALPHA = "clip(t/0.3,0,1)*clip((4-t)/0.6,0,1)"
_LONG_HOOK_ENABLE = "between(t,0,4.05)"


def _long_form_hook_stage(post_label: str, hook: str, *,
                          width: int = 1920,
                          has_subtitles: bool = False) -> Tuple[str, str]:
    """Per-line drawtext chain for the long-form opening hook title.

    Returns ``(chain_fragment, new_post_label)``. Mirrors the Shorts
    graph's proven per-line label-chaining pattern (one drawtext per
    wrapped line — the ``\\n``-in-text path is the Tesla Ep485 "letter
    n" landmine). Autofit at 16:9: safe margin 140, max 2 lines,
    candidates 64/56/48/40 px. Lines are centred around ``h*0.42`` —
    above frame centre, clear of the bottom caption zone.

    An empty/unrenderable hook returns ``("", post_label)`` so the
    caller's terminal logic is untouched.
    """
    font_path_raw = _find_font()
    font_path = _drawtext_escape(font_path_raw)
    hook_fontsize, wrapped = autofit_hook_overlay(
        hook,
        frame_width=width,
        safe_margin=140,
        max_lines=2,
        font_path=font_path_raw,
        candidates=(64, 56, 48, 40),
    )
    wrapped_lines = [ln for ln in (wrapped.split("\n") if wrapped else []) if ln]
    if not wrapped_lines:
        return "", post_label
    n_lines = len(wrapped_lines)
    line_spacing = 14
    line_h = hook_fontsize + line_spacing
    terminal = "[lfhooked]" if has_subtitles else "[v]"
    chain = ""
    for i, line in enumerate(wrapped_lines):
        escaped_line = _drawtext_escape(line)
        offset_px = (i - (n_lines - 1) / 2.0) * line_h
        sign = "+" if offset_px >= 0 else "-"
        y_expr = f"h*0.42{sign}{abs(offset_px):.0f}"
        is_last = (i == n_lines - 1)
        line_label = terminal if is_last else f"[lfhookln{i}]"
        chain += (
            f";{post_label}drawtext=fontfile='{font_path}':"
            f"text='{escaped_line}':"
            f"fontsize={hook_fontsize}:fontcolor=white:"
            f"x=(w-text_w)/2:y={y_expr}:"
            f"borderw=4:bordercolor=black:"
            f"shadowx=2:shadowy=2:shadowcolor=black@0.7:"
            f"alpha='{_LONG_HOOK_ALPHA}':"
            f"enable='{_LONG_HOOK_ENABLE}'"
            f"{line_label}"
        )
        post_label = line_label
    return chain, post_label


# Chapter title cards (Sep 2026). Long-form viewers' average view
# duration sits at ~80 s regardless of episode length and half the
# audience leaves inside the first 5% — the video gives no visual cue of
# what is coming. Each chapter boundary now shows a broadcast-style
# card (chapter title, top-left under the brand pill, boxed, 250 ms
# fade in/out, on screen ~4 s) driven by the same chapters JSON that
# powers the seek-bar chapters. Render/metadata only.
_CHAPTER_CARD_SECONDS = 4.0
# Structural chapter titles never earn a card — the viewer is watching
# the intro / closing already; a card saying "Closing" is noise.
_CHAPTER_CARD_SKIP_TITLES = frozenset({
    "introduction", "intro", "closing", "outro", "tomorrow teaser", "teaser",
})


def _long_form_chapter_cards_stage(
    post_label: str,
    cards: Sequence[Tuple[float, str]],
    *, width: int = 1920,
) -> Tuple[str, str]:
    """drawtext chain painting one title card per chapter boundary.

    *cards* is ``[(start_seconds, title), ...]``. Cards starting inside
    the opening hook window (< 5 s) are skipped — the hook owns the
    open. Returns ``(chain_fragment, new_post_label)``; an empty list
    returns ``("", post_label)`` so callers' terminal logic is untouched.
    """
    from engine.titles import CHAPTER_CARD_MAX, ELLIPSIS, fits

    usable = []
    for start, title in cards or []:
        try:
            s = float(start)
        except (TypeError, ValueError):
            continue
        t = str(title or "").strip()
        if s < 5.0 or not t:
            continue
        # Quality gate (Sep 3 2026): only a clean headline earns a card.
        # A title the chapter builder already clipped (trailing ellipsis
        # = a first-sentence fallback, never a real headline), one that
        # would not fit the card, or a structural label is skipped —
        # never cut. The limit lives in engine.titles like every other.
        if t.endswith(ELLIPSIS) or t.endswith("...") or not fits(t, CHAPTER_CARD_MAX):
            continue
        if t.lower().rstrip(".:") in _CHAPTER_CARD_SKIP_TITLES:
            continue
        usable.append((s, t))
    if not usable:
        return "", post_label
    font_path = _drawtext_escape(_find_font())
    chain = ""
    label = post_label
    for i, (s, t) in enumerate(usable):
        end = s + _CHAPTER_CARD_SECONDS
        out = f"[chap{i}]"
        alpha = (f"clip((t-{s:.2f})/0.25,0,1)*"
                 f"clip(({end:.2f}-t)/0.25,0,1)")
        chain += (
            f";{label}drawtext=fontfile='{font_path}':"
            f"text='{_drawtext_escape(t)}':"
            f"fontsize=40:fontcolor=white:"
            f"x=24:y=112:"
            f"box=1:boxcolor=black@0.55:boxborderw=14:"
            f"alpha='{alpha}':"
            f"enable='between(t,{s:.2f},{end + 0.05:.2f})'"
            f"{out}"
        )
        label = out
    return chain, label


def _long_form_subtitles_stage(post_label: str,
                               subtitles_path: str) -> str:
    """The terminal subtitles stage for the long-form composite.

    SRT goes through libass at the ASS default PlayRes (288 units), so
    the legacy ``force_style`` (FontSize=26 ≈ 98 px on screen) applies.
    A per-word ``.ass`` file (July 31 2026 — B1) declares its OWN
    PlayRes 1920x1080 and carries the equivalent long-form style in
    real pixels (Fontsize 98) — forcing the 288-unit style onto it
    would render ~26 px captions, so the ASS file's self-styling wins.
    """
    escaped = _subtitles_path_escape(subtitles_path)
    if subtitles_path.lower().endswith(".ass"):
        return f";{post_label}subtitles='{escaped}'[v]"
    return (
        f";{post_label}subtitles='{escaped}'"
        f":force_style='{_SUBTITLES_FORCE_STYLE}'[v]"
    )


def _long_form_filter_graph(*, width: int = 1920, height: int = 1080,
                            fps: int = 30,
                            bg_is_video: bool = False,
                            subtitles_path: Optional[str] = None,
                            with_url_pill: bool = False,
                            hook: Optional[str] = None,
                            chapter_cards: Optional[Sequence[Tuple[float, str]]] = None) -> str:
    """filter_complex for stage 2.

    Inputs:
      ``[0:v]`` — background. Either looped cover image (Ken Burns
      applied here) or pre-rendered slideshow MP4 (zoom already
      baked in; we just scale to fill).
      ``[1:a]`` — episode audio (passed through via ``-map 1:a``;
      doesn't participate in the filter graph).
      ``[2:v]`` — show brand pill PNG, looped (top-left).
      ``[3:v]`` — (optional, when ``with_url_pill=True``)
      ``nerranetwork.com`` URL pill PNG, looped (top-right).

    Earlier revisions overlaid a ``showcqt`` audio-spectrum band along
    the bottom 25% of the frame. For speech-heavy podcasts the
    spectrum read as multicolour static and dominated the visual,
    obscuring the slideshow photos behind it. Removed in favour of
    just slideshow + brand pill + disclosure + (optional) burned-in
    captions. Captions already provide the audio-sync feedback the
    spectrum used to.
    """
    if bg_is_video:
        # Slideshow MP4 already has motion + zoom at exactly this
        # resolution, so the scale/crop pair here is a no-op on every
        # real render — it only earns its keep if a caller ever hands in
        # a differently-sized background. ``scale`` short-circuits when
        # input and output dimensions already match, so leaving it costs
        # nothing and keeps that contract.
        bg_chain = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase"
            f":{_SCALE_FLAGS},"
            f"crop={width}:{height},setsar=1,{_GRADE_CHAIN},format=yuv420p[bg]"
        )
    else:
        # Degraded path: one static cover behind the whole episode, with a
        # very slow drift so it isn't a frozen JPEG. The rate is
        # deliberately tiny (1.08 over ~11 min at 30 fps) and is left
        # alone; what's fixed here is the ANCHOR. Without explicit x/y,
        # zoompan defaults both to "0" and creeps the cover toward its
        # top-left corner for the entire episode. Centred, the drift is a
        # slow push-in on the artwork instead.
        pre_w = int(width * _PRESCALE)
        pre_h = int(height * _PRESCALE)
        zoom_expr = "min(zoom+0.000004,1.08)"
        bg_chain = (
            f"[0:v]"
            f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase"
            f":{_SCALE_FLAGS},"
            f"crop={pre_w}:{pre_h},setsar=1,"
            f"zoompan=z='{zoom_expr}'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s={width}x{height}:fps={fps},"
            f"{_GRADE_CHAIN}"
            f"[bg]"
        )

    # No centered disclosure burn-in: compliance is covered by
    # status.containsSyntheticMedia=True on the API upload (renders
    # YouTube's own "Altered or synthetic content" label) plus the
    # synthetic_disclosure footer in the description. The brand pill
    # in the top-left carries the show name; the optional URL pill
    # in the top-right carries ``nerranetwork.com`` so listeners
    # always see where to find the network.
    graph = (
        f"{bg_chain};"
        f"[2:v]format=rgba[brand];"
        f"[bg][brand]overlay=x=24:y=24[branded]"
    )
    if with_url_pill:
        graph += (
            ";[3:v]format=rgba[urlpill];"
            "[branded][urlpill]overlay=x=W-w-24:y=24[stamped]"
        )
        post_brand_label = "[stamped]"
    else:
        post_brand_label = "[branded]"

    # Opening hook title (B4) — chains after the pills, before captions.
    if hook:
        frag, post_brand_label = _long_form_hook_stage(
            post_brand_label, hook, width=width,
            has_subtitles=bool(subtitles_path) or bool(chapter_cards),
        )
        graph += frag
        if not subtitles_path and post_brand_label == "[v]":
            return graph  # hook stage terminated the graph

    # Chapter title cards (Sep 2026) — after the hook, before captions.
    if chapter_cards:
        frag, post_brand_label = _long_form_chapter_cards_stage(
            post_brand_label, chapter_cards, width=width)
        graph += frag

    if subtitles_path:
        graph += _long_form_subtitles_stage(post_brand_label, subtitles_path)
    else:
        graph += f";{post_brand_label}null[v]"
    return graph


def _short_form_filter_graph(width: int = 1080, height: int = 1920,
                             fps: int = 30,
                             hook: Optional[str] = None,
                             bg_is_video: bool = False,
                             with_url_pill: bool = False,
                             subtitles_path: Optional[str] = None,
                             end_card: bool = False,
                             end_card_duration: float = 3.0,
                             total_duration: float = 55.0,
                             end_card_main_text: str = "WATCH FULL EPISODE",
                             end_card_sub_text: str = "Tap Subscribe ↗",
                             end_card_image_input_label: Optional[str] = None,
                             progress_bar: bool = False,
                             caption_margin_v: Optional[int] = None) -> str:
    """filter_complex for the 1080x1920 Shorts build.

    Inputs:
      ``[0:v]`` — background. Either looped cover image (static) or
      pre-rendered vertical slideshow MP4 (motion baked in; we just
      scale to fill).
      ``[1:a]`` — episode audio (clipped to ~55 s by input-side
      ``-ss``/``-t`` upstream; passed through via ``-map 1:a``).
      ``[2:v]`` — brand pill PNG, looped.

    Earlier revisions overlaid a ``showcqt`` audio-spectrum band in
    the vertical mid-band of the frame. For speech-heavy podcasts
    the spectrum read as multicolour static and dominated the
    visual. Removed in favour of just slideshow + brand pill +
    (optional) hook caption.
    """
    font_path = _drawtext_escape(_find_font())

    if bg_is_video:
        bg_chain = (
            f"[0:v]"
            f"scale={width}:{height}:force_original_aspect_ratio=increase"
            f":{_SCALE_FLAGS},"
            f"crop={width}:{height},setsar=1,"
            f"{_GRADE_CHAIN},{_SHORTS_SHARPEN},format=yuv420p[bg]"
        )
    else:
        # Degraded path (cover fallback): the old chain shipped a frozen
        # JPEG for the whole 35 s — the ONE render path with zero motion
        # — and upscaled it with ffmpeg's default bicubic (every other
        # upscale in this module uses lanczos), which _SHORTS_SHARPEN
        # then sharpened. Mirror the long-form degraded branch: lanczos
        # prescale + a slow centred push-in so the Short is never a
        # static frame.
        pre_w = int(width * _PRESCALE)
        pre_h = int(height * _PRESCALE)
        bg_chain = (
            f"[0:v]"
            f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase"
            f":{_SCALE_FLAGS},"
            f"crop={pre_w}:{pre_h},setsar=1,"
            f"zoompan=z='min(zoom+0.00006,1.08)'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s={width}x{height}:fps={fps},"
            f"{_GRADE_CHAIN},{_SHORTS_SHARPEN},format=yuv420p[bg]"
        )

    # Show brand pill goes top-right (anchor point for vertical Shorts).
    base = (
        f"{bg_chain};"
        f"[2:v]format=rgba[brand];"
        f"[bg][brand]overlay=x=W-w-24:y=24[branded]"
    )
    if with_url_pill:
        # URL pill at the BOTTOM (centered horizontally) so the show
        # pill at top + URL pill at bottom give clear top/bottom
        # network branding without crowding the hook caption that
        # sits in the middle for the first 3 s.
        base += (
            ";[3:v]format=rgba[urlpill];"
            "[branded][urlpill]overlay=x=(W-w)/2:y=H-h-100[stamped]"
        )
        post_brand_label = "[stamped]"
    else:
        post_brand_label = "[branded]"

    # Anchor for any post-brand overlay (progress bar + hook caption +
    # burn-in subtitles + the final ``[v]`` rename). We chain by
    # reassigning ``post_brand_label`` after each step so the order is:
    #   brand pill → URL pill → progress bar → hook (0-3s) →
    #   burn-in subtitles → [v]
    chain = base

    if progress_bar and total_duration > 0:
        # Aug 2026 render pass: thin animated bar across the top —
        # the standard Shorts retention device (visible time
        # remaining). Nerra cyan (matches the per-word caption
        # highlight); 10 px at y=0 sits far above the hook block
        # (y≈1056) and the caption card. Implementation note:
        # drawbox does NOT re-evaluate its width per frame on the
        # ffmpeg builds we ship on (verified: a t-expression paints
        # a static full-width bar), so the animation uses the
        # classic slide-in — a full-width cyan strip overlaid with
        # a per-frame x expression (overlay defaults to
        # eval=frame): off-screen left at t=0, flush at t=end.
        # shortest=1 ends the infinite color source with the main.
        # Drawn before hook/captions/end card so every later
        # overlay stacks above it.
        chain += (
            f";color=c=0x00D4FF@0.85:s={width}x10:r={fps}[pbsrc]"
            f";{post_brand_label}[pbsrc]overlay="
            f"x='-w+w*min(t/{total_duration:.2f},1)':y=0:"
            f"shortest=1[pbar]"
        )
        post_brand_label = "[pbar]"

    if hook:
        # Auto-shrink-to-fit (May 2026 retune): start at the legacy
        # fontsize=44 and shrink in 4-px steps only if the wrapped
        # text would truncate at the larger size. Pixel-accurate
        # word wrap via PIL ImageFont uses the actual frame width
        # (1080 px) instead of the old conservative char budget.
        # Output: ``(fontsize, wrapped)`` ready for drawtext.
        hook_fontsize, wrapped = autofit_hook_overlay(
            hook,
            frame_width=width,
            safe_margin=80,
            max_lines=4,
            font_path=_find_font(),
        )
        # May 26 2026 operator-caught regression (Tesla Ep485 + MAB):
        # multi-line hooks rendered as ONE overflowing line with the
        # `\n` byte showing up as the letter "n" between words —
        # "major warning" → "majornwarning", "volume reductions" →
        # "volumenreductions". The single-drawtext path emitted
        # `text='line1\nline2'` and relied on ffmpeg drawtext's
        # text= expansion to render `\n` as a newline. In practice
        # the backslash gets eaten somewhere in the filter_complex
        # parse → drawtext text= pipeline and only the literal "n"
        # survives. Fix: stack one drawtext filter PER wrapped line
        # with explicit y-offsets — sidesteps the `\n` escape
        # entirely and produces deterministic per-line layout.
        wrapped_lines = wrapped.split("\n") if wrapped else []
        n_lines = max(len(wrapped_lines), 1)
        line_spacing = 10
        line_h = hook_fontsize + line_spacing
        # May 2026 operator review: hook is the static 0-3 s
        # opening title — separate from the burn-in transcript
        # that follows. Position lifted ABOVE the burn-in zone
        # so the two overlays don't visually collide during the
        # first 3 s. ``y=h*0.55`` puts the hook block CENTER
        # around y≈1056 — inside the lower half but well above
        # the subtitle baseline at y≈1620 (MarginV=300 in
        # ``_SHORTS_SUBTITLES_FORCE_STYLE``). With multi-line
        # hooks, line i is offset from the block center by
        # ``(i - (n-1)/2) * line_h`` so the wrap stays visually
        # centered regardless of line count.
        #   * Default ``fontsize=44`` (auto-shrunk per hook length)
        #     is readable on a phone but no longer dominates the
        #     slideshow.
        #   * Outline-only (no ``box=1`` solid fill) keeps the
        #     imagery visible behind the words. A 4 px black
        #     outline + 2 px shadow stays readable on bright
        #     backgrounds without painting a black rectangle.
        hook_label = "[hooked]" if subtitles_path else "[v]"
        for i, line in enumerate(wrapped_lines):
            escaped_line = _drawtext_escape(line)
            offset_px = (i - (n_lines - 1) / 2.0) * line_h
            sign = "+" if offset_px >= 0 else "-"
            y_expr = f"h*0.55{sign}{abs(offset_px):.0f}"
            is_last = (i == n_lines - 1)
            line_label = hook_label if is_last else f"[hookln{i}]"
            # July 31 2026 (B3): fade the hook in over 250 ms and out
            # over 400 ms instead of the single-frame pop the bare
            # ``enable='between(t,0,3)'`` produced. The enable window
            # extends to 3.05 s so the alpha ramp reaches 0 on screen
            # rather than being cut off by the gate.
            chain += (
                f";{post_brand_label}drawtext=fontfile='{font_path}':"
                f"text='{escaped_line}':"
                f"fontsize={hook_fontsize}:fontcolor=white:"
                f"x=(w-text_w)/2:y={y_expr}:"
                f"borderw=4:bordercolor=black:"
                f"shadowx=2:shadowy=2:shadowcolor=black@0.7:"
                f"alpha='clip(t/0.25,0,1)*clip((3-t)/0.4,0,1)':"
                f"enable='between(t,0,3.05)'"
                f"{line_label}"
            )
            post_brand_label = line_label

    # Subtitles used to burn in HERE, with the end card overlaid on top
    # afterwards — and the PNG card is fully opaque, so the last ~3 s of
    # every Short played speech with its caption text hidden under the
    # card (8.6% of a 35 s Short, landing on the clip's final thought).
    # The caption stage now runs AFTER the end-card overlay: the caption
    # card paints its own 50%-black box, so it stays legible over the
    # CTA, and no spoken word loses its text.
    if subtitles_path and not end_card:
        escaped_sub = _subtitles_path_escape(subtitles_path)
        # Use the dedicated Shorts force-style so font + position
        # are tuned for the 1080x1920 vertical frame and don't
        # overlap the hook (above) or the URL pill (below).
        chain += (
            f";{post_brand_label}subtitles='{escaped_sub}'"
            f":force_style='{_shorts_subtitle_style(caption_margin_v)}'[v]"
        )
        return chain
    if hook and not end_card and not subtitles_path:
        # Hook was the last filter — already terminated at [v].
        return chain

    if end_card:
        # Last-N-seconds CTA card. Two render paths, gated by
        # ``end_card_image_input_label``:
        #
        # * PNG overlay (preferred). The caller renders the card
        #   PNG via engine.publisher.generate_shorts_end_card —
        #   that image composites the long-form thumbnail with
        #   the CTA copy in a richer layout than ffmpeg can paint
        #   inline. The label points at the ffmpeg input index
        #   for the PNG (e.g. ``[4:v]``). We overlay it on top of
        #   the slideshow with an ``enable`` clause for the last
        #   N seconds.
        #
        # * Drawtext fallback (no PNG provided). drawbox + 2
        #   drawtext filters paint the card inline — the
        #   pre-PR-#420 behaviour. Useful for tests / when PNG
        #   generation fails / for shows that opt-out of the
        #   thumbnail-bearing card.
        #
        # Both paths bind to the same ``between(t, END-N, END)``
        # enable window so the layer is atomic.
        if total_duration <= end_card_duration:
            end_card_start = 0.0
        else:
            end_card_start = max(0.0, total_duration - end_card_duration)
        end_card_end = total_duration
        enable_clause = (
            f"between(t,{end_card_start:.2f},{end_card_end:.2f})"
        )
        # When captions follow, the card terminates at [carded] and the
        # subtitles stage below produces the final [v].
        card_out = "[carded]" if subtitles_path else "[v]"

        if end_card_image_input_label:
            # PNG path. The input is added as a video stream
            # upstream (in _short_form_cmd) and labelled with
            # whatever index the caller assigned, e.g. ``[4:v]``.
            #
            # July 31 2026 (C4): alpha fade-in on the card's input
            # chain — ``fade`` with ``alpha=1`` ramps only the alpha
            # plane, so the card materialises over the last still in
            # 0.45 s instead of guillotining it in one frame. The
            # looped PNG input has running timestamps, so ``st=`` on
            # the card's own timeline lines up with the overlay's
            # enable window.
            chain += (
                f";{end_card_image_input_label}format=rgba,"
                f"fade=t=in:st={end_card_start:.2f}:d=0.45:alpha=1[endcard];"
                f"{post_brand_label}[endcard]overlay="
                f"x=0:y=0:enable='{enable_clause}'{card_out}"
            )
            if subtitles_path:
                escaped_sub = _subtitles_path_escape(subtitles_path)
                chain += (
                    f";{card_out}subtitles='{escaped_sub}'"
                    f":force_style='{_shorts_subtitle_style(caption_margin_v)}'[v]"
                )
            return chain

        # Drawtext fallback path. July 31 2026 (C4): the two drawtext
        # stages gain an alpha fade-in so the copy materialises rather
        # than popping; the drawbox backdrop stays hard (drawbox has no
        # alpha expression — acceptable on the degraded path).
        end_card_alpha = f"clip((t-{end_card_start:.2f})/0.45,0,1)"
        font_path = _drawtext_escape(_find_font())
        escaped_main = _drawtext_escape(end_card_main_text)
        escaped_sub = _drawtext_escape(end_card_sub_text)
        chain += (
            f";{post_brand_label}"
            # 1. Translucent black backdrop.
            f"drawbox=x=0:y=0:w=iw:h=ih:"
            f"color=black@0.78:t=fill:enable='{enable_clause}'"
            # 2. Headline.
            f",drawtext=fontfile='{font_path}':"
            f"text='{escaped_main}':"
            f"fontsize=88:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-100:"
            f"borderw=4:bordercolor=black:"
            f"shadowx=2:shadowy=2:shadowcolor=black@0.7:"
            f"alpha='{end_card_alpha}':"
            f"enable='{enable_clause}'"
            # 3. Sub-line — smaller, accent colour (cyan, matches
            # the per-word caption highlight from PR #415).
            f",drawtext=fontfile='{font_path}':"
            f"text='{escaped_sub}':"
            f"fontsize=56:fontcolor=0x00D4FF:"
            f"x=(w-text_w)/2:y=(h+text_h)/2+40:"
            f"borderw=3:bordercolor=black:"
            f"alpha='{end_card_alpha}':"
            f"enable='{enable_clause}'"
            f"{card_out}"
        )
        if subtitles_path:
            escaped_sub = _subtitles_path_escape(subtitles_path)
            chain += (
                f";{card_out}subtitles='{escaped_sub}'"
                f":force_style='{_shorts_subtitle_style(caption_margin_v)}'[v]"
            )
        return chain

    return chain + f";{post_brand_label}null[v]"


# ---------------------------------------------------------------------------
# Long-form command builder (stage 2)
# ---------------------------------------------------------------------------

def _ffmetadata_escape(text: str) -> str:
    """Escape the four characters ffmetadata treats as syntax."""
    out = str(text or "")
    for ch in ("\\", "=", ";", "#", "\n"):
        out = out.replace(ch, "\\" + ch if ch != "\n" else "\\\n")
    return out


def write_chapter_metadata(chapters_path: Path, out_path: Path,
                           total_duration_s: float) -> Optional[Path]:
    """Render an ffmetadata chapter file, or None if there's nothing to write.

    The network already produces chapters and attaches them in three
    places — the YouTube description, the audio RSS as
    ``<podcast:chapters>``, and now the video RSS — but never inside the
    MP4 itself. A container chapter track is what gives Apple's video
    player (and any future platform that ignores RSS sidecars) a
    scrubbable chapter list, and it travels with the file if someone
    downloads it.

    Requires at least two chapters: a single chapter spanning the whole
    episode is what players show anyway, so writing it adds a track for
    no benefit. Returns None on any parse problem — a bad metadata file
    would make ffmpeg fail the whole render, which is far worse than a
    video without chapters.
    """
    try:
        raw = json.loads(Path(chapters_path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Chapter metadata skipped (%s unreadable: %s)",
                     chapters_path, exc)
        return None

    items = raw.get("chapters") if isinstance(raw, dict) else raw
    if not isinstance(items, list) or len(items) < 2:
        return None

    marks: List[Tuple[float, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        start = item.get("startTime", item.get("start_time", item.get("start")))
        try:
            start_f = float(start)
        except (TypeError, ValueError):
            continue
        title = str(item.get("title") or item.get("name") or "").strip()
        marks.append((start_f, title or f"Chapter {len(marks) + 1}"))

    marks.sort(key=lambda m: m[0])
    if len(marks) < 2 or total_duration_s <= marks[-1][0]:
        return None

    lines = [";FFMETADATA1"]
    for i, (start_f, title) in enumerate(marks):
        end_f = marks[i + 1][0] if i + 1 < len(marks) else total_duration_s
        if end_f <= start_f:
            continue
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={int(start_f * 1000)}",
            f"END={int(end_f * 1000)}",
            f"title={_ffmetadata_escape(title)}",
        ]
    if len(lines) == 1:
        return None

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Chapter metadata: %d chapters -> %s", len(marks), out_path.name)
    return out_path


def _single_pass_enabled() -> bool:
    """Whether to fuse the slideshow and composite into one ffmpeg run.

    Default ON since July 29 2026, after a full A/B on both production
    render shapes (ffmpeg 6.1.1, 1920x1080, 4 scenes, 24 s):

    * uniform stills — 24.6 s two-stage vs 16.2 s fused (-34 %);
    * chapter-aligned schedule + burned-in captions — 22.3 s vs 17.2 s
      (-23 %), the shape Tesla/SpaceX actually ship.

    Both pairs came out byte-comparable where it matters: identical
    duration (24.000 s), frame count (720), geometry and codecs, mean
    absolute pixel difference under 0.3/255 at every sampled timestamp
    (encode noise — the fused path skips a generation of loss, so if
    anything it is the cleaner one), and an identical scene-progression
    timeline. Brand pill, URL pill and caption rendering were compared
    frame-to-frame and match.

    Set ``NERRA_SINGLE_PASS_RENDER=0`` to force the legacy two-stage
    path. Either way the two-stage pipeline remains the automatic
    fallback: a failure in the fused command is caught and re-rendered
    the old way, so this can only cost time, never an episode.
    """
    value = os.getenv("NERRA_SINGLE_PASS_RENDER", "").strip().lower()
    if value in ("0", "false", "no", "off"):
        return False
    return True


def _uniform_slideshow_plan(
    scene_paths: Sequence[Path], audio_duration_s: float,
) -> Tuple[List[Path], float]:
    """Scene list + per-scene hold for the non-scheduled slideshow.

    Extracted so the two-stage and single-pass paths compute the plan
    from ONE implementation. The cycling rule (no image held longer than
    ``_MAX_SCENE_HOLD_S``, capped at ``_MAX_SLIDESHOW_SLOTS`` ffmpeg
    inputs) is load-bearing on real episodes — Ep505 held one image for
    168 s before it existed, and Ep537 timed out the pipeline at 74
    uncapped slots — so the two paths must not be able to drift apart.
    """
    scenes = list(scene_paths)
    if audio_duration_s <= 0:
        return scenes, _SCENE_DURATION_SECONDS  # legacy 12 s

    hold = max(8.0, audio_duration_s / len(scenes))
    if hold > _MAX_SCENE_HOLD_S and len(scenes) > 1:
        from engine.scene_scheduler import _MAX_SLIDESHOW_SLOTS
        target = math.ceil(audio_duration_s / _MAX_SCENE_HOLD_S)
        target = min(target, _MAX_SLIDESHOW_SLOTS)
        scenes = [scenes[i % len(scenes)] for i in range(target)]
        hold = max(8.0, audio_duration_s / len(scenes))
    return scenes, hold


def _single_pass_scene_plan(
    schedule, scene_paths, audio_duration_s: float,
) -> Tuple[List[Path], Optional[List[float]], float]:
    """Resolve ``(scenes, per_scene_durations, uniform_duration)``.

    A chapter-aware schedule supplies its own per-scene holds; otherwise
    the uniform plan applies and ``per_scene_durations`` is None (which
    reproduces the legacy graph exactly).
    """
    if schedule:
        return ([p for p, _ in schedule],
                [d for _, d in schedule],
                _SCENE_DURATION_SECONDS)
    if not scene_paths:
        return [], None, _SCENE_DURATION_SECONDS
    scenes, hold = _uniform_slideshow_plan(scene_paths, audio_duration_s)
    return scenes, None, hold


def _single_pass_long_form_filter_graph(
    scene_count: int, *,
    scene_duration: float = _SCENE_DURATION_SECONDS,
    scene_durations: Optional[Sequence[float]] = None,
    width: int = 1920, height: int = 1080,
    fps: int = 30,
    crossfade: float = _SLIDESHOW_XFADE_S,
    subtitles_path: Optional[str] = None,
    with_url_pill: bool = False,
    hook: Optional[str] = None,
    kb_seed: int = 0,
    kb_extended: bool = True,
    input_map: Optional[Sequence[int]] = None,
    chapter_cards: Optional[Sequence[Tuple[float, str]]] = None,
) -> str:
    """One filter graph for slideshow + overlays + captions (P1-2).

    The two-stage path renders the Ken Burns slideshow to an intermediate
    MP4, then feeds that file back in as ``[0:v]`` of the composite. That
    costs a full extra encode AND a full extra decode of a 1080p file
    that exists only to be consumed seconds later — roughly 42% of a
    video show's wall clock — and it puts every delivered pixel through
    two lossy passes.

    Fusing them means the scene STILLS become the inputs, so the input
    indices all shift. Two-stage numbering is fixed at bg(0) / audio(1) /
    brand(2) / url-pill(3); here the scenes occupy ``0 .. n-1`` and
    everything else moves up by ``n - 1``. Getting that wrong is silent —
    ffmpeg happily overlays the wrong stream — so the offsets are derived
    from ``scene_count`` in one place rather than written out.

    The slideshow half is :func:`_slideshow_filter_graph` verbatim, with
    its ``[v]`` output relabelled ``[bg]``. Reusing it (rather than
    reimplementing) is deliberate: the xfade offset arithmetic and the
    per-scene duration handling are subtle, already tested, and must not
    fork between the two paths.
    """
    slideshow = _slideshow_filter_graph(
        scene_count,
        scene_duration=scene_duration,
        scene_durations=scene_durations,
        width=width, height=height, fps=fps,
        crossfade=crossfade,
        kb_seed=kb_seed, kb_extended=kb_extended,
        input_map=input_map,
    )
    # The slideshow graph's terminal label is always ``[v]``; the
    # composite needs it as ``[bg]``. Only the final occurrence is the
    # output (intermediate labels are [s0], [x1], ...), so replace from
    # the right. The network grade (C1) attaches here — the fused
    # path's [bg] formation — matching the two-stage composite's
    # bg_is_video branch so the two render paths ship the same look.
    if not slideshow.endswith("[v]"):
        raise ValueError("slideshow graph did not end with [v]")
    # format=yuv420p pins the composite's pixel-format negotiation the
    # same way the two-stage bg_is_video branch does — without it, the
    # rgba pill inputs let ffmpeg pick an RGB path for the whole
    # composite (a full-frame colorspace round-trip per frame, and
    # different chroma handling on overlay edges vs the two-stage path).
    graph = slideshow[: -len("[v]")] + f",{_GRADE_CHAIN},format=yuv420p[bg]"

    # Scene inputs occupy 0..n_inputs-1 (deduped when input_map is
    # given — a cycled plan's audio/brand/pill sit right after the
    # UNIQUE images, not after every slot), so audio/brand/pill shift up.
    n_inputs = (max(input_map) + 1) if input_map else scene_count
    brand_idx = n_inputs + 1
    pill_idx = n_inputs + 2

    graph += (
        f";[{brand_idx}:v]format=rgba[brand];"
        f"[bg][brand]overlay=x=24:y=24[branded]"
    )
    if with_url_pill:
        graph += (
            f";[{pill_idx}:v]format=rgba[urlpill];"
            "[branded][urlpill]overlay=x=W-w-24:y=24[stamped]"
        )
        post_brand_label = "[stamped]"
    else:
        post_brand_label = "[branded]"

    # Opening hook title (B4) — same stage as the two-stage composite.
    if hook:
        frag, post_brand_label = _long_form_hook_stage(
            post_brand_label, hook, width=width,
            has_subtitles=bool(subtitles_path) or bool(chapter_cards),
        )
        graph += frag
        if not subtitles_path and post_brand_label == "[v]":
            return graph  # hook stage terminated the graph

    # Chapter title cards (Sep 2026) — after the hook, before captions.
    if chapter_cards:
        frag, post_brand_label = _long_form_chapter_cards_stage(
            post_brand_label, chapter_cards, width=width)
        graph += frag

    if subtitles_path:
        graph += _long_form_subtitles_stage(post_brand_label, subtitles_path)
    else:
        graph += f";{post_brand_label}null[v]"
    return graph


def _outro_overlay_tail(input_label: str, *, start: float,
                        end: float) -> str:
    """Filter-graph fragment overlaying the outro card over ``[v]``.

    Appended AFTER a long-form graph has produced its terminal ``[v]``
    (all three long-form graph paths end there), consuming it and
    emitting ``[vout]`` — the caller flips its ``-map`` accordingly.
    Same fade-in + enable-window shape as the Shorts end-card PNG
    overlay, which has shipped since PR #417.
    """
    return (
        f";{input_label}format=rgba,"
        f"fade=t=in:st={start:.2f}:d=0.6:alpha=1[outrocard]"
        f";[v][outrocard]overlay=x=0:y=0:"
        f"enable='between(t,{start:.2f},{end:.2f})'[vout]"
    )


def _single_pass_long_form_cmd(
    scene_paths: Sequence[Path], audio_in: str, brand_in: str,
    output: str, *,
    scene_duration: float = _SCENE_DURATION_SECONDS,
    scene_durations: Optional[Sequence[float]] = None,
    width: int = 1920, height: int = 1080,
    fps: int = 30,
    crossfade: float = _SLIDESHOW_XFADE_S,
    subtitles_path: Optional[str] = None,
    url_pill_in: Optional[str] = None,
    chapter_metadata_in: Optional[str] = None,
    hook: Optional[str] = None,
    chapter_cards: Optional[Sequence[Tuple[float, str]]] = None,
    kb_seed: int = 0,
    kb_extended: bool = True,
    outro_card_in: Optional[str] = None,
    total_duration: float = 0.0,
    outro_duration: float = 6.0,
) -> List[str]:
    """Full ffmpeg command for the fused single-pass long-form render.

    Input order is load-bearing and mirrors the filter graph exactly:
    scenes ``0..n-1``, audio ``n``, brand ``n+1``, optional URL pill
    ``n+2``, optional ffmetadata last (it carries no streams, so it
    never appears in the graph — only in ``-map_metadata``).

    Each scene input keeps the two-stage path's ``-t`` padding so the
    xfade overlap cannot shorten a scene's visible time.
    """
    use_xfade = crossfade and crossfade > 0 and len(scene_paths) >= 2
    input_pad = (crossfade if use_xfade else 0.0) + 0.5
    durs: List[float] = (
        [float(d) for d in scene_durations]
        if scene_durations is not None
        else [scene_duration] * len(scene_paths)
    )

    unique_inputs, input_map = _dedupe_scene_inputs(scene_paths)
    input_t = {}
    for i, j in enumerate(input_map):
        input_t[j] = max(input_t.get(j, 0.0), durs[i] + input_pad)
    inputs: List[str] = []
    for j, path in enumerate(unique_inputs):
        inputs.extend([
            "-loop", "1",
            "-framerate", str(fps),
            "-t", f"{input_t[j]:.2f}",
            "-i", str(path),
        ])

    n = len(unique_inputs)
    inputs.extend(["-i", audio_in])
    inputs.extend(["-loop", "1", "-framerate", str(fps), "-i", brand_in])
    next_index = n + 2
    if url_pill_in:
        inputs.extend(["-loop", "1", "-framerate", str(fps), "-i", url_pill_in])
        next_index += 1

    # Outro card (Aug 2026 site showcase) — needs a real total duration
    # to place its enable window; without one, ship the legacy graph.
    outro_active = bool(
        outro_card_in and total_duration and total_duration > outro_duration
    )
    outro_label = None
    if outro_active:
        inputs.extend([
            "-loop", "1", "-framerate", str(fps), "-i", outro_card_in,
        ])
        outro_label = f"[{next_index}:v]"
        next_index += 1

    meta_inputs: List[str] = []
    meta_map: List[str] = []
    if chapter_metadata_in:
        meta_inputs = ["-f", "ffmetadata", "-i", chapter_metadata_in]
        meta_map = ["-map_metadata", str(next_index)]

    graph = _single_pass_long_form_filter_graph(
        len(scene_paths),
        input_map=input_map,
        scene_duration=scene_duration,
        scene_durations=scene_durations,
        width=width, height=height, fps=fps,
        crossfade=crossfade,
        subtitles_path=subtitles_path,
        with_url_pill=bool(url_pill_in),
        hook=hook,
        chapter_cards=chapter_cards,
        kb_seed=kb_seed, kb_extended=kb_extended,
    )
    map_label = "[v]"
    if outro_active and outro_label:
        graph += _outro_overlay_tail(
            outro_label,
            start=max(0.0, total_duration - outro_duration),
            end=total_duration,
        )
        map_label = "[vout]"

    return [
        "ffmpeg", "-y", "-threads", "0",
        *inputs,
        *meta_inputs,
        "-filter_complex",
        graph,
        "-map", map_label, "-map", f"{n}:a",
        *meta_map,
        *_VIDEO_ENCODE,
        "-r", str(fps),
        *_AUDIO_ENCODE,
        "-shortest",
        "-movflags", "+faststart",
        output,
    ]


def _long_form_cmd(audio_in: str, bg_in: str, brand_in: str,
                   output: str, *,
                   fps: int = 30,
                   bg_is_video: bool = False,
                   subtitles_path: Optional[str] = None,
                   url_pill_in: Optional[str] = None,
                   chapter_metadata_in: Optional[str] = None,
                   hook: Optional[str] = None,
                   chapter_cards: Optional[Sequence[Tuple[float, str]]] = None,
                   outro_card_in: Optional[str] = None,
                   total_duration: float = 0.0,
                   outro_duration: float = 6.0) -> List[str]:
    """Full ffmpeg command for stage 2.

    When *bg_is_video* is True, *bg_in* is a pre-rendered slideshow
    MP4; we ``-stream_loop -1`` it so it loops to match the audio
    length, and we don't apply ``-loop 1 -framerate``.

    When *url_pill_in* is provided, a 4th input (the
    ``nerranetwork.com`` URL pill) is added as input ``[3:v]`` and
    overlaid in the filter graph at the top-right corner.

    *chapter_metadata_in* is an ffmetadata file (see
    :func:`write_chapter_metadata`). It is added as the LAST input and
    referenced by index so it cannot disturb the ``[0:v]`` / ``[1:a]`` /
    ``[2:v]`` / ``[3:v]`` numbering the filter graph is written against —
    an ffmetadata input carries no streams, so it never appears in the
    graph, only in ``-map_metadata``.
    """
    if bg_is_video:
        bg_input = ["-stream_loop", "-1", "-i", bg_in]
    else:
        bg_input = ["-loop", "1", "-framerate", str(fps), "-i", bg_in]

    extra_inputs: List[str] = []
    # Input index: bg(0) + audio(1) + brand(2) + optional url pill(3)
    # + optional outro card next.
    next_index = 3
    if url_pill_in:
        extra_inputs.extend([
            "-loop", "1", "-framerate", str(fps), "-i", url_pill_in,
        ])
        next_index += 1

    outro_active = bool(
        outro_card_in and total_duration and total_duration > outro_duration
    )
    outro_label = None
    if outro_active:
        extra_inputs.extend([
            "-loop", "1", "-framerate", str(fps), "-i", outro_card_in,
        ])
        outro_label = f"[{next_index}:v]"
        next_index += 1

    meta_inputs: List[str] = []
    meta_map: List[str] = []
    if chapter_metadata_in:
        meta_inputs = ["-f", "ffmetadata", "-i", chapter_metadata_in]
        meta_map = ["-map_metadata", str(next_index)]

    graph = _long_form_filter_graph(
        fps=fps,
        bg_is_video=bg_is_video,
        subtitles_path=subtitles_path,
        with_url_pill=bool(url_pill_in),
        hook=hook,
        chapter_cards=chapter_cards,
    )
    map_label = "[v]"
    if outro_active and outro_label:
        graph += _outro_overlay_tail(
            outro_label,
            start=max(0.0, total_duration - outro_duration),
            end=total_duration,
        )
        map_label = "[vout]"

    return [
        "ffmpeg", "-y", "-threads", "0",
        *bg_input,
        "-i", audio_in,
        "-loop", "1", "-framerate", str(fps), "-i", brand_in,
        *extra_inputs,
        *meta_inputs,
        "-filter_complex",
        graph,
        "-map", map_label, "-map", "1:a",
        *meta_map,
        *_VIDEO_ENCODE,
        "-r", str(fps),
        *_AUDIO_ENCODE,
        "-shortest",
        "-movflags", "+faststart",
        output,
    ]


def _short_form_cmd(audio_in: str, bg_in: str, brand_in: str,
                    output: str, *,
                    start_offset: float = 0.0,
                    duration: float = 55.0,
                    fps: int = 30,
                    hook: Optional[str] = None,
                    bg_is_video: bool = False,
                    url_pill_in: Optional[str] = None,
                    subtitles_path: Optional[str] = None,
                    end_card: bool = False,
                    end_card_main_text: str = "WATCH FULL EPISODE",
                    end_card_sub_text: str = "Tap Subscribe ↗",
                    end_card_duration: float = 3.0,
                    end_card_image_in: Optional[str] = None,
                    caption_margin_v: Optional[int] = None,
                    bg_loop: bool = True,
                    progress_bar: bool = False) -> List[str]:
    """ffmpeg command for the 1080x1920 Shorts build.

    When *bg_is_video* is True, *bg_in* is a pre-rendered vertical
    slideshow MP4; we ``-stream_loop -1`` it so it loops to match the
    Shorts clip length, and we drop the ``-loop 1 -framerate``
    image-input flags. ``bg_loop=False`` (June 2026 sentence-cut pass)
    drops the ``-stream_loop`` too — used when the slideshow was built
    to the clip's FULL length from explicit scene-change times, so
    looping it would restart the visuals mid-clip.

    When *url_pill_in* is provided, a 4th input is added (the
    ``nerranetwork.com`` URL pill PNG) and overlaid at bottom-center.

    When *subtitles_path* is provided (May 2026), ffmpeg's
    ``subtitles`` filter burns the cues from a Shorts-windowed SRT
    onto the video using the dedicated
    ``_SHORTS_SUBTITLES_FORCE_STYLE`` (FontSize=34, MarginV=300) —
    tuned for the 1080x1920 frame and positioned so it doesn't
    collide with the static hook (0-3 s, y≈1056) or the URL pill
    (y≈1820).
    """
    if bg_is_video:
        if bg_loop:
            bg_input = ["-stream_loop", "-1", "-i", bg_in]
        else:
            bg_input = ["-i", bg_in]
    else:
        bg_input = ["-loop", "1", "-framerate", str(fps), "-i", bg_in]

    extra_inputs: List[str] = []
    # ffmpeg input order is fixed: [0:v] bg, [1:a] audio, [2:v] brand,
    # then optional [3:v] url_pill, then optional [N:v] end_card_image.
    # Compute the end-card image's input index based on what came
    # before it so the filter graph references the right stream.
    next_input_index = 3
    if url_pill_in:
        extra_inputs.extend([
            "-loop", "1", "-framerate", str(fps), "-i", url_pill_in,
        ])
        next_input_index += 1

    end_card_image_input_label: Optional[str] = None
    if end_card and end_card_image_in:
        extra_inputs.extend([
            "-loop", "1", "-framerate", str(fps), "-i", end_card_image_in,
        ])
        end_card_image_input_label = f"[{next_input_index}:v]"

    return [
        "ffmpeg", "-y", "-threads", "0",
        *bg_input,
        "-ss", f"{start_offset:.2f}",
        "-t", f"{duration:.2f}",
        "-i", audio_in,
        "-loop", "1", "-framerate", str(fps), "-i", brand_in,
        *extra_inputs,
        "-filter_complex",
        _short_form_filter_graph(1080, 1920, fps, hook,
                                 bg_is_video=bg_is_video,
                                 with_url_pill=bool(url_pill_in),
                                 subtitles_path=subtitles_path,
                                 end_card=end_card,
                                 end_card_duration=end_card_duration,
                                 total_duration=duration,
                                 end_card_main_text=end_card_main_text,
                                 end_card_sub_text=end_card_sub_text,
                                 end_card_image_input_label=end_card_image_input_label,
                                 caption_margin_v=caption_margin_v,
                                 progress_bar=progress_bar),
        "-map", "[v]", "-map", "1:a",
        *_VIDEO_ENCODE,
        "-r", str(fps),
        *_AUDIO_ENCODE,
        "-shortest",
        "-movflags", "+faststart",
        output,
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_long_form_video(
    audio_path: Path,
    cover_path: Path,
    output_path: Path,
    *,
    fps: int = 30,
    scene_paths: Optional[Sequence[Path]] = None,
    clip_paths: Optional[Sequence[Path]] = None,
    subtitles_path: Optional[Path] = None,
    show_name: Optional[str] = None,
    scene_schedule: Optional[Sequence[Tuple[Path, float]]] = None,
    broll_clips: Optional[Sequence[Path]] = None,
    chapters_path: Optional[Path] = None,
    hook: Optional[str] = None,
    chapter_cards: Optional[Sequence[Tuple[float, str]]] = None,
    outro_card_path: Optional[Path] = None,
    outro_card_duration: float = 6.0,
) -> Path:
    """Render a 1920x1080 long-form podcast video.

    Parameters
    ----------
    audio_path:
        Final mixed episode MP3.
    cover_path:
        Show cover image. Used as the background when ``scene_paths``
        is empty / unset (single-image Ken Burns), or as the fallback
        if slideshow rendering fails.
    output_path:
        Where to write the final MP4.
    fps:
        Frame rate.
    scene_paths:
        Optional list of slideshow images. ``len ≥ 2`` triggers the
        two-stage pipeline (slideshow MP4 first, then composite). A
        single-element list (or ``None``) uses the single-cover path.
    subtitles_path:
        Optional path to an SRT file. When provided, ``ffmpeg``'s
        ``subtitles`` filter burns the cues onto the video using a
        styled box just above the spectrum band.
    show_name:
        Display name of the show (e.g. "Tesla Shorts Time"). When
        provided (May 8 2026): renders TWO branded corner pills — the
        show name in the top-left + ``nerranetwork.com`` in the
        top-right. When ``None``: legacy single "Nerra Network" pill
        in the top-left only. Tests + back-compat callers omit this
        kwarg and keep the legacy behaviour.
    scene_schedule:
        Optional explicit ``[(scene_path, hold_seconds), …]`` plan
        (June 2026 — produced by
        ``engine.scene_scheduler.plan_chapter_schedule`` so scene
        switches land on chapter boundaries). With ≥2 entries the
        slideshow uses these per-scene durations (cumulative xfade
        offsets) instead of the uniform timer; ``None`` (or <2
        entries) keeps the legacy uniform behaviour byte-for-byte.
    broll_clips:
        Optional already-local evergreen 16:9 silent MP4s. Up to
        ``_MAX_BROLL_CLIPS`` (3) are interleaved at roughly even
        positions between the stills via the hybrid renderer;
        any failure degrades to the pure slideshow. Purely a
        consumer of existing files — this never generates clips.
    chapters_path:
        Optional ``chapters_ep<NNN>.json``. When it holds two or more
        chapters, they are written into the MP4 container as a chapter
        track, so Apple's video player can scrub by section and the
        chapters survive a download. Any problem reading it degrades to
        a video with no chapter track.
    hook:
        Optional episode hook (July 31 2026 — B4). When provided, the
        first ~4 s burn an on-screen hook title (autofit at 16:9,
        max 2 lines, alpha fade in/out) so the video's opening carries
        the same hook the cold-open audio speaks. ``None`` keeps the
        legacy title-less opening.
    outro_card_path:
        Optional 1920×1080 site-showcase PNG (Aug 2026 —
        ``engine.promo_card.generate_outro_card``). When provided, it
        fades in over the video's last ``outro_card_duration`` seconds
        (same overlay pattern as the Shorts end card). ``None`` — or a
        failure to read the episode's duration — keeps the legacy
        ending byte-for-byte.

    Returns
    -------
    Path
        ``output_path`` on success.
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"audio not found: {audio_path}")

    # Built before the render branches so both the hybrid and the
    # pure-slideshow paths get the same chapter track.
    chapter_meta: Optional[str] = None
    # Chapter title cards (Sep 2026): derived from the same chapters
    # JSON that powers the seek-bar chapters unless the caller supplied
    # its own list. ``chapter_cards=[]`` disables them explicitly.
    if chapter_cards is None and chapters_path and Path(chapters_path).exists():
        try:
            _raw = json.loads(Path(chapters_path).read_text(encoding="utf-8"))
            _chs = _raw.get("chapters") if isinstance(_raw, dict) else _raw
            chapter_cards = [
                (float(c.get("startTime", c.get("start_time", c.get("start")))),
                 str(c.get("title") or ""))
                for c in (_chs or []) if isinstance(c, dict)
                and c.get("title")
                and c.get("startTime", c.get("start_time", c.get("start"))) is not None
            ]
        except Exception as exc:  # noqa: BLE001 — cards are best-effort
            logger.info("chapter cards skipped (%s)", exc)
            chapter_cards = None
    if chapters_path and Path(chapters_path).exists():
        try:
            from engine.audio import get_audio_duration

            written = write_chapter_metadata(
                Path(chapters_path),
                output_path.with_suffix(".chapters.ffmeta"),
                get_audio_duration(str(audio_path)) or 0.0,
            )
            chapter_meta = str(written) if written else None
        except Exception as exc:  # noqa: BLE001 — chapters are never critical
            logger.warning("Chapter metadata skipped: %s", exc)
    if not cover_path.exists():
        raise FileNotFoundError(f"cover not found: {cover_path}")

    work_dir = output_path.parent
    # Pill cache is path-keyed, so the version lives in the FILENAME.
    # v2/v3 (July 31 2026 — B5): 2x supersampled render + cyan accent;
    # the bumped names force regeneration on persistent work dirs that
    # still hold a stale 1x pill.
    if show_name:
        # Per-show pill — sluggified so different shows get distinct
        # cached PNGs (otherwise the pill from the first show to run
        # on a persistent work dir would be reused for everyone).
        slug = "".join(c if c.isalnum() else "_" for c in show_name.lower()).strip("_")
        brand_path = work_dir / f"_show_pill_v2_{slug}.png"
        _make_show_pill(show_name, brand_path)
        url_pill_path = work_dir / "_url_pill_v2.png"
        _make_url_pill(url_pill_path)
    else:
        brand_path = work_dir / "_brand_pill_v3.png"
        _make_brand_pill(brand_path)
        url_pill_path = None

    # Per-episode Ken Burns seed (A1) — derived from the output stem so
    # a re-render is identical and different episodes de-synchronize.
    kb_seed = _kb_seed_from_stem(output_path.stem)

    # Outro card (Aug 2026 site showcase): resolved once, threaded into
    # every render path below. The overlay's enable window needs the
    # episode's real duration; an unreadable duration disables the card
    # rather than guessing a window.
    outro_in: Optional[str] = None
    outro_total = 0.0
    if outro_card_path and Path(outro_card_path).exists():
        try:
            from engine.audio import get_audio_duration as _outro_gd

            outro_total = float(_outro_gd(str(audio_path)) or 0.0)
        except Exception as exc:  # noqa: BLE001 — card is never critical
            logger.warning("Outro card skipped (duration probe: %s)", exc)
            outro_total = 0.0
        # Require breathing room past the card itself so a very short
        # render can't spend most of its runtime on the outro.
        if outro_total > outro_card_duration + 10.0:
            outro_in = str(outro_card_path)

    # Chapter-aware schedule (June 2026): an explicit per-scene plan wins
    # over the uniform timer. Normalized once so every branch below sees
    # clean (Path, float) pairs; <2 entries keeps legacy behaviour.
    schedule: Optional[List[Tuple[Path, float]]] = None
    if scene_schedule and len(scene_schedule) >= 2:
        schedule = [(Path(p), float(d)) for p, d in scene_schedule]

    bg_path: Path = cover_path
    bg_is_video = False
    if schedule or (scene_paths and len(scene_paths) >= 2):
        slideshow_path = work_dir / f"{output_path.stem}_slides.mp4"
        # Stretch each scene so the slideshow naturally spans the full
        # audio duration. Operator caught (May 8 2026) the previous
        # fixed 12 s/scene behaviour producing a 96 s slideshow that
        # ``-stream_loop -1`` cycled 3-6× across a typical 5-10 min
        # episode — listeners noticed the same eight photos on repeat.
        # Floor at 8 s so a very short episode doesn't whip through
        # scenes; no upper cap (long-form episodes get longer holds
        # which the Ken Burns zoom keeps watchable).
        from engine.audio import get_audio_duration as _get_duration
        try:
            audio_duration_s = _get_duration(str(audio_path)) or 0.0
        except Exception:
            audio_duration_s = 0.0

        # Hybrid path: interleave short video clips among the stills for
        # motion (Phase-4). Best-effort — any failure falls through to the
        # pure-stills slideshow below. ``broll_clips`` (June 2026) feeds
        # the same renderer with already-local evergreen clips, capped at
        # _MAX_BROLL_CLIPS so accents stay accents.
        usable_clips: List[Path] = [
            Path(c) for c in (clip_paths or []) if Path(c).exists()
        ]
        usable_clips.extend(
            Path(c) for c in list(broll_clips or [])[:_MAX_BROLL_CLIPS]
            if Path(c).exists()
        )
        if usable_clips and audio_duration_s > 0:
            try:
                clip_durs: List[float] = []
                for c in usable_clips:
                    try:
                        raw_dur = float(_get_duration(str(c)) or 5.0)
                    except Exception:
                        raw_dur = 5.0
                    # Clamp: a long source file contributes an accent,
                    # not a takeover (see _MAX_BROLL_SEGMENT_S).
                    if raw_dur > _MAX_BROLL_SEGMENT_S:
                        logger.info(
                            "B-roll %s is %.0fs — using its first %.0fs as "
                            "an accent", Path(c).name, raw_dur,
                            _MAX_BROLL_SEGMENT_S)
                        raw_dur = _MAX_BROLL_SEGMENT_S
                    clip_durs.append(raw_dur)
                if schedule:
                    visuals = _interleave_broll_into_schedule(
                        schedule, usable_clips, clip_durs,
                    )
                else:
                    visuals = _build_hybrid_sequence(
                        list(scene_paths), usable_clips, clip_durs,
                        audio_duration_s=audio_duration_s,
                    )
                hybrid_path = work_dir / f"{output_path.stem}_hybrid.mp4"
                _render_hybrid_slideshow(visuals, hybrid_path, fps=fps,
                                         kb_seed=kb_seed)
                bg_path = hybrid_path
                bg_is_video = True
            except subprocess.CalledProcessError as exc:
                logger.warning(
                    "Hybrid (stills+clips) render failed (%s) — falling back "
                    "to pure-stills slideshow", exc,
                )
            except Exception as exc:  # noqa: BLE001 — never block the publish
                logger.warning("Hybrid render error (%s) — using stills", exc)
        if bg_is_video:
            # Hybrid succeeded — skip the pure-stills slideshow render.
            cmd = _long_form_cmd(
                str(audio_path), str(bg_path), str(brand_path),
                str(output_path),
                fps=fps,
                bg_is_video=bg_is_video,
                subtitles_path=str(subtitles_path) if subtitles_path else None,
                url_pill_in=str(url_pill_path) if url_pill_path else None,
                chapter_metadata_in=chapter_meta,
                hook=hook,
                chapter_cards=chapter_cards,
                outro_card_in=outro_in,
                total_duration=outro_total,
                outro_duration=outro_card_duration,
            )
            logger.info(
                "Building long-form video → %s (hybrid clips=%d, captions=%s)",
                output_path.name, len(usable_clips), bool(subtitles_path),
            )
            _run_ffmpeg(cmd, label="long-form video")
            return output_path

        # Single-pass fusion (P1-2). Renders the slideshow and the
        # composite as ONE filter graph, removing a full intermediate
        # encode + decode of a 1080p file that exists only to be
        # consumed seconds later, and with it the last generational
        # loss. Opt-in via NERRA_SINGLE_PASS_RENDER=1 — see
        # _single_pass_long_form_cmd. Only the pure-stills paths qualify;
        # the hybrid clips path above has already produced a real video
        # background and is untouched.
        if _single_pass_enabled():
            sp_scenes, sp_durations, sp_uniform = _single_pass_scene_plan(
                schedule, scene_paths, audio_duration_s,
            )
            if sp_scenes:
                try:
                    cmd = _single_pass_long_form_cmd(
                        sp_scenes, str(audio_path), str(brand_path),
                        str(output_path),
                        scene_duration=sp_uniform,
                        scene_durations=sp_durations,
                        fps=fps,
                        subtitles_path=(
                            str(subtitles_path) if subtitles_path else None),
                        url_pill_in=(
                            str(url_pill_path) if url_pill_path else None),
                        chapter_metadata_in=chapter_meta,
                        hook=hook,
                chapter_cards=chapter_cards,
                        kb_seed=kb_seed,
                        outro_card_in=outro_in,
                        total_duration=outro_total,
                        outro_duration=outro_card_duration,
                    )
                    logger.info(
                        "Building long-form video → %s (SINGLE-PASS, "
                        "scenes=%d, captions=%s)",
                        output_path.name, len(sp_scenes), bool(subtitles_path),
                    )
                    _run_ffmpeg(cmd, label="long-form video (single-pass)")
                    return output_path
                except (subprocess.CalledProcessError, RuntimeError) as exc:
                    # Never lose a render to the new path: fall through to
                    # the proven two-stage pipeline below.
                    logger.warning(
                        "Single-pass render failed (%s) — falling back to "
                        "the two-stage pipeline", exc,
                    )

        if schedule:
            # Chapter-aware plan: the scheduler already decided both the
            # scene ORDER and each scene's hold, so we render the
            # slideshow with per-scene durations (cumulative xfade
            # offsets) instead of the uniform timer. Distinct filename —
            # a persistent work dir may hold a stale uniform render
            # under the legacy name.
            slideshow_path = work_dir / f"{output_path.stem}_slides_sched.mp4"
            try:
                _render_slideshow(
                    [p for p, _ in schedule], slideshow_path,
                    scene_durations=[d for _, d in schedule], fps=fps,
                    kb_seed=kb_seed,
                )
                bg_path = slideshow_path
                bg_is_video = True
            except (subprocess.CalledProcessError, RuntimeError) as exc:
                logger.warning(
                    "Scheduled slideshow render failed (%s) — falling back "
                    "to single cover", exc,
                )
        else:
            # Cycle the scene list so no single image holds longer than
            # _MAX_SCENE_HOLD_S (module constant; June 2026 motion pass lowered
            # it 25 → 15 s). The May 12 retune halved Grok spend to 4
            # images/aspect, which left each scene on screen ~2-3 minutes on a
            # full-length episode (Ep505: 4 scenes over 673 s = 168 s/image) —
            # visually static. Reusing the SAME images in rotation restores
            # visual rhythm at zero additional image cost.
            #
            # Shared with the single-pass path via _uniform_slideshow_plan so
            # the two renderers cannot compute different plans (July 2026).
            slideshow_scenes, scene_duration_s = _uniform_slideshow_plan(
                scene_paths, audio_duration_s,
            )
            try:
                _render_slideshow(
                    slideshow_scenes, slideshow_path,
                    scene_duration=scene_duration_s, fps=fps,
                    kb_seed=kb_seed,
                )
                bg_path = slideshow_path
                bg_is_video = True
            except (subprocess.CalledProcessError, RuntimeError) as exc:
                # _run_ffmpeg raises RuntimeError — catching only
                # CalledProcessError made this documented fallback dead
                # code, so a slideshow failure lost the WHOLE long-form
                # (and the video-podcast episode) instead of shipping
                # the cover render.
                logger.warning(
                    "Slideshow render failed (%s) — falling back to single cover",
                    exc,
                )

    cmd = _long_form_cmd(
        str(audio_path), str(bg_path), str(brand_path),
        str(output_path),
        fps=fps,
        bg_is_video=bg_is_video,
        subtitles_path=str(subtitles_path) if subtitles_path else None,
        url_pill_in=str(url_pill_path) if url_pill_path else None,
        chapter_metadata_in=chapter_meta,
        hook=hook,
                chapter_cards=chapter_cards,
        outro_card_in=outro_in,
        total_duration=outro_total,
        outro_duration=outro_card_duration,
    )
    logger.info("Building long-form video → %s (slideshow=%s, captions=%s)",
                output_path.name, bg_is_video, bool(subtitles_path))
    _run_ffmpeg(cmd, label="long-form video")
    return output_path


def build_short_video(audio_path: Path, cover_path: Path,
                      output_path: Path, *,
                      start_offset: float = 0.0,
                      duration: float = 55.0,
                      fps: int = 30,
                      hook: Optional[str] = None,
                      scene_paths: Optional[Sequence[Path]] = None,
                      show_name: Optional[str] = None,
                      subtitles_path: Optional[Path] = None,
                      end_card: bool = False,
                      end_card_main_text: str = "WATCH FULL EPISODE",
                      end_card_sub_text: str = "Tap Subscribe ↗",
                      end_card_duration: float = 3.0,
                      end_card_image_path: Optional[Path] = None,
                      drop_url_pill: bool = False,
                      caption_margin_v: Optional[int] = None,
                      scene_change_times: Optional[Sequence[float]] = None,
                      clip_paths: Optional[Sequence[Path]] = None,
                      clip_seconds: float = 5.0,
                      kb_extended: bool = True,
                      progress_bar: bool = True) -> Path:
    """Render a 1080x1920 vertical YouTube Shorts video.

    ``drop_url_pill`` / ``caption_margin_v`` support the multi-platform
    "safe-zone" variant: dropping the bottom-centre URL pill and lifting the
    captions (larger MarginV) keeps content clear of the bottom UI band that
    Instagram Reels and TikTok draw over. They default to YouTube behaviour.

    Parameters
    ----------
    audio_path:
        Source audio. Only the slice from *start_offset* to
        *start_offset + duration* is included.
    cover_path:
        Show cover image — used as the static background when
        ``scene_paths`` is empty/unset, or as the fallback if the
        slideshow render fails.
    output_path:
        Where to write the MP4.
    start_offset, duration, fps, hook:
        See module docstring.
    scene_paths:
        Optional list of slideshow images. ``len ≥ 2`` triggers the
        two-stage pipeline (vertical slideshow MP4 first, then
        composite). A single-element list (or ``None``) keeps the
        existing static-cover path.
    show_name:
        Display name of the show. When provided (May 8 2026):
        renders the show name in the top-right pill and a
        ``nerranetwork.com`` pill at bottom-center. When ``None``:
        legacy "Nerra Network" single pill in the top-right.
    subtitles_path:
        Optional SRT (May 2026). Cues must already be windowed and
        rebased to the Shorts clip's own t=0 timeline (see
        ``engine.captions.transcript_to_srt_window``). When
        provided, ffmpeg's ``subtitles`` filter burns the cues
        onto the video with the dedicated
        ``_SHORTS_SUBTITLES_FORCE_STYLE``. The cues sit between the
        static hook (above) and the URL pill (below) so all three
        overlays are visible together without overlap.
    scene_change_times:
        Optional scene-cut times in seconds RELATIVE to the clip start
        (June 2026 — produced by
        ``engine.scene_scheduler.sentence_cut_times`` so background
        changes land between sentences instead of on the flat 7 s
        grid). When provided with ≥2 scene images, the vertical
        slideshow is built to the clip's FULL length with those
        per-segment durations and the composite drops the
        ``-stream_loop`` (looping a full-length background would
        restart the visuals mid-clip). ``None`` keeps the legacy
        flat-pace loop path unchanged.
    clip_paths:
        Optional generated video clips (July 2026 — the Shorts motion
        A/B, see :mod:`engine.shorts_ab`). When two or more are given
        they become the background: the clips are interleaved with the
        still scenes into ONE full-length 1080x1920 hybrid via
        :func:`_render_hybrid_slideshow`, so the Short opens on motion
        and cuts back to stills between clips instead of looping four
        seconds of video for the whole 35 s. Falls through to the
        stills path on any render failure — the Short always ships.
    clip_seconds:
        Nominal seconds of each entry in *clip_paths*; the real
        duration is measured per file and this is only the fallback
        when a probe fails.
    kb_extended:
        Ken Burns vocabulary gate (July 31 2026 — A1). ``True``
        (default) uses the widened 8-move / 3-amplitude, per-episode-
        seeded motion. ``False`` pins the legacy 4-move / 1.09
        behaviour byte-for-byte — run_show passes
        ``kb_extended=not shorts_ab.is_enabled(config)`` so a show
        running the Shorts motion A/B does not have its CONTROL arm
        upgraded mid-experiment (which would bias the test toward
        "motion isn't worth paying for").
    """
    if duration >= 60:
        raise ValueError(
            f"Shorts duration must stay below 60s; got {duration}"
        )
    if not audio_path.exists():
        raise FileNotFoundError(f"audio not found: {audio_path}")
    if not cover_path.exists():
        raise FileNotFoundError(f"cover not found: {cover_path}")

    work_dir = output_path.parent
    # Per-episode Ken Burns seed (A1) — per-Short stems (_short_1/_2)
    # de-synchronize the two Shorts of one episode too.
    kb_seed = _kb_seed_from_stem(output_path.stem)
    if show_name:
        slug = "".join(c if c.isalnum() else "_" for c in show_name.lower()).strip("_")
        brand_path = work_dir / f"_show_pill_v2_{slug}.png"
        _make_show_pill(show_name, brand_path)
        url_pill_path = work_dir / "_url_pill_v2.png"
        _make_url_pill(url_pill_path)
        if drop_url_pill:
            # Social safe-zone variant: keep the top brand pill, drop the
            # bottom-centre URL pill (the caption carries the link, and the
            # bottom band is covered by IG/TikTok UI anyway).
            url_pill_path = None
    else:
        brand_path = work_dir / "_brand_pill_v3.png"
        _make_brand_pill(brand_path)
        url_pill_path = None

    bg_path: Path = cover_path
    bg_is_video = False
    bg_full_length = False

    # ---- Motion A/B treatment arm: generated video clips + stills ----
    # Runs BEFORE the stills paths so a successful hybrid wins, and
    # falls straight through to them on any failure.
    usable_clips = [Path(p) for p in (clip_paths or [])]
    usable_clips = [p for p in usable_clips if p.exists()]
    if len(usable_clips) >= 2:
        try:
            visuals = _build_short_hybrid_sequence(
                list(scene_paths or []) or [cover_path],
                usable_clips,
                duration=duration,
                nominal_clip_seconds=clip_seconds,
            )
            hybrid_path = work_dir / f"{output_path.stem}_short_hybrid.mp4"
            _render_hybrid_slideshow(
                visuals, hybrid_path, width=1080, height=1920, fps=fps,
                kb_seed=kb_seed, kb_extended=kb_extended,
            )
            bg_path = hybrid_path
            bg_is_video = True
            bg_full_length = True
        except Exception as exc:  # noqa: BLE001 — never lose the Short
            logger.warning(
                "Shorts hybrid (clips) render failed (%s) — falling back "
                "to the stills background", exc,
            )
            bg_is_video = False
            bg_full_length = False
            bg_path = cover_path

    if not bg_is_video and scene_paths and len(scene_paths) >= 2:
        if scene_change_times:
            # Sentence-snapped cuts (June 2026): build the vertical
            # slideshow to the clip's FULL length with per-segment
            # durations — no -stream_loop needed downstream. Scenes
            # rotate through the pool per segment, mirroring the flat
            # path's cycling. Any failure falls through to the legacy
            # flat-pace loop below.
            seg_durations = _short_segment_durations(
                scene_change_times, duration,
            )
            if seg_durations:
                seg_scenes = [
                    scene_paths[i % len(scene_paths)]
                    for i in range(len(seg_durations))
                ]
                slideshow_path = (
                    work_dir / f"{output_path.stem}_short_slides_sched.mp4"
                )
                try:
                    _render_slideshow(
                        seg_scenes, slideshow_path,
                        scene_durations=seg_durations,
                        width=1080, height=1920, fps=fps,
                        kb_seed=kb_seed, kb_extended=kb_extended,
                        crossfade=_SHORTS_XFADE_S,
                    )
                    bg_path = slideshow_path
                    bg_is_video = True
                    bg_full_length = True
                except (subprocess.CalledProcessError, RuntimeError) as exc:
                    logger.warning(
                        "Scheduled Shorts slideshow render failed (%s) — "
                        "falling back to the flat %.0fs pace",
                        exc, _SHORT_SCENE_DURATION_SECONDS,
                    )
        if not bg_is_video:
            slideshow_path = work_dir / f"{output_path.stem}_short_slides.mp4"
            try:
                _render_slideshow(
                    scene_paths, slideshow_path,
                    scene_duration=_SHORT_SCENE_DURATION_SECONDS,
                    width=1080, height=1920, fps=fps,
                    kb_seed=kb_seed, kb_extended=kb_extended,
                    crossfade=_SHORTS_XFADE_S,
                )
                bg_path = slideshow_path
                bg_is_video = True
            except (subprocess.CalledProcessError, RuntimeError) as exc:
                # Same dead-fallback shape as the long-form path above:
                # _run_ffmpeg raises RuntimeError.
                logger.warning(
                    "Shorts slideshow render failed (%s) — falling back to cover",
                    exc,
                )

    cmd = _short_form_cmd(
        str(audio_path), str(bg_path), str(brand_path),
        str(output_path),
        start_offset=start_offset,
        duration=duration, fps=fps, hook=hook,
        bg_is_video=bg_is_video,
        url_pill_in=str(url_pill_path) if url_pill_path else None,
        subtitles_path=str(subtitles_path) if subtitles_path else None,
        end_card=end_card,
        end_card_main_text=end_card_main_text,
        end_card_sub_text=end_card_sub_text,
        end_card_duration=end_card_duration,
        end_card_image_in=(
            str(end_card_image_path)
            if end_card_image_path and Path(end_card_image_path).exists()
            else None
        ),
        caption_margin_v=caption_margin_v,
        bg_loop=not bg_full_length,
        progress_bar=progress_bar,
    )
    logger.info(
        "Building Shorts video (%.1fs from %.1fs) → %s "
        "(subtitles=%s, end_card=%s)",
        duration, start_offset, output_path.name,
        bool(subtitles_path), end_card,
    )
    _run_ffmpeg(cmd, label="shorts video")
    return output_path
