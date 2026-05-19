# iOS 快捷指令接入

通过 iOS / iPadOS / macOS 的"快捷指令"（Shortcuts），任意场景一秒把待办丢给 Agent-Calendar 服务端。

## 请求格式（核心信息）

| 项 | 值 |
|---|---|
| URL | `https://vps.everettrain.cn/ingest` |
| Method | `POST` |
| Headers | `Authorization: Bearer <你的 API_TOKEN>`<br>`Content-Type: application/json` |
| Body (JSON) | `{ "text": "<原文本>", "source_channel": "shortcut" }` |

`text` 必填、`source_channel` 选填（默认 `api`，建议传 `shortcut` 便于回看来源）。

`text` 可以是一句话，也可以是一段话（≤ 4000 字符）：
```
"今晚 10 点和团队对一下进度，下周五前要把月度总结发出来"
```

服务端会用 DeepSeek 抽取 → 可能产出 1 条或多条 reminder。响应体：
```json
{
  "extraction_group_id": "uuid",
  "status": "success",
  "reminders": [
    {
      "id": "uuid",
      "kind": "event",
      "title": "和团队对进度",
      "target_at": "2026-05-19T22:00:00+08:00",
      ...
    }
  ],
  "attempts": 1,
  "total_tokens": 2237
}
```

## 配置 iOS 快捷指令（最常用：手动输入版）

打开"快捷指令" App → 右上角 `+` 新建：

### 第 1 步：让用户输入文本

- 添加动作 **"询问输入"**（Ask for Input）
  - 输入类型：`文本`
  - 提示：`要记什么？`
  - 默认值：留空

### 第 2 步：发请求到服务端

- 添加动作 **"获取 URL 的内容"**（Get Contents of URL）
  - **URL**：`https://vps.everettrain.cn/ingest`
  - 点开"显示更多"：
    - **方法**：`POST`
    - **请求头**：点 `添加新标头`，加两条
      - `Authorization` = `Bearer 你那串 64 字节的 token`
      - `Content-Type` = `application/json`
    - **请求体**：选 `JSON`，结构如下
      - `text`（类型 `文本`）= 选变量 **"提供的输入"**
      - `source_channel`（类型 `文本`）= `shortcut`

### 第 3 步（可选）：把结果说出来 / 显示通知

- **"获取词典值"**：键 `reminders` → 得到数组
- **"统计"**：项目数 → 数字 N
- **"显示通知"**：标题 `已记下`，文字 `共 N 条待办`

也可以再加一条 **"显示结果"** 把 `提供的输入` 复述给你确认。

### 命名

例如命名为 **"快速记事"**，加上 Siri 短语 `"记一下"`。

## 使用方式

| 入口 | 说明 |
|---|---|
| Siri：`"嘿 Siri，记一下"` | 最快，免打字 |
| 桌面小组件 | 主屏添加"快捷指令"小组件，常驻入口 |
| 共享菜单 | 编辑快捷指令属性 → 打开"在共享表单中显示" → 在任意 App（备忘录 / Safari 选中文本 / 微信复制内容）"分享 → 快捷指令"直接入库 |
| 桌面 / Mac 菜单栏 | macOS 上也能用同一份快捷指令 |

## 进阶：从剪贴板 / 选中文本一键入库

如果你已经选好了文字（如微信里复制了一段聊天）：

1. 把 **"询问输入"** 替换为 **"取得剪贴板"** 或 **"接收输入"**
2. 把 JSON 里的 `text` 改成对应变量
3. 在快捷指令属性里打开 **"在共享表单中显示"**，**接受类型** 勾选 `文本`

这样从任何 App → 分享 → 选你的快捷指令，文本直接发服务端。

## 错误自检

| 现象 | 原因 |
|---|---|
| `200` 但 reminders 为空 | 不太可能；如果 status 是 `pending_review`，说明 LLM 反复验证失败，可在桌面端 Today 顶部"待复核"区调整 |
| `401` | token 错；快捷指令的 Authorization 头要正好是 `Bearer xxx`（注意 Bearer 后有一个空格） |
| `422` | text 是空，或 JSON 结构有错（少了 `text` 字段） |
| 一直转圈 / 超时 | 公网不通；先在 iPhone 浏览器试 `https://vps.everettrain.cn/healthz` 能不能拿到 `{"status":"ok"}` |
| `网络已离线` 类错误 | iPhone 当前网络解析不到域名；详见客户端 Settings 提到的 DNS 排查 |

## 安全提示

- **Token 等同于你的整个服务端控制权**：拿到的人可以读所有你的 reminder、新增、删除
- 快捷指令存在 iCloud 同步时会带上 token，建议**不要共享**含有 token 的快捷指令
- 想分享给朋友：先**轮换 token**（`openssl rand -hex 32` 生成新 token → 改 `server/.env` → `./deploy.sh push-env`）后再分享空模板
- 如果以后想多端用，可以用 iCloud 钥匙串保存 token，快捷指令里通过"取得密钥"获取，不裸写在快捷指令里

## 也支持其它端点（高级用法）

| 端点 | 用途 | 是否需要鉴权 |
|---|---|---|
| `POST /ingest` | 自然语言 → 抽取（最常用） | ✅ |
| `POST /reminders` | 手动精确创建一条（不走 LLM） | ✅ |
| `GET /reminders?from=...&to=...&kind=event` | 列表查询 | ✅ |
| `POST /reminders/<id>/done` | 标记完成 | ✅ |
| `DELETE /reminders/<id>` | 删除 | ✅ |
| `GET /healthz` | 探活 | ❌ |

完整 schema 见服务端 `server/app/schemas.py`。
