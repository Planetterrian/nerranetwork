"""Tests that pin down the EXACT ffmpeg commands :mod:`engine.video` emits.

We don't actually run ffmpeg — we just verify the command lists. Same
pattern as :mod:`tests.test_audio_commands`. These act as a regression
fence: any future tweak to the long-form or Shorts video pipeline
will trip these tests, forcing the change to be intentional.

The tests also pin the keyframe-spacing args (``-g``, ``-keyint_min``,
``-sc_threshold``, ``-force_key_frames``) — without those, the
long-form MP4 has only one keyframe at t=0 and YouTube's transcoder
serves an unplayable rendition.
"""

from pathlib import Path

import pytest

from engine.video import (
    _AUDIO_ENCODE,
    _SUBTITLES_FORCE_STYLE,
    _VIDEO_ENCODE,
    _VIDEO_ENCODE_FAST,
    _drawtext_escape,
    _long_form_cmd,
    _long_form_filter_graph,
    _make_brand_pill,
    _short_form_cmd,
    _short_form_filter_graph,
    _slideshow_cmd,
    _slideshow_filter_graph,
    _subtitles_path_escape,
    _wrap_caption,
    build_long_form_video,
    build_short_video,
)


# ---------------------------------------------------------------------------
# Encoder profile — keyframe args are the playback fix
# ---------------------------------------------------------------------------

@pytest.fixture
def force_two_stage_render(monkeypatch):
    """Pin the legacy two-stage render for tests that assert its shape."""
    monkeypatch.setenv("NERRA_SINGLE_PASS_RENDER", "0")

def test_video_encode_profile_includes_keyframe_args():
    """``-g``, ``-keyint_min``, ``-sc_threshold`` and
    ``-force_key_frames`` must all be present.

    Without these, x264 sees the looped cover as one big static
    scene, emits a single IDR at t=0, and YouTube's transcoder
    rejects the rendition with "video can't play".
    """
    assert "-g" in _VIDEO_ENCODE
    assert _VIDEO_ENCODE[_VIDEO_ENCODE.index("-g") + 1] == "60"
    assert "-keyint_min" in _VIDEO_ENCODE
    assert _VIDEO_ENCODE[_VIDEO_ENCODE.index("-keyint_min") + 1] == "60"
    assert "-sc_threshold" in _VIDEO_ENCODE
    assert _VIDEO_ENCODE[_VIDEO_ENCODE.index("-sc_threshold") + 1] == "0"
    assert "-force_key_frames" in _VIDEO_ENCODE
    fkf_value = _VIDEO_ENCODE[_VIDEO_ENCODE.index("-force_key_frames") + 1]
    assert "expr:gte(t,n_forced*2)" in fkf_value


# ---------------------------------------------------------------------------
# Long-form filter graph — zoompan + brand + disclosure (no spectrum)
# ---------------------------------------------------------------------------

def test_long_form_filter_graph_uses_zoompan_and_brand_overlay():
    graph = _long_form_filter_graph()
    # Ken Burns zoom on the cover (single-image path).
    assert "zoompan" in graph
    # Brand pill is overlaid (third input).
    assert "[2:v]" in graph and "format=rgba" in graph
    # Final output label is [v].
    assert graph.endswith("[v]")


def test_long_form_filter_graph_drops_visual_distractions():
    """The earlier showcqt spectrum band, drawbox tint, and centered
    AI-disclosure burn-in were removed in favour of clean visuals.
    Compliance is now covered by the API ``containsSyntheticMedia``
    flag + description disclosure footer (no on-screen AI-narration
    reminder). Pin the absence of the dropped pieces so a future
    refactor doesn't quietly re-introduce them.

    July 31 2026 note: the OPENING HOOK TITLE (B4) is a deliberate,
    opt-in exception — ``hook=`` adds a 0-4 s drawtext title (see
    TestLongFormHookTitle). The DEFAULT graph (no hook) must stay
    clean, and the disclosure line specifically must never return."""
    graph = _long_form_filter_graph()
    assert "showcqt" not in graph
    assert "showwaves" not in graph
    assert "drawbox" not in graph
    assert "drawtext" not in graph  # hook is opt-in; default stays clean
    # Centered first-4s disclosure burn-in is gone.
    assert "AI-narrated content" not in graph
    assert "between(t,0,4)" not in graph


def test_long_form_filter_graph_respects_fps():
    graph = _long_form_filter_graph(fps=24)
    # zoompan honours the requested fps even without the spectrum.
    assert "fps=24" in graph


# ---------------------------------------------------------------------------
# Short-form filter graph
# ---------------------------------------------------------------------------

def test_short_form_filter_graph_uses_vertical_dims_and_brand():
    # Default (static cover) path: lanczos prescale at 2x + a slow
    # centred zoompan push-in ending at the 1080x1920 frame — the cover
    # fallback used to ship a frozen bicubic-upscaled JPEG for the whole
    # Short (the one render path with zero motion).
    graph = _short_form_filter_graph()
    assert "scale=2160:3840" in graph
    assert "flags=lanczos" in graph
    assert "zoompan=" in graph
    assert "s=1080x1920" in graph
    # Video background (real slideshow): motion is baked in — plain
    # fill-scale at frame size, no zoompan.
    vgraph = _short_form_filter_graph(bg_is_video=True)
    assert "scale=1080:1920" in vgraph
    assert "zoompan=" not in vgraph
    # Brand pill is anchored top-right (W-w-24).
    assert "x=W-w-24:y=24" in graph
    assert graph.endswith("[v]")


def test_short_form_filter_graph_drops_spectrum_band():
    graph = _short_form_filter_graph()
    assert "showcqt" not in graph
    assert "showwaves" not in graph
    assert "drawbox" not in graph


def test_short_form_filter_graph_with_hook_burns_caption():
    graph = _short_form_filter_graph(
        hook="Tesla just unveiled a Virtual Queue for Superchargers."
    )
    assert "drawtext" in graph
    # July 31 2026 (B3): the hook FADES in (250 ms) and out (400 ms)
    # instead of popping on/off in one frame. The enable window extends
    # to 3.05 s so the alpha ramp completes on screen.
    assert r"alpha='clip(t/0.25,0,1)*clip((3-t)/0.4,0,1)'" in graph
    assert r"enable='between(t,0,3.05)'" in graph
    # The bare single-frame gate must not come back.
    assert r"enable='between(t,0,3)'" not in graph
    # Some text from the hook appears (escaped) in the graph.
    assert "Tesla" in graph
    assert graph.endswith("[v]")


def test_short_form_filter_graph_hook_sits_in_bottom_half():
    """May 2026 follow-up: the Shorts hook moved out of the top
    half (was ``y=240``) and now sits at ``y=h*0.55`` (≈y=1056) —
    inside the lower half of the 1080x1920 frame but above the
    burn-in subtitle baseline (MarginV=300 → y≈1620) so the two
    overlays don't collide during the first 3 s when both are
    visible. The hook fades after 3 s; the subtitles continue."""
    graph = _short_form_filter_graph(hook="anything")
    # New mid-lower position that leaves room for burn-in subs below.
    assert "y=h*0.55" in graph
    # Old top-of-frame position must not return.
    assert "y=240" not in graph


def test_short_form_filter_graph_hook_is_not_prominent():
    """May 2026 operator review: drop the opaque-box treatment
    (was ``box=1:boxcolor=black@0.6``) and shrink the font (64
    → 44) so the hook no longer dominates the slideshow during
    its 3-second window. Outline + shadow keep it readable on
    bright frames without painting a black rectangle."""
    graph = _short_form_filter_graph(hook="anything")
    # Smaller font.
    assert "fontsize=44" in graph
    assert "fontsize=64" not in graph
    # No opaque box behind the text.
    assert "box=1" not in graph
    assert "boxcolor=" not in graph
    # Outline + soft shadow for readability without prominence.
    assert "borderw=4" in graph
    assert "bordercolor=black" in graph


def test_short_form_filter_graph_without_hook_omits_caption():
    graph = _short_form_filter_graph(hook=None)
    # No first-3s caption when hook isn't provided.
    assert "between(t,0,3)" not in graph
    # But the brand pill + visualization still produce the [v] output.
    assert graph.endswith("[v]")


def test_short_form_filter_graph_burns_subtitles_when_path_provided():
    """May 2026 operator review (round 2): Shorts captions upgraded
    from FontSize=34 outline-only to FontSize=48 bold on a 50 %-opaque
    box (TikTok-style "subtitle card"). The card has to stay
    readable on busy Grok-Imagine backgrounds and sit firmly below
    the 0–3 s hook overlay AND above the bottom URL pill — see the
    block comment on ``_SHORTS_SUBTITLES_FORCE_STYLE`` for the
    geometry math. Drift guard pins every field that affects
    legibility."""
    graph = _short_form_filter_graph(subtitles_path="/tmp/short.srt")
    assert "subtitles=" in graph
    # Caption text style.
    assert "FontSize=48" in graph
    assert "Bold=-1" in graph
    # Background card: BorderStyle=3 + non-zero alpha BackColour =
    # opaque box behind the words, not pure outline.
    assert "BorderStyle=3" in graph
    assert "BackColour=&H80000000" in graph
    # Position: clear of URL pill (y≈1820) and hook (y≈1056).
    assert "MarginV=340" in graph
    assert graph.endswith("[v]")


def test_short_form_filter_graph_subtitles_compose_with_hook():
    """When BOTH the hook and subtitles are present, the filter
    graph must end in a single ``[v]`` output. The hook renders at
    ``y=h*0.55`` (≈y=1056); the subtitles render at MarginV=300
    (baseline ≈y=1620). Both must be visible together for the
    first 3 seconds without overlapping."""
    graph = _short_form_filter_graph(
        hook="Today's market.", subtitles_path="/tmp/short.srt",
    )
    # Hook is wired through with its 0-3s gate (B3: 3.05 fade window).
    assert "between(t,0,3.05)" in graph
    # Subtitles filter is wired through.
    assert "subtitles=" in graph
    # Single final [v] output (no double-terminated graph).
    assert graph.endswith("[v]")
    # Hook chains into the subtitle stage rather than terminating
    # the graph early.
    assert "[hooked]subtitles=" in graph


def test_short_form_cmd_threads_subtitles_path():
    """The Shorts MP4 builder must pass ``subtitles_path`` through
    to the filter graph so the burn-in actually happens. May 2026
    operator complaint traced to the path being available
    (transcript exists) but unused in the Shorts command builder."""
    from engine.video import _short_form_cmd
    cmd = _short_form_cmd(
        "/v.mp3", "/bg.jpg", "/brand.png", "/out.mp4",
        subtitles_path="/tmp/short.srt",
    )
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "subtitles=" in fc
    assert "/tmp/short.srt" in fc


# ---------------------------------------------------------------------------
# Long-form command shape
# ---------------------------------------------------------------------------

def test_long_form_cmd_structure():
    cmd = _long_form_cmd("voice.mp3", "cover.jpg", "brand.png", "out.mp4")

    # Three inputs: cover (looped), audio, brand pill (looped).
    assert cmd[:2] == ["ffmpeg", "-y"]
    assert cmd.count("-loop") == 2  # cover + brand
    assert cmd.count("-i") == 3
    # filter_complex contains all the new filters.
    fc_idx = cmd.index("-filter_complex")
    graph = cmd[fc_idx + 1]
    assert "zoompan" in graph
    assert "[bg][brand]overlay" in graph
    # Map composited video and audio.
    map_indices = [i for i, x in enumerate(cmd) if x == "-map"]
    map_values = [cmd[i + 1] for i in map_indices]
    assert "[v]" in map_values
    assert "1:a" in map_values
    # Encoding + container args present.
    for token in ("-shortest", "-movflags", "+faststart"):
        assert token in cmd
    for token in _VIDEO_ENCODE:
        assert token in cmd
    for token in _AUDIO_ENCODE:
        assert token in cmd
    assert cmd[-1] == "out.mp4"


def test_long_form_cmd_respects_fps():
    cmd = _long_form_cmd("voice.mp3", "cover.jpg", "brand.png",
                         "out.mp4", fps=24)
    # -framerate is set on each looped image input *before* its -i.
    framerate_indices = [i for i, x in enumerate(cmd) if x == "-framerate"]
    assert len(framerate_indices) == 2
    for idx in framerate_indices:
        assert cmd[idx + 1] == "24"
    # -r controls the output frame rate.
    assert cmd[cmd.index("-r") + 1] == "24"


# ---------------------------------------------------------------------------
# Shorts command shape
# ---------------------------------------------------------------------------

def test_short_form_cmd_clips_audio():
    cmd = _short_form_cmd(
        "voice.mp3", "cover.jpg", "brand.png", "short.mp4",
        start_offset=15.0, duration=55.0,
    )
    # -ss / -t are applied to the audio input (between cover -i and audio -i).
    ss_idx = cmd.index("-ss")
    t_idx = cmd.index("-t")
    assert cmd[ss_idx + 1] == "15.00"
    assert cmd[t_idx + 1] == "55.00"
    # Three -i flags: cover, audio, brand.
    i_indices = [i for i, x in enumerate(cmd) if x == "-i"]
    assert len(i_indices) == 3
    # Audio input must come after -ss/-t.
    assert i_indices[1] > t_idx
    # Two looped image inputs (cover + brand pill); audio is not looped.
    assert cmd.count("-loop") == 2
    # Filter graph references vertical Shorts geometry (static-cover
    # path prescales 2x for the zoompan push-in, ending at 1080x1920).
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "s=1080x1920" in graph
    # Brand pill is overlaid; spectrum band was removed.
    assert "[bg][brand]overlay" in graph
    assert cmd[-1] == "short.mp4"


