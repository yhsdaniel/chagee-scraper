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
parser = argparse.ArgumentParser(description="CHAGEE MTD Scraper")
parser.add_argument('--storage', default=None, help='Path ke storage_state.json')
parser.add_argument('--env', default=None, help='Path ke .env')
parser.add_argument('--folder', default=None, help='Folder kerja')
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

service_account_path = Path(GOOGLE_SERVICE_ACCOUNT_FILE)
if not service_account_path.is_absolute():
    service_account_path = BASE / GOOGLE_SERVICE_ACCOUNT_FILE

METRICS_SELECTORS = {
    "GMV": "text=GMV >> xpath=../..//*[contains(@class,'value')]",
    "Gross Sales": "text=Gross Sales >> xpath=../..//*[contains(@class,'value')]",
    "TC": "text=TC >> xpath=../..//*[contains(@class,'value')]",
    "Cups": "text=Cups >> xpath=../..//*[contains(@class,'value')]",
    "DTC": "text=GMV >> xpath=../..//*[contains(@class,'value')]",
    "OTO": "text=GMV >> xpath=../..//*[contains(@class,'value')]",
}

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


def clean_number(text: str):
    if text is None:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", text.replace(",", ""))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def set_date_range(page):
    end_date = datetime.now()
    start_date = end_date.replace(day=1)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    print(f"Memilih tanggal di kalender: {start_str} hingga {end_str}...")

    try:
        iframe = page.locator("iframe").content_frame
        
        # 1. Klik input datepicker (bisa berupa input aktif, ant-picker, atau textbox)
        date_input = iframe.locator(".ant-picker, .quick-range-datetime, input[placeholder*='select' i]").first
        date_input.click()
        page.wait_for_timeout(1000)
        
        # 2. Cari cell berdasarkan title="YYYY-MM-DD" (standar Ant Design)
        print(f" -> Mencari dan mengeklik Start Date: {start_str}")
        start_cell = iframe.locator(f'td[title="{start_str}"], .ant-picker-cell[title="{start_str}"]').first
        
        # Jika belum terlihat (karena beda bulan), klik tombol prev bulan
        if not start_cell.is_visible():
            prev_btn = iframe.locator('.ant-picker-header-prev-btn, .ant-picker-header-super-prev-btn').first
            if prev_btn.is_visible():
                prev_btn.click()
                page.wait_for_timeout(800)
                
        start_cell.click(force=True)
        page.wait_for_timeout(1000)
        
        # 3. Klik End Date berdasarkan title="YYYY-MM-DD"
        print(f" -> Mencari dan mengeklik End Date: {end_str}")
        end_cell = iframe.locator(f'td[title="{end_str}"], .ant-picker-cell[title="{end_str}"]').first
        
        if not end_cell.is_visible():
            next_btn = iframe.locator('.ant-picker-header-next-btn, .ant-picker-header-super-next-btn').last
            if next_btn.is_visible():
                next_btn.click()
                page.wait_for_timeout(800)
                
        end_cell.click(force=True)
        page.wait_for_timeout(1000)
        
        # 4. Tutup kalender / Klik OK jika ada
        ok_btn = iframe.locator('.ant-picker-ok button')
        if ok_btn.is_visible():
            ok_btn.click()
        else:
            page.keyboard.press("Escape")
            
        page.wait_for_timeout(1000)
        print(f"✅ Berhasil mengatur tanggal: {start_str} s/d {end_str}")
        
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

        print("Melanjutkan proses scraping MTD...")
        page.wait_for_load_state("domcontentloaded")
        page.locator("iframe").first.wait_for(state="visible", timeout=90000)
        page.wait_for_timeout(3000)

        frame = get_target_frame(page)
        store_bottom_arrow = page.locator("iframe").content_frame.locator(".query-fold-icon").first
        store_bottom_arrow.wait_for(state="visible", timeout=5000)
        store_bottom_arrow.click(force=True)
        page.wait_for_timeout(1000)

        set_date_range(page)

        store_dropdown = page.locator("iframe").content_frame.locator("div").filter(has_text=re.compile(r"^Multiple choices$")).nth(2)
        store_dropdown.click()
        page.wait_for_timeout(1000)
        page.locator("iframe").content_frame.locator("body").hover(position={"x": 0, "y": 0}, force=True)
        page.wait_for_timeout(500)

        all_results = []

        for i, store in enumerate(TARGET_STORES):
            print(f"\nMemproses data untuk toko: {store}")

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

                inquire_btn = page.locator("iframe").content_frame.locator("#component-loader-23832712-70a0-4dab-89d4-5d6f204263d9").get_by_role("button", name="Inquire")
                inquire_btn.click()

                print("Menunggu data selesai dimuat...")
                page.wait_for_timeout(2000)

                body_text = page.locator("iframe").content_frame.locator("body").inner_text()

                store_data = {"Store Name": store}
                for metric_name, selector in METRICS_SELECTORS.items():
                    try:
                        just_numbers = "0"

                        if metric_name == "GMV":
                            match = re.search(r"GMV\s*(?:Rp\s*)?([\d,\.]+)", body_text)
                            if match:
                                just_number = match.group(1)
                                clean_number_str = just_number.replace(",", "")
                                final_number = int(clean_number_str)
                        elif metric_name == "Gross Sales":
                            match = re.search(r"Gross Sales\s*(?:Rp\s*)?([\d,\.]+)", body_text)
                            if match:
                                just_number = match.group(1)
                                clean_number_str = just_number.replace(",", "")
                                final_number = int(clean_number_str)
                        elif metric_name == "TC":
                            match = re.search(r"TC\s*([\d,\.]+)", body_text)
                            if match:
                                just_number = match.group(1)
                                clean_number_str = just_number.replace(",", "")
                                final_number = int(clean_number_str)
                        elif metric_name == "Cups":
                            match = re.search(r"Cups\s*([\d,\.]+)", body_text)
                            if match:
                                just_number = match.group(1)
                                clean_number_str = just_number.replace(",", "")
                                final_number = int(clean_number_str)

                        store_data[metric_name] = final_number
                    except Exception as e:
                        print(f"Error extracting {metric_name}: {e}")
                        store_data[metric_name] = None

                print(f"  -> Hasil: {store_data}")

                page.wait_for_timeout(2000)

                # Channel DTC
                channel_option = page.locator("iframe").content_frame.locator("div").filter(has_text=re.compile(r"^Multiple choices$")).nth(2)
                channel_option.click(force=True)
                page.wait_for_timeout(1000)

                dtc_channel = page.locator("iframe").content_frame.locator("div").filter(has_text=re.compile(r"^DTC$")).first
                dtc_channel.click(force=True)

                submit_btn.click()
                inquire_btn.click()

                print("Menunggu data DTC selesai dimuat...")
                page.wait_for_timeout(2000)

                dtc_body_text = page.locator("iframe").content_frame.locator("body").inner_text()

                just_number = "0"
                match = re.search(r"GMV\s*(?:Rp\s*)?([\d,\.]+)", dtc_body_text)
                if match:
                    just_number = match.group(1)
                    clean_number_str = just_number.replace(",", "")
                    final_number = int(clean_number_str)

                store_data["DTC"] = final_number
                print(f"  -> Hasil (dengan DTC): {store_data}")

                page.wait_for_timeout(2000)

                prev_channel = page.locator("iframe").content_frame.locator("div").filter(has_text=re.compile(r"^DTC$")).nth(2)
                prev_channel.click(force=True)
                prev_channel_remove = page.locator("iframe").content_frame.locator("div:nth-child(2) > .list-y-scroll > .list-x-scroll > .list-content > .advance-select-item")
                prev_channel_remove.click(force=True)

                page.wait_for_timeout(1000)

                # Channel OTO
                oto_channel = page.locator("iframe").content_frame.locator("div").filter(has_text=re.compile(r"^OTO$")).first
                oto_channel.click(force=True)

                submit_btn.click()
                inquire_btn.click()

                print("Menunggu data OTO selesai dimuat...")
                page.wait_for_timeout(2000)

                oto_body_text = page.locator("iframe").content_frame.locator("body").inner_text()

                just_number = "0"
                match = re.search(r"GMV\s*(?:Rp\s*)?([\d,\.]+)", oto_body_text)
                if match:
                    just_number = match.group(1)
                    clean_number_str = just_number.replace(",", "")
                    final_number = int(clean_number_str)

                store_data["OTO"] = final_number
                print(f"  -> Hasil (dengan OTO): {store_data}")

                prev_channel = page.locator("iframe").content_frame.locator("div").filter(has_text=re.compile(r"^OTO$")).nth(2)
                prev_channel.click(force=True)
                prev_channel_remove = page.locator("iframe").content_frame.locator("div:nth-child(2) > .list-y-scroll > .list-x-scroll > .list-content > .advance-select-item")
                prev_channel_remove.click(force=True)
                submit_btn.click()
                page.wait_for_timeout(2000)

                all_results.append(store_data)
                push_to_google_sheets(all_results)

            except Exception as e:
                print(f"Terjadi error saat memproses toko {store}: {e}")

        browser.close()
        return all_results


