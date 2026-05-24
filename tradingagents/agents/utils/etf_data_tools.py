from datetime import date
from langchain_core.tools import tool
from typing import Annotated

from tradingagents.dataflows.etf_research_service import (
    build_event_package,
    build_exposure_package,
    build_flow_package,
    build_market_package,
    build_product_package,
    format_research_package,
)
from tradingagents.dataflows.interface import route_to_vendor


def _curr_date_or_today(curr_date: str | None) -> str:
    return curr_date or date.today().strftime("%Y-%m-%d")


def _format_error(symbol: str, exc: Exception) -> str:
    return f"# ETF Data Error for {symbol}\n\nStatus: unavailable\nWarning: {exc}"


def _format_package(symbol: str, builder, curr_date: str | None) -> str:
    try:
        return format_research_package(builder(symbol, _curr_date_or_today(curr_date)))
    except Exception as exc:
        return _format_error(symbol, exc)


def _format_discount_premium(value) -> str:
    try:
        return f"{float(value):.4%}"
    except (TypeError, ValueError):
        return str(value)


def _contains_any_key(value, needles: tuple[str, ...]) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if any(needle in str(key).lower() for needle in needles):
                return True
            if _contains_any_key(item, needles):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_any_key(item, needles) for item in value)
    return False


@tool
def get_etf_price_data(
    symbol: Annotated[str, "A-share ETF code"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Retrieve ETF OHLCV and trading data."""
    return _format_package(symbol, build_market_package, end_date)


@tool
def get_etf_indicators(
    symbol: Annotated[str, "A-share ETF code"],
    indicator: Annotated[str, "technical indicator name"],
    curr_date: Annotated[str, "Current trading date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of look-back days"] = 30,
) -> str:
    """Retrieve ETF technical indicators."""
    return route_to_vendor(
        "get_etf_indicators",
        symbol,
        indicator,
        curr_date,
        look_back_days,
        asset_type="etf",
    )


@tool
def get_etf_profile(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve ETF product profile, NAV, and basic metadata."""
    return _format_package(ticker, build_product_package, curr_date)


@tool
def get_etf_holdings(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve ETF holdings / exposure data."""
    return _format_package(ticker, build_exposure_package, curr_date)


@tool
def get_etf_fund_flow(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve ETF fund-flow proxy data."""
    return _format_package(ticker, build_flow_package, curr_date)


@tool
def get_etf_discount_premium(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve ETF discount / premium information."""
    try:
        package = build_product_package(ticker, _curr_date_or_today(curr_date))
        formatted = format_research_package(package)
        discount_premium = package.metrics.get("discount_premium")
        if discount_premium is None:
            line = "- Discount/Premium: unavailable from aligned close and NAV in product package."
        else:
            line = f"- Discount/Premium: {_format_discount_premium(discount_premium)}"
        date_line = ""
        aligned_date = package.raw_summary.get("discount_premium_date")
        if aligned_date:
            date_line = f"\n- Aligned Date: {aligned_date}"
        return f"{formatted}\n\n## Discount / Premium\n{line}{date_line}"
    except Exception as exc:
        return _format_error(ticker, exc)


@tool
def get_etf_tracking_info(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve ETF tracking error / benchmark information."""
    try:
        package = build_product_package(ticker, _curr_date_or_today(curr_date))
        formatted = format_research_package(package)
        has_tracking_context = _contains_any_key(
            {"metrics": package.metrics, "raw_summary": package.raw_summary},
            ("tracking", "benchmark", "index"),
        )
        if has_tracking_context:
            note = (
                "- Tracking-specific time series is unavailable; use benchmark/index "
                "context present in metrics or raw_summary."
            )
        else:
            note = "- Tracking-specific time series is unavailable in the current product package."
        return f"{formatted}\n\n## Tracking Note\n{note}"
    except Exception as exc:
        return _format_error(ticker, exc)


@tool
def get_etf_news(
    ticker: Annotated[str, "A-share ETF code"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Retrieve ETF-specific or ETF-relevant news."""
    return _format_package(ticker, build_event_package, end_date)
