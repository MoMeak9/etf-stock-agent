# A 股 ETF 独立资产类型设计

- 日期：2026-04-14
- 状态：Draft
- 适用范围：仅 A 股场内 ETF
- 目标模式：`asset_type=etf`

## 1. 背景

当前系统的多 Agent 编排骨架已经较稳定：

- `Analyst -> Researcher -> Research Manager -> Trader -> Risk`
- 图编排、状态推进、辩论轮次控制、风险裁决、信号抽取都可复用

但现有语义以“个股/上市公司”为中心，主要问题是：

- Analyst prompt 默认分析对象是“公司/股票”
- `fundamentals` 角色默认围绕财报、估值、管理层展开
- Researcher / Trader / Risk 消费的上游报告也继承了个股语义

仓库中已经存在 ETF 的部分底层能力：

- 数据路由层已有 ETF 分支
- A 股 ETF 已有独立 vendor 方法入口

这说明底层数据接入基础已存在，但系统尚未形成完整的 ETF 分析框架。

## 2. 已确认决策

本设计基于以下已确认约束：

- 仅支持 A 股 ETF
- ETF 作为独立资产类型，不与个股共用同一套分析语义
- 在 CLI / 配置里显式新增 `asset_type=etf`
- 保留现有多 Agent 分层结构
- 分析目标为混合型，同时支持：
  - 交易视角
  - 配置视角
- 第一版支持范围：
  - 宽基 ETF
  - 行业 / 主题 ETF
  - 商品 ETF
- 暂不支持：
  - LOF
  - QDII
  - 债券 ETF
  - 货币 ETF
  - 场外基金
- 对现有个股模式的影响应尽量最小
- 允许抽取少量公共基础层，但不重写现有个股 prompt 体系

## 3. 目标与非目标

### 3.1 目标

1. 让系统显式支持 `asset_type=etf`
2. 在不破坏个股模式的前提下，引入 ETF 独立分析框架
3. 使 ETF 报告同时服务交易型和配置型决策
4. 让 ETF 模式保留多 Agent 协作、辩论和风控裁决能力
5. 为后续扩展更多资产类型保留清晰边界

### 3.2 非目标

1. 不重构为通用插件化资产平台
2. 不在第一版支持全球 ETF、多市场 ETF
3. 不在第一版实现复杂社交媒体抓取系统
4. 不追求一次性覆盖所有基金品种

## 4. 总体方案

采用“独立 ETF 框架，复用编排骨架”的方案。

### 4.1 核心原则

- 共享图编排，不共享分析语义
- 共享流程控制，不共享资产模板
- 共享状态推进方式，不强行共享报告字段定义

### 4.2 总体结构

系统按资产类型切分为两套框架：

- `asset_type=stock`
  - 继续使用现有个股 Agent 体系
- `asset_type=etf`
  - 使用 ETF 专用 Analyst / Prompt / Tools / Report 体系

二者共享：

- LangGraph 编排骨架
- 研究辩论与风险辩论机制
- memory 机制
- 信号提取机制
- 供应商路由底座

## 5. ETF 模式下的 Agent 设计

ETF 模式仍保留四层结构，但 Agent 职责改为 ETF 语义。

### 5.1 Analyst 层

#### 5.1.1 ETF Market Analyst

职责：

- 分析 ETF 行情、成交额、换手率、波动与技术指标
- 判断当前交易结构、支撑阻力、趋势强弱
- 生成交易视角市场报告

核心关注：

- OHLCV
- MA / MACD / RSI / BOLL
- 区间涨跌幅
- 波动率
- 成交额与活跃度

#### 5.1.2 ETF Product Analyst

职责：

- 替代现有个股 `fundamentals`
- 从基金产品和指数暴露角度分析 ETF 是否适合配置
- 生成产品面 / 结构面报告

核心关注：

- 跟踪指数
- ETF 分类（宽基 / 行业 / 主题 / 商品）
- 基金规模、份额变化
- 费率
- 跟踪误差 / 跟踪偏离
- 折溢价
- 流动性
- 前十大持仓
- 行业分布
- 权重集中度

#### 5.1.3 ETF News Analyst

职责：

- 分析 ETF 本身及其跟踪标的生态的事件驱动因素
- 形成事件催化与风险事件报告

核心关注：

- 基金公告
- 指数相关政策
- 行业 / 主题催化
- 商品 ETF 对应的大宗商品事件
- 宏观事件对风格或行业的影响

#### 5.1.4 ETF Sentiment / Flow Analyst

职责：

- 分析 ETF 短期资金行为、交易热度与情绪共振
- 形成短中期资金行为报告

核心关注：

- 资金净流入 / 流出
- 份额增减
- 成交热度
- 主题拥挤度
- 替代性情绪指标

### 5.2 Researcher 层

保留：

- Bull Researcher
- Bear Researcher
- Research Manager

但辩论问题改为：

- 这个 ETF 当前是否值得交易
- 这个 ETF 当前是否值得配置
- 当前机会更偏交易还是配置
- 风险收益比是否匹配当前市场阶段

Research Manager 必须输出双轨结论：

- 交易结论
- 配置结论

