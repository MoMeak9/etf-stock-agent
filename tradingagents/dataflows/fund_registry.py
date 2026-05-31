"""Open-ended public fund admission and profile helpers."""

from __future__ import annotations

from typing import Any

from tradingagents.dataflows.fund_models import FundAdmission, FundDataQuality
from tradingagents.dataflows.market_utils import detect_market, is_etf, normalize_symbol
from tradingagents.dataflows.tushare_fund import to_fund_ts_code

_ADMISSION_CACHE: dict[str, FundAdmission] = {}


def clear_fund_admission_cache() -> None:
    _ADMISSION_CACHE.clear()


def _first_record(df) -> dict[str, Any]:
    if df is None or getattr(df, "empty", True):
        return {}
    return {str(key): value for key, value in df.iloc[0].to_dict().items()}


def _normalize_fund_type(profile: dict[str, Any]) -> str:
    text = " ".join(
        str(profile.get(key, ""))
        for key in ("fund_type", "基金类型", "type", "name", "基金简称", "fullname")
    )
    lowered = text.lower()
    if "qdii" in lowered:
        return "qdii"
    if any(word in text for word in ("股票", "混合", "债券", "货币", "指数", "FOF", "基金中基金")):
        return "open"
    return "unknown"


def admit_fund(symbol: str) -> FundAdmission:
    normalized = normalize_symbol(str(symbol).zfill(6), "cn")
    ts_code = to_fund_ts_code(normalized)
    cached = _ADMISSION_CACHE.get(normalized)
    if cached is not None:
        return cached

    if detect_market(normalized) != "cn":
        return FundAdmission(
            symbol=normalized,
            ts_code=ts_code,
            is_supported=False,
            fund_type="unknown",
            reason="Fund mode currently supports only China public fund codes.",
            quality=FundDataQuality(status="blocked", missing_fields=["supported_cn_fund"]),
        )

    if is_etf(normalized):
        return FundAdmission(
            symbol=normalized,
            ts_code=ts_code,
            is_supported=False,
            fund_type="etf",
            reason="ETF code detected; use asset_type=etf for exchange-traded fund analysis.",
            quality=FundDataQuality(status="blocked", missing_fields=["open_fund_code"]),
        )

    warnings: list[str] = []
    profile: dict[str, Any] = {}
    primary_source = "tushare"
    fallback_source = "none"

    try:
        from tradingagents.dataflows import tushare_fund

        profile = _first_record(tushare_fund.fetch_fund_basic(normalized))
    except Exception as exc:
        warnings.append(f"fund_basic unavailable from tushare: {exc}")

    if not profile:
        try:
            from tradingagents.dataflows import akshare_fund

            profile = _first_record(akshare_fund.fetch_fund_basic(normalized))
            if profile:
                fallback_source = "akshare"
        except Exception as exc:
            warnings.append(f"fund_basic unavailable from akshare: {exc}")

    fund_type = _normalize_fund_type(profile)
    is_supported = bool(profile)
    status = "ok" if profile and fund_type != "unknown" else "partial" if is_supported else "unavailable"
    reason = "" if is_supported else "Open fund basic profile is unavailable from configured sources."

    admission = FundAdmission(
        symbol=normalized,
        ts_code=ts_code,
        is_supported=is_supported,
        fund_type=fund_type,
        reason=reason,
        profile=profile,
        quality=FundDataQuality(
            status=status,
            primary_source=primary_source,
            fallback_source=fallback_source,
            warnings=warnings,
            missing_fields=[] if profile else ["basic_profile"],
        ),
    )
    if profile:
        _ADMISSION_CACHE[normalized] = admission
    return admission
