import logging
import time
import json
from tradingagents.agents.utils.agent_utils import truncate_for_prompt

logger = logging.getLogger(__name__)


def create_research_manager(llm, memory):
    def research_manager_node(state) -> dict:
        history = state["investment_debate_state"].get("history", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        investment_debate_state = state["investment_debate_state"]

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

        asset_type = state.get("asset_type", "stock")

        if asset_type == "etf":
            prompt = f"""作为 ETF 投资组合经理和辩论主持人，您的职责是评估这轮辩论，并同时输出：
1. 交易结论（买入/持有/卖出）
2. 配置结论（适合配置/暂不配置/仅适合波段）

请简洁总结双方最有说服力的 ETF 论点，重点聚焦：
- ETF 当前是交易机会还是配置机会
- 资金流、技术结构、事件催化
- 持仓暴露、配置适配性、流动性、折溢价、跟踪质量

你必须给出：
- 明确的交易结论
- 明确的配置结论
- 目标价或关键交易区间
- 建议持有周期与适用场景

以下是您对错误的过去反思：
\"{past_memory_str}\"

以下是综合分析报告：
ETF 市场报告：{market_research_report}
ETF 资金流/情绪报告：{sentiment_report}
ETF 新闻报告：{news_report}
ETF 产品报告：{fundamentals_report}

以下是辩论历史：
{history}

请用中文输出，并在结果中明确写出“交易结论：”和“配置结论：”。"""
        elif asset_type == "fund":
            prompt = f"""作为开放式公募基金投资研究经理和辩论主持人，您的职责是评估这轮基金研究辩论，并形成面向中长期持有人的基金决策。

当前对象是开放式公募基金，不是股票，也不是 ETF 二级市场交易品种。最终建议只能围绕：申购、分批申购、持有、赎回、观望。

请简洁总结双方最有说服力的基金论点，重点聚焦：
- 净值表现、回撤、波动、收益质量与同类比较
- 产品结构、费率、规模、申购/赎回状态、限购或暂停情况
- 持仓结构与宏观环境、行业景气、资产类别周期的匹配度
- QDII 基金的汇率风险、海外市场风险、净值披露滞后、额度与申赎限制
- 债券基金的利率风险、信用风险、久期风险、组合流动性
- 货币市场基金的收益稳定性、流动性、赎回压力与资金面变化

您的输出必须包含：
- 明确的基金建议：只能从申购、分批申购、持有、赎回、观望中选择一个
- 中长期持有或观察逻辑
- 适用投资者与主要风险
- 对交易员后续行动计划的约束

禁止事项：
- 禁止使用股票买入/卖出、止损、目标价等语言
- 禁止使用 ETF 二级市场交易、折溢价套利、盘中交易等语言
- 禁止把完整选项列表作为建议输出，必须给出唯一基金建议

以下是您对错误的过去反思：
\"{past_memory_str}\"

以下是综合分析报告：
基金净值与收益报告：{market_research_report}
基金持仓与暴露报告：{sentiment_report}
基金公告与事件报告：{news_report}
基金产品结构报告：{fundamentals_report}

以下是辩论历史：
{history}

请用中文输出，并明确写出“基金建议：”。"""
        else:
            prompt = f"""作为投资组合经理和辩论主持人，您的职责是批判性地评估这轮辩论并做出明确决策：支持看跌分析师、看涨分析师，或者仅在基于所提出论点有强有力理由时选择持有。

简洁地总结双方的关键观点，重点关注最有说服力的证据或推理。您的建议——买入、卖出或持有——必须明确且可操作。避免仅仅因为双方都有有效观点就默认选择持有；要基于辩论中最强有力的论点做出承诺。

此外，为交易员制定详细的投资计划。这应该包括：

您的建议：基于最有说服力论点的明确立场。
理由：解释为什么这些论点导致您的结论。
战略行动：实施建议的具体步骤。
📊 目标价格分析：基于所有可用报告（基本面、新闻、情绪），提供全面的目标价格区间和具体价格目标。考虑：
- 基本面报告中的基本估值
- 新闻对价格预期的影响
- 情绪驱动的价格调整
- 技术支撑/阻力位
- 风险调整价格情景（保守、基准、乐观）
- 价格目标的时间范围（1个月、3个月、6个月）
💰 您必须提供具体的目标价格 - 不要回复"无法确定"或"需要更多信息"。

考虑您在类似情况下的过去错误。利用这些见解来完善您的决策制定，确保您在学习和改进。以对话方式呈现您的分析，就像自然说话一样，不使用特殊格式。

以下是您对错误的过去反思：
\"{past_memory_str}\"

以下是综合分析报告：
市场研究：{market_research_report}

情绪分析：{sentiment_report}

新闻分析：{news_report}

基本面分析：{fundamentals_report}

以下是辩论：
辩论历史：
{history}

请用中文撰写所有分析内容和建议。"""

        # 统计 prompt 大小
        prompt_length = len(prompt)
        estimated_tokens = int(prompt_length / 1.8)

        logger.info(f"Research Manager prompt stats: debate_history={len(history)} chars, total={prompt_length} chars, ~{estimated_tokens} tokens")

        start_time = time.time()

        response = llm.invoke(prompt)

        elapsed_time = time.time() - start_time

        response_length = len(response.content) if response and hasattr(response, 'content') else 0
        estimated_output_tokens = int(response_length / 1.8)

        logger.info(f"Research Manager LLM call completed in {elapsed_time:.2f}s, response: {response_length} chars, ~{estimated_output_tokens} tokens")

        new_investment_debate_state = {
            "judge_decision": response.content,
            "history": investment_debate_state.get("history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": response.content,
            "count": investment_debate_state["count"],
        }

        return {
            "investment_debate_state": new_investment_debate_state,
            "investment_plan": response.content,
        }

    return research_manager_node
