"""Grok Video API wrapper for full-episode video generation.

Generates multiple video clips from podcast script segments and stitches them
together for full-length YouTube videos. Parallel to the image-generation path
(engine.grok_imagine), but produces videos instead of still images.

Pricing (xAI docs, June 2026):
  480p:  $0.05 / second
  720p:  $0.07 / second
  Media input: $0.01/sec + $0.002/image

Max duration per clip: 15 seconds. For a 14-minute episode, we generate
~56 clips (900 seconds ÷ 16 seconds avg per clip with overlap), stitch them,
and encode to MP4 for YouTube.

Endpoint: POST https://api.x.ai/v1/videos/generations
Status:   GET  https://api.x.ai/v1/videos/{request_id}

Processing is asynchronous (up to several minutes). The pipeline polls
for completion and downloads the temporary URL when ready.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from datetime import datetime

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

GROK_VIDEO_ENDPOINT = "https://api.x.ai/v1/videos/generations"
GROK_VIDEO_STATUS_ENDPOINT = "https://api.x.ai/v1/videos"
DEFAULT_TIMEOUT_S = 60
DEFAULT_POLL_INTERVAL_S = 3
MAX_POLL_ATTEMPTS = 300  # 15 minutes at 3s intervals

# Pricing per second of video output
VIDEO_COST_USD = {
    "480p": 0.05,
    "720p": 0.07,
}

# Aspect ratios and their optimal resolutions for YouTube
ASPECT_RATIOS = {
    "16:9": "720p",  # Full-length episodes
    "9:16": "720p",  # Shorts
}


class GrokVideoError(RuntimeError):
    """Raised on a non-recoverable Grok Video API failure."""


@dataclass
class VideoClip:
    """Represents a single generated video clip."""

    clip_id: str
    request_id: str
    prompt: str
    duration_seconds: int
    resolution: str
    url: Optional[str] = None
    local_path: Optional[Path] = None
    status: str = "queued"  # queued, pending, completed, failed
    cost_usd: float = 0.0
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class GrokVideoResult:
    """Wraps video generation results plus cost tracking."""

    episode_num: int
    full_video_path: Optional[Path] = None
    short_video_path: Optional[Path] = None
    clips: List[VideoClip] = field(default_factory=list)
    total_cost_usd: float = 0.0
    generation_time_s: float = 0.0
    is_fallback: bool = False
    failures: List[str] = field(default_factory=list)


def _build_video_prompt(
    segment_text: str,
    show_config=None,
    hook: str = "",
    episode_title: str = "Episode",
    segment_index: int = 0,
    total_segments: int = 1,
    previous_visual_note: str = "",
) -> str:
    """Build a show-specific, visually coherent video prompt.

    Args:
        segment_text: The podcast script for this 15-second clip
        show_config: The loaded show config (has video_genre, video_mood, etc.)
        hook: The episode hook (headline/narrative)
        episode_title: Full episode title
        segment_index: Which segment this is (0 = first)
        total_segments: Total number of segments
        previous_visual_note: Continuity hint from prior segment

    Returns:
        Full prompt for Grok Video API
    """
    # Extract video-specific fields from config, with sensible defaults
    genre = ""
    mood = ""
    keywords = []
    visual_style = ""

    if show_config and hasattr(show_config, "youtube"):
        yt = show_config.youtube
        genre = getattr(yt, "video_genre", "")
        mood = getattr(yt, "video_mood", "")
        keywords = getattr(yt, "video_keywords", [])
        visual_style = getattr(yt, "video_visual_style", "")

    # Fallback genre if not specified
    if not genre:
        genre = "technology-news"

    # Build keywords string (first 5, joined)
    keywords_str = ", ".join(keywords[:5]) if keywords else ""

    # Truncate segment text for prompt inclusion
    segment_preview = segment_text[:500] if segment_text else ""

    # Continuity note for non-first segments
    continuity_line = ""
    if segment_index > 0 and previous_visual_note:
        continuity_line = f"\nVISUAL CONTINUITY NOTE: {previous_visual_note}"

    prompt = f"""Generate a professional, high-production-value video clip for a podcast episode.

