import pytest
from chanlun.models import Bi
from chanlun.segment import SegmentAnalyzer


def test_one_segment_from_three_bis():
    bis = [
        Bi(start=1, end=5, direction="up"),
        Bi(start=5, end=10, direction="down"),
        Bi(start=10, end=15, direction="up"),
    ]
    analyzer = SegmentAnalyzer(bis)
    segments = analyzer.build_segments()
    assert len(segments) == 1
    assert segments[0].start == 1
    assert segments[0].end == 15


def test_no_segment_insufficient_bis():
    bis = [Bi(start=0, end=5, direction="up"), Bi(start=5, end=10, direction="down")]
    analyzer = SegmentAnalyzer(bis)
    assert analyzer.build_segments() == []


def test_two_segments_six_bis():
    bis = [
        Bi(start=1, end=5, direction="up"),
        Bi(start=5, end=10, direction="down"),
        Bi(start=10, end=15, direction="up"),
        Bi(start=15, end=20, direction="down"),
        Bi(start=20, end=25, direction="up"),
        Bi(start=25, end=30, direction="down"),
    ]
    analyzer = SegmentAnalyzer(bis)
    segments = analyzer.build_segments()
    assert len(segments) == 2
    assert segments[0].start == 1 and segments[0].end == 15
    assert segments[1].start == 15 and segments[1].end == 30


def test_segment_bis_reference():
    bis = [
        Bi(start=1, end=5, direction="down"),
        Bi(start=5, end=10, direction="up"),
        Bi(start=10, end=15, direction="down"),
    ]
    analyzer = SegmentAnalyzer(bis)
    segments = analyzer.build_segments()
    assert len(segments[0].bis) == 3
    assert segments[0].direction == "down"
