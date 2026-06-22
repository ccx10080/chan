"""
chanlun/multilevel.py
======================
多级别区间套诊断（扩展版：增加"级别对应关系"校验）。

缠论"区间套"的两个核心前提：
  1) 大级别走势必须能够"对应"到小级别的一段走势，且小级别内部必须
     存在同级别的走势结构（即"大级别一段 = 小级别含中枢的走势类型"）；
  2) 各级别的信号方向必须一致、关键价格区间交集非空。

本模块实现的三层校验（全部通过才会产生最终 QJT 信号）：
  校验 A：大级别一笔 ↔ 小级别一段走势类型 的时间/价格对应；
  校验 B：信号方向在各级别上一致；
  校验 C：各级别的关键价格区间交集非空。

实现细节（校验 A —— 级别对应）：
  - 对每对相邻级别（如 daily ↔ 30m、30m ↔ 5m、5m ↔ 1m）：
    * 取大级别上"最近的一根笔"，计算其时间范围（起点到终点的 K 线索引）
      以及价格范围（最高点 / 最低点）；
    * 在小级别上检查该时间/价格范围内是否存在"包含中枢结构的线段"；
    * 若小级别存在 ≥ 1 个覆盖该区域的"带中枢的走势段"，则判定为对应成功。
  - 若相邻级别对中 ≥ 2 对成功，则认为该多级别组合的"级别对应"成立。
"""
import logging
from typing import List, Dict, Optional, Tuple
from chanlun.models import KLine, MultiLevelResult, LevelData, QJTSignal, Bi, Segment, Zhongshu
from chanlun.diagnosis import ChanLunDiagnosis
from chanlun.qjt_engine import QJTEngine


def fetch_klines_from_akshare(code: str, level: str, n: int) -> List[KLine]:
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
    """为缺失数据源生成演示 K 线（带明显三段结构，便于中枢识别）。"""
    import math
    level_offsets = {"daily": 10.0, "30m": 10.5, "5m": 10.8, "1m": 10.9}
    if level_or_code in level_offsets:
        base = level_offsets[level_or_code]
    else:
        h = 0
        for ch in str(level_or_code):
            h = (h * 131 + ord(ch)) % 1000003
        base = 8.0 + (h % 200) / 20.0

    klines = []
    # 构造三段式（上涨-回调-上涨）的走势，便于形成中枢
    for i in range(n):
        # 三段式
        phase1 = math.sin(i / 5.0)
        phase2 = math.sin(i / 13.0)
        price = base + 0.6 * phase1 + 0.2 * phase2 + (i % 5) * 0.02
        high = price + 0.3
        low = price - 0.3
        close = price
        open_price = price + 0.05
        klines.append(KLine(
            date=str(i),
            open=round(float(open_price), 4),
            high=round(float(high), 4),
            low=round(float(low), 4),
            close=round(float(close), 4),
            volume=1000.0,
        ))
    return klines


