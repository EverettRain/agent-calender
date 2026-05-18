import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, X } from "lucide-react";
import { useSettings } from "@/store/settings";
import { healthz } from "@/api/reminders";

export default function SettingsPage() {
  const settings = useSettings();
  const navigate = useNavigate();
  const [url, setUrl] = useState(settings.serverUrl);
  const [token, setToken] = useState(settings.apiToken);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<"ok" | "error" | null>(null);
  const [testMsg, setTestMsg] = useState("");

  // Keep local form in sync if store changes externally
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
    <div className="mx-auto max-w-xl p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">服务端连接</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          配置 Agent-Calendar 服务端地址与 API Token，保存后可立即拉取数据。
        </p>
      </div>

      <div className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium">服务端 URL</span>
          <input
            type="text"
            className="input mt-1"
            placeholder="http://127.0.0.1:8080 或 https://agent.yourdomain.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            指向你部署的 Agent-Calendar 服务端，结尾不带斜杠
          </p>
        </label>

        <label className="block">
          <span className="text-sm font-medium">服务端 API Token</span>
          <input
            type="password"
            className="input mt-1 font-mono"
            placeholder="服务端 .env 里的 API_TOKEN（一长串随机字符串）"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            autoComplete="off"
          />
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            <span className="font-semibold text-amber-600 dark:text-amber-400">
              注意
            </span>
            ：此字段为服务端连接密钥{" "}
            <code className="font-mono">API_TOKEN</code>，非 DeepSeek API key。
            DeepSeek Key 由服务端存储并提供，无需客户端手动输入。
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

      <div className="text-xs text-slate-400 border-t border-slate-200 dark:border-slate-800 pt-4">
        本地开发时 URL 通常是 <code>http://127.0.0.1:8080</code>。
        部署到 VPS 后建议走 SSH 隧道（本地 127.0.0.1:8080 → 远端）或反向代理出的 HTTPS 域名。
      </div>
    </div>
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
