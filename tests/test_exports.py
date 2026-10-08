"""Unit tests for the voiceover and dubbing script exporters."""

import json

import pytest

from config import VoiceoverSettings
from core.formatters import dubbing as dubbing_fmt
from core.formatters import voiceover as voiceover_fmt
from utils.errors import SudoScriptError
from utils.schema import Segment


@pytest.fixture()
def segments():
    return [
        Segment(
            index=0,
            start_s=0.0,
            end_s=2.0,
            source_text="original text",
            translated_text="przetłumaczony tekst",
        ),
        Segment(index=1, start_s=2.5, end_s=4.0, source_text="fallback line"),
    ]


def test_voiceover_json_contains_reading_estimate(tmp_path, segments):
    output = tmp_path / "voiceover.json"
    voiceover_fmt.export_json(
        segments,
        output,
        language="en",
        settings=VoiceoverSettings(reading_rate_cps=10.0),
    )
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["mode"] == "voiceover"
    first = data["segments"][0]
    assert first["text"] == "przetłumaczony tekst"
    assert first["estimated_reading_s"] == pytest.approx(2.0)


def test_voiceover_csv_writes_rows(tmp_path, segments):
    output = tmp_path / "voiceover.csv"
    voiceover_fmt.export_csv(segments, output, VoiceoverSettings())
    content = output.read_text(encoding="utf-8")
    assert "index,start_s,end_s,text,estimated_reading_s" in content
    assert "przetłumaczony tekst" in content


def test_dubbing_json_flags_length_mismatch(tmp_path, segments):
    output = tmp_path / "dubbing.json"
    dubbing_fmt.export_json(segments, output)
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["experimental"] is True
    second = data["segments"][1]
    # "fallback line" is kept as-is; length vs "przetłumaczony tekst" differs
    assert "target_char_count" in second
    assert "length_ok" in second


def test_voiceover_export_error_on_unwritable_path(segments):
    with pytest.raises(SudoScriptError):
        voiceover_fmt.export_json(
            segments, "/proc/definitely-not-writable/vo.json", None, VoiceoverSettings()
        )
