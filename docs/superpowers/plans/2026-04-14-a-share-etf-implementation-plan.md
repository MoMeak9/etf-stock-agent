# A 股 ETF 支持实现计划

> **面向 Agent 执行者：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步实现本计划。所有步骤使用复选框（`- [ ]`）语法跟踪。

**目标：** 显式增加 `asset_type=etf`，支持 A 股场内 ETF 的独立分析框架，同时保留现有多 Agent 编排骨架，并确保默认个股模式行为不变。

**架构：** 保留一套共享的 LangGraph 执行骨架，但根据 `asset_type` 切换 agent 工厂、提示词、数据工具、状态初始化和报告语义。ETF 模式使用 ETF 专用分析师和 ETF 专用产品/资金流/新闻语义；下游研究、交易、风控层在不破坏 stock 模式的前提下适配 ETF 报告内容。

**技术栈：** Python、Typer CLI、LangGraph、LangChain tool calling、pandas、akshare、tushare、pytest

**明确决策：** ETF 模式内部使用 ETF 专用报告字段（`etf_market_report`、`etf_product_report`、`etf_news_report`、`etf_flow_report`），并通过必选映射层回填到现有通用下游字段（`market_report`、`fundamentals_report`、`news_report`、`sentiment_report`）。下游 Agent 和报告生成优先继续读取这些通用字段，只是字段内容改为 ETF 语义，从而避免同时维护两套读取逻辑，并把 stock 模式回归风险降到最低。

---

## 文件结构

### 需要修改的现有文件

- `cli/models.py`
  增加 CLI 使用的资产类型枚举与配置模型。
- `cli/main.py`
  采集 `asset_type=etf`，按 ETF 模式切换 analyst 选择与报告展示标签，并将 ETF 配置传入 `TradingAgentsGraph`。
- `tradingagents/default_config.py`
  增加 ETF 默认配置与 vendor 配置，同时不改变 stock 默认值。
- `tradingagents/dataflows/config.py`
  在线程上下文中同时保存资产类型与市场上下文。
- `tradingagents/dataflows/interface.py`
  依据显式 `asset_type=etf` 路由 ETF 工具方法，而不是只靠代码规则猜测。
- `tradingagents/dataflows/market_utils.py`
  保持 stock 兼容，同时暴露 ETF 感知的元数据辅助函数。
- `tradingagents/agents/__init__.py`
  导出 ETF agent 工厂。
- `tradingagents/agents/utils/agent_states.py`
  增加 ETF 资产上下文与 ETF 报告字段。
- `tradingagents/graph/trading_graph.py`
  初始化 ETF tool nodes、ETF 上下文、ETF 报告生成与状态日志。
- `tradingagents/graph/setup.py`
  根据 `asset_type` 选择 stock 或 ETF 的 agent 工厂与节点。
- `tradingagents/graph/propagation.py`
  构造 ETF 专用初始请求与状态默认值。
- `tradingagents/graph/conditional_logic.py`
  增加 ETF analyst 的继续执行判断。
- `tradingagents/graph/signal_processing.py`
  提取 ETF trader 输出中的交易建议与配置建议。
- `tradingagents/agents/researchers/bull_researcher.py`
  消费 ETF 报告上下文，不再假设公司/财报语义。
- `tradingagents/agents/researchers/bear_researcher.py`
  同上，适配看空 ETF 研究语义。
- `tradingagents/agents/managers/research_manager.py`
  输出 ETF 双轨结论：交易结论 + 配置结论。
- `tradingagents/agents/trader/trader.py`
  输出 ETF 交易触发条件、目标价、止损与配置建议。
- `tradingagents/agents/risk_mgmt/aggressive_debator.py`
  讨论 ETF 视角下的上行机会与风险承受。
- `tradingagents/agents/risk_mgmt/conservative_debator.py`
  讨论 ETF 视角下的防守与下行风险。
