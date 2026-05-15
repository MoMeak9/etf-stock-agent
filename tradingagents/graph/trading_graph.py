# TradingAgents/graph/trading_graph.py

import os
from pathlib import Path
import json
from datetime import date
from typing import Dict, Any, Tuple, List, Optional

from langgraph.prebuilt import ToolNode

from tradingagents.llm_clients import create_llm_client

from tradingagents.agents import *
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.agents.utils.memory import FinancialSituationMemory
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from tradingagents.dataflows.config import set_config, set_market_context, set_asset_context
from tradingagents.dataflows.market_utils import detect_market, is_supported_cn_etf

# Import the tool methods from modular tool files
from tradingagents.agents.utils.core_stock_tools import get_stock_data
from tradingagents.agents.utils.technical_indicators_tools import get_indicators
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news,
    get_sentiment,
)
from tradingagents.agents.utils.etf_data_tools import (
    get_etf_price_data,
    get_etf_indicators,
    get_etf_profile,
    get_etf_holdings,
    get_etf_fund_flow,
    get_etf_discount_premium,
    get_etf_tracking_info,
    get_etf_news,
)

# Market router for toolkit
from tradingagents.agents.utils.market_router import get_market_info as _get_market_info

from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config: Dict[str, Any] = None,
        callbacks: Optional[List] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
            callbacks: Optional list of callback handlers (e.g., for tracking LLM/tool stats)
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG
        self.callbacks = callbacks or []
        self._asset_type = self.config.get("asset_type", "stock")
        self._analysis_mode = self.config.get("etf_analysis_mode", "hybrid")

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(
            os.path.join(self.config["project_dir"], "dataflows/data_cache"),
            exist_ok=True,
        )

        # Initialize LLMs with provider-specific thinking configuration
        llm_kwargs = self._get_provider_kwargs()

        # Add callbacks to kwargs if provided (passed to LLM constructor)
        if self.callbacks:
            llm_kwargs["callbacks"] = self.callbacks

        deep_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        quick_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )

        self.deep_thinking_llm = deep_client.get_llm()
        self.quick_thinking_llm = quick_client.get_llm()

        # Initialize memories with market prefix support
        # Default to US market; will be re-initialized if CN market detected
        self._memories_cache = {}
        self._current_market = "us"
        memories = self._get_memories("us")

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config["max_debate_rounds"],
            max_risk_discuss_rounds=self.config["max_risk_discuss_rounds"],
        )
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            memories["bull"],
            memories["bear"],
            memories["trader"],
            memories["invest_judge"],
            memories["risk_manager"],
            self.conditional_logic,
            toolkit=None,  # Market routing handled by market_router module
        )

        self.propagator = Propagator(
            max_recur_limit=self.config.get("max_recur_limit", 100),
            asset_type=self._asset_type,
            analysis_mode=self._analysis_mode,
        )
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph
        if self._asset_type == "etf" and selected_analysts == ["market", "social", "news", "fundamentals"]:
            selected_analysts = self.config.get(
                "selected_etf_analysts", ["market", "flow", "news", "product"]
            )
        self._selected_analysts = selected_analysts
        self.graph = self.graph_setup.setup_graph(selected_analysts, asset_type=self._asset_type)

    def _get_provider_kwargs(self) -> Dict[str, Any]:
        """Get provider-specific kwargs for LLM client creation."""
        kwargs = {}
        provider = self.config.get("llm_provider", "").lower()

        if provider == "google":
            thinking_level = self.config.get("google_thinking_level")
            if thinking_level:
                kwargs["thinking_level"] = thinking_level

        elif provider == "openai":
            reasoning_effort = self.config.get("openai_reasoning_effort")
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort

        elif provider == "deepseek":
            # DeepSeek V4 models default to thinking mode which requires
            # reasoning_content to be passed back in multi-turn conversations.
            # LangChain doesn't handle this properly, so disable thinking by default.
            if not self.config.get("deepseek_thinking"):
                kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

        elif provider == "custom":
            # Some custom OpenAI-compatible gateways are less stable with
            # chunked streaming on long responses. Keep it configurable and
            # default to non-streaming for reliability.
            if self.config.get("custom_streaming"):
                kwargs["streaming"] = True
            timeout = self.config.get("custom_timeout")
            if timeout:
                kwargs["timeout"] = timeout
            max_retries = self.config.get("custom_max_retries")
            if max_retries is not None:
                kwargs["max_retries"] = max_retries

        return kwargs

    def _create_tool_nodes(self) -> Dict[str, ToolNode]:
        """Create tool nodes for different data sources using abstract methods."""
        if self._asset_type == "etf":
            return {
                "market": ToolNode([get_etf_price_data, get_etf_indicators]),
                "flow": ToolNode([get_etf_fund_flow]),
                "news": ToolNode([get_etf_news]),
                "product": ToolNode(
                    [
                        get_etf_profile,
                        get_etf_holdings,
                        get_etf_fund_flow,
                        get_etf_discount_premium,
                        get_etf_tracking_info,
                    ]
                ),
            }
        return {
            "market": ToolNode(
                [
                    # Core stock data tools
                    get_stock_data,
                    # Technical indicators
                    get_indicators,
                ]
            ),
            "social": ToolNode(
                [
                    # Dedicated sentiment analysis tool
                    get_sentiment,
                ]
            ),
            "news": ToolNode(
                [
                    # News and insider information
                    get_news,
                    get_global_news,
                    get_insider_transactions,
                ]
            ),
            "fundamentals": ToolNode(
                [
                    # Fundamental analysis tools
                    get_fundamentals,
                    get_balance_sheet,
                    get_cashflow,
                    get_income_statement,
                ]
            ),
            "china_market": ToolNode(
                [
                    # China market analyst uses core tools (routed by interface)
                    get_stock_data,
                    get_indicators,
                    get_fundamentals,
                ]
            ),
        }

    def _get_memories(self, market: str) -> dict:
        """Get or create market-specific memory instances."""
        if market not in self._memories_cache:
            prefix = f"{market}_"
            self._memories_cache[market] = {
                "bull": FinancialSituationMemory(f"{prefix}bull_memory", self.config),
                "bear": FinancialSituationMemory(f"{prefix}bear_memory", self.config),
                "trader": FinancialSituationMemory(f"{prefix}trader_memory", self.config),
                "invest_judge": FinancialSituationMemory(f"{prefix}invest_judge_memory", self.config),
                "risk_manager": FinancialSituationMemory(f"{prefix}risk_manager_memory", self.config),
            }
        return self._memories_cache[market]

    def _rebuild_graph_for_market(self, market: str):
        """Rebuild the graph with market-specific memories if market changed."""
        if market == self._current_market:
            return
        self._current_market = market
        memories = self._get_memories(market)
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            memories["bull"],
            memories["bear"],
            memories["trader"],
            memories["invest_judge"],
            memories["risk_manager"],
            self.conditional_logic,
            toolkit=None,
        )
        self.graph = self.graph_setup.setup_graph(self._selected_analysts, asset_type=self._asset_type)

    def propagate(self, company_name, trade_date, on_node=None):
        """Run the trading agents graph for a company on a specific date.

        Args:
            company_name: Ticker symbol.
            trade_date: Analysis date string.
            on_node: Optional callback ``fn(node_name: str)`` invoked each time
                     a graph node finishes execution.  Useful for progress UIs.
        """

        self.ticker = company_name

        # Set market context for data routing (before any data fetching)
        market = detect_market(company_name)
        if self._asset_type == "etf" and not is_supported_cn_etf(company_name):
            raise ValueError("ETF mode currently supports only A-share exchange-traded ETF codes.")
        set_market_context(market)
        set_asset_context(self._asset_type)

        # Rebuild graph with market-specific memories if needed
        self._rebuild_graph_for_market(market)

        # Initialize state
        init_agent_state = self.propagator.create_initial_state(
            company_name, trade_date
        )
        args = self.propagator.get_graph_args(callbacks=self.callbacks)

        if on_node is not None or self.debug:
            # Streaming mode — use "updates" to get per-node granularity
            stream_kwargs = {
                "stream_mode": "values",
                "config": args.get("config", {}),
            }
            final_state = None
            last_printed_id = None
            prev_fields = {}  # track report field lengths to detect changes

            for chunk in self.graph.stream(init_agent_state, **stream_kwargs):
                final_state = chunk

                if on_node is not None:
                    # Detect which phase just progressed by watching state fields
                    cur_fields = {
                        k: len(chunk.get(k, "") or "")
                        for k in (
                            "market_report", "sentiment_report", "news_report",
                            "fundamentals_report", "china_market_report",
                            "etf_market_report", "etf_flow_report", "etf_news_report", "etf_product_report",
                            "investment_plan", "trader_investment_plan",
                            "final_trade_decision",
                        )
                    }
                    # Also track debate / risk counts
                    inv_count = chunk.get("investment_debate_state", {}).get("count", 0)
                    risk_count = chunk.get("risk_debate_state", {}).get("count", 0)
                    cur_fields["_inv_count"] = inv_count
                    cur_fields["_risk_count"] = risk_count

                    if cur_fields != prev_fields:
                        # Figure out which field changed
                        for field, val in cur_fields.items():
                            if val != prev_fields.get(field, 0):
                                on_node(field)
                        prev_fields = cur_fields

                if self.debug:
                    msgs = chunk.get("messages", [])
                    if msgs:
                        last_msg = msgs[-1]
                        msg_id = getattr(last_msg, "id", id(last_msg))
                        if msg_id != last_printed_id:
                            last_msg.pretty_print()
                            last_printed_id = msg_id
        else:
            # Standard mode without tracing
            final_state = self.graph.invoke(init_agent_state, **args)

        # Store current state for reflection
        self.curr_state = final_state

        # Log state
        self._log_state(trade_date, final_state)

        # Process signal
        decision = self.process_signal(final_state["final_trade_decision"])

        # Generate markdown report
        self._generate_report(trade_date, final_state, decision)

        # Return decision and processed signal
        return final_state, decision

    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "asset_type": final_state.get("asset_type", self._asset_type),
            "analysis_mode": final_state.get("analysis_mode", self._analysis_mode),
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "china_market_report": final_state.get("china_market_report", ""),
            "etf_market_report": final_state.get("etf_market_report", ""),
            "etf_flow_report": final_state.get("etf_flow_report", ""),
            "etf_news_report": final_state.get("etf_news_report", ""),
            "etf_product_report": final_state.get("etf_product_report", ""),
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "aggressive_history": final_state["risk_debate_state"]["aggressive_history"],
                "conservative_history": final_state["risk_debate_state"]["conservative_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
        }

        # Save to file
        directory = Path(f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/")
        directory.mkdir(parents=True, exist_ok=True)

        with open(
            f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/full_states_log_{trade_date}.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(self.log_states_dict, f, indent=4)

    def reflect_and_remember(self, returns_losses):
        """Reflect on decisions and update memory based on returns."""
        memories = self._get_memories(self._current_market)
        self.reflector.reflect_bull_researcher(
            self.curr_state, returns_losses, memories["bull"]
        )
        self.reflector.reflect_bear_researcher(
            self.curr_state, returns_losses, memories["bear"]
        )
        self.reflector.reflect_trader(
            self.curr_state, returns_losses, memories["trader"]
        )
        self.reflector.reflect_invest_judge(
            self.curr_state, returns_losses, memories["invest_judge"]
        )
        self.reflector.reflect_risk_manager(
            self.curr_state, returns_losses, memories["risk_manager"]
        )

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision.

        Returns a dict: {action, target_price, confidence, risk_score, reasoning}
        """
        return self.signal_processor.process_signal(full_signal, self.ticker)

    def _generate_report(self, trade_date, final_state, decision):
        """Generate a markdown analysis report in docs/reports/.

        Each execution produces one .md file containing all agent outputs.
        """
        from datetime import datetime as _dt

        ticker = final_state["company_of_interest"]
        report_dir = Path(
            os.path.join(self.config.get("project_dir", "."), "docs", "reports")
        )
        report_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{ticker}_{trade_date}_report.md"
        filepath = report_dir / filename

        final_decision = str(final_state.get("final_trade_decision", "")).strip()
        asset_type = final_state.get("asset_type", self._asset_type)
        report_title = "ETF 分析报告" if asset_type == "etf" else "股票分析报告"
        market_title = "ETF 市场分析报告" if asset_type == "etf" else "市场分析报告"
        fundamentals_title = "ETF 产品分析报告" if asset_type == "etf" else "基本面分析报告"
        news_title = "ETF 新闻分析报告" if asset_type == "etf" else "新闻分析报告"
        sentiment_title = "ETF 资金流与情绪分析报告" if asset_type == "etf" else "社交情绪分析报告"

        # Build report sections
        lines = [
            f"# {report_title} — {ticker}",
            f"",
            f"- **分析日期**: {trade_date}",
            f"- **生成时间**: {_dt.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"---",
            f"",
            f"## 决策摘要",
            f"",
            f"| 项目 | 结果 |",
            f"|------|------|",
            f"| 操作建议 | {decision.get('action', 'N/A')} |",
            f"| 目标价 | {decision.get('target_price', 'N/A')} |",
            f"| 置信度 | {decision.get('confidence', 'N/A')} |",
            f"| 风险评分 | {decision.get('risk_score', 'N/A')} |",
            f"",
            f"**决策理由**: {decision.get('reasoning', 'N/A')}",
            f"",
            f"---",
            f"",
        ]

        # Phase 1: Analyst Reports
        report_sections = [
            (market_title, "market_report"),
            (fundamentals_title, "fundamentals_report"),
            (news_title, "news_report"),
            (sentiment_title, "sentiment_report"),
            ("中国市场分析报告", "china_market_report"),
        ]
        for title, key in report_sections:
            content = final_state.get(key, "")
            if content and len(content.strip()) > 0:
                lines.append(f"## {title}")
                lines.append("")
                lines.append(content.strip())
                lines.append("")
                lines.append("---")
                lines.append("")

        # Phase 2: Investment Debate
        debate = final_state.get("investment_debate_state", {})
        if debate:
            lines.append("## 投资辩论")
            lines.append("")
            bull = debate.get("bull_history", "")
            if bull:
                lines.append("### 看涨研究员")
                lines.append("")
                lines.append(bull.strip())
                lines.append("")
            bear = debate.get("bear_history", "")
            if bear:
                lines.append("### 看跌研究员")
                lines.append("")
                lines.append(bear.strip())
                lines.append("")
            judge = debate.get("judge_decision", "")
            if judge:
                lines.append("### 研究经理决策")
                lines.append("")
                lines.append(judge.strip())
                lines.append("")
            lines.append("---")
            lines.append("")

        # Phase 2.5: Trader Plan
        trader_plan = final_state.get("trader_investment_plan", "")
        if trader_plan:
            lines.append("## 交易员投资计划")
            lines.append("")
            lines.append(trader_plan.strip())
            lines.append("")
            lines.append("---")
            lines.append("")

        # Phase 3: Risk Debate
        risk = final_state.get("risk_debate_state", {})
        if risk:
            lines.append("## 风险辩论")
            lines.append("")
            for role, key in [
                ("激进风控分析师", "aggressive_history"),
                ("保守风控分析师", "conservative_history"),
                ("中性风控分析师", "neutral_history"),
            ]:
                content = risk.get(key, "")
                if content:
                    lines.append(f"### {role}")
                    lines.append("")
                    lines.append(content.strip())
                    lines.append("")
            risk_judge = risk.get("judge_decision", "")
            if risk_judge and risk_judge.strip() != final_decision:
                lines.append("### 风险经理最终决策")
                lines.append("")
                lines.append(risk_judge.strip())
                lines.append("")
            lines.append("---")
            lines.append("")

        # Final Decision
        if final_decision:
            lines.append("## 最终交易决策")
            lines.append("")
            lines.append(final_decision.strip())
            lines.append("")

        # Write file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
