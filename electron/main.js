import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import pkg from 'electron-updater';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const isDev = !!process.env.IS_DEV || !app.isPackaged;
const { autoUpdater } = pkg;

let win = null;

function createWindow() {
    const preloadPath = fs.existsSync(path.join(__dirname, 'preload.cjs'))
        ? path.join(__dirname, 'preload.cjs')
        : path.join(__dirname, 'preload.js');

    win = new BrowserWindow({
        width: 1200,
        height: 850,
        minWidth: 900,
        minHeight: 650,
        show: false,
        backgroundColor: '#0f172a',
        webPreferences: {
            preload: preloadPath,
            contextIsolation: true,
            nodeIntegration: false
        }
    });

    if (isDev && process.env.IS_DEV) {
        win.loadURL('http://localhost:5173');
    } else {
        win.loadFile(path.join(__dirname, '../dist/index.html'));
    }

    win.once('ready-to-show', () => {
        win.show();
    });

    win.webContents.on('did-fail-load', (e, code, desc) => {
        console.error('FAILED LOAD:', code, desc);
    });

    return win;
}

// Auto updater setup (PRD §10)
function initAutoUpdater() {
    if (isDev && process.env.IS_DEV) {
        console.log('[AutoUpdater] Development mode: skipped auto-check');
        return;
    }

    try {
        autoUpdater.autoDownload = true;
        autoUpdater.autoInstallOnAppQuit = true;

        autoUpdater.on('update-available', (info) => {
            console.log('Update tersedia:', info.version);
            win?.webContents.send('update-available', info.version);
            win?.webContents.send('log', `[AUTO-UPDATE] Update versi ${info.version} ditemukan, sedang mengunduh...`);
        });

        autoUpdater.on('download-progress', (progress) => {
            win?.webContents.send('update-progress', Math.round(progress.percent));
        });

        autoUpdater.on('update-downloaded', (info) => {
            console.log('Update selesai diunduh:', info.version);
            win?.webContents.send('update-downloaded', info.version);
            win?.webContents.send('log', `[AUTO-UPDATE] Versi ${info.version} selesai diunduh.`);

            if (win) {
                const choice = dialog.showMessageBoxSync(win, {
                    type: 'info',
                    title: 'Update Tersedia',
                    message: `Versi ${info.version} telah selesai diunduh. Restart aplikasi sekarang untuk menerapkan update?`,
                    buttons: ['Restart Sekarang', 'Nanti']
                });
                if (choice === 0) {
                    autoUpdater.quitAndInstall();
                }
            }
        });

        autoUpdater.on('error', (err) => {
            console.error('Auto-update error:', err);
            win?.webContents.send('log', `[AUTO-UPDATE ERROR] ${err?.message || err}`);
        });

        autoUpdater.checkForUpdatesAndNotify();
    } catch (err) {
        console.error('Failed to initialize auto updater:', err);
    }
}

app.whenReady().then(() => {
    createWindow();
    initAutoUpdater();
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});

// Mapping: button name -> { pythonProject folder, script filename } (PRD §6)
const SCRIPT_MAP = {
    'Login': { dir: 'wow', script: 'login.py' },
    'MTD': { dir: 'wow', script: 'scraper-mtd.py' },
    'WOW': { dir: 'wow', script: 'main.py' },
    'Products': { dir: 'product', script: 'main.py' },
    'Download store': { dir: 'product', script: 'download.py' },
};

function getPythonExe(basePath) {
    if (isDev) {
        const devCandidates = process.platform === 'win32'
            ? [
                path.join(__dirname, '../venv/Scripts/python.exe'),
                path.join(__dirname, '../python/wow/venv/Scripts/python.exe'),
                path.join(__dirname, '../python/product/.venv/Scripts/python.exe'),
                path.join(basePath, 'runtime', 'python.exe')
            ]
            : [
                path.join(__dirname, '../venv/bin/python'),
                path.join(basePath, 'runtime', 'bin', 'python3')
            ];

        for (const candidate of devCandidates) {
            if (fs.existsSync(candidate)) {
                return candidate;
            }
        }
    }

    // DI CLIENT (PROD): selalu pakai python embed di extraResources (PRD §8.2)
    return path.join(basePath, 'runtime', 'python.exe');
}

function getSharedStoragePath() {
    const userDataPath = app.getPath('userData');
    if (!fs.existsSync(userDataPath)) {
        fs.mkdirSync(userDataPath, { recursive: true });
    }
    return path.join(userDataPath, 'storage_state.json');
}

// Session migration helper (PRD §7.3)
function migrateOldSessionIfNeeded(storagePath, basePath) {
    if (fs.existsSync(storagePath)) return;

    const userDataPath = app.getPath('userData');
    const oldCandidates = [
        path.join(userDataPath, 'wow_storage_state.json'),
        path.join(userDataPath, 'product_storage_state.json'),
        path.join(basePath, 'shared', 'storage_state.json'),
        path.join(basePath, 'wow', 'storage_state.json'),
        path.join(basePath, 'product', 'storage_state.json')
    ];

    for (const oldFile of oldCandidates) {
        if (fs.existsSync(oldFile)) {
            try {
                fs.copyFileSync(oldFile, storagePath);
                console.log(`[MIGRASI] Copy session lama: ${oldFile} -> ${storagePath}`);
                win?.webContents.send('log', `[MIGRASI] Session lama dipindahkan ke shared, tidak perlu login ulang`);
                break;
            } catch (e) {
                console.error(`[MIGRASI GAGAL] ${e.message}`);
            }
        }
    }
}

