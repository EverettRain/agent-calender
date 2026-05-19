import { cn } from "@/lib/utils";

interface Props {
  value: string | null;
  onChange: (hex: string) => void;
  /** Diameter class — defaults to h-5 w-5 (20px). */
  sizeClass?: string;
  /** Tooltip on hover. */
  title?: string;
  className?: string;
}

/**
 * Circular color swatch that opens the OS color picker when clicked.
 * The native <input type="color"> is hidden offscreen; the label IS the swatch.
 */
export default function ColorDot({
  value,
  onChange,
  sizeClass = "h-5 w-5",
  title = "选择颜色",
  className,
}: Props) {
  const color = value ?? "#94a3b8"; // slate-400 fallback
  return (
    <label
      className={cn(
        "relative inline-flex shrink-0 cursor-pointer rounded-full border border-slate-300 dark:border-slate-700 ring-1 ring-transparent hover:ring-slate-400 dark:hover:ring-slate-500 transition-shadow",
        sizeClass,
        className,
      )}
      style={{ backgroundColor: color }}
      title={title}
    >
      <input
        type="color"
        value={color}
        onChange={(e) => onChange(e.target.value)}
        className="absolute h-0 w-0 opacity-0 pointer-events-none"
        aria-label={title}
      />
    </label>
  );
}