- `tradingagents/agents/risk_mgmt/neutral_debator.py`
  讨论 ETF 视角下的平衡风险收益。
- `tradingagents/agents/managers/risk_manager.py`
  形成 ETF 最终风控裁决。

### 需要接入或补完的现有 ETF 数据文件

- `tradingagents/dataflows/akshare_etf.py`
  规范输出，补齐 ETF 产品/资金流/持仓/折溢价等辅助能力，供 ETF agents 使用。
- `tradingagents/dataflows/tushare_etf.py`
  同上，作为主数据源路径。

### 需要新增的文件

- `tradingagents/agents/utils/etf_data_tools.py`
  ETF 专用 LangChain tool 包装层。
- `tradingagents/agents/utils/etf_prompt_utils.py`
  ETF 共用提示词、报告段落与 ETF 类型后缀。
- `tradingagents/agents/analysts/etf_market_analyst.py`
  ETF 行情/技术分析师。
- `tradingagents/agents/analysts/etf_product_analyst.py`
  ETF 产品/结构/配置分析师。
- `tradingagents/agents/analysts/etf_news_analyst.py`
  ETF 新闻/事件分析师。
- `tradingagents/agents/analysts/etf_flow_analyst.py`
  ETF 资金流/情绪分析师。
- `test_etf_config.py`
  配置与资产上下文测试。
- `test_etf_dataflows.py`
  ETF 工具路由与格式化测试。
- `test_etf_analysts.py`
  ETF analyst 纯函数与提示词生成测试。
- `test_etf_graph.py`
  ETF 图编排、状态、映射层与集成测试。

## 任务 1：增加资产类型入口

**文件：**
- 修改：`cli/models.py`
- 修改：`cli/main.py`
- 修改：`tradingagents/default_config.py`
- 修改：`tradingagents/dataflows/config.py`
- 测试：`test_etf_config.py`

- [ ] **步骤 1：先写失败测试**

创建 `test_etf_config.py`，覆盖以下场景：
- 默认配置保持 `asset_type == "stock"`
- ETF 配置接受 `asset_type == "etf"`
- 资产上下文 setter/getter 不会覆盖现有 market context

- [ ] **步骤 2：运行测试并确认失败**

运行：`python -m pytest test_etf_config.py -q`

预期：FAIL，因为当前还没有 `asset_type` 默认值和资产上下文 API。

- [ ] **步骤 3：实现最小资产类型入口**

实现：
- 在 `cli/models.py` 中增加 `AssetType` 枚举
- 在 `cli/main.py` 中显式采集并传递 `asset_type`
- 在 `tradingagents/default_config.py` 中增加：
  - `asset_type`
  - `etf_analysis_mode`
  - `selected_etf_analysts`
  - `etf_data_vendors`
  - `etf_tool_vendors`
- 在 `tradingagents/dataflows/config.py` 中增加线程局部：
  - `set_asset_context()`
  - `get_asset_context()`
- 增加第一版 ETF 合法性校验挂钩，供后续拦截明显非 ETF / 非 A 股场内基金

- [ ] **步骤 4：再次运行测试并确认通过**

运行：`python -m pytest test_etf_config.py -q`

预期：PASS

- [ ] **步骤 5：提交**

```bash
git add test_etf_config.py cli/models.py cli/main.py tradingagents/default_config.py tradingagents/dataflows/config.py
git commit -m "feat: add ETF asset-type entry points"
```

## 任务 2：让数据路由显式感知 ETF

**文件：**
- 修改：`tradingagents/dataflows/interface.py`
- 修改：`tradingagents/dataflows/market_utils.py`
- 测试：`test_etf_dataflows.py`

- [ ] **步骤 1：先写失败测试**

创建 `test_etf_dataflows.py`，覆盖以下场景：
- 显式 `asset_type=etf` 时，即使 market 为 `cn`，也会路由到 ETF 方法
- stock 模式下原有 stock 路由保持不变
- ETF 元数据辅助函数返回：
  - `is_etf=True`
  - `market="cn"`
  - 正确标准化显示值

