"""Unit tests for data structures and their JSON round trips."""

from utils.schema import RenderedEvent, Segment, Transcript, WorkMode


def make_transcript() -> Transcript:
    return Transcript(
        language="en",
        segments=[
            Segment(
                index=0,
                start_s=1.5,
                end_s=3.25,
                source_text="Hello world.",
                translated_text="Witaj świecie.",
                frame_path="/tmp/seg_00000.jpg",
            ),
            Segment(index=1, start_s=4.0, end_s=6.0, source_text="Second line."),
        ],
    )


def test_transcript_json_round_trip():
    transcript = make_transcript()
    restored = Transcript.from_json(transcript.to_json())
    assert restored.language == "en"
    assert len(restored.segments) == 2
    original, second = restored.segments
    assert original.index == 0
    assert original.start_s == 1.5
    assert original.translated_text == "Witaj świecie."
    assert original.frame_path == "/tmp/seg_00000.jpg"
    assert second.translated_text is None


def test_segment_properties():
    segment = Segment(index=0, start_s=1.0, end_s=5.0, source_text="x")
    assert segment.duration_s == 4.0
    assert segment.midpoint_s == 3.0


def test_rendered_event_metrics():
    event = RenderedEvent(start_s=0.0, end_s=2.0, lines=["abc", "defg"])
    assert event.char_count == 7
    assert event.chars_per_second == 3.5
    assert event.text == "abc defg"


def test_work_mode_values():
    assert WorkMode("subtitles") is WorkMode.SUBTITLES
    assert WorkMode("voiceover") is WorkMode.VOICEOVER
