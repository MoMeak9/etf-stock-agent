"""A-share stock data fetching via akshare, with output format aligned to yfinance."""

import os
import time
from datetime import datetime
from typing import Annotated

import pandas as pd
from stockstats import wrap

from .config import get_config, bypass_proxy_for_cn, restore_proxy
from .stockstats_utils import _clean_dataframe

# Maximum number of calendar days to search backwards when current date has no data
_DATE_FALLBACK_DAYS = 10

# Chinese → English column name mapping
COLUMN_MAP = {
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


def _normalize_akshare_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize akshare DataFrame to yfinance-compatible format."""
    # Rename Chinese columns to English
    df = df.rename(columns=COLUMN_MAP)

    # Volume: akshare unit is "手" (lot = 100 shares), convert to shares
    if "Volume" in df.columns:
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce") * 100

    # Ensure Date column is string in YYYY-MM-DD format
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")

    # Round price columns to 2 decimal places
    price_cols = ["Open", "High", "Low", "Close"]
    for col in price_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

    return df


def _request_delay():
    """Add delay between requests to avoid being blocked."""
    config = get_config()
    interval = config.get("cn_request_interval", 0.3)
    time.sleep(interval)


def _is_narrow_range(start_date: str, end_date: str, max_days: int = 3) -> bool:
    """Check if date range is narrow enough to warrant fallback."""
    try:
        s = datetime.strptime(start_date, "%Y-%m-%d")
        e = datetime.strptime(end_date, "%Y-%m-%d")
        return (e - s).days <= max_days
    except ValueError:
        return False


def _retry_call(func, *args, max_retries=2, base_delay=1.0, **kwargs):
    """Retry an akshare API call with proxy bypass and exponential backoff."""
    saved_proxy = bypass_proxy_for_cn()
    try:
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    time.sleep(base_delay * (2 ** (attempt - 1)))
                    _request_delay()
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                if any(kw in err_str for kw in ["proxy", "connection", "timeout", "retries exceeded", "remote end closed"]):
                    continue
                raise
        raise last_error
    finally:
        restore_proxy(saved_proxy)


def get_stock_data(
    symbol: Annotated[str, "A-share stock code, e.g. 600519"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Fetch A-share daily OHLCV data via akshare.

    Output format matches get_YFin_data_online() for compatibility.
    """
    import akshare as ak

    saved_proxy = bypass_proxy_for_cn()
    try:
        # Validate dates
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")

        # akshare expects YYYYMMDD format
        ak_start = start_date.replace("-", "")
        ak_end = end_date.replace("-", "")

        _request_delay()

        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=ak_start,
            end_date=ak_end,
            adjust="qfq",
        )

        # If no data and querying a narrow window, try falling back to earlier dates
        if (df is None or df.empty) and _is_narrow_range(start_date, end_date):
            fallback_start = (
                datetime.strptime(end_date, "%Y-%m-%d")
                - pd.DateOffset(days=_DATE_FALLBACK_DAYS + 5)
            ).strftime("%Y%m%d")
            _request_delay()
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=fallback_start,
                end_date=ak_end,
                adjust="qfq",
            )

        if df is None or df.empty:
            raise Exception(
                f"No data found for A-share '{symbol}' between {start_date} and {end_date}"
            )

        df = _normalize_akshare_df(df)

        # Select only the standard OHLCV columns for output
        output_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        available = [c for c in output_cols if c in df.columns]
        df_out = df[available].copy()
        df_out = df_out.set_index("Date") if "Date" in df_out.columns else df_out

        csv_string = df_out.to_csv()

        header = f"# Stock data for {symbol} from {start_date} to {end_date}\n"
        header += f"# Market: A-share (CNY)\n"
        header += f"# Total records: {len(df_out)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        raise
    finally:
        restore_proxy(saved_proxy)


