# Open Mutual Fund Analysis Design

## 1. Goal

Add a dedicated `fund` asset type for ordinary open-ended public mutual funds, including QDII, bond funds, money-market funds, equity funds, hybrid funds, index funds, and FOFs.

The first version serves single-fund subscription, redemption, holding, watchlist, and dollar-cost-averaging decisions. Analysis should be long-term and macro-aware by default. It must not treat open-ended funds as stocks or exchange-traded ETF products.

Example target:

```bash
python analyze.py 008763 -l 3
python analyze.py 008763 --asset-type fund -l 3
```

`008763` should be recognized as an open-ended QDII fund when fund metadata is available from the registry probes.

## 2. Non-Goals

- Do not add LOF, closed-end fund, REIT, or other exchange-traded fund analysis in this phase.
- Do not add intraday trading, stop-loss, target-price, or secondary-market technical trading recommendations for open-ended funds.
- Do not merge ordinary funds into the existing ETF analysis path.
- Do not perform broad asset framework refactoring across stock, ETF, and fund in this phase.
- Do not build a full macroeconomic data platform in this phase; use a compact macro context package and explicit data-quality warnings.

## 3. Architecture

Use a fund-specific chain while reusing the existing graph orchestration skeleton.

Asset types become:

- `stock`: listed company stock analysis.
- `etf`: A-share exchange-traded ETF analysis.
- `fund`: ordinary open-ended public mutual fund analysis.
- `auto`: registry-based detection with ambiguity checks.

New modules:

- `tradingagents/dataflows/fund_models.py`
- `tradingagents/dataflows/fund_registry.py`
- `tradingagents/dataflows/tushare_fund.py`
- `tradingagents/dataflows/akshare_fund.py`
- `tradingagents/dataflows/fund_research_service.py`
- `tradingagents/agents/utils/fund_data_tools.py`
- `tradingagents/agents/utils/fund_macro_tools.py` if macro context grows beyond a single fund data tool.
- `tradingagents/agents/analysts/fund_nav_analyst.py`
- `tradingagents/agents/analysts/fund_product_analyst.py`
- `tradingagents/agents/analysts/fund_portfolio_analyst.py`
- `tradingagents/agents/analysts/fund_event_analyst.py`

Existing modules to extend:

- `analyze.py`
- `cli/models.py`
- `cli/utils.py`
- `tradingagents/api/schemas.py`
- `tradingagents/services/analysis_service.py`
- `tradingagents/default_config.py`
- `tradingagents/graph/trading_graph.py`
- `tradingagents/graph/setup.py`
- `tradingagents/graph/propagation.py`
- `tradingagents/agents/utils/agent_states.py`
- `tradingagents/agents/managers/research_manager.py`
- `tradingagents/agents/managers/risk_manager.py`
- `tradingagents/agents/trader/trader.py`

`TradingAgentsGraph._create_tool_nodes()` adds a fund branch with fund-specific tools. `GraphSetup` maps fund analysts into the graph. `AgentState` adds fund report fields and maps them to downstream generic report slots, similar to the ETF report mapping.

## 4. Fund Registry And Auto Detection

`fund_registry.py` owns fund admission and classification.

Admission input:

- Accept normalized 6-digit mainland public fund codes, such as `008763`.
- Reject non-6-digit symbols.
- Reject known ETF symbols in fund mode with a clear message suggesting `asset_type=etf`.
- Reject symbols with no fund metadata from Tushare or AKShare.

Fund type values:

- `qdii`
- `bond`
- `money_market`
- `equity`
- `hybrid`
- `index`
- `fof`
- `unknown`

Unknown type does not block the analysis if fund metadata exists. It sets quality status to `partial` and forces reports to state that classification is uncertain.

Auto detection:

1. If the user explicitly selects `stock`, `etf`, or `fund`, respect that selection.
2. If selection is `auto` or omitted, first check ETF admission through the ETF registry.
3. Probe `fund_registry` through Tushare first and AKShare fallback.
4. Probe stock eligibility after fund probing.
5. If exactly one asset type matches, use it.
6. If multiple asset types match, raise a clear ambiguity error and ask the user to specify `--asset-type`.
7. If no type matches, raise a validation error.

CLI examples:

```text
Symbol 000001 matches both stock and fund. Please use --asset-type stock or --asset-type fund.
```

API and Python paths raise equivalent validation errors when they request auto detection.

The CLI default should become automatic detection, so `python analyze.py 008763 -l 3` can resolve to `fund` when registry metadata confirms it. API requests that omit `asset_type` should also default to `auto`. Python `DEFAULT_CONFIG` may remain `stock` for backward compatibility, but callers can set `config["asset_type"] = "auto"` or `fund`.

## 5. Data Source Strategy

Use Tushare as the primary source and AKShare as fallback.

