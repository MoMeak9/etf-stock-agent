"""A-share stock data fetching via baostock (free, no token required)."""

import logging
import os
import time
from datetime import datetime
from typing import Annotated

import pandas as pd

from .config import get_config
from .stockstats_utils import _clean_dataframe

logger = logging.getLogger(__name__)


class BaoStockError(Exception):
    """Raised when baostock fails, triggering fallback in route_to_vendor."""
    pass


def _get_bs():
    """Import and return the baostock module."""
    try:
        import baostock as bs
        return bs
    except ImportError:
        raise BaoStockError(
            "baostock is not installed. Install with: pip install baostock"
        )


def _to_bs_code(symbol: str) -> str:
    """Convert 6-digit symbol to baostock code format (e.g., sh.600519, sz.000858)."""
    if not symbol:
        raise BaoStockError("Empty symbol provided")
    s = str(symbol).strip()
    if s.startswith(("6", "9")):
        return f"sh.{s}"
    return f"sz.{s}"


def _request_delay():
    """Add delay between requests."""
    config = get_config()
    interval = config.get("cn_request_interval", 0.3)
    time.sleep(interval)


def _bs_query_to_df(rs) -> pd.DataFrame:
    """Convert a baostock query result set to a DataFrame."""
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    if not data_list:
        return pd.DataFrame()
    return pd.DataFrame(data_list, columns=rs.fields)


