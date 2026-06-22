import pytest
from chanlun.backtest import SignalBacktest


def test_run_single_returns_expected_keys():
    engine = SignalBacktest()
    r = engine.run_single("000001", days_back=60, hold_days=5, use_demo=True)
    for k in ["code", "total_signals", "triggered_signals", "win_rate",
              "avg_return", "max_return", "min_return", "trades"]:
        assert k in r
    assert r["code"] == "000001"


def test_run_single_trades_have_valid_fields():
    engine = SignalBacktest()
    r = engine.run_single("000001", days_back=80, hold_days=5)
    for t in r["trades"]:
        assert "price_in" in t and "price_out" in t
        assert "return_pct" in t
        assert "hold_days" in t
        assert t["price_in"] > 0 and t["price_out"] > 0


def test_win_rate_between_0_and_1():
    engine = SignalBacktest()
    r = engine.run_single("000001", days_back=80, hold_days=5)
    assert 0.0 <= r["win_rate"] <= 1.0


def test_run_multi_returns_list_per_code():
    codes = ["000001", "600519", "000858"]
    engine = SignalBacktest()
    results = engine.run_multi(codes, days_back=80, hold_days=5)
    assert len(results) == 3
    for r, expected_code in zip(results, codes):
        assert r["code"] == expected_code


def test_small_days_back_handled_gracefully():
    engine = SignalBacktest()
    r = engine.run_single("000001", days_back=10, hold_days=50)
    # 持仓日数超过数据长度时应返回空
    assert r["total_signals"] == 0
    assert r["trades"] == []


def test_avg_return_in_valid_range_for_normal_scenario():
    engine = SignalBacktest()
    r = engine.run_single("000001", days_back=80, hold_days=5)
    if r["trades"]:
        # 平均收益应在最大/最小收益之间
        assert r["min_return"] - 0.01 <= r["avg_return"] <= r["max_return"] + 0.01
