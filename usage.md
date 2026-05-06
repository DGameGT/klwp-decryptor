# Cara Pakai KLWP Preset Decryptor

> Tool ini dibuat berdasarkan riset **DGameXO (dgxo / dgamexo)**

---

## Persiapan

### 1. Install Python 3
Pastikan Python 3 sudah terinstall di sistem kamu.

```bash
python3 --version
```

### 2. Install dependency

```bash
pip install rich questionary pycryptodome
```

### 3. Struktur folder

Pastikan `blank.klwp` ada satu folder dengan `klwp_decrypt.py`:

```
📁 folder kamu/
├── klwp_decrypt.py
└── blank.klwp
```

---

## Menjalankan Tool

```bash
python3 klwp_decrypt.py
```

Setelah dijalankan, akan muncul menu interaktif. Navigasi menggunakan **tombol panah**, pilih dengan **Enter**.

---

## Menu

### 1 — Cek Version Release

Baca release ID dari file `.klwp`.

**Input:** path ke file `.klwp`

**Output:** release ID (contoh: `363228708`)

Release ID ini dibutuhkan untuk mendownload APK KLWP yang sesuai di menu 4.

---

### 2 — Cek Author

Baca nama author dan email yang tercatat di dalam preset.

**Input:** path ke file `.klwp`

**Output:** author dan email

Catat informasi ini — dibutuhkan saat unlock di menu 6.

---

### 3 — Cek Locked Status

Cek apakah preset terkunci atau tidak.

**Input:** path ke file `.klwp`

**Output:** `LOCKED` atau `UNLOCKED`

---

### 4 — Download KLWP APK

Download APK KLWP sesuai versi yang dibutuhkan.

**Pilihan:**

- **Auto** — masukkan Release ID, tool otomatis download via `wget` atau `curl` ke folder saat ini
- **Manual** — tool tampilkan link halaman download, kamu cari dan download sendiri

> `wget` atau `curl` harus terinstall untuk mode auto.

---

### 5 — Teardown APK — Cari Seed

Ekstrak seed enkripsi dari native library di dalam APK KLWP.

**Input:** path ke file APK KLWP (`.apk`)

**Output:** tabel berisi tiga seed:

| Fungsi | Keterangan |
|---|---|
| Preset Unlock Seed | Digunakan untuk unlock preset |
| Komponent Unlock Seed | Untuk unlock komponent |
| Service DES Seed | Untuk service layer |

> `strings` dan `objdump` harus tersedia di sistem (biasanya sudah ada di Linux/macOS).

---

### 6 — Unlock Preset

Proses utama — dekripsi dan rekonstruksi preset terkunci.

**Yang dibutuhkan sebelum menjalankan menu ini:**
- File `.klwp` yang terkunci
- APK KLWP versi yang sesuai (cek release ID dulu via menu 1, download via menu 4)
- `blank.klwp` sudah ada di folder yang sama dengan script

**Langkah yang berjalan:**

1. Kamu diminta path ke file `.klwp`
2. Kamu diminta path ke APK KLWP
3. Tool ekstrak seed dari APK secara otomatis
4. Pilih mode input author/email:
   - **Otomatis** — ambil langsung dari data di dalam preset
   - **Manual** — kamu input sendiri
   - **Brute force** — coba beberapa kandidat sekaligus, pisah dengan koma
5. Tool mencoba semua kombinasi key dan menampilkan skor (0–80)
6. Kamu diminta path output untuk file hasil
7. Tool rekonstruksi preset menggunakan `blank.klwp` sebagai shell bersih, inject layer hasil dekripsi, copy aset (bitmaps/fonts/icons), dan simpan sebagai `.klwp` baru

**Indikator skor dekripsi:**

| Skor | Arti |
|---|---|
| 70–80 | Key benar, dekripsi berhasil |
| 40–69 | Mungkin benar, perlu dicek manual |
| 0–39 | Key salah, coba kombinasi lain |

---

## Alur Lengkap (dari awal)

```
1. Jalankan menu 1 → catat Release ID dari preset
2. Jalankan menu 4 → download APK KLWP sesuai Release ID
3. Jalankan menu 5 → ekstrak seed dari APK (opsional, untuk cek)
4. Jalankan menu 6 → unlock preset
```

---

## Troubleshooting

**Skor di bawah 40**
Author atau email yang digunakan saat mengunci berbeda dengan yang ada di preset. Coba mode brute force dengan beberapa variasi nama.

**`blank.klwp` tidak ditemukan**
Pastikan file `blank.klwp` ada di folder yang sama dengan `klwp_decrypt.py`.

**`strings` / `objdump` tidak ditemukan**
Install binutils:
```bash
# Debian/Ubuntu
sudo apt install binutils

# macOS
brew install binutils
```

**`wget` / `curl` tidak ditemukan**
```bash
# Debian/Ubuntu
sudo apt install wget

# macOS
brew install wget
```

**JSONDecodeError setelah dekripsi**
Kemungkinan padding tidak terbaca dengan benar. Coba kombinasi author/email yang berbeda.

---

## Catatan

- Tool ini **stateless** — setiap menu tanya input dari awal, tidak ada data yang disimpan antar sesi
- `blank.klwp` wajib ada — digunakan sebagai shell bersih agar key dari preset lama tidak ikut terbawa
- Seed enkripsi berbeda tiap versi KLWP — selalu ekstrak dari APK yang sesuai dengan release ID preset
