import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ThemePreference = "auto" | "light" | "dark";

interface PreferencesState {
  // Appearance
  theme: ThemePreference;
  setTheme: (t: ThemePreference) => void;

  // Today view
  todayRangeDays: number; // how many days into future to show
  showDone: boolean;
  showNotified: boolean;
  setTodayRangeDays: (n: number) => void;
  setShowDone: (v: boolean) => void;
  setShowNotified: (v: boolean) => void;

  // Manual reminder defaults (only used for client-side manual create)
  defaultEventOffsets: number[];
  defaultDeadlineOffsets: number[];
  setDefaultEventOffsets: (xs: number[]) => void;
  setDefaultDeadlineOffsets: (xs: number[]) => void;

  // Notifications
  notificationsEnabled: boolean;
  notificationsSilent: boolean;
  setNotificationsEnabled: (v: boolean) => void;
  setNotificationsSilent: (v: boolean) => void;

  resetAll: () => void;
}

const DEFAULTS = {
  theme: "auto" as ThemePreference,
  todayRangeDays: 7,
  showDone: false,
  showNotified: true,
  defaultEventOffsets: [0],
  defaultDeadlineOffsets: [60, 1440],
  notificationsEnabled: true,
  notificationsSilent: false,
};

export const usePreferences = create<PreferencesState>()(
  persist(
    (set) => ({
      ...DEFAULTS,
      setTheme: (theme) => set({ theme }),
      setTodayRangeDays: (todayRangeDays) =>
        set({ todayRangeDays: Math.max(1, Math.min(90, todayRangeDays)) }),
      setShowDone: (showDone) => set({ showDone }),
      setShowNotified: (showNotified) => set({ showNotified }),
      setDefaultEventOffsets: (xs) =>
        set({ defaultEventOffsets: normalizeOffsets(xs) }),
      setDefaultDeadlineOffsets: (xs) =>
        set({ defaultDeadlineOffsets: normalizeOffsets(xs) }),
      setNotificationsEnabled: (notificationsEnabled) =>
        set({ notificationsEnabled }),
      setNotificationsSilent: (notificationsSilent) =>
        set({ notificationsSilent }),
      resetAll: () => set({ ...DEFAULTS }),
    }),
    { name: "agent-calendar-preferences" },
  ),
);

function normalizeOffsets(xs: number[]): number[] {
  const cleaned = xs.filter((n) => Number.isInteger(n) && n >= 0);
  return Array.from(new Set(cleaned)).sort((a, b) => a - b);
}

/**
 * Parse a CSV string of offsets ("0,15,60") into a normalized number array.
 * Returns null when the input is malformed so the UI can surface an error.
 */
export function parseOffsetsCsv(raw: string): number[] | null {
  if (!raw.trim()) return [];
  const parts = raw.split(/[,\s]+/).filter(Boolean);
  const out: number[] = [];
  for (const p of parts) {
    const n = Number(p);
    if (!Number.isFinite(n) || !Number.isInteger(n) || n < 0) return null;
    out.push(n);
  }
  return normalizeOffsets(out);
}

export function offsetsToCsv(xs: number[]): string {
  return xs.join(", ");
}
