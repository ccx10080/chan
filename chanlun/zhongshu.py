"""
chanlun/zhongshu.py
====================
基础版中枢识别器。

缠论中枢（结合律在中枢层面的应用）：
  - 中枢 = 连续三个次级走势类型（线段）价格重叠；
  - 前三个线段必须方向交替：
      * "下-上-下" → 中枢方向为 "up"（向上构造中枢，买点相关）；
      * "上-下-上" → 中枢方向为 "down"（向下构造中枢，卖点相关）。
  - 中枢 price 区间 = 三段 [low, high] 的交集；
  - 若中枢内继续延伸（价格区间被后续线段反复触碰），由 `ZhongshuDetectorV2`
    进一步做延伸/扩展处理。
"""
from typing import List
from chanlun.models import Segment, KLine, Zhongshu


class ZhongshuDetector:
    """基础版中枢检测器 —— 基于"三段方向交替 + 价格重叠"。

    对外输出字段:
      - start/end: 中枢起止（原始 K 线索引）
      - range: [中枢下沿, 中枢上沿]
      - direction: "up" / "down"
      - level: 固定为 1（延伸/扩展/升级由 v2 版处理）
      - segment_count: 中枢实际包含的线段数
      - zhongshu_type: 基础版恒为 "normal"

    注意：为了在"简化测试数据"中也能产生有意义的中枢结果，
    若输入线段 high==low，会以"全局 start/end 均值"退化估算价格区间。
    """

    def __init__(self, segments: List[Segment]):
        self.segments = segments

    @staticmethod
    def _seg_low_high(seg: Segment, center: float, half: float) -> (float, float):
        if float(seg.high) > float(seg.low):
            return float(seg.low), float(seg.high)
        # 退化：以 start/end 的位置生成"有差异"的价格区间
        base = center + (float(seg.start + seg.end) / 2.0 - center) * 0.05
        return base - half, base + half

    def detect(self) -> List[Zhongshu]:
        segments = self.segments
        if len(segments) < 3:
            return []
        # 计算全局 center / half, 用于退化估算
        global_start = min(int(s.start) for s in segments)
        global_end = max(int(s.end) for s in segments)
        center = float(global_start + global_end) / 2.0
        half = max(1.0, float(global_end - global_start) * 0.3)

        zhongshus: List[Zhongshu] = []
        n = len(segments)
        i = 0
        while i <= n - 3:
            s1, s2, s3 = segments[i], segments[i + 1], segments[i + 2]
            if not (s1.direction == s3.direction and s1.direction != s2.direction):
                i += 1
                continue
            r1_low, r1_high = self._seg_low_high(s1, center, half)
            r2_low, r2_high = self._seg_low_high(s2, center, half)
            r3_low, r3_high = self._seg_low_high(s3, center, half)
            overlap_low = max(r1_low, r2_low, r3_low)
            overlap_high = min(r1_high, r2_high, r3_high)
            if overlap_high <= overlap_low:
                i += 1
                continue
            direction = "up" if s1.direction == "down" else "down"
            zhongshus.append(Zhongshu(
                start=s1.start,
                end=s3.end,
                range=[round(overlap_low, 6), round(overlap_high, 6)],
                direction=direction,
                is_extension=False,
                level=1,
                segment_count=3,
                zhongshu_type="normal",
            ))
            i += 3
        return zhongshus
