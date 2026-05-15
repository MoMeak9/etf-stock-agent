"""
市场路由器 - 轻量级市场检测和数据源选择协调层

职责：
1. 市场类型检测（A股/港股/美股）
2. 公司名解析（多数据源 fallback）
3. 货币信息获取
4. 数据源路由建议
"""

import re
from typing import Optional


# 内置港股名称映射（避免 API 调用）
_HK_STOCK_NAMES = {
    "0700.HK": "腾讯控股",
    "0941.HK": "中国移动",
    "0762.HK": "中国联通",
    "0728.HK": "中国电信",
    "0939.HK": "建设银行",
    "1398.HK": "工商银行",
    "3988.HK": "中国银行",
    "0005.HK": "汇丰控股",
    "1299.HK": "友邦保险",
    "2318.HK": "中国平安",
    "2628.HK": "中国人寿",
    "0857.HK": "中国石油",
    "0386.HK": "中国石化",
    "9988.HK": "阿里巴巴",
    "3690.HK": "美团",
    "1024.HK": "快手",
    "9618.HK": "京东集团",
    "1211.HK": "比亚迪",
    "2238.HK": "广汽集团",
    "0753.HK": "中国国航",
    "1093.HK": "石药集团",
    "1876.HK": "百威亚太",
    "0291.HK": "华润啤酒",
    "1109.HK": "华润置地",
    "6862.HK": "海底捞",
    "2020.HK": "安踏体育",
    "0027.HK": "银河娱乐",
    "1177.HK": "中国生物制药",
    "0388.HK": "香港交易所",
    "0883.HK": "中国海洋石油",
    "0016.HK": "新鸿基地产",
    "0002.HK": "中电控股",
    "0003.HK": "中华煤气",
    "0011.HK": "恒生银行",
    "0066.HK": "港铁公司",
    "0823.HK": "领展房产基金",
    "0001.HK": "长和",
    "0006.HK": "电能实业",
    "0012.HK": "恒基地产",
    "0017.HK": "新世界发展",
    "0101.HK": "恒隆地产",
    "0688.HK": "中国海外发展",
    "1038.HK": "长江基建",
    "1113.HK": "长实集团",
    "1928.HK": "金沙中国",
    "1997.HK": "九龙仓置业",
    "2007.HK": "碧桂园",
    "2269.HK": "药明生物",
    "2382.HK": "舜宇光学科技",
    "2688.HK": "新奥能源",
    "6098.HK": "碧桂园服务",
    "6969.HK": "思摩尔国际",
    "9633.HK": "农夫山泉",
    "9999.HK": "网易",
}


def detect_market(ticker: str) -> str:
    """
    检测股票所属市场。

    Rules:
      - .HK 后缀或纯 4-5 位数字且符合港股模式 → "hk"
      - 6 位数字或 .SH/.SZ 后缀 → "cn"
      - 纯字母 → "us"

    Returns: "us" | "cn" | "hk"
    """
    if not ticker or not ticker.strip():
        return "us"

    s = ticker.strip().upper()

    # HK market: .HK suffix
    if s.endswith(".HK"):
        return "hk"

    # CN market: .SH / .SZ suffix
    if re.match(r"^\d{6}\.(SH|SZ)$", s, re.IGNORECASE):
        return "cn"

    # CN market: SH / SZ prefix
    if re.match(r"^(SH|SZ)\d{6}$", s, re.IGNORECASE):
        return "cn"

    # CN market: pure 6-digit
    if re.match(r"^\d{6}$", s):
        return "cn"

    # US market: pure letters or letters with dots (BRK.B)
    if re.match(r"^[A-Za-z]+(\.[A-Za-z])?$", s):
        return "us"

    return "us"


def get_market_info(ticker: str) -> dict:
    """
    返回股票的市场元数据。

    Returns: {
        'market': 'cn' | 'hk' | 'us',
        'market_name': str,
        'currency': str,
        'currency_name': str,
        'currency_symbol': str,
        'is_china': bool,
        'is_hk': bool,
        'is_us': bool,
    }
    """
    market = detect_market(ticker)

    if market == "cn":
        return {
            "market": "cn",
            "market_name": "中国A股",
            "currency": "CNY",
            "currency_name": "人民币",
            "currency_symbol": "¥",
            "is_china": True,
            "is_hk": False,
            "is_us": False,
        }
    elif market == "hk":
        return {
            "market": "hk",
            "market_name": "香港市场",
            "currency": "HKD",
            "currency_name": "港币",
            "currency_symbol": "HK$",
            "is_china": False,
            "is_hk": True,
            "is_us": False,
        }
    else:
        return {
            "market": "us",
            "market_name": "美国市场",
            "currency": "USD",
            "currency_name": "美元",
            "currency_symbol": "$",
            "is_china": False,
            "is_hk": False,
            "is_us": True,
        }


