# CLI 后端路径

适用于 API 服务没起，或本次是多标的需要真并行的情况。

## 1. 准备仓库

固定位置：

```text
仓库:   /Users/minlong_1/Desktop/Github/etf-stock-agent
remote: https://github.com/MoMeak9/etf-stock-agent.git
```

只有触发门控通过后才做这些。动手前先看目标是什么：

1. 路径不存在 → 先确认 `git` 可用，再 `git clone <remote> <路径>`。
2. 路径存在且为空 → clone 进去。
3. 路径已经是 Git worktree → 直接复用。**不要**自动 `git pull`、`git reset`、切分支或跑清理命令。
4. 路径存在、不是 Git worktree、且有文件 → 停下，不删不覆盖任何东西，让用户指定一个安全的 clone 目录。
5. 确认仓库里有 `analyze.py` 和 `pyproject.toml`；不是预期项目就停下。
6. 系统没有 `git` → 报告需要装 Git，不要用破坏性手段替代。

## 2. 准备 Python 环境

1. 先确认有可用的系统 `python3`。没有就报告需要装 Python，不要去改系统包管理器配置。
2. 优先用仓库内的 `.venv/bin/python`。
3. `.venv/bin/python` 不存在 → 在仓库目录 `python3 -m venv .venv`，不污染系统 Python。
4. 判断是首次安装还是环境坏了：`.venv/bin/python -m pip show etf-stock-agent` 失败，或 `.venv/bin/python -m pip check` 失败，就执行：

   ```bash
   cd /Users/minlong_1/Desktop/Github/etf-stock-agent
   .venv/bin/python -m pip install -e ".[cn]"
   ```

   这一步可能要几分钟，用后台执行。

5. 不创建、修改、读取或打印 `.env`。缺 API key 时，把环境准备做完然后停下，告诉用户要配哪些变量（如 `DEEPSEEK_API_KEY`、`TUSHARE_TOKEN`）。

## 3. 后台启动分析

**必须后台运行**（Bash 工具的 `run_in_background: true`）。前台跑会在 600 秒超时，而进程还在继续，agent 会误判成失败。

```bash
cd /Users/minlong_1/Desktop/Github/etf-stock-agent
.venv/bin/python analyze.py <tickers> --asset-type <type> -l <level> -w <workers> [-d YYYY-MM-DD]
```

ticker 先校验再用，必要时加引号。启动后告诉用户任务已开始、预计 7-18 分钟（多标的并行时按最慢的算，不是累加）。

用户已经明确要求分析了，不要再问一次确认。环境准备、参数校验或必要配置任何一步失败，都不要启动命令。

## 4. 轮询完成

两种判断方式，优先用第二种。

**看后台进程输出**：Rich 的进度条带 ANSI 转义，很难可靠解析。只用它判断进程是否还活着、有没有报错，**不要**从里面抠决策数值。

**读汇总 JSON**（推荐）：`main()` 跑完会写 `eval_results/_batch_summary/batch_<时间戳>.json`。这个文件出现就说明整批结束了：

```bash
sleep 210
ls -t /Users/minlong_1/Desktop/Github/etf-stock-agent/eval_results/_batch_summary/*.json 2>/dev/null | head -1
```

注意要和启动前已有的最新文件对比，确认是本次新产生的 —— 目录里有历史批次。启动前先记下当时最新的文件名。

间隔 3-4 分钟一次，别更频繁。

## 5. 读结果

汇总 JSON 是一个数组，每个元素对应一个标的：

```json
[
  {
    "ticker": "DLR",
    "date": "2026-08-14",
    "status": "success",
    "decision": {"action": "买入", "target_price": "...", "confidence": 0.75, "risk_score": 0.4, "reasoning": "..."},
    "elapsed": 690.9,
    "stats": {"llm_calls": 42, "tool_calls": 18, "tokens_in": 380000, "tokens_out": 25000},
    "report_path": "/Users/.../docs/reports/DLR_2026-08-14_report.md",
    "report_exists": true
  }
]
```

`status` 为 `error` 时读 `error` 字段，`traceback` 里有完整栈。

报告路径由 `.env` 的 `TRADINGAGENTS_REPORTS_DIR` 决定，没配就是 `tradingagents/docs/reports/`。

耗时用 CLI 输出的 `总墙钟时间`，并行分析**不要**把各标的的 `elapsed` 相加。

## 失败处理

clone、建 venv、装依赖、外部数据源任何一环失败，都停下来报真实原因，不要伪造分析结果。

常见情况：

- 盘中跑 A 股：CLI 会提示日线数据要等收盘（~16:00），并自动回退到最近交易日。把这个提示转达给用户。
- 数据源报错但仍然产出了报告：保留报告里的缺失数据警告，不要当成完整结论。
