# A 股支持 — 实施工作流

> 基于 `cn_stock_architecture.md` 架构设计，分 4 个 Phase、20 个 Step 实施。
> 每个 Step 包含: 目标文件、具体任务、验证标准、依赖关系。

---

## 总览

```
Phase 1: 数据基础层          Phase 2: 路由集成层
┌─────────────────────┐     ┌─────────────────────┐
│ S1  market_utils.py  │────▶│ S8  interface.py     │
│ S2  akshare_stock    │────▶│ S9  config.py        │
│ S3  akshare 指标     │────▶│ S10 default_config   │
│ S4  akshare_news     │────▶│ S11 路由集成测试      │
│ S5  pyproject.toml   │     └──────────┬──────────┘
│ S6  数据层单元测试    │                │
│ S7  akshare 基本面    │                ▼
└─────────────────────┘     Phase 3: Agent 适配层
                            ┌─────────────────────┐
                            │ S12 cn_market_prompts│
                            │ S13 agent_states     │
                            │ S14 4 个 Analyst      │
                            │ S15 Researcher+Mgr   │
                            │ S16 Risk+Trader      │
                            │ S17 signal_processing│
                            │ S18 propagation+graph│
                            └──────────┬──────────┘
                                       ▼
                            Phase 4: 备用源 + 完善
                            ┌─────────────────────┐
                            │ S19 tushare_stock    │
                            │ S20 Memory 隔离       │
                            └─────────────────────┘
```

---

## Phase 1: 数据基础层

**目标**: 独立可运行的 akshare 数据获取模块，不改动任何现有文件。

### Step 1: 创建 `market_utils.py`

**文件**: `tradingagents/dataflows/market_utils.py` (新增)

**任务**:
- [ ] 实现 `detect_market(symbol) -> str`
  - 纯字母 → `"us"`
  - 6 位数字 / 带 `.SH`/`.SZ` 后缀 / 带 `SH`/`SZ` 前缀 → `"cn"`
  - 边界: 空字符串 → `"us"`, 混合格式容错
- [ ] 实现 `normalize_symbol(symbol, market) -> str`
  - A 股: 去除前缀/后缀，保留 6 位纯数字
  - 美股: `.upper()`
- [ ] 实现 `get_exchange(symbol) -> str`
  - `6`/`9` 开头 → `"SH"`, `0`/`2`/`3` 开头 → `"SZ"`
- [ ] 实现 `get_market_info(symbol) -> dict`
  - 返回 `{market, exchange, currency, language, symbol_normalized, symbol_display}`
- [ ] 实现 `get_cn_trade_dates(start_date, end_date) -> list`
  - 调用 `ak.tool_trade_date_hist_sina()`
  - 本地缓存到 `data_cache/cn_trade_dates.csv`
  - 缓存有效期: 文件存在且修改时间在 7 天内

**验证标准**:
```python
assert detect_market("600519") == "cn"
assert detect_market("000858.SZ") == "cn"
assert detect_market("SH600519") == "cn"
assert detect_market("NVDA") == "us"
assert detect_market("AAPL") == "us"
assert normalize_symbol("600519.SH", "cn") == "600519"
assert normalize_symbol("SZ000858", "cn") == "000858"
assert normalize_symbol("nvda", "us") == "NVDA"
assert get_exchange("600519") == "SH"
assert get_exchange("000858") == "SZ"
```

**依赖**: 无 (可独立开发)

---

### Step 2: 创建 `akshare_stock.py` — OHLCV 数据

**文件**: `tradingagents/dataflows/akshare_stock.py` (新增)

**任务**:
- [ ] 定义 `COLUMN_MAP` 中文→英文列名映射字典
- [ ] 实现 `_normalize_akshare_df(df) -> pd.DataFrame` 内部辅助函数:
  - 列名重命名 (COLUMN_MAP)
  - 成交量 ×100 (手→股)
  - 日期格式统一为 `YYYY-MM-DD`
  - 数值列保留 2 位小数
