"""Speech transcription with faster-whisper.

Produces the raw source-language text with exact per-utterance timings.
The heavy dependency is imported lazily so that the rest of the package
(including unit tests) works without a CUDA/ctranslate2 environment.
"""

from __future__ import annotations

import logging
from pathlib import Path

from config import WhisperSettings
from utils.errors import SudoScriptError
from utils.schema import Segment, Transcript

logger = logging.getLogger(__name__)


class TranscriptionError(SudoScriptError):
    """Raised when transcription fails or faster-whisper is unavailable."""


def transcribe(wav_path: str | Path, settings: WhisperSettings) -> Transcript:
    """Transcribe a 16 kHz mono WAV file into a Transcript."""
    wav = Path(wav_path)
    if not wav.is_file():
        raise TranscriptionError(f"Audio file does not exist: {wav}")

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - environment specific
        raise TranscriptionError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        ) from exc

    try:
        model = WhisperModel(
            settings.model_size,
            device=settings.device,
            compute_type=settings.compute_type,
        )
        segments_iter, info = model.transcribe(
            str(wav),
            vad_filter=settings.vad_filter,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        segments: list[Segment] = []
        for index, raw in enumerate(segments_iter):
            text = raw.text.strip()
            if not text:
                continue
            end_s = float(raw.end)
            start_s = float(raw.start)
            if end_s <= start_s:
                continue
            segments.append(
                Segment(
                    index=len(segments),
                    start_s=start_s,
                    end_s=end_s,
                    source_text=text,
                )
            )
    except TranscriptionError:
        raise
    except Exception as exc:
        raise TranscriptionError(f"Transcription failed: {exc}") from exc

    transcript = Transcript(language=getattr(info, "language", None), segments=segments)
    logger.info(
        "Transcribed %d segments (detected language: %s).",
        len(segments),
        transcript.language,
    )
    return transcript
