# Analysis API Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing `analyze.py` stock and ETF analysis capability into a local/intranet FastAPI service that accepts analysis jobs and lets users download generated Markdown reports.

**Architecture:** Keep `analyze.py` as the CLI surface, and add a service/API layer that reuses the same analysis primitives instead of duplicating agent logic. HTTP requests create in-memory job records only; a bounded `ProcessPoolExecutor` runs one analysis job per worker process to isolate process-level config mutations; API endpoints expose job status, final results, and generated Markdown report downloads. There is no Redis, SQL database, static database storage, or persistent job metadata in this local/intranet version.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, Pydantic, unittest, FastAPI TestClient, existing LangGraph/TradingAgents analysis stack.

---

## Current Context

The reusable analysis entry points already exist:

- `analyze.py`: `resolve_asset_type`, `resolve_intensity`, `build_config`, `resolve_analysis_date`, `analyze_single`, `_worker`, `_serializable_config`
- `tradingagents/graph/trading_graph.py`: `TradingAgentsGraph.propagate(...)`
- `tradingagents/dataflows/config.py`: market and asset context are thread-local, but `_config` is process-level; API concurrency must avoid running different configs in the same Python process.

Scope boundaries for this version:

- Provide an HTTP analysis service and Markdown report download.
- Store job state only in memory while the API process is alive.
- Keep generated reports on the existing local filesystem path produced by `TradingAgentsGraph._generate_report(...)`.
- Do not add Redis, Celery/RQ, SQLite, Postgres, object storage, static database files, or a frontend/static site.
- Do not guarantee job recovery after API process restart. Restarting the service clears in-memory job IDs and status.

Current baseline issue discovered before this plan:

```bash
python3 -m unittest discover -s tests -p 'test*.py' -v
```

Expected current output before Task 0:

```text
FAILED (errors=3)
```

Root cause: `tests/test_analyze_asset_type.py` expects `parse_args(... --asset-type ...)`, but `analyze.py::parse_args` does not currently add the `--asset-type` option or resolve it before `main()` chooses the intensity profile.

## File Structure

- Modify `analyze.py`
  - Add `--asset-type` CLI option.
  - Resolve `args.asset_type` before choosing stock vs ETF intensity in `main()`.
  - Keep existing CLI behavior for default stock analysis.

- Modify `pyproject.toml`
  - Add FastAPI and Uvicorn runtime dependencies.
  - Add `etf-stock-agent-api` console script.

- Modify `requirements.txt`
  - Add `fastapi` and `uvicorn[standard]` for non-PEP-621 installs.

- Create `tradingagents/services/__init__.py`
  - Package marker for service layer imports.

- Create `tradingagents/services/analysis_service.py`
  - Define service request/result dataclasses.
  - Convert HTTP/API request values into the same config and analyst selection used by CLI.
  - Provide `run_analysis_batch(...)` for synchronous worker execution.
  - Provide `run_analysis_batch_from_payload(...)` for process-pool safe JSON execution.

- Create `tradingagents/api/__init__.py`
  - Package marker for API layer imports.

- Create `tradingagents/api/schemas.py`
  - Pydantic request and response models.

- Create `tradingagents/api/job_store.py`
  - Thread-safe in-memory job store with timestamps, statuses, and final results.

- Create `tradingagents/api/runner.py`
  - Bounded background runner using `ProcessPoolExecutor`.
  - Submit jobs and save final results/errors to in-memory `JobStore`.

- Create `tradingagents/api/main.py`
  - FastAPI app and endpoints.

- Create `tests/test_analysis_service.py`
  - Unit tests for request normalization, date resolution, config construction, and patched analysis execution.

- Create `tests/test_analysis_api.py`
  - API tests for create/get/result/report download flows using a synchronous fake runner.

- Modify `README.md`
  - Add local/intranet API service usage, systemd deployment, endpoint examples, and report download commands.

---

## Task 0: Restore Existing CLI Asset-Type Regression

**Files:**
- Modify: `analyze.py`
- Test: `tests/test_analyze_asset_type.py`

- [ ] **Step 1: Run the existing failing regression**

Run:

```bash
python3 -m unittest tests.test_analyze_asset_type -v
```