Fallback rules:

- Each package falls back independently.
- Fallback is recorded in package quality.
- Empty data, missing required columns, vendor exceptions, or permission failures can trigger fallback.
- The system must never silently invent missing fund metrics.
- The final report must surface material data gaps.

Data quality fields:

- `status`: `ok`, `partial`, `unavailable`, or `blocked`
- `primary_source`
- `fallback_source`
- `as_of_date`
- `warnings`
- `missing_fields`

## 6. Research Packages

Each package returns:

- `symbol`
- `fund_type`
- `package_type`
- `status`
- `quality`
- `metrics`
- `raw_summary`

### 6.1 Fund NAV Package

Purpose: evaluate historical net-value performance and drawdown.

Fields and metrics:

- unit NAV
- accumulated NAV
- NAV date
- recent 1, 3, 6, and 12 month returns when enough data exists
- volatility
- maximum drawdown
- drawdown recovery behavior

For money-market funds, use seven-day annualized yield and per-10k-unit income when available instead of equity-style NAV analysis.

### 6.2 Fund Product Package

Purpose: evaluate fund product structure and subscription fit.

Fields:

- fund name
- fund company
- fund type
- inception date
- fund size
- fee structure
- purchase status
- redemption status
- minimum subscription amount
- risk level

Missing purchase or redemption status must be listed in `missing_fields`.

### 6.3 Fund Portfolio Package

Purpose: evaluate exposure and concentration.

Fields and metrics:

- stock, bond, cash, fund, and other-asset allocation when available
- top holdings
- industry exposure
- region exposure for QDII
- concentration metrics
- style or asset allocation drift when historical data exists

For QDII funds, include overseas market exposure, FX risk, overseas holiday mismatch, and NAV lag context.

For bond funds, include duration, credit quality, leverage, and rate sensitivity if available. Missing duration, rating, or leverage fields should degrade the package, not block it.

### 6.4 Fund Manager Package

Purpose: evaluate manager continuity and track record.

Fields:

- fund manager name
- appointment date
- tenure
- tenure return when available
- prior or concurrent managed products when available
- manager changes

Missing historical managed-product data does not block analysis.

### 6.5 Fund Event Package

Purpose: identify operational and announcement-driven risks.

Fields:

- fund announcements
- purchase limits
- purchase or redemption suspension
- dividends
- manager changes
- abnormal size changes
- liquidation or transformation risk

If structured announcement data is unstable in the first version, use title, date, and source summaries. Reports must identify source and timestamp.

### 6.6 Fund Performance Package

Purpose: evaluate relative and risk-adjusted performance.

Fields and metrics:

- peer ranking when available
- benchmark comparison when available
- Sharpe or return-to-drawdown proxy when available
- annual returns
- rolling return stability

If peer ranking is unavailable, degrade to self-history and benchmark comparison. Do not fabricate peer ranks.

### 6.7 Fund Macro Package

Purpose: add long-term macro context to open-ended fund analysis.

First-version inputs:

- global macro and market news already available through the existing `get_global_news` vendor route
- fund-type-specific macro focus generated from registry classification
- optional structured macro indicators when available from supported vendors

Macro focus by fund type:

- `qdii`: overseas equity market cycle, country or region policy, FX risk, RMB exchange-rate context, overseas interest-rate environment, geopolitical and holiday mismatch risks.
- `bond`: central-bank policy, yield-curve direction, credit spreads, liquidity, inflation, and duration risk.
- `money_market`: short-term rates, liquidity conditions, money-market yield direction, redemption pressure, and regulatory or seasonal cash stress.
- `equity`, `hybrid`, `index`: economic growth, liquidity cycle, sector cycle, risk appetite, valuation regime, and policy environment.
- `fof`: cross-asset allocation cycle, equity-bond balance, global risk appetite, and double-layer fee drag under lower-return regimes.

The macro package must be treated as context, not as a precise forecast. Missing macro data should degrade the report and force conservative wording.

## 7. Analysts

First version uses four fund analysts:

- `fund_nav_analyst`: NAV trend, drawdown, volatility, and return quality.
- `fund_product_analyst`: product structure, fees, scale, risk level, purchase and redemption suitability.
- `fund_portfolio_analyst`: holdings, asset allocation, region or industry exposure, concentration, style drift, and macro fit.
- `fund_event_analyst`: announcements, purchase limits, manager changes, dividends, operational risk.

Package consumption:

- `fund_nav_analyst` consumes NAV, performance, and macro packages.
- `fund_product_analyst` consumes product and manager packages.
- `fund_portfolio_analyst` consumes portfolio and macro packages.
- `fund_event_analyst` consumes event and macro packages.

Recommended default analyst set:

```python
["nav", "product", "portfolio", "event"]
```

Fund-specific report fields:

