"""Market detection, symbol normalization, and A-share trade calendar utilities."""

import os
import re
import time
from datetime import datetime

import pandas as pd

ETF_CODE_PREFIXES = ("51", "52", "56", "58", "15", "16")


def detect_market(symbol: str) -> str:
    """
    Detect market from stock symbol.

    Rules:
      - .HK suffix (0700.HK) → "hk"
      - Pure letters (NVDA, AAPL) → "us"
      - 6-digit numbers (600519, 000858) → "cn"
      - With suffix (000858.SZ, 600519.SH) → "cn"
      - With prefix (SZ000858, SH600519) → "cn"

    Returns: "us" | "cn" | "hk"
    """
    if not symbol or not symbol.strip():
        return "us"

    s = symbol.strip()

    # Check for .HK suffix (Hong Kong)
    if re.match(r"^\d{1,5}\.HK$", s, re.IGNORECASE):
        return "hk"

    # Check for .SH / .SZ suffix
    if re.match(r"^\d{6}\.(SH|SZ)$", s, re.IGNORECASE):
        return "cn"

    # Check for SH / SZ prefix
    if re.match(r"^(SH|SZ)\d{6}$", s, re.IGNORECASE):
        return "cn"

    # Pure 6-digit number
    if re.match(r"^\d{6}$", s):
        return "cn"

    # Pure letters (US stock)
    if re.match(r"^[A-Za-z]+$", s):
        return "us"

    # Fallback: if contains digits and letters mixed (e.g. BRK.B), assume US
    return "us"


def normalize_symbol(symbol: str, market: str) -> str:
    """
    Normalize user input to the format required by data sources.

    A-share: strip prefix/suffix, return 6-digit number.
    US: uppercase.
    """
    if not symbol:
        return symbol

    s = symbol.strip()

    if market == "cn":
        # Remove .SH / .SZ suffix
        s = re.sub(r"\.(SH|SZ)$", "", s, flags=re.IGNORECASE)
        # Remove SH / SZ prefix
        s = re.sub(r"^(SH|SZ)", "", s, flags=re.IGNORECASE)
        return s

    # US market
    return s.upper()


def is_etf(symbol: str) -> bool:
    """
    Detect whether an A-share symbol is an ETF.

    A-share ETF code prefixes:
      - Shanghai: 51xxxx, 52xxxx, 56xxxx, 58xxxx
      - Shenzhen: 15xxxx, 16xxxx

    Args:
        symbol: Raw or normalized 6-digit A-share code.

    Returns: True if the symbol matches known ETF prefixes.
    """
    normalized = normalize_symbol(symbol, "cn")
    if not normalized or len(normalized) != 6:
        return False
    prefix2 = normalized[:2]
    return prefix2 in ("51", "52", "56", "58", "15", "16")


def is_supported_cn_etf(symbol: str) -> bool:
    """First-pass eligibility check for the A-share ETF scope in phase 1."""
    return detect_market(symbol) == "cn" and is_etf(symbol)


def get_exchange(symbol: str) -> str:
    """
    Determine A-share exchange from stock code.

    Rules:
      - Starts with 6, 9 → "SH" (Shanghai)
      - Starts with 0, 2, 3 → "SZ" (Shenzhen)

    Returns: "SH" | "SZ"
    """
    normalized = normalize_symbol(symbol, "cn")
    if not normalized:
        return "SZ"

    if is_etf(normalized):
        return "SH" if normalized.startswith(("51", "52", "56", "58")) else "SZ"

    first = normalized[0]
    if first in ("6", "9"):
        return "SH"
    return "SZ"


def normalize_hk_symbol(symbol: str) -> str:
    """
    Normalize HK stock symbol to XXXX.HK format.

    Examples: 700 → 0700.HK, 00700 → 0700.HK, 0700.HK → 0700.HK
    """
    if not symbol:
        return symbol
    s = str(symbol).strip().upper()
    if s.endswith(".HK"):
        s = s[:-3]
    if s.isdigit():
        clean = s.lstrip("0") or "0"
        return f"{clean.zfill(4)}.HK"
    return s


def get_market_info(symbol: str) -> dict:
    """
    Return market metadata for a given symbol.

    Returns: {
        "market": "cn" | "us" | "hk",
        "exchange": "SH" | "SZ" | "HKG" | "",
        "currency": "CNY" | "USD" | "HKD",
        "language": "zh" | "en",
        "symbol_normalized": str,
        "symbol_display": str,
    }
    """
    market = detect_market(symbol)

    if market == "cn":
        normalized = normalize_symbol(symbol, "cn")
        exchange = get_exchange(normalized)
        etf = is_etf(normalized)
        return {
            "market": "cn",
            "exchange": exchange,
            "currency": "CNY",
            "language": "zh",
            "is_etf": is_etf(normalized),
            "symbol_normalized": normalized,
            "symbol_display": f"{normalized}.{exchange}",
        }

    if market == "hk":
        normalized = normalize_hk_symbol(symbol)
        return {
            "market": "hk",
            "exchange": "HKG",
            "currency": "HKD",
            "language": "zh",
            "is_etf": False,
            "symbol_normalized": normalized,
            "symbol_display": normalized,
        }

    normalized = normalize_symbol(symbol, "us")
    return {
        "market": "us",
        "exchange": "",
        "currency": "USD",
        "language": "en",
        "is_etf": False,
        "symbol_normalized": normalized,
        "symbol_display": normalized,
    }


def get_cn_trade_dates(start_date: str, end_date: str) -> list:
    """
    Get A-share trade dates within a date range.

    Uses akshare's tool_trade_date_hist_sina() with local caching.
    Cache is valid for 7 days.

    Args:
        start_date: YYYY-MM-DD format
        end_date: YYYY-MM-DD format

    Returns: list of date strings in YYYY-MM-DD format
    """
    from .config import get_config

    config = get_config()
    cache_dir = config.get("data_cache_dir", "data_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, "cn_trade_dates.csv")

    # Check cache validity (7 days)
    need_refresh = True
    if os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        age_days = (time.time() - mtime) / 86400
        if age_days < 7:
            need_refresh = False

    if need_refresh:
        try:
            import akshare as ak

            df = ak.tool_trade_date_hist_sina()
            df.to_csv(cache_file, index=False)
        except Exception as e:
            # If fetch fails but cache exists, use stale cache
            if os.path.exists(cache_file):
                need_refresh = False
            else:
                raise RuntimeError(f"Failed to fetch trade dates: {e}")

    df = pd.read_csv(cache_file)
    # Column is typically "trade_date"
    col = df.columns[0]
    dates = pd.to_datetime(df[col])

    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    filtered = dates[(dates >= start_dt) & (dates <= end_dt)]
    return [d.strftime("%Y-%m-%d") for d in sorted(filtered)]
