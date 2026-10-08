"""AI-dubbing script export (phase 2 groundwork, experimental).

The dubbing mode produces a structured script where every line carries
the target phonetic length derived from the source utterance, so an
external offline TTS/voice-cloning tool can generate audio that matches
the original speaking time and, ultimately, the lip movement.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from utils.errors import SudoScriptError
from utils.schema import Segment

logger = logging.getLogger(__name__)

#: Allowed relative deviation of the translated line length from the
#: source line length, expressed as a fraction of the source length.
_LENGTH_TOLERANCE = 0.15


class DubbingExportError(SudoScriptError):
    """Raised when the dubbing script cannot be written."""


def _rows(segments: list[Segment]) -> list[dict]:
    rows = []
    for segment in segments:
        text = (segment.translated_text or segment.source_text).strip()
        if not text:
            continue
        source_len = len(segment.source_text)
        tolerance = max(1, round(source_len * _LENGTH_TOLERANCE))
        rows.append(
            {
                "index": segment.index,
                "start_s": round(segment.start_s, 3),
                "end_s": round(segment.end_s, 3),
                "text": text,
                "target_char_count": source_len,
                "char_count_tolerance": tolerance,
                "length_ok": abs(len(text) - source_len) <= tolerance,
            }
        )
    return rows


def export_json(segments: list[Segment], output_path: str | Path) -> Path:
    """Write a JSON dubbing script with length targets per line."""
    output = Path(output_path)
    rows = _rows(segments)
    payload = {
        "mode": "dubbing",
        "experimental": True,
        "segments": rows,
    }
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        raise DubbingExportError(f"Could not write '{output}': {exc}") from exc
    mismatched = sum(1 for row in rows if not row["length_ok"])
    if mismatched:
        logger.warning(
            "%d of %d dubbing lines exceed the length tolerance; "
            "consider re-running with a stricter dubbing prompt.",
            mismatched,
            len(rows),
        )
    logger.info("Dubbing script written to %s (%d lines).", output, len(rows))
    return output
