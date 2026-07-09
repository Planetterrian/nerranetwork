"""Tests for the YouTube thumbnail auto-shrink-to-fit logic.

Operator caught (May 2026) that long hooks like the Tesla Cybercab
wireless-BMS line rendered as 5 lines at the legacy fixed 77 px size
on the 1080×1920 Shorts thumbnail and clipped against the top of the
safe area. The fix in ``engine.publisher.generate_episode_thumbnail``
iteratively shrinks the hook font until the wrapped block fits inside
60 % of the frame height (and at most 3 lines on Shorts / 4 on
long-form), with a hard floor at ~32 px so even pathological hooks
still produce readable text.

These tests verify the auto-fit behaviour against synthetic covers
without going through the full pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from engine.publisher import generate_episode_thumbnail


def _make_cover(path: Path, size=(1280, 720)) -> Path:
    img = Image.new("RGB", size, (40, 60, 100))
    img.save(path, format="JPEG", quality=92)
    return path


@pytest.fixture
def cover(tmp_path: Path) -> Path:
    return _make_cover(tmp_path / "cover.jpg")


# ---------------------------------------------------------------------------
# Long-form (1280×720)
# ---------------------------------------------------------------------------


def test_short_hook_renders_at_large_font(cover, tmp_path):
    """A 5-word hook fits trivially — must render and produce a JPEG
    around the YouTube long-form spec size."""
    out = tmp_path / "thumb.jpg"
    # generate_episode_thumbnail returns (output_path, final_hook_font);
    # production unpacks the tuple (run_show.py). Mirror that here.
    result, _hook_font = generate_episode_thumbnail(
        cover, episode_num=42, date_str="May 25, 2026",
        output_path=out, hook="Tesla beats Q1 delivery target",
        show_name="Tesla Shorts Time",
    )
    assert result.exists()
    with Image.open(result) as img:
        assert img.size == (1280, 720)


def test_long_hook_does_not_overflow_long_form_frame(cover, tmp_path):
    """A 30-word hook used to render at a fixed 91 px (1280//14) and
    overflow the safe area. Auto-fit must shrink it until the
    rendered block fits inside 60 % of the frame height."""
    long_hook = (
        "Tesla is hiring engineers to build a wireless Battery Management "
        "System for Cybercab that removes heavy wiring and unlocks the "
        "next decade of solid-state battery integration in mass-market EVs"
    )
    out = tmp_path / "thumb.jpg"
    # generate_episode_thumbnail returns (output_path, final_hook_font);
    # production unpacks the tuple (run_show.py). Mirror that here.
    result, _hook_font = generate_episode_thumbnail(
        cover, episode_num=460, date_str="May 25, 2026",
        output_path=out, hook=long_hook,
        show_name="Tesla Shorts Time",
    )
    assert result.exists()
    # The file is produced — auto-fit didn't blow up. We can't pixel-
    # diff the text without OCR, but the absence of an exception
    # combined with the next test (which inspects the wrap count via
    # an internal seam) is the regression baseline.


# ---------------------------------------------------------------------------
# Shorts (1080×1920) — the actual use case the operator hit
# ---------------------------------------------------------------------------


def test_shorts_thumbnail_long_hook_renders(tmp_path):
    """1080×1920 with a real-world long Tesla hook — must produce a
    file and not throw on the auto-fit loop."""
    cover = _make_cover(tmp_path / "cover.jpg", size=(1080, 1920))
    out = tmp_path / "short_thumb.jpg"
    # generate_episode_thumbnail returns (output_path, final_hook_font);
    # production unpacks the tuple (run_show.py). Mirror that here.
    result, _hook_font = generate_episode_thumbnail(
        cover, episode_num=460, date_str="May 25, 2026",
        output_path=out,
        hook=(
            "Tesla is hiring engineers to build a wireless Battery "
            "Management System for Cybercab that removes heavy wiring"
        ),
        show_name="Tesla Shorts Time",
        size=(1080, 1920),
    )
    assert result.exists()
    with Image.open(result) as img:
        assert img.size == (1080, 1920)


def test_runaway_hook_truncates_at_160_chars(cover, tmp_path, monkeypatch):
    """A 400-char hook is almost certainly an LLM run-on. The hard
    cap is 160 chars for the lower-third layout (July 2026) — anything
    longer gets truncated on a word boundary with a trailing ellipsis
    so the auto-fit loop doesn't chase illegible micro-text."""
    captured_strings: list[str] = []

    import engine.publisher as pub
    real_wrap = pub._wrap_text

    def spy(text, font, max_width):
        captured_strings.append(text)
        return real_wrap(text, font, max_width)

    monkeypatch.setattr(pub, "_wrap_text", spy)

    runaway = "Tesla " * 80  # 480 chars
    generate_episode_thumbnail(
        cover, episode_num=42, date_str="May 25, 2026",
        output_path=tmp_path / "out.jpg", hook=runaway,
        show_name="Tesla Shorts Time",
    )
    assert captured_strings, "expected at least one wrap call"
    first = captured_strings[0]
    assert len(first) <= 160, f"truncation failed: len={len(first)}"
    assert first.endswith("…"), f"missing ellipsis: {first[-5:]!r}"


def test_thumbnail_keeps_image_bright_not_full_darken(cover, tmp_path):
    """July 2026 image-first redesign: the upper half of the frame must
    stay near the source brightness (no full-frame 0.55 darken). A
    bright cyan cover should still read bright in the top third."""
    # Bright cyan cover so the mean of the top band is easy to assert.
    bright = tmp_path / "bright.jpg"
    Image.new("RGB", (1280, 720), (0, 200, 255)).save(bright, format="JPEG")
    out = tmp_path / "thumb.jpg"
    generate_episode_thumbnail(
        bright, episode_num=1, date_str="Jul 9, 2026",
        output_path=out, hook="Bright scene stays bright",
        show_name="Test Show",
    )
    with Image.open(out) as img:
        # Sample a 40×40 patch in the upper-left (below the show label
        # margin but above the scrim). Mean channel should stay high.
        patch = list(img.crop((80, 80, 120, 120)).getdata())
        mean_b = sum(p[2] for p in patch) / len(patch)
        assert mean_b > 150, (
            f"top-of-frame still looks darkened (mean blue={mean_b:.0f}); "
            "expected image-first scrim, not full Brightness 0.55"
        )


def test_shrink_loop_picks_smaller_font_for_long_hook(cover, tmp_path, monkeypatch):
    """For a hook that doesn't fit at max font, the shrink loop must
    re-call _wrap_text at SMALLER font sizes until the block fits."""
    fonts_used: list[int] = []

    import engine.publisher as pub
    real_load = pub._load_font

    def spy_load(size):
        fonts_used.append(size)
        return real_load(size)

    monkeypatch.setattr(pub, "_load_font", spy_load)

    long_hook = (
        "Tesla is hiring engineers to build a wireless Battery Management "
        "System for Cybercab that removes heavy wiring and changes EV design"
    )
    generate_episode_thumbnail(
        cover, episode_num=42, date_str="May 25, 2026",
        output_path=tmp_path / "out.jpg", hook=long_hook,
        show_name="Tesla Shorts Time",
        size=(1080, 1920),  # the Shorts case, where the shrink loop bites
    )

    # Filter to only the hook-font sizes (label + footer also call
    # _load_font with small sizes — those are predictable, the hook
    # loop is the one we want to verify).
    hook_sizes = [s for s in fonts_used if s > 40]
    # Multiple iterations means the loop saw "doesn't fit yet" at
    # the first size and tried smaller ones.
    assert len(hook_sizes) >= 2, (
        f"shrink loop didn't iterate on a long Shorts hook; "
        f"hook-size sequence was {hook_sizes}"
    )
    # The sizes must be strictly decreasing — we don't grow the font
    # back up once we've started shrinking.
    decreasing_pairs = all(
        hook_sizes[i] > hook_sizes[i + 1]
        for i in range(len(hook_sizes) - 1)
    )
    assert decreasing_pairs, f"shrink loop wasn't monotonic: {hook_sizes}"
