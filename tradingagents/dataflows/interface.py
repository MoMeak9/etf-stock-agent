from typing import Annotated

# Import from vendor-specific modules
from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .yfinance_news import get_news_yfinance, get_global_news_yfinance
from .alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_global_news as get_alpha_vantage_global_news,
)
from .alpha_vantage_common import AlphaVantageRateLimitError

# A-share vendor imports
from .akshare_stock import (
    get_stock_data as get_akshare_stock,
    get_indicators as get_akshare_indicators,
    get_fundamentals as get_akshare_fundamentals,
    get_balance_sheet as get_akshare_balance_sheet,
    get_cashflow as get_akshare_cashflow,
    get_income_statement as get_akshare_income_statement,
    get_insider_transactions as get_akshare_insider_transactions,
)
from .akshare_news import (
    get_news as get_akshare_news,
    get_global_news as get_akshare_global_news,
)

try:
    from .akshare_etf import (
        get_etf_price_data as get_akshare_etf_price_data,
        get_etf_indicators as get_akshare_etf_indicators,
        get_etf_profile as get_akshare_etf_profile,
        get_etf_holdings as get_akshare_etf_holdings,
        get_etf_fund_flow as get_akshare_etf_fund_flow,
        get_etf_discount_premium as get_akshare_etf_discount_premium,
        get_etf_tracking_info as get_akshare_etf_tracking_info,
        get_etf_news as get_akshare_etf_news,
    )
    _AKSHARE_ETF_AVAILABLE = True
except ImportError:
    _AKSHARE_ETF_AVAILABLE = False

# Tushare vendor imports (primary for A-share, optional: requires tushare package)
try:
    import tushare as _tushare_check  # verify the package is actually installed
    del _tushare_check
    from .tushare_stock import (
        get_stock_data as get_tushare_stock,
        get_indicators as get_tushare_indicators,
        get_fundamentals as get_tushare_fundamentals,
        get_balance_sheet as get_tushare_balance_sheet,
        get_cashflow as get_tushare_cashflow,
        get_income_statement as get_tushare_income_statement,
        get_insider_transactions as get_tushare_insider_transactions,
        TushareError,
    )
    _TUSHARE_AVAILABLE = True
except ImportError:
    _TUSHARE_AVAILABLE = False
    TushareError = Exception  # fallback so references don't break

_TUSHARE_ETF_AVAILABLE = False
if _TUSHARE_AVAILABLE:
    try:
        from .tushare_etf import (
            get_etf_price_data as get_tushare_etf_price_data,
            get_etf_indicators as get_tushare_etf_indicators,
            get_etf_profile as get_tushare_etf_profile,
            get_etf_holdings as get_tushare_etf_holdings,
            get_etf_fund_flow as get_tushare_etf_fund_flow,
            get_etf_discount_premium as get_tushare_etf_discount_premium,
            get_etf_tracking_info as get_tushare_etf_tracking_info,
            get_etf_news as get_tushare_etf_news,
        )
        _TUSHARE_ETF_AVAILABLE = True
    except ImportError:
        pass

# Market detection
from .market_utils import (
    detect_market,
    normalize_symbol,
    normalize_hk_symbol,
    is_supported_cn_etf,
)

# Configuration and routing logic
from .config import get_config, get_market_context, get_asset_context

# A-share ETF vendor imports (akshare-based, always available)
from .akshare_etf import (
    get_etf_price_data as get_akshare_etf_price_data,
    get_etf_indicators as get_akshare_etf_indicators,
    get_etf_profile as get_akshare_etf_profile,
    get_etf_holdings as get_akshare_etf_holdings,
    get_etf_fund_flow as get_akshare_etf_fund_flow,
    get_etf_discount_premium as get_akshare_etf_discount_premium,
    get_etf_tracking_info as get_akshare_etf_tracking_info,
    get_etf_news as get_akshare_etf_news,
)

# Tushare ETF vendor imports (optional, requires tushare package + token)
_TUSHARE_ETF_AVAILABLE = False
if _TUSHARE_AVAILABLE:
    try:
        from .tushare_etf import (
            get_etf_price_data as get_tushare_etf_price_data,
            get_etf_indicators as get_tushare_etf_indicators,
            get_etf_profile as get_tushare_etf_profile,
            get_etf_holdings as get_tushare_etf_holdings,
            get_etf_fund_flow as get_tushare_etf_fund_flow,
            get_etf_discount_premium as get_tushare_etf_discount_premium,
            get_etf_tracking_info as get_tushare_etf_tracking_info,
            get_etf_news as get_tushare_etf_news,
        )
        _TUSHARE_ETF_AVAILABLE = True
    except ImportError:
        pass

