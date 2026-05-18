# Agent-Calendar

自然语言驱动的个人日程系统。把一段话丢给服务端，由 LLM（DeepSeek V4）抽取成结构化提醒；客户端以日历/列表查看，到点本地通知。**单用户自用**、**服务端为唯一真相源**。

## 架构

- **服务端**：Python 3.11 + FastAPI，部署在私有 VPS（systemd，非 Docker）
  - LLM：DeepSeek 官方 API（OpenAI 兼容协议），抽象为 `LLMAdapter`
  - 存储：仅 SQLite（WAL + `aiosqlite`），SQLAlchemy + Alembic
  - 调度：APScheduler（`AsyncIOScheduler`，进程内）
  - 通信：REST (CRUD) + SSE (实时)
  - 鉴权：单用户 API Token（环境变量配置）
- **客户端**：Electron + React + TypeScript，Win/Mac 同一套代码
  - 服务端为唯一真相源，客户端只缓存（TanStack Query + Zustand）
  - 月/周历用 FullCalendar，原生系统通知，常驻系统托盘
- **输入入口**：iOS/Mac 快捷指令 POST、客户端输入框；V2 追加 Telegram、剪贴板扩展

## 目录

- `server/`：FastAPI 服务端
- `client/`：Electron + React 桌面客户端（Win/Mac）
- `Makefile`：开发便捷命令入口

## 开发

```bash
# 一次性装好两端
make install

# 分别在两个终端启动
make dev-server       # http://127.0.0.1:8080
make dev-client       # Electron dev 窗口
```

底层等价命令：
- 服务端：`cd server && uv sync && uv run uvicorn app.main:app --reload`
- 客户端：`cd client && pnpm install && pnpm dev`

## 环境变量（server/.env）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `API_TOKEN` | — | 单用户鉴权 token，必填 |
| `DEEPSEEK_API_KEY` | — | DeepSeek key，必填 |
| `DEEPSEEK_MODEL` | `deepseek-v4-pro` | 生成阶段模型 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/data.db` | 仅 SQLite |
| `TZ` | `Asia/Shanghai` | 展示与相对时间解析用 |
| `EXTRACTION_MAX_ATTEMPTS` | `3` | 含首次生成的总尝试次数 |
| `EXTRACTION_VERIFY_ENABLED` | `true` | 关掉可节省一半 token |
| `EXTRACTION_VERIFY_MODEL` | `deepseek-v4-flash` | 反向校验用便宜模型 |
| `EXTRACTION_TOKEN_BUDGET_PER_INGEST` | `8000` | 单次 ingest 累计 token 上限 |
| `DEFAULT_EVENT_OFFSETS_MINUTES` | `0` | event 默认提前提醒（CSV），LLM 未给时兜底 |
| `DEFAULT_DEADLINE_OFFSETS_MINUTES` | `1440,60` | deadline 默认提前提醒（CSV），LLM 未给时兜底 |

**DeepSeek 模型决策**（2026-05 确认）：
- `deepseek-v4-pro`：generate 阶段，需要强中文理解 + JSON Mode + 隐含的时间推理
- `deepseek-v4-flash`：verify 阶段，pass/fail 二分判断对模型能力要求低，用便宜模型省 token
- 旧模型 `deepseek-chat` / `deepseek-reasoner` 是 v4-flash 的别名，**2026-07-24 弃用**，本项目不要再用

## LLM 抽取管线

`ExtractorService.extract(text) -> list[Reminder]` 跑完整四步链路，**一次输入可能产出多条 Reminder**：

1. **Generate**（LLM call #1）— `response_format=json_object` + 透传 JSON Schema
   - 输出 schema：`{"reminders": [<item>, <item>, ...]}`，`minItems=1`
   - 每个 item 含 `kind` 区分 `event` / `deadline`
   - 系统提示词要求："识别原文中所有独立的待办意图，分别建条；同一件事不要拆，不同的事不要并"
2. **Schema Validate**（本地零 token）— Pydantic 解析数组；任一 item 不通过即整体失败
   - `kind=deadline` 校验 `end_at is None`、`duration_minutes is None`
   - `advance_reminders_minutes` 去重 + 升序 + 非负
3. **Reverse-Verify**（LLM call #2）— 输入原文 + 抽取数组，要求 verifier 同时回答：
   - **覆盖性**：原文里每个独立意图都进了数组？
   - **无幻觉**：数组里没有原文里没提的事项？
   - **分类正确**：每条的 `kind` 是否合理（明确"开始时间"→ event，明确"截止/前/deadline"→ deadline）
   - **字段正确**：时间、地点、人物、提前提醒数组是否合理
   - 输出固定 `{"pass": bool, "issues": [...]}`，不让 verifier 自己改 JSON（避免两个模型打架）
4. **失败重试** — 把 verify issues 反馈回步骤 1，最多 `EXTRACTION_MAX_ATTEMPTS` 次；超出则把所有 item 都置为 `pending_review` 状态写入，绝不丢弃

同一次 ingest 的所有 Reminder 与所有 ExtractionAttempt 共用一个 `extraction_group_id`，链路完整可追溯。
每轮 LLM 调用必须写入 `extraction_attempts` 表（含 prompt/response 片段、token、耗时、verify 结果）。
`pending_review` 条目在客户端"今日"视图顶部红色高亮，可人工修正后转 `pending`。

### 调度与通知

`NotificationService` 每分钟扫一次：
```
SELECT * FROM reminders WHERE status='pending'
  AND any(target_at - offset*60s <= NOW for offset in advance_reminders_minutes
          if offset not in fired_offsets)
