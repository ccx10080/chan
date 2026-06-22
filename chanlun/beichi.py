"""
chanlun/beichi.py
===================
背驰检测器（扩展版：区分趋势背驰 vs 盘整背驰）。

缠论背驰 = 对同级别、同方向的"走势段"动能进行对比。核心规则：

  1) 盘整背驰（PanZheng / consolidation divergence）：
     * 当前走势段没有出现两个及以上"同向中枢"；
     * 仅在"同一个中枢"内部进行"两同向段"对比；
     * 若最新同向段 price × time 的"动能" ≤ 前面某同向段 * 0.8，
       则视为"盘整背驰"。
  2) 趋势背驰（QuShi / trend divergence）：
     * 当前走势段包含了"两个及以上同向中枢"（典型的趋势走势：
       "上 + 中枢 + 上 + 中枢 + 上" 或 "下 + 中枢 + 下 + 中枢 + 下"）；
     * 且最新同向段的价格动能 ≤ 前一条同向段 * 0.8；
     * 此时为"趋势背驰"，是真正意义上的"大级别反转信号"。

对外输出：
  - "up趋势背驰" / "down趋势背驰"（优先级更高）；
  - "up盘整背驰" / "down盘整背驰"（否则）；
  - None（不满足背驰条件）。
"""
from typing import List, Optional, Tuple
from chanlun.models import Segment, Zhongshu


class BeichiDetector:
    """背驰检测器 —— 区分趋势背驰 / 盘整背驰。

    用法 1（推荐）: `BeichiDetector(segments, zhongshus=...)`
           — 提供中枢信息后，可以明确区分趋势背驰 vs 盘整背驰。
    用法 2（兼容原 API）: `BeichiDetector(segments)`
           — 仅使用 segment 本身，将所有信号降级为"盘整背驰"。
    """

    # 动能衰减阈值（0.8 表示最新段 ≤ 前一段的 80%）
    WEAKEN_THRESHOLD = 0.8

    def __init__(
        self,
        segments: List[Segment],
        zhongshus: Optional[List[Zhongshu]] = None,
    ):
        self.segments = segments
        self.zhongshus = zhongshus or []

    # ---------- 工具函数 ----------
    def _segment_energy(self, seg: Segment) -> float:
        """线段动能 = 价格范围 × 长度；若 high==low 则退化使用 start/end 索引跨度。"""
        if float(seg.high) > float(seg.low):
            price = abs(float(seg.high) - float(seg.low))
        else:
            price = float(abs(int(seg.end) - int(seg.start))) + 1.0
        length = max(1, int(seg.end) - int(seg.start))
        return price * length

    def _segments_in_zhongshu(self, zs: Zhongshu) -> List[Segment]:
        """返回时间范围属于 zs 内的线段列表。"""
        return [
            s for s in self.segments
            if int(s.start) >= int(zs.start) and int(s.end) <= int(zs.end)
        ]

    def _count_same_direction_zhongshus(
        self, direction: str
    ) -> int:
        """统计与 direction 相同的中枢数量。"""
        return sum(1 for z in self.zhongshus if z.direction == direction)

    # ---------- 主判定 ----------
    def _scan_same_direction_pairs(
        self, direction: str
    ) -> Optional[Tuple[Segment, Segment]]:
        """从末尾逆序寻找最近的两个同向段（中间可能夹有反向段）。"""
        segs = [s for s in self.segments if s.direction == direction]
        if len(segs) < 2:
            return None
        latest = segs[-1]
        prev = segs[-2]
        return prev, latest

    def detect(self) -> Optional[str]:
        """对外主接口：返回 'up趋势背驰' / 'down趋势背驰' / 'up盘整背驰' / 'down盘整背驰' / None。"""
        segments = self.segments
        if len(segments) < 3:
            return None

        # 1) 先找到最近一个"同向段对"（以最后一条段为起点）
        last_seg = segments[-1]
        target_direction = last_seg.direction
        pair = self._scan_same_direction_pairs(target_direction)
        if pair is None:
            return None
        prev, latest = pair

        # 2) 动能是否"明显衰减"
        prev_energy = self._segment_energy(prev)
        latest_energy = self._segment_energy(latest)
        if latest_energy > prev_energy * self.WEAKEN_THRESHOLD:
            # 最新同向段动能并未明显减弱 → 不构成背驰
            return None

        # 3) 区分趋势背驰 vs 盘整背驰
        #    - 若该方向的同向中枢数 ≥ 2 → 趋势背驰（更强信号）
        #    - 否则 → 盘整背驰
        same_dir_zs_count = self._count_same_direction_zhongshus(target_direction)
        if same_dir_zs_count >= 2:
            beichi_type = "趋势背驰"
        else:
            beichi_type = "盘整背驰"

        return f"{target_direction}{beichi_type}"

    # ---------- 辅助：返回结构化信息 ----------
    def detail(self) -> Optional[dict]:
        """返回更详细的背驰信息 dict，便于调试/展示。

        {
          "direction": "up" / "down",
          "beichi_type": "趋势背驰" / "盘整背驰",
          "prev_energy": float,
          "latest_energy": float,
          "same_direction_zhongshu_count": int,
        }
        """
        segments = self.segments
        if len(segments) < 3:
            return None
        last_seg = segments[-1]
        target_direction = last_seg.direction
        pair = self._scan_same_direction_pairs(target_direction)
        if pair is None:
            return None
        prev, latest = pair
        prev_energy = self._segment_energy(prev)
        latest_energy = self._segment_energy(latest)
        if latest_energy > prev_energy * self.WEAKEN_THRESHOLD:
            return None
        same_dir_zs_count = self._count_same_direction_zhongshus(target_direction)
        beichi_type = "趋势背驰" if same_dir_zs_count >= 2 else "盘整背驰"
        return {
            "direction": target_direction,
            "beichi_type": beichi_type,
            "prev_energy": round(prev_energy, 4),
            "latest_energy": round(latest_energy, 4),
            "same_direction_zhongshu_count": same_dir_zs_count,
        }
