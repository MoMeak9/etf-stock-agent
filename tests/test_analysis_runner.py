import unittest
from unittest.mock import patch

from tradingagents.api.job_store import JobStore
from tradingagents.api.runner import AnalysisJobRunner
from tradingagents.services.analysis_service import AnalysisRequest


class AnalysisRunnerTests(unittest.TestCase):
    def test_submit_creates_job_and_completes_with_fake_executor(self):
        store = JobStore()
        runner = AnalysisJobRunner(store=store, max_workers=1)
        self.addCleanup(runner.shutdown)

        def fake_submit(fn, payload):
            class FakeFuture:
                def add_done_callback(self, callback):
                    callback(self)

                def result(self):
                    return {
                        "status": "success",
                        "results": [{"ticker": "600519", "status": "success"}],
                    }

            return FakeFuture()

        with patch.object(runner._executor, "submit", side_effect=fake_submit):
            job = runner.submit(
                AnalysisRequest(tickers=["600519"], date="2026-05-22")
            )

        stored = store.get_job(job["job_id"])
        self.assertEqual(stored["status"], "success")
        self.assertEqual(stored["result"]["status"], "success")


if __name__ == "__main__":
    unittest.main()
