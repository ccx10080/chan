# chanlun/zhongshu_v2.py
# 增强型中枢识别：严格版三段价格重叠区域算法
from typing import List
from chanlun.models import Segment, KLine, Zhongshu


class ZhongshuDetectorV2:
    """
    严格版中枢识别：基于'连续三线段价格重叠区域'算法

    输入: segments: List[Segment], klines: List[KLine]
    输出: List[Zhongshu]

    算法:
      1) 对每条线段 seg_i，计算其实际 price range (seg_low, seg_high)
         - 取该线段覆盖的 K线: klines[seg.start ... seg.end]
         - seg_low = 该范围内 K线最低价的最小值
         - seg_high = 该范围内 K线最高价的最大值
      2) 考察每个连续三元组 (seg_i, seg_{i+1}, seg_{i+2})
         - 三段交集: overlap_low = max(seg_i.low, seg_{i+1}.low, seg_{i+2}.low)
           overlap_high = min(seg_i.high, seg_{i+1}.high, seg_{i+2}.high)
         - 若 overlap_high > overlap_low → 形成中枢
         - 中枢范围: start = seg_i.start, end = seg_{i+2}.end
         - 中枢 price range = [overlap_low, overlap_high]
      3) 合并相邻中枢（若时间范围重叠超过 50%）
      4) 计算中枢强度 level_strength = (high - low) / ((low + high)/2)
    """

    def __init__(self, segments: List[Segment], klines: List[KLine]):
        self.segments = segments
        self.klines = klines

    def detect(self) -> List[Zhongshu]:
        if len(self.segments) < 3 or len(self.klines) < 5:
            return []

        # 阶段1: 对每条线段计算价格范围
        seg_ranges = []
        for seg in self.segments:
            s = max(0, seg.start)
            e = min(len(self.klines) - 1, seg.end)
            if e < s:
                seg_ranges.append((None, None))
                continue
            lows = [self.klines[i].low for i in range(s, e + 1)]
            highs = [self.klines[i].high for i in range(s, e + 1)]
            seg_ranges.append((min(lows), (max(highs))))

        # 阶段2: 三元组扫描
        raw_zhongshus: List[Zhongshu] = []
        for i in range(len(self.segments) - 2):
            r1, r2, r3 = seg_ranges[i], seg_ranges[i + 1], seg_ranges[i + 2]
            if None in (r1[0], r2[0], r3[0]):
                continue
            overlap_low = max(r1[0], r2[0], r3[0])
            overlap_high = min(r1[1], r2[1], r3[1])
            if overlap_high <= overlap_low:
                continue
            seg_start = self.segments[i].start
            seg_end = self.segments[i + 2].end
            raw_zhongshus.append(Zhongshu(
                start=seg_start,
                end=seg_end,
                range=[round(overlap_low, 4), round(overlap_high, 4)]
            ))

        # 阶段3: 合并相邻中枢（时间范围重叠 > 50%）
        merged: List[Zhongshu] = []
        for z in raw_zhongshus:
            if not merged:
                merged.append(z)
                continue
            last = merged[-1]
            # 判断是否重叠
            overlap_start = max(last.start, z.start)
            overlap_end = min(last.end, z.end)
            if overlap_end > overlap_start:
                span = max(last.end, z.end) - min(last.start, z.start)
                if (overlap_end - overlap_start) / span > 0.5:
                    # 合并
                    new_start = min(last.start, z.start)
                    new_end = max(last.end, z.end)
                    new_low = min(last.range[0], z.range[0])
                    new_high = max(last.range[1], z.range[1])
                    merged[-1] = Zhongshu(start=new_start, end=new_end,
                                          range=[round(new_low, 4), round(new_high, 4)])
                    continue
            merged.append(z)

        return merged

    def compute_strength(self, zs: List[Zhongshu]) -> List[float]:
        """返回每个中枢的强度 (price_range / mid_price)"""
        strengths = []
        for z in zs:
            low, high = z.range[0], z.range[1]
            mid = (low + high) / 2.0
            if mid > 0:
                strengths.append(round((high - low) / mid, 6))
            else:
                strengths.append(0.0)
        return strengths
