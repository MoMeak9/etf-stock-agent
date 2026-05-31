"""Open-ended public fund admission and profile helpers."""

from __future__ import annotations

import re
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


def _profile_text(profile: dict[str, Any]) -> str:
    return " ".join(
        str(profile.get(key, ""))
        for key in ("fund_type", "基金类型", "type", "name", "基金简称", "fullname")
    )


def _is_exchange_traded_profile(profile: dict[str, Any]) -> bool:
    text = _profile_text(profile)
    lowered = text.lower()
    return any(token in lowered for token in ("lof", "reit", "reits")) or any(
        token in text for token in ("封闭", "封基", "场内")
    )


def classify_fund(profile: dict[str, Any]) -> str:
    text = _profile_text(profile)
    lowered = text.lower()
    if "qdii" in lowered:
        return "qdii"
    if "货币" in text or "money" in lowered:
        return "money_market"
    if "债" in text or "bond" in lowered:
        return "bond"
    if "fof" in lowered:
        return "fof"
    if "指数" in text or "index" in lowered:
        return "index"
    if "混合" in text or "hybrid" in lowered:
        return "hybrid"
    if "股票" in text or "equity" in lowered:
        return "equity"
    return "unknown"


def admit_fund(symbol: str) -> FundAdmission:
    raw_symbol = str(symbol).strip()
    normalized = normalize_symbol(raw_symbol, "cn")
    ts_code = to_fund_ts_code(normalized)
    cached = _ADMISSION_CACHE.get(normalized)
    if cached is not None:
        return cached

    if not re.fullmatch(r"\d{6}", normalized or ""):
        return FundAdmission(
            symbol=normalized,
            ts_code=ts_code,
            is_supported=False,
            fund_type="unknown",
            reason="Fund mode requires a six-digit China public fund code.",
            quality=FundDataQuality(status="blocked", missing_fields=["six_digit_fund_code"]),
        )

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

    if profile and _is_exchange_traded_profile(profile):
        admission = FundAdmission(
            symbol=normalized,
            ts_code=ts_code,
            is_supported=False,
            fund_type="exchange_traded",
            reason=(
                "Exchange-traded fund products are out of scope for fund mode; "
                "use a dedicated exchange-traded fund asset type when supported."
            ),
            profile=profile,
            quality=FundDataQuality(
                status="blocked",
                primary_source=primary_source,
                fallback_source=fallback_source,
                warnings=warnings,
                missing_fields=["open_ended_fund"],
            ),
        )
        _ADMISSION_CACHE[normalized] = admission
        return admission

    fund_type = classify_fund(profile)
    is_supported = bool(profile)
    status = "ok" if profile and fund_type != "unknown" else "partial" if is_supported else "blocked"
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
            missing_fields=[] if profile else ["fund_basic"],
        ),
    )
    if profile:
        _ADMISSION_CACHE[normalized] = admission
    return admission
