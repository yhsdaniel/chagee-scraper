# PRD — CHAGEE Scraper App (webapp-scraper)

## 1. Ringkasan Proyek
Aplikasi desktop Windows (Electron) untuk menjalankan berbagai scraper Python dengan **1x login, 1 session shared**.
User / client mendownload `.exe` dari website (link ke GitHub Releases), install, login 1x di browser, lalu bisa menjalankan scraper WOW dan Products tanpa install Python / venv / terminal.

- Nama repo: `webapp-scraper`
- Repo GitHub: `yhsdaniel/chagee-scraper` (contoh, sesuaikan)
- Platform target: Windows 10/11 64-bit
- Bahasa UI: Indonesia (user berbahasa Indonesia)
- User utama: client non-teknis (tidak tahu Python, venv, terminal)

## 2. Masalah yang Diselesaikan
- Sebelumnya scraper Python dijalankan dari terminal + `venv` + `input("tekan ENTER")` untuk save session.
- Setelah digabung ke Electron + React, `input()` tidak bisa dipakai (tidak ada terminal).
- Ada 2 folder scraper (`wow` dan `product`) yang sebelumnya login terpisah.
- Client tidak punya Python / venv, tidak boleh disuruh `pip install`.
- Versi app masih stuck di `1.0.4` karena auto-update tidak jalan / tidak ada versi baru.

## 3. Tujuan
1. 1 app desktop bisa menjalankan 5 job: Login, MTD, WOW, Products, Download store.
2. Login 1x, session dipakai bersama oleh `wow` dan `product`.
3. Client cukup download 1 file `.exe`, install, klik-klik saja.
4. Auto-update jalan saat buka app (Electron Updater via GitHub Releases).
5. Session tidak hilang saat auto-update.
6. Log Python tampil di UI React secara real-time.

## 4. Tech Stack — JANGAN DIGANTI TANPA ALASAN
- Frontend: React + Vite + Tailwind CSS
- Desktop shell: Electron + electron-builder + electron-updater
- Backend Python: Python 3.12 (embed untuk prod), Playwright (Chromium), gspread, python-dotenv
- Distribusi: GitHub Releases (file `.exe` + `latest.yml`). Vercel HANYA untuk landing page / preview web, BUKAN untuk distribusi `.exe` atau auto-update.
- Dev Python: `venv` di root project (`venv/Scripts/python.exe` di Windows)
- Prod Python: `python/runtime/python.exe` (Python 3.12 embed, dibundle via `extraResources`)

## 5. Struktur Folder — WAJIB SEPERTI INI

```
webapp-scraper/
  electron/
    main.js          # IPC, spawn Python, autoUpdater
    preload.js       # contextBridge
  src/
    App.jsx          # UI: Login, Run WOW, Run Products, Log viewer
  python/
    runtime/         # Python 3.12 embed (prod only, JANGAN commit venv ke sini)
      python.exe
      python312.dll
      python312._pth   # isi: python312.zip, ., Lib, import site
      browsers/        # Chromium Playwright (PLAYWRIGHT_BROWSERS_PATH)
    wow/
      login.py
      main.py          # WOW
      scraper-mtd.py   # MTD
      requirements.txt
      libs/            # hasil pip install --target libs (gspread, playwright, dll)
      .env             # atau pakai python/shared/.env
    product/
      main.py          # Products
      download.py      # Download store
      requirements.txt
      libs/
      .env
    shared/
      .env             # DASHBOARD_URL, dll (1 file saja)
  package.json
  vite.config.js
  setup-windows.bat  # helper setup di Windows
```

### Aturan Struktur
- JANGAN taruh `.env` di root project. Pakai `python/shared/.env` atau `python/<folder>/.env`.
- JANGAN taruh `storage_state.json` di root project. Session disimpan di `userData` (lihat §7).
- JANGAN commit `venv/`, `node_modules/`, `dist/`, `release/`, `python/runtime/browsers/` yang besar jika tidak perlu — tapi `extraResources` harus tetap include `python/**` saat build.
- `login.py` HANYA ada di `python/wow/login.py`. Jangan duplikasi di `product/`.
- Nama folder di disk adalah `wow` dan `product` (lowercase, singular). Jangan rename jadi `WOW-to-GS` / `Products` tanpa update `SCRIPT_MAP`.

## 6. Mapping Job (Kontrak Utama)

File: `electron/main.js` — `SCRIPT_MAP` adalah source of truth.

```js
const SCRIPT_MAP = {
    'Login': { dir: 'wow', script: 'login.py' },
    'MTD': { dir: 'wow', script: 'scraper-mtd.py' },
    'WOW': { dir: 'wow', script: 'main.py' },
    'Products': { dir: 'product', script: 'main.py' },
    'Download store': { dir: 'product', script: 'download.py' },
};
```

