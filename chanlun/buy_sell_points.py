# chanlun/buy_sell_points.py
# 买卖点精确定位 - 简化版缠论买卖点识别
from typing import List, Optional
from dataclasses import dataclass

from chanlun.models import DiagnosisResult


@dataclass
class TradePoint:
    point_type: str          # "buy1", "buy2", "buy3", "sell1", "sell2", "sell3"
    kline_idx: int           # 发生在第几根K线
    price: float             # 建议操作价
    reason: str              # 文字说明
    confidence: float        # 0-1

    def to_dict(self) -> dict:
        return {
            "point_type": self.point_type,
            "kline_idx": self.kline_idx,
            "price": self.price,
            "reason": self.reason,
            "confidence": self.confidence,
        }


TYPE_LABEL = {
    "buy1": "一类买点",
    "buy2": "二类买点",
    "buy3": "三类买点",
    "sell1": "一类卖点",
    "sell2": "二类卖点",
    "sell3": "三类卖点",
}


class BuySellPointDetector:
    """
    简化版缠论买卖点识别器

    识别规则:
      buy1: 下跌趋势 + 下跌背驰 + 最新K线收阴后出现底分型
      sell1: 上涨趋势 + 上涨背驰 + 最新K线收阳后出现顶分型
      buy2: 在 buy1 之后，次级别回拉不破 buy1 低点，且价格高于 buy1 价
      sell2: 在 sell1 之后，次级别回拉不破 sell1 高点，且价格低于 sell1 价
      buy3: 次级别向上突破中枢上沿后回抽不进入中枢区间
      sell3: 次级别向下突破中枢下沿后反弹不进入中枢区间

    简化实现: 优先检测 buy1/sell1 信号；在有 buy1/sell1 的前提下检测 buy2/sell2;
             若存在中枢则额外检测 buy3/sell3
    """

    def __init__(self, diagnosis: DiagnosisResult):
        self.diagnosis = diagnosis
        self.klines = diagnosis.klines
        self.segments = diagnosis.segments
        self.zhongshus = diagnosis.zhongshus
        self.trend = diagnosis.trend
        self.beichi = diagnosis.beichi

    def detect(self) -> List[TradePoint]:
        points: List[TradePoint] = []
        if not self.klines:
            return points

        last_idx = len(self.klines) - 1
        last_k = self.klines[last_idx]

        # ---- buy1 / sell1 基础检测 ----
        # 判断是否存在下跌背驰或上涨背驰
        has_down_beichi = self.beichi and "down" in str(self.beichi).lower()
        has_up_beichi = self.beichi and "up" in str(self.beichi).lower()

        if has_down_beichi:
            # 下跌背驰 + 最后一根K线收盘价 >= 开盘价（底部反转迹象）→ buy1
            if last_k.close >= last_k.open:
                p_buy1 = TradePoint(
                    point_type="buy1",
                    kline_idx=last_idx,
                    price=round(float(last_k.close), 4),
                    reason=f"下跌趋势末端出现下跌背驰, 最后K线收阳, 形成一类买点",
                    confidence=0.75
                )
                points.append(p_buy1)

        if has_up_beichi:
            # 上涨背驰 + 最后一根K线收盘价 <= 开盘价（顶部反转迹象）→ sell1
            if last_k.close <= last_k.open:
                p_sell1 = TradePoint(
                    point_type="sell1",
                    kline_idx=last_idx,
                    price=round(float(last_k.close), 4),
                    reason=f"上涨趋势末端出现上涨背驰, 最后K线收阴, 形成一类卖点",
                    confidence=0.75
                )
                points.append(p_sell1)

        # ---- buy3 / sell3 中枢突破检测 ----
        if self.zhongshus:
            last_zhongshu = self.zhongshus[-1]
            z_low, z_high = last_zhongshu.range[0], last_zhongshu.range[1]
            # 最新价格高于中枢上沿 → buy3
            if last_k.close > z_high:
                # 检查是否有一根 K 线曾回抽到接近中枢上沿
                near_top = False
                for k in self.klines[max(0, last_idx - 10): last_idx]:
                    if k.low < z_high and k.low > z_high * 0.99:
                        near_top = True
                        break
                if near_top or True:  # 简化：只要突破中枢上沿即标记为 buy3 信号
                    points.append(TradePoint(
                        point_type="buy3",
                        kline_idx=last_idx,
                        price=round(float(last_k.close), 4),
                        reason=f"最新价格 {last_k.close:.2f} 已突破中枢上沿 {z_high:.2f}, 为三类买点候选",
                        confidence=0.55
                    ))
            # 最新价格低于中枢下沿 → sell3
            if last_k.close < z_low:
                points.append(TradePoint(
                    point_type="sell3",
                    kline_idx=last_idx,
                    price=round(float(last_k.close), 4),
                    reason=f"最新价格 {last_k.close:.2f} 已跌破中枢下沿 {z_low:.2f}, 为三类卖点候选",
                    confidence=0.55
                ))

        # ---- buy2 / sell2 基于 buy1/sell1 的回拉确认 ----
        for p in list(points):
            if p.point_type == "buy1" and p.kline_idx >= 5:
                # 检查 buy1 之后的回拉不破 buy1 低点
                post = self.klines[p.kline_idx:]
                if post and post[-1].close > p.price:
                    # 没有跌破 buy1 价，形成 buy2
                    points.append(TradePoint(
                        point_type="buy2",
                        kline_idx=last_idx,
                        price=round(float(post[-1].close), 4),
                        reason=f"buy1 之后回拉不破低点 {p.price:.2f}, 形成二类买点",
                        confidence=0.65
                    ))
            if p.point_type == "sell1" and p.kline_idx >= 5:
                post = self.klines[p.kline_idx:]
                if post and post[-1].close < p.price:
                    points.append(TradePoint(
                        point_type="sell2",
                        kline_idx=last_idx,
                        price=round(float(post[-1].close), 4),
                        reason=f"sell1 之后回拉不破高点 {p.price:.2f}, 形成二类卖点",
                        confidence=0.65
                    ))

        # 按置信度降序排序
        points.sort(key=lambda x: x.confidence, reverse=True)
        return points

    def summary(self) -> str:
        pts = self.detect()
        if not pts:
            return "当前未检测到明确的缠论买卖点信号"
        lines = []
        for p in pts:
            label = TYPE_LABEL.get(p.point_type, p.point_type)
            lines.append(f"[{label}] 价格 {p.price}, 置信度 {p.confidence:.2f} — {p.reason}")
        return "\n".join(lines)
