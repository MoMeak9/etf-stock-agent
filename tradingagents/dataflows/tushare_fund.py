"""Open-ended public fund data access via Tushare."""

from __future__ import annotations

from tradingagents.dataflows.tushare_stock import _get_tushare_api


def to_fund_ts_code(symbol: str) -> str:
    normalized = str(symbol).strip()
    if normalized.upper().endswith(".OF"):
        return normalized.upper()
    return f"{normalized}.OF"


def _compact_date(date) -> str:
    if date is None:
        return ""
    return str(date).strip().replace("-", "")[:8]


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


def fetch_fund_nav(symbol: str, start_date, end_date):
    pro = _get_tushare_api()
    return pro.fund_nav(
        ts_code=to_fund_ts_code(symbol),
        start_date=_compact_date(start_date),
        end_date=_compact_date(end_date),
    )


def fetch_fund_portfolio(symbol: str):
    pro = _get_tushare_api()
    return pro.fund_portfolio(ts_code=to_fund_ts_code(symbol))


def fetch_fund_manager(symbol: str):
    pro = _get_tushare_api()
    if not hasattr(pro, "fund_manager"):
        return None
    return pro.fund_manager(ts_code=to_fund_ts_code(symbol))


def fetch_fund_announcement(symbol: str, start_date, end_date):
    pro = _get_tushare_api()
    if not hasattr(pro, "fund_announcement"):
        return None
    return pro.fund_announcement(
        ts_code=to_fund_ts_code(symbol),
        start_date=_compact_date(start_date),
        end_date=_compact_date(end_date),
    )
