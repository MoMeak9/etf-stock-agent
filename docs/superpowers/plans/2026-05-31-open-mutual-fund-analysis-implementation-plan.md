# Open Mutual Fund Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `asset_type=fund` for ordinary open-ended public mutual funds, with Tushare-first and AKShare-fallback research packages, registry-based auto detection, long-term macro-aware fund analysis, fund analysts, and CLI/API/Python entry points.

**Architecture:** Build a fund-specific chain that mirrors the ETF package pattern without reusing ETF trading semantics. Fund registry and research packages live in `tradingagents/dataflows`, fund tools and analysts live in `tradingagents/agents`, and existing graph/service/CLI entry points receive a new `fund` branch.

**Tech Stack:** Python, pandas, LangGraph, LangChain tools, Pydantic, unittest/pytest, Tushare, AKShare.

---

## File Structure

- Create `tradingagents/dataflows/fund_models.py`: typed contracts for fund admission, quality, and research packages.
- Create `tradingagents/dataflows/fund_registry.py`: fund admission, classification, ETF rejection, Tushare-first metadata probing, AKShare fallback.
- Create `tradingagents/dataflows/tushare_fund.py`: Tushare fund vendor adapter functions.
- Create `tradingagents/dataflows/akshare_fund.py`: AKShare fund vendor adapter functions.
- Create `tradingagents/dataflows/fund_research_service.py`: package builders, metrics, fallback orchestration, formatting.
- Create `tradingagents/agents/utils/fund_data_tools.py`: LangChain tool wrappers around fund packages, including macro context.
- Create `tradingagents/agents/utils/fund_prompt_utils.py`: shared fund prompt headers, long-term perspective, and banned language guidance.
- Create `tradingagents/agents/analysts/fund_nav_analyst.py`: NAV, performance, and macro-aware return quality analyst.
- Create `tradingagents/agents/analysts/fund_product_analyst.py`: product and manager analyst.
- Create `tradingagents/agents/analysts/fund_portfolio_analyst.py`: portfolio, exposure, and macro-fit analyst.
- Create `tradingagents/agents/analysts/fund_event_analyst.py`: event, announcement, and macro-risk analyst.
- Modify `analyze.py`: fund intensity profiles, auto detection, config, CLI help.
- Modify `cli/models.py` and `cli/utils.py`: fund asset type and analyst selection.
- Modify `tradingagents/api/schemas.py`: allow `fund` and default API asset type to `auto`.
- Modify `tradingagents/services/analysis_service.py`: allow fund and auto default.
- Modify `tradingagents/default_config.py`: selected fund analysts.
- Modify `tradingagents/agents/__init__.py`: export fund analyst factories.
- Modify `tradingagents/agents/utils/agent_states.py`: fund report fields and mapping.
- Modify `tradingagents/graph/conditional_logic.py`: continuation logic for fund analysts.
- Modify `tradingagents/graph/setup.py`: fund analyst factory map.
- Modify `tradingagents/graph/trading_graph.py`: fund tools, fund validation, progress tracking, report titles.
- Modify `tradingagents/graph/propagation.py`: fund initial prompt.
- Modify `tradingagents/agents/managers/research_manager.py`, `tradingagents/agents/managers/risk_manager.py`, and `tradingagents/agents/trader/trader.py`: fund-specific decision language.
- Add tests in `tests/test_fund_registry.py`, `tests/test_fund_research_service.py`, `tests/test_fund_tools_and_graph.py`, and update existing asset/API/service tests.

---

### Task 1: Fund Contracts And Registry

**Files:**
- Create: `tradingagents/dataflows/fund_models.py`
- Create: `tradingagents/dataflows/fund_registry.py`
- Test: `tests/test_fund_registry.py`

- [ ] **Step 1: Write failing registry tests**

Add this file:

```python
import unittest
from unittest.mock import patch

import pandas as pd

from tradingagents.dataflows.fund_registry import admit_fund, clear_fund_admission_cache


class FundRegistryTests(unittest.TestCase):
    def setUp(self):
        clear_fund_admission_cache()

    def test_admits_qdii_open_fund_from_tushare(self):
        profile = pd.DataFrame(
            [
                {
                    "ts_code": "008763.OF",
                    "name": "天弘越南市场股票发起(QDII)A",
                    "fund_type": "QDII",
                    "management": "天弘基金",
                }
            ]
        )
        with patch("tradingagents.dataflows.tushare_fund.fetch_fund_basic", return_value=profile):
            admission = admit_fund("008763")

        self.assertTrue(admission.is_supported)
        self.assertEqual(admission.symbol, "008763")
        self.assertEqual(admission.fund_type, "qdii")
        self.assertEqual(admission.quality.status, "ok")
        self.assertEqual(admission.quality.primary_source, "tushare")

    def test_rejects_etf_code_in_fund_mode(self):
        admission = admit_fund("159949")

        self.assertFalse(admission.is_supported)
        self.assertEqual(admission.quality.status, "blocked")
        self.assertIn("use asset_type=etf", admission.reason)

    def test_falls_back_to_akshare_when_tushare_empty(self):
        ak_profile = pd.DataFrame(
            [
                {
                    "基金代码": "008763",
                    "基金简称": "天弘越南市场股票发起(QDII)A",
                    "基金类型": "QDII",
                }
            ]
        )
        with patch("tradingagents.dataflows.tushare_fund.fetch_fund_basic", return_value=pd.DataFrame()), patch(
            "tradingagents.dataflows.akshare_fund.fetch_fund_basic", return_value=ak_profile
        ):
            admission = admit_fund("008763")

        self.assertTrue(admission.is_supported)
        self.assertEqual(admission.fund_type, "qdii")
        self.assertEqual(admission.quality.fallback_source, "akshare")

    def test_unknown_type_is_partial_but_supported(self):
        profile = pd.DataFrame([{"ts_code": "009999.OF", "name": "测试基金", "fund_type": "其他"}])
        with patch("tradingagents.dataflows.tushare_fund.fetch_fund_basic", return_value=profile):
            admission = admit_fund("009999")

        self.assertTrue(admission.is_supported)
        self.assertEqual(admission.fund_type, "unknown")
        self.assertEqual(admission.quality.status, "partial")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_fund_registry.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `tradingagents.dataflows.fund_registry`.

- [ ] **Step 3: Create fund model contracts**

Create `tradingagents/dataflows/fund_models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FundDataQuality:
    status: str = "ok"
    primary_source: str = "tushare"
    fallback_source: str = "none"
    as_of_date: str = ""
    warnings: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FundAdmission:
    symbol: str
    ts_code: str
    is_supported: bool
    fund_type: str
    reason: str = ""
    profile: dict[str, Any] = field(default_factory=dict)
    quality: FundDataQuality = field(default_factory=FundDataQuality)


@dataclass(frozen=True)
class FundResearchPackage:
    symbol: str
    fund_type: str
    package_type: str
    status: str
    quality: FundDataQuality
    metrics: dict[str, Any] = field(default_factory=dict)
    raw_summary: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Create minimal vendor stubs**

Create `tradingagents/dataflows/tushare_fund.py`:

```python
"""Open-ended public fund data access via Tushare."""

from __future__ import annotations

from tradingagents.dataflows.tushare_stock import _get_tushare_api


def to_fund_ts_code(symbol: str) -> str:
    normalized = str(symbol).strip()
    return f"{normalized}.OF"


def fetch_fund_basic(symbol: str):
    pro = _get_tushare_api()
    ts_code = to_fund_ts_code(symbol)
    try:
        return pro.fund_basic(ts_code=ts_code)
    except Exception as exc:
        message = str(exc).lower()
        if "ts_code" not in message and "unexpected" not in message and "keyword" not in message:
            raise
        df = pro.fund_basic()
        if df is not None and not df.empty and "ts_code" in df.columns:
            return df[df["ts_code"] == ts_code]
        return df
```