Expected: FAIL with `unrecognized arguments: --asset-type`.

- [ ] **Step 2: Add `--asset-type` to `parse_args`**

In `analyze.py`, inside `parse_args`, immediately after the `tickers` argument block, insert:

```python
    parser.add_argument(
        "--asset-type",
        type=str,
        choices=["stock", "etf", "auto"],
        default="stock",
        help="资产类型: stock 股票, etf A股场内ETF, auto 自动识别（默认: stock）",
    )
```

- [ ] **Step 3: Resolve asset type before choosing intensity in `main()`**

Replace this block in `analyze.py::main`:

```python
    args.original_date, args.date = resolve_analysis_date(
        tickers=args.tickers,
        requested_date=args.date,
        date_was_explicit=args.date_was_explicit,
    )
    intensity = INTENSITY_PROFILES[args.level]
    config = build_config(args, intensity)
    analysts = intensity["analysts"]
```

with:

```python
    args.asset_type = resolve_asset_type(args.tickers, args.asset_type)
    args.original_date, args.date = resolve_analysis_date(
        tickers=args.tickers,
        requested_date=args.date,
        date_was_explicit=args.date_was_explicit,
    )
    intensity = resolve_intensity(args)
    config = build_config(args, intensity)
    analysts = intensity["analysts"]
```

- [ ] **Step 4: Run the asset-type tests**

Run:

```bash
python3 -m unittest tests.test_analyze_asset_type -v
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Run the full current test suite**

Run:

```bash
python3 -m unittest discover -s tests -p 'test*.py' -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add analyze.py
git commit -m "fix: restore analyze asset type CLI option"
```

---

## Task 1: Add API Dependencies and Entry Point

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`

- [ ] **Step 1: Add a dependency regression test by checking package metadata**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path("pyproject.toml").read_text()
assert '"fastapi>=' in text
assert '"uvicorn[standard]>=' in text
assert 'etf-stock-agent-api = "tradingagents.api.main:run"' in text
PY
```

Expected: FAIL with `AssertionError`.

- [ ] **Step 2: Add dependencies and script to `pyproject.toml`**

In `[project].dependencies`, after `"akshare>=1.14.0",`, add:

```toml
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
```

In `[project.scripts]`, after `tradingagents = "cli.main:app"`, add:

```toml
etf-stock-agent-api = "tradingagents.api.main:run"
```

- [ ] **Step 3: Add dependencies to `requirements.txt`**

Append:

```text
fastapi
uvicorn[standard]
```

- [ ] **Step 4: Verify metadata**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path("pyproject.toml").read_text()
assert '"fastapi>=' in text
assert '"uvicorn[standard]>=' in text
assert 'etf-stock-agent-api = "tradingagents.api.main:run"' in text
req = Path("requirements.txt").read_text()
assert "fastapi" in req
assert "uvicorn[standard]" in req
PY
```

Expected: PASS with no output.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml requirements.txt
git commit -m "chore: add API service dependencies"
```

---

## Task 2: Create Analysis Service Layer

**Files:**
- Create: `tradingagents/services/__init__.py`
- Create: `tradingagents/services/analysis_service.py`
- Test: `tests/test_analysis_service.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_analysis_service.py` with:

```python
import unittest
from unittest.mock import patch

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
        self.assertEqual(prepared.config["selected_etf_analysts"], ["market", "flow", "news", "product"])

    def test_run_analysis_batch_uses_analyze_single_for_each_ticker(self):
        fake_result = {
            "ticker": "600519",
            "date": "2026-05-22",
            "status": "success",
            "decision": {"action": "hold"},
            "elapsed": 0.1,
            "stats": {"llm_calls": 0, "tool_calls": 0, "tokens_in": 0, "tokens_out": 0},
        }

        with patch("tradingagents.services.analysis_service.analyze.analyze_single", return_value=fake_result) as mocked:
            result = run_analysis_batch(
                AnalysisRequest(tickers=["600519"], date="2026-05-22"),
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["results"], [fake_result])
        self.assertEqual(result["tickers"], ["600519"])
        mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_analysis_service -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tradingagents.services'`.

- [ ] **Step 3: Create service package marker**

Create `tradingagents/services/__init__.py`:

```python
"""Service layer for reusable TradingAgents workflows."""
```

