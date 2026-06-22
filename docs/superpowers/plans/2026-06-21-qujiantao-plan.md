# 区间套分析功能 - 实现计划

> **说明**：本计划覆盖缠论核心模块 + 区间套功能的完整开发。项目从零开始构建。

---

## 任务1：项目基础结构与依赖

**创建文件**：
- `/workspace/requirements.txt`
- `/workspace/pytest.ini`
- `/workspace/conftest.py`
- `/workspace/chanlun/__init__.py`
- `/workspace/tests/chanlun/__init__.py`
- `/workspace/api/__init__.py`
- `/workspace/static/`（目录）

**依赖列表**：
```
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
akshare>=1.12.0
pytest>=7.0.0
```

**执行步骤**：
1. `mkdir -p /workspace/chanlun /workspace/api /workspace/static /workspace/tests/chanlun`
2. `touch /workspace/chanlun/__init__.py /workspace/api/__init__.py`
3. 创建 `requirements.txt`
4. `pip install -q fastapi uvicorn pydantic akshare pytest`
5. 创建 `pytest.ini`：`[pytest]\npythonpath = /workspace`
6. 创建 `conftest.py`（空文件或简单 sys.path 注入）

**验证**：运行 `python -c "import fastapi, pydantic, chanlun"` 无 ImportError

**提交**：`git add -A && git commit -m "chore: project scaffolding and dependencies"`

---

## 任务2：数据模型定义

**创建文件**：
- `/workspace/chanlun/models.py`
- `/workspace/tests/chanlun/test_models.py`

**需定义的模型**：

```python
from pydantic import BaseModel
from typing import List, Optional, Dict, Literal

class KLine(BaseModel):
    date: str          # 日期/时间字符串
    open: float        # 开盘价
    high: float        # 最高价
    low: float         # 最低价
    close: float       # 收盘价
    volume: float      # 成交量

class FenXing(BaseModel):
    type: Literal["ding", "di"]   # 顶分型/底分型
    start_idx: int                # 起始K线索引
    peak_idx: int                 # 极点K线索引
    end_idx: int                  # 结束K线索引

class Bi(BaseModel):
    start: int                    # 起始分型的peak_idx
    end: int                      # 结束分型的peak_idx
    direction: Literal["up", "down"]

class Segment(BaseModel):
    start: int
    end: int
    direction: Literal["up", "down"]
    bis: List[int] = []           # 包含的笔索引列表

class Zhongshu(BaseModel):
    start: int                    # 起始K线索引
    end: int                      # 结束K线索引
    range: List[float]            # 价格区间 [low, high]

class DiagnosisResult(BaseModel):
    code: str
    name: str
    klines: List[KLine]
    fenxings: List[FenXing]
    bis: List[Bi]
    segments: List[Segment]
    zhongshus: List[Zhongshu]
    trend: Literal["上涨趋势", "下跌趋势", "盘整"]
    beichi: Optional[str] = None  # 背驰描述

class LevelData(BaseModel):
    level: str                                # "1m" / "5m" / "30m" / "daily"
    level_name_cn: str                        # "1分钟" / ...
    klines: List[KLine]                       # K线数据（前端可选展示）
    diagnosis: DiagnosisResult                # 该级别诊断结果
    key_price_range: List[float]              # 关键价格区间
    key_time_range: List[int]                 # 关键时间区间
    direction: Optional[str]                   # "buy" / "sell" / None
    has_zhongshu: bool
    has_beichi: bool

class QJTSignal(BaseModel):
    levels_involved: List[str]                 # 涉及的级别
    direction: str                             # "buy" / "sell"
    price_intersection: List[float]            # 价格交集
    confidence: float                          # 0.0 - 1.0
    price_score: float
    direction_score: float
    time_score: float
    description: str
    precise_price: float

class MultiLevelResult(BaseModel):
    code: str
    name: str
    levels: Dict[str, LevelData]
    qjt_signals: List[QJTSignal]
    overall_assessment: str
    highest_confidence_signal: Optional[QJTSignal]
```

**测试覆盖**：
- 测试各模型实例化成功
- 测试字段类型验证（Literal 正确限制）
- 测试空列表/None 值的处理

**验证命令**：`cd /workspace && python -m pytest tests/chanlun/test_models.py -v`

**提交**：`git add -A && git commit -m "feat: define data models for chanlun and qjt"`