- UI React hanya mengirim `{ project: 'Login' | 'MTD' | 'WOW' | 'Products' | 'Download store', folder?: string }` via `ipcRenderer.invoke('run-project', ...)`.
- `main.js` TIDAK boleh hardcode nama script di luar `SCRIPT_MAP`.
- Jika `project` tidak dikenal, kirim log `[ERROR] Unknown project` ke renderer dan return `{ status: 'error' }`.

## 7. Session / Login — Kontrak Paling Penting

### 7.1 Satu Session Shared
- URL dashboard `WOW` dan `Products` adalah **SAMA**.
- Login dilakukan **1x** saja.
- Session disimpan di **1 file shared**: `<userData>/shared_storage_state.json`
  - `userData` = `app.getPath('userData')` (Electron). Contoh: `%APPDATA%/Chagee Scraper App/shared_storage_state.json`
  - Alasan pakai `userData`, bukan `resources/python/shared/`: file di `resources/` akan tertimpa saat auto-update. File di `userData` aman.
- `WOW`, `MTD`, `Products`, `Download store` semuanya membaca file yang sama.

### 7.2 Alur Login (Tanpa `input()` / ENTER)
`input()` DILARANG di semua script Python yang dijalankan via Electron, karena tidak ada terminal.
Alur yang benar:

1. React: klik `Buka Browser Login` -> `ipcRenderer.invoke('run-project', { project: 'Login' })`
2. `main.js`: spawn `python/wow/login.py` dengan arg `--storage <userData>/shared_storage_state.json --env <envPath>`
3. `login.py`: buka Chromium (headful), `page.goto(DASHBOARD_URL)`, lalu polling file trigger `python/wow/save.trigger` tiap 1 detik (bukan `input()`).
4. User login manual di browser.
5. User kembali ke app React, klik `Simpan Session` -> `ipcRenderer.invoke('save-session')` -> `main.js` menulis file `python/wow/save.trigger`.
6. `login.py` mendeteksi trigger, lalu `context.storage_state(path=<shared_storage>)`, hapus trigger, tutup browser.
7. React: `check-login` -> cek `fs.existsSync(shared_storage_state.json)` -> tampilkan `✅ Sudah Login`.

### 7.3 Migrasi Session Lama (Sekali Saja)
Jika `shared_storage_state.json` belum ada, `main.js` harus cek dan copy dari lokasi lama (jika ada), urutan:
1. `<userData>/wow_storage_state.json`
2. `<userData>/product_storage_state.json`
3. `<projectDir>/storage_state.json`
4. `<root>/storage_state.json` (legacy)

Jika ketemu, copy ke shared, kirim log `[MIGRASI] Session lama dipindahkan ke shared, tidak perlu login ulang`.

### 7.4 Kontrak Argumen Python
Semua script Python di `wow/` dan `product/` WAJIB menerima argumen ini (pakai `argparse`, `parse_known_args` agar tidak crash jika ada arg tambahan):

```
--storage <path>  # path ke shared_storage_state.json
--env <path>      # path ke .env
--folder <string> # opsional, folder kerja / filter
```

- Jika `--storage` tidak dikasih (dijalankan manual dari terminal), fallback ke `python/shared/storage_state.json`.
- Jika file storage tidak ada, script harus print `BELUM LOGIN! Klik Login dulu` dan exit dengan grace, bukan crash dengan traceback Playwright.

### 7.5 Kontrak `libs` di Python
Di baris paling atas setiap `main.py` / `login.py` / `scraper-mtd.py` / `download.py`, SEBELUM `import gspread` / `playwright`:

```python
import sys
from pathlib import Path
BASE = Path(__file__).parent
LIBS = BASE / "libs"
if str(LIBS) not in sys.path:
    sys.path.insert(0, str(LIBS))
```

Ini yang membuat script jalan di client tanpa `venv`.

## 8. Menjalankan Python — Dev vs Prod

### 8.1 Dev (laptop developer)
- Python: `venv/Scripts/python.exe` (Windows) / `venv/bin/python` (Mac/Linux)
- `isDev = process.env.IS_DEV` atau `!app.isPackaged`
- `basePath = path.join(__dirname, '../python')`

### 8.2 Prod (PC client, `.exe`)
- Python: `<resources>/python/runtime/python.exe` — JANGAN cari `venv`, JANGAN pakai string `'python'` / `'python3'` karena client tidak punya Python di PATH.
- `basePath = path.join(process.resourcesPath, 'python')`
- Jika `runtime/python.exe` tidak ada di prod, kirim log error jelas: `[ERROR] Runtime Python tidak ketemu: <path>. Build belum include python/runtime/` dan return error, jangan spawn `'python'`.
- Env saat spawn:
  ```
  PYTHONIOENCODING=utf-8
  PYTHONUTF8=1
  PYTHONUNBUFFERED=1
  PLAYWRIGHT_BROWSERS_PATH=<basePath>/runtime/browsers
  PYTHONPATH=<projectDir>/libs
  ```
