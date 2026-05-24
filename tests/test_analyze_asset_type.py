import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analyze


class AnalyzeAssetTypeTests(unittest.TestCase):
    def test_etf_asset_type_selects_etf_analysts_and_config(self):
        args = analyze.parse_args(["159949", "--asset-type", "etf", "-l", "3"])
        intensity = analyze.resolve_intensity(args)
        config = analyze.build_config(args, intensity)

        self.assertEqual(config["asset_type"], "etf")
        self.assertEqual(intensity["analysts"], ["market", "flow", "news", "product"])

    def test_auto_asset_type_detects_a_share_etf(self):
        args = analyze.parse_args(["159949", "--asset-type", "auto"])
        asset_type = analyze.resolve_asset_type(args.tickers, args.asset_type)

        self.assertEqual(asset_type, "etf")

    def test_auto_asset_type_rejects_mixed_stock_and_etf_batch(self):
        with self.assertRaisesRegex(ValueError, "mixed"):
            analyze.resolve_asset_type(["159949", "600519"], "auto")

    def test_stock_mode_remains_default(self):
        args = analyze.parse_args(["600519"])
        intensity = analyze.resolve_intensity(args)
        config = analyze.build_config(args, intensity)

        self.assertEqual(args.asset_type, "stock")
        self.assertEqual(config["asset_type"], "stock")
        self.assertEqual(intensity["analysts"], ["market", "fundamentals"])


if __name__ == "__main__":
    unittest.main()
