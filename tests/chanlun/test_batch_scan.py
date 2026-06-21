import pytest
from chanlun.batch_scan import BatchScanner


def test_scan_multiple_codes_returns_ranked_results():
    scanner = BatchScanner(use_demo=True)
    result = scanner.scan(["000001", "600519", "000858"], top_n=5)
    assert result["total_scanned"] == 3
    assert "signals_found" in result
    assert "ranked_results" in result
    assert isinstance(result["ranked_results"], list)
    for r in result["ranked_results"]:
        assert "code" in r
        assert "top_confidence" in r
        assert "direction" in r
        assert "n_signals" in r


def test_scan_respects_top_n():
    scanner = BatchScanner(use_demo=True)
    result = scanner.scan([f"CODE_{i}" for i in range(50)], top_n=3)
    assert len(result["ranked_results"]) <= 3


def test_scan_respects_min_confidence():
    scanner = BatchScanner(use_demo=True)
    # 置信度门槛 1.0（永远达不到）→ 应返回空
    result = scanner.scan(["000001"], top_n=10, min_confidence=1.0)
    assert result["ranked_results"] == []


def test_scan_empty_codes():
    scanner = BatchScanner(use_demo=True)
    result = scanner.scan([], top_n=10)
    assert result["total_scanned"] == 0
    assert result["ranked_results"] == []


def test_scan_handles_whitespace():
    scanner = BatchScanner(use_demo=True)
    result = scanner.scan([" 000001 ", "", "  "], top_n=10)
    assert result["total_scanned"] == 1


def test_scan_from_db_by_sector():
    from chanlun.stock_codes import StockCodeDB
    db = StockCodeDB()
    scanner = BatchScanner(use_demo=True)
    result = scanner.scan_from_db(db, sector="白酒", top_n=5)
    assert result["total_scanned"] >= 1


def test_ranked_results_sorted_by_confidence_desc():
    scanner = BatchScanner(use_demo=True)
    result = scanner.scan([f"C{i}" for i in range(10)], top_n=10)
    confs = [r["top_confidence"] for r in result["ranked_results"]]
    assert confs == sorted(confs, reverse=True)