- [ ] 实现 `get_stock_data(symbol, start_date, end_date) -> str`
  - 调用 `ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=..., end_date=..., adjust="qfq")`
  - 日期参数转换: `"2025-03-14"` → `"20250314"`
  - 调用 `_normalize_akshare_df()`
  - 输出 CSV 字符串 + header (格式与 `get_YFin_data_online` 对齐)
  - 空数据返回友好提示
  - `time.sleep(config.get("cn_request_interval", 0.3))` 请求间隔
- [ ] 错误处理: 网络错误、无效代码、akshare 接口变更

**验证标准**:
```python
result = get_stock_data("600519", "2025-03-01", "2025-03-14")
assert "Date" in result
assert "Open" in result
assert "Close" in result
assert "Volume" in result
assert "2025-03" in result  # 日期格式正确
# 数据行数 > 0
```

**依赖**: Step 1 (market_utils)

---

### Step 3: `akshare_stock.py` — 技术指标

**文件**: `tradingagents/dataflows/akshare_stock.py` (续)

**任务**:
- [ ] 实现 `_fetch_and_cache_cn_data(symbol, config) -> pd.DataFrame` 内部函数:
  - 获取 15 年日线数据: `ak.stock_zh_a_hist(symbol, period="daily", start_date=15年前, end_date=今天, adjust="qfq")`
  - 缓存到 `data_cache/{symbol}-AKShare-data-{start}-{end}.csv`
  - 缓存命中直接读取
  - 列名映射 + 格式归一化
- [ ] 实现 `get_indicators(symbol, indicator, curr_date, look_back_days) -> str`
  - 调用 `_fetch_and_cache_cn_data()` 获取数据
  - 导入并复用 `stockstats_utils._clean_dataframe()` 和 `stockstats.wrap()`
  - 与 `y_finance.py` 的 `get_stock_stats_indicators_window()` 逻辑一致:
    - 支持相同的指标集 (close_50_sma, rsi, macd, boll 等)
    - 按 look_back_days 窗口输出
    - 非交易日标记 "N/A: Not a trading day"
  - 输出格式与美股完全相同

**验证标准**:
```python
result = get_indicators("600519", "rsi", "2025-03-14", 30)
assert "rsi" in result.lower()
assert "2025-03-14" in result
assert "2025-02" in result  # 有 30 天回看
```

**依赖**: Step 2, `stockstats_utils.py` (现有, 只读)

---

### Step 4: 创建 `akshare_news.py`

**文件**: `tradingagents/dataflows/akshare_news.py` (新增)

**任务**:
- [ ] 实现 `get_news(ticker, start_date, end_date) -> str`
  - 调用 `ak.stock_news_em(symbol=ticker)`
  - 提取: 标题、内容(摘要)、发布时间、文章来源、新闻链接
  - 日期过滤 (start_date ~ end_date)
  - 输出 Markdown 格式:
    ```
    ## {ticker} 新闻, {start_date} 至 {end_date}:

    ### {标题} (来源: {来源})
    {摘要}
    链接: {url}
    ```
  - 无新闻时返回友好提示
- [ ] 实现 `get_global_news(curr_date, look_back_days, limit) -> str`
  - 调用 `ak.stock_info_global_em()` + `ak.stock_info_cjzc_em()`
  - 标题去重 (set)
  - 按日期过滤、限制条数
  - 输出 Markdown 格式 (与 `yfinance_news.get_global_news_yfinance` 对齐)

**验证标准**:
```python
news = get_news("600519", "2025-03-01", "2025-03-14")
assert "新闻" in news or "No news" in news.lower() or "没有" in news
global_news = get_global_news("2025-03-14", 7, 5)
assert "市场" in global_news or "news" in global_news.lower()
```

**依赖**: 无 (可与 Step 2/3 并行)

---

### Step 5: 更新 `pyproject.toml`

**文件**: `pyproject.toml` (修改)

**任务**:
- [ ] 在 `dependencies` 中添加:
  ```
  "akshare>=1.14.0",
  ```
- [ ] 在 `[project.optional-dependencies]` 新增 (如不存在则创建):
  ```toml
  [project.optional-dependencies]
  cn = ["akshare>=1.14.0", "tushare>=1.4.0"]
  ```
  > akshare 为必选依赖 (A 股基础), tushare 为可选依赖 (fallback)

