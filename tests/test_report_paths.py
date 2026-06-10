import tempfile
import unittest
from pathlib import Path

from analyze import _report_path_for
from tradingagents.graph.trading_graph import TradingAgentsGraph


class ReportPathTests(unittest.TestCase):
    def test_report_path_uses_configured_reports_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = _report_path_for(
                "600519",
                "2026-05-22",
                {"project_dir": "/ignored", "reports_dir": tmpdir},
            )

        self.assertEqual(
            report_path,
            Path(tmpdir) / "600519_2026-05-22_report.md",
        )

    def test_graph_generates_report_in_configured_reports_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = object.__new__(TradingAgentsGraph)
            graph.config = {"project_dir": "/ignored", "reports_dir": tmpdir}
            graph._asset_type = "stock"
            final_state = {
                "company_of_interest": "600519",
                "asset_type": "stock",
                "final_trade_decision": "HOLD",
            }

            graph._generate_report(
                "2026-05-22",
                final_state,
                {"action": "hold", "reasoning": "test"},
            )

            report_path = Path(tmpdir) / "600519_2026-05-22_report.md"
            self.assertTrue(report_path.exists())
            self.assertIn("600519", report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
