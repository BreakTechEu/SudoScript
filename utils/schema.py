"""Shared data structures for the SudoScript pipeline.

The pipeline passes data between steps through plain, JSON-serialisable
dataclasses so that any intermediate result can be cached to disk and the
pipeline can be resumed from an arbitrary step without recompute.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkMode(str, Enum):
    """What kind of text track the pipeline should produce."""

    SUBTITLES = "subtitles"
    VOICEOVER = "voiceover"
    DUBBING = "dubbing"


class OutputFormat(str, Enum):
    """Container formats supported by the export step."""

    SRT = "srt"
    ASS = "ass"
    JSON = "json"
    CSV = "csv"


@dataclass
class Segment:
    """One spoken utterance, from transcription through translation."""

    index: int
    start_s: float
    end_s: float
    source_text: str
    translated_text: str | None = None
    frame_path: str | None = None  # sampled still frame for the VLM

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    @property
    def midpoint_s(self) -> float:
        return (self.start_s + self.end_s) / 2.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "source_text": self.source_text,
            "translated_text": self.translated_text,
            "frame_path": self.frame_path,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Segment:
        return cls(
            index=int(raw["index"]),
            start_s=float(raw["start_s"]),
            end_s=float(raw["end_s"]),
            source_text=str(raw.get("source_text", "")),
            translated_text=raw.get("translated_text"),
            frame_path=raw.get("frame_path"),
        )


@dataclass
class Transcript:
    """Full transcription result for a single video."""

    language: str | None = None
    segments: list[Segment] = field(default_factory=list)

    def to_json(self) -> str:
        payload = {
            "language": self.language,
            "segments": [segment.to_dict() for segment in self.segments],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> Transcript:
        data = json.loads(raw)
        return cls(
            language=data.get("language"),
            segments=[Segment.from_dict(item) for item in data.get("segments", [])],
        )


@dataclass
class RenderedEvent:
    """A single subtitle event after timing and text layout."""

    start_s: float
    end_s: float
    lines: list[str]

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    @property
    def text(self) -> str:
        return " ".join(self.lines)

    @property
    def char_count(self) -> int:
        return sum(len(line) for line in self.lines)

    @property
    def chars_per_second(self) -> float:
        if self.duration_s <= 0:
            return float("inf")
        return self.char_count / self.duration_s
