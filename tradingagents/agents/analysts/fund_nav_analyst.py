from tradingagents.agents.utils.agent_states import apply_asset_report_mapping
from tradingagents.agents.utils.fund_data_tools import (
    get_fund_macro_context,
    get_fund_nav,
    get_fund_performance,
)
from tradingagents.agents.utils.fund_prompt_utils import build_fund_report_header


def create_fund_nav_analyst(llm, toolkit=None):
    def fund_nav_analyst_node(state):
        symbol = state["company_of_interest"]
        current_date = state["trade_date"]
        nav_data = get_fund_nav.invoke({"symbol": symbol, "curr_date": current_date})
        performance_data = get_fund_performance.invoke({"symbol": symbol, "curr_date": current_date})
        macro_data = get_fund_macro_context.invoke({"symbol": symbol, "curr_date": current_date})

        prompt = (
            f"{build_fund_report_header('基金净值与收益质量分析', symbol)}\n\n"
            "你是开放式公募基金净值分析师。请基于真实工具数据生成正式报告，重点分析："
            "净值走势、回撤、波动、收益质量、宏观环境适配度与数据缺口。"
            "若字段缺失，必须明确说明缺失对结论置信度的影响。\n\n"
            f"## NAV Data\n{nav_data}\n\n"
            f"## Performance Data\n{performance_data}\n\n"
            f"## Macro Context\n{macro_data}"
        )
        result = llm.invoke(prompt)
        report = result.content
        update = {
            "messages": [result],
            "fund_nav_report": report,
            "nav_tool_call_count": 3,
        }
        return apply_asset_report_mapping(update, "fund")

    return fund_nav_analyst_node
