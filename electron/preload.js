const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    startLogin: () => ipcRenderer.invoke('start-login'),
    saveSession: () => ipcRenderer.invoke('save-session'),
    checkLogin: () => ipcRenderer.invoke('check-login'),
    runWow: () => ipcRenderer.invoke('run-wow'),
    runProducts: () => ipcRenderer.invoke('run-products'),
    selectFolder: () => ipcRenderer.invoke('select-folder'),
    runProject: (project, folder) => ipcRenderer.invoke('run-project', { project, folder }),
    onLog: (callback) => ipcRenderer.on('log', (_, data) => callback(data))
});
