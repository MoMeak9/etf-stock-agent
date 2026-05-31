"""Research package builders for open-ended public fund analysis."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from tradingagents.dataflows.fund_models import FundAdmission, FundDataQuality, FundResearchPackage
from tradingagents.dataflows.fund_registry import admit_fund

DATE_COLUMNS = ("nav_date", "trade_date", "date", "Date", "end_date", "ann_date", "日期", "净值日期")
NAV_COLUMNS = ("unit_nav", "nav", "fund_nav", "adj_nav", "单位净值", "累计单位净值")


def _date_lookback(curr_date: str, days: int) -> str:
    return (pd.Timestamp(curr_date) - pd.DateOffset(days=days)).strftime("%Y-%m-%d")


def _has_data(data: Any) -> bool:
    if data is None:
        return False
    empty = getattr(data, "empty", None)
    if empty is not None:
        return not bool(empty)
    try:
        return len(data) > 0
    except TypeError:
        return True


def _call_with_fallback(
    primary: Callable[[], Any],
    fallback: Callable[[], Any] | None = None,
    validator: Callable[[Any], bool] | None = None,
    validation_label: str = "required fields",
):
    warnings: list[str] = []
    try:
        data = primary()
        if _has_data(data) and (validator is None or validator(data)):
            return data, "none", warnings
        warnings.append("tushare returned empty data" if not _has_data(data) else f"tushare missing required fields: {validation_label}")
    except Exception as exc:
        warnings.append(f"tushare failed: {exc}")

    if fallback is not None:
        try:
            data = fallback()
            if _has_data(data) and (validator is None or validator(data)):
                return data, "akshare", warnings
            warnings.append("akshare returned empty data" if not _has_data(data) else f"akshare missing required fields: {validation_label}")
        except Exception as exc:
            warnings.append(f"akshare failed: {exc}")
    return None, "akshare" if fallback is not None else "none", warnings


def _pick_column(df: Any, candidates: tuple[str, ...]) -> str | None:
    if not _has_data(df) or not hasattr(df, "columns"):
        return None
    columns = list(df.columns)
    lowered = {str(column).lower(): str(column) for column in columns}
    for candidate in candidates:
        if candidate in columns:
            return candidate
        matched = lowered.get(candidate.lower())
        if matched:
            return matched
    return None


def _numeric(values: pd.Series) -> pd.Series:
    return pd.to_numeric(
        values.astype("string").str.replace(",", "", regex=False).str.replace("%", "", regex=False),
        errors="coerce",
    )


def _parse_dates(values: pd.Series) -> pd.Series:
    cleaned = values.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    compact = cleaned.str.fullmatch(r"\d{8}", na=False)
    dates = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    if compact.any():
        dates.loc[compact] = pd.to_datetime(cleaned.loc[compact], format="%Y%m%d", errors="coerce")
    if (~compact).any():
        dates.loc[~compact] = pd.to_datetime(cleaned.loc[~compact], errors="coerce")
    return dates


def _latest_date(df: Any, date_col: str | None) -> str:
    if not _has_data(df) or not date_col or date_col not in df.columns:
        return ""
    dates = _parse_dates(df[date_col])
    if dates.isna().all():
        return ""
    return dates.max().strftime("%Y-%m-%d")


def _status(missing_fields: list[str], warnings: list[str]) -> str:
    if missing_fields or warnings:
        return "partial"
    return "ok"


def _frame_summary(df: Any, source: str = "tushare", date_col: str | None = None) -> dict[str, Any]:
    if not _has_data(df):
        return {"rows": 0, "columns": [], "source": "unavailable", "attempted_sources": [source]}
    return {
        "rows": int(len(df)),
        "columns": [str(column) for column in getattr(df, "columns", [])],
        "source": source,
        "latest_date": _latest_date(df, date_col) if date_col else "",
    }


def _blocked(symbol: str, package_type: str, admission: FundAdmission, curr_date: str) -> FundResearchPackage:
    quality = FundDataQuality(
        status="blocked",
        primary_source=admission.quality.primary_source,
        fallback_source=admission.quality.fallback_source,
        as_of_date=curr_date,
        warnings=list(admission.quality.warnings),
        missing_fields=list(admission.quality.missing_fields),
    )
    return FundResearchPackage(
        symbol=symbol,
        fund_type=admission.fund_type,
        package_type=package_type,
        status="blocked",
        quality=quality,
    )


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value))


def _source_from_fallback(fallback: str) -> str:
    return "tushare" if fallback == "none" else fallback


def _profile_value(profile: dict[str, Any], candidates: tuple[str, ...]):
    lowered = {str(key).lower(): value for key, value in profile.items()}
    for candidate in candidates:
        if candidate in profile:
            return profile[candidate]
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def _has_numeric_nav(frame: Any) -> bool:
    column = _pick_column(frame, NAV_COLUMNS)
    if not column:
        return False
    values = _numeric(frame[column]).dropna()
    return not values[values > 0].empty


def _nav_metrics(nav: Any, nav_col: str | None, date_col: str | None) -> dict[str, Any]:
    if not _has_data(nav) or not nav_col:
        return {}
    frame = nav.copy()
    frame["_nav_value"] = _numeric(frame[nav_col])
    if date_col and date_col in frame.columns:
        frame["_sort_date"] = _parse_dates(frame[date_col])
        frame = frame.dropna(subset=["_sort_date"]).sort_values("_sort_date", kind="mergesort")
    values = frame["_nav_value"].dropna()
    values = values[values > 0]
    if values.empty:
        return {}
    metrics = {"latest_nav": float(values.iloc[-1])}
    if len(values) >= 2 and float(values.iloc[0]) != 0:
        metrics["period_return"] = float(values.iloc[-1] / values.iloc[0] - 1)
        drawdown = values / values.cummax() - 1
        metrics["max_drawdown"] = float(drawdown.min())
    return metrics


def build_nav_package(symbol: str, curr_date: str) -> FundResearchPackage:
    from tradingagents.dataflows import akshare_fund, tushare_fund

    admission = admit_fund(symbol)
    if not admission.is_supported:
        return _blocked(symbol, "nav", admission, curr_date)

    start = _date_lookback(curr_date, 365)
    nav, fallback, warnings = _call_with_fallback(
        lambda: tushare_fund.fetch_fund_nav(symbol, start, curr_date),
        lambda: akshare_fund.fetch_fund_nav(symbol, start, curr_date),
        validator=_has_numeric_nav,
        validation_label="unit_nav/fund_nav",
    )
    date_col = _pick_column(nav, DATE_COLUMNS)
    nav_col = _pick_column(nav, NAV_COLUMNS)
    missing_fields: list[str] = []
    metrics = _nav_metrics(nav, nav_col, date_col)
    if not _has_data(nav):
        missing_fields.append("nav_history")
    if not nav_col:
        missing_fields.extend(["unit_nav", "fund_nav"])
    if _has_data(nav) and not metrics:
        missing_fields.append("latest_nav")

    status = "unavailable" if not _has_data(nav) else _status(missing_fields, warnings)
    quality = FundDataQuality(
        status=status,
        fallback_source=fallback,
        as_of_date=_latest_date(nav, date_col) or curr_date,
        warnings=warnings,
        missing_fields=_dedupe(missing_fields),
    )
    return FundResearchPackage(
        symbol=admission.symbol,
        fund_type=admission.fund_type,
        package_type="nav",
        status=status,
        quality=quality,
        metrics=metrics,
        raw_summary={
            "admission": admission.profile,
            "nav": _frame_summary(nav, source=_source_from_fallback(fallback), date_col=date_col),
            "nav_column": nav_col or "N/A",
        },
    )


def build_product_package(symbol: str, curr_date: str) -> FundResearchPackage:
    admission = admit_fund(symbol)
    if not admission.is_supported:
        return _blocked(symbol, "product", admission, curr_date)

    profile = admission.profile
    missing_fields = list(admission.quality.missing_fields)
    purchase_status = _profile_value(profile, ("purchase_status", "申购状态", "申购状态说明"))
    redemption_status = _profile_value(profile, ("redemption_status", "赎回状态", "赎回状态说明"))
    if purchase_status is None:
        missing_fields.append("purchase_status")
    if redemption_status is None:
        missing_fields.append("redemption_status")
    warnings = list(admission.quality.warnings)
    status = _status(missing_fields, warnings)
    quality = FundDataQuality(
        status=status,
        primary_source=admission.quality.primary_source,
        fallback_source=admission.quality.fallback_source,
        as_of_date=curr_date,
        warnings=warnings,
        missing_fields=_dedupe(missing_fields),
    )
    return FundResearchPackage(
        symbol=admission.symbol,
        fund_type=admission.fund_type,
        package_type="product",
        status=status,
        quality=quality,
        metrics={"purchase_status": purchase_status, "redemption_status": redemption_status},
        raw_summary={"admission": profile},
    )


def _partial_package(symbol: str, curr_date: str, package_type: str, missing_fields: list[str]) -> FundResearchPackage:
    admission = admit_fund(symbol)
    if not admission.is_supported:
        return _blocked(symbol, package_type, admission, curr_date)
    quality = FundDataQuality(
        status="partial",
        primary_source=admission.quality.primary_source,
        fallback_source=admission.quality.fallback_source,
        as_of_date=curr_date,
        warnings=_dedupe(list(admission.quality.warnings) + [f"{package_type} package is conservative in first fund version"]),
        missing_fields=_dedupe(list(admission.quality.missing_fields) + missing_fields),
    )
    return FundResearchPackage(
        symbol=admission.symbol,
        fund_type=admission.fund_type,
        package_type=package_type,
        status="partial",
        quality=quality,
        raw_summary={"admission": admission.profile},
    )


def build_portfolio_package(symbol: str, curr_date: str) -> FundResearchPackage:
    return _partial_package(symbol, curr_date, "portfolio", ["fund_portfolio", "holding_weight", "report_period"])


def build_manager_package(symbol: str, curr_date: str) -> FundResearchPackage:
    return _partial_package(symbol, curr_date, "manager", ["fund_manager", "manager_tenure"])


def build_event_package(symbol: str, curr_date: str) -> FundResearchPackage:
    return _partial_package(symbol, curr_date, "event", ["fund_announcements", "fund_event_feed"])


def build_performance_package(symbol: str, curr_date: str) -> FundResearchPackage:
    return _partial_package(symbol, curr_date, "performance", ["benchmark_return", "peer_rank", "risk_adjusted_return"])


def fetch_global_macro_news(curr_date: str, look_back_days: int = 30, limit: int = 10):
    from tradingagents.agents.utils.news_data_tools import get_global_news

    return get_global_news(curr_date, look_back_days, limit)


def _macro_focus_for(fund_type: str) -> list[str]:
    focus = ["rates", "inflation", "liquidity"]
    if str(fund_type).lower() == "qdii":
        focus.extend(["fx", "overseas_rates", "cross_border_liquidity"])
    return focus


def build_macro_package(symbol: str, curr_date: str) -> FundResearchPackage:
    admission = admit_fund(symbol)
    if not admission.is_supported:
        return _blocked(symbol, "macro", admission, curr_date)

    global_macro_news = fetch_global_macro_news(curr_date, look_back_days=30, limit=10)
    if isinstance(global_macro_news, dict):
        global_macro_text = "\n".join(str(value) for value in global_macro_news.values() if value)
    else:
        global_macro_text = str(global_macro_news or "")
    missing_fields = list(admission.quality.missing_fields)
    if not global_macro_text.strip():
        missing_fields.append("global_macro_news")
    warnings = list(admission.quality.warnings)
    status = _status(missing_fields, warnings)
    quality = FundDataQuality(
        status=status,
        primary_source=admission.quality.primary_source,
        fallback_source=admission.quality.fallback_source,
        as_of_date=curr_date,
        warnings=warnings,
        missing_fields=_dedupe(missing_fields),
    )
    return FundResearchPackage(
        symbol=admission.symbol,
        fund_type=admission.fund_type,
        package_type="macro",
        status=status,
        quality=quality,
        metrics={
            "macro_focus": _macro_focus_for(admission.fund_type),
            "analysis_horizon": "medium_to_long_term",
        },
        raw_summary={
            "admission": admission.profile,
            "global_macro_news": global_macro_text[:6000],
        },
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
        lines.append("- Warnings: " + "; ".join(str(warning) for warning in package.quality.warnings if warning))
    if package.quality.missing_fields:
        lines.append("- Missing Fields: " + ", ".join(str(field) for field in package.quality.missing_fields if field))
    if package.metrics:
        lines.extend(["", "## Derived Metrics"])
        for key, value in package.metrics.items():
            lines.append(f"- {key}: {_format_value(value)}")
    if package.raw_summary:
        lines.extend(["", "## Raw Summary"])
        for key, value in package.raw_summary.items():
            lines.append(f"- {key}: {_format_value(value)}")
    return "\n".join(lines)


def _format_value(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}={_format_value(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "[" + ", ".join(_format_value(item) for item in value) + "]"
    return str(value)
