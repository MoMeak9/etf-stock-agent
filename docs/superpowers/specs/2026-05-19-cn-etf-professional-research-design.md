# 中国大陆 ETF 专业研究能力设计

- 日期：2026-05-19
- 状态：Approved for planning
- 适用范围：中国大陆场内权益类与商品类 ETF
- 目标模式：`asset_type=etf`

## 1. 背景

当前项目已经具备 A 股 ETF 分析骨架：ETF 模式、ETF analyst、ETF tool routing、LangGraph 编排、报告字段映射和 CLI 入口都已存在。但现有能力仍偏第一版框架，核心数据深度不足，尤其是 ETF 准入、产品资料、折溢价、跟踪偏离、份额规模、持仓暴露、事件数据和数据质量说明。

本设计把 ETF 能力升级为“专业研究版”。ETF 分析参考个股 Agent 的分层组织方式，但走独立资产链路，不继承个股的财报、估值、管理层等分析语义。

## 2. 目标与非目标

### 2.1 目标

1. 支持中国大陆场内宽基、行业、主题、商品 ETF 的专业研究。
2. 使用 Tushare 作为主数据源，AkShare 作为兜底数据源。
3. 在数据层生成核心派生指标，而不是只把原始 API 字段交给 LLM。
4. 每份 ETF 报告同时覆盖交易视角和配置视角。
5. 建立 ETF 独立链路：ETF Market、ETF Flow、ETF News、ETF Product、ETF Research、ETF Trader、ETF Risk。
6. 提供数据体检命令，用于验收每个 ETF 的数据源可用性、字段完整度、派生指标和降级情况。
7. 对缺失数据、权限不足、字段不可用和兜底路径做明确质量标记。

### 2.2 非目标

1. 本轮不支持 LOF、QDII、债券 ETF、货币 ETF、场外基金。
2. 本轮不做同类 ETF 横向排名或组合推荐。
3. 本轮不建立传统单元测试体系，验收方式改为数据体检命令。
4. 本轮不重写整个 LangGraph 编排框架。
5. 本轮不把 ETF 作为 stock 链路的特殊 case。

## 3. 能力边界

支持范围：

- 宽基 ETF
- 行业 ETF
- 主题 ETF
- 商品 ETF

排除范围：

- LOF
- QDII
- 债券 ETF
- 货币 ETF
- 场外基金
- 未上市或已退市基金

系统必须优先使用产品元数据判断基金是否进入支持范围。如果产品元数据不可用，可使用代码前缀做弱判断，但必须在数据体检和报告中标记“分类置信度低”。

## 4. 总体架构

本轮采用“ETF 数据研究内核 + 现有 Agent 编排复用”的架构。

复用：

- `TradingAgentsGraph`
- LangGraph 状态推进
- LLM provider 抽象
- memory 基础设施
- 报告落盘
- 进度展示

新增或重构：

- `etf_registry`：ETF 范围识别、基金类型判断、交易所和代码规范化、准入结果。
- `etf_metrics`：折溢价、跟踪偏离、份额变化、流动性、持仓集中度、波动和回撤等派生指标。
- `etf_profile_service`：产品资料、净值、份额、费率、规模、跟踪指数、基金类型。
- `etf_exposure_service`：持仓、指数权重、行业或主题暴露、权重集中度。
- `etf_market_service`：行情、成交、波动、技术指标、流动性。
- `etf_event_service`：ETF 新闻、基金公告、指数事件、行业主题事件、商品事件。
- `etf_healthcheck`：数据体检命令，输出数据能力状态和降级路径。

`akshare_etf.py` 和 `tushare_etf.py` 保留为 vendor adapter。Agent 不直接依赖 vendor 原始输出，而是通过服务层拿到研究包。

## 5. ETF 独立分析链路

ETF 链路是独立资产链路：

```text
ETF Registry / Data Services
        ↓
ETF Market Analyst
        ↓
ETF Flow Analyst
        ↓
ETF News Analyst
        ↓
ETF Product Analyst
        ↓
ETF Bull / ETF Bear Research Debate
        ↓
ETF Research Manager
        ↓
ETF Trader
        ↓
ETF Risk Debate
        ↓
ETF Risk Manager / Final Decision
```

约束：