- [ ] **步骤 2：运行测试并确认失败**

运行：`python -m pytest test_etf_dataflows.py -q`

预期：FAIL，因为当前仍主要依赖代码规则判断，而不是显式资产类型。

- [ ] **步骤 3：实现 ETF 感知路由**

实现：
- 在 `tradingagents/dataflows/interface.py` 中增加基于 `asset_type` 的检测辅助逻辑
- 在 ETF 模式下优先走 ETF vendor 方法
- 在 `tradingagents/dataflows/market_utils.py` 中增加 ETF 元数据辅助函数，同时不改变 stock 默认行为
- 增加明确的 ETF 模式守卫，规则至少包括：
  - 必须是 `cn` 市场
  - 代码前缀符合 A 股 ETF 规则
  - 当 profile 元数据可用时，若基金类型属于 LOF/QDII/债券/货币/场外，则给出清晰拒绝或 warning

- [ ] **步骤 4：再次运行测试并确认通过**

运行：`python -m pytest test_etf_dataflows.py -q`

预期：PASS

- [ ] **步骤 5：提交**

```bash
git add test_etf_dataflows.py tradingagents/dataflows/interface.py tradingagents/dataflows/market_utils.py
git commit -m "feat: add explicit ETF routing"
```

## 任务 3：暴露 ETF Agent 工具面

**文件：**
- 新建：`tradingagents/agents/utils/etf_data_tools.py`
- 修改：`tradingagents/dataflows/akshare_etf.py`
- 修改：`tradingagents/dataflows/tushare_etf.py`
- 测试：`test_etf_dataflows.py`

- [ ] **步骤 1：先写失败测试**

扩展 `test_etf_dataflows.py`，覆盖：
- `get_etf_price_data()`
- `get_etf_indicators()`
- `get_etf_profile()`
- `get_etf_holdings()`
- `get_etf_fund_flow()`
- `get_etf_discount_premium()`
- `get_etf_tracking_info()`
- `get_etf_news()` 在 vendor 数据稀疏时仍能返回可用格式化文本

- [ ] **步骤 2：运行测试并确认失败**

运行：`python -m pytest test_etf_dataflows.py -q`

预期：FAIL，因为 ETF tool 包装和格式化接口尚不存在或未补齐。

- [ ] **步骤 3：实现 ETF tools 与格式化补全**

实现：
- 在 `tradingagents/agents/utils/etf_data_tools.py` 中增加 LangChain tools
- 在 `akshare_etf.py` / `tushare_etf.py` 中补齐 ETF agent 需要的格式化输出，使其可请求：
  - 行情数据
  - 技术指标
  - 产品信息
  - 持仓 / 暴露结构
  - 份额 / 资金流 / 热度
  - 折溢价信息 `get_etf_discount_premium()`
  - 跟踪 / 跟踪误差信息 `get_etf_tracking_info()`
  - ETF 相关新闻

- [ ] **步骤 4：再次运行测试并确认通过**

运行：`python -m pytest test_etf_dataflows.py -q`

预期：PASS

- [ ] **步骤 5：提交**

```bash
git add test_etf_dataflows.py tradingagents/agents/utils/etf_data_tools.py tradingagents/dataflows/akshare_etf.py tradingagents/dataflows/tushare_etf.py
git commit -m "feat: add ETF agent data tools"
```

## 任务 4：增加 ETF Analyst 层

**文件：**
- 新建：`tradingagents/agents/utils/etf_prompt_utils.py`
- 新建：`tradingagents/agents/analysts/etf_market_analyst.py`
- 新建：`tradingagents/agents/analysts/etf_product_analyst.py`
- 新建：`tradingagents/agents/analysts/etf_news_analyst.py`
- 新建：`tradingagents/agents/analysts/etf_flow_analyst.py`
- 修改：`tradingagents/agents/__init__.py`
- 测试：`test_etf_analysts.py`

