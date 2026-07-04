"""Tests for the two-host dialogue TTS path (July 2026, The DP Pod).

Covers:
- ``engine.tts_dialogue.parse_dialogue_turns`` label parsing (case/bold
  variants, continuation paragraphs, preamble attribution, generic-label
  stripping, zero-label fallback signal, consecutive-turn grouping)
- ``synthesize_dialogue`` voice routing / chunking / pause padding with
  Grok + ffmpeg mocked out
- the three gated speaker-prefix strippers preserving real dialogue labels
  while legacy single-host behaviour stays byte-for-byte identical
- a no-op drift guard: no existing show enables ``dialogue_mode``
"""

import ast
import sys
from pathlib import Path
from unittest import mock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.tts_dialogue import (  # noqa: E402
    dialogue_stats,
    parse_dialogue_turns,
    synthesize_dialogue,
)

VOICES = {"DAN": "0vscf8u8yrxc", "PATRICK": "kdif6sqjcyiq"}

SAMPLE_SCRIPT = """DAN: Welcome to The DP Pod — the Do Positive Podcast. I'm Dan Perra.

PATRICK: And I'm Patrick Novak. Time for The Positive Papers.

PATRICK: First up: a genuinely good week for solar storage.

DAN: Okay, that number surprised me.

PATRICK: Do something about it.
"""


# ---------------------------------------------------------------------------
# parse_dialogue_turns
# ---------------------------------------------------------------------------

class TestParseDialogueTurns:
    def test_basic_alternation_and_grouping(self):
        groups = parse_dialogue_turns(SAMPLE_SCRIPT, VOICES)
        assert [g[0] for g in groups] == ["DAN", "PATRICK", "DAN", "PATRICK"]
        # Consecutive PATRICK turns merged into one group
        assert "Positive Papers" in groups[1][1]
        assert "solar storage" in groups[1][1]

    def test_labels_stripped_from_spoken_text(self):
        groups = parse_dialogue_turns(SAMPLE_SCRIPT, VOICES)
        for _speaker, text in groups:
            assert "DAN:" not in text
            assert "PATRICK:" not in text

    def test_case_insensitive_labels(self):
        script = "dan: Hello there.\n\nPatrick: Hi Dan."
        groups = parse_dialogue_turns(script, VOICES)
        assert [g[0] for g in groups] == ["DAN", "PATRICK"]

    def test_bold_markdown_labels(self):
        script = "**DAN:** Hello there.\n\n**PATRICK**: Hi Dan."
        groups = parse_dialogue_turns(script, VOICES)
        assert [g[0] for g in groups] == ["DAN", "PATRICK"]

    def test_unlabeled_paragraph_continues_previous_turn(self):
        script = (
            "DAN: First thought.\n\n"
            "And a second paragraph that lost its label.\n\n"
            "PATRICK: My turn."
        )
        groups = parse_dialogue_turns(script, VOICES)
        assert len(groups) == 2
        assert "lost its label" in groups[0][1]

    def test_preamble_attributed_to_first_speaker(self):
        script = "A stray opening line.\n\nDAN: The real start.\n\nPATRICK: Reply."
        groups = parse_dialogue_turns(script, VOICES)
        assert groups[0][0] == "DAN"
        assert "stray opening line" in groups[0][1]
        assert groups[0][1].index("stray") < groups[0][1].index("real start")

    def test_generic_label_stripped_and_continues_turn(self):
        script = "DAN: Start.\n\nHOST: Scaffolding line kept as words.\n\nPATRICK: End."
        groups = parse_dialogue_turns(script, VOICES)
        assert [g[0] for g in groups] == ["DAN", "PATRICK"]
        assert "Scaffolding line kept as words." in groups[0][1]
        assert "HOST" not in groups[0][1]

    def test_zero_labels_returns_empty(self):
        script = "Just a plain narration paragraph.\n\nAnother one."
        assert parse_dialogue_turns(script, VOICES) == []

    def test_content_colon_lines_are_not_speakers(self):
        script = "DAN: Quick heads-up.\n\nNote: this is content, not a speaker."
        groups = parse_dialogue_turns(script, VOICES)
        assert len(groups) == 1
        assert "Note: this is content" in groups[0][1]

    def test_stats(self):
        stats = dialogue_stats(SAMPLE_SCRIPT, VOICES)
        assert stats["dialogue_labeled_paragraphs"] == 5
        assert stats["dialogue_unlabeled_paragraphs"] == 0
        assert stats["dialogue_turn_count"] == 4