def test_short_form_cmd_threads_hook_into_filter_graph():
    cmd = _short_form_cmd(
        "voice.mp3", "cover.jpg", "brand.png", "short.mp4",
        start_offset=10.0, duration=55.0,
        hook="A short headline",
    )
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "drawtext" in graph
    assert "A short headline" in graph
    # B3 fade window (in 0.25 s / out 0.4 s, gate to 3.05 s).
    assert r"enable='between(t,0,3.05)'" in graph
    assert r"alpha='clip(t/0.25,0,1)*clip((3-t)/0.4,0,1)'" in graph


def test_short_form_rejects_60s_duration(tmp_path):
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\x00")
    out = tmp_path / "short.mp4"
    with pytest.raises(ValueError, match="below 60s"):
        build_short_video(audio, cover, out, duration=60.0)


def test_short_form_accepts_under_60s(tmp_path, monkeypatch):
    """Shorts under 60s pass validation. We don't run ffmpeg — we
    capture the command and assert its shape."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\x00")
    out = tmp_path / "short.mp4"

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd

        class _R:
            returncode = 0
        return _R()

    monkeypatch.setattr("engine.video.subprocess.run", fake_run)
    build_short_video(audio, cover, out, duration=55.0,
                      start_offset=10.0, hook="Test headline")
    assert captured["cmd"][0] == "ffmpeg"
    assert "55.00" in captured["cmd"]
    # Brand pill PNG should have been generated alongside the output.
    # v3 (July 31 2026 — B5): 2x supersampled render + cyan accent; the
    # bumped filename forces regeneration on persistent work dirs.
    brand_pill = out.parent / "_brand_pill_v3.png"
    assert brand_pill.exists()


# ---------------------------------------------------------------------------
# Public API guards
# ---------------------------------------------------------------------------

def test_build_long_form_video_requires_audio(tmp_path):
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\x00")
    with pytest.raises(FileNotFoundError, match="audio not found"):
        build_long_form_video(tmp_path / "missing.mp3", cover,
                              tmp_path / "out.mp4")


def test_build_long_form_video_requires_cover(tmp_path):
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    with pytest.raises(FileNotFoundError, match="cover not found"):
        build_long_form_video(audio, tmp_path / "missing.jpg",
                              tmp_path / "out.mp4")


# ---------------------------------------------------------------------------
# Brand pill PNG generation
# ---------------------------------------------------------------------------

def test_make_brand_pill_creates_png(tmp_path):
    target = tmp_path / "_brand_pill.png"
    assert not target.exists()
    result = _make_brand_pill(target)
    assert result == target
    assert target.exists()
    # Sanity: PNG signature is 8 bytes \x89PNG\r\n\x1a\n.
    with open(target, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n"


def test_make_brand_pill_is_idempotent(tmp_path):
    """Second call should reuse the cached file (not rewrite it)."""
    target = tmp_path / "_brand_pill.png"
    _make_brand_pill(target)
    first_mtime = target.stat().st_mtime_ns
    # Touch a marker so we'd notice if Pillow re-wrote.
    second = _make_brand_pill(target)
    assert second == target
    assert target.stat().st_mtime_ns == first_mtime


def test_build_long_form_video_generates_brand_pill(tmp_path, monkeypatch):
    """``build_long_form_video`` should generate the brand pill on
    first call so the ffmpeg command can reference it."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\x00")
    out = tmp_path / "out.mp4"

    monkeypatch.setattr("engine.video.subprocess.run",
                        lambda cmd, **kwargs: type("R", (), {"returncode": 0})())
    build_long_form_video(audio, cover, out)
    # v3 filename (B5) — see test_short_form_accepts_under_60s.
    assert (out.parent / "_brand_pill_v3.png").exists()


# ---------------------------------------------------------------------------
# drawtext escaping
# ---------------------------------------------------------------------------

def test_drawtext_escape_handles_metacharacters():
    # Colons are option separators; backslashes and percent signs are
    # drawtext metachars; straight apostrophes are mapped to typographic
    # U+2019 (Tesla Ep469 May 11 fix — see test below).
    assert _drawtext_escape("It's 5:30 PM (50% off)") == \
        "It’s 5\\:30 PM (50\\% off)"
    assert _drawtext_escape("path\\to") == "path\\\\to"


def test_drawtext_escape_swaps_straight_apostrophe_for_curly():
    """Operator caught (Tesla Ep469, May 11 2026) the Shorts ffmpeg
    invocation failing on a hook containing "Tesla's …".

    Inside ffmpeg's filter_complex single-quoted region, the
    backslash is LITERAL — not an escape character. So our previous
    ``'`` → ``\\'`` escape produced ``\\'`` (backslash + apostrophe);
    the apostrophe then terminated the ``text='...'`` quoted region
    and the rest of the filter graph parsed as garbage. Exit status
    8, Tesla Ep469 Shorts didn't ship.

    Fix: replace straight ``'`` with the typographic apostrophe
    ``’`` (U+2019). It's not a quote character to ffmpeg's parser
    so no escaping needed, AND it renders more professionally as
    burned-in caption text."""
    # No backslash-apostrophe in the output; straight ' becomes ’.
    out = _drawtext_escape("Tesla's zero-intervention drive")
    assert "\\'" not in out, (
        "Straight apostrophe must NOT be escaped with backslash inside "
        "ffmpeg filter_complex single-quoted regions — the backslash is "
        "literal there, so the apostrophe terminates the quote and "
        "breaks parsing. Use typographic U+2019 instead."
    )
    assert "’" in out
    assert "Tesla’s" in out


def test_drawtext_escape_escapes_real_newlines():
    """Operator caught (Tesla Ep466, May 8 2026) the Shorts ffmpeg
    invocation failing because the wrapped 4-line hook contained
    real ``\\n`` characters inside ``text='...'``. ffmpeg's
    filter_complex parser terminates a single-quoted region on a
    real line feed, which truncated the text= value mid-string.

    The fix escapes real newlines to the literal two-char sequence
    ``\\n``. ffmpeg's drawtext text-expansion (which runs *after*
    filter_complex parsing) recognises ``\\n`` as a line break, so
    the caption still wraps visually."""
    # Real newline → literal \n (backslash + n)
    assert _drawtext_escape("line one\nline two") == r"line one\nline two"
    # Multi-line with apostrophe — the actual Tesla Ep466 case
    out = _drawtext_escape("Tesla Semi's\nbattery sizes")
    assert "\n" not in out, (
        f"Real newlines must be escaped to literal \\n; got {out!r}"
    )
    assert r"\n" in out
    # Apostrophe now uses typographic U+2019 (see test above) — verify
    # there's no backslash-apostrophe sequence that would close the
    # ffmpeg quoted region.
    assert "\\'" not in out
    assert "’" in out


def test_short_form_filter_graph_caption_has_no_real_newlines():
    """End-to-end pin: each drawtext text= region in the rendered
    Shorts filter graph MUST contain neither a real newline (which
    closes ffmpeg's single-quoted parsing region — broke Tesla
    Ep466's Shorts upload on May 8 2026) NOR a literal ``\\n``
    escape (which silently rendered as the letter "n" between
    wrap points — broke Tesla Ep485 / MAB Shorts on May 26 2026:
    "major warning" → "majornwarning", "volume reductions" →
    "volumenreductions"). The fix stacks one drawtext per
    wrapped line, so each text= value is a single physical line
    of plain words — no newline of any kind."""
    hook = (
        "California regulators just disclosed the Tesla Semi's "
        "battery sizes at 822 kWh and 548 kWh."
    )
    graph = _short_form_filter_graph(hook=hook)
    import re as _re
    # Every drawtext text= region in the graph must be newline-free
    # AND must not contain the literal \n escape sequence.
    text_values = _re.findall(r"text='([^']*(?:\\'[^']*)*)'", graph)
    assert text_values, "no drawtext text= regions found in graph"
    for tv in text_values:
        assert "\n" not in tv, (
            f"Real newline survived into drawtext text= value (would "
            f"break ffmpeg parsing): {tv!r}"
        )
        assert r"\n" not in tv, (
            f"Literal \\n escape in drawtext text= value (would render "
            f"as the letter 'n' between words): {tv!r}"
        )
    # A long multi-line hook must produce MULTIPLE drawtext filters
    # (one per wrapped line). Single-drawtext graph would be the
    # broken legacy path.
    drawtext_count = graph.count("drawtext=")
    assert drawtext_count >= 2, (
        f"long hook should produce >=2 stacked drawtext filters, "
        f"got {drawtext_count}"
    )


# ---------------------------------------------------------------------------
# Caption wrapping for Shorts
# ---------------------------------------------------------------------------

def test_wrap_caption_breaks_long_text():
    out = _wrap_caption(
        "Tesla just unveiled a Virtual Queue for Superchargers.",
        max_chars_per_line=22,
    )
    lines = out.split("\n")
    assert all(len(line) <= 26 for line in lines)  # small slack for greedy wrap
    assert len(lines) <= 3


def test_wrap_caption_short_text_unchanged():
    assert _wrap_caption("Short headline.") == "Short headline."


def test_wrap_caption_empty_returns_empty():
    assert _wrap_caption("") == ""


def test_wrap_caption_default_budget_fits_realistic_hook():
    """Operator caught (Tesla Ep466, May 8 2026) the default ``22 × 3``
    budget (66 chars) truncating realistic 90+ char hooks to
    ``...batter…`` mid-word. The new ``26 × 4`` defaults give a
    104-char budget — enough headroom for the longest hooks the LLM
    actually produces. Pin so a future "tighter wrap" change doesn't
    silently re-introduce the truncation."""
    hook = (
        "California regulators just disclosed the Tesla Semi's battery "
        "sizes at 822 kWh and 548 kWh."
    )
    out = _wrap_caption(hook)  # use defaults
    # No truncation marker.
    assert "..." not in out, (
        f"Realistic 90+ char hook truncated under default wrap "
        f"budget: {out!r}"
    )
    # Every word from the original survived (case-preserving).
    for word in hook.split():
        assert word in out, f"Word {word!r} dropped during wrap: {out!r}"


# ---------------------------------------------------------------------------
# Slideshow (stage 1) — multi-scene Ken Burns + concat
# ---------------------------------------------------------------------------

def test_slideshow_filter_graph_has_per_scene_chains():
    graph = _slideshow_filter_graph(scene_count=4)
    # One zoompan chain per scene, then a rotating xfade chain (≥2 scenes).
    assert graph.count("zoompan") == 4
    assert graph.count("[s0]") >= 1
    assert graph.count("[s3]") >= 1
    # Crossfade transitions replace the old hard-cut concat for ≥2 scenes.
    assert "concat=" not in graph
    assert graph.count("xfade=transition=") == 3  # N-1 joins for 4 scenes
    assert graph.endswith("[v]")


def test_slideshow_filter_graph_hard_cut_fallback():
    """crossfade=0 (the ffmpeg-failure retry path) hard-cuts via concat."""
    graph = _slideshow_filter_graph(scene_count=4, crossfade=0.0)
    assert "concat=n=4:v=1:a=0[v]" in graph
    assert "xfade" not in graph
    assert graph.endswith("[v]")


def test_slideshow_filter_graph_single_scene_uses_concat():
    """A lone scene can't xfade — it must still terminate at [v]."""
    graph = _slideshow_filter_graph(scene_count=1)
    assert "xfade" not in graph
    assert graph.endswith("[v]")


def test_slideshow_filter_graph_zoom_per_scene():
    """Slideshow zoom is faster than the single-image Ken Burns
    (each scene is only ~12s).

    July 2026: the 1.12 ceiling moved to ``_ZOOM_MAX`` (now 1.09) — the
    sources are 1792x1024, below the delivery frame, so the zoom was
    stacking magnification on an upsample. Asserted against the constant
    rather than a literal so the two cannot drift apart; the band is
    pinned in tests/test_video_render_quality.py.

    July 30 2026: the fixed per-frame increment is gone. It reached the
    ceiling after 5 s and then the picture was FROZEN for the rest of the
    scene — 57.1% of a 12 s scene, measured by rendering. The zoom is now
    normalised to each scene's own frame count, so it travels the same
    range whatever the hold length and never stops. The ceiling is still
    asserted against the constant so the two cannot drift apart.
    """
    graph = _slideshow_filter_graph(scene_count=2)
    # Duration-normalised: progress is a function of the output frame
    # number, not an accumulator against a cap.
    assert "on/" in graph
    # Aug 2026: amplitude is duration-adaptive — 0.006/s of hold, scaled
    # by the rung's ±1/3 rhythm factor and clamped to [0.04, 0.24].
    from engine.video import (_KB_AMP_PER_SECOND, _KB_AMP_MIN, _KB_AMP_MAX,
                              _KB_ZOOM_AMPLITUDES, _SCENE_DURATION_SECONDS,
                              _SLIDESHOW_XFADE_S)
    trim = _SCENE_DURATION_SECONDS + _SLIDESHOW_XFADE_S
    rung0 = (_KB_ZOOM_AMPLITUDES[0] - 1.0) / 0.09
    expected = round(min(_KB_AMP_MAX,
                         max(_KB_AMP_MIN,
                             _KB_AMP_PER_SECOND * trim * rung0)), 4)
    assert f"{expected}" in graph
    assert "min(zoom+0.0006" not in graph, (
        "the capped-accumulator zoom is back — it freezes the image for "
        "the remainder of every scene once the cap is reached"
    )


