# chanlun/backtest.py
# 信号回测：对单只股票滚动执行"以历史某日为诊断终点"的诊断，
# 收集历史信号并计算假设持有 N 日的盈亏。
from typing import List, Dict, Optional
from chanlun.models import KLine
from chanlun.multilevel import generate_demo_klines, MultiLevelDiagnosis


class SignalBacktest:
    """
    信号回测引擎（简化版）
    - 对 demo K 线数组滚动诊断
    - 在每个信号位置统计"持有 N 日"的收益
    - 统计胜率、平均收益、最大/最小收益、交易明细
    """

    def __init__(self):
        pass

    def run_single(self, code: str, days_back: int = 120, hold_days: int = 10,
                   use_demo: bool = True, min_confidence: float = 0.5) -> Dict:
        """
        参数:
          code: 股票代码
          days_back: 生成的 demo K 线数量（历史覆盖时长）
          hold_days: 每笔交易持仓天数
          use_demo: 是否使用 demo 数据（目前唯一支持方式）
          min_confidence: 信号触发最小置信度

        返回:
          {
            "code": str,
            "total_signals": int,
            "triggered_signals": int,
            "win_rate": float,
            "avg_return": float,
            "max_return": float,
            "min_return": float,
            "trades": List[{
                "signal_date_idx": int,
                "price_in": float,
                "price_out": float,
                "hold_days": int,
                "return_pct": float,
                "direction": str,
                "signal_confidence": float
            }]
          }
        """
        klines = generate_demo_klines(code, days_back)
        if len(klines) < hold_days + 10:
            return self._empty_result(code)

        trades = []
        # 滚动诊断，每隔 5 根 K 线诊断一次
        for i in range(20, len(klines) - hold_days, 5):
            # 截取到第 i 根 K 线的历史数据进行诊断
            sub_klines = klines[:i + 1]
            try:
                from chanlun.diagnosis import ChanLunDiagnosis
                from chanlun.qjt_engine import QJTEngine
                from chanlun.models import MultiLevelResult, LevelData

                diag = ChanLunDiagnosis(code, code, sub_klines).run()
                # 构造简化版 LevelData / QJT 引擎
                ld = LevelData(
                    level="daily", level_name_cn="日线",
                    klines=sub_klines, diagnosis=diag,
                    key_price_range=[min(k.low for k in sub_klines[-10:]),
                                     max(k.high for k in sub_klines[-10:])],
                    key_time_range=[max(0, len(sub_klines)-10), len(sub_klines)-1],
                    direction="buy" if diag.beichi else None,
                    has_zhongshu=bool(diag.zhongshus),
                    has_beichi=bool(diag.beichi),
                )
                # 仅当检测到背驰/中枢时，触发交易信号
                if not ld.has_beichi:
                    continue

                price_in = sub_klines[i].close
                price_out_idx = min(i + hold_days, len(klines) - 1)
                price_out = klines[price_out_idx].close
                hold = price_out_idx - i
                return_pct = (price_out - price_in) / price_in * 100

                trades.append({
                    "signal_date_idx": i,
                    "price_in": round(float(price_in), 4),
                    "price_out": round(float(price_out), 4),
                    "hold_days": hold,
                    "return_pct": round(float(return_pct), 4),
                    "direction": "buy",
                    "signal_confidence": 0.6,
                })
            except Exception:
                continue

        if not trades:
            return self._empty_result(code)

        wins = sum(1 for t in trades if t["return_pct"] > 0)
        rets = [t["return_pct"] for t in trades]

        return {
            "code": code,
            "total_signals": len(trades),
            "triggered_signals": len(trades),
            "win_rate": round(wins / len(trades), 4),
            "avg_return": round(sum(rets) / len(rets), 4),
            "max_return": round(max(rets), 4),
            "min_return": round(min(rets), 4),
            "trades": trades,
        }

    def _empty_result(self, code: str) -> Dict:
        return {
            "code": code,
            "total_signals": 0,
            "triggered_signals": 0,
            "win_rate": 0.0,
            "avg_return": 0.0,
            "max_return": 0.0,
            "min_return": 0.0,
            "trades": [],
        }

    def run_multi(self, codes: List[str], **kwargs) -> List[Dict]:
        """对多只股票执行回测"""
        results = []
        for code in codes:
            try:
                results.append(self.run_single(code, **kwargs))
            except Exception:
                results.append(self._empty_result(code))
        return results