- [ ] **Step 4: Implement `analysis_service.py`**

Create `tradingagents/services/analysis_service.py`:

```python
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

import analyze


@dataclass(frozen=True)
class AnalysisRequest:
    tickers: List[str]
    level: int = 2
    date: Optional[str] = None
    asset_type: str = "stock"
    provider: str = "deepseek"
    deep_model: str = "deepseek-v4-flash"
    quick_model: str = "deepseek-v4-flash"
    backend_url: str = ""
    cn_vendor: str = "tushare"
    debug: bool = False
    workers: int = 1


@dataclass(frozen=True)
class PreparedAnalysis:
    request: AnalysisRequest
    original_date: str
    trade_date: str
    asset_type: str
    intensity: Dict[str, Any]
    analysts: List[str]
    config: Dict[str, Any]
    total_steps_per_ticker: int


def _request_to_args(request: AnalysisRequest) -> argparse.Namespace:
    requested_date = request.date or date.today().strftime("%Y-%m-%d")
    return argparse.Namespace(
        tickers=list(request.tickers),
        level=request.level,
        date=requested_date,
        workers=max(1, int(request.workers)),
        provider=request.provider or os.getenv("LLM_PROVIDER", "deepseek"),
        deep_model=request.deep_model or os.getenv("DEEP_LLM_MODEL", os.getenv("CUSTOM_LLM_MODEL", "deepseek-v4-flash")),
        quick_model=request.quick_model or os.getenv("QUICK_LLM_MODEL", os.getenv("CUSTOM_LLM_MODEL", "deepseek-v4-flash")),
        backend_url=request.backend_url or os.getenv("CUSTOM_LLM_API_URL", ""),
        cn_vendor=request.cn_vendor or "tushare",
        debug=bool(request.debug),
        asset_type=request.asset_type or "stock",
        date_was_explicit=request.date is not None,
    )


def prepare_analysis(request: AnalysisRequest) -> PreparedAnalysis:
    if not request.tickers:
        raise ValueError("tickers must contain at least one symbol")
    if request.level not in {1, 2, 3, 4, 5}:
        raise ValueError("level must be between 1 and 5")
    if request.asset_type not in {"stock", "etf", "auto"}:
        raise ValueError("asset_type must be one of: stock, etf, auto")
    if request.cn_vendor not in {"tushare", "akshare", "baostock"}:
        raise ValueError("cn_vendor must be one of: tushare, akshare, baostock")

    args = _request_to_args(request)
    args.asset_type = analyze.resolve_asset_type(args.tickers, args.asset_type)
    args.original_date, args.date = analyze.resolve_analysis_date(
        tickers=args.tickers,
        requested_date=args.date,
        date_was_explicit=args.date_was_explicit,
    )
    intensity = analyze.resolve_intensity(args)
    config = analyze.build_config(args, intensity)
    analysts = list(intensity["analysts"])
    return PreparedAnalysis(
        request=request,
        original_date=args.original_date,
        trade_date=args.date,
        asset_type=args.asset_type,
        intensity=intensity,
        analysts=analysts,
        config=config,
        total_steps_per_ticker=analyze._calc_total_steps(analysts, config),
    )


def run_analysis_batch(request: AnalysisRequest) -> Dict[str, Any]:
    prepared = prepare_analysis(request)
    results: List[Dict[str, Any]] = []

    for ticker in prepared.request.tickers:
        result = analyze.analyze_single(
            ticker=ticker,
            trade_date=prepared.trade_date,
            config=prepared.config,
            analysts=prepared.analysts,
            debug=prepared.request.debug,
        )
        results.append(result)

    return {
        "status": "success" if all(item.get("status") == "success" for item in results) else "error",
        "tickers": list(prepared.request.tickers),
        "asset_type": prepared.asset_type,
        "original_date": prepared.original_date,
        "trade_date": prepared.trade_date,
        "level": prepared.request.level,
        "analysts": prepared.analysts,
        "total_steps_per_ticker": prepared.total_steps_per_ticker,
        "results": results,
    }


def request_to_json(request: AnalysisRequest) -> str:
    return json.dumps(asdict(request), ensure_ascii=False)


def request_from_json(payload: str) -> AnalysisRequest:
    return AnalysisRequest(**json.loads(payload))


def run_analysis_batch_from_payload(payload: str) -> Dict[str, Any]:
    load_dotenv()
    return run_analysis_batch(request_from_json(payload))
```

