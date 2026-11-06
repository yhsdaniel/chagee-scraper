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
import sys
import argparse
import gspread
import traceback
    
if sys.platform == 'win32':
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except: pass

# === 1. PARSE ARGS DULU (SEBELUM IMPORT LAIN) ===
parser = argparse.ArgumentParser()
parser.add_argument('--folder', default=None)
parser.add_argument('--storage', default=None)
parser.add_argument('--env', default=None)
args = parser.parse_args()
print(f"[PY-DEBUG] --folder={args.folder}")
print(f"[PY-DEBUG] --storage={args.storage}")
print(f"[PY-DEBUG] --env={args.env}")
# === 2. TENTUKAN BASE_DIR YANG BENAR ===
if args.env and os.path.exists(args.env):
    BASE_DIR = os.path.dirname(os.path.abspath(args.env))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"[PY-DEBUG] BASE_DIR = {BASE_DIR}")
print(f"[PY-DEBUG] List BASE_DIR = {os.listdir(BASE_DIR)[:20]}")
# === 3. LOAD ENV ===
from dotenv import load_dotenv
env_to_load = args.env if args.env and os.path.exists(args.env) else os.path.join(BASE_DIR, ".env")
print(f"[PY-DEBUG] Load .env dari: {env_to_load} Exists={os.path.exists(env_to_load)}")
if os.path.exists(env_to_load):
    load_dotenv(env_to_load, override=True)
else:
    print(f"[PY-ERROR] .env TIDAK KETEMU!")
    load_dotenv()

from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
# from supabase import create_client, Client

DASHBOARD_URL = os.getenv("DASHBOARD_URL")
if args.storage:
    STORAGE_STATE_FILE = args.storage
else:
    STORAGE_STATE_FILE = os.path.join(BASE_DIR, os.getenv("STORAGE_STATE_FILE", "storage_state.json"))

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SHEET_TAB = os.getenv("GOOGLE_SHEET_TAB", "Sheet1")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

# Fokus pada 4 metrics sesuai permintaan
METRICS_SELECTORS = {
    "GMV": "text=GMV >> xpath=../..//*[contains(@class,'value')]",
    "Gross Sales": "text=Gross Sales >> xpath=../..//*[contains(@class,'value')]",
    "TC": "text=TC >> xpath=../..//*[contains(@class,'value')]",
    "Cups": "text=Cups >> xpath=../..//*[contains(@class,'value')]",
    "DTC": "text=GMV >> xpath=../..//*[contains(@class,'value')]",
    "OTO": "text=GMV >> xpath=../..//*[contains(@class,'value')]",
}

# URL iframe jika bwcj ada di dalam iframe
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
    start_date = end_date - timedelta(days=6)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    print(f"Memilih tanggal di kalender: {start_str} hingga {end_str}...")
    
    try:
        iframe = page.locator("iframe").content_frame
        
        # 1. Klik area kotak input agar pop-up kalender muncul ke layar
        iframe.get_by_role("textbox", name="Please select a time").first.click()
        page.wait_for_timeout(1000) 
        
        # 2. Klik Start Date
        print(f" -> Mencari dan mengeklik Start Date: {start_str}")
        start_cell = iframe.get_by_role("cell", name=start_date.strftime("%#d"), exact=True, description=start_str).first
        
        # Jika tanggal tidak terlihat di layar, tekan tombol 'Bulan Sebelumnya' (Prev Month)
        if not start_cell.is_visible():
            prev_btn = iframe.locator('.ant-picker-header-prev-btn').first
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
            next_btn = iframe.locator('.ant-picker-header-next-btn').last
            if next_btn.is_visible():
                next_btn.click()
                page.wait_for_timeout(1000)
                
        end_cell.click(force=True)
        page.wait_for_timeout(1000)
        
        # 4. Tutup kalender 
        # Cek apakah ada tombol OK (biasanya ada jika memilih 'time'), jika ada klik OK.
        ok_btn = iframe.locator('.ant-picker-ok button')
        if ok_btn.is_visible():
            ok_btn.click()
        else:
            page.keyboard.press("Escape")
            
        page.wait_for_timeout(1000)
        
    except Exception as e:
        print(f"Error saat mengeklik tanggal di kalender: {e}")



