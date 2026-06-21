from typing import List, Optional
from chanlun.models import Segment


class BeichiDetector:
    """背驰检测器 - 检测同向线段力度减弱"""

    def __init__(self, segments: List[Segment]):
        self.segments = segments

    def detect(self) -> Optional[str]:
        if len(self.segments) < 3:
            return None
        for i in range(1, len(self.segments)):
            # 找到前一个同向线段
            j = i - 1
            while j >= 0 and self.segments[j].direction != self.segments[i].direction:
                j -= 1
            if j < 0:
                continue
            prev_len = self.segments[j].end - self.segments[j].start
            curr_len = self.segments[i].end - self.segments[i].start
            if curr_len < prev_len * 0.8:
                return f"{self.segments[i].direction}背驰"
        return None
