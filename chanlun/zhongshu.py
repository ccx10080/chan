from typing import List
from chanlun.models import Segment, Zhongshu


class ZhongshuDetector:
    """中枢检测器 - 三段方向交替识别为中枢"""

    def __init__(self, segments: List[Segment]):
        self.segments = segments

    def detect(self) -> List[Zhongshu]:
        if len(self.segments) < 3:
            return []
        zhongshus = []
        i = 0
        while i <= len(self.segments) - 3:
            s1 = self.segments[i]
            s2 = self.segments[i+1]
            s3 = self.segments[i+2]
            if s1.direction == s3.direction and s1.direction != s2.direction:
                start_idx = min(s1.start, s2.start, s3.start)
                end_idx = max(s1.end, s2.end, s3.end)
                zhongshus.append(Zhongshu(start=start_idx, end=end_idx,
                                          range=[float(start_idx), float(end_idx)]))
                i += 3
            else:
                i += 1
        return zhongshus
