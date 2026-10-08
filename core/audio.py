"""FFmpeg-based audio extraction.

The pipeline only ever needs one artefact from this module: a 16 kHz mono
WAV file that faster-whisper can consume directly.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from config import AudioSettings
from utils.errors import SudoScriptError

logger = logging.getLogger(__name__)

_STDERR_TAIL_CHARS = 500


class AudioExtractionError(SudoScriptError):
    """Raised when FFmpeg fails to produce a usable audio track."""


def _require_file(path: Path) -> Path:
    if not path.is_file():
        raise AudioExtractionError(f"Input file does not exist: {path}")
    return path


def _require_tool(binary: str) -> None:
    if shutil.which(binary) is None:
        raise AudioExtractionError(
            f"'{binary}' was not found on PATH. Install FFmpeg and make sure "
            "both 'ffmpeg' and 'ffprobe' are available."
        )


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def extract_audio(
    video_path: str | Path, output_wav: str | Path, settings: AudioSettings
) -> Path:
    """Extract a 16 kHz mono PCM WAV track from *video_path*.

    Returns the path of the created WAV file. Raises AudioExtractionError
    with a readable, actionable message on any failure.
    """
    video = _require_file(Path(video_path))
    _require_tool(settings.ffmpeg_bin)

    output = Path(output_wav)
    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(settings.sample_rate_hz),
        "-c:a",
        "pcm_s16le",
        str(output),
    ]
    result = _run(cmd)
    if result.returncode != 0:
        detail = result.stderr.strip()[-_STDERR_TAIL_CHARS:]
        raise AudioExtractionError(
            f"FFmpeg failed while extracting audio from '{video.name}'.\n{detail}"
        )
    if not output.is_file() or output.stat().st_size == 0:
        raise AudioExtractionError(
            f"FFmpeg produced no audio for '{video.name}'. "
            "The file may have no audio track at all."
        )
    logger.info("Audio track ready: %s", output)
    return output


def probe_duration_s(video_path: str | Path, settings: AudioSettings) -> float:
    """Return the container duration of *video_path* in seconds.

    Used by the pipeline to validate frame-sampling timestamps. Raises
    AudioExtractionError when the file cannot be probed.
    """
    video = _require_file(Path(video_path))
    _require_tool(settings.ffprobe_bin)

    cmd = [
        settings.ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video),
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise AudioExtractionError(
            f"ffprobe could not read duration of '{video.name}'."
        )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise AudioExtractionError(
            f"ffprobe returned a non-numeric duration for '{video.name}'."
        ) from exc
