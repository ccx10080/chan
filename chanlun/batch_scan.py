# chanlun/batch_scan.py
# 多股票批量扫描：对一批股票代码执行多级别诊断，并按信号强度排序
from typing import List, Dict, Optional
from chanlun.multilevel import MultiLevelDiagnosis


class BatchScanner:
    """对一批股票代码并行执行多级别诊断，返回按信号强度排序的结果。"""

    def __init__(self, use_demo: bool = True):
        self.use_demo = use_demo

    def scan(self, codes: List[str], top_n: int = 20,
             min_confidence: float = 0.0) -> Dict:
        """
        对每只股票执行一次 MultiLevelDiagnosis.run(), 汇总信号。

        返回:
          {
            "total_scanned": int,           # 总共扫描的股票数
            "signals_found": int,           # 至少有1个信号的股票数
            "ranked_results": List[dict],   # 按最高置信度降序
                [
                  {
                    "code": str,
                    "name": str,
                    "top_confidence": float,
                    "direction": str,         # "buy" / "sell" / "mixed"
                    "n_signals": int,
                    "precise_price": float or None,
                    "levels_involved": List[str],
                    "top_signal_desc": str
                  }, ...
                ]
          }
        """
        codes = [str(c).strip() for c in codes if str(c).strip()]
        results = []
        for code in codes:
            try:
                d = MultiLevelDiagnosis(code=code, name=code, use_demo=self.use_demo)
                r = d.run()
            except Exception:
                continue

            signals = r.qjt_signals or []
            if not signals and min_confidence > 0:
                continue

            top = signals[0] if signals else None
            directions = {s.direction for s in signals}
            if len(directions) == 1:
                direction = next(iter(directions))
            elif len(directions) > 1:
                direction = "mixed"
            else:
                direction = "none"

            levels_involved = []
            for s in signals:
                for lv in s.levels_involved:
                    if lv not in levels_involved:
                        levels_involved.append(lv)

            results.append({
                "code": r.code,
                "name": r.name,
                "top_confidence": round(top.confidence, 4) if top else 0.0,
                "direction": direction,
                "n_signals": len(signals),
                "precise_price": round(top.precise_price, 4) if top else None,
                "levels_involved": levels_involved,
                "top_signal_desc": top.description if top else "无信号",
            })

        # 过滤 min_confidence
        if min_confidence > 0:
            results = [r for r in results if r["top_confidence"] >= min_confidence]

        # 按最高置信度降序
        results.sort(key=lambda r: r["top_confidence"], reverse=True)
        ranked = results[:top_n]

        return {
            "total_scanned": len(codes),
            "signals_found": sum(1 for r in results if r["n_signals"] > 0),
            "ranked_results": ranked,
        }

    def scan_from_db(self, code_db, sector: Optional[str] = None, top_n: int = 20) -> Dict:
        """从 StockCodeDB 中按板块过滤后扫描。"""
        codes = [c["code"] for c in code_db.all_codes()
                 if sector is None or c.get("sector") == sector]
        return self.scan(codes, top_n=top_n)
