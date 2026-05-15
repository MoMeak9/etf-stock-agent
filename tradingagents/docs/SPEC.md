# ETF Stock Agent 项目规格文档

> 版本: 0.2.1 | 日期: 2026-04-05 | Python ≥ 3.10

## 1. 项目概述

ETF Stock Agent 是从 TradingAgents 提取出的 ETF 与股票多智能体 LLM 金融分析框架。系统模拟真实交易公司的组织架构，通过多个专业化 AI Agent 协作完成股票/ETF 分析、投资辩论、风险评估，最终输出结构化交易决策。

支持 A股、港股、美股 三大市场，内置多数据源自动路由与降级机制。

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     入口层 (Entry)                        │
│  main.py / analyze.py / cli/main.py (Typer CLI)         │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              编排层 (Orchestration)                       │
│         tradingagents/graph/trading_graph.py             │
│              TradingAgentsGraph                          │
│  ┌──────────┬───────────┬──────────────┬──────────┐     │
│  │ setup.py │propagation│conditional   │reflection│     │
│  │GraphSetup│Propagator │ConditionalLogic│Reflector│    │
│  └──────────┴───────────┴──────────────┴──────────┘     │
│              signal_processing.py                        │
│              SignalProcessor                             │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                智能体层 (Agents)                          │
│                                                          │
│  ┌─ 分析师团队 (Analysts) ─────────────────────────┐     │
│  │ market / fundamentals / news / social / china   │     │
│  └─────────────────────────────────────────────────┘     │
│  ┌─ 研究团队 (Researchers) ────────────────────────┐     │
│  │ bull_researcher / bear_researcher               │     │
│  └─────────────────────────────────────────────────┘     │
│  ┌─ 管理层 (Managers) ────────────────────────────┐      │
│  │ research_manager / risk_manager                 │     │
│  └─────────────────────────────────────────────────┘     │
│  ┌─ 风控团队 (Risk) ──────────────────────────────┐      │
│  │ aggressive / conservative / neutral debator     │     │
│  └─────────────────────────────────────────────────┘     │
│  ┌─ 交易员 (Trader) ─────────────────────────────┐       │
│  │ trader.py                                       │     │
│  └─────────────────────────────────────────────────┘     │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              数据层 (Dataflows)                           │
│         tradingagents/dataflows/interface.py             │
│              route_to_vendor()                           │
│  ┌──────────┬──────────┬──────────┬──────────┐          │
│  │ yfinance │alpha_    │ akshare  │ tushare  │          │
│  │          │vantage   │          │          │          │
│  └──────────┴──────────┴──────────┴──────────┘          │
│  baostock (可选) / hk_stock (港股)                        │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              LLM 客户端层 (LLM Clients)                   │
│         tradingagents/llm_clients/factory.py             │
│  ┌──────────┬──────────┬──────────┐                     │
│  │ OpenAI   │Anthropic │ Google   │                     │
│  │(+xai,    │          │          │                     │
│  │deepseek, │          │          │                     │
│  │minimax,  │          │          │                     │
│  │ollama,   │          │          │                     │
│  │openrouter│          │          │                     │
│  │custom)   │          │          │                     │
│  └──────────┴──────────┴──────────┘                     │
└─────────────────────────────────────────────────────────┘
```

## 3. 目录结构

```
etf-stock-agent/
├── main.py                    # 编程式入口
├── analyze.py                 # 多股票并行分析 CLI (5档强度)
├── cli/                       # Typer CLI 应用
│   ├── main.py                # CLI 定义 + 交互式向导
│   ├── config.py              # CLI 配置
│   ├── models.py              # AnalystType 枚举
│   ├── utils.py               # 显示辅助函数
│   ├── announcements.py       # 远程公告获取
│   └── stats_handler.py       # LangChain 回调统计
│
├── tradingagents/             # 核心包
│   ├── default_config.py      # 默认配置字典
│   │
│   ├── graph/                 # LangGraph 编排层
│   │   ├── trading_graph.py   # TradingAgentsGraph 主编排器
│   │   ├── setup.py           # GraphSetup 图构建
│   │   ├── propagation.py     # Propagator 初始状态
│   │   ├── conditional_logic.py # 路由决策逻辑
│   │   ├── signal_processing.py # 信号提取 (LLM → JSON)
│   │   └── reflection.py      # 交易后反思学习
│   │
│   ├── agents/                # 所有 Agent 定义
│   │   ├── analysts/          # 5 个分析师
│   │   ├── researchers/       # 多空研究员
│   │   ├── managers/          # 研究经理 + 风控经理
│   │   ├── risk_mgmt/         # 3 个风控辩论者
│   │   ├── trader/            # 交易员
│   │   └── utils/             # 共享工具
│   │       ├── agent_states.py      # 状态定义
│   │       ├── memory.py            # BM25 记忆系统
│   │       ├── market_router.py     # 市场检测/公司名解析
│   │       ├── core_stock_tools.py  # 股票数据工具
│   │       ├── technical_indicators_tools.py
│   │       ├── fundamental_data_tools.py
│   │       └── news_data_tools.py
│   │
│   ├── dataflows/             # 数据供应商抽象层
│   │   ├── config.py          # 全局配置 (线程安全)
│   │   ├── interface.py       # route_to_vendor() 路由引擎
│   │   ├── market_utils.py    # 市场检测/符号标准化
│   │   ├── y_finance.py       # yfinance 实现
│   │   ├── yfinance_news.py   # yfinance 新闻
│   │   ├── alpha_vantage*.py  # Alpha Vantage 系列
│   │   ├── akshare_*.py       # AKShare A股数据
│   │   ├── tushare_stock.py   # Tushare A股数据
│   │   ├── baostock_stock.py  # BaoStock (可选)
│   │   └── hk_stock.py        # 港股数据
│   │
│   ├── llm_clients/           # LLM 客户端抽象
│   │   ├── factory.py         # create_llm_client()
│   │   ├── base_client.py     # BaseLLMClient 接口
│   │   ├── openai_client.py   # OpenAI 兼容客户端
│   │   ├── anthropic_client.py
│   │   └── google_client.py
│   │
│   └── docs/                  # 项目规格文档
│
├── results/                   # 本地输出目录 (git ignored)
├── eval_results/              # 评估结果 (git ignored)
├── pyproject.toml             # 包元数据
├── requirements.txt           # 依赖列表
├── .env.example               # 环境变量示例
└── .env                       # 本地 API 密钥配置 (git ignored)
```

## 4. 核心数据流

### 4.1 完整分析流程 (LangGraph StateGraph)

```
START
  │
  ├──→ Market Analyst ──→ tool_call_market ──┐
  ├──→ News Analyst ────→ tool_call_news ────┤
  ├──→ Social Analyst ──→ tool_call_social ──┤  并行分析
  ├──→ Fundamentals ────→ tool_call_fund ────┤
  └──→ China Market* ───→ tool_call_china ───┘
                                              │
                    ┌─────────────────────────┘
                    ▼
            Bull Researcher ◄──────┐
                    │              │  投资辩论
                    ▼              │  (max_debate_rounds)
            Bear Researcher ───────┘
                    │
                    ▼
            Research Manager (裁判)
                    │
                    ▼
               Trader (交易决策)
                    │
                    ▼
         Aggressive Analyst ◄──────┐
                    │              │
         Conservative Analyst      │  风险辩论
                    │              │  (max_risk_discuss_rounds)
         Neutral Analyst ──────────┘
                    │
                    ▼
            Risk Judge (风控裁判)
                    │
                    ▼
                   END