# ---------------------------------------------------------------------------
# synthesize_dialogue (Grok + ffmpeg mocked)
# ---------------------------------------------------------------------------

class TestSynthesizeDialogue:
    def _run(self, tmp_path, script, voices=VOICES, **kwargs):
        calls = []

        def fake_chunk(text, voice_id, out_path, **kw):
            calls.append((text, voice_id))
            Path(out_path).write_bytes(b"RIFFfake")

        with mock.patch("engine.tts_dialogue.grok_speak_chunk", side_effect=fake_chunk), \
             mock.patch("engine.tts_dialogue._crossfade_wavs_to_mp3") as m_x, \
             mock.patch("engine.tts_dialogue._pad_wav_tail", side_effect=lambda p, ms: p) as m_pad:
            out = synthesize_dialogue(
                script, voices, tmp_path / "out.mp3",
                api_key="k", **kwargs,
            )
        return calls, m_x, m_pad, out

    def test_routes_each_group_to_its_speakers_voice(self, tmp_path):
        calls, m_x, _pad, _out = self._run(tmp_path, SAMPLE_SCRIPT)
        assert [voice for _t, voice in calls] == [
            VOICES["DAN"], VOICES["PATRICK"], VOICES["DAN"], VOICES["PATRICK"],
        ]
        assert m_x.call_count == 1
        # 4 groups → 4 wavs handed to the crossfade in order
        assert len(m_x.call_args[0][0]) == 4

    def test_no_wrap_ever_in_payload(self, tmp_path):
        calls, *_ = self._run(tmp_path, SAMPLE_SCRIPT)
        for text, _voice in calls:
            assert "<fast>" not in text and "</fast>" not in text

    def test_long_group_is_chunked(self, tmp_path):
        long_text = "DAN: " + ("A sentence here. " * 40)
        calls, *_ = self._run(tmp_path, long_text + "\n\nPATRICK: Short.",
                              max_chars=300)
        dan_calls = [t for t, v in calls if v == VOICES["DAN"]]
        assert len(dan_calls) > 1

    def test_pause_padding_between_groups_not_after_last(self, tmp_path):
        _calls, _x, m_pad, _out = self._run(tmp_path, SAMPLE_SCRIPT, pause_ms=300)
        # 4 groups → padding after the first 3 only
        assert m_pad.call_count == 3

    def test_zero_pause_skips_padding(self, tmp_path):
        _calls, _x, m_pad, _out = self._run(tmp_path, SAMPLE_SCRIPT, pause_ms=0)
        assert m_pad.call_count == 0

    def test_speed_passes_through_to_each_chunk(self, tmp_path):
        kwargs_seen = []

        def fake_chunk(text, voice_id, out_path, **kw):
            kwargs_seen.append(kw)
            Path(out_path).write_bytes(b"RIFFfake")

        with mock.patch("engine.tts_dialogue.grok_speak_chunk", side_effect=fake_chunk), \
             mock.patch("engine.tts_dialogue._crossfade_wavs_to_mp3"), \
             mock.patch("engine.tts_dialogue._pad_wav_tail", side_effect=lambda p, ms: p):
            synthesize_dialogue(
                SAMPLE_SCRIPT, VOICES, tmp_path / "out.mp3",
                api_key="k", speed=1.05,
            )
        assert kwargs_seen and all(kw.get("speed") == 1.05 for kw in kwargs_seen)

    def test_unlabeled_script_raises(self, tmp_path):
        with pytest.raises(ValueError, match="no recognised speaker labels"):
            self._run(tmp_path, "Plain narration only.")

    def test_placeholder_voice_id_raises(self, tmp_path):
        bad = {"DAN": "REPLACE_WITH_DAN_GROK_VOICE_ID", "PATRICK": "kdif6sqjcyiq"}
        with pytest.raises(ValueError, match="unusable voice"):
            self._run(tmp_path, SAMPLE_SCRIPT, voices=bad)

    def test_empty_voices_raises(self, tmp_path):
        with pytest.raises(ValueError, match="dialogue_voices is empty"):
            self._run(tmp_path, SAMPLE_SCRIPT, voices={})


