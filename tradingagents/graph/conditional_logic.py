# TradingAgents/graph/conditional_logic.py

from tradingagents.agents.utils.agent_states import AgentState

# Maximum tool calls per analyst type (death-loop prevention)
_MAX_TOOL_CALLS = {
    "market": 3,
    "social": 3,
    "news": 3,
    "fundamentals": 1,
    "flow": 3,
    "product": 2,
    "china_market": 3,
}


class ConditionalLogic:
    """Handles conditional logic for determining graph flow."""

    def __init__(self, max_debate_rounds=1, max_risk_discuss_rounds=1):
        """Initialize with configuration parameters."""
        self.max_debate_rounds = max_debate_rounds
        self.max_risk_discuss_rounds = max_risk_discuss_rounds

    def _should_continue_analyst(
        self,
        state: AgentState,
        analyst_type: str,
        report_field: str,
        tool_count_field: str,
        tools_node: str,
        clear_node: str,
    ) -> str:
        """Generic analyst continuation logic with death-loop prevention.

        Priority:
        1. If report already exists (>100 chars) → clear (done)
        2. If tool call count exceeded → clear (prevent death-loop)
        3. If last message has tool_calls → route to tools
        4. Otherwise → clear
        """
        # Priority 1: Report already generated
        report = state.get(report_field, "")
        if report and len(report) > 100:
            return clear_node

        # Priority 2: Tool call limit reached
        max_calls = _MAX_TOOL_CALLS.get(analyst_type, 3)
        tool_count = state.get(tool_count_field, 0)
        if tool_count >= max_calls:
            return clear_node

        # Priority 3: Check for tool calls in last message
        messages = state["messages"]
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return tools_node

        return clear_node

    def should_continue_market(self, state: AgentState):
        """Determine if market analysis should continue."""
        return self._should_continue_analyst(
            state, "market", "market_report", "market_tool_call_count",
            "tools_market", "Msg Clear Market",
        )

    def should_continue_social(self, state: AgentState):
        """Determine if social media analysis should continue."""
        return self._should_continue_analyst(
            state, "social", "sentiment_report", "sentiment_tool_call_count",
            "tools_social", "Msg Clear Social",
        )

    def should_continue_news(self, state: AgentState):
        """Determine if news analysis should continue."""
        return self._should_continue_analyst(
            state, "news", "news_report", "news_tool_call_count",
            "tools_news", "Msg Clear News",
        )

    def should_continue_fundamentals(self, state: AgentState):
        """Determine if fundamentals analysis should continue."""
        return self._should_continue_analyst(
            state, "fundamentals", "fundamentals_report", "fundamentals_tool_call_count",
            "tools_fundamentals", "Msg Clear Fundamentals",
        )

    def should_continue_china_market(self, state: AgentState):
        """Determine if China market analysis should continue."""
        return self._should_continue_analyst(
            state, "china_market", "china_market_report", "china_market_tool_call_count",
            "tools_china_market", "Msg Clear China_market",
        )

    def should_continue_flow(self, state: AgentState):
        """Determine if ETF flow analysis should continue."""
        return self._should_continue_analyst(
            state,
            "flow",
            "etf_flow_report",
            "flow_tool_call_count",
            "tools_flow",
            "Msg Clear Flow",
        )

    def should_continue_product(self, state: AgentState):
        """Determine if ETF product analysis should continue."""
        return self._should_continue_analyst(
            state,
            "product",
            "etf_product_report",
            "product_tool_call_count",
            "tools_product",
            "Msg Clear Product",
        )

    def should_continue_debate(self, state: AgentState) -> str:
        """Determine if debate should continue."""

        if (
            state["investment_debate_state"]["count"] >= 2 * self.max_debate_rounds
        ):  # N rounds of back-and-forth between 2 agents
            return "Research Manager"
        if state["investment_debate_state"]["current_response"].startswith("Bull"):
            return "Bear Researcher"
        return "Bull Researcher"

    def should_continue_risk_analysis(self, state: AgentState) -> str:
        """Determine if risk analysis should continue."""
        if (
            state["risk_debate_state"]["count"] >= 3 * self.max_risk_discuss_rounds
        ):  # N rounds of back-and-forth between 3 agents
            return "Risk Judge"
        if state["risk_debate_state"]["latest_speaker"].startswith("Aggressive"):
            return "Conservative Analyst"
        if state["risk_debate_state"]["latest_speaker"].startswith("Conservative"):
            return "Neutral Analyst"
        return "Aggressive Analyst"
