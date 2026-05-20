import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  MapPin,
  Pencil,
  Trash2,
  Users,
} from "lucide-react";
import {
  useDeleteReminder,
  useMarkDone,
  useUpdateReminder,
} from "@/hooks/useReminders";
import { useGroups } from "@/hooks/useTagsGroups";
import EditReminderDialog from "@/components/EditReminderDialog";
import {
  cn,
  formatCountdown,
  formatLocalDateTime,
} from "@/lib/utils";
import GroupBadge from "@/components/GroupBadge";
import TagChip from "@/components/TagChip";
import type { Reminder } from "@/types/api";

interface Props {
  reminder: Reminder;
}

/**
 * Read-only card for the Today page: shows title/time/tags/group but does NOT
 * expose offset display or editing — that lives on the Manage page now.
 * Only done + delete actions are surfaced here.
 */
export default function CompactReminderCard({ reminder }: Props) {
  const done = useMarkDone();
  const del = useDeleteReminder();
  const update = useUpdateReminder();
  const { data: groups } = useGroups();

  const isDeadline = reminder.kind === "deadline";
  const isReview = reminder.status === "pending_review";
  const [editing, setEditing] = useState(false);

  const approve = () =>
    update.mutate({ id: reminder.id, payload: { status: "pending" } });

  // For deadlines, re-render countdown every minute
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!isDeadline) return;
    const id = setInterval(() => setTick((n) => n + 1), 60_000);
    return () => clearInterval(id);
  }, [isDeadline]);

  const group = reminder.group_id
    ? groups?.find((g) => g.id === reminder.group_id) ?? null
    : null;

  return (
    <div
      className={cn(
        "card p-3 space-y-2",
        isReview && "border-red-300 dark:border-red-700 ring-1 ring-red-200 dark:ring-red-900",
        isDeadline
          ? "border-l-4 border-l-amber-500"
          : "border-l-4 border-l-indigo-500",
      )}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            {isReview && (
              <span className="chip bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300">
                <AlertTriangle className="h-3 w-3" />
                待人工复核
              </span>
            )}
            <span
              className={cn(
                "chip",
                isDeadline
                  ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                  : "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300",
              )}
            >
              {isDeadline ? "截止" : "事件"}
            </span>
            {reminder.status === "notified" && (
              <span className="chip bg-slate-100 text-slate-600 dark:bg-slate-900 dark:text-slate-400">
                已通知
              </span>
            )}
            {reminder.status === "done" && (
              <span className="chip bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                已完成
              </span>
            )}
          </div>
          <h3
            className={cn(
              "font-semibold truncate",
              reminder.status === "done"
                ? "text-slate-400 line-through"
                : "text-slate-900 dark:text-slate-100",
            )}
          >
            {reminder.title}
          </h3>
          {reminder.description && (
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              {reminder.description}
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-1">
          {isReview && (
            <button
              className="btn-ghost text-emerald-600 dark:text-emerald-400"
              title="通过复核"
              onClick={approve}
              disabled={update.isPending}
            >
              <CheckCircle2 className="h-4 w-4" />
            </button>
          )}
          <button
            className="btn-ghost"
            title="编辑"
            onClick={() => setEditing(true)}
          >
            <Pencil className="h-4 w-4" />
          </button>
          {reminder.status !== "done" && (
            <button
              className="btn-ghost"
              title="标记完成"
              onClick={() => done.mutate(reminder.id)}
              disabled={done.isPending}
            >
              <Check className="h-4 w-4" />
            </button>
          )}
          <button
            className="btn-danger"
            title="删除"
            onClick={() => del.mutate(reminder.id)}
            disabled={del.isPending}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Time row + metadata */}
      <div className="flex items-center flex-wrap gap-x-4 gap-y-1 text-sm text-slate-700 dark:text-slate-300">
        <span className="flex items-center gap-1">
          <Clock className="h-3.5 w-3.5 text-slate-400" />
          {formatLocalDateTime(reminder.target_at)}
        </span>
        {isDeadline && reminder.status !== "done" && (
          <span
            className={cn(
              "font-medium",
              new Date(reminder.target_at).getTime() < Date.now()
                ? "text-red-600 dark:text-red-400"
                : "text-amber-600 dark:text-amber-400",
            )}
          >
            {formatCountdown(reminder.target_at)}
          </span>
        )}
        {reminder.location && (
          <span className="flex items-center gap-1">
            <MapPin className="h-3.5 w-3.5 text-slate-400" />
            {reminder.location}
          </span>
        )}
        {reminder.participants.length > 0 && (
          <span className="flex items-center gap-1">
            <Users className="h-3.5 w-3.5 text-slate-400" />
            {reminder.participants.join(", ")}
          </span>
        )}
      </div>

      {/* Tags + group (read-only) */}
      {(reminder.tags.length > 0 || reminder.group_id) && (
        <div className="flex items-center flex-wrap gap-2">
          <GroupBadge group={group} />
          {reminder.tags.map((t) => (
            <TagChip key={t.id} tag={t} />
          ))}
        </div>
      )}

      <EditReminderDialog
        reminder={reminder}
        open={editing}
        onClose={() => setEditing(false)}
      />
    </div>
  );
}
