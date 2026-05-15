import unittest
from datetime import datetime

from tradingagents.agents.analysts import market_analyst


class MarketAnalystToolPlanningTests(unittest.TestCase):
    def test_adds_history_and_indicator_calls_when_only_single_day_stock_data_requested(self):
        current_date = "2025-03-27"
        existing_calls = [
            {
                "name": "get_stock_data",
                "args": {
                    "symbol": "002202",
                    "start_date": current_date,
                    "end_date": current_date,
                },
            }
        ]

        supplemental_calls = market_analyst._build_supplemental_tool_calls(
            ticker="002202",
            current_date=current_date,
            existing_tool_calls=existing_calls,
        )

        stock_calls = [call for call in supplemental_calls if call["name"] == "get_stock_data"]
        indicator_calls = [call for call in supplemental_calls if call["name"] == "get_indicators"]

        self.assertEqual(1, len(stock_calls))
        self.assertLess(stock_calls[0]["args"]["start_date"], current_date)
        self.assertEqual(current_date, stock_calls[0]["args"]["end_date"])
        self.assertTrue(any(call["args"]["indicator"] == "macd" for call in indicator_calls))
        self.assertTrue(any(call["args"]["indicator"] == "rsi" for call in indicator_calls))
        self.assertTrue(any(call["args"]["indicator"] == "boll" for call in indicator_calls))

    def test_analysis_prompt_requires_using_historical_data_for_trend_sections(self):
        prompt = market_analyst._build_market_analysis_prompt(
            company_name="金风科技",
            ticker="002202",
            market_name="中国A股",
            currency_name="人民币",
            currency_symbol="¥",
            current_date="2025-03-27",
            history_start_date="2024-12-27",
        )

        self.assertIn("已提供从 2024-12-27 到 2025-03-27 的历史行情数据", prompt)
        self.assertIn("不要再写“仅有单日数据”", prompt)
        self.assertIn("短期趋势（5-10个交易日）", prompt)
        self.assertIn("中期趋势（20-60个交易日）", prompt)
        self.assertIn("关键价格区间", prompt)

    def test_history_window_is_long_enough_for_ma60(self):
        current_date = "2025-03-27"
        history_start = market_analyst._history_start_date(current_date)

        current_dt = datetime.strptime(current_date, "%Y-%m-%d")
        history_dt = datetime.strptime(history_start, "%Y-%m-%d")

        self.assertGreaterEqual((current_dt - history_dt).days, 180)


if __name__ == "__main__":
    unittest.main()