def test_slideshow_zoom_is_anchored_not_left_to_default():
    """zoompan's x/y default to "0" — the TOP-LEFT corner.

    The pipeline never set them, so every scene on the network zoomed
    into its top-left corner and slid the subject down and right
    (measured drift of a centred subject: 0.044 of frame width per
    scene; 0.000 after this fix). Confirmed against ffmpeg 7.0's own
    ``-h filter=zoompan``, which documents x and y as default "0".
    """
    graph = _slideshow_filter_graph(scene_count=2)
    assert ":x='" in graph and ":y='" in graph, (
        "zoompan without explicit x/y anchors to the top-left corner"
    )
    assert "iw/zoom/2" in graph and "ih/zoom/2" in graph


def test_slideshow_prescale_leaves_subpixel_headroom():
    """zoompan steps x/y in whole SOURCE pixels.

    At the old 1.15x pre-scale a slow zoom often failed to advance a
    pixel between frames: 77.2% of consecutive frames were byte-identical
    (measured), i.e. the motion stuttered at well under the video's own
    frame rate. 2.0x brought that to 33.3% for +17% render time; 3.0x
    halves it again but costs +121%, which the 40-minute pipeline budget
    does not have to spare.
    """
    from engine.video import _PRESCALE

    assert _PRESCALE >= 2.0, (
        "pre-scale below 2.0 reintroduces visible integer-pixel judder"
    )


def test_slideshow_cmd_has_one_input_per_scene(tmp_path):
    paths = [tmp_path / f"scene{i}.jpg" for i in range(3)]
    out = tmp_path / "slides.mp4"
    cmd = _slideshow_cmd(paths, out)

    # Three -i flags (one per scene), three -loop flags.
    assert cmd.count("-i") == 3
    assert cmd.count("-loop") == 3
    # No audio in slideshow output.
    assert "-an" in cmd
    # Stage-1 slideshow is an intermediate → fast encode profile (re-encoded
    # by the stage-2 composite, which carries the full keyframe profile).
    for token in _VIDEO_ENCODE_FAST:
        assert token in cmd
    assert "veryfast" in cmd
    assert cmd[-1] == str(out)


# ---------------------------------------------------------------------------
# Long-form filter graph — slideshow (bg_is_video) variant
# ---------------------------------------------------------------------------

def test_long_form_filter_graph_video_bg_skips_zoompan():
    """When the background is already a slideshow video, we skip
    zoompan in stage 2 (the zoom is baked into the slideshow itself)."""
    graph = _long_form_filter_graph(bg_is_video=True)
    assert "zoompan" not in graph
    # Brand pill still overlays on top of the slideshow video.
    assert "[2:v]" in graph and "format=rgba" in graph
    assert "[bg][brand]overlay" in graph
    assert graph.endswith("[v]")


def test_long_form_filter_graph_image_bg_uses_zoompan():
    graph = _long_form_filter_graph(bg_is_video=False)
    assert "zoompan" in graph


# ---------------------------------------------------------------------------
# Long-form filter graph — subtitles burn-in
# ---------------------------------------------------------------------------

def test_long_form_filter_graph_with_subtitles_appends_filter():
    graph = _long_form_filter_graph(subtitles_path="/tmp/captions.srt")
    assert "subtitles=" in graph
    # ASS force-style is appended.
    assert "force_style=" in graph
    assert "Alignment=2" in graph
    # Subtitles sit FLUSH with the bottom area (May 2026 follow-up
    # — operator caught that the previous ``MarginV=120`` still
    # read as "central portion" rather than truly bottom). The new
    # ``MarginV=50`` puts the text baseline ≈y=1030 — just above
    # YouTube's auto-fading progress-bar HUD.
    assert "MarginV=50" in graph
    # Subtitles attach to the [branded] stage (was [disclosed] before
    # the centered burn-in was removed).
    assert "[branded]subtitles=" in graph
    assert graph.endswith("[v]")


def test_long_form_filter_graph_no_subtitles_uses_null_passthrough():
    graph = _long_form_filter_graph(subtitles_path=None)
    assert "subtitles=" not in graph
    # null filter renames [branded] → [v] without re-encoding the alpha.
    assert "[branded]null[v]" in graph


def test_subtitles_path_escape_handles_metacharacters():
    # Colons are option separators inside the subtitles filter.
    assert _subtitles_path_escape("/tmp/with:colon/file.srt") == \
        r"/tmp/with\:colon/file.srt"
    # Backslashes get normalised to forward slashes (Windows safety).
    assert _subtitles_path_escape("C:\\Users\\caps.srt") == \
        r"C\:/Users/caps.srt"


def test_subtitles_force_style_has_required_fields():
    """Sanity check on the ASS force-style string. May 2026 retune:
    pin the new "auto-caption-style" look so a future style edit
    doesn't silently regress to the old opaque-box look the operator
    asked to remove ("make it not as prominent"). May 22 follow-up:
    operator caught the previous ``MarginV=120 / FontSize=18`` still
    reading as central + too small — moved to ``MarginV=50`` (flush
    bottom) + ``FontSize=22`` (readable on phones)."""
    assert "FontName=DejaVu Sans" in _SUBTITLES_FORCE_STYLE
    assert "Alignment=2" in _SUBTITLES_FORCE_STYLE
    # Flush-bottom position (May 22 2026 operator follow-up).
    assert "MarginV=50" in _SUBTITLES_FORCE_STYLE
    # BorderStyle=1 = outline + soft shadow only (no opaque box).
    # Keeps the slideshow imagery visible behind the words.
    assert "BorderStyle=1" in _SUBTITLES_FORCE_STYLE
    assert "BorderStyle=3" not in _SUBTITLES_FORCE_STYLE
    # FontSize: 18 -> 22 (May 2026) -> 26 (July 2026). These are libass
    # script units, not pixels — the subtitles filter renders SRT at the
    # ASS default PlayResY=288, so a 1080p frame scales them by 3.75x.
    # The exact value and its rationale live in
    # tests/test_video_render_quality.py::TestCaptionLegibility.
    assert "FontSize=26" in _SUBTITLES_FORCE_STYLE


# ---------------------------------------------------------------------------
# Long-form command — slideshow + subtitles wiring
# ---------------------------------------------------------------------------

def test_long_form_cmd_video_bg_uses_stream_loop():
    """When bg is the pre-rendered slideshow MP4, we ``-stream_loop -1``
    it so it loops to match audio length, and we drop ``-loop 1
    -framerate``."""
    cmd = _long_form_cmd(
        "voice.mp3", "slides.mp4", "brand.png", "out.mp4",
        bg_is_video=True,
    )
    assert "-stream_loop" in cmd
    assert cmd[cmd.index("-stream_loop") + 1] == "-1"
    # Cover-style -loop / -framerate only on the brand input now (1 each).
    assert cmd.count("-loop") == 1
    # Three -i still: bg, audio, brand.
    assert cmd.count("-i") == 3


def test_long_form_cmd_threads_subtitles_path():
    cmd = _long_form_cmd(
        "voice.mp3", "cover.jpg", "brand.png", "out.mp4",
        subtitles_path="/work/captions.srt",
    )
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "subtitles=" in graph
    assert "captions.srt" in graph


def test_build_long_form_video_falls_back_to_cover_with_one_scene(tmp_path,
                                                                  monkeypatch):
    """Single-scene list should NOT trigger the two-stage slideshow
    pipeline (one photo isn't a slideshow)."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    out = tmp_path / "out.mp4"

    captured_cmds = []
    monkeypatch.setattr(
        "engine.video.subprocess.run",
        lambda cmd, **kw: (captured_cmds.append(list(cmd)),
                           type("R", (), {"returncode": 0})())[1],
    )
    build_long_form_video(audio, cover, out, scene_paths=[cover])
    # Only one ffmpeg invocation (no slideshow stage).
    assert len(captured_cmds) == 1
    # The single command's filter graph contains zoompan (image bg).
    graph = captured_cmds[0][captured_cmds[0].index("-filter_complex") + 1]
    assert "zoompan" in graph


# These four pin the TWO-STAGE pipeline, which since July 29 2026 is the
# automatic fallback rather than the default path (engine.video
# ._single_pass_enabled flipped ON after an A/B showed equivalent output
# 23-34%% faster). They stay valuable exactly because that fallback still
# ships on any fused-command failure — so force the legacy path rather
# than deleting the coverage.
@pytest.mark.usefixtures("force_two_stage_render")
def test_build_long_form_video_renders_slideshow_for_multi_scene(tmp_path,
                                                                 monkeypatch):
    """Multi-scene list triggers a stage-1 slideshow render before
    the final composite."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    scenes = []
    for i in range(3):
        s = tmp_path / f"scene{i}.jpg"
        s.write_bytes(b"\xFF\xD8")
        scenes.append(s)
    out = tmp_path / "out.mp4"

    captured_cmds = []

    def fake_run(cmd, **kw):
        captured_cmds.append(list(cmd))

        # Stage 1 writes the slideshow MP4; touch it so stage 2 sees it.
        for i, arg in enumerate(cmd):
            if arg == "-an":
                # Slideshow command — last arg is output path.
                Path(cmd[-1]).write_bytes(b"\x00")
                break
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("engine.video.subprocess.run", fake_run)
    # ``build_long_form_video`` now probes audio duration via
    # ``engine.audio.get_audio_duration`` (May 8 2026 — stretches scene
    # duration to span audio). Stub it so the ffprobe subprocess that
    # function would otherwise spawn doesn't show up in ``captured_cmds``.
    monkeypatch.setattr(
        "engine.audio.get_audio_duration", lambda _path: 360.0,
    )
    build_long_form_video(audio, cover, out, scene_paths=scenes)

    # Two ffmpeg invocations: stage-1 slideshow, stage-2 composite.
    assert len(captured_cmds) == 2
    # Stage 1 has one input per scene SLOT, no audio output. June 2026:
    # scenes cycle so no image holds >15 s — 360 s / 3 scenes would have
    # been 120 s/image, so the list repeats (360/15 → 24 slots), each
    # slot still drawn from the 3 source scenes.
    assert "-an" in captured_cmds[0]
    assert captured_cmds[0].count("-i") >= 3
    assert captured_cmds[0].count("-i") % 3 == 0  # whole cycles of the 3 scenes
    # Stage 2 uses -stream_loop on the slideshow MP4.
    assert "-stream_loop" in captured_cmds[1]


def test_build_long_form_video_threads_subtitles(tmp_path, monkeypatch):
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    srt = tmp_path / "captions.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    out = tmp_path / "out.mp4"

    captured = {}
    monkeypatch.setattr(
        "engine.video.subprocess.run",
        lambda cmd, **kw: (captured.update(cmd=list(cmd)),
                           type("R", (), {"returncode": 0})())[1],
    )
    build_long_form_video(audio, cover, out, subtitles_path=srt)
    graph = captured["cmd"][captured["cmd"].index("-filter_complex") + 1]
    assert "subtitles=" in graph
    assert "captions.srt" in graph


# ---------------------------------------------------------------------------
# Shorts slideshow — vertical version of the long-form slideshow
# ---------------------------------------------------------------------------

def test_slideshow_filter_graph_supports_vertical_dimensions():
    """The slideshow generator should respect width/height kwargs so
    the same code path produces both 1920x1080 and 1080x1920 output."""
    graph = _slideshow_filter_graph(
        scene_count=3, width=1080, height=1920,
    )
    assert "1080:1920" in graph or "s=1080x1920" in graph
    # Per-scene zoompan still drives motion.
    assert graph.count("zoompan") == 3
    # ≥2 scenes → rotating xfade transitions (concat is the crossfade=0 fallback).
    assert graph.count("xfade=transition=") == 2
    assert graph.endswith("[v]")


def test_slideshow_cmd_accepts_width_height(tmp_path):
    paths = [tmp_path / f"scene{i}.jpg" for i in range(3)]
    out = tmp_path / "vertical_slides.mp4"
    cmd = _slideshow_cmd(paths, out, width=1080, height=1920,
                         scene_duration=7.0)
    assert cmd.count("-i") == 3
    assert "-an" in cmd
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "s=1080x1920" in graph or "1080:1920" in graph
    assert cmd[-1] == str(out)


def test_short_form_filter_graph_with_video_bg_skips_loop_setup():
    """When the Shorts background is the slideshow MP4, the bg chain
    should still produce [bg] but the caller doesn't need a zoompan
    (motion's already in the slideshow)."""
    graph = _short_form_filter_graph(bg_is_video=True)
    assert "scale=1080:1920" in graph
    # Brand pill still overlays on top of the slideshow video.
    assert "[bg][brand]overlay" in graph
    assert graph.endswith("[v]")


def test_short_form_cmd_uses_stream_loop_for_video_bg():
    """When bg is the pre-rendered vertical slideshow MP4, we use
    -stream_loop -1 instead of -loop 1 -framerate."""
    cmd = _short_form_cmd(
        "voice.mp3", "vertical_slides.mp4", "brand.png", "short.mp4",
        start_offset=10.0, duration=55.0, bg_is_video=True,
    )
    assert "-stream_loop" in cmd
    assert cmd[cmd.index("-stream_loop") + 1] == "-1"
    # -loop only on the brand input now (1 occurrence, not 2).
    assert cmd.count("-loop") == 1
    # Three -i still: bg, audio, brand.
    assert cmd.count("-i") == 3


def test_short_form_cmd_image_bg_unchanged():
    """When bg is a still image (default path), the existing -loop 1
    -framerate flags still apply."""
    cmd = _short_form_cmd(
        "voice.mp3", "cover.jpg", "brand.png", "short.mp4",
        start_offset=10.0, duration=55.0,
    )
    assert "-stream_loop" not in cmd
    # Two looped image inputs (cover + brand pill).
    assert cmd.count("-loop") == 2


