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

import logging
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)


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


def _make_brand_pill(output_path: Path,
                     *, text: str = _BRAND_PILL_TEXT,
                     width: int = 220, height: int = 60) -> Path:
    """Render a rounded-rect brand pill as an RGBA PNG. Idempotent.

    *text* is the displayed string. Width auto-fits via font shrink
    (font tries 30 → 12 px until the text fits with a 32 px side
    margin). Show names up to ~30 chars fit comfortably at the
    default 220 × 60; longer names get the smaller font, still
    legible against the cover background.
    """
    if output_path.exists():
        return output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = height // 2
    draw.rounded_rectangle(
        [(0, 0), (width - 1, height - 1)],
        radius=radius,
        fill=(0, 0, 0, 140),
    )

    font_path = _find_font()
    font = None
    # Wider top range than legacy (was 22 → 12) to accommodate longer
    # show names that previously got clamped to the smallest font even
    # when more horizontal room was available.
    for size in range(28, 11, -1):
        try:
            candidate = ImageFont.truetype(font_path, size)
        except (IOError, OSError):
            continue
        bbox = candidate.getbbox(text)
        if bbox[2] - bbox[0] <= width - 32:
            font = candidate
            break
    if font is None:
        font = ImageFont.load_default()

    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width - text_w) // 2 - bbox[0]
    y = (height - text_h) // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 235))

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


def _slideshow_filter_graph(scene_count: int, *,
                            scene_duration: float = _SCENE_DURATION_SECONDS,
                            width: int = 1920, height: int = 1080,
                            fps: int = 30) -> str:
    """Build the filter_complex for a Ken Burns slideshow with hard cuts.

    Each scene gets a 1.00 → 1.12 zoom over its window. Hard cuts
    between scenes (no crossfade) — the spectrum + brand pill + caption
    motion in stage 2 hides any visual jump.
    """
    pre_w = int(width * 1.15)
    pre_h = int(height * 1.15)
    zoom_expr = "min(zoom+0.0006,1.12)"
    frames_per_scene = int(scene_duration * fps)

    chains: List[str] = []
    for i in range(scene_count):
        chains.append(
            f"[{i}:v]"
            f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase,"
            f"crop={pre_w}:{pre_h},setsar=1,"
            f"zoompan=z='{zoom_expr}':d={frames_per_scene}"
            f":s={width}x{height}:fps={fps},"
            f"trim=duration={scene_duration:.2f},setpts=PTS-STARTPTS"
            f"[s{i}]"
        )
    concat_in = "".join(f"[s{i}]" for i in range(scene_count))
    chains.append(f"{concat_in}concat=n={scene_count}:v=1:a=0[v]")
    return ";".join(chains)


def _slideshow_cmd(scene_paths: Sequence[Path], output: Path,
                   *, scene_duration: float = _SCENE_DURATION_SECONDS,
                   width: int = 1920, height: int = 1080,
                   fps: int = 30) -> List[str]:
    """ffmpeg command for stage 1 (slideshow render).

    *width* and *height* default to 1920x1080 for the long-form path;
    pass 1080x1920 for the vertical Shorts variant.
    """
    inputs: List[str] = []
    for path in scene_paths:
        inputs.extend([
            "-loop", "1",
            "-framerate", str(fps),
            "-t", f"{scene_duration + 0.5:.2f}",
            "-i", str(path),
        ])
    return [
        "ffmpeg", "-y", "-threads", "0",
        *inputs,
        "-filter_complex",
        _slideshow_filter_graph(len(scene_paths),
                                scene_duration=scene_duration,
                                width=width, height=height, fps=fps),
        "-map", "[v]",
        "-r", str(fps),
        *_VIDEO_ENCODE,
        "-an",
        "-movflags", "+faststart",
        str(output),
    ]


