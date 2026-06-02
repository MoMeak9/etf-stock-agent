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


def test_fund_signal_processing_preserves_batch_subscription_in_free_text():
    from tradingagents.graph.signal_processing import SignalProcessor

    processor = SignalProcessor(quick_thinking_llm=None)

    result = processor.process_signal(
        "建议在回撤后分批申购，理由是净值波动仍高但长期配置价值改善。",
        asset_type="fund",
    )

    assert result["action"] == "分批申购"
    assert "target_price" not in result


def test_fund_signal_processing_prefers_positive_recommendation_after_negation():
    from tradingagents.graph.signal_processing import SignalProcessor

    processor = SignalProcessor(quick_thinking_llm=None)

    not_subscribe = processor.process_signal(
        "不建议申购，建议观望。理由是申购状态和宏观风险仍不清晰。",
        asset_type="fund",
    )
    keep_watch = processor.process_signal(
        "行动方案：不要申购，继续观望。理由是短期净值波动偏高。",
        asset_type="fund",
    )

    assert not_subscribe["action"] == "观望"
    assert keep_watch["action"] == "观望"


def test_research_manager_fund_prompt_requires_one_action(monkeypatch):
    from tradingagents.agents.managers import research_manager
    from types import SimpleNamespace

    captured = {}

    class DummyLLM:
        def invoke(self, prompt):
            captured["prompt"] = prompt
            return SimpleNamespace(content="基金建议：持有。")

    state = {
        "asset_type": "fund",
        "company_of_interest": "008763",
        "market_report": "",
        "sentiment_report": "",
        "news_report": "",
        "fundamentals_report": "",
        "investment_debate_state": {"history": "", "count": 0},
    }

    node = research_manager.create_research_manager(DummyLLM(), memory=None)
    node(state)

    prompt = captured["prompt"]
    assert "只能从申购、分批申购、持有、赎回、观望中选择一个" in prompt
    assert "禁止把完整选项列表作为建议输出" in prompt


def test_fund_report_section_labels_use_fund_language():
    from tradingagents.graph.trading_graph import _report_section_labels_for_asset

    labels = _report_section_labels_for_asset("fund")

    assert labels["investment_debate_title"] == "基金观点辩论"
    assert labels["bull_researcher_title"] == "积极基金研究员"
    assert labels["bear_researcher_title"] == "谨慎基金研究员"
    assert labels["trader_plan_title"] == "基金操作计划"
    assert labels["final_decision_title"] == "最终基金决策"
