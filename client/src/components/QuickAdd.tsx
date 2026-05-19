import { useState } from "react";
import { Sparkles } from "lucide-react";
import { useIngest } from "@/hooks/useReminders";
import Loader from "@/components/Loader";

export default function QuickAdd() {
  const [text, setText] = useState("");
  const ingest = useIngest();

  const submit = () => {
    const t = text.trim();
    if (!t) return;
    ingest.mutate(
      { text: t, source_channel: "desktop" },
      {
        onSuccess: () => setText(""),
      },
    );
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="card p-3 space-y-2">
      <textarea
        className="input min-h-[64px] resize-y"
        placeholder="用一句话描述，例如：明天 14 点和张三开会，周五前要交报告。⌘/Ctrl+Enter 提交"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={ingest.isPending}
      />
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400">
          {ingest.isPending && (
            <Loader size="sm" label="正在智能识别（约 5-15 秒）…" />
          )}
          {!ingest.isPending && ingest.isError && (
            <span className="text-red-500">
              失败：{extractErr(ingest.error)}
            </span>
          )}
          {!ingest.isPending && ingest.isSuccess && (
            <span className="text-green-600">
              已创建 {ingest.data.reminders.length} 条
            </span>
          )}
        </span>
        <button
          className="btn-primary"
          onClick={submit}
          disabled={!text.trim() || ingest.isPending}
        >
          <Sparkles className="h-3.5 w-3.5" />
          抽取
        </button>
      </div>
    </div>
  );
}

function extractErr(e: unknown): string {
  if (typeof e === "object" && e !== null) {
    const err = e as { message?: string };
    if (err.message) return err.message;
  }
  return String(e);
}