- `fund_nav_report`
- `fund_product_report`
- `fund_portfolio_report`
- `fund_event_report`

Generic downstream mapping:

- `fund_nav_report` -> `market_report`
- `fund_product_report` -> `fundamentals_report`
- `fund_portfolio_report` -> `sentiment_report`
- `fund_event_report` -> `news_report`

This preserves downstream debate and risk management structure without reusing stock or ETF semantics.

## 8. Fund-Type-Specific Prompt Rules

All fund prompts must use fund decision language:

- subscribe
- hold
- redeem
- watch
- dollar-cost average or phased subscription

Prompts must avoid:

- stock buy or sell language
- intraday trading language
- stop-loss and target-price language
- ETF secondary-market liquidity or premium language, unless a future exchange-traded fund mode is explicitly added

Type-specific focus:

- `qdii`: overseas market exposure, currency risk, NAV lag, overseas holidays, purchase limits, quota constraints, region and industry concentration.
- `bond`: interest-rate risk, credit risk, duration, leverage, drawdown, institutional holder risk.
- `money_market`: seven-day annualized yield, per-10k-unit income, scale, liquidity, subscription and redemption convenience, yield stability.
- `equity`, `hybrid`, `index`: concentration, industry exposure, manager style, drawdown control, benchmark and peer context.
- `fof`: underlying fund allocation, diversification, double-layer fees, manager allocation ability.
- `unknown`: conservative analysis with explicit type uncertainty.

All fund prompts should explicitly favor a medium-to-long-term perspective. The report should discuss whether the fund fits a multi-month to multi-year allocation or holding plan, rather than reacting only to recent NAV movement.

## 9. Entry Points

### 9.1 CLI

Supported examples:

```bash
python analyze.py 008763 -l 3
python analyze.py 008763 --asset-type fund -l 3
python analyze.py 008763 --asset-type fund -l 3 -d 2026-05-31
```

Fund intensity profiles:

- 1: NAV quick scan
- 2: NAV plus product structure
- 3: NAV plus product, portfolio, and event analysis
- 4: deep fund analysis with more debate
- 5: maximum-depth fund analysis with more risk discussion

### 9.2 API

`AnalysisJobCreate.asset_type` accepts `fund`:

```json
{
  "tickers": ["008763"],
  "asset_type": "fund",
  "level": 3
}
```

API requests may use `asset_type=auto`, applying the same ambiguity rules as CLI.

### 9.3 Python

```python
config["asset_type"] = "fund"
config["selected_fund_analysts"] = ["nav", "product", "portfolio", "event"]
```

## 10. Report Output

Reports continue to write to:

```text
tradingagents/docs/reports/{fund_code}_{date}_report.md
```

Fund report title:

```text
基金分析报告
```

The final decision must be one of:

- subscribe
- phased subscribe
- hold
- redeem
- watch

The Chinese report may render these as:

- 申购
- 分批申购
- 持有
- 赎回
- 观望

The report must include a data quality section summarizing unavailable or degraded packages.

## 11. Error Handling

- Non-6-digit fund codes are blocked in fund mode.
- ETF codes passed to fund mode are blocked with guidance to use `asset_type=etf`.
- Stock codes passed to fund mode are blocked if fund metadata is unavailable.
- If Tushare and AKShare both fail for a package, return `status=unavailable` and include warnings.
- If all key packages are unavailable, analysts generate a conservative data-insufficient report and avoid positive subscription recommendations.
- Partial package failures do not block the full graph.
- Mixed asset types in one batch are rejected, matching the current stock and ETF batch behavior.

## 12. Testing

Use mock vendors for unit and integration tests. Tests must not require live network access or real Tushare tokens.

Required test coverage:

- CLI accepts `asset_type=fund`.
- API schema accepts `asset_type=fund`.
- `008763` can resolve to fund through auto detection when registry metadata is mocked.
- Ambiguous symbols require explicit `--asset-type`.
- ETF symbols are not captured by fund registry.
- Tushare empty data falls back to AKShare and records fallback source.
- Missing required package fields appear in `missing_fields`.
- Fund report fields map to downstream generic fields.
- Fund prompts avoid stock and ETF trading terms.
- Fund mode uses fund-specific analysts and tools.
- Mixed stock, ETF, and fund batches are rejected.

## 13. Acceptance Criteria

The implementation is complete when:

- `python analyze.py 008763 -l 3` resolves to fund in mocked tests.
- `python analyze.py 008763 --asset-type fund -l 3` uses fund analysts and fund tools.
- API jobs accept `asset_type=fund`.
- Python config with `asset_type=fund` runs the fund graph branch.
- Reports use fund decision language and contain data quality disclosure.
- Unit tests cover registry admission, auto detection, fallback quality, analyst selection, and report mapping.
