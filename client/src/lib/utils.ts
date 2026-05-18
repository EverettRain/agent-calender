import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Format a UTC ISO string as local time using the user's locale.
 * Returns e.g. "5月19日 14:00"
 */
export function formatLocalDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function formatLocalDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
    weekday: "short",
  });
}

export function formatLocalTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/**
 * Render a deadline countdown ("还剩 2 天 3 小时" / "已过 1 小时").
 */
export function formatCountdown(targetIso: string, nowMs: number = Date.now()): string {
  const target = new Date(targetIso).getTime();
  const diffMs = target - nowMs;
  const past = diffMs < 0;
  const abs = Math.abs(diffMs);

  const days = Math.floor(abs / 86_400_000);
  const hours = Math.floor((abs % 86_400_000) / 3_600_000);
  const minutes = Math.floor((abs % 3_600_000) / 60_000);

  let body: string;
  if (days > 0) body = `${days} 天 ${hours} 小时`;
  else if (hours > 0) body = `${hours} 小时 ${minutes} 分钟`;
  else if (minutes > 0) body = `${minutes} 分钟`;
  else body = "<1 分钟";

  return past ? `已过 ${body}` : `还剩 ${body}`;
}

/**
 * Render an advance offset (in minutes) as human text.
 */
export function formatOffset(minutes: number): string {
  if (minutes === 0) return "到点";
  if (minutes < 60) return `提前 ${minutes} 分钟`;
  if (minutes < 1440) return `提前 ${Math.floor(minutes / 60)} 小时`;
  return `提前 ${Math.floor(minutes / 1440)} 天`;
}
