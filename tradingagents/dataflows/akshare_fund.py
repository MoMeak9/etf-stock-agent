"""Open-ended public fund data access via AKShare."""

from __future__ import annotations


def fetch_fund_basic(symbol: str):
    import akshare as ak

    funds = ak.fund_name_em()
    if funds is None or funds.empty:
        return funds
    code_column = "基金代码" if "基金代码" in funds.columns else funds.columns[0]
    return funds[funds[code_column].astype(str).str.zfill(6) == str(symbol).zfill(6)]
