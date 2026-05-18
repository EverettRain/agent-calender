import { useMemo } from "react";
import { Inbox } from "lucide-react";
import QuickAdd from "@/components/QuickAdd";
import ReminderCard from "@/components/ReminderCard";
import { useReminders } from "@/hooks/useReminders";
import type { Reminder } from "@/types/api";

export default function Today() {
  const range = useMemo(() => {
    const now = new Date();
    const start = new Date(now.getTime() - 60 * 60 * 1000); // 1h ago, catch just-passed events
    const end = new Date(now);
    end.setDate(end.getDate() + 7);
    return { from: start.toISOString(), to: end.toISOString() };
  }, []);

  const { data, isLoading, isError, error } = useReminders({
    ...range,
    limit: 200,
  });

  const partitioned = useMemo(() => partition(data ?? []), [data]);

  return (
    <div className="mx-auto max-w-3xl p-4 space-y-4">
      <QuickAdd />

      {isLoading && <Empty msg="加载中..." />}
      {isError && (
        <Empty
          msg={`加载失败：${(error as Error)?.message ?? "未知错误"}`}
          danger
        />
      )}

      {!isLoading && !isError && data && (
        <>
          {partitioned.review.length > 0 && (
            <Section title="待复核" hint="LLM 抽取后审核未通过，请检查后调整状态">
              {partitioned.review.map((r) => (
                <ReminderCard key={r.id} reminder={r} />
              ))}
            </Section>
          )}

          {partitioned.upcoming.length > 0 && (
            <Section title={`未来 7 天 · ${partitioned.upcoming.length} 条`}>
              {partitioned.upcoming.map((r) => (
                <ReminderCard key={r.id} reminder={r} />
              ))}
            </Section>
          )}

          {partitioned.past.length > 0 && (
            <Section title="最近过期 / 已通知" hint="按时间倒序">
              {partitioned.past.map((r) => (
                <ReminderCard key={r.id} reminder={r} />
              ))}
            </Section>
          )}

          {partitioned.review.length === 0 &&
            partitioned.upcoming.length === 0 &&
            partitioned.past.length === 0 && (
              <div className="flex flex-col items-center py-16 text-slate-400">
                <Inbox className="h-10 w-10 mb-2" />
                <p>未来 7 天没有待办</p>
                <p className="text-xs mt-1">用上方 QuickAdd 添加一条试试</p>
              </div>
            )}
        </>
      )}
    </div>
  );
}

function partition(rs: Reminder[]) {
  const now = Date.now();
  const review: Reminder[] = [];
  const upcoming: Reminder[] = [];
  const past: Reminder[] = [];

  for (const r of rs) {
    if (r.status === "cancelled" || r.status === "done") continue;
    if (r.status === "pending_review") {
      review.push(r);
      continue;
    }
    if (new Date(r.target_at).getTime() >= now) {
      upcoming.push(r);
    } else {
      past.push(r);
    }
  }
  upcoming.sort(
    (a, b) =>
      new Date(a.target_at).getTime() - new Date(b.target_at).getTime(),
  );
  past.sort(
    (a, b) =>
      new Date(b.target_at).getTime() - new Date(a.target_at).getTime(),
  );
  return { review, upcoming, past };
}

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
    <section className="space-y-2">
      <div className="flex items-baseline gap-2">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
          {title}
        </h2>
        {hint && (
          <span className="text-xs text-slate-400">· {hint}</span>
        )}
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function Empty({ msg, danger = false }: { msg: string; danger?: boolean }) {
  return (
    <div
      className={`card px-4 py-8 text-center text-sm ${
        danger ? "text-red-500" : "text-slate-400"
      }`}
    >
      {msg}
    </div>
  );
}