**验证标准**:
```bash
pip install -e ".[cn]"  # 安装含中国数据源的版本
python -c "import akshare; print(akshare.__version__)"
```

**依赖**: 无 (可最先执行)

---

### Step 6: 数据层单元测试

**文件**: `tests/test_cn_dataflows.py` (新增)

**任务**:
- [ ] `test_detect_market()`: 覆盖所有代码格式
- [ ] `test_normalize_symbol()`: 各种输入标准化
- [ ] `test_get_exchange()`: 沪/深判断
- [ ] `test_akshare_stock_data()`: 获取日线 OHLCV，验证列名、格式、数据完整性
- [ ] `test_akshare_indicators()`: RSI 计算，验证与 stockstats 逻辑一致
- [ ] `test_akshare_news()`: 获取新闻，验证 Markdown 格式
- [ ] `test_column_mapping()`: 验证所有中文列名正确映射为英文
- [ ] `test_volume_conversion()`: 验证成交量 手→股 转换

**验证标准**: `pytest tests/test_cn_dataflows.py -v` 全部通过

**依赖**: Step 1-4

---

### Step 7: `akshare_stock.py` — 基本面数据

**文件**: `tradingagents/dataflows/akshare_stock.py` (续)

**任务**:
- [ ] 实现 `get_fundamentals(ticker, curr_date) -> str`
  - 调用 `ak.stock_individual_info_em(symbol=ticker)`
  - 输出字段: 公司名称、行业、总市值、流通市值、PE、PB、每股收益等
  - 所有金额标注 `(CNY)`
  - 格式与 `y_finance.get_fundamentals()` 对齐
- [ ] 实现 `get_balance_sheet(ticker, freq, curr_date) -> str`
  - 调用 `ak.stock_balance_sheet_by_report_em(symbol=ticker)`
  - 输出 CSV 字符串
- [ ] 实现 `get_cashflow(ticker, freq, curr_date) -> str`
  - 调用 `ak.stock_cash_flow_sheet_by_report_em(symbol=ticker)`
- [ ] 实现 `get_income_statement(ticker, freq, curr_date) -> str`
  - 调用 `ak.stock_profit_sheet_by_report_em(symbol=ticker)`
- [ ] 实现 `get_insider_transactions(ticker) -> str`
  - 尝试 `ak.stock_dzjy_mdetail(symbol=ticker)` (大宗交易)
  - 无数据时返回: "A 股暂无直接的内部交易数据，请参考大宗交易和股东增减持信息"

**验证标准**:
```python
fundamentals = get_fundamentals("600519")
assert "CNY" in fundamentals or "人民币" in fundamentals
```

**依赖**: Step 2 (复用 _normalize 函数)

---

## Phase 1 检查点

完成 Step 1-7 后进行整体验证:

```python
# 手动验证脚本
from tradingagents.dataflows.market_utils import detect_market, get_market_info
from tradingagents.dataflows.akshare_stock import get_stock_data, get_indicators, get_fundamentals
from tradingagents.dataflows.akshare_news import get_news, get_global_news

# 市场识别
info = get_market_info("600519")
print(info)  # {"market": "cn", "exchange": "SH", "currency": "CNY", ...}

# 行情数据
print(get_stock_data("600519", "2025-03-01", "2025-03-14"))

# 技术指标
print(get_indicators("600519", "rsi", "2025-03-14", 30))

# 新闻
print(get_news("600519", "2025-03-01", "2025-03-14"))

# 基本面
print(get_fundamentals("600519"))
```

---

## Phase 2: 路由集成层

**目标**: 现有 vendor 路由机制能自动识别 A 股 symbol 并路由到 akshare。

### Step 8: 增强 `interface.py`

**文件**: `tradingagents/dataflows/interface.py` (修改)

