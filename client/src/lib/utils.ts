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
 * Convert a UTC ISO string to a value usable by <input type="datetime-local">
 * (local wall-clock "YYYY-MM-DDTHH:mm", no timezone suffix).
 */
export function isoToDatetimeLocal(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

/**
 * Convert a datetime-local form value (local wall-clock) back to a UTC ISO string.
 * Returns null for empty input.
 */
export function datetimeLocalToIso(local: string): string | null {
  if (!local) return null;
  // new Date("YYYY-MM-DDTHH:mm") is interpreted as local time → toISOString gives UTC
  const d = new Date(local);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
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
