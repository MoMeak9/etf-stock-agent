import logging
import time
import json
from tradingagents.agents.utils.agent_utils import truncate_for_prompt

logger = logging.getLogger(__name__)


def create_neutral_debator(llm):
    def neutral_node(state) -> dict:
        asset_type = state.get("asset_type", "stock")
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_conservative_response = risk_debate_state.get("current_conservative_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        market_research_report = truncate_for_prompt(market_research_report)
        sentiment_report = truncate_for_prompt(sentiment_report)
        news_report = truncate_for_prompt(news_report)
        fundamentals_report = truncate_for_prompt(fundamentals_report)
        trader_decision = truncate_for_prompt(state["trader_investment_plan"], max_chars=2200)

        logger.info(f"Neutral Analyst input data lengths: market={len(market_research_report)}, sentiment={len(sentiment_report)}, news={len(news_report)}, fundamentals={len(fundamentals_report)}, trader={len(trader_decision)}, history={len(history)}")

        if asset_type == "etf":
            prompt = f"""作为中性 ETF 风险分析师，您的角色是平衡交易机会与配置风险，综合评估 ETF 的上行弹性、回撤风险、流动性、折溢价和跟踪稳定性。以下是交易员的决策：

{trader_decision}

请利用以下资料，在激进和保守之间提出更均衡的 ETF 策略：
市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务报告：{news_report}
ETF 产品报告：{fundamentals_report}
当前对话历史：{history}
激进分析师最后回应：{current_aggressive_response}
安全分析师最后回应：{current_conservative_response}

请用中文辩论式输出，说明 ETF 当前更适合交易、配置，还是保持中性观望。"""
        else:
            prompt = f"""作为中性风险分析师，您的角色是提供平衡的视角，权衡交易员决策或计划的潜在收益和风险。您优先考虑全面的方法，评估上行和下行风险，同时考虑更广泛的市场趋势、潜在的经济变化和多元化策略。以下是交易员的决策：

{trader_decision}

您的任务是挑战激进和安全分析师，指出每种观点可能过于乐观或过于谨慎的地方。使用以下数据来源的见解来支持调整交易员决策的温和、可持续策略：

市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务报告：{news_report}
公司基本面报告：{fundamentals_report}
以下是当前对话历史：{history} 以下是激进分析师的最后回应：{current_aggressive_response} 以下是安全分析师的最后回应：{current_conservative_response}。如果其他观点没有回应，请不要虚构，只需提出您的观点。

通过批判性地分析双方来积极参与，解决激进和保守论点中的弱点，倡导更平衡的方法。挑战他们的每个观点，说明为什么适度风险策略可能提供两全其美的效果，既提供增长潜力又防范极端波动。专注于辩论而不是简单地呈现数据，旨在表明平衡的观点可以带来最可靠的结果。请用中文以对话方式输出，就像您在说话一样，不使用任何特殊格式。"""

        logger.info("Neutral Analyst invoking LLM...")
        llm_start_time = time.time()

        response = llm.invoke(prompt)

        llm_elapsed = time.time() - llm_start_time
        logger.info(f"Neutral Analyst LLM call completed in {llm_elapsed:.2f}s")
        logger.info(f"Neutral Analyst response length: {len(response.content)} chars")

        argument = f"Neutral Analyst: {response.content}"

        new_count = risk_debate_state["count"] + 1
        logger.info(f"Neutral risk analyst completed, count: {risk_debate_state['count']} -> {new_count}")

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": neutral_history + "\n" + argument,
            "latest_speaker": "Neutral",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": argument,
            "count": new_count,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
