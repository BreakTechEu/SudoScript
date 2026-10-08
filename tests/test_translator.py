"""Unit tests for VLM response parsing and prompt building."""

import pytest

from core.translator import (
    TranslationError,
    build_prompt,
    parse_translation,
)
from utils.schema import WorkMode


def test_parse_clean_json():
    assert (
        parse_translation('{"translation": "Cześć wszystkim."}') == "Cześć wszystkim."
    )


def test_parse_fenced_json():
    raw = '```json\n{"translation": "Fenced."}\n```'
    assert parse_translation(raw) == "Fenced."


def test_parse_json_with_surrounding_prose():
    raw = 'Sure! Here is the result: {"translation": "Prose around."} Hope it helps.'
    assert parse_translation(raw) == "Prose around."


def test_parse_plain_text_fallback():
    assert parse_translation("Just a plain translation.") == "Just a plain translation."


def test_parse_empty_raises():
    with pytest.raises(TranslationError):
        parse_translation("   ")


def test_parse_unexpected_json_shape_raises():
    with pytest.raises(TranslationError):
        parse_translation('{"summary": "no translation key"}')


def test_prompt_contains_mode_guidelines():
    prompt = build_prompt("hello", WorkMode.SUBTITLES, "Polish")
    assert "subtitle" in prompt.lower()
    assert "Polish" in prompt
    assert "Transcript line: hello" in prompt
    assert '"translation"' in prompt


def test_prompt_differs_between_modes():
    subtitles = build_prompt("hello", WorkMode.SUBTITLES, "Polish")
    dubbing = build_prompt("hello", WorkMode.DUBBING, "Polish")
    assert subtitles != dubbing
