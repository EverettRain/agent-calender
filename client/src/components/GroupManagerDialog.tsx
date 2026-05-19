import { useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import ColorDot from "@/components/ColorDot";
import {
  useCreateGroup,
  useDeleteGroup,
  useGroups,
  useUpdateGroup,
} from "@/hooks/useTagsGroups";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function GroupManagerDialog({ open, onClose }: Props) {
  const { data: groups } = useGroups();
  const create = useCreateGroup();
  const update = useUpdateGroup();
  const del = useDeleteGroup();

  const [name, setName] = useState("");
  const [err, setErr] = useState<string | null>(null);

  if (!open) return null;

  const submit = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    try {
      await create.mutateAsync({ name: trimmed });
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

        <h2 className="text-base font-semibold">管理分组（列表）</h2>

        <div className="flex items-center gap-2">
          <input
            className="input flex-1"
            placeholder="新分组名称（如 Work / Personal）"
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
        {err && <p className="text-xs text-red-500">{err}</p>}

        <div className="max-h-72 overflow-y-auto space-y-1 border-t border-slate-200 dark:border-slate-800 pt-3">
          {(groups ?? []).length === 0 && (
            <p className="text-sm text-slate-400 py-2">
              还没有分组，所有条目都在"未分组"里
            </p>
          )}
          {groups?.map((g) => (
            <div
              key={g.id}
              className="flex items-center justify-between gap-2 py-1.5 px-1 rounded hover:bg-slate-50 dark:hover:bg-slate-800/50"
            >
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <ColorDot
                  value={g.color ?? "#6366f1"}
                  onChange={(hex) =>
                    update.mutate({ id: g.id, payload: { color: hex } })
                  }
                  title="改颜色"
                />
                <input
                  className="bg-transparent text-sm truncate flex-1 focus:outline-none focus:bg-white dark:focus:bg-slate-900 px-1 rounded"
                  defaultValue={g.name}
                  onBlur={(e) => {
                    if (e.target.value !== g.name) {
                      update.mutate({
                        id: g.id,
                        payload: { name: e.target.value },
                      });
                    }
                  }}
                />
              </div>
              <button
                className="btn-danger"
                onClick={() => {
                  if (
                    confirm(
                      `删除分组 "${g.name}"？里面的条目会回到"未分组"（不会删除条目本身）。`,
                    )
                  ) {
                    del.mutate(g.id);
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
