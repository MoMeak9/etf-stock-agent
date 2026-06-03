from argparse import Namespace

import analyze


def test_fund_console_labels_use_fund_language():
    original_console = analyze.console
    recording_console = analyze.Console(record=True, width=120)
    analyze.console = recording_console
    try:
        args = Namespace(
            tickers=["001513"],
            asset_type="fund",
            date="2026-06-03",
            original_date="2026-06-03",
            level=3,
            workers=1,
            provider="deepseek",
            quick_model="deepseek-v4-flash",
        )
        intensity = {
            "name": "基金标准",
            "desc": "净值+产品+持仓+事件",
            "analysts": ["nav", "product", "portfolio", "event"],
            "max_debate_rounds": 2,
            "max_risk_discuss_rounds": 2,
        }
        result = {
            "ticker": "001513",
            "status": "success",
            "decision": {
                "action": "持有",
                "confidence": 0.7,
                "risk_score": 0.5,
                "reasoning": "基于基金净值、产品结构、持仓暴露与风险因素的综合建议",
            },
            "elapsed": 1.0,
            "stats": {"llm_calls": 1, "tool_calls": 1, "tokens_in": 10, "tokens_out": 5},
        }

        analyze.print_header(args, intensity)
        analyze.print_result(result, 1, 1, asset_type="fund")
        analyze.print_summary([result], asset_type="fund")

        output = recording_console.export_text()
    finally:
        analyze.console = original_console

    assert "基金列表" in output
    assert "资产类型  : 开放式基金" in output
    assert "基金建议" in output
    assert "目标价" not in output
    assert "股票列表" not in output
