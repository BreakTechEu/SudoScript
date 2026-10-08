"""Unit tests for subtitle text layout (CPL and line-count rules)."""

import pytest

from config import SubtitleRules
from core.formatters.subtitle import (
    SubtitleTooLongError,
    layout_lines,
    split_text,
    wrap_greedy,
)


@pytest.fixture()
def rules():
    return SubtitleRules(max_chars_per_line=42, max_lines=2)


def test_short_text_fits_one_line(rules):
    assert layout_lines("Hello there.", rules) == ["Hello there."]


def test_long_text_breaks_into_two_balanced_lines(rules):
    text = "A moderately long line that wraps into two balanced lines."
    lines = layout_lines(text, rules)
    assert len(lines) == 2
    assert all(len(line) <= rules.max_chars_per_line for line in lines)
    # balanced: line lengths differ by at most 10 characters
    assert abs(len(lines[0]) - len(lines[1])) <= 10


def test_oversized_text_raises(rules):
    text = " ".join(["word"] * 40)  # far beyond 2 x 42 characters
    with pytest.raises(SubtitleTooLongError):
        layout_lines(text, rules)


def test_wrap_greedy_respects_cpl(rules):
    text = " ".join(["counterintuitively"] * 6)
    lines = wrap_greedy(text, rules.max_chars_per_line)
    assert all(len(line) <= rules.max_chars_per_line for line in lines)


def test_split_text_chunks_fit_rules(rules):
    text = " ".join(["meaningfulness"] * 30)
    chunks = split_text(text, rules)
    assert len(chunks) > 1
    for chunk in chunks:
        lines = layout_lines(chunk, rules)  # must not raise
        assert len(" ".join(lines)) == len(chunk)


def test_single_word_longer_than_cpl_stays_intact(rules):
    lines = layout_lines("extraordinarilylongword" * 3, rules)
    assert lines  # never dropped, wrapped as its own line
