"""SudoScript configuration.

Every tunable pipeline setting is declared here as a small frozen dataclass.
The command line (see main.py) can override individual values without
editing this file. Keep this module dependency-free so it can be imported
anywhere, including from unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AudioSettings:
    """Audio extraction (FFmpeg) parameters."""

    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    sample_rate_hz: int = 16_000  # 16 kHz mono WAV, as expected by Whisper


@dataclass(frozen=True)
class SceneSettings:
    """Scene-cut detection (PySceneDetect) parameters."""

    threshold: float = 27.0  # ContentDetector threshold; lower = more cuts
    min_scene_len_s: float = 0.6  # cuts closer than this are ignored


@dataclass(frozen=True)
class WhisperSettings:
    """Speech transcription (faster-whisper) parameters."""

    model_size: str = "small"
    device: str = "auto"  # "auto", "cpu" or "cuda"
    compute_type: str = "auto"  # faster-whisper compute type, e.g. "int8"
    vad_filter: bool = True  # skip silence, improves segment alignment


@dataclass(frozen=True)
class OllamaSettings:
    """Local multimodal translation (Ollama) parameters."""

    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5vl:7b"
    request_timeout_s: float = 300.0
    temperature: float = 0.2  # low temperature: translation must be stable
    max_retries: int = 3  # retries per segment on transport failures


@dataclass(frozen=True)
class SubtitleRules:
    """Technical subtitle norms (Netflix-style defaults).

    Attributes are enforced by core.formatters.subtitle.
    """

    max_chars_per_line: int = 42  # CPL
    max_lines: int = 2
    max_chars_per_second: float = 17.0  # CPS (reading speed)
    min_duration_s: float = 1.0
    max_duration_s: float = 7.0
    min_gap_s: float = 0.1  # enforced gap between consecutive events
    cut_clearance_s: float = 0.08  # ~2 frames at 25 fps; never cross a scene cut


@dataclass(frozen=True)
class VoiceoverSettings:
    """Parameters for the AI-voiceover script export (phase 2 groundwork)."""

    reading_rate_cps: float = 14.0  # average narrator reading speed in chars/s


@dataclass(frozen=True)
class Settings:
    """Root configuration object used by the whole pipeline."""

    audio: AudioSettings = field(default_factory=AudioSettings)
    scene: SceneSettings = field(default_factory=SceneSettings)
    whisper: WhisperSettings = field(default_factory=WhisperSettings)
    ollama: OllamaSettings = field(default_factory=OllamaSettings)
    subtitles: SubtitleRules = field(default_factory=SubtitleRules)
    voiceover: VoiceoverSettings = field(default_factory=VoiceoverSettings)
    frame_quality: int = 2  # JPEG quality for sampled frames (2 = best)


DEFAULT_SETTINGS = Settings()
