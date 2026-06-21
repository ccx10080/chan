from typing import List
from chanlun.models import Bi, Segment


class SegmentAnalyzer:
    """线段分析器 - 每3笔构成一条线段"""

    def __init__(self, bis: List[Bi]):
        self.bis = bis

    def build_segments(self) -> List[Segment]:
        if len(self.bis) < 3:
            return []
        segments = []
        i = 0
        while i <= len(self.bis) - 3:
            group = self.bis[i:i+3]
            start = group[0].start
            end = group[2].end
            if group[0].direction == "up":
                direction = "up"
            else:
                direction = "down"
            segments.append(Segment(start=start, end=end, direction=direction, bis=list(range(i, i+3))))
            i += 3
        return segments
