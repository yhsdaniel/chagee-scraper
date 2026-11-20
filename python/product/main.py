import sys
import os
import glob
import argparse
from pathlib import Path

BASE = Path(__file__).resolve().parent
LIBS = BASE / "libs"
if str(LIBS) not in sys.path:
    sys.path.insert(0, str(LIBS))

# Parse CLI arguments (PRD §7.4)
parser = argparse.ArgumentParser(description="CHAGEE Products Summary to Google Sheets")
parser.add_argument('--storage', default=None, help='Path ke storage_state.json')
parser.add_argument('--env', default=None, help='Path ke .env')
parser.add_argument('--folder', default=None, help='Folder berisi file excel store')
args, _ = parser.parse_known_args()

# Muat environment variables jika ada
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

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Resolusi folder input file excel
if args.folder and Path(args.folder).exists():
    folder_path = Path(args.folder).resolve()
else:
    folder_path = BASE / "store_list"

print(f"[PRODUCTS] Memproses file Excel dari folder: {folder_path}")

cred_file = BASE / "google_credential.json"
if not cred_file.exists():
    root_cred = BASE.parent.parent / "google_credential.json"
    if root_cred.exists():
        cred_file = root_cred
    else:
        print(f"[ERROR] File kredensial Google tidak ditemukan di: {cred_file}")
        sys.exit(1)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(str(cred_file), scopes=scope)
client = gspread.authorize(creds)
spreadsheet = client.open("Product Summary Automation")
sheet = spreadsheet.sheet1
category_ws = spreadsheet.worksheet("category")

# Read category
category_data = category_ws.get_all_values()
headers = category_data[0]
df_kategori = pd.DataFrame(category_data[1:], columns=headers)
df_kategori['Kata Kunci'] = df_kategori['Kata Kunci'].astype(str).str.lower()
kamus_kategori = dict(zip(df_kategori['Kata Kunci'], df_kategori['Kategori']))


def kategorikan_dinamis(nama_produk):
    nama_produk = str(nama_produk).lower()
    for keyword, kategori in kamus_kategori.items():
        if keyword in nama_produk:
            return kategori
    return 'Lainnya'


target_stores = [
    "23 Paskal Bandung",
    "AEON Mall BSD",
    "Ciputra Mall Jakarta",
    "Flavor Bliss",
    "Lippo Icon Gajah Mada",
    "Lippo Mall Puri",
    "Mall Ciputra Tangerang",
    "Paris Van Java",
    "Puri Indah Mall",
    "Summarecon Mall Bandung",
    "Summarecon Mall Serpong",
    "Supermall Karawaci",
    "TangCity",
    "The Breeze BSD",
    "Trans Studio Mall Bandung"
]

search_pattern = os.path.join(str(folder_path), "*.xlsx")
excel_files = glob.glob(search_pattern)

if len(excel_files) == 0:
    print(f"Peringatan: Tidak ada file .xlsx di folder: {folder_path}")
    sys.exit(0)

if len(excel_files) == len(target_stores):
    excel_files.sort(key=os.path.getmtime)
    for index, old_file in enumerate(excel_files):
        extension = os.path.splitext(old_file)[1]
        new_file = os.path.join(str(folder_path), target_stores[index] + extension)
        if old_file != new_file:
            try:
                os.rename(old_file, new_file)
                old_name_file = os.path.basename(old_file)
                print(f"Success changed: {old_name_file} -> {new_file}")
            except Exception as e:
                print(f"Gagal rename {old_file}: {e}")

if len(target_stores) > 0:
    excel_files = [os.path.join(str(folder_path), f"{toko}.xlsx") for toko in target_stores]
else:
    excel_files = glob.glob(os.path.join(str(folder_path), "*.xlsx"))

hasil_rekap = []
hasil_rekap_makanan = []