```
对每条命中：通过 SSE 派发 `reminder_due` 事件（V1 用），把 offset 追加到 `fired_offsets`。
当 `fired_offsets ⊇ advance_reminders_minutes` 且 `NOW > target_at` 时，状态置 `notified`。

## 数据模型

```
Reminder { id, kind, title, description, target_at, end_at, duration_minutes,
           location, participants[], advance_reminders_minutes[], fired_offsets[],
           status, source_text, source_channel, llm_model,
           extraction_group_id, created_at, updated_at }

ExtractionAttempt { id, extraction_group_id, source_text, attempt_no, stage,
                    model, prompt_tokens, completion_tokens, latency_ms,
                    result_json, verify_pass?, verify_issues?, error?,
                    created_at }
```

### Reminder 关键字段

- `kind`：`event` | `deadline`
  - `event`：`target_at` = 开始时刻；可选 `end_at` 或 `duration_minutes`
  - `deadline`：`target_at` = 截止时刻；`end_at` 必须为 null
- `target_at`：UTC 存储，展示转 `Asia/Shanghai`
- `advance_reminders_minutes`：整数数组，每个值 `N` 表示在 `target_at - N 分钟` 触发一次通知
  - `event` LLM 默认 `[0]`（到点提醒）
  - `deadline` LLM 默认 `[1440, 60]`（提前 1 天 + 1 小时）
  - `[]` 表示完全不提醒（静默条目）
  - 非负、自动去重、升序存储
  - `target_at - offset` 已过去的不补发，但保留在列表里
- `fired_offsets`：已触发过的 offset 集合，调度器用它做去重避免重复推送
- `extraction_group_id`：同一次 ingest 产生的多条 Reminder 共用同一 UUID，可关联回 `ExtractionAttempt` 链
- `status`：`pending` / `pending_review` / `notified` / `done` / `cancelled`
  - 所有 offset 都已 fired 且 `NOW > target_at` 时，状态从 `pending` → `notified`

### ExtractionAttempt 关键字段

- `extraction_group_id`：与 `Reminder` 同 group 关联
- `stage`：`generate` / `verify`
- 表清理：成功链路保留 30 天，失败 `pending_review` 永久保留

## 资源约束（VPS 硬限制）

本应用预算：**RAM 300MB / 磁盘 1GB**（含 SQLite）。所有设计为此服务：

- 单 Uvicorn worker：`uvicorn ... --workers 1 --limit-concurrency 5 --backlog 10`
- systemd `MemoryMax=320M` / `MemoryHigh=280M`
- 禁止 in-memory 缓存业务数据，全部走 SQLite
- 禁止引入 Redis / Celery / Postgres / 独立 Nginx 进程 / Docker
- 禁止 numpy / pandas / scipy 等大型依赖
- `/ingest` 末尾 `gc.collect()`（LLM 响应字符串大且生命周期短）
- 日志 `RotatingFileHandler`，10MB × 10 份
- `venv` 体积警戒线 300MB，超出需精简依赖

## 核心约定

- 服务端是数据真相源，客户端永远以拉取 / SSE 为准，不写本地副本
- LLM 抽取必须走 generate → validate → verify → retry 管线
- 抽取产出永远是 **数组**（即便只有一条）；失败则整数组进 `pending_review`，不部分入库
- 同一次 ingest 的所有 Reminder + ExtractionAttempt 共用 `extraction_group_id`
- 任何一轮 LLM 调用必须写 `extraction_attempts` 表，禁止"调一次扔一次"
- 解析失败或验证不过的事项进 `pending_review`，绝不丢弃
- `Reminder.kind` 区分 `event` / `deadline`；`deadline` 强制 `end_at = null`
- `advance_reminders_minutes` 入库前去重 + 升序；非负
- 已过期的 offset 不补发，但保留在列表里供审计
- 时间存 UTC，展示 `Asia/Shanghai`
- 新增字段：先 `models.py` + `schemas.py`，再 Alembic 迁移
- 接口变更同步更新 `client/src/api/client.ts` 的类型
- 新增依赖前 `du -sh .venv` 评估资源影响

## 当前进度

- [x] Phase 0 文档初始化 + 目录骨架
- [ ] Phase 1 服务端 MVP（DB + 抽取管线 + `/ingest` + `/reminders`）
- [ ] Phase 2 调度与 SSE 推送
- [ ] Phase 3 客户端 MVP（Today 视图 + 通知 + 托盘）
- [ ] Phase 4 月/周历视图 + 打包
- [ ] Phase 5 (V2) Telegram、RRULE 重复、搜索、多 Provider

完整计划见 `/Users/everett_rain/.claude/plans/deepseek-v4-pro-win-mac-telegram-claude-glowing-manatee.md`。