- `cwd` = `projectDir` (misal `python/wow` atau `python/product`)
- Args: `['-u', scriptPath, '--folder', folder?, '--storage', storagePath, '--env', envPath?]`
- `stdout` / `stderr` di-forward ke renderer via `win.webContents.send('log', ...)` dengan prefix `[<project>]` dan `[<project> ERROR]`.
- `close` -> kirim log `[<project>] Finished with code: <code>`.

## 9. Electron Main — Spesifikasi `main.js`

- `app.whenReady()` -> `createWindow()` + `autoUpdater` (lihat §10).
- IPC yang harus ada:
  - `run-project` -> `(event, { project, folder })` -> spawn Python, return `{ status: 'running' | 'error', storagePath? }`
  - `save-session` -> tulis file `python/wow/save.trigger`, return `true`
  - `check-login` -> return `boolean` (apakah `shared_storage_state.json` ada)
  - `logout` (opsional) -> hapus `shared_storage_state.json`, return `true`
- `preload.js` harus expose via `contextBridge`:
  ```js
  window.electron = {
    runProject: (project, folder) => ipcRenderer.invoke('run-project', { project, folder }),
    saveSession: () => ipcRenderer.invoke('save-session'),
    checkLogin: () => ipcRenderer.invoke('check-login'),
    logout: () => ipcRenderer.invoke('logout'),
    onLog: (cb) => ipcRenderer.on('log', (e, msg) => cb(msg)),
  }
  ```
- `contextIsolation: true`, `nodeIntegration: false`, `preload` wajib.
- Jangan pakai `fs` / `child_process` langsung dari renderer.

## 10. Auto-Update

- Library: `electron-updater`
- Provider: GitHub Releases (repo di `package.json` -> `build.publish`)
- `package.json` harus punya:
  ```json
  "build": {
    "extraResources": [{ "from": "python", "to": "python", "filter": ["**/*"] }],
    "publish": [{ "provider": "github", "owner": "<owner>", "repo": "<repo>" }]
  }
  ```
- `filter: ["**/*"]` WAJIB, bukan `**/*.py` saja, agar `runtime/python.exe` + `runtime/browsers/` ikut ter-copy.
- Di `main.js`:
  ```js
  if (!isDev) {
    autoUpdater.autoDownload = true;
    autoUpdater.autoInstallOnAppQuit = true;
    autoUpdater.checkForUpdatesAndNotify();
  }
  autoUpdater.on('update-downloaded', () => autoUpdater.quitAndInstall());
  ```
- Aturan: auto-update HANYA jalan jika ada versi lebih baru di GitHub. Jika app `1.0.4` dan release terbaru juga `1.0.4`, tidak akan update. Untuk test, naikkan versi ke `1.0.5` via `npm version patch`, lalu `npm run release`, lalu buka app `1.0.4` lama.
- `latest.yml` harus ada di GitHub Releases, jika tidak ada auto-update tidak akan jalan.
- Session di `userData` tidak boleh terhapus saat update.

## 11. UI React — Spesifikasi `src/App.jsx`

- Header: nama app + versi (baca dari `package.json` via `app.getVersion()` / IPC jika perlu).
- Card Status Login: `✅ Sudah Login (shared)` / `❌ Belum Login` + path `shared_storage_state.json` (tampilkan path userData, bukan resources).
- Tombol:
  - `Buka Browser Login` (saat belum login / sedang login)
  - `Simpan Session ke Shared` (saat sedang login, setelah user login di browser)
  - `Jalankan WOW` / `Jalankan MTD` / `Jalankan Products` / `Jalankan Download store` — disabled jika belum login
  - `Logout` (hapus shared session, opsional)
- Log viewer: area scroll, tampilkan log dari `window.electron.onLog`, auto-scroll ke bawah, format `[WOW] ...`, `[Products ERROR] ...`.
- Semua tombol harus handle `disabled` saat job sedang running (opsional: tampilkan spinner).
- Bahasa UI: Indonesia.

## 12. Setup Windows (Developer)

File: `setup-windows.bat` di root — 1 klik untuk setup di Windows. Isi:
1. Aktivasi `venv`
2. `pip install -r python/wow/requirements.txt --target python/wow/libs --only-binary :all:`
3. `pip install -r python/product/requirements.txt --target python/product/libs --only-binary :all:`
4. `PLAYWRIGHT_BROWSERS_PATH=python/runtime/browsers` + `playwright install chromium`
5. Cek `python/wow/libs/gspread` dan `python/runtime/browsers/chromium-*` ada.