- [ ] **Step 5: Run service tests**

Run:

```bash
python3 -m unittest tests.test_analysis_service -v
```

Expected: PASS, 3 tests.

- [ ] **Step 6: Run full tests**

Run:

```bash
python3 -m unittest discover -s tests -p 'test*.py' -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tradingagents/services tests/test_analysis_service.py
git commit -m "feat: add reusable analysis service layer"
```

---

## Task 3: Add API Schemas and Job Store

**Files:**
- Create: `tradingagents/api/__init__.py`
- Create: `tradingagents/api/schemas.py`
- Create: `tradingagents/api/job_store.py`
- Test: `tests/test_analysis_api_models.py`

- [ ] **Step 1: Write failing schema/store tests**

Create `tests/test_analysis_api_models.py`:

```python
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
```

- [ ] **Step 2: Run model tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_analysis_api_models -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tradingagents.api'`.

- [ ] **Step 3: Create API package marker**

Create `tradingagents/api/__init__.py`:

```python
"""HTTP API package for ETF Stock Agent."""
```

- [ ] **Step 4: Implement Pydantic schemas**

Create `tradingagents/api/schemas.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AnalysisJobCreate(BaseModel):
    tickers: List[str] = Field(min_length=1)
    level: int = Field(default=2, ge=1, le=5)
    date: Optional[str] = None
    asset_type: Literal["stock", "etf", "auto"] = "stock"
    provider: str = "deepseek"
    deep_model: str = "deepseek-v4-flash"
    quick_model: str = "deepseek-v4-flash"
    backend_url: str = ""
    cn_vendor: Literal["tushare", "akshare", "baostock"] = "tushare"
    debug: bool = False
    workers: int = Field(default=1, ge=1, le=8)


class AnalysisJobSummary(BaseModel):
    job_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    request: Dict[str, Any]
    error: Optional[str] = None


class AnalysisJobDetail(AnalysisJobSummary):
    result: Optional[Dict[str, Any]] = None


class AnalysisResultResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
```

- [ ] **Step 5: Implement thread-safe in-memory job store**

Create `tradingagents/api/job_store.py`:

```python
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

    def _update(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.update(fields)
            job["updated_at"] = _now()
```

- [ ] **Step 6: Run model tests**

Run:

```bash
python3 -m unittest tests.test_analysis_api_models -v
```

Expected: PASS, 2 tests.

- [ ] **Step 7: Commit**

```bash
git add tradingagents/api tests/test_analysis_api_models.py
git commit -m "feat: add API schemas and job store"
```

---

## Task 4: Add Background Runner

**Files:**
- Create: `tradingagents/api/runner.py`
- Test: `tests/test_analysis_runner.py`

- [ ] **Step 1: Write failing runner test**

Create `tests/test_analysis_runner.py`:

```python
import unittest
from unittest.mock import patch

from tradingagents.api.job_store import JobStore
from tradingagents.api.runner import AnalysisJobRunner
from tradingagents.services.analysis_service import AnalysisRequest


class AnalysisRunnerTests(unittest.TestCase):
    def test_submit_creates_job_and_completes_with_fake_executor(self):
        store = JobStore()
        runner = AnalysisJobRunner(store=store, max_workers=1)

        def fake_submit(fn, payload):
            class FakeFuture:
                def add_done_callback(self, callback):
                    callback(self)

                def result(self):
                    return {"status": "success", "results": [{"ticker": "600519", "status": "success"}]}

            return FakeFuture()

        with patch.object(runner._executor, "submit", side_effect=fake_submit):
            job = runner.submit(AnalysisRequest(tickers=["600519"], date="2026-05-22"))

        stored = store.get_job(job["job_id"])
        self.assertEqual(stored["status"], "success")
        self.assertEqual(stored["result"]["status"], "success")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run runner test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_analysis_runner -v
```

Expected: FAIL with `ModuleNotFoundError` for `tradingagents.api.runner`.

- [ ] **Step 3: Implement background runner**

