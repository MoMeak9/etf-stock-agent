"""ETF admission and profile helpers."""

from __future__ import annotations

from typing import Any

from tradingagents.dataflows.etf_models import DataQuality, ETFAdmission
from tradingagents.dataflows.market_utils import detect_market, get_exchange, is_etf, normalize_symbol


def _to_ts_code(symbol: str) -> str:
    normalized = normalize_symbol(symbol, "cn")
    return f"{normalized}.{get_exchange(normalized)}"


def _first_record(df) -> dict[str, Any]:
    if df is None or getattr(df, "empty", True):
        return {}
    return {str(key): value for key, value in df.iloc[0].to_dict().items()}


def _classify_etf(profile: dict[str, Any]) -> str:
    text = " ".join(str(profile.get(key, "")) for key in ("etf_type", "fund_type", "name", "cname", "csname", "index_name"))
    lowered = text.lower()
    if "qdii" in lowered:
        return "qdii"
    if any(word in text for word in ("债", "货币", "黄金", "商品")):
        return "commodity" if "黄金" in text or "商品" in text else "unsupported"
    if any(word in text for word in ("行业", "主题")):
        return "theme"
    return "broad"


def admit_etf(symbol: str) -> ETFAdmission:
    normalized = normalize_symbol(symbol, "cn")
    exchange = get_exchange(normalized)
    ts_code = _to_ts_code(normalized)

    if detect_market(symbol) != "cn" or not is_etf(normalized):
        return ETFAdmission(
            symbol=normalized,
            ts_code=ts_code,
            exchange=exchange,
            is_supported=False,
            etf_type="unknown",
            reason="ETF mode currently supports only A-share exchange-traded ETFs.",
            quality=DataQuality(status="blocked", missing_fields=["supported_cn_etf"]),
        )

    warnings: list[str] = []
    profile: dict[str, Any] = {}
    try:
        from tradingagents.dataflows import tushare_etf

        profile = _first_record(tushare_etf.fetch_etf_basic(normalized))
    except Exception as exc:
        warnings.append(f"etf_basic unavailable: {exc}")

    etf_type = _classify_etf(profile)
    is_supported = etf_type in {"broad", "theme", "commodity"}
    reason = "" if is_supported else f"ETF type '{etf_type}' is not supported for professional analysis."
    return ETFAdmission(
        symbol=normalized,
        ts_code=ts_code,
        exchange=exchange,
        is_supported=is_supported,
        etf_type=etf_type,
        reason=reason,
        profile=profile,
        quality=DataQuality(
            status="ok" if profile and is_supported else "partial" if is_supported else "blocked",
            warnings=warnings,
            missing_fields=[] if profile else ["basic_profile"],
        ),
    )
