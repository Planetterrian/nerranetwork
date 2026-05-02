"""
Tests that capture the EXACT ffmpeg commands the current scripts would generate.

We don't run ffmpeg — we verify the command lists match the expected structure.
This is our regression baseline: after refactoring the audio pipeline into a
shared engine, we can verify it produces identical ffmpeg invocations.

The commands are extracted from tesla_shorts_time.py lines 3737-3880.

Also tests the enhanced music framework features:
  - mono silence for voice_intro_delay
  - engine command builder parity
  - dual-music / delayed-intro timing calculations
"""

from pathlib import Path, PurePosixPath

import pytest


# ---------------------------------------------------------------------------
# Expected command templates (parameterised by file paths)
# ---------------------------------------------------------------------------

def voice_normalization_full(voice_in: str, voice_out: str) -> list:
    """The 5-stage filter chain for voice normalization. The 6.5 kHz
    de-essing dip was retired May 2026 once the second custom voice
    clone (kdif6sqjcyiq, recorded on a better mic) replaced the
    sibilant b4cusb2omvkz."""
    return [
        "ffmpeg", "-y", "-threads", "0", "-i", voice_in,
        "-af",
        "highpass=f=80,lowpass=f=15000,"
        "loudnorm=I=-18:TP=-1.5:LRA=11:linear=true,"
        "acompressor=threshold=-20dB:ratio=4:attack=1:release=100:makeup=2,"
        "alimiter=level_in=1:level_out=0.95:limit=0.95",
        "-ar", "44100", "-ac", "1",
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        voice_out,
    ]


def voice_normalization_fallback(voice_in: str, voice_out: str) -> list:
    """Simplified fallback when the full chain fails."""
    return [
        "ffmpeg", "-y", "-threads", "0", "-i", voice_in,
        "-af", "loudnorm=I=-18:TP=-1.5:LRA=11:linear=true",
        "-ar", "44100", "-ac", "1",
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        voice_out,
    ]


def music_intro(music_in: str, intro_out: str) -> list:
    """5-second intro at 0.6 volume with 2s fade-out at the end."""
    return [
        "ffmpeg", "-y", "-threads", "0", "-i", music_in, "-t", "5",
        "-af", "volume=0.6,afade=t=out:curve=log:st=3:d=2",
        "-ar", "44100", "-ac", "2",
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        intro_out,
    ]


def music_overlap(music_in: str, overlap_out: str) -> list:
    """3-second overlap starting at 5s mark, 0.5 volume with 1s fade-in and 0.5s fade-out."""
    return [
        "ffmpeg", "-y", "-threads", "0", "-i", music_in, "-ss", "5", "-t", "3",
        "-af", "afade=t=in:curve=log:st=0:d=1,volume=0.5,"
               "afade=t=out:curve=log:st=2.5:d=0.5",
        "-ar", "44100", "-ac", "2",
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        overlap_out,
    ]


def music_fadeout(music_in: str, fadeout_out: str) -> list:
    """18-second fadeout from 8s mark with logarithmic curve."""
    return [
        "ffmpeg", "-y", "-threads", "0", "-i", music_in, "-ss", "8", "-t", "18",
        "-af", "volume=0.4,afade=t=out:curve=log:st=0:d=18",
        "-ar", "44100", "-ac", "2",
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        fadeout_out,
    ]


def music_outro(music_in: str, outro_out: str) -> list:
    """30-second outro with stream loop, fade-in and fade-out."""
    return [
        "ffmpeg", "-y", "-threads", "0",
        "-stream_loop", "-1", "-i", music_in, "-t", "30",
        "-af", "volume=0.4,afade=t=in:curve=log:st=0:d=2,afade=t=out:curve=log:st=27:d=3",
        "-ar", "44100", "-ac", "2",
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        outro_out,
    ]


def silence_segment(duration_seconds: float, silence_out: str) -> list:
    """Generate silent stereo audio of given duration."""
    return [
        "ffmpeg", "-y", "-threads", "0",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(duration_seconds),
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        silence_out,
    ]


def music_concat(concat_list: str, music_full_out: str) -> list:
    """Concatenate music segments via concat demuxer with re-encoding."""
    return [
        "ffmpeg", "-y", "-threads", "0",
        "-f", "concat", "-safe", "0", "-i", concat_list,
        "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        music_full_out,
    ]


