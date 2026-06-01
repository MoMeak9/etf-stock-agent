from tradingagents.agents.utils.agent_states import apply_asset_report_mapping
from tradingagents.agents.utils.fund_data_tools import get_fund_macro_context, get_fund_portfolio
from tradingagents.agents.utils.fund_prompt_utils import build_fund_report_header


def create_fund_portfolio_analyst(llm, toolkit=None):
    def fund_portfolio_analyst_node(state):
        symbol = state["company_of_interest"]
        current_date = state["trade_date"]
        portfolio_data = get_fund_portfolio.invoke({"symbol": symbol, "curr_date": current_date})
        macro_data = get_fund_macro_context.invoke({"symbol": symbol, "curr_date": current_date})

        prompt = (
            f"{build_fund_report_header('基金组合与持仓分析', symbol)}\n\n"
            "你是开放式公募基金组合分析师。请重点分析资产配置、行业或区域暴露、集中度、"
            "组合与宏观环境的匹配度、潜在拥挤风险和数据缺口。\n\n"
            f"## Portfolio Data\n{portfolio_data}\n\n"
            f"## Macro Context\n{macro_data}"
        )
        result = llm.invoke(prompt)
        report = result.content
        update = {
            "messages": [result],
            "fund_portfolio_report": report,
            "portfolio_tool_call_count": 2,
        }
        return apply_asset_report_mapping(update, "fund")

    return fund_portfolio_analyst_node
