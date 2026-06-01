from tradingagents.agents.utils.agent_states import apply_asset_report_mapping
from tradingagents.agents.utils.fund_data_tools import get_fund_event, get_fund_macro_context
from tradingagents.agents.utils.fund_prompt_utils import build_fund_report_header


def create_fund_event_analyst(llm, toolkit=None):
    def fund_event_analyst_node(state):
        symbol = state["company_of_interest"]
        current_date = state["trade_date"]
        event_data = get_fund_event.invoke({"symbol": symbol, "curr_date": current_date})
        macro_data = get_fund_macro_context.invoke({"symbol": symbol, "curr_date": current_date})

        prompt = (
            f"{build_fund_report_header('基金事件与公告分析', symbol)}\n\n"
            "你是开放式公募基金事件分析师。请重点分析基金公告、产品事件、宏观新闻扰动、"
            "申赎或运作变化及其对中长期持有决策的影响。缺失公告源时必须说明。\n\n"
            f"## Event Data\n{event_data}\n\n"
            f"## Macro Context\n{macro_data}"
        )
        result = llm.invoke(prompt)
        report = result.content
        update = {
            "messages": [result],
            "fund_event_report": report,
            "event_tool_call_count": 2,
        }
        return apply_asset_report_mapping(update, "fund")

    return fund_event_analyst_node
