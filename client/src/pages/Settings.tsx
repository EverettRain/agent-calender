import { useEffect, useState } from "react";
import { useNavigate, useParams, NavLink } from "react-router-dom";
import {
  Bell,
  Brain,
  Check,
  Info,
  Plug,
  Sliders,
  Sun,
  Moon,
  Monitor,
  X,
} from "lucide-react";
import { useSettings } from "@/store/settings";
import {
  offsetsToCsv,
  parseOffsetsCsv,
  usePreferences,
  type ThemePreference,
} from "@/store/preferences";
import { healthz } from "@/api/reminders";
import { useAppSettings, useUpdateAppSettings } from "@/hooks/useAppSettings";
import { cn } from "@/lib/utils";

type TabId = "connection" | "preferences" | "models" | "about";

const TABS: { id: TabId; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "connection", label: "连接", icon: Plug },
  { id: "preferences", label: "偏好", icon: Sliders },
  { id: "models", label: "模型", icon: Brain },
  { id: "about", label: "关于", icon: Info },
];

export default function SettingsPage() {
  const params = useParams<{ tab?: string }>();
  const current = (TABS.find((t) => t.id === params.tab)?.id ?? "connection") as TabId;

  return (
    <div className="mx-auto max-w-2xl p-6">
      <div className="mb-6 flex items-center gap-1 border-b border-slate-200 dark:border-slate-800">
        {TABS.map(({ id, label, icon: Icon }) => (
          <NavLink
            key={id}
            to={id === "connection" ? "/settings" : `/settings/${id}`}
            className={cn(
              "flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
              current === id
                ? "border-indigo-500 text-indigo-600 dark:text-indigo-400"
                : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300",
            )}
            end
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </NavLink>
        ))}
      </div>

      {current === "connection" && <ConnectionPanel />}
      {current === "preferences" && <PreferencesPanel />}
      {current === "models" && <ModelsPanel />}
      {current === "about" && <AboutPanel />}
    </div>
  );
}

// ============================================================
// Connection panel
// ============================================================

function ConnectionPanel() {
  const settings = useSettings();
  const navigate = useNavigate();
  const [url, setUrl] = useState(settings.serverUrl);
  const [token, setToken] = useState(settings.apiToken);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"ok" | "error" | null>(null);
  const [testMsg, setTestMsg] = useState("");

  useEffect(() => {
    setUrl(settings.serverUrl);
    setToken(settings.apiToken);
  }, [settings.serverUrl, settings.apiToken]);

  const save = () => {
    settings.setServerUrl(url);
    settings.setApiToken(token);
    setTestResult(null);
  };

  const test = async () => {
    save();
    setTesting(true);
    setTestResult(null);
    setTestMsg("");
    try {
      const r = await healthz();
      if (r.status === "ok") {
        setTestResult("ok");
        setTestMsg("连接成功");
      } else {
        setTestResult("error");
        setTestMsg(`意外响应: ${JSON.stringify(r)}`);
      }
    } catch (e: unknown) {
      setTestResult("error");
      setTestMsg(extractErr(e));
    } finally {
      setTesting(false);
    }
  };

  const canSubmit = url.trim() && token.trim();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">服务端连接</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          填入服务端地址与访问 Token，保存后即可同步数据。
        </p>
      </div>

      <div className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium">服务端 URL</span>
          <input
            type="text"
            className="input mt-1"
            placeholder="https://your-server.example.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            指向你的 Agent-Calendar 服务端，结尾不带斜杠
          </p>
        </label>

        <label className="block">
          <span className="text-sm font-medium">服务端 API Token</span>
          <input
            type="password"
            className="input mt-1 font-mono"
            placeholder="服务端配置的访问 Token"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            autoComplete="off"
          />
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            服务端给你的访问令牌，向管理员索取
          </p>
        </label>
      </div>

      <div className="flex items-center gap-2">
        <button
          className="btn-primary"
          onClick={() => {
            save();
            navigate("/");
          }}
          disabled={!canSubmit}
        >
          保存并进入
        </button>
        <button className="btn-ghost" onClick={test} disabled={!canSubmit || testing}>
          {testing ? "测试中..." : "测试连接"}
        </button>
        {testResult === "ok" && (
          <span className="chip bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300">
            <Check className="h-3 w-3" />
            {testMsg}
          </span>
        )}
        {testResult === "error" && (
          <span className="chip bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300">
            <X className="h-3 w-3" />
            {testMsg}
          </span>
        )}
      </div>

    </div>
  );
}

// ============================================================
// Preferences panel
// ============================================================

