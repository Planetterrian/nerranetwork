"""Hiss and clicks on Nerra Daily: the joins, Mira's voice, the story pauses
(Oct 29 2026).

Operator listen: "many sound quality issues predominantly hisses and clicks"
on Mira's introduction and the first show. Measured on Ep070:

* every join was an MP3 stream copy, which keeps each file's encoder
  padding: ~39 ms of digital silence (1,735 samples) and a hard step at each
  handoff;
* Mira's pieces were loudness-normalized only: 11 clicks in a 35 s intro and
  a pause floor ~3 dB hissier than a show's (the shows' own voice chain
  measured 11 -> 1 and -67.3 -> -71.5 dB on the same intro);
* a spliced story pause was ``apad`` digital zero, so a show's hiss switched
  off and on at every story change;
* a show reached the edition through three MP3 generations, Mira through
  four.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not installed")


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _decode(path: Path, rate: int = 44100) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1",
                          "-ar", str(rate), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def _tone_mp3(path: Path, seconds: float, freq: int) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency={freq}:duration={seconds}:sample_rate=44100",
                    "-ac", "2", "-c:a", "libmp3lame", "-q:a", "2", str(path)],
                   check=True)


def _longest_zero_run(x: np.ndarray, start: int, end: int) -> int:
    best = run = 0
    for v in np.abs(x[start:end]) < 1e-6:
        run = run + 1 if v else 0
        best = max(best, run)
    return best


class TestTheJoinIsSampleExact:
    def test_concatenate_audio_never_stream_copies(self):
        src = _read("engine/audio.py")
        body = src[src.index("def concatenate_audio("):src.index("# Transition sting generation")]
        assert '"-c", "copy"' not in body and "-f\", \"concat\"" not in body
        assert "concat=n=" in body          # the decoded concat filter
        assert "afade=t=in" in body and "afade=t=out" in body

    @needs_ffmpeg
    def test_a_decoded_join_adds_no_gap(self, tmp_path):
        from engine.audio import concatenate_audio

        a, b = tmp_path / "a.mp3", tmp_path / "b.mp3"
        _tone_mp3(a, 2.0, 440)
        _tone_mp3(b, 2.0, 660)
        out = concatenate_audio([a, b], tmp_path / "joined.mp3")
        x = _decode(out)
        # A sample-exact join: the joined file is the two inputs' length
        # (the old stream copy added ~39 ms of padding per join).
        assert abs(len(x) / 44100 - 4.0) < 0.01
        join = int(2.0 * 44100)
        assert _longest_zero_run(x, join - 2205, join + 2205) < int(0.003 * 44100)

    @needs_ffmpeg
    def test_the_join_has_no_step(self, tmp_path):
        from engine.audio import concatenate_audio

        # Two pieces that end and start at different sample values: a step.
        a, b = tmp_path / "a.wav", tmp_path / "b.wav"
        for path, freq in ((a, 997), (b, 1499)):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                            f"sine=frequency={freq}:duration=1.003:sample_rate=44100",
                            "-c:a", "pcm_s16le", str(path)], check=True)
        out = concatenate_audio([a, b], tmp_path / "joined.wav")
        x = _decode(out).astype(np.float64)
        d2 = np.abs(x[2:] - 2 * x[1:-1] + x[:-2])
        body = np.median(d2)
        join = len(_decode(a))
        assert d2[join - 60:join + 60].max() < 4 * d2[: join - 2000].max() + body

    def test_the_default_mp3_encode_is_the_master_setting(self):
        from engine.audio import JOIN_MP3_ENCODE_ARGS, _join_encode_args

        assert JOIN_MP3_ENCODE_ARGS == ["-c:a", "libmp3lame", "-q:a", "0"]
        assert _join_encode_args(Path("x.flac")) == ["-c:a", "flac"]
        assert _join_encode_args(Path("x.wav")) == ["-c:a", "pcm_s16le"]


class TestPiecesAreLossless:
    def test_the_piece_format_is_flac(self):
        from engine.daily_edition import EDITION_ENCODE_ARGS, PIECE_SUFFIX, SEGMENT_ENCODE_ARGS

        assert "flac" in SEGMENT_ENCODE_ARGS and "libmp3lame" not in SEGMENT_ENCODE_ARGS
        assert PIECE_SUFFIX == ".flac"
        assert EDITION_ENCODE_ARGS[-3:] == ["libmp3lame", "-q:a", "0"]

    @pytest.mark.parametrize("rel", ["scripts/build_daily_edition.py",
                                     "scripts/build_personal_feeds.py",
                                     "scripts/build_personal_sample.py"])
    def test_the_finished_file_is_encoded_once(self, rel):
        src = _read(rel)
        assert "encode_args=EDITION_ENCODE_ARGS" in src
        assert "PIECE_SUFFIX" in src

    def test_no_piece_is_named_mp3(self):
        ed = _read("scripts/build_daily_edition.py")
        assert 'f"seg_{seg.slug}.mp3"' not in ed and 'f"mira_{name}.mp3"' not in ed
        pf = _read("scripts/build_personal_feeds.py")
        for old in ('f"{slug}.mp3"', 'f"{slug}.level.mp3"', '"sting.mp3"',
                    'f"{name}.mp3"', 'f"{name}.voice.mp3"', 'f"{slug}.trimmed.mp3"'):
            assert old not in pf, old

    def test_mira_comes_from_grok_as_wav(self):
        assert 'f"mira_{name}_raw.wav"' in _read("scripts/build_daily_edition.py")
        assert 'f"{name}.raw.wav"' in _read("scripts/build_personal_feeds.py")
        from engine.tts import _tts_output_codec_args

        assert _tts_output_codec_args("a/b.wav") == ["-c:a", "pcm_s16le"]
        assert _tts_output_codec_args("a/b.mp3") == ["-c:a", "libmp3lame", "-q:a", "0"]


class TestMiraGoesThroughTheVoiceChain:
    def test_one_owner_of_the_chain(self):
        from engine.audio import _voice_norm_full_cmd, voice_chain_filters

        cmd = _voice_norm_full_cmd("in.wav", "out.wav")
        assert voice_chain_filters() in cmd
        assert "adeclick" in voice_chain_filters()
        assert "adeclick" not in voice_chain_filters(denoise=False)

    def test_mira_piece_carries_the_chain_then_the_loudness_spec(self):
        from engine.audio import voice_chain_filters
        from engine.daily_edition import mira_piece_cmd

        joined = " ".join(mira_piece_cmd(Path("in.wav"), Path("out.flac")))
        chain = voice_chain_filters()
        assert chain in joined
        assert joined.index(chain) < joined.index("loudnorm=I=-16:TP=-1.5:LRA=11,adelay")


class TestStoryPausesCarryRoomTone:
    def test_quietest_window_skips_a_breath(self):
        from engine.story_breaks import quietest_window

        rate = 48000
        rng = np.random.default_rng(0)
        x = rng.normal(0, 1e-3, rate)              # one second of room tone
        x[: rate // 2] += rng.normal(0, 3e-2, rate // 2)   # a breath first
        start, end = quietest_window(x, rate)
        assert start >= 0.5 and abs((end - start) - 0.12) < 1e-6

    def test_room_tone_replaces_the_zeros(self):
        from engine.story_breaks import insert_silences_cmd

        graph = insert_silences_cmd(Path("a.mp3"), Path("b.wav"), [10.0, 20.0], [0.5, 0.6],
                                    room_tone=[(9.9, 10.02), None])[8]
        assert "atrim=start=9.900:end=10.020" in graph and "aloop=" in graph
        assert "atrim=duration=0.500" in graph
        # The second cut has no room tone: digital silence, as before.
        assert graph.count("apad=pad_dur=") == 1 and "apad=pad_dur=0.600" in graph

    def test_without_room_tone_the_command_is_the_old_shape(self):
        from engine.story_breaks import insert_silences_cmd

        graph = insert_silences_cmd(Path("a.mp3"), Path("b.wav"), [10.0], 0.5)[8]
        assert "aloop" not in graph and "apad=pad_dur=0.500" in graph

    @needs_ffmpeg
    def test_the_spliced_pause_is_never_digital_zero(self, tmp_path):
        from engine import story_breaks as sb

        src = tmp_path / "voice.wav"
        # Tone, a noisy pause, tone: the shape of a story change.
        subprocess.run(["ffmpeg", "-v", "error", "-y",
                        "-f", "lavfi", "-i", "sine=frequency=300:duration=1:sample_rate=48000",
                        "-f", "lavfi", "-i", "anoisesrc=d=0.5:c=pink:a=0.002:r=48000",
                        "-f", "lavfi", "-i", "sine=frequency=300:duration=1:sample_rate=48000",
                        "-filter_complex", "[0][1][2]concat=n=3:v=0:a=1",
                        "-c:a", "pcm_s16le", str(src)], check=True)
        brk = sb.Break(cut=1.25, insert=0.6, gap_start=1.0, gap_end=1.5)
        tones = sb.room_tone_spans(src, [brk])
        assert tones[0] is not None
        out = tmp_path / "out.wav"
        subprocess.run(sb.insert_silences_cmd(src, out, [brk.cut], [brk.insert],
                                              room_tone=tones), check=True)
        x = _decode(out, 48000)
        assert abs(len(x) / 48000 - 3.1) < 0.01
        pause = x[int(1.3 * 48000):int(1.8 * 48000)]
        assert _longest_zero_run(pause, 0, len(pause)) < 48   # never 1 ms of zero
        assert np.sqrt(np.mean(pause.astype(np.float64) ** 2)) > 1e-4

    def test_run_show_passes_the_room_tone(self):
        src = _read("run_show.py")
        assert "_sb.room_tone_spans(raw_mp3, _breaks)" in src
        assert "room_tone=_tones" in src
        assert 'metrics.record("story_break_room_tone"' in src


class TestTheProbeIsReadOnly:
    def test_workflow(self):
        wf = _read(".github/workflows/probe-audio-chain.yml")
        assert "contents: read" in wf and "scripts/probe_audio_chain.py" in wf
        assert "upload-artifact" in wf and "git push" not in wf
