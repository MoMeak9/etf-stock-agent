# ETF Stock Agent

ETF Stock Agent is a focused extraction of the ETF and stock analysis core from TradingAgents. It keeps the multi-agent analysis graph, stock and A-share ETF analyst roles, market data routing, CLI entry points, LLM provider abstraction, and regression tests, while excluding generated reports, caches, and local secret files.

## What Is Included

- Stock analysis agents: market, fundamentals, news, social, China market
- ETF analysis agents: market, flow, news, product
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

Batch stock analysis:

```bash
python analyze.py 000001 600519 AAPL -l 3 -w 2
```

## Sensitive Data

The repository ignores `.env`, `.env.*`, generated reports, caches, credentials, and local worktrees. Keep real API keys only in your local shell environment or an untracked `.env` file.

## Verification

```bash
python -m unittest test_etf_graph.py test_etf_analysts.py test_market_analyst.py test_fundamentals_analyst.py
python -m compileall tradingagents cli analyze.py main.py
```
