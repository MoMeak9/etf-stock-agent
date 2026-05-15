# TradingAgents/graph/propagation.py

from typing import Dict, Any, List, Optional
from langchain_core.messages import HumanMessage
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from tradingagents.dataflows.market_utils import get_market_info


class Propagator:
    """Handles state initialization and propagation through the graph."""

    def __init__(self, max_recur_limit=100, asset_type="stock", analysis_mode="hybrid"):
        """Initialize with configuration parameters."""
        self.max_recur_limit = max_recur_limit
        self.asset_type = asset_type
        self.analysis_mode = analysis_mode

    def create_initial_state(
        self, company_name: str, trade_date: str
    ) -> Dict[str, Any]:
        """Create the initial state for the agent graph."""
        market_context = get_market_info(company_name)
        if self.asset_type == "etf":
            analysis_request = (
                f"请对 A 股 ETF {company_name} 进行全面分析，"
                f"包括 ETF 行情、产品结构、新闻事件和资金流/情绪，"
                f"同时给出交易建议与配置建议。"
                f"分析日期：{trade_date}。"
            )
        else:
            analysis_request = (
                f"请对股票 {company_name} 进行全面分析，"
                f"包括技术面、基本面、新闻面和情绪面，"
                f"最终给出买入/持有/卖出建议。"
                f"分析日期：{trade_date}。"
            )
        return {
            "messages": [HumanMessage(content=analysis_request)],
            "company_of_interest": company_name,
            "trade_date": str(trade_date),
            "asset_type": self.asset_type,
            "analysis_mode": self.analysis_mode,
            "market_context": market_context,
            "investment_debate_state": InvestDebateState(
                {
                    "bull_history": "",
                    "bear_history": "",
                    "history": "",
                    "current_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            ),
            "risk_debate_state": RiskDebateState(
                {
                    "aggressive_history": "",
                    "conservative_history": "",
                    "neutral_history": "",
                    "history": "",
                    "latest_speaker": "",
                    "current_aggressive_response": "",
                    "current_conservative_response": "",
                    "current_neutral_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            ),
            "market_report": "",
            "fundamentals_report": "",
            "sentiment_report": "",
            "news_report": "",
            "china_market_report": "",
            "etf_market_report": "",
            "etf_product_report": "",
            "etf_news_report": "",
            "etf_flow_report": "",
            "market_tool_call_count": 0,
            "sentiment_tool_call_count": 0,
            "news_tool_call_count": 0,
            "fundamentals_tool_call_count": 0,
            "china_market_tool_call_count": 0,
            "flow_tool_call_count": 0,
            "product_tool_call_count": 0,
        }

    def get_graph_args(self, callbacks: Optional[List] = None) -> Dict[str, Any]:
        """Get arguments for the graph invocation.

        Args:
            callbacks: Optional list of callback handlers for tool execution tracking.
                       Note: LLM callbacks are handled separately via LLM constructor.
        """
        config = {"recursion_limit": self.max_recur_limit}
        if callbacks:
            config["callbacks"] = callbacks
        return {
            "stream_mode": "values",
            "config": config,
        }
