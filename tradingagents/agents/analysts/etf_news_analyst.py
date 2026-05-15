from tradingagents.agents.utils.etf_data_tools import get_etf_news
from tradingagents.agents.utils.etf_prompt_utils import build_etf_news_prompt
from tradingagents.agents.utils.agent_states import apply_asset_report_mapping


def create_etf_news_analyst(llm, toolkit=None):
    def etf_news_analyst_node(state):
        ticker = state["company_of_interest"]
        current_date = state["trade_date"]
        news_data = get_etf_news.invoke(
            {
                "ticker": ticker,
                "start_date": current_date,
                "end_date": current_date,
            }
        )
        prompt = (
            f"{build_etf_news_prompt(ticker)}\n\n"
            f"## ETF 相关新闻\n{news_data}"
        )
        result = llm.invoke(prompt)
        report = result.content
        update = {
            "messages": [result],
            "etf_news_report": report,
            "news_tool_call_count": 1,
        }
        return apply_asset_report_mapping(update, "etf")

    return etf_news_analyst_node