def push_to_google_sheets(results: list):
    if not results:
        print("Data kosong, tidak ada yang dikirim ke Google Sheets.")
        return

    if not service_account_path.exists():
        print(f"Peringatan: Kredensial service account tidak ditemukan di {service_account_path}. Lewati push Google Sheets.")
        return

    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(
            str(service_account_path), scopes=scopes
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        ws = sh.worksheet(GOOGLE_SHEET_TAB)

        existing_values = ws.get_all_values()
        if not existing_values:
            print("Sheet kosong, tidak ada template header.")
            return

        headers = existing_values[0]

        try:
            store_col_idx = headers.index("Store name")
        except ValueError:
            print("Error: Kolom 'Store name' tidak ditemukan di baris pertama Sheets.")
            return

        metric_mapping = {
            "GMV": "GMV",
            "Gross Sales": "Gross Sales",
            "TC": "TC",
            "Cups": "Cups",
            "DTC": "DTC",
            "OTO": "OTO",
        }

        col_indices = {}
        for res_key, header_key in metric_mapping.items():
            try:
                col_indices[res_key] = headers.index(header_key)
            except ValueError:
                print(f"Peringatan: Kolom '{header_key}' tidak ditemukan di Sheets.")

        store_row_map = {}
        for i, row in enumerate(existing_values):
            if i == 0:
                continue
            if len(row) > store_col_idx:
                store_name = row[store_col_idx].strip()
                if store_name:
                    store_row_map[store_name] = i + 1

        cells_to_update = []
        for data in results:
            store_name = data.get("Store Name", "").strip()
            if store_name in store_row_map:
                row_idx = store_row_map[store_name]

                for metric_name, val in data.items():
                    if metric_name in col_indices and val is not None:
                        col_idx = col_indices[metric_name] + 1
                        cells_to_update.append(gspread.Cell(row=row_idx, col=col_idx, value=val))
            else:
                print(f"Peringatan: Toko '{store_name}' tidak ditemukan di Sheets (pastikan ejaan sama persis).")

        if cells_to_update:
            ws.update_cells(cells_to_update)
            print(f"\nBerhasil! Memperbarui {len(cells_to_update)} sel data ke Google Sheets pada baris yang sesuai.")
        else:
            print("\nTidak ada data yang cocok untuk diperbarui ke Sheets.")
    except Exception as e:
        print(f"Error saat push ke Google Sheets: {e}")


def main():
    scrape_dashboard()


if __name__ == "__main__":
    main()
