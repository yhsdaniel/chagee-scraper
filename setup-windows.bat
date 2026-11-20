@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   CHAGEE Scraper - Setup Windows Environment (PRD §12)
echo ========================================================

:: 1. Cek Python / venv
if exist venv\Scripts\python.exe (
    set "PY_CMD=venv\Scripts\python.exe"
    echo [1/5] Menggunakan venv lokal: !PY_CMD!
) else if exist python\wow\venv\Scripts\python.exe (
    set "PY_CMD=python\wow\venv\Scripts\python.exe"
    echo [1/5] Menggunakan python\wow\venv: !PY_CMD!
) else if exist python\runtime\python.exe (
    set "PY_CMD=python\runtime\python.exe"
    echo [1/5] Menggunakan python\runtime: !PY_CMD!
) else (
    set "PY_CMD=python"
    echo [1/5] Menggunakan system python
)

:: 2. Install libs WOW
echo [2/5] Menyiapkan library untuk python/wow/libs...
"%PY_CMD%" -m pip install -r python\wow\requirements.txt --target python\wow\libs --only-binary :all: --no-warn-script-location

:: 3. Install libs Products
echo [3/5] Menyiapkan library untuk python\product\libs...
"%PY_CMD%" -m pip install -r python\product\requirements.txt --target python\product\libs --only-binary :all: --no-warn-script-location

:: 4. Install Chromium Playwright ke python/runtime/browsers
echo [4/5] Memeriksa browser Chromium di python/runtime/browsers...
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0python\runtime\browsers"
if not exist "%PLAYWRIGHT_BROWSERS_PATH%" mkdir "%PLAYWRIGHT_BROWSERS_PATH%"

"%PY_CMD%" -m playwright install chromium

:: 5. Verifikasi
echo [5/5] Melakukan verifikasi setup...
if exist python\wow\libs\gspread (
    echo   [OK] python\wow\libs\gspread ditemukan.
) else (
    echo   [WARN] python\wow\libs\gspread belum ditemukan!
)

if exist python\product\libs\pandas (
    echo   [OK] python\product\libs\pandas ditemukan.
) else (
    echo   [WARN] python\product\libs\pandas belum ditemukan!
)

if exist python\runtime\browsers (
    echo   [OK] python\runtime\browsers ditemukan.
)

echo.
echo ========================================================
echo   Setup selesai! Anda sekarang dapat menjalankan:
echo   - Dev mode     : npm run dev
echo   - Build Web    : npm run build:web
echo   - Build App    : npm run build:win
echo ========================================================
pause
