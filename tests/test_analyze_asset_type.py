import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analyze
from tradingagents.dataflows.fund_models import FundAdmission


class AnalyzeAssetTypeTests(unittest.TestCase):
    def test_etf_asset_type_selects_etf_analysts_and_config(self):
        args = analyze.parse_args(["159949", "--asset-type", "etf", "-l", "3"])
        intensity = analyze.resolve_intensity(args)
        config = analyze.build_config(args, intensity)

        self.assertEqual(config["asset_type"], "etf")
        self.assertEqual(intensity["analysts"], ["market", "flow", "news", "product"])

    def test_fund_asset_type_selects_fund_analysts_and_config(self):
        args = analyze.parse_args(["008763", "--asset-type", "fund", "-l", "3"])
        intensity = analyze.resolve_intensity(args)
        config = analyze.build_config(args, intensity)

        self.assertEqual(config["asset_type"], "fund")
        self.assertEqual(intensity["analysts"], ["nav", "product", "portfolio", "event"])
        self.assertEqual(
            config["selected_fund_analysts"],
            ["nav", "product", "portfolio", "event"],
        )

    def test_auto_asset_type_detects_a_share_etf(self):
        args = analyze.parse_args(["159949", "--asset-type", "auto"])
        asset_type = analyze.resolve_asset_type(args.tickers, args.asset_type)

        self.assertEqual(asset_type, "etf")

    def test_auto_asset_type_detects_open_fund(self):
        admission = FundAdmission(
            symbol="008763",
            ts_code="008763.OF",
            is_supported=True,
            fund_type="qdii",
        )
        with patch("tradingagents.dataflows.fund_registry.admit_fund", return_value=admission):
            self.assertEqual(analyze.resolve_asset_type(["008763"], "auto"), "fund")

    def test_auto_asset_type_rejects_mixed_stock_and_etf_batch(self):
        with self.assertRaisesRegex(ValueError, "mixed"):
            analyze.resolve_asset_type(["159949", "600519"], "auto")

    def test_default_auto_resolves_stock(self):
        args = analyze.parse_args(["600519"])
        intensity = analyze.resolve_intensity(args)
        config = analyze.build_config(args, intensity)

        self.assertEqual(args.asset_type, "stock")
        self.assertEqual(config["asset_type"], "stock")
        self.assertEqual(intensity["analysts"], ["market", "fundamentals"])

    def test_default_auto_stock_does_not_probe_fund_registry(self):
        with patch(
            "tradingagents.dataflows.fund_registry.admit_fund",
            side_effect=AssertionError("fund registry should not be probed for obvious stocks"),
        ):
            args = analyze.parse_args(["600519"])

        self.assertEqual(args.asset_type, "stock")


if __name__ == "__main__":
    unittest.main()
