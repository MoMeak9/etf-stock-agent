"""A-share ETF data access via akshare."""

from datetime import datetime
from typing import Annotated

import pandas as pd

from .config import bypass_proxy_for_cn, restore_proxy

ETF_COLUMN_MAP = {
    "日期": "Date",
    "开盘": "Open",
    "收盘": "Close",
    "最高": "High",
    "最低": "Low",
    "成交量": "Volume",
    "成交额": "Amount",
    "振幅": "Amplitude",
    "涨跌幅": "Change_Pct",
    "涨跌额": "Change_Amt",
    "换手率": "Turnover",
}


def _normalize_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=ETF_COLUMN_MAP)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    if "Volume" in df.columns:
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce") * 100
    for column in ("Open", "High", "Low", "Close"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").round(4)
    return df


def fetch_etf_daily(symbol: str, start_date: str, end_date: str):
    """Fetch structured daily ETF market data from akshare."""
    import akshare as ak

    saved = bypass_proxy_for_cn()
    try:
        df = ak.fund_etf_hist_em(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
        return _normalize_price_frame(df) if df is not None else df
    finally:
        restore_proxy(saved)


def fetch_etf_basic(symbol: str):
    """Fetch structured ETF basic metadata from akshare."""
    import akshare as ak

    saved = bypass_proxy_for_cn()
    try:
        funds = ak.fund_name_em()
        if funds is None or funds.empty:
            return funds
        return funds[funds["基金代码"] == symbol]
    finally:
        restore_proxy(saved)


def fetch_etf_nav(symbol: str):
    """Fetch structured ETF NAV data from akshare."""
    import akshare as ak

    saved = bypass_proxy_for_cn()
    try:
        return ak.fund_etf_fund_info_em(fund=symbol)
    finally:
        restore_proxy(saved)


def fetch_etf_portfolio(symbol: str, year: str):
    """Fetch structured ETF portfolio holdings from akshare."""
    import akshare as ak

    saved = bypass_proxy_for_cn()
    try:
        return ak.fund_portfolio_hold_em(symbol=symbol, date=year)
    finally:
        restore_proxy(saved)


def get_etf_price_data(
    symbol: Annotated[str, "A-share ETF code"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    import akshare as ak

    saved = bypass_proxy_for_cn()
    try:
        df = ak.fund_etf_hist_em(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
        if df is None or df.empty:
            return f"# ETF Price Data\n\n未获取到 {symbol} 在 {start_date} 至 {end_date} 的 ETF 行情数据。"

        df = _normalize_price_frame(df)
        output_cols = [c for c in ("Date", "Open", "High", "Low", "Close", "Volume") if c in df.columns]
        return (
            f"# ETF Price Data for {symbol}\n"
            f"# Source: akshare\n\n"
            + df[output_cols].to_csv(index=False)
        )
    finally:
        restore_proxy(saved)


def get_etf_indicators(
    symbol: Annotated[str, "A-share ETF code"],
    indicator: Annotated[str, "technical indicator name"],
    curr_date: Annotated[str, "current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
) -> str:
    from .stockstats_utils import _clean_dataframe
    from stockstats import wrap
    from dateutil.relativedelta import relativedelta

    end_date = pd.Timestamp(curr_date)
    start_date = (end_date - pd.DateOffset(days=max(look_back_days + 90, 180))).strftime("%Y-%m-%d")
    raw = get_etf_price_data(symbol, start_date, curr_date)
    lines = [line for line in raw.splitlines() if line and not line.startswith("#")]
    if len(lines) < 2:
        return f"## {indicator} values for ETF {symbol}\n\n无可用行情数据。"

    df = pd.read_csv(pd.io.common.StringIO("\n".join(lines)))
    df = _clean_dataframe(df)
    wrapped = wrap(df)
    wrapped["Date"] = wrapped["Date"].dt.strftime("%Y-%m-%d")
    wrapped[indicator]

    before = datetime.strptime(curr_date, "%Y-%m-%d") - relativedelta(days=look_back_days)
    result_lines = []
    current_dt = datetime.strptime(curr_date, "%Y-%m-%d")
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
    import akshare as ak

    saved = bypass_proxy_for_cn()
    try:
        sections = []
        nav = ak.fund_etf_fund_info_em(fund=ticker)
        if nav is not None and not nav.empty:
            sections.append("## 近期净值数据\n" + nav.tail(30).to_csv(index=False))
        try:
            funds = ak.fund_name_em()
            matched = funds[funds["基金代码"] == ticker]
            if not matched.empty:
                sections.append("## ETF 基本信息\n" + matched.to_csv(index=False))
        except Exception:
            pass

        if not sections:
            return f"# ETF Profile for {ticker}\n\n未获取到 ETF 产品信息。"
        return f"# ETF Profile for {ticker}\n# Source: akshare\n\n" + "\n\n".join(sections)
    finally:
        restore_proxy(saved)


def get_etf_holdings(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "current date, yyyy-mm-dd"] = None,
) -> str:
    import akshare as ak

    saved = bypass_proxy_for_cn()
    try:
        year = (curr_date or datetime.now().strftime("%Y-%m-%d"))[:4]
        df = ak.fund_portfolio_hold_em(symbol=ticker, date=year)
        if df is None or df.empty:
            return f"# ETF Holdings for {ticker}\n\n未获取到 ETF 持仓数据。"
        return f"# ETF Holdings for {ticker}\n# Source: akshare\n\n" + df.head(20).to_csv(index=False)
    finally:
        restore_proxy(saved)


def get_etf_fund_flow(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "current date, yyyy-mm-dd"] = None,
) -> str:
    import akshare as ak

    saved = bypass_proxy_for_cn()
    try:
        df = ak.fund_etf_fund_info_em(fund=ticker)
        if df is None or df.empty:
            return f"# ETF Fund Flow for {ticker}\n\n未获取到 ETF 份额/净值趋势数据。"
        return (
            f"# ETF Fund Flow for {ticker}\n"
            f"# Source: akshare\n"
            f"# Note: 使用净值与份额趋势作为资金流代理指标。\n\n"
            + df.tail(60).to_csv(index=False)
        )
    finally:
        restore_proxy(saved)


def get_etf_discount_premium(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "current date, yyyy-mm-dd"] = None,
) -> str:
    return (
        f"# ETF Discount Premium for {ticker}\n\n"
        "当前 akshare 路径未稳定提供折溢价明细，后续可结合 IOPV / 二级市场价格补齐。\n"
        "请在产品分析中将该字段视为“数据有限”，避免编造具体折溢价结论。"
    )


def get_etf_tracking_info(
    ticker: Annotated[str, "A-share ETF code"],
    curr_date: Annotated[str, "current date, yyyy-mm-dd"] = None,
) -> str:
    return (
        f"# ETF Tracking Info for {ticker}\n\n"
        "当前 akshare 路径未稳定提供跟踪误差时间序列。\n"
        "请结合基金名称、跟踪指数、持仓结构和净值趋势做保守判断。"
    )


def get_etf_news(
    ticker: Annotated[str, "A-share ETF code"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    try:
        from .akshare_news import get_news

        news = get_news(ticker, start_date, end_date)
        if news:
            return f"# ETF News for {ticker}\n# Source: akshare-compatible fallback\n\n{news}"
    except Exception:
        pass

    return (
        f"# ETF News for {ticker}\n\n"
        f"未获取到 {ticker} 在 {start_date} 至 {end_date} 的 ETF 专项新闻，"
        "后续可回退到指数/主题相关新闻分析。"
    )