def test_build_short_video_falls_back_to_cover_with_one_scene(tmp_path,
                                                              monkeypatch):
    """Single-scene list should NOT trigger the two-stage Shorts
    pipeline (one photo isn't a slideshow)."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    out = tmp_path / "short.mp4"

    captured_cmds = []
    monkeypatch.setattr(
        "engine.video.subprocess.run",
        lambda cmd, **kw: (captured_cmds.append(list(cmd)),
                           type("R", (), {"returncode": 0})())[1],
    )
    build_short_video(audio, cover, out, duration=55.0,
                      scene_paths=[cover])
    # Only one ffmpeg invocation (no slideshow stage).
    assert len(captured_cmds) == 1
    # And no -stream_loop on the bg.
    assert "-stream_loop" not in captured_cmds[0]


def test_build_short_video_renders_vertical_slideshow_for_multi_scene(tmp_path,
                                                                       monkeypatch):
    """Multi-scene list triggers a stage-1 vertical slideshow render
    before the final composite."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    scenes = []
    for i in range(3):
        s = tmp_path / f"scene{i}.jpg"
        s.write_bytes(b"\xFF\xD8")
        scenes.append(s)
    out = tmp_path / "short.mp4"

    captured_cmds = []

    def fake_run(cmd, **kw):
        captured_cmds.append(list(cmd))
        # Stage 1 writes the slideshow MP4; touch it so stage 2 sees it.
        if "-an" in cmd:
            from pathlib import Path as _P
            _P(cmd[-1]).write_bytes(b"\x00")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("engine.video.subprocess.run", fake_run)
    build_short_video(audio, cover, out, duration=55.0,
                      scene_paths=scenes)

    # Two ffmpeg invocations: stage-1 vertical slideshow, stage-2 composite.
    assert len(captured_cmds) == 2
    # Stage 1: 3 inputs, no audio output, vertical resolution in graph.
    assert "-an" in captured_cmds[0]
    assert captured_cmds[0].count("-i") == 3
    stage1_graph = captured_cmds[0][
        captured_cmds[0].index("-filter_complex") + 1
    ]
    assert "s=1080x1920" in stage1_graph or "1080:1920" in stage1_graph
    # Stage 2 uses -stream_loop on the slideshow MP4.
    assert "-stream_loop" in captured_cmds[1]


# ---------------------------------------------------------------------------
# Brand pill text — should NOT mention AI-narration on screen
# ---------------------------------------------------------------------------

def test_brand_pill_text_omits_ai_narrated_marker():
    """The on-screen brand pill should be just "Nerra Network" — the
    AI-narration disclosure lives in the description footer + the
    YouTube containsSyntheticMedia API flag, not on the video."""
    from engine.video import _BRAND_PILL_TEXT
    assert "AI-narrated" not in _BRAND_PILL_TEXT
    assert "AI narrated" not in _BRAND_PILL_TEXT
    assert _BRAND_PILL_TEXT == "Nerra Network"


# ---------------------------------------------------------------------------
# Shorts end-screen CTA card — last-3s subscribe overlay
# ---------------------------------------------------------------------------
#
# Operator priority #3 (May 2026): every Short ends with a 3-second
# CTA card pointing the viewer at YouTube's own Subscribe button on
# the Shorts player's right rail. drawbox backdrop + 2 drawtext lines.

def test_short_form_filter_graph_omits_end_card_when_disabled():
    """``end_card=False`` (default) must produce exactly the legacy
    chain — no drawbox, no end-card drawtext, the existing
    short-form drift guards stay green."""
    graph = _short_form_filter_graph(end_card=False)
    assert "drawbox" not in graph
    assert "WATCH FULL EPISODE" not in graph
    assert "Tap Subscribe" not in graph


def test_short_form_filter_graph_appends_end_card_when_enabled():
    """``end_card=True`` must add: a full-frame translucent backdrop,
    a big headline drawtext, and a smaller sub-line drawtext — all
    bound to the same ``between(t, total-3, total)`` enable window."""
    graph = _short_form_filter_graph(
        end_card=True, total_duration=55.0, end_card_duration=3.0,
    )
    # Backdrop covers the full frame at ~78 % opacity.
    assert "drawbox=x=0:y=0:w=iw:h=ih" in graph
    assert "color=black@0.78" in graph
    # Headline + sub-line text.
    assert "WATCH FULL EPISODE" in graph
    assert "Tap Subscribe" in graph
    # All three filters share a single enable window keyed off the
    # passed ``total_duration``.
    assert "between(t,52.00,55.00)" in graph
    # Output is still a single [v] terminator.
    assert graph.endswith("[v]")


def test_short_form_filter_graph_end_card_window_scales_with_duration():
    """A 30 s Short must still get a 3 s end card at t=27..30, not a
    hard-coded t=52..55 window."""
    graph = _short_form_filter_graph(
        end_card=True, total_duration=30.0, end_card_duration=3.0,
    )
    assert "between(t,27.00,30.00)" in graph


def test_short_form_filter_graph_end_card_custom_duration():
    """``end_card_duration`` is operator-configurable; a 5 s card on
    a 55 s clip should fire from t=50."""
    graph = _short_form_filter_graph(
        end_card=True, total_duration=55.0, end_card_duration=5.0,
    )
    assert "between(t,50.00,55.00)" in graph


def test_short_form_filter_graph_end_card_custom_text():
    """Per-show YAML can override the CTA copy (Russian shows, A/B
    testing, etc.) — the override must appear verbatim in the
    drawtext payload."""
    graph = _short_form_filter_graph(
        end_card=True, total_duration=55.0,
        end_card_main_text="WATCH THE FULL SHOW",
        end_card_sub_text="Subscribe now",
    )
    assert "WATCH THE FULL SHOW" in graph
    assert "Subscribe now" in graph
    # Defaults must NOT appear.
    assert "WATCH FULL EPISODE" not in graph


def test_short_form_filter_graph_end_card_composes_with_subtitles():
    """When BOTH subtitles and the end card are present, the card
    terminates at [carded] and the SUBTITLES stage is the [v]
    terminator. Order matters: the opaque card used to paint over the
    captions, so the last ~3 s of speech played with its text hidden —
    captions now burn in on top (their 50%-black box keeps them
    legible over the CTA). No double-terminated graph."""
    graph = _short_form_filter_graph(
        end_card=True, subtitles_path="/tmp/short.srt", total_duration=55.0,
    )
    # End card lands at [carded]; captions consume it.
    assert "[carded]" in graph
    assert "[carded]subtitles=" in graph
    # The only [v] is from the subtitles stage, which runs last.
    assert graph.count("[v]") == 1
    assert graph.endswith("[v]")
    assert graph.index("drawbox") < graph.index("subtitles=")
    assert "WATCH FULL EPISODE" in graph


def test_short_form_filter_graph_end_card_composes_with_hook_only():
    """End card + hook (no subtitles): hook fires 0-3 s, end card
    fires 52-55 s, both bound to drawtext but on opposite ends of
    the clip. Both must coexist in the same chain ending at [v]."""
    graph = _short_form_filter_graph(
        end_card=True, hook="Today on the show.", total_duration=55.0,
    )
    # Hook still gates on first 3 s (B3: fade window ends at 3.05).
    assert "between(t,0,3.05)" in graph
    # End card gates on last 3 s.
    assert "between(t,52.00,55.00)" in graph
    assert graph.endswith("[v]")


def test_short_form_filter_graph_end_card_degenerate_short_clip():
    """If someone sets total_duration <= end_card_duration, the card
    should render for the whole clip rather than fail / produce a
    negative start time."""
    graph = _short_form_filter_graph(
        end_card=True, total_duration=2.0, end_card_duration=3.0,
    )
    assert "between(t,0.00,2.00)" in graph


def test_short_form_cmd_threads_end_card_params(tmp_path, monkeypatch):
    """``build_short_video(end_card=True, …)`` must pass the end-card
    params down through ``_short_form_cmd`` into the filter graph."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    out = tmp_path / "short.mp4"

    captured = []
    monkeypatch.setattr(
        "engine.video.subprocess.run",
        lambda cmd, **kw: (captured.append(list(cmd)),
                           type("R", (), {"returncode": 0})())[1],
    )
    build_short_video(
        audio, cover, out, duration=55.0,
        end_card=True,
        end_card_main_text="CUSTOM CTA",
        end_card_sub_text="Subscribe →",
        end_card_duration=4.0,
    )
    assert captured, "no ffmpeg cmd captured"
    graph = captured[-1][captured[-1].index("-filter_complex") + 1]
    assert "CUSTOM CTA" in graph
    assert "Subscribe " in graph  # ASCII portion of the sub-text
    assert "between(t,51.00,55.00)" in graph


# ---------------------------------------------------------------------------
# Shorts hook overlay auto-shrink-to-fit
# ---------------------------------------------------------------------------
#
# Same shrink-to-fit pattern the thumbnail uses (see
# tests/test_thumbnail_autofit.py). The 0-3 s drawtext hook used to
# render at a fixed fontsize=44 with a char-based 26 × 4 wrap that
# silently truncated > 104-char hooks. Auto-fit drops the font in
# 4-px steps (44 → 40 → 36 → 32) until the wrapped block fits the
# frame width without dropping words.

def test_autofit_hook_overlay_short_hook_stays_at_44():
    """A short hook (< 1 line at 44 px) must keep the legacy
    fontsize=44 — preserves the existing visual for the common case."""
    from engine.video import autofit_hook_overlay
    size, wrapped = autofit_hook_overlay("Tesla beats Q1 target.")
    assert size == 44
    # Single line, no break inserted.
    assert "\n" not in wrapped


def test_autofit_hook_overlay_long_hook_shrinks():
    """A hook that genuinely exceeds the 44-px 4-line budget must
    shrink to a smaller size in the candidate ladder. (The original
    char-based 26 × 4 = 104-char limit was conservative — a
    pixel-accurate wrap at 44 px fits ~38 chars / line × 4 lines =
    ~150 chars before needing to shrink.) This hook is ~170 chars
    so it forces a shrink."""
    from engine.video import autofit_hook_overlay
    long_hook = (
        "California regulators just disclosed the Tesla Semi's "
        "battery sizes at 822 kWh and 548 kWh, alongside a revised "
        "Cybertruck consumer range estimate that surprised analysts."
    )
    size, wrapped = autofit_hook_overlay(long_hook)
    # Must drop below the legacy default 44.
    assert size < 44, f"expected shrink for {len(long_hook)}-char hook, got {size}"
    assert size >= 32
    # Must NOT truncate at the chosen size — every source word fits.
    src_words = long_hook.split()
    out_words = wrapped.replace("\n", " ").split()
    assert len(out_words) == len(src_words), (
        f"words dropped during autofit: src={len(src_words)} "
        f"out={len(out_words)} wrapped={wrapped!r}"
    )


def test_autofit_hook_overlay_91_char_hook_fits_at_44():
    """Operator's original truncation complaint was at the char-based
    104-char budget. With the pixel-accurate wrap a 91-char hook
    fits comfortably at 44 px — no shrink needed. This is the
    regression direction (i.e. don't shrink hooks that don't need
    it)."""
    from engine.video import autofit_hook_overlay
    hook_91 = (
        "California regulators just disclosed the Tesla Semi's "
        "battery sizes at 822 kWh and 548 kWh."
    )
    assert len(hook_91) >= 80
    size, wrapped = autofit_hook_overlay(hook_91)
    assert size == 44, f"91-char hook should fit at 44 px, got {size}"
    src_words = hook_91.split()
    out_words = wrapped.replace("\n", " ").split()
    assert len(out_words) == len(src_words)


def test_autofit_hook_overlay_empty_hook():
    from engine.video import autofit_hook_overlay
    size, wrapped = autofit_hook_overlay("")
    assert wrapped == ""
    # Default font size still returned so callers don't have to
    # special-case the empty path.
    assert size == 44


def test_autofit_hook_overlay_respects_max_lines():
    """A 200-char hook MUST stay within max_lines=4 regardless of
    which fontsize wins. Too many lines on a 9:16 frame collides
    with the burn-in caption card at y≈1480."""
    from engine.video import autofit_hook_overlay
    runaway = "word " * 80  # 400 chars
    _size, wrapped = autofit_hook_overlay(runaway, max_lines=4)
    assert wrapped.count("\n") <= 3  # ≤4 lines


def test_autofit_hook_overlay_floor_appends_ellipsis_on_truncation():
    """When even the smallest fontsize can't fit, the floor renders
    the wrapped lines + a visible "…" on the last line so the
    truncation is OBVIOUS to a viewer rather than feeling like a
    cut-off bug."""
    from engine.video import autofit_hook_overlay
    runaway = "supercalifragilistic " * 30
    _size, wrapped = autofit_hook_overlay(
        runaway, max_lines=2, candidates=(44, 32),
    )
    # The last line gets the ellipsis marker once we hit the floor.
    assert wrapped.endswith("...")


def test_short_form_filter_graph_long_hook_uses_smaller_font():
    """End-to-end: a long hook in the actual filter graph should
    emit a smaller fontsize=N drawtext, not the default 44."""
    long_hook = (
        "Tesla just disclosed an unprecedented restructuring of its "
        "Cybercab manufacturing supply chain across three continents "
        "to absorb the surprise tariff changes announced overnight."
    )
    graph = _short_form_filter_graph(hook=long_hook)
    # The drawtext fontsize=N where N may be 40, 36, or 32 depending
    # on the exact font metrics — assert it's NOT the default 44.
    import re
    m = re.search(r"fontsize=(\d+)", graph)
    assert m, "no fontsize found in graph"
    chosen = int(m.group(1))
    assert chosen < 44, (
        f"long hook should have shrunk below 44, got {chosen}"
    )
    assert chosen >= 32, f"smallest allowed is 32, got {chosen}"


# ---------------------------------------------------------------------------
# Shorts end-card PNG overlay path
# ---------------------------------------------------------------------------
#
# May 2026 visual upgrade (PR #420): when a pre-rendered end-card
# PNG is passed to build_short_video, the filter graph swaps the
# drawbox+drawtext fallback for a single overlay= filter sourcing
# the PNG. The drawtext path stays as the soft-failure fallback
# (PNG generation failed → ship the text-only card).

def test_short_form_filter_graph_end_card_image_uses_overlay():
    """When ``end_card_image_input_label`` is provided, the filter
    graph must overlay that image (NOT emit drawbox + drawtext).

    July 31 2026 (C4): the card's input chain carries an alpha
    fade-in (``fade=...:alpha=1`` ramps only the alpha plane), so the
    card materialises over the last still in 0.45 s instead of
    guillotining it in a single frame."""
    graph = _short_form_filter_graph(
        end_card=True, total_duration=55.0,
        end_card_image_input_label="[3:v]",
    )
    # Overlay filter sourcing the image label, with the alpha fade-in.
    assert "[3:v]format=rgba,fade=t=in:st=52.00:d=0.45:alpha=1[endcard]" in graph
    assert "[endcard]overlay=x=0:y=0:enable='between(t,52.00,55.00)'[v]" in graph
    # Drawtext fallback is NOT emitted.
    assert "drawbox" not in graph
    assert "WATCH FULL EPISODE" not in graph


def test_short_form_filter_graph_end_card_drawtext_when_no_image():
    """No ``end_card_image_input_label`` keeps the legacy drawtext +
    drawbox fallback path so the soft-failure behaviour ships."""
    graph = _short_form_filter_graph(
        end_card=True, total_duration=55.0,
        end_card_image_input_label=None,
    )
    assert "drawbox" in graph
    assert "WATCH FULL EPISODE" in graph
    assert "[endcard]overlay" not in graph


def test_short_form_filter_graph_end_card_image_composes_with_captions():
    """Overlay path must compose cleanly with subtitles too —
    captions terminate at ``[capted]`` and the overlay chains from
    there to the final ``[v]``."""
    graph = _short_form_filter_graph(
        end_card=True, total_duration=55.0,
        subtitles_path="/tmp/short.srt",
        end_card_image_input_label="[4:v]",
    )
    # Card overlay terminates at [carded]; captions burn in ON TOP so
    # the final seconds of speech keep their text over the opaque PNG.
    assert "[carded]" in graph
    assert "[4:v]format=rgba,fade=t=in:st=52.00:d=0.45:alpha=1[endcard]" in graph
    assert "[endcard]overlay" in graph
    assert "[carded]subtitles=" in graph
    assert graph.index("[endcard]overlay") < graph.index("[carded]subtitles=")
    assert graph.endswith("[v]")
    assert graph.count("[v]") == 1


def test_short_form_cmd_adds_end_card_image_as_input(tmp_path, monkeypatch):
    """``build_short_video(end_card_image_path=path)`` must add the
    image as another ffmpeg ``-i`` input AND wire the right index
    label into the filter graph."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    end_card = tmp_path / "end_card.png"
    end_card.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal PNG magic
    out = tmp_path / "short.mp4"

    captured = []
    monkeypatch.setattr(
        "engine.video.subprocess.run",
        lambda cmd, **kw: (captured.append(list(cmd)),
                           type("R", (), {"returncode": 0})())[1],
    )
    build_short_video(
        audio, cover, out, duration=55.0,
        show_name="Tesla Shorts Time",  # → adds url_pill at [3:v]
        end_card=True,
        end_card_image_path=end_card,
    )
    assert captured, "no ffmpeg cmd captured"
    cmd = captured[-1]
    # The end-card PNG appears as a -i input.
    assert str(end_card) in cmd
    # Filter graph references the right index. With show_name=Tesla
    # the URL pill takes [3:v], so the end-card lands at [4:v].
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "[4:v]format=rgba,fade=" in graph
    assert "[endcard]" in graph


