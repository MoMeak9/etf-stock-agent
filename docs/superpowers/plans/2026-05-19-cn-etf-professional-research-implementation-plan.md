# CN ETF Professional Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `asset_type=etf` into a professional China mainland ETF research flow for equity and commodity ETFs, with Tushare-first data, AkShare fallback, derived research metrics, quality labels, and a data healthcheck command.

**Architecture:** Keep the existing LangGraph and ETF analyst chain, but insert an ETF research data layer between vendor adapters and Agent tools. Vendor adapters return structured data, services assemble research packages, metrics compute derived signals, tools format packages for LLM consumption, and `analyze.py --etf-healthcheck` verifies capability without traditional unit tests.

**Tech Stack:** Python 3.10+, pandas, Tushare, AkShare, LangChain tools, Typer/argparse CLI, Rich console output.

---

## File Structure

Create:

- `tradingagents/dataflows/etf_models.py`
  Shared dataclasses and constants for ETF admission, data quality, data blocks, derived metrics, and research packages.
- `tradingagents/dataflows/etf_metrics.py`
  Pure pandas/numeric helpers for premium/discount, share changes, liquidity, drawdown, volatility, concentration, and tracking deviation.
- `tradingagents/dataflows/etf_registry.py`
  ETF code normalization, Tushare `etf_basic` admission checks, supported type detection, and rejection reasons.
- `tradingagents/dataflows/etf_research_service.py`
  Service layer that calls Tushare first, falls back to AkShare, assembles market/product/exposure/event packages, and formats packages into markdown.
- `tradingagents/dataflows/etf_healthcheck.py`
  Healthcheck runner and Rich/text formatting for module readiness: `ready`, `partial`, `blocked`.

Modify:

- `tradingagents/dataflows/tushare_etf.py`
  Add structured fetch functions for `etf_basic`, `fund_daily`, `etf_share_size`, `fund_nav`, `fund_portfolio`, `etf_index`, `mkt_idx_bmk`, and `index_weight`; keep existing string API wrappers for compatibility.
- `tradingagents/dataflows/akshare_etf.py`
  Add structured fallback fetch functions for basic info, daily price, nav/share proxy, holdings, and ETF-relevant news; keep existing string API wrappers for compatibility.
- `tradingagents/agents/utils/etf_data_tools.py`
  Route LangChain tools to `etf_research_service` packages and return research-friendly markdown with data quality labels.
- `tradingagents/agents/utils/etf_prompt_utils.py`
  Strengthen ETF-only prompt constraints and require data-quality discussion.
- `tradingagents/agents/analysts/etf_market_analyst.py`
  Consume market/package markdown instead of raw CSV-style outputs where practical.
- `tradingagents/agents/analysts/etf_product_analyst.py`
  Consume product/exposure package markdown and stop depending on existing stub discount/tracking text.
- `tradingagents/agents/analysts/etf_flow_analyst.py`
  Consume flow metrics from package markdown and clearly label proxy metrics.
- `tradingagents/agents/analysts/etf_news_analyst.py`
  Consume event package markdown and avoid invented events.
- `analyze.py`
  Add `--etf-healthcheck` mode that runs data diagnostics for ETF symbols without invoking LLM analysis.
- `README.md`
  Document ETF healthcheck usage and Tushare-first requirements.

Do not create traditional unit tests in this implementation plan. Verification uses compile checks, import checks, and healthcheck runs against representative ETF symbols.

## Task 1: Add ETF Research Data Contracts

**Files:**
- Create: `tradingagents/dataflows/etf_models.py`

- [ ] **Step 1: Create shared model file**

Add dataclasses and constants:

