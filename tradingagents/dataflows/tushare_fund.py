"""Open-ended public fund data access via Tushare."""

from __future__ import annotations

from tradingagents.dataflows.tushare_stock import _get_tushare_api


def to_fund_ts_code(symbol: str) -> str:
    normalized = str(symbol).strip()
    return f"{normalized}.OF"


def fetch_fund_basic(symbol: str):
    pro = _get_tushare_api()
    ts_code = to_fund_ts_code(symbol)
    try:
        return pro.fund_basic(ts_code=ts_code, market="O")
    except Exception as exc:
        message = str(exc).lower()
        if "ts_code" not in message and "unexpected" not in message and "keyword" not in message:
            raise
        df = pro.fund_basic(market="O")
        if df is not None and not df.empty and "ts_code" in df.columns:
            return df[df["ts_code"] == ts_code]
        return df
