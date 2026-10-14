# Indonesia e-Faktur Coretax DJP Sync & Automation
**Odoo 17.0 Enterprise-Grade Tax Localization Module**  
*Built for Indonesian Tax Reform (PMK No. 112/PMK.03/2022 & Coretax DJP Integration)*

---

## 🌟 Executive Overview
Modul ini mengotomatiskan penerbitan dan pelaporan Faktur Pajak Elektronik langsung dari antarmuka Invoice Odoo 17, mengeliminasi proses ekspor-impor manual CSV yang rawan *human error* dan sanksi denda pajak.

### Key Architectural Highlights
1. **Seamless Core Model Inheritance:** Mewarisi langsung model `account.move` tanpa merusak alur akuntansi standar Odoo.
2. **16-Digit NIK/NPWP Validation:** Algoritma pembersihan dan validasi panjang digit otomatis sesuai format Coretax terkini.
3. **Automated XML Schema DJP Generator:** Kompilasi instan DPP (Dasar Pengenaan Pajak), PPN 11%/12%, dan kode transaksi faktur ke format XML resmi DJP Coretax.
4. **Audit Trail & NSFP Lifecycle:** Melacak riwayat perubahan nomor seri faktur pajak dan status dokumen (*Draft -> Ready -> Generated -> Posted*).

---

## 🛠️ Tech Stack & Standards
- **Framework:** Odoo 17.0 Community & Enterprise
- **Language:** Python 3.10+, XML Views
- **Standard:** OCA (Odoo Community Association) Architecture Guide
- **Database:** PostgreSQL 15+

---

## 🚀 Installation & Local Testing (Docker Environment)

1. Clone repositori ke folder `custom_addons` Odoo Anda:
   ```bash
   git clone https://github.com/your-username/id_efaktur_coretax_sync.git ./custom_addons/id_efaktur_coretax_sync
   ```
2. Jalankan container Odoo 17 & PostgreSQL:
   ```bash
   docker compose up -d
   ```
3. Akses Odoo di browser: `http://localhost:8069`.
4. Masuk ke **Apps** ➔ Klik **Update Apps List** ➔ Cari `id_efaktur_coretax_sync` ➔ Klik **Activate**.

---

## 📸 Workflow Demonstration
1. Buat **Customer Invoice** baru, pilih pelanggan dengan data NPWP/NIK 16 digit.
2. Masukkan item transaksi, konfirmasi invoice (*Post*).
3. Buka tab **e-Faktur Coretax DJP**, masukkan NSFP resmi.
4. Klik tombol **"Generate Coretax XML"** di header invoice.
5. Unduh file XML yang dihasilkan dan siap diunggah ke portal Coretax DJP.

---
**Author:** Ridlo Abdullah Ulinnuha  
**License:** LGPL-3
