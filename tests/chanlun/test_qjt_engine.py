import pytest
from chanlun.models import KLine, DiagnosisResult, LevelData
from chanlun.qjt_engine import QJTEngine


def build_level(level, level_cn, price_range, time_range, direction, n=50):
    """构造测试用的 LevelData"""
    klines = [
        KLine(date=str(i), open=10+i*0.1, high=11+i*0.1,
              low=9+i*0.1, close=10+i*0.1, volume=1000.0)
        for i in range(n)
    ]
    diag = DiagnosisResult(code="T", name="T", klines=klines,
                           fenxings=[], bis=[], segments=[], zhongshus=[],
                           trend="盘整", beichi=None)
    return LevelData(level=level, level_name_cn=level_cn,
                     klines=klines, diagnosis=diag,
                     key_price_range=price_range, key_time_range=time_range,
                     direction=direction, has_zhongshu=True, has_beichi=True)


def test_four_level_buy_signal():
    """4级别完全嵌套形成买入信号"""
    levels = {
        "daily": build_level("daily", "日线", [10.0, 12.0], [30, 45], "buy", 50),
        "30m":   build_level("30m", "30分钟", [10.5, 11.8], [400, 480], "buy", 500),
        "5m":    build_level("5m", "5分钟", [10.8, 11.5], [800, 900], "buy", 1000),
        "1m":    build_level("1m", "1分钟", [10.9, 11.2], [1500, 1800], "buy", 2000),
    }
    engine = QJTEngine()
    signals = engine.detect_signals(levels)
    assert len(signals) >= 1
    assert signals[0].direction == "buy"
    assert signals[0].confidence > 0.5


def test_price_no_intersection():
    """价格区间无交集 -> 无信号"""
    levels = {
        "daily": build_level("daily", "日线", [10.0, 11.0], [30, 45], "buy", 50),
        "30m":   build_level("30m", "30分钟", [13.0, 14.0], [400, 480], "buy", 500),
    }
    engine = QJTEngine()
    signals = engine.detect_signals(levels)
    assert len(signals) == 0


def test_direction_mismatch():
    """方向不一致 -> 无信号"""
    levels = {
        "daily": build_level("daily", "日线", [10.0, 12.0], [30, 45], "buy", 50),
        "30m":   build_level("30m", "30分钟", [10.5, 11.8], [400, 480], "sell", 500),
    }
    engine = QJTEngine()
    signals = engine.detect_signals(levels)
    assert len(signals) == 0


def test_sell_signal_detected():
    """4级别完全嵌套形成卖出信号"""
    levels = {
        "daily": build_level("daily", "日线", [10.0, 12.0], [30, 45], "sell", 50),
        "30m":   build_level("30m", "30分钟", [10.5, 11.8], [400, 480], "sell", 500),
        "5m":    build_level("5m", "5分钟", [10.8, 11.5], [800, 900], "sell", 1000),
        "1m":    build_level("1m", "1分钟", [10.9, 11.2], [1500, 1800], "sell", 2000),
    }
    engine = QJTEngine()
    signals = engine.detect_signals(levels)
    assert len(signals) >= 1
    assert signals[0].direction == "sell"


def test_insufficient_levels():
    """少于2级别不触发"""
    levels = {
        "daily": build_level("daily", "日线", [10.0, 12.0], [30, 45], "buy", 50),
    }
    engine = QJTEngine()
    signals = engine.detect_signals(levels)
    assert signals == []


def test_empty_levels():
    engine = QJTEngine()
    assert engine.detect_signals({}) == []


def test_signal_precise_price_in_range():
    """信号精确价位必须在交集区间内"""
    levels = {
        "daily": build_level("daily", "日线", [10.0, 12.0], [30, 45], "buy", 50),
        "30m":   build_level("30m", "30分钟", [10.5, 11.8], [400, 480], "buy", 500),
        "5m":    build_level("5m", "5分钟", [10.8, 11.5], [800, 900], "buy", 1000),
    }
    engine = QJTEngine()
    signals = engine.detect_signals(levels)
    assert len(signals) >= 1
    s = signals[0]
    assert s.price_intersection[0] <= s.precise_price <= s.price_intersection[1]
    assert s.description is not None and len(s.description) > 0


def test_confidence_valid_range():
    """置信度必须在0-1之间"""
    levels = {
        "daily": build_level("daily", "日线", [10.0, 12.0], [30, 45], "buy", 50),
        "30m":   build_level("30m", "30分钟", [10.5, 11.8], [400, 480], "buy", 500),
    }
    engine = QJTEngine()
    signals = engine.detect_signals(levels)
    for s in signals:
        assert 0.0 <= s.confidence <= 1.0
        assert 0.0 <= s.price_score <= 1.0
        assert 0.0 <= s.direction_score <= 1.0
        assert 0.0 <= s.time_score <= 1.0
