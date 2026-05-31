"""Open-ended public fund data access via AKShare."""

from __future__ import annotations

from datetime import date


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol).strip()
    if normalized.upper().endswith(".OF"):
        normalized = normalized[:-3]
    return normalized.zfill(6) if normalized.isdigit() else normalized


def fetch_fund_basic(symbol: str):
    import akshare as ak

    funds = ak.fund_name_em()
    if funds is None or funds.empty:
        return funds
    code_column = "基金代码" if "基金代码" in funds.columns else funds.columns[0]
    return funds[funds[code_column].astype(str).str.zfill(6) == _normalize_symbol(symbol)]


def fetch_fund_nav(symbol: str, start_date=None, end_date=None):
    import akshare as ak

    return ak.fund_open_fund_info_em(symbol=_normalize_symbol(symbol), indicator="单位净值走势")


def fetch_fund_portfolio(symbol: str):
    import akshare as ak

    return ak.fund_portfolio_hold_em(symbol=_normalize_symbol(symbol), date=str(date.today().year))


def fetch_fund_manager(symbol: str):
    return None


def fetch_fund_announcement(symbol: str, start_date=None, end_date=None):
    return None
