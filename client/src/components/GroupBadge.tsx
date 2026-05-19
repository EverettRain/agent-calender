import { cn } from "@/lib/utils";
import { Folder } from "lucide-react";
import type { Group } from "@/types/api";

interface Props {
  group: Group | null | undefined;
  className?: string;
}

export default function GroupBadge({ group, className }: Props) {
  if (!group) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 text-xs text-slate-400",
          className,
        )}
      >
        <Folder className="h-3 w-3" />
        未分组
      </span>
    );
  }
  const style = group.color
    ? { color: group.color }
    : undefined;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-xs font-medium",
        !group.color && "text-slate-600 dark:text-slate-300",
        className,
      )}
      style={style}
    >
      <Folder className="h-3 w-3" />
      {group.name}
    </span>
  );
}
