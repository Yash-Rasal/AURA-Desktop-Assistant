const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("companion", {
  getBackendUrl: () => ipcRenderer.invoke("get-backend-url"),
  showWindow: () => ipcRenderer.send("show-window"),
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
  onHotkeyScreenshot: (cb) => ipcRenderer.on("hotkey-screenshot", cb),
  onHotkeyVoice: (cb) => ipcRenderer.on("hotkey-voice", cb),
});
