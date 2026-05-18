# Agent-Calendar Server

FastAPI 后端：接收原始文本 → DeepSeek 抽取结构化提醒 → SQLite 持久化 → SSE 推给客户端。

详细架构与约束见项目根 [CLAUDE.md](../CLAUDE.md)。

## 目录

```
server/
├── app/
│   ├── main.py              # FastAPI 入口（Phase 1 实现）
│   ├── config.py            # pydantic-settings 配置
│   ├── db.py                # SQLAlchemy async engine + session
│   ├── models.py            # ORM: Reminder, ExtractionAttempt
│   ├── schemas.py           # Pydantic DTO
│   ├── api/
│   │   ├── ingest.py        # POST /ingest
│   │   ├── reminders.py     # GET/POST/PUT/DELETE /reminders
│   │   └── stream.py        # GET /stream (SSE)
│   ├── llm/
│   │   ├── adapter.py       # LLMAdapter 协议
│   │   ├── deepseek.py      # DeepSeek 实现
│   │   ├── prompts.py       # extract / verify 两套 prompt
│   │   └── schema.py        # JSON Schema 定义
│   └── services/
│       ├── extractor.py     # 抽取管线核心
│       ├── scheduler.py     # APScheduler
│       └── notifier.py      # SSE 派发
├── alembic/                 # 迁移
├── deploy/                  # systemd 单元文件等
├── tests/
├── pyproject.toml
└── .env.example
```

## 本地开发

```bash
# 1. 安装 uv（如未安装）: https://docs.astral.sh/uv/getting-started/installation/
# 2. 安装依赖
uv sync

# 3. 拷贝并填写环境变量
cp .env.example .env
# 编辑 .env，填入 API_TOKEN 和 DEEPSEEK_API_KEY

# 4. 初始化数据库（Phase 1 落地后才有 alembic 迁移）
# uv run alembic upgrade head

# 5. 启动
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
```

或从项目根：`make dev-server`。

## 测试

```bash
uv run pytest
uv run pytest --cov=app
```

## 部署到 VPS

参考 `deploy/agent-calendar.service`（systemd 单元，含 `MemoryMax=320M`）。
对外反代到现有 Caddy/Nginx → `127.0.0.1:8080`。