### Catatan Windows
- Gunakan `cmd`, bukan PowerShell, untuk setup (PowerShell sering gagal karena `.\` dan execution policy).
- `python/runtime/python312._pth` harus berisi:
  ```
  python312.zip
  .
  Lib
  import site
  ```
  Jika `import site` masih dikomentari (`# import site`), `pip` tidak akan jalan di Python embed.
- Jika install via `runtime/python.exe` gagal (`No module named pip`), fallback: install libs pakai `venv` (lihat `setup-windows.bat`), hasil sama.
- Jika error `python.exe is not recognized`, cek extract: jangan sampai `python/runtime/python-3.12.7-embed-amd64/python.exe` (double folder).

## 13. Build & Release

```powershell
# 1. Naikkan versi
npm version patch   # 1.0.4 -> 1.0.5

# 2. Build + publish ke GitHub Releases
$env:GH_TOKEN="ghp_xxxx"
npm run release
```

- Script `release` di `package.json` harus menjalankan `vite build` + `electron-builder --publish always` (atau sesuai setup yang ada, jangan ubah tanpa konfirmasi).
- Link download untuk client: `https://github.com/<owner>/<repo>/releases/latest` — JANGAN kirim link Vercel sebagai link download `.exe`.
- Setelah release, verifikasi di GitHub Releases ada: `CHAGEE-Scraper-Setup-1.0.5.exe` + `latest.yml`.

## 14. Alur Client (Acceptance Criteria)

1. Client buka website -> klik `Download untuk Windows` -> download `.exe` dari GitHub Releases.
2. Double-klik `.exe` -> Install -> Finish. Tidak perlu install Python / venv / pip.
3. Buka app -> status `❌ Belum Login`.
4. Klik `Buka Browser Login` -> browser Chromium terbuka -> login manual.
5. Kembali ke app, klik `Simpan Session ke Shared` -> status jadi `✅ Sudah Login`.
6. Klik `Jalankan WOW` -> log tampil, scraper jalan, tidak minta login lagi.
7. Klik `Jalankan Products` -> log tampil, scraper jalan, pakai session yang sama, tidak minta login lagi.
8. Tutup app, buka lagi -> masih `✅ Sudah Login`.
9. Ada release `1.0.6` -> buka app `1.0.5` -> auto-download -> tutup app -> buka lagi -> versi jadi `1.0.6`, session masih ada.

## 15. Yang Dilarang / Jangan Dilakukan

- JANGAN pakai `input()` di script Python yang dijalankan via Electron.
- JANGAN pakai `spawn('python')` / `spawn('python3')` di prod.
- JANGAN cari `venv` di PC client.
- JANGAN simpan session di `resources/python/shared/` (akan tertimpa auto-update).
- JANGAN simpan session per-folder (`wow_storage_state.json` + `product_storage_state.json`).
- JANGAN ganti `SCRIPT_MAP` tanpa update UI React.
- JANGAN ubah nama folder `wow` / `product` tanpa update `SCRIPT_MAP` + `package.json` + Python.
- JANGAN kirim link Vercel sebagai link download `.exe`.

## 16. Pertanyaan Terbuka untuk Developer (Isi Sebelum Coding)

- [ ] `DASHBOARD_URL` yang benar: ?
- [ ] `requirements.txt` untuk `wow` dan `product` isinya apa saja? (sertakan versi `playwright`, `gspread`, `python-dotenv`)
- [ ] `GH_TOKEN` dan repo GitHub yang benar: ?
- [ ] Apakah `scraper-mtd.py` dan `download.py` butuh `--folder`? Format `--folder` apa?
- [ ] Apakah ada Google Sheet / kredensial lain yang perlu dibundle? (jangan hardcode secret di PRD)
- [ ] Versi Electron / Node yang dipakai: ?

## 17. File yang Harus Dibaca AI Agent Pertama Kali

1. `electron/main.js` — kontrak `SCRIPT_MAP` + `run-project` + `autoUpdater`
2. `electron/preload.js`
3. `src/App.jsx`
4. `package.json` — `build.extraResources` + `build.publish` + scripts
5. `python/wow/login.py` — alur login + trigger
6. `python/wow/main.py` + `python/product/main.py` — cara baca `--storage` + `libs`
7. `python/shared/.env` — `DASHBOARD_URL`

---
*PRD ini dibuat untuk di-input ke Antigravity IDE. AI agent harus membaca PRD ini dulu sebelum mengubah code, dan tidak boleh mengubah kontrak di §6, §7, §8 tanpa konfirmasi user.*
