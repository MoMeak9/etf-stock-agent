import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from tradingagents.api.job_store import JobStore
from tradingagents.api.main import create_app


class FakeRunner:
    def __init__(self, store):
        self.store = store

    def submit(self, request):
        job = self.store.create_job(
            {
                "tickers": request.tickers,
                "level": request.level,
                "date": request.date,
                "asset_type": request.asset_type,
                "provider": request.provider,
                "deep_model": request.deep_model,
                "quick_model": request.quick_model,
                "backend_url": request.backend_url,
                "cn_vendor": request.cn_vendor,
                "debug": request.debug,
                "workers": request.workers,
            }
        )
        self.store.mark_succeeded(
            job["job_id"],
            {
                "status": "success",
                "results": [{"ticker": request.tickers[0], "status": "success"}],
            },
        )
        return self.store.get_job(job["job_id"])


class AnalysisApiTests(unittest.TestCase):
    def setUp(self):
        self.store = JobStore()
        self.env = patch.dict(os.environ, {"ANALYSIS_API_TOKEN": "test-token"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.app = create_app(store=self.store, runner=FakeRunner(self.store))
        self.client = TestClient(self.app)
        self.headers = {"Authorization": "Bearer test-token"}

    def test_healthz_does_not_require_token(self):
        response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_create_job_requires_token(self):
        response = self.client.post(
            "/api/v1/analysis/jobs",
            json={"tickers": ["600519"], "date": "2026-05-22"},
        )

        self.assertEqual(response.status_code, 401)

    def test_create_and_read_job_result(self):
        created = self.client.post(
            "/api/v1/analysis/jobs",
            headers=self.headers,
            json={"tickers": ["600519"], "date": "2026-05-22"},
        )

        self.assertEqual(created.status_code, 201)
        job_id = created.json()["job_id"]

        detail = self.client.get(
            f"/api/v1/analysis/jobs/{job_id}", headers=self.headers
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["status"], "success")

        result = self.client.get(
            f"/api/v1/analysis/jobs/{job_id}/result", headers=self.headers
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["result"]["status"], "success")

    def test_unknown_job_returns_404(self):
        response = self.client.get("/api/v1/analysis/jobs/missing", headers=self.headers)

        self.assertEqual(response.status_code, 404)

    def test_report_endpoint_returns_404_when_report_missing(self):
        created = self.client.post(
            "/api/v1/analysis/jobs",
            headers=self.headers,
            json={"tickers": ["600519"], "date": "2026-05-22"},
        )
        job_id = created.json()["job_id"]

        response = self.client.get(
            f"/api/v1/analysis/jobs/{job_id}/reports/600519",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 404)

    def test_report_endpoint_downloads_markdown_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "600519_2026-05-22_report.md"
            report_path.write_text("# Report\n\nDecision", encoding="utf-8")
            job = self.store.create_job({"tickers": ["600519"]})
            self.store.mark_succeeded(
                job["job_id"],
                {
                    "status": "success",
                    "results": [
                        {
                            "ticker": "600519",
                            "status": "success",
                            "report_path": str(report_path),
                        }
                    ],
                },
            )

            response = self.client.get(
                f"/api/v1/analysis/jobs/{job['job_id']}/reports/600519",
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "# Report\n\nDecision")
        self.assertIn("text/markdown", response.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
