import pandas as pd
import glob
import os
import gspread
from google.oauth2.service_account import Credentials

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("google_credential.json", scopes=scope)
client = gspread.authorize(creds)
spreadsheet = client.open("Product Summary Automation")
sheet = spreadsheet.sheet1
category = spreadsheet.worksheet("category")

#read category
category = category.get_all_values()

#convert category to dataframe
headers = category[0]
df_kategori = pd.DataFrame(category[1:], columns=headers)

# Ubah semua kata kunci menjadi huruf kecil agar pencocokan lebih mudah
df_kategori['Kata Kunci'] = df_kategori['Kata Kunci'].astype(str).str.lower()

# Buat dictionary (kamus) dari dataframe kategori
# Hasilnya seperti: {'cake': 'Makanan', 'iphone': 'Merchandise', 'tea': 'Minuman'}
kamus_kategori = dict(zip(df_kategori['Kata Kunci'], df_kategori['Kategori']))

def kategorikan_dinamis(nama_produk):
    nama_produk = str(nama_produk).lower()
    
    # Cek setiap kata kunci di dalam kamus
    for keyword, kategori in kamus_kategori.items():
        if keyword in nama_produk:
            return kategori  # Jika cocok, kembalikan kategorinya
            
    # Jika tidak ada satupun kata kunci yang cocok di file Master, 
    # masukkan ke kategori "Lainnya" agar mudah dideteksi
    return 'Lainnya'


folder_path = "./store_list"
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

search_pattern = os.path.join(folder_path, "*.xlsx")
excel_files = glob.glob(search_pattern)

if len(excel_files) != len(target_stores):
    print(f"Error: Total file {len(excel_files)} not match with target stores {len(target_stores)}")
else:
    excel_files.sort(key=os.path.getmtime)
    
    for index, old_file in enumerate(excel_files):
        extension = os.path.splitext(old_file)[1]
        new_file = folder_path + "/" + target_stores[index] + extension
        os.rename(old_file, new_file)
        
        old_name_file = os.path.basename(old_file)
        print(f"Success changed: {old_name_file} -> {new_file}")

# Jika target_stores diisi, maka hanya proses toko-toko tersebut. Jika kosong, proses semua file di folder.
if len(target_stores) > 0:
    excel_files = [os.path.join(folder_path, f"{toko}.xlsx") for toko in target_stores]
else:
    excel_files = glob.glob(os.path.join(folder_path, "*.xlsx"))

hasil_rekap = []
hasil_rekap_makanan = []

for file in excel_files:
    if not os.path.exists(file):
        print(f"File tidak ditemukan: {file}")
        continue
        
    nama_toko = os.path.basename(file).replace('.xlsx', '').replace('CHAGEE ID ', '').strip()
    
    df = pd.read_excel(file)
    
    # Gunakan fungsi kategorisasi yang baru
    df['Kategori'] = df['product name'].apply(kategorikan_dinamis)
    
    # Hitung GMV per kategori (dikonversi ke tipe standar Python 'float' agar bisa dibaca JSON / Google Sheets)
    gmv_makanan = float(df.loc[df['Kategori'] == 'Makanan', 'GMV'].sum())
    gmv_minuman = float(df.loc[df['Kategori'] == 'Minuman', 'GMV'].sum())
    gmv_merch = float(df.loc[df['Kategori'] == 'Merchandise', 'GMV'].sum())
    gmv_lainnya = float(df.loc[df['Kategori'] == 'Lainnya', 'GMV'].sum())
    
    # Hitung CUPS per kategori. Otomatis mencari kolom bernama 'Cups' atau 'Product num'
    kolom_cups = 'Cups' # Default
    for col in df.columns:
        if col.lower() in ['cups', 'product num']:
            kolom_cups = col
            break
            
    if kolom_cups in df.columns:
        cups_makanan = int(df.loc[df['Kategori'] == 'Makanan', kolom_cups].sum())
        cups_minuman = int(df.loc[df['Kategori'] == 'Minuman', kolom_cups].sum())
        cups_merch = int(df.loc[df['Kategori'] == 'Merchandise', kolom_cups].sum())
        cups_lainnya = int(df.loc[df['Kategori'] == 'Lainnya', kolom_cups].sum())
        # hitung cups pada kategori makanan (Jasmine Tea Cake, Earl Grey Cake, dan seterusnya)
        cups_jct = int(df.loc[df['product name'].str.contains('Jasmine Tea Cake'), kolom_cups].sum())
        cups_lcc = int(df.loc[df['product name'].str.contains('Lemon Cheese Cake'), kolom_cups].sum())
        cups_poc = int(df.loc[df['product name'].str.contains('Peach Oolong Cake'), kolom_cups].sum())
        cups_egc = int(df.loc[df['product name'].str.contains('Earl Grey Cake'), kolom_cups].sum())
        cups_cc = int(df.loc[df['product name'].str.contains('Chocolate Cake'), kolom_cups].sum())
        cups_cct = int(df.loc[df['product name'].str.contains('CHAGEE Classic Tiramisu'), kolom_cups].sum())
        cups_pcpc = int(df.loc[df['product name'].str.contains('Pandan Coco Palm Cake'), kolom_cups].sum())
        cups_oc = int(df.loc[df['product name'].str.contains('Osmanthus Choux'), kolom_cups].sum())
    else:
        cups_makanan = cups_minuman = cups_merch = cups_lainnya = 0
        cups_jct = cups_lcc = cups_poc = cups_egc = cups_cc = cups_cct = cups_pcpc = cups_oc = 0
    gmv_food = float(df.loc[df['Kategori'] == 'Makanan', 'GMV'].sum())
    
    
    # Simpan hasil rekap per toko (Diurutkan persis sesuai dengan header Google Sheets)
    hasil_rekap.append([
        nama_toko, 
        gmv_makanan, cups_makanan,
        gmv_minuman, cups_minuman, 
        gmv_merch, cups_merch, 
        gmv_lainnya, cups_lainnya,
    ])
    
    #REKAP DETAIL MAKANAN
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

#REKAP DETAIL MAKANAN
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

print(f"Selesai! Data dari {len(excel_files)} toko telah dipindahkan ke Google Sheets menggunakan Master Kategori.")