Create `tradingagents/dataflows/akshare_fund.py`:

```python
"""Open-ended public fund data access via AKShare."""

from __future__ import annotations


def fetch_fund_basic(symbol: str):
    import akshare as ak

    funds = ak.fund_name_em()
    if funds is None or funds.empty:
        return funds
    code_column = "基金代码" if "基金代码" in funds.columns else funds.columns[0]
    return funds[funds[code_column].astype(str).str.zfill(6) == str(symbol).zfill(6)]
```

- [ ] **Step 5: Implement registry**

Create `tradingagents/dataflows/fund_registry.py`:

```python
"""Open-ended public fund admission and classification helpers."""

from __future__ import annotations

import re
from typing import Any

from tradingagents.dataflows.fund_models import FundAdmission, FundDataQuality
from tradingagents.dataflows.market_utils import is_etf
from tradingagents.dataflows.tushare_fund import to_fund_ts_code

_ADMISSION_CACHE: dict[str, FundAdmission] = {}


def clear_fund_admission_cache() -> None:
    _ADMISSION_CACHE.clear()


def _has_data(frame: Any) -> bool:
    return frame is not None and not getattr(frame, "empty", True)


def _first_record(frame: Any) -> dict[str, Any]:
    if not _has_data(frame):
        return {}
    return {str(key): value for key, value in frame.iloc[0].to_dict().items()}


def _profile_text(profile: dict[str, Any]) -> str:
    keys = ("fund_type", "type", "name", "short_name", "基金类型", "基金简称", "基金名称")
    return " ".join(str(profile.get(key, "")) for key in keys)


def classify_fund(profile: dict[str, Any]) -> str:
    text = _profile_text(profile).lower()
    if "qdii" in text:
        return "qdii"
    if any(token in text for token in ("货币", "money")):
        return "money_market"
    if any(token in text for token in ("债", "bond")):
        return "bond"
    if "fof" in text:
        return "fof"
    if any(token in text for token in ("指数", "index")):
        return "index"
    if any(token in text for token in ("混合", "hybrid")):
        return "hybrid"
    if any(token in text for token in ("股票", "equity")):
        return "equity"
    return "unknown"


def admit_fund(symbol: str) -> FundAdmission:
    normalized = str(symbol).strip()
    if normalized in _ADMISSION_CACHE:
        return _ADMISSION_CACHE[normalized]

    ts_code = to_fund_ts_code(normalized)
    if not re.fullmatch(r"\d{6}", normalized):
        return FundAdmission(
            symbol=normalized,
            ts_code=ts_code,
            is_supported=False,
            fund_type="unknown",
            reason="fund mode requires a 6-digit mainland public fund code.",
            quality=FundDataQuality(status="blocked", missing_fields=["six_digit_fund_code"]),
        )

    if is_etf(normalized):
        return FundAdmission(
            symbol=normalized,
            ts_code=ts_code,
            is_supported=False,
            fund_type="unknown",
            reason="This symbol looks like an A-share ETF; use asset_type=etf.",
            quality=FundDataQuality(status="blocked", missing_fields=["open_fund_profile"]),
        )

    warnings: list[str] = []
    fallback_source = "none"
    profile: dict[str, Any] = {}
    try:
        from tradingagents.dataflows import tushare_fund

        profile = _first_record(tushare_fund.fetch_fund_basic(normalized))
        if not profile:
            warnings.append("tushare returned empty fund_basic")
    except Exception as exc:
        warnings.append(f"tushare failed: {exc}")

    if not profile:
        try:
            from tradingagents.dataflows import akshare_fund

            profile = _first_record(akshare_fund.fetch_fund_basic(normalized))
            if profile:
                fallback_source = "akshare"
            else:
                warnings.append("akshare returned empty fund_basic")
        except Exception as exc:
            warnings.append(f"akshare failed: {exc}")

    if not profile:
        return FundAdmission(
            symbol=normalized,
            ts_code=ts_code,
            is_supported=False,
            fund_type="unknown",
            reason="No open-ended public fund metadata found.",
            quality=FundDataQuality(status="blocked", fallback_source=fallback_source, warnings=warnings, missing_fields=["fund_basic"]),
        )

    fund_type = classify_fund(profile)
    quality_status = "partial" if fund_type == "unknown" else "ok"
    missing_fields = ["fund_type"] if fund_type == "unknown" else []
    admission = FundAdmission(
        symbol=normalized,
        ts_code=ts_code,
        is_supported=True,
        fund_type=fund_type,
        profile=profile,
        quality=FundDataQuality(
            status=quality_status,
            fallback_source=fallback_source,
            warnings=warnings,
            missing_fields=missing_fields,
        ),
    )
    _ADMISSION_CACHE[normalized] = admission
    return admission
```

- [ ] **Step 6: Run registry tests**

Run:

```bash
pytest tests/test_fund_registry.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tradingagents/dataflows/fund_models.py tradingagents/dataflows/fund_registry.py tradingagents/dataflows/tushare_fund.py tradingagents/dataflows/akshare_fund.py tests/test_fund_registry.py
git commit -m "feat: add open fund registry"
```

---

### Task 2: Fund Vendor Adapters And Research Packages

**Files:**
- Modify: `tradingagents/dataflows/tushare_fund.py`
- Modify: `tradingagents/dataflows/akshare_fund.py`
- Create: `tradingagents/dataflows/fund_research_service.py`
- Test: `tests/test_fund_research_service.py`

- [ ] **Step 1: Write failing package tests**

Create `tests/test_fund_research_service.py`:

```python
import unittest
from unittest.mock import patch

import pandas as pd

from tradingagents.dataflows.fund_registry import clear_fund_admission_cache
from tradingagents.dataflows.fund_research_service import (
    build_macro_package,
    build_nav_package,
    build_product_package,
    format_fund_research_package,
)


class FundResearchServiceTests(unittest.TestCase):
    def setUp(self):
        clear_fund_admission_cache()

    def _basic(self):
        return pd.DataFrame(
            [{"ts_code": "008763.OF", "name": "天弘越南市场股票发起(QDII)A", "fund_type": "QDII"}]
        )

    def test_nav_package_computes_return_and_drawdown(self):
        nav = pd.DataFrame(
            [
                {"nav_date": "20260101", "unit_nav": 1.0, "accum_nav": 1.0},
                {"nav_date": "20260201", "unit_nav": 1.2, "accum_nav": 1.2},
                {"nav_date": "20260301", "unit_nav": 0.9, "accum_nav": 0.9},
                {"nav_date": "20260401", "unit_nav": 1.1, "accum_nav": 1.1},
            ]
        )
        with patch("tradingagents.dataflows.tushare_fund.fetch_fund_basic", return_value=self._basic()), patch(
            "tradingagents.dataflows.tushare_fund.fetch_fund_nav", return_value=nav
        ):
            package = build_nav_package("008763", "2026-04-01")

        self.assertEqual(package.status, "ok")
        self.assertIn("period_return", package.metrics)
        self.assertLess(package.metrics["max_drawdown"], 0)

    def test_product_package_records_missing_purchase_status(self):
        with patch("tradingagents.dataflows.tushare_fund.fetch_fund_basic", return_value=self._basic()):
            package = build_product_package("008763", "2026-04-01")

        self.assertEqual(package.status, "partial")
        self.assertIn("purchase_status", package.quality.missing_fields)

    def test_format_includes_quality_and_metrics(self):
        with patch("tradingagents.dataflows.tushare_fund.fetch_fund_basic", return_value=self._basic()):
            package = build_product_package("008763", "2026-04-01")

        formatted = format_fund_research_package(package)
        self.assertIn("Fund Product Research Package", formatted)
        self.assertIn("Missing Fields", formatted)

    def test_macro_package_uses_global_news_context(self):
        with patch("tradingagents.dataflows.tushare_fund.fetch_fund_basic", return_value=self._basic()), patch(
            "tradingagents.dataflows.fund_research_service.fetch_global_macro_news",
            return_value="## Global Market News\nFed rates and Vietnam market liquidity",
        ):
            package = build_macro_package("008763", "2026-04-01")

        self.assertEqual(package.package_type, "macro")
        self.assertEqual(package.fund_type, "qdii")
        self.assertIn("global_macro_news", package.raw_summary)
        self.assertIn("fx", package.metrics["macro_focus"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_fund_research_service.py -v
```

