import sys
import os
import re
import json
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
LIBS = BASE / "libs"
if str(LIBS) not in sys.path:
    sys.path.insert(0, str(LIBS))

# Parse CLI arguments (PRD §7.4)
parser = argparse.ArgumentParser(description="CHAGEE Product Store Downloader")
parser.add_argument('--storage', default=None, help='Path ke storage_state.json')
parser.add_argument('--env', default=None, help='Path ke .env')
parser.add_argument('--folder', default=None, help='Folder tujuan download store')
args, _ = parser.parse_known_args()

STORAGE_STATE_FILE = Path(args.storage).resolve() if args.storage else (BASE.parent / "shared" / "storage_state.json")

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

# Verifikasi session login
if not STORAGE_STATE_FILE.exists():
    print(f"BELUM LOGIN! File session tidak ditemukan di: {STORAGE_STATE_FILE}")
    print("Silakan klik 'Buka Browser Login' dan simpan session terlebih dahulu.")
    sys.exit(0)

import gspread
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://bi.chagee.com")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEET_TAB = os.getenv("GOOGLE_SHEET_TAB", "Sheet1")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

IFRAME_URL_CONTAINS = "bwcj"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

TARGET_STORES = [
    "CHAGEE ID 23 Paskal Bandung",
    "CHAGEE ID AEON Mall BSD",
    "CHAGEE ID Ciputra Mall Jakarta",
    "CHAGEE ID Flavor Bliss",
    "CHAGEE ID Lippo Icon Gajah Mada",
    "CHAGEE ID Lippo Mall Puri",
    "CHAGEE ID Mall Ciputra Tangerang",
    "CHAGEE ID Puri Indah Mall",
    "CHAGEE ID Paris Van Java",
    "CHAGEE ID Summarecon Mall Bandung",
    "CHAGEE ID Summarecon Mall Serpong",
    "CHAGEE ID Supermall Karawaci",
    "CHAGEE ID TangCity",
    "CHAGEE ID The Breeze BSD",
    "CHAGEE ID Trans Studio Mall Bandung",
]


def get_target_frame(page):
    if not IFRAME_URL_CONTAINS:
        return page

    for frame in page.frames:
        if IFRAME_URL_CONTAINS.lower() in frame.url.lower():
            return frame

    print("PERINGATAN: iframe dengan keyword tersebut tidak ditemukan, fallback ke main page.")
    return page


def set_date_range(page):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    print(f"Memilih tanggal di kalender: {start_str} hingga {end_str}...")

    try:
        iframe = page.locator("iframe").content_frame

        print(f" -> Mencari dan mengeklik Start Date: {start_str}")
        iframe.locator("#component-loader-dcdd53ca-3b74-4971-b1b7-7caa29f791b5 > .component-wrapper > .query-component > .query-fields-wrapper > .query-fields-container > div > .query-field > .query-item > .query-datetime > .quick-range-datetime > .ant-picker > .ant-picker-input.ant-picker-input-active > input").first.click()
        page.wait_for_timeout(1000)

        start_cell = iframe.get_by_role("cell", name=start_date.strftime("%#d"), exact=True, description=start_str).first

        if not start_cell.is_visible():
            prev_btn = page.locator("iframe").content_frame.locator("iframe").content_frame.get_by_role("button").filter(has_text=re.compile(r"^$")).nth(1).first
            if prev_btn.is_visible():
                prev_btn.click()
                page.wait_for_timeout(1000)

        start_cell.click(force=True)
        page.wait_for_timeout(1000)

        print(f" -> Mencari dan mengeklik End Date: {end_str}")
        end_cell = iframe.get_by_role("cell", name=end_date.strftime("%#d"), exact=True, description=end_str).first

        if not end_cell.is_visible():
            next_btn = page.locator("iframe").content_frame.locator("iframe").content_frame.get_by_role("button").filter(has_text=re.compile(r"^$")).nth(2).last
            if next_btn.is_visible():
                next_btn.click()
                page.wait_for_timeout(1000)

        end_cell.click(force=True)
        page.wait_for_timeout(1000)

        ok_btn = page.locator("iframe").content_frame.locator('.ant-picker-ok button')
        if ok_btn.is_visible():
            ok_btn.click()
        else:
            page.keyboard.press("Escape")

    except Exception as e:
        print(f"Error saat mengeklik tanggal di kalender: {e}")


