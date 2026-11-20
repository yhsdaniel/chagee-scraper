const { contextBridge, ipcRenderer } = require('electron');

const electronBridge = {
    // Core project runners & session management (PRD §9)
    runProject: (project, folder) => ipcRenderer.invoke('run-project', { project, folder }),
    saveSession: () => ipcRenderer.invoke('save-session'),
    checkLogin: () => ipcRenderer.invoke('check-login'),
    logout: () => ipcRenderer.invoke('logout'),
    selectFolder: () => ipcRenderer.invoke('select-folder'),
    getVersion: () => ipcRenderer.invoke('get-version'),
    getUserDataPath: () => ipcRenderer.invoke('get-user-data-path'),

    // Auto updater controls (PRD §10)
    checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
    quitAndInstall: () => ipcRenderer.invoke('quit-and-install'),

    // Event listeners
    onLog: (callback) => {
        const listener = (_, data) => callback(data);
        ipcRenderer.on('log', listener);
        return () => ipcRenderer.removeListener('log', listener);
    },
    onUpdateAvailable: (callback) => {
        const listener = (_, version) => callback(version);
        ipcRenderer.on('update-available', listener);
        return () => ipcRenderer.removeListener('update-available', listener);
    },
    onUpdateProgress: (callback) => {
        const listener = (_, percent) => callback(percent);
        ipcRenderer.on('update-progress', listener);
        return () => ipcRenderer.removeListener('update-progress', listener);
    },
    onUpdateDownloaded: (callback) => {
        const listener = (_, info) => callback(info);
        ipcRenderer.on('update-downloaded', listener);
        return () => ipcRenderer.removeListener('update-downloaded', listener);
    },
    onUpdateReady: (callback) => {
        const listener = (_, info) => callback(info);
        ipcRenderer.on('update-downloaded', listener);
        return () => ipcRenderer.removeListener('update-downloaded', listener);
    }
};

contextBridge.exposeInMainWorld('electron', electronBridge);
contextBridge.exposeInMainWorld('electronAPI', electronBridge);
