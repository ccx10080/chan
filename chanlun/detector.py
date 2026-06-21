from typing import List
from chanlun.models import KLine, FenXing


class FenXingDetector:
    """分型检测器 - 识别顶分型和底分型"""

    def __init__(self, klines: List[KLine]):
        self.klines = klines

    def detect(self) -> List[FenXing]:
        fenxings = []
        i = 1
        while i < len(self.klines) - 1:
            fx = self._check_fenxing(i)
            if fx:
                fenxings.append(fx)
                i = fx.end_idx + 1
            else:
                i += 1
        return fenxings

    def _check_fenxing(self, idx: int):
        if idx < 1 or idx >= len(self.klines) - 1:
            return None
        left = self.klines[idx - 1]
        mid = self.klines[idx]
        right = self.klines[idx + 1]

        if mid.high > left.high and mid.high > right.high:
            return FenXing(type="ding", start_idx=idx - 1, peak_idx=idx, end_idx=idx + 1)
        if mid.low < left.low and mid.low < right.low:
            return FenXing(type="di", start_idx=idx - 1, peak_idx=idx, end_idx=idx + 1)
        return None
