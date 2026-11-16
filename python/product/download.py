"""
scraper.py
----------
Mengambil data (GMV, Gross Sales, TC, AOV) dari dashboard
BI yang dirender via JavaScript (termasuk di dalam iframe), lalu menulis
hasilnya ke Google Sheets.
"""

from datetime import datetime, timedelta
import os
import re
import json
import time
import re

import gspread

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
# from supabase import create_client, Client

import tkinter as tk
from tkinter import simpledialog, messagebox

load_dotenv()

DASHBOARD_URL = os.getenv("DASHBOARD_URL")
STORAGE_STATE_FILE = os.getenv("STORAGE_STATE_FILE", "storage_state.json")

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
    start_date = end_date - timedelta(days=7)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    print(f"Memilih tanggal di kalender: {start_str} hingga {end_str}...")
    
    try:
        
        iframe = page.locator("iframe").content_frame
        
        # 2. Klik Start Date
        print(f" -> Mencari dan mengeklik Start Date: {start_str}")
        
        
        # 1. Klik area kotak input agar pop-up kalender muncul ke layar
        iframe.locator("#component-loader-dcdd53ca-3b74-4971-b1b7-7caa29f791b5 > .component-wrapper > .query-component > .query-fields-wrapper > .query-fields-container > div > .query-field > .query-item > .query-datetime > .quick-range-datetime > .ant-picker > .ant-picker-input.ant-picker-input-active > input").first.click()
        page.wait_for_timeout(1000) 
        
        # 2. Klik Start Date
        print(f" -> Mencari dan mengeklik Start Date: {start_str}")
        start_cell = iframe.get_by_role("cell", name=start_date.strftime("%#d"), exact=True, description=start_str).first
        
        # Jika tanggal tidak terlihat di layar, tekan tombol 'Bulan Sebelumnya' (Prev Month)
        if not start_cell.is_visible():
            prev_btn = page.locator("iframe").content_frame.locator("iframe").content_frame.get_by_role("button").filter(has_text=re.compile(r"^$")).nth(1).first
            if prev_btn.is_visible():
                prev_btn.click()
                page.wait_for_timeout(1000)
                
        start_cell.click(force=True)
        page.wait_for_timeout(1000)
        
        # 3. Klik End Date        
        print(f" -> Mencari dan mengeklik End Date: {end_str}")
        end_cell = iframe.get_by_role("cell", name=end_date.strftime("%#d"), exact=True, description=end_str).first
        
        # Karena klik start date mungkin menggeser kalender, cek apakah end date masih terlihat
        # Jika tidak terlihat, tekan tombol 'Bulan Berikutnya' (Next Month)
        if not end_cell.is_visible():
            next_btn = page.locator("iframe").content_frame.locator("iframe").content_frame.get_by_role("button").filter(has_text=re.compile(r"^$")).nth(2).last
            if next_btn.is_visible():
                next_btn.click()
                page.wait_for_timeout(1000)
                
        end_cell.click(force=True)
        page.wait_for_timeout(1000)
        
        # 4. Tutup kalender 
        # Cek apakah ada tombol OK (biasanya ada jika memilih 'time'), jika ada klik OK.
        ok_btn = page.locator("iframe").content_frame.locator('.ant-picker-ok button')
        if ok_btn.is_visible():
            ok_btn.click()
        else:
            page.keyboard.press("Escape")
        
    except Exception as e:
        print(f"Error saat mengeklik tanggal di kalender: {e}")