def scrape_dashboard():
    all_results = []
    try:
        
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
            print("✅ Sesi berhasil disimpan secara lengkap!")
            
            # JANGAN gunakan browser.close() di sini, biarkan script berlanjut!

            # 6. Lanjut ke proses scraping
            print("Melanjutkan proses scraping...")
            page.wait_for_load_state("domcontentloaded")
            # Menunggu dashboard terbuka (timeout 90 detik) seperti yang diminta
            page.locator("iframe").first.wait_for(state="visible", timeout=90000)
            page.wait_for_timeout(5000)

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
                    
                    inquire_btn = page.locator("iframe").content_frame.locator("#component-loader-23832712-70a0-4dab-89d4-5d6f204263d9").get_by_role("button", name="Inquire")
                    inquire_btn.click()
                    
                    print("Menunggu data selesai dimuat...")
                    page.wait_for_timeout(2000)

                    # Get all text from the dashboard body to avoid complex HTML/DOM nesting issues
                    body_text = page.locator("iframe").content_frame.locator("body").inner_text()
                    
                    store_data = {"Store Name": store}
                    # GMV, Gross, TC, Cups
                    for key in ["GMV", "Gross Sales", "TC", "Cups"]:
                        m = re.search(rf"{key}\s*(?:Rp\s*)?([\d,\.]+)", body_text)
                        if m:
                            store_data[key] = int(m.group(1).replace(",", ""))
                            
                    print(f"  -> Hasil: {store_data}")

                    page.wait_for_timeout(2000)

                    # Buka dropdown channel (Pastikan nth(2) adalah dropdown channel, bukan store)
                    channel_option = page.locator("iframe").content_frame.locator("div").filter(has_text=re.compile(r"^Multiple choices$")).nth(2)
                    channel_option.click(force=True)
                    page.wait_for_timeout(1000)

                    # Pilih DTC
                    dtc_channel = page.locator("iframe").content_frame.locator("div").filter(has_text=re.compile(r"^DTC$")).first
                    dtc_channel.click(force=True)
                    
                    submit_btn.click()
                    inquire_btn.click()
                    
                    # Tunggu data DTC termuat
                    print("Menunggu data DTC selesai dimuat...")
                    page.wait_for_timeout(2000)
                    
                    # Ambil ulang teks di halaman untuk channel DTC
                    dtc_body_text = page.locator("iframe").content_frame.locator("body").inner_text()
                    
                    just_number = "0"
                    # Cari angka GMV dari teks DTC terbaru
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

                    # Pilih OTO
                    oto_channel = page.locator("iframe").content_frame.locator("div").filter(has_text=re.compile(r"^OTO$")).first
                    oto_channel.click(force=True)
                    
                    submit_btn.click()
                    inquire_btn.click()
                    
                    # Tunggu data OTO termuat
                    print("Menunggu data OTO selesai dimuat...")
                    page.wait_for_timeout(2000)
                    
                    # Ambil ulang teks di halaman untuk channel OTO
                    oto_body_text = page.locator("iframe").content_frame.locator("body").inner_text()
                    
                    just_number = "0"
                    # Cari angka GMV dari teks OTO terbaru
                    match = re.search(r"GMV\s*(?:Rp\s*)?([\d,\.]+)", oto_body_text)
                    if match:
                        just_number = match.group(1)
                        clean_number_str = just_number.replace(",", "")
                        final_number = int(clean_number_str)
                        
                    store_data["OTO"] = final_number
                    print(f"  -> Hasil (dengan OTO): {store_data}")

                    #DELETE CHANNEL
                    prev_channel = page.locator("iframe").content_frame.locator("div").filter(has_text=re.compile(r"^OTO$")).nth(2)
                    prev_channel.click(force=True)
                    prev_channel_remove = page.locator("iframe").content_frame.locator("div:nth-child(2) > .list-y-scroll > .list-x-scroll > .list-content > .advance-select-item")
                    prev_channel_remove.click(force=True)
                    submit_btn.click()
                    page.wait_for_timeout(2000)

                    all_results.append(store_data)
                    push_to_google_sheets(all_results)
                    
                except Exception as e:
                    print(f"Error toko {store}: {e}")
                    traceback.print_exc()

            browser.close() # <-- Browser BARU DITUTUP setelah semua scraping (loop) selesai
            return all_results
        
    except Exception as e:
        print(f"[FATAL] {e}")
        traceback.print_exc()
        return []


def push_to_google_sheets(results: list):
    if not results:
        print("Data kosong, tidak ada yang dikirim ke Google Sheets.")
        return
        
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(GOOGLE_SHEET_ID)
    ws = sh.worksheet(GOOGLE_SHEET_TAB)

    existing_values = ws.get_all_values()
    if not existing_values:
        print("Sheet kosong, tidak ada template header.")
        return

    # Ambil header (baris pertama)
    headers = existing_values[0]
    
    try:
        # Cari index kolom "Store name" (kasus sensitif, sesuai di gambar)
        store_col_idx = headers.index("Store name")
    except ValueError:
        print("Error: Kolom 'Store name' tidak ditemukan di baris pertama Sheets.")
        return

    # Mapping nama metrik dari hasil scraping ke nama kolom di Sheets
    metric_mapping = {
        "GMV": "GMV",
        "Gross Sales": "Gross Sales",
        "TC": "TC",
        "Cups": "Cups",
        "DTC": "DTC",
        "OTO": "OTO",
    }

    # Cari index kolom untuk masing-masing metrik
    col_indices = {}
    for res_key, header_key in metric_mapping.items():
        try:
            col_indices[res_key] = headers.index(header_key)
        except ValueError:
            print(f"Peringatan: Kolom '{header_key}' tidak ditemukan di Sheets.")

    # Peta baris untuk setiap nama toko
    store_row_map = {}
    for i, row in enumerate(existing_values):
        if i == 0:
            continue
        if len(row) > store_col_idx:
            store_name = row[store_col_idx].strip()
            if store_name:
                store_row_map[store_name] = i + 1  # +1 karena gspread 1-indexed

    # Siapkan cell yang akan diupdate
    cells_to_update = []
    for data in results:
        store_name = data.get("Store Name", "").strip()
        if store_name in store_row_map:
            row_idx = store_row_map[store_name]
            
            for metric_name, val in data.items():
                if metric_name in col_indices and val is not None:
                    col_idx = col_indices[metric_name] + 1  # +1 untuk gspread 1-indexed
                    cells_to_update.append(gspread.Cell(row=row_idx, col=col_idx, value=val))
        else:
            print(f"Peringatan: Toko '{store_name}' tidak ditemukan di Sheets (pastikan ejaan sama persis).")

    if cells_to_update:
        # Lakukan batch update
        ws.update_cells(cells_to_update)
        print(f"\nBerhasil! Memperbarui {len(cells_to_update)} sel data ke Google Sheets pada baris yang sesuai.")
    else:
        print("\nTidak ada data yang cocok untuk diperbarui ke Sheets.")
    pass
        
def main():
    print(f"Running with local folder: {args.folder}")
    scrape_dashboard()

if __name__ == "__main__":
    main()