class TestGrokSpeedPayload:
    """Documented Grok TTS speed multiplier: sent only when != 1.0, so every
    existing show's payload stays byte-identical at the default."""

    def _payload_for(self, tmp_path, **kwargs):
        from engine import tts as tts_mod

        captured = {}

        class _Resp:
            status_code = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def iter_content(self, chunk_size): return iter([b"RIFF"])
            def raise_for_status(self): pass

        def fake_post(url, json=None, headers=None, stream=None, timeout=None):
            captured.update(json)
            return _Resp()

        with mock.patch.object(tts_mod.requests, "post", side_effect=fake_post):
            tts_mod.grok_speak_chunk(
                "Hello there.", "voice", tmp_path / "c.wav",
                api_key="k", **kwargs,
            )
        return captured

    def test_default_speed_omits_field(self, tmp_path):
        payload = self._payload_for(tmp_path)
        assert "speed" not in payload

    def test_custom_speed_included_and_clamped(self, tmp_path):
        assert self._payload_for(tmp_path, speed=1.05)["speed"] == 1.05
        assert self._payload_for(tmp_path, speed=9.0)["speed"] == 1.5


# ---------------------------------------------------------------------------
# The three gated speaker-prefix strippers
# ---------------------------------------------------------------------------

def _load_run_show_fns():
    """AST-extract the run_show helpers (avoids heavy top-level imports)."""
    source = (PROJECT_ROOT / "run_show.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    needed = {"_clean_podcast_script", "_break_long_paragraphs"}
    funcs = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in needed:
            funcs[node.name] = ast.get_source_segment(source, node)
    assert needed <= set(funcs)
    import re as _re
    src = source
    m = _re.search(r"^_SENTENCE_SPLIT_RE\s*=.*$", src, _re.MULTILINE)
    ns = {"re": _re}
    if m:
        exec(m.group(0), ns)  # noqa: S102
    exec(funcs["_break_long_paragraphs"], ns)  # noqa: S102
    exec(funcs["_clean_podcast_script"], ns)  # noqa: S102
    return ns["_clean_podcast_script"]


class TestCleanPodcastScriptDialogueMode:
    def test_dialogue_mode_preserves_real_labels(self):
        clean = _load_run_show_fns()
        out = clean(SAMPLE_SCRIPT, host_name="Patrick", dialogue_mode=True)
        assert "DAN:" in out
        assert "PATRICK:" in out

    def test_dialogue_mode_still_strips_generic_prefixes(self):
        clean = _load_run_show_fns()
        out = clean(
            "Narrator: A framing line.\n\nDAN: Hello.",
            host_name="Patrick", dialogue_mode=True,
        )
        assert "Narrator:" not in out
        assert "DAN: Hello." in out

    def test_legacy_default_still_strips_host_name(self):
        clean = _load_run_show_fns()
        out = clean("Patrick: Tesla shipped a thing.", host_name="Patrick")
        assert "Patrick:" not in out
        assert "Tesla shipped a thing." in out


class TestSanitizePodcastScriptDialogueMode:
    def test_preserve_flag_keeps_patrick_label(self):
        from engine.generator import _sanitize_podcast_script
        text = "PATRICK: The lever this week is heat pumps.\n\nDAN: Numbers, please."
        out = _sanitize_podcast_script(text, preserve_speaker_labels=True)
        assert "PATRICK:" in out
        assert "DAN:" in out

    def test_preserve_flag_still_strips_generic_host(self):
        from engine.generator import _sanitize_podcast_script
        text = "Host: framing line here.\n\nDAN: Hello."
        out = _sanitize_podcast_script(text, preserve_speaker_labels=True)
        assert "Host:" not in out

    def test_default_still_strips_patrick(self):
        from engine.generator import _sanitize_podcast_script
        text = "Patrick: Tesla update leads today."
        out = _sanitize_podcast_script(text)
        assert "Patrick:" not in out


# ---------------------------------------------------------------------------
# Existing-show no-op drift guard
# ---------------------------------------------------------------------------

def test_no_existing_show_enables_dialogue_mode():
    """Dialogue mode is opt-in; only two-host shows (dp_pod) may set it.
    (The Age of AI's guest audio is REAL recorded phone audio via the
    Nerra Voices pipeline, not dialogue TTS.)"""
    from engine.config import discover_show_slugs, load_config

    allowed = {"dp_pod"}
    for slug in discover_show_slugs():
        cfg = load_config(PROJECT_ROOT / "shows" / f"{slug}.yaml")
        if slug in allowed:
            continue
        assert cfg.tts.dialogue_mode is False, (
            f"{slug} unexpectedly enables tts.dialogue_mode — the two-host "
            "path is reserved for dialogue shows and changes shipped audio"
        )


def test_dialogue_defaults_are_noop():
    from engine.config import TTSConfig

    cfg = TTSConfig()
    assert cfg.dialogue_mode is False
    assert cfg.dialogue_voices == {}
    assert cfg.dialogue_pause_ms == 300