Expected: FAIL with missing `fund_research_service`.

- [ ] **Step 3: Extend vendor adapters**

Add these functions to `tradingagents/dataflows/tushare_fund.py`:

```python
def _compact_date(date: str) -> str:
    return str(date).replace("-", "")


def fetch_fund_nav(symbol: str, start_date: str, end_date: str):
    pro = _get_tushare_api()
    return pro.fund_nav(
        ts_code=to_fund_ts_code(symbol),
        start_date=_compact_date(start_date),
        end_date=_compact_date(end_date),
    )


def fetch_fund_portfolio(symbol: str):
    pro = _get_tushare_api()
    return pro.fund_portfolio(ts_code=to_fund_ts_code(symbol))


def fetch_fund_manager(symbol: str):
    pro = _get_tushare_api()
    method = getattr(pro, "fund_manager", None)
    if method is None:
        return None
    return method(ts_code=to_fund_ts_code(symbol))


def fetch_fund_announcement(symbol: str, start_date: str, end_date: str):
    pro = _get_tushare_api()
    method = getattr(pro, "fund_announcement", None)
    if method is None:
        return None
    return method(ts_code=to_fund_ts_code(symbol), start_date=_compact_date(start_date), end_date=_compact_date(end_date))
```

Add these functions to `tradingagents/dataflows/akshare_fund.py`:

```python
def fetch_fund_nav(symbol: str, start_date: str, end_date: str):
    import akshare as ak

    return ak.fund_open_fund_info_em(symbol=str(symbol), indicator="单位净值走势")


def fetch_fund_portfolio(symbol: str):
    import akshare as ak

    return ak.fund_portfolio_hold_em(symbol=str(symbol), date=str(end_date_year()))


def fetch_fund_manager(symbol: str):
    return None


def fetch_fund_announcement(symbol: str, start_date: str, end_date: str):
    return None


def end_date_year() -> str:
    from datetime import date

    return str(date.today().year)
```

- [ ] **Step 4: Implement research service**

Create `tradingagents/dataflows/fund_research_service.py` with these core functions:

