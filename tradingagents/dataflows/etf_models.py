"""Shared data contracts for A-share ETF research packages."""

from dataclasses import dataclass, field
from typing import Any, Literal

QualityStatus = Literal["ok", "partial", "unavailable", "blocked"]


@dataclass
class DataQuality:
    status: QualityStatus
    primary_source: str = "tushare"
    fallback_source: str = "none"
    as_of_date: str = ""
    warnings: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


@dataclass
class ETFAdmission:
    symbol: str
    ts_code: str
    exchange: str
    is_supported: bool
    etf_type: str
    reason: str = ""
    profile: dict[str, Any] = field(default_factory=dict)
    quality: DataQuality = field(default_factory=lambda: DataQuality(status="partial"))


@dataclass
class ETFResearchPackage:
    symbol: str
    package_type: str
    status: QualityStatus
    quality: DataQuality
    metrics: dict[str, Any] = field(default_factory=dict)
    raw_summary: dict[str, Any] = field(default_factory=dict)