function PreferencesPanel() {
  const p = usePreferences();

  return (
    <div className="space-y-8">
      <header>
        <h2 className="text-lg font-semibold mb-1">应用偏好</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          这些设置只影响当前这台设备上的展示与提醒。
        </p>
      </header>

      {/* Theme */}
      <Section title="外观" hint="跟随系统会响应系统主题的浅色/深色切换">
        <div className="flex gap-2">
          <ThemeBtn current={p.theme} value="auto" onSelect={p.setTheme} icon={Monitor} label="跟随系统" />
          <ThemeBtn current={p.theme} value="light" onSelect={p.setTheme} icon={Sun} label="浅色" />
          <ThemeBtn current={p.theme} value="dark" onSelect={p.setTheme} icon={Moon} label="深色" />
        </div>
      </Section>

      {/* Today view */}
      <Section title="今日视图">
        <NumberRow
          label="展示未来"
          unit="天"
          value={p.todayRangeDays}
          onChange={p.setTodayRangeDays}
          min={1}
          max={90}
        />
        <ToggleRow
          label="显示已完成的条目"
          checked={p.showDone}
          onChange={p.setShowDone}
        />
        <ToggleRow
          label="显示已通知过的条目"
          checked={p.showNotified}
          onChange={p.setShowNotified}
        />
      </Section>

      {/* Notifications */}
      <Section title="通知" hint="到点会弹出系统通知，需先在系统设置中允许 Agent-Calendar 发送通知">
        <ToggleRow
          label="启用系统通知"
          checked={p.notificationsEnabled}
          onChange={p.setNotificationsEnabled}
        />
        <ToggleRow
          label="静默通知（不出声）"
          checked={p.notificationsSilent}
          onChange={p.setNotificationsSilent}
          disabled={!p.notificationsEnabled}
        />
      </Section>

      {/* Default offsets for manual create */}
      <Section
        title="手动创建条目时的默认提醒"
        hint="仅在你手动创建条目时使用；用自然语言记录时会自动判断"
      >
        <OffsetsRow
          label="事件类型默认提前提醒"
          value={p.defaultEventOffsets}
          onChange={p.setDefaultEventOffsets}
          example="0  ← 到点提醒"
        />
        <OffsetsRow
          label="截止类型默认提前提醒"
          value={p.defaultDeadlineOffsets}
          onChange={p.setDefaultDeadlineOffsets}
          example="60, 1440  ← 提前 1 小时 + 提前 1 天"
        />
      </Section>

      <div className="border-t border-slate-200 dark:border-slate-800 pt-4">
        <button
          className="btn-danger"
          onClick={() => {
            if (confirm("把所有偏好恢复成默认值？连接配置不会动。")) {
              p.resetAll();
            }
          }}
        >
          恢复默认偏好
        </button>
      </div>
    </div>
  );
}

// ============================================================
// Models panel (server-side runtime settings)
// ============================================================

const KNOWN_MODELS = [
  { value: "deepseek-v4-pro", label: "deepseek-v4-pro（强，识别推荐）" },
  { value: "deepseek-v4-flash", label: "deepseek-v4-flash（快，复核推荐）" },
  { value: "deepseek-chat", label: "deepseek-chat（旧，将弃用）" },
  { value: "deepseek-reasoner", label: "deepseek-reasoner（旧，将弃用）" },
];

function ModelsPanel() {
  const { data, isLoading, isError, error } = useAppSettings();
  const update = useUpdateAppSettings();
  const [saved, setSaved] = useState(false);

  if (isLoading) {
    return <p className="text-sm text-slate-400">加载中…</p>;
  }
  if (isError || !data) {
    return (
      <p className="text-sm text-red-500">
        加载失败：{(error as Error)?.message ?? "未知错误"}
      </p>
    );
  }

  const patch = (payload: Parameters<typeof update.mutate>[0]) => {
    update.mutate(payload, {
      onSuccess: () => {
        setSaved(true);
        setTimeout(() => setSaved(false), 1500);
      },
    });
  };

  return (
    <div className="space-y-8">
      <header>
        <h2 className="text-lg font-semibold mb-1">模型与抽取</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          这些是服务端的全局设置，所有设备与 Telegram 共享，修改即时生效。
          {saved && <span className="ml-2 text-green-600">已保存 ✓</span>}
        </p>
      </header>

      <Section title="识别模型" hint="把自然语言抽取成结构化待办时使用">
        <ModelPicker
          value={data.generate_model}
          onChange={(m) => patch({ generate_model: m })}
        />
      </Section>

      <Section title="复核模型" hint="反向校验抽取结果时使用，通常用更快更便宜的模型">
        <ModelPicker
          value={data.verify_model}
          onChange={(m) => patch({ verify_model: m })}
        />
      </Section>

      <Section title="抽取参数">
        <ToggleRow
          label="启用复核（更准但更慢、更费 token）"
          checked={data.verify_enabled}
          onChange={(v) => patch({ verify_enabled: v })}
        />
        <NumberRow
          label="最大尝试次数"
          value={data.max_attempts}
          onChange={(n) => patch({ max_attempts: n })}
          min={1}
          max={10}
        />
        <NumberRow
          label="单次 token 预算"
          value={data.token_budget}
          onChange={(n) => patch({ token_budget: n })}
          min={500}
          max={200000}
          unit="tokens"
        />
      </Section>

      <p className="text-xs text-slate-400 border-t border-slate-200 dark:border-slate-800 pt-4">
        识别频繁被标记"待复核"时，可尝试：换更强的识别模型、关掉复核、或调高 token 预算。
      </p>
    </div>
  );
}

function ModelPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (m: string) => void;
}) {
  const isKnown = KNOWN_MODELS.some((m) => m.value === value);
  const [custom, setCustom] = useState(!isKnown);
  const [draft, setDraft] = useState(value);

  return (
    <div className="space-y-2">
      {!custom ? (
        <select
          className="input"
          value={value}
          onChange={(e) => {
            if (e.target.value === "__custom__") {
              setCustom(true);
              setDraft(value);
            } else {
              onChange(e.target.value);
            }
          }}
        >
          {KNOWN_MODELS.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
          {!isKnown && <option value={value}>{value}（自定义）</option>}
          <option value="__custom__">自定义…</option>
        </select>
      ) : (
        <div className="flex gap-2">
          <input
            className="input font-mono flex-1"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="输入模型名，如 deepseek-v4-pro"
          />
          <button
            className="btn-primary"
            onClick={() => draft.trim() && onChange(draft.trim())}
          >
            应用
          </button>
          <button className="btn-ghost" onClick={() => setCustom(false)}>
            选预设
          </button>
        </div>
      )}
      <p className="text-xs text-slate-400">当前：<code className="font-mono">{value}</code></p>
    </div>
  );
}

// ============================================================
// About panel
// ============================================================

function AboutPanel() {
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">关于</h2>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        <dt className="text-slate-500">应用</dt>
        <dd>Agent-Calendar</dd>
        <dt className="text-slate-500">版本</dt>
        <dd>{__APP_VERSION__}</dd>
        <dt className="text-slate-500">智能抽取</dt>
        <dd>由 DeepSeek 模型驱动</dd>
      </dl>

      <div className="text-xs text-slate-500 dark:text-slate-400 border-t border-slate-200 dark:border-slate-800 pt-4 space-y-1">
        <p>
          <Bell className="inline h-3 w-3 mr-1" />
          没有收到通知？请前往系统设置 → 通知 → Agent-Calendar，开启通知权限。
        </p>
      </div>
    </div>
  );
}

// ============================================================
// Reusable form bits
// ============================================================

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        {hint && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{hint}</p>}
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function ToggleRow({
  label,
  checked,
  onChange,
  disabled = false,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label
      className={cn(
        "flex items-center justify-between gap-4 py-1.5 cursor-pointer",
        disabled && "opacity-50 cursor-not-allowed",
      )}
    >
      <span className="text-sm">{label}</span>
      <input
        type="checkbox"
        className="h-4 w-4 accent-indigo-500"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
    </label>
  );
}

function NumberRow({
  label,
  value,
  onChange,
  unit,
  min,
  max,
  hint,
}: {
  label: string;
  value: number;
  onChange: (n: number) => void;
  unit?: string;
  min?: number;
  max?: number;
  hint?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span className="text-sm">
        {label}
        {hint && (
          <span className="ml-1 text-xs text-slate-400">· {hint}</span>
        )}
      </span>
      <div className="flex items-center gap-1">
        <input
          type="number"
          className="input w-20"
          value={value}
          min={min}
          max={max}
          onChange={(e) => {
            const n = Number(e.target.value);
            if (Number.isFinite(n)) onChange(n);
          }}
        />
        {unit && <span className="text-xs text-slate-400">{unit}</span>}
      </div>
    </div>
  );
}

function OffsetsRow({
  label,
  value,
  onChange,
  example,
}: {
  label: string;
  value: number[];
  onChange: (xs: number[]) => void;
  example: string;
}) {
  const [draft, setDraft] = useState(offsetsToCsv(value));
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setDraft(offsetsToCsv(value));
  }, [value]);

  const commit = () => {
    const parsed = parseOffsetsCsv(draft);
    if (parsed === null) {
      setErr("格式错误：用逗号分隔的非负整数（分钟）");
      return;
    }
    setErr(null);
    onChange(parsed);
    setDraft(offsetsToCsv(parsed));
  };

  return (
    <div className="space-y-1 py-1.5">
      <label className="text-sm block">{label}</label>
      <input
        type="text"
        className={cn(
          "input font-mono",
          err && "border-red-400 focus:ring-red-400",
        )}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        placeholder={example}
      />
      {err ? (
        <p className="text-xs text-red-500">{err}</p>
      ) : (
        <p className="text-xs text-slate-400">每个值代表"提前 N 分钟"；0 = 到点</p>
      )}
    </div>
  );
}

function ThemeBtn({
  current,
  value,
  onSelect,
  icon: Icon,
  label,
}: {
  current: ThemePreference;
  value: ThemePreference;
  onSelect: (v: ThemePreference) => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  const active = current === value;
  return (
    <button
      type="button"
      className={cn(
        "flex flex-1 items-center justify-center gap-1.5 rounded-md border px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
          : "border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800",
      )}
      onClick={() => onSelect(value)}
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}

function extractErr(e: unknown): string {
  if (typeof e === "object" && e !== null) {
    const err = e as { message?: string; response?: { status?: number; data?: unknown } };
    if (err.response) return `HTTP ${err.response.status} ${JSON.stringify(err.response.data)}`;
    if (err.message) return err.message;
  }
  return String(e);
}
