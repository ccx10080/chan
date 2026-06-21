import pytest
from chanlun.models import Segment
from chanlun.beichi import BeichiDetector


def test_up_beichi_detected():
    segments = [
        Segment(start=0, end=20, direction="up", bis=[]),
        Segment(start=20, end=25, direction="down", bis=[]),
        Segment(start=25, end=35, direction="up", bis=[]),
    ]
    detector = BeichiDetector(segments)
    result = detector.detect()
    assert result is not None
    assert "up" in result


def test_no_beichi():
    segments = [
        Segment(start=0, end=10, direction="up", bis=[]),
        Segment(start=10, end=15, direction="down", bis=[]),
        Segment(start=15, end=28, direction="up", bis=[]),
    ]
    detector = BeichiDetector(segments)
    assert detector.detect() is None


def test_insufficient_segments():
    segments = [Segment(start=0, end=10, direction="up", bis=[])]
    detector = BeichiDetector(segments)
    assert detector.detect() is None