```

### 4.2 状态模型

**AgentState** (主状态，继承 `MessagesState`):

| 字段 | 类型 | 说明 |
|------|------|------|
| `company_of_interest` | str | 目标股票代码 |
| `trade_date` | str | 交易日期 |
| `market_context` | dict | 市场/交易所/货币/语言 |
| `market_report` | str | 市场分析师报告 |
| `sentiment_report` | str | 社交媒体分析师报告 |
| `news_report` | str | 新闻分析师报告 |
| `fundamentals_report` | str | 基本面分析师报告 |
| `china_market_report` | str | 中国市场分析师报告 |
| `*_tool_call_count` | int | 各分析师工具调用计数 (防死循环) |
| `investment_debate_state` | InvestDebateState | 投资辩论状态 |
| `investment_plan` | str | 研究经理生成的投资计划 |
| `trader_investment_plan` | str | 交易员生成的交易计划 |
| `risk_debate_state` | RiskDebateState | 风控辩论状态 |
| `final_trade_decision` | str | 最终交易决策 |

**InvestDebateState** (投资辩论):

| 字段 | 类型 | 说明 |
|------|------|------|
| `bull_history` | str | 多头论点历史 |
| `bear_history` | str | 空头论点历史 |
| `history` | str | 完整对话历史 |
| `current_response` | str | 最新回复 |
| `judge_decision` | str | 裁判最终决策 |
| `count` | int | 当前辩论轮数 |

**RiskDebateState** (风控辩论):

| 字段 | 类型 | 说明 |
|------|------|------|
| `aggressive_history` | str | 激进分析师历史 |
| `conservative_history` | str | 保守分析师历史 |
| `neutral_history` | str | 中性分析师历史 |
| `judge_decision` | str | 风控裁判决策 |
| `count` | int | 当前辩论轮数 |

## 5. 智能体规格

### 5.1 分析师团队 (Analysts)

| 分析师 | 模块 | 职责 | 使用工具 |
|--------|------|------|----------|
| Market Analyst | `market_analyst.py` | 技术分析、价格走势、技术指标 | `get_stock_data`, `get_indicators` |
| Fundamentals Analyst | `fundamentals_analyst.py` | 财务报表、基本面分析 | `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement` |
| News Analyst | `news_analyst.py` | 新闻事件、全球动态 | `get_news`, `get_global_news`, `get_insider_transactions` |
| Social Media Analyst | `social_media_analyst.py` | 市场情绪、社交媒体舆情 | `get_sentiment`, `get_news` |
| China Market Analyst | `china_market_analyst.py` | A股/港股专项分析 | 同上 (中国市场特化) |

- 所有分析师使用 `quick_think_llm`
- 每个分析师有独立的 `tool_call_count` 防止死循环
- 分析师可并行执行

### 5.2 研究团队 (Researchers)

| 角色 | 模块 | 职责 |
|------|------|------|
| Bull Researcher | `bull_researcher.py` | 构建看多论点，引用分析师报告 |
| Bear Researcher | `bear_researcher.py` | 构建看空论点，挑战多头观点 |
| Research Manager | `research_manager.py` | 裁判角色，综合多空辩论做出投资建议 |

- 多空辩论轮数由 `max_debate_rounds` 控制
- Research Manager 使用 `deep_think_llm`
- 研究员拥有 BM25 记忆系统，可检索历史相似情境

### 5.3 风控团队 (Risk Management)

| 角色 | 模块 | 风格 |
|------|------|------|
| Aggressive Debator | `aggressive_debator.py` | 激进风控，倾向高收益 |
| Conservative Debator | `conservative_debator.py` | 保守风控，强调风险控制 |
| Neutral Debator | `neutral_debator.py` | 中性风控，平衡收益与风险 |
| Risk Manager | `risk_manager.py` | 风控裁判，综合三方意见 |

- 三方轮流辩论，轮数由 `max_risk_discuss_rounds` 控制
- Risk Manager 使用 `deep_think_llm`

### 5.4 交易员 (Trader)

| 角色 | 模块 | 职责 |
|------|------|------|
| Trader | `trader.py` | 综合研究经理建议，制定具体交易计划 |

- 使用 `deep_think_llm`
- 拥有 BM25 记忆系统

## 6. 数据供应商路由

### 6.1 路由机制

`route_to_vendor(method, *args, **kwargs)` 是数据层的核心路由引擎：

1. 检测股票市场 (CN/HK/US)
2. 根据配置选择主数据源
3. 调用失败时自动降级到备选数据源

### 6.2 市场-数据源映射

| 市场 | 主数据源 | 备选数据源 |
|------|----------|------------|
| US (美股) | yfinance | alpha_vantage |
| CN (A股) | tushare | akshare → baostock |
| HK (港股) | yfinance | hk_stock |

### 6.3 数据类别

| 类别 | 工具函数 | 说明 |
|------|----------|------|
| `core_stock_apis` | `get_stock_data` | OHLCV 行情数据 |
| `technical_indicators` | `get_indicators` | 技术指标 (MA, RSI, MACD 等) |
| `fundamental_data` | `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement` | 财务报表 |
| `news_data` | `get_news`, `get_global_news`, `get_insider_transactions`, `get_sentiment` | 新闻与舆情 |

## 7. LLM 客户端

### 7.1 工厂模式

`create_llm_client(provider, model, base_url)` 返回 `BaseLLMClient` 实例。

### 7.2 支持的 Provider

| Provider | 客户端类 | 说明 |
|----------|----------|------|
| `openai` | `OpenAIClient` | OpenAI 官方 API |
| `anthropic` | `AnthropicClient` | Claude 系列 |
| `google` | `GoogleClient` | Gemini 系列 |
| `deepseek` | `OpenAIClient` | DeepSeek (OpenAI 兼容) |
| `minimax` | `OpenAIClient` | MiniMax (OpenAI 兼容) |
| `xai` | `OpenAIClient` | xAI Grok (OpenAI 兼容) |
| `ollama` | `OpenAIClient` | 本地模型 |
| `openrouter` | `OpenAIClient` | OpenRouter 聚合 |
| `custom` | `OpenAIClient` | 自定义 OpenAI 兼容端点 |

### 7.3 双 LLM 策略

| LLM 角色 | 配置键 | 默认值 | 使用场景 |
|-----------|--------|--------|----------|
| `quick_think_llm` | `quick_think_llm` | `gpt-5-mini` | 分析师、信号处理、反思 |
| `deep_think_llm` | `deep_think_llm` | `gpt-5.2` | 研究经理、风控裁判、交易员 |

## 8. 记忆系统

### 8.1 FinancialSituationMemory

基于 BM25 (Best Matching 25) 的词法相似度检索，无需 API 调用，完全离线运行。

- `add_situations([(situation, advice)])` — 存储情境-建议对
- `get_memories(current_situation, n_matches)` — 检索最相似的历史情境
- 分数归一化到 0-1 范围

### 8.2 记忆实例

| 实例 | 持有者 | 用途 |
|------|--------|------|
| `bull_memory` | Bull Researcher | 历史多头分析经验 |
| `bear_memory` | Bear Researcher | 历史空头分析经验 |
| `trader_memory` | Trader | 历史交易决策经验 |
| `invest_judge_memory` | Research Manager | 历史投资裁判经验 |
| `risk_manager_memory` | Risk Manager | 历史风控裁判经验 |

### 8.3 反思机制 (Reflector)

交易完成后，`Reflector` 对每个角色的决策进行反思：
1. 评估决策正确性 (收益/亏损)
2. 分析成功/失败因素
3. 提出改进建议
4. 将经验写入对应的 Memory 实例

## 9. 信号处理

`SignalProcessor.process_signal()` 将自然语言交易信号转换为结构化 JSON：

```json
{
    "action": "买入/持有/卖出",
    "target_price": 45.50,
    "confidence": 0.85,
    "risk_score": 0.3,
    "reasoning": "决策理由摘要"
}
```

处理流程：
1. LLM 提取 → 尝试 JSON 解析
2. 失败时 → 正则表达式回退提取
3. 仍失败 → 返回默认持有决策

## 10. 配置规格

### 10.1 DEFAULT_CONFIG

```python
{
    # LLM 设置
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.2",
    "quick_think_llm": "gpt-5-mini",
    "backend_url": "https://api.openai.com/v1",
    "google_thinking_level": None,
    "openai_reasoning_effort": None,

    # 辩论设置
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,

    # 数据源 (US)
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    },

    # 数据源 (CN)
    "cn_data_vendors": {
        "core_stock_apis": "tushare",
        "technical_indicators": "tushare",
        "fundamental_data": "tushare",
        "news_data": "akshare",
    },

    # 数据源 (HK)
    "hk_data_vendors": {
        "core_stock_apis": "yfinance",
        ...
    },

    "tushare_token": "$TUSHARE_TOKEN",
    "cn_request_interval": 0.3,
}
```

### 10.2 环境变量

| 变量 | 用途 |
|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 |
| `GOOGLE_API_KEY` | Google AI API 密钥 |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage 数据密钥 |
| `TUSHARE_TOKEN` | Tushare 数据令牌 |
| `TRADINGAGENTS_RESULTS_DIR` | 结果输出目录 |

## 11. 入口与使用方式

### 11.1 编程式调用 (main.py)

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph

ta = TradingAgentsGraph(
    selected_analysts=["market", "social", "news", "fundamentals"],
    config={...},
)
result = ta.propagate(ticker="AAPL", trade_date="2026-04-05")
```