def get_company_name(ticker: str, market: str = None) -> str:
    """
    多源 fallback 公司名解析。

    A股: tushare → akshare → ticker
    港股: 静态映射 → yfinance → ticker
    美股: yfinance → ticker
    """
    if market is None:
        market = detect_market(ticker)

    if market == "hk":
        return _get_hk_company_name(ticker)
    elif market == "cn":
        return _get_cn_company_name(ticker)
    else:
        return _get_us_company_name(ticker)


def _normalize_hk_symbol(symbol: str) -> str:
    """标准化港股代码为 XXXX.HK 格式。"""
    if not symbol:
        return symbol
    s = str(symbol).strip().upper()
    if s.endswith(".HK"):
        s = s[:-3]
    if s.isdigit():
        clean = s.lstrip("0") or "0"
        return f"{clean.zfill(4)}.HK"
    return s


def _get_hk_company_name(ticker: str) -> str:
    """港股公司名: 静态映射 → yfinance → 默认值。"""
    normalized = _normalize_hk_symbol(ticker)
    # 1. 静态映射
    if normalized in _HK_STOCK_NAMES:
        return _HK_STOCK_NAMES[normalized]
    # 2. yfinance fallback
    try:
        import yfinance as yf
        info = yf.Ticker(normalized).info
        name = info.get("longName") or info.get("shortName")
        if name:
            return name
    except Exception:
        pass
    return f"港股{normalized}"


def _get_cn_company_name(ticker: str) -> str:
    """A股公司名: tushare → akshare → 默认值。"""
    # 提取纯 6 位数字
    code = re.sub(r"\.(SH|SZ)$", "", ticker.strip(), flags=re.IGNORECASE)
    code = re.sub(r"^(SH|SZ)", "", code, flags=re.IGNORECASE)

    # 1. tushare
    try:
        import tushare as ts
        import os
        token = os.getenv("TUSHARE_TOKEN", "")
        if token:
            pro = ts.pro_api(token)
            df = pro.stock_basic(ts_code=f"{code}.SH", fields="name")
            if df.empty:
                df = pro.stock_basic(ts_code=f"{code}.SZ", fields="name")
            if not df.empty:
                return df.iloc[0]["name"]
    except Exception:
        pass

    # 2. akshare
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        match = df[df["code"] == code]
        if not match.empty:
            return match.iloc[0]["name"]
    except Exception:
        pass

    return ticker


def _get_us_company_name(ticker: str) -> str:
    """美股公司名: yfinance → 默认值。"""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker.upper()).info
        name = info.get("longName") or info.get("shortName")
        if name:
            return name
    except Exception:
        pass
    return ticker.upper()


def is_dashscope_model(llm) -> bool:
    """检测是否为 DashScope/阿里百炼 模型。"""
    class_name = llm.__class__.__name__
    if "DashScope" in class_name:
        return True
    # 检查 base_url
    base_url = getattr(llm, "openai_api_base", "") or getattr(llm, "base_url", "")
    if base_url and "dashscope" in str(base_url).lower():
        return True
    return False


def is_deepseek_model(llm) -> bool:
    """检测是否为 DeepSeek 模型。"""
    class_name = llm.__class__.__name__
    if "DeepSeek" in class_name:
        return True
    base_url = getattr(llm, "openai_api_base", "") or getattr(llm, "base_url", "")
    if base_url and "deepseek" in str(base_url).lower():
        return True
    model_name = getattr(llm, "model_name", "") or getattr(llm, "model", "")
    if model_name and "deepseek" in str(model_name).lower():
        return True
    return False


def is_zhipu_model(llm) -> bool:
    """检测是否为 智谱 (Zhipu/GLM) 模型。"""
    class_name = llm.__class__.__name__
    if "Zhipu" in class_name or "GLM" in class_name:
        return True
    base_url = getattr(llm, "openai_api_base", "") or getattr(llm, "base_url", "")
    if base_url and "zhipu" in str(base_url).lower():
        return True
    model_name = getattr(llm, "model_name", "") or getattr(llm, "model", "")
    if model_name and ("glm" in str(model_name).lower() or "zhipu" in str(model_name).lower()):
        return True
    return False


def needs_prefetch(llm) -> bool:
    """判断模型是否需要预抓取模式（tool calling 不稳定的模型）。"""
    return is_dashscope_model(llm) or is_deepseek_model(llm) or is_zhipu_model(llm)
