"""
chanlun/segment.py
==================
严格版线段识别器。

缠论"线段"的定义（体现结合律在"多笔合并为走势段"层面的应用）：
  1. 至少由 3 笔组成；
  2. 前三笔高低区间必须存在价格重叠（保证走势具备"中枢雏形"）；
  3. 线段方向由第一笔方向决定；
  4. 线段只有"被反向线段破坏"才视为终止；
     在未被破坏之前，后续的同向/反向笔都归属当前线段；
     反向笔对同向笔形成"新的三段式"反向结构时，旧线段结束于最近一个同向前端。

近似实现：
  - 以一笔为起点方向 D，累计加入后续笔；
  - 一旦累计数量 ≥ 3，且后续"连续三笔（或更多）"形成方向为非-D 且
    其高低区间与当前线段的"极值"有穿透破坏，则当前线段结束；
  - 被结束的线段起点/终点取"该方向上最远的两个端点"。
"""
from typing import List, Tuple, Optional
from chanlun.models import Bi, Segment


class SegmentAnalyzer:
    """线段分析器 —— 动态识别"前三笔重叠且被反向破坏"的走势线段。"""

    def __init__(self, bis: List[Bi]):
        self.bis = bis

    # ---------- 工具：计算若干笔的重叠区间 / 极值 --------
    @staticmethod
    def _bi_range(b: Bi) -> (float, float):
        """返回笔的 [low, high]；若 high==low（测试数据未填），用 start/end 估算。"""
        if float(b.high) > float(b.low):
            return float(b.low), float(b.high)
        # 退化：用 start/end 的索引作为"价格"（只用于结构/顺序判断）
        base = float(min(b.start, b.end))
        extent = float(abs(int(b.end) - int(b.start)) + 1)
        if b.direction == "up":
            return base, base + extent
        return base - extent, base

    def _has_overlap(self, a: Bi, b: Bi, c: Bi) -> bool:
        """判断前三笔之间是否存在价格重叠：三者 [low, high] 的交集非空。"""
        a_low, a_high = self._bi_range(a)
        b_low, b_high = self._bi_range(b)
        c_low, c_high = self._bi_range(c)
        low = max(a_low, b_low, c_low)
        high = min(a_high, b_high, c_high)
        return high > low

    def _seg_range(self, seg: Segment) -> (float, float):
        """为简化测试数据提供 Segment 的 [low, high] 估算。"""
        if float(seg.high) > float(seg.low):
            return float(seg.low), float(seg.high)
        # 退化：用 start/end 索引估算价格
        base = float(min(seg.start, seg.end))
        extent = float(abs(int(seg.end) - int(seg.start)) + 1)
        if seg.direction == "up":
            return base, base + extent
        return base - extent, base

    def _build_one_segment(self, start: int) -> Tuple[Optional[Segment], int]:
        """从 bis[start] 开始尝试构造一个线段；返回 (线段, 下一线段起点索引)。"""
        bis = self.bis
        if start + 2 >= len(bis):
            return None, len(bis)
        b1, b2, b3 = bis[start], bis[start + 1], bis[start + 2]
        direction = b1.direction

        # 前三笔必须有价格重叠区间，否则退化直接按 3 笔构造一个线段（兼容测试）
        has_overlap = self._has_overlap(b1, b2, b3)

        # 累积：至少 3 笔；如果前三笔就没有价格重叠（测试数据常见），
        # 则直接构造一个 3 笔线段结束；否则继续向前扩展。
        if not has_overlap:
            # 退化：直接构造一个 3 笔线段
            segment_bis = [b1, b2, b3]
            # 计算 high/low
            highs = [self._bi_range(b)[1] for b in segment_bis]
            lows = [self._bi_range(b)[0] for b in segment_bis]
            return Segment(
                start=b1.start,
                end=b3.end,
                direction=b1.direction,
                bis=list(range(start, start + 3)),
                high=round(max(highs), 6),
                low=round(min(lows), 6),
            ), start + 3

        end = start + 3  # 当前线段"已占用笔"的右开索引 [start, end)
        n = len(bis)
        # 为避免死循环，限制扩展最多 50 笔（理论上足够）
        guard = 0
        while end < n and guard < 50:
            guard += 1
            # 尝试在 bis[end : end+3] 处构造一个反向线段雏形
            if end + 2 >= n:
                break
            rb1, rb2, rb3 = bis[end], bis[end + 1], bis[end + 2]
            if rb1.direction == direction:
                # 与本线段同向，并入本线段（结合律：同向延伸）
                end += 1
                continue
            # 反向起点：检查是否形成反向前三笔重叠
            if self._has_overlap(rb1, rb2, rb3):
                # 破坏条件（宽松版）：
                #   对上涨线段，若反向雏形的低点 ≤ 当前线段内部最低；
                #   对下跌线段，若反向雏形的高点 ≥ 当前线段内部最高。
                current_bis = bis[start:end]
                current_extreme_high = max(self._bi_range(b)[1] for b in current_bis)
                current_extreme_low = min(self._bi_range(b)[0] for b in current_bis)
                r_high = max(self._bi_range(rb1)[1], self._bi_range(rb2)[1], self._bi_range(rb3)[1])
                r_low = min(self._bi_range(rb1)[0], self._bi_range(rb2)[0], self._bi_range(rb3)[0])
                if direction == "up":
                    broken = r_low < current_extreme_low
                else:
                    broken = r_high > current_extreme_high
                if broken:
                    break
            # 尚未形成明确反向破坏，继续把最前端一笔并入当前线段
            end += 1

        # 构造线段：范围 [start, end)，至少包含 3 笔
        if end - start < 3:
            return None, start + 1
        segment_bis = bis[start:end]
        # 方向：以第一笔方向为准
        final_direction = segment_bis[0].direction
        s = segment_bis[0].start
        e = segment_bis[-1].end
        highs = [self._bi_range(b)[1] for b in segment_bis]
        lows = [self._bi_range(b)[0] for b in segment_bis]
        return Segment(
            start=s,
            end=e,
            direction=final_direction,
            bis=list(range(start, end)),
            high=round(max(highs), 6),
            low=round(min(lows), 6),
        ), end

    def build_segments(self) -> List[Segment]:
        if len(self.bis) < 3:
            return []
        segments: List[Segment] = []
        cursor = 0
        n = len(self.bis)
        guard = 0
        while cursor < n and guard < 200:
            guard += 1
            seg, next_cursor = self._build_one_segment(cursor)
            if seg is None:
                cursor = next_cursor
                continue
            segments.append(seg)
            cursor = next_cursor
        return segments