- ETF prompt 禁止公司财报、PE/PB、管理层、收入、利润等个股语义。
- ETF 决策必须同时给出交易建议和配置建议。
- ETF 风控必须覆盖流动性、折溢价、跟踪偏离、持仓集中、主题拥挤、商品波动。
- 下游通用字段映射只是兼容层，真实 ETF 领域字段仍是 `etf_market_report`、`etf_flow_report`、`etf_news_report`、`etf_product_report`。

## 6. Tushare 主数据接口映射

本轮以 Tushare 为主源，AkShare 为兜底。Tushare 接口依据官方文档设计。

### 6.1 准入与产品资料

主接口：`pro.etf_basic(...)`

关键字段：

- `ts_code`
- `csname`
- `extname`
- `cname`
- `index_code`
- `index_name`
- `setup_date`
- `list_date`
- `list_status`
- `exchange`
- `mgr_name`
- `custod_name`
- `mgt_fee`
- `etf_type`

规则：

- `list_status != L` 时拒绝完整分析。
- `etf_type == QDII` 时拒绝本轮专业分析。
- `index_code` 和 `index_name` 用于宽基、行业、主题、商品分类。
- `mgt_fee` 纳入产品质量与配置视角。
- `exchange` 用于校验代码后缀和选择实时参考能力。

参考：Tushare ETF 基本信息文档 `https://tushare.pro/document/2?doc_id=385`。

### 6.2 行情与交易活跃度

主接口：`fund_daily`

用途：

- ETF 日线行情
- 开高低收
- 涨跌幅
- 成交量
- 成交额
- 技术指标
- 波动与回撤
- 流动性判断

### 6.3 规模、份额、净值与折溢价

主接口：

- `etf_share_size`
- `fund_nav`

用途：

- 份额变化
- 规模变化
- 单位净值
- 资金行为代理
- 折溢价计算

折溢价优先公式：

```text
(close - nav) / nav
```

如果当日 NAV 不可用，使用最近可用 `fund_nav.unit_nav` 与最近收盘价对齐，并在质量标记中说明日期错配。

### 6.4 实时参考与申赎

增强接口：`rt_etf_sz_iopv`

用途：

- 深市 ETF 实时 IOPV
- 最新价
- 成交
- 申购赎回参考

限制：

- 当前仅作为增强项。
- 若接口权限不足或不覆盖沪市 ETF，不影响完整分析，但实时折溢价标记为 unavailable。

### 6.5 指数与基准

主接口：

- `etf_index`
- `mkt_idx_bmk`
- `index_weight`

用途：

- 跟踪指数识别
- ETF 分类
- 指数成分与权重
- 持仓暴露补充
- 行业主题或宽基判断
- 集中度分析

### 6.6 持仓暴露

主接口：`fund_portfolio`

用途：

- 前十大持仓
- Top N 集中度
- 持仓暴露结构

限制：

- 持仓通常按季度更新，有滞后性。
- 报告必须标记持仓截止日期。

## 7. 数据流

ETF 模式的数据流分为四步。

### 7.1 识别与准入

输入代码后先标准化为 A 股基金代码，再查询产品元数据。只有宽基、行业、主题、商品 ETF 进入完整分析。LOF、QDII、债券、货币、场外基金返回明确不支持原因。

### 7.2 多源采集

默认先查 Tushare。Tushare 缺字段、权限不足或失败时，用 AkShare 兜底。每个数据块都记录：

- `source`
- `as_of_date`
- `freshness`
- `quality`
- `warnings`

### 7.3 派生指标计算

数据层计算并输出：

- 折溢价
- 跟踪偏离
- 近 5/20/60 日份额变化率
- 成交额、成交量、换手率、近 20 日均成交额
- 极端低流动性标记
- Top 1/3/5/10 持仓集中度
- 近 20/60 日波动率
- 最大回撤
- 趋势状态
- 数据质量评分

### 7.4 Agent 消费

ETF analyst 消费四类研究包：

- 市场包
- 产品包
- 暴露包
- 事件包

每个包都包含关键数据、派生指标、缺失字段和风险提示。

## 8. Agent 报告形态

### 8.1 ETF Market Analyst

消费市场包，输出交易结构报告：

- 趋势
- 成交活跃度
- 波动
- 技术位
- 折溢价是否影响短期交易
- 短期风险触发条件

### 8.2 ETF Product Analyst

消费产品包与暴露包，输出配置研究报告：

- 基金类型
- 跟踪指数
- 规模和份额
- 费率
- 持仓集中度
- 流动性
- 跟踪质量
- 适合配置的场景

