"""A-share stock data fetching via tushare (fallback vendor for akshare)."""

import os
import time
from datetime import datetime
from typing import Annotated

import pandas as pd

from .config import get_config
from .stockstats_utils import _clean_dataframe

# Maximum number of trading days to search backwards when current date has no data
_DATE_FALLBACK_DAYS = 10


class TushareError(Exception):
    """Raised when tushare fails, triggering fallback in route_to_vendor."""
    pass


def _get_tushare_api():
    """Get tushare pro API instance."""
    config = get_config()
    token = config.get("tushare_token", "") or os.getenv("TUSHARE_TOKEN", "")
    if not token:
        raise TushareError(
            "TUSHARE_TOKEN not configured. Set it in config or as environment variable."
        )
    try:
        import tushare as ts
        ts.set_token(token)
        return ts.pro_api()
    except ImportError:
        raise TushareError(
            "tushare is not installed. Install with: pip install tushare"
        )
    except Exception as e:
        raise TushareError(f"Failed to initialize tushare API: {e}")


def _to_ts_code(symbol: str) -> str:
    """Convert 6-digit symbol to tushare ts_code format (e.g., 600519.SH)."""
    if not symbol:
        raise TushareError("Empty symbol provided")
    if symbol[0] in ("6", "9"):
        return f"{symbol}.SH"
    return f"{symbol}.SZ"


def _request_delay():
    """Add delay between requests."""
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


def _fallback_to_previous_trading_day(pro, ts_code: str, ref_date: str) -> pd.DataFrame:
    """When ref_date has no data, search backwards up to _DATE_FALLBACK_DAYS trading days.

    Returns the daily DataFrame for the most recent available date, or empty DataFrame.
    """
    ref_ts = ref_date.replace("-", "")
    start_ts = (
        pd.Timestamp(ref_ts) - pd.DateOffset(days=_DATE_FALLBACK_DAYS + 5)
    ).strftime("%Y%m%d")

    _request_delay()
    df = pro.daily(ts_code=ts_code, start_date=start_ts, end_date=ref_ts)
    return df