Create `tradingagents/api/runner.py`:

```python
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
        future = self._executor.submit(run_analysis_batch_from_payload, request_to_json(request))
        self._futures[job_id] = future
        future.add_done_callback(lambda completed: self._complete(job_id, completed))
        return self.store.get_job(job_id)

    def _complete(self, job_id: str, future: Future) -> None:
        try:
            result = future.result()
        except Exception as exc:
            self.store.mark_failed(job_id, f"{exc}\n{traceback.format_exc()}")
            return

        if result.get("status") == "success":
            self.store.mark_succeeded(job_id, result)
        else:
            self.store.mark_failed(job_id, result.get("error", "analysis failed"))
            current = self.store.get_job(job_id)
            if current is not None:
                current["result"] = result
```

- [ ] **Step 4: Fix failed-job result persistence**

If the test suite later needs failed job results, replace `_complete` with this version:

```python
    def _complete(self, job_id: str, future: Future) -> None:
        try:
            result = future.result()
        except Exception as exc:
            self.store.mark_failed(job_id, f"{exc}\n{traceback.format_exc()}")
            return

        if result.get("status") == "success":
            self.store.mark_succeeded(job_id, result)
        else:
            self.store._update(
                job_id,
                status="error",
                result=result,
                error=result.get("error", "analysis failed"),
            )
```

- [ ] **Step 5: Run runner tests**

Run:

```bash
python3 -m unittest tests.test_analysis_runner -v
```

Expected: PASS, 1 test.

- [ ] **Step 6: Commit**

```bash
git add tradingagents/api/runner.py tests/test_analysis_runner.py
git commit -m "feat: add analysis job runner"
```

---

## Task 5: Add FastAPI App and Endpoints

**Files:**
- Create: `tradingagents/api/main.py`
- Test: `tests/test_analysis_api.py`

- [ ] **Step 1: Write failing API endpoint tests**

Create `tests/test_analysis_api.py`:

```python
import unittest

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
            {"status": "success", "results": [{"ticker": request.tickers[0], "status": "success"}]},
        )
        return self.store.get_job(job["job_id"])


class AnalysisApiTests(unittest.TestCase):
    def setUp(self):
        self.store = JobStore()
        self.app = create_app(store=self.store, runner=FakeRunner(self.store))
        self.client = TestClient(self.app)

    def test_create_and_read_job_result(self):
        created = self.client.post(
            "/api/v1/analysis/jobs",
            json={"tickers": ["600519"], "date": "2026-05-22"},
        )

        self.assertEqual(created.status_code, 201)
        job_id = created.json()["job_id"]

        detail = self.client.get(f"/api/v1/analysis/jobs/{job_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["status"], "success")

        result = self.client.get(f"/api/v1/analysis/jobs/{job_id}/result")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["result"]["status"], "success")

    def test_unknown_job_returns_404(self):
        response = self.client.get("/api/v1/analysis/jobs/missing")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_analysis_api -v
```

Expected: FAIL with `ModuleNotFoundError` or missing `create_app`.

- [ ] **Step 3: Implement FastAPI app**

Create `tradingagents/api/main.py`:

```python
from __future__ import annotations

import os
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Response, status

from tradingagents.api.job_store import JobStore
from tradingagents.api.runner import AnalysisJobRunner
from tradingagents.api.schemas import (
    AnalysisJobCreate,
    AnalysisJobDetail,
    AnalysisJobSummary,
    AnalysisResultResponse,
)
from tradingagents.services.analysis_service import AnalysisRequest


def _to_request(payload: AnalysisJobCreate) -> AnalysisRequest:
    return AnalysisRequest(
        tickers=payload.tickers,
        level=payload.level,
        date=payload.date,
        asset_type=payload.asset_type,
        provider=payload.provider,
        deep_model=payload.deep_model,
        quick_model=payload.quick_model,
        backend_url=payload.backend_url,
        cn_vendor=payload.cn_vendor,
        debug=payload.debug,
        workers=payload.workers,
    )


def create_app(
    store: Optional[JobStore] = None,
    runner: Optional[AnalysisJobRunner] = None,
) -> FastAPI:
    job_store = store or JobStore()
    job_runner = runner or AnalysisJobRunner(
        store=job_store,
        max_workers=int(os.getenv("ANALYSIS_API_WORKERS", "2")),
    )

    app = FastAPI(
        title="ETF Stock Agent API",
        version="0.1.0",
        description="HTTP API for asynchronous stock and ETF analysis jobs.",
    )
    app.state.job_store = job_store
    app.state.job_runner = job_runner

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.post(
        "/api/v1/analysis/jobs",
        response_model=AnalysisJobSummary,
        status_code=status.HTTP_201_CREATED,
    )
    def create_analysis_job(payload: AnalysisJobCreate) -> dict:
        return app.state.job_runner.submit(_to_request(payload))

    @app.get("/api/v1/analysis/jobs/{job_id}", response_model=AnalysisJobDetail)
    def get_analysis_job(job_id: str) -> dict:
        job = app.state.job_store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job

    @app.get("/api/v1/analysis/jobs/{job_id}/result", response_model=AnalysisResultResponse)
    def get_analysis_job_result(job_id: str, response: Response) -> dict:
        job = app.state.job_store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        if job["status"] in {"queued", "running"}:
            response.status_code = status.HTTP_202_ACCEPTED
        return {
            "job_id": job_id,
            "status": job["status"],
            "result": job.get("result"),
            "error": job.get("error"),
        }

    return app


app = create_app()


def run() -> None:
    uvicorn.run(
        "tradingagents.api.main:app",
        host=os.getenv("ANALYSIS_API_HOST", "127.0.0.1"),
        port=int(os.getenv("ANALYSIS_API_PORT", "8000")),
        reload=os.getenv("ANALYSIS_API_RELOAD", "0") == "1",
    )


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Run API tests**

Run:

```bash
python3 -m unittest tests.test_analysis_api -v
```

Expected: PASS, 2 tests.

- [ ] **Step 5: Run full tests**

Run:

```bash
python3 -m unittest discover -s tests -p 'test*.py' -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tradingagents/api/main.py tests/test_analysis_api.py
git commit -m "feat: expose analysis job API"
```

---

## Task 6: Add Report Download Endpoint

**Files:**
- Modify: `tradingagents/api/main.py`
- Test: `tests/test_analysis_api.py`

- [ ] **Step 1: Add failing report endpoint test**

Append this test method to `AnalysisApiTests` in `tests/test_analysis_api.py`:

```python
    def test_report_endpoint_returns_404_when_report_missing(self):
        created = self.client.post(
            "/api/v1/analysis/jobs",
            json={"tickers": ["600519"], "date": "2026-05-22"},
        )
        job_id = created.json()["job_id"]

        response = self.client.get(f"/api/v1/analysis/jobs/{job_id}/reports/600519")

        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run API tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_analysis_api -v
```

Expected: FAIL because the report route does not exist.

- [ ] **Step 3: Add report route imports**

In `tradingagents/api/main.py`, add:

```python
from pathlib import Path
from fastapi.responses import FileResponse
```

- [ ] **Step 4: Add report route inside `create_app`**

Add this route after `get_analysis_job_result`:

```python
    @app.get("/api/v1/analysis/jobs/{job_id}/reports/{ticker}")
    def get_analysis_report(job_id: str, ticker: str) -> FileResponse:
        job = app.state.job_store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        result = job.get("result") or {}
        for item in result.get("results", []):
            if item.get("ticker") != ticker:
                continue
            report_path = item.get("report_path")
            if not report_path:
                raise HTTPException(status_code=404, detail="report path not available")
            path = Path(report_path)
            if not path.exists() or not path.is_file():
                raise HTTPException(status_code=404, detail="report file not found")
            return FileResponse(
                path=str(path),
                media_type="text/markdown; charset=utf-8",
                filename=path.name,
            )
        raise HTTPException(status_code=404, detail="ticker result not found")
```

- [ ] **Step 5: Run API tests**

Run:

```bash
python3 -m unittest tests.test_analysis_api -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tradingagents/api/main.py tests/test_analysis_api.py
git commit -m "feat: add analysis report download endpoint"
```

---

## Task 7: Document API Usage

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add failing documentation check**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path("README.md").read_text()
assert "## API Service" in text
assert "POST /api/v1/analysis/jobs" in text
assert "GET /api/v1/analysis/jobs/{job_id}/result" in text
PY
```

