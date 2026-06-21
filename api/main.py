import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from chanlun.models import KLine, DiagnosisResult, MultiLevelResult
from chanlun.diagnosis import ChanLunDiagnosis
from chanlun.multilevel import MultiLevelDiagnosis

app = FastAPI(title="缠论区间套股票诊断系统", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DiagnosisRequest(BaseModel):
    code: str
    name: str = ""
    use_demo: bool = True


@app.get("/")
async def root():
    index_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "缠论区间套股票诊断系统 - API 已启动"}


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0"}


@app.post("/api/diagnosis")
async def diagnose_single_level(req: DiagnosisRequest):
    """单级别诊断 - 直接使用日线级别"""
    try:
        from chanlun.multilevel import fetch_klines_from_akshare, generate_demo_klines
        if req.use_demo:
            klines = generate_demo_klines("daily", 250)
        else:
            klines = fetch_klines_from_akshare(req.code, "daily", 250)
            if not klines:
                klines = generate_demo_klines("daily", 250)

        if len(klines) < 10:
            raise HTTPException(status_code=400, detail="K线数据不足，无法进行诊断")

        result = ChanLunDiagnosis(req.code, req.name or req.code, klines).run()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"诊断失败: {str(e)}")


@app.post("/api/multilevel-diagnosis")
async def diagnose_multi_level(req: DiagnosisRequest):
    """多级别区间套诊断 - 日线 / 30m / 5m / 1m 四级联判"""
    try:
        d = MultiLevelDiagnosis(req.code, req.name or req.code, use_demo=req.use_demo)
        result = d.run()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"多级别诊断失败: {str(e)}")


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


@app.post("/api/custom-diagnosis")
async def custom_diagnosis(data: dict):
    """使用用户提供的K线数据进行多级别诊断"""
    try:
        klines_data = data.get("klines", [])
        klines = [KLine(**k) for k in klines_data]
        if len(klines) < 10:
            raise HTTPException(status_code=400, detail="提供的K线数据不足")
        result = ChanLunDiagnosis(data.get("code", "CUSTOM"), data.get("name", "自定义"), klines).run()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
