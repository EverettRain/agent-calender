import { contextBridge, ipcRenderer } from "electron";
import { IPC, type NotifyPayload } from "./ipc-channels";

/**
 * Safe bridge exposed to the renderer.
 *
 * The renderer must use only this API to talk to the OS — no nodeIntegration,
 * no direct ipcRenderer access, no dangerouslySetInnerHTML escape hatches.
 */
const api = {
  notify: (payload: NotifyPayload): Promise<boolean> =>
    ipcRenderer.invoke(IPC.NOTIFY, payload),

  openExternal: (url: string): Promise<void> =>
    ipcRenderer.invoke(IPC.OPEN_EXTERNAL, url),

  showWindow: (): Promise<void> => ipcRenderer.invoke(IPC.WINDOW_SHOW),

  hideWindow: (): Promise<void> => ipcRenderer.invoke(IPC.WINDOW_HIDE),

  platform: (): Promise<NodeJS.Platform> => ipcRenderer.invoke(IPC.PLATFORM),
};

contextBridge.exposeInMainWorld("electron", api);

export type ElectronApi = typeof api;