### 11.2 CLI 交互式向导

```bash
tradingagents          # 启动交互式向导
```

通过 Typer 提供交互式配置：选择 LLM Provider → 模型 → 分析师 → 股票代码 → 日期。

### 11.3 多股票并行分析 (analyze.py)

```bash
python analyze.py 000001 600519 AAPL -l 3 -w 4 -d 2026-04-05
```

5 档分析强度：

| 档位 | 名称 | 分析师 | 辩论轮数 |
|------|------|--------|----------|
| 1 | 闪电 | market | 1 |
| 2 | 快速 | market + fundamentals | 1 |
| 3 | 标准 | market + fundamentals + news | 1 |
| 4 | 深度 | market + fundamentals + news + social | 2 |
| 5 | 极致 | 全部 (含 china_market) | 3 |

## 12. 输出产物

### 12.1 结构化决策 (JSON)

```json
{
    "action": "买入",
    "target_price": 45.50,
    "confidence": 0.85,
    "risk_score": 0.3,
    "reasoning": "..."
}
```

### 12.2 分析报告 (Markdown)

默认输出到本地 `results/` 或 CLI 配置的报告目录，生成产物不进入 Git，包含：
- 各分析师完整报告
- 投资辩论 (多头/空头/裁判)
- 风险辩论 (激进/保守/中性/裁判)
- 最终交易决策