- [ ] **步骤 1：先写失败测试**

创建 `test_etf_analysts.py`，采用当前仓库已有的 helper-test 风格，只测试确定性纯函数，不依赖真实 LLM 行为。至少覆盖：
- ETF market 辅助函数会补齐 ETF 行情 + 技术指标工具调用
- ETF product prompt builder 明确引用：
  - 基金 profile
  - holdings
  - discount/premium
  - tracking info
  且绝不出现公司财报语义
- ETF news prompt builder 聚焦 ETF / 指数 / 产品事件
- ETF flow prompt builder 聚焦资金流、份额变化、拥挤度

- [ ] **步骤 2：运行测试并确认失败**

运行：`python -m pytest test_etf_analysts.py -q`

预期：FAIL，因为 ETF analyst 模块和纯函数还不存在。

- [ ] **步骤 3：实现 ETF analysts**

实现 ETF analysts，要求：
- 每份报告都同时包含交易视角和配置视角
- 不出现“公司管理层 / PE / PB / PEG”语义
- 对宽基 / 行业主题 / 商品 ETF 使用不同 ETF 类型提示后缀

在 `tradingagents/agents/utils/etf_prompt_utils.py` 中抽取：
- ETF 报告标题
- ETF 风险语言
- ETF 类型专用 prompt 后缀
- 用于测试的确定性 prompt builder 和工具调用规划函数

- [ ] **步骤 4：再次运行测试并确认通过**

运行：`python -m pytest test_etf_analysts.py -q`

预期：PASS

- [ ] **步骤 5：提交**

```bash
git add test_etf_analysts.py tradingagents/agents/utils/etf_prompt_utils.py tradingagents/agents/analysts/etf_market_analyst.py tradingagents/agents/analysts/etf_product_analyst.py tradingagents/agents/analysts/etf_news_analyst.py tradingagents/agents/analysts/etf_flow_analyst.py tradingagents/agents/__init__.py
git commit -m "feat: add ETF analyst framework"
```

## 任务 5：集成 ETF 图编排、状态与映射层

**文件：**
- 修改：`tradingagents/agents/utils/agent_states.py`
- 修改：`tradingagents/graph/trading_graph.py`
- 修改：`tradingagents/graph/setup.py`
- 修改：`tradingagents/graph/propagation.py`
- 修改：`tradingagents/graph/conditional_logic.py`
- 测试：`test_etf_graph.py`

- [ ] **步骤 1：先写失败测试**

创建 `test_etf_graph.py`，覆盖：
- ETF 模式构建的是 ETF analyst 节点，而不是 stock analyst 节点
- 初始状态包含：
  - `asset_type=etf`
  - ETF 报告占位字段
- ETF 图可以在选定 ETF analysts 下成功 compile
- ETF 模式下，ETF 专用字段会通过映射层回填到通用下游字段
- stock 图仍可无变化 compile
- 非 A 股 ETF 或超出范围基金类型在 ETF 模式下会被明确拒绝或 warning

- [ ] **步骤 2：运行测试并确认失败**

运行：`python -m pytest test_etf_graph.py -q`

预期：FAIL，因为当前 graph/state 仍是 stock-only。

- [ ] **步骤 3：实现 ETF 图编排集成**

实现：
- 在 `agent_states.py` 中增加 ETF 报告字段与上下文字段
- 在状态构造层或图状态装配层实现 ETF -> 通用字段的映射辅助函数
- 在 `propagation.py` 中使用 ETF 专用初始请求
- 在 `trading_graph.py` 中增加 ETF tool nodes
- 在 `setup.py` 中按 `asset_type` 切换 ETF 工厂
- 在 `conditional_logic.py` 中增加 ETF analyst continuation 规则
- 在 CLI / graph 入口加轻量 ETF runtime guard，遇到非 A 股场内 ETF 尽早失败

