from tradingagents.agents.utils.etf_data_tools import (
    get_etf_discount_premium,
    get_etf_fund_flow,
    get_etf_holdings,
    get_etf_profile,
    get_etf_tracking_info,
)
from tradingagents.agents.utils.etf_prompt_utils import build_etf_product_prompt
from tradingagents.agents.utils.agent_states import apply_asset_report_mapping


def create_etf_product_analyst(llm, toolkit=None):
    def etf_product_analyst_node(state):
        ticker = state["company_of_interest"]
        current_date = state["trade_date"]
        profile_data = get_etf_profile.invoke({"ticker": ticker, "curr_date": current_date})
        holdings_data = get_etf_holdings.invoke({"ticker": ticker, "curr_date": current_date})
        flow_data = get_etf_fund_flow.invoke({"ticker": ticker, "curr_date": current_date})
        discount_data = get_etf_discount_premium.invoke({"ticker": ticker, "curr_date": current_date})
        tracking_data = get_etf_tracking_info.invoke({"ticker": ticker, "curr_date": current_date})

        prompt = (
            f"{build_etf_product_prompt(ticker)}\n\n"
            f"## ETF Profile\n{profile_data}\n\n"
            f"## ETF Holdings\n{holdings_data}\n\n"
            f"## ETF Fund Flow\n{flow_data}\n\n"
            f"## ETF Discount Premium\n{discount_data}\n\n"
            f"## ETF Tracking Info\n{tracking_data}"
        )
        result = llm.invoke(prompt)
        report = result.content
        update = {
            "messages": [result],
            "etf_product_report": report,
            "product_tool_call_count": 5,
        }
        return apply_asset_report_mapping(update, "etf")

    return etf_product_analyst_node