def scrape_dashboard():
    with sync_playwright() as p:
        launch_args = [
            "--start-maximized",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process"
        ]

        try:
            browser = p.chromium.launch(
                channel="chrome",
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
            "storage_state": str(STORAGE_STATE_FILE)
        }

        print(f"Memuat session dari {STORAGE_STATE_FILE} ...")
        context = browser.new_context(**context_args)
        page = context.new_page()
        page.goto(DASHBOARD_URL)

        print("Menunggu sinkronisasi token selama 3 detik...")
        page.wait_for_timeout(3000)

        try:
            context.storage_state(path=str(STORAGE_STATE_FILE))
        except Exception:
            pass

        print("Melanjutkan proses scraping Download Store...")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_selector("iframe", state="attached", timeout=60000)
        page.wait_for_timeout(3000)

        frame = get_target_frame(page)
        click_product = page.locator("iframe").content_frame.locator("div").filter(has_text=re.compile(r"^Product$")).nth(1)
        click_product.click(force=True)
        page.wait_for_selector("iframe", state="attached", timeout=60000)

        page.wait_for_timeout(2000)
        set_date_range(page)
        page.wait_for_timeout(1000)

        store_dropdown = page.locator("iframe").content_frame.locator("#component-loader-dcdd53ca-3b74-4971-b1b7-7caa29f791b5 > .component-wrapper > .query-component > .query-fields-wrapper > .query-fields-container > div:nth-child(2) > .query-field > .query-item > .enum-select > .advance-select-input-selected-value").first
        store_dropdown.click()
        page.wait_for_timeout(1000)
        page.locator("iframe").content_frame.locator("body").hover(position={"x": 0, "y": 0}, force=True)
        page.wait_for_timeout(500)

        def sanitize_filename(name: str) -> str:
            name = re.sub(r'[\\/:*?"<>|]+', '_', name)
            return name.strip()

        # Gunakan parameter folder dari UI jika ada
        if args.folder:
            download_dir = Path(args.folder).resolve()
        else:
            download_dir = BASE / "store_list"
        download_dir.mkdir(parents=True, exist_ok=True)
        print(f"Folder penyimpanan file download: {download_dir}")

        for i, store in enumerate(TARGET_STORES):
            print(f"\nMemproses download untuk toko: {store}")

            try:
                if i >= 1:
                    prev_store = TARGET_STORES[i - 1]
                    prev_store_option = page.locator("iframe").content_frame.locator("div").filter(
                        has_text=re.compile(f"^{prev_store}$", re.IGNORECASE)
                    ).first
                    prev_store_option.click(force=True)
                    page.wait_for_timeout(1000)
                    page.locator("iframe").content_frame.locator("body").hover(position={"x": 0, "y": 0}, force=True)
                    page.wait_for_timeout(500)

                if i >= 1:
                    prev_store_remove = page.locator("iframe").content_frame.locator("div:nth-child(2) > .list-y-scroll > .list-x-scroll > .list-content > .advance-select-item")
                    prev_store_remove.click(force=True)
                    page.wait_for_timeout(1000)
                    page.locator("iframe").content_frame.locator("body").hover(position={"x": 0, "y": 0}, force=True)
                    page.wait_for_timeout(500)

                store_option = page.locator("iframe").content_frame.locator("div").filter(has_text=re.compile(f"^{store}$", re.IGNORECASE)).first
                scroll_target = page.locator("iframe").content_frame.locator(".list-y-scroll").first

                count = 0
                max_scrolls = 100
                while not store_option.is_visible() and count < max_scrolls:
                    if scroll_target.is_visible():
                        scroll_target.evaluate("el => el.scrollTop += 100")
                    page.wait_for_timeout(1000)
                    count += 1

                if store_option.is_visible():
                    store_option.scroll_into_view_if_needed()
                    page.wait_for_timeout(1000)
                    page.mouse.move(0, 0)
                    page.wait_for_timeout(1000)
                    store_option.click(force=True)
                else:
                    print(f"[{store}] Tidak ditemukan setelah scroll {max_scrolls} kali. Melanjutkan ke toko berikutnya...")
                    continue

                page.wait_for_timeout(1000)

                submit_btn = page.locator("iframe").content_frame.get_by_role("button", name="OK")
                submit_btn.click()

                inquire_btn = page.locator("iframe").content_frame.locator("#component-loader-dcdd53ca-3b74-4971-b1b7-7caa29f791b5 > .component-wrapper > .query-component > .query-fields-wrapper > .query-button-container > .query-button-areas > .ant-btn.ant-btn-primary.query-area-button.query-last-button")
                inquire_btn.click()

                print("Menunggu data selesai dimuat...")
                click_product.wait_for(state="visible", timeout=10000)

                page.wait_for_selector("iframe", state="attached", timeout=60000)

                iframe = page.locator("iframe").content_frame
                pie_chart_container = iframe.locator("#component-loader-ac2afb03-6ceb-4f4e-b963-57f0fd5f73b4").locator(".pie-wrapper-view canvas")

                iframe.locator("body").hover(position={"x": 500, "y": 300})

                max_scrolls = 15
                count = 0
                while not pie_chart_container.is_visible() and count < max_scrolls:
                    page.mouse.wheel(0, 400)
                    page.wait_for_timeout(1000)
                    count += 1

                pie_chart_container.scroll_into_view_if_needed()
                pie_chart_container.wait_for(state="visible", timeout=20000)

                if pie_chart_container.is_visible():
                    pie_chart_container.hover()
                    page.wait_for_timeout(800)
                    dropdown_icon = page.locator("iframe").content_frame.locator("#qbi-nufo4n2c > .sc-kAyceB > .card-header-wrapper > .card-header-tail > .card-menu-wrapper").first
                    dropdown_icon.click(force=True)
                    page.wait_for_timeout(1000)
                    page.locator("iframe").content_frame.get_by_text("Export", exact=True).click(force=True)
                    page.wait_for_timeout(1000)
                    page.locator("iframe").content_frame.get_by_role("button", name="OK").first.wait_for(state="visible")

                    with page.expect_download(timeout=30000) as download_info:
                        page.locator("iframe").content_frame.get_by_role("button", name="OK").first.click(force=True)

                    download = download_info.value
                    print(f"[{store}] Suggested filename: {download.suggested_filename}")
                    failure = download.failure()
                    if failure:
                        raise RuntimeError(f"Download gagal untuk {store}: {failure}")

                    original_ext = Path(download.suggested_filename).suffix or ".xlsx"
                    safe_name = sanitize_filename(store)
                    new_filename = f"{safe_name}{original_ext}"
                    file_path = download_dir / new_filename

                    counter = 1
                    while file_path.exists():
                        file_path = download_dir / f"{safe_name} ({counter}){original_ext}"
                        counter += 1

                    download.save_as(str(file_path))
                    print(f"File berhasil disimpan ke: {file_path.resolve()}")

                    page.locator("iframe").content_frame.get_by_role("button", name="OK").first.wait_for(state="hidden", timeout=10000)
                    page.wait_for_timeout(1000)

            except Exception as e:
                print(f"Terjadi error saat memproses toko {store}: {e}")

        browser.close()


def main():
    scrape_dashboard()


if __name__ == "__main__":
    main()
