import pytest
from chanlun.models import KLine
from chanlun.detector import FenXingDetector


def test_detect_ding_fenxing():
    klines = [
        KLine(date="1", open=10, high=12, low=9, close=11, volume=1000),
        KLine(date="2", open=11, high=15, low=10, close=14, volume=1000),
        KLine(date="3", open=14, high=14, low=11, close=12, volume=1000),
    ]
    detector = FenXingDetector(klines)
    fenxings = detector.detect()
    assert len(fenxings) == 1
    assert fenxings[0].type == "ding"
    assert fenxings[0].peak_idx == 1


def test_detect_di_fenxing():
    klines = [
        KLine(date="1", open=15, high=15, low=12, close=13, volume=1000),
        KLine(date="2", open=13, high=14, low=10, close=11, volume=1000),
        KLine(date="3", open=11, high=13, low=11, close=12, volume=1000),
    ]
    detector = FenXingDetector(klines)
    fenxings = detector.detect()
    assert len(fenxings) == 1
    assert fenxings[0].type == "di"
    assert fenxings[0].peak_idx == 1


def test_no_fenxing_flat():
    klines = [
        KLine(date="1", open=10, high=11, low=9, close=10, volume=1000),
        KLine(date="2", open=10, high=11, low=9, close=10, volume=1000),
        KLine(date="3", open=10, high=11, low=9, close=10, volume=1000),
    ]
    detector = FenXingDetector(klines)
    fenxings = detector.detect()
    assert len(fenxings) == 0


def test_multiple_fenxings():
    highs = [10, 12, 10, 11, 9, 10, 8, 9, 7]
    lows = [8, 10, 8, 9, 7, 8, 6, 7, 5]
    klines = [
        KLine(date=str(i), open=(highs[i]+lows[i])/2, high=highs[i], low=lows[i],
              close=(highs[i]+lows[i])/2, volume=1000)
        for i in range(len(highs))
    ]
    detector = FenXingDetector(klines)
    fenxings = detector.detect()
    assert len(fenxings) >= 2
