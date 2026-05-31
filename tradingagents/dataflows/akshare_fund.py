"""Open-ended public fund data access via AKShare."""

from __future__ import annotations

from datetime import date


def fetch_fund_basic(symbol: str):
    import akshare as ak

    funds = ak.fund_name_em()
    if funds is None or funds.empty:
        return funds
    code_column = "基金代码" if "基金代码" in funds.columns else funds.columns[0]
    return funds[funds[code_column].astype(str).str.zfill(6) == str(symbol).zfill(6)]


def fetch_fund_nav(symbol: str, start_date=None, end_date=None):
    import akshare as ak

    return ak.fund_open_fund_info_em(symbol=str(symbol), indicator="单位净值走势")


def fetch_fund_portfolio(symbol: str):
    import akshare as ak

    return ak.fund_portfolio_hold_em(symbol=str(symbol), date=str(date.today().year))


def fetch_fund_manager(symbol: str):
    return None


def fetch_fund_announcement(symbol: str, start_date=None, end_date=None):
    return None
