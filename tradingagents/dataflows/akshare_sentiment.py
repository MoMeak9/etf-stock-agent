"""A-share social sentiment data fetching via akshare.

Provides investor sentiment data from Chinese financial platforms
(Eastmoney Guba/股吧, Xueqiu/雪球, etc.) for social media analysis.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from .config import get_config, bypass_proxy_for_cn, restore_proxy

logger = logging.getLogger(__name__)


def _request_delay():
    """Delay between requests to avoid being blocked."""
    config = get_config()
    interval = config.get("cn_request_interval", 0.3)
    time.sleep(interval)


def get_stock_sentiment(
    symbol: str,
    curr_date: str,
    look_back_days: int = 7,
) -> str:
    """
    Retrieve social media sentiment data for a Chinese A-share stock.

    Fetches investor discussion data from Eastmoney Guba (东方财富股吧),
    individual stock news, and analyst ratings.

    Args:
        symbol: Stock code (e.g. '000001', '600519')
        curr_date: Current date in yyyy-mm-dd format
        look_back_days: Number of days to look back (default 7)

    Returns:
        str: Formatted sentiment analysis data
    """
    # Normalize symbol (strip exchange suffix)
    code = symbol.strip()
    for suffix in (".SH", ".SZ", ".sh", ".sz"):
        code = code.replace(suffix, "")

    sections = []

    # 1. 东方财富股吧热帖 (Eastmoney Guba hot posts)
    guba_data = _get_guba_posts(code)
    if guba_data:
        sections.append(guba_data)

    # 2. 个股新闻 (Individual stock news for sentiment)
    news_data = _get_stock_news_sentiment(code)
    if news_data:
        sections.append(news_data)

    # 3. 机构评级 (Analyst ratings)
    rating_data = _get_analyst_ratings(code)
    if rating_data:
        sections.append(rating_data)

    # 4. 资金流向 (Capital flow - sentiment indicator)
    flow_data = _get_capital_flow(code)
    if flow_data:
        sections.append(flow_data)

    if not sections:
        return (
            f"# 社交情绪数据 - {symbol}\n\n"
            f"⚠️ 未能获取到 {symbol} 的社交情绪数据。\n"
            f"可能原因：API 限制或网络问题。\n"
            f"建议：基于已有的新闻数据和市场数据进行情绪推断分析。"
        )

    header = (
        f"# 社交情绪数据 - {symbol}\n"
        f"数据日期：{curr_date}（回溯 {look_back_days} 天）\n\n"
    )
    return header + "\n\n".join(sections)


def _get_guba_posts(code: str) -> Optional[str]:
    """获取东方财富股吧热帖。"""
    saved = bypass_proxy_for_cn()
    try:
        import akshare as ak
        _request_delay()
        df = ak.stock_comment_em(symbol=code)
        if df is None or df.empty:
            return None

        result = "## 东方财富股吧情绪\n\n"

        # 取最近记录
        if len(df) > 10:
            df = df.tail(10)

        # 格式化输出
        cols = df.columns.tolist()
        result += f"| {' | '.join(str(c) for c in cols)} |\n"
        result += f"| {' | '.join('---' for _ in cols)} |\n"
        for _, row in df.iterrows():
            result += f"| {' | '.join(str(v) for v in row.values)} |\n"

        return result

    except Exception as e:
        logger.debug(f"Guba data fetch failed for {code}: {e}")
        return None
    finally:
        restore_proxy(saved)


def _get_stock_news_sentiment(code: str) -> Optional[str]:
    """获取个股新闻用于情绪分析。"""
    saved = bypass_proxy_for_cn()
    try:
        import akshare as ak
        _request_delay()
        df = ak.stock_news_em(symbol=code)
        if df is None or df.empty:
            return None

        result = "## 近期个股新闻\n\n"

        # 取最近 10 条
        if len(df) > 10:
            df = df.head(10)

        for _, row in df.iterrows():
            title = row.get("新闻标题", row.get("title", ""))
            source = row.get("新闻来源", row.get("source", ""))
            pub_date = row.get("发布时间", row.get("publish_time", ""))
            content = row.get("新闻内容", row.get("content", ""))
            if content and len(str(content)) > 200:
                content = str(content)[:200] + "..."
            result += f"- **{title}** ({source}, {pub_date})\n"
            if content:
                result += f"  {content}\n"

        return result

    except Exception as e:
        logger.debug(f"Stock news fetch failed for {code}: {e}")
        return None
    finally:
        restore_proxy(saved)


def _get_analyst_ratings(code: str) -> Optional[str]:
    """获取机构评级数据。"""
    saved = bypass_proxy_for_cn()
    try:
        import akshare as ak
        _request_delay()
        df = ak.stock_comment_detail_zlkp_jgcyd_em(symbol=code)
        if df is None or df.empty:
            return None

        result = "## 机构评级\n\n"
        if len(df) > 10:
            df = df.tail(10)

        cols = df.columns.tolist()
        result += f"| {' | '.join(str(c) for c in cols)} |\n"
        result += f"| {' | '.join('---' for _ in cols)} |\n"
        for _, row in df.iterrows():
            result += f"| {' | '.join(str(v) for v in row.values)} |\n"

        return result

    except Exception as e:
        logger.debug(f"Analyst ratings fetch failed for {code}: {e}")
        return None
    finally:
        restore_proxy(saved)


def _get_capital_flow(code: str) -> Optional[str]:
    """获取资金流向数据（情绪指标）。"""
    saved = bypass_proxy_for_cn()
    try:
        import akshare as ak
        _request_delay()
        df = ak.stock_individual_fund_flow(stock=code, market="sh" if code.startswith("6") else "sz")
        if df is None or df.empty:
            return None

        result = "## 资金流向（情绪指标）\n\n"
        # 取最近 5 天
        if len(df) > 5:
            df = df.tail(5)

        cols = df.columns.tolist()
        result += f"| {' | '.join(str(c) for c in cols)} |\n"
        result += f"| {' | '.join('---' for _ in cols)} |\n"
        for _, row in df.iterrows():
            result += f"| {' | '.join(str(v) for v in row.values)} |\n"

        return result

    except Exception as e:
        logger.debug(f"Capital flow fetch failed for {code}: {e}")
        return None
    finally:
        restore_proxy(saved)
