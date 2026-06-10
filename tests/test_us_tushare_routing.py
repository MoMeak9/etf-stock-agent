import unittest
from unittest.mock import Mock, patch

import pandas as pd

from tradingagents.dataflows import interface
from tradingagents.dataflows.tushare_stock import get_stock_data


class UsTushareRoutingTests(unittest.TestCase):
    def test_tushare_fetches_us_daily_for_us_symbol(self):
        fake_pro = Mock()
        fake_pro.us_daily.return_value = pd.DataFrame(
            [
                {
                    "trade_date": "20260602",
                    "open": 180.1,
                    "high": 182.0,
                    "low": 179.5,
                    "close": 181.2,
                    "vol": 1234567,
                }
            ]
        )

        with patch("tradingagents.dataflows.tushare_stock._get_tushare_api", return_value=fake_pro):
            result = get_stock_data("NVDA", "2026-06-01", "2026-06-03")

        fake_pro.us_daily.assert_called_once_with(
            ts_code="NVDA.O",
            start_date="20260601",
            end_date="20260603",
        )
        self.assertIn("# Market: US stock (USD) [tushare]", result)
        self.assertIn("2026-06-02", result)

    def test_tushare_maps_common_nyse_symbol_suffix(self):
        fake_pro = Mock()
        fake_pro.us_daily.return_value = pd.DataFrame(
            [
                {
                    "trade_date": "20260602",
                    "open": 270.1,
                    "high": 271.0,
                    "low": 269.5,
                    "close": 270.2,
                    "vol": 1234567,
                }
            ]
        )

        with patch("tradingagents.dataflows.tushare_stock._get_tushare_api", return_value=fake_pro):
            get_stock_data("IBM", "2026-06-01", "2026-06-03")

        fake_pro.us_daily.assert_called_once_with(
            ts_code="IBM.N",
            start_date="20260601",
            end_date="20260603",
        )

    def test_us_route_can_fallback_from_yfinance_to_tushare(self):
        def failing_yfinance(*args, **kwargs):
            raise RuntimeError("yfinance unavailable")

        def fake_tushare(*args, **kwargs):
            return "tushare us data"

        methods = {
            "get_stock_data": {
                "yfinance": failing_yfinance,
                "tushare": fake_tushare,
            }
        }

        config = {
            "asset_type": "stock",
            "data_vendors": {"core_stock_apis": "yfinance"},
            "tool_vendors": {},
        }

        with patch.object(interface, "VENDOR_METHODS", methods), patch.object(
            interface, "get_config", return_value=config
        ):
            result = interface.route_to_vendor(
                "get_stock_data",
                "NVDA",
                "2026-06-01",
                "2026-06-03",
            )

        self.assertEqual(result, "tushare us data")


if __name__ == "__main__":
    unittest.main()
