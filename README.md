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

也可以通过 `analyze.py` 直接运行：

```bash
python analyze.py 159949 --asset-type etf -l 3 -d 2026-05-21
```

如果希望自动识别 A 股 ETF：

```bash
python analyze.py 159949 --asset-type auto -l 3 -d 2026-05-21
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
- `analyze.py` 同时支持股票和 ETF。默认按股票分析；ETF 请使用 `--asset-type etf`，或使用 `--asset-type auto` 自动识别。同一批次不要混合股票和 ETF。

## A-Share ETF Research Packages

A-share ETF tools use structured research packages before generating analyst reports. The package layer normalizes vendor data and makes data quality explicit:

- Product package aligns secondary-market close and NAV on the same date before computing discount/premium.
- Exposure package uses disclosed ETF holdings and falls back from date-specific index weights to the latest available index weights when Tushare has no same-day data.
- Market package converts Tushare `fund_daily.amount` from thousand CNY to CNY, reports latest amount, 20-day average amount, and whether latest turnover is above the 20-day average.
- Tool outputs include package status, source, warnings, missing fields, derived metrics, and compact raw summaries so analysts can distinguish unavailable data from weak data.
- Product prompts require tracking-error time-series gaps to be stated explicitly; low discount/premium is not treated as proof of low tracking error.

Batch stock or ETF analysis:

```bash
python analyze.py 000001 600519 AAPL -l 3 -w 2
python analyze.py 159949 510300 --asset-type etf -l 3 -w 2
```

## Sensitive Data

The repository ignores `.env`, `.env.*`, generated reports, caches, credentials, and local worktrees. Keep real API keys only in your local shell environment or an untracked `.env` file.

## API Service

The API service is intended for local or intranet deployment. It keeps job state in memory only, writes reports to the existing local report directory, and does not use Redis, SQL databases, or static database files.

Configure a single shared token in `.env`:

```bash
ANALYSIS_API_TOKEN=replace-with-a-long-random-string
```

Start the local API server:

```bash
python3 -m uvicorn tradingagents.api.main:app --host 127.0.0.1 --port 8000
```

Endpoints:

```text
POST /api/v1/analysis/jobs
GET /api/v1/analysis/jobs/{job_id}
GET /api/v1/analysis/jobs/{job_id}/result
GET /api/v1/analysis/jobs/{job_id}/reports/{ticker}
```

Submit an asynchronous stock analysis job:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/analysis/jobs \
  -H 'Authorization: Bearer replace-with-a-long-random-string' \
  -H 'Content-Type: application/json' \
  -d '{
    "tickers": ["600519"],
    "date": "2026-05-22",
    "level": 2,
    "asset_type": "stock",
    "provider": "deepseek",
    "quick_model": "deepseek-v4-flash",
    "deep_model": "deepseek-v4-flash",
    "cn_vendor": "tushare"
  }'
```

Submit an A-share ETF job:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/analysis/jobs \
  -H 'Authorization: Bearer replace-with-a-long-random-string' \
  -H 'Content-Type: application/json' \
  -d '{
    "tickers": ["159949"],
    "date": "2026-05-22",
    "level": 3,
    "asset_type": "etf"
  }'
```

Check job state:

```bash
curl -sS http://127.0.0.1:8000/api/v1/analysis/jobs/{job_id} \
  -H 'Authorization: Bearer replace-with-a-long-random-string'
```

Read final result:

```bash
curl -sS http://127.0.0.1:8000/api/v1/analysis/jobs/{job_id}/result \
  -H 'Authorization: Bearer replace-with-a-long-random-string'
```

Download a generated Markdown report:

```bash
curl -sS -o report.md http://127.0.0.1:8000/api/v1/analysis/jobs/{job_id}/reports/600519 \
  -H 'Authorization: Bearer replace-with-a-long-random-string'
```

Minimal systemd deployment on a local or intranet host:

```ini
[Unit]
Description=ETF Stock Agent API
After=network.target

[Service]
Type=simple
WorkingDirectory=/Users/minlong_1/Desktop/Github/etf-stock-agent
EnvironmentFile=/Users/minlong_1/Desktop/Github/etf-stock-agent/.env
Environment=ANALYSIS_API_WORKERS=1
ExecStart=/opt/homebrew/bin/python3 -m uvicorn tradingagents.api.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

The API runs analysis in background worker processes because the underlying dataflow configuration is process-level. Keep `ANALYSIS_API_WORKERS` small enough for your LLM and data-provider rate limits.

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
