import { useState } from "react";
import { X } from "lucide-react";
import { useUpdateReminder } from "@/hooks/useReminders";
import { useGroups } from "@/hooks/useTagsGroups";
import {
  cn,
  datetimeLocalToIso,
  isoToDatetimeLocal,
} from "@/lib/utils";
import type { Reminder, ReminderKind, ReminderUpdate } from "@/types/api";

interface Props {
  reminder: Reminder;
  open: boolean;
  onClose: () => void;
}

/**
 * Full-field editor for a reminder: kind / title / time / range / location /
 * participants / group. (Tags + offsets are edited inline on the card.)
 */
export default function EditReminderDialog({ reminder, open, onClose }: Props) {
  const update = useUpdateReminder();
  const { data: groups } = useGroups();

  const [kind, setKind] = useState<ReminderKind>(reminder.kind);
  const [title, setTitle] = useState(reminder.title);
  const [description, setDescription] = useState(reminder.description ?? "");
  const [targetLocal, setTargetLocal] = useState(
    isoToDatetimeLocal(reminder.target_at),
  );
  const [endLocal, setEndLocal] = useState(isoToDatetimeLocal(reminder.end_at));
  const [location, setLocation] = useState(reminder.location ?? "");
  const [participants, setParticipants] = useState(
    reminder.participants.join(", "),
  );
  const [groupId, setGroupId] = useState<string>(reminder.group_id ?? "");
  const [err, setErr] = useState<string | null>(null);

  if (!open) return null;

  const submit = async () => {
    setErr(null);
    const targetIso = datetimeLocalToIso(targetLocal);
    if (!title.trim()) {
      setErr("标题不能为空");
      return;
    }
    if (!targetIso) {
      setErr("请填写有效的时间");
      return;
    }

    const payload: ReminderUpdate = {
      kind,
      title: title.trim(),
      description: description.trim() || null,
      target_at: targetIso,
      location: location.trim() || null,
      participants: participants
        .split(/[,，]/)
        .map((s) => s.trim())
        .filter(Boolean),
      group_id: groupId || null,
    };

    if (kind === "event") {
      payload.end_at = datetimeLocalToIso(endLocal);
    } else {
      // deadline: server forbids end_at/duration; clear by switching kind
      payload.end_at = null;
    }

    try {
      await update.mutateAsync({ id: reminder.id, payload });
      onClose();
    } catch (e: unknown) {
      setErr(extractErr(e));
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 dark:bg-slate-950/60 p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg card p-5 space-y-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          className="absolute right-3 top-3 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
          onClick={onClose}
          aria-label="关闭"
        >
          <X className="h-4 w-4" />
        </button>

        <h2 className="text-base font-semibold">编辑事项</h2>

        {/* Kind */}
        <div>
          <span className="text-sm font-medium">类型</span>
          <div className="mt-1 flex gap-2">
            <KindBtn current={kind} value="event" label="事件" onSelect={setKind} />
            <KindBtn current={kind} value="deadline" label="截止" onSelect={setKind} />
          </div>
        </div>

        {/* Title */}
        <label className="block">
          <span className="text-sm font-medium">标题</span>
          <input
            className="input mt-1"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
          />
        </label>

        {/* Description */}
        <label className="block">
          <span className="text-sm font-medium">描述</span>
          <textarea
            className="input mt-1 min-h-[56px] resize-y"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>

        {/* Time */}
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-sm font-medium">
              {kind === "deadline" ? "截止时间" : "开始时间"}
            </span>
            <input
              type="datetime-local"
              className="input mt-1"
              value={targetLocal}
              onChange={(e) => setTargetLocal(e.target.value)}
            />
          </label>
          {kind === "event" && (
            <label className="block">
              <span className="text-sm font-medium">结束时间（可选）</span>
              <input
                type="datetime-local"
                className="input mt-1"
                value={endLocal}
                onChange={(e) => setEndLocal(e.target.value)}
              />
            </label>
          )}
        </div>

        {/* Location + participants */}
        <label className="block">
          <span className="text-sm font-medium">地点</span>
          <input
            className="input mt-1"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            maxLength={200}
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">关联人物</span>
          <input
            className="input mt-1"
            value={participants}
            onChange={(e) => setParticipants(e.target.value)}
            placeholder="逗号分隔，如 张三, 李四"
          />
        </label>

        {/* Group */}
        <label className="block">
          <span className="text-sm font-medium">分组</span>
          <select
            className="input mt-1"
            value={groupId}
            onChange={(e) => setGroupId(e.target.value)}
          >
            <option value="">未分组</option>
            {groups?.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </label>

        {err && <p className="text-sm text-red-500">{err}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <button className="btn-ghost" onClick={onClose}>
            取消
          </button>
          <button
            className="btn-primary"
            onClick={submit}
            disabled={update.isPending}
          >
            {update.isPending ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}

function KindBtn({
  current,
  value,
  label,
  onSelect,
}: {
  current: ReminderKind;
  value: ReminderKind;
  label: string;
  onSelect: (v: ReminderKind) => void;
}) {
  const active = current === value;
  return (
    <button
      type="button"
      className={cn(
        "flex-1 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? value === "deadline"
            ? "border-amber-500 bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
            : "border-indigo-500 bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
          : "border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800",
      )}
      onClick={() => onSelect(value)}
    >
      {label}
    </button>
  );
}

function extractErr(e: unknown): string {
  if (typeof e === "object" && e !== null) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string };
    if (err.response?.data?.detail) return String(err.response.data.detail);
    if (err.message) return err.message;
  }
  return String(e);
}
