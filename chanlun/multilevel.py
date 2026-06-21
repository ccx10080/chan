import logging
from typing import List, Dict, Optional
from chanlun.models import KLine, MultiLevelResult, LevelData, QJTSignal
from chanlun.diagnosis import build_level_data
from chanlun.qjt_engine import QJTEngine


def fetch_klines_from_akshare(code: str, level: str, n: int) -> List[KLine]:
    """从 akshare 获取指定级别K线数据；如失败则返回空列表"""
    try:
        import akshare as ak
        period_map = {"daily": "daily", "30m": "30", "5m": "5", "1m": "1"}
        period = period_map.get(level, "daily")

        df = ak.stock_zh_a_hist(symbol=code, period=period, adjust="qfq")
        if df is None or len(df) == 0:
            return []
        df = df.tail(n)

        return [
            KLine(
                date=str(row.get('日期', i)),
                open=float(row.get('开盘', 0)),
                high=float(row.get('最高', 0)),
                low=float(row.get('最低', 0)),
                close=float(row.get('收盘', 0)),
                volume=float(row.get('成交量', 0))
            )
            for i, (_, row) in enumerate(df.iterrows())
        ]
    except Exception as e:
        logging.warning(f"akshare 级别{level} 获取失败: {e}")
        return []


def generate_demo_klines(level_or_code: str, n: int) -> List[KLine]:
    """生成模拟K线数据，用于演示/离线测试
    首个参数可以是级别名（daily/30m/5m/1m），也可以是股票代码；
    对于代码会按内部哈希映射到一个稳定的价格起点。
    """
    import math
    klines = []
    level_offsets = {"daily": 10.0, "30m": 10.5, "5m": 10.8, "1m": 10.9}
    if level_or_code in level_offsets:
        base = level_offsets[level_or_code]
    else:
        # 按代码哈希得到一个稳定的起始价格
        h = 0
        for ch in str(level_or_code):
            h = (h * 131 + ord(ch)) % 1000003
        base = 8.0 + (h % 200) / 20.0
    for i in range(n):
        phase = i / 5.0
        high = base + math.sin(phase) * 0.5 + (i % 3) * 0.05
        low = high - 0.3 - (i % 2) * 0.05
        close = (high + low) / 2
        open_price = close + 0.02
        klines.append(KLine(date=str(i), open=round(open_price, 4),
                            high=round(high, 4), low=round(low, 4),
                            close=round(close, 4), volume=1000.0))
    return klines


class MultiLevelDiagnosis:
    """多级别诊断主流程 - 日线 / 30m / 5m / 1m 四级联判"""

    def __init__(self, code: str, name: str = "", use_demo: bool = True):
        self.code = code
        self.name = name or code
        self.use_demo = use_demo
        self.level_configs = [
            ("daily", "日线", 250),
            ("30m", "30分钟", 500),
            ("5m", "5分钟", 800),
            ("1m", "1分钟", 1200),
        ]

    def run(self) -> MultiLevelResult:
        levels: Dict[str, LevelData] = {}

        for level, level_cn, n_bars in self.level_configs:
            if self.use_demo:
                klines = generate_demo_klines(level, n_bars)
            else:
                klines = fetch_klines_from_akshare(self.code, level, n_bars)
                if len(klines) < 10:
                    klines = generate_demo_klines(level, n_bars)

            if len(klines) >= 10:
                ld = build_level_data(self.code, self.name, level, level_cn, klines)
                levels[level] = ld

        if not levels:
            raise ValueError("所有级别数据获取失败，无法进行诊断")

        signals = QJTEngine().detect_signals(levels)
        highest = signals[0] if signals else None

        # 汇总评估信息
        parts = []
        for lv_key, ld in levels.items():
            parts.append(
                f"{ld.level_name_cn}: {ld.diagnosis.trend}, "
                f"中枢{'有' if ld.has_zhongshu else '无'}, "
                f"背驰:{'有' if ld.has_beichi else '无'}, "
                f"方向:{ld.direction or '未定'}"
            )
        overall = "; ".join(parts)

        if signals:
            signal_summary = f"。检测到 {len(signals)} 个区间套信号，"
            top = signals[0]
            dir_text = "买入" if top.direction == "buy" else "卖出"
            lv_text = "、".join(top.levels_involved)
            signal_summary += (f"最高置信度 {top.confidence:.2f} {dir_text}信号 "
                               f"({lv_text}), 精确价位 {top.precise_price}")
            overall += signal_summary
        else:
            overall += "。未检测到有效区间套信号"

        return MultiLevelResult(
            code=self.code,
            name=self.name,
            levels=levels,
            qjt_signals=signals,
            overall_assessment=overall,
            highest_confidence_signal=highest
        )
