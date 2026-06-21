from typing import List
from chanlun.models import KLine, FenXing, Bi


class BiAnalyzer:
    """笔分析器 - 从分型序列构建笔"""

    def __init__(self, klines: List[KLine], fenxings: List[FenXing]):
        self.klines = klines
        self.fenxings = fenxings

    def build_bis(self) -> List[Bi]:
        if len(self.fenxings) < 2:
            return []

        bis = []
        i = 0
        while i < len(self.fenxings) - 1:
            fx1 = self.fenxings[i]
            fx2 = self.fenxings[i + 1]
            if fx2.start_idx <= fx1.end_idx:
                i += 1
                continue
            kline_count = fx2.end_idx - fx1.start_idx + 1
            if kline_count < 5:
                i += 1
                continue
            if fx1.type == "ding" and fx2.type == "di":
                direction = "down"
            elif fx1.type == "di" and fx2.type == "ding":
                direction = "up"
            else:
                i += 1
                continue
            bis.append(Bi(start=fx1.peak_idx, end=fx2.peak_idx, direction=direction))
            i += 1
        return bis