```python
from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from tradingagents.dataflows.fund_models import FundDataQuality, FundResearchPackage
from tradingagents.dataflows.fund_registry import admit_fund

DATE_COLUMNS = ("nav_date", "date", "end_date", "ann_date", "净值日期", "日期")


def _date_lookback(curr_date: str, days: int) -> str:
    return (pd.Timestamp(curr_date) - pd.DateOffset(days=days)).strftime("%Y-%m-%d")


def _has_data(data: Any) -> bool:
    return data is not None and not getattr(data, "empty", True)


def _call_with_fallback(primary: Callable[[], Any], fallback: Callable[[], Any] | None = None):
    warnings: list[str] = []
    try:
        data = primary()
        if _has_data(data):
            return data, "none", warnings
        warnings.append("tushare returned empty data")
    except Exception as exc:
        warnings.append(f"tushare failed: {exc}")
    if fallback is not None:
        try:
            data = fallback()
            if _has_data(data):
                return data, "akshare", warnings
            warnings.append("akshare returned empty data")
        except Exception as exc:
            warnings.append(f"akshare failed: {exc}")
    return None, "akshare" if fallback is not None else "none", warnings


def _pick_column(df: Any, candidates: tuple[str, ...]) -> str | None:
    if not _has_data(df) or not hasattr(df, "columns"):
        return None
    lowered = {str(column).lower(): str(column) for column in df.columns}
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype("string").str.replace(",", "", regex=False).str.replace("%", "", regex=False), errors="coerce")


def _parse_dates(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    compact = cleaned.str.fullmatch(r"\d{8}", na=False)
    dates = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    if compact.any():
        dates.loc[compact] = pd.to_datetime(cleaned.loc[compact], format="%Y%m%d", errors="coerce")
    if (~compact).any():
        dates.loc[~compact] = pd.to_datetime(cleaned.loc[~compact], errors="coerce")
    return dates


def _latest_date(df: Any, date_col: str | None) -> str:
    if not _has_data(df) or not date_col:
        return ""
    dates = _parse_dates(df[date_col])
    if dates.isna().all():
        return ""
    return dates.max().strftime("%Y-%m-%d")


def _status(missing_fields: list[str], warnings: list[str]) -> str:
    return "partial" if missing_fields or warnings else "ok"


def _frame_summary(df: Any, source: str, date_col: str | None = None) -> dict[str, Any]:
    if not _has_data(df):
        return {"rows": 0, "columns": [], "source": "unavailable"}
    return {
        "rows": int(len(df)),
        "columns": [str(column) for column in df.columns],
        "source": source,
        "latest_date": _latest_date(df, date_col) if date_col else "",
    }


def _blocked(symbol: str, package_type: str, curr_date: str, reason: str) -> FundResearchPackage:
    return FundResearchPackage(
        symbol=symbol,
        fund_type="unknown",
        package_type=package_type,
        status="blocked",
        quality=FundDataQuality(status="blocked", as_of_date=curr_date, warnings=[reason], missing_fields=["fund_admission"]),
    )


def build_nav_package(symbol: str, curr_date: str) -> FundResearchPackage:
    from tradingagents.dataflows import akshare_fund, tushare_fund

    admission = admit_fund(symbol)
    if not admission.is_supported:
        return _blocked(symbol, "nav", curr_date, admission.reason)
    start = _date_lookback(curr_date, 370)
    nav, fallback, warnings = _call_with_fallback(
        lambda: tushare_fund.fetch_fund_nav(symbol, start, curr_date),
        lambda: akshare_fund.fetch_fund_nav(symbol, start, curr_date),
    )
    missing_fields: list[str] = []
    metrics: dict[str, Any] = {}
    date_col = _pick_column(nav, DATE_COLUMNS)
    value_col = _pick_column(nav, ("unit_nav", "nav", "单位净值", "累计净值"))
    if _has_data(nav) and value_col:
        frame = nav.copy()
        frame["_value"] = _numeric(frame[value_col])
        if date_col:
            frame["_date"] = _parse_dates(frame[date_col])
            frame = frame.dropna(subset=["_date"]).sort_values("_date")
        values = frame["_value"].dropna()
        if len(values) >= 2:
            metrics["period_return"] = float(values.iloc[-1] / values.iloc[0] - 1)
            running_max = values.cummax()
            drawdown = values / running_max - 1
            metrics["max_drawdown"] = float(drawdown.min())
            metrics["latest_nav"] = float(values.iloc[-1])
        else:
            missing_fields.append("nav_history")
    else:
        missing_fields.append("unit_nav")
    if not _has_data(nav):
        missing_fields.append("fund_nav")
    status = "unavailable" if not _has_data(nav) else _status(missing_fields, warnings)
    return FundResearchPackage(
        symbol=admission.symbol,
        fund_type=admission.fund_type,
        package_type="nav",
        status=status,
        quality=FundDataQuality(status=status, fallback_source=fallback, as_of_date=_latest_date(nav, date_col), warnings=warnings, missing_fields=missing_fields),
        metrics=metrics,
        raw_summary={"nav": _frame_summary(nav, "tushare" if fallback == "none" else fallback, date_col)},
    )


def build_product_package(symbol: str, curr_date: str) -> FundResearchPackage:
    admission = admit_fund(symbol)
    if not admission.is_supported:
        return _blocked(symbol, "product", curr_date, admission.reason)
    profile = dict(admission.profile)
    missing_fields: list[str] = []
    for field_name, candidates in {
        "purchase_status": ("purchase_status", "申购状态"),
        "redemption_status": ("redemption_status", "赎回状态"),
    }.items():
        if not any(candidate in profile and str(profile.get(candidate, "")).strip() for candidate in candidates):
            missing_fields.append(field_name)
    warnings = list(admission.quality.warnings)
    status = _status(missing_fields + list(admission.quality.missing_fields), warnings)
    return FundResearchPackage(
        symbol=admission.symbol,
        fund_type=admission.fund_type,
        package_type="product",
        status=status,
        quality=FundDataQuality(status=status, fallback_source=admission.quality.fallback_source, as_of_date=curr_date, warnings=warnings, missing_fields=missing_fields),
        raw_summary={"profile": profile},
    )


def build_portfolio_package(symbol: str, curr_date: str) -> FundResearchPackage:
    admission = admit_fund(symbol)
    return FundResearchPackage(admission.symbol, admission.fund_type, "portfolio", "partial", FundDataQuality(status="partial", as_of_date=curr_date, missing_fields=["portfolio_detail"]), raw_summary={"profile": admission.profile})


def build_manager_package(symbol: str, curr_date: str) -> FundResearchPackage:
    admission = admit_fund(symbol)
    return FundResearchPackage(admission.symbol, admission.fund_type, "manager", "partial", FundDataQuality(status="partial", as_of_date=curr_date, missing_fields=["manager_history"]), raw_summary={"profile": admission.profile})


def build_event_package(symbol: str, curr_date: str) -> FundResearchPackage:
    admission = admit_fund(symbol)
    return FundResearchPackage(admission.symbol, admission.fund_type, "event", "partial", FundDataQuality(status="partial", as_of_date=curr_date, missing_fields=["fund_announcements"]), raw_summary={"profile": admission.profile})


def build_performance_package(symbol: str, curr_date: str) -> FundResearchPackage:
    admission = admit_fund(symbol)
    return FundResearchPackage(admission.symbol, admission.fund_type, "performance", "partial", FundDataQuality(status="partial", as_of_date=curr_date, missing_fields=["peer_ranking"]), raw_summary={"profile": admission.profile})


def fetch_global_macro_news(curr_date: str, look_back_days: int = 30, limit: int = 10) -> str:
    from tradingagents.agents.utils.news_data_tools import get_global_news

    return str(get_global_news.invoke({"curr_date": curr_date, "look_back_days": look_back_days, "limit": limit}))


def _macro_focus_for(fund_type: str) -> list[str]:
    focus = {
        "qdii": ["overseas_market_cycle", "fx", "overseas_rates", "policy", "holiday_mismatch"],
        "bond": ["central_bank_policy", "yield_curve", "credit_spread", "inflation", "duration"],
        "money_market": ["short_term_rates", "liquidity", "redemption_pressure", "seasonal_cash_stress"],
        "equity": ["growth_cycle", "liquidity_cycle", "sector_cycle", "valuation_regime", "policy"],
        "hybrid": ["growth_cycle", "liquidity_cycle", "equity_bond_balance", "risk_appetite"],
        "index": ["benchmark_cycle", "valuation_regime", "liquidity_cycle", "policy"],
        "fof": ["cross_asset_allocation", "equity_bond_balance", "global_risk_appetite", "fee_drag"],
    }
    return focus.get(fund_type, ["macro_context_uncertain", "data_quality"])


def build_macro_package(symbol: str, curr_date: str) -> FundResearchPackage:
    admission = admit_fund(symbol)
    if not admission.is_supported:
        return _blocked(symbol, "macro", curr_date, admission.reason)
    warnings: list[str] = []
    global_news = ""
    try:
        global_news = fetch_global_macro_news(curr_date, look_back_days=30, limit=10)
    except Exception as exc:
        warnings.append(f"global_macro_news unavailable: {exc}")
    missing_fields = [] if global_news.strip() else ["global_macro_news"]
    status = _status(missing_fields, warnings)
    return FundResearchPackage(
        symbol=admission.symbol,
        fund_type=admission.fund_type,
        package_type="macro",
        status=status,
        quality=FundDataQuality(status=status, as_of_date=curr_date, warnings=warnings, missing_fields=missing_fields),
        metrics={"macro_focus": _macro_focus_for(admission.fund_type), "analysis_horizon": "medium_to_long_term"},
        raw_summary={"global_macro_news": global_news[:6000]},
    )


def format_fund_research_package(package: FundResearchPackage) -> str:
    lines = [
        f"# Fund {package.package_type.title()} Research Package for {package.symbol}",
        "",
        f"- Fund Type: {package.fund_type}",
        f"- Status: {package.status}",
        f"- Quality Status: {package.quality.status}",
        f"- Primary Source: {package.quality.primary_source}",
        f"- Fallback Source: {package.quality.fallback_source}",
        f"- As Of Date: {package.quality.as_of_date or 'N/A'}",
    ]
    if package.quality.warnings:
        lines.append("- Warnings: " + "; ".join(package.quality.warnings))
    if package.quality.missing_fields:
        lines.append("- Missing Fields: " + ", ".join(package.quality.missing_fields))
    if package.metrics:
        lines.append("")
        lines.append("## Metrics")
        for key, value in package.metrics.items():
            lines.append(f"- {key}: {value}")
    if package.raw_summary:
        lines.append("")
        lines.append("## Raw Summary")
        for key, value in package.raw_summary.items():
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)
```

- [ ] **Step 5: Run package tests**

Run:

```bash
pytest tests/test_fund_research_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tradingagents/dataflows/tushare_fund.py tradingagents/dataflows/akshare_fund.py tradingagents/dataflows/fund_research_service.py tests/test_fund_research_service.py
git commit -m "feat: add fund research packages"
```

---

### Task 3: Fund Tools And Analysts

**Files:**
- Create: `tradingagents/agents/utils/fund_data_tools.py`
- Create: `tradingagents/agents/utils/fund_prompt_utils.py`
- Create: `tradingagents/agents/analysts/fund_nav_analyst.py`
- Create: `tradingagents/agents/analysts/fund_product_analyst.py`
- Create: `tradingagents/agents/analysts/fund_portfolio_analyst.py`
- Create: `tradingagents/agents/analysts/fund_event_analyst.py`
- Modify: `tradingagents/agents/__init__.py`
- Test: `tests/test_fund_tools_and_graph.py`

- [ ] **Step 1: Write failing tool and analyst smoke tests**

Create `tests/test_fund_tools_and_graph.py`:

```python
import unittest
from unittest.mock import patch

from tradingagents.agents.utils.agent_states import apply_asset_report_mapping
from tradingagents.agents.utils.fund_data_tools import get_fund_nav


class FundToolsAndGraphTests(unittest.TestCase):
    def test_fund_tool_formats_package(self):
        with patch(
            "tradingagents.agents.utils.fund_data_tools.build_nav_package",
        ) as mocked:
            mocked.return_value.symbol = "008763"
            mocked.return_value.fund_type = "qdii"
            mocked.return_value.package_type = "nav"
            mocked.return_value.status = "ok"
            mocked.return_value.quality.status = "ok"
            mocked.return_value.quality.primary_source = "tushare"
            mocked.return_value.quality.fallback_source = "none"
            mocked.return_value.quality.as_of_date = "2026-05-31"
            mocked.return_value.quality.warnings = []
            mocked.return_value.quality.missing_fields = []
            mocked.return_value.metrics = {"period_return": 0.1}
            mocked.return_value.raw_summary = {}
            result = get_fund_nav.invoke({"symbol": "008763", "curr_date": "2026-05-31"})

        self.assertIn("Fund Nav Research Package", result)

    def test_fund_report_mapping(self):
        update = {"fund_nav_report": "nav report", "fund_product_report": "product report"}
        mapped = apply_asset_report_mapping(update, "fund")

        self.assertEqual(mapped["market_report"], "nav report")
        self.assertEqual(mapped["fundamentals_report"], "product report")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_fund_tools_and_graph.py -v
```

