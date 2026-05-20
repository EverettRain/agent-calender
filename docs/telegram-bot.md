# Telegram Bot 集成

Agent-Calendar 服务端内嵌 Telegram Bot，让你不需要桌面端也能查待办、记新事项、收到提醒。

## 架构

- **内嵌于 FastAPI 主进程**（同一个 systemd unit，同一份 venv）
- **Webhook 模式**：Telegram → `POST https://你的域名/telegram/webhook` → PTB Application 处理
- **共享 EventBroker**：到点提醒通过同一个 `reminder_due` 事件分发给桌面端 SSE + Telegram
- **资源**：闲时增加 ~25-40MB RSS（PTB），完全在 320MB 预算内

## 部署步骤

### 第 1 步：在 BotFather 注册 bot

打开 Telegram，搜 **@BotFather** 开聊，发：

```
/newbot
```

按提示输入：
- **bot 显示名**：随便起，如 `My Agent Calendar`
- **bot 用户名**：必须以 `bot` 结尾且全局唯一，如 `everett_agent_calendar_bot`

BotFather 会回一个 **Token**，形如 `7123456789:AAH-xxxxxxxxxxxxxxxxxxxxx` —— 这就是 `TELEGRAM_BOT_TOKEN`。**别公开**。

可选：再发 `/setdescription` `/setuserpic` 设描述和头像；`/setcommands` 注册命令列表（供 Telegram 客户端的快捷指令面板用）：

```
start - 注册或查看欢迎信息
help - 命令清单
today - 今日 + 未来 3 天的待办
week - 未来 7 天的待办
```

### 第 2 步：生成 webhook secret

本地生成一个 32 字节随机串：

```bash
openssl rand -hex 32
```

复制下来，下一步用。

### 第 3 步：填 .env

编辑 `server/.env`，添加：

```bash
PUBLIC_BASE_URL=https://vps.everettrain.cn
TELEGRAM_BOT_TOKEN=7123456789:AAH-xxxxxxxxxxxxxxxxxxxxx
TELEGRAM_ALLOWED_CHAT_IDS=
TELEGRAM_WEBHOOK_SECRET=粘上面生成的串
```

`TELEGRAM_ALLOWED_CHAT_IDS` 先留空 —— 第一次启动后获取自己 chat_id 再填。

### 第 4 步：部署

```bash
./deploy.sh deploy
```

这会自动：

1. rsync 新代码到 VPS
2. 检测 pyproject.toml 变化（python-telegram-bot 是新依赖）→ 触发 `pip install -e ./app_src`
3. 跑 alembic（无新迁移，无操作）
4. 重启服务
5. lifespan 启动时调用 `bot.set_webhook(...)` 注册到 Telegram

### 第 5 步：注册自己（拿 chat_id）

打开 Telegram，搜你刚创建的 bot 用户名，开聊，发：

```
/start
```

Bot 会回复：

> 还未授权。请把下面这个 chat_id 加到服务端 TELEGRAM_ALLOWED_CHAT_IDS 后重启：
> `123456789`

把这串数字记下。

### 第 6 步：加白 + 重启

```bash
sed -i '' 's/^TELEGRAM_ALLOWED_CHAT_IDS=.*/TELEGRAM_ALLOWED_CHAT_IDS=123456789/' server/.env
./deploy.sh push-env
# 确认 → y 推送 .env → y 重启
```

### 第 7 步：验收

回 Telegram，再发：

```
/start
```

应回：

> 你已经授权 ✓
>
> 直接发一句话即可记录：
>   例：明天14点和张三开会，周五前要交报告
> ...

发个真实的：

```
明天 14 点和张三开会，周五前要交季度报告
```

10-20 秒后 bot 应回复 ✅ 已识别 2 条 + 两张卡片。

打开桌面端今日页面 —— 同样的两条 reminder 应该出现，证明 Telegram 与桌面端共用同一份数据。

### 第 8 步：等到点测试

创建一条 1 分钟后到点的：

```
一分钟后的测试
```

约 60-90 秒后，bot 会主动推送：

```
📅 事件开始：一分钟后的测试
  ⏰ 05-20 15:42

[✓ 完成]  [🔔 推迟 10 分]  [🗑 删除]
```

点 `🔔 推迟 10 分` → 等 10 分钟会再来一条。点 `✓ 完成` → 桌面端那条立即变成"已完成"。

## 命令清单

| 命令 / 行为 | 说明 |
|---|---|
| 直接发文字 | 自然语言记录，自动建条目（10-20s LLM 抽取） |
| `/start` | 欢迎信息 + 获取自己 chat_id |
| `/help` | 命令清单 |
| `/today` | 今日 + 未来 3 天的待办 |
| `/week` | 未来 7 天的待办 |
| 点击 `✓ 完成` | 标记 done，原消息加删除线 |
| 点击 `🔔 推迟 10 分` | 10 分钟后重新推送同一条 |
| 点击 `🗑 删除` | 软删，原消息加删除线 |

## 排错速查

| 现象 | 原因 |
|---|---|
| Bot 无响应 | 看 VPS 日志 `./deploy.sh logs`，找 `telegram.webhook_set` 或 `telegram.disabled` 行 |
| `/start` 一直回 "还未授权" | chat_id 填错；从 `/start` 那条响应里复制裸数字 |
| 部署后 Telegram 一直收旧版逻辑 | 浏览器访问 `https://vps.everettrain.cn/healthz` 确认服务起来；webhook 重新设置在 lifespan 启动时自动做 |
| 推送的消息没有 inline 按钮 | Telegram 端没正确解析；检查 `parse_mode=HTML` 是否被代理剥掉 |
| 公网测试 `/telegram/webhook` 直接返回 503 | 服务端 `.env` 里没填 `TELEGRAM_BOT_TOKEN` 或 `PUBLIC_BASE_URL`，bot 被禁用 |

## 安全提示

- **`TELEGRAM_BOT_TOKEN` 等于 bot 控制权**，别公开（同 `API_TOKEN`）
- **`TELEGRAM_WEBHOOK_SECRET` 防止伪造 webhook**，Telegram 在每次推送时会把这个值带在 header `X-Telegram-Bot-Api-Secret-Token` 里，服务端做 hmac.compare_digest 验证
- **白名单 chat_id 是唯一的访问控制**，未在名单上的消息**静默 drop**（不响应、不记录、不报错），避免被攻击者枚举
- token 泄露的应急流程：
  1. 在 BotFather 发 `/revoke` 然后选 bot → 旧 token 立即失效
  2. 拿新 token 改 `.env`
  3. `./deploy.sh push-env`（自动重启 + 重新 set_webhook）

## 资源占用实测

- 服务端 idle RSS：纯桌面端模式 ~60MB → 启用 TG 后 ~85-95MB
- 推送一条消息：CPU 抖动 < 50ms，网络出包 < 1KB
- 320MB 上限下日常使用余量 ~225MB

## 后续路线（V2）

- `/done <id>` `/del <id>` 命令式操作（V1 只有 inline 按钮）
- 按 group / tag 过滤：`/g 工作` `/t #紧急`
- `/search <关键词>`
- 群聊模式（让朋友也能给同一个 bot 发条目，每人独立 group）
