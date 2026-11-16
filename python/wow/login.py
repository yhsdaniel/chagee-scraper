"""
export_login_state.py
----------------------
Jalankan script ini SEKALI secara manual untuk login ke dashboard via browser
yang dibuka otomatis. Setelah kamu login manual (termasuk kalau ada SSO/2FA),
tekan ENTER di terminal, dan session/cookie/local storage akan disimpan ke
storage_state.json. File ini lalu dipakai oleh scraper.py supaya TIDAK perlu
login ulang setiap kali scraping (selama token belum expired).

Cara pakai:
    python export_login_state.py
"""

import os, time
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# BASE = python/WOW-to-GS
BASE = Path(__file__).parent
PYTHON_DIR = BASE.parent
SHARED_DIR = PYTHON_DIR / "shared"
SHARED_DIR.mkdir(parents=True, exist_ok=True)

# load .env dari shared, fallback ke .env lokal kalau ada
load_dotenv(SHARED_DIR / ".env")
load_dotenv(BASE / ".env")

DASHBOARD_URL = os.getenv("DASHBOARD_URL")
STORAGE_STATE_FILE = SHARED_DIR / "storage_state.json"
TRIGGER_FILE = BASE / "save.trigger"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def main():
    if TRIGGER_FILE.exists():
        TRIGGER_FILE.unlink()

    with sync_playwright() as p:
        # headless=False supaya browser terlihat dan kamu bisa login manual
        browser = p.chromium.launch(
            channel='chrome', 
            headless=False,
            args=[
                "--start-maximized",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process" 
            ]
        )
        # 1. Siapkan argumen context
        context_args = {
            "no_viewport": True,
            "user_agent": USER_AGENT,
        }
        context = browser.new_context(**context_args)
        page = context.new_page()

        print(f"Membuka {DASHBOARD_URL} ...")
        page.goto(DASHBOARD_URL)

        print("\n>>> Silakan login manual di jendela browser yang terbuka.")
        # ganti input() -> nunggu trigger dari React
        while True:
            if TRIGGER_FILE.exists():
                print(">>> Trigger diterima, menyimpan session...", flush=True)
                break
            if not browser.is_connected():
                print(">>> Browser ditutup, batal.", flush=True)
                return
            time.sleep(1)

        # SIMPAN CUMA 1x KE SHARED
        context.storage_state(path=str(STORAGE_STATE_FILE))
        print(f"Session tersimpan di: {STORAGE_STATE_FILE}", flush=True)

        if TRIGGER_FILE.exists():
            TRIGGER_FILE.unlink()

        browser.close()


if __name__ == "__main__":
    main()