**任务**:
- [ ] 新增 import: akshare_stock 所有函数、akshare_news 函数、market_utils 函数
- [ ] `VENDOR_LIST` 追加 `"akshare"`
- [ ] `VENDOR_METHODS` 每个方法新增 `"akshare": ...` 条目:
  - `get_stock_data` → `get_akshare_stock`
  - `get_indicators` → `get_akshare_indicators`
  - `get_fundamentals` → `get_akshare_fundamentals`
  - `get_balance_sheet` → `get_akshare_balance_sheet`
  - `get_cashflow` → `get_akshare_cashflow`
  - `get_income_statement` → `get_akshare_income_statement`
  - `get_insider_transactions` → `get_akshare_insider_transactions`
  - `get_news` → `get_akshare_news`
  - `get_global_news` → `get_akshare_global_news`
- [ ] 新增 `get_vendor_cn(category, method) -> str` 函数:
  - 读取 `config["cn_tool_vendors"]` (工具级) 或 `config["cn_data_vendors"]` (分类级)
- [ ] 修改 `route_to_vendor()`:
  - 提取第一个参数 symbol
  - 对非 `get_global_news` 方法调用 `detect_market(symbol)`
  - `market == "cn"` → 调用 `get_vendor_cn()` 获取 vendor
  - `market == "us"` → 原有 `get_vendor()` 逻辑 (不变)
  - 对 symbol 调用 `normalize_symbol()` 后传递给实现函数
  - fallback 异常链: 保留 `AlphaVantageRateLimitError`, 新增通用 `Exception` 捕获 (仅对 A 股 vendor)
- [ ] 对 `get_global_news`: 从 config 中读取 `get_market_context()` 判断市场

**验证标准**:
```python
from tradingagents.dataflows.interface import route_to_vendor
# A 股自动路由
result = route_to_vendor("get_stock_data", "600519", "2025-03-01", "2025-03-14")
assert "Date" in result and "Close" in result
# 美股不受影响
result = route_to_vendor("get_stock_data", "NVDA", "2025-03-01", "2025-03-14")
assert "Date" in result
```

**依赖**: Phase 1 全部完成

---

### Step 9: 增强 `config.py`

**文件**: `tradingagents/dataflows/config.py` (修改)

**任务**:
- [ ] 新增线程安全的市场上下文管理:
  ```python
  import threading
  _market_context = threading.local()

  def set_market_context(market: str): ...
  def get_market_context() -> str: ...
  ```
- [ ] 确保 `get_config()` 包含 `cn_data_vendors` 和 `cn_tool_vendors` 的默认值

**验证标准**:
```python
from tradingagents.dataflows.config import set_market_context, get_market_context
set_market_context("cn")
assert get_market_context() == "cn"
# 默认值
from tradingagents.dataflows.config import get_config
config = get_config()
assert "cn_data_vendors" in config
```

**依赖**: 无 (可与 Step 8 并行)

---

### Step 10: 扩展 `default_config.py`

**文件**: `tradingagents/default_config.py` (修改)

**任务**:
- [ ] 在 `DEFAULT_CONFIG` 中新增:
  ```python
  "cn_data_vendors": {
      "core_stock_apis": "akshare",
      "technical_indicators": "akshare",
      "fundamental_data": "akshare",
      "news_data": "akshare",
  },
  "cn_tool_vendors": {},
  "tushare_token": os.getenv("TUSHARE_TOKEN", ""),
  "cn_request_interval": 0.3,
  ```

**验证标准**: `from tradingagents.default_config import DEFAULT_CONFIG; assert "cn_data_vendors" in DEFAULT_CONFIG`

**依赖**: 无 (可与 Step 8/9 并行)

---

### Step 11: 路由集成测试

**文件**: `tests/test_cn_routing.py` (新增)

**任务**:
- [ ] `test_route_cn_stock_data()`: 600519 自动走 akshare
- [ ] `test_route_us_stock_data()`: NVDA 仍走 yfinance (回归)
- [ ] `test_route_cn_indicators()`: A 股技术指标路由
- [ ] `test_route_cn_news()`: A 股新闻路由
- [ ] `test_route_cn_fundamentals()`: A 股基本面路由
- [ ] `test_symbol_normalization_in_route()`: "600519.SH" 经路由后变为 "600519"
- [ ] `test_market_context_for_global_news()`: set_market_context("cn") 后 global_news 走 akshare