```python
from dataclasses import dataclass, field
from typing import Any, Literal

QualityStatus = Literal["ok", "partial", "unavailable", "blocked"]
HealthRating = Literal["ready", "partial", "blocked"]

SUPPORTED_ETF_TYPES = {"broad", "sector", "theme", "commodity"}
UNSUPPORTED_ETF_TYPES = {"lof", "qdii", "bond", "money", "otc", "unknown"}

@dataclass
class DataQuality:
    status: QualityStatus
    primary_source: str = "tushare"
    fallback_source: str = "none"
    as_of_date: str = ""
    warnings: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)

@dataclass
class ETFAdmission:
    symbol: str
    ts_code: str
    exchange: str
    is_supported: bool
    etf_type: str
    reason: str = ""
    profile: dict[str, Any] = field(default_factory=dict)
    quality: DataQuality = field(default_factory=lambda: DataQuality(status="partial"))

@dataclass
class ETFResearchPackage:
    symbol: str
    package_type: str
    status: QualityStatus
    quality: DataQuality
    metrics: dict[str, Any] = field(default_factory=dict)
    raw_summary: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 2: Verify import**

Run:

```bash
python3 - <<'PY'
from tradingagents.dataflows.etf_models import DataQuality, ETFAdmission, ETFResearchPackage
print(DataQuality(status="ok"))
print(ETFAdmission(symbol="510300", ts_code="510300.SH", exchange="SH", is_supported=True, etf_type="broad"))
print(ETFResearchPackage(symbol="510300", package_type="market", status="ok", quality=DataQuality(status="ok")))
PY
```

Expected: three dataclass instances print without exceptions.

- [ ] **Step 3: Compile**

Run:

```bash
python3 -m compileall tradingagents/dataflows/etf_models.py
```

Expected: compile succeeds.

- [ ] **Step 4: Commit**

```bash
git add tradingagents/dataflows/etf_models.py
git commit -m "feat: add ETF research data contracts"
```

## Task 2: Add ETF Derived Metrics

**Files:**
- Create: `tradingagents/dataflows/etf_metrics.py`

- [ ] **Step 1: Create metrics helpers**

Implement focused functions:

```python
import math
import pandas as pd

def to_numeric_series(series):
    return pd.to_numeric(series, errors="coerce")

def compute_discount_premium(close, nav):
    close = float(close) if close is not None else math.nan
    nav = float(nav) if nav is not None else math.nan
    if math.isnan(close) or math.isnan(nav) or nav == 0:
        return None
    return (close - nav) / nav

def compute_share_change(df: pd.DataFrame, periods=(5, 20, 60), share_col="share"):
    if df is None or df.empty or share_col not in df.columns:
        return {}
    ordered = df.copy()
    ordered[share_col] = to_numeric_series(ordered[share_col])
    ordered = ordered.dropna(subset=[share_col])
    if ordered.empty:
        return {}
    latest = ordered[share_col].iloc[-1]
    out = {}
    for period in periods:
        if len(ordered) > period and ordered[share_col].iloc[-period - 1] != 0:
            base = ordered[share_col].iloc[-period - 1]
            out[f"share_change_{period}d"] = (latest - base) / base
    return out

def compute_liquidity(df: pd.DataFrame, amount_col="amount"):
    if df is None or df.empty:
        return {}
    amount = to_numeric_series(df.get(amount_col, pd.Series(dtype=float))).dropna()
    if amount.empty:
        return {}
    latest = amount.iloc[-1]
    avg20 = amount.tail(20).mean()
    return {"latest_amount": latest, "avg_amount_20d": avg20, "low_liquidity": avg20 < 20_000_000}

def compute_volatility_and_drawdown(df: pd.DataFrame, close_col="close"):
    if df is None or df.empty or close_col not in df.columns:
        return {}
    close = to_numeric_series(df[close_col]).dropna()
    if len(close) < 2:
        return {}
    returns = close.pct_change().dropna()
    rolling_max = close.cummax()
    drawdown = close / rolling_max - 1
    return {
        "volatility_20d": returns.tail(20).std() * (252 ** 0.5) if len(returns) >= 20 else None,
        "volatility_60d": returns.tail(60).std() * (252 ** 0.5) if len(returns) >= 60 else None,
        "max_drawdown": drawdown.min(),
    }

def compute_concentration(df: pd.DataFrame, weight_col="mkv"):
    if df is None or df.empty or weight_col not in df.columns:
        return {}
    weights = to_numeric_series(df[weight_col]).dropna().sort_values(ascending=False)
    if weights.empty:
        return {}
    total = weights.sum()
    if total == 0:
        return {}
    normalized = weights / total
    return {
        "top1_weight": normalized.head(1).sum(),
        "top3_weight": normalized.head(3).sum(),
        "top5_weight": normalized.head(5).sum(),
        "top10_weight": normalized.head(10).sum(),
    }

def compute_tracking_deviation(etf_returns: pd.Series, benchmark_returns: pd.Series):
    aligned = pd.concat([etf_returns, benchmark_returns], axis=1).dropna()
    if aligned.empty:
        return {}
    diff = aligned.iloc[:, 0] - aligned.iloc[:, 1]
    return {
        "avg_tracking_deviation": diff.mean(),
        "annualized_tracking_error": diff.std() * (252 ** 0.5) if len(diff) > 1 else None,
    }
