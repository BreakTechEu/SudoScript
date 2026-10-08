"""Frame sampling with FFmpeg.

For every transcribed utterance a single still frame is extracted from
the middle of the phrase. The frame is the visual context that the VLM
uses to infer speaker gender, formality and props on screen.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from config import AudioSettings
from utils.errors import SudoScriptError
from utils.schema import Segment

logger = logging.getLogger(__name__)

_STDERR_TAIL_CHARS = 500


class FrameSamplingError(SudoScriptError):
    """Raised when the video file cannot be read for frame extraction."""


def extract_frame(
    video_path: str | Path,
    timestamp_s: float,
    output_path: str | Path,
    settings: AudioSettings,
    jpeg_quality: int = 2,
) -> Path | None:
    """Extract one frame at *timestamp_s* into a JPEG file.

    Returns the output path on success, or None when FFmpeg could not
    produce a frame (e.g. timestamp beyond the video end). A missing
    frame is never fatal: the translator simply falls back to text-only
    mode for that segment.
    """
    video = Path(video_path)
    if not video.is_file():
        raise FrameSamplingError(f"Input file does not exist: {video}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{max(timestamp_s, 0.0):.3f}",
        "-i",
        str(video),
        "-frames:v",
        "1",
        "-q:v",
        str(jpeg_quality),
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
        logger.debug(
            "No frame at %.3fs for '%s': %s",
            timestamp_s,
            video.name,
            result.stderr.strip()[-_STDERR_TAIL_CHARS:],
        )
        output.unlink(missing_ok=True)
        return None
    return output


def sample_frames(
    video_path: str | Path,
    segments: list[Segment],
    frames_dir: str | Path,
    settings: AudioSettings,
    jpeg_quality: int = 2,
) -> list[Segment]:
    """Attach a sampled frame path to each segment (in place and returned).

    Segments whose frame could not be extracted keep frame_path=None and
    the pipeline continues: translation quality degrades gracefully from
    multimodal to text-only for those lines.
    """
    video = Path(video_path)
    frames = Path(frames_dir)
    frames.mkdir(parents=True, exist_ok=True)

    failures = 0
    for segment in segments:
        frame_path = extract_frame(
            video,
            segment.midpoint_s,
            frames / f"seg_{segment.index:05d}.jpg",
            settings,
            jpeg_quality=jpeg_quality,
        )
        segment.frame_path = str(frame_path) if frame_path else None
        failures += frame_path is None

    logger.info(
        "Sampled %d/%d frames (%d missing).",
        len(segments) - failures,
        len(segments),
        failures,
    )
    return segments
