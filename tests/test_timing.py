"""Unit tests for timing constraints (durations, CPS, scene cuts)."""

import pytest

from config import SubtitleRules
from core.formatters.subtitle import avoid_scene_cuts, build_events, enforce_durations
from utils.schema import RenderedEvent, Segment


def make_rules() -> SubtitleRules:
    return SubtitleRules(
        max_chars_per_line=42,
        max_lines=2,
        max_chars_per_second=17.0,
        min_duration_s=1.0,
        max_duration_s=7.0,
        min_gap_s=0.1,
        cut_clearance_s=0.08,
    )


def event(start: float, end: float, text: str = "Short line.") -> RenderedEvent:
    return RenderedEvent(start_s=start, end_s=end, lines=[text])


class TestEnforceDurations:
    def test_short_event_is_extended(self):
        rules = make_rules()
        events = enforce_durations([event(1.0, 1.2)], rules)
        assert events[0].duration_s == pytest.approx(rules.min_duration_s)

    def test_extension_respects_next_event_gap(self):
        rules = make_rules()
        events = enforce_durations([event(1.0, 1.2), event(1.5, 3.0)], rules)
        assert events[0].end_s <= events[1].start_s - rules.min_gap_s

    def test_too_fast_event_extends_to_reach_cps(self):
        rules = make_rules()
        text = "A" * 34  # needs 2 seconds at 17 cps
        events = enforce_durations([event(0.0, 1.0, text)], rules)
        assert events[0].duration_s >= 2.0

    def test_overlong_event_is_trimmed(self):
        rules = make_rules()
        events = enforce_durations([event(0.0, 12.0)], rules)
        assert events[0].duration_s == pytest.approx(rules.max_duration_s)


class TestAvoidSceneCuts:
    def test_event_crossing_cut_is_trimmed(self):
        rules = make_rules()
        events = [event(1.0, 5.0)]
        adjusted = avoid_scene_cuts(events, [3.0], rules)
        assert adjusted[0].end_s <= 3.0 - rules.cut_clearance_s
        assert adjusted[0].duration_s >= rules.min_duration_s

    def test_trimmed_short_event_shifts_start(self):
        rules = make_rules()
        # cut 0.3s after start: trimming would leave 0.3s < min duration
        events = [event(1.0, 5.0)]
        adjusted = avoid_scene_cuts(events, [1.3], rules)
        assert adjusted[0].end_s <= 1.3 - rules.cut_clearance_s
        assert adjusted[0].duration_s >= rules.min_duration_s

    def test_event_between_cuts_is_untouched(self):
        rules = make_rules()
        events = [event(1.0, 4.9)]
        adjusted = avoid_scene_cuts(events, [5.5, 8.0], rules)
        assert adjusted[0].end_s == 4.9

    def test_shift_does_not_collide_with_previous_event(self):
        rules = make_rules()
        events = [event(0.0, 3.0), event(3.1, 6.0)]
        adjusted = avoid_scene_cuts(events, [3.4], rules)
        assert adjusted[1].start_s >= adjusted[0].end_s + rules.min_gap_s


class TestBuildEvents:
    def test_long_translated_text_is_split_proportionally(self):
        rules = make_rules()
        segment = Segment(
            index=0,
            start_s=0.0,
            end_s=8.0,
            source_text="original",
            translated_text=" ".join(["długie"] * 30),
        )
        events = build_events([segment], rules)
        assert len(events) > 1
        # chunks tile the original time span without gaps or overlaps
        import itertools

        for previous, current in itertools.pairwise(events):
            assert current.start_s == pytest.approx(previous.end_s)
        assert events[-1].end_s <= segment.end_s

    def test_untranslated_segment_falls_back_to_source(self):
        rules = make_rules()
        segment = Segment(index=0, start_s=0.0, end_s=2.0, source_text="kept as is")
        events = build_events([segment], rules)
        assert events[0].text == "kept as is"
