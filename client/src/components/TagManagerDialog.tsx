import { useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import ColorDot from "@/components/ColorDot";
import {
  useCreateTag,
  useDeleteTag,
  useTags,
  useUpdateTag,
} from "@/hooks/useTagsGroups";
import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  onClose: () => void;
}

const PRESET_COLORS = [
  "#ef4444",
  "#f97316",
  "#eab308",
  "#22c55e",
  "#10b981",
  "#06b6d4",
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
  "#6b7280",
];

export default function TagManagerDialog({ open, onClose }: Props) {
  const { data: tags } = useTags();
  const create = useCreateTag();
  const update = useUpdateTag();
  const del = useDeleteTag();

  const [name, setName] = useState("");
  const [color, setColor] = useState<string>(PRESET_COLORS[6]);
  const [err, setErr] = useState<string | null>(null);

  if (!open) return null;

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    try {
      await create.mutateAsync({ name: trimmed, color });
      setName("");
      setErr(null);
    } catch (e: unknown) {
      setErr(extractErr(e));
    }
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/40 dark:bg-slate-950/60 p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md card p-5 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          className="absolute right-3 top-3 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
          onClick={onClose}
          aria-label="关闭"
        >
          <X className="h-4 w-4" />
        </button>

        <h2 className="text-base font-semibold">管理 Tag</h2>

        {/* Create form */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <input
              className="input flex-1"
              placeholder="新 tag 名称"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              maxLength={64}
            />
            <button
              className="btn-primary"
              onClick={submit}
              disabled={!name.trim() || create.isPending}
            >
              <Plus className="h-3.5 w-3.5" />
              添加
            </button>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-500">颜色：</span>
            {PRESET_COLORS.map((c) => (
              <button
                key={c}
                className={cn(
                  "h-5 w-5 rounded-full border-2",
                  color === c
                    ? "border-slate-900 dark:border-white"
                    : "border-transparent",
                )}
                style={{ backgroundColor: c }}
                onClick={() => setColor(c)}
                title={c}
              />
            ))}
          </div>
          {err && <p className="text-xs text-red-500">{err}</p>}
        </div>

        {/* List */}
        <div className="max-h-72 overflow-y-auto space-y-1 border-t border-slate-200 dark:border-slate-800 pt-3">
          {(tags ?? []).length === 0 && (
            <p className="text-sm text-slate-400 py-2">还没有 tag</p>
          )}
          {tags?.map((t) => (
            <div
              key={t.id}
              className="flex items-center justify-between gap-2 py-1.5 px-1 rounded hover:bg-slate-50 dark:hover:bg-slate-800/50"
            >
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <ColorDot
                  value={t.color ?? "#888888"}
                  onChange={(hex) =>
                    update.mutate({ id: t.id, payload: { color: hex } })
                  }
                  title="改颜色"
                />
                <input
                  className="bg-transparent text-sm truncate flex-1 focus:outline-none focus:bg-white dark:focus:bg-slate-900 px-1 rounded"
                  defaultValue={t.name}
                  onBlur={(e) => {
                    if (e.target.value !== t.name) {
                      update.mutate({
                        id: t.id,
                        payload: { name: e.target.value },
                      });
                    }
                  }}
                />
              </div>
              <button
                className="btn-danger"
                onClick={() => {
                  if (confirm(`删除 tag "${t.name}"？所有关联也会清除。`)) {
                    del.mutate(t.id);
                  }
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function extractErr(e: unknown): string {
  if (typeof e === "object" && e !== null) {
    const err = e as { response?: { status?: number; data?: { detail?: string } } };
    if (err.response?.data?.detail) return err.response.data.detail;
    if (err.response?.status === 409) return "名称已存在";
  }
  return String(e);
}
