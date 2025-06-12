const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  showNotification: (title, body) => ipcRenderer.invoke('show-notification', { title, body }),
  openExternal: (url) => ipcRenderer.invoke('open-external', url)
});
