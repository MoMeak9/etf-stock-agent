from langchain_core.messages import AIMessage
import logging
import time
import json

from tradingagents.agents.utils.market_router import get_market_info, get_company_name
from tradingagents.agents.utils.agent_utils import truncate_for_prompt

logger = logging.getLogger(__name__)


def create_bull_researcher(llm, memory):
    def bull_node(state) -> dict:
        logger.debug("Bull researcher node started")

        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")

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

        logger.debug(f"Reports received - market: {len(market_research_report)}, sentiment: {len(sentiment_report)}, news: {len(news_report)}, fundamentals: {len(fundamentals_report)}")
        logger.debug(f"Ticker: {ticker}, company: {company_name}, market: {market_info['market_name']}, currency: {currency}")

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
            prompt = f"""你是一位看涨分析师，负责为 A 股 ETF {company_name} 建立强有力的投资论证。

⚠️ 当前分析对象是 ETF，不是上市公司。请重点讨论交易机会、配置价值、流动性、资金流、持仓暴露、主题或指数驱动因素。
⚠️ 所有价格和风险分析请使用 {currency}（{currency_symbol}）作为单位。

请用中文回答，重点关注以下几个方面：
- 交易价值：短中期趋势、资金流、事件催化、技术结构
- 配置价值：指数或主题暴露、长期持有逻辑、仓位适配性
- 产品优势：流动性、持仓结构、份额变化、折溢价与跟踪质量
- 反驳看跌观点：针对 ETF 风险、拥挤度、回撤担忧做出回应

可用资源：
ETF 市场报告：{market_research_report}
ETF 资金流/情绪报告：{sentiment_report}
ETF 新闻报告：{news_report}
ETF 产品报告：{fundamentals_report}
辩论对话历史：{history}
最后的看跌论点：{current_response}
类似情况的反思和经验教训：{past_memory_str}

请给出看涨论证，并明确区分这是更偏“交易机会”还是更偏“配置机会”。"""
        else:
            prompt = f"""你是一位看涨分析师，负责为股票 {company_name}（股票代码：{ticker}）的投资建立强有力的论证。

⚠️ 重要提醒：当前分析的是 {'中国A股' if is_china else '海外股票'}，所有价格和估值请使用 {currency}（{currency_symbol}）作为单位。
⚠️ 在你的分析中，请始终使用公司名称"{company_name}"而不是股票代码"{ticker}"来称呼这家公司。

你的任务是构建基于证据的强有力案例，强调增长潜力、竞争优势和积极的市场指标。利用提供的研究和数据来解决担忧并有效反驳看跌论点。

请用中文回答，重点关注以下几个方面：
- 增长潜力：突出公司的市场机会、收入预测和可扩展性
- 竞争优势：强调独特产品、强势品牌或主导市场地位等因素
- 积极指标：使用财务健康状况、行业趋势和最新积极消息作为证据
- 反驳看跌观点：用具体数据和合理推理批判性分析看跌论点，全面解决担忧并说明为什么看涨观点更有说服力
- 参与讨论：以对话风格呈现你的论点，直接回应看跌分析师的观点并进行有效辩论，而不仅仅是列举数据

可用资源：
市场研究报告：{market_research_report}
社交媒体情绪报告：{sentiment_report}
最新世界事务新闻：{news_report}
公司基本面报告：{fundamentals_report}
辩论对话历史：{history}
最后的看跌论点：{current_response}
类似情况的反思和经验教训：{past_memory_str}

请使用这些信息提供令人信服的看涨论点，反驳看跌担忧，并参与动态辩论，展示看涨立场的优势。你还必须处理反思并从过去的经验教训和错误中学习。

请确保所有回答都使用中文。
"""

        response = llm.invoke(prompt)

        argument = f"Bull Analyst: {response.content}"

        new_count = investment_debate_state["count"] + 1
        logger.info(f"Bull researcher completed, count: {investment_debate_state['count']} -> {new_count}")

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": bull_history + "\n" + argument,
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": new_count,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