```

- [ ] **Step 2: Run smoke calculation**

Run:

```bash
python3 - <<'PY'
import pandas as pd
from tradingagents.dataflows.etf_metrics import compute_discount_premium, compute_share_change, compute_liquidity
print(round(compute_discount_premium(1.02, 1.0), 4))
df = pd.DataFrame({"share": [100, 110, 120, 130, 140, 150], "amount": [1e7, 2e7, 3e7, 4e7, 5e7, 6e7]})
print(compute_share_change(df, periods=(5,)))
print(compute_liquidity(df))
PY
```

Expected: premium prints `0.02`, share change has `share_change_5d`, liquidity has `avg_amount_20d`.

- [ ] **Step 3: Compile**

Run:

```bash
python3 -m compileall tradingagents/dataflows/etf_metrics.py
```

Expected: compile succeeds.

- [ ] **Step 4: Commit**

```bash
git add tradingagents/dataflows/etf_metrics.py
git commit -m "feat: add ETF derived metrics"
```

## Task 3: Add ETF Registry and Admission Checks

**Files:**
- Create: `tradingagents/dataflows/etf_registry.py`
- Modify: `tradingagents/dataflows/tushare_etf.py`

- [ ] **Step 1: Add structured Tushare basic fetcher**

In `tradingagents/dataflows/tushare_etf.py`, add:

```python
def fetch_etf_basic(ticker: str):
    pro = _get_tushare_api()
    ts_code = _to_etf_ts_code(ticker)
    try:
        df = pro.etf_basic(ts_code=ts_code)
    except Exception:
        df = pro.etf_basic()
        if df is not None and not df.empty and "ts_code" in df.columns:
            df = df[df["ts_code"] == ts_code]
    return df
```

Keep existing `get_etf_profile()` unchanged for compatibility.

- [ ] **Step 2: Create registry**

Implement:

```python
from tradingagents.dataflows.etf_models import DataQuality, ETFAdmission
from tradingagents.dataflows.market_utils import detect_market, get_exchange, normalize_symbol

SUPPORTED_LABEL_HINTS = {
    "宽基": "broad",
    "行业": "sector",
    "主题": "theme",
    "商品": "commodity",
    "黄金": "commodity",
    "有色": "commodity",
    "能源": "commodity",
}

UNSUPPORTED_LABEL_HINTS = {
    "QDII": "qdii",
    "LOF": "lof",
    "债": "bond",
    "货币": "money",
}

def to_etf_ts_code(symbol: str) -> str:
    normalized = normalize_symbol(symbol, "cn")
    return f"{normalized}.{get_exchange(normalized)}"

def classify_etf(profile: dict) -> tuple[str, str]:
    text = " ".join(str(profile.get(k, "")) for k in ("etf_type", "cname", "csname", "extname", "index_name")).upper()
    for hint, etf_type in UNSUPPORTED_LABEL_HINTS.items():
        if hint.upper() in text:
            return etf_type, f"不支持的 ETF 类型: {hint}"
    for hint, etf_type in SUPPORTED_LABEL_HINTS.items():
        if hint.upper() in text:
            return etf_type, ""
    return "theme", "未能精确分类，按主题 ETF 弱分类处理"

def admit_etf(symbol: str) -> ETFAdmission:
    if detect_market(symbol) != "cn":
        return ETFAdmission(symbol=symbol, ts_code="", exchange="", is_supported=False, etf_type="unknown", reason="ETF 模式仅支持中国大陆场内 ETF", quality=DataQuality(status="blocked"))

    normalized = normalize_symbol(symbol, "cn")
    ts_code = to_etf_ts_code(normalized)
    exchange = get_exchange(normalized)

    try:
        from tradingagents.dataflows.tushare_etf import fetch_etf_basic
        df = fetch_etf_basic(normalized)
    except Exception as exc:
        return ETFAdmission(symbol=normalized, ts_code=ts_code, exchange=exchange, is_supported=True, etf_type="theme", reason=f"产品元数据不可用，使用代码前缀弱判断: {exc}", quality=DataQuality(status="partial", warnings=["classification_low_confidence"]))

    if df is None or df.empty:
        return ETFAdmission(symbol=normalized, ts_code=ts_code, exchange=exchange, is_supported=False, etf_type="unknown", reason="Tushare etf_basic 未找到该 ETF", quality=DataQuality(status="blocked", missing_fields=["etf_basic"]))

    profile = df.iloc[0].to_dict()
    if profile.get("list_status") and profile.get("list_status") != "L":
        return ETFAdmission(symbol=normalized, ts_code=ts_code, exchange=exchange, is_supported=False, etf_type="unknown", reason="基金未处于上市状态", profile=profile, quality=DataQuality(status="blocked"))

    etf_type, reason = classify_etf(profile)
    is_supported = etf_type in {"broad", "sector", "theme", "commodity"}
    status = "ok" if is_supported and not reason else "partial" if is_supported else "blocked"
    return ETFAdmission(symbol=normalized, ts_code=ts_code, exchange=exchange, is_supported=is_supported, etf_type=etf_type, reason=reason, profile=profile, quality=DataQuality(status=status, warnings=[reason] if reason else []))
