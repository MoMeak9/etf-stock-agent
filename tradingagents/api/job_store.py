from __future__ import annotations

import copy
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def create_job(self, request: Dict[str, Any]) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex
        now = _now()
        job = {
            "job_id": job_id,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "request": copy.deepcopy(request),
            "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
        return copy.deepcopy(job)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def mark_running(self, job_id: str) -> None:
        self._update(job_id, status="running")

    def mark_succeeded(self, job_id: str, result: Dict[str, Any]) -> None:
        self._update(job_id, status="success", result=copy.deepcopy(result), error=None)

    def mark_failed(self, job_id: str, error: str) -> None:
        self._update(job_id, status="error", error=error)

    def mark_failed_with_result(
        self, job_id: str, error: str, result: Dict[str, Any]
    ) -> None:
        self._update(job_id, status="error", error=error, result=copy.deepcopy(result))

    def _update(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.update(fields)
            job["updated_at"] = _now()