def _fetch_and_cache_cn_data(symbol: str) -> pd.DataFrame:
    """
    Fetch 15 years of A-share daily data with local caching.

    Cache file: {symbol}-AKShare-data-{start}-{end}.csv
    """
    import akshare as ak

    config = get_config()
    cache_dir = config.get("data_cache_dir", "data_cache")
    os.makedirs(cache_dir, exist_ok=True)

    today = pd.Timestamp.today()
    start_date = today - pd.DateOffset(years=15)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = today.strftime("%Y-%m-%d")

    cache_file = os.path.join(
        cache_dir, f"{symbol}-AKShare-data-{start_str}-{end_str}.csv"
    )

    if os.path.exists(cache_file):
        data = pd.read_csv(cache_file, on_bad_lines="skip")
    else:
        saved_proxy = bypass_proxy_for_cn()
        try:
            _request_delay()

            ak_start = start_date.strftime("%Y%m%d")
            ak_end = today.strftime("%Y%m%d")

            data = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=ak_start,
                end_date=ak_end,
                adjust="qfq",
            )

            if data is None or data.empty:
                raise Exception(f"No historical data available for A-share {symbol}")

            data = _normalize_akshare_df(data)
            data.to_csv(cache_file, index=False)
        finally:
            restore_proxy(saved_proxy)

    return data


