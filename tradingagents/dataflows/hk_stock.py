"""
Hong Kong stock data source provider.

Provides HK stock data via yfinance with symbol normalization,
rate limiting, retry logic, and inline technical indicator calculations.
Follows the same function-based, CSV-returning pattern as y_finance.py.
"""

import logging
import time
import numpy as np
import pandas as pd
import yfinance as yf

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Annotated

from .config import get_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiting state
# ---------------------------------------------------------------------------
_last_request_time = 0.0
_MIN_REQUEST_INTERVAL = 2.0  # seconds between requests
_MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# Static HK stock name mapping (top ~50 stocks)
# ---------------------------------------------------------------------------
HK_STOCK_NAMES = {
    # Tencent
    "0700.HK": "Tencent Holdings",
    # Telecom
    "0941.HK": "China Mobile",
    "0762.HK": "China Unicom",
    "0728.HK": "China Telecom",
    # Banks
    "0939.HK": "CCB",
    "1398.HK": "ICBC",
    "3988.HK": "Bank of China",
    "0005.HK": "HSBC Holdings",
    "0011.HK": "Hang Seng Bank",
    "2388.HK": "BOC Hong Kong",
    "3328.HK": "Bank of Communications",
    # Insurance
    "1299.HK": "AIA Group",
    "2318.HK": "Ping An Insurance",
    "2628.HK": "China Life Insurance",
    "2601.HK": "CPIC",
    # Oil & Gas
    "0857.HK": "PetroChina",
    "0386.HK": "Sinopec",
    "0883.HK": "CNOOC",
    # Real Estate
    "1109.HK": "China Resources Land",
    "1997.HK": "Wharf REIC",
    "0016.HK": "SHK Properties",
    "0012.HK": "Henderson Land",
    "0017.HK": "New World Development",
    "0688.HK": "China Overseas Land",
    "0001.HK": "CK Hutchison",
    # Tech
    "9988.HK": "Alibaba Group",
    "3690.HK": "Meituan",
    "1024.HK": "Kuaishou Technology",
    "9618.HK": "JD.com",
    "9888.HK": "Baidu",
    "9999.HK": "NetEase",
    "0020.HK": "SenseTime",
    "9868.HK": "XPeng",
    "9866.HK": "NIO",
    # Consumer
    "1876.HK": "Budweiser APAC",
    "0291.HK": "China Resources Beer",
    "2319.HK": "Mengniu Dairy",
    "0027.HK": "Galaxy Entertainment",
    # Pharma / Healthcare
    "1093.HK": "CSPC Pharmaceutical",
    "2269.HK": "WuXi Biologics",
    # Auto
    "2238.HK": "GAC Group",
    "1211.HK": "BYD Company",
    "2015.HK": "Li Auto",
    # Airlines
    "0753.HK": "Air China",
    "0670.HK": "China Eastern Airlines",
    # Power / Utilities
    "0902.HK": "Huaneng Power",
    "0991.HK": "Datang Power",
    "0836.HK": "China Resources Power",
    # Other
    "0388.HK": "HKEX",
    "2382.HK": "Sunny Optical",
    "0669.HK": "Techtronic Industries",
    "0002.HK": "CLP Holdings",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _wait_for_rate_limit():
    """Enforce minimum interval between requests."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def _normalize_hk_symbol(symbol: str) -> str:
    """Normalize a Hong Kong stock symbol to Yahoo Finance format (e.g. 0700.HK).

    Accepted inputs: '700', '0700', '00700', '0700.HK', '00700.HK'
    Output: '0700.HK' (4-digit zero-padded with .HK suffix)
    """
    if not symbol:
        return symbol

    symbol = str(symbol).strip().upper()

    # Strip existing .HK suffix
    if symbol.endswith(".HK"):
        symbol = symbol[:-3]

    # If purely numeric, zero-pad to 4 digits
    if symbol.isdigit():
        clean = symbol.lstrip("0") or "0"
        symbol = clean.zfill(4)

    return f"{symbol}.HK"


def _fetch_with_retry(fetch_fn, description="request"):
    """Execute *fetch_fn* with exponential-backoff retry.

    Returns the result of *fetch_fn()* on success, or raises the last
    exception after *_MAX_RETRIES* failures.
    """
    last_exc = None
    for attempt in range(_MAX_RETRIES):
        try:
            _wait_for_rate_limit()
            return fetch_fn()
        except Exception as exc:
            last_exc = exc
            err_msg = str(exc)
            logger.warning(
                "HK stock %s failed (attempt %d/%d): %s",
                description, attempt + 1, _MAX_RETRIES, err_msg,
            )
            if "Rate limited" in err_msg or "Too Many Requests" in err_msg:
                time.sleep(60)
            else:
                time.sleep(2 ** attempt)
    raise last_exc  # type: ignore[misc]


def _compute_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add MA, RSI, MACD, and Bollinger Bands columns *in-place*.

    Expects columns: Close, High, Low, Volume (standard yfinance names).
    """
    close = df["Close"]

    # Moving averages
    for window in (5, 10, 20, 60):
        df[f"MA{window}"] = close.rolling(window=window, min_periods=1).mean()

    # RSI (14-period)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14, min_periods=1).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD (12/26/9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD_DIF"] = ema12 - ema26
    df["MACD_DEA"] = df["MACD_DIF"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = (df["MACD_DIF"] - df["MACD_DEA"]) * 2

    # Bollinger Bands (20-period, 2 std)
    df["BOLL_Mid"] = close.rolling(window=20, min_periods=1).mean()
    std20 = close.rolling(window=20, min_periods=1).std()
    df["BOLL_Upper"] = df["BOLL_Mid"] + 2 * std20
    df["BOLL_Lower"] = df["BOLL_Mid"] - 2 * std20

    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_stock_data(
    symbol: Annotated[str, "HK stock symbol (e.g. '700', '0700', '0700.HK')"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Fetch HK stock OHLCV data with technical indicators, returned as CSV string."""

    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    yf_symbol = _normalize_hk_symbol(symbol)

    def _fetch():
        ticker = yf.Ticker(yf_symbol)
        return ticker.history(start=start_date, end=end_date)

    try:
        data = _fetch_with_retry(_fetch, description=f"get_stock_data({yf_symbol})")
    except Exception as e:
        return f"Error fetching HK stock data for '{yf_symbol}': {e}"

    if data.empty:
        return (
            f"No data found for HK symbol '{yf_symbol}' "
            f"between {start_date} and {end_date}"
        )

    # Remove timezone from index
    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    # Round price columns
    for col in ("Open", "High", "Low", "Close", "Adj Close"):
        if col in data.columns:
            data[col] = data[col].round(2)

    # Technical indicators
    data = _compute_technical_indicators(data)

    # Round indicator columns
    indicator_cols = [
        "MA5", "MA10", "MA20", "MA60",
        "RSI", "MACD_DIF", "MACD_DEA", "MACD_Hist",
        "BOLL_Mid", "BOLL_Upper", "BOLL_Lower",
    ]
    for col in indicator_cols:
        if col in data.columns:
            data[col] = data[col].round(4)

    csv_string = data.to_csv()

    header = f"# HK Stock data for {yf_symbol} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(data)}\n"
    header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    return header + csv_string


def get_indicators(
    symbol: Annotated[str, "HK stock symbol"],
    indicator_name: Annotated[str, "Technical indicator name (e.g. 'rsi', 'macd', 'boll')"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Fetch a specific technical indicator for an HK stock over a date range."""

    yf_symbol = _normalize_hk_symbol(symbol)

    # Map user-friendly names to computed column names
    indicator_map = {
        "ma5": "MA5",
        "ma10": "MA10",
        "ma20": "MA20",
        "ma60": "MA60",
        "rsi": "RSI",
        "macd": "MACD_DIF",
        "macd_dif": "MACD_DIF",
        "macd_dea": "MACD_DEA",
        "macd_hist": "MACD_Hist",
        "macds": "MACD_DEA",
        "macdh": "MACD_Hist",
        "boll": "BOLL_Mid",
        "boll_mid": "BOLL_Mid",
        "boll_ub": "BOLL_Upper",
        "boll_upper": "BOLL_Upper",
        "boll_lb": "BOLL_Lower",
        "boll_lower": "BOLL_Lower",
    }

    col_name = indicator_map.get(indicator_name.lower())
    if col_name is None:
        return (
            f"Indicator '{indicator_name}' is not supported. "
            f"Choose from: {list(indicator_map.keys())}"
        )

    # Fetch extra history so rolling windows are fully populated
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    prefetch_start = (start_dt - relativedelta(days=120)).strftime("%Y-%m-%d")

    def _fetch():
        ticker = yf.Ticker(yf_symbol)
        return ticker.history(start=prefetch_start, end=end_date)

    try:
        data = _fetch_with_retry(_fetch, description=f"get_indicators({yf_symbol})")
    except Exception as e:
        return f"Error fetching indicator data for '{yf_symbol}': {e}"

    if data.empty:
        return f"No data found for HK symbol '{yf_symbol}'"

    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    for col in ("Open", "High", "Low", "Close"):
        if col in data.columns:
            data[col] = data[col].round(2)

    data = _compute_technical_indicators(data)

    # Trim to requested date range
    data = data.loc[start_date:end_date]

    if data.empty:
        return (
            f"No indicator data for '{yf_symbol}' "
            f"between {start_date} and {end_date}"
        )

    result_lines = [
        f"## {indicator_name} values for {yf_symbol} "
        f"from {start_date} to {end_date}:\n"
    ]
    for idx, row in data.iterrows():
        date_str = idx.strftime("%Y-%m-%d")
        value = row.get(col_name)
        if pd.isna(value):
            result_lines.append(f"{date_str}: N/A")
        else:
            result_lines.append(f"{date_str}: {value:.4f}")

    return "\n".join(result_lines)


def get_fundamentals(
    ticker: Annotated[str, "HK stock symbol"],
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None,
) -> str:
    """Get company fundamentals overview from yfinance."""
    yf_symbol = _normalize_hk_symbol(ticker)
    try:
        def _fetch():
            return yf.Ticker(yf_symbol).info

        info = _fetch_with_retry(_fetch, description=f"get_fundamentals({yf_symbol})")

        if not info:
            return f"No fundamentals data found for HK symbol '{yf_symbol}'"

        fields = [
            ("Name", info.get("longName")),
            ("Sector", info.get("sector")),
            ("Industry", info.get("industry")),
            ("Market Cap", info.get("marketCap")),
            ("Currency", info.get("currency", "HKD")),
            ("Exchange", info.get("exchange")),
            ("PE Ratio (TTM)", info.get("trailingPE")),
            ("Forward PE", info.get("forwardPE")),
            ("PEG Ratio", info.get("pegRatio")),
            ("Price to Book", info.get("priceToBook")),
            ("EPS (TTM)", info.get("trailingEps")),
            ("Forward EPS", info.get("forwardEps")),
            ("Dividend Yield", info.get("dividendYield")),
            ("Beta", info.get("beta")),
            ("52 Week High", info.get("fiftyTwoWeekHigh")),
            ("52 Week Low", info.get("fiftyTwoWeekLow")),
            ("50 Day Average", info.get("fiftyDayAverage")),
            ("200 Day Average", info.get("twoHundredDayAverage")),
            ("Revenue (TTM)", info.get("totalRevenue")),
            ("Gross Profit", info.get("grossProfits")),
            ("EBITDA", info.get("ebitda")),
            ("Net Income", info.get("netIncomeToCommon")),
            ("Profit Margin", info.get("profitMargins")),
            ("Operating Margin", info.get("operatingMargins")),
            ("Return on Equity", info.get("returnOnEquity")),
            ("Return on Assets", info.get("returnOnAssets")),
            ("Debt to Equity", info.get("debtToEquity")),
            ("Current Ratio", info.get("currentRatio")),
            ("Book Value", info.get("bookValue")),
            ("Free Cash Flow", info.get("freeCashflow")),
        ]

        lines = [f"{label}: {value}" for label, value in fields if value is not None]

        header = f"# Company Fundamentals for {yf_symbol}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + "\n".join(lines)

    except Exception as e:
        return f"Error retrieving fundamentals for {yf_symbol}: {e}"


def get_balance_sheet(
    ticker: Annotated[str, "HK stock symbol"],
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None,
    freq: Annotated[str, "frequency: 'annual' or 'quarterly'"] = "quarterly",
) -> str:
    """Get balance sheet data from yfinance."""
    yf_symbol = _normalize_hk_symbol(ticker)
    try:
        def _fetch():
            t = yf.Ticker(yf_symbol)
            if freq.lower() == "quarterly":
                return t.quarterly_balance_sheet
            return t.balance_sheet

        data = _fetch_with_retry(_fetch, description=f"get_balance_sheet({yf_symbol})")

        if data.empty:
            return f"No balance sheet data found for HK symbol '{yf_symbol}'"

        csv_string = data.to_csv()
        header = f"# Balance Sheet data for {yf_symbol} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + csv_string

    except Exception as e:
        return f"Error retrieving balance sheet for {yf_symbol}: {e}"


def get_cashflow(
    ticker: Annotated[str, "HK stock symbol"],
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None,
    freq: Annotated[str, "frequency: 'annual' or 'quarterly'"] = "quarterly",
) -> str:
    """Get cash flow data from yfinance."""
    yf_symbol = _normalize_hk_symbol(ticker)
    try:
        def _fetch():
            t = yf.Ticker(yf_symbol)
            if freq.lower() == "quarterly":
                return t.quarterly_cashflow
            return t.cashflow

        data = _fetch_with_retry(_fetch, description=f"get_cashflow({yf_symbol})")

        if data.empty:
            return f"No cash flow data found for HK symbol '{yf_symbol}'"

        csv_string = data.to_csv()
        header = f"# Cash Flow data for {yf_symbol} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + csv_string

    except Exception as e:
        return f"Error retrieving cash flow for {yf_symbol}: {e}"


def get_income_statement(
    ticker: Annotated[str, "HK stock symbol"],
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None,
    freq: Annotated[str, "frequency: 'annual' or 'quarterly'"] = "quarterly",
) -> str:
    """Get income statement data from yfinance."""
    yf_symbol = _normalize_hk_symbol(ticker)
    try:
        def _fetch():
            t = yf.Ticker(yf_symbol)
            if freq.lower() == "quarterly":
                return t.quarterly_income_stmt
            return t.income_stmt

        data = _fetch_with_retry(
            _fetch, description=f"get_income_statement({yf_symbol})"
        )

        if data.empty:
            return f"No income statement data found for HK symbol '{yf_symbol}'"

        csv_string = data.to_csv()
        header = f"# Income Statement data for {yf_symbol} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + csv_string

    except Exception as e:
        return f"Error retrieving income statement for {yf_symbol}: {e}"


def get_insider_transactions(
    ticker: Annotated[str, "HK stock symbol"],
    curr_date: Annotated[str, "current date (not used for yfinance)"] = None,
) -> str:
    """Get insider transactions data from yfinance.

    Note: insider transaction data may be limited for HK stocks.
    """
    yf_symbol = _normalize_hk_symbol(ticker)
    try:
        def _fetch():
            return yf.Ticker(yf_symbol).insider_transactions

        data = _fetch_with_retry(
            _fetch, description=f"get_insider_transactions({yf_symbol})"
        )

        if data is None or data.empty:
            return f"No insider transactions data found for HK symbol '{yf_symbol}'"

        csv_string = data.to_csv()
        header = f"# Insider Transactions data for {yf_symbol}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + csv_string

    except Exception as e:
        return f"Error retrieving insider transactions for {yf_symbol}: {e}"


def get_news(
    symbol: Annotated[str, "HK stock symbol"],
    curr_date: Annotated[str, "current date in yyyy-mm-dd format"],
    look_back: Annotated[int, "number of days to look back for news"] = 7,
) -> str:
    """Get recent news for an HK stock from yfinance."""
    yf_symbol = _normalize_hk_symbol(symbol)
    try:
        def _fetch():
            return yf.Ticker(yf_symbol).news

        news_items = _fetch_with_retry(
            _fetch, description=f"get_news({yf_symbol})"
        )

        if not news_items:
            return f"No news found for HK symbol '{yf_symbol}'"

        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        cutoff_dt = curr_dt - timedelta(days=look_back)

        lines = [
            f"# News for {yf_symbol} (last {look_back} days from {curr_date})\n"
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        ]

        count = 0
        for item in news_items:
            # yfinance news items may have 'providerPublishTime' (unix timestamp)
            publish_time = item.get("providerPublishTime")
            if publish_time:
                pub_dt = datetime.utcfromtimestamp(publish_time)
                if pub_dt < cutoff_dt:
                    continue
                date_str = pub_dt.strftime("%Y-%m-%d %H:%M")
            else:
                date_str = "Unknown date"

            title = item.get("title", "No title")
            publisher = item.get("publisher", "Unknown")
            link = item.get("link", "")

            lines.append(f"\n## [{count + 1}] {title}")
            lines.append(f"Publisher: {publisher}")
            lines.append(f"Date: {date_str}")
            if link:
                lines.append(f"Link: {link}")
            count += 1

        if count == 0:
            return (
                f"No news found for HK symbol '{yf_symbol}' "
                f"in the last {look_back} days from {curr_date}"
            )

        lines.insert(1, f"# Total articles: {count}\n")
        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving news for {yf_symbol}: {e}"


def get_global_news(
    curr_date: Annotated[str, "current date in yyyy-mm-dd format"],
    look_back: Annotated[int, "number of days to look back for news"] = 7,
) -> str:
    """Get global / Hong Kong market news.

    Uses the Hang Seng Index (^HSI) as a proxy for broad HK market news.
    """
    try:
        def _fetch():
            return yf.Ticker("^HSI").news

        news_items = _fetch_with_retry(_fetch, description="get_global_news(^HSI)")

        if not news_items:
            return "No global HK market news found"

        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        cutoff_dt = curr_dt - timedelta(days=look_back)

        lines = [
            f"# Global HK Market News (last {look_back} days from {curr_date})\n"
            f"# Source: Hang Seng Index (^HSI) feed\n"
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        ]

        count = 0
        for item in news_items:
            publish_time = item.get("providerPublishTime")
            if publish_time:
                pub_dt = datetime.utcfromtimestamp(publish_time)
                if pub_dt < cutoff_dt:
                    continue
                date_str = pub_dt.strftime("%Y-%m-%d %H:%M")
            else:
                date_str = "Unknown date"

            title = item.get("title", "No title")
            publisher = item.get("publisher", "Unknown")
            link = item.get("link", "")

            lines.append(f"\n## [{count + 1}] {title}")
            lines.append(f"Publisher: {publisher}")
            lines.append(f"Date: {date_str}")
            if link:
                lines.append(f"Link: {link}")
            count += 1

        if count == 0:
            return (
                f"No global HK market news found "
                f"in the last {look_back} days from {curr_date}"
            )

        lines.insert(1, f"# Total articles: {count}\n")
        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving global HK market news: {e}"


def get_company_name(
    symbol: Annotated[str, "HK stock symbol"],
) -> str:
    """Get the company name for an HK stock.

    Strategy (multi-fallback):
      1. Static mapping (HK_STOCK_NAMES) -- instant, no API call
      2. yfinance ticker.info lookup -- requires network
      3. Default formatted name -- always succeeds
    """
    yf_symbol = _normalize_hk_symbol(symbol)

    # Strategy 1: static mapping
    if yf_symbol in HK_STOCK_NAMES:
        return HK_STOCK_NAMES[yf_symbol]

    # Strategy 2: yfinance lookup
    try:
        def _fetch():
            return yf.Ticker(yf_symbol).info

        info = _fetch_with_retry(
            _fetch, description=f"get_company_name({yf_symbol})"
        )
        name = info.get("longName") or info.get("shortName")
        if name:
            return name
    except Exception as e:
        logger.debug("Failed to fetch company name for %s: %s", yf_symbol, e)

    # Strategy 3: default
    return f"HK Stock {yf_symbol}"