Expected: FAIL with missing `fund_data_tools`.

- [ ] **Step 3: Create fund data tools**

Create `tradingagents/agents/utils/fund_data_tools.py`:

```python
from __future__ import annotations

from datetime import date
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.fund_research_service import (
    build_event_package,
    build_macro_package,
    build_manager_package,
    build_nav_package,
    build_performance_package,
    build_portfolio_package,
    build_product_package,
    format_fund_research_package,
)


def _curr_date_or_today(curr_date: str | None) -> str:
    return curr_date or date.today().strftime("%Y-%m-%d")


def _format_error(symbol: str, exc: Exception) -> str:
    return f"# Fund Data Error for {symbol}\n\nStatus: unavailable\nWarning: {exc}"


def _format_package(symbol: str, builder, curr_date: str | None) -> str:
    try:
        return format_fund_research_package(builder(symbol, _curr_date_or_today(curr_date)))
    except Exception as exc:
        return _format_error(symbol, exc)


@tool
def get_fund_nav(symbol: Annotated[str, "Open-ended public fund code"], curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None) -> str:
    """Retrieve fund NAV, return, volatility, and drawdown package."""
    return _format_package(symbol, build_nav_package, curr_date)


@tool
def get_fund_product(symbol: Annotated[str, "Open-ended public fund code"], curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None) -> str:
    """Retrieve fund product profile and subscription metadata package."""
    return _format_package(symbol, build_product_package, curr_date)


@tool
def get_fund_portfolio(symbol: Annotated[str, "Open-ended public fund code"], curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None) -> str:
    """Retrieve fund portfolio and exposure package."""
    return _format_package(symbol, build_portfolio_package, curr_date)


@tool
def get_fund_manager(symbol: Annotated[str, "Open-ended public fund code"], curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None) -> str:
    """Retrieve fund manager package."""
    return _format_package(symbol, build_manager_package, curr_date)


@tool
def get_fund_event(symbol: Annotated[str, "Open-ended public fund code"], curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None) -> str:
    """Retrieve fund announcements, restriction, and event package."""
    return _format_package(symbol, build_event_package, curr_date)


@tool
def get_fund_performance(symbol: Annotated[str, "Open-ended public fund code"], curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None) -> str:
    """Retrieve fund relative and risk-adjusted performance package."""
    return _format_package(symbol, build_performance_package, curr_date)


@tool
def get_fund_macro_context(symbol: Annotated[str, "Open-ended public fund code"], curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None) -> str:
    """Retrieve long-term macro context relevant to the fund type."""
    return _format_package(symbol, build_macro_package, curr_date)
```

- [ ] **Step 4: Create prompt utilities**

Create `tradingagents/agents/utils/fund_prompt_utils.py`:

```python
FUND_DECISION_LANGUAGE = "申购、分批申购、持有、赎回、观望"


def build_fund_report_header(title: str, symbol: str) -> str:
    return (
        f"# {title} - {symbol}\n"
        f"- 分析标的：开放式公募基金 {symbol}\n"
        "- 分析视角：以中长期配置、持有和申赎决策为主，结合宏观环境，不做短线交易判断。\n"
        f"- 决策语言限定：{FUND_DECISION_LANGUAGE}\n"
        "- 禁止使用股票买卖、ETF二级市场交易、止损价、目标价等表达。\n"
    )
```

- [ ] **Step 5: Create fund analysts**

Create `tradingagents/agents/analysts/fund_nav_analyst.py`:

```python
from tradingagents.agents.utils.agent_states import apply_asset_report_mapping
from tradingagents.agents.utils.fund_data_tools import get_fund_macro_context, get_fund_nav, get_fund_performance
from tradingagents.agents.utils.fund_prompt_utils import build_fund_report_header


def create_fund_nav_analyst(llm, toolkit=None):
    def fund_nav_analyst_node(state):
        symbol = state["company_of_interest"]
        current_date = state["trade_date"]
        nav_data = get_fund_nav.invoke({"symbol": symbol, "curr_date": current_date})
        performance_data = get_fund_performance.invoke({"symbol": symbol, "curr_date": current_date})
        macro_data = get_fund_macro_context.invoke({"symbol": symbol, "curr_date": current_date})
        prompt = (
            f"{build_fund_report_header('基金净值与收益质量分析', symbol)}\n"
            "请基于真实数据分析净值趋势、回撤、波动、收益质量、宏观环境适配性和数据缺口。\n\n"
            f"## NAV Package\n{nav_data}\n\n"
            f"## Performance Package\n{performance_data}\n\n"
            f"## Macro Package\n{macro_data}"
        )
        result = llm.invoke(prompt)
        update = {"messages": [result], "fund_nav_report": result.content, "nav_tool_call_count": 2}
        return apply_asset_report_mapping(update, "fund")

    return fund_nav_analyst_node
```

Create the remaining analysts with the same direct-invoke style:

```python
# tradingagents/agents/analysts/fund_product_analyst.py
from tradingagents.agents.utils.agent_states import apply_asset_report_mapping
from tradingagents.agents.utils.fund_data_tools import get_fund_manager, get_fund_product
from tradingagents.agents.utils.fund_prompt_utils import build_fund_report_header


def create_fund_product_analyst(llm, toolkit=None):
    def fund_product_analyst_node(state):
        symbol = state["company_of_interest"]
        current_date = state["trade_date"]
        product_data = get_fund_product.invoke({"symbol": symbol, "curr_date": current_date})
        manager_data = get_fund_manager.invoke({"symbol": symbol, "curr_date": current_date})
        prompt = f"{build_fund_report_header('基金产品结构分析', symbol)}\n\n## Product Package\n{product_data}\n\n## Manager Package\n{manager_data}"
        result = llm.invoke(prompt)
        return apply_asset_report_mapping({"messages": [result], "fund_product_report": result.content, "product_tool_call_count": 2}, "fund")

    return fund_product_analyst_node
```

```python
# tradingagents/agents/analysts/fund_portfolio_analyst.py
from tradingagents.agents.utils.agent_states import apply_asset_report_mapping
from tradingagents.agents.utils.fund_data_tools import get_fund_macro_context, get_fund_portfolio
from tradingagents.agents.utils.fund_prompt_utils import build_fund_report_header


def create_fund_portfolio_analyst(llm, toolkit=None):
    def fund_portfolio_analyst_node(state):
        symbol = state["company_of_interest"]
        current_date = state["trade_date"]
        portfolio_data = get_fund_portfolio.invoke({"symbol": symbol, "curr_date": current_date})
        macro_data = get_fund_macro_context.invoke({"symbol": symbol, "curr_date": current_date})
        prompt = f"{build_fund_report_header('基金持仓与暴露分析', symbol)}\n\n## Portfolio Package\n{portfolio_data}\n\n## Macro Package\n{macro_data}"
        result = llm.invoke(prompt)
        return apply_asset_report_mapping({"messages": [result], "fund_portfolio_report": result.content, "portfolio_tool_call_count": 1}, "fund")

    return fund_portfolio_analyst_node
```

```python
# tradingagents/agents/analysts/fund_event_analyst.py
from tradingagents.agents.utils.agent_states import apply_asset_report_mapping
from tradingagents.agents.utils.fund_data_tools import get_fund_event, get_fund_macro_context
from tradingagents.agents.utils.fund_prompt_utils import build_fund_report_header


def create_fund_event_analyst(llm, toolkit=None):
    def fund_event_analyst_node(state):
        symbol = state["company_of_interest"]
        current_date = state["trade_date"]
        event_data = get_fund_event.invoke({"symbol": symbol, "curr_date": current_date})
        macro_data = get_fund_macro_context.invoke({"symbol": symbol, "curr_date": current_date})
        prompt = f"{build_fund_report_header('基金公告与事件风险分析', symbol)}\n\n## Event Package\n{event_data}\n\n## Macro Package\n{macro_data}"
        result = llm.invoke(prompt)
        return apply_asset_report_mapping({"messages": [result], "fund_event_report": result.content, "event_tool_call_count": 1}, "fund")

    return fund_event_analyst_node
```