for file in excel_files:
    if not os.path.exists(file):
        print(f"File tidak ditemukan: {file}")
        continue

    nama_toko = os.path.basename(file).replace('.xlsx', '').replace('CHAGEE ID ', '').strip()

    try:
        df = pd.read_excel(file)
    except Exception as e:
        print(f"Gagal membaca file {file}: {e}")
        continue

    df['Kategori'] = df['product name'].apply(kategorikan_dinamis)

    gmv_makanan = float(df.loc[df['Kategori'] == 'Makanan', 'GMV'].sum()) if 'GMV' in df.columns else 0.0
    gmv_minuman = float(df.loc[df['Kategori'] == 'Minuman', 'GMV'].sum()) if 'GMV' in df.columns else 0.0
    gmv_merch = float(df.loc[df['Kategori'] == 'Merchandise', 'GMV'].sum()) if 'GMV' in df.columns else 0.0
    gmv_lainnya = float(df.loc[df['Kategori'] == 'Lainnya', 'GMV'].sum()) if 'GMV' in df.columns else 0.0

    kolom_cups = 'Cups'
    for col in df.columns:
        if col.lower() in ['cups', 'product num']:
            kolom_cups = col
            break

    if kolom_cups in df.columns:
        cups_makanan = int(df.loc[df['Kategori'] == 'Makanan', kolom_cups].sum())
        cups_minuman = int(df.loc[df['Kategori'] == 'Minuman', kolom_cups].sum())
        cups_merch = int(df.loc[df['Kategori'] == 'Merchandise', kolom_cups].sum())
        cups_lainnya = int(df.loc[df['Kategori'] == 'Lainnya', kolom_cups].sum())

        cups_jct = int(df.loc[df['product name'].str.contains('Jasmine Tea Cake', na=False), kolom_cups].sum())
        cups_lcc = int(df.loc[df['product name'].str.contains('Lemon Cheese Cake', na=False), kolom_cups].sum())
        cups_poc = int(df.loc[df['product name'].str.contains('Peach Oolong Cake', na=False), kolom_cups].sum())
        cups_egc = int(df.loc[df['product name'].str.contains('Earl Grey Cake', na=False), kolom_cups].sum())
        cups_cc = int(df.loc[df['product name'].str.contains('Chocolate Cake', na=False), kolom_cups].sum())
        cups_cct = int(df.loc[df['product name'].str.contains('CHAGEE Classic Tiramisu', na=False), kolom_cups].sum())
        cups_pcpc = int(df.loc[df['product name'].str.contains('Pandan Coco Palm Cake', na=False), kolom_cups].sum())
        cups_oc = int(df.loc[df['product name'].str.contains('Osmanthus Choux', na=False), kolom_cups].sum())
    else:
        cups_makanan = cups_minuman = cups_merch = cups_lainnya = 0
        cups_jct = cups_lcc = cups_poc = cups_egc = cups_cc = cups_cct = cups_pcpc = cups_oc = 0

    gmv_food = float(df.loc[df['Kategori'] == 'Makanan', 'GMV'].sum()) if 'GMV' in df.columns else 0.0

    hasil_rekap.append([
        nama_toko,
        gmv_makanan, cups_makanan,
        gmv_minuman, cups_minuman,
        gmv_merch, cups_merch,
        gmv_lainnya, cups_lainnya,
    ])

    hasil_rekap_makanan.append([
        nama_toko,
        cups_jct,
        cups_lcc,
        cups_poc,
        cups_egc,
        cups_cc,
        cups_cct,
        cups_pcpc,
        cups_oc,
        gmv_food
    ])

header = [
    "Nama Toko",
    "GMV Food", "Cups Food",
    "GMV Drink", "Cups Drink",
    "GMV Merchandise", "Cups Merchandise",
    "GMV Lainnya", "Cups Lainnya"
]
data_utama = [header] + hasil_rekap

header_makanan = [
    "Nama Toko",
    "JCT",
    "LCK",
    "POC",
    "EGC",
    "CC",
    "CCT",
    "PCBC",
    "OC",
    "GMV"
]
data_detail_makanan = [header_makanan] + hasil_rekap_makanan

sheet.clear()
sheet.update(values=data_utama, range_name='A1')
sheet.update(values=data_detail_makanan, range_name='A17')

print(f"✅ Selesai! Data dari {len(excel_files)} toko telah dipindahkan ke Google Sheets menggunakan Master Kategori.")
