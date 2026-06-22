import pytest
from chanlun.models import KLine, DiagnosisResult, Segment, Zhongshu
from chanlun.buy_sell_points import BuySellPointDetector, TradePoint, TYPE_LABEL


def build_klines(n, price_fn):
    out = []
    for i in range(n):
        p = price_fn(i)
        out.append(KLine(date=str(i), open=p, high=p+2, low=p-2, close=p, volume=1000))
    return out


def test_buy1_detection_with_down_beichi():
    # 下跌趋势+下跌背驰+最后K线收阳 → buy1
    prices = [120, 115, 110, 105, 100, 95, 97]  # 最后一根阳(97>95)
    klines = []
    for i, p in enumerate(prices):
        close = p if i == len(prices) - 1 else p
        open_price = p if i == 0 else prices[i-1]
        klines.append(KLine(date=str(i), open=open_price, high=p+2, low=p-2, close=close, volume=1000))
    diag = DiagnosisResult(code='T', name='T', klines=klines, fenxings=[], bis=[],
                           segments=[], zhongshus=[], trend='下跌趋势', beichi='down背驰')
    detector = BuySellPointDetector(diag)
    points = detector.detect()
    types = {p.point_type for p in points}
    assert "buy1" in types


def test_sell1_detection_with_up_beichi():
    prices = [100, 105, 110, 115, 120, 125, 123]
    klines = []
    for i, p in enumerate(prices):
        close = p
        open_price = p if i == 0 else prices[i-1]
        klines.append(KLine(date=str(i), open=open_price, high=p+2, low=p-2, close=close, volume=1000))
    diag = DiagnosisResult(code='T', name='T', klines=klines, fenxings=[], bis=[],
                           segments=[], zhongshus=[], trend='上涨趋势', beichi='up背驰')
    detector = BuySellPointDetector(diag)
    points = detector.detect()
    types = {p.point_type for p in points}
    assert "sell1" in types


def test_no_signal_when_no_beichi():
    klines = build_klines(20, lambda i: 100 + i)
    diag = DiagnosisResult(code='T', name='T', klines=klines, fenxings=[], bis=[],
                           segments=[], zhongshus=[], trend='上涨趋势', beichi=None)
    detector = BuySellPointDetector(diag)
    points = detector.detect()
    # 没有背驰，不应该出现 buy1/sell1
    types = {p.point_type for p in points}
    assert "buy1" not in types
    assert "sell1" not in types


def test_buy3_detected_above_zhongshu():
    # 构造中枢 + 突破中枢上沿
    klines = []
    # 震荡中枢区域
    for i in range(20):
        p = 100 + (i % 5)
        klines.append(KLine(date=str(i), open=p, high=p+2, low=p-2, close=p, volume=1000))
    # 最后5根K线突破向上
    for i in range(20, 25):
        p = 115 + (i - 20)
        klines.append(KLine(date=str(i), open=p, high=p+2, low=p-2, close=p, volume=1000))
    diag = DiagnosisResult(
        code='T', name='T', klines=klines, fenxings=[], bis=[],
        segments=[Segment(start=0, end=10, direction='up', bis=[])],
        zhongshus=[Zhongshu(start=0, end=20, range=[98.0, 106.0])],
        trend='上涨趋势', beichi=None
    )
    detector = BuySellPointDetector(diag)
    points = detector.detect()
    types = {p.point_type for p in points}
    assert "buy3" in types


def test_sell3_detected_below_zhongshu():
    klines = []
    for i in range(20):
        p = 100 + (i % 5)
        klines.append(KLine(date=str(i), open=p, high=p+2, low=p-2, close=p, volume=1000))
    for i in range(20, 25):
        p = 85 - (i - 20)
        klines.append(KLine(date=str(i), open=p, high=p+2, low=p-2, close=p, volume=1000))
    diag = DiagnosisResult(
        code='T', name='T', klines=klines, fenxings=[], bis=[],
        segments=[Segment(start=0, end=10, direction='down', bis=[])],
        zhongshus=[Zhongshu(start=0, end=20, range=[98.0, 106.0])],
        trend='下跌趋势', beichi=None
    )
    detector = BuySellPointDetector(diag)
    points = detector.detect()
    types = {p.point_type for p in points}
    assert "sell3" in types


def test_tradepoint_to_dict():
    p = TradePoint(point_type='buy1', kline_idx=10, price=100.0, reason='test', confidence=0.75)
    d = p.to_dict()
    assert d['point_type'] == 'buy1'
    assert d['price'] == 100.0
    assert d['confidence'] == 0.75


def test_summary_contains_points_when_detected():
    klines = build_klines(15, lambda i: 120 - i)
    # 最后一根收阳
    klines.append(KLine(date='15', open=103, high=106, low=102, close=105, volume=1500))
    diag = DiagnosisResult(code='T', name='T', klines=klines, fenxings=[], bis=[],
                           segments=[], zhongshus=[], trend='下跌趋势', beichi='down背驰')
    detector = BuySellPointDetector(diag)
    summary = detector.summary()
    assert 'buy1' in summary or '买点' in summary


def test_empty_klines_safe():
    diag = DiagnosisResult(code='T', name='T', klines=[], fenxings=[], bis=[],
                           segments=[], zhongshus=[], trend='盘整', beichi=None)
    detector = BuySellPointDetector(diag)
    assert detector.detect() == []


def test_points_sorted_by_confidence_desc():
    # 构造一个既有 buy1 又有 buy3/buy2 的场景
    klines = []
    for i in range(25):
        p = 120 - i  # 整体下跌
        klines.append(KLine(date=str(i), open=p, high=p+2, low=p-2, close=p, volume=1000))
    # 最后一根收阳
    klines.append(KLine(date='25', open=94, high=98, low=93, close=96, volume=1500))
    diag = DiagnosisResult(
        code='T', name='T', klines=klines, fenxings=[], bis=[],
        segments=[Segment(start=0, end=10, direction='down', bis=[])],
        zhongshus=[Zhongshu(start=0, end=15, range=[105.0, 115.0])],
        trend='下跌趋势', beichi='down背驰'
    )
    detector = BuySellPointDetector(diag)
    points = detector.detect()
    if len(points) >= 2:
        confs = [p.confidence for p in points]
        assert confs == sorted(confs, reverse=True)


def test_type_labels_have_all_six_types():
    for t in ['buy1', 'buy2', 'buy3', 'sell1', 'sell2', 'sell3']:
        assert t in TYPE_LABEL
        assert TYPE_LABEL[t]
