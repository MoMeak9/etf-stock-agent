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
