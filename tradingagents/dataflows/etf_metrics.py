"""Derived metric helpers for ETF research packages."""

import math

import pandas as pd


def to_numeric_series(series):
    return pd.to_numeric(series, errors="coerce")


def _finite_float(value):
    try:
        number = float(value) if value is not None else math.nan
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _float_or_none(value):
    number = _finite_float(value)
    return float(number) if number is not None else None


def _parse_metric_dates(values):
    cleaned = values.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    compact_mask = cleaned.str.fullmatch(r"\d{8}", na=False)
    dates = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    if compact_mask.any():
        dates.loc[compact_mask] = pd.to_datetime(
            cleaned.loc[compact_mask],
            format="%Y%m%d",
            errors="coerce",
        )
    generic_mask = ~compact_mask
    if generic_mask.any():
        dates.loc[generic_mask] = pd.to_datetime(cleaned.loc[generic_mask], errors="coerce")
    return dates


def _sort_by_date(df: pd.DataFrame, date_col=None):
    ordered = df.copy()
    if not date_col or date_col not in ordered.columns:
        return ordered
    dates = _parse_metric_dates(ordered[date_col])
    if dates.isna().all():
        return ordered
    return (
        ordered.assign(_metric_sort_date=dates)
        .dropna(subset=["_metric_sort_date"])
        .sort_values("_metric_sort_date", kind="mergesort")
        .drop(columns="_metric_sort_date")
    )


def compute_discount_premium(close, nav):
    close_value = _finite_float(close)
    nav_value = _finite_float(nav)
    if close_value is None or nav_value is None or nav_value == 0:
        return None
    return (close_value - nav_value) / nav_value


def compute_share_change(df: pd.DataFrame, periods=(5, 20, 60), share_col="share", date_col=None):
    if df is None or df.empty or share_col not in df.columns:
        return {}
    ordered = _sort_by_date(df, date_col)
    ordered[share_col] = to_numeric_series(ordered[share_col])
    ordered = ordered.dropna(subset=[share_col])
    if ordered.empty:
        return {}
    latest = ordered[share_col].iloc[-1]
    out = {}
    for period in periods:
        if len(ordered) <= period:
            continue
        base = ordered[share_col].iloc[-period - 1]
        if base == 0 or not math.isfinite(float(base)):
            continue
        out[f"share_change_{period}d"] = float((latest - base) / base)
    return out


def compute_liquidity(df: pd.DataFrame, amount_col="amount", date_col=None, amount_multiplier=1.0):
    if df is None or df.empty or amount_col not in df.columns:
        return {}
    ordered = _sort_by_date(df, date_col)
    amount = to_numeric_series(ordered[amount_col]).dropna()
    if amount.empty:
        return {}
    amount_cny = amount * amount_multiplier
    latest = float(amount_cny.iloc[-1])
    avg20 = float(amount_cny.tail(20).mean())
    latest_vs_avg20 = (latest - avg20) / avg20 if avg20 else None
    return {
        "latest_amount_cny": latest,
        "avg_amount_20d_cny": avg20,
        "latest_amount_vs_avg20": latest_vs_avg20,
        "latest_amount_above_avg20": bool(latest > avg20),
        "low_liquidity": bool(avg20 < 20_000_000),
    }


def compute_volatility_and_drawdown(df: pd.DataFrame, close_col="close", date_col=None):
    if df is None or df.empty or close_col not in df.columns:
        return {}
    ordered = _sort_by_date(df, date_col)
    close = to_numeric_series(ordered[close_col]).dropna()
    close = close[close > 0]
    if len(close) < 2:
        return {}
    returns = close.pct_change().dropna()
    rolling_max = close.cummax()
    drawdown = close / rolling_max - 1
    return {
        "volatility_20d": _float_or_none(returns.tail(20).std() * math.sqrt(252))
        if len(returns) >= 20
        else None,
        "volatility_60d": _float_or_none(returns.tail(60).std() * math.sqrt(252))
        if len(returns) >= 60
        else None,
        "max_drawdown": _float_or_none(drawdown.min()),
    }


def compute_concentration(df: pd.DataFrame, weight_col="mkv"):
    if df is None or df.empty or weight_col not in df.columns:
        return {}
    weights = to_numeric_series(df[weight_col]).dropna().sort_values(ascending=False)
    weights = weights[weights > 0]
    if weights.empty:
        return {}
    total = weights.sum()
    if total == 0 or not math.isfinite(float(total)):
        return {}
    normalized = weights / total
    return {
        "top1_weight": float(normalized.head(1).sum()),
        "top3_weight": float(normalized.head(3).sum()),
        "top5_weight": float(normalized.head(5).sum()),
        "top10_weight": float(normalized.head(10).sum()),
    }