def get_indicators(
    symbol: Annotated[str, "A-share stock code"],
    indicator: Annotated[str, "technical indicator name, e.g. rsi, macd"],
    curr_date: Annotated[str, "current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
) -> str:
    """
    Get technical indicators for A-share stock, reusing stockstats logic.

    Supports the same indicator set as US stocks:
    close_50_sma, close_200_sma, close_10_ema, macd, macds, macdh,
    rsi, boll, boll_ub, boll_lb, atr, vwma, mfi
    """
    from dateutil.relativedelta import relativedelta

    best_ind_params = {
        "close_50_sma": "50 SMA: 中期趋势指标。用于识别趋势方向和动态支撑/阻力。",
        "close_200_sma": "200 SMA: 长期趋势基准。用于确认整体市场趋势。",
        "close_10_ema": "10 EMA: 短期响应均线。用于捕捉快速动量变化。",
        "macd": "MACD: 通过EMA差值计算动量。关注交叉和背离信号。",
        "macds": "MACD信号线: MACD线的EMA平滑。用于触发交易信号。",
        "macdh": "MACD柱状图: MACD线与信号线的差值。用于判断动量强度。",
        "rsi": "RSI: 衡量超买/超卖状态。70以上超买，30以下超卖。A股中需结合涨跌停考虑。",
        "boll": "布林带中轨: 20日SMA。作为价格运动的动态基准。",
        "boll_ub": "布林带上轨: 中轨上方2个标准差。可能的超买区域。",
        "boll_lb": "布林带下轨: 中轨下方2个标准差。可能的超卖区域。",
        "atr": "ATR: 平均真实波幅，衡量波动率。用于设置止损和仓位管理。",
        "vwma": "VWMA: 成交量加权移动均线。结合量价验证趋势。",
        "mfi": "MFI: 资金流量指标，结合价格和成交量衡量买卖压力。80以上超买，20以下超卖。",
    }

    if indicator not in best_ind_params:
        raise ValueError(
            f"Indicator {indicator} is not supported. Choose from: {list(best_ind_params.keys())}"
        )

    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    try:
        data = _fetch_and_cache_cn_data(symbol)
        data = _clean_dataframe(data)
        df = wrap(data)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

        # Calculate indicator for all dates at once
        df[indicator]

        # Build date→value mapping
        indicator_data = {}
        for _, row in df.iterrows():
            date_str = row["Date"]
            val = row[indicator]
            if pd.isna(val):
                indicator_data[date_str] = "N/A"
            else:
                indicator_data[date_str] = str(val)

        # Generate output for the lookback window
        ind_string = ""
        current_dt = curr_date_dt
        while current_dt >= before:
            date_str = current_dt.strftime("%Y-%m-%d")
            value = indicator_data.get(
                date_str, "N/A: Not a trading day (weekend or holiday)"
            )
            ind_string += f"{date_str}: {value}\n"
            current_dt = current_dt - relativedelta(days=1)

    except Exception as e:
        raise

    result_str = (
        f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
        + ind_string
        + "\n\n"
        + best_ind_params.get(indicator, "")
    )

    return result_str


def get_fundamentals(
    ticker: Annotated[str, "A-share stock code"],
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get A-share company fundamentals overview via akshare."""
    import akshare as ak

    try:
        _request_delay()
        df = _retry_call(ak.stock_individual_info_em, symbol=ticker)

        if df is None or df.empty:
            raise Exception(f"No fundamentals data found for A-share '{ticker}'")

        # Convert to key-value format
        lines = []
        for _, row in df.iterrows():
            item = row.get("item", row.iloc[0]) if len(row) > 0 else ""
            value = row.get("value", row.iloc[1]) if len(row) > 1 else ""
            lines.append(f"{item}: {value}")

        header = f"# Company Fundamentals for {ticker} (A-share, CNY)\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + "\n".join(lines)

    except Exception as e:
        raise


def get_balance_sheet(
    ticker: Annotated[str, "A-share stock code"],
    freq: Annotated[str, "frequency: annual or quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get A-share balance sheet data via akshare."""
    import akshare as ak

    try:
        _request_delay()
        df = _retry_call(ak.stock_balance_sheet_by_report_em, symbol=ticker)

        if df is None or df.empty:
            raise Exception(f"No balance sheet data found for A-share '{ticker}'")

        # Limit to recent reports
        if len(df) > 8:
            df = df.head(8)

        csv_string = df.to_csv(index=False)

        header = f"# Balance Sheet for {ticker} (A-share, CNY)\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        raise


def get_cashflow(
    ticker: Annotated[str, "A-share stock code"],
    freq: Annotated[str, "frequency: annual or quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get A-share cash flow statement via akshare."""
    import akshare as ak

    try:
        _request_delay()
        df = _retry_call(ak.stock_cash_flow_sheet_by_report_em, symbol=ticker)

        if df is None or df.empty:
            raise Exception(f"No cash flow data found for A-share '{ticker}'")

        if len(df) > 8:
            df = df.head(8)

        csv_string = df.to_csv(index=False)

        header = f"# Cash Flow Statement for {ticker} (A-share, CNY)\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        raise


def get_income_statement(
    ticker: Annotated[str, "A-share stock code"],
    freq: Annotated[str, "frequency: annual or quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get A-share income statement via akshare."""
    import akshare as ak

    try:
        _request_delay()
        df = _retry_call(ak.stock_profit_sheet_by_report_em, symbol=ticker)

        if df is None or df.empty:
            raise Exception(f"No income statement data found for A-share '{ticker}'")

        if len(df) > 8:
            df = df.head(8)

        csv_string = df.to_csv(index=False)

        header = f"# Income Statement for {ticker} (A-share, CNY)\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        raise


def get_insider_transactions(
    ticker: Annotated[str, "A-share stock code"],
) -> str:
    """
    Get A-share major shareholder trading activity.

    Note: A-shares don't have direct insider transaction data like US markets.
    Returns block trade (大宗交易) data instead.
    """
    import akshare as ak

    try:
        if not ticker:
            return "A 股代码为空，无法获取大宗交易数据。"
        _request_delay()
        exchange = "SH" if ticker[0] in ("6", "9") else "SZ"
        full_code = f"{exchange}{ticker}"
        df = ak.stock_dzjy_mdetail(symbol=full_code)

        if df is None or df.empty:
            return (
                f"A 股 {ticker} 暂无近期大宗交易数据。\n"
                f"注: A 股市场没有类似美股的内部交易披露制度，"
                f"请参考大股东增减持公告获取相关信息。"
            )

        if len(df) > 20:
            df = df.head(20)

        csv_string = df.to_csv(index=False)

        header = f"# Block Trades (大宗交易) for {ticker} (A-share, CNY)\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except Exception as e:
        return (
            f"A 股 {ticker} 大宗交易数据获取失败: {str(e)}\n"
            f"注: A 股市场没有类似美股的内部交易披露制度，"
            f"请参考大股东增减持公告获取相关信息。"
        )