- [ ] **步骤 4：再次运行测试并确认通过**

运行：`python -m pytest test_etf_graph.py -q`

预期：PASS

- [ ] **步骤 5：提交**

```bash
git add test_etf_graph.py tradingagents/agents/utils/agent_states.py tradingagents/graph/trading_graph.py tradingagents/graph/setup.py tradingagents/graph/propagation.py tradingagents/graph/conditional_logic.py
git commit -m "feat: integrate ETF asset graph"
```

## 任务 6：适配研究、交易、风控和信号提取的 ETF 语义

**文件：**
- 修改：`tradingagents/agents/researchers/bull_researcher.py`
- 修改：`tradingagents/agents/researchers/bear_researcher.py`
- 修改：`tradingagents/agents/managers/research_manager.py`
- 修改：`tradingagents/agents/trader/trader.py`
- 修改：`tradingagents/agents/risk_mgmt/aggressive_debator.py`
- 修改：`tradingagents/agents/risk_mgmt/conservative_debator.py`
- 修改：`tradingagents/agents/risk_mgmt/neutral_debator.py`
- 修改：`tradingagents/agents/managers/risk_manager.py`
- 修改：`tradingagents/graph/signal_processing.py`
- 测试：`test_etf_graph.py`

- [ ] **步骤 1：先写失败测试**

扩展 `test_etf_graph.py`，用 mocked ETF 报告验证：
- researchers 讨论 ETF 的交易价值 / 配置价值，而不是公司基本面
- research manager 同时输出交易结论和配置结论
- trader 输出包含：
  - 触发条件
  - 目标价
  - 止损
  - 配置适用性
- risk manager 可以基于 ETF 风险完成最终裁决
- signal processor 能从 ETF trader 文本中提取结构化结果

- [ ] **步骤 2：运行测试并确认失败**

运行：`python -m pytest test_etf_graph.py -q`

预期：FAIL，因为当前下游 prompt 仍然默认公司/股票语义。

- [ ] **步骤 3：实现 ETF 下游 prompt 适配**

实现：
- debate prompts 改成 ETF 语义，但仍优先读取映射回来的通用报告字段
- research manager 和 trader 输出双轨结果
- risk analysts / risk manager 使用 ETF 风险因子
- signal extraction 兼容 ETF 决策文本，同时保持 stock 兼容性

- [ ] **步骤 4：再次运行测试并确认通过**

运行：`python -m pytest test_etf_graph.py -q`

预期：PASS

- [ ] **步骤 5：提交**

```bash
git add test_etf_graph.py tradingagents/agents/researchers/bull_researcher.py tradingagents/agents/researchers/bear_researcher.py tradingagents/agents/managers/research_manager.py tradingagents/agents/trader/trader.py tradingagents/agents/risk_mgmt/aggressive_debator.py tradingagents/agents/risk_mgmt/conservative_debator.py tradingagents/agents/risk_mgmt/neutral_debator.py tradingagents/agents/managers/risk_manager.py tradingagents/graph/signal_processing.py
git commit -m "feat: adapt downstream agents for ETF decisions"
```

## 任务 7：收尾 CLI 标签、报告输出与回归覆盖

**文件：**
- 修改：`cli/main.py`
- 修改：`tradingagents/graph/trading_graph.py`
- 修改：`tradingagents/docs/SPEC.md`
- 测试：`test_etf_config.py`
- 测试：`test_etf_graph.py`
- 测试：`test_market_analyst.py`
- 测试：`test_fundamentals_analyst.py`

- [ ] **步骤 1：先写失败测试**

增加或扩展测试，验证：
- ETF 模式下 CLI 报告区块标签改为 ETF 语义
- 保存到磁盘的报告结构在 ETF 模式下使用 ETF analyst 名称
- 现有 stock analyst 测试依旧通过

- [ ] **步骤 2：运行测试并确认失败**

