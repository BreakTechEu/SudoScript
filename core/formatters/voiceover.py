"""AI-voiceover script export (phase 2 groundwork).

SudoScript itself never synthesises audio. This module prepares a
structured script (JSON or CSV) with exact timings and an estimated
reading duration per line, so an external offline TTS tool can generate
the narration track.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from config import VoiceoverSettings
from utils.errors import SudoScriptError
from utils.schema import Segment

logger = logging.getLogger(__name__)


class VoiceoverExportError(SudoScriptError):
    """Raised when the voiceover script cannot be written."""


def _rows(segments: list[Segment], settings: VoiceoverSettings) -> list[dict]:
    rows = []
    for segment in segments:
        text = (segment.translated_text or segment.source_text).strip()
        if not text:
            continue
        rows.append(
            {
                "index": segment.index,
                "start_s": round(segment.start_s, 3),
                "end_s": round(segment.end_s, 3),
                "text": text,
                "estimated_reading_s": round(len(text) / settings.reading_rate_cps, 3),
            }
        )
    return rows


def export_json(
    segments: list[Segment],
    output_path: str | Path,
    language: str | None,
    settings: VoiceoverSettings,
) -> Path:
    """Write a JSON voiceover script with per-line timing metadata."""
    output = Path(output_path)
    payload = {
        "mode": "voiceover",
        "language": language,
        "reading_rate_cps": settings.reading_rate_cps,
        "segments": _rows(segments, settings),
    }
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        raise VoiceoverExportError(f"Could not write '{output}': {exc}") from exc
    logger.info(
        "Voiceover script written to %s (%d lines).", output, len(payload["segments"])
    )
    return output


def export_csv(
    segments: list[Segment],
    output_path: str | Path,
    settings: VoiceoverSettings,
) -> Path:
    """Write a CSV voiceover script for spreadsheet-driven TTS workflows."""
    output = Path(output_path)
    rows = _rows(segments, settings)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["index", "start_s", "end_s", "text", "estimated_reading_s"],
            )
            writer.writeheader()
            writer.writerows(rows)
    except OSError as exc:
        raise VoiceoverExportError(f"Could not write '{output}': {exc}") from exc
    logger.info("Voiceover CSV written to %s (%d lines).", output, len(rows))
    return output