---

## 任务3：分型检测器

**创建文件**：
- `/workspace/chanlun/detector.py`
- `/workspace/tests/chanlun/test_detector.py`

**核心类**：`FenXingDetector`

**算法**：
```
遍历 K 线索引 i 从 1 到 len-2:
  left_high, mid_high, right_high = klines[i-1].high, klines[i].high, klines[i+1].high
  left_low, mid_low, right_low = klines[i-1].low, klines[i].low, klines[i+1].low
  若 mid_high > left_high 且 mid_high > right_high → 顶分型
  若 mid_low < left_low 且 mid_low < right_low → 底分型
  检测到分型后，跳过 end_idx 之后的K线继续扫描
返回 FenXing 列表
```

**测试用例**（在 `test_detector.py` 中）：
1. 手动构造3根K线，识别顶分型
2. 手动构造3根K线，识别底分型
3. 构造连续K线，确保没有分型被识别
4. 构造交替分型，确保能识别多个分型

**验证命令**：`cd /workspace && python -m pytest tests/chanlun/test_detector.py -v`

**提交**：`git add -A && git commit -m "feat: add FenXing detector for top/bottom patterns"`

---

## 任务4：笔分析器

**创建文件**：
- `/workspace/chanlun/bi.py`
- `/workspace/tests/chanlun/test_bi.py`

**核心类**：`BiAnalyzer`

**算法**：
```
输入: K线列表 + 分型列表
遍历分型对 (fx_i, fx_{i+1}):
  计算K线数: gap = fx_{i+1}.end_idx - fx_i.start_idx + 1
  若 gap < 5 → 跳过（笔需要至少5根K线）
  判断方向:
    若 fx_i 是顶分型 且 fx_{i+1} 是底分型 → "down"
    若 fx_i 是底分型 且 fx_{i+1} 是顶分型 → "up"
    否则 → 跳过
  创建 Bi(start=fx_i.peak_idx, end=fx_{i+1}.peak_idx, direction)
返回 Bi 列表
```

**测试用例**：
1. 构造6根K线+2分型，形成1笔
2. 分型间隔不足5K → 不形成笔
3. 同类型分型相邻 → 不形成笔
4. 连续多个笔的构建

**验证命令**：`cd /workspace && python -m pytest tests/chanlun/test_bi.py -v`

**提交**：`git add -A && git commit -m "feat: add BiAnalyzer for building trend lines"`

---

## 任务5：线段分析器

**创建文件**：
- `/workspace/chanlun/segment.py`
- `/workspace/tests/chanlun/test_segment.py`

**核心类**：`SegmentAnalyzer`

**算法**：
```
输入: 笔列表
每 3 笔为一组构成一条线段:
  start = group[0].start
  end = group[2].end
  direction = 简化逻辑: 第 1 笔方向或基于价格涨跌判断
  记录该线段包含哪几笔
返回 Segment 列表
```

**测试用例**：
1. 3笔 → 1条线段
2. 少于3笔 → 无线段
3. 6笔 → 2条线段
4. 线段起点与终点正确对应价格位置

**验证命令**：`cd /workspace && python -m pytest tests/chanlun/test_segment.py -v`

**提交**：`git add -A && git commit -m "feat: add SegmentAnalyzer for building segments"`

---

## 任务6：中枢检测器

**创建文件**：
- `/workspace/chanlun/zhongshu.py`
- `/workspace/tests/chanlun/test_zhongshu.py`

**核心类**：`ZhongshuDetector`

**算法**：
```
输入: 线段列表
每 3 条线段为一组:
  seg1, seg2, seg3 = group
  若 seg1.direction == seg3.direction (第1,3段同向)
     AND seg1.direction != seg2.direction (中间段反向)
    → 形成一个中枢
    价格区间 = [min(三段涉及的K线低点), max(三段涉及的K线高点)]
    简化: 以线段索引作为位置标记，价格取分型涉及的K线高低点
返回 Zhongshu 列表
```

**测试用例**：
1. up-down-up 三段 → 识别1个中枢
2. 方向交替错误 → 不识别中枢
3. 少于3段 → 不识别中枢
4. 中枢的价格区间合理

**验证命令**：`cd /workspace && python -m pytest tests/chanlun/test_zhongshu.py -v`

**提交**：`git add -A && git commit -m "feat: add Zhongshu detector for identifying中枢"`