def test_short_form_cmd_end_card_image_index_when_no_url_pill(tmp_path, monkeypatch):
    """When the show passes ``show_name=None`` (legacy single
    pill), there's no URL pill at [3:v], so the end-card PNG lands
    at [3:v] instead of [4:v]."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    end_card = tmp_path / "end_card.png"
    end_card.write_bytes(b"\x89PNG\r\n\x1a\n")
    out = tmp_path / "short.mp4"

    captured = []
    monkeypatch.setattr(
        "engine.video.subprocess.run",
        lambda cmd, **kw: (captured.append(list(cmd)),
                           type("R", (), {"returncode": 0})())[1],
    )
    build_short_video(
        audio, cover, out, duration=55.0,
        show_name=None,  # legacy "Nerra Network" single pill, no URL pill
        end_card=True,
        end_card_image_path=end_card,
    )
    assert captured
    cmd = captured[-1]
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "[3:v]format=rgba,fade=" in graph
    assert "[endcard]" in graph


def test_short_form_cmd_missing_end_card_image_falls_back_to_drawtext(
    tmp_path, monkeypatch,
):
    """When the operator passes ``end_card_image_path`` but the file
    doesn't exist on disk, build_short_video must fall back to the
    drawtext path rather than crash or feed a missing file to
    ffmpeg."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    out = tmp_path / "short.mp4"

    captured = []
    monkeypatch.setattr(
        "engine.video.subprocess.run",
        lambda cmd, **kw: (captured.append(list(cmd)),
                           type("R", (), {"returncode": 0})())[1],
    )
    build_short_video(
        audio, cover, out, duration=55.0,
        show_name="Tesla Shorts Time",
        end_card=True,
        end_card_image_path=tmp_path / "nonexistent_end_card.png",
    )
    assert captured
    cmd = captured[-1]
    graph = cmd[cmd.index("-filter_complex") + 1]
    # Drawtext fallback in use.
    assert "drawbox" in graph
    assert "WATCH FULL EPISODE" in graph
    # Filter graph does NOT reference any [N:v] for the missing image.
    assert "[endcard]overlay" not in graph


# ---------------------------------------------------------------------------
# generate_shorts_end_card — PNG composition
# ---------------------------------------------------------------------------

def test_generate_shorts_end_card_produces_valid_png(tmp_path):
    """Smoke test: feed a tiny stub thumbnail in, get a 1080×1920
    PNG out with the expected text rendered."""
    from PIL import Image
    from engine.publisher import generate_shorts_end_card

    thumb = tmp_path / "long_thumb.jpg"
    Image.new("RGB", (1280, 720), (60, 80, 120)).save(thumb, format="JPEG")
    out = tmp_path / "end_card.png"

    generate_shorts_end_card(
        thumb, out,
        show_name="Tesla Shorts Time",
    )

    assert out.exists()
    with Image.open(out) as img:
        assert img.format == "PNG"
        assert img.size == (1080, 1920)


def test_generate_shorts_end_card_missing_thumbnail_still_renders(tmp_path):
    """Long-form thumbnail can fail upstream; the end card must
    still ship (just without the embedded thumbnail). Defensive
    against an unexpected upstream failure on rare episodes."""
    from PIL import Image
    from engine.publisher import generate_shorts_end_card

    out = tmp_path / "end_card.png"
    generate_shorts_end_card(
        tmp_path / "nonexistent.jpg", out,
        show_name="Tesla Shorts Time",
    )
    assert out.exists()
    with Image.open(out) as img:
        assert img.size == (1080, 1920)


def test_generate_shorts_end_card_custom_text(tmp_path):
    """``main_text`` / ``sub_text`` are configurable per show."""
    from PIL import Image
    from engine.publisher import generate_shorts_end_card

    thumb = tmp_path / "long_thumb.jpg"
    Image.new("RGB", (1280, 720), (10, 10, 10)).save(thumb, format="JPEG")
    out = tmp_path / "end_card.png"
    # Default vs custom shouldn't crash either way — that's the
    # contract we're verifying here.
    generate_shorts_end_card(
        thumb, out,
        show_name="Russian Show",
        main_text="СМОТРИТЕ ВЕСЬ ЭПИЗОД",
        sub_text="Подписывайтесь ↗",
    )
    assert out.exists()


# ---------------------------------------------------------------------------
# Chapter-aware scene schedule (June 2026) — per-scene slideshow durations
# ---------------------------------------------------------------------------
#
# engine.scene_scheduler plans [(scene, hold_seconds), …] so scene
# switches land on chapter boundaries. The renderer consumes the plan
# via scene_durations= (graph/cmd level) and scene_schedule= (public
# API). The invariant that matters most: a UNIFORM schedule reproduces
# the legacy graph/command byte-for-byte, and None keeps every legacy
# path untouched.

def test_slideshow_filter_graph_schedule_uses_cumulative_offsets():
    """Variable durations → xfade offsets are the CUMULATIVE visible
    time (sum(durations[:k])), not k * uniform_duration."""
    graph = _slideshow_filter_graph(
        scene_count=3, scene_durations=[10.0, 14.0, 8.0],
    )
    # Join 1 starts after scene 0's 10 s; join 2 after 10 + 14 = 24 s.
    assert "offset=10.00" in graph
    assert "offset=24.00" in graph
    # Each clip renders its OWN duration + the 0.6 s crossfade pad.
    assert "trim=duration=10.60" in graph
    assert "trim=duration=14.60" in graph
    assert "trim=duration=8.60" in graph
    assert graph.endswith("[v]")


def test_slideshow_filter_graph_uniform_schedule_matches_legacy():
    """A uniform durations list must reproduce the legacy graph EXACTLY
    (math.fsum of k equal floats rounds identically to k * duration) —
    the drift fence that says the schedule path is a strict superset."""
    for dur in (10.0, 13.85, 12.0):
        legacy = _slideshow_filter_graph(scene_count=4, scene_duration=dur)
        sched = _slideshow_filter_graph(
            scene_count=4, scene_durations=[dur] * 4,
        )
        assert sched == legacy


def test_slideshow_filter_graph_schedule_hard_cut_uses_per_scene_trims():
    """The crossfade=0 fallback (ffmpeg-failure retry) must keep the
    per-scene durations via each clip's own trim in the concat chain."""
    graph = _slideshow_filter_graph(
        scene_count=3, scene_durations=[10.0, 14.0, 8.0], crossfade=0.0,
    )
    assert "concat=n=3:v=1:a=0[v]" in graph
    assert "xfade" not in graph
    assert "trim=duration=10.00" in graph
    assert "trim=duration=14.00" in graph
    assert "trim=duration=8.00" in graph


def test_slideshow_filter_graph_schedule_length_mismatch_raises():
    with pytest.raises(ValueError, match="scene_durations length"):
        _slideshow_filter_graph(scene_count=3, scene_durations=[10.0, 14.0])


def test_slideshow_cmd_schedule_sets_per_input_duration(tmp_path):
    paths = [tmp_path / f"scene{i}.jpg" for i in range(3)]
    out = tmp_path / "slides.mp4"
    cmd = _slideshow_cmd(paths, out, scene_durations=[10.0, 14.0, 8.0])
    # Each looped image input's -t covers its own clip: dur + 0.6 + 0.5.
    t_indices = [i for i, x in enumerate(cmd) if x == "-t"]
    t_values = [cmd[i + 1] for i in t_indices]
    assert t_values == ["11.10", "15.10", "9.10"]


def test_slideshow_cmd_uniform_schedule_matches_legacy(tmp_path):
    paths = [tmp_path / f"scene{i}.jpg" for i in range(3)]
    out = tmp_path / "slides.mp4"
    legacy = _slideshow_cmd(paths, out, scene_duration=13.85)
    sched = _slideshow_cmd(paths, out, scene_durations=[13.85] * 3)
    assert sched == legacy


def test_render_slideshow_schedule_hard_cut_fallback(tmp_path, monkeypatch):
    """When the crossfade render fails, the hard-cut retry must carry
    the SAME per-scene durations (concat with per-scene trims)."""
    import subprocess as _subprocess

    from engine.video import _render_slideshow

    scenes = []
    for i in range(3):
        s = tmp_path / f"scene{i}.jpg"
        s.write_bytes(b"\xFF\xD8")
        scenes.append(s)
    out = tmp_path / "slides.mp4"

    calls = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        if len(calls) == 1:
            raise _subprocess.CalledProcessError(1, cmd, stderr="xfade broke")
        Path(cmd[-1]).write_bytes(b"\x00")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("engine.video.subprocess.run", fake_run)
    _render_slideshow(scenes, out, scene_durations=[10.0, 14.0, 8.0])
    assert len(calls) == 2
    retry_graph = calls[1][calls[1].index("-filter_complex") + 1]
    assert "concat=n=3" in retry_graph
    assert "xfade" not in retry_graph
    assert "trim=duration=10.00" in retry_graph
    assert "trim=duration=14.00" in retry_graph
    assert "trim=duration=8.00" in retry_graph


