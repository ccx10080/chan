"""
chanlun/detector.py
===================
严格版缠论分型检测器。

流程（体现"结合律"的核心应用之一 —— K 线包含处理）：
  1. 从左到右遍历原始 K 线，维护一根"已处理 K 线"栈 `_processed`；
  2. 每加入一根新 K 线，若与栈顶存在"包含关系"（一根完全在另一根内部），
     则按当前走势方向合并为一根新的"包含 K 线"，并把这根包含 K 线的
     `original_idx` 指向极值那根原始 K 线（便于后续分型反查原始坐标）；
  3. 包含处理完成后，对 `_processed` 的最后三根执行"顶/底分型"判别；
  4. 若命中分型，则把"原始 K 线索引区间 + 分型类型 + 极值价"记录为一个 FenXing；
  5. 分型之间允许"部分共用 K 线"（由包含处理已经自然抹平噪声），
     后续 BiAnalyzer 会对"同方向分型相邻"再做取舍（结合律在笔层面的应用）。
"""
from typing import List, Tuple
from chanlun.models import KLine, FenXing


# ---------------------------------------------------------------------------
# 内部数据结构："包含处理后的 K 线" —— 保留原始索引映射
# ---------------------------------------------------------------------------
class _CKLine:
    __slots__ = ("original_idx", "high", "low", "open", "close", "date", "volume")

    def __init__(self, original_idx: int, high: float, low: float,
                 open: float, close: float, date: str, volume: float):
        self.original_idx = original_idx
        self.high = high
        self.low = low
        self.open = open
        self.close = close
        self.date = date
        self.volume = volume


