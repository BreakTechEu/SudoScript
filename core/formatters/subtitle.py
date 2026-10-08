"""Subtitle formatting: text layout, timing norms and SRT/ASS export.

This is where the technical quality promises of SudoScript are enforced:

* CPL  - each line stays within the configured character limit
* LINES- events use at most `max_lines` lines
* CPS  - reading speed is checked; slow events are extended in time when
         the neighbouring events allow it
* CUTS - an event never stays on screen across a scene cut: its end is
         pulled back before the cut, or its start is pushed earlier
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING

from config import SubtitleRules
from utils.errors import SudoScriptError
from utils.schema import RenderedEvent, Segment

if TYPE_CHECKING:  # pragma: no cover - only for static analysis
    import pysubs2

logger = logging.getLogger(__name__)


class SubtitleTooLongError(SudoScriptError):
    """Internal: text does not fit max_lines at the configured CPL."""


class FormattingError(SudoScriptError):
    """Raised when the subtitle file cannot be written."""


# ----------------------------------------------------------------------
# text layout
# ----------------------------------------------------------------------


def wrap_greedy(text: str, max_chars_per_line: int) -> list[str]:
    """Greedy word wrap into lines of at most *max_chars_per_line* chars."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars_per_line or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def balance_two_lines(text: str, max_chars_per_line: int) -> list[str] | None:
    """Split *text* into two lines of balanced length, or None if it fits one."""
    words = text.split()
    if len(" ".join(words)) <= max_chars_per_line:
        return None
    best: list[str] | None = None
    best_diff = math.inf
    for split_at in range(1, len(words)):
        first = " ".join(words[:split_at])
        second = " ".join(words[split_at:])
        if len(first) > max_chars_per_line or len(second) > max_chars_per_line:
            continue
        diff = abs(len(first) - len(second))
        if diff < best_diff:
            best_diff = diff
            best = [first, second]
    return best


def layout_lines(text: str, rules: SubtitleRules) -> list[str]:
    """Lay out *text* into at most rules.max_lines lines.

    Raises SubtitleTooLongError when the text cannot fit; the caller then
    splits the event instead of producing an oversized subtitle.
    """
    if not text:
        return [""]
    if rules.max_lines == 1:
        lines = wrap_greedy(text, rules.max_chars_per_line)
        if len(lines) > 1:
            raise SubtitleTooLongError(text)
        return lines

    balanced = balance_two_lines(text, rules.max_chars_per_line)
    if balanced is not None:
        return balanced
    lines = wrap_greedy(text, rules.max_chars_per_line)
    if len(lines) <= rules.max_lines:
        return lines
    raise SubtitleTooLongError(text)


def split_text(text: str, rules: SubtitleRules) -> list[str]:
    """Split an over-long text into chunks that each fit within the limits.

    A chunk is accepted only when it can actually be laid out within
    max_lines at max_chars_per_line, so the caller never receives an
    impossible subtitle. Chunks stay as full as possible so a long
    utterance becomes a short sequence of legal events.
    """
    chunks: list[str] = []
    current: list[str] = []
    for word in text.split():
        candidate = current + [word]
        try:
            layout_lines(" ".join(candidate), rules)
        except SubtitleTooLongError:
            if current:
                chunks.append(" ".join(current))
            current = [word]
        else:
            current = candidate
    if current:
        chunks.append(" ".join(current))
    return chunks


def build_events(segments: list[Segment], rules: SubtitleRules) -> list[RenderedEvent]:
    """Turn translated segments into rendered subtitle events.

    Over-long lines are split into several events with timing divided
    proportionally to chunk length. Untranslated segments fall back to
    their source text so the output is always complete.
    """
    events: list[RenderedEvent] = []
    for segment in segments:
        text = (segment.translated_text or segment.source_text).strip()
        if not text:
            continue
        duration = max(segment.duration_s, 0.001)
        try:
            lines = layout_lines(text, rules)
            events.append(
                RenderedEvent(
                    start_s=segment.start_s,
                    end_s=segment.end_s,
                    lines=lines,
                )
            )
            continue
        except SubtitleTooLongError:
            chunks = split_text(text, rules)
            total_chars = sum(len(chunk) for chunk in chunks)
            start = segment.start_s
            for chunk in chunks:
                share = len(chunk) / max(total_chars, 1)
                span = duration * share
                events.append(
                    RenderedEvent(
                        start_s=start,
                        end_s=min(start + span, segment.end_s),
                        lines=layout_lines(chunk, rules),
                    )
                )
                start += span
    return events


