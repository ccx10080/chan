from typing import List
from chanlun.models import KLine, DiagnosisResult, LevelData
from chanlun.detector import FenXingDetector
from chanlun.bi import BiAnalyzer
from chanlun.segment import SegmentAnalyzer
from chanlun.zhongshu import ZhongshuDetector
from chanlun.trend import TrendAnalyzer
from chanlun.beichi import BeichiDetector


class ChanLunDiagnosis:
    """单级别缠论诊断主流程"""

    def __init__(self, code: str, name: str, klines: List[KLine]):
        self.code = code
        self.name = name
        self.klines = klines

    def run(self) -> DiagnosisResult:
        fenxings = FenXingDetector(self.klines).detect()
        bis = BiAnalyzer(self.klines, fenxings).build_bis()
        segments = SegmentAnalyzer(bis).build_segments()
        zhongshus = ZhongshuDetector(segments).detect()
        trend = TrendAnalyzer(segments).analyze()
        # 将中枢信息传给背驰检测器，用于区分"趋势背驰"与"盘整背驰"
        beichi = BeichiDetector(segments, zhongshus=zhongshus).detect()
        return DiagnosisResult(
            code=self.code, name=self.name, klines=self.klines,
            fenxings=fenxings, bis=bis, segments=segments,
            zhongshus=zhongshus, trend=trend, beichi=beichi
        )


def build_level_data(code: str, name: str, level: str, level_name_cn: str, klines: List[KLine]) -> LevelData:
    """从单级别诊断结果构建 LevelData"""
    diagnosis = ChanLunDiagnosis(code, name, klines).run()

    if diagnosis.zhongshus:
        price_low = min(z.range[0] for z in diagnosis.zhongshus)
        price_high = max(z.range[1] for z in diagnosis.zhongshus)
        key_price = [price_low, price_high]
    else:
        key_price = [min(k.low for k in klines), max(k.high for k in klines)]

    if diagnosis.zhongshus:
        last = diagnosis.zhongshus[-1]
        key_time = [last.start, last.end]
    else:
        key_time = [len(klines) // 2, len(klines) - 1]

    if diagnosis.beichi and "up" in diagnosis.beichi:
        direction = "buy"
    elif diagnosis.beichi and "down" in diagnosis.beichi:
        direction = "sell"
    elif diagnosis.trend == "下跌趋势":
        direction = "buy"
    elif diagnosis.trend == "上涨趋势":
        direction = "sell"
    else:
        direction = None

    return LevelData(
        level=level, level_name_cn=level_name_cn, klines=klines,
        diagnosis=diagnosis, key_price_range=key_price,
        key_time_range=key_time, direction=direction,
        has_zhongshu=len(diagnosis.zhongshus) > 0,
        has_beichi=diagnosis.beichi is not None
    )
