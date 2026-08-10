# ETF/股票自然语言分析 Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建一个可被 Codex 自动发现的个人 Skill，在用户明确请求分析/研究标的时解析自然语言参数，准备仓库环境并运行现有 `analyze.py`。

**Architecture:** Skill 只负责触发判断、参数映射、仓库/虚拟环境自愈、CLI 启动和结果整理；实际分析继续由 `/Users/minlong_1/Desktop/Github/etf-stock-agent/analyze.py` 完成。Skill 安装在 `/Users/minlong_1/.agents/skills/etf-stock-analysis`，不修改仓库业务代码或 `.env`。

**Tech Stack:** Codex Skill (`SKILL.md`)、`agents/openai.yaml`、Skill Creator 的 `init_skill.py`/`quick_validate.py`、Git、Python 3、项目 `pip install -e ".[cn]"`。

---

## 文件结构

- Create: `/Users/minlong_1/.agents/skills/etf-stock-analysis/SKILL.md` — 触发规则、自然语言参数映射、环境自愈、CLI 执行和结果整理。
- Create: `/Users/minlong_1/.agents/skills/etf-stock-analysis/agents/openai.yaml` — Skill 列表中的展示名、简介和默认提示词。
- Create: `docs/superpowers/plans/2026-08-10-etf-stock-analysis-skill-implementation-plan.md` — 本实现计划。
- Modify: 无仓库业务代码；不修改 `.env` 或依赖文件。

## Task 1: 初始化个人 Skill 目录

- [ ] **Step 1: 确认目标目录不存在或仅包含本次 Skill 文件**

Run:

```bash
test ! -e /Users/minlong_1/.agents/skills/etf-stock-analysis || find /Users/minlong_1/.agents/skills/etf-stock-analysis -maxdepth 2 -type f -print
```

Expected: 目录不存在，或只显示本 Skill 的已有文件；不删除其他用户文件。

- [ ] **Step 2: 使用 Skill Creator 初始化目录和元数据模板**

Run:

```bash
python3 /Users/minlong_1/.codex/skills/.system/skill-creator/scripts/init_skill.py \
  etf-stock-analysis \
  --path /Users/minlong_1/.agents/skills \
  --interface display_name="ETF/股票分析" \
  --interface short_description="明确请求时自动运行股票、ETF或基金研究" \
  --interface default_prompt="分析一个股票、ETF或开放式基金，自动准备仓库环境、运行 analyze.py 并整理研究结论。"
```

Expected: 创建 `SKILL.md` 和 `agents/openai.yaml` 模板。

## Task 2: 先建立 Skill 行为压力场景

- [ ] **Step 1: 固定触发与不触发场景**

验证样例：

```text
触发：分析 DLR
触发：快速分析 DLR，单线程
触发：深度研究 ETF 510300，3 个并行
触发：分析 008763，截至 2026-08-07
不触发：DLR 今天涨了吗
不触发：帮我找 DLR 的新闻
需询问：只说“分析”但没有标的
```

- [ ] **Step 2: 固定环境自愈约束**

要求 Skill 能指导后续 Agent：目标目录不存在时 clone canonical remote；缺少 `.venv` 时创建并安装 `pip install -e ".[cn]"`；已有非空非 Git 目录不覆盖；不自动 pull/reset；不创建或输出 `.env`。

## Task 3: 编写最小可执行 Skill 指令

- [ ] **Step 1: 写入 frontmatter 和触发描述**

使用小写连字符名称 `etf-stock-analysis`。`description` 必须以 `Use when` 开头，并明确只在用户提出“分析/研究/评估/复盘 + 标的”时使用，避免仅提到 ticker 时触发。

- [ ] **Step 2: 写入请求解析规则**

覆盖：标的必须是可直接传给 CLI 的 ticker/code；默认 `-l 5 -w 3`；强度 1-5 映射；并行数正整数；日期 `YYYY-MM-DD`；ETF/基金/股票资产类型；明确数字参数优先；缺标的、中文名称无法解析或混合资产时先询问。

- [ ] **Step 3: 写入环境准备规则**

固定工作目录 `/Users/minlong_1/Desktop/Github/etf-stock-agent` 和 remote `https://github.com/MoMeak9/etf-stock-agent.git`。按顺序指导检查 Git worktree、clone、`analyze.py`/`pyproject.toml`、`.venv/bin/python`、`python3 -m venv .venv`、`pip check` 和 `pip install -e ".[cn]"`。禁止覆盖非空目录、自动 pull/reset、读取/输出密钥。

- [ ] **Step 4: 写入执行和结果整理规则**

使用 `.venv/bin/python analyze.py ...`，保留 Rich 进度；只在明确请求后执行环境变更；失败时返回真实错误。完成后整理标的、实际日期、资产类型、建议、置信度、风险、调用统计、CLI 墙钟耗时和 Markdown 报告绝对路径。

## Task 4: 生成和校验 Skill 元数据

- [ ] **Step 1: 根据最终 `SKILL.md` 重新生成 `agents/openai.yaml`**

Run:

```bash
python3 /Users/minlong_1/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py \
  /Users/minlong_1/.agents/skills/etf-stock-analysis \
  --interface display_name="ETF/股票分析" \
  --interface short_description="明确请求时自动运行股票、ETF或基金研究" \
  --interface default_prompt="分析一个股票、ETF或开放式基金，自动准备仓库环境、运行 analyze.py 并整理研究结论。"
```

- [ ] **Step 2: 运行 Skill Creator 基础校验**

Run:

```bash
python3 /Users/minlong_1/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  /Users/minlong_1/.agents/skills/etf-stock-analysis
```

Expected: 校验成功，无 frontmatter、命名或元数据错误。

- [ ] **Step 3: 运行静态完整性检查**

Run:

```bash
rg -n "TODO|TBD|placeholder|待定" /Users/minlong_1/.agents/skills/etf-stock-analysis || true
wc -l /Users/minlong_1/.agents/skills/etf-stock-analysis/SKILL.md
```

Expected: 没有占位符；`SKILL.md` 小于 500 行。

## Task 5: 安全 forward-test 和收尾

- [ ] **Step 1: 用独立代理验证触发场景**

给新代理最小上下文：Skill 路径和单条自然语言请求；要求只输出是否触发及计划命令，不执行网络、clone、pip 或 `analyze.py`。覆盖至少一个明确触发请求和一个非触发请求。

- [ ] **Step 2: 对照设计逐项检查**

逐项确认：明确请求才触发、默认参数正确、环境自愈安全、参数边界校验、无密钥泄露、失败不伪造结果。

- [ ] **Step 3: 检查最终文件和仓库状态**

Run:

```bash
git diff --check
git status --short
```

Expected: 仓库只包含本计划文档的预期变更；个人 Skill 文件位于 `/Users/minlong_1/.agents/skills/etf-stock-analysis`。

- [ ] **Step 4: 提交仓库内计划文档**

```bash
git add docs/superpowers/plans/2026-08-10-etf-stock-analysis-skill-implementation-plan.md
git commit -m "docs: add ETF analysis skill implementation plan"
```

不提交个人 Skill 到当前仓库，除非用户后续明确要求将它复制到仓库中。