---

## 任务7：趋势与背驰分析

**创建文件**：
- `/workspace/chanlun/trend.py`
- `/workspace/chanlun/beichi.py`
- `/workspace/tests/chanlun/test_trend.py`
- `/workspace/tests/chanlun/test_beichi.py`

**核心类 TrendAnalyzer**：
```
输入: 线段列表
统计 direction=="up" 数量 vs "down" 数量
up明显多 → "上涨趋势"
down明显多 → "下跌趋势"
均衡 → "盘整"
```

**核心类 BeichiDetector**：
```
输入: 线段列表
找到每个线段的前一个同向线段
比较两段的长度 (end - start)
若后续线段长度 < 前一段 * 0.8
  → 判定为该方向的背驰
返回 "up背驰" / "down背驰" / None
```

**测试用例**：
- 上涨线段力度减弱 → up背驰
- 无力度减弱 → None
- 下跌线段力度减弱 → down背驰
- 趋势方向正确判定

**验证命令**：`cd /workspace && python -m pytest tests/chanlun/test_trend.py tests/chanlun/test_beichi.py -v`

**提交**：`git add -A && git commit -m "feat: add trend and beichi detectors"`

---

## 任务8：单级别诊断主流程

**创建文件**：
- `/workspace/chanlun/diagnosis.py`
- `/workspace/tests/chanlun/test_diagnosis.py`

**核心类**：`ChanLunDiagnosis`

**主流程**：
```python
def run(self) -> DiagnosisResult:
    fenxings = FenXingDetector(self.klines).detect()
    bis = BiAnalyzer(self.klines, fenxings).build_bis()
    segments = SegmentAnalyzer(bis).build_segments()
    zhongshus = ZhongshuDetector(segments).detect()
    trend = TrendAnalyzer(segments).analyze()
    beichi = BeichiDetector(segments).detect()
    return DiagnosisResult(code=..., name=..., klines=..., 
                           fenxings=fenxings, bis=bis, segments=segments,
                           zhongshus=zhongshus, trend=trend, beichi=beichi)
```

**辅助函数 `_leveldata_from_diagnosis`**：
```python
def build_level_data(code, name, level, level_name_cn, klines) -> LevelData:
    diagnosis = ChanLunDiagnosis(code, name, klines).run()
    # 提取关键价格区间：取所有中枢区间的并集
    if diagnosis.zhongshus:
        low = min(z.range[0] for z in diagnosis.zhongshus)
        high = max(z.range[1] for z in diagnosis.zhongshus)
        key_price = [low, high]
    else:
        key_price = [min(k.low for k in klines), max(k.high for k in klines)]

    # 提取关键时间区间：最后一个中枢的时间位置
    if diagnosis.zhongshus:
        last_z = diagnosis.zhongshus[-1]
        key_time = [last_z.start, last_z.end]
    else:
        key_time = [len(klines) // 2, len(klines) - 1]

    # 判断方向：根据背驰信号+趋势
    if diagnosis.beichi and "up" in diagnosis.beichi:
        direction = "buy"
    elif diagnosis.beichi and "down" in diagnosis.beichi:
        direction = "sell"
    elif diagnosis.trend == "下跌趋势":
        direction = "buy"   # 下跌趋势中找买点
    elif diagnosis.trend == "上涨趋势":
        direction = "sell"  # 上涨趋势中找卖点
    else:
        direction = None

    return LevelData(level=level, level_name_cn=level_name_cn,
                     klines=klines, diagnosis=diagnosis,
                     key_price_range=key_price, key_time_range=key_time,
                     direction=direction,
                     has_zhongshu=len(diagnosis.zhongshus) > 0,
                     has_beichi=diagnosis.beichi is not None)
```

**测试用例**：
- 使用模拟K线构造完整诊断流程
- 验证各字段被正确填充
- 验证 LevelData 可从 DiagnosisResult 转换

**验证命令**：`cd /workspace && python -m pytest tests/chanlun/test_diagnosis.py -v`

**提交**：`git add -A && git commit -m "feat: add single-level ChanLunDiagnosis main pipeline"`

---

## 任务9：区间套判定引擎（新增核心模块）

**创建文件**：
- `/workspace/chanlun/qjt_engine.py`
- `/workspace/tests/chanlun/test_qjt_engine.py`