# BaoStock vendor imports (optional, requires baostock package)
try:
    import baostock as _baostock_check  # verify the package is actually installed
    del _baostock_check
    from .baostock_stock import (
        get_stock_data as get_baostock_stock,
        get_indicators as get_baostock_indicators,
        get_fundamentals as get_baostock_fundamentals,
        get_balance_sheet as get_baostock_balance_sheet,
        get_cashflow as get_baostock_cashflow,
        get_income_statement as get_baostock_income_statement,
        get_insider_transactions as get_baostock_insider_transactions,
    )
    _BAOSTOCK_AVAILABLE = True
except ImportError:
    _BAOSTOCK_AVAILABLE = False

# HK stock vendor imports
try:
    from .hk_stock import (
        get_stock_data as get_hk_stock,
        get_indicators as get_hk_indicators,
        get_fundamentals as get_hk_fundamentals,
        get_balance_sheet as get_hk_balance_sheet,
        get_cashflow as get_hk_cashflow,
        get_income_statement as get_hk_income_statement,
        get_insider_transactions as get_hk_insider_transactions,
    )
    _HK_AVAILABLE = True
except ImportError:
    _HK_AVAILABLE = False

# Methods where the first argument is NOT a stock symbol
_NON_SYMBOL_METHODS = {"get_global_news"}

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    }
}

ETF_TOOLS_CATEGORIES = {
    "etf_price_data": {
        "description": "ETF OHLCV and trading data",
        "tools": ["get_etf_price_data", "get_etf_indicators"],
    },
    "etf_product_data": {
        "description": "ETF profile, holdings, tracking, and premium data",
        "tools": [
            "get_etf_profile",
            "get_etf_holdings",
            "get_etf_fund_flow",
            "get_etf_discount_premium",
            "get_etf_tracking_info",
        ],
    },
    "etf_news_data": {
        "description": "ETF-relevant news data",
        "tools": ["get_etf_news"],
    },
}

VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
    "akshare",
    "tushare",
    "baostock",
    "hk",
]

ETF_VENDOR_LIST = [
    "tushare",
    "akshare",
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
        "akshare": get_akshare_stock,
        **({"tushare": get_tushare_stock} if _TUSHARE_AVAILABLE else {}),
        **({"baostock": get_baostock_stock} if _BAOSTOCK_AVAILABLE else {}),
        **({"hk": get_hk_stock} if _HK_AVAILABLE else {}),
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
        "akshare": get_akshare_indicators,
        **({"tushare": get_tushare_indicators} if _TUSHARE_AVAILABLE else {}),
        **({"baostock": get_baostock_indicators} if _BAOSTOCK_AVAILABLE else {}),
        **({"hk": get_hk_indicators} if _HK_AVAILABLE else {}),
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
        "akshare": get_akshare_fundamentals,
        **({"tushare": get_tushare_fundamentals} if _TUSHARE_AVAILABLE else {}),
        **({"baostock": get_baostock_fundamentals} if _BAOSTOCK_AVAILABLE else {}),
        **({"hk": get_hk_fundamentals} if _HK_AVAILABLE else {}),
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
        "akshare": get_akshare_balance_sheet,
        **({"tushare": get_tushare_balance_sheet} if _TUSHARE_AVAILABLE else {}),
        **({"baostock": get_baostock_balance_sheet} if _BAOSTOCK_AVAILABLE else {}),
        **({"hk": get_hk_balance_sheet} if _HK_AVAILABLE else {}),
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
        "akshare": get_akshare_cashflow,
        **({"tushare": get_tushare_cashflow} if _TUSHARE_AVAILABLE else {}),
        **({"baostock": get_baostock_cashflow} if _BAOSTOCK_AVAILABLE else {}),
        **({"hk": get_hk_cashflow} if _HK_AVAILABLE else {}),
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
        "akshare": get_akshare_income_statement,
        **({"tushare": get_tushare_income_statement} if _TUSHARE_AVAILABLE else {}),
        **({"baostock": get_baostock_income_statement} if _BAOSTOCK_AVAILABLE else {}),
        **({"hk": get_hk_income_statement} if _HK_AVAILABLE else {}),
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
        "akshare": get_akshare_news,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
        "akshare": get_akshare_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
        "akshare": get_akshare_insider_transactions,
        **({"tushare": get_tushare_insider_transactions} if _TUSHARE_AVAILABLE else {}),
        **({"baostock": get_baostock_insider_transactions} if _BAOSTOCK_AVAILABLE else {}),
        **({"hk": get_hk_insider_transactions} if _HK_AVAILABLE else {}),
    },
}

