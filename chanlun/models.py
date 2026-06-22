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
    peak_price: float = 0.0   # 分型极值价（顶分型=最高high，底分型=最低low），来自"包含处理后K线"


class Bi(BaseModel):
    start: int           # 起点分型 peak_idx（基于原始K线索引）
    end: int             # 终点分型 peak_idx（基于原始K线索引）
    direction: Literal["up", "down"]
    high: float = 0.0    # 笔范围内（原始K线）最高 high
    low: float = 0.0     # 笔范围内（原始K线）最低 low


class Segment(BaseModel):
    start: int
    end: int
    direction: Literal["up", "down"]
    bis: List[int] = []
    high: float = 0.0    # 线段范围内最高 high
    low: float = 0.0     # 线段范围内最低 low
    has_zhongshu: bool = False  # 线段内部是否已形成"级别内中枢结构"（走势类型意义）


class Zhongshu(BaseModel):
    start: int                      # 中枢起点（原始K线索引）
    end: int                        # 中枢终点（原始K线索引）
    range: List[float]              # [中枢下沿, 中枢上沿] 价格区间
    direction: Optional[str] = None # 中枢构建方向："up"（下-上-下）或 "down"（上-下-上）
    is_extension: bool = False      # 是否由"延伸/扩展"合并形成


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