def get_stock_data(
    symbol: Annotated[str, "A-share stock code, e.g. 600519"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Fetch A-share daily OHLCV data via tushare."""
    try:
        pro = _get_tushare_api()
        ts_code = _to_ts_code(symbol)
        ts_start = start_date.replace("-", "")
        ts_end = end_date.replace("-", "")

        _request_delay()

        df = pro.daily(ts_code=ts_code, start_date=ts_start, end_date=ts_end)

        # If no data and querying a narrow window, try falling back to earlier dates
        # (handles: market still open, non-trading day, or data not yet published)
        if (df is None or df.empty) and _is_narrow_range(start_date, end_date):
            df = _fallback_to_previous_trading_day(pro, ts_code, end_date)

        if df is None or df.empty:
            raise TushareError(
                f"No data found for A-share '{symbol}' between {start_date} and {end_date}"
            )

        # Rename to standard format
        df = df.rename(columns={
            "trade_date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "vol": "Volume",
        })

        # Format Date
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")

        # Volume: tushare unit is 手 (100 shares)
        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce") * 100

        # Round prices
        for col in ["Open", "High", "Low", "Close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

        # Sort by date ascending
        df = df.sort_values("Date")

        output_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        available = [c for c in output_cols if c in df.columns]
        df_out = df[available].set_index("Date")

        csv_string = df_out.to_csv()

        header = f"# Stock data for {symbol} from {start_date} to {end_date}\n"
        header += f"# Market: A-share (CNY) [tushare]\n"
        header += f"# Total records: {len(df_out)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

        return header + csv_string

    except TushareError:
        raise
    except Exception as e:
        raise TushareError(f"tushare error for {symbol}: {e}")


def get_indicators(
    symbol: Annotated[str, "A-share stock code"],
    indicator: Annotated[str, "technical indicator name"],
    curr_date: Annotated[str, "current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
) -> str:
    """Get technical indicators via tushare + stockstats."""
    from stockstats import wrap
    from dateutil.relativedelta import relativedelta

    try:
        pro = _get_tushare_api()
        ts_code = _to_ts_code(symbol)

        today = pd.Timestamp.today()
        start_date = (today - pd.DateOffset(years=15)).strftime("%Y%m%d")
        end_date_str = today.strftime("%Y%m%d")

        config = get_config()
        cache_dir = config.get("data_cache_dir", "data_cache")
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(
            cache_dir, f"{symbol}-Tushare-data-{start_date}-{end_date_str}.csv"
        )

        if os.path.exists(cache_file):
            data = pd.read_csv(cache_file, on_bad_lines="skip")
        else:
            _request_delay()
            data = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date_str)
            if data is None or data.empty:
                raise TushareError(f"No historical data for {symbol}")

            data = data.rename(columns={
                "trade_date": "Date", "open": "Open", "high": "High",
                "low": "Low", "close": "Close", "vol": "Volume",
            })
            data["Date"] = pd.to_datetime(data["Date"]).dt.strftime("%Y-%m-%d")
            data["Volume"] = pd.to_numeric(data["Volume"], errors="coerce") * 100
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

    except TushareError:
        raise
    except Exception as e:
        raise TushareError(f"tushare indicator error for {symbol}: {e}")


def _call_with_retry(fn, *args, max_retries: int = 3, **kwargs):
    """Call a tushare API function with retry on connection errors."""
    import requests
    last_exc = None
    for attempt in range(max_retries):
        try:
            return fn(*args, **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
            last_exc = e
            wait = 2 ** attempt  # 1s, 2s, 4s
            time.sleep(wait)
        except Exception:
            raise
    raise last_exc


def get_fundamentals(
    ticker: Annotated[str, "A-share stock code"],
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get A-share fundamentals via tushare.

    Combines daily_basic (market valuation metrics) with fina_indicator
    (financial ratios, ref: https://tushare.pro/document/2?doc_id=112).
    """
    try:
        pro = _get_tushare_api()
        ts_code = _to_ts_code(ticker)

        # Determine reference date (YYYYMMDD)
        if curr_date:
            ref_date = curr_date.replace("-", "")
        else:
            ref_date = datetime.now().strftime("%Y%m%d")

        # For daily_basic, look back up to 10 trading days to find the latest record
        start_date_basic = (
            pd.Timestamp(ref_date) - pd.DateOffset(days=14)
        ).strftime("%Y%m%d")

        _request_delay()
        df_basic = None
        try:
            df_basic = _call_with_retry(
                pro.daily_basic,
                ts_code=ts_code,
                start_date=start_date_basic,
                end_date=ref_date,
                fields="ts_code,trade_date,turnover_rate,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_mv,circ_mv",
            )
        except Exception:
            pass  # handled below; fina_indicator may still succeed

        _request_delay()
        df_daily = None
        try:
            df_daily = _call_with_retry(
                pro.daily,
                ts_code=ts_code,
                start_date=start_date_basic,
                end_date=ref_date,
            )
        except Exception:
            pass

        # fina_indicator: get latest 4 quarterly reports (doc_id=112)
        # Limit to last 2 years to avoid pulling entire history and timing out
        start_date_fina = (
            pd.Timestamp(ref_date) - pd.DateOffset(years=2)
        ).strftime("%Y%m%d")
        _request_delay()
        df_fina = None
        try:
            df_fina = _call_with_retry(
                pro.fina_indicator,
                ts_code=ts_code,
                start_date=start_date_fina,
                end_date=ref_date,
                fields=(
                    "ts_code,ann_date,end_date,"
                    "eps,dt_eps,bps,roe,roe_waa,roe_dt,roa,roic,"
                    "grossprofit_margin,netprofit_margin,"
                    "current_ratio,quick_ratio,cash_ratio,"
                    "debt_to_assets,assets_to_eqt,"
                    "ocf_to_or,ocf_to_opincome,"
                    "ebit,ebitda,cfps"
                ),
            )
        except Exception:
            pass  # handled below

        lines = []

        # --- Market valuation from daily_basic ---
        if df_basic is not None and not df_basic.empty:
            latest_basic = df_basic.sort_values("trade_date", ascending=False).iloc[0]
            lines.append("## Market Valuation Metrics")
            field_labels = {
                "trade_date": "Trade Date",
                "turnover_rate": "Turnover Rate (%)",
                "pe": "P/E Ratio",
                "pe_ttm": "P/E TTM",
                "pb": "P/B Ratio",
                "ps": "P/S Ratio",
                "ps_ttm": "P/S TTM",
                "dv_ratio": "Dividend Yield (%)",
                "dv_ttm": "Dividend Yield TTM (%)",
                "total_mv": "Total Market Cap (CNY 10k)",
                "circ_mv": "Circulating Market Cap (CNY 10k)",
            }
            for col, label in field_labels.items():
                val = latest_basic.get(col)
                if val is not None and str(val) not in ("nan", "None", ""):
                    lines.append(f"{label}: {val}")

        if df_daily is not None and not df_daily.empty:
            latest_daily = df_daily.sort_values("trade_date", ascending=False).iloc[0]
            trade_date = latest_daily.get("trade_date")
            close_price = latest_daily.get("close")
            if trade_date is not None and str(trade_date) not in ("nan", "None", ""):
                if not lines:
                    lines.append("## Market Valuation Metrics")
                if not any(line.startswith("Trade Date:") for line in lines):
                    lines.append(f"Trade Date: {trade_date}")
            if close_price is not None and str(close_price) not in ("nan", "None", ""):
                if not lines:
                    lines.append("## Market Valuation Metrics")
                lines.append(f"Close Price: {close_price}")

        # --- Financial ratios from fina_indicator ---
        if df_fina is not None and not df_fina.empty:
            df_fina = df_fina.sort_values("end_date", ascending=False)
            latest_fina = df_fina.iloc[0]
            lines.append("")
            lines.append("## Financial Indicators (fina_indicator)")
            fina_labels = {
                "ann_date": "Announcement Date",
                "end_date": "Report Period",
                "eps": "EPS (CNY)",
                "dt_eps": "Diluted EPS (CNY)",
                "bps": "BPS (CNY)",
                "roe": "ROE (%)",
                "roe_waa": "ROE Weighted (%)",
                "roe_dt": "ROE Deducted (%)",
                "roa": "ROA (%)",
                "roic": "ROIC (%)",
                "grossprofit_margin": "Gross Profit Margin (%)",
                "netprofit_margin": "Net Profit Margin (%)",
                "current_ratio": "Current Ratio",
                "quick_ratio": "Quick Ratio",
                "cash_ratio": "Cash Ratio",
                "debt_to_assets": "Debt-to-Assets (%)",
                "assets_to_eqt": "Assets-to-Equity",
                "ocf_to_or": "OCF / Revenue",
                "ocf_to_opincome": "OCF / Operating Income",
                "ebit": "EBIT (CNY)",
                "ebitda": "EBITDA (CNY)",
                "cfps": "Cash Flow Per Share (CNY)",
            }
            for col, label in fina_labels.items():
                val = latest_fina.get(col)
                if val is not None and str(val) not in ("nan", "None", ""):
                    lines.append(f"{label}: {val}")

        if not lines:
            raise TushareError(f"No fundamentals data found for A-share '{ticker}'")

        header = f"# Company Fundamentals for {ticker} (A-share, CNY) [tushare]\n"
        header += f"# Reference Date: {curr_date or datetime.now().strftime('%Y-%m-%d')}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + "\n".join(lines)

    except TushareError:
        raise
    except Exception as e:
        raise TushareError(f"tushare fundamentals error for {ticker}: {e}")


def get_balance_sheet(
    ticker: Annotated[str, "A-share stock code"],
    freq: Annotated[str, "frequency: annual or quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get A-share balance sheet via tushare."""
    try:
        pro = _get_tushare_api()
        ts_code = _to_ts_code(ticker)
        ref_date = (curr_date or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
        start_date = (
            pd.Timestamp(ref_date) - pd.DateOffset(years=3)
        ).strftime("%Y%m%d")
        _request_delay()
        df = _call_with_retry(
            pro.balancesheet,
            ts_code=ts_code,
            start_date=start_date,
            end_date=ref_date,
        )
        if df is None or df.empty:
            raise TushareError(f"No balance sheet data for A-share '{ticker}'")
        df = df.sort_values("end_date", ascending=False)
        if len(df) > 8:
            df = df.head(8)
        header = f"# Balance Sheet for {ticker} (A-share, CNY) [tushare]\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + df.to_csv(index=False)
    except TushareError:
        raise
    except Exception as e:
        raise TushareError(f"tushare balance sheet error for {ticker}: {e}")


def get_cashflow(
    ticker: Annotated[str, "A-share stock code"],
    freq: Annotated[str, "frequency: annual or quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get A-share cash flow via tushare."""
    try:
        pro = _get_tushare_api()
        ts_code = _to_ts_code(ticker)
        ref_date = (curr_date or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
        start_date = (
            pd.Timestamp(ref_date) - pd.DateOffset(years=3)
        ).strftime("%Y%m%d")
        _request_delay()
        df = _call_with_retry(
            pro.cashflow,
            ts_code=ts_code,
            start_date=start_date,
            end_date=ref_date,
        )
        if df is None or df.empty:
            raise TushareError(f"No cash flow data for A-share '{ticker}'")
        df = df.sort_values("end_date", ascending=False)
        if len(df) > 8:
            df = df.head(8)
        header = f"# Cash Flow for {ticker} (A-share, CNY) [tushare]\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + df.to_csv(index=False)
    except TushareError:
        raise
    except Exception as e:
        raise TushareError(f"tushare cashflow error for {ticker}: {e}")


def get_income_statement(
    ticker: Annotated[str, "A-share stock code"],
    freq: Annotated[str, "frequency: annual or quarterly"] = "quarterly",
    curr_date: Annotated[str, "current date"] = None,
) -> str:
    """Get A-share income statement via tushare."""
    try:
        pro = _get_tushare_api()
        ts_code = _to_ts_code(ticker)
        ref_date = (curr_date or datetime.now().strftime("%Y-%m-%d")).replace("-", "")
        start_date = (
            pd.Timestamp(ref_date) - pd.DateOffset(years=3)
        ).strftime("%Y%m%d")
        _request_delay()
        df = _call_with_retry(
            pro.income,
            ts_code=ts_code,
            start_date=start_date,
            end_date=ref_date,
        )
        if df is None or df.empty:
            raise TushareError(f"No income statement data for A-share '{ticker}'")
        df = df.sort_values("end_date", ascending=False)
        if len(df) > 8:
            df = df.head(8)
        header = f"# Income Statement for {ticker} (A-share, CNY) [tushare]\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + df.to_csv(index=False)
    except TushareError:
        raise
    except Exception as e:
        raise TushareError(f"tushare income error for {ticker}: {e}")


def get_insider_transactions(
    ticker: Annotated[str, "A-share stock code"],
) -> str:
    """Get A-share shareholder trading via tushare."""
    try:
        pro = _get_tushare_api()
        ts_code = _to_ts_code(ticker)
        _request_delay()
        df = pro.stk_holdertrade(ts_code=ts_code)
        if df is None or df.empty:
            return (
                f"A 股 {ticker} 暂无近期股东增减持数据。\n"
                f"注: A 股市场没有类似美股的内部交易披露制度。"
            )
        if len(df) > 20:
            df = df.head(20)
        header = f"# Shareholder Trades for {ticker} (A-share, CNY) [tushare]\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        return header + df.to_csv(index=False)
    except TushareError:
        raise
    except Exception as e:
        raise TushareError(f"tushare insider error for {ticker}: {e}")
