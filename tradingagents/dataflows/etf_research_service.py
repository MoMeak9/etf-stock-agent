"""Research package builders for China mainland ETF analysis."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from tradingagents.dataflows.etf_metrics import (
    compute_concentration,
    compute_discount_premium,
    compute_liquidity,
    compute_share_change,
    compute_volatility_and_drawdown,
)
from tradingagents.dataflows.etf_models import DataQuality, ETFAdmission, ETFResearchPackage
from tradingagents.dataflows.etf_registry import admit_etf

DATE_COLUMNS = ("trade_date", "date", "Date", "end_date", "nav_date", "ann_date", "日期", "净值日期")


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
        warnings.append(f"tushare returned empty data" if not _has_data(data) else f"tushare missing required fields: {validation_label}")
    except Exception as exc:
        warnings.append(f"tushare failed: {exc}")
    if fallback is not None:
        try:
            data = fallback()
            if _has_data(data) and (validator is None or validator(data)):
                return data, "akshare", warnings
            warnings.append(f"akshare returned empty data" if not _has_data(data) else f"akshare missing required fields: {validation_label}")
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


def _filter_latest_period(df: Any, latest_period: str):
    if not _has_data(df) or not latest_period:
        return df
    date_col = _pick_column(df, DATE_COLUMNS)
    if not date_col:
        return df
    dates = _parse_dates(df[date_col])
    return df.loc[dates == pd.Timestamp(latest_period)]


def _numeric_values(values: pd.Series) -> pd.Series:
    return pd.to_numeric(
        values.astype("string").str.replace(",", "", regex=False).str.replace("%", "", regex=False),
        errors="coerce",
    )


def _has_numeric_values(df: Any, candidates: tuple[str, ...], positive: bool = False) -> bool:
    column = _pick_column(df, candidates)
    if not column:
        return False
    values = _numeric_values(df[column]).dropna()
    if positive:
        values = values[values > 0]
    return not values.empty


def _with_numeric_column(df: Any, column: str):
    if not _has_data(df) or column not in df.columns:
        return df
    normalized = df.copy()
    normalized[column] = _numeric_values(normalized[column])
    return normalized


def _latest_value(df: Any, value_candidates: tuple[str, ...], date_candidates: tuple[str, ...] = DATE_COLUMNS):
    if not _has_data(df):
        return None
    value_col = _pick_column(df, value_candidates)
    if not value_col:
        return None
    date_col = _pick_column(df, date_candidates)
    ordered = df
    if date_col:
        dates = _parse_dates(df[date_col])
        if not dates.isna().all():
            ordered = df.assign(_sort_date=dates).dropna(subset=["_sort_date"]).sort_values("_sort_date")
    values = _numeric_values(ordered[value_col]).dropna()
    if values.empty:
        return None
    return float(values.iloc[-1])


def _aligned_latest_values(
    left: Any,
    right: Any,
    left_value_candidates: tuple[str, ...],
    right_value_candidates: tuple[str, ...],
):
    left_date_col = _pick_column(left, DATE_COLUMNS)
    right_date_col = _pick_column(right, DATE_COLUMNS)
    left_value_col = _pick_column(left, left_value_candidates)
    right_value_col = _pick_column(right, right_value_candidates)
    if not all((left_date_col, right_date_col, left_value_col, right_value_col)):
        return None, None, ""

    left_frame = pd.DataFrame(
        {
            "date": _parse_dates(left[left_date_col]),
            "left": _numeric_values(left[left_value_col]),
        }
    ).dropna()
    right_frame = pd.DataFrame(
        {
            "date": _parse_dates(right[right_date_col]),
            "right": _numeric_values(right[right_value_col]),
        }
    ).dropna()
    merged = left_frame.merge(right_frame, on="date", how="inner").sort_values("date")
    if merged.empty:
        return _latest_value(left, left_value_candidates), _latest_value(right, right_value_candidates), ""
    latest = merged.iloc[-1]
    return float(latest["left"]), float(latest["right"]), latest["date"].strftime("%Y-%m-%d")


def _status_from(missing_fields: list[str], warnings: list[str]) -> str:
    if missing_fields or warnings:
        return "partial"
    return "ok"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value))


def _clean(value):
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_clean(v) for v in value if v is not None]
    return value


def _frame_summary(df: Any, source: str = "tushare", date_col: str | None = None):
    if not _has_data(df):
        return {"rows": 0, "columns": [], "source": "unavailable", "attempted_sources": [source]}
    return {
        "rows": int(len(df)),
        "columns": [str(column) for column in getattr(df, "columns", [])],
        "source": source,
        "latest_date": _latest_date(df, date_col) if date_col else "",
    }


def _frame_tail_records(
    df: Any,
    columns: tuple[str, ...],
    rows: int = 10,
    date_col: str | None = None,
) -> list[dict[str, Any]]:
    if not _has_data(df):
        return []
    selected = [column for column in columns if column in df.columns]
    if not selected:
        return []
    ordered = df
    if date_col and date_col in df.columns:
        dates = _parse_dates(df[date_col])
        if not dates.isna().all():
            ordered = df.assign(_sort_date=dates).dropna(subset=["_sort_date"]).sort_values("_sort_date")
    return ordered[selected].tail(rows).to_dict(orient="records")


def _blocked_package(symbol: str, package_type: str, admission: ETFAdmission, curr_date: str):
    quality = DataQuality(
        status="blocked",
        as_of_date=curr_date,
        warnings=admission.quality.warnings,
        missing_fields=admission.quality.missing_fields,
    )
    return ETFResearchPackage(symbol=symbol, package_type=package_type, status="blocked", quality=quality)


def _profile_value(profile: dict[str, Any], candidates: tuple[str, ...]):
    lowered = {str(key).lower(): value for key, value in profile.items()}
    for candidate in candidates:
        if candidate in profile:
            return profile[candidate]
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def _is_qdii_admission(admission: ETFAdmission) -> bool:
    return str(admission.etf_type).lower() == "qdii"


def _qdii_context(admission: ETFAdmission) -> dict[str, Any]:
    if not _is_qdii_admission(admission):
        return {}
    return _clean(
        {
            "qdii_profile": True,
            "cross_border": True,
            "index_code": _profile_value(admission.profile, ("index_code", "指数代码")),
            "index_name": _profile_value(admission.profile, ("index_name", "指数名称")),
            "currency_fx_risk": "QDII ETF NAV and secondary-market price may be affected by RMB/foreign-currency moves.",
            "nav_lag_risk": "Overseas-market close times and NAV publication can lag A-share trading hours.",
            "holiday_mismatch_risk": "A-share and overseas-market holidays may differ, affecting liquidity and price discovery.",
            "premium_discount_risk": "Cross-border creation/redemption constraints can make ETF premium or discount persist.",
        }
    )


def _append_qdii_warnings(warnings: list[str], admission: ETFAdmission) -> list[str]:
    if not _is_qdii_admission(admission):
        return warnings
    return _dedupe(
        warnings
        + [
            "QDII ETF cross-border risks: FX, NAV lag, holiday mismatch, and persistent premium/discount should be assessed separately.",
        ]
    )


def build_market_package(symbol: str, curr_date: str) -> ETFResearchPackage:
    from tradingagents.dataflows import akshare_etf, tushare_etf

    admission = admit_etf(symbol)
    start = _date_lookback(curr_date, 220)
    daily, fallback, warnings = _call_with_fallback(
        lambda: tushare_etf.fetch_etf_daily(symbol, start, curr_date),
        lambda: akshare_etf.fetch_etf_daily(symbol, start, curr_date),
        validator=lambda frame: _has_numeric_values(frame, ("amount", "Amount", "成交额"), positive=True)
        and _has_numeric_values(frame, ("close", "Close", "收盘", "收盘价"), positive=True),
        validation_label="daily amount and close",
    )
    if not _has_data(daily):
        quality = DataQuality(status="unavailable", fallback_source=fallback, warnings=warnings, missing_fields=["daily"])
        return ETFResearchPackage(symbol=symbol, package_type="market", status="unavailable", quality=quality)
    date_col = _pick_column(daily, DATE_COLUMNS)
    amount_col = _pick_column(daily, ("amount", "Amount", "成交额"))
    close_col = _pick_column(daily, ("close", "Close", "收盘", "收盘价"))
    metrics: dict[str, Any] = {}
    missing_fields: list[str] = []
    if amount_col:
        amount_multiplier = 1000 if amount_col.lower() == "amount" and fallback == "none" else 1
        metrics.update(
            compute_liquidity(
                _with_numeric_column(daily, amount_col),
                amount_col=amount_col,
                date_col=date_col,
                amount_multiplier=amount_multiplier,
            )
        )
    else:
        missing_fields.append("amount")
    if close_col:
        metrics.update(compute_volatility_and_drawdown(_with_numeric_column(daily, close_col), close_col=close_col, date_col=date_col))
    else:
        missing_fields.append("close")
    warnings = _append_qdii_warnings(warnings, admission)
    status = _status_from(missing_fields, warnings)
    quality = DataQuality(status=status, fallback_source=fallback, as_of_date=_latest_date(daily, date_col), warnings=warnings, missing_fields=missing_fields)
    raw_columns = tuple(
        column
        for column in (date_col, "open", "Open", "high", "High", "low", "Low", "close", "Close", amount_col, "vol", "Volume")
        if column
    )
    return ETFResearchPackage(
        symbol=symbol,
        package_type="market",
        status=status,
        quality=quality,
        metrics=_clean(metrics),
        raw_summary=_clean(
            {
                "qdii_context": _qdii_context(admission),
                "daily": _frame_summary(daily, source="tushare" if fallback == "none" else fallback, date_col=date_col),
                "recent_daily_sample": _frame_tail_records(daily, raw_columns, rows=20, date_col=date_col),
            }
        ),
    )


def build_product_package(symbol: str, curr_date: str) -> ETFResearchPackage:
    from tradingagents.dataflows import akshare_etf, tushare_etf

    admission = admit_etf(symbol)
    if not admission.is_supported:
        return _blocked_package(symbol, "product", admission, curr_date)
    start_nav = _date_lookback(curr_date, 90)
    start_daily = _date_lookback(curr_date, 30)
    basic, basic_fallback, basic_warnings = _call_with_fallback(
        lambda: tushare_etf.fetch_etf_basic(symbol),
        lambda: akshare_etf.fetch_etf_basic(symbol),
        validator=lambda frame: _has_data(frame),
        validation_label="basic profile",
    )
    nav, nav_fallback, nav_warnings = _call_with_fallback(
        lambda: tushare_etf.fetch_etf_nav(symbol, start_nav, curr_date),
        lambda: akshare_etf.fetch_etf_nav(symbol),
        validator=lambda frame: _has_numeric_values(frame, ("unit_nav", "nav", "adj_nav", "单位净值", "累计单位净值"), positive=True),
        validation_label="NAV value",
    )
    daily, daily_fallback, daily_warnings = _call_with_fallback(
        lambda: tushare_etf.fetch_etf_daily(symbol, start_daily, curr_date),
        lambda: akshare_etf.fetch_etf_daily(symbol, start_daily, curr_date),
        validator=lambda frame: _has_numeric_values(frame, ("close", "Close", "收盘", "收盘价"), positive=True),
        validation_label="daily close",
    )
    warnings = _append_qdii_warnings(_dedupe(list(admission.quality.warnings) + basic_warnings + nav_warnings + daily_warnings), admission)
    missing_fields = list(admission.quality.missing_fields)
    close, nav_value, aligned_date = _aligned_latest_values(
        daily,
        nav,
        ("close", "Close", "收盘", "收盘价"),
        ("unit_nav", "nav", "adj_nav", "单位净值", "累计单位净值"),
    )
    discount_premium = compute_discount_premium(close, nav_value)
    metrics = {}
    if discount_premium is None:
        missing_fields.extend(["latest_close", "latest_nav", "discount_premium"])
    else:
        metrics["discount_premium"] = discount_premium
    if not aligned_date and discount_premium is not None:
        warnings.append("discount_premium_date_mismatch")
    status = _status_from(missing_fields, warnings)
    quality = DataQuality(status=status, fallback_source=_merge_fallbacks(basic_fallback, nav_fallback, daily_fallback), as_of_date=aligned_date or _latest_date(nav, _pick_column(nav, DATE_COLUMNS)), warnings=warnings, missing_fields=_dedupe(missing_fields))
    return ETFResearchPackage(
        symbol=admission.symbol,
        package_type="product",
        status=status,
        quality=quality,
        metrics=_clean(metrics),
        raw_summary=_clean(
            {
                "admission": admission.profile,
                "qdii_context": _qdii_context(admission),
                "basic": _frame_summary(basic, source=_source_from_fallback(basic_fallback)),
                "nav": _frame_summary(nav, source=_source_from_fallback(nav_fallback), date_col=_pick_column(nav, DATE_COLUMNS)),
                "daily": _frame_summary(daily, source=_source_from_fallback(daily_fallback), date_col=_pick_column(daily, DATE_COLUMNS)),
                "latest_close": close,
                "latest_nav": nav_value,
                "discount_premium_date": aligned_date,
            }
        ),
    )


def build_exposure_package(symbol: str, curr_date: str) -> ETFResearchPackage:
    from tradingagents.dataflows import akshare_etf, tushare_etf

    admission = admit_etf(symbol)
    if not admission.is_supported:
        return _blocked_package(symbol, "exposure", admission, curr_date)
    holdings, holdings_fallback, holding_warnings = _call_with_fallback(
        lambda: tushare_etf.fetch_etf_portfolio(symbol),
        lambda: akshare_etf.fetch_etf_portfolio(symbol, curr_date[:4]),
        validator=lambda frame: _has_numeric_values(frame, ("mkv", "stk_mkv_ratio", "weight", "占净值比例"), positive=True),
        validation_label="holding weight",
    )
    warnings = _append_qdii_warnings(_dedupe(list(admission.quality.warnings) + holding_warnings), admission)
    missing_fields = list(admission.quality.missing_fields)
    holdings_date_col = _pick_column(holdings, ("end_date", "报告期", "截止日期", "日期"))
    latest_period = _latest_date(holdings, holdings_date_col)
    holdings_latest = _filter_latest_period(holdings, latest_period)
    weight_col = _pick_column(holdings_latest, ("mkv", "stk_mkv_ratio", "weight", "占净值比例"))
    metrics = {}
    if weight_col:
        metrics.update(compute_concentration(_with_numeric_column(holdings_latest, weight_col), weight_col=weight_col))
    elif _has_data(holdings):
        missing_fields.append("holding_weight")
    if not _has_data(holdings):
        missing_fields.append("holdings")
        if _is_qdii_admission(admission):
            warnings.append("QDII ETF holdings unavailable from current vendor path; exposure analysis is degraded, not blocked.")

    index_code = _profile_value(admission.profile, ("index_code", "指数代码"))
    index_weights = None
    if index_code:
        trade_date = curr_date.replace("-", "")
        index_weights, _, index_warnings = _call_with_fallback(lambda: tushare_etf.fetch_index_weight(str(index_code), trade_date=trade_date))
        if not _has_data(index_weights):
            latest_index_weights, _, latest_warnings = _call_with_fallback(lambda: tushare_etf.fetch_index_weight(str(index_code)))
            if _has_data(latest_index_weights):
                index_weights = latest_index_weights
                warnings.append("index_weight_fallback_latest")
            else:
                warnings.extend(f"index_weight {warning}" for warning in index_warnings + latest_warnings)
    else:
        missing_fields.append("index_code")
    status = "unavailable" if not _has_data(holdings) else _status_from(missing_fields, warnings)
    quality = DataQuality(status=status, as_of_date=latest_period, warnings=_dedupe(warnings), missing_fields=_dedupe(missing_fields))
    return ETFResearchPackage(
        symbol=admission.symbol,
        package_type="exposure",
        status=status,
        quality=quality,
        metrics=_clean(metrics),
        raw_summary=_clean(
            {
                "admission": admission.profile,
                "qdii_context": _qdii_context(admission),
                "holdings": _frame_summary(holdings, source=_source_from_fallback(holdings_fallback), date_col=holdings_date_col),
                "holding_weight_column": weight_col or "N/A",
                "latest_period": latest_period or "N/A",
                "index_code": index_code or "N/A",
                "index_weights": _frame_summary(index_weights, source="tushare", date_col=_pick_column(index_weights, DATE_COLUMNS)),
                "holdings_lag_note": "Holdings are periodic disclosures and may lag current ETF basket exposure.",
            }
        ),
    )


def build_flow_package(symbol: str, curr_date: str) -> ETFResearchPackage:
    from tradingagents.dataflows import akshare_etf, tushare_etf

    admission = admit_etf(symbol)
    if not admission.is_supported:
        return _blocked_package(symbol, "flow", admission, curr_date)
    start = _date_lookback(curr_date, 120)
    flow, fallback, flow_warnings = _call_with_fallback(
        lambda: tushare_etf.fetch_etf_share_size(symbol, start, curr_date),
        lambda: akshare_etf.fetch_etf_nav(symbol),
        validator=lambda frame: _has_numeric_values(frame, ("share", "fd_share", "total_share", "基金份额", "净资产"), positive=True),
        validation_label="share or size",
    )
    warnings = _append_qdii_warnings(_dedupe(list(admission.quality.warnings) + flow_warnings), admission)
    missing_fields = list(admission.quality.missing_fields)
    share_col = _pick_column(flow, ("share", "fd_share", "total_share", "基金份额", "净资产"))
    date_col = _pick_column(flow, DATE_COLUMNS)
    metrics = {}
    if share_col:
        metrics.update(compute_share_change(_with_numeric_column(flow, share_col), share_col=share_col, date_col=date_col))
        metrics["latest_share_or_proxy"] = _latest_value(flow, (share_col,), DATE_COLUMNS)
    elif _has_data(flow):
        missing_fields.append("share_or_proxy_size")
    if not _has_data(flow):
        missing_fields.append("share_size")
    status = "unavailable" if not _has_data(flow) else _status_from(missing_fields, warnings)
    quality = DataQuality(status=status, fallback_source=fallback, as_of_date=_latest_date(flow, date_col), warnings=warnings, missing_fields=_dedupe(missing_fields))
    return ETFResearchPackage(
        symbol=admission.symbol,
        package_type="flow",
        status=status,
        quality=quality,
        metrics=_clean(metrics),
        raw_summary=_clean(
            {
                "qdii_context": _qdii_context(admission),
                "flow": _frame_summary(flow, source=_source_from_fallback(fallback), date_col=date_col),
                "share_column": share_col or "N/A",
            }
        ),
    )


def build_event_package(symbol: str, curr_date: str) -> ETFResearchPackage:
    admission = admit_etf(symbol)
    if not admission.is_supported:
        return _blocked_package(symbol, "event", admission, curr_date)
    warnings = _append_qdii_warnings(_dedupe(list(admission.quality.warnings) + ["ETF-specific structured event feed unavailable; no events invented"]), admission)
    missing_fields = _dedupe(list(admission.quality.missing_fields) + ["etf_event_feed", "fund_announcements"])
    quality = DataQuality(status="partial", as_of_date=curr_date, warnings=warnings, missing_fields=missing_fields)
    return ETFResearchPackage(
        symbol=admission.symbol,
        package_type="event",
        status="partial",
        quality=quality,
        raw_summary=_clean(
            {
                "admission": admission.profile,
                "qdii_context": _qdii_context(admission),
                "index_code": _profile_value(admission.profile, ("index_code", "指数代码")) or "N/A",
            }
        ),
    )


def _source_from_fallback(fallback: str) -> str:
    return "tushare" if fallback == "none" else fallback


def _merge_fallbacks(*fallbacks: str) -> str:
    used = [fallback for fallback in fallbacks if fallback and fallback != "none"]
    return ",".join(dict.fromkeys(used)) if used else "none"


def format_research_package(package: ETFResearchPackage) -> str:
    lines = [
        f"# ETF {package.package_type.title()} Research Package for {package.symbol}",
        "",
        f"- Status: {package.status}",
        f"- Quality Status: {package.quality.status}",
        f"- Primary Source: {package.quality.primary_source}",
        f"- Fallback Source: {package.quality.fallback_source}",
        f"- As Of Date: {package.quality.as_of_date or 'N/A'}",
    ]
    if package.quality.warnings:
        lines.append("- Warnings: " + "; ".join(str(w) for w in package.quality.warnings if w))
    if package.quality.missing_fields:
        lines.append("- Missing Fields: " + ", ".join(str(field) for field in package.quality.missing_fields if field))
    if package.metrics:
        lines.extend(["", "## Derived Metrics"])
        for key, value in package.metrics.items():
            lines.append(f"- {key}: {value}")
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