# These four pin the TWO-STAGE pipeline, which since July 29 2026 is the
# automatic fallback rather than the default path (engine.video
# ._single_pass_enabled flipped ON after an A/B showed equivalent output
# 23-34%% faster). They stay valuable exactly because that fallback still
# ships on any fused-command failure — so force the legacy path rather
# than deleting the coverage.
@pytest.mark.usefixtures("force_two_stage_render")
def test_build_long_form_video_uses_scene_schedule(tmp_path, monkeypatch):
    """scene_schedule= drives the stage-1 slideshow: scheduled scene
    order, per-scene -t inputs, cumulative xfade offsets."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    scenes = []
    for i in range(3):
        s = tmp_path / f"scene{i}.jpg"
        s.write_bytes(b"\xFF\xD8")
        scenes.append(s)
    out = tmp_path / "out.mp4"

    captured_cmds = []

    def fake_run(cmd, **kw):
        captured_cmds.append(list(cmd))
        if "-an" in cmd:
            Path(cmd[-1]).write_bytes(b"\x00")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("engine.video.subprocess.run", fake_run)
    monkeypatch.setattr("engine.audio.get_audio_duration", lambda _p: 32.0)
    schedule = [(scenes[0], 10.0), (scenes[2], 14.0), (scenes[1], 8.0)]
    build_long_form_video(audio, cover, out, scene_schedule=schedule)

    assert len(captured_cmds) == 2
    stage1 = captured_cmds[0]
    assert stage1[-1].endswith("_slides_sched.part.mp4")  # .part -> atomic replace
    # Scheduled ORDER (scene2 before scene1), not the input list order.
    i_indices = [i for i, x in enumerate(stage1) if x == "-i"]
    input_paths = [stage1[i + 1] for i in i_indices]
    assert input_paths == [str(scenes[0]), str(scenes[2]), str(scenes[1])]
    graph = stage1[stage1.index("-filter_complex") + 1]
    assert "offset=10.00" in graph
    assert "offset=24.00" in graph
    # Stage 2 still loops the slideshow background.
    assert "-stream_loop" in captured_cmds[1]


# These four pin the TWO-STAGE pipeline, which since July 29 2026 is the
# automatic fallback rather than the default path (engine.video
# ._single_pass_enabled flipped ON after an A/B showed equivalent output
# 23-34%% faster). They stay valuable exactly because that fallback still
# ships on any fused-command failure — so force the legacy path rather
# than deleting the coverage.
@pytest.mark.usefixtures("force_two_stage_render")
def test_build_long_form_video_short_schedule_keeps_legacy_path(tmp_path,
                                                                monkeypatch):
    """A degenerate 1-entry schedule must NOT flip the pipeline — the
    legacy uniform slideshow (from scene_paths) still runs."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    scenes = []
    for i in range(3):
        s = tmp_path / f"scene{i}.jpg"
        s.write_bytes(b"\xFF\xD8")
        scenes.append(s)
    out = tmp_path / "out.mp4"

    captured_cmds = []

    def fake_run(cmd, **kw):
        captured_cmds.append(list(cmd))
        if "-an" in cmd:
            Path(cmd[-1]).write_bytes(b"\x00")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("engine.video.subprocess.run", fake_run)
    monkeypatch.setattr("engine.audio.get_audio_duration", lambda _p: 36.0)
    build_long_form_video(audio, cover, out, scene_paths=scenes,
                          scene_schedule=[(scenes[0], 36.0)])
    assert len(captured_cmds) == 2
    assert captured_cmds[0][-1].endswith("_slides.part.mp4")  # .part -> atomic replace
    assert "_slides_sched" not in captured_cmds[0][-1]


def test_build_long_form_video_none_schedule_is_byte_identical(tmp_path,
                                                               monkeypatch):
    """scene_schedule=None / broll_clips=None must produce EXACTLY the
    same ffmpeg command as omitting the kwargs (legacy fence)."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    out = tmp_path / "out.mp4"

    captured_cmds = []
    monkeypatch.setattr(
        "engine.video.subprocess.run",
        lambda cmd, **kw: (captured_cmds.append(list(cmd)),
                           type("R", (), {"returncode": 0})())[1],
    )
    build_long_form_video(audio, cover, out)
    build_long_form_video(audio, cover, out,
                          scene_schedule=None, broll_clips=None)
    assert len(captured_cmds) == 2
    assert captured_cmds[0] == captured_cmds[1]


# ---------------------------------------------------------------------------
# Shorts sentence-cut background (June 2026) — full-length, no loop
# ---------------------------------------------------------------------------

def test_short_segment_durations_sum_to_clip_length():
    from engine.video import _short_segment_durations
    durs = _short_segment_durations([6.5, 13.9, 21.0], 30.0)
    assert durs == pytest.approx([6.5, 7.4, 7.1, 9.0])
    assert sum(durs) == pytest.approx(30.0)


def test_short_segment_durations_drops_end_hugging_and_bunched_cuts():
    from engine.video import _short_segment_durations
    # 29.9 hugs the 30 s end; 6.6 is within 0.5 s of 6.5.
    durs = _short_segment_durations([6.5, 6.6, 29.9], 30.0)
    assert durs == [6.5, 23.5]
    # Nothing usable → empty (caller keeps the legacy flat path).
    assert _short_segment_durations([29.9], 30.0) == []
    assert _short_segment_durations([], 30.0) == []


def test_build_short_video_scene_change_times_drops_stream_loop(tmp_path,
                                                                monkeypatch):
    """Explicit cut times cover the whole clip → the slideshow is built
    full-length and the composite must NOT -stream_loop it."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    scenes = []
    for i in range(3):
        s = tmp_path / f"scene{i}.jpg"
        s.write_bytes(b"\xFF\xD8")
        scenes.append(s)
    out = tmp_path / "short.mp4"

    captured_cmds = []

    def fake_run(cmd, **kw):
        captured_cmds.append(list(cmd))
        if "-an" in cmd:
            Path(cmd[-1]).write_bytes(b"\x00")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("engine.video.subprocess.run", fake_run)
    build_short_video(audio, cover, out, duration=55.0,
                      scene_paths=scenes,
                      scene_change_times=[6.8, 14.0, 21.5, 29.0, 36.5, 44.0])
    assert len(captured_cmds) == 2
    stage1, stage2 = captured_cmds
    # Stage 1: full-length scheduled slideshow (7 segments summing 55 s),
    # cumulative xfade offsets at the requested cut times.
    assert stage1[-1].endswith("_short_slides_sched.part.mp4")  # .part -> atomic replace
    graph1 = stage1[stage1.index("-filter_complex") + 1]
    assert "offset=6.80" in graph1
    assert "offset=14.00" in graph1
    assert "offset=44.00" in graph1
    # Stage 2: bg is the slideshow, WITHOUT the loop. Stage 1 renders to
    # a .part temp that is atomically replaced, so stage 2 sees the
    # final name.
    assert "-stream_loop" not in stage2
    assert stage1[-1].removesuffix(".part.mp4") + ".mp4" in stage2
    # Only the brand pill remains a looped image input.
    assert stage2.count("-loop") == 1


def test_build_short_video_cut_times_scenes_rotate_across_segments(tmp_path,
                                                                   monkeypatch):
    """6 segments from a 3-scene pool → the pool cycles in order."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    scenes = []
    for i in range(3):
        s = tmp_path / f"scene{i}.jpg"
        s.write_bytes(b"\xFF\xD8")
        scenes.append(s)
    out = tmp_path / "short.mp4"

    captured_cmds = []

    def fake_run(cmd, **kw):
        captured_cmds.append(list(cmd))
        if "-an" in cmd:
            Path(cmd[-1]).write_bytes(b"\x00")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("engine.video.subprocess.run", fake_run)
    build_short_video(audio, cover, out, duration=55.0,
                      scene_paths=scenes,
                      scene_change_times=[8.0, 16.0, 24.0, 32.0, 40.0])
    stage1 = captured_cmds[0]
    i_indices = [i for i, x in enumerate(stage1) if x == "-i"]
    input_paths = [stage1[i + 1] for i in i_indices]
    # Aug 2026 input dedup: 6 slots over a 3-scene pool open each unique
    # file ONCE and fan out via split — the rotation now lives in the
    # filter graph's consumption order, not in duplicate -i entries.
    assert input_paths == [str(s) for s in scenes]
    graph = stage1[stage1.index("-filter_complex") + 1]
    for j in range(3):
        assert f"[{j}:v]split=2[in{j}c0][in{j}c1]" in graph
    # 6 Ken Burns chains still render — one per slot.
    assert graph.count("zoompan=") == 6


def test_build_short_video_none_cut_times_is_byte_identical(tmp_path,
                                                            monkeypatch):
    """scene_change_times=None must produce EXACTLY the legacy command."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    out = tmp_path / "short.mp4"

    captured_cmds = []
    monkeypatch.setattr(
        "engine.video.subprocess.run",
        lambda cmd, **kw: (captured_cmds.append(list(cmd)),
                           type("R", (), {"returncode": 0})())[1],
    )
    build_short_video(audio, cover, out, duration=55.0)
    build_short_video(audio, cover, out, duration=55.0,
                      scene_change_times=None)
    assert len(captured_cmds) == 2
    assert captured_cmds[0] == captured_cmds[1]


def test_build_short_video_unusable_cut_times_keep_flat_loop_path(tmp_path,
                                                                  monkeypatch):
    """Cut times that all fall inside the end guard produce no usable
    segments → the legacy flat-pace loop path still ships."""
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    scenes = []
    for i in range(2):
        s = tmp_path / f"scene{i}.jpg"
        s.write_bytes(b"\xFF\xD8")
        scenes.append(s)
    out = tmp_path / "short.mp4"

    captured_cmds = []

    def fake_run(cmd, **kw):
        captured_cmds.append(list(cmd))
        if "-an" in cmd:
            Path(cmd[-1]).write_bytes(b"\x00")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("engine.video.subprocess.run", fake_run)
    build_short_video(audio, cover, out, duration=55.0,
                      scene_paths=scenes, scene_change_times=[54.9])
    assert len(captured_cmds) == 2
    assert captured_cmds[0][-1].endswith("_short_slides.part.mp4")  # .part -> atomic replace
    assert "-stream_loop" in captured_cmds[1]


# ---------------------------------------------------------------------------
# Evergreen B-roll interleave (June 2026) — local clips only, soft-fail
# ---------------------------------------------------------------------------

def _make_broll(tmp_path, n):
    clips = []
    for i in range(n):
        c = tmp_path / f"broll{i}.mp4"
        c.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        clips.append(c)
    return clips


def _make_long_form_fixtures(tmp_path):
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"\x00")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8")
    scenes = []
    for i in range(4):
        s = tmp_path / f"scene{i}.jpg"
        s.write_bytes(b"\xFF\xD8")
        scenes.append(s)
    return audio, cover, scenes


def test_build_long_form_video_broll_uses_hybrid_renderer(tmp_path,
                                                          monkeypatch):
    audio, cover, scenes = _make_long_form_fixtures(tmp_path)
    clips = _make_broll(tmp_path, 2)
    out = tmp_path / "out.mp4"

    captured_cmds = []

    def fake_run(cmd, **kw):
        captured_cmds.append(list(cmd))
        if "-an" in cmd:
            Path(cmd[-1]).write_bytes(b"\x00")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("engine.video.subprocess.run", fake_run)
    monkeypatch.setattr(
        "engine.audio.get_audio_duration",
        lambda p: 5.0 if str(p).endswith(".mp4") else 120.0,
    )
    build_long_form_video(audio, cover, out, scene_paths=scenes,
                          broll_clips=clips)
    # Stage 1 = hybrid render (stills + clips), stage 2 = composite.
    assert len(captured_cmds) == 2
    hybrid = captured_cmds[0]
    assert hybrid[-1].endswith("_hybrid.part.mp4")  # .part -> atomic replace
    # Both clips appear as plain (non-looped) inputs.
    for clip in clips:
        assert str(clip) in hybrid
    graph = hybrid[hybrid.index("-filter_complex") + 1]
    assert "concat=" in graph
    assert "-stream_loop" in captured_cmds[1]


def test_build_long_form_video_broll_caps_at_three(tmp_path, monkeypatch):
    audio, cover, scenes = _make_long_form_fixtures(tmp_path)
    clips = _make_broll(tmp_path, 5)
    out = tmp_path / "out.mp4"

    captured_cmds = []

    def fake_run(cmd, **kw):
        captured_cmds.append(list(cmd))
        if "-an" in cmd:
            Path(cmd[-1]).write_bytes(b"\x00")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("engine.video.subprocess.run", fake_run)
    monkeypatch.setattr(
        "engine.audio.get_audio_duration",
        lambda p: 5.0 if str(p).endswith(".mp4") else 120.0,
    )
    build_long_form_video(audio, cover, out, scene_paths=scenes,
                          broll_clips=clips)
    hybrid = captured_cmds[0]
    used = [c for c in clips if str(c) in hybrid]
    assert len(used) == 3
    assert used == clips[:3]


