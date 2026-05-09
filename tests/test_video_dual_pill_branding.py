"""Tests for the May 8 2026 dual-pill corner branding feature.

Operator asked for show-name + nerranetwork.com branding visible in
opposite corners of every YouTube video so listeners always see who
they're watching and where to find the network. Pre-feature behaviour:
a single generic ``Nerra Network`` pill in one corner.

The feature is opt-in via ``show_name=`` on ``build_long_form_video``
and ``build_short_video`` — when omitted, the legacy single-pill
behaviour is preserved (existing tests pass unchanged).

These tests pin:

  1. ``_make_brand_pill(text=…)`` accepts custom text (per-show pill).
  2. ``_make_show_pill`` and ``_make_url_pill`` are wrappers that
     render the show-specific and ``nerranetwork.com`` pills.
  3. Filter graphs gain an optional ``with_url_pill`` flag that adds
     a ``[3:v]`` URL-pill overlay at top-right (long-form) / bottom-
     center (Shorts).
  4. Command builders gain ``url_pill_in=`` that adds a 4th input
     and propagates the filter-graph flag.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.video import (
    _long_form_cmd,
    _long_form_filter_graph,
    _make_brand_pill,
    _make_show_pill,
    _make_url_pill,
    _short_form_cmd,
    _short_form_filter_graph,
)


# ---------------------------------------------------------------------------
# Pill PNG generation
# ---------------------------------------------------------------------------


class TestPillGeneration:

    def test_brand_pill_accepts_custom_text(self, tmp_path):
        """Operator's per-show branding flow needs ``_make_brand_pill``
        to render any caller-supplied text, not just the legacy
        hardcoded "Nerra Network"."""
        out = tmp_path / "tesla_pill.png"
        _make_brand_pill(out, text="Tesla Shorts Time", width=320, height=60)
        assert out.exists()
        # Open the PNG and check basic shape.
        from PIL import Image
        img = Image.open(out)
        assert img.size == (320, 60)
        assert img.mode == "RGBA"

    def test_brand_pill_default_text_is_nerra_network(self, tmp_path):
        """Backward compat: legacy callers omit ``text`` and get
        "Nerra Network" as before."""
        out = tmp_path / "default_pill.png"
        _make_brand_pill(out)
        assert out.exists()

    def test_show_pill_uses_default_wider_size(self, tmp_path):
        """``_make_show_pill`` defaults to 320 px wide so longer show
        names like "Models & Agents for Beginners" fit at a readable
        font size."""
        out = tmp_path / "mab_pill.png"
        _make_show_pill("Models & Agents for Beginners", out)
        from PIL import Image
        img = Image.open(out)
        assert img.size == (320, 60)

    def test_url_pill_renders(self, tmp_path):
        """``_make_url_pill`` renders the canonical
        ``nerranetwork.com`` branding pill."""
        out = tmp_path / "url_pill.png"
        _make_url_pill(out)
        from PIL import Image
        img = Image.open(out)
        assert img.size == (260, 60)
        assert img.mode == "RGBA"


# ---------------------------------------------------------------------------
# Filter graph — with_url_pill flag
# ---------------------------------------------------------------------------


class TestLongFormFilterGraphWithUrlPill:

    def test_default_no_url_pill(self):
        """Backward compat: no ``with_url_pill`` flag → no [3:v]
        overlay — existing tests + production callers without
        ``show_name`` keep their single-pill rendering."""
        graph = _long_form_filter_graph()
        assert "[3:v]" not in graph
        # Single brand overlay only.
        assert graph.count("overlay=") == 1

    def test_with_url_pill_adds_top_right_overlay(self):
        """``with_url_pill=True`` adds a [3:v] URL pill overlay at
        top-right (x=W-w-24:y=24) so the long-form video has both
        the show pill (top-left) and the nerranetwork.com pill
        (top-right) visible."""
        graph = _long_form_filter_graph(with_url_pill=True)
        assert "[3:v]" in graph
        # Top-left show pill stays at x=24:y=24.
        assert "overlay=x=24:y=24" in graph
        # Top-right URL pill at x=W-w-24:y=24.
        assert "overlay=x=W-w-24:y=24" in graph
        # Two overlays total.
        assert graph.count("overlay=") == 2
        # Final output label is still [v].
        assert graph.endswith("[v]")


class TestShortFormFilterGraphWithUrlPill:

    def test_default_no_url_pill(self):
        graph = _short_form_filter_graph()
        assert "[3:v]" not in graph
        assert graph.count("overlay=") == 1

    def test_with_url_pill_adds_bottom_center_overlay(self):
        """For 9:16 Shorts the URL pill goes bottom-center (top is
        the show pill, middle is the hook caption for the first 3 s,
        so bottom is the only clear corner). Anchored at
        ``x=(W-w)/2:y=H-h-100``."""
        graph = _short_form_filter_graph(with_url_pill=True)
        assert "[3:v]" in graph
        # Top-right show pill stays at x=W-w-24:y=24.
        assert "overlay=x=W-w-24:y=24" in graph
        # Bottom-center URL pill.
        assert "overlay=x=(W-w)/2:y=H-h-100" in graph
        assert graph.count("overlay=") == 2

    def test_with_url_pill_and_hook_both_render(self):
        """Hook caption + URL pill must coexist — caption comes after
        the URL pill in the filter chain so the [stamped] label
        carries through."""
        graph = _short_form_filter_graph(
            hook="Tesla just unveiled a Virtual Queue.",
            with_url_pill=True,
        )
        # All three overlays present.
        assert graph.count("overlay=") == 2  # show pill + URL pill
        assert "drawtext" in graph  # hook caption
        # The drawtext input is the [stamped] label (URL pill output),
        # NOT the [branded] label (show pill output) — pin the chain
        # order so a future refactor doesn't drop the URL pill.
        assert "[stamped]drawtext" in graph
        assert graph.endswith("[v]")


# ---------------------------------------------------------------------------
# Command builders — url_pill_in kwarg
# ---------------------------------------------------------------------------


class TestLongFormCmdWithUrlPill:

    def test_default_three_inputs(self):
        """Backward compat: no ``url_pill_in`` → 3 inputs (cover,
        audio, brand) as before."""
        cmd = _long_form_cmd("voice.mp3", "cover.jpg", "brand.png", "out.mp4")
        assert cmd.count("-i") == 3

    def test_url_pill_adds_fourth_input(self):
        cmd = _long_form_cmd(
            "voice.mp3", "cover.jpg", "brand.png", "out.mp4",
            url_pill_in="urlpill.png",
        )
        # 4 inputs now.
        assert cmd.count("-i") == 4
        # Last -i argument points at the URL pill.
        i_indices = [i for i, x in enumerate(cmd) if x == "-i"]
        assert cmd[i_indices[-1] + 1] == "urlpill.png"
        # Filter graph carries the with_url_pill flag.
        fc = cmd[cmd.index("-filter_complex") + 1]
        assert "[3:v]" in fc


class TestShortFormCmdWithUrlPill:

    def test_default_three_inputs(self):
        cmd = _short_form_cmd("voice.mp3", "cover.jpg", "brand.png", "out.mp4")
        assert cmd.count("-i") == 3

    def test_url_pill_adds_fourth_input(self):
        cmd = _short_form_cmd(
            "voice.mp3", "cover.jpg", "brand.png", "out.mp4",
            url_pill_in="urlpill.png",
        )
        assert cmd.count("-i") == 4
        i_indices = [i for i, x in enumerate(cmd) if x == "-i"]
        assert cmd[i_indices[-1] + 1] == "urlpill.png"
        fc = cmd[cmd.index("-filter_complex") + 1]
        assert "[3:v]" in fc