```

- [ ] **Step 3: Verify imports and weak path**

Run without requiring a token:

```bash
python3 - <<'PY'
from tradingagents.dataflows.etf_registry import to_etf_ts_code, classify_etf
print(to_etf_ts_code("510300"))
print(classify_etf({"cname": "沪深300ETF", "index_name": "沪深300"}))
print(classify_etf({"cname": "纳指QDII ETF", "etf_type": "QDII"}))
PY
```

Expected: `510300.SH`, a supported classification, and a QDII rejection classification.

- [ ] **Step 4: Compile**

Run:

```bash
python3 -m compileall tradingagents/dataflows/tushare_etf.py tradingagents/dataflows/etf_registry.py
```

Expected: compile succeeds.

- [ ] **Step 5: Commit**

```bash
git add tradingagents/dataflows/tushare_etf.py tradingagents/dataflows/etf_registry.py
git commit -m "feat: add ETF admission registry"
```

## Task 4: Add Structured Vendor Fetchers

**Files:**
- Modify: `tradingagents/dataflows/tushare_etf.py`
- Modify: `tradingagents/dataflows/akshare_etf.py`

- [ ] **Step 1: Add Tushare structured fetchers**

Add functions to `tushare_etf.py`:

```python
def fetch_etf_daily(symbol: str, start_date: str, end_date: str):
    pro = _get_tushare_api()
    return pro.fund_daily(ts_code=_to_etf_ts_code(symbol), start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""))

def fetch_etf_share_size(symbol: str, start_date: str, end_date: str):
    pro = _get_tushare_api()
    return pro.etf_share_size(ts_code=_to_etf_ts_code(symbol), start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""))

def fetch_etf_nav(symbol: str, start_date: str, end_date: str):
    pro = _get_tushare_api()
    return pro.fund_nav(ts_code=_to_etf_ts_code(symbol), start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""))

def fetch_etf_portfolio(symbol: str):
    pro = _get_tushare_api()
    return pro.fund_portfolio(ts_code=_to_etf_ts_code(symbol))

def fetch_etf_index(symbol: str = ""):
    pro = _get_tushare_api()
    if symbol:
        return pro.etf_index(ts_code=_to_etf_ts_code(symbol))
    return pro.etf_index()

def fetch_index_weight(index_code: str, trade_date: str = ""):
    pro = _get_tushare_api()
    kwargs = {"index_code": index_code}
    if trade_date:
        kwargs["trade_date"] = trade_date.replace("-", "")
    return pro.index_weight(**kwargs)
```

If local Tushare method names differ, keep the function names above and adapt only the internal call. Do not leak raw exceptions past the service layer except through `TushareError`.

- [ ] **Step 2: Add AkShare structured fallback fetchers**

Add functions to `akshare_etf.py`:

```python
def fetch_etf_daily(symbol: str, start_date: str, end_date: str):
    import akshare as ak
    saved = bypass_proxy_for_cn()
    try:
        df = ak.fund_etf_hist_em(symbol=symbol, period="daily", start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""), adjust="qfq")
        return _normalize_price_frame(df) if df is not None else df
    finally:
        restore_proxy(saved)

def fetch_etf_basic(symbol: str):
    import akshare as ak
    saved = bypass_proxy_for_cn()
    try:
        funds = ak.fund_name_em()
        if funds is None or funds.empty:
            return funds
        return funds[funds["基金代码"] == symbol]
    finally:
        restore_proxy(saved)

def fetch_etf_nav(symbol: str):
    import akshare as ak
    saved = bypass_proxy_for_cn()
    try:
        return ak.fund_etf_fund_info_em(fund=symbol)
    finally:
        restore_proxy(saved)

def fetch_etf_portfolio(symbol: str, year: str):
    import akshare as ak
    saved = bypass_proxy_for_cn()
    try:
        return ak.fund_portfolio_hold_em(symbol=symbol, date=year)
    finally:
        restore_proxy(saved)
