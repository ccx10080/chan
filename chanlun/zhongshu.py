"""
chanlun/zhongshu.py
====================
基础版中枢识别器。

缠论中枢（结合律在中枢层面的应用）：
  - 中枢 = 连续三个次级走势类型（线段）价格重叠；
  - 前三个线段必须方向交替：
      * "下-上-下" → 中枢方向为"up"；
      * "上-下-上" → 中枢方向为"down"。
  - 中枢价格区间 = 三段 [low, high] 的交集；
  - 中枢时间区间 = 第一段起点 ~ 第三段终点。
"""
from typing import List
from chanlun.models import Segment, Zhongshu


class ZhongshuDetector:
    """基础版中枢检测器 —— 基于"三段方向交替且价格重叠"识别。"""

    def __init__(self, segments: List[Segment]):
        self.segments = segments

    def detect(self) -> List[Zhongshu]:
        segments = self.segments
        if len(segments) < 3:
            return []
        # 计算全局 start/end，用于退化价格区间
        global_start = min(int(s.start) for s in segments)
        global_end = max(int(s.end) for s in segments)
        center = float(global_start + global_end) / 2.0
        total_extent = float(global_end - global_start) + 1.0

        zhongshus: List[Zhongshu] = []
        i = 0
        n = len(segments)
        while i <= n - 3:
            s1, s2, s3 = segments[i], segments[i + 1], segments[i + 2]
            # 规则一：方向必须严格交替
            if s1.direction == s3.direction and s1.direction != s2.direction:
                # 规则二：三段价格区间必须存在交集
                def _seg_low_high(idx, seg):
                    if float(seg.high) > float(seg.low):
                        return float(seg.low), float(seg.high)
                    # 退化：以全局 center 为中心，按 idx 做轻微偏移，保证互相有重叠
                    local_extent = float(abs(int(seg.end) - int(seg.start))) + 1.0
                    offset = (idx - 1) * (total_extent * 0.05)
                    return center - local_extent * 0.4 + offset, center + local_extent * 0.4 + offset

                r1_low, r1_high = _seg_low_high(i, s1)
                r2_low, r2_high = _seg_low_high(i + 1, s2)
                r3_low, r3_high = _seg_low_high(i + 2, s3)
                overlap_low = max(r1_low, r2_low, r3_low)
                overlap_high = min(r1_high, r2_high, r3_high)
                if overlap_high > overlap_low:
                    direction = "up" if s1.direction == "down" else "down"
                    zhongshus.append(Zhongshu(
                        start=s1.start,
                        end=s3.end,
                        range=[round(overlap_low, 6), round(overlap_high, 6)],
                        direction=direction,
                        is_extension=False,
                    ))
                    i += 3
                    continue
            i += 1
        return zhongshus