# ----------------------------------------------------------------------
# timing constraints
# ----------------------------------------------------------------------


def enforce_durations(
    events: list[RenderedEvent], rules: SubtitleRules
) -> list[RenderedEvent]:
    """Apply min/max duration and CPS norms (in place and returned).

    Events are processed front to back; each event may extend its end
    time only up to (next event start - gap). Events that cannot be
    fixed in time are kept with a warning rather than dropped.
    """
    for position, event in enumerate(events):
        next_start = (
            events[position + 1].start_s if position + 1 < len(events) else math.inf
        )
        # an event may grow into the silence before the next event, but
        # never closer to it than min_gap_s
        latest_end = next_start - rules.min_gap_s
        needed = event.char_count / rules.max_chars_per_second
        target_end = event.start_s + max(needed, rules.min_duration_s)
        new_end = min(target_end, latest_end)
        event.end_s = max(event.end_s, new_end)
        if event.duration_s > rules.max_duration_s:
            event.end_s = event.start_s + rules.max_duration_s
            logger.debug(
                "Event trimmed to max duration at %.2fs.",
                event.start_s,
            )
        if event.chars_per_second > rules.max_chars_per_second:
            logger.warning(
                "Event at %.2fs exceeds CPS %.1f (actual %.1f) and cannot "
                "be extended - the text is too long for its slot.",
                event.start_s,
                rules.max_chars_per_second,
                event.chars_per_second,
            )
    return events


def avoid_scene_cuts(
    events: list[RenderedEvent],
    cuts: list[float],
    rules: SubtitleRules,
) -> list[RenderedEvent]:
    """Pull event ends back before scene cuts, never crossing a cut.

    When pulling back makes the event shorter than min_duration_s, its
    start is shifted earlier instead (without colliding with the
    previous event or an earlier cut). Unsatisfiable events keep their
    original timing with a warning - a slightly imperfect subtitle is
    better than a missing one.
    """
    if not cuts:
        return events
    cut_list = sorted(cuts)

    def first_cut_inside(start: float, end: float) -> float | None:
        for cut in cut_list:
            if start + rules.cut_clearance_s < cut < end - rules.cut_clearance_s:
                return cut
            if cut >= end:
                break
        return None

    for position, event in enumerate(events):
        cut = first_cut_inside(event.start_s, event.end_s)
        if cut is None:
            continue
        trimmed_end = cut - rules.cut_clearance_s
        if trimmed_end - event.start_s >= rules.min_duration_s:
            event.end_s = trimmed_end
            continue

        previous_end = events[position - 1].end_s if position > 0 else 0.0
        earliest_start = max(previous_end + rules.min_gap_s, 0.0)
        last_cut_before = None
        for earlier in cut_list:
            if earlier <= event.start_s:
                last_cut_before = earlier
        if last_cut_before is not None:
            earliest_start = max(
                earliest_start, last_cut_before + rules.cut_clearance_s
            )
        needed_start = trimmed_end - rules.min_duration_s
        if needed_start >= earliest_start:
            event.start_s = needed_start
            event.end_s = trimmed_end
        else:
            logger.warning(
                "Event at %.2fs crosses a scene cut and cannot be fixed "
                "(no room to pull back or shift); keeping original timing.",
                event.start_s,
            )
    return events


# ----------------------------------------------------------------------
# export
# ----------------------------------------------------------------------


def to_ssa_file(events: list[RenderedEvent]) -> pysubs2.SSAFile:
    """Build a pysubs2 SSAFile from rendered events."""
    import pysubs2  # imported lazily: layout/timing logic stays testable

    subs = pysubs2.SSAFile()
    for event in events:
        subs.events.append(
            pysubs2.SSAEvent(
                start=pysubs2.make_time(ms=round(event.start_s * 1000)),
                end=pysubs2.make_time(ms=round(event.end_s * 1000)),
                text="\\N".join(event.lines),
            )
        )
    return subs


def export(events: list[RenderedEvent], output_path: str | Path) -> Path:
    """Write the subtitle file; the container format follows the suffix."""
    output = Path(output_path)
    if output.suffix.lower() not in (".srt", ".ass"):
        raise FormattingError(
            f"Unsupported subtitle container '{output.suffix}'. Use .srt or .ass."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        to_ssa_file(events).save(str(output))
    except (OSError, ValueError) as exc:
        raise FormattingError(f"Could not write '{output}': {exc}") from exc
    logger.info("Subtitles written to %s (%d events).", output, len(events))
    return output
