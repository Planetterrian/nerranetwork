"""TTS helpers for the podcast generation pipeline.

Supports two providers, selected per-show via ``tts.provider``:

  - **elevenlabs** (default for English shows) — `eleven_flash_v2_5` via the
    streaming endpoint. Stability / similarity_boost / style settings.
  - **grok** (Russian shows since May 2026) — xAI's `/v1/tts` endpoint at
    ~36× lower per-character cost than ElevenLabs Flash. Reuses the
    `GROK_API_KEY` / `XAI_API_KEY` env var already used for LLM calls.

Public API:
  - synthesize(): top-level entry point — text in, audio file out, picks
    the provider on the *provider* kwarg
  - validate_elevenlabs_auth(): fail-fast API key check (ElevenLabs only)
  - chunk_text(): sentence-aware text splitting for the configurable chunk limit
  - speak_chunk(): single-chunk ElevenLabs TTS with retry
  - speak(): full ElevenLabs TTS with automatic chunking + ffmpeg concatenation
  - synthesize_sections(): section-aware synthesis (per-section files)
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import List

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"
GROK_TTS_ENDPOINT = "https://api.x.ai/v1/tts"
# Grok caps per-request text at 15,000 chars; we use 14,000 as the chunk
# ceiling to leave a small headroom for any trailing punctuation we add.
GROK_MAX_CHARS_PER_REQUEST = 14000


def _ffmpeg_escape(path: Path) -> str:
    """Escape a path for use inside an ffmpeg concat list file."""
    return str(path.absolute()).replace("'", "'\\''")


# ---------------------------------------------------------------------------
# Pronunciation map + TTS text preparation
# ---------------------------------------------------------------------------

_PRONUNCIATION_MAP_PATH = Path(__file__).resolve().parent.parent / "shows" / "pronunciation_map.yaml"
_PRONUNCIATION_CACHE: dict = {}


def _load_pronunciation_map() -> dict:
    """Load the pronunciation overrides from shows/pronunciation_map.yaml.

    Cached after first load. Returns an empty dict if the file is missing
    or malformed — an empty map is the expected default.
    """
    if _PRONUNCIATION_CACHE:
        return _PRONUNCIATION_CACHE
    try:
        import yaml
        if _PRONUNCIATION_MAP_PATH.exists():
            data = yaml.safe_load(_PRONUNCIATION_MAP_PATH.read_text(encoding="utf-8")) or {}
            corrections = data.get("corrections") or {}
            if isinstance(corrections, dict):
                _PRONUNCIATION_CACHE.update(corrections)
    except Exception as exc:
        logger.warning("Could not load pronunciation map: %s", exc)
    return _PRONUNCIATION_CACHE


def prepare_text_for_tts(text: str) -> str:
    """Normalize text for optimal TTS pronunciation.

    Applied ONLY to the text sent to the TTS engine — the digest, blog,
    transcript, and social posts continue to use the standard written form.

    Current steps:
      1. Strip any residual production metadata that slipped past the
         generator sanitizer (double safety net with P0-1 in generator.py).
      2. Apply whole-word case-insensitive substitutions from
         shows/pronunciation_map.yaml.  The map is empty by default and
         only populated when a mispronunciation is confirmed on the
         production voice and model.
    """
    if not text:
        return text

    # Safety net: strip any residual production-notes blocks or word-count
    # metadata lines. This mirrors _strip_metadata_from_script in generator.py
    # but operates on the TTS input copy, so even late-stage leaks never
    # reach ElevenLabs.
    text = re.sub(
        r"\[PRODUCTION NOTES[^\]]*\][\s\S]*?\[END PRODUCTION NOTES\]",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?im)^\s*\(?\s*(word\s*count|total\s*words|character\s*count)\s*[:：].*$",
        "",
        text,
    )

    corrections = _load_pronunciation_map()
    for written, spoken in corrections.items():
        if not written or not spoken:
            continue
        pattern = r"\b" + re.escape(str(written)) + r"\b"
        text = re.sub(pattern, str(spoken), text, flags=re.IGNORECASE)

    return text.strip()


def validate_elevenlabs_auth(api_key: str) -> None:
    """Fail fast with a clear message when the ElevenLabs key is rejected."""
    resp = requests.get(
        f"{ELEVENLABS_API_BASE}/user",
        headers={"xi-api-key": api_key},
        timeout=10,
    )
    if resp.status_code == 401:
        raise RuntimeError(
            "ElevenLabs rejected the API key (401). "
            "Update ELEVENLABS_API_KEY in .env/GitHub secrets."
        )
    resp.raise_for_status()


def chunk_text(text: str, max_chars: int = 5000) -> List[str]:
    """Split text into chunks for ElevenLabs API.

    Split priority (best → worst for natural audio):
      0. Paragraph boundaries (\\n\\n) — least audible prosody reset
      1. Sentence boundaries (., !, ?) — cleanest within-paragraph break
      2. Clause boundaries (semicolons, colons, em dashes) — natural pause
      3. Conjunctions after commas (", and", ", but", ", so") — clause-level
      4. Any comma — last resort within-sentence split
      5. Last space in the trailing 30% of the chunk
    """
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    remaining = text.strip()

    while len(remaining) > max_chars:
        chunk_candidate = remaining[:max_chars]

        best_split = -1

        # 0. Prefer the rightmost paragraph boundary (double newline).
        #    Paragraph breaks are natural pause points where a prosody
        #    reset between TTS chunks is least audible.  Only use if the
        #    split point is in the back 40% of the chunk to avoid very
        #    uneven chunks.
        min_para_pos = int(max_chars * 0.6)
        para_idx = chunk_candidate.rfind("\n\n", min_para_pos)
        if para_idx != -1:
            best_split = para_idx + 2  # include the double newline in chunk 1

        # 1. Fallback: rightmost sentence ending
        if best_split == -1:
            sentence_endings: List[int] = []
            for i, char in enumerate(chunk_candidate):
                if char in ".!?":
                    # Avoid splitting on abbreviations (e.g., "U.S.") or decimals
                    # by requiring whitespace or end-of-text after the punctuation
                    if i + 1 >= len(chunk_candidate) or chunk_candidate[i + 1] in " \n\t":
                        sentence_endings.append(i + 1)

            if sentence_endings:
                best_split = sentence_endings[-1]

        # 2. Fallback: clause boundaries (semicolons, colons, em dashes)
        if best_split == -1:
            clause_splits: List[int] = []
            for i, char in enumerate(chunk_candidate):
                if char in ";:" or (char == '—'):
                    clause_splits.append(i + 1)
            if clause_splits:
                best_split = clause_splits[-1]

        # 3. Fallback: conjunction after comma (", and", ", but", ", so", ", or")
        if best_split == -1:
            import re
            conj_pattern = re.compile(r",\s+(?:and|but|so|or|yet|because|while|although)\s", re.IGNORECASE)
            conj_matches = list(conj_pattern.finditer(chunk_candidate))
            if conj_matches:
                # Split after the comma, before the conjunction
                best_split = conj_matches[-1].start() + 1

        # 4. Fallback: any comma (keep last one found)
        if best_split == -1:
            for i, char in enumerate(chunk_candidate):
                if char == ",":
                    best_split = i + 1

        # 5. Fallback: last space in the trailing 30%
        if best_split == -1:
            search_start = int(max_chars * 0.7)
            for i in range(len(chunk_candidate) - 1, search_start - 1, -1):
                if chunk_candidate[i] == " ":
                    best_split = i + 1
                    break

        # Absolute last resort
        if best_split == -1:
            for i in range(max_chars - 1, max(max_chars - 50, 0), -1):
                if i < len(chunk_candidate) and chunk_candidate[i] == " ":
                    best_split = i + 1
                    break

        if best_split == -1 or best_split == 0:
            best_split = max_chars

        chunk_text_str = remaining[:best_split].strip()
        if chunk_text_str:
            chunks.append(chunk_text_str)
        remaining = remaining[best_split:].strip()

    if remaining:
        chunks.append(remaining)

    if len(chunks) > 1:
        logger.info(
            "Split text into %d chunks: %s characters",
            len(chunks),
            [len(c) for c in chunks],
        )

    return chunks


def _sanitize_for_elevenlabs(text: str) -> str:
    """Last-resort sanitization before sending text to ElevenLabs.

    Removes characters and patterns known to cause 400 errors:
    - URLs (shouldn't be here after pronunciation processing, but defense-in-depth)
    - Control characters (except newlines)
    - Zero-width unicode characters
    - Excessive whitespace
    """
    # Decode HTML entities (e.g. &amp; → &, &nbsp; → space)
    import html as _html
    text = _html.unescape(text)
    # Strip any surviving URLs
    text = re.sub(r"https?://\S+", "", text)
    # Strip residual markdown formatting characters
    text = re.sub(r"[*_~`#]+", "", text)
    # Truncate extremely long unbroken tokens (100+ chars) that can confuse TTS
    text = re.sub(r"\S{100,}", lambda m: m.group(0)[:80], text)
    # Strip zero-width characters (joiners, non-joiners, BOM, etc.)
    text = re.sub(r"[\u200b-\u200f\u2028-\u202f\ufeff\u00ad]+", "", text)
    # Strip control characters except newline and tab
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Collapse excessive whitespace
    text = re.sub(r"[ \t]{3,}", "  ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


class ElevenLabsClientError(Exception):
    """Non-retryable ElevenLabs API error (4xx).

    Raised for client errors (400, 403, 422 etc.) that will not resolve on
    retry.  Carries the status code and response body for diagnostics.
    """

    def __init__(self, message: str, status_code: int, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class _ElevenLabsServerError(requests.HTTPError):
    """Retryable ElevenLabs server error (5xx / 429).

    Wraps HTTPError so the retry decorator can distinguish server errors
    (which should be retried) from client errors (which should not).
    """


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout, _ElevenLabsServerError)),
)
def speak_chunk(
    text: str,
    voice_id: str,
    out_path: Path,
    *,
    api_key: str,
    model_id: str = "eleven_flash_v2_5",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
    use_speaker_boost: bool = True,
    language_code: str = "",
    speed: float = 1.0,
    apply_text_normalization: str = "on",
    timeout: int = 120,
    previous_text: str = "",
    next_text: str = "",
) -> None:
    """Generate audio for a single text chunk via the ElevenLabs streaming API.

    Always uses the ``/stream`` endpoint so audio is written to disk in
    chunks rather than buffered entirely in memory.

    Parameters *previous_text* and *next_text* provide surrounding context
    so ElevenLabs can maintain natural prosody across chunk boundaries
    (the text is not spoken, only used for conditioning).

    Only retries on transient errors (connection failures, timeouts).
    Client errors (4xx) fail immediately with diagnostic info.
    """
    # Defense-in-depth: sanitize text before sending to ElevenLabs
    text = _sanitize_for_elevenlabs(text)
    if not text:
        raise ValueError(
            "speak_chunk: text is empty after sanitization — refusing to "
            "produce a silent chunk that would degrade audio quality"
        )

    url = "/".join([ELEVENLABS_API_BASE, "text-to-speech", voice_id, "stream"])

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": use_speaker_boost,
            "speed": speed,
        },
        "apply_text_normalization": apply_text_normalization,
    }
    # ElevenLabs uses language_code for optimal pronunciation in
    # non-English content (ISO 639-1, e.g. "ru", "es").
    if language_code:
        payload["language_code"] = language_code
    # ElevenLabs uses previous/next_text to condition prosody at chunk
    # boundaries, reducing audible transitions between chunks.
    if previous_text:
        payload["previous_text"] = _sanitize_for_elevenlabs(previous_text)
    if next_text:
        payload["next_text"] = _sanitize_for_elevenlabs(next_text)

    with requests.post(url, json=payload, headers=headers, stream=True, timeout=timeout) as r:
        if r.status_code == 401:
            raise ElevenLabsClientError(
                "ElevenLabs returned 401 Unauthorized. "
                "Verify ELEVENLABS_API_KEY and that the voice ID is accessible.",
                status_code=401,
            )
        if 400 <= r.status_code < 500 and r.status_code != 429:
            body = r.text[:500]
            logger.error(
                "ElevenLabs returned %d for chunk (%d chars): %s",
                r.status_code, len(text), body,
            )
            raise ElevenLabsClientError(
                f"ElevenLabs returned {r.status_code}: {body}",
                status_code=r.status_code,
                body=body,
            )
        if r.status_code == 429 or r.status_code >= 500:
            body = r.text[:500]
            logger.warning(
                "ElevenLabs returned %d (retryable) for chunk (%d chars): %s",
                r.status_code, len(text), body,
            )
            raise _ElevenLabsServerError(
                f"ElevenLabs returned {r.status_code}: {body}",
                response=r,
            )
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for data in r.iter_content(chunk_size=8192):
                f.write(data)


# Fallback model chain: if the primary model returns a 4xx, try these
# alternatives in order.  Only triggered on ElevenLabsClientError (not on
# server errors, which are retried in-place by speak_chunk).
_MODEL_FALLBACKS = {
    "eleven_flash_v2_5": "eleven_multilingual_v2",
    "eleven_v3": "eleven_flash_v2_5",
    "eleven_turbo_v2_5": "eleven_multilingual_v2",
}


def speak(
    text: str,
    voice_id: str,
    filename: str,
    *,
    api_key: str,
    max_chars: int = 10000,
    model_id: str = "eleven_flash_v2_5",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
    use_speaker_boost: bool = True,
    language_code: str = "",
    speed: float = 1.0,
    apply_text_normalization: str = "on",
    timeout: int = 120,
    append_exclamation: bool = False,
) -> None:
    """Generate audio with automatic chunking and ffmpeg concatenation.

    For texts within *max_chars*, a single API call is made.  Longer texts
    are split at sentence boundaries, synthesised as separate chunks, and
    concatenated with ``ffmpeg -f concat``.  Always uses the ElevenLabs
    streaming endpoint.

    If the primary model returns a 4xx error, automatically falls back to
    an older model (see ``_MODEL_FALLBACKS``).
    """
    tts_kwargs = dict(
        api_key=api_key,
        model_id=model_id,
        stability=stability,
        similarity_boost=similarity_boost,
        style=style,
        use_speaker_boost=use_speaker_boost,
        language_code=language_code,
        speed=speed,
        apply_text_normalization=apply_text_normalization,
        timeout=timeout,
    )

    text = prepare_text_for_tts(text)
    chunks = chunk_text(text, max_chars=max_chars)

    try:
        _speak_with_model(chunks, voice_id, filename, tts_kwargs, append_exclamation)
        return
    except ElevenLabsClientError as exc:
        fallback = _MODEL_FALLBACKS.get(model_id)
        if not fallback:
            raise
        logger.warning(
            "ElevenLabs %s returned %d — falling back to %s",
            model_id, exc.status_code, fallback,
        )
        tts_kwargs["model_id"] = fallback
        _speak_with_model(chunks, voice_id, filename, tts_kwargs, append_exclamation)


def _speak_with_model(
    chunks: List[str],
    voice_id: str,
    filename: str,
    tts_kwargs: dict,
    append_exclamation: bool,
) -> None:
    """Internal: synthesize chunks with the model specified in tts_kwargs."""
    if len(chunks) == 1:
        text = chunks[0]
        out_text = text + "!" if append_exclamation else text
        speak_chunk(out_text, voice_id, Path(filename), **tts_kwargs)
        logger.info("ElevenLabs TTS: Generated single chunk (%d chars)", len(text))
        return

    logger.info(
        "ElevenLabs TTS: Splitting into %d chunks for seamless generation",
        len(chunks),
    )
    chunk_files: List[Path] = []
    # Use a unique temp directory per synthesis run to avoid chunk filename
    # collisions when multiple shows run in parallel on the same machine.
    import tempfile as _tmpmod
    tmp_dir = Path(_tmpmod.mkdtemp(prefix="tts_", dir=str(Path(filename).parent)))

    # Context window for previous_text / next_text conditioning.
    # ElevenLabs recommends ~1000 chars of context for prosody continuity.
    _CONTEXT_CHARS = 1000

    wav_files: List[Path] = []
    try:
        for i, chunk_text_str in enumerate(chunks):
            chunk_file = tmp_dir / f"tts_chunk_{i:03d}.mp3"
            if append_exclamation:
                if i < len(chunks) - 1:
                    chunk_text_str = chunk_text_str.rstrip(".!?") + "."
                else:
                    chunk_text_str = chunk_text_str + "!"

            # Provide surrounding text so ElevenLabs maintains prosody
            prev_ctx = chunks[i - 1][-_CONTEXT_CHARS:] if i > 0 else ""
            next_ctx = chunks[i + 1][:_CONTEXT_CHARS] if i < len(chunks) - 1 else ""

            speak_chunk(
                chunk_text_str, voice_id, chunk_file,
                **tts_kwargs,
                previous_text=prev_ctx,
                next_text=next_ctx,
            )
            chunk_files.append(chunk_file)
            logger.info(
                "Generated chunk %d/%d (%d chars)",
                i + 1, len(chunks), len(chunk_text_str),
            )

        # Decode each MP3 chunk to WAV for lossless concatenation.
        # This avoids quality loss from re-encoding MP3→MP3 at boundaries.
        for cf in chunk_files:
            wav_file = cf.with_suffix(".wav")
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(cf), "-ar", "44100", "-ac", "1", str(wav_file)],
                check=True, capture_output=True, timeout=120,
            )
            wav_files.append(wav_file)

        # Concatenate WAV files with a very short crossfade to eliminate
        # boundary artifacts without overlapping speech.  0.05s (50ms) is
        # enough to avoid pops/clicks at chunk joins while staying well
        # within the natural silence between sentences.
        _XFADE_SECS = "0.05"
        if len(wav_files) == 2:
            merged_wav = tmp_dir / "tts_merged.wav"
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(wav_files[0]), "-i", str(wav_files[1]),
                    "-filter_complex", f"acrossfade=d={_XFADE_SECS}:c1=tri:c2=tri",
                    str(merged_wav),
                ],
                check=True, capture_output=True, timeout=300,
            )
        else:
            # Chain crossfades for 3+ chunks
            merged_wav = wav_files[0]
            for idx in range(1, len(wav_files)):
                step_out = tmp_dir / f"tts_xfade_{idx:03d}.wav"
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", str(merged_wav), "-i", str(wav_files[idx]),
                        "-filter_complex", f"acrossfade=d={_XFADE_SECS}:c1=tri:c2=tri",
                        str(step_out),
                    ],
                    check=True, capture_output=True, timeout=300,
                )
                merged_wav = step_out

        # Single final MP3 encode from lossless WAV
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(merged_wav),
                "-c:a", "libmp3lame", "-q:a", "2",
                str(filename),
            ],
            check=True, capture_output=True, timeout=300,
        )
        logger.info("ElevenLabs TTS: Concatenated %d chunks via WAV intermediates (single MP3 encode)", len(chunks))

    finally:
        for cf in chunk_files + wav_files:
            try:
                if cf.exists():
                    cf.unlink()
            except Exception:
                pass
        # Clean up any intermediate crossfade/merged files
        for tmp_file in tmp_dir.glob("tts_xfade_*.wav"):
            try:
                tmp_file.unlink()
            except Exception:
                pass
        for tmp_file in tmp_dir.glob("tts_merged.wav"):
            try:
                tmp_file.unlink()
            except Exception:
                pass
        # Remove the per-run temp directory (created above to isolate
        # parallel synthesis runs from each other).
        try:
            if tmp_dir.exists() and tmp_dir != Path(filename).parent:
                tmp_dir.rmdir()  # only removes if empty
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Grok TTS (xAI /v1/tts)
# ---------------------------------------------------------------------------

class GrokTTSClientError(Exception):
    """Non-retryable Grok TTS API error (4xx)."""

    def __init__(self, message: str, status_code: int, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class _GrokTTSServerError(requests.HTTPError):
    """Retryable Grok TTS server error (5xx / 429)."""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (requests.ConnectionError, requests.Timeout, _GrokTTSServerError),
    ),
)
def grok_speak_chunk(
    text: str,
    voice_id: str,
    out_path: Path,
    *,
    api_key: str,
    language_code: str = "auto",
    timeout: int = 120,
) -> None:
    """Generate audio for a single text chunk via the Grok ``/v1/tts`` endpoint.

    Returns MP3 bytes by default (24 kHz / 128 kbps, per xAI docs). Retries
    only on transient errors (timeouts, connection failures, 429/5xx). The
    API key reuses ``GROK_API_KEY`` / ``XAI_API_KEY`` — the same one used
    for LLM calls — so no new env var is needed.
    """
    if not text or not text.strip():
        raise ValueError(
            "grok_speak_chunk: text is empty — refusing to produce a silent chunk",
        )
    if len(text) > GROK_MAX_CHARS_PER_REQUEST + 1000:
        # The API caps at 15k; we pre-chunk under that. If a caller bypassed
        # chunking, fail loudly rather than truncating silently.
        raise ValueError(
            f"grok_speak_chunk: text length {len(text)} exceeds Grok's "
            f"15,000-char per-request cap. Caller must chunk first.",
        )

    payload = {
        "text": text,
        "voice_id": voice_id,
        "language": language_code or "auto",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    with requests.post(
        GROK_TTS_ENDPOINT, json=payload, headers=headers,
        stream=True, timeout=timeout,
    ) as r:
        if r.status_code == 401:
            raise GrokTTSClientError(
                "Grok TTS returned 401 Unauthorized. Verify GROK_API_KEY / "
                "XAI_API_KEY and that the voice_id is accessible.",
                status_code=401,
            )
        if 400 <= r.status_code < 500 and r.status_code != 429:
            body = r.text[:500]
            logger.error(
                "Grok TTS returned %d for chunk (%d chars): %s",
                r.status_code, len(text), body,
            )
            raise GrokTTSClientError(
                f"Grok TTS returned {r.status_code}: {body}",
                status_code=r.status_code,
                body=body,
            )
        if r.status_code == 429 or r.status_code >= 500:
            body = r.text[:500]
            logger.warning(
                "Grok TTS returned %d (retryable) for chunk (%d chars): %s",
                r.status_code, len(text), body,
            )
            raise _GrokTTSServerError(
                f"Grok TTS returned {r.status_code}: {body}",
                response=r,
            )
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for data in r.iter_content(chunk_size=8192):
                f.write(data)


def _speak_with_grok(
    text: str,
    voice_id: str,
    filename: str,
    *,
    api_key: str,
    max_chars: int = GROK_MAX_CHARS_PER_REQUEST,
    language_code: str = "auto",
    timeout: int = 120,
    append_exclamation: bool = False,
) -> None:
    """Grok-TTS counterpart of ``speak()``.

    Same chunk → WAV → crossfade → final MP3 pipeline as the ElevenLabs
    path. Single chunks short-circuit to a direct MP3 write (no re-encode).
    """
    text = prepare_text_for_tts(text)
    # Cap at Grok's 15k-char request limit even when caller passes a
    # higher max_chars (e.g. shows that inherited the ElevenLabs default).
    effective_max = min(max_chars, GROK_MAX_CHARS_PER_REQUEST)
    chunks = chunk_text(text, max_chars=effective_max)

    if len(chunks) == 1:
        out_text = chunks[0]
        if append_exclamation:
            out_text = out_text + "!"
        grok_speak_chunk(
            out_text, voice_id, Path(filename),
            api_key=api_key, language_code=language_code, timeout=timeout,
        )
        logger.info("Grok TTS: Generated single chunk (%d chars)", len(out_text))
        return

    logger.info(
        "Grok TTS: Splitting into %d chunks for seamless generation",
        len(chunks),
    )
    import tempfile as _tmpmod
    tmp_dir = Path(_tmpmod.mkdtemp(prefix="tts_grok_", dir=str(Path(filename).parent)))
    chunk_files: List[Path] = []
    wav_files: List[Path] = []
    try:
        for i, chunk_text_str in enumerate(chunks):
            chunk_file = tmp_dir / f"tts_chunk_{i:03d}.mp3"
            if append_exclamation:
                if i < len(chunks) - 1:
                    chunk_text_str = chunk_text_str.rstrip(".!?") + "."
                else:
                    chunk_text_str = chunk_text_str + "!"
            grok_speak_chunk(
                chunk_text_str, voice_id, chunk_file,
                api_key=api_key, language_code=language_code, timeout=timeout,
            )
            chunk_files.append(chunk_file)
            logger.info(
                "Grok TTS: Generated chunk %d/%d (%d chars)",
                i + 1, len(chunks), len(chunk_text_str),
            )

        # Decode each MP3 chunk to WAV for lossless concatenation, mirroring
        # the ElevenLabs path. Output is mono 44.1 kHz to match the rest
        # of the pipeline (Grok's default is 24 kHz; ffmpeg upsamples on
        # decode and we re-encode once at the end).
        for cf in chunk_files:
            wav_file = cf.with_suffix(".wav")
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(cf), "-ar", "44100", "-ac", "1", str(wav_file)],
                check=True, capture_output=True, timeout=120,
            )
            wav_files.append(wav_file)

        _XFADE_SECS = "0.05"
        if len(wav_files) == 2:
            merged_wav = tmp_dir / "tts_merged.wav"
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(wav_files[0]), "-i", str(wav_files[1]),
                    "-filter_complex", f"acrossfade=d={_XFADE_SECS}:c1=tri:c2=tri",
                    str(merged_wav),
                ],
                check=True, capture_output=True, timeout=300,
            )
        else:
            merged_wav = wav_files[0]
            for idx in range(1, len(wav_files)):
                step_out = tmp_dir / f"tts_xfade_{idx:03d}.wav"
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", str(merged_wav), "-i", str(wav_files[idx]),
                        "-filter_complex", f"acrossfade=d={_XFADE_SECS}:c1=tri:c2=tri",
                        str(step_out),
                    ],
                    check=True, capture_output=True, timeout=300,
                )
                merged_wav = step_out

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(merged_wav),
                "-c:a", "libmp3lame", "-q:a", "2",
                str(filename),
            ],
            check=True, capture_output=True, timeout=300,
        )
        logger.info(
            "Grok TTS: Concatenated %d chunks via WAV intermediates "
            "(single MP3 encode)", len(chunks),
        )
    finally:
        for cf in chunk_files + wav_files:
            try:
                if cf.exists():
                    cf.unlink()
            except Exception:
                pass
        for tmp_file in tmp_dir.glob("tts_xfade_*.wav"):
            try:
                tmp_file.unlink()
            except Exception:
                pass
        for tmp_file in tmp_dir.glob("tts_merged.wav"):
            try:
                tmp_file.unlink()
            except Exception:
                pass
        try:
            if tmp_dir.exists() and tmp_dir != Path(filename).parent:
                tmp_dir.rmdir()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public entry points (provider-aware)
# ---------------------------------------------------------------------------

def synthesize(
    text: str,
    voice_id: str,
    output_path: str | Path,
    *,
    api_key: str,
    provider: str = "elevenlabs",
    max_chars: int = 10000,
    model_id: str = "eleven_flash_v2_5",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
    language_code: str = "",
    speed: float = 1.0,
    apply_text_normalization: str = "on",
    timeout: int = 120,
    append_exclamation: bool = False,
) -> Path:
    """Top-level entry point: text in, audio file path out.

    *provider* picks the backend:

      - ``"elevenlabs"`` (default) — uses the ElevenLabs streaming endpoint
        with the full ElevenLabs voice-settings palette (stability /
        similarity_boost / style / speed / model_id).
      - ``"grok"`` — uses xAI's ``/v1/tts`` endpoint. Voice settings other
        than ``language_code`` are ignored (Grok doesn't expose them).

    Handles chunking and concatenation internally so callers just pass
    text and get back a path.
    """
    output_path = Path(output_path)
    if provider == "grok":
        # Grok's "auto" detects language; explicit codes (e.g. "ru") are
        # the safer choice for non-English shows.
        _speak_with_grok(
            text, voice_id, str(output_path),
            api_key=api_key,
            max_chars=max_chars,
            language_code=language_code or "auto",
            timeout=timeout,
            append_exclamation=append_exclamation,
        )
        return output_path
    # Default: ElevenLabs
    speak(
        text,
        voice_id,
        str(output_path),
        api_key=api_key,
        max_chars=max_chars,
        model_id=model_id,
        stability=stability,
        similarity_boost=similarity_boost,
        style=style,
        language_code=language_code,
        speed=speed,
        apply_text_normalization=apply_text_normalization,
        timeout=timeout,
        append_exclamation=append_exclamation,
    )
    return output_path


def synthesize_sections(
    sections: List[str],
    voice_id: str,
    output_dir: Path,
    *,
    api_key: str,
    provider: str = "elevenlabs",
    section_prefix: str = "section",
    max_chars: int = 10000,
    model_id: str = "eleven_flash_v2_5",
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
    language_code: str = "",
    speed: float = 1.0,
    apply_text_normalization: str = "on",
    timeout: int = 120,
) -> List[Path]:
    """Synthesize multiple script sections into individual audio files.

    Each section is synthesized via the configured *provider* backend
    (``elevenlabs`` or ``grok``), reusing the chunking / concatenation
    pipeline of that provider. Returns an ordered list of MP3 paths —
    one per section.

    Parameters
    ----------
    sections:
        Ordered list of text sections to synthesize.
    voice_id:
        Backend-specific voice ID. ElevenLabs uses 20-char alphanumeric
        IDs; Grok uses the named voices (``eve``, ``ara``, etc.) or
        custom 8-char alphanumeric IDs.
    output_dir:
        Directory for intermediate per-section MP3 files.
    api_key:
        ElevenLabs key for ``provider="elevenlabs"``; xAI / Grok key for
        ``provider="grok"``.
    section_prefix:
        Filename prefix for section files.
    max_chars:
        Maximum characters per TTS API chunk.

    Returns
    -------
    list[Path]
        Ordered list of MP3 file paths, one per section.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    section_files: List[Path] = []

    for i, section_text in enumerate(sections):
        section_text = section_text.strip()
        if not section_text:
            logger.warning("Skipping empty section %d", i)
            continue

        section_path = output_dir / f"{section_prefix}_{i:03d}.mp3"
        if provider == "grok":
            _speak_with_grok(
                section_text,
                voice_id,
                str(section_path),
                api_key=api_key,
                max_chars=max_chars,
                language_code=language_code or "auto",
                timeout=timeout,
            )
        else:
            speak(
                section_text,
                voice_id,
                str(section_path),
                api_key=api_key,
                max_chars=max_chars,
                model_id=model_id,
                stability=stability,
                similarity_boost=similarity_boost,
                style=style,
                language_code=language_code,
                speed=speed,
                apply_text_normalization=apply_text_normalization,
                timeout=timeout,
            )
        section_files.append(section_path)
        logger.info(
            "Synthesized section %d/%d (%d chars): %s",
            i + 1, len(sections), len(section_text), section_path.name,
        )

    return section_files