**核心类**：`QJTEngine`

**主判定逻辑**：
```python
def detect_signals(self, levels: Dict[str, LevelData]) -> List[QJTSignal]:
    signals = []
    level_keys = ["daily", "30m", "5m", "1m"]
    available_levels = [k for k in level_keys if k in levels]

    # 枚举所有可能的级别组合（从2级到4级叠加）
    for r in range(len(available_levels), 1, -1):
        for combo in itertools.combinations(available_levels, r):
            # 阶段1：价格区间交集
            all_ranges = [levels[lv].key_price_range for lv in combo]
            intersection = self._price_intersection(all_ranges)
            if intersection is None:
                continue
            price_score = 1.0 - (intersection[1] - intersection[0]) / max(
                (r[1] - r[0]) for r in all_ranges)
            price_score = max(0.0, min(1.0, price_score))

            # 阶段2：方向一致性
            directions = [levels[lv].direction for lv in combo]
            if None in directions:
                continue
            direction_score = 1.0 if len(set(directions)) == 1 else 0.0
            if direction_score == 0.0:
                continue
            final_direction = directions[0]

            # 阶段3：时间区间包含关系（简化：判断级别排序正确即可）
            time_score = self._time_containment_score(combo, levels)

            # 综合置信度
            confidence = price_score * 0.35 + direction_score * 0.35 + time_score * 0.30
            if confidence < 0.5:
                continue

            # 生成描述
            desc = f"{len(combo)}级别{''.join(combo)}嵌套{final_direction}信号，价格区间{intersection}"
            precise_price = (intersection[0] + intersection[1]) / 2.0

            signals.append(QJTSignal(
                levels_involved=list(combo), direction=final_direction,
                price_intersection=intersection, confidence=confidence,
                price_score=price_score, direction_score=direction_score,
                time_score=time_score, description=desc,
                precise_price=round(precise_price, 4)
            ))

    # 按置信度降序排序
    signals.sort(key=lambda s: s.confidence, reverse=True)
    return signals

def _price_intersection(self, ranges: List[List[float]]) -> Optional[List[float]]:
    low = max(r[0] for r in ranges)
    high = min(r[1] for r in ranges)
    if high <= low:
        return None
    return [round(low, 4), round(high, 4)]

def _time_containment_score(self, combo, levels) -> float:
    # 按级别顺序检测小级别时间区间是否在大级别之内
    # 简化：判断各级别key_time_range的索引是否有合理的对应关系
    # 由于不同级别K线数量不同，这里用相对位置比较
    scores = []
    for i in range(len(combo) - 1):
        outer_lv = combo[i]
        inner_lv = combo[i + 1]
        outer_total = len(levels[outer_lv].klines)
        inner_total = len(levels[inner_lv].klines)
        if outer_total == 0 or inner_total == 0:
            scores.append(0.5)
            continue
        outer_start_ratio = levels[outer_lv].key_time_range[0] / outer_total
        outer_end_ratio = levels[outer_lv].key_time_range[1] / outer_total
        inner_start_ratio = levels[inner_lv].key_time_range[0] / inner_total
        inner_end_ratio = levels[inner_lv].key_time_range[1] / inner_total
        # 检测是否内级别的时间区间与外级别有合理重叠
        overlap = max(0, min(inner_end_ratio, outer_end_ratio) - max(inner_start_ratio, outer_start_ratio))
        scores.append(min(1.0, overlap * 3.0))
    return sum(scores) / len(scores) if scores else 0.5
```

**测试用例**：
1. 构造4级 LevelData 数据，价格区间完全嵌套 → 应识别出高置信度信号
2. 价格区间无交集 → 不产生信号
3. 方向不一致 → 不产生信号
4. 只有2个级别可用 → 产生低置信度信号
5. 空输入 → 空输出

**验证命令**：`cd /workspace && python -m pytest tests/chanlun/test_qjt_engine.py -v`

**提交**：`git add -A && git commit -m "feat: add QJT (区间套) detection engine"`

---

## 任务10：多级别诊断主流程

**创建文件**：
- `/workspace/chanlun/multilevel.py`
- `/workspace/tests/chanlun/test_multilevel.py`

**核心类**：`MultiLevelDiagnosis`