```

- [ ] **Step 3: Verify symbols import**

Run:

```bash
python3 - <<'PY'
from tradingagents.dataflows import tushare_etf, akshare_etf
for name in ["fetch_etf_daily", "fetch_etf_basic", "fetch_etf_nav", "fetch_etf_portfolio"]:
    print(name, hasattr(tushare_etf, name), hasattr(akshare_etf, name))
PY
```

Expected: all listed names exist; Tushare may also include extra structured methods.

- [ ] **Step 4: Compile**

Run:

```bash
python3 -m compileall tradingagents/dataflows/tushare_etf.py tradingagents/dataflows/akshare_etf.py
```

Expected: compile succeeds.

- [ ] **Step 5: Commit**

```bash
git add tradingagents/dataflows/tushare_etf.py tradingagents/dataflows/akshare_etf.py
git commit -m "feat: add structured ETF vendor fetchers"
```

## Task 5: Build ETF Research Service

**Files:**
- Create: `tradingagents/dataflows/etf_research_service.py`

- [ ] **Step 1: Implement service helpers**

Create `etf_research_service.py` with:

```python
from datetime import datetime
import pandas as pd

from tradingagents.dataflows.etf_models import DataQuality, ETFResearchPackage
from tradingagents.dataflows.etf_registry import admit_etf
from tradingagents.dataflows.etf_metrics import (
    compute_concentration,
    compute_discount_premium,
    compute_liquidity,
    compute_share_change,
    compute_volatility_and_drawdown,
)

def _date_lookback(curr_date: str, days: int) -> str:
    return (pd.Timestamp(curr_date) - pd.DateOffset(days=days)).strftime("%Y-%m-%d")

def _call_with_fallback(primary, fallback=None):
    warnings = []
    try:
        data = primary()
        if data is not None and not getattr(data, "empty", False):
            return data, "tushare", "none", warnings
        warnings.append("tushare returned empty data")
    except Exception as exc:
        warnings.append(f"tushare failed: {exc}")
    if fallback is not None:
        try:
            data = fallback()
            if data is not None and not getattr(data, "empty", False):
                return data, "tushare", "akshare", warnings
            warnings.append("akshare returned empty data")
        except Exception as exc:
            warnings.append(f"akshare failed: {exc}")
    return None, "tushare", "none", warnings

def build_market_package(symbol: str, curr_date: str) -> ETFResearchPackage:
    from tradingagents.dataflows import tushare_etf, akshare_etf
    start = _date_lookback(curr_date, 220)
    df, primary, fallback, warnings = _call_with_fallback(
        lambda: tushare_etf.fetch_etf_daily(symbol, start, curr_date),
        lambda: akshare_etf.fetch_etf_daily(symbol, start, curr_date),
    )
    if df is None or df.empty:
        quality = DataQuality(status="unavailable", primary_source=primary, fallback_source=fallback, warnings=warnings, missing_fields=["daily"])
        return ETFResearchPackage(symbol=symbol, package_type="market", status="unavailable", quality=quality)
    metrics = {}
    close_col = "close" if "close" in df.columns else "Close"
    amount_col = "amount" if "amount" in df.columns else "Amount"
    metrics.update(compute_liquidity(df, amount_col=amount_col))
    metrics.update(compute_volatility_and_drawdown(df, close_col=close_col))
    quality = DataQuality(status="ok", primary_source=primary, fallback_source=fallback, as_of_date=curr_date, warnings=warnings)
    return ETFResearchPackage(symbol=symbol, package_type="market", status="ok", quality=quality, metrics=metrics, raw_summary={"rows": len(df), "columns": list(df.columns)})
