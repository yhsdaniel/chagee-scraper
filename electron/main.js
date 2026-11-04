import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import electronUpdater from 'electron-updater';

const { autoUpdater } = electronUpdater;
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let win;

function createWindow() {
    const preloadPath = fs.existsSync(path.join(__dirname, 'preload.cjs'))
        ? path.join(__dirname, 'preload.cjs')
        : path.join(__dirname, 'preload.js');

    win = new BrowserWindow({
        width: 1100, height: 800,
        webPreferences: {
            preload: preloadPath,
            contextIsolation: true,
            nodeIntegration: false
        }
    });

    if (process.env.IS_DEV) {
        win.loadURL('http://localhost:5173');
    } else {
        win.loadFile(path.join(__dirname, '../dist/index.html'));
    }
}

app.whenReady().then(() => {
    createWindow();
    autoUpdater.checkForUpdatesAndNotify();
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});

ipcMain.handle('select-folder', async () => {
    const { filePaths } = await dialog.showOpenDialog({ properties: ['openDirectory'] });
    return filePaths[0];
});

// Mapping: button name -> { pythonProject folder, script filename }
const SCRIPT_MAP = {
    'Login': { dir: 'WOW to Gsheets', script: 'login.py' },
    'MTD': { dir: 'WOW to Gsheets', script: 'scraper-mtd.py' },
    'WOW': { dir: 'WOW to Gsheets', script: 'main.py' },
    'Products': { dir: 'Products to Gsheets', script: 'main.py' },
    'Download store': { dir: 'Products to Gsheets', script: 'download.py' },
};

ipcMain.handle('run-project', async (event, { project, folder }) => {
    const isDev = process.env.IS_DEV;
    const basePath = isDev ? path.join(__dirname, '../python') : path.join(process.resourcesPath, 'python');

    // Resolve which directory and script to use
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

    // Session storage in writable AppData
    const userDataPath = app.getPath('userData');
    if (!fs.existsSync(userDataPath)) fs.mkdirSync(userDataPath, { recursive: true });

    const storagePath = path.join(userDataPath, `${mapping.dir}_storage_state.json`);
    const envPath = path.join(projectDir, '.env');

    console.log(`[DEBUG] project="${project}" -> ${mapping.dir}/${mapping.script}`);
    console.log(`[DEBUG] Using storage: ${storagePath} (exists: ${fs.existsSync(storagePath)})`);

    // Detect Python venv
    const candidates = process.platform === 'win32'
        ? [
            path.join(projectDir, 'venv', 'Scripts', 'python.exe'),
            path.join(projectDir, '.venv', 'Scripts', 'python.exe'),
            'python'
        ]
        : [
            path.join(projectDir, 'venv', 'bin', 'python'),
            path.join(projectDir, '.venv', 'bin', 'python'),
            'python3'
        ];

    const pythonPath = candidates.find(c => !c.includes(path.sep) || fs.existsSync(c)) || candidates[0];
    console.log(`[DEBUG] Python: ${pythonPath}`);

    const args = ['-u', scriptPath];

    if (folder) {
        args.push('--folder', folder);
    }
    if (storagePath) {
        args.push('--storage', storagePath);
    }
    if (fs.existsSync(envPath)) {
        args.push('--env', envPath);
    }

    // Auto-migrate old session file from project dir to AppData
    const oldStoragePath = path.join(projectDir, 'storage_state.json');
    if (fs.existsSync(oldStoragePath) && !fs.existsSync(storagePath)) {
        try {
            fs.copyFileSync(oldStoragePath, storagePath);
            console.log(`[MIGRASI] Copy session lama: ${oldStoragePath} -> ${storagePath}`);
            win?.webContents.send('log', `[MIGRASI] Session lama dipindahkan, tidak perlu login ulang`);
        } catch (e) {
            console.log(`[MIGRASI GAGAL] ${e.message}`);
        }
    }

    console.log(`[DEBUG] Spawning: ${pythonPath} ${args.join(' ')}`);

    const py = spawn(pythonPath, args, {
        cwd: projectDir,
        env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' }
    });

    py.stdout.on('data', (data) => win?.webContents.send('log', `[${project}] ${data}`));
    py.stderr.on('data', (data) => win?.webContents.send('log', `[${project} ERROR] ${data}`));
    py.on('error', (err) => {
        win?.webContents.send('log', `[${project} SYSTEM ERROR] ${err.message}\nPython path: ${pythonPath}`);
    });
    py.on('close', (code) => {
        win?.webContents.send('log', `[${project}] Finished with code: ${code}`);
    });

    return { status: 'running', storagePath };
});