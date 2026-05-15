from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import logging
import time
import json
import traceback
from datetime import datetime, timedelta

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
from tradingagents.agents.utils.core_stock_tools import get_stock_data
from tradingagents.agents.utils.technical_indicators_tools import get_indicators

# === 配置参数 ===
MARKET_DATA_LOOKBACK_DAYS = 180
MARKET_INDICATOR_LOOKBACK_DAYS = 60
REQUIRED_MARKET_INDICATORS = [
    "close_5_sma",
    "close_10_sma",
    "close_20_sma",
    "close_60_sma",
    "macd",
    "macds",
    "macdh",
    "rsi",
    "boll",
    "boll_ub",
    "boll_lb",
]

def _history_start_date(current_date: str, lookback_days: int | None = None) -> str:
    if lookback_days is None:
        lookback_days = MARKET_DATA_LOOKBACK_DAYS
    dt = datetime.strptime(current_date, "%Y-%m-%d")
    return (dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

def _build_supplemental_tool_calls(
    ticker: str,
    current_date: str,
    existing_tool_calls: list[dict] | None,
) -> list[dict]:
    """补足技术分析所需的历史行情和关键指标调用。"""
    existing_tool_calls = existing_tool_calls or []
    supplemental_calls: list[dict] = []

    has_history_stock_data = False
    requested_indicators = set()
    history_start = _history_start_date(current_date)

    for tool_call in existing_tool_calls:
        if tool_call.get("name") == "get_stock_data":
            args = tool_call.get("args", {})
            start_date = args.get("start_date")
            end_date = args.get("end_date")
            if (
                isinstance(start_date, str)
                and isinstance(end_date, str)
                and start_date < end_date
                and start_date <= history_start
                and end_date >= current_date
            ):
                has_history_stock_data = True
        elif tool_call.get("name") == "get_indicators":
            indicator_arg = str(tool_call.get("args", {}).get("indicator", ""))
            for indicator in indicator_arg.split(","):
                indicator = indicator.strip()
                if indicator:
                    requested_indicators.add(indicator)

    if not has_history_stock_data:
        supplemental_calls.append(
            {
                "name": "get_stock_data",
                "args": {
                    "symbol": ticker,
                    "start_date": history_start,
                    "end_date": current_date,
                },
            }
        )

    for indicator in REQUIRED_MARKET_INDICATORS:
        if indicator not in requested_indicators:
            supplemental_calls.append(
                {
                    "name": "get_indicators",
                    "args": {
                        "symbol": ticker,
                        "indicator": indicator,
                        "curr_date": current_date,
                        "look_back_days": MARKET_INDICATOR_LOOKBACK_DAYS,
                    },
                }
            )

    return supplemental_calls

def _build_market_analysis_prompt(
    company_name: str,
    ticker: str,
    market_name: str,
    currency_name: str,
    currency_symbol: str,
    current_date: str,
    history_start_date: str,
) -> str:
    """构建最终技术分析报告提示词。"""
    return f"""现在请基于上述工具获取的数据，生成详细的技术分析报告。

**分析对象：**
- 公司名称：{company_name}
- 股票代码：{ticker}
- 所属市场：{market_name}
- 计价货币：{currency_name}（{currency_symbol}）

**数据使用要求：**
- 已提供从 {history_start_date} 到 {current_date} 的历史行情数据，以及关键技术指标结果。
- 如果上文已经包含多日历史行情和指标结果，不要再写“仅有单日数据”或“缺乏过去5至10个交易日/20至60个交易日数据”。
- 短期趋势（5-10个交易日）、中期趋势（20-60个交易日）、成交量分析、关键价格区间，优先基于历史行情和指标结果填写。
- 只有当工具结果明确显示无数据、报错或记录不足时，才能说明无法计算，并指出具体缺失项。

**输出格式要求（必须严格遵守）：**

请按照以下专业格式输出报告，不要使用emoji符号（如📊📈📉💭等），使用纯文本标题：

# **{company_name}（{ticker}）技术分析报告**
**分析日期：[当前日期]**

---

## 一、股票基本信息

- **公司名称**：{company_name}
- **股票代码**：{ticker}
- **所属市场**：{market_name}
- **当前价格**：[从工具数据中获取] {currency_symbol}
- **涨跌幅**：[从工具数据中获取]
- **成交量**：[从工具数据中获取]

---

## 二、技术指标分析

### 1. 移动平均线（MA）分析

[分析MA5、MA10、MA20、MA60等均线系统，包括：]
- 当前各均线数值
- 均线排列形态（多头/空头）
- 价格与均线的位置关系
- 均线交叉信号

### 2. MACD指标分析

[分析MACD指标，包括：]
- DIF、DEA、MACD柱状图当前数值
- 金叉/死叉信号
- 背离现象
- 趋势强度判断

### 3. RSI相对强弱指标

[分析RSI指标，包括：]
- RSI当前数值
- 超买/超卖区域判断
- 背离信号
- 趋势确认

### 4. 布林带（BOLL）分析

[分析布林带指标，包括：]
- 上轨、中轨、下轨数值
- 价格在布林带中的位置
- 带宽变化趋势
- 突破信号

---

## 三、价格趋势分析

### 1. 短期趋势（5-10个交易日）

[分析短期价格走势，包括支撑位、压力位、关键价格区间]

### 2. 中期趋势（20-60个交易日）

[分析中期价格走势，结合均线系统判断趋势方向]

### 3. 成交量分析

[分析成交量变化，量价配合情况]

---

## 四、投资建议

### 1. 综合评估

[基于上述技术指标，给出综合评估]

### 2. 操作建议

- **投资评级**：买入/持有/卖出
- **目标价位**：[给出具体价格区间] {currency_symbol}
- **止损位**：[给出止损价格] {currency_symbol}
- **风险提示**：[列出主要风险因素]

### 3. 关键价格区间

- **支撑位**：[具体价格]
- **压力位**：[具体价格]
- **突破买入价**：[具体价格]
- **跌破卖出价**：[具体价格]

---

**重要提醒：**
- 必须严格按照上述格式输出，使用标准的Markdown标题（#、##、###）
- 不要使用emoji符号（📊📈📉💭等）
- 所有价格数据使用{currency_name}（{currency_symbol}）表示
- 确保在分析中正确使用公司名称"{company_name}"和股票代码"{ticker}"
- 报告标题必须是：# **{company_name}（{ticker}）技术分析报告**
- 报告必须基于工具返回的真实数据进行分析
- 包含具体的技术指标数值和专业分析
- 提供明确的投资建议和风险提示
- 报告长度不少于800字
- 使用中文撰写
- 使用表格展示数据时，确保格式规范"""
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import logging
import time
import json
import traceback
from datetime import datetime, timedelta

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
from tradingagents.agents.utils.core_stock_tools import get_stock_data
from tradingagents.agents.utils.technical_indicators_tools import get_indicators

MARKET_DATA_LOOKBACK_DAYS = 180
MARKET_INDICATOR_LOOKBACK_DAYS = 60
REQUIRED_MARKET_INDICATORS = [
    "close_5_sma",
    "close_10_sma",
    "close_20_sma",
    "close_60_sma",
    "macd",
    "macds",
    "macdh",
    "rsi",
    "boll",
    "boll_ub",
    "boll_lb",
]


def _history_start_date(current_date: str, lookback_days: int | None = None) -> str:
    if lookback_days is None:
        lookback_days = MARKET_DATA_LOOKBACK_DAYS
    dt = datetime.strptime(current_date, "%Y-%m-%d")
    return (dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")


def _build_supplemental_tool_calls(
    ticker: str,
    current_date: str,
    existing_tool_calls: list[dict] | None,
) -> list[dict]:
    """补足技术分析所需的历史行情和关键指标调用。"""
    existing_tool_calls = existing_tool_calls or []
    supplemental_calls: list[dict] = []

    has_history_stock_data = False
    requested_indicators = set()
    history_start = _history_start_date(current_date)

    for tool_call in existing_tool_calls:
        if tool_call.get("name") == "get_stock_data":
            args = tool_call.get("args", {})
            start_date = args.get("start_date")
            end_date = args.get("end_date")
            if (
                isinstance(start_date, str)
                and isinstance(end_date, str)
                and start_date < end_date
                and start_date <= history_start
                and end_date >= current_date
            ):
                has_history_stock_data = True
        elif tool_call.get("name") == "get_indicators":
            indicator_arg = str(tool_call.get("args", {}).get("indicator", ""))
            for indicator in indicator_arg.split(","):
                indicator = indicator.strip()
                if indicator:
                    requested_indicators.add(indicator)

    if not has_history_stock_data:
        supplemental_calls.append(
            {
                "name": "get_stock_data",
                "args": {
                    "symbol": ticker,
                    "start_date": history_start,
                    "end_date": current_date,
                },
            }
        )

    for indicator in REQUIRED_MARKET_INDICATORS:
        if indicator not in requested_indicators:
            supplemental_calls.append(
                {
                    "name": "get_indicators",
                    "args": {
                        "symbol": ticker,
                        "indicator": indicator,
                        "curr_date": current_date,
                        "look_back_days": MARKET_INDICATOR_LOOKBACK_DAYS,
                    },
                }
            )

    return supplemental_calls


def _build_market_analysis_prompt(
    company_name: str,
    ticker: str,
    market_name: str,
    currency_name: str,
    currency_symbol: str,
    current_date: str,
    history_start_date: str,
) -> str:
    """构建最终技术分析报告提示词。"""
    return f"""现在请基于上述工具获取的数据，生成详细的技术分析报告。

**分析对象：**
- 公司名称：{company_name}
- 股票代码：{ticker}
- 所属市场：{market_name}
- 计价货币：{currency_name}（{currency_symbol}）

**数据使用要求：**
- 已提供从 {history_start_date} 到 {current_date} 的历史行情数据，以及关键技术指标结果。
- 如果上文已经包含多日历史行情和指标结果，不要再写“仅有单日数据”或“缺乏过去5至10个交易日/20至60个交易日数据”。
- 短期趋势（5-10个交易日）、中期趋势（20-60个交易日）、成交量分析、关键价格区间，优先基于历史行情和指标结果填写。
- 只有当工具结果明确显示无数据、报错或记录不足时，才能说明无法计算，并指出具体缺失项。

**输出格式要求（必须严格遵守）：**

请按照以下专业格式输出报告，不要使用emoji符号（如📊📈📉💭等），使用纯文本标题：

# **{company_name}（{ticker}）技术分析报告**
**分析日期：[当前日期]**

---

## 一、股票基本信息

- **公司名称**：{company_name}
- **股票代码**：{ticker}
- **所属市场**：{market_name}
- **当前价格**：[从工具数据中获取] {currency_symbol}
- **涨跌幅**：[从工具数据中获取]
- **成交量**：[从工具数据中获取]

---

## 二、技术指标分析

### 1. 移动平均线（MA）分析

[分析MA5、MA10、MA20、MA60等均线系统，包括：]
- 当前各均线数值
- 均线排列形态（多头/空头）
- 价格与均线的位置关系
- 均线交叉信号

### 2. MACD指标分析

[分析MACD指标，包括：]
- DIF、DEA、MACD柱状图当前数值
- 金叉/死叉信号
- 背离现象
- 趋势强度判断

### 3. RSI相对强弱指标

[分析RSI指标，包括：]
- RSI当前数值
- 超买/超卖区域判断
- 背离信号
- 趋势确认

### 4. 布林带（BOLL）分析

[分析布林带指标，包括：]
- 上轨、中轨、下轨数值
- 价格在布林带中的位置
- 带宽变化趋势
- 突破信号

---

## 三、价格趋势分析

### 1. 短期趋势（5-10个交易日）

[分析短期价格走势，包括支撑位、压力位、关键价格区间]

### 2. 中期趋势（20-60个交易日）

[分析中期价格走势，结合均线系统判断趋势方向]

### 3. 成交量分析

[分析成交量变化，量价配合情况]

---

## 四、投资建议

### 1. 综合评估

[基于上述技术指标，给出综合评估]

### 2. 操作建议

- **投资评级**：买入/持有/卖出
- **目标价位**：[给出具体价格区间] {currency_symbol}
- **止损位**：[给出止损价格] {currency_symbol}
- **风险提示**：[列出主要风险因素]

### 3. 关键价格区间

- **支撑位**：[具体价格]
- **压力位**：[具体价格]
- **突破买入价**：[具体价格]
- **跌破卖出价**：[具体价格]

---

**重要提醒：**
- 必须严格按照上述格式输出，使用标准的Markdown标题（#、##、###）
- 不要使用emoji符号（📊📈📉💭等）
- 所有价格数据使用{currency_name}（{currency_symbol}）表示
- 确保在分析中正确使用公司名称"{company_name}"和股票代码"{ticker}"
- 报告标题必须是：# **{company_name}（{ticker}）技术分析报告**
- 报告必须基于工具返回的真实数据进行分析
- 包含具体的技术指标数值和专业分析
- 提供明确的投资建议和风险提示
- 报告长度不少于800字
- 使用中文撰写
- 使用表格展示数据时，确保格式规范"""


def create_market_analyst(llm, toolkit=None):

    def market_analyst_node(state):
        logger.debug(f"===== Market analyst node started =====")

        # Tool call counter - prevent infinite loops
        tool_call_count = state.get("market_tool_call_count", 0)
        max_tool_calls = 3
        logger.info(f"Current tool call count: {tool_call_count}/{max_tool_calls}")

        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        logger.debug(f"Input params: ticker={ticker}, date={current_date}")
        logger.debug(f"Message count in state: {len(state.get('messages', []))}")
        logger.debug(f"Existing market report: {state.get('market_report', 'None')}")

        # Get market info from market_router
        market_info = get_market_info(ticker)

        logger.debug(f"Stock type: {ticker} -> {market_info['market_name']} ({market_info['currency_name']})")

        # Get company name
        company_name = get_company_name(ticker)
        logger.debug(f"Company name: {ticker} -> {company_name}")

        # Use core_stock_tools and technical_indicators_tools
        logger.info(f"[Market Analyst] Using core stock tools for market data")
        tools = [get_stock_data, get_indicators]

        # Get tool names for debug
        tool_names_debug = []
        for tool in tools:
            if hasattr(tool, 'name'):
                tool_names_debug.append(tool.name)
            elif hasattr(tool, '__name__'):
                tool_names_debug.append(tool.__name__)
            else:
                tool_names_debug.append(str(tool))
        logger.info(f"[Market Analyst] Bound tools: {tool_names_debug}")
        logger.info(f"[Market Analyst] Target market: {market_info['market_name']}")
        history_start_date = _history_start_date(current_date)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一位专业的股票技术分析师，与其他分析师协作。\n"
                    "\n"
                    "📋 **分析对象：**\n"
                    "- 公司名称：{company_name}\n"
                    "- 股票代码：{ticker}\n"
                    "- 所属市场：{market_name}\n"
                    "- 计价货币：{currency_name}（{currency_symbol}）\n"
                    "- 分析日期：{current_date}\n"
                    "\n"
                    "🔧 **工具使用：**\n"
                    "你可以使用以下工具：{tool_names}\n"
                    "⚠️ 重要工作流程：\n"
                    "1. 如果消息历史中没有工具结果，先调用 get_stock_data 工具获取历史股票数据\n"
                    "   - ticker: {ticker}\n"
                    "   - start_date: {history_start_date}\n"
                    "   - end_date: {current_date}\n"
                    "2. 然后调用 get_indicators 获取关键技术指标：{required_indicators}\n"
                    "3. 如果消息历史中已经有工具结果（ToolMessage），立即基于工具数据生成最终分析报告\n"
                    "4. 不要重复调用工具！\n"
                    "5. 接收到工具数据后，必须立即生成完整的技术分析报告，不要再调用任何工具\n"
                    "\n"
                    "📝 **输出格式要求（必须严格遵守）：**\n"
                    "\n"
                    "## 📊 股票基本信息\n"
                    "- 公司名称：{company_name}\n"
                    "- 股票代码：{ticker}\n"
                    "- 所属市场：{market_name}\n"
                    "\n"
                    "## 📈 技术指标分析\n"
                    "[在这里分析移动平均线、MACD、RSI、布林带等技术指标，提供具体数值]\n"
                    "\n"
                    "## 📉 价格趋势分析\n"
                    "[在这里分析价格趋势，考虑{market_name}市场特点]\n"
                    "\n"
                    "## 💭 投资建议\n"
                    "[在这里给出明确的投资建议：买入/持有/卖出]\n"
                    "\n"
                    "⚠️ **重要提醒：**\n"
                    "- 必须使用上述格式输出，不要自创标题格式\n"
                    "- 所有价格数据使用{currency_name}（{currency_symbol}）表示\n"
                    "- 确保在分析中正确使用公司名称\"{company_name}\"和股票代码\"{ticker}\"\n"
                    "- 不要在标题中使用\"技术分析报告\"等自创标题\n"
                    "- 如果你有明确的技术面投资建议（买入/持有/卖出），请在投资建议部分明确标注\n"
                    "- 不要使用'最终交易建议'前缀，因为最终决策需要综合所有分析师的意见\n"
                    "\n"
                    "请使用中文，基于真实数据进行分析。",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        # Get tool names safely
        tool_names = []
        for tool in tools:
            if hasattr(tool, 'name'):
                tool_names.append(tool.name)
            elif hasattr(tool, '__name__'):
                tool_names.append(tool.__name__)
            else:
                tool_names.append(str(tool))

        # Set all template variables
        prompt = prompt.partial(tool_names=", ".join(tool_names))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(history_start_date=history_start_date)
        prompt = prompt.partial(required_indicators=", ".join(REQUIRED_MARKET_INDICATORS))
        prompt = prompt.partial(ticker=ticker)
        prompt = prompt.partial(company_name=company_name)
        prompt = prompt.partial(market_name=market_info['market_name'])
        prompt = prompt.partial(currency_name=market_info['currency_name'])
        prompt = prompt.partial(currency_symbol=market_info['currency_symbol'])

        logger.info(f"[Market Analyst] LLM type: {llm.__class__.__name__}")
        logger.info(f"[Market Analyst] LLM model: {getattr(llm, 'model_name', 'unknown')}")
        logger.info(f"[Market Analyst] Message history count: {len(state['messages'])}")
        logger.info(f"[Market Analyst] Company name: {company_name}")
        logger.info(f"[Market Analyst] Ticker: {ticker}")

        chain = prompt | llm.bind_tools(tools)

        logger.info(f"[Market Analyst] Starting LLM call...")
        result = chain.invoke({"messages": state["messages"]})
        logger.info(f"[Market Analyst] LLM call complete")

        # Log LLM response
        logger.debug(f"[Market Analyst] Response type: {type(result).__name__}")
        logger.debug(f"[Market Analyst] Response content: {str(result.content)[:500]}...")
        if hasattr(result, 'tool_calls') and result.tool_calls:
            logger.debug(f"[Market Analyst] Tool calls: {result.tool_calls}")

        # Use Google tool call handler for Google models
        if GoogleToolCallHandler.is_google_model(llm):
            logger.info(f"[Market Analyst] Google model detected, using unified tool call handler")

            analysis_prompt_template = GoogleToolCallHandler.create_analysis_prompt(
                ticker=ticker,
                company_name=company_name,
                analyst_type="市场分析",
                specific_requirements="重点关注市场数据、价格走势、交易量变化等市场指标。"
            )

            report, messages = GoogleToolCallHandler.handle_google_tool_calls(
                result=result,
                llm=llm,
                tools=tools,
                state=state,
                analysis_prompt_template=analysis_prompt_template,
                analyst_name="市场分析师"
            )

            return {
                "messages": [result],
                "market_report": report,
                "market_tool_call_count": tool_call_count + 1
            }
        else:
            # Non-Google model processing
            logger.info(f"[Market Analyst] Non-Google model ({llm.__class__.__name__}), using standard processing")

            if len(result.tool_calls) == 0:
                report = result.content
                logger.info(f"[Market Analyst] Direct reply (no tool calls), length: {len(report)}")
            else:
                logger.info(f"[Market Analyst] Tool calls detected: {[call.get('name', 'unknown') for call in result.tool_calls]}")

                try:
                    from langchain_core.messages import ToolMessage, HumanMessage

                    tool_messages = []
                    supplemental_context = []
                    tool_calls = list(result.tool_calls)
                    for tool_call in tool_calls:
                        tool_name = tool_call.get('name')
                        tool_args = tool_call.get('args', {})
                        tool_id = tool_call.get('id')

                        logger.debug(f"Executing tool: {tool_name}, args: {tool_args}")

                        tool_result = None
                        for tool in tools:
                            current_tool_name = None
                            if hasattr(tool, 'name'):
                                current_tool_name = tool.name
                            elif hasattr(tool, '__name__'):
                                current_tool_name = tool.__name__

                            if current_tool_name == tool_name:
                                try:
                                    tool_result = tool.invoke(tool_args)
                                    logger.debug(f"Tool execution success, result length: {len(str(tool_result))}")
                                    break
                                except Exception as tool_error:
                                    logger.error(f"Tool execution failed: {tool_error}")
                                    tool_result = f"Tool execution failed: {str(tool_error)}"

                        if tool_result is None:
                            tool_result = f"Tool not found: {tool_name}"

                        tool_message = ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_id
                        )
                        tool_messages.append(tool_message)

                    supplemental_calls = _build_supplemental_tool_calls(
                        ticker=ticker,
                        current_date=current_date,
                        existing_tool_calls=tool_calls,
                    )
                    for tool_call in supplemental_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        logger.debug(f"Executing supplemental tool: {tool_name}, args: {tool_args}")

                        tool_result = None
                        for tool in tools:
                            current_tool_name = None
                            if hasattr(tool, 'name'):
                                current_tool_name = tool.name
                            elif hasattr(tool, '__name__'):
                                current_tool_name = tool.__name__

                            if current_tool_name == tool_name:
                                try:
                                    tool_result = tool.invoke(tool_args)
                                    break
                                except Exception as tool_error:
                                    logger.error(f"Supplemental tool execution failed: {tool_error}")
                                    tool_result = f"Tool execution failed: {str(tool_error)}"

                        if tool_result is None:
                            tool_result = f"Tool not found: {tool_name}"

                        supplemental_context.append(
                            "补充工具数据：\n"
                            f"- 工具：{tool_name}\n"
                            f"- 参数：{json.dumps(tool_args, ensure_ascii=False)}\n"
                            f"- 结果：\n{tool_result}"
                        )

                    analysis_prompt = _build_market_analysis_prompt(
                        company_name=company_name,
                        ticker=ticker,
                        market_name=market_info["market_name"],
                        currency_name=market_info["currency_name"],
                        currency_symbol=market_info["currency_symbol"],
                        current_date=current_date,
                        history_start_date=history_start_date,
                    )

                    messages = state["messages"] + [result] + tool_messages
                    if supplemental_context:
                        messages.append(HumanMessage(content="\n\n".join(supplemental_context)))
                    messages.append(HumanMessage(content=analysis_prompt))

                    final_result = llm.invoke(messages)
                    report = final_result.content

                    logger.info(f"[Market Analyst] Generated full analysis report, length: {len(report)}")

                    return {
                        "messages": [result] + tool_messages + [final_result],
                        "market_report": report,
                        "market_tool_call_count": tool_call_count + 1
                    }

                except Exception as e:
                    logger.error(f"[Market Analyst] Tool execution or analysis generation failed: {e}")
                    traceback.print_exc()

                    report = f"Market analyst called tools but analysis generation failed: {[call.get('name', 'unknown') for call in result.tool_calls]}"

                    return {
                        "messages": [result],
                        "market_report": report,
                        "market_tool_call_count": tool_call_count + 1
                    }

            return {
                "messages": [result],
                "market_report": report,
                "market_tool_call_count": tool_call_count + 1
            }

    return market_analyst_node
