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
        deep_model=request.deep_model
        or os.getenv("DEEP_LLM_MODEL", os.getenv("CUSTOM_LLM_MODEL", "deepseek-v4-flash")),
        quick_model=request.quick_model
        or os.getenv("QUICK_LLM_MODEL", os.getenv("CUSTOM_LLM_MODEL", "deepseek-v4-flash")),
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
        "status": "success"
        if all(item.get("status") == "success" for item in results)
        else "error",
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
