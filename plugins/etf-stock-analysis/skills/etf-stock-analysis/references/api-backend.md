# API 后端路径

适用于本地 API 服务已在运行、且本次是单个标的的情况。

## 1. 取 token

token 在仓库 `.env` 的 `ANALYSIS_API_TOKEN`。所有 `/api/v1/*` 端点都要求它。

**不要把 token 打印到对话里。** 用 shell 变量传递：

```bash
cd /Users/minlong_1/Desktop/Github/etf-stock-agent
TOKEN=$(grep -E '^ANALYSIS_API_TOKEN=' .env | cut -d= -f2-)
[ -n "$TOKEN" ] || echo "ANALYSIS_API_TOKEN 未配置"
```

token 为空就停下，让用户在 `.env` 里配置，不要替他生成或写入。

## 2. 提交任务

立即返回，不阻塞：

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/analysis/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"tickers":["DLR"],"level":5,"asset_type":"auto"}'
```

请求体字段（对应 `tradingagents/api/schemas.py` 的 `AnalysisJobCreate`）：

| 字段 | 说明 |
|---|---|
| `tickers` | 字符串数组，至少一个 |
| `level` | 1-5，默认 2；skill 默认传 5 |
| `date` | `YYYY-MM-DD`，不传则用当天并回退到可用交易日 |
| `asset_type` | `stock` / `etf` / `fund` / `auto` |

不要传 `provider`、`backend_url`、`deep_model`、`quick_model` —— 让服务端用自己 `.env` 里的配置。这些字段客户端可控，传了会覆盖服务端设置。

返回 201 和 `job_id`：

```json
{"job_id": "a1b2c3...", "status": "running", "created_at": "..."}
```

注意 `status` 立刻就是 `running`，但实际可能还在进程池里排队（`runner.py` 在 submit 时就标记了 running），这个状态不完全准确。

## 3. 轮询

**每次间隔 3-4 分钟**，不要更频繁 —— 一次分析要 7-18 分钟，密集轮询没有意义。用 `sleep` 配合单次 curl，保证每次 Bash 调用远低于 600 秒上限：

```bash
sleep 210
curl -sS -w '\nHTTP:%{http_code}\n' \
  http://127.0.0.1:8000/api/v1/analysis/jobs/<job_id>/result \
  -H "Authorization: Bearer $TOKEN"
```

状态码含义：

- `202` — 还在 `queued` 或 `running`，继续等
- `200` + `status: success` — 完成，`result` 里有全部数据
- `200` + `status: error` — 失败，读 `error` 字段
- `404` — job 不存在。**服务重启会清空内存里的 job 表**，此时报告文件仍在磁盘上，可以去 `reports_dir` 找 `<ticker>_<date>_report.md`

轮询期间告诉用户还在跑、大致要多久，不要静默等待。

## 4. 读结果

`result` 结构（来自 `run_analysis_batch`）：

```json
{
  "status": "success",
  "tickers": ["DLR"],
  "asset_type": "stock",
  "original_date": "2026-08-16",
  "trade_date": "2026-08-14",
  "level": 5,
  "analysts": ["market", "fundamentals", "news", "social"],
  "results": [
    {
      "ticker": "DLR",
      "status": "success",
      "decision": {"action": "买入", "target_price": "...", "confidence": 0.75, "risk_score": 0.4, "reasoning": "..."},
      "elapsed": 690.9,
      "stats": {"llm_calls": 42, "tool_calls": 18, "tokens_in": 380000, "tokens_out": 25000},
      "report_path": "/app/reports/DLR_2026-08-14_report.md",
      "report_exists": true
    }
  ]
}
```

`original_date` 和 `trade_date` 不同就说明日期被回退了，要在结论里说明实际用的是哪天。

## 5. 取报告

```bash
curl -sS http://127.0.0.1:8000/api/v1/analysis/jobs/<job_id>/reports/<ticker> \
  -H "Authorization: Bearer $TOKEN"
```

如果服务跑在 Docker 里，`report_path` 是**容器内**路径（`/app/reports/...`）。宿主机上的实际位置由 `.env` 的 `TRADINGAGENTS_REPORTS_VOLUME` 决定（默认 `./reports`）。给用户路径时要给宿主机路径，或者直接用上面这个端点把内容取出来。

## 启动服务

服务没起而用户想用 API 路径时，给出命令让用户自己决定，不要擅自启动长驻服务：

```bash
cd /Users/minlong_1/Desktop/Github/etf-stock-agent
docker compose up -d --build
curl -sf http://127.0.0.1:8000/healthz
```

服务是按本机/内网单机设计的，不要建议暴露到公网。