ETF_VENDOR_METHODS = {
    "get_etf_price_data": {
        **({"tushare": get_tushare_etf_price_data} if _TUSHARE_ETF_AVAILABLE else {}),
        **({"akshare": get_akshare_etf_price_data} if _AKSHARE_ETF_AVAILABLE else {}),
    },
    "get_etf_indicators": {
        **({"tushare": get_tushare_etf_indicators} if _TUSHARE_ETF_AVAILABLE else {}),
        **({"akshare": get_akshare_etf_indicators} if _AKSHARE_ETF_AVAILABLE else {}),
    },
    "get_etf_profile": {
        **({"tushare": get_tushare_etf_profile} if _TUSHARE_ETF_AVAILABLE else {}),
        **({"akshare": get_akshare_etf_profile} if _AKSHARE_ETF_AVAILABLE else {}),
    },
    "get_etf_holdings": {
        **({"tushare": get_tushare_etf_holdings} if _TUSHARE_ETF_AVAILABLE else {}),
        **({"akshare": get_akshare_etf_holdings} if _AKSHARE_ETF_AVAILABLE else {}),
    },
    "get_etf_fund_flow": {
        **({"tushare": get_tushare_etf_fund_flow} if _TUSHARE_ETF_AVAILABLE else {}),
        **({"akshare": get_akshare_etf_fund_flow} if _AKSHARE_ETF_AVAILABLE else {}),
    },
    "get_etf_discount_premium": {
        **({"tushare": get_tushare_etf_discount_premium} if _TUSHARE_ETF_AVAILABLE else {}),
        **({"akshare": get_akshare_etf_discount_premium} if _AKSHARE_ETF_AVAILABLE else {}),
    },
    "get_etf_tracking_info": {
        **({"tushare": get_tushare_etf_tracking_info} if _TUSHARE_ETF_AVAILABLE else {}),
        **({"akshare": get_akshare_etf_tracking_info} if _AKSHARE_ETF_AVAILABLE else {}),
    },
    "get_etf_news": {
        **({"tushare": get_tushare_etf_news} if _TUSHARE_ETF_AVAILABLE else {}),
        **({"akshare": get_akshare_etf_news} if _AKSHARE_ETF_AVAILABLE else {}),
    },
}

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    for category, info in ETF_TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a US data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def get_vendor_cn(category: str, method: str = None) -> str:
    """Get the configured vendor for a CN (A-share) data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check CN tool-level configuration first
    if method:
        cn_tool_vendors = config.get("cn_tool_vendors", {})
        if method in cn_tool_vendors:
            return cn_tool_vendors[method]

    # Fall back to CN category-level configuration
    return config.get("cn_data_vendors", {}).get(category, "tushare")


def get_vendor_hk(category: str, method: str = None) -> str:
    """Get the configured vendor for HK market data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check HK tool-level configuration first
    if method:
        hk_tool_vendors = config.get("hk_tool_vendors", {})
        if method in hk_tool_vendors:
            return hk_tool_vendors[method]

    # Fall back to HK category-level configuration
    return config.get("hk_data_vendors", {}).get(category, "yfinance")


def get_vendor_etf(category: str, method: str = None) -> str:
    """Get the configured vendor for ETF data categories or specific ETF tools."""
    config = get_config()

    if method:
        etf_tool_vendors = config.get("etf_tool_vendors", {})
        if method in etf_tool_vendors:
            return etf_tool_vendors[method]

    return config.get("etf_data_vendors", {}).get(category, "tushare,akshare")