**主流程**：
```python
def run(self) -> MultiLevelResult:
    level_configs = [
        ("daily", "日线", 250),
        ("30m", "30分钟", 500),
        ("5m", "5分钟", 800),
        ("1m", "1分钟", 1200),
    ]

    levels = {}
    for level, level_cn, bar_count in level_configs:
        try:
            klines = self._fetch_klines(self.code, level, bar_count)
            if len(klines) >= 10:
                ld = build_level_data(self.code, self.name, level, level_cn, klines)
                levels[level] = ld
        except Exception as e:
            logging.warning(f"级别{level}数据获取失败: {e}")

    if not levels:
        raise ValueError("所有级别数据均获取失败")

    # 运行区间套判定
    signals = QJTEngine().detect_signals(levels)

    # 总体评估
    assessment_parts = []
    for lv, ld in levels.items():
        assessment_parts.append(
            f"{ld.level_name_cn}: {ld.diagnosis.trend}, "
            f"中枢{'有' if ld.has_zhongshu else '无'}, "
            f"背驰:{ld.has_beichi}, 方向:{ld.direction}"
        )
    assessment = "; ".join(assessment_parts)
    if signals:
        assessment += f"。检测到{len(signals)}个区间套信号，最高置信度{signals[0].confidence:.2f}({signals[0].direction})"
    else:
        assessment += "。未检测到有效区间套信号"

    highest = signals[0] if signals else None

    return MultiLevelResult(
        code=self.code, name=self.name, levels=levels,
        qjt_signals=signals, overall_assessment=assessment,
        highest_confidence_signal=highest
    )

# 辅助：从 akshare 获取多级别K线
def _fetch_klines(code: str, level: str, n: int) -> List[KLine]:
    import akshare as ak
    period_map = {"daily": "daily", "30m": "30", "5m": "5", "1m": "1"}
    period = period_map.get(level, "daily")

    try:
        df = ak.stock_zh_a_hist(symbol=code, period=period, adjust="qfq")
        if df is None or len(df) == 0:
            return []
        df = df.tail(n)

        return [
            KLine(
                date=str(row.get('日期', i)),
                open=float(row.get('开盘', 0)),
                high=float(row.get('最高', 0)),
                low=float(row.get('最低', 0)),
                close=float(row.get('收盘', 0)),
                volume=float(row.get('成交量', 0))
            )
            for i, (_, row) in enumerate(df.iterrows())
        ]
    except Exception:
        return []
```

**测试用例**：
1. 使用模拟K线数据（不依赖akshare）验证主流程能生成 MultiLevelResult
2. 验证 4 个级别数据被正确填充
3. 验证 QJTEngine 能正确识别信号

**验证命令**：`cd /workspace && python -m pytest tests/chanlun/test_multilevel.py -v`

**提交**：`git add -A && git commit -m "feat: add MultiLevelDiagnosis orchestrator"`

---

## 任务11：FastAPI 后端

**创建文件**：
- `/workspace/api/main.py`
- `/workspace/tests/chanlun/test_api.py`

**API端点**：
```
POST /api/multilevel-diagnosis
{
    "code": "000001",
    "name": "平安银行",   # 可选
    "use_demo": false     # 若为true使用模拟数据，不依赖akshare
}
→ 返回 MultiLevelResult（JSON）

POST /api/diagnosis
{
    "code": "000001",
    "name": "平安银行",
    "use_demo": false
}
→ 返回单级别 DiagnosisResult

GET /
→ 返回 static/index.html

GET /docs
→ FastAPI Swagger UI
```

**中间件**：CORS 允许跨域

**测试用例**：
1. 使用 `FastAPI TestClient` 调用 `/api/multilevel-diagnosis`（`use_demo=true`）
2. 验证响应格式正确，包含 `levels` 和 `qjt_signals`

**验证命令**：`cd /workspace && python -m pytest tests/chanlun/test_api.py -v`

**提交**：`git add -A && git commit -m "feat: add FastAPI endpoints for multi-level diagnosis"`

---

## 任务12：前端页面（多级别K线可视化）

**创建文件**：
- `/workspace/static/index.html`

**页面功能**：

1. **头部**：标题 + 股票代码输入 + 诊断按钮 + 演示按钮

2. **信号横幅**（若检测到信号）：
   ```
   🔴 极高置信度 4级别买入区间套
   精确价位：10.94 ± 0.02 | 置信度：0.92
   【信号描述文字】
   ```

