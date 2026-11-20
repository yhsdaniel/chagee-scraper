import sys
import os
import time
import argparse
from pathlib import Path

BASE = Path(__file__).resolve().parent
LIBS = BASE / "libs"
if str(LIBS) not in sys.path:
    sys.path.insert(0, str(LIBS))

# Parse CLI arguments (PRD §7.4)
parser = argparse.ArgumentParser(description="CHAGEE Scraper Login Automation")
parser.add_argument('--storage', default=None, help='Path ke storage_state.json')
parser.add_argument('--env', default=None, help='Path ke .env')
parser.add_argument('--folder', default=None, help='Folder kerja / target')
args, _ = parser.parse_known_args()

# Fallback ke python/shared/storage_state.json jika dijalankan manual
STORAGE_STATE_FILE = Path(args.storage).resolve() if args.storage else (BASE.parent / "shared" / "storage_state.json")

# Hapus trigger lama jika ada
TRIGGER = BASE / "save.trigger"
if TRIGGER.exists():
    try:
        TRIGGER.unlink()
    except Exception:
        pass

# Muat environment variables
from dotenv import load_dotenv

if args.env and Path(args.env).exists():
    load_dotenv(args.env)
else:
    shared_env = BASE.parent / "shared" / ".env"
    if shared_env.exists():
        load_dotenv(shared_env)
    local_env = BASE / ".env"
    if local_env.exists():
        load_dotenv(local_env)

from playwright.sync_api import sync_playwright

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://bi.chagee.com")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def main():
    print(f"[LOGIN] Membuka URL: {DASHBOARD_URL}")
    print(f"[LOGIN] Target session storage: {STORAGE_STATE_FILE}")

    with sync_playwright() as p:
        launch_args = [
            "--start-maximized",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process"
        ]

        # Coba buka via channel 'chrome' (jika ada Chrome), fallback ke Chromium bawaan
        try:
            browser = p.chromium.launch(
                channel='chrome',
                headless=False,
                args=launch_args
            )
        except Exception:
            browser = p.chromium.launch(
                headless=False,
                args=launch_args
            )

        context_args = {
            "no_viewport": True,
            "user_agent": USER_AGENT,
        }

        # Jika sudah pernah login sebelumnya, muat session agar user tidak selalu scan ulang jika token masih aktif
        if STORAGE_STATE_FILE.exists():
            print(f"[LOGIN] Memuat session existing dari: {STORAGE_STATE_FILE}")
            context_args["storage_state"] = str(STORAGE_STATE_FILE)

        context = browser.new_context(**context_args)
        page = context.new_page()

        try:
            page.goto(DASHBOARD_URL)
        except Exception as e:
            print(f"[LOGIN ERROR] Gagal membuka URL: {e}")

        print("\n>>> Silakan lakukan login di jendela browser yang terbuka.")
        print(">>> Setelah login selesai, klik 'Simpan Session' di aplikasi desktop.")
        print(f">>> Menunggu trigger simpan dari aplikasi...")

        # Polling trigger file (PRD §7.2 - tanpa input() / terminal)
        while True:
            if TRIGGER.exists():
                print("[LOGIN] Trigger 'save.trigger' terdeteksi! Menyimpan session...")
                break
            time.sleep(1)

        # Pastikan parent folder ada
        STORAGE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(STORAGE_STATE_FILE))

        try:
            TRIGGER.unlink()
        except Exception:
            pass

        print(f"✅ Session berhasil disimpan di: {STORAGE_STATE_FILE}")
        browser.close()


if __name__ == "__main__":
    main()
