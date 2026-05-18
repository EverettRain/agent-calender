import { app, BrowserWindow, ipcMain, Notification, shell, Tray, Menu, nativeImage } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { IPC, type NotifyPayload } from "./ipc-channels";

// __dirname is not defined in ES modules — derive it from import.meta.url
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Single-instance lock
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
}

const VITE_DEV_SERVER_URL = process.env["VITE_DEV_SERVER_URL"];
const IS_DEV = !!VITE_DEV_SERVER_URL;

const PROJECT_ROOT = path.join(__dirname, "..");
const RENDERER_DIST = path.join(PROJECT_ROOT, "dist");
const PRELOAD = path.join(__dirname, "preload.mjs");

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let quittingFromTray = false;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 960,
    height: 720,
    minWidth: 480,
    minHeight: 480,
    show: true,
    title: "Agent-Calendar",
    backgroundColor: "#0f172a",
    webPreferences: {
      preload: PRELOAD,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  if (IS_DEV && VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(VITE_DEV_SERVER_URL);
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(RENDERER_DIST, "index.html"));
  }

  // Closing the window hides to tray instead of quitting (macOS-style behaviour
  // on every platform — we're a background tool).
  mainWindow.on("close", (event) => {
    if (!quittingFromTray) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });
}

function createTray() {
  // Tiny transparent 16x16 PNG so Electron has something to render.
  // We then setTitle so it shows as text on macOS menu bar.
  const transparent16x16 = nativeImage.createFromBuffer(
    Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQAQMAAAAlPW0iAAAABlBMVEUAAAAAAAClZ7nPAAAAAXRSTlMAQObYZgAAAAlwSFlzAAAOxAAADsQBlSsOGwAAAA9JREFUCNdjGAWjYBSMAggAAv4AAUUz2DkAAAAASUVORK5CYII=",
      "base64",
    ),
  );
  // Mark as template so macOS adapts colour automatically.
  transparent16x16.setTemplateImage(true);

  tray = new Tray(transparent16x16);
  tray.setTitle("📅");
  tray.setToolTip("Agent-Calendar");

  const menu = Menu.buildFromTemplate([
    {
      label: "显示窗口",
      click: () => {
        mainWindow?.show();
        mainWindow?.focus();
      },
    },
    { type: "separator" },
    {
      label: "退出",
      click: () => {
        quittingFromTray = true;
        app.quit();
      },
    },
  ]);
  tray.setContextMenu(menu);

  tray.on("click", () => {
    if (mainWindow?.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow?.show();
      mainWindow?.focus();
    }
  });
}

function registerIpc() {
  ipcMain.handle(IPC.NOTIFY, (_e, payload: NotifyPayload) => {
    if (!Notification.isSupported()) return false;
    const n = new Notification({
      title: payload.title,
      body: payload.body,
      silent: payload.silent ?? false,
    });
    n.on("click", () => {
      mainWindow?.show();
      mainWindow?.focus();
    });
    n.show();
    return true;
  });

  ipcMain.handle(IPC.OPEN_EXTERNAL, async (_e, url: string) => {
    await shell.openExternal(url);
  });

  ipcMain.handle(IPC.WINDOW_SHOW, () => {
    mainWindow?.show();
    mainWindow?.focus();
  });

  ipcMain.handle(IPC.WINDOW_HIDE, () => {
    mainWindow?.hide();
  });

  ipcMain.handle(IPC.PLATFORM, () => process.platform);
}

app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
});

app.whenReady().then(() => {
  registerIpc();
  createWindow();
  createTray();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    } else {
      mainWindow?.show();
    }
  });
});

app.on("window-all-closed", () => {
  // Don't quit; we keep running in the tray so notifications can still fire.
});

app.on("before-quit", () => {
  quittingFromTray = true;
});
