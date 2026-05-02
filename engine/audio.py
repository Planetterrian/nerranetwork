"""Audio utility functions for the podcast generation pipeline.

Provides:
  - get_audio_duration(): cached ffprobe duration lookup
  - format_duration(): seconds -> HH:MM:SS or MM:SS string
  - normalize_voice(): ffmpeg highpass/lowpass/loudnorm/compressor chain with fallback
  - concatenate_audio(): ffmpeg concat demuxer
  - generate_transition_sting(): create a short audio sting with ffmpeg
  - concatenate_with_stings(): interleave section audio with sting transitions
  - mix_with_music(): full music mixing pipeline (intro/overlap/fadeout/silence/outro)

Music mixing supports three modes configured via YAML:
  1. Standard: single music file for intro + overlap + fadeout + outro (TST, PT)
  2. Delayed intro: voice_intro_delay > 0 shifts voice start so music plays alone
  3. Dual-music: separate background_music_path for the outro section (FF)
"""

import logging
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _ffmpeg_escape(path: Path) -> str:
    """Escape a path for use inside an ffmpeg concat list file.

    ffmpeg concat list entries use ``file 'path'`` syntax where single quotes
    inside the path must be escaped as ``'\\''``.
    """
    return str(path.absolute()).replace("'", "'\\''")


_audio_duration_cache: Dict[Path, float] = {}

# ---------------------------------------------------------------------------
# Common encoding constants
# ---------------------------------------------------------------------------

_ENCODE_ARGS = ["-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast"]


# ---------------------------------------------------------------------------
# Duration helpers
# ---------------------------------------------------------------------------

def get_audio_duration(path: Path) -> float | None:
    """Return duration in seconds for an audio file, or *None* on failure.

    Results are cached to avoid redundant ``ffprobe`` calls within the
    same process.  Returns ``None`` (not ``0.0``) when the file is missing
    or unreadable so callers can distinguish errors from genuine 0-length
    audio.
    """
    if path in _audio_duration_cache:
        return _audio_duration_cache[path]

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        duration = float(result.stdout.strip())
        _audio_duration_cache[path] = duration
        return duration
    except Exception as exc:
        logger.warning("Unable to determine duration for %s: %s", path, exc)
        return None


def format_duration(seconds: float) -> str:
    """Format duration in seconds to ``HH:MM:SS`` or ``MM:SS``."""
    if not seconds or seconds <= 0:
        return "00:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


# ---------------------------------------------------------------------------
# Voice normalization
# ---------------------------------------------------------------------------

def _voice_norm_codec_args(output_path: str) -> list:
    """Return codec arguments based on the output file extension.

    WAV outputs use lossless PCM; MP3 outputs use libmp3lame at 192 kbps.
    Using WAV for intermediates avoids lossy re-encoding when the audio
    will be processed further (e.g. music mixing).
    """
    if output_path.endswith(".wav"):
        return ["-c:a", "pcm_s16le"]
    return ["-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast"]


def _voice_norm_full_cmd(voice_in: str, voice_out: str) -> list:
    """Build the 5-stage voice normalization ffmpeg command.

    Order matters — each stage operates on the output of the previous:

      1. highpass=80 Hz       — strip sub-bass rumble / TTS artifacts
      2. lowpass=15 kHz       — strip ultrasonic hiss above intelligibility
      3. loudnorm I=-18      — voice-only LUFS target (mix gets re-norm'd to -16)
      4. acompressor 4:1     — gentle dynamics control (NPR-ish consistency)
      5. alimiter level_out=0.95 — peak protection, prevents clipping into mix

    History: the chain briefly carried a 6.5 kHz -3 dB dip in May 2026
    to de-ess the original ``b4cusb2omvkz`` clone, which had a noisy
    high end. The replacement custom voice ``kdif6sqjcyiq`` (recorded
    on a better microphone) doesn't need it — Patrick's A/B against
    Tesla Ep457 / Ep459 showed the dip making the new voice feel
    duller without removing audible sibilance, so the dip was retired.
    Re-add it if a future voice clone reintroduces "s" / "sh" hiss.
    See landmine #17.
    """
    return [
        "ffmpeg", "-y", "-threads", "0", "-i", voice_in,
        "-af",
        "highpass=f=80,lowpass=f=15000,"
        "loudnorm=I=-18:TP=-1.5:LRA=11:linear=true,"
        "acompressor=threshold=-20dB:ratio=4:attack=1:release=100:makeup=2,"
        "alimiter=level_in=1:level_out=0.95:limit=0.95",
        "-ar", "44100", "-ac", "1",
    ] + _voice_norm_codec_args(voice_out) + [voice_out]


