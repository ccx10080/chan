import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_levels_endpoint():
    response = client.get("/api/levels")
    assert response.status_code == 200
    data = response.json()
    assert "levels" in data
    assert len(data["levels"]) >= 4


def test_multilevel_diagnosis_demo():
    """使用演示数据测试多级别诊断接口"""
    response = client.post("/api/multilevel-diagnosis", json={
        "code": "TEST", "name": "测试", "use_demo": True
    })
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "TEST"
    assert "levels" in data
    assert "qjt_signals" in data
    assert "overall_assessment" in data


def test_single_level_diagnosis_demo():
    """使用演示数据测试单级别诊断接口"""
    response = client.post("/api/diagnosis", json={
        "code": "TEST", "name": "测试", "use_demo": True
    })
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "TEST"
    assert "klines" in data
    assert "fenxings" in data
    assert "bis" in data


def test_custom_diagnosis_with_klines():
    """使用自定义K线数据进行诊断"""
    klines = []
    highs = [10, 12, 15, 13, 11, 14, 17, 15, 13, 16, 18, 15, 13, 14, 12, 15, 17, 14, 12, 15]
    lows = [8, 10, 11, 9, 8, 10, 12, 10, 9, 11, 14, 11, 9, 10, 9, 11, 14, 11, 9, 11]
    for i in range(len(highs)):
        klines.append({
            "date": str(i), "open": (highs[i]+lows[i])/2,
            "high": highs[i], "low": lows[i],
            "close": (highs[i]+lows[i])/2, "volume": 1000
        })
    response = client.post("/api/custom-diagnosis", json={
        "code": "CUSTOM", "name": "自定义", "klines": klines
    })
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "CUSTOM"


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
