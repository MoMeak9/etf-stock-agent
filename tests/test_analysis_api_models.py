import unittest

from tradingagents.api.job_store import JobStore
from tradingagents.api.schemas import AnalysisJobCreate


class AnalysisApiModelTests(unittest.TestCase):
    def test_request_defaults(self):
        payload = AnalysisJobCreate(tickers=["600519"])

        self.assertEqual(payload.level, 2)
        self.assertEqual(payload.asset_type, "stock")
        self.assertEqual(payload.workers, 1)

    def test_job_store_lifecycle(self):
        store = JobStore()
        job = store.create_job({"tickers": ["600519"]})

        self.assertEqual(job["status"], "queued")
        self.assertEqual(store.get_job(job["job_id"])["job_id"], job["job_id"])

        store.mark_running(job["job_id"])
        store.mark_succeeded(job["job_id"], {"status": "success", "results": []})

        stored = store.get_job(job["job_id"])
        self.assertEqual(stored["status"], "success")
        self.assertEqual(stored["result"]["status"], "success")


if __name__ == "__main__":
    unittest.main()
