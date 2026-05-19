import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface LoaderProps {
  /** Render-style: inline (default), block (centered), full (page-centered overlay). */
  variant?: "inline" | "block" | "full";
  /** Icon size keyword. */
  size?: "sm" | "md" | "lg";
  /** Optional caption next to the spinner. */
  label?: string;
  className?: string;
}

const sizeMap = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-8 w-8",
} as const;

/**
 * Spinner with optional label. Reuse across pages so the loading state is
 * visually consistent (and obviously "loading", not "broken").
 */
export default function Loader({
  variant = "inline",
  size = "md",
  label,
  className,
}: LoaderProps) {
  const spinner = (
    <span
      className={cn(
        "inline-flex items-center gap-2 text-slate-500 dark:text-slate-400",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <Loader2 className={cn(sizeMap[size], "animate-spin text-indigo-500")} />
      {label && <span className="text-sm">{label}</span>}
    </span>
  );

  if (variant === "block") {
    return <div className="flex justify-center py-8">{spinner}</div>;
  }
  if (variant === "full") {
    return (
      <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/60 backdrop-blur-sm dark:bg-slate-900/60">
        {spinner}
      </div>
    );
  }
  return spinner;
}
