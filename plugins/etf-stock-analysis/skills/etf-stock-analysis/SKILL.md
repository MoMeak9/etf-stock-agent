---
name: etf-stock-analysis
description: Use when the user explicitly asks to analyze, research, evaluate, or review one or more stock / A-share ETF / open-ended fund tickers, such as "分析 DLR" or "研究 510300". Do not use when the user only mentions a ticker, asks for a price or news, or names no ticker at all.
---

# ETF / 股票 / 基金研究

触发本仓库已有的多智能体研究链路（`analyze.py` 或本地 API 服务），把自然语言请求翻译成参数，异步执行，然后整理决策和报告路径。

## 关键约束：必须异步

单个标的的一次分析实测耗时 **7-18 分钟**（`eval_results/_batch_summary/` 的历史记录：432s / 645s / 693s / 784s / 806s / 868s / 924s / 955s / 962s / 1102s）。Bash 工具单次调用上限 600 秒，**前台运行几乎一定会在报告写完前超时**，而进程其实还在跑。

所以：永远不要在前台等待分析完成。用下面两条路径之一，然后轮询。

## 触发门控

动手之前先判断用户到底要什么。查价格、查新闻、问公司/基金是什么、做对比 —— 这些都是**硬性不触发**，即使外层任务说要用这个 skill 也不触发。

同时满足两条才执行：

1. 明确的分析意图：`分析`、`研究`、`评估`、`复盘`、`深度分析`、`全面分析` 或等价表达。
2. 至少一个能直接传给 CLI 的 ticker/code，例如 `DLR`、`AAPL`、`510300`、`008763`。

不触发的例子：

```text
DLR 今天涨了吗？
帮我找 DLR 的新闻
DLR 是什么公司？
比较 DLR 和 PLD
```

有分析动词但没标的 → 先问标的。中文公司名或基金简称不要自行转成代码 → 先问 ticker、市场或资产类型。

多标的只有在确认同属一种资产类型后才能一起传。可能混了股票/ETF/基金时，要求用户分批，不要静默拆分或替用户改批次。

## 参数映射

默认值：

```text
--asset-type auto -l 5 -w 3
```

| 用户表达 | 参数 |
|---|---|
| 快速扫描、闪电、粗看 | `-l 1` |
| 快速分析、简要分析 | `-l 2` |
| 标准分析、常规分析 | `-l 3` |
| 深度分析、深入研究 | `-l 4` |
| 极致、全面、最高精度、完整研究 | `-l 5` |
| `强度 N`、`级别 N`、`-l N` | 以显式数字 `N` 为准 |
| `N 个并行`、`N 线程`、`并行数 N` | `-w N` |
| 串行、单线程、不要并行 | `-w 1` |
| 截至 YYYY-MM-DD、分析日期 YYYY-MM-DD | `-d YYYY-MM-DD` |
| ETF | `--asset-type etf` |
| 开放式基金、公募基金 | `--asset-type fund` |
| 股票 | `--asset-type stock` |

显式数字优先于描述词。`-l` 必须是 1-5 的整数，`-w` 必须是正整数；不合法就先让用户改，不要启动。本版本不解析 provider、模型、后端地址、数据源和 debug —— 用户问起就说明由服务端 `.env` 决定，建议直接用仓库 CLI 的完整参数。

## 选择后端

先探测本地 API 服务：

```bash
curl -sf --max-time 3 http://127.0.0.1:8000/healthz
```

| | 服务在跑 | 服务没起 |
|---|---|---|
| 单个标的 | 走 **API 路径** | 走 **CLI 路径** |
| 多个标的且 `-w` > 1 | 走 **CLI 路径**（见下） | 走 **CLI 路径** |

多标的必须走 CLI：API 的 `run_analysis_batch` 是串行 for 循环，`workers` 字段收下了但不生效，3 个标的会串成 45 分钟；CLI 的 `-w 3` 走真正的 `ProcessPoolExecutor`。如果用户明确要求用 API 跑多标的，照做，但要提前说明这是串行的、耗时会累加。

两条路径的详细步骤见：

- API 路径 → `references/api-backend.md`
- CLI 路径 → `references/cli-backend.md`

## 整理结果

只报告 CLI 输出或结构化结果里真实存在的信息：

- 标的、资产类型、实际生效的分析日期（注意 `analyze.py` 会把日期回退到可用交易日，和用户输入的可能不同）
- 操作建议 / 基金建议
- 目标价（股票和 ETF 有，基金没有）
- 置信度、风险评分
- LLM / 工具调用统计
- 总耗时
- 每份 Markdown 报告的绝对路径

保留报告里的数据缺失提示和警告。说明这是模型基于当前可得数据生成的研究结果，不要承诺收益，也不要把缺失数据包装成确定结论。

失败就报真实的失败原因和失败的阶段。绝不编造决策或报告路径。

## 边界

- 不修改 `analyze.py` 或分析链路，CLI 和 API 是分析逻辑、日期回退、资产识别、报告落盘的唯一事实来源。
- 不创建、修改、读取或打印 `.env` 里的密钥。缺 key 就在环境准备完成后停下，告诉用户需要配哪个变量。
- 只有在触发门控通过之后，才允许 clone、建 venv、装依赖。普通聊天或只提到 ticker 一律不做这些。