def _detect_asset_for_route(kwargs) -> str:
    """Detect asset type from explicit kwargs, thread-local context, or config."""
    if "asset_type" in kwargs and kwargs["asset_type"]:
        return str(kwargs["asset_type"]).lower()

    asset_context = get_asset_context()
    if asset_context:
        return str(asset_context).lower()

    return str(get_config().get("asset_type", "stock")).lower()

def _detect_market_for_route(method: str, args, kwargs) -> str:
    """Detect market from the method call arguments."""
    if method in _NON_SYMBOL_METHODS:
        # get_global_news has no symbol arg; use thread-local context
        return get_market_context()

    # Extract symbol from first positional arg or keyword
    symbol = ""
    if args:
        symbol = args[0]
    else:
        symbol = kwargs.get("symbol", kwargs.get("ticker", ""))

    if not symbol:
        return "us"

    return detect_market(str(symbol))

def _route_etf_vendor(method: str, *args, **kwargs):
    """Route ETF method calls to ETF-specific vendor implementations."""
    kwargs = dict(kwargs)
    kwargs.pop("asset_type", None)

    if method not in ETF_VENDOR_METHODS:
        return f"Error: ETF method '{method}' not supported."

    symbol = ""
    if method not in _NON_SYMBOL_METHODS:
        if args:
            symbol = str(args[0])
        else:
            symbol = str(kwargs.get("symbol", kwargs.get("ticker", "")))

    if symbol and not is_supported_cn_etf(symbol):
        return "Error: ETF mode currently supports only A-share exchange-traded ETFs."

    category = get_category_for_method(method)
    vendor_config = get_vendor_etf(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(",") if v.strip()]

    if method not in ETF_VENDOR_METHODS:
        return f"Error: ETF method '{method}' not supported."

    if method not in _NON_SYMBOL_METHODS and args:
        normalized = normalize_symbol(str(args[0]), "cn")
        args = (normalized,) + args[1:]

    all_available_vendors = list(ETF_VENDOR_METHODS[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    last_error = None
    for vendor in fallback_vendors:
        if vendor not in ETF_VENDOR_METHODS[method]:
            continue

        impl_func = ETF_VENDOR_METHODS[method][vendor]
        try:
            return impl_func(*args, **kwargs)
        except Exception as e:
            last_error = e
            continue

    return f"Error: All ETF data vendors failed for '{method}'. Last error: {last_error}"

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with market-aware fallback."""
    asset_type = _detect_asset_for_route(kwargs)

    if asset_type == "etf" and method in ETF_VENDOR_METHODS:
        return _route_etf_vendor(method, *args, **kwargs)

    # Detect market from symbol
    market = _detect_market_for_route(method, args, kwargs)

    # Get vendor config based on market
    category = get_category_for_method(method)
    if market == "cn":
        vendor_config = get_vendor_cn(category, method)
    elif market == "hk":
        vendor_config = get_vendor_hk(category, method)
    else:
        vendor_config = get_vendor(category, method)

    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # Normalize symbol for the target vendor
    if method not in _NON_SYMBOL_METHODS and args:
        symbol = str(args[0])
        if market == "hk":
            normalized = normalize_hk_symbol(symbol)
        else:
            normalized = normalize_symbol(symbol, market)
        args = (normalized,) + args[1:]

    # Build fallback chain: primary vendors first, then remaining available vendors
    # For each market, only include compatible vendors in fallback
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    if market == "cn":
        cn_vendors = ["tushare", "akshare", "baostock"]
        all_available_vendors = [v for v in all_available_vendors if v in cn_vendors]
    elif market == "hk":
        hk_vendors = ["hk", "yfinance"]
        all_available_vendors = [v for v in all_available_vendors if v in hk_vendors]
    else:
        us_vendors = ["yfinance", "alpha_vantage"]
        all_available_vendors = [v for v in all_available_vendors if v in us_vendors]

    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    last_error = None
    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            return impl_func(*args, **kwargs)
        except AlphaVantageRateLimitError:
            continue  # Rate limits trigger fallback
        except Exception as e:
            last_error = e
            # For CN/HK vendors, any exception triggers fallback to next vendor
            if market in ("cn", "hk"):
                continue
            raise

    # All vendors exhausted — return error string instead of raising,
    # so the LLM agent can see the error and continue gracefully.
    return f"Error: All data vendors failed for '{method}' (market={market}). Last error: {last_error}"
