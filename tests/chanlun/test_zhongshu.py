import pytest
from chanlun.models import Segment
from chanlun.zhongshu import ZhongshuDetector


def test_up_down_up_zhongshu():
    segments = [
        Segment(start=1, end=10, direction="up", bis=[]),
        Segment(start=10, end=20, direction="down", bis=[]),
        Segment(start=20, end=30, direction="up", bis=[]),
    ]
    detector = ZhongshuDetector(segments)
    zhongshus = detector.detect()
    assert len(zhongshus) == 1
    assert zhongshus[0].start == 1
    assert zhongshus[0].end == 30


def test_down_up_down_zhongshu():
    segments = [
        Segment(start=1, end=10, direction="down", bis=[]),
        Segment(start=10, end=20, direction="up", bis=[]),
        Segment(start=20, end=30, direction="down", bis=[]),
    ]
    detector = ZhongshuDetector(segments)
    zhongshus = detector.detect()
    assert len(zhongshus) == 1


def test_no_zhongshu_same_direction():
    segments = [
        Segment(start=1, end=10, direction="up", bis=[]),
        Segment(start=10, end=20, direction="up", bis=[]),
        Segment(start=20, end=30, direction="up", bis=[]),
    ]
    detector = ZhongshuDetector(segments)
    zhongshus = detector.detect()
    assert len(zhongshus) == 0


def test_no_zhongshu_insufficient():
    segments = [Segment(start=1, end=10, direction="up", bis=[])]
    detector = ZhongshuDetector(segments)
    assert detector.detect() == []
