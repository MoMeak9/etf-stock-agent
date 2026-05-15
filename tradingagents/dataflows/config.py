import os
import threading
import tradingagents.default_config as default_config
from typing import Dict, Optional

# Use default config but allow it to be overridden
_config: Optional[Dict] = None

# Thread-safe market context for the current analysis run
_market_context = threading.local()
_asset_context = threading.local()


def set_market_context(market: str):
    """Set the current market context (called at start of propagate())."""
    _market_context.market = market


def get_market_context() -> str:
    """Get the current market context. Defaults to 'us'."""
    return getattr(_market_context, "market", "us")


def set_asset_context(asset_type: str):
    """Set the current asset context (stock or etf)."""
    _asset_context.asset_type = asset_type


def get_asset_context() -> str:
    """Get the current asset context. Defaults to stock mode."""
    return getattr(_asset_context, "asset_type", "stock")


def initialize_config():
    """Initialize the configuration with default values."""
    global _config
    if _config is None:
        _config = default_config.DEFAULT_CONFIG.copy()


def set_config(config: Dict):
    """Update the configuration with custom values."""
    global _config
    if _config is None:
        _config = default_config.DEFAULT_CONFIG.copy()
    _config.update(config)


def get_config() -> Dict:
    """Get the current configuration."""
    if _config is None:
        initialize_config()
    return _config.copy()


def bypass_proxy_for_cn():
    """Temporarily disable proxy for CN data API calls (eastmoney, sina, etc.).

    Many users have local proxies (e.g., Clash at 127.0.0.1:7890) configured in
    macOS system settings that can't route to Chinese domestic APIs.
    Uses NO_PROXY=* to bypass all proxy settings including macOS system proxies.
    Returns a dict of saved values for restore_proxy() to use.
    """
    proxy_keys = ("no_proxy", "NO_PROXY")
    saved = {}
    for key in proxy_keys:
        saved[key] = os.environ.get(key)
    # NO_PROXY=* tells requests/urllib3 to bypass proxy for all hosts
    os.environ["no_proxy"] = "*"
    os.environ["NO_PROXY"] = "*"
    return saved


def restore_proxy(saved: dict):
    """Restore proxy env vars saved by bypass_proxy_for_cn()."""
    for key, val in saved.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


# Initialize with default config
initialize_config()