def _voice_norm_fallback_cmd(voice_in: str, voice_out: str) -> list:
    """Build the simplified fallback voice normalization command."""
    return [
        "ffmpeg", "-y", "-threads", "0", "-i", voice_in,
        "-af", "loudnorm=I=-18:TP=-1.5:LRA=11:linear=true",
        "-ar", "44100", "-ac", "1",
    ] + _voice_norm_codec_args(voice_out) + [voice_out]


def normalize_voice(input_path: Path, output_path: Path) -> Path:
    """Normalize voice audio with a multi-stage filter chain.

    Tries the full chain (highpass -> lowpass -> loudnorm -> compressor ->
    limiter).  If it fails (e.g. ffmpeg version mismatch), falls back to
    loudnorm only.

    When *output_path* ends in ``.wav``, output is lossless PCM to avoid
    an unnecessary lossy encoding pass (useful when the result will be
    mixed with music and encoded to MP3 later).

    Returns *output_path* on success.
    """
    file_duration = get_audio_duration(input_path) or 0.0
    timeout_seconds = max(int(file_duration * 3) + 120, 600)

    try:
        logger.info("Attempting voice normalization with full filter chain...")
        cmd = _voice_norm_full_cmd(str(input_path), str(output_path))
        subprocess.run(cmd, check=True, capture_output=True, timeout=timeout_seconds)
        logger.info("Voice normalization (full chain) succeeded.")
    except subprocess.CalledProcessError:
        logger.warning("Full filter chain failed, falling back to loudnorm only...")
        cmd = _voice_norm_fallback_cmd(str(input_path), str(output_path))
        subprocess.run(cmd, check=True, capture_output=True, timeout=timeout_seconds)
        logger.info("Voice normalization (fallback) succeeded.")

    return output_path


# ---------------------------------------------------------------------------
# Audio concatenation
# ---------------------------------------------------------------------------

