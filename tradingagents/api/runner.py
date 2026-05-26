from __future__ import annotations

import traceback
from concurrent.futures import Future, ProcessPoolExecutor
from typing import Dict

from tradingagents.api.job_store import JobStore
from tradingagents.services.analysis_service import (
    AnalysisRequest,
    request_to_json,
    run_analysis_batch_from_payload,
)


class AnalysisJobRunner:
    def __init__(self, store: JobStore, max_workers: int = 2) -> None:
        self.store = store
        self._executor = ProcessPoolExecutor(max_workers=max_workers)
        self._futures: Dict[str, Future] = {}

    def submit(self, request: AnalysisRequest) -> dict:
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
        job_id = job["job_id"]
        self.store.mark_running(job_id)
        future = self._executor.submit(
            run_analysis_batch_from_payload, request_to_json(request)
        )
        self._futures[job_id] = future
        future.add_done_callback(lambda completed: self._complete(job_id, completed))
        return self.store.get_job(job_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _complete(self, job_id: str, future: Future) -> None:
        try:
            result = future.result()
        except Exception as exc:
            self.store.mark_failed(job_id, f"{exc}\n{traceback.format_exc()}")
            return

        if result.get("status") == "success":
            self.store.mark_succeeded(job_id, result)
            return

        self.store.mark_failed_with_result(
            job_id,
            result.get("error", "analysis failed"),
            result,
        )
