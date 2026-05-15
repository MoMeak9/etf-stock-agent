import unittest

from tradingagents.agents.analysts import fundamentals_analyst


class _FakeTool:
    def __init__(self, name, result):
        self.name = name
        self._result = result
        self.calls = []

    def invoke(self, args):
        self.calls.append(args)
        return self._result


class FundamentalsAnalystHelpersTests(unittest.TestCase):
    def test_collect_fundamentals_context_includes_analysis_date_stock_data(self):
        tools = [
            _FakeTool(
                "get_fundamentals",
                "# Company Fundamentals for 000001\n最新股价: 11.02\n总股本: 19405918198\n流通股: 19405600653",
            ),
            _FakeTool(
                "get_stock_data",
                "# Stock data for 000001 from 2025-03-27 to 2025-03-27\nDate,Open,High,Low,Close,Volume\n2025-03-27,10.80,10.85,10.70,10.79,55334900\n",
            ),
            _FakeTool("get_balance_sheet", "balance-sheet-data"),
        ]

        combined = fundamentals_analyst._collect_fundamentals_context(
            tools=tools,
            ticker="000001",
            current_date="2025-03-27",
        )

        self.assertIn("分析日期收盘价: 10.79", combined)
        self.assertIn("总股本: 19405918198", combined)
        self.assertIn("balance-sheet-data", combined)
        self.assertNotIn("最新股价: 11.02", combined)

    def test_prompt_requires_price_alignment_to_analysis_date(self):
        prompt = fundamentals_analyst._build_fundamentals_analysis_prompt(
            company_name="平安银行",
            ticker="000001",
            current_date="2025-03-27",
            currency_info="人民币（¥）",
            combined_data="sample-data",
        )

        self.assertIn("分析日期对应的收盘价", prompt)
        self.assertIn("不得使用晚于分析日期的价格", prompt)
        self.assertIn("sample-data", prompt)

    def test_extract_analysis_date_close_price_from_stock_csv(self):
        stock_data = (
            "# Stock data for 000001 from 2025-03-27 to 2025-03-27\n"
            "Date,Open,High,Low,Close,Volume\n"
            "2025-03-27,10.80,10.85,10.70,10.79,55334900\n"
        )

        close_price = fundamentals_analyst._extract_analysis_date_close_price(
            stock_data=stock_data,
            current_date="2025-03-27",
        )

        self.assertEqual("10.79", close_price)

    def test_normalize_fundamentals_report_rewrites_conflicting_price_mentions(self):
        report = (
            "## 基本面分析报告\n"
            "- **最新股价**：**¥11.02**\n"
            "- 当前股价 **¥11.02**\n"
            "- 股价：¥11.02\n"
        )

        normalized = fundamentals_analyst._normalize_fundamentals_report(
            report=report,
            analysis_date_close_price="10.79",
            current_date="2025-03-27",
        )

        self.assertIn("¥10.79", normalized)
        self.assertNotIn("¥11.02", normalized)


if __name__ == "__main__":
    unittest.main()