- [ ] **Step 6: Export fund analysts and mapping**

Modify `tradingagents/agents/__init__.py` to import and export:

```python
from .analysts.fund_nav_analyst import create_fund_nav_analyst
from .analysts.fund_product_analyst import create_fund_product_analyst
from .analysts.fund_portfolio_analyst import create_fund_portfolio_analyst
from .analysts.fund_event_analyst import create_fund_event_analyst
```

Add these names to `__all__`.

Modify `tradingagents/agents/utils/agent_states.py`:

```python
    fund_nav_report: Annotated[str, "Report from the Fund NAV Analyst"]
    fund_product_report: Annotated[str, "Report from the Fund Product Analyst"]
    fund_portfolio_report: Annotated[str, "Report from the Fund Portfolio Analyst"]
    fund_event_report: Annotated[str, "Report from the Fund Event Analyst"]
    nav_tool_call_count: Annotated[int, "Number of tool calls by Fund NAV Analyst"]
    portfolio_tool_call_count: Annotated[int, "Number of tool calls by Fund Portfolio Analyst"]
    event_tool_call_count: Annotated[int, "Number of tool calls by Fund Event Analyst"]
```

Add mapping:

```python
FUND_GENERIC_REPORT_MAP = {
    "fund_nav_report": "market_report",
    "fund_product_report": "fundamentals_report",
    "fund_portfolio_report": "sentiment_report",
    "fund_event_report": "news_report",
}
```

Update `apply_asset_report_mapping` so `asset_type == "fund"` uses `FUND_GENERIC_REPORT_MAP`.

- [ ] **Step 7: Run tool and mapping tests**

Run:

```bash
pytest tests/test_fund_tools_and_graph.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tradingagents/agents/utils/fund_data_tools.py tradingagents/agents/utils/fund_prompt_utils.py tradingagents/agents/analysts/fund_*_analyst.py tradingagents/agents/__init__.py tradingagents/agents/utils/agent_states.py tests/test_fund_tools_and_graph.py
git commit -m "feat: add fund tools and analysts"
```

---

### Task 4: Graph Integration

**Files:**
- Modify: `tradingagents/default_config.py`
- Modify: `tradingagents/graph/conditional_logic.py`
- Modify: `tradingagents/graph/setup.py`
- Modify: `tradingagents/graph/trading_graph.py`
- Modify: `tradingagents/graph/propagation.py`
- Test: `tests/test_fund_tools_and_graph.py`

- [ ] **Step 1: Add graph tests**

Append to `tests/test_fund_tools_and_graph.py`:

```python
    def test_graph_setup_accepts_fund_analysts(self):
        from tradingagents.graph.conditional_logic import ConditionalLogic
        from tradingagents.graph.setup import GraphSetup

        class FakeLLM:
            def invoke(self, prompt):
                class Result:
                    content = "基金分析报告：观望"
                return Result()

        setup = GraphSetup(
            FakeLLM(),
            FakeLLM(),
            {},
            None,
            None,
            None,
            None,
            None,
            ConditionalLogic(),
        )
        graph = setup.setup_graph(["nav", "product", "portfolio", "event"], asset_type="fund")

        self.assertIsNotNone(graph)
```

- [ ] **Step 2: Run graph test to verify it fails**

Run:

```bash
pytest tests/test_fund_tools_and_graph.py::FundToolsAndGraphTests::test_graph_setup_accepts_fund_analysts -v
```

Expected: FAIL with `Unknown analyst type: nav`.

- [ ] **Step 3: Add default config**

Modify `tradingagents/default_config.py`:

```python
"selected_fund_analysts": ["nav", "product", "portfolio", "event"],
```

Keep `asset_type` default as `stock` in `DEFAULT_CONFIG`.

- [ ] **Step 4: Add conditional logic**

Modify `_MAX_TOOL_CALLS` in `tradingagents/graph/conditional_logic.py`:

```python
    "nav": 2,
    "portfolio": 1,
    "event": 1,
```

Add methods:

```python
    def should_continue_nav(self, state: AgentState):
        return self._should_continue_analyst(state, "nav", "fund_nav_report", "nav_tool_call_count", "tools_nav", "Msg Clear Nav")

    def should_continue_portfolio(self, state: AgentState):
        return self._should_continue_analyst(state, "portfolio", "fund_portfolio_report", "portfolio_tool_call_count", "tools_portfolio", "Msg Clear Portfolio")

    def should_continue_event(self, state: AgentState):
        return self._should_continue_analyst(state, "event", "fund_event_report", "event_tool_call_count", "tools_event", "Msg Clear Event")
```

Use the existing `should_continue_product` for fund product only if it checks `fund_product_report` when `asset_type == "fund"`. If keeping one method becomes confusing, add `should_continue_product` branch:

```python
report_field = "fund_product_report" if state.get("asset_type") == "fund" else "etf_product_report"
```

- [ ] **Step 5: Add fund factory map**

Modify `GraphSetup._create_analyst_node`:

```python
        if asset_type == "etf":
            factory_map = {
                "market": create_etf_market_analyst,
                "flow": create_etf_flow_analyst,
                "news": create_etf_news_analyst,
                "product": create_etf_product_analyst,
            }
        elif asset_type == "fund":
            factory_map = {
                "nav": create_fund_nav_analyst,
                "product": create_fund_product_analyst,
                "portfolio": create_fund_portfolio_analyst,
                "event": create_fund_event_analyst,
            }
        else:
            factory_map = {
                "market": create_market_analyst,
                "social": create_social_media_analyst,
                "news": create_news_analyst,
                "fundamentals": create_fundamentals_analyst,
            }
```

- [ ] **Step 6: Add fund tool nodes and validation**

Modify imports in `tradingagents/graph/trading_graph.py`:

```python
from tradingagents.agents.utils.fund_data_tools import (
    get_fund_event,
    get_fund_manager,
    get_fund_macro_context,
    get_fund_nav,
    get_fund_performance,
    get_fund_portfolio,
    get_fund_product,
)
from tradingagents.dataflows.fund_registry import admit_fund
```

Add fund branch in `_create_tool_nodes()`:

```python
        if self._asset_type == "fund":
            return {
                "nav": ToolNode([get_fund_nav, get_fund_performance, get_fund_macro_context]),
                "product": ToolNode([get_fund_product, get_fund_manager]),
                "portfolio": ToolNode([get_fund_portfolio, get_fund_macro_context]),
                "event": ToolNode([get_fund_event, get_fund_macro_context]),
            }
```

Add analyst default rewrite in `__init__`:

```python
        if self._asset_type == "fund" and selected_analysts == ["market", "social", "news", "fundamentals"]:
            selected_analysts = self.config.get("selected_fund_analysts", ["nav", "product", "portfolio", "event"])
```

Add validation in `propagate()`:

```python
        if self._asset_type == "fund":
            admission = admit_fund(company_name)
            if not admission.is_supported:
                raise ValueError(admission.reason or "Fund mode requires an open-ended public fund code.")
```

- [ ] **Step 7: Add fund initial prompt**

Modify `tradingagents/graph/propagation.py` in `create_initial_state` so fund mode uses:

```python
        if self.asset_type == "fund":
            init_msg = (
                f"请对开放式公募基金 {company_name} 进行全面分析，"
                f"重点覆盖净值表现、产品结构、持仓暴露、基金经理、公告、申赎限制与中长期宏观环境，"
                f"最终输出申购、分批申购、持有、赎回或观望建议。"
            )
```

Initialize fund report fields and tool counters to empty strings and zero.

