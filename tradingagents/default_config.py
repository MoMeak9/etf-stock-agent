import os

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.2",
    "quick_think_llm": "gpt-5-mini",
    "backend_url": "https://api.openai.com/v1",
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "custom_streaming": False,
    "custom_timeout": 180,
    "custom_max_retries": 4,
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Asset type configuration
    "asset_type": "stock",
    "etf_analysis_mode": "hybrid",
    "selected_etf_analysts": ["market", "flow", "news", "product"],
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
    # ETF data vendor configuration
    "etf_data_vendors": {
        "etf_price_data": "tushare,akshare",
        "etf_product_data": "tushare,akshare",
        "etf_news_data": "akshare",
    },
    "etf_tool_vendors": {
        # Example: "get_etf_profile": "tushare",
    },
    # A-share (CN market) data vendor configuration
    # Primary: tushare (more accurate fundamentals), Fallback: akshare, baostock
    "cn_data_vendors": {
        "core_stock_apis": "tushare",        # Options: tushare, akshare, baostock
        "technical_indicators": "tushare",   # Options: tushare, akshare, baostock
        "fundamental_data": "tushare",       # Options: tushare, akshare, baostock
        "news_data": "akshare",              # Options: akshare (tushare/baostock have no news API)
    },
    "cn_tool_vendors": {
        # Example: "get_stock_data": "akshare",  # Override category default
    },
    # HK market data vendor configuration
    "hk_data_vendors": {
        "core_stock_apis": "yfinance",       # Options: yfinance
        "technical_indicators": "yfinance",  # Options: yfinance
        "fundamental_data": "yfinance",      # Options: yfinance
        "news_data": "yfinance",             # Options: yfinance
    },
    "hk_tool_vendors": {
        # Example: "get_stock_data": "yfinance",
    },
    # Tushare token (required for tushare as primary vendor)
    "tushare_token": os.getenv("TUSHARE_TOKEN", ""),
    # A-share request interval (seconds) to avoid being blocked
    "cn_request_interval": 0.3,
}