**验证标准**: `pytest tests/test_cn_routing.py -v` 全部通过

**依赖**: Step 8-10

---

## Phase 2 检查点

```python
from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.dataflows.config import set_market_context

# 完整路由验证
set_market_context("cn")

# 所有工具通过路由调用 A 股数据
print(route_to_vendor("get_stock_data", "600519", "2025-03-01", "2025-03-14"))
print(route_to_vendor("get_indicators", "600519", "rsi", "2025-03-14", 30))
print(route_to_vendor("get_news", "600519", "2025-03-01", "2025-03-14"))
print(route_to_vendor("get_global_news", "2025-03-14", 7, 5))
print(route_to_vendor("get_fundamentals", "600519"))

# 美股回归验证
set_market_context("us")
print(route_to_vendor("get_stock_data", "NVDA", "2025-03-01", "2025-03-14"))
```

---

## Phase 3: Agent 适配层

**目标**: Agent 分析 A 股时自动切换中文 prompt + 规则感知。

### Step 12: 创建 `cn_market_prompts.py`

**文件**: `tradingagents/agents/utils/cn_market_prompts.py` (新增)

**任务**:
- [ ] 定义 `CN_MARKET_RULES` 常量 (A 股交易制度 + 市场特征 + 货币)
- [ ] 定义 `CN_ANALYST_SUFFIX` (分析师中文后缀)
- [ ] 定义 `CN_RESEARCHER_SUFFIX` (研究员/辩论中文后缀)
- [ ] 定义 `CN_TRADER_SUFFIX` (交易员中文后缀, 含 "最终交易建议" 格式)
- [ ] 定义 `CN_RISK_SUFFIX` (风控中文后缀)
- [ ] 定义辅助函数 `get_prompt_suffix(market: str, role: str) -> str`
  - `market != "cn"` → 返回空字符串
  - `role` ∈ {"analyst", "researcher", "trader", "risk"} → 返回对应后缀

**验证标准**: 导入不报错，所有常量非空

**依赖**: 无 (可独立开发)

---

### Step 13: 扩展 `agent_states.py`

**文件**: `tradingagents/agents/utils/agent_states.py` (修改)

**任务**:
- [ ] 在 `AgentState` 中新增字段:
  ```python
  market_context: Annotated[dict, "Market context (market, exchange, currency, language)"]
  ```
- [ ] 确保默认值兼容 (空 dict 不影响现有流程)

**验证标准**: 现有单测不受影响

**依赖**: 无

---

### Step 14: 改造 4 个 Analyst Agent

**文件** (均修改):
- `tradingagents/agents/analysts/market_analyst.py`
- `tradingagents/agents/analysts/social_media_analyst.py`
- `tradingagents/agents/analysts/news_analyst.py`
- `tradingagents/agents/analysts/fundamentals_analyst.py`

**每个文件的改动模式完全相同**:

- [ ] 新增 import:
  ```python
  from tradingagents.agents.utils.cn_market_prompts import get_prompt_suffix
  ```
- [ ] 在工厂函数内的 `xxx_node(state)` 中:
  - 读取 `market_ctx = state.get("market_context", {})`
  - 在现有 `system_prompt` 字符串末尾追加:
    ```python
    system_prompt += get_prompt_suffix(market_ctx.get("market", "us"), "analyst")
    ```
- [ ] 不修改任何原有 prompt 内容、不修改 tool 调用逻辑

**验证标准**: 导入不报错, 美股调用时 suffix 为空字符串 (无影响)

**依赖**: Step 12, 13

---

### Step 15: 改造 Researcher + Manager Agent

**文件** (均修改):
- `tradingagents/agents/researchers/bull_researcher.py`
- `tradingagents/agents/researchers/bear_researcher.py`
- `tradingagents/agents/managers/research_manager.py`

