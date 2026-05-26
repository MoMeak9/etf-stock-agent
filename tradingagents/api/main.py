from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.responses import FileResponse

from tradingagents.api.job_store import JobStore
from tradingagents.api.runner import AnalysisJobRunner
from tradingagents.api.schemas import (
    AnalysisJobCreate,
    AnalysisJobDetail,
    AnalysisJobSummary,
    AnalysisResultResponse,
)
from tradingagents.services.analysis_service import AnalysisRequest


def require_api_token(authorization: Annotated[Optional[str], Header()] = None) -> None:
    expected = os.getenv("ANALYSIS_API_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="ANALYSIS_API_TOKEN is not configured",
        )
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="invalid or missing API token")


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

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        shutdown = getattr(app.state.job_runner, "shutdown", None)
        if shutdown:
            shutdown()

    app = FastAPI(
        title="ETF Stock Agent API",
        version="0.1.0",
        description="HTTP API for asynchronous stock and ETF analysis jobs.",
        lifespan=lifespan,
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
        dependencies=[Depends(require_api_token)],
    )
    def create_analysis_job(payload: AnalysisJobCreate) -> dict:
        return app.state.job_runner.submit(_to_request(payload))

    @app.get(
        "/api/v1/analysis/jobs/{job_id}",
        response_model=AnalysisJobDetail,
        dependencies=[Depends(require_api_token)],
    )
    def get_analysis_job(job_id: str) -> dict:
        job = app.state.job_store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job

    @app.get(
        "/api/v1/analysis/jobs/{job_id}/result",
        response_model=AnalysisResultResponse,
        dependencies=[Depends(require_api_token)],
    )
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

    @app.get(
        "/api/v1/analysis/jobs/{job_id}/reports/{ticker}",
        dependencies=[Depends(require_api_token)],
    )
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