```

Also add package builders:

- `build_product_package(symbol, curr_date)`
- `build_exposure_package(symbol, curr_date)`
- `build_flow_package(symbol, curr_date)`
- `build_event_package(symbol, curr_date)`

Each builder must:

- call `admit_etf()` first when product metadata is needed
- use Tushare first and AkShare fallback
- populate `status`, `warnings`, `missing_fields`, `metrics`, and `raw_summary`
- return `blocked` when admission is unsupported

- [ ] **Step 2: Add package formatter**

Add:

```python
def format_research_package(package: ETFResearchPackage) -> str:
    lines = [
        f"# ETF {package.package_type.title()} Research Package for {package.symbol}",
        f"",
        f"- Status: {package.status}",
        f"- Primary Source: {package.quality.primary_source}",
        f"- Fallback Source: {package.quality.fallback_source}",
        f"- As Of Date: {package.quality.as_of_date or 'N/A'}",
    ]
    if package.quality.warnings:
        lines.append("- Warnings: " + "; ".join(str(w) for w in package.quality.warnings if w))
    if package.quality.missing_fields:
        lines.append("- Missing Fields: " + ", ".join(package.quality.missing_fields))
    if package.metrics:
        lines.append("\n## Derived Metrics")
        for key, value in package.metrics.items():
            lines.append(f"- {key}: {value}")
    if package.raw_summary:
        lines.append("\n## Raw Summary")
        for key, value in package.raw_summary.items():
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)
```

- [ ] **Step 3: Smoke the service without live API**

Run:

```bash
python3 - <<'PY'
from tradingagents.dataflows.etf_research_service import format_research_package
from tradingagents.dataflows.etf_models import DataQuality, ETFResearchPackage
pkg = ETFResearchPackage(symbol="510300", package_type="market", status="partial", quality=DataQuality(status="partial", warnings=["demo"]), metrics={"avg_amount_20d": 1})
print(format_research_package(pkg))
PY
```

Expected: markdown prints status, warnings, and metrics.

- [ ] **Step 4: Compile**

Run:

```bash
python3 -m compileall tradingagents/dataflows/etf_research_service.py
```

Expected: compile succeeds.

- [ ] **Step 5: Commit**

```bash
git add tradingagents/dataflows/etf_research_service.py
git commit -m "feat: add ETF research service"
```

## Task 6: Add ETF Data Healthcheck

**Files:**
- Create: `tradingagents/dataflows/etf_healthcheck.py`

- [ ] **Step 1: Implement healthcheck runner**

Create:

```python
from dataclasses import dataclass, field

from tradingagents.dataflows.etf_registry import admit_etf
from tradingagents.dataflows.etf_research_service import (
    build_event_package,
    build_exposure_package,
    build_flow_package,
    build_market_package,
    build_product_package,
)

@dataclass
class ETFHealthcheckResult:
    symbol: str
    rating: str
    modules: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    reason: str = ""

def run_etf_healthcheck(symbol: str, curr_date: str) -> ETFHealthcheckResult:
    admission = admit_etf(symbol)
    result = ETFHealthcheckResult(symbol=symbol, rating="blocked", reason=admission.reason)
    result.modules["admission"] = "ready" if admission.is_supported else "blocked"
    result.warnings.extend(admission.quality.warnings)
    if not admission.is_supported:
        return result
    builders = {
        "market": build_market_package,
        "product": build_product_package,
        "exposure": build_exposure_package,
        "flow": build_flow_package,
        "event": build_event_package,
    }
    for name, builder in builders.items():
        pkg = builder(symbol, curr_date)
        result.modules[name] = "ready" if pkg.status == "ok" else "partial" if pkg.status == "partial" else "blocked"
        result.warnings.extend(pkg.quality.warnings)
    if any(v == "blocked" for v in result.modules.values()):
        result.rating = "blocked"
    elif any(v == "partial" for v in result.modules.values()):
        result.rating = "partial"
    else:
        result.rating = "ready"
    return result

def format_healthcheck_result(result: ETFHealthcheckResult) -> str:
    lines = [f"# ETF Healthcheck: {result.symbol}", f"Rating: {result.rating}"]
    if result.reason:
        lines.append(f"Reason: {result.reason}")
    lines.append("Modules:")
    for name, status in result.modules.items():
        lines.append(f"- {name}: {status}")
    if result.warnings:
        lines.append("Warnings:")
        for warning in result.warnings:
            if warning:
                lines.append(f"- {warning}")
    return "\n".join(lines)
```

- [ ] **Step 2: Verify formatter**

Run:

```bash
python3 - <<'PY'
from tradingagents.dataflows.etf_healthcheck import ETFHealthcheckResult, format_healthcheck_result
print(format_healthcheck_result(ETFHealthcheckResult(symbol="510300", rating="partial", modules={"admission": "ready"}, warnings=["demo"])))
PY
```

Expected: markdown-like healthcheck text prints.

- [ ] **Step 3: Compile**

Run:

```bash
python3 -m compileall tradingagents/dataflows/etf_healthcheck.py
```

Expected: compile succeeds.

- [ ] **Step 4: Commit**

```bash
git add tradingagents/dataflows/etf_healthcheck.py
git commit -m "feat: add ETF data healthcheck"
```

## Task 7: Wire Healthcheck Into analyze.py

**Files:**
- Modify: `analyze.py`

- [ ] **Step 1: Add healthcheck flag while keeping tickers required**

In `parse_args`, keep current positional `tickers` behavior unless it blocks `--etf-healthcheck`. Add:

```python
parser.add_argument(
    "--etf-healthcheck",
    action="store_true",
    help="运行 ETF 数据体检，不调用 LLM 分析",
)
```

Keep `tickers` required because healthcheck still needs symbols.

- [ ] **Step 2: Add early healthcheck path**

At the beginning of `main()` after `args` and date resolution:

```python
if args.etf_healthcheck:
    from tradingagents.dataflows.etf_healthcheck import run_etf_healthcheck, format_healthcheck_result
    for ticker in args.tickers:
        result = run_etf_healthcheck(ticker, args.date)
        console.print(format_healthcheck_result(result))
    return
