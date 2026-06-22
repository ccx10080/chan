import os
import time
import tempfile
import pytest
from chanlun.cache import DiagnosisCache


@pytest.fixture
def cache():
    _, path = tempfile.mkstemp(suffix=".sqlite")
    c = DiagnosisCache(db_path=path)
    c.clear_all()
    yield c
    try:
        os.unlink(path)
    except OSError:
        pass


def test_save_and_get_single(cache):
    cache.save_single("T", "daily", {"foo": "bar", "n": 42})
    result = cache.get_single("T", "daily")
    assert result is not None
    assert result["foo"] == "bar"
    assert result["n"] == 42


def test_get_single_wrong_code_returns_none(cache):
    cache.save_single("A", "daily", {"v": 1})
    assert cache.get_single("B", "daily") is None


def test_get_single_expired(cache):
    cache.save_single("T", "daily", {"v": 1})
    # 设置非常长的过期应返回结果
    result = cache.get_single("T", "daily", max_age_h=99999)
    assert result is not None and result["v"] == 1


def test_save_and_get_multilevel(cache):
    payload = {"code": "T", "levels": ["daily", "30m"], "signals": 2}
    cache.save_multilevel("T", payload)
    hit = cache.get_multilevel("T")
    assert hit is not None
    assert hit["signals"] == 2


def test_log_request_and_get_recent(cache):
    cache.log_request("/api/diagnosis", "000001", 150.0, 200)
    cache.log_request("/api/diagnosis", "600519", 200.0, 200, error=None)
    cache.log_request("/api/test", None, 50.0, 500, error="oops")
    logs = cache.get_recent_logs(10)
    assert len(logs) == 3
    assert logs[0]["endpoint"] == "/api/test"
    assert logs[0]["error"] == "oops"
    assert logs[0]["status_code"] == 500


def test_get_history_returns_ordered(cache):
    for i in range(5):
        cache.save_multilevel("T", {"run": i})
        time.sleep(0.001)
    history = cache.get_history("T", n=3)
    assert len(history) == 3
    # 按时间降序: 最新的 run 应该在前
    runs = [h["result"]["run"] for h in history]
    assert runs == sorted(runs, reverse=True)


def test_clear_all_removes_everything(cache):
    cache.save_single("A", "daily", {"v": 1})
    cache.save_multilevel("B", {"v": 2})
    cache.log_request("/t", "X", 10.0, 200)
    cache.clear_all()
    assert cache.get_single("A", "daily") is None
    assert cache.get_multilevel("B") is None
    assert len(cache.get_recent_logs(10)) == 0


def test_different_levels_are_independent(cache):
    cache.save_single("T", "daily", {"lvl": "daily"})
    cache.save_single("T", "30m", {"lvl": "30m"})
    assert cache.get_single("T", "daily")["lvl"] == "daily"
    assert cache.get_single("T", "30m")["lvl"] == "30m"


def test_json_serialization_preserves_unicode(cache):
    cache.save_single("T", "daily", {"message": "你好 缠论"})
    result = cache.get_single("T", "daily")
    assert result["message"] == "你好 缠论"