def concatenate_audio(file_list: List[Path], output_path: Path) -> Path:
    """Concatenate audio files using the ffmpeg concat demuxer.

    Creates a temporary concat list file, runs ``ffmpeg -f concat``,
    and cleans up the list.  Returns *output_path*.
    """
    concat_list = output_path.parent / "concat_list.txt"
    try:
        with open(concat_list, "w", encoding="utf-8") as f:
            for fp in file_list:
                f.write(f"file '{_ffmpeg_escape(fp)}'\n")

        cmd = [
            "ffmpeg", "-y", "-threads", "0",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    finally:
        try:
            if concat_list.exists():
                concat_list.unlink()
        except Exception:
            pass

    return output_path


# ---------------------------------------------------------------------------
# Transition sting generation
# ---------------------------------------------------------------------------

def _generate_sting_cmd(output_path: str) -> list:
    """Build the ffmpeg command to generate a short transition sting.

    Creates a ~0.15 s two-tone chime (880 Hz + 1320 Hz) with quick
    fade-in/out, suitable as a subtle section break marker.
    """
    return [
        "ffmpeg", "-y", "-threads", "0",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=0.15",
        "-f", "lavfi", "-i", "sine=frequency=1320:duration=0.15",
        "-filter_complex",
        "[0][1]amix=inputs=2,"
        "afade=t=in:d=0.05,"
        "afade=t=out:st=0.1:d=0.05,"
        "adelay=100|100",
        "-ar", "44100", "-ac", "1",
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        output_path,
    ]


def generate_transition_sting(output_path: Path) -> Path:
    """Generate a short audio transition sting if it doesn't already exist.

    The sting is a subtle two-tone chime (~0.15 s) generated with ffmpeg's
    sine wave synthesiser.  Safe to call multiple times — skips generation
    if the file already exists.

    Returns *output_path* on success.
    """
    if output_path.exists():
        logger.info("Transition sting already exists: %s", output_path)
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = _generate_sting_cmd(str(output_path))
    subprocess.run(cmd, check=True, capture_output=True)
    logger.info("Generated transition sting: %s", output_path)
    return output_path


def _sting_padding_cmd(sting_path: str, padded_out: str,
                       pre_silence: float = 0.4,
                       post_silence: float = 0.4) -> list:
    """Build command to wrap a sting with silence padding.

    Produces: [pre_silence] + [sting] + [post_silence] so transitions
    have a natural breathing room around them.
    """
    total_pad = pre_silence + post_silence
    return [
        "ffmpeg", "-y", "-threads", "0",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
        "-t", f"{pre_silence:.2f}",
        "-i", sting_path,
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
        "-t", f"{post_silence:.2f}",
        "-filter_complex",
        "[0][1][2]concat=n=3:v=0:a=1",
        "-ar", "44100", "-ac", "1",
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        padded_out,
    ]


def concatenate_with_stings(
    section_files: List[Path],
    output_path: Path,
    *,
    sting_path: Optional[Path] = None,
    pre_silence: float = 0.4,
    post_silence: float = 0.4,
) -> Path:
    """Concatenate section audio files with transition stings between them.

    If *sting_path* is ``None`` or doesn't exist, falls back to plain
    concatenation without stings.

    Parameters
    ----------
    section_files:
        Ordered list of per-section MP3 files from TTS.
    output_path:
        Where to write the combined voice track.
    sting_path:
        Path to the transition sting audio file.
    pre_silence:
        Seconds of silence before the sting.
    post_silence:
        Seconds of silence after the sting.

    Returns
    -------
    Path
        The *output_path* that was written.
    """
    if len(section_files) <= 1 or not sting_path or not sting_path.exists():
        # Fall back to plain concatenation
        if len(section_files) == 1:
            # Just copy/re-encode the single file
            import shutil
            shutil.copy2(section_files[0], output_path)
            return output_path
        return concatenate_audio(section_files, output_path)

    with tempfile.TemporaryDirectory(dir=output_path.parent) as tmp_str:
        tmp_dir = Path(tmp_str)

        # Create a padded sting (silence + sting + silence)
        padded_sting = tmp_dir / "padded_sting.mp3"
        cmd = _sting_padding_cmd(
            str(sting_path), str(padded_sting),
            pre_silence=pre_silence, post_silence=post_silence,
        )
        subprocess.run(cmd, check=True, capture_output=True)

        # Build the interleaved file list: section, sting, section, sting, ...
        interleaved: List[Path] = []
        for i, section_file in enumerate(section_files):
            interleaved.append(section_file)
            if i < len(section_files) - 1:
                interleaved.append(padded_sting)

        # Concatenate with re-encoding for seamless joins
        concat_list = tmp_dir / "sting_concat.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for fp in interleaved:
                f.write(f"file '{_ffmpeg_escape(fp)}'\n")

        cmd = [
            "ffmpeg", "-y", "-threads", "0",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c:a", "libmp3lame", "-q:a", "2",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    logger.info(
        "Concatenated %d sections with stings → %s",
        len(section_files), output_path,
    )
    return output_path


# ---------------------------------------------------------------------------
# Music segment command builders (match test_audio_commands.py exactly)
# ---------------------------------------------------------------------------

def _music_intro_cmd(music_in: str, intro_out: str,
                     duration: int = 5, volume: float = 0.6) -> list:
    fade_start = max(0, duration - 2)
    return [
        "ffmpeg", "-y", "-threads", "0", "-i", music_in, "-t", str(duration),
        "-af", f"volume={volume},afade=t=out:curve=log:st={fade_start}:d=2",
        "-ar", "44100", "-ac", "2",
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        intro_out,
    ]


def _music_overlap_cmd(music_in: str, overlap_out: str,
                       start: int = 5, duration: int = 3,
                       volume: float = 0.5) -> list:
    # Fade-out over the last 0.5s so the transition to the fadeout segment
    # is smooth (avoids a volume discontinuity at the concat boundary).
    fade_out_start = max(0, duration - 0.5)
    return [
        "ffmpeg", "-y", "-threads", "0", "-i", music_in,
        "-ss", str(start), "-t", str(duration),
        "-af", f"afade=t=in:curve=log:st=0:d=1,volume={volume},"
               f"afade=t=out:curve=log:st={fade_out_start}:d=0.5",
        "-ar", "44100", "-ac", "2",
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        overlap_out,
    ]


def _music_fadeout_cmd(music_in: str, fadeout_out: str,
                       start: int = 8, duration: int = 18,
                       volume: float = 0.4) -> list:
    return [
        "ffmpeg", "-y", "-threads", "0", "-i", music_in,
        "-ss", str(start), "-t", str(duration),
        "-af", f"volume={volume},afade=t=out:curve=log:st=0:d={duration}",
        "-ar", "44100", "-ac", "2",
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        fadeout_out,
    ]


def _music_outro_cmd(music_in: str, outro_out: str,
                     duration: int = 30, volume: float = 0.4,
                     fade_in_duration: int = 2,
                     fade_out_start: int = 27,
                     fade_out_duration: int = 3) -> list:
    return [
        "ffmpeg", "-y", "-threads", "0",
        "-stream_loop", "-1", "-i", music_in, "-t", str(duration),
        "-af",
        f"volume={volume},"
        f"afade=t=in:curve=log:st=0:d={fade_in_duration},"
        f"afade=t=out:curve=log:st={fade_out_start}:d={fade_out_duration}",
        "-ar", "44100", "-ac", "2",
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        outro_out,
    ]


def _silence_cmd(duration_seconds: float, silence_out: str) -> list:
    return [
        "ffmpeg", "-y", "-threads", "0",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(duration_seconds),
        "-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast",
        silence_out,
    ]


def _mono_silence_cmd(duration_seconds: float, silence_out: str) -> list:
    """Generate mono silence matching the normalized voice format.

    Output codec adapts to the file extension: WAV for lossless
    intermediates, MP3 for final output.
    """
    codec = (
        ["-c:a", "pcm_s16le"]
        if silence_out.endswith(".wav")
        else ["-c:a", "libmp3lame", "-b:a", "192k", "-preset", "fast"]
    )
    return [
        "ffmpeg", "-y", "-threads", "0",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(duration_seconds),
    ] + codec + [silence_out]


def _music_concat_cmd(concat_list: str, music_full_out: str) -> list:
    # Re-encode MP3 output to eliminate frame boundary artifacts
    # (pops/clicks/overlapping samples) that occur with -c copy.
    # WAV output uses stream copy (no frame boundary issues with PCM).
    if music_full_out.endswith(".wav"):
        codec = ["-c", "copy"]
    else:
        codec = list(_ENCODE_ARGS)
    return [
        "ffmpeg", "-y", "-threads", "0",
        "-f", "concat", "-safe", "0", "-i", concat_list,
    ] + codec + [music_full_out]


def _final_mix_cmd(voice_in: str, music_in: str, final_out: str) -> list:
    """Voice + music final mix with sidechain ducking + EBU R128 loudnorm.

    Filter graph stages:

      1. ``asplit`` — duplicate the voice signal so it can drive both the
         sidechain compressor (as the trigger) and the final amix (as audio).
      2. ``sidechaincompress`` — when voice is present, music is pulled
         down 8 dB; when voice pauses, music rises smoothly. ``threshold=-30 dB``
         and ``ratio=8`` mean even modest voice levels duck the music; the
         ``attack=20 ms`` / ``release=300 ms`` pair gives broadcast feel
         (fast enough to catch syllable transients, slow enough not to pump).
         ``level_sc=2`` doubles the trigger sensitivity so quieter narration
         still ducks the bed reliably.
      3. ``amix`` — sums voice + ducked music with longest-duration semantics.
      4. ``loudnorm I=-16`` — final integrated-loudness target. Apple
         Podcasts and Spotify both auto-normalize listener-side, so episodes
         well under -16 LUFS get attenuated and feel quiet next to NPR-mastered
         shows. ``TP=-1.5`` keeps headroom to absorb true-peak intersample
         peaks without clipping. ``LRA=11`` preserves natural dynamics
         (a denser LRA flatlines the audio).

    Final encode is libmp3lame -q:a 0 (~245 kbps VBR — archival quality
    spoken-word + music; ~6.5 MB per 30-min episode).
    """
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
# Full music mixing pipeline
# ---------------------------------------------------------------------------

def mix_with_music(
    voice_path: Path,
    music_path: Path,
    output_path: Path,
    *,
    intro_duration: int = 5,
    overlap_duration: int = 3,
    fade_duration: int = 18,
    outro_duration: int = 30,
    intro_volume: float = 0.6,
    overlap_volume: float = 0.5,
    fade_volume: float = 0.4,
    outro_volume: float = 0.4,
    voice_intro_delay: float = 0.0,
    background_music_path: Optional[Path] = None,
    outro_crossfade: float = 0.0,
) -> Path:
    """Full music mixing pipeline supporting three modes.

    **Standard mode** (voice_intro_delay=0, no background_music_path):
      0–5 s:  music intro alone (intro_volume)
      5–15 s: music overlap while voice starts (overlap_volume)
      15–25 s: music fadeout (fade_volume -> 0, logarithmic)
      25 s–end: silence (no music under voice)
      after voice: 30 s outro with fade-in/out

    **Delayed-intro mode** (voice_intro_delay > 0):
      Voice is shifted right by *voice_intro_delay* seconds so music plays
      alone at the start.  Set intro_duration >= voice_intro_delay so the
      intro music covers the full delay period.

    **Dual-music mode** (background_music_path provided):
      Primary *music_path* is used for intro/overlap/fadeout segments.
      *background_music_path* is used for the outro segment, allowing a
      different musical feel for the show's closing.

    **Outro crossfade** (outro_crossfade > 0):
      Outro music begins fading in *outro_crossfade* seconds before the
      voice ends, overlapping the final portion of speech.  The outro then
      continues for *outro_duration* seconds after the voice finishes.

    If *music_path* doesn't exist, normalizes voice only and returns.
    """
    if not music_path.exists():
        logger.warning("Music file %s not found — returning voice-only.", music_path)
        return normalize_voice(voice_path, output_path)

    voice_duration = get_audio_duration(voice_path) or 0.0
    timeout_seconds = max(int(voice_duration * 3) + 120, 600)

    # Resolve the outro music source (primary or background)
    outro_music = music_path
    if background_music_path and background_music_path.exists():
        outro_music = background_music_path
        logger.info("Using background music for outro: %s", outro_music.name)
    elif background_music_path:
        logger.warning(
            "Background music %s not found — using primary music for outro.",
            background_music_path,
        )

    with tempfile.TemporaryDirectory(dir=voice_path.parent) as tmp_str:
        tmp_dir = Path(tmp_str)

        # Normalize voice to lossless WAV — MP3 encoding happens once in final mix
        voice_mix = tmp_dir / "voice_normalized_mix.wav"
        normalize_voice(voice_path, voice_mix)

        # --- Apply voice intro delay if configured ---
        effective_voice_duration = voice_duration
        if voice_intro_delay > 0:
            logger.info(
                "Applying %.1fs voice intro delay (music plays alone first).",
                voice_intro_delay,
            )
            if voice_intro_delay > intro_duration:
                logger.warning(
                    "voice_intro_delay (%.1fs) > intro_duration (%ds) — "
                    "consider increasing intro_duration to match.",
                    voice_intro_delay, intro_duration,
                )

            voice_silence = tmp_dir / "voice_delay_silence.wav"
            subprocess.run(
                _mono_silence_cmd(voice_intro_delay, str(voice_silence)),
                check=True, capture_output=True,
            )

            voice_delayed = tmp_dir / "voice_delayed.wav"
            delay_list = tmp_dir / "delay_concat.txt"
            with open(delay_list, "w") as f:
                f.write(f"file '{voice_silence.absolute()}'\n")
                f.write(f"file '{voice_mix.absolute()}'\n")
            subprocess.run(
                _music_concat_cmd(str(delay_list), str(voice_delayed)),
                check=True, capture_output=True,
            )
            voice_mix = voice_delayed
            effective_voice_duration = voice_duration + voice_intro_delay

        # --- Generate music segments in parallel ---
        music_intro_f = tmp_dir / "music_intro.mp3"
        music_overlap_f = tmp_dir / "music_overlap.mp3"
        music_fadeout_f = tmp_dir / "music_fadeout.mp3"
        music_outro_f = tmp_dir / "music_outro.mp3"
        music_silence_f = tmp_dir / "music_silence.mp3"

        fade_start = intro_duration + overlap_duration

        def _run_segment(name: str, cmd: list) -> str:
            subprocess.run(cmd, check=True, capture_output=True)
            return name

        # Calculate outro segment parameters with crossfade support
        total_outro_duration = int(outro_crossfade + outro_duration)
        if outro_crossfade > 0:
            # Fade-in over the crossfade period, fade-out over 3s at end
            outro_fade_in = int(outro_crossfade)
            outro_fade_out_start = max(total_outro_duration - 3, 0)
            outro_fade_out_dur = 3
            logger.info(
                "Outro crossfade: music starts %.0fs before voice ends, "
                "%ds total outro (%ds fade-in, %ds tail).",
                outro_crossfade, total_outro_duration,
                outro_fade_in, outro_duration,
            )
        else:
            # Default: short 2s fade-in, 3s fade-out at end
            total_outro_duration = outro_duration
            outro_fade_in = 2
            outro_fade_out_start = max(outro_duration - 3, 0)
            outro_fade_out_dur = 3

        segment_cmds = [
            ("intro", _music_intro_cmd(
                str(music_path), str(music_intro_f),
                duration=intro_duration, volume=intro_volume)),
            ("overlap", _music_overlap_cmd(
                str(music_path), str(music_overlap_f),
                start=intro_duration, duration=overlap_duration,
                volume=overlap_volume)),
            ("fadeout", _music_fadeout_cmd(
                str(music_path), str(music_fadeout_f),
                start=fade_start, duration=fade_duration,
                volume=fade_volume)),
            ("outro", _music_outro_cmd(
                str(outro_music), str(music_outro_f),
                duration=total_outro_duration, volume=outro_volume,
                fade_in_duration=outro_fade_in,
                fade_out_start=outro_fade_out_start,
                fade_out_duration=outro_fade_out_dur)),
        ]

        # Silence between fadeout and outro
        music_bed_duration = intro_duration + overlap_duration + fade_duration
        middle_silence_duration = max(
            effective_voice_duration - music_bed_duration - outro_crossfade, 0.0,
        )

        if middle_silence_duration > 0.1:
            segment_cmds.append(
                ("silence", _silence_cmd(middle_silence_duration, str(music_silence_f)))
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(_run_segment, name, cmd): name
                for name, cmd in segment_cmds
            }
            for future in as_completed(futures):
                name = futures[future]
                future.result()  # propagate any exceptions
                logger.info("Generated music segment: %s", name)

        # --- Concatenate music segments ---
        concat_files = [music_intro_f, music_overlap_f, music_fadeout_f]
        if middle_silence_duration > 0.1:
            concat_files.append(music_silence_f)
        concat_files.append(music_outro_f)

        music_full = tmp_dir / "music_full.mp3"
        music_concat_list = tmp_dir / "music_concat.txt"
        with open(music_concat_list, "w") as f:
            for fp in concat_files:
                f.write(f"file '{_ffmpeg_escape(fp)}'\n")

        cmd = _music_concat_cmd(str(music_concat_list), str(music_full))
        subprocess.run(cmd, check=True, capture_output=True)

        # --- Final mix: voice + music ---
        cmd = _final_mix_cmd(str(voice_mix), str(music_full), str(output_path))
        subprocess.run(cmd, check=True, capture_output=True, timeout=timeout_seconds)

    logger.info("Final mix complete: %s", output_path)
    return output_path