- [ ] **Step 8: Run graph tests**

Run:

```bash
pytest tests/test_fund_tools_and_graph.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add tradingagents/default_config.py tradingagents/graph/conditional_logic.py tradingagents/graph/setup.py tradingagents/graph/trading_graph.py tradingagents/graph/propagation.py tests/test_fund_tools_and_graph.py
git commit -m "feat: wire fund analysts into graph"
```

---

### Task 5: CLI, API, And Service Entry Points

**Files:**
- Modify: `analyze.py`
- Modify: `cli/models.py`
- Modify: `cli/utils.py`
- Modify: `tradingagents/api/schemas.py`
- Modify: `tradingagents/services/analysis_service.py`
- Test: `tests/test_analyze_asset_type.py`
- Test: `tests/test_analysis_service.py`
- Test: `tests/test_analysis_api_models.py`

- [ ] **Step 1: Update failing tests**

Modify `tests/test_analyze_asset_type.py`:

```python
    def test_fund_asset_type_selects_fund_analysts_and_config(self):
        args = analyze.parse_args(["008763", "--asset-type", "fund", "-l", "3"])
        intensity = analyze.resolve_intensity(args)
        config = analyze.build_config(args, intensity)

        self.assertEqual(config["asset_type"], "fund")
        self.assertEqual(intensity["analysts"], ["nav", "product", "portfolio", "event"])
        self.assertEqual(config["selected_fund_analysts"], ["nav", "product", "portfolio", "event"])

    def test_auto_asset_type_detects_open_fund(self):
        with unittest.mock.patch("tradingagents.dataflows.fund_registry.admit_fund") as mocked:
            mocked.return_value.is_supported = True
            asset_type = analyze.resolve_asset_type(["008763"], "auto")

        self.assertEqual(asset_type, "fund")
```

Update `test_stock_mode_remains_default` to `test_cli_default_uses_auto_resolution_for_stock` and expect `args.asset_type == "stock"` after parsing `600519`.

Modify `tests/test_analysis_api_models.py`:

```python
        self.assertEqual(payload.asset_type, "auto")

    def test_request_accepts_fund_asset_type(self):
        payload = AnalysisJobCreate(tickers=["008763"], asset_type="fund")
        self.assertEqual(payload.asset_type, "fund")
```

Modify `tests/test_analysis_service.py`:

```python
    def test_prepare_fund_selects_fund_profiles(self):
        with patch("tradingagents.dataflows.fund_registry.admit_fund") as mocked:
            mocked.return_value.is_supported = True
            prepared = prepare_analysis(
                AnalysisRequest(tickers=["008763"], date="2026-05-22", asset_type="fund", level=3)
            )

        self.assertEqual(prepared.asset_type, "fund")
        self.assertEqual(prepared.analysts, ["nav", "product", "portfolio", "event"])
        self.assertEqual(prepared.config["asset_type"], "fund")
```

- [ ] **Step 2: Run entry point tests to verify they fail**

Run:

```bash
pytest tests/test_analyze_asset_type.py tests/test_analysis_service.py tests/test_analysis_api_models.py -v
```

Expected: FAIL because `fund` is not accepted.

- [ ] **Step 3: Add fund intensity profiles and auto detection**

Modify `analyze.py`:

```python
FUND_INTENSITY_PROFILES = {
    1: {"name": "基金闪电", "desc": "净值快速扫描", "analysts": ["nav"], "max_debate_rounds": 1, "max_risk_discuss_rounds": 1, "max_recur_limit": 50},
    2: {"name": "基金快速", "desc": "净值+产品结构", "analysts": ["nav", "product"], "max_debate_rounds": 1, "max_risk_discuss_rounds": 1, "max_recur_limit": 80},
    3: {"name": "基金标准", "desc": "净值+产品+持仓+事件", "analysts": ["nav", "product", "portfolio", "event"], "max_debate_rounds": 2, "max_risk_discuss_rounds": 2, "max_recur_limit": 100},
    4: {"name": "基金深度", "desc": "深度基金分析", "analysts": ["nav", "product", "portfolio", "event"], "max_debate_rounds": 3, "max_risk_discuss_rounds": 3, "max_recur_limit": 150},
    5: {"name": "基金极致", "desc": "最高精度基金分析", "analysts": ["nav", "product", "portfolio", "event"], "max_debate_rounds": 5, "max_risk_discuss_rounds": 5, "max_recur_limit": 200},
}
```

Update `resolve_asset_type`:

```python
    if normalized in {"stock", "etf", "fund"}:
        return normalized
```

For auto mode, use:

```python
    from tradingagents.dataflows.market_utils import detect_market, is_etf
    from tradingagents.dataflows.fund_registry import admit_fund

    detected = []
    for ticker in tickers:
        candidates = []
        if detect_market(ticker) == "cn" and is_etf(ticker):
            candidates.append("etf")
        fund_admission = admit_fund(ticker)
        if fund_admission.is_supported:
            candidates.append("fund")
        if detect_market(ticker) in {"cn", "us", "hk"} and "etf" not in candidates and "fund" not in candidates:
            candidates.append("stock")
        if len(candidates) > 1:
            raise ValueError(f"Symbol {ticker} matches multiple asset types: {', '.join(candidates)}. Please specify --asset-type.")
        detected.append(candidates[0] if candidates else "stock")
```

Reject mixed detected types as existing code does.

Update `resolve_intensity` to select fund profiles.

Update `build_config`:

```python
    if asset_type == "fund":
        config["selected_fund_analysts"] = intensity["analysts"]
```

Change parser choices to `["stock", "etf", "fund", "auto"]` and default to `"auto"`.

- [ ] **Step 4: Update API and service**

Modify `tradingagents/api/schemas.py`:

```python
asset_type: Literal["stock", "etf", "fund", "auto"] = "auto"
```

Modify `tradingagents/services/analysis_service.py`:

```python
asset_type: str = "auto"
```

and validation:

```python
if request.asset_type not in {"stock", "etf", "fund", "auto"}:
    raise ValueError("asset_type must be one of: stock, etf, fund, auto")
```

- [ ] **Step 5: Update interactive CLI models**

Modify `cli/models.py`:

```python
class AssetType(str, Enum):
    STOCK = "stock"
    ETF = "etf"
    FUND = "fund"
    AUTO = "auto"
```

Modify `cli/utils.py`:

```python
FUND_ANALYST_ORDER = [
    ("Fund NAV Analyst", "nav"),
    ("Fund Product Analyst", "product"),
    ("Fund Portfolio Analyst", "portfolio"),
    ("Fund Event Analyst", "event"),
]
```

and in `select_analysts`:

```python
    if asset_type == AssetType.ETF.value:
        analyst_order = ETF_ANALYST_ORDER
    elif asset_type == AssetType.FUND.value:
        analyst_order = FUND_ANALYST_ORDER
    else:
        analyst_order = STOCK_ANALYST_ORDER
```

- [ ] **Step 6: Run entry point tests**

Run:

```bash
pytest tests/test_analyze_asset_type.py tests/test_analysis_service.py tests/test_analysis_api_models.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add analyze.py cli/models.py cli/utils.py tradingagents/api/schemas.py tradingagents/services/analysis_service.py tests/test_analyze_asset_type.py tests/test_analysis_service.py tests/test_analysis_api_models.py
git commit -m "feat: add fund entry points"
```

---

### Task 6: Fund Decision Language In Downstream Agents And Reports

**Files:**
- Modify: `tradingagents/agents/managers/research_manager.py`
- Modify: `tradingagents/agents/managers/risk_manager.py`
- Modify: `tradingagents/agents/trader/trader.py`
- Modify: `tradingagents/graph/trading_graph.py`
- Test: `tests/test_fund_decision_language.py`

- [ ] **Step 1: Write failing language tests**

Create `tests/test_fund_decision_language.py`:

```python
import unittest


class FundDecisionLanguageTests(unittest.TestCase):
    def test_fund_report_title_helper(self):
        from tradingagents.graph.trading_graph import _report_titles_for_asset

        titles = _report_titles_for_asset("fund")
        self.assertEqual(titles["report_title"], "基金分析报告")
        self.assertEqual(titles["fundamentals_title"], "基金产品结构分析报告")

    def test_fund_summary_fields_do_not_require_target_price(self):
        from tradingagents.graph.trading_graph import _decision_rows_for_asset

        rows = _decision_rows_for_asset("fund", {"action": "观望", "confidence": "中", "risk_score": "中"})
        rendered = "\n".join(rows)
        self.assertNotIn("目标价", rendered)
        self.assertIn("基金建议", rendered)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run language tests to verify they fail**

Run:

```bash
pytest tests/test_fund_decision_language.py -v
```

Expected: FAIL because helper functions do not exist.

- [ ] **Step 3: Add report helpers**

Modify `tradingagents/graph/trading_graph.py` near imports:

```python
def _report_titles_for_asset(asset_type: str) -> dict:
    if asset_type == "etf":
        return {
            "report_title": "ETF 分析报告",
            "market_title": "ETF 市场分析报告",
            "fundamentals_title": "ETF 产品分析报告",
            "news_title": "ETF 新闻分析报告",
            "sentiment_title": "ETF 资金流与情绪分析报告",
        }
    if asset_type == "fund":
        return {
            "report_title": "基金分析报告",
            "market_title": "基金净值与收益质量分析报告",
            "fundamentals_title": "基金产品结构分析报告",
            "news_title": "基金公告与事件风险分析报告",
            "sentiment_title": "基金持仓与暴露分析报告",
        }
    return {
        "report_title": "股票分析报告",
        "market_title": "市场分析报告",
        "fundamentals_title": "基本面分析报告",
        "news_title": "新闻分析报告",
        "sentiment_title": "社交情绪分析报告",
    }


def _decision_rows_for_asset(asset_type: str, decision: dict) -> list[str]:
    if asset_type == "fund":
        return [
            f"| 基金建议 | {decision.get('action', 'N/A')} |",
            f"| 置信度 | {decision.get('confidence', 'N/A')} |",
            f"| 风险评分 | {decision.get('risk_score', 'N/A')} |",
        ]
    return [
        f"| 操作建议 | {decision.get('action', 'N/A')} |",
        f"| 目标价 | {decision.get('target_price', 'N/A')} |",
        f"| 置信度 | {decision.get('confidence', 'N/A')} |",
        f"| 风险评分 | {decision.get('risk_score', 'N/A')} |",
    ]
```

Replace the inline report title block in `TradingAgentsGraph.propagate()` with:

```python
        titles = _report_titles_for_asset(asset_type)
        report_title = titles["report_title"]
        market_title = titles["market_title"]
        fundamentals_title = titles["fundamentals_title"]
        news_title = titles["news_title"]
        sentiment_title = titles["sentiment_title"]
```

Replace the decision summary rows with:

```python
            f"| 项目 | 结果 |",
            f"|------|------|",
            *_decision_rows_for_asset(asset_type, decision),
```

- [ ] **Step 4: Add fund prompts downstream**

In `research_manager.py`, add this `asset_type == "fund"` branch before the stock branch:

```python
        if asset_type == "fund":
            prompt = f"""作为开放式公募基金投资研究经理，您的职责是评估基金是否适合中长期申购、分批申购、持有、赎回或观望。

请重点关注：
- 基金净值表现是否支持中长期持有，而不是短线交易
- 产品结构、费率、规模、申赎状态是否适合当前投资者
- 持仓暴露与宏观环境是否匹配
- QDII 的汇率、海外市场、NAV 滞后和限购风险
- 债基的利率、信用、久期和流动性风险
- 货基的收益稳定性、流动性和赎回压力

请禁止使用股票买入/卖出、止损价、目标价、ETF二级市场交易等表达。

基金净值报告：{market_research_report}
基金持仓/宏观报告：{sentiment_report}
基金事件报告：{news_report}
基金产品报告：{fundamentals_report}

历史记忆：{past_memory_str}

请输出清晰的中长期基金决策建议。"""
```

In `risk_manager.py`, add this `asset_type == "fund"` branch before the stock branch:

```python
        if asset_type == "fund":
            prompt = f"""作为开放式公募基金风险管理委员会主席，您的目标是基于中长期视角评估交易员的基金计划，并给出最终基金行动建议。

风险审查重点：
1. 产品结构、费率、规模和申赎限制
2. 净值回撤、波动和收益质量
3. 持仓集中度、资产配置和宏观环境错配
4. 基金经理变更或管理能力风险
5. QDII 汇率、海外市场、NAV 滞后和额度风险
6. 债基利率、信用、久期和流动性风险
7. 货基收益稳定性、流动性和赎回压力

禁止输出股票买卖、止损价、目标价或 ETF 二级市场交易建议。最终建议只能使用：申购、分批申购、持有、赎回、观望。

交易员计划：{trader_decision}

基金净值报告：{market_research_report}
基金持仓/宏观报告：{sentiment_report}
基金事件报告：{news_report}
基金产品报告：{fundamentals_report}

历史记忆：{past_memory_str}

请输出最终风险裁决。"""
```

In `trader.py`, add this `asset_type == "fund"` branch before the stock branch:

```python
        if asset_type == "fund":
            prompt = f"""你是开放式公募基金投资执行顾问。请基于研究经理的判断，形成中长期基金操作计划。

输出要求：
- 行动只能是：申购、分批申购、持有、赎回、观望
- 必须说明适合的持有期限或观察周期
- 必须结合宏观环境和基金类型风险
- 不得输出股票买卖、目标价、止损价或 ETF 二级市场交易语言

研究经理判断：
{investment_plan}

请给出基金操作计划。"""
```

- [ ] **Step 5: Run language tests**

Run:

```bash
pytest tests/test_fund_decision_language.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tradingagents/agents/managers/research_manager.py tradingagents/agents/managers/risk_manager.py tradingagents/agents/trader/trader.py tradingagents/graph/trading_graph.py tests/test_fund_decision_language.py
git commit -m "feat: add fund decision language"
```

---

### Task 7: End-To-End Verification And Documentation

**Files:**
- Modify: `README.md`
- Test: existing test suite

- [ ] **Step 1: Add README fund usage**

Add a short section to `README.md`:

```markdown
## Open-Ended Public Fund Analysis

The project supports ordinary open-ended public fund analysis through `asset_type=fund`.

```bash
python analyze.py 008763 -l 3
python analyze.py 008763 --asset-type fund -l 3
```

Fund mode is for subscription, holding, redemption, watchlist, and phased-subscription decisions. It does not produce stock trading, ETF secondary-market trading, stop-loss, or target-price recommendations.
```
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
pytest tests/test_fund_registry.py tests/test_fund_research_service.py tests/test_fund_tools_and_graph.py tests/test_fund_decision_language.py tests/test_analyze_asset_type.py tests/test_analysis_service.py tests/test_analysis_api_models.py -v
```

Expected: PASS.

- [ ] **Step 3: Run full tests**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 4: Verify CLI help includes fund**

Run:

```bash
python analyze.py --help
```

Expected: help output includes `fund` in `--asset-type` choices and includes an example for `008763`.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add fund analysis usage"
```

---

## Self-Review Notes

- Spec coverage: registry, auto detection, Tushare-first fallback, research packages, fund analysts, graph integration, CLI/API/Python entry points, fund decision language, report output, and tests are covered.
- Scope check: LOF, closed-end funds, REITs, and exchange-traded fund analysis remain out of scope.
- Type consistency: The plan uses `fund_type`, `FundDataQuality`, `FundAdmission`, `FundResearchPackage`, `selected_fund_analysts`, `fund_*_report`, and analyst ids `nav`, `product`, `portfolio`, `event` consistently.