Expected: FAIL with `AssertionError`.

- [ ] **Step 2: Add API section to README**

Append this section to `README.md`:

```markdown
## API Service

Start the local API server:

```bash
python3 -m uvicorn tradingagents.api.main:app --host 127.0.0.1 --port 8000
```

Submit an asynchronous stock analysis job:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/analysis/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "tickers": ["600519"],
    "date": "2026-05-22",
    "level": 2,
    "asset_type": "stock",
    "provider": "deepseek",
    "quick_model": "deepseek-v4-flash",
    "deep_model": "deepseek-v4-flash",
    "cn_vendor": "tushare"
  }'
```

Submit an A-share ETF job:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/analysis/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "tickers": ["159949"],
    "date": "2026-05-22",
    "level": 3,
    "asset_type": "etf"
  }'
```

Check job state:

```bash
curl -sS http://127.0.0.1:8000/api/v1/analysis/jobs/{job_id}
```

Read final result:

```bash
curl -sS http://127.0.0.1:8000/api/v1/analysis/jobs/{job_id}/result
```

Download a generated Markdown report:

```bash
curl -sS -o report.md http://127.0.0.1:8000/api/v1/analysis/jobs/{job_id}/reports/600519
```

The API runs analysis in background worker processes because the underlying dataflow configuration is process-level. Keep `ANALYSIS_API_WORKERS` small enough for your LLM and data-provider rate limits.
```

- [ ] **Step 3: Verify documentation**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
text = Path("README.md").read_text()
assert "## API Service" in text
assert "POST /api/v1/analysis/jobs" in text
assert "GET /api/v1/analysis/jobs/{job_id}/result" in text
PY
```

Expected: PASS with no output.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document analysis API service"
```

---

## Task 8: Local Smoke Test Without Live LLM Calls

**Files:**
- No source changes expected

- [ ] **Step 1: Run import checks**

Run:

```bash
python3 - <<'PY'
from tradingagents.api.main import app
from tradingagents.services.analysis_service import AnalysisRequest, prepare_analysis

prepared = prepare_analysis(AnalysisRequest(tickers=["600519"], date="2026-05-22"))
assert app.title == "ETF Stock Agent API"
assert prepared.asset_type == "stock"
assert prepared.trade_date == "2026-05-22"
PY
```

Expected: PASS with no output.

- [ ] **Step 2: Run full unit suite**

Run:

```bash
python3 -m unittest discover -s tests -p 'test*.py' -v
```

Expected: PASS.

- [ ] **Step 3: Start the API server**

Run:

```bash
ANALYSIS_API_WORKERS=1 python3 -m uvicorn tradingagents.api.main:app --host 127.0.0.1 --port 8000
```

Expected output includes:

```text
Uvicorn running on http://127.0.0.1:8000
```

- [ ] **Step 4: Verify health endpoint in a second shell**

Run:

```bash
curl -sS http://127.0.0.1:8000/healthz
```

Expected:

```json
{"status":"ok"}
```

- [ ] **Step 5: Stop the server**

Press `Ctrl-C` in the uvicorn shell.

- [ ] **Step 6: Commit smoke-test-only changes if any files changed**

Run:

```bash
git status --short
```

Expected: no uncommitted files from smoke testing.

---

## Task 9: Optional Live API Analysis Smoke Test

**Files:**
- No source changes expected

- [ ] **Step 1: Confirm required environment variables**

Run one of these, depending on provider:

```bash
python3 - <<'PY'
import os
required = ["DEEPSEEK_API_KEY"]
missing = [name for name in required if not os.getenv(name)]
if missing:
    raise SystemExit(f"Missing env vars: {', '.join(missing)}")
PY
```

Expected with DeepSeek configured: PASS with no output.

- [ ] **Step 2: Start the API**

Run:

```bash
ANALYSIS_API_WORKERS=1 python3 -m uvicorn tradingagents.api.main:app --host 127.0.0.1 --port 8000
```

Expected output includes:

```text
Uvicorn running on http://127.0.0.1:8000
```

- [ ] **Step 3: Submit a low-cost stock job**

