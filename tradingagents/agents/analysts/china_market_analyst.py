"""
中国市场分析师 - A股/港股专属分析师

专门分析中国A股、港股等中国资本市场的独特特征，
包括涨跌停制度、T+1交易、板块轮动、政策影响等。
"""

import logging

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.market_router import get_company_name, get_market_info
from tradingagents.agents.utils.core_stock_tools import get_stock_data
from tradingagents.agents.utils.technical_indicators_tools import get_indicators
from tradingagents.agents.utils.fundamental_data_tools import get_fundamentals

logger = logging.getLogger(__name__)


def create_china_market_analyst(llm, toolkit=None):
    """创建中国市场分析师节点。

    Args:
        llm: 语言模型实例
        toolkit: 可选的 market_router 实例（未使用，保持接口一致）
    """

    def china_market_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]

        # 获取市场信息和公司名称
        market_info = get_market_info(ticker)
        company_name = get_company_name(ticker, market_info["market"])

        # 使用标准工具文件的工具（自动路由到正确数据源）
        tools = [get_stock_data, get_indicators, get_fundamentals]

        system_message = f"""您是一位专业的中国股市分析师，专门分析A股、港股等中国资本市场。您具备深厚的中国股市知识和丰富的本土投资经验。

📋 **分析对象：**
- 公司名称：{company_name}
- 股票代码：{ticker}
- 所属市场：{market_info['market_name']}
- 计价货币：{market_info['currency']}（{market_info['currency_symbol']}）
- 当前日期：{current_date}

您的专业领域包括：
1. **A股市场分析**: 深度理解A股的独特性，包括涨跌停制度、T+1交易、融资融券等
2. **中国经济政策**: 熟悉货币政策、财政政策对股市的影响机制
3. **行业板块轮动**: 掌握中国特色的板块轮动规律和热点切换
4. **监管环境**: 了解证监会政策、退市制度、注册制等监管变化
5. **市场情绪**: 理解中国投资者的行为特征和情绪波动

中国股市特色考虑：
- 主板涨跌停板限制（±10%），创业板（±20%），ST股票（±5%）
- T+1 交易制度（当日买入次日才能卖出）
- 科创板、创业板的差异化分析
- 北向资金流向（沪股通/深股通）
- 国企改革、混改等主题投资机会

🔴 严格要求：
1. 必须调用工具获取真实数据，不允许假设或编造
2. 所有价格使用 {market_info['currency_symbol']} 标注
3. 报告全部使用中文撰写
4. 在报告末尾附上关键发现和投资建议的Markdown表格

请基于获取的实时数据和技术指标，结合中国股市的特殊性，撰写专业的分析报告。"""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_message),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""
        if not result.tool_calls:
            report = result.content

        # 更新工具调用计数
        tool_count = state.get("china_market_tool_call_count", 0)
        if result.tool_calls:
            tool_count += 1

        return {
            "messages": [result],
            "china_market_report": report,
            "china_market_tool_call_count": tool_count,
            "sender": "ChinaMarketAnalyst",
        }

    return china_market_analyst_node
