"""
chanlun/zhongshu_v2.py
========================
严格版中枢识别器。

在基础版基础上进一步引入结合律相关处理：
  1) 方向校验：三段必须方向交替（如 "down-up-down" 或 "up-down-up"）；
  2) 中枢延伸：后续线段若"价格仍在已有中枢区间内"，则将中枢时间与价格
     范围扩展（时间：取并集；价格：取各段价格区间的新交集上限与下限）；
  3) 中枢扩展：若"相邻的两个中枢"在时间上或价格上存在较大交集（比例
     超过阈值），则合并为一个更大级别的中枢（扩展）。
"""
from typing import List
from chanlun.models import Segment, KLine, Zhongshu


class ZhongshuDetectorV2:
    """严格版中枢识别器 —— 基于"连续三线段 + 方向校验 + 延伸与扩展"。"""

    def __init__(self, segments: List[Segment], klines: List[KLine]):
        self.segments = segments
        self.klines = klines

    # ---------- 基础：三段式中枢识别 ----------
    def _scan_triplets(self) -> List[Zhongshu]:
        segments = self.segments
        if len(segments) < 3 or len(self.klines) < 5:
            return []

        # 为每段计算基于实际 K 线的 [low, high]
        seg_price_ranges: List[(float, float)] = []
        for seg in segments:
            s = max(0, int(seg.start))
            e = min(len(self.klines) - 1, int(seg.end))
            if e < s:
                seg_price_ranges.append((float(seg.low), float(seg.high)))
            else:
                lows = [float(self.klines[i].low) for i in range(s, e + 1)]
                highs = [float(self.klines[i].high) for i in range(s, e + 1)]
                seg_price_ranges.append((min(lows), max(highs)))

        raw: List[Zhongshu] = []
        n = len(segments)
        for i in range(n - 2):
            s1, s2, s3 = segments[i], segments[i + 1], segments[i + 2]
            # 方向交替校验
            if not (s1.direction == s3.direction and s1.direction != s2.direction):
                continue
            r1, r2, r3 = seg_price_ranges[i], seg_price_ranges[i + 1], seg_price_ranges[i + 2]
            overlap_low = max(r1[0], r2[0], r3[0])
            overlap_high = min(r1[1], r2[1], r3[1])
            if overlap_high <= overlap_low:
                continue
            # 中枢方向：第一段 direction=down 表示中枢为"up"（构造买点中枢）
            direction = "up" if s1.direction == "down" else "down"
            raw.append(Zhongshu(
                start=s1.start,
                end=s3.end,
                range=[round(overlap_low, 6), round(overlap_high, 6)],
                direction=direction,
                is_extension=False,
            ))
        return raw

    # ---------- 延伸：中枢之间若相邻/接近则合并 ----------
    def _merge_extension(self, zs_list: List[Zhongshu]) -> List[Zhongshu]:
        if not zs_list:
            return zs_list
        merged: List[Zhongshu] = [zs_list[0]]
        for z in zs_list[1:]:
            last = merged[-1]
            # 判断时间范围是否相邻或有重叠（两个中枢时间间隔 < 5 根 K 线即认为可能延伸）
            time_overlap_ratio = 0.0
            span = max(z.end, last.end) - min(z.start, last.start)
            if span > 0:
                overlap = max(0, min(last.end, z.end) - max(z.start, last.start))
                time_overlap_ratio = overlap / span if span > 0 else 0

            # 判断价格区间是否相交（延伸要求价格仍有交集）
            price_intersect = (z.range[0] <= last.range[1]) and (z.range[1] >= last.range[0])

            # 判断是否属于同方向（同向延伸更有意义）
            same_direction = last.direction == z.direction

            if (time_overlap_ratio > 0.3 or (z.start - last.end) <= 2) and price_intersect and same_direction:
                # 合并为一个延伸中枢
                new_start = min(last.start, z.start)
                new_end = max(last.end, z.end)
                new_low = max(last.range[0], z.range[0])  # 交集：更严格的下限
                new_high = min(last.range[1], z.range[1])  # 交集：更严格的上限
                # 若交集为空，则取两段的并集（扩展级别）
                if new_high <= new_low:
                    new_low = min(last.range[0], z.range[0])
                    new_high = max(last.range[1], z.range[1])
                merged[-1] = Zhongshu(
                    start=new_start,
                    end=new_end,
                    range=[round(new_low, 6), round(new_high, 6)],
                    direction=last.direction,
                    is_extension=True,
                )
                continue
            merged.append(z)
        return merged

    # ---------- 扩展：相邻但不同方向的中枢合并（级别扩展） ----------
    def _merge_expansion(self, zs_list: List[Zhongshu]) -> List[Zhongshu]:
        if len(zs_list) < 2:
            return zs_list
        final: List[Zhongshu] = [zs_list[0]]
        for z in zs_list[1:]:
            last = final[-1]
            # 价格上若 50% 以上重叠，且时间上紧邻，则视作同一"大级别中枢"
            z_low = z.range[0]
            z_high = z.range[1]
            last_low = last.range[0]
            last_high = last.range[1]
            price_overlap_low = max(z_low, last_low)
            price_overlap_high = min(z_high, last_high)
            if price_overlap_high <= price_overlap_low:
                final.append(z)
                continue
            total_low = min(z_low, last_low)
            total_high = max(z_high, last_high)
            if total_high - total_low > 0:
                overlap_ratio = (price_overlap_high - price_overlap_low) / (total_high - total_low)
            else:
                overlap_ratio = 0
            if overlap_ratio >= 0.5 and (z.start - last.end) <= 3:
                merged = Zhongshu(
                    start=min(last.start, z.start),
                    end=max(last.end, z.end),
                    range=[round(total_low, 6), round(total_high, 6)],
                    direction=last.direction,
                    is_extension=True,
                )
                final[-1] = merged
            else:
                final.append(z)
        return final

    # ---------- 对外主接口 ----------
    def detect(self) -> List[Zhongshu]:
        raw = self._scan_triplets()
        extended = self._merge_extension(raw)
        return self._merge_expansion(extended)

    # ---------- 中枢强度计算 ----------
    def compute_strength(self, zs: List[Zhongshu]) -> List[float]:
        strengths = []
        for z in zs:
            low, high = z.range[0], z.range[1]
            mid = (low + high) / 2.0
            if mid > 0:
                strengths.append(round((high - low) / mid, 6))
            else:
                strengths.append(0.0)
        return strengths