```

This must return before `build_config()` and before any LLM graph is created.

- [ ] **Step 3: Run help check**

Run:

```bash
python3 analyze.py --help | rg "etf-healthcheck"
```

Expected: help output contains `--etf-healthcheck`.

- [ ] **Step 4: Run no-token healthcheck smoke**

Run:

```bash
python3 analyze.py 510300 --etf-healthcheck -d 2026-05-15
```

Expected: command exits without LLM API calls. If `TUSHARE_TOKEN` is absent or vendor calls fail, output may be `partial` or `blocked`, but it must explain the failure instead of raising an uncaught traceback.

- [ ] **Step 5: Compile**

Run:

```bash
python3 -m compileall analyze.py tradingagents/dataflows
```

Expected: compile succeeds.

- [ ] **Step 6: Commit**

```bash
git add analyze.py
git commit -m "feat: add ETF healthcheck CLI"
```

## Task 8: Route ETF Tools Through Research Packages

**Files:**
- Modify: `tradingagents/agents/utils/etf_data_tools.py`

- [ ] **Step 1: Replace direct `route_to_vendor` use for research package tools**

Update tools:

- `get_etf_price_data` calls `build_market_package()` and `format_research_package()`.
- `get_etf_profile` calls `build_product_package()`.
- `get_etf_holdings` calls `build_exposure_package()`.
- `get_etf_fund_flow` calls `build_flow_package()`.
- `get_etf_discount_premium` calls `build_product_package()` and extracts/prints discount metrics if present.
- `get_etf_tracking_info` calls `build_product_package()` or a dedicated tracking package if implemented.
- `get_etf_news` calls `build_event_package()`.

Keep `get_etf_indicators` on the existing route for now unless market package fully replaces its output; ETF market analyst can continue to request indicators separately.

- [ ] **Step 2: Add graceful error formatting**

Each tool should catch exceptions and return:

```text
# ETF Data Error for <symbol>

Status: unavailable
Warning: <exception message>
```

Do not raise from LangChain tools for recoverable data failures.

- [ ] **Step 3: Smoke invoke one tool**

Run:

```bash
python3 - <<'PY'
from tradingagents.agents.utils.etf_data_tools import get_etf_profile
print(get_etf_profile.invoke({"ticker": "510300", "curr_date": "2026-05-15"})[:500])
PY
```

Expected: returns package markdown or a formatted unavailable message; no raw traceback.

- [ ] **Step 4: Compile**

Run:

```bash
python3 -m compileall tradingagents/agents/utils/etf_data_tools.py
```

Expected: compile succeeds.

- [ ] **Step 5: Commit**

```bash
git add tradingagents/agents/utils/etf_data_tools.py
git commit -m "feat: route ETF tools through research packages"
```

## Task 9: Strengthen ETF Analyst Prompts

**Files:**
- Modify: `tradingagents/agents/utils/etf_prompt_utils.py`
- Modify: `tradingagents/agents/analysts/etf_market_analyst.py`
- Modify: `tradingagents/agents/analysts/etf_product_analyst.py`
- Modify: `tradingagents/agents/analysts/etf_flow_analyst.py`
- Modify: `tradingagents/agents/analysts/etf_news_analyst.py`

- [ ] **Step 1: Add common data quality prompt section**

In `etf_prompt_utils.py`, add:

```python
ETF_DATA_QUALITY_REQUIREMENT = (
    "必须说明本报告依赖的数据质量：哪些数据完整、哪些为 partial、哪些 unavailable。"
    "如果折溢价、跟踪偏离、持仓集中度或事件数据不可用，必须明确写出不可用原因，禁止编造。"
)