def _get_year_quarter(curr_date: str):
    """Parse curr_date to determine the most recent reporting year and quarter."""
    try:
        dt = datetime.strptime(curr_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        dt = datetime.now()
    year = dt.year
    quarter = (dt.month - 1) // 3 + 1
    # Financial reports lag by ~1 quarter, so look at the previous quarter
    quarter -= 1
    if quarter <= 0:
        quarter = 4
        year -= 1
    return year, quarter


def get_stock_data(
    symbol: Annotated[str, "A-share stock code, e.g. 600519"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Fetch A-share daily OHLCV data via baostock."""
    try:
        bs = _get_bs()
        bs_code = _to_bs_code(symbol)

        lg = bs.login()
        if lg.error_code != '0':
            return f"BaoStock login failed: {lg.error_msg}"

        try:
            _request_delay()

            rs = bs.query_history_k_data_plus(
                code=bs_code,
                fields="date,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2",  # 前复权
            )

            if rs.error_code != '0':
                return f"BaoStock query error for {symbol}: {rs.error_msg}"

            df = _bs_query_to_df(rs)
        finally:
            bs.logout()

        if df.empty:
            raise BaoStockError(
                f"No data found for A-share '{symbol}' between {start_date} and {end_date}"
            )

        # Rename to standard format
        df = df.rename(columns={
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        })

        # Convert numeric columns
        for col in ["Open", "High", "Low", "Close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").round(2)
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")

        # Sort by date ascending
        df = df.sort_values("Date")

        output_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        available = [c for c in output_cols if c in df.columns]
        df_out = df[available].set_index("Date")

        csv_string = df_out.to_csv()

        header = f"# Stock data for {symbol} from {start_date} to {end_date}\n"
        header += f"# Market: A-share (CNY) [baostock]\n"
        header += f"# Total records: {len(df_out)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except BaoStockError:
        raise
    except Exception as e:
        raise BaoStockError(f"baostock error for {symbol}: {e}")


def get_indicators(
    symbol: Annotated[str, "A-share stock code"],
    indicator: Annotated[str, "technical indicator name"],
    curr_date: Annotated[str, "current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
) -> str:
    """Get technical indicators via baostock + stockstats."""
    from stockstats import wrap
    from dateutil.relativedelta import relativedelta

    try:
        bs = _get_bs()
        bs_code = _to_bs_code(symbol)

        today = pd.Timestamp.today()
        start_date = (today - pd.DateOffset(years=15)).strftime("%Y-%m-%d")
        end_date_str = today.strftime("%Y-%m-%d")

        config = get_config()
        cache_dir = config.get("data_cache_dir", "data_cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(
            cache_dir, f"{symbol}-BaoStock-data-{start_date}-{end_date_str}.csv"
        )

        if os.path.exists(cache_file):
            data = pd.read_csv(cache_file, on_bad_lines="skip")
        else:
            lg = bs.login()
            if lg.error_code != '0':
                raise BaoStockError(f"BaoStock login failed: {lg.error_msg}")

            try:
                _request_delay()

                rs = bs.query_history_k_data_plus(
                    code=bs_code,
                    fields="date,open,high,low,close,volume",
                    start_date=start_date,
                    end_date=end_date_str,
                    frequency="d",
                    adjustflag="2",
                )

                if rs.error_code != '0':
                    raise BaoStockError(f"BaoStock query error: {rs.error_msg}")

                data = _bs_query_to_df(rs)
            finally:
                bs.logout()

            if data.empty:
                raise BaoStockError(f"No historical data for {symbol}")

            data = data.rename(columns={
                "date": "Date", "open": "Open", "high": "High",
                "low": "Low", "close": "Close", "volume": "Volume",
            })
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                if col in data.columns:
                    data[col] = pd.to_numeric(data[col], errors="coerce")
            data = data.sort_values("Date")
            data.to_csv(cache_file, index=False)

        data = _clean_dataframe(data)
        df = wrap(data)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        df[indicator]

        indicator_data = {}
        for _, row in df.iterrows():
            date_str = row["Date"]
            val = row[indicator]
            indicator_data[date_str] = "N/A" if pd.isna(val) else str(val)

        curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        before = curr_date_dt - relativedelta(days=look_back_days)

        ind_string = ""
        current_dt = curr_date_dt
        while current_dt >= before:
            date_str = current_dt.strftime("%Y-%m-%d")
            value = indicator_data.get(date_str, "N/A: Not a trading day")
            ind_string += f"{date_str}: {value}\n"
            current_dt = current_dt - relativedelta(days=1)

        return f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n{ind_string}"

    except BaoStockError:
        raise
    except Exception as e:
        raise BaoStockError(f"baostock indicator error for {symbol}: {e}")


def get_fundamentals(
    ticker: Annotated[str, "A-share stock code"],
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get A-share fundamentals (valuation data) via baostock."""
    try:
        bs = _get_bs()
        bs_code = _to_bs_code(ticker)

        # Use curr_date or default to recent 5 days
        if curr_date:
            start_date = curr_date
            end_date = curr_date
        else:
            end_date = datetime.now().strftime("%Y-%m-%d")
            from datetime import timedelta
            start_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")

        lg = bs.login()
        if lg.error_code != '0':
            return f"BaoStock login failed: {lg.error_msg}"

        try:
            _request_delay()

            # Query valuation indicators: peTTM, pbMRQ, psTTM, pcfNcfTTM
            rs = bs.query_history_k_data_plus(
                code=bs_code,
                fields="date,code,close,peTTM,pbMRQ,psTTM,pcfNcfTTM",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="3",  # 不复权
            )

            if rs.error_code != '0':
                return f"BaoStock query error for {ticker}: {rs.error_msg}"

            df = _bs_query_to_df(rs)
        finally:
            bs.logout()

        if df.empty:
            raise BaoStockError(f"No fundamentals data for A-share '{ticker}'")

        # Take the latest row
        latest = df.iloc[-1]
        lines = []
        field_labels = {
            "date": "trade_date",
            "code": "bs_code",
            "close": "close",
            "peTTM": "pe_ttm",
            "pbMRQ": "pb_mrq",
            "psTTM": "ps_ttm",
            "pcfNcfTTM": "pcf_ttm",
        }
        for col in df.columns:
            val = latest.get(col, None) if hasattr(latest, 'get') else latest[col]
            if val is not None and str(val) != "" and str(val) != "nan":
                label = field_labels.get(col, col)
                lines.append(f"{label}: {val}")

        header = f"# Company Fundamentals for {ticker} (A-share, CNY) [baostock]\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + "\n".join(lines)

    except BaoStockError:
        raise
    except Exception as e:
        raise BaoStockError(f"baostock fundamentals error for {ticker}: {e}")


def _get_financial_report(ticker: str, year: int, quarter: int, query_func_name: str, report_name: str) -> str:
    """Generic helper to fetch a quarterly financial report from baostock."""
    try:
        bs = _get_bs()
        bs_code = _to_bs_code(ticker)

        lg = bs.login()
        if lg.error_code != '0':
            return f"BaoStock login failed: {lg.error_msg}"

        try:
            _request_delay()

            query_func = getattr(bs, query_func_name)
            rs = query_func(code=bs_code, year=year, quarter=quarter)

            if rs.error_code != '0':
                return f"BaoStock query error for {ticker} {report_name}: {rs.error_msg}"

            df = _bs_query_to_df(rs)
        finally:
            bs.logout()

        if df.empty:
            # Try the previous quarter
            prev_quarter = quarter - 1
            prev_year = year
            if prev_quarter <= 0:
                prev_quarter = 4
                prev_year -= 1

            lg = bs.login()
            if lg.error_code != '0':
                raise BaoStockError(f"No {report_name} data for A-share '{ticker}'")

            try:
                _request_delay()
                rs = query_func(code=bs_code, year=prev_year, quarter=prev_quarter)
                if rs.error_code != '0':
                    raise BaoStockError(f"No {report_name} data for A-share '{ticker}'")
                df = _bs_query_to_df(rs)
            finally:
                bs.logout()

            if df.empty:
                raise BaoStockError(f"No {report_name} data for A-share '{ticker}'")

        header = f"# {report_name} for {ticker} (A-share, CNY) [baostock]\n"
        header += f"# Period: {year}Q{quarter}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + df.to_csv(index=False)

    except BaoStockError:
        raise
    except Exception as e:
        raise BaoStockError(f"baostock {report_name} error for {ticker}: {e}")


def get_balance_sheet(
    ticker: Annotated[str, "A-share stock code"],
    freq: Annotated[str, "frequency: annual or quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get A-share balance sheet (solvency data) via baostock."""
    year, quarter = _get_year_quarter(curr_date)
    return _get_financial_report(ticker, year, quarter, "query_balance_data", "Balance Sheet")


def get_cashflow(
    ticker: Annotated[str, "A-share stock code"],
    freq: Annotated[str, "frequency: annual or quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get A-share cash flow via baostock."""
    year, quarter = _get_year_quarter(curr_date)
    return _get_financial_report(ticker, year, quarter, "query_cash_flow_data", "Cash Flow")


def get_income_statement(
    ticker: Annotated[str, "A-share stock code"],
    freq: Annotated[str, "frequency: annual or quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get A-share income statement (profitability data) via baostock."""
    year, quarter = _get_year_quarter(curr_date)
    return _get_financial_report(ticker, year, quarter, "query_profit_data", "Income Statement")


def get_insider_transactions(
    ticker: Annotated[str, "A-share stock code"],
) -> str:
    """Get insider transactions - not supported by baostock."""
    return (
        f"A 股 {ticker} 暂无内部交易数据。\n"
        f"注: BaoStock 不提供股东增减持数据接口。"
    )
