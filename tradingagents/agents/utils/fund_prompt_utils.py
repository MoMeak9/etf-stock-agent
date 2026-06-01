FUND_DECISION_LANGUAGE = "申购、分批申购、持有、赎回、观望"


def build_fund_report_header(title: str, symbol: str) -> str:
    return (
        f"# {title}\n\n"
        f"- 分析标的：开放式公募基金 {symbol}\n"
        "- 分析视角：以中长期持有与宏观环境匹配为核心，兼顾净值波动、回撤和申赎可行性。\n"
        f"- 决策语言只能使用或围绕：{FUND_DECISION_LANGUAGE}。\n"
        "- 禁止使用个股、ETF、止损价、目标价、短线交易突破等措辞。"
    )
