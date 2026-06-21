from pydantic import BaseModel
from typing import List, Optional, Dict, Literal


class KLine(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class FenXing(BaseModel):
    type: Literal["ding", "di"]
    start_idx: int
    peak_idx: int
    end_idx: int


class Bi(BaseModel):
    start: int
    end: int
    direction: Literal["up", "down"]


class Segment(BaseModel):
    start: int
    end: int
    direction: Literal["up", "down"]
    bis: List[int] = []


class Zhongshu(BaseModel):
    start: int
    end: int
    range: List[float]


class DiagnosisResult(BaseModel):
    code: str
    name: str
    klines: List[KLine]
    fenxings: List[FenXing]
    bis: List[Bi]
    segments: List[Segment]
    zhongshus: List[Zhongshu]
    trend: Literal["上涨趋势", "下跌趋势", "盘整"]
    beichi: Optional[str] = None


class LevelData(BaseModel):
    level: str
    level_name_cn: str
    klines: List[KLine]
    diagnosis: DiagnosisResult
    key_price_range: List[float]
    key_time_range: List[int]
    direction: Optional[str]
    has_zhongshu: bool
    has_beichi: bool


class QJTSignal(BaseModel):
    levels_involved: List[str]
    direction: str
    price_intersection: List[float]
    confidence: float
    price_score: float
    direction_score: float
    time_score: float
    description: str
    precise_price: float


class MultiLevelResult(BaseModel):
    code: str
    name: str
    levels: Dict[str, LevelData]
    qjt_signals: List[QJTSignal]
    overall_assessment: str
    highest_confidence_signal: Optional[QJTSignal]