def _render_slideshow(scene_paths: Sequence[Path], output: Path,
                      *, scene_duration: float = _SCENE_DURATION_SECONDS,
                      width: int = 1920, height: int = 1080,
                      fps: int = 30) -> Path:
    """Render the stage-1 slideshow MP4. Idempotent (skips if output exists)."""
    if output.exists():
        return output
    cmd = _slideshow_cmd(scene_paths, output,
                         scene_duration=scene_duration,
                         width=width, height=height, fps=fps)
    logger.info("Rendering slideshow (%d scenes, %dx%d) → %s",
                len(scene_paths), width, height, output.name)
    _run_ffmpeg(cmd, label="slideshow render")
    return output


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
_SUBTITLES_FORCE_STYLE = (
    "FontName=DejaVu Sans,"
    "FontSize=22,"
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


def _long_form_filter_graph(*, width: int = 1920, height: int = 1080,
                            fps: int = 30,
                            bg_is_video: bool = False,
                            subtitles_path: Optional[str] = None,
                            with_url_pill: bool = False) -> str:
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
        # Slideshow MP4 already has motion + zoom; just normalize to
        # the target frame and fps.
        bg_chain = (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,format=yuv420p[bg]"
        )
    else:
        pre_w = int(width * 1.15)
        pre_h = int(height * 1.15)
        zoom_expr = "min(zoom+0.000004,1.08)"
        bg_chain = (
            f"[0:v]"
            f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase,"
            f"crop={pre_w}:{pre_h},setsar=1,"
            f"zoompan=z='{zoom_expr}':d=1:s={width}x{height}:fps={fps}"
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

    if subtitles_path:
        escaped = _subtitles_path_escape(subtitles_path)
        graph += (
            f";{post_brand_label}subtitles='{escaped}'"
            f":force_style='{_SUBTITLES_FORCE_STYLE}'[v]"
        )
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
                             end_card_sub_text: str = "Tap Subscribe ↗") -> str:
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

    bg_chain = (
        f"[0:v]"
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,format=yuv420p[bg]"
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

    # Anchor for any post-brand overlay (hook caption + burn-in
    # subtitles + the final ``[v]`` rename). We chain by reassigning
    # ``post_brand_label`` after each step so the order is:
    #   brand pill → URL pill → hook (0-3s) → burn-in subtitles → [v]
    chain = base
    if hook:
        wrapped = _wrap_caption(hook)
        escaped = _drawtext_escape(wrapped)
        # May 2026 operator review: hook is the static 0-3 s
        # opening title — separate from the burn-in transcript
        # that follows. Position lifted ABOVE the burn-in zone
        # so the two overlays don't visually collide during the
        # first 3 s. ``y=h*0.55`` puts the hook around y≈1056 —
        # inside the lower half but well above the subtitle
        # baseline at y≈1620 (MarginV=300 in
        # ``_SHORTS_SUBTITLES_FORCE_STYLE``).
        #   * ``fontsize=44`` is still readable on a phone but
        #     no longer dominates the slideshow.
        #   * Outline-only (no ``box=1`` solid fill) keeps the
        #     imagery visible behind the words. A 4 px black
        #     outline + 2 px shadow stays readable on bright
        #     backgrounds without painting a black rectangle.
        hook_label = "[hooked]" if subtitles_path else "[v]"
        hook_filter = (
            f";{post_brand_label}drawtext=fontfile='{font_path}':"
            f"text='{escaped}':"
            f"fontsize=44:fontcolor=white:"
            f"x=(w-text_w)/2:y=h*0.55:"
            f"borderw=4:bordercolor=black:"
            f"shadowx=2:shadowy=2:shadowcolor=black@0.7:"
            f"line_spacing=10:"
            f"enable='between(t,0,3)'"
            f"{hook_label}"
        )
        chain += hook_filter
        post_brand_label = hook_label

    if subtitles_path:
        escaped_sub = _subtitles_path_escape(subtitles_path)
        # Use the dedicated Shorts force-style so font + position
        # are tuned for the 1080x1920 vertical frame and don't
        # overlap the hook (above) or the URL pill (below).
        sub_label = "[capted]" if end_card else "[v]"
        chain += (
            f";{post_brand_label}subtitles='{escaped_sub}'"
            f":force_style='{_SHORTS_SUBTITLES_FORCE_STYLE}'{sub_label}"
        )
        post_brand_label = sub_label
        if not end_card:
            return chain
    elif hook and not end_card:
        # Hook was the last filter — already terminated at [v].
        return chain

    if end_card:
        # Last-3-seconds CTA card. Three stacked overlays bound to a
        # single enable window so the layer is atomic — either all
        # three render (between t=END-3 and t=END) or none do.
        #
        #   1. ``drawbox`` paints a full-frame translucent black panel
        #      to wipe the slideshow + captions, focusing attention.
        #   2. ``drawtext`` for the headline ("WATCH FULL EPISODE")
        #      sits centred slightly above mid-frame.
        #   3. ``drawtext`` for the sub-line ("Tap Subscribe ↗") sits
        #      under the headline, pointing the viewer at YouTube's
        #      own subscribe button on the right rail of the Shorts
        #      player.
        #
        # Why drawbox / drawtext rather than a composited PNG: zero
        # filesystem dependency (no new asset to generate per-episode),
        # the text is parameterisable per-show via YAML, and the
        # filter chain stays self-contained. A PNG end-card with the
        # long-form thumbnail is a worthwhile follow-up but adds an
        # asset-generation step that ffmpeg doesn't need today.
        font_path = _drawtext_escape(_find_font())
        if total_duration <= end_card_duration:
            # Degenerate case: clip shorter than the end card. Run
            # the card for the whole clip.
            end_card_start = 0.0
        else:
            end_card_start = max(0.0, total_duration - end_card_duration)
        end_card_end = total_duration
        enable_clause = (
            f"between(t,{end_card_start:.2f},{end_card_end:.2f})"
        )
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
            f"enable='{enable_clause}'"
            # 3. Sub-line — smaller, accent colour (cyan, matches
            # the per-word caption highlight from the previous PR).
            f",drawtext=fontfile='{font_path}':"
            f"text='{escaped_sub}':"
            f"fontsize=56:fontcolor=0x00D4FF:"
            f"x=(w-text_w)/2:y=(h+text_h)/2+40:"
            f"borderw=3:bordercolor=black:"
            f"enable='{enable_clause}'"
            f"[v]"
        )
        return chain

    return chain + f";{post_brand_label}null[v]"


# ---------------------------------------------------------------------------
# Long-form command builder (stage 2)
# ---------------------------------------------------------------------------

def _long_form_cmd(audio_in: str, bg_in: str, brand_in: str,
                   output: str, *,
                   fps: int = 30,
                   bg_is_video: bool = False,
                   subtitles_path: Optional[str] = None,
                   url_pill_in: Optional[str] = None) -> List[str]:
    """Full ffmpeg command for stage 2.

    When *bg_is_video* is True, *bg_in* is a pre-rendered slideshow
    MP4; we ``-stream_loop -1`` it so it loops to match the audio
    length, and we don't apply ``-loop 1 -framerate``.

    When *url_pill_in* is provided, a 4th input (the
    ``nerranetwork.com`` URL pill) is added as input ``[3:v]`` and
    overlaid in the filter graph at the top-right corner.
    """
    if bg_is_video:
        bg_input = ["-stream_loop", "-1", "-i", bg_in]
    else:
        bg_input = ["-loop", "1", "-framerate", str(fps), "-i", bg_in]

    extra_inputs: List[str] = []
    if url_pill_in:
        extra_inputs = [
            "-loop", "1", "-framerate", str(fps), "-i", url_pill_in,
        ]

    return [
        "ffmpeg", "-y", "-threads", "0",
        *bg_input,
        "-i", audio_in,
        "-loop", "1", "-framerate", str(fps), "-i", brand_in,
        *extra_inputs,
        "-filter_complex",
        _long_form_filter_graph(
            fps=fps,
            bg_is_video=bg_is_video,
            subtitles_path=subtitles_path,
            with_url_pill=bool(url_pill_in),
        ),
        "-map", "[v]", "-map", "1:a",
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
                    end_card_duration: float = 3.0) -> List[str]:
    """ffmpeg command for the 1080x1920 Shorts build.

    When *bg_is_video* is True, *bg_in* is a pre-rendered vertical
    slideshow MP4; we ``-stream_loop -1`` it so it loops to match the
    Shorts clip length, and we drop the ``-loop 1 -framerate``
    image-input flags.

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
        bg_input = ["-stream_loop", "-1", "-i", bg_in]
    else:
        bg_input = ["-loop", "1", "-framerate", str(fps), "-i", bg_in]

    extra_inputs: List[str] = []
    if url_pill_in:
        extra_inputs = [
            "-loop", "1", "-framerate", str(fps), "-i", url_pill_in,
        ]

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
                                 end_card_sub_text=end_card_sub_text),
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
    subtitles_path: Optional[Path] = None,
    show_name: Optional[str] = None,
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

    Returns
    -------
    Path
        ``output_path`` on success.
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"audio not found: {audio_path}")
    if not cover_path.exists():
        raise FileNotFoundError(f"cover not found: {cover_path}")

    work_dir = output_path.parent
    # Bumped filename when the pill text changed (was
    # "Nerra Network · AI-narrated", now per-show name). The new
    # filename forces regeneration even on persistent work dirs that
    # still hold an old cached pill.
    if show_name:
        # Per-show pill — sluggified so different shows get distinct
        # cached PNGs (otherwise the pill from the first show to run
        # on a persistent work dir would be reused for everyone).
        slug = "".join(c if c.isalnum() else "_" for c in show_name.lower()).strip("_")
        brand_path = work_dir / f"_show_pill_{slug}.png"
        _make_show_pill(show_name, brand_path)
        url_pill_path = work_dir / "_url_pill_v1.png"
        _make_url_pill(url_pill_path)
    else:
        brand_path = work_dir / "_brand_pill_v2.png"
        _make_brand_pill(brand_path)
        url_pill_path = None

    bg_path: Path = cover_path
    bg_is_video = False
    if scene_paths and len(scene_paths) >= 2:
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
        if audio_duration_s > 0:
            scene_duration_s = max(8.0, audio_duration_s / len(scene_paths))
        else:
            scene_duration_s = _SCENE_DURATION_SECONDS  # legacy 12 s
        try:
            _render_slideshow(
                scene_paths, slideshow_path,
                scene_duration=scene_duration_s, fps=fps,
            )
            bg_path = slideshow_path
            bg_is_video = True
        except subprocess.CalledProcessError as exc:
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
                      end_card_duration: float = 3.0) -> Path:
    """Render a 1080x1920 vertical YouTube Shorts video.

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
    if show_name:
        slug = "".join(c if c.isalnum() else "_" for c in show_name.lower()).strip("_")
        brand_path = work_dir / f"_show_pill_{slug}.png"
        _make_show_pill(show_name, brand_path)
        url_pill_path = work_dir / "_url_pill_v1.png"
        _make_url_pill(url_pill_path)
    else:
        brand_path = work_dir / "_brand_pill_v2.png"
        _make_brand_pill(brand_path)
        url_pill_path = None

    bg_path: Path = cover_path
    bg_is_video = False
    if scene_paths and len(scene_paths) >= 2:
        slideshow_path = work_dir / f"{output_path.stem}_short_slides.mp4"
        try:
            _render_slideshow(
                scene_paths, slideshow_path,
                scene_duration=_SHORT_SCENE_DURATION_SECONDS,
                width=1080, height=1920, fps=fps,
            )
            bg_path = slideshow_path
            bg_is_video = True
        except subprocess.CalledProcessError as exc:
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
    )
    logger.info(
        "Building Shorts video (%.1fs from %.1fs) → %s "
        "(subtitles=%s, end_card=%s)",
        duration, start_offset, output_path.name,
        bool(subtitles_path), end_card,
    )
    _run_ffmpeg(cmd, label="shorts video")
    return output_path
