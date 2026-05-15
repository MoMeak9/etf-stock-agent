"""A-share ETF data access via tushare."""

from datetime import datetime
from typing import Annotated

import pandas as pd

from .market_utils import get_exchange, normalize_symbol
from .stockstats_utils import _clean_dataframe
from .tushare_stock import TushareError, _get_tushare_api


def _to_etf_ts_code(symbol: str) -> str:
    """Convert A-share ETF code to the correct tushare ts_code format."""
    normalized = normalize_symbol(symbol, "cn")
    exchange = get_exchange(normalized)
    return f"{normalized}.{exchange}"


def get_etf_price_data(
    symbol: Annotated[str, "A-share ETF code"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    try:
        pro = _get_tushare_api()
        ts_code = _to_etf_ts_code(symbol)
        df = pro.fund_daily(
            ts_code=ts_code,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        if df is None or df.empty:
            return f"# ETF Price Data\n\n未获取到 {symbol} 在 {start_date} 至 {end_date} 的 ETF 行情数据。"

        df = df.rename(
            columns={
                "trade_date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "vol": "Volume",
            }
        )
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
        return f"# ETF Price Data for {symbol}\n# Source: tushare\n\n" + df[
            [c for c in ("Date", "Open", "High", "Low", "Close", "Volume") if c in df.columns]
        ].sort_values("Date").to_csv(index=False)
    except Exception as exc:
        raise TushareError(f"tushare ETF price error for {symbol}: {exc}")


def get_etf_indicators(
    symbol: Annotated[str, "A-share ETF code"],
    indicator: Annotated[str, "technical indicator name"],
    curr_date: Annotated[str, "current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
) -> str:
    from stockstats import wrap
    from dateutil.relativedelta import relativedelta

    raw = get_etf_price_data(
        symbol,
        (pd.Timestamp(curr_date) - pd.DateOffset(days=max(look_back_days + 90, 180))).strftime("%Y-%m-%d"),
        curr_date,
    )
    lines = [line for line in raw.splitlines() if line and not line.startswith("#")]
    if len(lines) < 2:
        return f"## {indicator} values for ETF {symbol}\n\n无可用行情数据。"

    df = pd.read_csv(pd.io.common.StringIO("\n".join(lines)))
    df = _clean_dataframe(df)
    wrapped = wrap(df)
    wrapped["Date"] = wrapped["Date"].dt.strftime("%Y-%m-%d")
    wrapped[indicator]

    before = datetime.strptime(curr_date, "%Y-%m-%d") - relativedelta(days=look_back_days)
    current_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    result_lines = []
    while current_dt >= before:
        date_str = current_dt.strftime("%Y-%m-%d")
        matched = wrapped.loc[wrapped["Date"] == date_str, indicator]
        if matched.empty:
            result_lines.append(f"{date_str}: N/A: Not a trading day")
        else:
            value = matched.iloc[0]
            result_lines.append(f"{date_str}: {'N/A' if pd.isna(value) else value}")
        current_dt -= relativedelta(days=1)

    return f"## {indicator} values for ETF {symbol}\n\n" + "\n".join(result_lines)


def get_etf_profile(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "current date, yyyy-mm-dd"] = None,
) -> str:
    try:
        pro = _get_tushare_api()
        ts_code = _to_etf_ts_code(ticker)
        parts = []

        basic = pro.fund_basic(ts_code=ts_code)
        if basic is not None and not basic.empty:
            parts.append("## ETF 基本信息\n" + basic.to_csv(index=False))

        ref_date = (curr_date or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
        nav = pro.fund_nav(
            ts_code=ts_code,
            start_date=(pd.Timestamp(ref_date) - pd.DateOffset(days=30)).strftime("%Y%m%d"),
            end_date=ref_date,
        )
        if nav is not None and not nav.empty:
            parts.append("## 近期净值数据\n" + nav.head(20).to_csv(index=False))

        share = pro.fund_share(
            ts_code=ts_code,
            start_date=(pd.Timestamp(ref_date) - pd.DateOffset(days=60)).strftime("%Y%m%d"),
            end_date=ref_date,
        )
        if share is not None and not share.empty:
            parts.append("## 近期份额变化\n" + share.head(20).to_csv(index=False))

        if not parts:
            return f"# ETF Profile for {ticker}\n\n未获取到 ETF 产品信息。"
        return f"# ETF Profile for {ticker}\n# Source: tushare\n\n" + "\n\n".join(parts)
    except Exception as exc:
        raise TushareError(f"tushare ETF profile error for {ticker}: {exc}")


def get_etf_holdings(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "current date, yyyy-mm-dd"] = None,
) -> str:
    try:
        pro = _get_tushare_api()
        ts_code = _to_etf_ts_code(ticker)
        df = pro.fund_portfolio(ts_code=ts_code)
        if df is None or df.empty:
            return f"# ETF Holdings for {ticker}\n\n未获取到 ETF 持仓数据。"
        latest_period = df.sort_values("end_date", ascending=False)["end_date"].iloc[0]
        df = df[df["end_date"] == latest_period].head(20)
        return f"# ETF Holdings for {ticker}\n# Source: tushare\n\n" + df.to_csv(index=False)
    except Exception as exc:
        raise TushareError(f"tushare ETF holdings error for {ticker}: {exc}")


def get_etf_fund_flow(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "current date, yyyy-mm-dd"] = None,
) -> str:
    try:
        pro = _get_tushare_api()
        ts_code = _to_etf_ts_code(ticker)
        ref_date = (curr_date or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
        df = pro.fund_share(
            ts_code=ts_code,
            start_date=(pd.Timestamp(ref_date) - pd.DateOffset(days=90)).strftime("%Y%m%d"),
            end_date=ref_date,
        )
        if df is None or df.empty:
            return f"# ETF Fund Flow for {ticker}\n\n未获取到 ETF 份额变化数据。"
        return (
            f"# ETF Fund Flow for {ticker}\n# Source: tushare\n"
            f"# Note: 使用基金份额变化作为资金流代理指标。\n\n"
            + df.head(60).to_csv(index=False)
        )
    except Exception as exc:
        raise TushareError(f"tushare ETF fund flow error for {ticker}: {exc}")


def get_etf_discount_premium(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "current date, yyyy-mm-dd"] = None,
) -> str:
    return (
        f"# ETF Discount Premium for {ticker}\n\n"
        "当前 tushare 路径未稳定提供 ETF 折溢价明细。\n"
        "在产品分析中应明确标记为“数据有限”，不要推断精确折溢价数值。"
    )


def get_etf_tracking_info(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "current date, yyyy-mm-dd"] = None,
) -> str:
    return (
        f"# ETF Tracking Info for {ticker}\n\n"
        "当前 tushare 路径未稳定提供跟踪误差时间序列。\n"
        "可结合跟踪指数、持仓结构、净值变化做保守分析。"
    )


def get_etf_news(
    ticker: Annotated[str, "A-share ETF code"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    return (
        f"# ETF News for {ticker}\n\n"
        f"当前 tushare ETF 路径未提供 {start_date} 至 {end_date} 的专项新闻接口。\n"
        "后续可回退到 ETF 所跟踪指数、行业主题或商品相关新闻。"
    )
