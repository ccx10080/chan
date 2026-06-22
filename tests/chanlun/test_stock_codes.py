import pytest
from chanlun.stock_codes import StockCodeDB


@pytest.fixture
def db():
    return StockCodeDB()


def test_db_has_enough_codes(db):
    items = db.all_codes()
    assert len(items) >= 40


def test_search_by_exact_code(db):
    results = db.search("000001")
    assert len(results) >= 1
    assert results[0]["code"] == "000001"


def test_search_by_name_keyword(db):
    results = db.search("茅台")
    assert len(results) >= 1
    assert "茅台" in results[0]["name"]


def test_search_by_sector(db):
    results = db.search("银行")
    assert len(results) >= 2


def test_search_empty_query_returns_empty(db):
    assert db.search("") == []


def test_search_no_match(db):
    assert db.search("不存在这只股票XYZ") == []


def test_get_name_and_sector(db):
    assert db.get_name("600519") is not None
    assert db.get_sector("600519") is not None


def test_get_name_unknown_code_returns_none(db):
    assert db.get_name("999999") is None
    assert db.get_sector("999999") is None


def test_search_limit_respected(db):
    results = db.search("银行", limit=3)
    assert len(results) <= 3


def test_codes_are_unique(db):
    codes = [c["code"] for c in db.all_codes()]
    assert len(codes) == len(set(codes))
