from tradingagents.agents.utils.etf_data_tools import get_etf_fund_flow
from tradingagents.agents.utils.etf_prompt_utils import build_etf_flow_prompt
from tradingagents.agents.utils.agent_states import apply_asset_report_mapping


def create_etf_flow_analyst(llm, toolkit=None):
    def etf_flow_analyst_node(state):
        ticker = state["company_of_interest"]
        current_date = state["trade_date"]
        flow_data = get_etf_fund_flow.invoke(
            {"ticker": ticker, "curr_date": current_date}
        )
        prompt = (
            f"{build_etf_flow_prompt(ticker)}\n\n"
            f"## ETF 资金流数据\n{flow_data}"
        )
        result = llm.invoke(prompt)
        report = result.content
        update = {
            "messages": [result],
            "etf_flow_report": report,
            "flow_tool_call_count": 1,
        }
        return apply_asset_report_mapping(update, "etf")

    return etf_flow_analyst_node
