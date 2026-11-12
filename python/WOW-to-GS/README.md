# Dashboard Scraper → Google Sheets (Python + Playwright)

Paket ini mengambil data metric (GMV, Gross Sales, GS%, TC, AOV, Cups, dll)
dari dashboard BI yang dirender via JavaScript (termasuk di dalam iframe),
lalu menulis ke Google Sheets secara otomatis.

---

## 1. Install Python & dependencies

### 1.1 Pastikan Python terinstall
Cek versi (minimal Python 3.9+):
```bash
python3 --version
```
Kalau belum ada, download di https://www.python.org/downloads/

### 1.2 Buat virtual environment (opsional tapi disarankan)
```bash
cd dashboard-scraper
python3 -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows
```

### 1.3 Install semua library Python
```bash
pip install -r requirements.txt
```

### 1.4 Install browser untuk Playwright
Playwright butuh browser engine sendiri (Chromium), install dengan:
```bash
# Mac/Linux
playwright install chromium
# Windows
playwright install chromium
```

---

## 2. Setup akses Google Sheets (Service Account)

1. Buka https://console.cloud.google.com/
2. Buat project baru (atau pakai yang sudah ada).
3. Aktifkan **Google Sheets API** dan **Google Drive API** (cari di "APIs & Services" → "Enable APIs").
4. Buat **Service Account**: "APIs & Services" → "Credentials" → "Create Credentials" → "Service Account".
5. Setelah service account dibuat, masuk ke tab "Keys" → "Add Key" → "Create new key" → pilih **JSON** → download.
6. Rename file JSON yang didownload menjadi `service_account.json`, taruh di folder `dashboard-scraper/`.
7. Buka file JSON tersebut, salin alamat email-nya (formatnya seperti `xxx@xxx.iam.gserviceaccount.com`).
8. Buka Google Sheet tujuan kamu → klik **Share** → tempel email tersebut → beri akses **Editor**.
9. Salin **Spreadsheet ID** dari URL sheet kamu, contoh:
   `https://docs.google.com/spreadsheets/d/1AbCDeFGhij.../edit` → ID-nya adalah `1AbCDeFGhij...`

---

## 3. Setup file konfigurasi (.env)

Copy `.env.example` jadi `.env`:
```bash
cp .env.example .env
```
Lalu isi semua value-nya:
- `DASHBOARD_URL` → URL dashboard kamu
- `GOOGLE_SHEET_ID` → ID spreadsheet dari langkah 2.9
- `GOOGLE_SHEET_TAB` → nama tab/sheet tujuan (misal `Sheet1`)
- `LOGIN_USERNAME` / `LOGIN_PASSWORD` → isi HANYA jika dashboard pakai form login sederhana (lihat opsi B di bawah). Kalau pakai SSO/2FA, kosongkan saja dan pakai Opsi A.

---

## 4. Login ke Dashboard — Dua Opsi

### Opsi A (Direkomendasikan): Pakai session/token dari browser kamu sendiri
Cocok untuk SSO, 2FA, atau login kompleks lainnya. Kamu login manual SEKALI,
session-nya disimpan, lalu dipakai berulang kali oleh scraper.

```bash
python export_login_state.py
```
- Browser akan terbuka otomatis.
- Login manual seperti biasa (termasuk isi password, 2FA, dsb).
- Setelah dashboard berhasil tampil, kembali ke terminal, tekan **ENTER**.
- File `storage_state.json` akan otomatis dibuat — ini berisi cookie & token session kamu.

> Catatan: token/session ini biasanya punya masa berlaku (misal beberapa jam/hari).
> Kalau scraper mulai gagal login, cukup jalankan ulang `export_login_state.py`.

### Opsi B: Auto-login pakai username & password
Hanya works kalau login dashboard berupa form sederhana (tanpa SSO/2FA/captcha).
Isi `LOGIN_USERNAME` dan `LOGIN_PASSWORD` di `.env`, lalu sesuaikan selector
login di `scraper.py` pada fungsi `login_with_form()` (cari `input[name='username']`
dst, sesuaikan dengan elemen form login dashboard kamu via Inspect Element).

---

## 5. Sesuaikan selector data (WAJIB sebelum scraping pertama)

Di `scraper.py`, bagian `METRICS_SELECTORS` dan `IFRAME_URL_CONTAINS` adalah
**contoh/template** — kamu perlu sesuaikan dengan struktur HTML dashboard
kamu yang sebenarnya:

1. Buka dashboard di Chrome.
2. Klik kanan pada angka GMV → **Inspect**.
3. Lihat di DevTools, dashboard ada di dalam `<iframe>` atau tidak. Kalau ada,
   catat sebagian URL/src iframe-nya, isi ke `IFRAME_URL_CONTAINS`.
4. Lihat class/struktur HTML elemen angka tersebut, sesuaikan `METRICS_SELECTORS`.
5. Jalankan `scraper.py` pertama kali dengan `headless=False` (ubah sementara
   di `scraper.py`, baris `browser = p.chromium.launch(headless=True)` →
   `headless=False`) supaya kamu bisa lihat prosesnya secara visual untuk debug.

---

## 6. Jalankan scraping

```bash
python scraper.py
```
Jika berhasil, akan muncul log angka yang ter-scrape, dan baris baru otomatis
ditambahkan ke Google Sheets kamu dengan timestamp.

---

## 7. Otomatisasi terjadwal (opsional)

### Opsi 1: Cron job (Mac/Linux)
```bash
crontab -e
```
Tambahkan baris ini untuk jalan tiap jam:
```
0 * * * * cd /path/ke/dashboard-scraper && /path/ke/venv/bin/python scraper.py >> log.txt 2>&1
```

### Opsi 2: Task Scheduler (Windows)
Buat scheduled task yang menjalankan:
```
venv\Scripts\python.exe scraper.py
```

### Opsi 3: GitHub Actions (server selalu hidup, gratis untuk repo publik/limit tertentu)
Bisa saya bantu buatkan workflow `.yml`-nya kalau kamu mau pakai opsi ini —
tapi perlu diperhatikan: kalau pakai Opsi A (storage_state.json) untuk login,
file token tersebut perlu disimpan sebagai GitHub Secret dan di-refresh berkala
karena bersifat sensitif dan bisa expired.

---

## Troubleshooting

| Masalah | Penyebab umum | Solusi |
|---|---|---|
| Semua metric `None` | Selector salah | Inspect ulang elemen HTML, perbaiki `METRICS_SELECTORS` |
| Timeout saat ambil elemen | Iframe salah / data belum render | Perbesar `wait_for_timeout`, cek `IFRAME_URL_CONTAINS` |
| Login gagal terus (Opsi A) | Token expired | Jalankan ulang `export_login_state.py` |
| Error akses Google Sheets | Service account belum di-share ke sheet | Ulangi langkah 2.8 |
| `playwright install` gagal | Koneksi/permission | Coba `playwright install --with-deps chromium` |
