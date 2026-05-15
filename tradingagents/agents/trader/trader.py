import functools
import logging
import time
import json

from tradingagents.agents.utils.market_router import get_market_info, get_company_name
from tradingagents.agents.utils.agent_utils import truncate_for_prompt

logger = logging.getLogger(__name__)


def create_trader(llm, memory):
    def trader_node(state, name):
        company_name = state["company_of_interest"]
        asset_type = state.get("asset_type", "stock")
        investment_plan = state["investment_plan"]
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        # 使用统一的股票类型检测
        market_info = get_market_info(company_name)
        is_china = market_info['is_china']
        is_hk = market_info['is_hk']
        is_us = market_info['is_us']

        # 根据股票类型确定货币单位
        currency = market_info['currency']
        currency_symbol = market_info['currency_symbol']

        logger.debug(f"Trader node started for {company_name}, market: {market_info['market_name']}, currency: {currency}")
        logger.debug(f"Fundamentals report length: {len(fundamentals_report)}")

        market_research_report = truncate_for_prompt(market_research_report)
        sentiment_report = truncate_for_prompt(sentiment_report)
        news_report = truncate_for_prompt(news_report)
        fundamentals_report = truncate_for_prompt(fundamentals_report)
        investment_plan = truncate_for_prompt(investment_plan, max_chars=2200)

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"

        # 检查memory是否可用
        if memory is not None:
            past_memories = memory.get_memories(curr_situation, n_matches=2)
            past_memory_str = ""
            for i, rec in enumerate(past_memories, 1):
                past_memory_str += rec["recommendation"] + "\n\n"
        else:
            logger.warning("memory is None, skipping memory retrieval")
            past_memories = []
            past_memory_str = "暂无历史记忆数据可参考。"

        if asset_type == "etf":
            context = {
                "role": "user",
                "content": f"基于多位 ETF 分析师的综合结论，这里有一份面向 {company_name} 的 ETF 投资计划。请在此基础上给出明确的交易建议和配置建议。\n\nETF 投资计划：{investment_plan}\n\n请区分短中期交易机会与中期配置适配性。",
            }
        else:
            context = {
                "role": "user",
                "content": f"Based on a comprehensive analysis by a team of analysts, here is an investment plan tailored for {company_name}. This plan incorporates insights from current technical market trends, macroeconomic indicators, and social media sentiment. Use this plan as a foundation for evaluating your next trading decision.\n\nProposed Investment Plan: {investment_plan}\n\nLeverage these insights to make an informed and strategic decision.",
            }

        if asset_type == "etf":
            system_content = f"""您是一位专业的 ETF 交易员，负责分析 ETF 市场数据并做出投资与配置决策。

⚠️ 当前分析对象是 ETF {company_name}，而不是上市公司。
⚠️ 请使用 {currency}（{currency_symbol}）作为价格单位。

请在输出中同时包含：
1. **交易建议**：买入/持有/卖出
2. **交易目标价位**：必须给出具体数值
3. **止损或失效条件**
4. **配置建议**：适合配置/暂不配置/仅适合波段
5. **建议仓位区间**
6. **置信度** 与 **风险评分**
7. **详细推理**

特别注意：
- 需要明确区分“交易机会”和“配置价值”
- 重点参考 ETF 产品报告中的持仓结构、流动性、份额变化、折溢价、跟踪信息
- 禁止使用上市公司财报视角做推理
- 最终必须出现“交易建议：”和“配置建议：”

请用中文输出，并以 `最终交易建议: **买入/持有/卖出**` 结束。

类似情况下的交易反思和经验教训：{past_memory_str}"""
        else:
            system_content = f"""您是一位专业的交易员，负责分析市场数据并做出投资决策。基于您的分析，请提供具体的买入、卖出或持有建议。

⚠️ 重要提醒：当前分析的股票代码是 {company_name}，请使用正确的货币单位：{currency}（{currency_symbol}）

🔴 严格要求：
- 股票代码 {company_name} 的公司名称必须严格按照基本面报告中的真实数据
- 绝对禁止使用错误的公司名称或混淆不同的股票
- 所有分析必须基于提供的真实数据，不允许假设或编造
- **必须提供具体的目标价位，不允许设置为null或空值**

请在您的分析中包含以下关键信息：
1. **投资建议**: 明确的买入/持有/卖出决策
2. **目标价位**: 基于分析的合理目标价格({currency}) - 🚨 强制要求提供具体数值
   - 买入建议：提供目标价位和预期涨幅
   - 持有建议：提供合理价格区间（如：{currency_symbol}XX-XX）
   - 卖出建议：提供止损价位和目标卖出价
3. **置信度**: 对决策的信心程度(0-1之间)
4. **风险评分**: 投资风险等级(0-1之间，0为低风险，1为高风险)
5. **详细推理**: 支持决策的具体理由

🎯 目标价位计算指导：
- 基于基本面分析中的估值数据（P/E、P/B、DCF等）
- 参考技术分析的支撑位和阻力位
- 考虑行业平均估值水平
- 结合市场情绪和新闻影响
- 即使市场情绪过热，也要基于合理估值给出目标价

特别注意：
- 如果是中国A股（6位数字代码），请使用人民币（¥）作为价格单位
- 如果是美股或港股，请使用美元（$）作为价格单位
- 目标价位必须与当前股价的货币单位保持一致
- 必须使用基本面报告中提供的正确公司名称
- **绝对不允许说"无法确定目标价"或"需要更多信息"**

请用中文撰写分析内容，并始终以'最终交易建议: **买入/持有/卖出**'结束您的回应以确认您的建议。

请不要忘记利用过去决策的经验教训来避免重复错误。以下是类似情况下的交易反思和经验教训: {past_memory_str}"""

        messages = [
            {
                "role": "system",
                "content": system_content,
            },
            context,
        ]

        logger.debug(f"Invoking LLM with currency: {currency}")

        result = llm.invoke(messages)

        logger.debug(f"Trader response length: {len(result.content)}")

        return {
            "messages": [result],
            "trader_investment_plan": result.content,
            "sender": name,
        }

    return functools.partial(trader_node, name="Trader")