Run in a second shell:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/analysis/jobs \
  -H 'Content-Type: application/json' \
  -d '{"tickers":["600519"],"date":"2026-05-22","level":1,"asset_type":"stock"}'
```

Expected: JSON with `"job_id"` and `"status":"running"` or `"status":"success"`.

- [ ] **Step 4: Poll the result**

Replace `<job_id>` with the returned ID:

```bash
curl -sS http://127.0.0.1:8000/api/v1/analysis/jobs/<job_id>/result
```

Expected while running:

```json
{"job_id":"<job_id>","status":"running","result":null,"error":null}
```

Expected after completion:

```json
{"job_id":"<job_id>","status":"success","result":{"status":"success", "...":"..."},"error":null}
```

- [ ] **Step 5: Stop the server**

Press `Ctrl-C` in the uvicorn shell.

---

## Task 10: Finishing Branch Gate

**Files:**
- No source changes expected unless tests reveal defects

- [ ] **Step 1: Run the full test suite**

Run:

```bash
python3 -m unittest discover -s tests -p 'test*.py' -v
```

Expected: PASS.

- [ ] **Step 2: Detect git environment**

Run:

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
printf 'GIT_DIR=%s\nGIT_COMMON=%s\n' "$GIT_DIR" "$GIT_COMMON"
```

Expected in the current workspace:

```text
GIT_DIR=/Users/minlong_1/Desktop/Github/etf-stock-agent/.git
GIT_COMMON=/Users/minlong_1/Desktop/Github/etf-stock-agent/.git
```

- [ ] **Step 3: Determine base branch**

Run:

```bash
git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null
```

Expected: prints a commit SHA.

- [ ] **Step 4: Present exactly these completion options**

If on a named branch in a normal repo or named-branch worktree, present:

```text
Implementation complete. What would you like to do?

1. Merge back to main locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

If on detached HEAD, present:

```text
Implementation complete. You're on a detached HEAD (externally managed workspace).

1. Push as new branch and create a Pull Request
2. Keep as-is (I'll handle it later)
3. Discard this work

Which option?
```

- [ ] **Step 5: If option 1 is selected, merge locally**

Run:

```bash
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"
git checkout main
git pull
git merge <feature-branch>
python3 -m unittest discover -s tests -p 'test*.py' -v
git branch -d <feature-branch>
```

Expected: merge succeeds, tests pass, feature branch is deleted.

- [ ] **Step 6: If option 2 is selected, push and create PR**

Run:

```bash
git push -u origin <feature-branch>
gh pr create --title "Add analysis API service" --body "$(cat <<'EOF'
## Summary
- Add a reusable analysis service layer around analyze.py primitives
- Add FastAPI job endpoints for asynchronous analysis, events, results, and report downloads
- Document API startup and curl usage

## Test Plan
- [ ] python3 -m unittest discover -s tests -p 'test*.py' -v
- [ ] curl -sS http://127.0.0.1:8000/healthz
EOF
)"
```

Expected: branch is pushed and GitHub returns a PR URL. Do not clean up the worktree after creating a PR.

- [ ] **Step 7: If option 3 is selected, preserve branch**

Report:

```text
Keeping branch <feature-branch>. Worktree preserved at /Users/minlong_1/Desktop/Github/etf-stock-agent.
```

- [ ] **Step 8: If option 4 is selected, require exact confirmation**

Print:

```text
This will permanently delete:
- Branch <feature-branch>
- All commits: <commit-list>
- Worktree at /Users/minlong_1/Desktop/Github/etf-stock-agent

Type 'discard' to confirm.
```

Only if the user types exactly `discard`, run:

```bash
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"
git branch -D <feature-branch>
```

Expected: branch is force-deleted. In the current normal repo environment there is no worktree to remove.

---

## Self-Review

- Spec coverage: The plan covers CLI baseline restoration, service extraction, API models, background execution, REST endpoints, report download, docs, tests, smoke checks, and development-branch finishing.
- Placeholder scan: The plan does not use `TBD`, `TODO`, `implement later`, or vague test instructions. Every code-changing step includes concrete code.
- Type consistency: `AnalysisRequest`, `PreparedAnalysis`, `AnalysisJobCreate`, `JobStore`, and `AnalysisJobRunner` names are consistent across tests and implementations.
