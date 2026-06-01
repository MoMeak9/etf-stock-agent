from tradingagents.agents.utils.agent_states import apply_asset_report_mapping
from tradingagents.agents.utils.fund_data_tools import get_fund_manager, get_fund_product
from tradingagents.agents.utils.fund_prompt_utils import build_fund_report_header


def create_fund_product_analyst(llm, toolkit=None):
    def fund_product_analyst_node(state):
        symbol = state["company_of_interest"]
        current_date = state["trade_date"]
        product_data = get_fund_product.invoke({"symbol": symbol, "curr_date": current_date})
        manager_data = get_fund_manager.invoke({"symbol": symbol, "curr_date": current_date})

        prompt = (
            f"{build_fund_report_header('基金产品与管理人分析', symbol)}\n\n"
            "你是开放式公募基金产品分析师。请重点分析产品类型、申购赎回状态、管理人信息、"
            "产品质量、持有适配性、费用与数据缺口。若管理人或申赎字段缺失，必须提示限制。\n\n"
            f"## Product Data\n{product_data}\n\n"
            f"## Manager Data\n{manager_data}"
        )
        result = llm.invoke(prompt)
        report = result.content
        update = {
            "messages": [result],
            "fund_product_report": report,
            "product_tool_call_count": 2,
        }
        return apply_asset_report_mapping(update, "fund")

    return fund_product_analyst_node
