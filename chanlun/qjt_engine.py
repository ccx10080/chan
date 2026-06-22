import itertools
from typing import List, Dict, Optional
from chanlun.models import LevelData, QJTSignal


class QJTEngine:
    """区间套判定引擎"""

    def detect_signals(self, levels: Dict[str, LevelData]) -> List[QJTSignal]:
        signals = []
        level_keys = ["daily", "30m", "5m", "1m"]
        available = [k for k in level_keys if k in levels]
        if len(available) < 2:
            return signals

        for r in range(len(available), 1, -1):
            for combo in itertools.combinations(available, r):
                level_data_list = [levels[lv] for lv in combo]

                # 阶段1：价格区间交集
                ranges = [ld.key_price_range for ld in level_data_list]
                intersection = self._price_intersection(ranges)
                if intersection is None:
                    continue

                smallest_range = min(r[1] - r[0] for r in ranges)
                inter_size = intersection[1] - intersection[0]
                if smallest_range > 0:
                    price_score = min(1.0, inter_size / smallest_range)
                else:
                    price_score = 0.5
                price_score = round(price_score, 4)

                # 阶段2：方向一致性
                directions = [ld.direction for ld in level_data_list]
                if None in directions:
                    continue
                direction_score = 1.0 if len(set(directions)) == 1 else 0.0
                if direction_score == 0.0:
                    continue
                final_direction = directions[0]

                # 阶段3：时间区间匹配
                time_score = self._time_containment_score(list(combo), levels)
                time_score = round(time_score, 4)

                # 综合置信度
                confidence = round(
                    price_score * 0.35 + direction_score * 0.35 + time_score * 0.30,
                    4
                )
                if confidence < 0.5:
                    continue

                # 构造信号描述
                level_names = "、".join(levels[lv].level_name_cn for lv in combo)
                precise_price = round((intersection[0] + intersection[1]) / 2.0, 4)
                desc = (f"{len(combo)}级别（{level_names}）嵌套"
                        f"{'买入' if final_direction == 'buy' else '卖出'}信号，"
                        f"价格交集区间 {intersection[0]:.4f} - {intersection[1]:.4f}，"
                        f"精确价位 {precise_price}")

                signals.append(QJTSignal(
                    levels_involved=list(combo),
                    direction=final_direction,
                    price_intersection=intersection,
                    confidence=confidence,
                    price_score=price_score,
                    direction_score=direction_score,
                    time_score=time_score,
                    description=desc,
                    precise_price=precise_price
                ))

        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals

    def _price_intersection(self, ranges: List[List[float]]) -> Optional[List[float]]:
        """计算多个价格区间的交集"""
        if not ranges:
            return None
        low = max(r[0] for r in ranges)
        high = min(r[1] for r in ranges)
        if high <= low:
            return None
        return [round(low, 4), round(high, 4)]

    def _time_containment_score(self, combo: List[str], levels: Dict[str, LevelData]) -> float:
        """计算时间区间包含关系得分"""
        if len(combo) < 2:
            return 1.0
        scores = []
        for i in range(len(combo) - 1):
            outer_lv = combo[i]
            inner_lv = combo[i + 1]
            outer_total = len(levels[outer_lv].klines)
            inner_total = len(levels[inner_lv].klines)
            if outer_total == 0 or inner_total == 0:
                scores.append(0.5)
                continue
            outer_start_ratio = levels[outer_lv].key_time_range[0] / outer_total
            outer_end_ratio = levels[outer_lv].key_time_range[1] / outer_total
            inner_start_ratio = levels[inner_lv].key_time_range[0] / inner_total
            inner_end_ratio = levels[inner_lv].key_time_range[1] / inner_total
            overlap = max(0.0, min(inner_end_ratio, outer_end_ratio) - max(inner_start_ratio, outer_start_ratio))
            scores.append(min(1.0, max(0.2, overlap * 2.0)))
        return round(sum(scores) / len(scores), 4) if scores else 0.5
