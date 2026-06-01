from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tradingagents.agents.utils.agent_states import apply_asset_report_mapping
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.setup import GraphSetup


def test_fund_tool_formats_package():
    from tradingagents.agents.utils.fund_data_tools import get_fund_nav

    package = SimpleNamespace(
        symbol="008763",
        fund_type="qdii",
        package_type="nav",
        status="ok",
        quality=SimpleNamespace(
            status="ok",
            primary_source="tushare",
            fallback_source="none",
            as_of_date="2026-05-31",
            warnings=[],
            missing_fields=[],
        ),
        metrics={"latest_nav": 1.2345},
        raw_summary={"rows": 10},
    )

    with patch(
        "tradingagents.agents.utils.fund_data_tools.build_nav_package",
        return_value=package,
    ):
        output = get_fund_nav.invoke({"symbol": "008763", "curr_date": "2026-05-31"})

    assert "Fund Nav Research Package" in output


def test_fund_report_mapping():
    update = {
        "fund_nav_report": "nav report",
        "fund_product_report": "product report",
    }

    mapped = apply_asset_report_mapping(update, "fund")

    assert mapped["market_report"] == "nav report"
    assert mapped["fundamentals_report"] == "product report"


class FundToolsAndGraphTests(unittest.TestCase):
    def test_graph_setup_accepts_fund_analysts(self):
        class FakeLLM:
            def invoke(self, _prompt):
                return SimpleNamespace(content="fake response")

        setup = GraphSetup(
            quick_thinking_llm=FakeLLM(),
            deep_thinking_llm=FakeLLM(),
            tool_nodes={},
            bull_memory=None,
            bear_memory=None,
            trader_memory=None,
            invest_judge_memory=None,
            risk_manager_memory=None,
            conditional_logic=ConditionalLogic(),
        )

        graph = setup.setup_graph(
            selected_analysts=["nav", "product", "portfolio", "event"],
            asset_type="fund",
        )

        self.assertIsNotNone(graph)
