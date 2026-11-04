const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    selectFolder: () => ipcRenderer.invoke('select-folder'),
    runProject: (project, folder) => ipcRenderer.invoke('run-project', { project, folder }),
    onLog: (callback) => ipcRenderer.on('log', (_, data) => callback(data)),
    onUpdateReady: (callback) => {
        ipcRenderer.on('update-ready', () => callback())
    },
    checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
    quitAndInstall: () => ipcRenderer.invoke('quit-and-install')
});

