# Agent-Calendar Client

Electron + React + TypeScript 桌面客户端，Win/Mac 同一套代码打包。

详细架构与约定见项目根 [CLAUDE.md](../CLAUDE.md)。

## 目录

```
client/
├── electron/                # 主进程 + preload（Phase 3 实现）
│   ├── main.ts              # 窗口 + Tray + 通知 + 自启
│   ├── preload.ts           # contextBridge IPC
│   └── notifier.ts          # 监听 SSE 弹原生通知
├── src/                     # 渲染层（React）
│   ├── main.tsx             # React 入口
│   ├── App.tsx
│   ├── pages/
│   │   ├── Today.tsx        # 今日 / 未来 7 天 时间轴
│   │   ├── Calendar.tsx     # 月 / 周历 (FullCalendar)
│   │   └── Settings.tsx     # 服务端地址 + Token
│   ├── components/
│   │   ├── QuickAdd.tsx     # 手动补一条 → POST /ingest
│   │   └── ReminderCard.tsx
│   ├── api/client.ts        # axios 客户端
│   ├── hooks/useReminders.ts
│   └── store/settings.ts    # Zustand 本地 UI 态
├── build/                   # electron-builder 资源（图标等）
├── index.html
├── vite.config.ts
├── tsconfig*.json
├── electron-builder.yml
└── package.json
```

## 本地开发

```bash
# 1. 安装 pnpm（如未安装）: https://pnpm.io/installation
# 2. 安装依赖
pnpm install

# 3. 启动 Vite + Electron 联动 dev
pnpm dev
```

或从项目根：`make dev-client`。

首次启动会出现 Settings 页填写：
- 服务端地址（默认 `http://127.0.0.1:8080`）
- API Token（与 `server/.env` 的 `API_TOKEN` 一致）

## 打包

```bash
pnpm build          # 输出到 release/ 下，含 .dmg 与 .exe
```

注意：跨平台打包建议在对应系统上执行（Mac 出 .dmg，Win 出 .exe）；
或在 CI 里用 GitHub Actions 的 macos-latest / windows-latest 矩阵。
