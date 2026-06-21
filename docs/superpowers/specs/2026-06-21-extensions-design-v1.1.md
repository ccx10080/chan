# 缠论区间套系统 - 扩展功能规格文档 (v1.1)

> 基于 v1.0（11 个核心模块 + 6 个 API 端点 + 55 测试）的扩展方案
> 目标：实现 A1/A2/B1/B2/B3/C/C2/D1/D2 共 9 个子功能

---

## 总体功能矩阵

| 代号 | 功能 | 新建/修改文件 | 新增测试数 |
|------|------|---------------|-----------|
| **A1** | 股票代码库 + 搜索 | `chanlun/stock_codes.py` + `api/main.py`(API) + `static/index.html`(联想) | ≥4 |
| **A2** | SQLite 缓存/持久化 | `chanlun/cache.py` + `api/main.py`(缓存层接入) | ≥5 |
| **B1** | 增强中枢识别 | `chanlun/zhongshu_v2.py` + 修改 `diagnosis.py` | ≥6 |
| **B2** | 买卖点精确定位 | `chanlun/buy_sell_points.py` | ≥6 |
| **B3** | 多股票批量扫描 | `chanlun/batch_scan.py` + `api/main.py`(批量API) | ≥4 |
| **D1** | 异步数据获取 + 超时 | 修改 `chanlun/multilevel.py` + `api/main.py`(async) | ≥3 |
| **D2** | 结构化日志监控 | 修改 `api/main.py` + `chanlun/` 各模块 | ≥1 |
| **C**  | 图表增强标注 | 修改 `static/index.html`(ECharts标注) | -（前端） |
| **C2** | 信号回测/胜率统计 | `chanlun/backtest.py` + `api/main.py`(回测API) + `static/index.html`(表格) | ≥5 |

---

## 模块设计细则

### 1. A1 股票代码库

**类**：`StockCodeDB`

```python
# chanlun/stock_codes.py
class StockCodeDB:
    """
    内置约 60 只A股核心股票代码 + 名称。
    方法:
      search(query: str, limit=10) -> List[dict]  # 支持代码/名称模糊匹配 (大小写不敏感, 部分匹配)
      get_name(code: str) -> str | None
      all_codes() -> List[dict]
    """

# 内置表（沪深300核心成分 + 主要指数 + 科技/银行/消费代表）
CODE_LIST = [
    {"code": "000001", "name": "平安银行", "sector": "银行"},
    {"code": "000002", "name": "万科A",   "sector": "房地产"},
    {"code": "000333", "name": "美的集团", "sector": "家电"},
    {"code": "000651", "name": "格力电器", "sector": "家电"},
    {"code": "000858", "name": "五粮液",   "sector": "白酒"},
    {"code": "002415", "name": "海康威视", "sector": "安防"},
    {"code": "600000", "name": "浦发银行", "sector": "银行"},
    {"code": "600036", "name": "招商银行", "sector": "银行"},
    {"code": "600276", "name": "恒瑞医药", "sector": "医药"},
    {"code": "600519", "name": "贵州茅台", "sector": "白酒"},
    {"code": "600887", "name": "伊利股份", "sector": "食品"},
    {"code": "601012", "name": "隆基绿能", "sector": "光伏"},
    {"code": "601318", "name": "中国平安", "sector": "保险"},
    {"code": "601398", "name": "工商银行", "sector": "银行"},
    {"code": "601899", "name": "紫金矿业", "sector": "有色"},
    {"code": "603288", "name": "海天味业", "sector": "食品"},
    {"code": "688981", "name": "中芯国际", "sector": "半导体"},
    # ... 补充到约 60 只, 覆盖各大板块
]
```

**API**：`GET /api/stock/search?q=xxx&limit=10` → `{ results: [ {code, name, sector} ] }`

**前端**：输入框添加 `datalist` 联想，实时展示匹配的股票候选项。

---

