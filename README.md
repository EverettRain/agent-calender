# Agent-Calendar

自然语言驱动的个人日程系统。把一段话丢给服务端，由 LLM（DeepSeek V4）抽取成结构化提醒；客户端以日历/列表查看，到点本地通知。

> 项目约定与详细架构见 [CLAUDE.md](./CLAUDE.md)
> 完整开发计划见 `~/.claude/plans/deepseek-v4-pro-win-mac-telegram-claude-glowing-manatee.md`

## 目录

```
agent-calender/
├── server/     # Python 3.11 + FastAPI 后端，部署到私有 VPS
├── client/     # Electron + React + TS 桌面端（Win/Mac）
├── CLAUDE.md   # 项目核心约定（架构、抽取管线、资源约束）
├── README.md
└── Makefile    # 开发便捷命令入口
```

## 快速开始

```bash
# 一次性安装两端依赖
make install

# 开发：分别在两个终端启动
make dev-server     # 服务端 http://127.0.0.1:8080
make dev-client     # 客户端 Electron dev 窗口
```

需要先配置 `server/.env`，参考 `server/.env.example`。

## 部署到 VPS

```bash
# 1. 拷贝并编辑配置（remoteHost、serviceUser 等）
cp deploy.config.example.json deploy.config.json
$EDITOR deploy.config.json

# 2. 确保本地 server/.env 已填好 API_TOKEN 与 DEEPSEEK_API_KEY

# 3. 启动交互菜单
./deploy.sh
```

常用菜单项：
- **1. setup** — 首装：创建用户/目录/venv、装依赖、写 systemd、跑 alembic、启动服务
- **2. deploy** — 增量更新：rsync 代码、必要时重装依赖、跑 migration、重启
- **3. status / 4. logs** — 查看 systemd 状态、内存占用、journalctl
- **8. backup-db** — SQLite hot backup 拉到本地 `backups/db/`
- **10. push-env** — 把本地 .env 同步到远端并可选择重启

也支持非交互模式：`./deploy.sh deploy` / `./deploy.sh status` 等，方便接入 CI。

VPS 前置要求：
- 一个 sudo 用户用于 SSH（脚本所有 sudo 操作通过 `sudoCmd`）
- 安装好 Python 3.11-3.13、`rsync`、`systemd`
- 如果需要 HTTPS，前置一个 Caddy/Nginx 反代到 `127.0.0.1:8080`

## 当前进度

- [x] Phase 0 文档 + 目录骨架
- [ ] Phase 1 服务端 MVP
- [ ] Phase 2 调度 + SSE 推送
- [ ] Phase 3 客户端 MVP
- [ ] Phase 4 月/周历 + 打包
- [ ] Phase 5 (V2) Telegram、RRULE 重复、搜索、多 Provider