def final_mix(voice_in: str, music_in: str, final_out: str) -> list:
    """Mix voice and music tracks together with sidechain ducking +
    EBU R128 loudnorm (May 2026 broadcast-quality upgrade)."""
    return [
        "ffmpeg", "-y", "-threads", "0",
        "-i", voice_in, "-i", music_in,
        "-filter_complex",
        "[0:a]asplit=2[voice_mix][voice_sc];"
        "[1:a][voice_sc]sidechaincompress="
        "threshold=-30dB:ratio=8:attack=20:release=300:level_sc=2"
        "[music_ducked];"
        "[voice_mix][music_ducked]amix=inputs=2:duration=longest:dropout_transition=2[mixed];"
        "[mixed]loudnorm=I=-16:TP=-1.5:LRA=11[out]",
        "-map", "[out]",
        "-ar", "44100", "-ac", "2",
        "-c:a", "libmp3lame", "-q:a", "0",
        final_out,
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVoiceNormalization:
    """Verify the voice normalization filter chain."""

    def test_full_chain_structure(self):
        cmd = voice_normalization_full("/tmp/voice.mp3", "/tmp/voice_mix.mp3")
        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert cmd[cmd.index("-i") + 1] == "/tmp/voice.mp3"

        af_idx = cmd.index("-af")
        af_value = cmd[af_idx + 1]

        # Verify all five filter stages are present in order
        assert "highpass=f=80" in af_value
        assert "lowpass=f=15000" in af_value
        assert "loudnorm=I=-18:TP=-1.5:LRA=11:linear=true" in af_value
        assert "acompressor=threshold=-20dB:ratio=4:attack=1:release=100:makeup=2" in af_value
        assert "alimiter=level_in=1:level_out=0.95:limit=0.95" in af_value

        # Filter order matters — verify sequencing
        assert af_value.index("highpass") < af_value.index("lowpass")
        assert af_value.index("lowpass") < af_value.index("loudnorm")
        assert af_value.index("loudnorm") < af_value.index("acompressor")
        assert af_value.index("acompressor") < af_value.index("alimiter")

    def test_full_chain_encoding_params(self):
        cmd = voice_normalization_full("/tmp/voice.mp3", "/tmp/voice_mix.mp3")
        assert "-ar" in cmd and cmd[cmd.index("-ar") + 1] == "44100"
        assert "-ac" in cmd and cmd[cmd.index("-ac") + 1] == "1"  # mono voice
        assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "libmp3lame"
        assert "-b:a" in cmd and cmd[cmd.index("-b:a") + 1] == "192k"

    def test_fallback_chain(self):
        cmd = voice_normalization_fallback("/tmp/v.mp3", "/tmp/vm.mp3")
        af_value = cmd[cmd.index("-af") + 1]
        assert af_value == "loudnorm=I=-18:TP=-1.5:LRA=11:linear=true"
        # Same encoding params
        assert cmd[cmd.index("-ac") + 1] == "1"

    def test_loudnorm_params(self):
        """LUFS target is -18 with -1.5 dB true peak — verify these constants."""
        cmd = voice_normalization_full("/tmp/v.mp3", "/tmp/out.mp3")
        af = cmd[cmd.index("-af") + 1]
        assert "I=-18" in af
        assert "TP=-1.5" in af
        assert "LRA=11" in af
        assert "linear=true" in af


class TestMusicSegments:
    """Verify each music segment's ffmpeg command."""

    def test_intro_duration_and_volume(self):
        cmd = music_intro("/music.mp3", "/intro.mp3")
        assert cmd[cmd.index("-t") + 1] == "5"
        af = cmd[cmd.index("-af") + 1]
        assert "volume=0.6" in af
        assert "afade=t=out:curve=log:st=3:d=2" in af

    def test_intro_stereo(self):
        cmd = music_intro("/m.mp3", "/i.mp3")
        assert cmd[cmd.index("-ac") + 1] == "2"  # stereo

    def test_overlap_timing(self):
        cmd = music_overlap("/music.mp3", "/overlap.mp3")
        assert cmd[cmd.index("-ss") + 1] == "5"
        assert cmd[cmd.index("-t") + 1] == "3"
        af = cmd[cmd.index("-af") + 1]
        assert "volume=0.5" in af
        assert "afade=t=in:curve=log:st=0:d=1" in af

    def test_fadeout_timing_and_curve(self):
        cmd = music_fadeout("/music.mp3", "/fadeout.mp3")
        assert cmd[cmd.index("-ss") + 1] == "8"
        assert cmd[cmd.index("-t") + 1] == "18"
        af = cmd[cmd.index("-af") + 1]
        assert "volume=0.4" in af
        assert "afade=t=out:curve=log:st=0:d=18" in af

    def test_outro_stream_loop_and_fades(self):
        cmd = music_outro("/music.mp3", "/outro.mp3")
        assert "-stream_loop" in cmd
        assert cmd[cmd.index("-stream_loop") + 1] == "-1"
        assert cmd[cmd.index("-t") + 1] == "30"
        af = cmd[cmd.index("-af") + 1]
        assert "volume=0.4" in af
        assert "afade=t=in:curve=log:st=0:d=2" in af
        assert "afade=t=out:curve=log:st=27:d=3" in af


class TestSilenceGeneration:

    def test_silence_source(self):
        cmd = silence_segment(120.5, "/silence.mp3")
        assert "anullsrc=r=44100:cl=stereo" in cmd
        assert cmd[cmd.index("-t") + 1] == "120.5"

    def test_silence_zero_duration(self):
        cmd = silence_segment(0.0, "/s.mp3")
        assert cmd[cmd.index("-t") + 1] == "0.0"


class TestMusicConcatenation:

    def test_concat_demuxer(self):
        cmd = music_concat("/tmp/list.txt", "/tmp/full.mp3")
        assert "-f" in cmd and cmd[cmd.index("-f") + 1] == "concat"
        assert "-safe" in cmd and cmd[cmd.index("-safe") + 1] == "0"
        assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "libmp3lame"


class TestFinalMix:

    def test_filter_complex_has_sidechain_ducking(self):
        cmd = final_mix("/voice.mp3", "/music.mp3", "/final.mp3")
        fc = cmd[cmd.index("-filter_complex") + 1]
        # Voice is split so it can both drive the sidechain compressor AND
        # be summed back into the mix.
        assert "asplit=2" in fc
        assert "[voice_mix]" in fc and "[voice_sc]" in fc
        # Music is ducked under voice presence.
        assert "sidechaincompress=" in fc
        assert "threshold=-30dB" in fc
        assert "ratio=8" in fc
        assert "[music_ducked]" in fc
        # Voice + ducked music summed.
        assert "amix=inputs=2" in fc
        assert "duration=longest" in fc
        assert "dropout_transition=2" in fc

    def test_filter_complex_has_loudnorm_target(self):
        """Final mix must hit -16 LUFS / TP=-1.5 (Apple Podcasts / Spotify spec)."""
        cmd = final_mix("/voice.mp3", "/music.mp3", "/final.mp3")
        fc = cmd[cmd.index("-filter_complex") + 1]
        assert "loudnorm=I=-16" in fc
        assert "TP=-1.5" in fc

    def test_final_mix_maps_filter_output(self):
        """`-map [out]` must point at the loudnorm tail; otherwise ffmpeg
        emits the raw amix stream and we lose loudness normalization."""
        cmd = final_mix("/v.mp3", "/m.mp3", "/f.mp3")
        assert "-map" in cmd
        assert cmd[cmd.index("-map") + 1] == "[out]"

    def test_final_mix_stereo(self):
        cmd = final_mix("/v.mp3", "/m.mp3", "/f.mp3")
        assert cmd[cmd.index("-ac") + 1] == "2"  # stereo output

    def test_final_mix_encoding(self):
        cmd = final_mix("/v.mp3", "/m.mp3", "/f.mp3")
        # Bumped from CBR 192k to VBR -q:a 0 (~245 kbps) for archival-quality
        # spoken-word + music in May 2026.
        assert "-q:a" in cmd and cmd[cmd.index("-q:a") + 1] == "0"
        assert cmd[cmd.index("-ar") + 1] == "44100"


class TestMusicTimingConstants:
    """Cross-check the music timing design documented in the script:

    - 0-5s: music intro alone (volume 0.6)
    - 5-8s: music overlap while voice starts (volume 0.5)
    - 8-26s: music fadeout (volume 0.4 → 0 over 18s)
    - 26s-end: silence (no music under voice)
    - after voice: 30s outro with fade-in/out
    """

    def test_intro_is_5_seconds(self):
        cmd = music_intro("/m.mp3", "/i.mp3")
        assert cmd[cmd.index("-t") + 1] == "5"

    def test_overlap_starts_at_5s_lasts_3s(self):
        cmd = music_overlap("/m.mp3", "/o.mp3")
        assert cmd[cmd.index("-ss") + 1] == "5"
        assert cmd[cmd.index("-t") + 1] == "3"

    def test_fadeout_starts_at_8s_lasts_18s(self):
        """8s start = intro (5s) + overlap (3s), runs 18s to 26s mark."""
        cmd = music_fadeout("/m.mp3", "/f.mp3")
        assert cmd[cmd.index("-ss") + 1] == "8"
        assert cmd[cmd.index("-t") + 1] == "18"

    def test_silence_is_voice_minus_26(self):
        """Silence duration = voice_duration - 26.0 (clamped to >= 0)."""
        voice_duration = 180.0
        expected_silence = voice_duration - 26.0
        cmd = silence_segment(expected_silence, "/s.mp3")
        assert cmd[cmd.index("-t") + 1] == str(expected_silence)

    def test_outro_is_30_seconds(self):
        cmd = music_outro("/m.mp3", "/o.mp3")
        assert cmd[cmd.index("-t") + 1] == "30"

    def test_outro_fade_in_2s_fade_out_3s_from_27s(self):
        cmd = music_outro("/m.mp3", "/o.mp3")
        af = cmd[cmd.index("-af") + 1]
        # Fade in: 0-2s
        assert "afade=t=in:curve=log:st=0:d=2" in af
        # Fade out: 27-30s (starts at 27, 3s duration)
        assert "afade=t=out:curve=log:st=27:d=3" in af


class TestConcatListContent:
    """Verify the concat list file would contain the right segments in order."""

    def test_segment_order_with_silence(self):
        """When voice > 26s, there's a silence segment between fadeout and outro."""
        voice_duration = 180.0
        silence_dur = voice_duration - 26.0

        segments = ["music_intro.mp3", "music_overlap.mp3", "music_fadeout.mp3"]
        if silence_dur > 0.1:
            segments.append("music_silence.mp3")
        segments.append("music_outro.mp3")

        assert segments == [
            "music_intro.mp3",
            "music_overlap.mp3",
            "music_fadeout.mp3",
            "music_silence.mp3",
            "music_outro.mp3",
        ]

    def test_segment_order_without_silence(self):
        """When voice <= 26s, silence is skipped."""
        voice_duration = 20.0
        silence_dur = max(voice_duration - 26.0, 0.0)

        segments = ["music_intro.mp3", "music_overlap.mp3", "music_fadeout.mp3"]
        if silence_dur > 0.1:
            segments.append("music_silence.mp3")
        segments.append("music_outro.mp3")

        assert segments == [
            "music_intro.mp3",
            "music_overlap.mp3",
            "music_fadeout.mp3",
            "music_outro.mp3",
        ]


# ---------------------------------------------------------------------------
# Engine command builder parity tests
# ---------------------------------------------------------------------------

class TestEngineCommandBuilderParity:
    """Verify that engine/audio.py command builders produce identical output
    to the reference templates above."""

    def test_voice_norm_full_matches(self):
        from engine.audio import _voice_norm_full_cmd
        ref = voice_normalization_full("/tmp/v.mp3", "/tmp/o.mp3")
        eng = _voice_norm_full_cmd("/tmp/v.mp3", "/tmp/o.mp3")
        assert ref == eng

    def test_voice_norm_fallback_matches(self):
        from engine.audio import _voice_norm_fallback_cmd
        ref = voice_normalization_fallback("/tmp/v.mp3", "/tmp/o.mp3")
        eng = _voice_norm_fallback_cmd("/tmp/v.mp3", "/tmp/o.mp3")
        assert ref == eng

    def test_intro_cmd_matches(self):
        from engine.audio import _music_intro_cmd
        ref = music_intro("/m.mp3", "/i.mp3")
        eng = _music_intro_cmd("/m.mp3", "/i.mp3")
        assert ref == eng

    def test_overlap_cmd_matches(self):
        from engine.audio import _music_overlap_cmd
        ref = music_overlap("/m.mp3", "/o.mp3")
        eng = _music_overlap_cmd("/m.mp3", "/o.mp3")
        assert ref == eng

    def test_fadeout_cmd_matches(self):
        from engine.audio import _music_fadeout_cmd
        ref = music_fadeout("/m.mp3", "/f.mp3")
        eng = _music_fadeout_cmd("/m.mp3", "/f.mp3")
        assert ref == eng

    def test_outro_cmd_matches(self):
        from engine.audio import _music_outro_cmd
        ref = music_outro("/m.mp3", "/o.mp3")
        eng = _music_outro_cmd("/m.mp3", "/o.mp3")
        assert ref == eng

    def test_silence_cmd_matches(self):
        from engine.audio import _silence_cmd
        ref = silence_segment(42.5, "/s.mp3")
        eng = _silence_cmd(42.5, "/s.mp3")
        assert ref == eng

    def test_concat_cmd_matches(self):
        from engine.audio import _music_concat_cmd
        ref = music_concat("/l.txt", "/f.mp3")
        eng = _music_concat_cmd("/l.txt", "/f.mp3")
        assert ref == eng

    def test_final_mix_cmd_matches(self):
        from engine.audio import _final_mix_cmd
        ref = final_mix("/v.mp3", "/m.mp3", "/f.mp3")
        eng = _final_mix_cmd("/v.mp3", "/m.mp3", "/f.mp3")
        assert ref == eng


# ---------------------------------------------------------------------------
# Mono silence (voice intro delay support)
# ---------------------------------------------------------------------------

class TestMonoSilence:
    """Verify the mono silence command used for voice_intro_delay."""

    def test_mono_silence_structure(self):
        from engine.audio import _mono_silence_cmd
        cmd = _mono_silence_cmd(28.0, "/delay.mp3")
        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert "anullsrc=r=44100:cl=mono" in cmd
        assert cmd[cmd.index("-t") + 1] == "28.0"

    def test_mono_silence_is_mono(self):
        """Must be mono to match normalized voice for concat."""
        from engine.audio import _mono_silence_cmd
        cmd = _mono_silence_cmd(5.0, "/s.mp3")
        assert "cl=mono" in cmd[cmd.index("-i") + 1]

    def test_mono_silence_encoding(self):
        from engine.audio import _mono_silence_cmd
        cmd = _mono_silence_cmd(10.0, "/s.mp3")
        assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "libmp3lame"
        assert "-b:a" in cmd and cmd[cmd.index("-b:a") + 1] == "192k"


# ---------------------------------------------------------------------------
# Voice intro delay timing
# ---------------------------------------------------------------------------

class TestVoiceIntroDelayTiming:
    """Verify the timing math for voice_intro_delay mode.

    When voice_intro_delay > 0, silence is prepended to the voice,
    extending effective_voice_duration and shifting everything forward.
    """

    def test_silence_extends_effective_duration(self):
        """voice_intro_delay adds to effective voice duration for silence calc."""
        voice_duration = 180.0
        voice_intro_delay = 28.0
        intro_duration = 28
        overlap_duration = 3
        fade_duration = 18

        effective = voice_duration + voice_intro_delay
        music_bed = intro_duration + overlap_duration + fade_duration
        silence_dur = max(effective - music_bed, 0.0)

        # 208 - 49 = 159
        assert silence_dur == pytest.approx(159.0)

    def test_zero_delay_is_standard_mode(self):
        """voice_intro_delay=0 should produce same timeline as original."""
        voice_duration = 180.0
        voice_intro_delay = 0.0
        intro_duration = 5
        overlap_duration = 3
        fade_duration = 18

        effective = voice_duration + voice_intro_delay
        music_bed = intro_duration + overlap_duration + fade_duration
        silence_dur = max(effective - music_bed, 0.0)

        # Original: 180 - 26 = 154
        assert silence_dur == pytest.approx(154.0)


# ---------------------------------------------------------------------------
# Dual-music mode timing
# ---------------------------------------------------------------------------

class TestDualMusicMode:
    """Verify dual-music mode uses the right source for each segment."""

    def test_intro_uses_primary_music(self):
        """Intro/overlap/fadeout should source from primary music file."""
        from engine.audio import _music_intro_cmd
        cmd = _music_intro_cmd("/primary.mp3", "/intro.mp3", duration=28, volume=0.6)
        assert cmd[cmd.index("-i") + 1] == "/primary.mp3"
        assert cmd[cmd.index("-t") + 1] == "28"

    def test_outro_uses_background_music(self):
        """When background music is provided, outro sources from it."""
        from engine.audio import _music_outro_cmd
        cmd = _music_outro_cmd("/background.mp3", "/outro.mp3", duration=30, volume=0.4)
        assert cmd[cmd.index("-i") + 1] == "/background.mp3"

    def test_custom_intro_duration_for_delayed_shows(self):
        """Shows like FF use intro_duration=28 to match voice_intro_delay."""
        from engine.audio import _music_intro_cmd
        cmd = _music_intro_cmd("/m.mp3", "/i.mp3", duration=28, volume=0.6)
        assert cmd[cmd.index("-t") + 1] == "28"
        assert "volume=0.6" in cmd[cmd.index("-af") + 1]


# ---------------------------------------------------------------------------
# Config integration
# ---------------------------------------------------------------------------

class TestAudioConfigDefaults:
    """Verify AudioConfig dataclass has the new fields with correct defaults."""

    def test_voice_intro_delay_default(self):
        from engine.config import AudioConfig
        cfg = AudioConfig()
        assert cfg.voice_intro_delay == 0.0

    def test_background_music_file_default(self):
        from engine.config import AudioConfig
        cfg = AudioConfig()
        assert cfg.background_music_file is None

    def test_all_timing_defaults(self):
        from engine.config import AudioConfig
        cfg = AudioConfig()
        assert cfg.intro_duration == 5.0
        assert cfg.overlap_duration == 3.0
        assert cfg.fade_duration == 18.0
        assert cfg.outro_duration == 30.0
        assert cfg.intro_volume == 0.6
        assert cfg.overlap_volume == 0.5
        assert cfg.fade_volume == 0.4
        assert cfg.outro_volume == 0.4


class TestShowMusicConfigs:
    """Verify each show's YAML loads with correct music configuration."""

    @pytest.fixture
    def load_config(self):
        from engine.config import load_config
        return load_config

    def test_tesla_has_music(self, load_config):
        cfg = load_config("shows/tesla.yaml")
        assert cfg.audio.music_file == "assets/music/tesla_shorts_time.mp3"
        assert cfg.audio.voice_intro_delay == 5.0
        assert cfg.audio.outro_crossfade == 20.0

    def test_ff_has_dual_music(self, load_config):
        cfg = load_config("shows/fascinating_frontiers.yaml")
        assert cfg.audio.music_file == "assets/music/fascinatingfrontiers.mp3"
        assert cfg.audio.background_music_file == "assets/music/fascinatingfrontiers_bg.mp3"
        assert cfg.audio.voice_intro_delay == 5.0
        assert cfg.audio.fade_duration == 27.0

    def test_pt_has_music(self, load_config):
        cfg = load_config("shows/planetterrian.yaml")
        assert cfg.audio.music_file == "assets/music/oilers-pride.mp3"

    def test_ov_has_music(self, load_config):
        cfg = load_config("shows/omni_view.yaml")
        # OV got its own dedicated theme in May 2026
        # (replaced the old shared `LubechangeOilers.mp3`).
        assert cfg.audio.music_file == "assets/music/OmniView.mp3"

    def test_ei_has_music(self, load_config):
        cfg = load_config("shows/env_intel.yaml")
        # EI got its own dedicated theme in May 2026
        # (replaced the shared `tesla_shorts_time.mp3`).
        assert cfg.audio.music_file == "assets/music/EnvIntel.mp3"

    def test_ei_standard_timing(self, load_config):
        """EI uses standard intro timing with lower volumes for briefing format."""
        cfg = load_config("shows/env_intel.yaml")
        assert cfg.audio.intro_duration == 5.0
        assert cfg.audio.outro_duration == 30.0
        assert cfg.audio.outro_crossfade == 20.0
        assert cfg.audio.intro_volume <= 0.5