### 5.3 Trader 层

Trader 在 ETF 模式下输出双轨建议：

- 交易建议
  - 买入 / 持有 / 卖出
  - 目标价
  - 止损位
  - 触发条件
- 配置建议
  - 是否适合定投 / 中期配置 / 波段参与
  - 建议仓位区间
  - 适用前提

### 5.4 Risk 层

保留：

- Aggressive
- Conservative
- Neutral
- Risk Manager

风险讨论重点改为 ETF 风险：

- 跟踪误差风险
- 折溢价风险
- 流动性风险
- 主题拥挤风险
- 行业集中风险
- 商品波动风险
- 政策扰动风险

## 6. ETF 数据内容与工具体系

第一版采用“ETF 专用工具语义”。

### 6.1 数据类型

#### 6.1.1 行情与技术

- 日线 OHLCV
- 成交额
- 换手率
- 波动率
- 技术指标

#### 6.1.2 产品属性

- 基金名称
- 基金代码
- 管理人
- 成立日期
- 跟踪指数
- ETF 类型
- 管理费 / 托管费

#### 6.1.3 产品质量与交易属性

- 基金规模
- 最新份额
- 份额变化
- 折溢价
- 跟踪误差或替代指标
- 流动性

#### 6.1.4 暴露结构

- 前十大持仓
- 行业分布
- 权重集中度
- 主题定义摘要

#### 6.1.5 资金与事件

- ETF 资金流
- 成交热度
- 相关公告
- 行业 / 商品 / 宏观相关新闻

### 6.2 工具建议

建议新增 ETF 专用工具族：

- `get_etf_price_data`
- `get_etf_indicators`
- `get_etf_profile`
- `get_etf_holdings`
- `get_etf_fund_flow`
- `get_etf_discount_premium`
- `get_etf_tracking_info`
- `get_etf_news`

如果实现上需要减少重复，可在内部路由层映射到现有 vendor，但对 Agent 暴露的工具语义应保持 ETF 化。

### 6.3 数据返回形态

建议保留双层返回：

- 面向 Agent 的格式化文本
- 面向内部逻辑和测试的结构化对象

这样能兼容现有 LangGraph tool 调用方式，同时提升测试可控性。

## 7. CLI、配置与资产类型切换

### 7.1 CLI

CLI 增加显式资产类型选择：

- `asset_type=stock`
- `asset_type=etf`

ETF 模式下可增加辅助输入：

- ETF 代码
- ETF 分类（可选自动识别）
- 分析偏好：
  - 交易优先
  - 配置优先
  - 混合型

第一版默认仍走混合型。

### 7.2 配置

在默认配置中新增：

- `asset_type`
- `etf_data_vendors`
- `etf_tool_vendors`
- `selected_etf_analysts`
- `etf_analysis_mode`

建议示例：

```python
{
    "asset_type": "etf",
    "etf_analysis_mode": "hybrid",
    "selected_etf_analysts": ["market", "product", "news", "flow"]
}
```

### 7.3 兼容性原则

- 默认值保持 `asset_type=stock`
- 不显式开启 ETF 模式时，现有行为不变

## 8. Graph 与状态设计

### 8.1 图编排

不建议新建一整套图引擎。

建议做法：

- 保留统一的 graph setup 骨架
- 根据 `asset_type` 选择不同的 agent factory map
- 根据 `asset_type` 选择不同的 tool nodes

### 8.2 Agent 状态

建议在现有状态基础上增加 ETF 资产上下文：

- `asset_type`
- `asset_profile`
- `analysis_mode`

ETF 专用报告字段建议为：

- `etf_market_report`
- `etf_product_report`
- `etf_news_report`
- `etf_flow_report`

为减少对下游辩论和交易层改动，也可以增加一层报告映射：

- ETF Market Analyst -> 映射到研究层消费的 `market_report`
- ETF Product Analyst -> 映射到 `fundamentals_report` 的语义替代位
- ETF News Analyst -> 映射到 `news_report`
- ETF Flow Analyst -> 映射到 `sentiment_report`

推荐做法：

- 状态内部保留 ETF 专用字段
- 在研究层输入组装阶段统一映射为通用消费上下文

这样既不污染个股逻辑，又避免下游模块大改。

### 8.3 初始请求

ETF 模式的初始请求不能再写成“分析公司基本面”。

应改为：

- 分析 ETF 的市场表现
- 分析 ETF 的产品结构与暴露
- 分析 ETF 的资金行为与情绪
- 分析 ETF 的相关新闻与风险
- 给出交易与配置建议

## 9. Prompt 体系设计

ETF 模式必须独立 prompt 体系。

### 9.1 Prompt 原则

- 分析对象始终是“ETF 产品”
- 禁止把 ETF 当作上市公司描述
- 同时输出交易视角和配置视角
- 对不同 ETF 类型使用不同重点

### 9.2 ETF 类型差异化提示

不同类别 ETF 的 prompt 重点不同：

- 宽基 ETF
  - 风格暴露
  - 市场 Beta
  - 长期配置价值
- 行业 / 主题 ETF
  - 行业景气度
  - 主题催化
  - 拥挤风险