ETF_FORBIDDEN_STOCK_LANGUAGE = (
    "禁止使用公司财报、PE/PB/PEG、管理层、营收、利润、ROE 等个股基本面措辞。"
)
```

Append both strings to all ETF prompt builders.

- [ ] **Step 2: Update analyst prompts to mention research packages**

In each ETF analyst file, change wording from “下面已提供 CSV/数据” to “下面已提供 ETF research package”。Require:

- `ETF Market Analyst`: trading view plus liquidity and discount/premium caveat.
- `ETF Product Analyst`: allocation view plus product quality and exposure.
- `ETF Flow Analyst`: proxy metric disclosure.
- `ETF News Analyst`: no invented events.

- [ ] **Step 3: Grep for forbidden stock terms in ETF prompt helpers**

Run:

```bash
rg -n "PE|PB|PEG|管理层|营收|利润|ROE|财报" tradingagents/agents/utils/etf_prompt_utils.py tradingagents/agents/analysts/etf_*.py
```

Expected: only the explicit forbidden-language warning may contain these terms.

- [ ] **Step 4: Compile**

Run:

```bash
python3 -m compileall tradingagents/agents/utils/etf_prompt_utils.py tradingagents/agents/analysts/etf_market_analyst.py tradingagents/agents/analysts/etf_product_analyst.py tradingagents/agents/analysts/etf_flow_analyst.py tradingagents/agents/analysts/etf_news_analyst.py
```

Expected: compile succeeds.

- [ ] **Step 5: Commit**

```bash
git add tradingagents/agents/utils/etf_prompt_utils.py tradingagents/agents/analysts/etf_market_analyst.py tradingagents/agents/analysts/etf_product_analyst.py tradingagents/agents/analysts/etf_flow_analyst.py tradingagents/agents/analysts/etf_news_analyst.py
git commit -m "feat: strengthen ETF analyst prompts"
```

## Task 10: Add ETF Professional Research Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add ETF healthcheck section**

Add a short section:

````markdown
## ETF Data Healthcheck

Professional A-share ETF analysis uses Tushare first and AkShare as fallback.
Set `TUSHARE_TOKEN` for the richest ETF product, share, NAV, holding, and index data.

```bash
python analyze.py 510300 159919 518880 --etf-healthcheck -d 2026-05-15
```

Ratings:

- `ready`: core data is available for professional analysis.
- `partial`: analysis can run, but reports must disclose missing data.
- `blocked`: admission failed or core data is unavailable.
````

- [ ] **Step 2: Check markdown rendering basics**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path("README.md").read_text()
assert "ETF Data Healthcheck" in text
assert "--etf-healthcheck" in text
print("README ETF healthcheck docs present")
PY
```

Expected: assertion passes.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document ETF healthcheck"
```

## Task 11: End-to-End Verification

**Files:**
- No new files unless fixes are needed.

- [ ] **Step 1: Compile all project Python**

Run:

```bash
python3 -m compileall tradingagents cli analyze.py main.py
```

Expected: compile succeeds.

- [ ] **Step 2: Run import smoke**

Run:

```bash
python3 - <<'PY'
from tradingagents.dataflows.etf_healthcheck import run_etf_healthcheck
from tradingagents.dataflows.etf_research_service import build_market_package
from tradingagents.agents.utils.etf_data_tools import get_etf_profile
print("imports ok")
PY
```

Expected: `imports ok`.

- [ ] **Step 3: Run representative healthchecks**

Run:

```bash
python3 analyze.py 510300 159919 518880 --etf-healthcheck -d 2026-05-15
```

Expected:

- Each symbol prints a healthcheck block.
- Command does not invoke an LLM.
- Command exits without uncaught traceback.
- If `TUSHARE_TOKEN` or API permissions are missing, output is `partial` or `blocked` with warnings.

- [ ] **Step 4: Confirm stock mode still compiles and CLI help works**

Run:

```bash
python3 analyze.py --help >/tmp/analyze_help.txt
rg "分析强度" /tmp/analyze_help.txt
```

Expected: help text still renders.

- [ ] **Step 5: Final status check**

Run:

```bash
git status --short
```

Expected: clean working tree, unless generated cache files are intentionally untracked and ignored.

## Task 12: Final Commit If Verification Required Fixes

**Files:**
- Any files fixed during Task 11.

- [ ] **Step 1: Commit verification fixes only if files changed**

```bash
git add <changed-files>
git commit -m "fix: stabilize ETF professional research flow"
```

- [ ] **Step 2: Record final verification evidence**

In the final handoff, include:

- compile command result
- import smoke result
- healthcheck command result summary
- whether `TUSHARE_TOKEN` was present
- any modules that are still `partial` or `blocked`