def scrape_dashboard():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
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

        # 2. Masukkan storage_state JIKA file JSON-nya ada
        if os.path.exists(STORAGE_STATE_FILE):
            print(f"Memuat session dari {STORAGE_STATE_FILE} ...")
            context_args["storage_state"] = STORAGE_STATE_FILE
            
        context = browser.new_context(**context_args)
        page = context.new_page()
        page.goto(DASHBOARD_URL)

        # 3. Cek apakah masih butuh login (hanya gunakan pause jika diperlukan)
        print("Silakan cek browser. JIKA halaman meminta QR, silakan SCAN.")
        print("Jika dashboard langsung terbuka, klik ikon PLAY / RESUME di Playwright Inspector.")

        # 4. Beri waktu iframe dan halaman termuat sempurna setelah resume
        print("Menunggu sinkronisasi token selama 3 detik...")
        page.wait_for_timeout(3000)
        
        # 5. Simpan (atau perbarui) state session agar token yang baru ikut tersimpan
        context.storage_state(path=STORAGE_STATE_FILE)
        print("[OK] Sesi berhasil disimpan secara lengkap!")

        # 6. Lanjut ke proses scraping
        print("Melanjutkan proses scraping...")
        page.wait_for_load_state("domcontentloaded")
        # Menunggu dashboard terbuka (timeout 90 detik) seperti yang diminta
        page.wait_for_selector("iframe", state="attached", timeout=60000)
        
        page.wait_for_timeout(3000)

        frame = get_target_frame(page)
        click_product = page.locator("iframe").content_frame.locator("div").filter(has_text=re.compile(r"^Product$")).nth(1)
        click_product.first
        click_product.click(force=True)
        page.wait_for_selector("iframe", state="attached", timeout=60000)
        # click_more_percentage_of_product = page.locator("iframe").content_frame.locator(".svg-icon-wrapper.bi-icon-new.ant-dropdown-trigger.card-menu-show > .svg-icon").click(Force=True)
        # store_bottom_arrow = page.locator("iframe").content_frame.locator(".query-fold-icon").first
        # store_bottom_arrow.wait_for(state="visible", timeout=5000)
        # store_bottom_arrow.click(force=True)
        
        page.wait_for_timeout(2000)

        set_date_range(page)
        
        page.wait_for_timeout(1000)
        
        store_dropdown = page.locator("iframe").content_frame.locator("#component-loader-dcdd53ca-3b74-4971-b1b7-7caa29f791b5 > .component-wrapper > .query-component > .query-fields-wrapper > .query-fields-container > div:nth-child(2) > .query-field > .query-item > .enum-select > .advance-select-input-selected-value").first
        store_dropdown.click()
        page.wait_for_timeout(1000)
        page.locator("iframe").content_frame.locator("body").hover(position={"x": 0, "y": 0}, force=True)
        page.wait_for_timeout(500)
        
        # Helper biar nama file aman
        def sanitize_filename(name: str) -> str:
            name = re.sub(r'[\\/:*?"<>|]+', '_', name)
            return name.strip()
        
        # Folder store_list berada satu folder dengan file Python ini
        app_dir = Path(__file__).resolve().parent
        download_dir = app_dir / "store_list"
        download_dir.mkdir(parents=True, exist_ok=True)
        
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

                # Lakukan scroll ke bawah selama opsi toko belum terlihat
                count = 0
                max_scrolls = 100
                while not store_option.is_visible() and count < max_scrolls:
                    if scroll_target.is_visible():
                        # Scroll perlahan agar list virtual sempat merender elemen baru
                        scroll_target.evaluate("el => el.scrollTop += 100")
                    page.wait_for_timeout(1000)
                    count += 1
                
                if store_option.is_visible():
                    # Pastikan elemen ada di viewport lalu klik secara normal (tanpa force=True)
                    # Ini mencegah Playwright meng-klik elemen lain (misal FX Sudirman) yang menumpuk di atasnya
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
                
                store_data = {"Store Name": store}
                
                # page.wait_for_timeout(2000)
                
                page.wait_for_selector("iframe", state="attached", timeout=60000)
                
                count = 0
                max_scrolls = 100
                while not store_option.is_visible() and count < max_scrolls:
                    if scroll_target.is_visible():
                        # Scroll perlahan agar list virtual sempat merender elemen baru
                        scroll_target.evaluate("el => el.scrollTop += 100")
                    page.wait_for_timeout(1000)
                    count += 1
                        
                print(f"  -> Hasil: {store_data}")
                
                # 1. Gunakan content_frame dari iframe
                iframe = page.locator("iframe").content_frame
                
                # Target container atau elemen pie chart
                pie_chart_container = iframe.locator("#component-loader-ac2afb03-6ceb-4f4e-b963-57f0fd5f73b4").locator(".pie-wrapper-view canvas")
                
                # 2. Hover ke area dashboard agar mouse wheel aktif di dalam frame
                iframe.locator("body").hover(position={"x": 500, "y": 300})

                # 3. Scroll ke bawah bertahap sampai pie chart muncul
                max_scrolls = 15
                count = 0
                
                while not pie_chart_container.is_visible() and count < max_scrolls:
                    page.mouse.wheel(0, 400)  # Scroll ke bawah 600px
                    page.wait_for_timeout(1000)
                    count += 1

                # 4. Pastikan elemen benar-benar berada di viewport
                pie_chart_container.scroll_into_view_if_needed()
                pie_chart_container.wait_for(state="visible", timeout=20000)
                
                if pie_chart_container.is_visible():
                    # 5. Klik icon dropdown/menu export
                    pie_chart_container.hover()
                    page.wait_for_timeout(800)
                    dropdown_icon = page.locator("iframe").content_frame.locator("#qbi-nufo4n2c > .sc-kAyceB > .card-header-wrapper > .card-header-tail > .card-menu-wrapper").first
                    dropdown_icon.click(force=True)
                    page.wait_for_timeout(1000)
                    page.locator("iframe").content_frame.get_by_text("Export", exact=True).click(force=True)
                    page.wait_for_timeout(1000)
                    page.locator("iframe").content_frame.get_by_role("button", name="OK").first.wait_for(state="visible")
                    # 2. Tunggu event download sebelum klik tombol
                    with page.expect_download(timeout=30000) as download_info:
                        page.locator("iframe").content_frame.get_by_role("button", name="OK").first.click(force=True)
                    # 3. Ambil objek Download
                    download = download_info.value
                    # 4. Periksa nama file dan error download
                    print(f"[{store}] Suggested filename: {download.suggested_filename}")
                    failure = download.failure()
                    if failure:
                        raise RuntimeError(f"Download gagal untuk {store}: {failure}")
                    # 5. GANTI NAMA SESUAI NAMA TOKO
                    original_ext = Path(download.suggested_filename).suffix or ".xlsx"
                    safe_name = sanitize_filename(store)
                    new_filename = f"{safe_name}{original_ext}"
                    file_path = download_dir / new_filename
                    # Jaga-jaga kalau ada nama toko yang duplikat persis
                    counter = 1
                    while file_path.exists():
                        file_path = download_dir / f"{safe_name} ({counter}){original_ext}"
                        counter += 1
                    download.save_as(str(file_path))
                    print(f"File berhasil disimpan ke: {file_path.resolve()}")
                    # Tunggu modal tertutup sebelum lanjut ke toko berikutnya
                    page.locator("iframe").content_frame.get_by_role("button", name="OK").first.wait_for(state="hidden", timeout=10000)
                    page.wait_for_timeout(1000)
                
            except Exception as e:
                print(f"Terjadi error saat memproses toko {store}: {e}")

        browser.close()
        return
        
def main():
    scrape_dashboard()

if __name__ == "__main__":
    main()


# if __name__ == "__main__":
#     root = tk.Tk()
#     root.withdraw()
    
#     # Munculkan pop-up input untuk meminta License Key
#     key = simpledialog.askstring("Login Automation", "Masukkan License Key:")
#     if key:
#         key = key.strip()
#         if check_subscription(key):
#             scrape_dashboard()
#         else:
#             pass
#     else:
#         messagebox.showwarning("Dibatalkan", "License Key harus diisi!")
