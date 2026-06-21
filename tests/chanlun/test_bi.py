import pytest
from chanlun.models import KLine, FenXing
from chanlun.bi import BiAnalyzer


def build_klines_from_highs_lows(highs, lows):
    return [
        KLine(date=str(i), open=(highs[i]+lows[i])/2, high=highs[i], low=lows[i],
              close=(highs[i]+lows[i])/2, volume=1000.0)
        for i in range(len(highs))
    ]


def test_build_up_bi():
    """底-顶 分型构成上涨笔"""
    highs = [12, 11, 10, 12, 13, 15, 14, 13, 14, 16]
    lows = [8, 9, 7, 8, 9, 10, 11, 10, 11, 12]
    klines = build_klines_from_highs_lows(highs, lows)
    fenxings = [
        FenXing(type="di", start_idx=1, peak_idx=2, end_idx=3),
        FenXing(type="ding", start_idx=4, peak_idx=5, end_idx=6),
    ]
    analyzer = BiAnalyzer(klines, fenxings)
    bis = analyzer.build_bis()
    assert len(bis) == 1
    assert bis[0].direction == "up"


def test_build_down_bi():
    """顶-底 分型构成下跌笔"""
    highs = [12, 15, 14, 13, 12, 11, 10, 11, 10, 9]
    lows = [8, 10, 9, 8, 7, 8, 7, 8, 7, 6]
    klines = build_klines_from_highs_lows(highs, lows)
    fenxings = [
        FenXing(type="ding", start_idx=0, peak_idx=1, end_idx=2),
        FenXing(type="di", start_idx=5, peak_idx=6, end_idx=7),
    ]
    analyzer = BiAnalyzer(klines, fenxings)
    bis = analyzer.build_bis()
    assert len(bis) == 1
    assert bis[0].direction == "down"


def test_no_bi_insufficient_klines():
    """分型间隔不足5K不形成笔"""
    klines = build_klines_from_highs_lows(
        [12, 15, 13, 11, 12],
        [8, 10, 9, 7, 8]
    )
    fenxings = [
        FenXing(type="ding", start_idx=0, peak_idx=1, end_idx=2),
        FenXing(type="di", start_idx=2, peak_idx=3, end_idx=4),
    ]
    analyzer = BiAnalyzer(klines, fenxings)
    bis = analyzer.build_bis()
    assert len(bis) == 0


def test_empty_bi():
    klines = build_klines_from_highs_lows([10, 11, 12], [8, 9, 10])
    analyzer = BiAnalyzer(klines, [])
    assert analyzer.build_bis() == []