### 8.3 ETF Flow Analyst

消费份额变化、成交热度、资金流代理和折溢价变化，输出资金行为报告：

- 份额变化
- 交易热度
- 拥挤度
- 流动性风险
- 资金行为代理说明

真实资金流不可得时，必须明确说明使用的是代理指标。

### 8.4 ETF News Analyst

消费事件包，输出事件驱动报告：

- 基金公告
- 指数调整
- 行业或主题政策
- 商品价格驱动
- 宏观扰动

新闻不足时，不得编造事件，只能降级为“事件数据不足 + 需关注方向”。

### 8.5 最终输出

最终报告必须包含：

- 交易建议：买入、持有、卖出。
- 目标价。
- 止损或失效条件。
- 交易仓位建议。
- 配置建议：适合配置、暂不配置、仅适合波段。
- 配置比例或适配场景。
- 置信度。
- 风险评分。
- 数据可信度说明。

## 9. 数据质量、错误处理与降级

每个研究包返回统一元信息：

```python
{
    "status": "ok | partial | unavailable | blocked",
    "primary_source": "tushare",
    "fallback_source": "akshare | none",
    "as_of_date": "...",
    "warnings": [...],
    "missing_fields": [...],
    "metrics": {...},
    "raw_summary": {...},
}
```

降级规则：

- Tushare 权限不足、网络失败、字段为空时，尝试 AkShare。
- AkShare 成功但字段不完整时，状态为 `partial`。
- 准入失败、行情缺失、产品基础信息缺失时，状态为 `blocked` 或 `unavailable`，不建议进入完整 Agent 分析。
- 折溢价、跟踪偏离、持仓集中度等派生指标不能计算时，不允许 LLM 猜测。

错误呈现分两层：

- 数据体检命令展示接口失败、失败原因和兜底路径。
- 分析报告只展示对投资判断有意义的缺失说明。

## 10. 数据体检命令

本轮不用传统单元测试作为硬要求，改用数据体检命令作为验收入口。

建议命令：

```bash
python analyze.py --etf-healthcheck 510300 159919 518880
```

也可以增加 CLI 子命令：

```bash
etf-stock-agent etf-healthcheck 510300 159919 518880
```

体检输出按 ETF 和能力模块分组：

- 准入检查：是否在 `etf_basic` 中存在、是否上市、是否 QDII、是否属于支持范围。
- 产品资料：基金名称、管理人、托管人、费率、跟踪指数、上市日期。
- 行情数据：`fund_daily` 是否可用，最近交易日、近 20 日成交额、收盘价。
- 份额/规模/净值：`etf_share_size` 或替代路径是否可用，能否计算份额变化和折溢价。
- 持仓暴露：`fund_portfolio` 或指数权重是否可用，能否生成 Top N 集中度。
- 跟踪质量：是否能拿到 ETF 净值或价格与基准指数序列，能否计算跟踪偏离。
- 事件数据：公告、指数、行业或商品事件是否有可用来源。
- 降级记录：哪些能力用了 AkShare 兜底，哪些能力为 partial 或 unavailable。

总评级：

- `ready`：核心数据齐全，可运行专业分析。
- `partial`：可运行，但报告必须标记缺失项。
- `blocked`：准入失败或核心数据缺失，不建议生成正式分析。

## 11. 验收标准

1. `510300`、`159919`、`518880` 等代表性 ETF 能通过数据体检，给出每个能力模块状态。
2. QDII、LOF、债券、货币或未上市基金被明确拒绝或标记为不支持。
3. ETF 分析报告不出现公司财报、PE/PB、管理层、营收利润等个股语义。
4. 报告同时输出交易建议和配置建议。
5. 折溢价、份额变化、流动性、持仓集中度、跟踪偏离等指标能计算时必须展示；不能计算时必须说明原因。
6. Tushare 失败或缺字段时尝试 AkShare 兜底，并在体检结果中记录。
7. 完整分析只在体检评级为 `ready` 或 `partial` 时建议运行。

## 12. 后续可扩展方向

后续可单独设计：

- 同类 ETF 对比与推荐。
- 债券 ETF、货币 ETF、QDII ETF 专用链路。
- 真实 API smoke test。
- 数据缓存和刷新策略。
- 报告可追溯引用表。
- 组合层面的 ETF 配置建议。
