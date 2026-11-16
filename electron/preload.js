const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    selectFolder: () => ipcRenderer.invoke('select-folder'),
    runProject: (project, folder) => ipcRenderer.invoke('run-project', { project, folder }),
    onLog: (callback) => ipcRenderer.on('log', (_, data) => callback(data))
});
