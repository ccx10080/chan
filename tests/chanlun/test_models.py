import pytest
from chanlun.models import (
    KLine, FenXing, Bi, Segment, Zhongshu,
    DiagnosisResult, LevelData, QJTSignal, MultiLevelResult
)


def test_kline_creation():
    k = KLine(date="2024-01-01", open=100.0, high=105.0, low=99.0, close=103.0, volume=10000.0)
    assert k.high == 105.0
    assert k.low == 99.0


def test_fenxing_creation():
    fx = FenXing(type="ding", start_idx=0, peak_idx=1, end_idx=2)
    assert fx.type == "ding"


def test_bi_creation():
    b = Bi(start=0, end=5, direction="up")
    assert b.direction == "up"


def test_segment_creation():
    s = Segment(start=0, end=10, direction="up", bis=[0, 1, 2])
    assert s.direction == "up"
    assert len(s.bis) == 3


def test_zhongshu_creation():
    z = Zhongshu(start=0, end=10, range=[100.0, 105.0])
    assert z.range == [100.0, 105.0]


def test_leveldata_creation():
    klines = [KLine(date=str(i), open=10+i*0.1, high=11+i*0.1, low=9+i*0.1, close=10+i*0.1, volume=1000) for i in range(30)]
    diag = DiagnosisResult(code="T", name="T", klines=klines, fenxings=[], bis=[], segments=[], zhongshus=[], trend="盘整", beichi=None)
    ld = LevelData(level="5m", level_name_cn="5分钟", klines=klines, diagnosis=diag,
                   key_price_range=[10.0, 12.0], key_time_range=[10, 20],
                   direction="buy", has_zhongshu=False, has_beichi=False)
    assert ld.level == "5m"
    assert ld.direction == "buy"


def test_qjtsignal_creation():
    s = QJTSignal(levels_involved=["daily", "30m"], direction="buy",
                  price_intersection=[10.5, 11.0], confidence=0.85,
                  price_score=0.9, direction_score=1.0, time_score=0.7,
                  description="test", precise_price=10.75)
    assert s.confidence == 0.85
    assert s.direction == "buy"


def test_multilevelresult_creation():
    klines = [KLine(date=str(i), open=10, high=11, low=9, close=10, volume=1000) for i in range(10)]
    diag = DiagnosisResult(code="T", name="T", klines=klines, fenxings=[], bis=[], segments=[], zhongshus=[], trend="盘整", beichi=None)
    ld = LevelData(level="daily", level_name_cn="日线", klines=klines, diagnosis=diag,
                   key_price_range=[10.0, 11.0], key_time_range=[5, 8],
                   direction=None, has_zhongshu=False, has_beichi=False)
    mlr = MultiLevelResult(code="T", name="T", levels={"daily": ld}, qjt_signals=[],
                           overall_assessment="无信号", highest_confidence_signal=None)
    assert "daily" in mlr.levels
    assert mlr.overall_assessment == "无信号"
