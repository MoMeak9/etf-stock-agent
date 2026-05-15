"""A-share Chinese financial news fetching via akshare."""

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

from .config import get_config, bypass_proxy_for_cn, restore_proxy


def _request_delay():
    """Add delay between requests to avoid being blocked."""
    config = get_config()
    interval = config.get("cn_request_interval", 0.3)
    time.sleep(interval)


def _retry_call(func, *args, max_retries=2, base_delay=2.0, **kwargs):
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
                if any(kw in err_str for kw in ["rate limit", "too many requests", "proxy", "connection", "timeout", "retries exceeded"]):
                    continue
                raise
        raise last_error
    finally:
        restore_proxy(saved_proxy)


def get_news(
    ticker: str,
    start_date: str,
    end_date: str,
) -> str:
    """
    Retrieve news for a specific A-share stock via akshare (东方财富).

    Args:
        ticker: A-share stock code (e.g., "600519")
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        Formatted markdown string containing news articles
    """
    import akshare as ak

    try:
        _request_delay()
        df = _retry_call(ak.stock_news_em, symbol=ticker)

        if df is None or df.empty:
            return f"{ticker} 在 {start_date} 至 {end_date} 期间没有相关新闻"

        # Parse date range for filtering
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        news_str = ""
        filtered_count = 0

        for _, row in df.iterrows():
            title = row.get("新闻标题", row.get("title", ""))
            content = row.get("新闻内容", row.get("content", ""))
            pub_date_str = row.get("发布时间", row.get("publish_time", ""))
            source = row.get("文章来源", row.get("source", "东方财富"))
            link = row.get("新闻链接", row.get("url", ""))

            # Date filtering
            if pub_date_str:
                try:
                    pub_date = datetime.strptime(str(pub_date_str)[:10], "%Y-%m-%d")
                    if not (start_dt <= pub_date <= end_dt + relativedelta(days=1)):
                        continue
                except (ValueError, TypeError):
                    pass  # Include if date can't be parsed

            # Truncate long content for summary
            summary = str(content)[:200] + "..." if len(str(content)) > 200 else str(content)

            news_str += f"### {title} (来源: {source})\n"
            if summary:
                news_str += f"{summary}\n"
            if link:
                news_str += f"链接: {link}\n"
            news_str += "\n"
            filtered_count += 1

            if filtered_count >= 20:
                break

        if filtered_count == 0:
            return f"{ticker} 在 {start_date} 至 {end_date} 期间没有相关新闻"

        return f"## {ticker} 新闻, {start_date} 至 {end_date}:\n\n{news_str}"

    except Exception as e:
        return f"获取 {ticker} 新闻失败: {str(e)}"


def get_global_news(
    curr_date: str,
    look_back_days: int = 7,
    limit: int = 10,
) -> str:
    """
    Retrieve Chinese macro/global financial news via akshare.

    Uses 东方财富 global news and financial breakfast APIs.

    Args:
        curr_date: Current date in yyyy-mm-dd format
        look_back_days: Number of days to look back
        limit: Maximum number of articles to return

    Returns:
        Formatted markdown string containing global news
    """
    import akshare as ak

    all_news = []
    seen_titles = set()

    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    start_dt = curr_dt - relativedelta(days=look_back_days)
    start_date = start_dt.strftime("%Y-%m-%d")

    # Source 1: Global stock information
    # Note: akshare global news APIs return current/recent news without precise date fields.
    # The look_back_days parameter is used for header context only.
    try:
        _request_delay()
        df_global = _retry_call(ak.stock_info_global_em)
        if df_global is not None and not df_global.empty:
            for _, row in df_global.iterrows():
                title = str(row.get("标题", row.iloc[0] if len(row) > 0 else ""))
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    all_news.append({
                        "title": title,
                        "content": str(row.get("内容", "")),
                        "source": "东方财富全球资讯",
                    })
                if len(all_news) >= limit:
                    break
    except Exception:
        pass  # Continue with other sources

    # Source 2: Financial breakfast (财经早餐)
    if len(all_news) < limit:
        try:
            _request_delay()
            df_cjzc = _retry_call(ak.stock_info_cjzc_em)
            if df_cjzc is not None and not df_cjzc.empty:
                for _, row in df_cjzc.iterrows():
                    title = str(row.get("标题", row.iloc[0] if len(row) > 0 else ""))
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        all_news.append({
                            "title": title,
                            "content": str(row.get("内容", "")),
                            "source": "东方财富财经早餐",
                        })
                    if len(all_news) >= limit:
                        break
        except Exception:
            pass

    if not all_news:
        return f"没有找到 {start_date} 至 {curr_date} 期间的全球/宏观新闻"

    news_str = ""
    for item in all_news[:limit]:
        news_str += f"### {item['title']} (来源: {item['source']})\n"
        content = item.get("content", "")
        if content:
            summary = content[:300] + "..." if len(content) > 300 else content
            news_str += f"{summary}\n"
        news_str += "\n"

    return f"## 中国及全球市场新闻, {start_date} 至 {curr_date}:\n\n{news_str}"