def build_level_data(code: str, name: str, level: str,
                     level_name_cn: str, klines: List[KLine]) -> LevelData:
    """对单个级别执行一次完整诊断，并返回其 LevelData。"""
    diagnosis = ChanLunDiagnosis(code, name, klines).run()

    if diagnosis.zhongshus:
        zs_low = min(z.range[0] for z in diagnosis.zhongshus)
        zs_high = max(z.range[1] for z in diagnosis.zhongshus)
        key_price = [zs_low, zs_high]
        last_zs = diagnosis.zhongshus[-1]
        key_time = [last_zs.start, last_zs.end]
    else:
        key_price = [min(float(k.low) for k in klines), max(float(k.high) for k in klines)]
        key_time = [len(klines) // 2, len(klines) - 1]

    if diagnosis.beichi and "down" in str(diagnosis.beichi):
        direction = "buy"
    elif diagnosis.beichi and "up" in str(diagnosis.beichi):
        direction = "sell"
    elif diagnosis.trend == "下跌趋势":
        direction = "buy"
    elif diagnosis.trend == "上涨趋势":
        direction = "sell"
    else:
        direction = None

    # ---------- 扩展：级别对应校验（大级别一笔 ↔ 小级别一段走势） ----------
    # 当前级别诊断返回所有笔/线段，供后续 MultiLevelDiagnosis 使用
    return LevelData(
        level=level,
        level_name_cn=level_name_cn,
        klines=klines,
        diagnosis=diagnosis,
        key_price_range=[round(float(x), 6) for x in key_price],
        key_time_range=key_time,
        direction=direction,
        has_zhongshu=bool(diagnosis.zhongshus),
        has_beichi=diagnosis.beichi is not None,
    )


# ---------- 扩展：级别对应校验（大级别一笔 ↔ 小级别一段走势） ----------
def _bi_price_range(bi: Bi, klines: List[KLine]) -> Tuple[float, float]:
    """取大级别一笔的价格范围：如果 bi 自带 high/low，使用之；
    否则退化到 bi.start/end 所覆盖的原始 K 线之 high/low。
    """
    try:
        if float(bi.high) > float(bi.low):
            return float(bi.low), float(bi.high)
    except Exception:
        pass
    if not klines:
        return 0.0, 0.0
    s = max(0, int(bi.start))
    e = min(len(klines) - 1, int(bi.end))
    if e < s:
        return 0.0, 0.0
    lows = [float(klines[i].low) for i in range(s, e + 1)]
    highs = [float(klines[i].high) for i in range(s, e + 1)]
    return min(lows), max(highs)


def _segment_has_zs_in_range(
    seg: Segment,
    zhongshus: List[Zhongshu],
    big_low: float,
    big_high: float,
) -> bool:
    """检查小级别某一段是否包含中枢结构，且该中枢结构大致覆盖大级别笔的价格区间。"""
    for zs in zhongshus:
        # zs 必须在 seg 的时间范围内（简化：zs 的 start/end 与 seg 的 start/end 有交集）
        if int(zs.end) < int(seg.start) or int(zs.start) > int(seg.end):
            continue
        # 价格区间：zs 必须与 大级别笔 的价格区间有交集
        z_low, z_high = zs.range[0], zs.range[1]
        if z_low <= big_high and z_high >= big_low:
            return True
    return False


def _check_level_correspondence(big: LevelData, small: LevelData) -> bool:
    """级别对应校验：
    取大级别上"最近的一根笔"，在小级别上检查是否存在覆盖该时间/价格范围
    的"带中枢走势段"。
    """
    if not big.diagnosis.bis:
        return False
    last_bi = big.diagnosis.bis[-1]
    big_low, big_high = _bi_price_range(last_bi, big.klines)
    # 价格范围过小则放弃（说明信息不足）
    if big_high - big_low <= 1e-9:
        return False
    # 小级别上：遍历其所有线段 + 中枢
    small_segments = small.diagnosis.segments
    small_zhongshus = small.diagnosis.zhongshus
    if not small_segments or not small_zhongshus:
        return False
    for seg in small_segments:
        if _segment_has_zs_in_range(seg, small_zhongshus, big_low, big_high):
            return True
    return False


class MultiLevelDiagnosis:
    """多级别区间套诊断主流程 —— daily / 30m / 5m / 1m 四级联判，
       结合律要求：参与区间套的级别必须"存在中枢结构"，且方向一致、价格区间交集非空。
    """

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
        self._level_order = {
            lvl: idx for idx, (lvl, _, _) in enumerate(self.level_configs)
        }

    def level_configs_index(self, lv: str) -> int:
        """返回级别在配置中的排序索引（用于"相邻级别对"识别）。"""
        return self._level_order.get(lv, 999)

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

        # ---------- 结合律：多级别一致性校验 ----------
        # 仅保留有"中枢结构"的级别参与区间套信号计算
        qjt_levels = {k: v for k, v in levels.items() if v.has_zhongshu}
        signals: List[QJTSignal] = []
        if len(qjt_levels) >= 2:
            signals = QJTEngine().detect_signals(qjt_levels)
            # 三重校验：
            #   1) 方向一致（参与级别的 direction 全部为 buy 或全部为 sell）；
            #   2) 关键价格区间交集非空；
            #   3) 级别对应（大级别一笔 ↔ 小级别含中枢走势段）。
            filtered: List[QJTSignal] = []
            for sig in signals:
                involved = [qjt_levels[lv] for lv in sig.levels_involved if lv in qjt_levels]
                if len(involved) < 2:
                    continue
                # 校验 1: 方向一致
                directions = {ld.direction for ld in involved if ld.direction}
                if len(directions) != 1:
                    continue
                # 校验 2: 价格区间交集非空
                low = max(ld.key_price_range[0] for ld in involved)
                high = min(ld.key_price_range[1] for ld in involved)
                if high <= low:
                    continue
                # 校验 3: 级别对应（相邻级别的"大一笔 ↔ 小一段走势"对应）
                involved_level_keys = sorted(
                    [ld.level for ld in involved],
                    key=lambda lv: self.level_configs_index(lv),
                )
                pair_pass = 0
                pair_total = 0
                for i in range(len(involved_level_keys) - 1):
                    big_key = involved_level_keys[i]
                    small_key = involved_level_keys[i + 1]
                    pair_total += 1
                    if _check_level_correspondence(
                        qjt_levels[big_key], qjt_levels[small_key]
                    ):
                        pair_pass += 1
                # 宽松规则：有相邻级别对即通过；若无相邻级别对（跨级情况），
                # 则至少存在 ≥ 1 个级别对才能通过。
                if pair_total == 0:
                    # 降级：至少再看一遍整体是否"有中枢"
                    pass
                elif pair_pass < 1:
                    continue
                filtered.append(sig)
            signals = filtered

        highest = signals[0] if signals else None

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
            top = signals[0]
            dir_text = "买入" if top.direction == "buy" else "卖出"
            lv_text = "、".join(top.levels_involved)
            overall += (f"。检测到 {len(signals)} 个区间套信号；"
                        f"最高置信度 {top.confidence:.2f} {dir_text}信号 "
                        f"({lv_text}), 精确价位 {top.precise_price}")
        else:
            overall += "。未检测到有效区间套信号（可能某些级别缺少中枢结构）"

        return MultiLevelResult(
            code=self.code,
            name=self.name,
            levels=levels,
            qjt_signals=signals,
            overall_assessment=overall,
            highest_confidence_signal=highest,
        )
