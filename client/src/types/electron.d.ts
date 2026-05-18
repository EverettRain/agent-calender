/**
 * Type augmentation for window.electron exposed via preload contextBridge.
 * Mirrors the api object in electron/preload.ts.
 */
export interface NotifyPayload {
  title: string;
  body: string;
  silent?: boolean;
}

export interface ElectronApi {
  notify: (payload: NotifyPayload) => Promise<boolean>;
  openExternal: (url: string) => Promise<void>;
  showWindow: () => Promise<void>;
  hideWindow: () => Promise<void>;
  platform: () => Promise<NodeJS.Platform>;
}

declare global {
  interface Window {
    electron?: ElectronApi;
  }
}

export {};