class FenXingDetector:
    """分型检测器 —— 先做 K 线包含处理，再识别顶/底分型。

    对外接口：
        detector = FenXingDetector(klines)
        fenxings = detector.detect()
        # detector.processed_klines  可访问包含处理后的 _CKLine 序列（调试用）
    """

    def __init__(self, klines: List[KLine]):
        self.klines = klines
        self.processed_klines: List[_CKLine] = []  # 调试用

    # ---------------- 核心：包含处理 ----------------
    @staticmethod
    def _is_contained(a: "_CKLineLike", b: "_CKLineLike") -> bool:
        """只有严格"被包含"关系才合并（即整个 K 线实体落在另一根内部）。"""
        return (float(b.high) <= float(a.high) and float(b.low) >= float(a.low)) or \
               (float(a.high) <= float(b.high) and float(a.low) >= float(b.low))

    def _merge(self, left: "_CKLineLike", right: "_CKLineLike", up: bool) -> "_CKLineLike":
        """按方向合并两根存在包含关系的 K 线。

        缠论规则：
          - 向上合并（up=True）：high = max，low = max
          - 向下合并（up=False）：high = min，low = min
        合并后的 original_idx 指向"极值那根"。
        """
        if up:
            new_high = max(float(left.high), float(right.high))
            new_low = max(float(left.low), float(right.low))
            anchor = right if float(right.high) >= float(left.high) else left
        else:
            new_high = min(float(left.high), float(right.high))
            new_low = min(float(left.low), float(right.low))
            anchor = right if float(right.low) <= float(left.low) else left
        return _CKLine(
            original_idx=anchor.original_idx,
            high=round(new_high, 6),
            low=round(new_low, 6),
            open=float(left.open),
            close=float(right.close),
            date=getattr(right, "date", ""),
            volume=round(float(getattr(left, "volume", 0)) + float(getattr(right, "volume", 0)), 4),
        )

    def _push_and_merge(self, ck: "_CKLineLike") -> None:
        """压入一根 K 线并尝试在栈顶执行最多 1 轮包含处理。

        关键保护：
          - 若合并会导致"当前局部最高/最低"（即潜在分型顶点）被吞并，
            则主动放弃合并，保留分型顶点信息；
          - 仅在栈长度 ≥3 时才合并（保证有方向判断依据）。
        """
        self.processed_klines.append(ck)
        if len(self.processed_klines) < 3:
            return
        # 最多 1 轮合并
        a = self.processed_klines[-2]
        b = self.processed_klines[-1]
        if not self._is_contained(a, b):
            return
        # 保护：如果 a 比 b 更"极端"（更高高 或 更低低），
        # 且 a 至少在一个维度上"支配"了 processed[-3]，
        # 则认为 a 可能是分型顶点，不应当与 b 合并。
        if (float(a.high) > float(b.high) or float(a.low) < float(b.low)) and (
            float(a.high) >= float(self.processed_klines[-3].high)
            or float(a.low) <= float(self.processed_klines[-3].low)
        ):
            return
        up = float(self.processed_klines[-3].high) <= float(a.high)
        merged = self._merge(a, b, up=up)
        self.processed_klines.pop()
        self.processed_klines.pop()
        self.processed_klines.append(merged)

    # ---------------- 分型识别 ----------------
    def _check_fenxing_triplet(self) -> Tuple[str, int, int, int, float] | None:
        """在 processed_klines 的"最后三根"上判断是否构成分型。

        返回: (type, start_original_idx, peak_original_idx, end_original_idx, peak_price)
        """
        if len(self.processed_klines) < 3:
            return None
        p1, p2, p3 = self.processed_klines[-3], self.processed_klines[-2], self.processed_klines[-1]

        # 顶分型：中间 high 严格最高，且两侧的 "high 被中间支配"
        if p2.high > p1.high and p2.high > p3.high:
            return ("ding", p1.original_idx, p2.original_idx, p3.original_idx, round(p2.high, 6))
        # 底分型：中间 low 严格最低
        if p2.low < p1.low and p2.low < p3.low:
            return ("di", p1.original_idx, p2.original_idx, p3.original_idx, round(p2.low, 6))
        return None

    def detect(self) -> List[FenXing]:
        self.processed_klines = []
        fenxings: List[FenXing] = []
        # 最近一次分型的 end_idx，用于避免分型之间过度重叠
        last_fenxing_end = -1

        for i, k in enumerate(self.klines):
            ck = _CKLine(
                original_idx=i,
                high=float(k.high),
                low=float(k.low),
                open=float(k.open),
                close=float(k.close),
                date=str(k.date),
                volume=float(k.volume),
            )
            self._push_and_merge(ck)
            fx = self._check_fenxing_triplet()
            if fx is None:
                continue
            fx_type, s_idx, p_idx, e_idx, price = fx
            if s_idx <= last_fenxing_end:
                # 与上一个分型发生重叠（共用 K 线），
                # 这是缠论中"同一根K线不能同时属于两个分型"原则的松弛实现：
                # 若同一位置同时存在顶/底候选，保留更先出现且极值更强的。
                # 这里仅跳过重叠，由 BiAnalyzer 在"分型取舍"阶段进一步归并。
                continue
            fenxings.append(FenXing(
                type=fx_type,
                start_idx=s_idx,
                peak_idx=p_idx,
                end_idx=e_idx,
                peak_price=price,
            ))
            last_fenxing_end = e_idx

        # ---------------- 后处理：相邻同方向分型按"极值"取舍 ----------------
        # 若出现 "ding, ding, di" 这种"同向相邻"，结合律允许保留更极端者；
        # 这里执行一次"同向同方向合并"，保证顶底分型尽量交错（不强行交替，
        # 因为 BiAnalyzer 还要做"笔是否成立"的二次判断）。
        if len(fenxings) >= 2:
            filtered: List[FenXing] = [fenxings[0]]
            for fx in fenxings[1:]:
                last = filtered[-1]
                if last.type == fx.type:
                    # 同方向，按极值取舍
                    if fx.type == "ding":
                        winner = last if last.peak_price >= fx.peak_price else fx
                    else:
                        winner = last if last.peak_price <= fx.peak_price else fx
                    # 替换为 winner，但区间取并集以扩大覆盖
                    filtered[-1] = FenXing(
                        type=winner.type,
                        start_idx=min(last.start_idx, fx.start_idx),
                        peak_idx=winner.peak_idx,
                        end_idx=max(last.end_idx, fx.end_idx),
                        peak_price=winner.peak_price,
                    )
                else:
                    filtered.append(fx)
            fenxings = filtered

        return fenxings
