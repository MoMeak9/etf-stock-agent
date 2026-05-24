ETF_MARKET_INDICATORS = [
    "close_5_sma",
    "close_10_sma",
    "close_20_sma",
    "close_60_sma",
    "macd",
    "rsi",
    "boll",
]


def get_etf_type_prompt_suffix(etf_type: str) -> str:
    normalized = (etf_type or "").strip().lower()
    if "commodity" in normalized or "商品" in normalized:
        return "重点分析商品价格驱动、波动放大特征、宏观与政策扰动。"
    if "sector" in normalized or "theme" in normalized or "行业" in normalized or "主题" in normalized:
        return "重点分析行业景气、主题催化、拥挤度与回撤风险。"
    return "重点分析市场 Beta、风格暴露、长期配置价值与流动性。"


def build_etf_report_header(analyst_title: str, ticker: str) -> str:
    return (
        f"# {analyst_title}\n\n"
        f"- 分析标的：A 股 ETF {ticker}\n"
        "- 输出必须同时覆盖交易视角与配置视角。\n"
    )


def build_etf_product_prompt(ticker: str, etf_type: str = "") -> str:
    return (
        f"{build_etf_report_header('ETF 产品分析', ticker)}\n"
        "请围绕以下数据生成报告：基金 profile、holdings（持仓结构）、折溢价、跟踪信息、费率、规模与份额变化。\n"
        "必须明确讨论：产品质量、流动性、配置适配性、交易风险。\n"
        "若跟踪误差时间序列不可用，必须写明该字段缺失；不得用低折溢价直接推断跟踪误差优秀。\n"
        f"{get_etf_type_prompt_suffix(etf_type)}\n"
        "禁止出现公司财报、估值倍数、管理层等个股基本面措辞。"
    )


def build_etf_news_prompt(ticker: str, etf_type: str = "") -> str:
    return (
        f"{build_etf_report_header('ETF 新闻分析', ticker)}\n"
        "请重点分析 ETF 本身、跟踪指数、行业/主题、商品价格、政策、基金公告与产品事件。\n"
        f"{get_etf_type_prompt_suffix(etf_type)}\n"
        "不要把新闻解读成上市公司经营层面的基本面结论。"
    )


def build_etf_flow_prompt(ticker: str, etf_type: str = "") -> str:
    return (
        f"{build_etf_report_header('ETF 资金流与情绪分析', ticker)}\n"
        "请重点分析资金流、份额变化、成交热度、拥挤度、短期情绪共振。\n"
        f"{get_etf_type_prompt_suffix(etf_type)}\n"
        "输出里必须包含短期交易观察和中期配置风险提示。"
    )
