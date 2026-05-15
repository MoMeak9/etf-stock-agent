from langchain_core.tools import tool
from typing import Annotated

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_etf_price_data(
    symbol: Annotated[str, "A-share ETF code"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Retrieve ETF OHLCV and trading data."""
    return route_to_vendor(
        "get_etf_price_data",
        symbol,
        start_date,
        end_date,
        asset_type="etf",
    )


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
    return route_to_vendor(
        "get_etf_profile",
        ticker,
        curr_date,
        asset_type="etf",
    )


@tool
def get_etf_holdings(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve ETF holdings / exposure data."""
    return route_to_vendor(
        "get_etf_holdings",
        ticker,
        curr_date,
        asset_type="etf",
    )


@tool
def get_etf_fund_flow(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve ETF fund-flow proxy data."""
    return route_to_vendor(
        "get_etf_fund_flow",
        ticker,
        curr_date,
        asset_type="etf",
    )


@tool
def get_etf_discount_premium(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve ETF discount / premium information."""
    return route_to_vendor(
        "get_etf_discount_premium",
        ticker,
        curr_date,
        asset_type="etf",
    )


@tool
def get_etf_tracking_info(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"] = None,
) -> str:
    """Retrieve ETF tracking error / benchmark information."""
    return route_to_vendor(
        "get_etf_tracking_info",
        ticker,
        curr_date,
        asset_type="etf",
    )


@tool
def get_etf_news(
    ticker: Annotated[str, "A-share ETF code"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Retrieve ETF-specific or ETF-relevant news."""
    return route_to_vendor(
        "get_etf_news",
        ticker,
        start_date,
        end_date,
        asset_type="etf",
    )