运行：`python -m pytest test_etf_config.py test_etf_graph.py test_market_analyst.py test_fundamentals_analyst.py -q`

预期：在 ETF 标签/报告输出改造前 FAIL。

- [ ] **步骤 3：实现 CLI / 报告 / 文档收尾**

实现：
- 在 `cli/main.py` 中增加 ETF 专用 analyst 标签与报告标题
- 在 `tradingagents/graph/trading_graph.py` 中修改：
  - ETF 模式 markdown 报告标题
  - ETF 模式 section 生成
  - ETF 模式 `_log_state` 输出内容
- 在 `tradingagents/docs/SPEC.md` 中补充 `asset_type=etf` 模式与 ETF agent 角色说明
- 确保 stock 模式标签与报告保持不变

- [ ] **步骤 4：运行聚焦回归套件**

运行：`python -m pytest test_etf_config.py test_etf_dataflows.py test_etf_analysts.py test_etf_graph.py test_market_analyst.py test_fundamentals_analyst.py -q`

预期：PASS

- [ ] **步骤 5：提交**

```bash
git add cli/main.py tradingagents/graph/trading_graph.py tradingagents/docs/SPEC.md test_etf_config.py test_etf_dataflows.py test_etf_analysts.py test_etf_graph.py test_market_analyst.py test_fundamentals_analyst.py
git commit -m "feat: finalize ETF CLI and regression coverage"
```

## 最终验证

- [ ] 运行完整实现测试集

```bash
python -m pytest \
  test_etf_config.py \
  test_etf_dataflows.py \
  test_etf_analysts.py \
  test_etf_graph.py \
  test_market_analyst.py \
  test_fundamentals_analyst.py \
  test_report_generation.py \
  -q
```

预期：
- ETF 专用测试全部通过
- stock 回归测试继续通过

- [ ] 分别做一遍 ETF 模式和 stock 模式的手动 CLI smoke test

ETF smoke test 检查项：
- 选择 `asset_type=etf`
- 输入一个 A 股场内 ETF 代码
- 确认使用的是 ETF analysts
- 确认 trader 输出同时包含交易建议和配置建议

Stock smoke test 检查项：
- 选择 `asset_type=stock`
- 输入一个普通股票代码
- 确认仍显示旧的 analyst 标签和报告结构

- [ ] 只在确实还有未提交改动时再做最后一次提交

```bash
git status --short
# 只有当这里仍有未提交修改时再执行：
git add cli/main.py cli/models.py tradingagents/default_config.py tradingagents/dataflows/config.py tradingagents/dataflows/interface.py tradingagents/dataflows/market_utils.py tradingagents/dataflows/akshare_etf.py tradingagents/dataflows/tushare_etf.py tradingagents/agents/__init__.py tradingagents/agents/utils/agent_states.py tradingagents/agents/utils/etf_data_tools.py tradingagents/agents/utils/etf_prompt_utils.py tradingagents/agents/analysts/etf_market_analyst.py tradingagents/agents/analysts/etf_product_analyst.py tradingagents/agents/analysts/etf_news_analyst.py tradingagents/agents/analysts/etf_flow_analyst.py tradingagents/graph/trading_graph.py tradingagents/graph/setup.py tradingagents/graph/propagation.py tradingagents/graph/conditional_logic.py tradingagents/graph/signal_processing.py tradingagents/agents/researchers/bull_researcher.py tradingagents/agents/researchers/bear_researcher.py tradingagents/agents/managers/research_manager.py tradingagents/agents/trader/trader.py tradingagents/agents/risk_mgmt/aggressive_debator.py tradingagents/agents/risk_mgmt/conservative_debator.py tradingagents/agents/risk_mgmt/neutral_debator.py tradingagents/agents/managers/risk_manager.py tradingagents/docs/SPEC.md test_etf_config.py test_etf_dataflows.py test_etf_analysts.py test_etf_graph.py
git commit -m "feat: add A-share ETF asset type support"
```
