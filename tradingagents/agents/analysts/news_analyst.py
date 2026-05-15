from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import logging
import time
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Import Google tool call handler
from tradingagents.agents.utils.google_tool_handler import GoogleToolCallHandler

# Import market router utilities
from tradingagents.agents.utils.market_router import (
    get_company_name,
    get_market_info,
    needs_prefetch,
    is_dashscope_model,
    is_deepseek_model,
    is_zhipu_model,
)

# Import tool functions
from tradingagents.agents.utils.news_data_tools import get_news, get_global_news


def create_news_analyst(llm, toolkit=None):
    def news_analyst_node(state):
        start_time = datetime.now()

        # Tool call counter - prevent infinite loops
        tool_call_count = state.get("news_tool_call_count", 0)
        max_tool_calls = 3
        logger.info(f"[News Analyst] Current tool call count: {tool_call_count}/{max_tool_calls}")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        logger.info(f"[News Analyst] Starting analysis for {ticker}, trade date: {current_date}")
        session_id = state.get("session_id", "unknown")
        logger.info(f"[News Analyst] Session ID: {session_id}")

        # Get market info
        market_info = get_market_info(ticker)
        logger.info(f"[News Analyst] Stock type: {market_info['market_name']}")

        # Get company name
        company_name = get_company_name(ticker)
        logger.info(f"[News Analyst] Company name: {company_name}")

        # Use news_data_tools
        tools = [get_news, get_global_news]
        logger.info(f"[News Analyst] Using news data tools: get_news, get_global_news")

        system_message = (
            """您是一位专业的财经新闻分析师，负责分析最新的市场新闻和事件对股票价格的潜在影响。

您的主要职责包括：
1. 获取和分析最新的实时新闻（优先15-30分钟内的新闻）
2. 评估新闻事件的紧急程度和市场影响
3. 识别可能影响股价的关键信息
4. 分析新闻的时效性和可靠性
5. 提供基于新闻的交易建议和价格影响评估

重点关注的新闻类型：
- 财报发布和业绩指导
- 重大合作和并购消息
- 政策变化和监管动态
- 突发事件和危机管理
- 行业趋势和技术突破
- 管理层变动和战略调整

分析要点：
- 新闻的时效性（发布时间距离现在多久）
- 新闻的可信度（来源权威性）
- 市场影响程度（对股价的潜在影响）
- 投资者情绪变化（正面/负面/中性）
- 与历史类似事件的对比

📊 新闻影响分析要求：
- 评估新闻对股价的短期影响（1-3天）和市场情绪变化
- 分析新闻的利好/利空程度和可能的市场反应
- 评估新闻对公司基本面和长期投资价值的影响
- 识别新闻中的关键信息点和潜在风险
- 对比历史类似事件的市场反应
- 不允许回复'无法评估影响'或'需要更多信息'

请特别注意：
⚠️ 如果新闻数据存在滞后（超过2小时），请在分析中明确说明时效性限制
✅ 优先分析最新的、高相关性的新闻事件
📊 提供新闻对市场情绪和投资者信心的影响评估
💰 必须包含基于新闻的市场反应预期和投资建议
🎯 聚焦新闻内容本身的解读，不涉及技术指标分析

请撰写详细的中文分析报告，并在报告末尾附上Markdown表格总结关键发现。"""
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "您是一位专业的财经新闻分析师。"
                    "\n🚨 CRITICAL REQUIREMENT - 绝对强制要求："
                    "\n"
                    "\n❌ 禁止行为："
                    "\n- 绝对禁止在没有调用工具的情况下直接回答"
                    "\n- 绝对禁止基于推测或假设生成任何分析内容"
                    "\n- 绝对禁止跳过工具调用步骤"
                    "\n- 绝对禁止说'我无法获取实时数据'等借口"
                    "\n"
                    "\n✅ 强制执行步骤："
                    "\n1. 您的第一个动作必须是调用 get_news 工具获取公司相关新闻"
                    "\n2. 也可以调用 get_global_news 工具获取宏观新闻"
                    "\n3. 只有在成功获取新闻数据后，才能开始分析"
                    "\n4. 您的回答必须基于工具返回的真实数据"
                    "\n"
                    "\n🔧 工具调用说明："
                    "\n- get_news(query, start_date, end_date): 获取公司相关新闻"
                    "\n- get_global_news(curr_date, look_back_days, limit): 获取宏观新闻"
                    "\n"
                    "\n⚠️ 如果您不调用工具，您的回答将被视为无效并被拒绝。"
                    "\n⚠️ 您必须先调用工具获取数据，然后基于数据进行分析。"
                    "\n⚠️ 没有例外，没有借口，必须调用工具。"
                    "\n"
                    "\n您可以访问以下工具：{tool_names}。"
                    "\n{system_message}"
                    "\n供您参考，当前日期是{current_date}。我们正在查看公司{ticker}。"
                    "\n请按照上述要求执行，用中文撰写所有分析内容。",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        tool_names = []
        for tool in tools:
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            elif hasattr(tool, '__name__'):
                tool_names.append(tool.__name__)
            else:
                tool_names.append(str(tool))
        prompt = prompt.partial(tool_names=", ".join(tool_names))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(ticker=ticker)

        # Get model info
        model_info = ""
        try:
            if hasattr(llm, 'model_name'):
                model_info = f"{llm.__class__.__name__}:{llm.model_name}"
            else:
                model_info = llm.__class__.__name__
        except Exception:
            model_info = "Unknown"

        logger.info(f"[News Analyst] Preparing LLM call, model: {model_info}")

        # DashScope/DeepSeek/Zhipu pre-processing: force fetch news data
        pre_fetched_news = None
        if needs_prefetch(llm):
            logger.warning(f"[News Analyst] Detected {llm.__class__.__name__} model, starting pre-fetch...")
            try:
                logger.info(f"[News Analyst] Pre-fetch: forcing get_news call...")

                # Use get_news tool directly
                pre_fetched_news = get_news.invoke({
                    "ticker": ticker,
                    "start_date": current_date,
                    "end_date": current_date
                })

                logger.info(f"[News Analyst] Pre-fetch result length: {len(str(pre_fetched_news)) if pre_fetched_news else 0} chars")

                if pre_fetched_news and len(str(pre_fetched_news).strip()) > 100:
                    logger.info(f"[News Analyst] Pre-fetch successful: {len(str(pre_fetched_news))} chars")

                    # Generate analysis directly based on pre-fetched news
                    analysis_system_prompt = f"""您是一位专业的财经新闻分析师。

您的职责是基于提供的新闻数据，对股票进行深入的新闻分析。

分析要点：
1. 总结最新的新闻事件和市场动态
2. 分析新闻对股票的潜在影响
3. 评估市场情绪和投资者反应
4. 提供基于新闻的投资建议

重要说明：新闻数据已经为您提供，您无需调用任何工具，直接基于提供的数据进行分析。"""

                    enhanced_prompt = f"""请基于以下已获取的最新新闻数据，对股票 {ticker}（{company_name}）进行详细的新闻分析：

=== 最新新闻数据 ===
{pre_fetched_news}

请撰写详细的中文分析报告，包括：
1. 新闻事件总结
2. 对股票的影响分析
3. 市场情绪评估
4. 投资建议"""

                    logger.info(f"[News Analyst] Using pre-fetched news to generate analysis directly...")

                    llm_start_time = datetime.now()
                    result = llm.invoke([
                        {"role": "system", "content": analysis_system_prompt},
                        {"role": "user", "content": enhanced_prompt}
                    ])

                    llm_end_time = datetime.now()
                    llm_time_taken = (llm_end_time - llm_start_time).total_seconds()
                    logger.info(f"[News Analyst] LLM call complete (pre-fetch mode), took: {llm_time_taken:.2f}s")

                    if hasattr(result, 'content') and result.content:
                        report = result.content
                        logger.info(f"[News Analyst] Pre-fetch mode success, report length: {len(report)} chars")

                        from langchain_core.messages import AIMessage
                        clean_message = AIMessage(content=report)

                        end_time = datetime.now()
                        time_taken = (end_time - start_time).total_seconds()
                        logger.info(f"[News Analyst] Analysis complete (pre-fetch mode), total time: {time_taken:.2f}s")
                        return {
                            "messages": [clean_message],
                            "news_report": report,
                            "news_tool_call_count": tool_call_count + 1
                        }
                    else:
                        logger.warning(f"[News Analyst] LLM returned empty result, falling back to standard mode")

                else:
                    logger.warning(f"[News Analyst] Pre-fetch failed or content too short, falling back to standard mode")

            except Exception as e:
                logger.error(f"[News Analyst] Pre-fetch failed: {e}, falling back to standard mode")
                import traceback
                logger.error(f"[News Analyst] Stack trace: {traceback.format_exc()}")

        # Standard mode - use Google tool call handler or standard processing
        llm_start_time = datetime.now()
        chain = prompt | llm.bind_tools(tools)
        logger.info(f"[News Analyst] Starting LLM call for {ticker}")
        result = chain.invoke({"messages": state["messages"]})

        llm_end_time = datetime.now()
        llm_time_taken = (llm_end_time - llm_start_time).total_seconds()
        logger.info(f"[News Analyst] LLM call complete, took: {llm_time_taken:.2f}s")

        # Google model handling
        if GoogleToolCallHandler.is_google_model(llm):
            logger.info(f"[News Analyst] Google model detected, using unified tool call handler")

            analysis_prompt_template = GoogleToolCallHandler.create_analysis_prompt(
                ticker=ticker,
                company_name=company_name,
                analyst_type="新闻分析",
                specific_requirements="重点关注新闻事件对股价的影响、市场情绪变化、政策影响等。"
            )

            report, messages = GoogleToolCallHandler.handle_google_tool_calls(
                result=result,
                llm=llm,
                tools=tools,
                state=state,
                analysis_prompt_template=analysis_prompt_template,
                analyst_name="新闻分析师"
            )
        else:
            # Non-Google model processing
            logger.info(f"[News Analyst] Non-Google model ({llm.__class__.__name__}), using standard processing")

            current_tool_calls = len(result.tool_calls) if hasattr(result, 'tool_calls') else 0
            logger.info(f"[News Analyst] LLM called {current_tool_calls} tools")

            if current_tool_calls == 0:
                logger.warning(f"[News Analyst] {llm.__class__.__name__} did not call any tools, starting fallback...")

                try:
                    # Force get news data
                    logger.info(f"[News Analyst] Forcing get_news tool call...")

                    forced_news = get_news.invoke({
                        "query": ticker,
                        "start_date": current_date,
                        "end_date": current_date
                    })

                    logger.info(f"[News Analyst] Forced fetch result length: {len(str(forced_news)) if forced_news else 0} chars")

                    if forced_news and len(str(forced_news).strip()) > 100:
                        logger.info(f"[News Analyst] Forced fetch success: {len(str(forced_news))} chars")

                        forced_prompt = f"""
您是一位专业的财经新闻分析师。请基于以下最新获取的新闻数据，对股票 {ticker}（{company_name}）进行详细的新闻分析：

=== 最新新闻数据 ===
{forced_news}

=== 分析要求 ===
{system_message}

请基于上述真实新闻数据撰写详细的中文分析报告。
"""

                        logger.info(f"[News Analyst] Regenerating analysis from forced news data...")
                        forced_result = llm.invoke([{"role": "user", "content": forced_prompt}])

                        if hasattr(forced_result, 'content') and forced_result.content:
                            report = forced_result.content
                            logger.info(f"[News Analyst] Forced fallback success, report length: {len(report)} chars")
                        else:
                            logger.warning(f"[News Analyst] Forced fallback LLM returned empty, using original result")
                            report = result.content if hasattr(result, 'content') else ""
                    else:
                        logger.warning(f"[News Analyst] News tool fetch failed or too short, using original result")
                        report = result.content if hasattr(result, 'content') else ""

                except Exception as e:
                    logger.error(f"[News Analyst] Forced fallback failed: {e}")
                    import traceback
                    logger.error(f"[News Analyst] Stack trace: {traceback.format_exc()}")
                    report = result.content if hasattr(result, 'content') else ""
            else:
                # Has tool calls, use result directly
                report = result.content

        total_time_taken = (datetime.now() - start_time).total_seconds()
        logger.info(f"[News Analyst] Analysis complete, total time: {total_time_taken:.2f}s")

        # Return clean AIMessage without tool_calls to prevent infinite loops
        from langchain_core.messages import AIMessage
        clean_message = AIMessage(content=report)

        logger.info(f"[News Analyst] Returning clean message, report length: {len(report)} chars")

        return {
            "messages": [clean_message],
            "news_report": report,
            "news_tool_call_count": tool_call_count + 1
        }

    return news_analyst_node