**改动模式**:
- [ ] 同 Step 14，但使用 `get_prompt_suffix(market, "researcher")`
- [ ] 特别注意 Research Manager: 它读取辩论历史，prompt 后缀在其 system prompt 末尾追加

**依赖**: Step 12, 13

---

### Step 16: 改造 Risk Debator + Trader Agent

**文件** (均修改):
- `tradingagents/agents/risk_mgmt/aggressive_debator.py`
- `tradingagents/agents/risk_mgmt/conservative_debator.py`
- `tradingagents/agents/risk_mgmt/neutral_debator.py`
- `tradingagents/agents/managers/risk_manager.py`
- `tradingagents/agents/trader/trader.py`

**改动模式**:
- [ ] Risk 4 个: `get_prompt_suffix(market, "risk")`
- [ ] Trader: `get_prompt_suffix(market, "trader")`
- [ ] Trader 特殊: CN_TRADER_SUFFIX 中的信号格式为 "最终交易建议: **买入/持有/卖出**"

**依赖**: Step 12, 13

---

### Step 17: 增强 `signal_processing.py`

**文件**: `tradingagents/graph/signal_processing.py` (修改)

**任务**:
- [ ] 阅读当前 `process_signal()` 的信号提取逻辑
- [ ] 新增中文信号识别:
  - 匹配 "最终交易建议" 或 "FINAL TRANSACTION PROPOSAL"
  - "买入" / "BUY" → BUY
  - "卖出" / "SELL" → SELL
  - "持有" / "HOLD" → HOLD
- [ ] 确保英文信号识别逻辑不变

**验证标准**:
```python
assert process_signal("...最终交易建议: **买入**...") == "BUY"
assert process_signal("...FINAL TRANSACTION PROPOSAL: **SELL**...") == "SELL"
```

**依赖**: 无 (可独立)

---

### Step 18: 改造 `propagation.py` + `trading_graph.py`

**文件**:
- `tradingagents/graph/propagation.py` (修改)
- `tradingagents/graph/trading_graph.py` (修改)

**propagation.py 任务**:
- [ ] 在 `create_initial_state()` 中:
  ```python
  from tradingagents.dataflows.market_utils import get_market_info
  market_context = get_market_info(company_name)
  ```
  添加到返回的初始状态 dict 中

**trading_graph.py 任务**:
- [ ] 在 `propagate()` 方法中, `company_name` 解析后:
  ```python
  from tradingagents.dataflows.market_utils import detect_market
  from tradingagents.dataflows.config import set_market_context
  market = detect_market(company_name)
  set_market_context(market)
  ```
- [ ] 确保 `set_market_context()` 在所有数据获取调用之前执行

**验证标准**: `graph.propagate("600519", "2025-03-14")` 完整运行不报错

**依赖**: Step 8-16 全部完成

---

## Phase 3 检查点 (关键里程碑)

这是最重要的端到端验证:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph

graph = TradingAgentsGraph(config={
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5-mini",  # 测试用小模型
    "quick_think_llm": "gpt-5-mini",
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
})

# A 股端到端测试
state, signal = graph.propagate("600519", "2025-03-14")
print(f"Signal: {signal}")                    # 应为 BUY/SELL/HOLD
print(f"Market Report 语言: {'中文' if '分析' in state['market_report'] else '英文'}")