# These four pin the TWO-STAGE pipeline, which since July 29 2026 is the
# automatic fallback rather than the default path (engine.video
# ._single_pass_enabled flipped ON after an A/B showed equivalent output
# 23-34%% faster). They stay valuable exactly because that fallback still
# ships on any fused-command failure — so force the legacy path rather
# than deleting the coverage.
@pytest.mark.usefixtures("force_two_stage_render")
def test_build_long_form_video_broll_failure_degrades_to_slideshow(tmp_path,
                                                                   monkeypatch):
    """Any ffmpeg failure on the hybrid render must degrade to the pure
    slideshow — same soft-fallback philosophy as the crossfade retry."""
    import subprocess as _subprocess

    audio, cover, scenes = _make_long_form_fixtures(tmp_path)
    clips = _make_broll(tmp_path, 2)
    out = tmp_path / "out.mp4"

    captured_cmds = []

    def fake_run(cmd, **kw):
        captured_cmds.append(list(cmd))
        if cmd[-1].endswith((".part.mp4", "_hybrid.mp4")) and "_hybrid" in cmd[-1]:
            raise _subprocess.CalledProcessError(1, cmd, stderr="boom")
        if "-an" in cmd:
            Path(cmd[-1]).write_bytes(b"\x00")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("engine.video.subprocess.run", fake_run)
    monkeypatch.setattr(
        "engine.audio.get_audio_duration",
        lambda p: 5.0 if str(p).endswith(".mp4") else 120.0,
    )
    build_long_form_video(audio, cover, out, scene_paths=scenes,
                          broll_clips=clips)
    # hybrid (failed) → pure slideshow → composite.
    assert len(captured_cmds) == 3
    assert captured_cmds[0][-1].endswith("_hybrid.part.mp4")  # .part -> atomic replace
    assert captured_cmds[1][-1].endswith("_slides.part.mp4")  # .part -> atomic replace
    assert "-stream_loop" in captured_cmds[2]
    # No clip reaches the fallback slideshow.
    for clip in clips:
        assert str(clip) not in captured_cmds[1]


def test_build_long_form_video_broll_with_schedule_keeps_scene_order(
    tmp_path, monkeypatch,
):
    """B-roll + chapter schedule: scheduled stills keep their planned
    order in the hybrid sequence, with clips interleaved among them."""
    audio, cover, scenes = _make_long_form_fixtures(tmp_path)
    clips = _make_broll(tmp_path, 1)
    out = tmp_path / "out.mp4"

    captured_cmds = []

    def fake_run(cmd, **kw):
        captured_cmds.append(list(cmd))
        if "-an" in cmd:
            Path(cmd[-1]).write_bytes(b"\x00")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("engine.video.subprocess.run", fake_run)
    monkeypatch.setattr(
        "engine.audio.get_audio_duration",
        lambda p: 5.0 if str(p).endswith(".mp4") else 40.0,
    )
    schedule = [(scenes[2], 10.0), (scenes[0], 15.0), (scenes[1], 15.0)]
    build_long_form_video(audio, cover, out, scene_schedule=schedule,
                          broll_clips=clips)
    hybrid = captured_cmds[0]
    assert hybrid[-1].endswith("_hybrid.part.mp4")  # .part -> atomic replace
    i_indices = [i for i, x in enumerate(hybrid) if x == "-i"]
    input_paths = [hybrid[i + 1] for i in i_indices]
    # Clip opens the sequence; scheduled still order preserved after it.
    assert input_paths[0] == str(clips[0])
    assert [p for p in input_paths if p != str(clips[0])] == [
        str(scenes[2]), str(scenes[0]), str(scenes[1]),
    ]


def test_interleave_broll_into_schedule_scales_holds():
    """Unit-level: still order preserved, holds scaled so total stays
    ≈ the scheduled total after the clips take their share."""
    from engine.video import _interleave_broll_into_schedule

    schedule = [(Path("/s/a.png"), 20.0), (Path("/s/b.png"), 20.0),
                (Path("/s/c.png"), 20.0)]
    visuals = _interleave_broll_into_schedule(
        schedule, [Path("/c/x.mp4")], [6.0],
    )
    stills = [(path, dur) for path, is_video, dur in visuals if not is_video]
    clips = [(path, dur) for path, is_video, dur in visuals if is_video]
    assert [p for p, _ in stills] == [Path("/s/a.png"), Path("/s/b.png"),
                                      Path("/s/c.png")]
    assert clips == [(Path("/c/x.mp4"), 6.0)]
    total = sum(d for _, d in stills) + sum(d for _, d in clips)
    assert abs(total - 60.0) < 1e-6


# ---------------------------------------------------------------------------
# Long-form captions: sidecar track only, no burn-in (July 30 2026)
#
# The pipeline had always done BOTH — build_long_form_video received the SRT
# to burn into the pixels, AND upload_caption_track uploaded the same SRT as
# a real track. A viewer who pressed CC saw two sets of captions at once.
#
# The track wins on this surface: it toggles, auto-translates, the player
# positions it, YouTube indexes it, and it does not permanently cover the
# Grok scene imagery the episode paid for. Apple's video podcast player
# also expects sidecar captions. Shorts KEEP their burn-in — watched muted,
# in-feed, with no caption UI to fall back on.
# ---------------------------------------------------------------------------

class TestLongFormCaptionLayer:
    @staticmethod
    def _run_show():
        from pathlib import Path
        return (Path(__file__).resolve().parent.parent
                / "run_show.py").read_text(encoding="utf-8")

    def test_burn_in_defaults_off(self):
        from engine.config import YouTubeConfig
        assert YouTubeConfig().long_form_burn_in_captions is False

    def test_long_form_render_is_gated_on_the_flag(self):
        src = self._run_show()
        assert "long_form_burn_in_captions" in src
        # The old unconditional form must not come back.
        assert "\n                subtitles_path=srt_path,\n" not in src

    def test_shorts_burn_in_is_untouched(self):
        """Shorts are the surface where burned-in captions are correct."""
        src = self._run_show()
        assert "subtitles_path=this_srt_path" in src

    def test_caption_track_failure_is_visible(self):
        """It is now the ONLY caption layer, so silence is not acceptable."""
        src = self._run_show()
        assert "caption_track_uploaded" in src
        assert "shipped with NO captions" in src

    def test_burn_in_decision_is_centralized_in_defaults(self):
        """Aug 1 2026 reversal: burn-in is ON as the NETWORK default.

        History: July 30 made burn-in opt-in ("captions from the track,
        not the pixels") — and no show opted in, so long-form shipped
        with no on-screen captions at all and the July-31 per-word ASS
        layer was dormant. The operator's video directive turned it back
        on network-wide. The decision lives in _defaults.yaml ONLY:
        per-show files stay silent (a show wanting out sets false
        explicitly, which this guard permits but none does today)."""
        import pathlib
        import yaml as _yaml
        root = pathlib.Path(__file__).resolve().parent.parent
        defaults = _yaml.safe_load(
            (root / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert (defaults.get("youtube") or {}).get(
            "long_form_burn_in_captions") is True
        for path in sorted((root / "shows").glob("*.yaml")):
            if path.name == "_defaults.yaml":
                continue
            raw = _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            yt = raw.get("youtube") or {}
            assert yt.get("long_form_burn_in_captions") is not True, (
                f"{path.name}: redundant per-show flip — the default is "
                "already true; only explicit opt-OUTs belong in show YAMLs")


# ---------------------------------------------------------------------------
# July 31 2026 render pass — network grade (C1) + Shorts sharpen (C2)
# ---------------------------------------------------------------------------
#
# One grade chain (_GRADE_CHAIN) applied wherever the composite forms
# its [bg]: long-form both branches, Shorts, and the fused single-pass
# graph. Applied ONCE per delivered pixel — never inside the stage-1
# slideshow graph, or the two-stage path would grade twice.

class TestNetworkGrade:
    def _grade(self):
        from engine.video import _GRADE_CHAIN
        return _GRADE_CHAIN

    def test_grade_chain_constant_shape(self):
        grade = self._grade()
        assert "eq=contrast=1.05:saturation=1.08:gamma=0.98" in grade
        assert "vignette=angle=PI/5" in grade
        assert "gradfun=3.5:8" in grade
        # Deliberately NO noise grain — it fights the 4 Mbps maxrate
        # ceiling (see _VIDEO_ENCODE).
        assert "noise" not in grade

    def test_long_form_video_bg_branch_is_graded(self):
        graph = _long_form_filter_graph(bg_is_video=True)
        assert self._grade() in graph
        # Grade lands on the [bg] formation, before the pill overlays.
        assert graph.index(self._grade()) < graph.index("[bg]")

    def test_long_form_degraded_cover_branch_is_graded(self):
        graph = _long_form_filter_graph(bg_is_video=False)
        assert self._grade() in graph

    def test_short_form_bg_is_graded_and_sharpened(self):
        from engine.video import _SHORTS_SHARPEN
        graph = _short_form_filter_graph()
        assert self._grade() in graph
        # C2: mild luma-only output sharpen for the 9:16 upsample.
        assert _SHORTS_SHARPEN in graph
        assert "unsharp=5:5:0.5:5:5:0.0" in graph
        # Sharpen follows the grade in the bg chain.
        assert graph.index(self._grade()) < graph.index(_SHORTS_SHARPEN)

    def test_single_pass_graph_is_graded_once(self):
        from engine.video import _single_pass_long_form_filter_graph
        graph = _single_pass_long_form_filter_graph(3)
        assert graph.count(self._grade()) == 1
        assert graph.index(self._grade()) < graph.index("[bg]")

    def test_stage_one_slideshow_graph_is_not_graded(self):
        """The two-stage path grades at composite time; grading the
        intermediate too would double-apply the look."""
        graph = _slideshow_filter_graph(scene_count=3)
        assert self._grade() not in graph
        assert "vignette" not in graph

    def test_long_form_sharpen_is_shorts_only(self):
        """Long-form skips the unsharp stage — 2.0x lanczos prescale
        was measured as the knee there; sharpening a 16:9 slideshow
        would halo the Grok imagery for no phone-screen payoff."""
        assert "unsharp" not in _long_form_filter_graph(bg_is_video=True)
        assert "unsharp" not in _long_form_filter_graph(bg_is_video=False)


class TestRenderLookVersion:
    def test_constant_is_two(self):
        from engine.video import RENDER_LOOK_VERSION
        assert RENDER_LOOK_VERSION == 2

    def test_run_show_records_it_next_to_visual_mode(self):
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "run_show.py").read_text(encoding="utf-8")
        assert 'result["render_look_version"]' in src

    def test_pipeline_metric_recorded(self):
        from engine.pipeline import record_youtube_outcomes

        class _M:
            def __init__(self):
                self.data = {}

            def record(self, key, value):
                self.data[key] = value

        from types import SimpleNamespace
        m = _M()
        record_youtube_outcomes(
            m, {"render_look_version": 2,
                "long_form_captions_path": "ass"}, 1.0,
            config=SimpleNamespace(youtube=None),
        )
        assert m.data["render_look_version"] == 2
        assert m.data["long_form_captions_path"] == "ass"


# ---------------------------------------------------------------------------
# July 31 2026 render pass — long-form opening hook title (B4)
# ---------------------------------------------------------------------------

class TestLongFormHookTitle:
    HOOK = "Tesla just unveiled a Virtual Queue for Superchargers."

    def test_hook_burns_title_with_fade(self):
        graph = _long_form_filter_graph(hook=self.HOOK)
        assert "drawtext" in graph
        assert "Tesla" in graph
        # Centred around h*0.42 (above centre, clear of captions).
        assert "y=h*0.42" in graph
        # Alpha fade: in 0.3 s, out 0.6 s ending t=4; gate to 4.05 so
        # the ramp completes on screen.
        assert r"alpha='clip(t/0.3,0,1)*clip((4-t)/0.6,0,1)'" in graph
        assert r"enable='between(t,0,4.05)'" in graph
        assert graph.endswith("[v]")

    def test_no_hook_keeps_legacy_graph(self):
        assert _long_form_filter_graph() == _long_form_filter_graph(hook=None)
        assert "drawtext" not in _long_form_filter_graph(hook=None)

    def test_hook_composes_with_subtitles(self):
        graph = _long_form_filter_graph(
            hook=self.HOOK, subtitles_path="/tmp/captions.srt",
        )
        assert "subtitles=" in graph
        # Hook chains INTO the subtitle stage (per-line labels), never
        # double-terminates the graph.
        assert "[lfhooked]subtitles=" in graph
        assert graph.count("[v]") == 1
        assert graph.endswith("[v]")

    def test_long_hook_stacks_one_drawtext_per_line(self):
        """Per-line drawtext (the Tesla Ep485 'letter n' landmine —
        never a \\n inside text=), max 2 lines at 16:9."""
        long_hook = (
            "California regulators just disclosed the Tesla Semi's "
            "battery sizes at 822 kWh and 548 kWh in a filing."
        )
        graph = _long_form_filter_graph(hook=long_hook)
        import re as _re
        text_values = _re.findall(r"text='([^']*)'", graph)
        assert text_values
        for tv in text_values:
            assert "\n" not in tv
            assert r"\n" not in tv

    def test_hook_autofit_uses_16x9_candidates(self):
        """Autofit ladder at 1920 starts at 64 px — a short hook gets
        the biggest size, and every candidate stays in 64..40."""
        import re as _re
        graph = _long_form_filter_graph(hook="Tesla wins.")
        m = _re.search(r"fontsize=(\d+)", graph)
        assert m and int(m.group(1)) == 64
        long_graph = _long_form_filter_graph(hook=self.HOOK * 3)
        m2 = _re.search(r"fontsize=(\d+)", long_graph)
        assert m2 and 40 <= int(m2.group(1)) < 64

    def test_long_form_cmd_threads_hook(self):
        cmd = _long_form_cmd("voice.mp3", "cover.jpg", "brand.png",
                             "out.mp4", hook=self.HOOK)
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "Tesla" in graph and "y=h*0.42" in graph

    def test_single_pass_graph_threads_hook(self):
        from engine.video import _single_pass_long_form_filter_graph
        graph = _single_pass_long_form_filter_graph(3, hook=self.HOOK)
        assert "y=h*0.42" in graph
        assert r"enable='between(t,0,4.05)'" in graph
        assert graph.endswith("[v]")

    def test_build_long_form_video_threads_hook(self, tmp_path, monkeypatch):
        audio = tmp_path / "voice.mp3"
        audio.write_bytes(b"\x00")
        cover = tmp_path / "cover.jpg"
        cover.write_bytes(b"\xFF\xD8")
        out = tmp_path / "out.mp4"
        captured = []
        monkeypatch.setattr(
            "engine.video.subprocess.run",
            lambda cmd, **kw: (captured.append(list(cmd)),
                               type("R", (), {"returncode": 0})())[1],
        )
        build_long_form_video(audio, cover, out, hook=self.HOOK)
        graph = captured[-1][captured[-1].index("-filter_complex") + 1]
        assert "y=h*0.42" in graph

    def test_run_show_passes_hook_to_long_form(self):
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "run_show.py").read_text(encoding="utf-8")
        assert "hook=hook or None," in src


