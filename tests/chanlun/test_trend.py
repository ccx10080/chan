import pytest
from chanlun.models import Segment
from chanlun.trend import TrendAnalyzer


def test_up_trend():
    segments = [Segment(start=i*10, end=i*10+9, direction="up", bis=[]) for i in range(4)]
    segments[1] = Segment(start=10, end=19, direction="down", bis=[])
    analyzer = TrendAnalyzer(segments)
    assert analyzer.analyze() == "盘整"


def test_sideways_trend():
    segments = [
        Segment(start=0, end=10, direction="up", bis=[]),
        Segment(start=10, end=20, direction="down", bis=[]),
        Segment(start=20, end=30, direction="up", bis=[]),
        Segment(start=30, end=40, direction="down", bis=[]),
    ]
    analyzer = TrendAnalyzer(segments)
    assert analyzer.analyze() == "盘整"


def test_insufficient_segments():
    analyzer = TrendAnalyzer([Segment(start=0, end=10, direction="up", bis=[])])
    assert analyzer.analyze() == "盘整"
