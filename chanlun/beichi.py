"""
chanlun/beichi.py
===================
背驰检测器（结合律升级版）。

缠论背驰核心前提：
  - 对比两段"同级别、同方向"的走势（这里采用"线段"级别作为基本单位）；
  - 对比的是两段同向走势的"价格动能"（高度）与"时间长度"的综合。

当前实现：
  - 对每个同向线段（相对上一个同向线段），若 price_height < previous * 0.8，
    则认为"力度减弱"，发出背驰信号；
  - `detect()` 返回 'up背驰' / 'down背驰' 或 None。
"""
from typing import List, Optional
from chanlun.models import Segment


class BeichiDetector:
    """背驰检测器 —— 对比同向线段价格动能减弱情况。"""

    def __init__(self, segments: List[Segment]):
        self.segments = segments

    def _segment_energy(self, seg: Segment) -> float:
        """线段动能 = price_span * length；若 high==low 则退化使用 start/end。"""
        if float(seg.high) > float(seg.low):
            price = abs(float(seg.high) - float(seg.low))
        else:
            # 退化：使用 start/end 的索引跨度作为"价格差"估算
            price = float(abs(int(seg.end) - int(seg.start))) + 1.0
        length = max(1, int(seg.end) - int(seg.start))
        return price * length

    def detect(self) -> Optional[str]:
        segments = self.segments
        if len(segments) < 3:
            return None
        # 找最近的同向线段（忽略中间反向）
        last_up: Optional[Segment] = None
        last_down: Optional[Segment] = None
        for seg in reversed(segments):
            if seg.direction == "up":
                if last_up is None:
                    last_up = seg
                else:
                    if self._segment_energy(seg) > self._segment_energy(last_up) * 0.8:
                        # 前一条同向线段动能更大 → 当前上攻段力度减弱 → 可能上涨背驰
                        return "up背驰"
                    break
            else:
                if last_down is None:
                    last_down = seg
                else:
                    if self._segment_energy(seg) > self._segment_energy(last_down) * 0.8:
                        return "down背驰"
                    break
        return None
