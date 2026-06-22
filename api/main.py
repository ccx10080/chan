import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict

from chanlun.models import KLine, DiagnosisResult, MultiLevelResult
from chanlun.diagnosis import ChanLunDiagnosis
from chanlun.multilevel import MultiLevelDiagnosis
from chanlun.cache import DiagnosisCache
from chanlun.stock_codes import StockCodeDB
from chanlun.batch_scan import BatchScanner
from chanlun.backtest import SignalBacktest
from chanlun.zhongshu_v2 import ZhongshuDetectorV2
from chanlun.buy_sell_points import BuySellPointDetector

app = FastAPI(title="缠论区间套股票诊断系统 v1.1", version="1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_cache = DiagnosisCache()
_code_db = StockCodeDB()


class DiagnosisRequest(BaseModel):
    code: str
    name: str = ""
    use_demo: bool = True


class BatchScanRequest(BaseModel):
    codes: List[str]
    top_n: int = 20
    min_confidence: float = 0.0
    use_demo: bool = True


class BacktestRequest(BaseModel):
    code: str
    days_back: int = 120
    hold_days: int = 10
    use_demo: bool = True
    min_confidence: float = 0.5


def _log_request(endpoint: str, code: Optional[str], t0: float, status_code: int,
                 error: Optional[str] = None):
    try:
        _cache.log_request(endpoint=endpoint, code=code,
                            response_time_ms=round((time.time() - t0) * 1000, 2),
                            status_code=status_code, error=error)
    except Exception:
        pass


@app.get("/")
async def root():
    index_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "缠论区间套股票诊断系统 - API 已启动"}


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.1"}


@app.get("/api/levels")
async def list_levels():
    """返回支持的时间级别列表"""
    return {
        "levels": [
            {"key": "daily", "name_cn": "日线", "bar_count": 250},
            {"key": "30m", "name_cn": "30分钟", "bar_count": 500},
            {"key": "5m", "name_cn": "5分钟", "bar_count": 800},
            {"key": "1m", "name_cn": "1分钟", "bar_count": 1200},
        ]
    }


