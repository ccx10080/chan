"""
chanlun/bi.py
=============
严格版笔识别器。

缠论中"笔"的形成规则（体现结合律在"分型取舍 + 笔回退组合"层面的应用）：
  1. 必须由"底分型 → 顶分型"或"顶分型 → 底分型"交替组成；
  2. 两个分型之间必须存在"不共用 K 线"的区间，且两者之间至少间隔 1 根
     原始 K 线（即总共 ≥ 5 根 K 线）；
  3. 若同方向分型连续出现（如 "ding, ding, di"），
     则按"保留更极端值并舍弃较弱者"的原则取舍（结合律）；
  4. 若"预构成笔"因某种原因不成立，
     则可与后续分型重新组合（例如：原先的"顶"被更新的更高顶取代）。

本模块采用"两次扫描 + 回退确认"：
  Scan 1：先强制把 `fenxings` 归化为严格顶底交替的序列（同方向取舍）。
  Scan 2：在交替序列上按"间隔 ≥ 1 根 K 线"的原则构造笔，
          若某一候选不成立，则回退并"用下一个同类型分型尝试"。
"""
from typing import List
from chanlun.models import KLine, FenXing, Bi


class BiAnalyzer:
    """笔分析器 —— 基于"包含处理后的分型"构造严格交替的笔序列。"""

    def __init__(self, klines: List[KLine], fenxings: List[FenXing]):
        self.klines = klines
        self.fenxings = fenxings

    # ---------- 规则一：归化为严格顶底交替序列 ----------
    def _normalize(self) -> List[FenXing]:
        if len(self.fenxings) < 2:
            return list(self.fenxings)
        normalized: List[FenXing] = [self.fenxings[0]]
        for fx in self.fenxings[1:]:
            last = normalized[-1]
            if fx.type == last.type:
                # 同方向连续出现：
                #   - 顶分型：保留价格较高者；
                #   - 底分型：保留价格较低者。
                if fx.type == "ding":
                    stronger = last if last.peak_price >= fx.peak_price else fx
                else:
                    stronger = last if last.peak_price <= fx.peak_price else fx
                # 区间取并集（结合律：同方向分型可以合并）
                normalized[-1] = FenXing(
                    type=stronger.type,
                    start_idx=min(last.start_idx, fx.start_idx),
                    peak_idx=stronger.peak_idx,
                    end_idx=max(last.end_idx, fx.end_idx),
                    peak_price=stronger.peak_price,
                )
            else:
                # 方向相反 → 直接新增
                normalized.append(fx)
        return normalized

    # ---------- 规则二：两分型之间必须存在"不共用"的 K 线区间 ----------
    @staticmethod
    def _can_form_bi(a: FenXing, b: FenXing) -> bool:
        """两分型是否满足笔的基本构成条件。

        缠论"笔"的简化规则：
          - 顶底分型之间不能共用 K 线（b.start_idx > a.end_idx）；
          - 两分型 peak 之间至少间隔 1 根 K 线（即 `b.peak_idx - a.peak_idx >= 2`）。
        """
        if b.peak_idx <= a.peak_idx:
            return False
        # 顶底之间至少间隔 1 根 K 线（不包括两根分型自身的 K 线）
        if b.peak_idx - a.peak_idx < 2:
            return False
        if b.start_idx <= a.end_idx:
            return False
        return True

    # ---------- 笔构造主流程 ----------
    def build_bis(self) -> List[Bi]:
        normalized = self._normalize()
        if len(normalized) < 2:
            return []

        bis: List[Bi] = []
        i = 0
        n = len(normalized)
        while i < n - 1:
            base = normalized[i]
            # 在后续分型中寻找"第一个与 base 方向相反且能构成笔"的分型；
            # 若其后还有同方向但更强的分型，可继续向前选（回退确认）。
            j_candidates = []
            for j in range(i + 1, n):
                if normalized[j].type == base.type:
                    # 同方向：跳过（因为已经是交替序列，这里理论上很少见）
                    continue
                j_candidates.append(j)
                if self._can_form_bi(base, normalized[j]):
                    # 找到第一个可用的即可；
                    # 但为了"回退确认"，我们再向后多探 1 个同方向分型，
                    # 若出现价格更强的，改用更强的（这是缠论"笔被笔破坏后
                    # 仍可按新分型重分"的近似实现）。
                    # ---- 尝试回退 ----
                    for k in range(j + 1, n):
                        if normalized[k].type != normalized[j].type:
                            break
                        # 同向且更极端？
                        if normalized[k].type == "ding":
                            better = normalized[k].peak_price > normalized[j].peak_price
                        else:
                            better = normalized[k].peak_price < normalized[j].peak_price
                        if better and self._can_form_bi(base, normalized[k]):
                            j = k
                        else:
                            break
                    end_fx = normalized[j]
                    direction = "up" if (base.type == "di" and end_fx.type == "ding") else "down"
                    s = min(base.peak_idx, end_fx.peak_idx)
                    e = max(base.peak_idx, end_fx.peak_idx)
                    highs = [float(self.klines[idx].high) for idx in range(s, e + 1)]
                    lows = [float(self.klines[idx].low) for idx in range(s, e + 1)]
                    bis.append(Bi(
                        start=base.peak_idx,
                        end=end_fx.peak_idx,
                        direction=direction,
                        high=round(max(highs), 6),
                        low=round(min(lows), 6),
                    ))
                    i = j
                    break
            else:
                # 从 base 出发没有能成笔的 → base 被放弃，向前移动
                i += 1

        return bis
