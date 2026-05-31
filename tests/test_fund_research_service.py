import unittest
from unittest.mock import patch

import pandas as pd

from tradingagents.dataflows.fund_models import FundAdmission, FundDataQuality


class FundResearchServiceTests(unittest.TestCase):
    def _admission(self, profile=None, fund_type="hybrid"):
        return FundAdmission(
            symbol="008763",
            ts_code="008763.OF",
            is_supported=True,
            fund_type=fund_type,
            profile=profile or {"name": "测试基金", "fund_type": fund_type},
            quality=FundDataQuality(status="ok"),
        )

    def test_build_nav_package_computes_return_and_negative_drawdown(self):
        from tradingagents.dataflows.fund_research_service import build_nav_package

        nav = pd.DataFrame(
            [
                {"nav_date": "20240101", "unit_nav": "1.00"},
                {"nav_date": "20240102", "unit_nav": "1.20"},
                {"nav_date": "20240103", "unit_nav": "0.90"},
                {"nav_date": "20240104", "unit_nav": "1.10"},
            ]
        )
        with patch("tradingagents.dataflows.fund_research_service.admit_fund", return_value=self._admission()), patch(
            "tradingagents.dataflows.tushare_fund.fetch_fund_nav", return_value=nav
        ), patch("tradingagents.dataflows.akshare_fund.fetch_fund_nav") as ak_fetch:
            package = build_nav_package("008763", "2024-01-04")

        ak_fetch.assert_not_called()
        self.assertEqual(package.package_type, "nav")
        self.assertAlmostEqual(package.metrics["period_return"], 0.10)
        self.assertLess(package.metrics["max_drawdown"], 0)
        self.assertAlmostEqual(package.metrics["max_drawdown"], -0.25)
        self.assertAlmostEqual(package.metrics["latest_nav"], 1.10)
        self.assertEqual(package.quality.as_of_date, "2024-01-04")

    def test_build_product_package_records_missing_purchase_status(self):
        from tradingagents.dataflows.fund_research_service import build_product_package

        with patch(
            "tradingagents.dataflows.fund_research_service.admit_fund",
            return_value=self._admission(profile={"name": "测试基金", "fund_type": "混合型"}),
        ):
            package = build_product_package("008763", "2024-01-04")

        self.assertEqual(package.package_type, "product")
        self.assertEqual(package.status, "partial")
        self.assertIn("purchase_status", package.quality.missing_fields)
        self.assertIn("redemption_status", package.quality.missing_fields)

    def test_format_fund_research_package_includes_title_and_missing_fields(self):
        from tradingagents.dataflows.fund_research_service import build_product_package, format_fund_research_package

        with patch(
            "tradingagents.dataflows.fund_research_service.admit_fund",
            return_value=self._admission(profile={"name": "测试基金", "fund_type": "混合型"}),
        ):
            formatted = format_fund_research_package(build_product_package("008763", "2024-01-04"))

        self.assertIn("# Fund Product Research Package for 008763", formatted)
        self.assertIn("Missing Fields", formatted)
        self.assertIn("purchase_status", formatted)

    def test_build_macro_package_uses_global_macro_news_for_qdii(self):
        from tradingagents.dataflows.fund_research_service import build_macro_package

        with patch(
            "tradingagents.dataflows.fund_research_service.admit_fund",
            return_value=self._admission(fund_type="qdii", profile={"name": "QDII基金", "fund_type": "QDII"}),
        ), patch(
            "tradingagents.dataflows.fund_research_service.fetch_global_macro_news",
            return_value="FX pressure and overseas rates matter.",
        ):
            package = build_macro_package("008763", "2024-01-04")

        self.assertEqual(package.package_type, "macro")
        self.assertEqual(package.fund_type, "qdii")
        self.assertIn("global_macro_news", package.raw_summary)
        self.assertIn("fx", package.metrics["macro_focus"])
        self.assertEqual(package.metrics["analysis_horizon"], "medium_to_long_term")


if __name__ == "__main__":
    unittest.main()
