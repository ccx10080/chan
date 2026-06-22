"""
chanlun/zhongshu_v2.py
========================
严格版中枢识别器（扩展版）。

相对于基础版，这里增加了三项"结合律"相关的高级处理：

  1) 基础识别：三段方向交替 + 三段价格重叠；
  2) 中枢延伸（extension）：后续同向线段若价格继续进入当前中枢区间，
     就把当前中枢的"时间/价格范围延伸；
  3) 中枢扩展（expansion）：相邻的两个中枢的高/低点相互触碰（即后一个中枢
     回撤到前一个中枢的价格区间），视为"同一高一级别中枢"；
  4) 升级中枢（higher-level zhongshu）：若延伸后单个中枢包含的线段数量 ≥9，
     则该中枢可以"升级为高一级别中枢"（缠论中 9 段 自动升级）。

对外输出的 `Zhongshu` 对象中：
  - `level` 字段标记级别（1=本级，2=高一级）；
  - `segment_count` 字段标记该中枢实际覆盖的线段数；
  - `zhongshu_type` 取值 `normal / extension / expansion / higher`。

"""
from typing import List
from chanlun.models import Segment, KLine, Zhongshu


class ZhongshuDetectorV2:
    """严格版中枢识别器 —— 基于"连续三线段 + 方向校验 + 延伸/扩展/升级"。"""

    # 升级阈值：延伸后达到此值 → 升级为高一级别中枢
    UPGRADE_SEGMENT_THRESHOLD = 9
    # 扩展价格重叠比例
    EXPANSION_OVERLAP_RATIO = 0.5

    def __init__(self, segments: List[Segment], klines: List[KLine]):
        self.segments = segments
        self.klines = klines

    # ---------- 工具 ----------
    @staticmethod
    def _seg_price_range(seg: Segment, klines: List[KLine]) -> (float, float):
        """返回线段覆盖 K 线的实际 [最低, 最高] 价格区间。"""
        if float(seg.high) > float(seg.low):
            return float(seg.low), float(seg.high)
        s = max(0, int(seg.start))
        e = min(len(klines) - 1, int(seg.end))
        if e < s or len(klines) == 0:
            # 退化：用 start/end 索引充当"假价格"，便于结构测试
            base = float(s + e) / 2.0
            return base - 1.0, base + 1.0
        lows = [float(klines[i].low) for i in range(s, e + 1)]
        highs = [float(klines[i].high) for i in range(s, e + 1)]
        return min(lows), max(highs)

    # ---------- 1) 基础三段中枢识别 ----------
    def _scan_triplets(self) -> List[Zhongshu]:
        segments = self.segments
        klines = self.klines
        if len(segments) < 3 or len(klines) < 5:
            return []

        seg_price_ranges: List[(float, float)] = [
            self._seg_price_range(seg, klines) for seg in segments
        ]

        raw: List[Zhongshu] = []
        n = len(segments)
        for i in range(n - 2):
            s1, s2, s3 = segments[i], segments[i + 1], segments[i + 2]
            # 方向严格交替：下-上-下 或 上-下-上
            if not (s1.direction == s3.direction and s1.direction != s2.direction):
                continue
            r1, r2, r3 = seg_price_ranges[i], seg_price_ranges[i + 1], seg_price_ranges[i + 2]
            overlap_low = max(r1[0], r2[0], r3[0])
            overlap_high = min(r1[1], r2[1], r3[1])
            if overlap_high <= overlap_low:
                continue
            # 中枢方向：第一段 direction=down 表示 "下-上-下结构。
            # 按缠论习惯，三段下上中下，中枢内（）。
            direction = "up" if s1.direction == "down" else "down"
            raw.append(Zhongshu(
                start=s1.start,
                end=s3.end,
                range=[round(overlap_low, 6), round(overlap_high, 6)],
                direction=direction,
                is_extension=False,
                level=1,
                segment_count=3,
                zhongshu_type="normal",
            ))
        return raw

    # ---------- 2) 中枢延伸（extension） ----------
    def _apply_extension(self, zs_list: List[Zhongshu]) -> List[Zhongshu]:
        """对所有中枢应用"延伸"规则：
        相邻同向 + 价格区间相交（或仅轻微错开） → 合并为一条更长的中枢。
        segment_count 累加，为后续"升级中枢"做准备。
        """
        if len(zs_list) < 2:
            return zs_list
        merged: List[Zhongshu] = [zs_list[0]]
        for z in zs_list[1:]:
            last = merged[-1]
            # 同向 + 价格相交 才允许合并
            if last.direction != z.direction:
                merged.append(z)
                continue
            z_low, z_high = z.range[0], z.range[1]
            l_low, l_high = last.range[0], last.range[1]
            price_intersect = (z_low <= l_high) and (z_high >= l_low)
            if not price_intersect:
                merged.append(z)
                continue
            new_start = min(last.start, z.start)
            new_end = max(last.end, z.end)
            new_low = min(l_low, z_low)
            new_high = max(l_high, z_high)
            merged[-1] = Zhongshu(
                start=new_start,
                end=new_end,
                range=[round(new_low, 6), round(new_high, 6)],
                direction=last.direction,
                is_extension=True,
                level=last.level,
                segment_count=last.segment_count + z.segment_count,
                zhongshu_type="extension",
            )
        return merged

    # ---------- 3) 中枢扩展（expansion） ----------
    def _apply_expansion(self, zs_list: List[Zhongshu]) -> List[Zhongshu]:
        """对相邻但不同向/同向但已延伸中枢, 若它们价格重叠度超过阈值 → 合并为"扩展中枢"。
        这对应缠论中"两个中枢被认为是同一个大级别的"
        逻辑：
        """
        if len(zs_list) < 2:
            return zs_list
        final: List[Zhongshu] = [zs_list[0]]
        for z in zs_list[1:]:
            last = final[-1]
            z_low, z_high = z.range[0], z.range[1]
            l_low, l_high = last.range[0], last.range[1]
            price_overlap_low = max(z_low, l_low)
            price_overlap_high = min(z_high, l_high)
            if price_overlap_high <= price_overlap_low:
                # 不相交, 直接加入
                final.append(z)
                continue
            total_low = min(z_low, l_low)
            total_high = max(z_high, l_high)
            overlap_ratio = 0.0
            if total_high - total_low > 0:
                overlap_ratio = (price_overlap_high - price_overlap_low) / (total_high - total_low)
            # 时间相邻也作为辅助判定
            if overlap_ratio >= self.EXPANSION_OVERLAP_RATIO or (z.start - last.end) <= 3:
                # 满足其中一项即可作为"扩展中枢"
                merged = Zhongshu(
                    start=min(last.start, z.start),
                    end=max(last.end, z.end),
                    range=[round(total_low, 6), round(total_high, 6)],
                    direction=last.direction,
                    is_extension=True,
                    level=last.level,
                    segment_count=last.segment_count + z.segment_count,
                    zhongshu_type="expansion",
                )
                final[-1] = merged
            else:
                final.append(z)
        return final

    # ---------- 4) 延伸/扩展升级（higher）升级中枢 ----------
    def _apply_upgrade(self, zs_list: List[Zhongshu]) -> List[Zhongshu]:
        """若某中枢的 segment_count 超过阈值(>=9) → 级别从1提升为更高，。
        这对应缠论对升级中枢"规则。
        """
        upgraded: List[Zhongshu] = []
        for z in zs_list:
            if z.segment_count >= self.UPGRADE_SEGMENT_THRESHOLD:
                upgraded.append(Zhongshu(
                    start=z.start,
                    end=z.end,
                    range=[round(z.range[0], 6), round(z.range[1], 6)],
                    direction=z.direction,
                    is_extension=True,
                    level=z.level + 1,
                    segment_count=z.segment_count,
                    zhongshu_type="higher",
                ))
            else:
                upgraded.append(z)
        return upgraded

    # ---------- 对外主接口 ----------
    def detect(self) -> List[Zhongshu]:
        """对线段列表执行：基础识别 → 延伸 → 扩展 → 升级 四步流程
        """
        raw = self._scan_triplets()
        extended = self._apply_extension(raw)
        expansion = self._apply_expansion(extended)
        upgraded = self._apply_upgrade(expansion)
        return upgraded

    # ---------- 工具：中枢强度 ----------
    def compute_strength(self, zs: List[Zhongshu]) -> List[float]:
        """中枢强度 = (high - low) / midpoint, 用于多级别对比。"""
        strengths = []
        for z in zs:
            low, high = z.range[0], z.range[1]
            mid = (low + high) / 2.0
            if mid > 0:
                strengths.append(round((high - low) / mid, 6))
            else:
                strengths.append(0.0)
        return strengths
