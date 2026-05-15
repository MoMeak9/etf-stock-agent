import sys
import types
import unittest

rank_bm25_stub = types.ModuleType("rank_bm25")


class DummyBM25:
    def __init__(self, *args, **kwargs):
        pass


rank_bm25_stub.BM25Okapi = DummyBM25
sys.modules.setdefault("rank_bm25", rank_bm25_stub)

from langgraph.prebuilt import ToolNode

from tradingagents.agents.utils.agent_states import apply_asset_report_mapping
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.trader.trader import create_trader
from tradingagents.agents.managers.risk_manager import create_risk_manager
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.propagation import Propagator
from tradingagents.graph.signal_processing import SignalProcessor
from tradingagents.graph.setup import GraphSetup


class _DummyLLM:
    pass


class _FakeLLM:
    def __init__(self, content):
        self.content = content
        self.last_input = None

    def invoke(self, payload):
        self.last_input = payload
        return types.SimpleNamespace(content=self.content, response_metadata={})


class ETFGraphTests(unittest.TestCase):
    def _build_etf_state(self):
        return {
            "asset_type": "etf",
            "company_of_interest": "510300",
            "trade_date": "2025-03-27",
            "market_report": "ETF 市场报告：趋势向上。",
            "sentiment_report": "ETF 资金流报告：份额增加。",
            "news_report": "ETF 新闻报告：主题催化增强。",
            "fundamentals_report": "ETF 产品报告：流动性充足，折溢价可控。",
            "investment_plan": "交易结论：买入\n配置结论：适合配置",
            "trader_investment_plan": "交易建议：买入\n配置建议：适合配置",
            "investment_debate_state": {
                "history": "Bull Analyst: 看多\nBear Analyst: 看空",
                "bull_history": "",
                "bear_history": "",
                "current_response": "Bear Analyst: 看空",
                "judge_decision": "",
                "count": 2,
            },
            "risk_debate_state": {
                "history": "Aggressive Analyst: 买入\nConservative Analyst: 谨慎",
                "aggressive_history": "",
                "conservative_history": "",
                "neutral_history": "",
                "latest_speaker": "Conservative",
                "current_aggressive_response": "Aggressive Analyst: 买入",
                "current_conservative_response": "Conservative Analyst: 谨慎",
                "current_neutral_response": "",
                "judge_decision": "",
                "count": 2,
            },
        }

    def test_etf_initial_state_contains_asset_context_and_placeholders(self):
        propagator = Propagator(asset_type="etf", analysis_mode="hybrid")

        state = propagator.create_initial_state("510300", "2025-03-27")

        self.assertEqual("etf", state["asset_type"])
        self.assertEqual("hybrid", state["analysis_mode"])
        self.assertEqual("", state["etf_market_report"])
        self.assertEqual("", state["etf_product_report"])
        self.assertEqual("", state["etf_news_report"])
        self.assertEqual("", state["etf_flow_report"])
        self.assertIn("A 股 ETF 510300", state["messages"][0].content)

    def test_apply_asset_report_mapping_populates_generic_slots(self):
        mapped = apply_asset_report_mapping(
            {
                "etf_market_report": "market report",
                "etf_product_report": "product report",
                "etf_news_report": "news report",
                "etf_flow_report": "flow report",
            },
            "etf",
        )

        self.assertEqual("market report", mapped["market_report"])
        self.assertEqual("product report", mapped["fundamentals_report"])
        self.assertEqual("news report", mapped["news_report"])
        self.assertEqual("flow report", mapped["sentiment_report"])

    def test_etf_graph_compiles_with_etf_analyst_nodes(self):
        setup = GraphSetup(
            _DummyLLM(),
            _DummyLLM(),
            {
                "market": ToolNode([]),
                "flow": ToolNode([]),
                "news": ToolNode([]),
                "product": ToolNode([]),
            },
            None,
            None,
            None,
            None,
            None,
            ConditionalLogic(),
        )

        graph = setup.setup_graph(["market", "flow", "news", "product"], asset_type="etf")
        node_names = set(graph.get_graph().nodes.keys())

        self.assertIn("Market Analyst", node_names)
        self.assertIn("Flow Analyst", node_names)
        self.assertIn("News Analyst", node_names)
        self.assertIn("Product Analyst", node_names)
        self.assertNotIn("Social Analyst", node_names)
        self.assertNotIn("Fundamentals Analyst", node_names)

    def test_stock_graph_still_compiles(self):
        setup = GraphSetup(
            _DummyLLM(),
            _DummyLLM(),
            {
                "market": ToolNode([]),
                "social": ToolNode([]),
                "news": ToolNode([]),
                "fundamentals": ToolNode([]),
            },
            None,
            None,
            None,
            None,
            None,
            ConditionalLogic(),
        )

        graph = setup.setup_graph(["market", "social", "news", "fundamentals"], asset_type="stock")
        node_names = set(graph.get_graph().nodes.keys())

        self.assertIn("Social Analyst", node_names)
        self.assertIn("Fundamentals Analyst", node_names)

    def test_bull_researcher_uses_etf_specific_prompt_language(self):
        llm = _FakeLLM("看涨")
        node = create_bull_researcher(llm, memory=None)

        node(self._build_etf_state())

        self.assertIn("ETF", llm.last_input)
        self.assertIn("配置价值", llm.last_input)
        self.assertIn("流动性", llm.last_input)

    def test_research_manager_requires_trading_and_allocation_conclusions_for_etf(self):
        llm = _FakeLLM("交易结论：买入\n配置结论：适合配置")
        node = create_research_manager(llm, memory=None)

        result = node(self._build_etf_state())

        self.assertIn("交易结论", llm.last_input)
        self.assertIn("配置结论", llm.last_input)
        self.assertIn("配置结论：适合配置", result["investment_plan"])

    def test_trader_prompt_requests_etf_dual_track_output(self):
        llm = _FakeLLM("交易建议：买入\n配置建议：适合配置\n最终交易建议: **买入**")
        node = create_trader(llm, memory=None)

        result = node(self._build_etf_state())
        system_prompt = llm.last_input[0]["content"]

        self.assertIn("ETF", system_prompt)
        self.assertIn("配置建议", system_prompt)
        self.assertIn("折溢价", system_prompt)
        self.assertIn("交易建议：买入", result["trader_investment_plan"])

    def test_risk_manager_prompt_mentions_etf_specific_risks(self):
        llm = _FakeLLM("交易建议：持有\n配置建议：暂不配置")
        node = create_risk_manager(llm, memory=None)

        result = node(self._build_etf_state())

        self.assertIn("跟踪误差", llm.last_input)
        self.assertIn("折溢价", llm.last_input)
        self.assertIn("配置建议", result["final_trade_decision"])

    def test_signal_processor_parses_etf_decision_json(self):
        llm = _FakeLLM('{"action":"买入","target_price":4.2,"confidence":0.8,"risk_score":0.4,"reasoning":"ETF 交易与配置条件共振"}')
        processor = SignalProcessor(llm)

        result = processor.process_signal("ETF 交易建议与配置建议已明确。", "510300")

        self.assertEqual("买入", result["action"])
        self.assertEqual(4.2, result["target_price"])
        self.assertEqual(0.8, result["confidence"])


if __name__ == "__main__":
    unittest.main()
