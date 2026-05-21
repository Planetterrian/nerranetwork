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
    refactor doesn't quietly re-introduce them."""
    graph = _long_form_filter_graph()
    assert "showcqt" not in graph
    assert "showwaves" not in graph
    assert "drawbox" not in graph
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
    graph = _short_form_filter_graph()
    assert "scale=1080:1920" in graph
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
    # Hook caption shows for the first 3s only.
    assert r"enable='between(t,0,3)'" in graph
    # Some text from the hook appears (escaped) in the graph.
    assert "Tesla" in graph
    assert graph.endswith("[v]")


def test_short_form_filter_graph_hook_sits_in_bottom_third():
    """May 2026 operator review: the shorts hook moved out of the
    top half (was ``y=240``) into the bottom third of the
    1080x1920 frame. ``y=h*0.70`` puts the baseline at y≈1344,
    well inside the bottom-third zone (y > 1280) and above the
    URL pill at y≈1820. Pin the new position so a future style
    edit doesn't drift back to the top."""
    graph = _short_form_filter_graph(hook="anything")
    # New bottom-third position.
    assert "y=h*0.70" in graph
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
    # Filter graph references vertical Shorts geometry.
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "scale=1080:1920" in graph
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
    assert r"enable='between(t,0,3)'" in graph


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
    brand_pill = out.parent / "_brand_pill_v2.png"
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
    assert (out.parent / "_brand_pill_v2.png").exists()


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
    """End-to-end pin: the rendered Shorts filter graph for a
    realistic multi-line hook MUST NOT contain real newline
    characters inside the drawtext text= region. A real newline
    there terminates ffmpeg's single-quoted parsing region and
    breaks the entire filter graph — exactly what failed Tesla
    Ep466's Shorts upload on May 8 2026."""
    hook = (
        "California regulators just disclosed the Tesla Semi's "
        "battery sizes at 822 kWh and 548 kWh."
    )
    graph = _short_form_filter_graph(hook=hook)
    # Find the drawtext text= region.
    import re as _re
    m = _re.search(r"text='([^']*(?:\\'[^']*)*)'", graph)
    assert m is not None, "drawtext text= region not found in graph"
    text_value = m.group(1)
    # No real newlines may appear inside the quoted region.
    assert "\n" not in text_value, (
        f"Real newline survived into drawtext text= value (would break "
        f"ffmpeg parsing): {text_value!r}"
    )
    # But the literal escape sequence \n MUST be present so the rendered
    # caption still wraps to multiple lines.
    assert r"\n" in text_value, (
        f"Multi-line hook should produce literal \\n breaks; got "
        f"{text_value!r}"
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
    # One zoompan chain per scene, then a final concat.
    assert graph.count("zoompan") == 4
    assert graph.count("[s0]") >= 1
    assert graph.count("[s3]") >= 1
    assert "concat=n=4:v=1:a=0[v]" in graph
    assert graph.endswith("[v]")


def test_slideshow_filter_graph_zoom_per_scene():
    """Slideshow zoom is faster than the single-image Ken Burns
    (each scene is only ~12s)."""
    graph = _slideshow_filter_graph(scene_count=2)
    assert "min(zoom+0.0006,1.12)" in graph


def test_slideshow_cmd_has_one_input_per_scene(tmp_path):
    paths = [tmp_path / f"scene{i}.jpg" for i in range(3)]
    out = tmp_path / "slides.mp4"
    cmd = _slideshow_cmd(paths, out)

    # Three -i flags (one per scene), three -loop flags.
    assert cmd.count("-i") == 3
    assert cmd.count("-loop") == 3
    # No audio in slideshow output.
    assert "-an" in cmd
    # Encoding profile applies (keyframe args present).
    for token in _VIDEO_ENCODE:
        assert token in cmd
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
    # Subtitles sit in the bottom third of the 1920x1080 frame (May
    # 2026 operator review). ``MarginV=120`` puts the baseline ~120
    # px above the bottom edge — comfortably below y=720 (bottom
    # third boundary) and high enough that the YouTube progress bar
    # doesn't overlap on mobile.
    assert "MarginV=120" in graph
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
    asked to remove ("make it not as prominent")."""
    assert "FontName=DejaVu Sans" in _SUBTITLES_FORCE_STYLE
    assert "Alignment=2" in _SUBTITLES_FORCE_STYLE
    # Bottom-third position (May 2026 operator review).
    assert "MarginV=120" in _SUBTITLES_FORCE_STYLE
    # BorderStyle=1 = outline + soft shadow only (no opaque box).
    # Keeps the slideshow imagery visible behind the words.
    assert "BorderStyle=1" in _SUBTITLES_FORCE_STYLE
    assert "BorderStyle=3" not in _SUBTITLES_FORCE_STYLE
    # Smaller font reads less as "subtitle bar" and more as
    # "auto-caption hint" — also matches YouTube auto-caption sizing.
    assert "FontSize=18" in _SUBTITLES_FORCE_STYLE


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
    # Stage 1 has 3 inputs (one per scene), no audio output.
    assert "-an" in captured_cmds[0]
    assert captured_cmds[0].count("-i") == 3
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
    assert "concat=n=3:v=1:a=0[v]" in graph


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
