import { useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Folder,
  Inbox,
  Layers,
  Pencil,
  Plus,
  Tag as TagIcon,
} from "lucide-react";
import Loader from "@/components/Loader";
import ReminderCard from "@/components/ReminderCard";
import TagManagerDialog from "@/components/TagManagerDialog";
import GroupManagerDialog from "@/components/GroupManagerDialog";
import { useReminders } from "@/hooks/useReminders";
import { useGroups, useTags } from "@/hooks/useTagsGroups";
import { cn } from "@/lib/utils";
import type { Reminder } from "@/types/api";

type SelectionKind = "all" | "inbox" | "group" | "tag";

interface Selection {
  kind: SelectionKind;
  id?: string; // group id or tag id
  label: string;
}

export default function Manage() {
  const [selection, setSelection] = useState<Selection>({
    kind: "all",
    label: "全部",
  });
  const [tagDialog, setTagDialog] = useState(false);
  const [groupDialog, setGroupDialog] = useState(false);
  const [doneOpen, setDoneOpen] = useState(false);

  // We fetch the full set once (include_cancelled=false by default) and slice
  // client-side; volumes are tiny for a single user so this is simpler than
  // re-querying on every sidebar click.
  const { data, isError, error } = useReminders({
    limit: 1000,
    include_cancelled: false,
  });
  const { data: groups } = useGroups();
  const { data: tags } = useTags();

  const filtered = useMemo(() => {
    if (!data) return [] as Reminder[];
    switch (selection.kind) {
      case "all":
        return data;
      case "inbox":
        return data.filter((r) => r.group_id === null);
      case "group":
        return data.filter((r) => r.group_id === selection.id);
      case "tag":
        return data.filter((r) =>
          r.tags.some((t) => t.id === selection.id),
        );
    }
  }, [data, selection]);

  const { pending, doneRs } = useMemo(() => {
    const pending: Reminder[] = [];
    const doneRs: Reminder[] = [];
    for (const r of filtered) {
      if (r.status === "done") doneRs.push(r);
      else pending.push(r);
    }
    pending.sort(
      (a, b) =>
        new Date(a.target_at).getTime() - new Date(b.target_at).getTime(),
    );
    doneRs.sort(
      (a, b) =>
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
    );
    return { pending, doneRs };
  }, [filtered]);

  const ready = data !== undefined;

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 border-r border-slate-200 dark:border-slate-800 overflow-y-auto py-3 px-2 space-y-4">
        <NavItem
          icon={Layers}
          label="全部"
          active={selection.kind === "all"}
          onClick={() => setSelection({ kind: "all", label: "全部" })}
        />
        <NavItem
          icon={Inbox}
          label="未分组"
          active={selection.kind === "inbox"}
          onClick={() => setSelection({ kind: "inbox", label: "未分组" })}
        />

        <Section title="分组" onManage={() => setGroupDialog(true)}>
          {groups?.length === 0 && (
            <p className="text-xs text-slate-400 px-2 py-1">还没有分组</p>
          )}
          {groups?.map((g) => (
            <NavItem
              key={g.id}
              icon={Folder}
              iconColor={g.color ?? undefined}
              label={g.name}
              active={selection.kind === "group" && selection.id === g.id}
              onClick={() =>
                setSelection({ kind: "group", id: g.id, label: g.name })
              }
            />
          ))}
        </Section>

        <Section title="标签" onManage={() => setTagDialog(true)}>
          {tags?.length === 0 && (
            <p className="text-xs text-slate-400 px-2 py-1">还没有 tag</p>
          )}
          {tags?.map((t) => (
            <NavItem
              key={t.id}
              icon={TagIcon}
              iconColor={t.color ?? undefined}
              label={`#${t.name}`}
              active={selection.kind === "tag" && selection.id === t.id}
              onClick={() =>
                setSelection({ kind: "tag", id: t.id, label: t.name })
              }
            />
          ))}
        </Section>
      </aside>

      {/* Main */}
      <section className="flex-1 overflow-y-auto p-5 space-y-5">
        <header>
          <h1 className="text-lg font-semibold">{selection.label}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            {ready
              ? `${pending.length} 条待完成 · ${doneRs.length} 条已完成`
              : "加载中…"}
          </p>
        </header>

        {isError && (
          <div className="text-sm text-red-500">
            加载失败：{(error as Error)?.message ?? "未知错误"}
          </div>
        )}

        {!ready ? (
          <div className="card min-h-[400px] flex items-center justify-center">
            <Loader variant="block" size="lg" label="加载条目中…" />
          </div>
        ) : (
          <>
            {/* Pending section (always expanded) */}
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                待完成 · {pending.length}
              </h2>
              {pending.length === 0 ? (
                <p className="text-sm text-slate-400 py-4">这里空着</p>
              ) : (
                <div className="space-y-2">
                  {pending.map((r) => (
                    <ReminderCard key={r.id} reminder={r} />
                  ))}
                </div>
              )}
            </section>

            {/* Done section (default collapsed) */}
            {doneRs.length > 0 && (
              <section className="space-y-2">
                <button
                  className="flex items-center gap-1 text-sm font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white"
                  onClick={() => setDoneOpen((v) => !v)}
                >
                  {doneOpen ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                  )}
                  已完成 · {doneRs.length}
                </button>
                {doneOpen && (
                  <div className="space-y-2">
                    {doneRs.map((r) => (
                      <ReminderCard key={r.id} reminder={r} />
                    ))}
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </section>

      <TagManagerDialog open={tagDialog} onClose={() => setTagDialog(false)} />
      <GroupManagerDialog
        open={groupDialog}
        onClose={() => setGroupDialog(false)}
      />
    </div>
  );
}

// ============================================================

function Section({
  title,
  onManage,
  children,
}: {
  title: string;
  onManage: () => void;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center justify-between px-2 mb-1">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          {title}
        </h3>
        <button
          className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
          onClick={onManage}
          title={`管理${title}`}
        >
          <Pencil className="h-3 w-3" />
        </button>
      </div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function NavItem({
  icon: Icon,
  iconColor,
  label,
  active,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  iconColor?: string;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 w-full text-left rounded-md px-2 py-1.5 text-sm transition-colors",
        active
          ? "bg-slate-200 text-slate-900 dark:bg-slate-700 dark:text-white font-medium"
          : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
      )}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" style={iconColor ? { color: iconColor } : undefined} />
      <span className="truncate">{label}</span>
    </button>
  );
}

// Manage page note: we reuse the global "+" navigation symbol for sidebar
// management; keeping the visual minimal so adding lots of tags doesn't
// crowd the sidebar.
export const _PlusUnusedHint = Plus;
