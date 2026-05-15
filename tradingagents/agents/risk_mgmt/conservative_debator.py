from langchain_core.messages import AIMessage
import logging
import time
import json
from tradingagents.agents.utils.agent_utils import truncate_for_prompt

logger = logging.getLogger(__name__)


def create_conservative_debator(llm):
    def conservative_node(state) -> dict:
        asset_type = state.get("asset_type", "stock")
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")

        current_aggressive_response = risk_debate_state.get("current_aggressive_response", "")
        current_neutral_response = risk_debate_state.get("current_neutral_response", "")

        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        market_research_report = truncate_for_prompt(market_research_report)
        sentiment_report = truncate_for_prompt(sentiment_report)
        news_report = truncate_for_prompt(news_report)
        fundamentals_report = truncate_for_prompt(fundamentals_report)
        trader_decision = truncate_for_prompt(state["trader_investment_plan"], max_chars=2200)

        logger.info(f"Conservative Analyst input data lengths: market={len(market_research_report)}, sentiment={len(sentiment_report)}, news={len(news_report)}, fundamentals={len(fundamentals_report)}, trader={len(trader_decision)}, history={len(history)}")

        if asset_type == "etf":
            prompt = f"""作为保守 ETF 风险分析师，您的目标是保护资产、控制回撤，并重点审查 ETF 的折溢价、跟踪误差、流动性和主题拥挤风险。以下是交易员的决策：

{trader_decision}

请直接回应激进和中性观点，并利用以下资料论证为什么 ETF 当前可能只适合轻仓、观望或暂不配置：
市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务报告：{news_report}
ETF 产品报告：{fundamentals_report}
当前对话历史：{history}
激进分析师最后回应：{current_aggressive_response}
中性分析师最后回应：{current_neutral_response}

请用中文辩论式输出，明确指出 ETF 的核心下行风险。"""
        else:
            prompt = f"""作为安全/保守风险分析师，您的主要目标是保护资产、最小化波动性，并确保稳定、可靠的增长。您优先考虑稳定性、安全性和风险缓解，仔细评估潜在损失、经济衰退和市场波动。在评估交易员的决策或计划时，请批判性地审查高风险要素，指出决策可能使公司面临不当风险的地方，以及更谨慎的替代方案如何能够确保长期收益。以下是交易员的决策：

{trader_decision}

您的任务是积极反驳激进和中性分析师的论点，突出他们的观点可能忽视的潜在威胁或未能优先考虑可持续性的地方。直接回应他们的观点，利用以下数据来源为交易员决策的低风险方法调整建立令人信服的案例：

市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务报告：{news_report}
公司基本面报告：{fundamentals_report}
以下是当前对话历史：{history} 以下是激进分析师的最后回应：{current_aggressive_response} 以下是中性分析师的最后回应：{current_neutral_response}。如果其他观点没有回应，请不要虚构，只需提出您的观点。

通过质疑他们的乐观态度并强调他们可能忽视的潜在下行风险来参与讨论。解决他们的每个反驳点，展示为什么保守立场最终是公司资产最安全的道路。专注于辩论和批评他们的论点，证明低风险策略相对于他们方法的优势。请用中文以对话方式输出，就像您在说话一样，不使用任何特殊格式。"""

        logger.info("Conservative Analyst invoking LLM...")
        llm_start_time = time.time()

        response = llm.invoke(prompt)

        llm_elapsed = time.time() - llm_start_time
        logger.info(f"Conservative Analyst LLM call completed in {llm_elapsed:.2f}s")

        argument = f"Conservative Analyst: {response.content}"

        new_count = risk_debate_state["count"] + 1
        logger.info(f"Conservative risk analyst completed, count: {risk_debate_state['count']} -> {new_count}")

        new_risk_debate_state = {
            "history": history + "\n" + argument,
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": conservative_history + "\n" + argument,
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Conservative",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": new_count,
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
