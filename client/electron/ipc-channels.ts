/**
 * IPC channel names shared between main and preload.
 * Renderer never imports this directly — it only uses the typed bridge
 * exposed via contextBridge in preload.ts.
 */
export const IPC = {
  NOTIFY: "notify",
  OPEN_EXTERNAL: "open-external",
  WINDOW_SHOW: "window-show",
  WINDOW_HIDE: "window-hide",
  PLATFORM: "platform",
} as const;

export interface NotifyPayload {
  title: string;
  body: string;
  silent?: boolean;
}
