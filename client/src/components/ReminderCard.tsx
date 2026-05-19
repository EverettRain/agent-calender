import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Bell,
  Check,
  Clock,
  MapPin,
  Plus,
  Trash2,
  Users,
  X,
} from "lucide-react";
import {
  useDeleteReminder,
  useMarkDone,
  useUpdateReminder,
} from "@/hooks/useReminders";
import { useGroups, useTags } from "@/hooks/useTagsGroups";
import {
  cn,
  formatCountdown,
  formatLocalDateTime,
  formatOffset,
} from "@/lib/utils";
import GroupBadge from "@/components/GroupBadge";
import TagChip from "@/components/TagChip";
import type { Reminder, Tag } from "@/types/api";

interface Props {
  reminder: Reminder;
}

/**
 * Full reminder card with all editing affordances — used by the Manage page
 * and the Calendar detail overlay. Today now uses CompactReminderCard.
 */
export default function ReminderCard({ reminder }: Props) {
  const update = useUpdateReminder();
  const done = useMarkDone();
  const del = useDeleteReminder();
  const { data: groups } = useGroups();
  const { data: allTags } = useTags();

  const isDeadline = reminder.kind === "deadline";
  const isReview = reminder.status === "pending_review";

  const [, setTick] = useState(0);
  useEffect(() => {
    if (!isDeadline) return;
    const id = setInterval(() => setTick((n) => n + 1), 60_000);
    return () => clearInterval(id);
  }, [isDeadline]);

  const group = reminder.group_id
    ? groups?.find((g) => g.id === reminder.group_id) ?? null
    : null;

  const removeOffset = (n: number) => {
    update.mutate({
      id: reminder.id,
      payload: {
        advance_reminders_minutes: reminder.advance_reminders_minutes.filter(
          (x) => x !== n,
        ),
      },
    });
  };

  const addCommonOffset = (n: number) => {
    if (reminder.advance_reminders_minutes.includes(n)) return;
    update.mutate({
      id: reminder.id,
      payload: {
        advance_reminders_minutes: [
          ...reminder.advance_reminders_minutes,
          n,
        ],
      },
    });
  };

  const changeGroup = (groupId: string | null) => {
    update.mutate({ id: reminder.id, payload: { group_id: groupId } });
  };

  const toggleTag = (tag: Tag) => {
    const has = reminder.tags.some((t) => t.id === tag.id);
    const next = has
      ? reminder.tags.filter((t) => t.id !== tag.id).map((t) => t.id)
      : [...reminder.tags.map((t) => t.id), tag.id];
    update.mutate({ id: reminder.id, payload: { tag_ids: next } });
  };

  return (
    <div
      className={cn(
        "card p-4 space-y-3",
        isReview &&
          "border-red-300 dark:border-red-700 ring-1 ring-red-200 dark:ring-red-900",
        isDeadline
          ? "border-l-4 border-l-amber-500"
          : "border-l-4 border-l-indigo-500",
      )}
    >
      {/* Header */}
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

      {/* Time */}
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

      {/* Group selector + tag chips */}
      <div className="flex items-center flex-wrap gap-2">
        <select
          className="text-xs rounded border border-slate-300 dark:border-slate-700 bg-transparent px-2 py-0.5"
          value={reminder.group_id ?? ""}
          onChange={(e) => changeGroup(e.target.value || null)}
          disabled={update.isPending}
        >
          <option value="">未分组</option>
          {groups?.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
        <GroupBadge group={group} className="hidden" />
        {reminder.tags.map((t) => (
          <TagChip key={t.id} tag={t} onRemove={() => toggleTag(t)} />
        ))}
        {/* Add-tag picker */}
        {allTags && allTags.length > reminder.tags.length && (
          <details className="relative">
            <summary className="chip cursor-pointer text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 list-none">
              <Plus className="h-3 w-3" />
              加 tag
            </summary>
            <div className="absolute z-10 mt-1 max-h-48 overflow-y-auto rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-lg p-1 min-w-[140px]">
              {allTags
                .filter((t) => !reminder.tags.some((rt) => rt.id === t.id))
                .map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className="block w-full text-left px-2 py-1 text-xs rounded hover:bg-slate-100 dark:hover:bg-slate-700"
                    onClick={() => toggleTag(t)}
                  >
                    #{t.name}
                  </button>
                ))}
            </div>
          </details>
        )}
      </div>

      {/* Offsets */}
      <div className="flex items-center flex-wrap gap-2 text-xs">
        <span className="text-slate-400 flex items-center gap-1">
          <Bell className="h-3 w-3" />
          提醒：
        </span>
        {reminder.advance_reminders_minutes.length === 0 && (
          <span className="text-slate-400 italic">静默</span>
        )}
        {reminder.advance_reminders_minutes.map((n) => {
          const fired = reminder.fired_offsets.includes(n);
          return (
            <span
              key={n}
              className={cn(
                "chip",
                fired
                  ? "bg-slate-100 text-slate-500 line-through dark:bg-slate-900"
                  : "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
              )}
            >
              {formatOffset(n)}
              {!fired && (
                <button
                  className="opacity-50 hover:opacity-100"
                  onClick={() => removeOffset(n)}
                  title="移除该提醒"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </span>
          );
        })}
        <span className="ml-auto flex gap-1">
          {[
            { label: "到点", n: 0 },
            { label: "5 分钟", n: 5 },
            { label: "1 小时", n: 60 },
            { label: "1 天", n: 1440 },
          ]
            .filter((o) => !reminder.advance_reminders_minutes.includes(o.n))
            .map((o) => (
              <button
                key={o.n}
                className="chip hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500"
                onClick={() => addCommonOffset(o.n)}
              >
                <Plus className="h-3 w-3" />
                {o.label}
              </button>
            ))}
        </span>
      </div>
    </div>
  );
}
