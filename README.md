# ETF Stock Agent

ETF Stock Agent is a focused extraction of the ETF and stock analysis core from TradingAgents. It keeps the multi-agent analysis graph, stock and A-share ETF analyst roles, market data routing, CLI entry points, LLM provider abstraction, and regression tests, while excluding generated reports, caches, and local secret files.

## What Is Included

- Stock analysis agents: market, fundamentals, news, social, China market
- ETF analysis agents: market, flow, news, product
- Structured ETF research packages for market, product, exposure, flow, and event data
- LangGraph orchestration for analyst reports, investment debate, trader plan, risk debate, and final decision
- Data adapters for yfinance, Alpha Vantage, AKShare, Tushare, BaoStock, and HK stock helpers
- CLI flows via `etf-stock-agent` / `tradingagents` and batch analysis via `analyze.py`
- Example environment file without secrets

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[cn]"
cp .env.example .env
```

Fill `.env` with the LLM and data provider keys you actually use. For US stock data with yfinance, no market data key is required. For A-share ETF/stock data, set `TUSHARE_TOKEN` when using Tushare.

## Examples

Run the interactive CLI:

```bash
etf-stock-agent
```

Run a stock analysis from Python:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["quick_think_llm"] = "gpt-5-mini"
config["deep_think_llm"] = "gpt-5.2"

graph = TradingAgentsGraph(
    selected_analysts=["market", "fundamentals", "news"],
    config=config,
)
state, decision = graph.propagate("AAPL", "2026-05-14")
print(decision)
```

Run an A-share ETF analysis:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["asset_type"] = "etf"
config["selected_etf_analysts"] = ["market", "flow", "news", "product"]

graph = TradingAgentsGraph(config=config)
state, decision = graph.propagate("510300", "2026-05-14")
print(decision)
```

## A 股 ETF 中文使用说明

本项目支持直接分析 A 股场内 ETF，例如 `159949`、`510300`、`588000` 等。ETF 模式会启用四类分析师：行情技术、资金流与情绪、新闻事件、产品结构，并在最终报告中给出交易与配置视角。

### 环境准备

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[cn]"
cp .env.example .env
```

在 `.env` 中配置：

```bash
TUSHARE_TOKEN=你的TushareToken
DEEPSEEK_API_KEY=你的DeepSeekKey
```

也可以改用项目已支持的其他 LLM provider。A 股 ETF 数据优先使用 Tushare，并在部分行情、净值或组合数据不可用时尝试 AKShare fallback。

### 运行一次完整 ETF 分析

```python
from pathlib import Path
from dotenv import load_dotenv

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

load_dotenv(dotenv_path=Path(".env"))

config = DEFAULT_CONFIG.copy()
config["asset_type"] = "etf"
config["selected_etf_analysts"] = ["market", "flow", "news", "product"]
config["llm_provider"] = "deepseek"
config["quick_think_llm"] = "deepseek-chat"
config["deep_think_llm"] = "deepseek-chat"

graph = TradingAgentsGraph(
    selected_analysts=config["selected_etf_analysts"],
    config=config,
)

state, decision = graph.propagate("159949", "2026-05-21")
print(decision)
```

报告会写入：

```text
tradingagents/docs/reports/{ETF代码}_{日期}_report.md
```

### ETF 数据口径

- 行情包：提供收盘价、成交额、20 日均成交额、波动率、最大回撤等；Tushare `fund_daily.amount` 会从“千元”换算成“元”。
- 产品包：用同一日期的二级市场收盘价和基金 NAV 计算折溢价，避免价格日期和净值日期错配。
- 持仓/暴露包：优先读取 ETF 定期持仓；指数权重若没有指定交易日数据，会 fallback 到 Tushare 最新可用权重。
- 资金流包：基于份额或规模代理数据计算 5/20/60 日变化。
- 跟踪误差：如果缺少跟踪误差时间序列，报告会明确写明缺失；不会把低折溢价直接等同于低跟踪误差。

### 常见注意事项

- ETF 代码直接传 6 位代码即可，例如 `159949`，不需要写成 `159949.SZ`。
- 交易日期建议使用 `YYYY-MM-DD`，例如 `2026-05-21`。
- Tushare 对部分 ETF 或指数权重接口可能返回空数据；报告中的 `Warnings` 和 `Missing Fields` 会说明数据缺口。
- 当前 `analyze.py` 主要用于批量股票分析；完整 ETF 分析建议使用上面的 Python graph 调用方式。

## A-Share ETF Research Packages

A-share ETF tools use structured research packages before generating analyst reports. The package layer normalizes vendor data and makes data quality explicit:

- Product package aligns secondary-market close and NAV on the same date before computing discount/premium.
- Exposure package uses disclosed ETF holdings and falls back from date-specific index weights to the latest available index weights when Tushare has no same-day data.
- Market package converts Tushare `fund_daily.amount` from thousand CNY to CNY, reports latest amount, 20-day average amount, and whether latest turnover is above the 20-day average.
- Tool outputs include package status, source, warnings, missing fields, derived metrics, and compact raw summaries so analysts can distinguish unavailable data from weak data.
- Product prompts require tracking-error time-series gaps to be stated explicitly; low discount/premium is not treated as proof of low tracking error.

Batch stock analysis:

```bash
python analyze.py 000001 600519 AAPL -l 3 -w 2
```

## Sensitive Data

The repository ignores `.env`, `.env.*`, generated reports, caches, credentials, and local worktrees. Keep real API keys only in your local shell environment or an untracked `.env` file.

## Verification

```bash
python -m compileall tradingagents cli analyze.py main.py
```

With local LLM and data-provider keys configured, run a full ETF smoke test:

```bash
python - <<'PY'
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()
config["asset_type"] = "etf"
config["selected_etf_analysts"] = ["market", "flow", "news", "product"]
config["llm_provider"] = "deepseek"
config["quick_think_llm"] = "deepseek-chat"
config["deep_think_llm"] = "deepseek-chat"

graph = TradingAgentsGraph(selected_analysts=config["selected_etf_analysts"], config=config)
state, decision = graph.propagate("159949", "2026-05-21")
print(decision)
PY
```

If your local checkout includes test modules, run them with:

```bash
python -m unittest discover -s tests -p 'test*.py' -v
```
