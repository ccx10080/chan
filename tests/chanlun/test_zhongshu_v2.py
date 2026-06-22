import pytest
from chanlun.models import KLine, Segment
from chanlun.zhongshu_v2 import ZhongshuDetectorV2


def build_klines(n=30):
    klines = []
    for i in range(n):
        p = 100 + (i % 7)
        klines.append(KLine(date=str(i), open=p, high=p+2, low=p-2, close=p+1, volume=1000))
    return klines


def test_detect_three_segments_form_zhongshu():
    klines = build_klines(30)
    segments = [
        Segment(start=0, end=8, direction='up', bis=[0,1,2]),
        Segment(start=8, end=17, direction='down', bis=[3,4,5]),
        Segment(start=17, end=25, direction='up', bis=[6,7,8]),
    ]
    detector = ZhongshuDetectorV2(segments, klines)
    zs = detector.detect()
    assert len(zs) >= 1
    assert zs[0].start == 0
    assert zs[0].end == 25
    assert zs[0].range[1] > zs[0].range[0]


def test_insufficient_segments_returns_empty():
    detector = ZhongshuDetectorV2([], build_klines(10))
    assert detector.detect() == []


def test_no_price_overlap_no_zhongshu():
    # 三段价格完全错开：分别构造在不同价格带
    # 段1：高区 (prices 200~210)；段2：中区 (prices 150~160)；段3：低区 (prices 100~110)
    klines = []
    # 段1 - 高
    for i in range(6):
        p = 200 + i
        klines.append(KLine(date=str(i), open=p, high=p+1, low=p-1, close=p, volume=1000))
    # 段2 - 中
    for i in range(6, 12):
        p = 150 + (i - 6)
        klines.append(KLine(date=str(i), open=p, high=p+1, low=p-1, close=p, volume=1000))
    # 段3 - 低
    for i in range(12, 18):
        p = 100 + (i - 12)
        klines.append(KLine(date=str(i), open=p, high=p+1, low=p-1, close=p, volume=1000))

    segments = [
        Segment(start=0, end=5, direction='up', bis=[0,1,2]),
        Segment(start=5, end=11, direction='down', bis=[3,4,5]),
        Segment(start=11, end=17, direction='up', bis=[6,7,8]),
    ]
    detector = ZhongshuDetectorV2(segments, klines)
    zs = detector.detect()
    # 三段价格完全无重叠，不应识别为中枢
    assert len(zs) == 0


def test_compute_strength():
    klines = build_klines(30)
    segments = [
        Segment(start=0, end=8, direction='up', bis=[0,1,2]),
        Segment(start=8, end=17, direction='down', bis=[3,4,5]),
        Segment(start=17, end=25, direction='up', bis=[6,7,8]),
    ]
    detector = ZhongshuDetectorV2(segments, klines)
    zs = detector.detect()
    if zs:
        strengths = detector.compute_strength(zs)
        assert len(strengths) == len(zs)
        for s in strengths:
            assert 0 <= s <= 1.0


def test_multiple_triplets_merged():
    """多段连续应该合并成一个大中枢"""
    klines = build_klines(40)
    segments = [
        Segment(start=0, end=5, direction='up', bis=[0,1,2]),
        Segment(start=5, end=10, direction='down', bis=[3,4,5]),
        Segment(start=10, end=15, direction='up', bis=[6,7,8]),
        Segment(start=15, end=20, direction='down', bis=[9,10,11]),
        Segment(start=20, end=25, direction='up', bis=[12,13,14]),
    ]
    detector = ZhongshuDetectorV2(segments, klines)
    zs = detector.detect()
    # 应有至少1个中枢识别
    assert len(zs) >= 1


def test_price_range_contains_all_segments_overlap():
    """中枢价格区间必须是三段价格区间的交集（而非并集）"""
    klines = build_klines(30)
    segments = [
        Segment(start=0, end=8, direction='up', bis=[0,1,2]),
        Segment(start=8, end=17, direction='down', bis=[3,4,5]),
        Segment(start=17, end=25, direction='up', bis=[6,7,8]),
    ]
    detector = ZhongshuDetectorV2(segments, klines)
    zs = detector.detect()
    if zs:
        # 手动计算每段价格区间
        seg_ranges = []
        for seg in segments:
            s = max(0, seg.start)
            e = min(len(klines)-1, seg.end)
            lows = [klines[i].low for i in range(s, e+1)]
            highs = [klines[i].high for i in range(s, e+1)]
            seg_ranges.append((min(lows), max(highs)))
        expected_low = max(r[0] for r in seg_ranges)
        expected_high = min(r[1] for r in seg_ranges)
        assert zs[0].range[0] >= expected_low - 0.01
        assert zs[0].range[1] <= expected_high + 0.01


def test_empty_klines_safe():
    detector = ZhongshuDetectorV2([Segment(start=0, end=10, direction='up')], [])
    assert detector.detect() == []
