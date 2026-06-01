import unittest
from unittest.mock import patch

from tradingagents.dataflows.fund_models import FundAdmission
from tradingagents.services.analysis_service import (
    AnalysisRequest,
    prepare_analysis,
    run_analysis_batch,
)


class AnalysisServiceTests(unittest.TestCase):
    def test_prepare_stock_defaults_match_cli(self):
        prepared = prepare_analysis(
            AnalysisRequest(tickers=["600519"], date="2026-05-22")
        )

        self.assertEqual(prepared.asset_type, "stock")
        self.assertEqual(prepared.analysts, ["market", "fundamentals"])
        self.assertEqual(prepared.config["asset_type"], "stock")
        self.assertEqual(prepared.config["llm_provider"], "deepseek")
        self.assertEqual(prepared.original_date, "2026-05-22")
        self.assertEqual(prepared.trade_date, "2026-05-22")

    def test_prepare_etf_selects_etf_profiles(self):
        prepared = prepare_analysis(
            AnalysisRequest(
                tickers=["159949"],
                date="2026-05-22",
                asset_type="etf",
                level=3,
            )
        )

        self.assertEqual(prepared.asset_type, "etf")
        self.assertEqual(prepared.analysts, ["market", "flow", "news", "product"])
        self.assertEqual(prepared.config["asset_type"], "etf")
        self.assertEqual(
            prepared.config["selected_etf_analysts"],
            ["market", "flow", "news", "product"],
        )

    def test_prepare_fund_selects_fund_profiles(self):
        admission = FundAdmission(
            symbol="008763",
            ts_code="008763.OF",
            is_supported=True,
            fund_type="qdii",
        )

        with patch("tradingagents.dataflows.fund_registry.admit_fund", return_value=admission):
            prepared = prepare_analysis(
                AnalysisRequest(tickers=["008763"], asset_type="fund", level=3)
            )

        self.assertEqual(prepared.asset_type, "fund")
        self.assertEqual(prepared.analysts, ["nav", "product", "portfolio", "event"])
        self.assertEqual(prepared.config["asset_type"], "fund")

    def test_run_analysis_batch_uses_analyze_single_for_each_ticker(self):
        fake_result = {
            "ticker": "600519",
            "date": "2026-05-22",
            "status": "success",
            "decision": {"action": "hold"},
            "elapsed": 0.1,
            "stats": {
                "llm_calls": 0,
                "tool_calls": 0,
                "tokens_in": 0,
                "tokens_out": 0,
            },
        }

        with patch(
            "tradingagents.services.analysis_service.analyze.analyze_single",
            return_value=fake_result,
        ) as mocked:
            result = run_analysis_batch(
                AnalysisRequest(tickers=["600519"], date="2026-05-22"),
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["results"], [fake_result])
        self.assertEqual(result["tickers"], ["600519"])
        mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
