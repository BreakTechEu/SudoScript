"""Pipeline orchestration.

The pipeline is a fixed sequence of steps over a persistent work
directory. Intermediate results (transcript, cuts, translations) are
cached as JSON, so a long job interrupted at, say, the translation step
can be resumed with --from-step without recomputing FFmpeg, Whisper or
scene analysis.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from config import Settings
from core import audio, scene, transcriber, video
from core import translator as translator_module
from core.formatters import dubbing, subtitle, voiceover
from utils.errors import SudoScriptError
from utils.schema import OutputFormat, Segment, Transcript, WorkMode

logger = logging.getLogger(__name__)

STEP_AUDIO = "audio"
STEP_CUTS = "cuts"
STEP_TRANSCRIBE = "transcribe"
STEP_FRAMES = "frames"
STEP_TRANSLATE = "translate"
STEP_EXPORT = "export"

STEP_ORDER = [
    STEP_AUDIO,
    STEP_CUTS,
    STEP_TRANSCRIBE,
    STEP_FRAMES,
    STEP_TRANSLATE,
    STEP_EXPORT,
]


@dataclass
class PipelineOptions:
    """User-facing pipeline choices."""

    mode: WorkMode = WorkMode.SUBTITLES
    output_format: OutputFormat = OutputFormat.SRT
    target_language: str = "Polish"
    output_path: Path | None = None  # default: next to the video
    work_dir: Path | None = None  # default: <video dir>/.sudoscript


class Pipeline:
    """Runs the six SudoScript steps, with caching and resume support."""

    def __init__(
        self,
        video_path: str | Path,
        settings: Settings,
        options: PipelineOptions,
    ):
        self.video_path = Path(video_path)
        self.settings = settings
        self.options = options
        self.work_dir = options.work_dir or (
            self.video_path.parent / ".sudoscript" / self.video_path.stem
        )
        self._transcript: Transcript | None = None
        self._cuts: list[float] = []
        self._cuts_cached: bool = False
        self._load_state()

    # ------------------------------------------------------------------
    # state persistence
    # ------------------------------------------------------------------

    @property
    def state_path(self) -> Path:
        return self.work_dir / "state.json"

    def _load_state(self) -> None:
        if not self.state_path.is_file():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._transcript = Transcript.from_json(
                json.dumps(data.get("transcript", {}), ensure_ascii=False)
            )
            self._cuts = [float(c) for c in data.get("cuts", [])]
            self._cuts_cached = True
            logger.info(
                "Resumed cached state from %s (%d segments, %d cuts).",
                self.state_path,
                len(self._transcript.segments),
                len(self._cuts),
            )
        except (OSError, ValueError) as exc:
            logger.warning("Ignoring unreadable state file (%s); starting fresh.", exc)
            self._transcript = None
            self._cuts = []

    def _save_state(self) -> None:
        self.work_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "video": str(self.video_path),
            "cuts": self._cuts,
            "transcript": (
                json.loads(self._transcript.to_json()) if self._transcript else None
            ),
        }
        self.state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # steps
    # ------------------------------------------------------------------

    def _step_audio(self) -> Path:
        wav_path = self.work_dir / "audio.wav"
        if wav_path.is_file():
            logger.info("Reusing cached audio: %s", wav_path)
            return wav_path
        return audio.extract_audio(self.video_path, wav_path, self.settings.audio)

    def _step_cuts(self) -> None:
        self._cuts = scene.detect_scene_cuts(self.video_path, self.settings.scene)
        self._cuts_cached = True
        self._save_state()

    def _step_transcribe(self) -> Transcript:
        wav_path = self._step_audio()
        self._transcript = transcriber.transcribe(wav_path, self.settings.whisper)
        self._save_state()
        return self._transcript

    def _step_frames(self) -> None:
        if not self._transcript:
            raise SudoScriptError("Transcription must run before frame sampling.")
        video.sample_frames(
            self.video_path,
            self._transcript.segments,
            self.work_dir / "frames",
            self.settings.audio,
            jpeg_quality=self.settings.frame_quality,
        )

    def _step_translate(self) -> None:
        if not self._transcript:
            raise SudoScriptError("Transcription must run before translation.")
        client = translator_module.OllamaClient(self.settings.ollama)
        client.ensure_available()
        translator_module.translate_segments(
            self._transcript.segments,
            client,
            self.options.mode,
            self.options.target_language,
        )
        self._save_state()

    def _step_export(self) -> Path:
        if not self._transcript:
            raise SudoScriptError("Transcription must run before export.")
        output = self._resolve_output_path()
        fmt = self.options.output_format
        if self.options.mode == WorkMode.SUBTITLES:
            if fmt not in (OutputFormat.SRT, OutputFormat.ASS):
                raise SudoScriptError(
                    f"Subtitles mode supports .srt and .ass output; got '{fmt.value}'."
                )
            events = subtitle.build_events(
                self._transcript.segments, self.settings.subtitles
            )
            events = subtitle.enforce_durations(events, self.settings.subtitles)
            events = subtitle.avoid_scene_cuts(
                events, self._cuts, self.settings.subtitles
            )
            return subtitle.export(events, output)
        if self.options.mode == WorkMode.VOICEOVER:
            if fmt == OutputFormat.CSV:
                return voiceover.export_csv(
                    self._transcript.segments, output, self.settings.voiceover
                )
            return voiceover.export_json(
                self._transcript.segments,
                output,
                self._transcript.language,
                self.settings.voiceover,
            )
        if self.options.mode == WorkMode.DUBBING:
            return dubbing.export_json(self._transcript.segments, output)
        raise SudoScriptError(f"Unsupported work mode: {self.options.mode}")

    def _resolve_output_path(self) -> Path:
        if self.options.output_path:
            return Path(self.options.output_path)
        fmt = self.options.output_format.value
        return self.video_path.with_suffix(f".{fmt}")

    # ------------------------------------------------------------------
    # orchestration
    # ------------------------------------------------------------------

    def run(self, from_step: str = STEP_AUDIO) -> Path:
        """Run the pipeline starting from *from_step*.

        A step runs when it is requested, or when a later requested step
        depends on its artefact and nothing usable is cached.
        """
        if from_step not in STEP_ORDER:
            raise SudoScriptError(
                f"Unknown step '{from_step}'. Valid steps: {', '.join(STEP_ORDER)}"
            )
        start_index = STEP_ORDER.index(from_step)

        def needs(step: str) -> bool:
            return STEP_ORDER.index(step) >= start_index

        if needs(STEP_CUTS) or not self._cuts_cached:
            self._step_cuts()

        if needs(STEP_TRANSCRIBE) or self._transcript is None:
            self._step_transcribe()

        if needs(STEP_FRAMES):
            self._step_frames()

        if needs(STEP_TRANSLATE) or self._translations_missing():
            self._step_translate()

        return self._step_export()

    def segments(self) -> list[Segment]:
        """Access the (possibly cached) transcript segments."""
        if not self._transcript:
            raise SudoScriptError("No transcript available yet.")
        return self._transcript.segments

    def _translations_missing(self) -> bool:
        """True when the cached transcript has no translated segments at all."""
        if not self._transcript or not self._transcript.segments:
            return True
        return not any(segment.translated_text for segment in self._transcript.segments)
