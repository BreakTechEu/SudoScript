"""SRT formatting and validation, independent from model backends."""
from __future__ import annotations

import re
import tempfile
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
    if max_lines < 1:
        raise ValueError("max_lines must be positive")
    blocks: list[str] = []
    previous_end = 0.0
    for segment in segments:
        text = (segment.translated_text or "").strip()
        if not text:
            continue
        start = max(segment.start, previous_end, 0.0)
        end = max(segment.end, start + 0.001)
        lines = wrap_text(text, max_chars)
        groups = [lines[i:i + max_lines] for i in range(0, len(lines), max_lines)]
        if not groups:
            continue
        weights = [max(1, sum(len(line) for line in group)) for group in groups]
        total_weight = sum(weights)
        duration = end - start
        cursor = start
        elapsed_weight = 0
        for index, group in enumerate(groups):
            elapsed_weight += weights[index]
            group_end = end if index == len(groups) - 1 else start + duration * elapsed_weight / total_weight
            group_end = max(group_end, cursor + 0.001)
            blocks.append(
                f"{len(blocks) + 1}\n{timestamp(cursor)} --> {timestamp(group_end)}\n"
                + "\n".join(group)
            )
            cursor = group_end
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
                match = _TIMESTAMP.match(value)
                assert match is not None
                h, m, s, ms = map(int, match.groups())
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
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with open(fd, "w", encoding="utf-8", newline="\n", closefd=True) as handle:
            handle.write(content)
            handle.flush()
            import os
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
