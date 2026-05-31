from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FundDataQuality:
    status: str = "ok"
    primary_source: str = "tushare"
    fallback_source: str = "none"
    as_of_date: str = ""
    warnings: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FundAdmission:
    symbol: str
    ts_code: str
    is_supported: bool
    fund_type: str
    reason: str = ""
    profile: dict[str, Any] = field(default_factory=dict)
    quality: FundDataQuality = field(default_factory=FundDataQuality)


@dataclass(frozen=True)
class FundResearchPackage:
    symbol: str
    fund_type: str
    package_type: str
    status: str
    quality: FundDataQuality
    metrics: dict[str, Any] = field(default_factory=dict)
    raw_summary: dict[str, Any] = field(default_factory=dict)
