def test_fund_report_title_helper():
    from tradingagents.graph.trading_graph import _report_titles_for_asset

    titles = _report_titles_for_asset("fund")

    assert titles["report_title"] == "基金分析报告"
    assert titles["fundamentals_title"] == "基金产品结构分析报告"


def test_fund_summary_fields_do_not_require_target_price():
    from tradingagents.graph.trading_graph import _decision_rows_for_asset

    rows = _decision_rows_for_asset(
        "fund",
        {"action": "观望", "confidence": "中", "risk_score": "中"},
    )
    rendered = "\n".join(rows)

    assert "目标价" not in rendered
    assert "基金建议" in rendered
