"""Tests for the hybrid short video-clip generator + the video.py hybrid graph."""

from pathlib import Path

import engine.grok_video_clips as gvc
from engine.grok_video_clips import ClipSet, _short_clip_prompt, generate_short_clips
from engine.video import _build_hybrid_sequence, _hybrid_filter_graph


def test_count_zero_returns_empty():
    out = generate_short_clips(work_dir=Path("/tmp"), episode_num=1, count=0)
    assert isinstance(out, ClipSet)
    assert len(out) == 0


def test_no_api_key_is_noop(monkeypatch):
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    out = generate_short_clips(work_dir=Path("/tmp"), episode_num=1, count=3)
    assert len(out) == 0
    assert out.total_cost_usd == 0.0


def test_short_clip_prompt_uses_context_and_bans_text():
    class _YT:
        video_genre = "aerospace-engineering"
        video_mood = "epic"
        video_keywords = ["Starship", "Raptor"]
        video_visual_style = "cinematic rockets"

    class _Cfg:
        youtube = _YT()

    p = _short_clip_prompt("Starship test flight", _Cfg(), "hook", 5)
    assert "Starship test flight" in p
    assert "No text" in p
    assert "aerospace-engineering" in p


def test_hybrid_sequence_interleaves_clips_and_caps_hold():
    stills = [Path(f"s{i}.jpg") for i in range(4)]
    clips = [Path("c0.mp4"), Path("c1.mp4")]
    durs = [5.0, 5.0]
    visuals = _build_hybrid_sequence(
        stills, clips, durs, audio_duration_s=600.0, max_scene_hold_s=25.0,
    )
    # Both clips present and flagged as video.
    videos = [v for v in visuals if v[1]]
    assert len(videos) == 2
    # Stills cycled so none holds longer than the cap.
    still_holds = [v[2] for v in visuals if not v[1]]
    assert still_holds and max(still_holds) <= 25.0
    # First visual is a clip (opens with motion).
    assert visuals[0][1] is True


def test_hybrid_sequence_no_clips_is_pure_stills():
    stills = [Path("a.jpg"), Path("b.jpg")]
    visuals = _build_hybrid_sequence(stills, [], [], audio_duration_s=60.0)
    assert all(v[1] is False for v in visuals)


def test_hybrid_filter_graph_handles_mixed_inputs():
    visuals = [
        (Path("c0.mp4"), True, 5.0),
        (Path("s0.jpg"), False, 12.0),
        (Path("s1.jpg"), False, 12.0),
    ]
    graph = _hybrid_filter_graph(visuals, width=1920, height=1080, fps=30)
    # One concat over all three segments.
    assert "concat=n=3:v=1:a=0[v]" in graph
    # The image segment uses zoompan; the video segment does not.
    assert "zoompan" in graph
    # Each input mapped to its own segment label.
    assert "[s0]" in graph and "[s1]" in graph and "[s2]" in graph
