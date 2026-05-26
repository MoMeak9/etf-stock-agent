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