### 12.3 评估结果 (JSON)

输出到 `eval_results/{ticker}/`，包含完整状态日志。

## 13. 依赖关系

### 核心框架
- `langgraph >= 0.4.8` — Agent 图编排
- `langchain-core >= 0.3.81` — LLM 抽象层
- `langchain-openai >= 0.3.23` — OpenAI 集成
- `langchain-anthropic >= 0.3.15` — Anthropic 集成
- `langchain-google-genai >= 2.1.5` — Google 集成

### 数据获取
- `yfinance >= 0.2.63` — 美股/港股行情
- `akshare >= 1.14.0` — A股数据
- `tushare >= 1.4.0` (可选) — A股数据 (更精确)
- `alpha_vantage` (通过 requests) — 备选数据源

### 工具库
- `pandas >= 2.3.0` — 数据处理
- `stockstats >= 0.6.5` — 技术指标计算
- `rank-bm25 >= 0.2.2` — 记忆检索
- `redis >= 6.2.0` — 缓存 (可选)
- `rich >= 14.0.0` — 终端 UI
- `typer >= 0.21.0` — CLI 框架
- `backtrader >= 1.9.78` — 回测引擎

## 14. 关键设计决策

| 决策 | 理由 |
|------|------|
| LangGraph StateGraph | 支持条件路由、并行执行、状态管理 |
| 双 LLM 策略 | 分析师用快速模型降低成本，决策层用强模型保证质量 |
| BM25 记忆 | 无需外部 API，离线运行，零额外成本 |
| 多数据源降级 | 单一数据源不可靠时自动切换，提高系统韧性 |
| 辩论机制 | 多空对抗 + 三方风控辩论，减少单一视角偏差 |
| 工具调用计数 | 防止 Agent 陷入无限工具调用循环 |
| 中文 Prompt | 面向中国市场用户，A股/港股分析更精准 |