3. **4个级别K线图**（垂直堆叠，每个图用 ECharts 绘制）：
   - 日线K线 + 中枢阴影区域
   - 30分钟K线 + 日线中枢区间参考线
   - 5分钟K线 + 30分钟中枢区间参考线
   - 1分钟K线 + 所有上级中枢区间虚线 + 精确买点红星标记

4. **诊断摘要表格**：
   - 级别 | 趋势 | 中枢 | 背驰 | 方向 | 关键价格区间

5. **演示模式**：构造模拟数据，直接展示完整的区间套信号案例，用于离线预览。

**提交**：`git add -A && git commit -m "feat: add multi-level K-line visualization frontend"`

---

## 任务13：最终集成测试与验证

**创建文件**（如需要）：
- `/workspace/tests/chanlun/test_integration.py`（端到端测试）

**执行的集成检查**：
1. **全测试套件**：`cd /workspace && python -m pytest tests/ -v --tb=short`
2. **模块导入检查**：
   ```
   python -c "
   from chanlun.models import KLine, LevelData, QJTSignal, MultiLevelResult
   from chanlun.detector import FenXingDetector
   from chanlun.bi import BiAnalyzer
   from chanlun.segment import SegmentAnalyzer
   from chanlun.zhongshu import ZhongshuDetector
   from chanlun.trend import TrendAnalyzer
   from chanlun.beichi import BeichiDetector
   from chanlun.diagnosis import ChanLunDiagnosis, build_level_data
   from chanlun.qjt_engine import QJTEngine
   from chanlun.multilevel import MultiLevelDiagnosis
   from api.main import app
   print('全部模块导入成功')
   "
   ```
3. **模拟数据端到端测试**：使用构造的K线数据，验证完整的区间套流程能输出信号

4. **服务器启动测试**：
   ```bash
   cd /workspace && python -m uvicorn api.main:app --port 8765 &
   sleep 2
   curl -s http://localhost:8765/docs | head -20
   kill %1 || true
   ```

**验收标准**：
- 所有测试通过（≥ 20 个测试用例）
- 所有模块能无错导入
- 模拟数据的区间套分析能输出至少1个信号
- API服务能正常启动

**提交**：`git add -A && git commit -m "feat: final integration tests"`

---

## 文件结构总览

```
/workspace/
├── chanlun/
│   ├── __init__.py
│   ├── models.py           # 所有数据模型
│   ├── detector.py         # 分型检测
│   ├── bi.py               # 笔分析
│   ├── segment.py          # 线段分析
│   ├── zhongshu.py         # 中枢检测
│   ├── trend.py            # 趋势分析
│   ├── beichi.py           # 背驰检测
│   ├── diagnosis.py        # 单级别诊断 + LevelData 构建
│   ├── qjt_engine.py       # 区间套判定引擎 ★
│   └── multilevel.py       # 多级别诊断主流程 ★
├── api/
│   ├── __init__.py
│   └── main.py             # FastAPI
├── static/
│   └── index.html          # 前端页面（4级别K线）
├── tests/chanlun/
│   ├── test_models.py
│   ├── test_detector.py
│   ├── test_bi.py
│   ├── test_segment.py
│   ├── test_zhongshu.py
│   ├── test_trend.py
│   ├── test_beichi.py
│   ├── test_diagnosis.py
│   ├── test_qjt_engine.py  # ★
│   ├── test_multilevel.py  # ★
│   └── test_api.py
├── docs/superpowers/specs/2026-06-21-qujiantao-design.md
├── requirements.txt
├── pytest.ini
├── conftest.py
└── README.md
```

---

## 提交序列

本项目的 commit 序列预计如下（13个任务 + 文档）：

1. `chore: project scaffolding and dependencies`
2. `feat: define data models for chanlun and qjt`
3. `feat: add FenXing detector`
4. `feat: add BiAnalyzer`
5. `feat: add SegmentAnalyzer`
6. `feat: add Zhongshu detector`
7. `feat: add trend and beichi detectors`
8. `feat: add single-level ChanLunDiagnosis`
9. `feat: add QJT (区间套) detection engine`  ⬅ 核心
10. `feat: add MultiLevelDiagnosis orchestrator` ⬅ 核心
11. `feat: add FastAPI endpoints`
12. `feat: add multi-level K-line visualization frontend`
13. `feat: final integration tests`
