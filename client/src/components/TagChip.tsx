import { cn } from "@/lib/utils";
import type { Tag } from "@/types/api";

interface Props {
  tag: Tag;
  onRemove?: () => void;
  className?: string;
}

/** Color-coded chip; falls back to neutral when no color set. */
export default function TagChip({ tag, onRemove, className }: Props) {
  const style = tag.color
    ? { backgroundColor: tag.color + "22", color: tag.color, borderColor: tag.color + "55" }
    : undefined;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
        !tag.color &&
          "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200",
        className,
      )}
      style={style}
    >
      <span>#{tag.name}</span>
      {onRemove && (
        <button
          type="button"
          className="opacity-60 hover:opacity-100"
          onClick={onRemove}
          aria-label={`移除 ${tag.name}`}
        >
          ×
        </button>
      )}
    </span>
  );
}
