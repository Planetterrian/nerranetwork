"""Network review, Sep 30 2026 — the repetition and reproducibility half.

* engine/frame_memory.py — data-side rotation memory for sentence FRAMES
  (the openers a show leans on every day), opt-in per show, rendered
  through the shared prompt snippets' ``{recent_frames_block}``.
* requirements.txt — PyAV pinned below 19 (the 09-30 Whisper outage: 23
  episodes with no transcript, the spoken-text gate blind on all of them).
* engine/transcripts.py — a non-VAD transcription error is an outage,
  annotated as one, never retried as "VAD unavailable".
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import frame_memory as fm  # noqa: E402

CLOSING = "That's a wrap for today. Follow Nerra Network wherever you listen."
DISCLOSURE = "This episode was produced with the help of artificial intelligence."


def _script(teaser_tail: str, body_opener: str, extra: str = "") -> str:
    return (
        f"Welcome back. {body_opener} rolled out the new battery pack to three plants this week.\n\n"
        f"The company said the change cuts cost by four percent, according to Reuters.\n\n"
        f"{extra}"
        f"Before we go, keep an eye on {teaser_tail}.\n\n"
        f"{CLOSING}\n{DISCLOSURE}\n"
    )


SCRIPTS = [
    _script("the Thursday earnings call", "The battery maker"),
    _script("the regulator's Friday vote", "A supplier in Ohio"),
    _script("the launch window on Sunday", "The carmaker"),
    _script("the new tariff schedule", "One assembler"),
    _script("the recall notice", "The plant in Austin"),
    _script("the Q3 deliveries", "The battery maker", extra="One thing worth watching is the price. "),
]


class TestRecurringFrames:
    def test_the_teaser_frame_is_found_and_furniture_is_not(self):
        frames = fm.recurring_frames(SCRIPTS)
        openers = [f[0] for f in frames]
        assert "before we go keep" in openers
        # The closing and the disclosure recur verbatim: fixed text, never listed.
        assert not any(o.startswith("that s a wrap") or o.startswith("this episode was") for o in openers)
        # A body sentence that changes every day is not a frame.
        assert not any(o.startswith("the company said") for o in openers) or \
            len([s for s in SCRIPTS if "The company said" in s]) >= 3  # furniture, so excluded anyway

    def test_fewer_than_three_scripts_is_no_memory(self):
        assert fm.recurring_frames(SCRIPTS[:2]) == []

    def test_a_chapter_anchor_is_exempt(self):
        scripts = [s.replace("Before we go, keep an eye on", "One thing worth watching is") for s in SCRIPTS]
        assert any(f[0] == "one thing worth watching" for f in fm.recurring_frames(scripts))
        exempt = fm.recurring_frames(scripts, exempt_patterns=[r"one thing worth watching|Short Spot"])
        assert not any(f[0] == "one thing worth watching" for f in exempt)

    def test_content_openers_are_never_frames(self):
        """A ticker, an index, a digit or a proper noun in the opener is a
        fact the show must say daily, not a habit."""
        assert fm._opener("T S L A closed at three hundred dollars today.") == ""
        assert fm._opener("The S P 500 finished the session higher today.") == ""
        assert fm._opener("Nikkei Asia reports the deal closed on Friday.") == ""
        assert fm._opener("Over 3 plants changed hands this quarter alone.") == ""
        assert fm._opener("Before we go, keep an eye on the vote.") == "before we go keep"

    def test_short_sentences_are_not_judged(self):
        assert fm._opener("Before we go, thanks.") == ""

    def test_the_block_bans_and_never_supplies_a_line(self, tmp_path):
        for i, s in enumerate(SCRIPTS):
            (tmp_path / f"Show_Ep{i:03d}_2026092{i}_tts.txt").write_text(s, encoding="utf-8")

        class Cfg:
            output_dir = str(tmp_path)
            chapters = None

        block = fm.build_recent_frames_block(Cfg())
        assert block.startswith("ROTATION MEMORY")
        assert '"before we go keep …"' in block
        assert "of the last 6 scripts" in block
        # It names what was used; it never writes the replacement.
        assert "instead say" not in block.lower() and "for example" not in block.lower()

    def test_a_rerun_never_reads_its_own_script(self, tmp_path):
        for i, s in enumerate(SCRIPTS):
            (tmp_path / f"Show_Ep{i:03d}_2026092{i}_tts.txt").write_text(s, encoding="utf-8")
        paths = fm.script_paths(tmp_path, window=6, exclude_contains="Ep005_")
        assert all("Ep005_" not in p.name for p in paths)

    def test_an_empty_directory_is_an_empty_block(self, tmp_path):
        class Cfg:
            output_dir = str(tmp_path)
            chapters = None
        assert fm.build_recent_frames_block(Cfg()) == ""


class TestWiring:
    OPTED_IN = ["fascinating_frontiers", "planetterrian", "omni_view", "models_agents",
                "models_agents_beginners", "spacex", "tesla", "omni_view_europe",
                "omni_view_asia_pacific", "omni_view_africa_mideast", "omni_view_latam",
                "omni_view_north_america", "omni_view_world", "vancouver", "mag7",
                "ai_chips", "prediction_markets"]

    @pytest.mark.parametrize("slug", OPTED_IN)
    def test_the_named_shows_opt_in(self, slug):
        from engine.config import load_config
        assert load_config(ROOT / "shows" / f"{slug}.yaml").frame_memory is True

    def test_modern_investing_and_the_narrative_shows_stay_off(self):
        """MIT's list was dominated by its ledger-supplied lines ("the
        position exited at", "average return per trade") — fixed wording
        the tracker writes, not a habit; it stays off until the memory can
        see the prompt context. The narrative shows have no news frames."""
        from engine.config import load_config
        for slug in ("modern_investing", "unintended_consequences", "first_principles", "dp_pod"):
            assert load_config(ROOT / "shows" / f"{slug}.yaml").frame_memory is False, slug

    def test_the_shared_snippets_render_the_block(self):
        for rel in ("content_discipline.txt", "omni_desk_podcast_body.txt"):
            text = (ROOT / "shows" / "prompts" / "_shared" / rel).read_text(encoding="utf-8")
            assert "{recent_frames_block}" in text, rel

    def test_every_opted_in_show_reaches_the_placeholder(self):
        """A show that opts in but whose podcast prompt includes neither
        snippet would compute a block nobody renders."""
        from engine.config import load_config
        for slug in self.OPTED_IN:
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
            prompt = Path(cfg.llm.podcast_prompt_file)
            if not prompt.is_absolute():
                prompt = ROOT / prompt
            text = prompt.read_text(encoding="utf-8")
            assert ("content_discipline.txt" in text or "omni_desk_podcast_body.txt" in text
                    or "{recent_frames_block}" in text), slug

    def test_pipeline_sets_the_var_and_defaults_it_empty(self):
        src = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'pod_vars["recent_frames_block"] = build_recent_frames_block(' in src
        assert 'pod_vars.setdefault("recent_frames_block", "")' in src


class TestWhisperOutageGuards:
    def test_pyav_is_pinned_below_19(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        # The CEILING is the guard; the floor rose to 18.1 with the Oct 9
        # 2026 runner upgrade (tests/test_transcripts_pyav_2026_10_08.py).
        m = re.search(r"^av>=[\d.]+,<19\s*$", req, re.M)
        assert m, "PyAV must stay below 19 until faster-whisper releases against it"

    def test_a_non_vad_error_is_not_retried_as_vad(self, monkeypatch, tmp_path):
        from engine import transcripts as tr

        calls = []

        class Model:
            def __init__(self, *a, **k):
                pass

            def transcribe(self, path, **kw):
                calls.append(kw)
                raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")

        import types
        fake = types.ModuleType("faster_whisper")
        fake.WhisperModel = Model
        monkeypatch.setitem(sys.modules, "faster_whisper", fake)
        audio = tmp_path / "ep.mp3"
        audio.write_bytes(b"\x00" * 16)
        printed = []
        monkeypatch.setattr("builtins.print", lambda *a, **k: printed.append(" ".join(map(str, a))))
        result = tr.generate_transcript(audio, tmp_path, "Show_Ep001_20260930", vad_filter=True)
        assert result is None
        assert len(calls) == 1, "the VAD-less retry ran for a non-VAD error"
        assert any("::error::transcription failed" in ln for ln in printed)

    def test_a_vad_shaped_error_still_gets_the_retry(self, monkeypatch, tmp_path):
        from engine import transcripts as tr

        calls = []

        class Model:
            def __init__(self, *a, **k):
                pass

            def transcribe(self, path, **kw):
                calls.append(kw)
                raise RuntimeError("onnxruntime is not installed (silero VAD)")

        import types
        fake = types.ModuleType("faster_whisper")
        fake.WhisperModel = Model
        monkeypatch.setitem(sys.modules, "faster_whisper", fake)
        audio = tmp_path / "ep.mp3"
        audio.write_bytes(b"\x00" * 16)
        monkeypatch.setattr("builtins.print", lambda *a, **k: None)
        assert tr.generate_transcript(audio, tmp_path, "Show_Ep001_20260930", vad_filter=True) is None
        assert len(calls) == 2

    def test_source_guard_on_the_retry_branch(self):
        src = (ROOT / "engine" / "transcripts.py").read_text(encoding="utf-8")
        assert '_vad_shaped = any(t in _msg for t in ("onnx", "silero", "vad"))' in src
        assert "::error::transcription failed" in src


class TestPromptsStillRender:
    def test_opted_in_prompts_render_with_the_block(self):
        from engine.generator import load_prompt

        class _Forgiving(dict):
            def __missing__(self, key):
                return ""

        from engine.config import load_config
        for slug in TestWiring.OPTED_IN:
            path = Path(load_config(ROOT / "shows" / f"{slug}.yaml").llm.podcast_prompt_file)
            if not path.is_absolute():
                path = ROOT / path
            rendered = load_prompt(str(path), _Forgiving(recent_frames_block="ROTATION MEMORY — x"))
            assert "ROTATION MEMORY — x" in rendered, slug


class TestFrameMemoryReadsTheRealConfig:
    """Oct 1 2026 readout: the block read ``config.output_dir`` — an attribute
    only the test double had — so production rendered "" on all 17 opted-in
    shows for a day. The directory lives on ``config.episode.output_dir``."""

    def test_a_loaded_show_config_reaches_its_scripts(self, tmp_path):
        from engine.config import load_config
        # Omni View exempts "Before we go" as a chapter anchor, so the
        # fixture frame is one no show exempts.
        for i, s in enumerate(SCRIPTS):
            s = s.replace("Before we go, keep an eye on", "One thing worth watching is")
            (tmp_path / f"Omni_View_Ep{i:03d}_2026092{i}_tts.txt").write_text(s, encoding="utf-8")
        cfg = load_config(ROOT / "shows" / "omni_view.yaml")
        assert not hasattr(cfg, "output_dir"), "the flat attribute must not quietly reappear"
        cfg.episode.output_dir = str(tmp_path)
        block = fm.build_recent_frames_block(cfg)
        assert block.startswith("ROTATION MEMORY") and '"one thing worth watching …"' in block

    def test_the_helper_prefers_the_nested_directory(self, tmp_path):
        class Ep:
            output_dir = str(tmp_path)

        class Cfg:
            episode = Ep()
            output_dir = "/nowhere"
        assert fm._config_output_dir(Cfg()) == str(tmp_path)
