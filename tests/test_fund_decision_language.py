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


def test_fund_signal_processing_preserves_watch_and_redeem_without_target_price():
    from tradingagents.graph.signal_processing import SignalProcessor

    processor = SignalProcessor(quick_thinking_llm=None)

    watch = processor.process_signal(
        "基金建议：观望。置信度：中。风险评分：中。理由：等待净值和申购状态更清晰。",
        asset_type="fund",
    )
    redeem = processor.process_signal(
        "最终基金建议: **赎回**。置信度：高。风险评分：高。理由：净值回撤扩大且流动性风险上升。",
        asset_type="fund",
    )

    assert watch["action"] == "观望"
    assert redeem["action"] == "赎回"
    assert "target_price" not in watch
    assert "target_price" not in redeem


def test_fund_report_section_labels_use_fund_language():
    from tradingagents.graph.trading_graph import _report_section_labels_for_asset

    labels = _report_section_labels_for_asset("fund")

    assert labels["investment_debate_title"] == "基金观点辩论"
    assert labels["bull_researcher_title"] == "积极基金研究员"
    assert labels["bear_researcher_title"] == "谨慎基金研究员"
    assert labels["trader_plan_title"] == "基金操作计划"
    assert labels["final_decision_title"] == "最终基金决策"
