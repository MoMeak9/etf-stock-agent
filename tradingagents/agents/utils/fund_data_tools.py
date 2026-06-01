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
def get_fund_nav(
    symbol: Annotated[str, "Open-ended public fund code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve open-ended fund NAV history and derived risk-return metrics."""
    return _format_package(symbol, build_nav_package, curr_date)


@tool
def get_fund_product(
    symbol: Annotated[str, "Open-ended public fund code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve open-ended fund product profile and purchase/redemption metadata."""
    return _format_package(symbol, build_product_package, curr_date)


@tool
def get_fund_portfolio(
    symbol: Annotated[str, "Open-ended public fund code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve open-ended fund portfolio and holdings structure data."""
    return _format_package(symbol, build_portfolio_package, curr_date)


@tool
def get_fund_manager(
    symbol: Annotated[str, "Open-ended public fund code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve open-ended fund manager and tenure data."""
    return _format_package(symbol, build_manager_package, curr_date)


@tool
def get_fund_event(
    symbol: Annotated[str, "Open-ended public fund code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve open-ended fund announcements and product events."""
    return _format_package(symbol, build_event_package, curr_date)


@tool
def get_fund_performance(
    symbol: Annotated[str, "Open-ended public fund code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve open-ended fund benchmark, peer, and risk-adjusted performance data."""
    return _format_package(symbol, build_performance_package, curr_date)


@tool
def get_fund_macro_context(
    symbol: Annotated[str, "Open-ended public fund code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve macro context relevant to an open-ended fund's medium/long-term fit."""
    return _format_package(symbol, build_macro_package, curr_date)