### 2. A2 SQLite 缓存/持久化

**类**：`DiagnosisCache`

```python
# chanlun/cache.py
class DiagnosisCache:
    """
    SQLite 缓存 / 持久化。
    数据来源: ./chanlun_cache.sqlite (自动创建)

    表1: single_diagnosis (code, date, level, result_json)
    表2: multilevel_diagnosis (code, date, result_json)
    表3: request_log (timestamp, endpoint, code, response_time_ms, status_code, error)

    方法:
      get_single(code, level, max_age_h=24) -> dict | None
      save_single(code, level, result_json)
      get_multilevel(code, max_age_h=6) -> dict | None
      save_multilevel(code, result_json)
      log_request(endpoint, code, ms, status, error=None)
      get_history(code, n=30) -> List[dict]   # 返回近期诊断记录
    """
```

**接入方式**：`api/main.py` 在 `POST /api/diagnosis` 和 `POST /api/multilevel-diagnosis` 入口先命中缓存；若无缓存则执行诊断，然后写入缓存。

---

### 3. B1 增强中枢识别

**类**：`ZhongshuDetectorV2`

```python
# chanlun/zhongshu_v2.py
class ZhongshuDetectorV2:
    """
    严格版中枢识别：基于"连续三线段价格重叠区域"算法

    输入: List[Segment] + List[KLine]
    输出: List[Zhongshu]

    算法:
      1) 对每一条线段 seg_i，计算其 price range (low, high) 与时间索引 (start, end)
      2) 考察三元组 (seg_i, seg_{i+1}, seg_{i+2})
         - 计算三段 price range 的交集: overlap_low = max(seg_i.low, seg_{i+1}.low, seg_{i+2}.low)
         - overlap_high = min(seg_i.high, seg_{i+1}.high, seg_{i+2}.high)
         - 若 overlap_high > overlap_low，则形成一个中枢
         - 中枢起点 = seg_i.start, 终点 = seg_{i+2}.end
      3) 合并相邻中枢(重叠的合并为一个更大中枢)
      4) 返回中枢列表 (按时间排序)

    返回字段:
      Zhongshu(start_idx, end_idx, range=[low, high], level_strength)
      level_strength = (high - low) / average_price  # 中枢强度(震荡幅度)
    """
```

**替换策略**：`diagnosis.py` 中，若 `ZhongshuDetectorV2` 可用则优先使用。

---

### 4. B2 买卖点精确定位

**类**：`BuySellPointDetector`

```python
# chanlun/buy_sell_points.py
@dataclass
class TradePoint:
    point_type: Literal["buy1", "buy2", "buy3", "sell1", "sell2", "sell3"]  # 第一/二/三类买/卖点
    kline_idx: int             # K线索引
    price: float               # 建议操作价
    reason: str                # 文字说明
    confidence: float          # 0-1

class BuySellPointDetector:
    """
    缠论买卖点识别器

    输入: DiagnosisResult
    输出: List[TradePoint]

    规则:
      1类买点 (buy1): 下跌趋势末端, 最新背驰为 down 背驰, 且当前价格已进入中枢下方
      1类卖点 (sell1): 上涨趋势末端, 最新背驰为 up 背驰, 且当前价格已进入中枢上方
      2类买点 (buy2): 在 buy1 之后的次级回拉不破 buy1 低点
      2类卖点 (sell2): 在 sell1 之后的次级回拉不破 sell1 高点
      3类买点 (buy3): 次级别突破中枢上沿后回抽不进入中枢区间
      3类卖点 (sell3): 次级别跌破中枢下沿后反弹不进入中枢区间

    简化实现: 优先检测 buy1/sell1 信号 (与背驰对齐)
    """
```

---

### 5. B3 多股票批量扫描

**类**：`BatchScanner`

