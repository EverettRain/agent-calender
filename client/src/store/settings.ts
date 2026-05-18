import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsState {
  serverUrl: string;
  apiToken: string;
  setServerUrl: (url: string) => void;
  setApiToken: (token: string) => void;
  isConfigured: () => boolean;
  reset: () => void;
}

export const useSettings = create<SettingsState>()(
  persist(
    (set, get) => ({
      serverUrl: "",
      apiToken: "",
      setServerUrl: (url) => set({ serverUrl: url.trim().replace(/\/+$/, "") }),
      setApiToken: (token) => set({ apiToken: token.trim() }),
      isConfigured: () => Boolean(get().serverUrl) && Boolean(get().apiToken),
      reset: () => set({ serverUrl: "", apiToken: "" }),
    }),
    { name: "agent-calendar-settings" },
  ),
);