// IPC Handlers
ipcMain.handle('select-folder', async () => {
    const { filePaths } = await dialog.showOpenDialog({ properties: ['openDirectory'] });
    return filePaths?.[0] || '';
});

ipcMain.handle('get-version', () => app.getVersion());

ipcMain.handle('get-user-data-path', () => {
    const storagePath = getSharedStoragePath();
    return {
        userData: app.getPath('userData'),
        storagePath: storagePath
    };
});

ipcMain.handle('check-login', () => {
    const basePath = isDev ? path.join(__dirname, '../python') : path.join(process.resourcesPath, 'python');
    const storagePath = getSharedStoragePath();
    migrateOldSessionIfNeeded(storagePath, basePath);
    return fs.existsSync(storagePath);
});

ipcMain.handle('save-session', () => {
    const basePath = isDev ? path.join(__dirname, '../python') : path.join(process.resourcesPath, 'python');
    const trigger = path.join(basePath, 'wow', 'save.trigger');
    try {
        fs.writeFileSync(trigger, 'save');
        win?.webContents.send('log', '[IPC] Trigger save-session dikirim ke login.py');
        return true;
    } catch (e) {
        win?.webContents.send('log', `[IPC ERROR] Gagal mengirim trigger: ${e.message}`);
        return false;
    }
});

ipcMain.handle('logout', () => {
    const storagePath = getSharedStoragePath();
    if (fs.existsSync(storagePath)) {
        try {
            fs.unlinkSync(storagePath);
            win?.webContents.send('log', '[IPC] Berhasil logout. Shared session dihapus.');
            return true;
        } catch (e) {
            win?.webContents.send('log', `[IPC ERROR] Gagal menghapus session: ${e.message}`);
            return false;
        }
    }
    return true;
});

ipcMain.handle('check-for-updates', () => {
    if (!isDev) {
        autoUpdater.checkForUpdatesAndNotify();
    }
    return true;
});

ipcMain.handle('quit-and-install', () => {
    autoUpdater.quitAndInstall();
    return true;
});

ipcMain.handle('run-project', async (event, { project, folder }) => {
    const basePath = isDev ? path.join(__dirname, '../python') : path.join(process.resourcesPath, 'python');

    const mapping = SCRIPT_MAP[project];
    if (!mapping) {
        const msg = `[ERROR] Unknown project: "${project}". Valid: ${Object.keys(SCRIPT_MAP).join(', ')}`;
        win?.webContents.send('log', msg);
        return { status: 'error', message: msg };
    }

    const projectDir = path.join(basePath, mapping.dir);
    const scriptPath = path.join(projectDir, mapping.script);

    if (!fs.existsSync(scriptPath)) {
        const msg = `[ERROR] Script not found: ${scriptPath}`;
        win?.webContents.send('log', msg);
        return { status: 'error', message: msg };
    }

    const storagePath = getSharedStoragePath();
    migrateOldSessionIfNeeded(storagePath, basePath);

    // Cari .env di shared atau project folder
    const envShared = path.join(basePath, 'shared', '.env');
    const envProject = path.join(projectDir, '.env');
    const envPath = fs.existsSync(envShared) ? envShared : (fs.existsSync(envProject) ? envProject : null);

    const pythonPath = getPythonExe(basePath);
    console.log(`[DEBUG] project="${project}" -> ${mapping.dir}/${mapping.script}`);
    console.log(`[DEBUG] Python executable: ${pythonPath}`);
    console.log(`[DEBUG] Storage path: ${storagePath}`);

    if (!fs.existsSync(pythonPath)) {
        const msg = `[ERROR] Runtime Python tidak ketemu: ${pythonPath}. Pastikan runtime telah terpasang dengan benar.`;
        win?.webContents.send('log', msg);
        return { status: 'error', message: msg };
    }

    const args = ['-u', scriptPath, '--storage', storagePath];
    if (folder) {
        args.push('--folder', folder);
    }
    if (envPath) {
        args.push('--env', envPath);
    }

    win?.webContents.send('log', `[${project}] Memulai proses dengan Python: ${pythonPath}`);

    const py = spawn(pythonPath, args, {
        cwd: projectDir,
        env: {
            ...process.env,
            PYTHONIOENCODING: 'utf-8',
            PYTHONUTF8: '1',
            PYTHONUNBUFFERED: '1',
            PLAYWRIGHT_BROWSERS_PATH: path.join(basePath, 'runtime', 'browsers'),
            PYTHONPATH: path.join(projectDir, 'libs'),
        }
    });

    py.stdout.on('data', (data) => {
        win?.webContents.send('log', `[${project}] ${data.toString()}`);
    });

    py.stderr.on('data', (data) => {
        win?.webContents.send('log', `[${project} ERROR] ${data.toString()}`);
    });

    py.on('error', (err) => {
        win?.webContents.send('log', `[${project} SYSTEM ERROR] ${err.message}\nPython path: ${pythonPath}`);
    });

    py.on('close', (code) => {
        win?.webContents.send('log', `[${project}] Selesai dengan exit code: ${code}`);
    });

    return { status: 'running', storagePath };
});
