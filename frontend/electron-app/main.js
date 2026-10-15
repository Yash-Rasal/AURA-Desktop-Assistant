const {
  app,
  BrowserWindow,
  globalShortcut,
  ipcMain,
  Tray,
  Menu,
  nativeImage,
  shell,
} = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");
const http = require("http");

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8765";
const PROJECT_ROOT = path.resolve(__dirname, "..", "..");
let mainWindow = null;
let tray = null;
let pythonProcess = null;

function createTrayIcon() {
  return nativeImage.createEmpty();
}

function showWindow() {
  if (mainWindow) {
    if (!mainWindow.isVisible()) {
      mainWindow.show();
    }
    mainWindow.focus();
    return true;
  }
  return false;
}

function createWindow() {
  if (showWindow()) return;

  mainWindow = new BrowserWindow({
    width: 420,
    height: 560,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: false,
    resizable: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));

  // Open the DevTools automatically in a separate window so you can inspect it
  mainWindow.webContents.openDevTools({ mode: 'detach' });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.on("close", (e) => {
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function registerHotkeys() {
  globalShortcut.register("Control+Alt+A", () => {
    if (mainWindow && mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      createWindow();
      showWindow();
    }
  });

  const sendHotkey = (event) => {
    if (!mainWindow) createWindow();
    showWindow();
    if (mainWindow.webContents.isLoading()) {
      mainWindow.webContents.once("did-finish-load", () => {
        mainWindow.webContents.send(event);
      });
    } else {
      mainWindow.webContents.send(event);
    }
  };

  globalShortcut.register("Control+Alt+S", () => sendHotkey("hotkey-screenshot"));
  globalShortcut.register("Control+Alt+V", () => sendHotkey("hotkey-voice"));
}

function createTray() {
  tray = new Tray(createTrayIcon());
  const menu = Menu.buildFromTemplate([
    { label: "Open Companion (Ctrl+Alt+A)", click: () => { createWindow(); showWindow(); } },
    { type: "separator" },
    {
      label: "Quit",
      click: () => {
        app.isQuitting = true;
        app.quit();
      },
    },
  ]);
  tray.setToolTip("Desktop AI Companion");
  tray.setContextMenu(menu);
  tray.on("double-click", () => { createWindow(); showWindow(); });
}

function startBackend() {
  if (process.env.SKIP_BACKEND === "1") return;

  const req = http.get(`${BACKEND_URL}/health`, (res) => {
    if (res.statusCode === 200) {
      console.log("Backend is already running on port 8765.");
    }
  });

  req.on("error", () => {
    if (process.platform === "win32") {
      const { execSync } = require("child_process");
      try {
        execSync(
          'powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \\"name like \'python%\'\\" | Where-Object { $_.CommandLine -like \'*backend*run.py*\' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"',
          { stdio: "ignore" }
        );
      } catch (e) {}
    }

    const venvPython = path.join(PROJECT_ROOT, "backend", ".venv", "Scripts", "python.exe");
    const pythonCmd = fs.existsSync(venvPython) ? venvPython : "python";
    const runScript = path.join(PROJECT_ROOT, "backend", "run.py");

    const logsDir = path.join(PROJECT_ROOT, "data", "logs");
    if (!fs.existsSync(logsDir)) {
      fs.mkdirSync(logsDir, { recursive: true });
    }
    const logFile = fs.openSync(path.join(logsDir, "backend.log"), "a");

    pythonProcess = spawn(pythonCmd, [runScript], {
      cwd: path.join(PROJECT_ROOT, "backend"),
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
      stdio: ["ignore", logFile, logFile],
      windowsHide: true,
    });

    pythonProcess.on("error", (err) => {
      console.error("Failed to start Python backend:", err.message);
    });
  });
}

function stopBackend() {
  if (pythonProcess && !pythonProcess.killed) {
    if (process.platform === "win32") {
      const { execSync } = require("child_process");
      try {
        execSync(`taskkill /PID ${pythonProcess.pid} /T /F`);
      } catch (e) {
        // process might already be dead
      }
    } else {
      pythonProcess.kill();
    }
  }
}

let ollamaProcess = null;

function ensureOllama() {
  const req = http.get("http://127.0.0.1:11434/api/tags", (res) => {
    if (res.statusCode === 200) {
      console.log("Ollama is already running.");
    }
  });

  req.on("error", () => {
    console.log("Ollama not running. Starting Ollama daemon...");
    const localOllama = process.env.LOCALAPPDATA
      ? path.join(process.env.LOCALAPPDATA, "Programs", "Ollama", "ollama.exe")
      : "ollama";
    const ollamaBin = fs.existsSync(localOllama) ? localOllama : "ollama";

    try {
      ollamaProcess = spawn(ollamaBin, ["serve"], {
        detached: true,
        stdio: "ignore",
        windowsHide: true,
      });
      ollamaProcess.on("error", (err) => {
        console.error("Failed to auto-start Ollama:", err.message);
      });
      ollamaProcess.unref();
    } catch (e) {
      console.error("Failed to start Ollama:", e.message);
    }
  });
}

const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    } else {
      createWindow();
      showWindow();
    }
  });

  app.whenReady().then(() => {
    ensureOllama();
    startBackend();
    createTray();
    registerHotkeys();
    createWindow();
  });
}

app.on("before-quit", () => {
  app.isQuitting = true;
  stopBackend();
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
  stopBackend();
});

app.on("window-all-closed", (e) => {
  e.preventDefault();
});

ipcMain.handle("get-backend-url", () => BACKEND_URL);
ipcMain.handle("open-external", (_e, url) => shell.openExternal(url));
ipcMain.on("show-window", () => {
  if (!mainWindow) createWindow();
  showWindow();
});
