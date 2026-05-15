from langchain_core.messages import AIMessage
import logging
import time
import json

from tradingagents.agents.utils.market_router import get_market_info, get_company_name
from tradingagents.agents.utils.agent_utils import truncate_for_prompt

logger = logging.getLogger(__name__)


def create_bear_researcher(llm, memory):
    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        # 使用统一的股票类型检测
        ticker = state.get('company_of_interest', 'Unknown')
        market_info = get_market_info(ticker)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        asset_type = state.get("asset_type", "stock")
        company_name = get_company_name(ticker, market_info['market']) if asset_type != "etf" else f"ETF {ticker}"

        currency = market_info['currency']
        currency_symbol = market_info['currency_symbol']

        market_research_report = truncate_for_prompt(market_research_report)
        sentiment_report = truncate_for_prompt(sentiment_report)
        news_report = truncate_for_prompt(news_report)
        fundamentals_report = truncate_for_prompt(fundamentals_report)

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"

        # 安全检查：确保memory不为None
        if memory is not None:
            past_memories = memory.get_memories(curr_situation, n_matches=2)
        else:
            logger.warning("memory is None, skipping memory retrieval")
            past_memories = []

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        if asset_type == "etf":
            prompt = f"""你是一位看跌分析师，负责论证当前不应配置或不应交易 A 股 ETF {company_name} 的理由。

⚠️ 当前分析对象是 ETF，不是上市公司。请重点讨论 ETF 的拥挤交易、主题回撤、流动性、折溢价、跟踪误差和配置不适配风险。
⚠️ 所有价格和风险分析请使用 {currency}（{currency_symbol}）作为单位。

请用中文回答，重点关注以下几个方面：
- 交易风险：短期回撤、热点退潮、事件透支、技术破位
- 配置风险：暴露过度集中、长期持有逻辑不足、风格不匹配
- 产品缺陷：流动性不足、份额流出、折溢价、跟踪偏离
- 反驳看涨观点：指出看涨方对 ETF 交易性和配置性的乐观假设问题

可用资源：
ETF 市场报告：{market_research_report}
ETF 资金流/情绪报告：{sentiment_report}
ETF 新闻报告：{news_report}
ETF 产品报告：{fundamentals_report}
辩论对话历史：{history}
最后的看涨论点：{current_response}
类似情况的反思和经验教训：{past_memory_str}

请给出看跌论证，并明确说明这更像是“暂不交易”还是“暂不配置”的结论。"""
        else:
            prompt = f"""你是一位看跌分析师，负责论证不投资股票 {company_name}（股票代码：{ticker}）的理由。

⚠️ 重要提醒：当前分析的是 {market_info['market_name']}，所有价格和估值请使用 {currency}（{currency_symbol}）作为单位。
⚠️ 在你的分析中，请始终使用公司名称"{company_name}"而不是股票代码"{ticker}"来称呼这家公司。

你的目标是提出合理的论证，强调风险、挑战和负面指标。利用提供的研究和数据来突出潜在的不利因素并有效反驳看涨论点。

请用中文回答，重点关注以下几个方面：

- 风险和挑战：突出市场饱和、财务不稳定或宏观经济威胁等可能阻碍股票表现的因素
- 竞争劣势：强调市场地位较弱、创新下降或来自竞争对手威胁等脆弱性
- 负面指标：使用财务数据、市场趋势或最近不利消息的证据来支持你的立场
- 反驳看涨观点：用具体数据和合理推理批判性分析看涨论点，揭露弱点或过度乐观的假设
- 参与讨论：以对话风格呈现你的论点，直接回应看涨分析师的观点并进行有效辩论，而不仅仅是列举事实

可用资源：

市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务新闻：{news_report}
公司基本面报告：{fundamentals_report}
辩论对话历史：{history}
最后的看涨论点：{current_response}
类似情况的反思和经验教训：{past_memory_str}

请使用这些信息提供令人信服的看跌论点，反驳看涨声明，并参与动态辩论，展示投资该股票的风险和弱点。你还必须处理反思并从过去的经验教训和错误中学习。

请确保所有回答都使用中文。
"""

        response = llm.invoke(prompt)

        argument = f"Bear Analyst: {response.content}"

        new_count = investment_debate_state["count"] + 1
        logger.info(f"Bear researcher completed, count: {investment_debate_state['count']} -> {new_count}")

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bear_history": bear_history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count": new_count,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