# 美股回归测试
state2, signal2 = graph.propagate("NVDA", "2025-03-14")
print(f"Signal: {signal2}")                   # 仍正常工作
```

---

## Phase 4: 备用源 + 完善

**目标**: tushare fallback、Memory 隔离、生产就绪。

### Step 19: 创建 `tushare_stock.py`

**文件**: `tradingagents/dataflows/tushare_stock.py` (新增)

**任务**:
- [ ] 定义 `TushareError(Exception)` 自定义异常
- [ ] 实现 `_get_tushare_api()`:
  - 从 config 或环境变量读取 `TUSHARE_TOKEN`
  - 无 token 时 raise `TushareError("TUSHARE_TOKEN not configured")`
- [ ] 实现所有函数 (签名与 akshare_stock.py 完全相同):
  - `get_stock_data()` → `ts.pro_bar(ts_code=..., adj='qfq', ...)`
  - `get_indicators()` → 获取日线 + stockstats 计算
  - `get_fundamentals()` → `ts.daily_basic()` + `ts.stock_company()`
  - `get_balance_sheet()` → `ts.balancesheet()`
  - `get_cashflow()` → `ts.cashflow()`
  - `get_income_statement()` → `ts.income()`
  - `get_insider_transactions()` → `ts.stk_holdertrade()`
- [ ] tushare ts_code 格式: `600519.SH` / `000858.SZ` (需从纯数字转换)
- [ ] 在 `interface.py` 中注册 tushare vendor 到 `VENDOR_METHODS`
- [ ] `interface.py` fallback 异常增加 `TushareError`

**验证标准**: 配置 tushare 后 fallback 链路: akshare 失败 → tushare 接管

**依赖**: Phase 2 完成

---

### Step 20: Memory 市场隔离

**文件**: `tradingagents/graph/trading_graph.py` (修改)

**任务**:
- [ ] Memory 初始化改为延迟 + 按市场前缀:
  ```python
  self._memories = {}

  def _get_memories(self, market):
      if market not in self._memories:
          prefix = f"{market}_"
          self._memories[market] = {
              "bull": FinancialSituationMemory(f"{prefix}bull_memory", self.config),
              ...
          }
      return self._memories[market]
  ```
- [ ] `propagate()` 中根据 market 获取对应 memories
- [ ] `reflect_and_remember()` 使用对应市场的 memories
- [ ] 向后兼容: 检测旧版无前缀 memory 文件，首次使用时自动重命名为 `us_` 前缀
- [ ] `graph_setup` 需要接收动态 memory (修改构造或方法签名)

**验证标准**:
```python
# 分析 A 股后检查
assert os.path.exists("tradingagents/memory/cn_bull_memory.json")
# 分析美股后检查
assert os.path.exists("tradingagents/memory/us_bull_memory.json")
# 旧文件已迁移
assert not os.path.exists("tradingagents/memory/bull_memory.json")
```

**依赖**: Phase 3 完成

---

## Phase 4 检查点 (最终验证)

```python
# 1. tushare fallback 测试 (模拟 akshare 失败)
import unittest.mock as mock
with mock.patch("tradingagents.dataflows.akshare_stock.get_stock_data", side_effect=Exception("模拟失败")):
    result = route_to_vendor("get_stock_data", "600519", "2025-03-01", "2025-03-14")
    # 应自动 fallback 到 tushare (需配置 token)

# 2. Memory 隔离验证
graph.propagate("600519", "2025-03-14")
graph.propagate("NVDA", "2025-03-14")
# 检查 cn_* 和 us_* memory 文件分别存在

# 3. 完整回归: 美股分析结果与改造前一致
```

---

## 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| akshare 接口变更 | 中 | 高 | 固定版本号; 封装层隔离; 单测覆盖 |
| A 股数据格式不一致 | 中 | 中 | `_normalize_akshare_df` 统一处理; 详尽的列名映射 |
| LLM 中文 prompt 效果差 | 低 | 中 | Prompt 迭代优化; 可切换回英文 |
| stockstats 与 A 股数据兼容 | 低 | 高 | Phase 1 Step 3 提前验证 |
| tushare token 获取困难 | 中 | 低 | tushare 为可选; akshare 为主力 |

---

## 执行建议

**并行优化**: 以下 Step 可并行执行:
- Step 1 + Step 4 + Step 5 (无依赖)
- Step 9 + Step 10 + Step 12 (无依赖)
- Step 14 + Step 15 + Step 16 + Step 17 (仅依赖 Step 12/13)

**最快路径** (关键路径):
```
Step 5 → Step 1 → Step 2 → Step 3 → Step 8 → Step 18 → Phase 3 检查点
  (并行)   Step 4         Step 7
  (并行)         Step 12 → Step 14/15/16 → Step 17
```

**建议先做 Step 5 (pyproject.toml) + Step 1 (market_utils) + Step 12 (prompts)** 三个独立模块，然后其余模块可快速推进。