PODCAST CONTEXT:
- Episode Title: {episode_title}
- Main Topic: {hook if hook else episode_title}
- Content Genre: {genre}
- Mood/Tone: {mood if mood else "professional"}
- Key Topics: {keywords_str if keywords_str else "technology news"}
- Segment: {segment_index + 1} of {total_segments}

VISUAL DIRECTION:
{visual_style if visual_style else "Cinematic, professional, modern, high production value"}

SCRIPT FOR THIS SEGMENT:
{segment_preview}

REQUIREMENTS:
- Duration: exactly 15 seconds
- Resolution: 1280x720 (16:9 YouTube standard)
- Visual style: Cohesive with podcast branding and episode theme
- No text overlays or subtitles (podcast provides audio)
- Dynamic camera movements, varied composition
- Professional color grading, bright and clear
- Smooth transitions between shots
- High-quality licensed or original content{continuity_line}

AVOID:
- Blurry or low-quality footage
- Excessive special effects that distract from content
- Irrelevant or off-topic visuals
- Text overlays or watermarks
- Generic "news broadcast" aesthetic
- Talking heads unless essential to the topic"""

    return prompt.strip()


def _composite_video_with_audio(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
) -> bool:
    """Composite a video with pre-mixed audio using FFmpeg.

    This ensures the pre-mixed podcast audio (with intro/outro music,
    EQ, compression) is used instead of any audio the video might have.

    Args:
        video_path: Path to the video MP4 (may have audio)
        audio_path: Path to the pre-mixed audio (MP3 or WAV)
        output_path: Where to write the composited result

    Returns:
        True if successful, False otherwise
    """
    if not video_path.exists():
        logger.error("Video file not found: %s", video_path)
        return False
    if not audio_path.exists():
        logger.error("Audio file not found: %s", audio_path)
        return False

    try:
        # FFmpeg command to composite video + audio
        # -c:v copy: Keep video codec (no re-encoding, preserve quality)
        # -c:a aac: Use AAC audio codec (YouTube-compatible)
        # -map 0:v:0 -map 1:a:0: Use video from input 0, audio from input 1
        # -shortest: Stop at shortest input (safety against video overflow)
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            "-y",
            str(output_path),
        ]

        logger.info("Compositing video with audio: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            logger.error(
                "FFmpeg audio composite failed: %s\nStderr: %s",
                result.returncode, result.stderr,
            )
            return False

        logger.info(
            "Audio composite successful: %s (%.1f MB)",
            output_path,
            output_path.stat().st_size / (1024 * 1024),
        )
        return True

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg audio composite timed out for %s", video_path)
        return False
    except Exception as exc:
        logger.error("FFmpeg audio composite error: %s", exc)
        return False


def _break_script_into_clips(
    script: str,
    max_duration_s: int = 15,
    overlap_s: int = 1,
) -> List[tuple[str, int]]:
    """Break a podcast script into segments for video generation.

    Each segment becomes a separate API call to Grok Video. We target
    *max_duration_s* per clip (the API max is 15s), with slight overlap
    to ensure smooth stitching.

    Returns: List of (segment_text, estimated_duration_s) tuples.
    """
    if not script or not script.strip():
        return []

    # Simple heuristic: ~150 words per minute of speech ≈ 2.5 words/sec
    # So 15 seconds ≈ 37–40 words. We'll use a conservative estimate
    # and split on sentence boundaries when possible.
    words_per_second = 2.5
    target_words = int(max_duration_s * words_per_second)

    segments = []
    sentences = script.split(". ")

    current_segment = []
    current_word_count = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        word_count = len(sentence.split())

        # If adding this sentence would exceed target, save current segment
        if current_word_count + word_count > target_words and current_segment:
            segment_text = ". ".join(current_segment) + "."
            estimated_duration = int(current_word_count / words_per_second)
            segments.append((segment_text, estimated_duration))
            current_segment = [sentence]
            current_word_count = word_count
        else:
            current_segment.append(sentence)
            current_word_count += word_count

    # Flush remaining segment
    if current_segment:
        segment_text = ". ".join(current_segment) + "."
        estimated_duration = int(current_word_count / words_per_second)
        segments.append((segment_text, estimated_duration))

    logger.info(
        "Split script into %d video clips (target %ds each)",
        len(segments), max_duration_s,
    )

    return segments


def _post_video_request(
    payload: dict,
    api_key: str,
    timeout_s: int,
) -> requests.Response:
    """One-shot POST to the video generations endpoint."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(
        GROK_VIDEO_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=timeout_s,
    )


