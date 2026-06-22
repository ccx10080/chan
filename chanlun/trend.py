from typing import List
from chanlun.models import Segment


class TrendAnalyzer:
    """趋势分析器"""

    def __init__(self, segments: List[Segment]):
        self.segments = segments

    def analyze(self) -> str:
        if len(self.segments) < 3:
            return "盘整"
        for i in range(1, len(self.segments)):
            if self.segments[i].direction == self.segments[i - 1].direction:
                return "盘整"
        up = sum(1 for s in self.segments if s.direction == "up")
        down = sum(1 for s in self.segments if s.direction == "down")
        if up > down + 1:
            return "上涨趋势"
        elif down > up + 1:
            return "下跌趋势"
        else:
            return "盘整"