@app.get("/api/stock/search")
async def search_stock(query: str, limit: int = 10):
    """模糊搜索股票代码 / 名称 / 板块"""
    t0 = time.time()
    try:
        results = _code_db.search(query, limit=limit)
        _log_request("/api/stock/search", query, t0, 200)
        return {"query": query, "total_matched": len(results), "results": results}
    except Exception as e:
        _log_request("/api/stock/search", query, t0, 500, str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/list")
async def list_stocks():
    """返回全部内置股票列表"""
    try:
        return {"total": len(_code_db.all_codes()), "stocks": _code_db.all_codes()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/diagnosis")
async def diagnose_single_level(req: DiagnosisRequest):
    """单级别诊断 - 使用日线级别，接入 SQLite 缓存"""
    t0 = time.time()
    code = str(req.code).strip()
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    try:
        # 查缓存
        cached = _cache.get_single(code, "daily", max_age_h=24) if req.use_demo else _cache.get_single(code, "daily", max_age_h=2)
        if cached:
            _log_request("/api/diagnosis", code, t0, 200, None)
            cached["_from_cache"] = True
            return cached

        from chanlun.multilevel import fetch_klines_from_akshare, generate_demo_klines
        if req.use_demo:
            klines = generate_demo_klines("daily", 250)
        else:
            klines = fetch_klines_from_akshare(code, "daily", 250)
            if not klines:
                klines = generate_demo_klines("daily", 250)

        if len(klines) < 10:
            raise HTTPException(status_code=400, detail="K线数据不足，无法进行诊断")

        result = ChanLunDiagnosis(code, req.name or code, klines).run()
        result_dict = result.model_dump() if hasattr(result, "model_dump") else result.dict()

        # 买卖点附加检测
        try:
            buy_sell = BuySellPointDetector(result).detect()
            result_dict["buy_sell_points"] = [bp.to_dict() for bp in buy_sell]
        except Exception:
            result_dict["buy_sell_points"] = []

        # 写入缓存
        try:
            _cache.save_single(code, "daily", result_dict)
        except Exception:
            pass

        _log_request("/api/diagnosis", code, t0, 200)
        result_dict["_from_cache"] = False
        return result_dict
    except HTTPException:
        raise
    except Exception as e:
        _log_request("/api/diagnosis", code, t0, 500, str(e))
        raise HTTPException(status_code=500, detail=f"诊断失败: {str(e)}")


@app.post("/api/multilevel-diagnosis")
async def diagnose_multi_level(req: DiagnosisRequest):
    """多级别区间套诊断 - 日线 / 30m / 5m / 1m 四级联判，接入缓存"""
    t0 = time.time()
    code = str(req.code).strip()
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    try:
        cached = _cache.get_multilevel(code, max_age_h=6 if req.use_demo else 1)
        if cached:
            _log_request("/api/multilevel-diagnosis", code, t0, 200)
            cached["_from_cache"] = True
            return cached

        d = MultiLevelDiagnosis(code, req.name or code, use_demo=req.use_demo)
        result = d.run()
        result_dict = result.model_dump() if hasattr(result, "model_dump") else result.dict()

        # 给每个级别附加买卖点信息
        try:
            for lvl_key, lvl_data in result.levels.items():
                bp = BuySellPointDetector(lvl_data.diagnosis).detect()
                # Pydantic dict 直接在 dict 中补充
                if "levels" in result_dict and lvl_key in result_dict["levels"]:
                    result_dict["levels"][lvl_key]["buy_sell_points"] = [b.to_dict() for b in bp]
        except Exception:
            pass

        try:
            _cache.save_multilevel(code, result_dict)
        except Exception:
            pass

        _log_request("/api/multilevel-diagnosis", code, t0, 200)
        result_dict["_from_cache"] = False
        return result_dict
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        _log_request("/api/multilevel-diagnosis", code, t0, 500, str(e))
        raise HTTPException(status_code=500, detail=f"多级别诊断失败: {str(e)}")


@app.post("/api/batch-scan")
async def batch_scan(req: BatchScanRequest):
    """对一批股票执行批量多级别诊断，按信号强度排序"""
    t0 = time.time()
    if not req.codes:
        raise HTTPException(status_code=400, detail="codes 不能为空列表")
    try:
        scanner = BatchScanner(use_demo=req.use_demo)
        result = scanner.scan(req.codes, top_n=req.top_n, min_confidence=req.min_confidence)
        _log_request("/api/batch-scan", f"{len(req.codes)} codes", t0, 200)
        return result
    except Exception as e:
        _log_request("/api/batch-scan", f"{len(req.codes)} codes", t0, 500, str(e))
        raise HTTPException(status_code=500, detail=f"批量扫描失败: {str(e)}")


@app.post("/api/backtest")
async def backtest(req: BacktestRequest):
    """信号回测 - 对历史K线滚动诊断并计算持有 N 日的盈亏"""
    t0 = time.time()
    code = str(req.code).strip()
    if not code:
        raise HTTPException(status_code=400, detail="股票代码不能为空")
    try:
        bt = SignalBacktest()
        result = bt.run_single(
            code=code,
            days_back=req.days_back,
            hold_days=req.hold_days,
            use_demo=req.use_demo,
            min_confidence=req.min_confidence,
        )
        _log_request("/api/backtest", code, t0, 200)
        return result
    except Exception as e:
        _log_request("/api/backtest", code, t0, 500, str(e))
        raise HTTPException(status_code=500, detail=f"回测失败: {str(e)}")


@app.get("/api/history")
async def get_history(code: str, n: int = 30):
    """查询某只股票近期多级别诊断历史结果"""
    try:
        history = _cache.get_history(code, n=n)
        return {"code": code, "total": len(history), "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs")
async def get_logs(n: int = 50):
    """返回最近的请求日志（用于监控）"""
    try:
        logs = _cache.get_recent_logs(n)
        return {"total": len(logs), "logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/custom-diagnosis")
async def custom_diagnosis(data: dict):
    """使用用户提供的K线数据进行诊断"""
    t0 = time.time()
    try:
        klines_data = data.get("klines", [])
        klines = [KLine(**k) for k in klines_data]
        if len(klines) < 10:
            raise HTTPException(status_code=400, detail="提供的K线数据不足")
        result = ChanLunDiagnosis(data.get("code", "CUSTOM"), data.get("name", "自定义"), klines).run()
        result_dict = result.model_dump() if hasattr(result, "model_dump") else result.dict()
        # 附加买卖点
        try:
            bp = BuySellPointDetector(result).detect()
            result_dict["buy_sell_points"] = [b.to_dict() for b in bp]
        except Exception:
            result_dict["buy_sell_points"] = []
        _log_request("/api/custom-diagnosis", data.get("code"), t0, 200)
        return result_dict
    except HTTPException:
        raise
    except Exception as e:
        _log_request("/api/custom-diagnosis", data.get("code"), t0, 500, str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
