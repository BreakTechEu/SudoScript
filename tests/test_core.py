from pathlib import Path

import pytest

from sudoscript.cache import fingerprint
from sudoscript.models import JobState, Segment
from sudoscript.pipeline import Settings, SudoScriptError
from sudoscript.subtitles import build_srt, timestamp, validate_srt_text, wrap_text


def test_timestamp_rounds_and_carries():
    assert timestamp(59.9996) == "00:01:00,000"


def test_wrap_text_never_exceeds_limit_even_for_long_token():
    lines = wrap_text("abcde extraordinarilylongword xyz", max_chars=8)
    assert all(len(line) <= 8 for line in lines)
    assert "".join(lines).replace(" ", "").startswith("abcde")


def test_build_srt_uses_only_successfully_translated_segments():
    segments = [
        Segment(0, 0, 1, "hello", "cześć", status="translated"),
        Segment(1, 1, 2, "failed", None, status="failed"),
    ]
    content = build_srt(segments)
    assert "cześć" in content
    assert "failed" not in content
    assert validate_srt_text(content) == []


def test_empty_srt_is_invalid():
    assert validate_srt_text("") == ["SRT is empty"]


def test_state_round_trip_and_null_rejection():
    state = JobState(1, "/video.mp4", "hash", "config", segments=[
        Segment(0, 0.0, 1.0, "hello", "cześć", status="translated")
    ])
    restored = JobState.from_dict(state.to_dict())
    assert restored.segments[0].translated_text == "cześć"
    with pytest.raises(ValueError):
        JobState.from_dict(None)  # type: ignore[arg-type]


def test_fingerprint_is_key_order_independent():
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})


def test_remote_backend_rejected_by_default():
    with pytest.raises(SudoScriptError, match="Remote Ollama"):
        Settings(ollama_url="https://example.com").validate()


def test_bad_layout_settings_rejected():
    with pytest.raises(SudoScriptError, match="layout"):
        Settings(max_chars_per_line=3).validate()
