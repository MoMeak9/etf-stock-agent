# A 股股票分析支持 — 技术架构设计

## 目录

1. [架构总览](#1-架构总览)
2. [模块设计](#2-模块设计)
3. [数据流设计](#3-数据流设计)
4. [接口规格](#4-接口规格)
5. [Agent Prompt 适配](#5-agent-prompt-适配)
6. [配置系统扩展](#6-配置系统扩展)
7. [Memory 系统隔离](#7-memory-系统隔离)
8. [文件变更清单](#8-文件变更清单)
9. [实施阶段划分](#9-实施阶段划分)

---

## 1. 架构总览

### 1.1 设计原则

- **向后兼容**: 所有现有美股功能不受影响，默认行为不变
- **最小侵入**: 通过现有 vendor 路由机制扩展，不改变核心 Agent 架构
- **市场自动识别**: 用户输入股票代码后系统自动判断市场，无需手动配置
- **数据格式统一**: A 股数据在 dataflow 层完成格式归一化，上层 Agent 无感知

### 1.2 系统架构图

```
用户输入 (600519 / NVDA)
        │
        ▼
┌─────────────────────────┐
│   market_utils.py       │  ← 新增: 市场识别 & 代码标准化
│   detect_market(symbol) │
│   normalize_symbol()    │
└────────┬────────────────┘
         │ market="cn" / "us"
         ▼
┌─────────────────────────────────────────────────────┐
│                  interface.py (增强)                  │
│                                                      │
│  route_to_vendor(method, *args)                      │
│    ├─ market="us" → data_vendors 配置                │
│    │   fallback: yfinance → alpha_vantage            │
│    └─ market="cn" → cn_data_vendors 配置             │
│        fallback: akshare → tushare                   │
└──┬──────────┬──────────┬──────────┬─────────────────┘
   │          │          │          │
   ▼          ▼          ▼          ▼
┌────────┐┌────────┐┌─────────┐┌──────────┐
│akshare ││tushare ││yfinance ││alpha_    │
│_stock  ││_stock  ││         ││vantage   │
│.py     ││.py     ││         ││          │
│(新增)  ││(新增)  ││(不变)   ││(不变)    │
└────────┘└────────┘└─────────┘└──────────┘

┌─────────────────────────────────────────────────────┐
│           Agent Layer (prompt 动态适配)               │
│                                                      │
│  market="cn" → 注入中文 prompt + A 股规则知识         │
│  market="us" → 保持原有英文 prompt (不变)             │
│                                                      │
│  Memory 按市场前缀隔离:                               │
│    cn_bull_memory / us_bull_memory                    │
└─────────────────────────────────────────────────────┘
```

---

## 2. 模块设计

### 2.1 新增模块: `market_utils.py`

**位置**: `tradingagents/dataflows/market_utils.py`

**职责**: 市场识别、代码标准化、A 股交易日历

```python
# ============================================================
# 核心函数签名
# ============================================================

def detect_market(symbol: str) -> str:
    """
    根据股票代码自动识别市场。

    规则:
      - 纯字母 (NVDA, AAPL) → "us"
      - 6位纯数字 (600519, 000858) → "cn"
      - 带后缀 (000858.SZ, 600519.SH) → "cn"
      - 带前缀 (SZ000858, SH600519) → "cn"

    Returns: "us" | "cn"
    """

def normalize_symbol(symbol: str, market: str) -> str:
    """
    将用户输入标准化为各数据源需要的格式。

    A 股:
      输入: "600519" / "600519.SH" / "SH600519"
      输出: "600519" (akshare 需要纯 6 位数字)

    美股:
      输入: "nvda" / "NVDA"
      输出: "NVDA" (大写)
    """

def get_exchange(symbol: str) -> str:
    """
    根据 A 股代码判断交易所。

    规则:
      - 6/9 开头 → "SH" (上交所)
      - 0/2/3 开头 → "SZ" (深交所)

    Returns: "SH" | "SZ"
    """

def get_cn_trade_dates(start_date: str, end_date: str) -> list[str]:
    """
    获取指定日期范围内的 A 股交易日列表。
    使用 akshare 的 tool_trade_date_hist_sina() 接口。
    结果缓存到本地避免重复请求。
    """

def get_market_info(symbol: str) -> dict:
    """
    返回市场相关元信息，供 Agent prompt 注入。

    Returns: {
        "market": "cn" | "us",
        "exchange": "SH" | "SZ" | "NYSE" | "NASDAQ",
        "currency": "CNY" | "USD",
        "language": "zh" | "en",
        "symbol_normalized": "600519",
        "symbol_display": "600519.SH",
    }
    """
```

### 2.2 新增模块: `akshare_stock.py`

**位置**: `tradingagents/dataflows/akshare_stock.py`

**职责**: 封装 akshare A 股行情 & 基本面接口，输出格式与 yfinance 对齐

```python
# ============================================================
# 列名映射常量
# ============================================================
COLUMN_MAP = {
    "日期": "Date",
    "开盘": "Open",
    "收盘": "Close",
    "最高": "High",
    "最低": "Low",
    "成交量": "Volume",      # 注意: akshare 单位为"手"(100股), 需 ×100
    "成交额": "Amount",
    "振幅": "Amplitude",
    "涨跌幅": "Change_Pct",
    "涨跌额": "Change_Amt",
    "换手率": "Turnover",
}

# ============================================================
# 核心函数签名 (与 yfinance 对齐)
# ============================================================

def get_stock_data(symbol: str, start_date: str, end_date: str) -> str:
    """
    获取 A 股日线 OHLCV 数据。

    实现:
      1. ak.stock_zh_a_hist(symbol=symbol, period="daily",
                            start_date=start_date.replace("-",""),
                            end_date=end_date.replace("-",""),
                            adjust="qfq")
      2. 列名中文→英文映射
      3. 成交量 ×100 (手→股)
      4. 日期格式 YYYYMMDD → YYYY-MM-DD
      5. 价格保留 2 位小数
      6. 输出 CSV 字符串 + header (与 get_YFin_data_online 格式一致)

    请求间隔: time.sleep(0.3) 避免封禁
    """

def get_indicators(
    symbol: str, indicator: str, curr_date: str, look_back_days: int = 30
) -> str:
    """
    获取 A 股技术指标。

    实现:
      1. 使用 akshare 获取 15 年日线数据 (缓存到 data_cache/)
      2. 中文列名 → 英文列名映射
      3. 复用 stockstats.wrap() 计算指标 (与美股完全相同的指标计算逻辑)
      4. 按 look_back_days 窗口输出

    缓存文件名: {symbol}-AKShare-data-{start}-{end}.csv
    """

def get_fundamentals(ticker: str, curr_date: str = None) -> str:
    """
    获取 A 股公司基本面概览。

    实现:
      ak.stock_individual_info_em(symbol=ticker)
      → 公司名称、行业、市值、PE、PB 等
      输出: 与 yfinance get_fundamentals 相同格式的文本
      货币标注: 所有金额标注 "(CNY)"
    """

def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """
    获取 A 股资产负债表。

    实现: ak.stock_balance_sheet_by_report_em(symbol=ticker)
    输出: CSV 格式，与 yfinance 格式对齐
    """

def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """同上, ak.stock_cash_flow_sheet_by_report_em()"""

def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None) -> str:
    """同上, ak.stock_profit_sheet_by_report_em()"""

def get_insider_transactions(ticker: str) -> str:
    """
    A 股无直接 insider transaction 数据。
    返回大股东增减持信息 (akshare 龙虎榜/股东变动接口)。
    若无可用数据，返回友好提示: "A 股暂无内部交易数据，请参考大股东增减持信息"
    """
```

### 2.3 新增模块: `akshare_news.py`

**位置**: `tradingagents/dataflows/akshare_news.py`

**职责**: A 股中文财经新闻

```python
def get_news(ticker: str, start_date: str, end_date: str) -> str:
    """
    获取个股相关新闻。

    实现:
      ak.stock_news_em(symbol=ticker)
      → 标题、内容摘要、来源、发布时间
      按日期范围过滤
      输出: Markdown 格式 (与 yfinance_news 一致)

      ## {ticker} 新闻, {start_date} 至 {end_date}:

      ### 标题 (来源: 东方财富)
      摘要内容...
      链接: https://...
    """

def get_global_news(curr_date: str, look_back_days: int = 7, limit: int = 10) -> str:
    """
    获取中国宏观财经新闻。

    实现:
      ak.stock_info_global_em()  # 全球财经资讯
      + ak.stock_info_cjzc_em()  # 财经早餐

      去重、按日期过滤、限制条数
      输出: Markdown 格式

      ## 中国及全球市场新闻, {start_date} 至 {curr_date}:

      ### 标题 (来源: 东方财富)
      摘要...
    """
```

### 2.4 新增模块: `tushare_stock.py`

**位置**: `tradingagents/dataflows/tushare_stock.py`

**职责**: tushare 作为 A 股备用数据源 (fallback)

```python
# 所有函数签名与 akshare_stock.py 完全相同
# 差异仅在实现层:
#   - 需要 TUSHARE_TOKEN 环境变量
#   - 使用 ts.pro_api() 调用
#   - 数据格式转换为统一输出格式

def get_stock_data(symbol, start_date, end_date) -> str: ...
def get_indicators(symbol, indicator, curr_date, look_back_days) -> str: ...
def get_fundamentals(ticker, curr_date) -> str: ...
def get_balance_sheet(ticker, freq, curr_date) -> str: ...
def get_cashflow(ticker, freq, curr_date) -> str: ...
def get_income_statement(ticker, freq, curr_date) -> str: ...
def get_insider_transactions(ticker) -> str: ...

# 新增自定义异常 (用于 fallback 触发)
class TushareError(Exception):
    """tushare 请求失败时抛出，触发 fallback 机制"""
```

---

## 3. 数据流设计

### 3.1 核心数据流: 市场感知路由

```
用户: graph.propagate("600519", "2025-03-14")
        │
        ▼
  Propagator.create_initial_state()
        │ company_of_interest = "600519"
        ▼
  AgentState 新增字段:
    market_context = get_market_info("600519")
    # → {"market": "cn", "exchange": "SH", "currency": "CNY", ...}
        │
        ▼
  Market Analyst Node
    │ 调用 get_stock_data("600519", ...)
    │     ▼
    │ route_to_vendor("get_stock_data", "600519", ...)
    │     │ detect_market("600519") → "cn"
    │     │ 查 cn_data_vendors["core_stock_apis"] → "akshare"
    │     ▼
    │ akshare_stock.get_stock_data("600519", ...)
    │     │ ak.stock_zh_a_hist(symbol="600519", ...)
    │     │ 列名映射 + 格式归一化
    │     ▼
    │ 返回: CSV 格式字符串 (Date, Open, High, Low, Close, Volume)
    ▼
  Agent 接收到与美股完全相同格式的数据
  但 system prompt 已注入中文指令 + A 股规则
```

### 3.2 技术指标数据流

```
get_indicators("600519", "rsi", "2025-03-14", 30)
    │
    ▼ route_to_vendor → akshare
    │
    ▼ akshare_stock.get_indicators()
    │
    ├─ 检查缓存: data_cache/600519-AKShare-data-2010-01-01-2025-03-16.csv
    │  ├─ 存在 → pd.read_csv()
    │  └─ 不存在 → ak.stock_zh_a_hist(15年数据) → 保存 CSV
    │
    ▼ 列名映射: 日期→Date, 开盘→Open, 收盘→Close, ...
    │
    ▼ stockstats.wrap(data)  ← 复用完全相同的 stockstats 逻辑
    │
    ▼ df["rsi"]  ← 触发指标计算
    │
    ▼ 按 look_back_days 窗口提取 → 输出字符串
```

### 3.3 新闻数据流

```
get_news("600519", "2025-03-07", "2025-03-14")
    │
    ▼ route_to_vendor → akshare
    │
    ▼ akshare_news.get_news()
    │   ak.stock_news_em(symbol="600519")
    │   → DataFrame: [标题, 内容, 发布时间, 文章来源, 新闻链接]
    │
    ▼ 日期过滤 (start_date ~ end_date)
    │
    ▼ 格式化为 Markdown:
      ## 600519 新闻, 2025-03-07 至 2025-03-14:
      ### 贵州茅台2024年净利润同比增长... (来源: 东方财富)
      ...
```

---

## 4. 接口规格

### 4.1 interface.py 增强设计

**关键改动**: `route_to_vendor()` 增加市场感知能力

```python
# ============================================================
# interface.py 改动方案
# ============================================================

# 1. 新增 import
from .akshare_stock import (
    get_stock_data as get_akshare_stock,
    get_indicators as get_akshare_indicators,
    get_fundamentals as get_akshare_fundamentals,
    get_balance_sheet as get_akshare_balance_sheet,
    get_cashflow as get_akshare_cashflow,
    get_income_statement as get_akshare_income_statement,
    get_insider_transactions as get_akshare_insider_transactions,
)
from .akshare_news import (
    get_news as get_akshare_news,
    get_global_news as get_akshare_global_news,
)
from .tushare_stock import (
    get_stock_data as get_tushare_stock,
    get_indicators as get_tushare_indicators,
    # ... 其余同理
    TushareError,
)
from .market_utils import detect_market, normalize_symbol

# 2. VENDOR_LIST 扩展
VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
    "akshare",       # 新增
    "tushare",       # 新增
]

# 3. VENDOR_METHODS 扩展 (每个方法增加 akshare/tushare 实现)
VENDOR_METHODS = {
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
        "akshare": get_akshare_stock,         # 新增
        "tushare": get_tushare_stock,          # 新增
    },
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
        "akshare": get_akshare_indicators,     # 新增
        "tushare": get_tushare_indicators,     # 新增
    },
    # ... 其余方法同理
}

# 4. route_to_vendor 增强: 市场感知路由
def route_to_vendor(method: str, *args, **kwargs):
    """
    增强: 从第一个参数 (symbol/ticker) 自动检测市场,
    根据市场选择对应的 vendor 配置。
    """
    # 提取 symbol (所有工具函数的第一个参数都是 symbol/ticker)
    symbol = args[0] if args else kwargs.get("symbol", kwargs.get("ticker", ""))

    # 对于 get_global_news，第一个参数是 curr_date 不是 symbol
    # 此时使用默认市场配置
    if method == "get_global_news":
        market = _get_current_market_context()  # 从全局上下文获取
    else:
        market = detect_market(symbol) if symbol else "us"

    # 根据市场选择 vendor 配置
    category = get_category_for_method(method)
    if market == "cn":
        vendor_config = get_vendor_cn(category, method)
    else:
        vendor_config = get_vendor(category, method)

    # 标准化 symbol 传给具体实现
    if symbol and method != "get_global_news":
        normalized = normalize_symbol(symbol, market)
        args = (normalized,) + args[1:]

    # 原有 fallback 逻辑 (增加 TushareError 作为 fallback 触发条件)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]
    # ... fallback chain 逻辑同原有实现
    # 新增: except TushareError 也触发 fallback
```

### 4.2 get_global_news 市场上下文方案

`get_global_news` 的第一个参数是 `curr_date` 而非 symbol，需要特殊处理:

```python
# config.py 增加线程安全的市场上下文
import threading

_market_context = threading.local()

def set_market_context(market: str):
    """在 propagate() 开始时设置当前分析的市场"""
    _market_context.market = market

def get_market_context() -> str:
    """获取当前市场上下文，默认 us"""
    return getattr(_market_context, 'market', 'us')
```

**调用时机**: 在 `TradingAgentsGraph.propagate()` 中，解析 `company_name` 后立即调用 `set_market_context()`。

### 4.3 AgentState 扩展

```python
# agent_states.py 新增字段
class AgentState(MessagesState):
    company_of_interest: Annotated[str, "Company that we are interested in trading"]
    trade_date: Annotated[str, "What date we are trading at"]

    # 新增: 市场上下文
    market_context: Annotated[dict, "Market context info (market, exchange, currency, language)"]

    sender: Annotated[str, "Agent that sent this message"]
    # ... 其余字段不变
```

---

## 5. Agent Prompt 适配

### 5.1 设计方案: Prompt 后缀注入

**原则**: 不修改原有英文 prompt，通过**条件性后缀**追加中文指令和 A 股规则。

**实现位置**: 各 `create_xxx_analyst()` / `create_xxx_researcher()` 工厂函数中。

### 5.2 中文 Prompt 后缀定义

新增文件: `tradingagents/agents/utils/cn_market_prompts.py`

```python
# ============================================================
# A 股市场规则知识注入
# ============================================================

CN_MARKET_RULES = """
## A 股市场规则 (你必须在分析中考虑这些规则)

### 交易制度
- **T+1 交易**: 当日买入的股票，次日方可卖出。这意味着短线操作受限，需考虑隔夜风险。
- **涨跌停限制**:
  - 主板 (沪市/深市主板): ±10%
  - 创业板 (300xxx): ±20%
  - 科创板 (688xxx): ±20%
  - ST 股票: ±5%
- **交易时间**: 9:30-11:30, 13:00-15:00 (UTC+8)，含 1.5 小时午休
- **集合竞价**: 9:15-9:25 (开盘), 14:57-15:00 (收盘)
- **最小交易单位**: 100 股 (1手)

### 市场特征
- **散户主导**: A 股散户投资者占比高，市场情绪波动较大
- **政策敏感**: 政府政策（如降准降息、行业监管）对市场影响显著
- **板块轮动**: A 股存在明显的板块轮动现象
- **无做空机制**: 普通投资者无法直接做空（融券除外）

### 货币
- **计价货币**: 人民币 (CNY)
- 所有价格和财务数据均以人民币计价
"""

CN_ANALYST_SUFFIX = """
## 重要指令
- 请使用**中文**进行分析和输出报告
- 你正在分析的是**中国 A 股**上市公司
- 分析中必须考虑 A 股特有的交易规则 (涨跌停、T+1 等)
- 所有金额单位为**人民币 (CNY)**
- 新闻和舆情数据来源为中国财经媒体

""" + CN_MARKET_RULES

CN_RESEARCHER_SUFFIX = """
## 重要指令
- 请使用**中文**进行辩论和分析
- 你正在辩论的是**中国 A 股**上市公司的投资价值
- 请考虑 A 股特有的市场特征 (散户主导、政策敏感、板块轮动等)
- 请考虑 T+1 交易制度对短期策略的影响
- 涨跌停板制度意味着极端行情下可能无法及时止损

""" + CN_MARKET_RULES

CN_TRADER_SUFFIX = """
## 重要指令
- 请使用**中文**提供交易建议
- 你正在为**中国 A 股**股票提供交易方案
- **必须考虑**:
  - T+1 制度: 建议买入后至少持有至次日
  - 涨跌停: 追涨停板风险极高，跌停板可能无法卖出
  - 最小交易单位: 100 股 (1手)
  - 所有金额和收益以人民币 (CNY) 计
- 最终交易建议格式: "最终交易建议: **买入/持有/卖出**"

""" + CN_MARKET_RULES

CN_RISK_SUFFIX = """
## 重要指令
- 请使用**中文**进行风险分析
- 你正在评估**中国 A 股**股票的风险
- 特别关注:
  - 涨跌停风险: 连续跌停可能导致无法及时出场
  - 政策风险: 行业监管政策变化
  - 流动性风险: 小盘股流动性不足
  - 汇率风险 (如果涉及外资持仓)
  - T+1 制度下的隔夜风险

""" + CN_MARKET_RULES
```

### 5.3 Prompt 注入机制

在每个 Agent 工厂函数中增加条件判断:

```python
# 以 market_analyst.py 为例的改造模式

from tradingagents.agents.utils.cn_market_prompts import CN_ANALYST_SUFFIX

def create_market_analyst(llm, tool_node):
    def market_analyst_node(state):
        company = state["company_of_interest"]
        market_ctx = state.get("market_context", {})

        # 原有 system prompt
        system_prompt = "You are a Market Analyst..."  # 现有英文 prompt

        # A 股时追加中文后缀
        if market_ctx.get("market") == "cn":
            system_prompt += CN_ANALYST_SUFFIX

        # ... 原有调用逻辑不变
    return market_analyst_node
```

**改造的 Agent 清单** (所有 12 个 Agent 均需改造):

| Agent | 文件 | 使用的 Prompt 后缀 |
|-------|------|-------------------|
| Market Analyst | `analysts/market_analyst.py` | `CN_ANALYST_SUFFIX` |
| Social Media Analyst | `analysts/social_media_analyst.py` | `CN_ANALYST_SUFFIX` |
| News Analyst | `analysts/news_analyst.py` | `CN_ANALYST_SUFFIX` |
| Fundamentals Analyst | `analysts/fundamentals_analyst.py` | `CN_ANALYST_SUFFIX` |
| Bull Researcher | `researchers/bull_researcher.py` | `CN_RESEARCHER_SUFFIX` |
| Bear Researcher | `researchers/bear_researcher.py` | `CN_RESEARCHER_SUFFIX` |
| Research Manager | `managers/research_manager.py` | `CN_RESEARCHER_SUFFIX` |
| Trader | `trader/trader.py` | `CN_TRADER_SUFFIX` |
| Aggressive Debator | `risk_mgmt/aggressive_debator.py` | `CN_RISK_SUFFIX` |
| Conservative Debator | `risk_mgmt/conservative_debator.py` | `CN_RISK_SUFFIX` |
| Neutral Debator | `risk_mgmt/neutral_debator.py` | `CN_RISK_SUFFIX` |
| Risk Manager | `managers/risk_manager.py` | `CN_RISK_SUFFIX` |

### 5.4 Trader 信号处理适配

`signal_processing.py` 需要识别中文交易信号:

```python
# signal_processing.py 增强
# 原有: 匹配 "FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**"
# 新增: 匹配 "最终交易建议: **买入/持有/卖出**"

SIGNAL_PATTERNS = {
    "BUY": ["BUY", "买入"],
    "SELL": ["SELL", "卖出"],
    "HOLD": ["HOLD", "持有"],
}
```

---

## 6. 配置系统扩展

### 6.1 default_config.py 新增配置

```python
DEFAULT_CONFIG = {
    # ... 原有配置不变 ...

    # ============ A 股配置 (新增) ============

    # A 股数据源配置 (结构与 data_vendors 完全对称)
    "cn_data_vendors": {
        "core_stock_apis": "akshare",        # Options: akshare, tushare
        "technical_indicators": "akshare",   # Options: akshare, tushare
        "fundamental_data": "akshare",       # Options: akshare, tushare
        "news_data": "akshare",              # Options: akshare
    },

    # A 股工具级别覆盖
    "cn_tool_vendors": {
        # Example: "get_stock_data": "tushare",
    },

    # tushare token (可选, 仅 tushare vendor 需要)
    "tushare_token": os.getenv("TUSHARE_TOKEN", ""),

    # A 股请求间隔 (秒), 防止被数据源封禁
    "cn_request_interval": 0.3,
}
```

### 6.2 用户配置示例

```python
# 用户代码: 使用 A 股分析
from tradingagents.graph.trading_graph import TradingAgentsGraph

graph = TradingAgentsGraph(config={
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.2",
    "quick_think_llm": "gpt-5-mini",
    # A 股配置 (可选, 以下为默认值)
    "cn_data_vendors": {
        "core_stock_apis": "akshare",
        "technical_indicators": "akshare",
        "fundamental_data": "tushare",  # 基本面用 tushare (更准确)
        "news_data": "akshare",
    },
    "tushare_token": "your_token_here",
})

# A 股分析 — 自动识别市场
state, signal = graph.propagate("600519", "2025-03-14")
# → 自动使用 akshare, 中文输出, A 股规则

# 美股分析 — 完全不变
state, signal = graph.propagate("NVDA", "2025-03-14")
# → 自动使用 yfinance, 英文输出, 原有逻辑
```

---

## 7. Memory 系统隔离

### 7.1 设计方案: 市场前缀隔离

```python
# trading_graph.py 中 Memory 初始化改造

class TradingAgentsGraph:
    def __init__(self, ...):
        # ...

        # Memory 初始化改为延迟初始化 (在 propagate 中根据市场创建)
        self._memories = {}

    def _get_memories(self, market: str):
        """根据市场获取或创建对应的 Memory 实例"""
        if market not in self._memories:
            prefix = f"{market}_"  # "cn_" 或 "us_"
            self._memories[market] = {
                "bull": FinancialSituationMemory(f"{prefix}bull_memory", self.config),
                "bear": FinancialSituationMemory(f"{prefix}bear_memory", self.config),
                "trader": FinancialSituationMemory(f"{prefix}trader_memory", self.config),
                "invest_judge": FinancialSituationMemory(f"{prefix}invest_judge_memory", self.config),
                "risk_manager": FinancialSituationMemory(f"{prefix}risk_manager_memory", self.config),
            }
        return self._memories[market]
```

### 7.2 存储目录结构

```
tradingagents/
└── memory/
    ├── us_bull_memory.json          # 美股看多记忆
    ├── us_bear_memory.json          # 美股看空记忆
    ├── us_trader_memory.json        # 美股交易记忆
    ├── us_invest_judge_memory.json  # 美股投资判断记忆
    ├── us_risk_manager_memory.json  # 美股风控记忆
    ├── cn_bull_memory.json          # A 股看多记忆
    ├── cn_bear_memory.json          # A 股看空记忆
    ├── cn_trader_memory.json        # A 股交易记忆
    ├── cn_invest_judge_memory.json  # A 股投资判断记忆
    └── cn_risk_manager_memory.json  # A 股风控记忆
```

### 7.3 向后兼容

现有无前缀的 Memory 文件 (如 `bull_memory.json`) 在首次 propagate 美股时自动迁移为 `us_bull_memory.json`。

---

## 8. 文件变更清单

### 新增文件 (6 个)

| 文件 | 说明 | 行数估计 |
|------|------|---------|
| `dataflows/market_utils.py` | 市场识别 & 代码标准化 & 交易日历 | ~150 |
| `dataflows/akshare_stock.py` | akshare 行情 + 基本面 + 指标 | ~350 |
| `dataflows/akshare_news.py` | akshare 新闻接口 | ~120 |
| `dataflows/tushare_stock.py` | tushare 备用数据源 | ~300 |
| `agents/utils/cn_market_prompts.py` | A 股 Prompt 后缀定义 | ~120 |
| `docs/design/cn_stock_architecture.md` | 本设计文档 | — |

### 修改文件 (16 个)

| 文件 | 改动说明 | 改动量 |
|------|----------|--------|
| `dataflows/interface.py` | vendor 注册 + 市场感知路由 | 中 |
| `dataflows/config.py` | 市场上下文管理 | 小 |
| `default_config.py` | 新增 A 股配置项 | 小 |
| `agents/utils/agent_states.py` | AgentState 新增 market_context | 小 |
| `agents/analysts/market_analyst.py` | Prompt 条件注入 | 小 |
| `agents/analysts/social_media_analyst.py` | Prompt 条件注入 | 小 |
| `agents/analysts/news_analyst.py` | Prompt 条件注入 | 小 |
| `agents/analysts/fundamentals_analyst.py` | Prompt 条件注入 | 小 |
| `agents/researchers/bull_researcher.py` | Prompt 条件注入 | 小 |
| `agents/researchers/bear_researcher.py` | Prompt 条件注入 | 小 |
| `agents/managers/research_manager.py` | Prompt 条件注入 | 小 |
| `agents/managers/risk_manager.py` | Prompt 条件注入 | 小 |
| `agents/risk_mgmt/*.py` (3 files) | Prompt 条件注入 | 小 |
| `agents/trader/trader.py` | Prompt 条件注入 + 中文信号 | 小 |
| `graph/trading_graph.py` | 市场上下文初始化 + Memory 隔离 | 中 |
| `graph/propagation.py` | 初始状态增加 market_context | 小 |
| `graph/signal_processing.py` | 中文信号识别 | 小 |
| `pyproject.toml` | 新增 akshare, tushare 依赖 | 小 |

---

## 9. 实施阶段划分

### Phase 1: 数据基础层 (优先级最高)

**目标**: 能通过 akshare 获取 A 股行情数据

**文件**:
- `dataflows/market_utils.py` (新增)
- `dataflows/akshare_stock.py` (新增, 仅 `get_stock_data` + `get_indicators`)
- `dataflows/akshare_news.py` (新增)

**验证**: 单元测试调用 `get_stock_data("600519", "2025-03-01", "2025-03-14")` 返回正确 CSV

### Phase 2: 路由集成层

**目标**: interface.py 能根据 symbol 自动路由到 akshare

**文件**:
- `dataflows/interface.py` (修改)
- `dataflows/config.py` (修改)
- `default_config.py` (修改)

**验证**: `route_to_vendor("get_stock_data", "600519", ...)` 自动走 akshare

### Phase 3: Agent 适配层

**目标**: 所有 Agent 分析 A 股时使用中文 + 规则感知

**文件**:
- `agents/utils/cn_market_prompts.py` (新增)
- `agents/utils/agent_states.py` (修改)
- 12 个 Agent 文件 (修改)
- `graph/propagation.py` (修改)
- `graph/trading_graph.py` (修改)
- `graph/signal_processing.py` (修改)

**验证**: `graph.propagate("600519", "2025-03-14")` 完整运行，输出中文报告

### Phase 4: 备用源 + 完善

**目标**: tushare fallback、基本面完善、Memory 隔离

**文件**:
- `dataflows/tushare_stock.py` (新增)
- `akshare_stock.py` 补全基本面函数
- `graph/trading_graph.py` Memory 隔离
- `pyproject.toml` 依赖更新

**验证**: akshare 失败时自动 fallback 到 tushare; Memory 按市场隔离

---

## 附录: 关键设计决策记录

| # | 决策 | 理由 |
|---|------|------|
| D1 | 技术指标沿用 stockstats | 保持美股/A 股指标计算一致性，减少维护成本 |
| D2 | A 股规则通过 Prompt 注入而非硬编码 | LLM 足够理解规则含义，硬编码灵活性差 |
| D3 | 交易日历用 akshare 获取 + 本地缓存 | 避免每次调用都请求网络，且数据稳定 |
| D4 | Memory 按市场前缀隔离 | A 股和美股的历史经验不通用，隔离防止干扰 |
| D5 | 市场识别在 route_to_vendor 层做 | 最小侵入，Tool 层和 Agent 层都不需要感知市场切换逻辑 |
| D6 | get_global_news 通过线程上下文获取市场 | 该函数无 symbol 参数，需要额外机制传递市场信息 |