```python
# chanlun/batch_scan.py
class BatchScanner:
    """
    对一批股票代码并行执行多级别诊断。

    方法:
      scan(codes: List[str], use_demo=True, top_n=20) -> dict:
         {
           "total_scanned": n,
           "signals_found": m,
           "ranked_results": [          # 按信号总置信度降序
              {
                "code": "...",
                "name": "...",
                "top_confidence": 0.92,
                "direction": "buy",
                "n_signals": 3,
                "precise_price": 10.94,
                "levels": ["daily", "30m", "5m"],
                "trend": "盘整",
              }, ...
           ]
         }
    """
```

**API**：`POST /api/batch-scan`
```json
{ "codes": ["000001", "600519", ...], "use_demo": true, "top_n": 20, "min_confidence": 0.6 }
```

---

### 6. D1 + D2 异步化与结构化日志

**修改 `chanlun/multilevel.py`**：添加 `MultiLevelDiagnosisAsync` 类，其中 4 个级别的 `fetch_klines_from_akshare` 并行执行；对每次 akshare 调用设置 15s 超时。

**修改 `api/main.py`**：
- 将诊断相关 endpoint 改为 `async def`
- 在全局初始化中启动 `DiagnosisCache`
- 为每次请求记录结构化日志（代码、级别数、信号数、响应时间）
- 在异常时记录错误栈到 cache 的 `request_log` 表

---

### 7. C 前端图表增强标注

修改 `static/index.html` 的 `renderChart` 函数，新增：

- **分型标注**：`markPoint` — 顶分型红色圆点，底分型绿色圆点
- **笔标注**：用 `markLine` 在相邻分型之间绘制连线（绿/红色）
- **中枢区域**：用 `markArea` 绘制黄色半透明阴影矩形覆盖 K线中枢区域
- **买卖点**：用 `markPoint` 带 `⭐` emoji 的大图标标注
- **上级中枢参考线**：1 分钟图上叠加 5 分钟 / 30 分钟 / 日线中枢上下沿虚线

---

### 8. C2 信号回测/胜率统计

**类**：`SignalBacktest`

```python
# chanlun/backtest.py
class SignalBacktest:
    """
    对单只股票滚动执行"以历史某日为诊断终点"的诊断，
    收集历史信号并计算假设持有 N 日的盈亏。

    方法:
      run_single(code, days_back=120, hold_days=10, use_demo=True) -> dict:
         {
           "total_signals": n,
           "buy_signals": n_buy,
           "sell_signals": n_sell,
           "win_rate": float,           # 胜率
           "avg_return": float,         # 平均收益率
           "max_return": float,
           "min_return": float,
           "trades": [
              {"date_idx": i, "price_in": p, "price_out": p, "return": r, "direction": ...},
              ...
           ]
         }
    """
```

**API**：`POST /api/backtest` → 返回上面结构；前端以表格+汇总展示。

---

## 验收标准

- [ ] `chanlun/stock_codes.py` 通过 ≥4 测试；搜索"平安"/"000001"能命中
- [ ] `chanlun/cache.py` 通过 ≥5 测试；读写一致；缓存命中时跳过诊断
- [ ] `chanlun/zhongshu_v2.py` 通过 ≥6 测试；返回对象包含 price range 与 level_strength
- [ ] `chanlun/buy_sell_points.py` 通过 ≥6 测试；至少能识别 buy1/sell1 信号
- [ ] `chanlun/batch_scan.py` 通过 ≥4 测试；批量扫描返回 Top N 列表
- [ ] `chanlun/backtest.py` 通过 ≥5 测试；返回胜率/收益率/交易明细
- [ ] `api/main.py` 新增 API 端点全部通过 TestClient 测试
- [ ] `static/index.html` 新增 ECharts 图表标注（分型/笔/中枢/买卖点）
- [ ] 全项目测试数 **≥ 90**，且 **全部通过**
- [ ] API 启动正常，前端 `http://localhost:8000` 可访问并完成一次完整诊断
