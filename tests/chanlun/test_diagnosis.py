import pytest
from chanlun.models import KLine
from chanlun.diagnosis import ChanLunDiagnosis, build_level_data


def build_test_klines(n=30):
    highs = [10 + (i % 5) * 0.5 + (i // 3) * 0.2 for i in range(n)]
    lows = [h - 2 for h in highs]
    return [
        KLine(date=str(i), open=(highs[i]+lows[i])/2, high=highs[i], low=lows[i],
              close=(highs[i]+lows[i])/2, volume=1000.0)
        for i in range(n)
    ]


def test_diagnosis_produces_result():
    klines = build_test_klines(30)
    d = ChanLunDiagnosis("TEST", "测试", klines)
    r = d.run()
    assert r.code == "TEST"
    assert r.name == "测试"
    assert len(r.klines) == 30
    assert r.trend in ["上涨趋势", "下跌趋势", "盘整"]


def test_diagnosis_fields_filled():
    klines = build_test_klines(50)
    d = ChanLunDiagnosis("TEST2", "测试2", klines)
    r = d.run()
    assert isinstance(r.fenxings, list)
    assert isinstance(r.bis, list)
    assert isinstance(r.segments, list)
    assert isinstance(r.zhongshus, list)


def test_build_level_data():
    klines = build_test_klines(40)
    ld = build_level_data("T", "T", "5m", "5分钟", klines)
    assert ld.level == "5m"
    assert ld.level_name_cn == "5分钟"
    assert len(ld.key_price_range) == 2
    assert len(ld.key_time_range) == 2
    assert ld.direction in [None, "buy", "sell"]


def test_small_klines_handled():
    klines = build_test_klines(10)
    d = ChanLunDiagnosis("TINY", "T", klines)
    r = d.run()
    assert r.trend == "盘整"
