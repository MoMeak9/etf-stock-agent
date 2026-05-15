import sys
import types
import unittest

rank_bm25_stub = types.ModuleType("rank_bm25")
rank_bm25_stub.BM25Okapi = object
sys.modules.setdefault("rank_bm25", rank_bm25_stub)

from tradingagents.agents.analysts import etf_market_analyst
from tradingagents.agents.utils import etf_prompt_utils


class ETFAnalystHelperTests(unittest.TestCase):
    def test_market_helper_adds_price_and_indicator_calls(self):
        planned_calls = etf_market_analyst._build_etf_market_tool_calls(
            ticker="510300",
            current_date="2025-03-27",
            existing_tool_calls=[],
        )

        self.assertTrue(any(call["name"] == "get_etf_price_data" for call in planned_calls))
        self.assertTrue(any(call["name"] == "get_etf_indicators" for call in planned_calls))
        self.assertTrue(any(call["args"].get("indicator") == "macd" for call in planned_calls if call["name"] == "get_etf_indicators"))

    def test_product_prompt_mentions_profile_holdings_discount_and_tracking(self):
        prompt = etf_prompt_utils.build_etf_product_prompt("510300", "宽基 ETF")

        self.assertIn("profile", prompt)
        self.assertIn("holding", prompt.lower())
        self.assertIn("折溢价", prompt)
        self.assertIn("跟踪信息", prompt)
        self.assertNotIn("PE", prompt)
        self.assertNotIn("PB", prompt)
        self.assertNotIn("PEG", prompt)
        self.assertIn("禁止出现公司财报", prompt)

    def test_news_prompt_focuses_on_etf_and_index_events(self):
        prompt = etf_prompt_utils.build_etf_news_prompt("510300", "行业主题 ETF")

        self.assertIn("ETF 本身", prompt)
        self.assertIn("跟踪指数", prompt)
        self.assertIn("产品事件", prompt)
        self.assertIn("行业景气", prompt)

    def test_flow_prompt_focuses_on_fund_flow_and_crowding(self):
        prompt = etf_prompt_utils.build_etf_flow_prompt("510300", "行业主题 ETF")

        self.assertIn("资金流", prompt)
        self.assertIn("份额变化", prompt)
        self.assertIn("拥挤度", prompt)
        self.assertIn("配置风险提示", prompt)


if __name__ == "__main__":
    unittest.main()
