"""Local-first transcription and translation pipeline."""
from __future__ import annotations

import base64
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from .cache import atomic_write_json, fingerprint, read_json_object, sha256_file
from .models import JobState, Segment
from .subtitles import build_srt, write_srt

log = logging.getLogger(__name__)


class SudoScriptError(RuntimeError):
    """Expected user-facing pipeline error."""


@dataclass(frozen=True)
class Settings:
    target_language: str = "Polish"
    whisper_model: str = "small"
    ollama_model: str = "qwen2.5vl:7b"
    ollama_url: str = "http://127.0.0.1:11434"
    ffmpeg: str = "ffmpeg"
    max_chars_per_line: int = 42
    max_lines: int = 2
    request_timeout_s: int = 180
    allow_remote_ollama: bool = False

    def validate(self) -> None:
        if not self.target_language.strip():
            raise SudoScriptError("Target language cannot be empty.")
        if self.max_chars_per_line < 10 or self.max_lines not in (1, 2, 3):
            raise SudoScriptError("Invalid subtitle layout limits.")
        parsed = urlparse(self.ollama_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise SudoScriptError("Ollama URL must be a valid HTTP(S) URL.")
        local_names = {"localhost", "127.0.0.1", "::1"}
        if parsed.hostname.lower() not in local_names and not self.allow_remote_ollama:
            raise SudoScriptError(
                "Remote Ollama host rejected. Use loopback by default or explicitly enable "
                "--allow-remote-ollama after reviewing the privacy implications."
            )


class Pipeline:
    STATE_SCHEMA = 1

    def __init__(self, video_path: Path, settings: Settings, workdir: Path | None = None):
        self.video_path = video_path.expanduser().resolve()
        self.settings = settings
        self.workdir = (workdir or self.video_path.parent / ".sudoscript" / self.video_path.stem)
        self.workdir = self.workdir.expanduser().resolve()
        self.state_path = self.workdir / "state.json"

    def run(self, output_path: Path | None = None) -> Path:
        self.settings.validate()
        if not self.video_path.is_file():
            raise SudoScriptError(f"Input video does not exist: {self.video_path}")
        if shutil.which(self.settings.ffmpeg) is None and not Path(self.settings.ffmpeg).is_file():
            raise SudoScriptError(f"FFmpeg executable not found: {self.settings.ffmpeg}")

        self.workdir.mkdir(parents=True, exist_ok=True)
        input_hash = sha256_file(self.video_path)
        config_hash = fingerprint({
            "target_language": self.settings.target_language,
            "whisper_model": self.settings.whisper_model,
            "ollama_model": self.settings.ollama_model,
            "ollama_url": self.settings.ollama_url,
            "max_chars_per_line": self.settings.max_chars_per_line,
            "max_lines": self.settings.max_lines,
        })
        state = self._load_state(input_hash, config_hash)
        audio_path = self.workdir / "audio.wav"

        if state.stage not in ("transcribed", "translated", "exported") or not audio_path.is_file():
            self._extract_audio(audio_path)
            state.audio_path = str(audio_path)
            state.stage = "audio"
            atomic_write_json(self.state_path, state.to_dict())

        if state.stage not in ("transcribed", "translated", "exported") or not state.segments:
            state.segments = self._transcribe(audio_path)
            state.stage = "transcribed"
            atomic_write_json(self.state_path, state.to_dict())

        if state.stage not in ("translated", "exported") or any(
            segment.status != "translated" for segment in state.segments
        ):
            self._translate(state.segments)
            state.stage = "translated"
            atomic_write_json(self.state_path, state.to_dict())

        srt = build_srt(
            state.segments,
            max_chars=self.settings.max_chars_per_line,
            max_lines=self.settings.max_lines,
        )
        destination = (output_path or self.video_path.with_suffix(".srt")).expanduser().resolve()
        try:
            write_srt(destination, srt)
        except (OSError, ValueError) as exc:
            raise SudoScriptError(f"Could not write SRT: {exc}") from exc

        state.stage = "exported"
        atomic_write_json(self.state_path, state.to_dict())
        report = {
            "schema_version": 1,
            "input": str(self.video_path),
            "input_sha256": input_hash,
            "output": str(destination),
            "target_language": self.settings.target_language,
            "segment_count": len(state.segments),
            "translated_count": sum(s.status == "translated" for s in state.segments),
            "failed_segments": [
                {"index": s.index, "error": s.error}
                for s in state.segments if s.status != "translated"
            ],
            "warnings": state.warnings,
        }
        atomic_write_json(destination.with_suffix(".report.json"), report)
        return destination

    def _load_state(self, input_hash: str, config_hash: str) -> JobState:
        if not self.state_path.is_file():
            return JobState(1, str(self.video_path), input_hash, config_hash)
        try:
            state = JobState.from_dict(read_json_object(self.state_path))
            if state.input_sha256 != input_hash or state.config_fingerprint != config_hash:
                log.info("Cache invalidated because input or relevant configuration changed.")
                return JobState(1, str(self.video_path), input_hash, config_hash)
            if state.input_path != str(self.video_path):
                return JobState(1, str(self.video_path), input_hash, config_hash)
            return state
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.warning("Ignoring invalid state file: %s", exc)
            return JobState(1, str(self.video_path), input_hash, config_hash)

    def _extract_audio(self, output: Path) -> None:
        temporary = output.with_name(f".{output.name}.tmp.wav")
        command = [
            self.settings.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
            "-y", "-i", str(self.video_path), "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "pcm_s16le", str(temporary),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=3600, check=False)
            if result.returncode != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
                detail = result.stderr.strip()[-1000:]
                raise SudoScriptError(f"FFmpeg audio extraction failed: {detail}")
            os.replace(temporary, output)
        except subprocess.TimeoutExpired as exc:
            raise SudoScriptError("FFmpeg audio extraction timed out.") from exc
        finally:
            temporary.unlink(missing_ok=True)

    def _transcribe(self, audio_path: Path) -> list[Segment]:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise SudoScriptError("faster-whisper is missing. Install the project dependencies.") from exc
        try:
            model = WhisperModel(self.settings.whisper_model, device="auto", compute_type="default")
            raw_segments, _info = model.transcribe(str(audio_path), vad_filter=True)
            result: list[Segment] = []
            for item in raw_segments:
                text = str(item.text).strip()
                start, end = float(item.start), float(item.end)
                if text and start >= 0 and end > start:
                    result.append(Segment(len(result), start, end, text))
            if not result:
                raise SudoScriptError("No speech segments were detected.")
            return result
        except SudoScriptError:
            raise
        except Exception as exc:
            raise SudoScriptError(f"Transcription failed: {exc}") from exc

    def _translate(self, segments: list[Segment]) -> None:
        for segment in segments:
            if segment.status == "translated" and segment.translated_text:
                continue
            payload: dict[str, object] = {
                "model": self.settings.ollama_model,
                "stream": False,
                "messages": [{
                    "role": "user",
                    "content": (
                        f"Translate the spoken dialogue into {self.settings.target_language}. "
                        "Preserve meaning, tone and names. Return only the translation, without "
                        "quotes, commentary or markdown.\n\nSource dialogue:\n" + segment.source_text
                    ),
                }],
                "options": {"temperature": 0.1},
            }
            try:
                response = requests.post(
                    self.settings.ollama_url.rstrip("/") + "/api/chat",
                    json=payload,
                    timeout=self.settings.request_timeout_s,
                )
                response.raise_for_status()
                data = response.json()
                translated = data.get("message", {}).get("content")
                if not isinstance(translated, str) or not translated.strip():
                    raise ValueError("empty or malformed model response")
                segment.translated_text = translated.strip()
                segment.status = "translated"
                segment.error = None
            except (requests.RequestException, ValueError, TypeError) as exc:
                segment.translated_text = None
                segment.status = "failed"
                segment.error = str(exc)[:500]
                log.error("Translation failed for segment %d: %s", segment.index, exc)
        if any(segment.status != "translated" for segment in segments):
            raise SudoScriptError(
                "One or more segments failed translation. State was saved for retry; "
                "no incomplete SRT was exported."
            )