@retry(
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _request_one_video(
    prompt: str,
    *,
    duration_s: int,
    api_key: str,
    resolution: str = "720p",
    aspect_ratio: str = "16:9",
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> str:
    """POST a single prompt to /v1/videos/generations and return the request_id.

    The API returns immediately with a request_id; the actual video
    generation happens asynchronously. Caller must poll the status
    endpoint to get the final video URL.
    """
    payload = {
        "model": "grok-imagine-video",
        "prompt": prompt,
        "duration": max(1, min(duration_s, 15)),  # Clamp to 1-15 seconds
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
    }

    resp = _post_video_request(payload, api_key, timeout_s)

    if resp.status_code >= 400:
        raise GrokVideoError(
            f"Grok Video HTTP {resp.status_code}: {resp.text[:300]}"
        )

    body = resp.json()
    try:
        request_id = body["id"]
    except (KeyError, TypeError) as exc:
        raise GrokVideoError(
            f"Grok Video response missing 'id': {body!r}"
        ) from exc

    return request_id


def _poll_video_status(
    request_id: str,
    *,
    api_key: str,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    max_attempts: int = MAX_POLL_ATTEMPTS,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> dict:
    """Poll the status endpoint until the video is ready or fails.

    Returns the final response body when status is 'completed'.
    Raises GrokVideoError if the video generation fails or times out.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{GROK_VIDEO_STATUS_ENDPOINT}/{request_id}"

    for attempt in range(max_attempts):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout_s)
            if resp.status_code >= 400:
                raise GrokVideoError(
                    f"Grok Video status HTTP {resp.status_code}: {resp.text[:300]}"
                )

            body = resp.json()
            status = body.get("status", "unknown")

            logger.debug(
                "Grok Video %s status check (attempt %d/%d): %s",
                request_id, attempt + 1, max_attempts, status,
            )

            if status == "completed":
                logger.info("Grok Video %s completed", request_id)
                return body

            if status == "failed":
                error = body.get("error", {})
                msg = error.get("message", "Unknown error")
                raise GrokVideoError(f"Grok Video generation failed: {msg}")

            # Still pending — wait and retry
            if attempt < max_attempts - 1:
                time.sleep(poll_interval_s)

        except requests.exceptions.RequestException as exc:
            if attempt < max_attempts - 1:
                logger.warning(
                    "Grok Video status check failed (attempt %d/%d): %s",
                    attempt + 1, max_attempts, exc,
                )
                time.sleep(poll_interval_s)
            else:
                raise GrokVideoError(
                    f"Grok Video status polling failed: {exc}"
                ) from exc

    raise GrokVideoError(
        f"Grok Video {request_id} timed out after {max_attempts} attempts"
    )


def _download_video(url: str, output_path: Path, timeout_s: int = 120) -> bool:
    """Download a video from the temporary URL and save locally."""
    try:
        resp = requests.get(url, timeout=timeout_s, stream=True)
        if resp.status_code >= 400:
            logger.error(
                "Failed to download video from %s: HTTP %d",
                url, resp.status_code,
            )
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info("Downloaded video to %s", output_path)
        return True

    except Exception as exc:
        logger.error("Failed to download video: %s", exc)
        return False


def _stitch_videos_ffmpeg(
    input_paths: List[Path],
    output_path: Path,
    cleanup: bool = True,
) -> bool:
    """Concatenate multiple video files using ffmpeg.

    Uses the concat demuxer for seamless stitching. Requires ffmpeg
    with libx264 (H.264 codec) for MP4 output.
    """
    if not input_paths:
        logger.error("No input videos to stitch")
        return False

    # Create a concat demuxer file
    concat_file = output_path.parent / "concat.txt"
    try:
        with open(concat_file, "w") as f:
            for path in input_paths:
                f.write(f"file '{path.resolve()}'\n")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # ffmpeg concat: take input from concat.txt, re-encode to h264
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",  # Quality: 18-28, lower is better
            "-c:a", "aac",
            "-q:a", "5",
            "-y",  # Overwrite output
            str(output_path),
        ]

        logger.info("Stitching %d video clips → %s", len(input_paths), output_path)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes
        )

        if result.returncode != 0:
            logger.error(
                "ffmpeg stitching failed: %s",
                result.stderr[-500:] if result.stderr else "unknown error",
            )
            return False

        logger.info("Successfully stitched videos to %s", output_path)

        # Cleanup temporary concat file
        if cleanup:
            concat_file.unlink(missing_ok=True)

        return True

    except subprocess.TimeoutExpired:
        logger.error("ffmpeg stitching timed out")
        return False
    except Exception as exc:
        logger.error("ffmpeg stitching error: %s", exc)
        return False


def generate_grok_videos(
    *,
    work_dir: Path,
    episode_num: int,
    podcast_script: str,
    hook: str = "",
    episode_title: str = "Episode",
    api_key: Optional[str] = None,
    resolution: str = "720p",
    aspect_ratio: str = "16:9",
    generate_short: bool = True,
    short_duration_seconds: int = 40,
    final_mp3_path: Optional[Path] = None,
    show_config=None,
) -> GrokVideoResult:
    """Generate full-length and short videos from a podcast script.

    Workflow:
    1. Split the script into 15-second clips (max API duration)
    2. Generate each clip via Grok Video API (async)
    3. Poll for completion
    4. Download each clip
    5. Stitch clips together for full video
    6. Composite video with pre-mixed audio (if provided)
    7. Optionally generate a separate short version

    Args:
        work_dir: Directory for video output
        episode_num: Episode number (for file naming)
        podcast_script: The full podcast script text
        hook: Episode hook/headline (optional, used in prompts)
        episode_title: Episode title (optional, used in prompts)
        api_key: Grok API key (falls back to env vars if not provided)
        resolution: "720p" or "480p" for video quality
        aspect_ratio: "16:9" for full-length, "9:16" for shorts
        generate_short: Whether to generate a short version
        short_duration_seconds: Duration in seconds for the short
        final_mp3_path: Path to pre-mixed episode audio (for composite)
        show_config: Show configuration object (has video_genre, video_mood, etc.)

    Returns:
        GrokVideoResult with paths to generated videos and cost tracking.
    """
    start_time = time.time()

    if api_key is None:
        api_key = (
            os.getenv("GROK_API_KEY", "").strip()
            or os.getenv("XAI_API_KEY", "").strip()
        )

    result = GrokVideoResult(episode_num=episode_num)

    # Fallback if no API key
    if not api_key:
        logger.warning(
            "GROK_API_KEY/XAI_API_KEY not set — video generation fallback"
        )
        result.is_fallback = True
        return result

    # Break script into clips
    script_segments = _break_script_into_clips(podcast_script)
    if not script_segments:
        logger.warning("No script segments to generate video from")
        result.is_fallback = True
        return result

    # Generate video prompts from segments using show-specific prompt builder
    clips = []
    num_segments = len(script_segments)
    for idx, (segment_text, est_duration) in enumerate(script_segments):
        # Build a show-specific, visually coherent prompt
        prompt = _build_video_prompt(
            segment_text=segment_text,
            show_config=show_config,
            hook=hook,
            episode_title=episode_title,
            segment_index=idx,
            total_segments=num_segments,
        )

        clip = VideoClip(
            clip_id=f"ep{episode_num:03d}_clip{idx:02d}",
            request_id="",
            prompt=prompt[:2000],  # API accepts longer prompts now
            duration_seconds=min(est_duration, 15),  # Clamp to max
            resolution=resolution,
        )
        clips.append(clip)

    logger.info(
        "Generated %d video prompts for episode %d",
        len(clips), episode_num,
    )

    # Submit all clips for generation (sequential with rate limiting)
    # The Grok Video API has resource limits; submitting too fast causes HTTP 429.
    # 1-2s delay between submissions keeps us within safe limits.
    SUBMISSION_DELAY_S = 1.5

    for idx, clip in enumerate(clips):
        # Rate limit: wait between submissions (but not before the first)
        if idx > 0:
            logger.info(
                "Rate limit: waiting %.1fs before clip %d/%d",
                SUBMISSION_DELAY_S, idx + 1, len(clips),
            )
            time.sleep(SUBMISSION_DELAY_S)

        try:
            request_id = _request_one_video(
                clip.prompt,
                duration_s=clip.duration_seconds,
                api_key=api_key,
                resolution=resolution,
                aspect_ratio=aspect_ratio,
            )
            clip.request_id = request_id
            clip.status = "pending"
            logger.info(
                "Submitted video clip %s (request_id=%s, %d/%d)",
                clip.clip_id, request_id, idx + 1, len(clips),
            )
        except GrokVideoError as exc:
            clip.status = "failed"
            clip.error_message = str(exc)
            result.failures.append(f"{clip.clip_id}: {exc}")
            logger.warning("Failed to submit %s: %s", clip.clip_id, exc)

    # Poll for completion and download
    video_dir = work_dir / f"videos_ep{episode_num:03d}"
    video_dir.mkdir(parents=True, exist_ok=True)

    completed_clips = []
    for clip in clips:
        if clip.status == "failed":
            continue

        try:
            status_response = _poll_video_status(
                clip.request_id,
                api_key=api_key,
            )

            # Extract video URL from response
            url = status_response.get("url")
            if not url:
                raise GrokVideoError(
                    f"Response missing video URL: {status_response}"
                )

            # Download the video
            local_path = video_dir / f"{clip.clip_id}.mp4"
            if _download_video(url, local_path):
                clip.url = url
                clip.local_path = local_path
                clip.status = "completed"

                # Calculate cost: duration * cost_per_second
                duration_sec = clip.duration_seconds
                cost_per_sec = VIDEO_COST_USD.get(resolution, 0.07)
                clip.cost_usd = round(duration_sec * cost_per_sec, 4)
                result.total_cost_usd += clip.cost_usd

                completed_clips.append(clip)
                logger.info(
                    "Completed %s (duration=%ds, cost=$%.4f)",
                    clip.clip_id, duration_sec, clip.cost_usd,
                )
            else:
                clip.status = "failed"
                clip.error_message = "Download failed"
                result.failures.append(f"{clip.clip_id}: Download failed")

        except GrokVideoError as exc:
            clip.status = "failed"
            clip.error_message = str(exc)
            result.failures.append(f"{clip.clip_id}: {exc}")
            logger.warning("Failed to complete %s: %s", clip.clip_id, exc)

    result.clips = clips

    # Stitch completed clips together
    if completed_clips:
        local_paths = [c.local_path for c in completed_clips]
        full_video_path = video_dir / f"episode_{episode_num:03d}_full.mp4"

        if _stitch_videos_ffmpeg(local_paths, full_video_path):
            logger.info("Full episode video stitched: %s", full_video_path)

            # Composite with pre-mixed audio if provided
            if final_mp3_path and final_mp3_path.exists():
                audio_composited_path = video_dir / f"episode_{episode_num:03d}_with_audio.mp4"
                if _composite_video_with_audio(full_video_path, final_mp3_path, audio_composited_path):
                    # Replace the video path with the audio-composited version
                    full_video_path.unlink()  # Remove the video-only version
                    audio_composited_path.rename(full_video_path)  # Rename to standard name
                    result.full_video_path = full_video_path
                    logger.info("Full episode video ready with audio composite: %s", full_video_path)
                else:
                    logger.warning("Audio composite failed; using video-only version")
                    result.full_video_path = full_video_path
                    result.failures.append("Audio composite failed; using video-only")
            else:
                if not final_mp3_path:
                    logger.warning("No audio path provided; video will not have audio")
                result.full_video_path = full_video_path
                logger.info("Full episode video ready: %s", full_video_path)
        else:
            result.failures.append("Video stitching failed")
            logger.error("Failed to stitch clips for episode %d", episode_num)

    # Optionally generate short version
    if generate_short and completed_clips:
        short_clips = completed_clips[: max(1, short_duration_seconds // 15)]
        short_video_path = video_dir / f"episode_{episode_num:03d}_short.mp4"

        if _stitch_videos_ffmpeg(
            [c.local_path for c in short_clips],
            short_video_path,
        ):
            result.short_video_path = short_video_path
            logger.info("Short video ready: %s", short_video_path)
        else:
            logger.warning("Failed to generate short video")

    result.generation_time_s = round(time.time() - start_time, 2)
    logger.info(
        "Video generation complete: %d clips, $%.2f cost, %.0f seconds",
        len(completed_clips), result.total_cost_usd, result.generation_time_s,
    )

    return result
