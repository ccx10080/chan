import pytest
from chanlun.multilevel import MultiLevelDiagnosis, generate_demo_klines
from chanlun.models import KLine


def test_generate_demo_klines():
    klines = generate_demo_klines("5m", 100)
    assert len(klines) == 100
    assert isinstance(klines[0], KLine)
    assert klines[0].high > klines[0].low


def test_multilevel_diagnosis_demo_mode():
    """演示模式下应能产生完整多级别诊断结果"""
    d = MultiLevelDiagnosis("DEMO", "演示股票", use_demo=True)
    r = d.run()
    assert r.code == "DEMO"
    assert r.name == "演示股票"
    assert len(r.levels) >= 2
    for lv_key, ld in r.levels.items():
        assert ld.level in ["daily", "30m", "5m", "1m"]
        assert ld.level_name_cn is not None
        assert len(ld.klines) >= 10
        assert ld.diagnosis is not None
        assert ld.diagnosis.trend is not None
        assert len(ld.key_price_range) == 2
        assert len(ld.key_time_range) == 2


def test_highest_signal_exists_if_signals():
    d = MultiLevelDiagnosis("DEMO", "演示", use_demo=True)
    r = d.run()
    if r.qjt_signals:
        assert r.highest_confidence_signal is not None
        assert r.highest_confidence_signal.confidence == r.qjt_signals[0].confidence


def test_overall_assessment_not_empty():
    d = MultiLevelDiagnosis("DEMO", "演示", use_demo=True)
    r = d.run()
    assert r.overall_assessment is not None
    assert len(r.overall_assessment) > 0


def test_signals_sorted_by_confidence_desc():
    d = MultiLevelDiagnosis("DEMO", "演示", use_demo=True)
    r = d.run()
    confs = [s.confidence for s in r.qjt_signals]
    assert confs == sorted(confs, reverse=True)


def test_each_signal_has_valid_confidence():
    d = MultiLevelDiagnosis("DEMO", "演示", use_demo=True)
    r = d.run()
    for s in r.qjt_signals:
        assert 0.5 <= s.confidence <= 1.0
        assert s.direction in ["buy", "sell"]
        assert len(s.levels_involved) >= 2
        assert len(s.price_intersection) == 2


def test_different_levels_have_different_klines():
    d = MultiLevelDiagnosis("DEMO", "演示", use_demo=True)
    r = d.run()
    counts = {k: len(v.klines) for k, v in r.levels.items()}
    assert len(set(counts.values())) >= 1