# ---------------------------------------------------------------------------
# July 31 2026 render pass — long-form per-word ASS captions (B1)
# ---------------------------------------------------------------------------

class TestLongFormAssSubtitles:
    def test_ass_path_skips_the_288_unit_force_style(self):
        """A per-word .ass declares its own PlayRes 1920x1080 and
        carries the long-form style in REAL pixels (Fontsize 98).
        Forcing the SRT force_style (FontSize=26 in 288-unit space)
        onto it would render ~26 px captions."""
        graph = _long_form_filter_graph(subtitles_path="/tmp/captions.ass")
        assert "subtitles=" in graph
        assert "captions.ass" in graph
        assert "force_style" not in graph
        assert graph.endswith("[v]")

    def test_srt_path_keeps_legacy_force_style(self):
        graph = _long_form_filter_graph(subtitles_path="/tmp/captions.srt")
        assert "force_style=" in graph
        assert "FontSize=26" in graph

    def test_single_pass_graph_matches(self):
        from engine.video import _single_pass_long_form_filter_graph
        ass_graph = _single_pass_long_form_filter_graph(
            3, subtitles_path="/tmp/captions.ass")
        assert "force_style" not in ass_graph
        srt_graph = _single_pass_long_form_filter_graph(
            3, subtitles_path="/tmp/captions.srt")
        assert "force_style=" in srt_graph

    def test_run_show_prefers_ass_with_srt_fallback(self):
        """The burn-in path mirrors the Shorts ASS-first/SRT-fallback
        pattern and records which layer shipped."""
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "run_show.py").read_text(encoding="utf-8")
        assert "transcript_to_ass_full" in src
        assert "(long_ass_path or srt_path)" in src
        assert 'result["long_form_captions_path"] = "ass"' in src
        assert 'result["long_form_captions_path"] = "srt_fallback"' in src


# ---------------------------------------------------------------------------
# July 31 2026 render pass — Ken Burns vocabulary + per-episode seed (A1)
# ---------------------------------------------------------------------------

def _eval_kb_expr(expr: str, *, on: float, n_zoom: float) -> float:
    """Numerically evaluate a zoompan x/y expression with iw=ih=1."""
    e = expr.replace("iw", "1.0").replace("ih", "1.0")
    e = e.replace("zoom", repr(float(n_zoom)))
    e = e.replace("on", repr(float(on)))
    return eval(e)  # noqa: S307 — controlled arithmetic-only expression


class TestKenBurnsVocabulary:
    def test_eight_moves_with_legacy_prefix(self):
        from engine.video import _KB_LEGACY_MOVE_COUNT, _KB_MOVES
        assert len(_KB_MOVES) == 8
        # The FIRST FOUR entries are the legacy vocabulary in the
        # legacy order — the A/B control arm indexes into this prefix.
        assert _KB_MOVES[:4] == ("in_centre", "out_centre",
                                 "in_pan_x", "out_pan_y")
        assert _KB_MOVES[4:] == ("in_pan_y", "out_pan_x",
                                 "in_pan_xy", "out_pan_xy")
        assert _KB_LEGACY_MOVE_COUNT == 4

    def test_zoom_amplitudes(self):
        from engine.video import _KB_ZOOM_AMPLITUDES
        assert _KB_ZOOM_AMPLITUDES == (1.06, 1.09, 1.12)

    def test_pan_feasibility_all_moves_all_amplitudes(self):
        """Numeric feasibility: for every move x amplitude, the
        requested window origin stays inside [0, 1 - 1/zoom] on both
        axes for every frame — i.e. zoompan never has to clamp, which
        is the edge-anchored-zoom defect the July 30 pass fixed."""
        from engine.video import _KB_MOVES, _KB_ZOOM_AMPLITUDES, _ken_burns
        frames = 90
        for move in _KB_MOVES:
            for amp in _KB_ZOOM_AMPLITUDES:
                z_expr, x_expr, y_expr = _ken_burns(
                    frames, move, zoom_max=amp)
                for on in range(frames):
                    z = _eval_kb_expr(z_expr, on=on, n_zoom=1.0)
                    assert 1.0 - 1e-9 <= z <= amp + 1e-9, (
                        f"{move}@{amp}: zoom {z} out of band at on={on}")
                    for axis, expr in (("x", x_expr), ("y", y_expr)):
                        origin = _eval_kb_expr(expr, on=on, n_zoom=z)
                        upper = 1.0 - 1.0 / z
                        assert -1e-9 <= origin <= upper + 1e-9, (
                            f"{move}@{amp} {axis}: origin {origin:.6f} "
                            f"outside [0, {upper:.6f}] at on={on} (zoom {z:.4f})"
                        )

    def test_diagonals_ramp_both_axes(self):
        from engine.video import _ken_burns
        _z, x, y = _ken_burns(60, "in_pan_xy", zoom_max=1.12)
        # Both axes carry the same travel ramp (not a static 0.5).
        assert "0.5+" in x and "0.5+" in y

    def test_seed_offsets_the_rotation_deterministically(self):
        from engine.video import _kb_seed_from_stem
        s1 = _kb_seed_from_stem("Tesla_Pod_Ep042_20260731")
        s2 = _kb_seed_from_stem("Tesla_Pod_Ep042_20260731")
        s3 = _kb_seed_from_stem("Tesla_Pod_Ep043_20260801")
        assert s1 == s2          # re-render identical
        assert s1 != s3          # episodes de-synchronize
        assert isinstance(s1, int) and s1 >= 0

    def test_seed_changes_the_graph(self):
        g0 = _slideshow_filter_graph(scene_count=4, kb_seed=0)
        g1 = _slideshow_filter_graph(scene_count=4, kb_seed=1)
        assert g0 != g1

    def test_extended_graph_alternates_amplitudes(self):
        """Three consecutive slots at seed 0 carry three DISTINCT
        rung-scaled amplitudes (the 1.06/1.09/1.12 ladder survives as a
        ±1/3 rhythm multiplier on the duration-adaptive base)."""
        import re as _re
        graph = _slideshow_filter_graph(scene_count=3, kb_seed=0)
        amps = set(_re.findall(r"zoompan=z='\((?:1\+|[0-9.]+-)([0-9.]+)\*", graph))
        assert len(amps) == 3, amps

    def test_amplitude_scales_with_hold_length(self):
        """Aug 2026: a fixed amplitude made a 29 s hold crawl at
        ~0.3%/s — sub-perceptual, functionally a frozen still. The zoom
        range now grows with the hold so travel speed stays visible."""
        import re as _re

        def amp_of(graph):
            return float(_re.search(r"zoompan=z='\((?:1\+|[0-9.]+-)([0-9.]+)\*", graph).group(1))

        short_hold = _slideshow_filter_graph(
            scene_count=2, scene_durations=[5.0, 5.0])
        long_hold = _slideshow_filter_graph(
            scene_count=2, scene_durations=[29.0, 29.0])
        assert amp_of(long_hold) > amp_of(short_hold) * 2

    def test_amplitude_floor_and_ceiling(self):
        import re as _re
        from engine.video import _KB_AMP_MIN, _KB_AMP_MAX

        def amps(graph):
            return [float(a) for a in
                    _re.findall(r"zoompan=z='\((?:1\+|[0-9.]+-)([0-9.]+)\*", graph)]

        tiny = _slideshow_filter_graph(scene_count=2,
                                       scene_durations=[2.0, 2.0])
        huge = _slideshow_filter_graph(scene_count=2,
                                       scene_durations=[90.0, 90.0])
        assert all(a >= _KB_AMP_MIN - 1e-9 for a in amps(tiny))
        assert all(a <= _KB_AMP_MAX + 1e-9 for a in amps(huge))

    def test_legacy_mode_pins_four_moves_at_109(self):
        """kb_extended=False must reproduce the pre-A1 graph: first 4
        moves in index order at the single 1.09 amplitude, seed
        ignored — this IS the Shorts A/B control arm's render."""
        from engine.video import _ZOOM_MAX
        legacy = _slideshow_filter_graph(scene_count=4, kb_extended=False)
        assert str(_ZOOM_MAX) in legacy
        assert "1.06" not in legacy and "1.12" not in legacy
        # Seed is ignored in legacy mode — byte-identical either way.
        assert legacy == _slideshow_filter_graph(
            scene_count=4, kb_extended=False, kb_seed=12345)

    def test_build_short_video_kb_extended_defaults_true(self):
        import inspect
        params = inspect.signature(build_short_video).parameters
        assert "kb_extended" in params
        assert params["kb_extended"].default is True

    def test_run_show_gates_shorts_kb_on_the_ab(self):
        """run_show must pass kb_extended=not <A/B enabled> so an
        enrolled show's control arm is not upgraded mid-experiment."""
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "run_show.py").read_text(encoding="utf-8")
        assert "kb_extended=not _ab_on," in src

    def test_build_short_video_legacy_kb_when_not_extended(self, tmp_path,
                                                           monkeypatch):
        """End-to-end: kb_extended=False keeps the stage-1 vertical
        slideshow on the legacy vocabulary (no 1.06/1.12 amplitudes)."""
        audio = tmp_path / "voice.mp3"
        audio.write_bytes(b"\x00")
        cover = tmp_path / "cover.jpg"
        cover.write_bytes(b"\xFF\xD8")
        scenes = []
        for i in range(3):
            s = tmp_path / f"scene{i}.jpg"
            s.write_bytes(b"\xFF\xD8")
            scenes.append(s)
        out = tmp_path / "short.mp4"

        captured = []

        def fake_run(cmd, **kw):
            captured.append(list(cmd))
            if "-an" in cmd:
                Path(cmd[-1]).write_bytes(b"\x00")
            return type("R", (), {"returncode": 0})()

        monkeypatch.setattr("engine.video.subprocess.run", fake_run)
        build_short_video(audio, cover, out, duration=55.0,
                          scene_paths=scenes, kb_extended=False)
        stage1 = captured[0]
        graph = stage1[stage1.index("-filter_complex") + 1]
        assert "1.09" in graph
        assert "1.06" not in graph and "1.12" not in graph


# ---------------------------------------------------------------------------
# July 31 2026 render pass — crisper pills (B5)
# ---------------------------------------------------------------------------

class TestPillV2:
    def test_pill_is_delivered_at_requested_size(self, tmp_path):
        """2x supersample is internal — the saved PNG is the requested
        delivery size (LANCZOS-downscaled)."""
        from PIL import Image
        target = tmp_path / "pill.png"
        _make_brand_pill(target, width=220, height=60)
        with Image.open(target) as img:
            assert img.size == (220, 60)

    def test_pill_has_cyan_left_edge_accent(self, tmp_path):
        """A ~2 px Nerra-cyan accent inside the left edge of the
        rounded rect — brand cohesion with the caption highlight."""
        from PIL import Image
        target = tmp_path / "pill.png"
        _make_brand_pill(target, width=220, height=60)
        with Image.open(target) as img:
            r, g, b, a = img.convert("RGBA").getpixel((1, 30))
        assert a > 0
        # Cyan-dominant: blue and green well above red.
        assert b > 150 and g > 100 and b > r + 60, (r, g, b, a)

    def test_pill_centre_is_still_the_dark_field(self, tmp_path):
        from PIL import Image
        target = tmp_path / "pill.png"
        _make_brand_pill(target, width=220, height=60, text="")
        with Image.open(target) as img:
            r, g, b, a = img.convert("RGBA").getpixel((110, 30))
        assert a > 0 and max(r, g, b) < 60

    def test_pill_v2_idempotent(self, tmp_path):
        target = tmp_path / "pill.png"
        _make_brand_pill(target)
        first = target.stat().st_mtime_ns
        _make_brand_pill(target)
        assert target.stat().st_mtime_ns == first

    def test_builders_use_versioned_filenames(self, tmp_path, monkeypatch):
        """The cache is path-keyed, so the supersampled look only ships
        if the builders use the bumped names."""
        audio = tmp_path / "voice.mp3"
        audio.write_bytes(b"\x00")
        cover = tmp_path / "cover.jpg"
        cover.write_bytes(b"\xFF\xD8")
        monkeypatch.setattr(
            "engine.video.subprocess.run",
            lambda cmd, **kw: type("R", (), {"returncode": 0})())
        build_short_video(audio, cover, tmp_path / "short.mp4",
                          duration=55.0, show_name="Tesla Shorts Time")
        assert (tmp_path / "_show_pill_v2_tesla_shorts_time.png").exists()
        assert (tmp_path / "_url_pill_v2.png").exists()
        # Stale v1 names must not be written.
        assert not (tmp_path / "_show_pill_tesla_shorts_time.png").exists()
        assert not (tmp_path / "_url_pill_v1.png").exists()