- 商品 ETF
  - 商品价格驱动
  - 宏观与政策扰动
  - 波动放大特征

### 9.3 报告统一结构

每个 ETF Analyst 报告建议统一包含：

1. 分析对象
2. 核心数据摘要
3. 交易视角结论
4. 配置视角结论
5. 风险提示

Trader 最终报告建议包含：

1. 最终交易建议
2. 最终配置建议
3. 目标价与触发条件
4. 适用投资者画像
5. 风险边界

## 10. 数据路由与底层实现原则

### 10.1 路由原则

路由需要同时考虑：

- `asset_type`
- `market`
- ETF 分类

也就是说，ETF 路由不能只靠 `market == cn`。

建议形成统一资产识别：

- `asset_type=stock`
- `asset_type=etf`

并在 ETF 模式下直接使用 ETF vendor 方法，而不是依赖“先识别为 CN，再判断是否 ETF”的隐式分支。

### 10.2 公共抽象边界

允许提取的公共抽象：

- 通用 graph setup 框架
- 通用 state 初始化框架
- 通用 vendor route 接口
- 通用 report assembly 接口

不建议强行合并的内容：

- stock prompt 与 etf prompt
- stock fundamentals 与 etf product analysis
- stock company-name resolution 与 etf product-name resolution

## 11. 错误处理与降级策略

ETF 模式需要更明确的降级策略，因为部分产品数据可能缺失。

### 11.1 数据降级

当缺少以下数据时的处理建议：

- 缺少持仓结构
  - 退化为指数属性 + 历史表现分析
- 缺少跟踪误差
  - 以折溢价、规模、流动性做替代判断
- 缺少资金流
  - 退化为成交热度与份额变化

### 11.2 Prompt 降级

prompt 必须允许模型在数据不足时：

- 明确说明缺失项
- 不伪造公司类结论
- 仍输出保守建议

### 11.3 决策降级

当 ETF 产品数据关键字段缺失时：

- Trader 可以输出保守配置建议
- Risk Manager 倾向于持有 / 观望，而不是激进买入

## 12. 对现有个股模式的影响控制

必须遵守以下隔离原则：

1. `asset_type=stock` 默认行为不变
2. 现有 stock prompt 不因 ETF 接入而重写
3. stock tool 路由逻辑只做必要抽象，不做语义混合
4. 新增 ETF 文件优先，不在 stock 模块中堆叠大量条件分支

## 13. 测试策略

### 13.1 单元测试

需要覆盖：

- CLI / config 的 `asset_type=etf`
- ETF 代码识别
- ETF vendor 路由
- ETF tool formatter
- ETF prompt 关键语义

### 13.2 集成测试

覆盖典型 ETF：

- 宽基 ETF
- 行业 / 主题 ETF
- 商品 ETF

验证：

- Analyst 报告生成成功
- Researcher 辩论能消费 ETF 报告
- Trader 能输出双轨建议
- Risk Manager 能完成最终裁决

### 13.3 回归测试

必须验证：

- 现有个股模式无行为回归
- `asset_type=stock` 输出与之前一致或仅有无害差异

## 14. 分阶段实施建议

### Phase 1：资产入口与骨架切换

- CLI 增加 `asset_type=etf`
- 配置增加 ETF 模式字段
- graph setup 支持按资产类型切换 agent map / tool map

### Phase 2：ETF 数据能力层

- 补齐 ETF 工具接口
- 补齐产品属性、资金流、持仓、折溢价等 formatter
- 完成 ETF 数据路由

### Phase 3：ETF Analyst 层

- ETF Market Analyst
- ETF Product Analyst
- ETF News Analyst
- ETF Flow Analyst

### Phase 4：ETF 下游协作层

- Researcher prompt ETF 化
- Trader 双轨建议输出
- Risk prompt ETF 化
- SignalProcessor 兼容 ETF 决策文本

### Phase 5：验证与打磨

- 集成测试
- 回归测试
- 报告结构统一
- Prompt 调优

## 15. 风险与权衡

### 15.1 主要风险

- ETF 数据源完整性不稳定
- 主题 ETF 的“新闻相关性”判定较难
- Product Analyst 容易退化为数据罗列
- 交易与配置双轨建议可能互相冲突

### 15.2 对应策略

- 第一版先做最小充分数据集
- Prompt 明确区分交易结论与配置结论
- 通过 Research Manager 统一输出混合型裁决
- 用 Risk 层兜底处理冲突建议

## 16. 推荐结论

推荐按以下方向实施：

- 新增显式 `asset_type=etf`
- ETF 作为独立资产类型
- 保留现有多 Agent 分层骨架
- 新增 ETF 专用 Analyst / Prompt / Tool / Report 体系
- 对个股模式保持最小影响

这是当前约束下风险最低、语义最清晰、也最利于后续扩展的方案。

## 17. 后续动作

在本设计确认后，下一步应进入实现计划阶段，拆解为：

1. 资产入口与配置改造
2. ETF 数据工具与路由
3. ETF Analyst 实现
4. ETF 下游 prompt 适配
5. 测试与回归
