import unittest
from unittest.mock import patch

import pandas as pd

from tradingagents.dataflows.fund_registry import admit_fund, classify_fund, clear_fund_admission_cache


class FundRegistryTests(unittest.TestCase):
    def setUp(self):
        clear_fund_admission_cache()

    def test_admits_qdii_open_fund_from_tushare(self):
        profile = pd.DataFrame(
            [
                {
                    "ts_code": "008763.OF",
                    "name": "天弘越南市场股票发起(QDII)A",
                    "fund_type": "QDII",
                    "management": "天弘基金",
                }
            ]
        )
        with patch("tradingagents.dataflows.tushare_fund.fetch_fund_basic", return_value=profile):
            admission = admit_fund("008763")

        self.assertTrue(admission.is_supported)
        self.assertEqual(admission.symbol, "008763")
        self.assertEqual(admission.fund_type, "qdii")
        self.assertEqual(admission.quality.status, "ok")
        self.assertEqual(admission.quality.primary_source, "tushare")

    def test_rejects_etf_code_in_fund_mode(self):
        admission = admit_fund("159949")

        self.assertFalse(admission.is_supported)
        self.assertEqual(admission.quality.status, "blocked")
        self.assertIn("use asset_type=etf", admission.reason)

    def test_falls_back_to_akshare_when_tushare_empty(self):
        ak_profile = pd.DataFrame(
            [
                {
                    "基金代码": "008763",
                    "基金简称": "天弘越南市场股票发起(QDII)A",
                    "基金类型": "QDII",
                }
            ]
        )
        with patch("tradingagents.dataflows.tushare_fund.fetch_fund_basic", return_value=pd.DataFrame()), patch(
            "tradingagents.dataflows.akshare_fund.fetch_fund_basic", return_value=ak_profile
        ):
            admission = admit_fund("008763")

        self.assertTrue(admission.is_supported)
        self.assertEqual(admission.fund_type, "qdii")
        self.assertEqual(admission.quality.fallback_source, "akshare")

    def test_unknown_type_is_partial_but_supported(self):
        profile = pd.DataFrame([{"ts_code": "009999.OF", "name": "测试基金", "fund_type": "其他"}])
        with patch("tradingagents.dataflows.tushare_fund.fetch_fund_basic", return_value=profile):
            admission = admit_fund("009999")

        self.assertTrue(admission.is_supported)
        self.assertEqual(admission.fund_type, "unknown")
        self.assertEqual(admission.quality.status, "partial")

    def test_rejects_non_six_digit_fund_code(self):
        admission = admit_fund("123")

        self.assertFalse(admission.is_supported)
        self.assertEqual(admission.quality.status, "blocked")
        self.assertIn("six_digit_fund_code", admission.quality.missing_fields)

    def test_classifies_supported_fund_categories(self):
        cases = [
            ({"fund_type": "QDII"}, "qdii"),
            ({"fund_type": "货币型"}, "money_market"),
            ({"fund_type": "bond"}, "bond"),
            ({"fund_type": "FOF"}, "fof"),
            ({"fund_type": "指数型"}, "index"),
            ({"fund_type": "hybrid"}, "hybrid"),
            ({"fund_type": "股票型"}, "equity"),
            ({"fund_type": "其他"}, "unknown"),
        ]

        for profile, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(classify_fund(profile), expected)

    def test_blocks_when_tushare_and_akshare_metadata_empty(self):
        with patch("tradingagents.dataflows.tushare_fund.fetch_fund_basic", return_value=pd.DataFrame()), patch(
            "tradingagents.dataflows.akshare_fund.fetch_fund_basic", return_value=pd.DataFrame()
        ):
            admission = admit_fund("008763")

        self.assertFalse(admission.is_supported)
        self.assertEqual(admission.quality.status, "blocked")
        self.assertIn("fund_basic", admission.quality.missing_fields)


if __name__ == "__main__":
    unittest.main()
