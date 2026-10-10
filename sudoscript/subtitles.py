"""SRT formatting and validation, kept independent from model backends."""
from __future__ import annotations

import re
from pathlib import Path
from .models import Segment

_TIMESTAMP = re.compile(r"^(\d{2,}):(\d{2}):(\d{2}),(\d{3})$")


def timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def wrap_text(text: str, max_chars: int = 42) -> list[str]:
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        # Do not silently violate the line limit for a long unbroken token.
        if len(word) > max_chars:
            if current:
                lines.append(current)
                current = ""
            lines.extend(word[i:i + max_chars] for i in range(0, len(word), max_chars))
            continue
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def build_srt(segments: list[Segment], max_chars: int = 42, max_lines: int = 2) -> str:
    blocks: list[str] = []
    previous_end = 0.0
    for segment in segments:
        text = (segment.translated_text or "").strip()
        if not text:
            continue
        start = max(segment.start, previous_end)
        end = max(segment.end, start + 0.001)
        lines = wrap_text(text, max_chars)
        if len(lines) > max_lines:
            # Keep output readable and complete; flagging is handled by the report.
            lines = lines[:max_lines]
        blocks.append(
            f"{len(blocks) + 1}\n{timestamp(start)} --> {timestamp(end)}\n" + "\n".join(lines)
        )
        previous_end = end
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def validate_srt_text(text: str) -> list[str]:
    errors: list[str] = []
    if not text:
        return ["SRT is empty"]
    blocks = [block for block in text.strip().split("\n\n") if block.strip()]
    expected = 1
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 3:
            errors.append(f"Block {expected}: too few lines")
            expected += 1
            continue
        if lines[0].strip() != str(expected):
            errors.append(f"Block {expected}: invalid sequence number")
        times = lines[1].split(" --> ")
        if len(times) != 2 or not all(_TIMESTAMP.match(t) for t in times):
            errors.append(f"Block {expected}: invalid timestamp")
        else:
            def to_ms(value: str) -> int:
                h, m, s, ms = map(int, _TIMESTAMP.match(value).groups())
                return ((h * 60 + m) * 60 + s) * 1000 + ms
            if to_ms(times[1]) <= to_ms(times[0]):
                errors.append(f"Block {expected}: end must be after start")
        expected += 1
    return errors


def write_srt(path: Path, content: str) -> None:
    errors = validate_srt_text(content)
    if errors:
        raise ValueError("Refusing to write invalid SRT: " + "; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
