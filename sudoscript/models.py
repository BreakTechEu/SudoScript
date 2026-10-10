"""Typed data structures used across pipeline stages."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Segment:
    index: int
    start: float
    end: float
    source_text: str
    translated_text: str | None = None
    frame_path: str | None = None
    status: str = "transcribed"
    error: str | None = None

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Segment":
        return cls(
            index=int(value["index"]),
            start=float(value["start"]),
            end=float(value["end"]),
            source_text=str(value["source_text"]),
            translated_text=value.get("translated_text"),
            frame_path=value.get("frame_path"),
            status=str(value.get("status", "transcribed")),
            error=value.get("error"),
        )


@dataclass
class JobState:
    schema_version: int
    input_path: str
    input_sha256: str
    config_fingerprint: str
    stage: str = "new"
    audio_path: str | None = None
    segments: list[Segment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "input_path": self.input_path,
            "input_sha256": self.input_sha256,
            "config_fingerprint": self.config_fingerprint,
            "stage": self.stage,
            "audio_path": self.audio_path,
            "segments": [segment.to_dict() for segment in self.segments],
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "JobState":
        if not isinstance(value, dict):
            raise ValueError("Job state must be a JSON object")
        if value.get("schema_version") != 1:
            raise ValueError("Unsupported job-state schema version")
        segments = value.get("segments", [])
        warnings = value.get("warnings", [])
        if not isinstance(segments, list) or not isinstance(warnings, list):
            raise ValueError("Invalid job-state collections")
        return cls(
            schema_version=1,
            input_path=str(value["input_path"]),
            input_sha256=str(value["input_sha256"]),
            config_fingerprint=str(value["config_fingerprint"]),
            stage=str(value.get("stage", "new")),
            audio_path=value.get("audio_path"),
            segments=[Segment.from_dict(item) for item in segments],
            warnings=[str(item) for item in warnings],
        )
