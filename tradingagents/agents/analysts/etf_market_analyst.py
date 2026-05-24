from datetime import datetime, timedelta

from tradingagents.agents.utils.etf_data_tools import (
    get_etf_indicators,
    get_etf_price_data,
)
from tradingagents.agents.utils.etf_prompt_utils import (
    ETF_MARKET_INDICATORS,
    build_etf_report_header,
)
from tradingagents.agents.utils.agent_states import apply_asset_report_mapping


def _history_start_date(current_date: str, lookback_days: int = 180) -> str:
    dt = datetime.strptime(current_date, "%Y-%m-%d")
    return (dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")


def _build_etf_market_tool_calls(
    ticker: str,
    current_date: str,
    existing_tool_calls: list[dict] | None,
) -> list[dict]:
    existing_tool_calls = existing_tool_calls or []
    planned_calls = []
    history_start = _history_start_date(current_date)
    has_history_price = False
    requested_indicators = set()

    for call in existing_tool_calls:
        if call.get("name") == "get_etf_price_data":
            args = call.get("args", {})
            if args.get("start_date", "") <= history_start and args.get("end_date") == current_date:
                has_history_price = True
        elif call.get("name") == "get_etf_indicators":
            indicator = str(call.get("args", {}).get("indicator", "")).strip()
            if indicator:
                requested_indicators.add(indicator)

    if not has_history_price:
        planned_calls.append(
            {
                "name": "get_etf_price_data",
                "args": {
                    "symbol": ticker,
                    "start_date": history_start,
                    "end_date": current_date,
                },
            }
        )

    for indicator in ETF_MARKET_INDICATORS:
        if indicator not in requested_indicators:
            planned_calls.append(
                {
                    "name": "get_etf_indicators",
                    "args": {
                        "symbol": ticker,
                        "indicator": indicator,
                        "curr_date": current_date,
                        "look_back_days": 60,
                    },
                }
            )

    return planned_calls


def _truncate_csv_block(text: str, max_rows: int = 40) -> str:
    lines = text.splitlines()
    if len(lines) <= max_rows + 3:
        return text

    header = [line for line in lines[:3]]
    body = lines[3:]
    return "\n".join(header + body[-max_rows:])


def _truncate_indicator_block(text: str, max_lines: int = 25) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines])


def create_etf_market_analyst(llm, toolkit=None):
    def etf_market_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        history_start = _history_start_date(current_date)

        price_data = get_etf_price_data.invoke(
            {
                "symbol": ticker,
                "start_date": history_start,
                "end_date": current_date,
            }
        )
        indicator_results = []
        core_indicators = ["close_20_sma", "close_60_sma", "macd", "rsi", "boll"]
        for indicator in core_indicators:
            indicator_results.append(
                _truncate_indicator_block(get_etf_indicators.invoke(
                    {
                        "symbol": ticker,
                        "indicator": indicator,
                        "curr_date": current_date,
                        "look_back_days": 60,
                    }
                ))
            )

        report_prompt = (
            f"{build_etf_report_header('ETF 市场分析', ticker)}\n"
            "你是 ETF 行情与技术分析师。下面已提供 ETF 历史行情与关键技术指标，请基于真实数据输出正式分析报告。\n"
            "输出必须同时包含：交易视角、配置视角、关键价格区间、主要风险提示。\n\n"
            f"## 历史行情\n{_truncate_csv_block(price_data)}\n\n"
            f"## 技术指标\n{chr(10).join(indicator_results)}"
        )

        result = llm.invoke(report_prompt)
        report = result.content
        update = {
            "messages": [result],
            "etf_market_report": report,
            "market_tool_call_count": len(core_indicators) + 1,
        }
        return apply_asset_report_mapping(update, "etf")

    return etf_market_analyst_node
