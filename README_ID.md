# Dekripsi Preset KLWP yang Terkunci: Panduan Teknis Lengkap

> Didokumentasikan oleh **DGameXO (dgxo / dgamexo)**
> Panduan ini mencakup proses lengkap mulai dari memahami skema enkripsi hingga memulihkan preset yang terkunci.

---

## Daftar Isi

1. [Gambaran Umum](#gambaran-umum)
2. [Cara Kerja Enkripsi KLWP](#cara-kerja-enkripsi-klwp)
3. [Yang Dibutuhkan](#yang-dibutuhkan)
4. [Langkah 1: Identifikasi Versi Preset](#langkah-1-identifikasi-versi-preset)
5. [Langkah 2: Download APK yang Sesuai](#langkah-2-download-apk-yang-sesuai)
6. [Langkah 3: Decode APK dengan Apktool](#langkah-3-decode-apk-dengan-apktool)
7. [Langkah 4: Temukan Seed Enkripsi di Native Library](#langkah-4-temukan-seed-enkripsi-di-native-library)
8. [Langkah 5: Pahami Derivasi Key](#langkah-5-pahami-derivasi-key)
9. [Langkah 6: Ekstrak Data Terenkripsi](#langkah-6-ekstrak-data-terenkripsi)
10. [Langkah 7: Brute Force Key](#langkah-7-brute-force-key)
11. [Langkah 8: Dekripsi dan Rekonstruksi Preset](#langkah-8-dekripsi-dan-rekonstruksi-preset)
12. [Langkah 9: Repack dan Import](#langkah-9-repack-dan-import)
13. [Catatan Per Versi](#catatan-per-versi)
14. [Troubleshooting](#troubleshooting)

---

## Gambaran Umum

KLWP (Kustom Live Wallpaper) memungkinkan creator untuk mengunci preset sebelum diekspor, yang mencegah pengguna lain untuk mengedit atau melihat layer di dalamnya. Ketika preset dikunci, data layer-nya dienkripsi dan disimpan di dalam file `.klwp` dengan key `internal_readonly`.

Panduan ini mendokumentasikan proses reverse engineering lengkap yang digunakan untuk menemukan skema enkripsi dan berhasil mendekripsi preset yang terkunci.

### Alur Enkripsi

```
Creator mengunci preset di KLWP
        |
        v
Data layer (JSON array) --> enkripsi DES/ECB --> encode Base64 URL-safe
        |
        v
Disimpan sebagai nilai "internal_readonly" di preset.json dalam file .klwp
```

### Alur Dekripsi

```
Baca "internal_readonly" dari preset.json
        |
        v
Decode Base64 URL-safe --> dekripsi DES/ECB (dengan key yang diturunkan)
        |
        v
JSON array semua layer --> inject ke preset_root.viewgroup_items
        |
        v
Repack sebagai .klwp --> import ke KLWP
```

---

## Cara Kerja Enkripsi KLWP

### Algoritma

KLWP menggunakan **DES (Data Encryption Standard)** dalam mode **ECB (Electronic Codebook)** dengan padding **PKCS7**.

Data terenkripsi diencode menggunakan **Base64 URL-safe** (flag Android `0xa` = `Base64.URL_SAFE`). Artinya string Base64 menggunakan `-` sebagai pengganti `+` dan `_` sebagai pengganti `/`.

Hal ini dikonfirmasi dengan menemukan `DESHelper.kt` yang dikompilasi ke dalam APK di:

```
smali_classes5/z6/a.smali
```

Inisialisasi cipher yang relevan dalam smali:

```smali
const-string v0, "DES"
invoke-static {v0}, Ljavax/crypto/Cipher;->getInstance(Ljava/lang/String;)Ljavax/crypto/Cipher;
const/4 v3, 0x2   # DECRYPT_MODE
invoke-virtual {v0, v3, p0}, Ljavax/crypto/Cipher;->init(ILjava/security/Key;)V
```

### Derivasi Key

Key DES tidak di-hardcode sebagai string biasa. Key diturunkan melalui proses berikut:

```
key = String.format("%08d", hashCode(seed + author + email))
```

Dimana:
- `seed` adalah string yang dikembalikan oleh fungsi native `getPresetUnlockSeed()` dari `liblocal-config-lib.so`
- `author` adalah nilai field `author` di `preset_info` pada saat preset dikunci
- `email` adalah nilai field `email` di `preset_info` pada saat preset dikunci
- `hashCode()` adalah implementasi standar `String.hashCode()` milik Java

String key final diencode sebagai UTF-8 dan hanya **8 byte pertama** yang digunakan sebagai key DES.

### Implementasi Java hashCode

`String.hashCode()` milik Java bersifat deterministik dan bisa direplikasi dalam Python:

```python
def java_hashcode(s):
    h = 0
    for c in s:
        h = (31 * h + ord(c)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return h
```

Perlu dicatat bahwa hasilnya bisa negatif. `String.format("%08d", negative_number)` milik Java menghasilkan string yang lebih panjang dari 8 karakter (misalnya `-236174758`), dan hanya 8 byte pertama yang digunakan sebagai key DES.

### Dari Mana Seed Berasal

Seed dikembalikan oleh fungsi C native yang dimuat dari `liblocal-config-lib.so`. Library ini dimuat melalui:

```java
System.loadLibrary("local-config-lib")
```

Tiga fungsi native di `SeedHelper.kt`:

| Fungsi | Tujuan |
|---|---|
| `getPresetUnlockSeed()` | Seed untuk kunci preset KLWP |
| `getKomponentUnlockSeed()` | Seed untuk kunci komponent KLWP |
| `getServiceDESSeed()` | Seed untuk DES level layanan |

Untuk KLWP v3.63 (build `363228708`), seed yang diekstrak dari `lib/x86_64/liblocal-config-lib.so`:

| Fungsi | Seed |
|---|---|
| `getPresetUnlockSeed` | `poiuyrqoispsx` |
| `getKomponentUnlockSeed` | `askoeruqwoie` |
| `getServiceDESSeed` | `ouweirit72idn` |

---

## Yang Dibutuhkan

- Lingkungan Linux atau macOS (WSL bisa digunakan di Windows)
- `apktool` (versi 2.x) terinstal atau tersedia di `~/bin/apktool`
- `objdump` dan `strings` (biasanya sudah terinstal di Linux)
- `python3` dengan `pycryptodome`: `pip install pycryptodome`
- File `.klwp` yang terkunci dan ingin didekripsi
- Perkiraan terbaik dari **nama author** dan **email** yang digunakan saat preset dikunci
- APK KLWP untuk **versi yang sama** dengan yang digunakan saat mengunci preset

---

## Langkah 1: Identifikasi Versi Preset

File `.klwp` adalah arsip ZIP. Ekstrak langsung dengan `unzip`:

```bash
unzip your_preset.klwp -d preset_extracted
cat preset_extracted/preset.json
```

Cari blok `preset_info`:

```json
{
  "preset_info": {
    "version": 12,
    "title": "Test",
    "author": "dgamexo",
    "release": 363228708,
    "locked": true
  }
}
```

Field `release` adalah `versionCode` Android dari build KLWP yang digunakan untuk mengunci preset.

### Membaca Nomor Release

| nilai release | versi KLWP |
|---|---|
| `363228708` | 3.63b228708 |
| `362224415` | 3.62b224415 |
| `361223012` | 3.61b223012 |
| `360220710` | 3.60b220710 |

Format: 3 digit pertama = versi major.minor, digit sisanya = nomor build.

Perhatikan juga field `author` dan `email`. Ini adalah nilai yang diset pada saat penguncian. Jika file sudah didistribusikan ulang dengan `preset_info` yang dimodifikasi, nilainya mungkin berbeda dari yang asli.

---

## Langkah 2: Download APK yang Sesuai

Download APK KLWP yang sesuai dengan versi `release`.

Arsip resmi: `https://docs.kustom.rocks/docs/downloads/download-klwp/`

APKMirror: `https://www.apkmirror.com/apk/kustom-industries/klwp-live-wallpaper-maker/`

Download varian **Google Play**, bukan AOSP atau Huawei, karena native library-nya bisa berbeda.

Untuk v3.63: `https://kustom.rocks/download/klwp/363228708/google_release`

---

## Langkah 3: Decode APK dengan Apktool

```bash
~/bin/apktool d klwp_google_release_363.apk -o klwp_363_decoded
cd klwp_363_decoded
```

Ini menghasilkan:
- `smali/` sampai `smali_classes5/` - bytecode yang sudah didecompile
- `lib/` - native library
- `assets/` - aset yang dibundel

---

## Langkah 4: Temukan Seed Enkripsi di Native Library

Temukan library-nya:

```bash
find . -name "liblocal-config-lib.so"
```

Gunakan varian `x86_64` untuk analisis.

### Ekstrak String Kandidat

```bash
strings ./lib/x86_64/liblocal-config-lib.so | grep -E ".{8,20}" | head -30
```

Di v3.63, cari:

```
poiuyrqoispsx
ouweirit72idn
askoeruqwoie
```

### Petakan String ke Fungsi

Dapatkan offset file:

```bash
strings -o ./lib/x86_64/liblocal-config-lib.so | grep -E "poiuyrqoispsx|ouweirit72idn|askoeruqwoie|getPresetUnlockSeed|getKomponentUnlockSeed|getServiceDESSeed"
```

Disassemble untuk menemukan offset yang dimuat tiap fungsi:

```bash
objdump -d ./lib/x86_64/liblocal-config-lib.so 2>/dev/null | grep -A10 "getPresetUnlockSeed>"
```

Komentar instruksi `lea` menunjukkan alamat memori yang dimuat. Cocokkan dengan output `strings -o`.

Untuk v3.63 x86_64:

| Offset | String | Fungsi |
|---|---|---|
| `0x598` | `poiuyrqoispsx` | `getPresetUnlockSeed` |
| `0x5a6` | `ouweirit72idn` | `getServiceDESSeed` |
| `0x5b4` | `askoeruqwoie` | `getKomponentUnlockSeed` |

---

## Langkah 5: Pahami Derivasi Key

Direkonstruksi dari `smali_classes5/org/kustom/lib/render/RootLayerModule.smali`:

```java
String seed   = SeedHelper.getPresetUnlockSeed();
String author = presetInfo.getAuthor();
String email  = presetInfo.getEmail();

String combined = seed + (author != null ? author : "") + (email != null ? email : "");
int    hash     = combined.hashCode();
String key      = String.format("%08d", hash);
// Hanya 8 byte pertama yang digunakan sebagai key DES
```

Ekuivalen Python:

```python
def java_hashcode(s):
    h = 0
    for c in s:
        h = (31 * h + ord(c)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return h

seed   = "poiuyrqoispsx"
author = "dgamexo"
email  = ""

combined = seed + author + email
h        = java_hashcode(combined)
key_str  = f"{h:08d}"      # misalnya "-236174758"
key      = key_str.encode('utf-8')[:8]
```

---

## Langkah 6: Ekstrak Data Terenkripsi

```bash
grep -o 'internal_readonly[^,}]*' preset_extracted/preset.json > internal_readonly_values.txt
head -c 200 internal_readonly_values.txt
```

Nilainya akan terlihat seperti Base64 URL-safe yang menggunakan karakter `-` dan `_`:

```
internal_readonly": "LajhAAincgvul-7Qluu6YHuXE9XTeqS97dkKe...
```

---

## Langkah 7: Brute Force Key

Dekripsi yang benar menghasilkan JSON yang bisa dibaca dengan skor 80/80 karakter printable di 80 byte pertama.

```python
from Crypto.Cipher import DES
import base64

def java_hashcode(s):
    h = 0
    for c in s:
        h = (31 * h + ord(c)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return h

with open('internal_readonly_values.txt', 'r') as f:
    raw = f.read().strip()

data = raw.split(': "', 1)[1].rstrip('"')
data = data.replace('-', '+').replace('_', '/')
pad  = (4 - len(data) % 4) % 4
data += "=" * pad
encrypted = base64.b64decode(data)

seed = "poiuyrqoispsx"

authors = ["username_kamu", "nama_creator", ""]
emails  = ["kamu@email.com", "creator@email.com", ""]

best = []
for author in authors:
    for email in emails:
        combined = seed + author + email
        h        = java_hashcode(combined)
        key_str  = f"{h:08d}"
        key      = key_str.encode('utf-8')[:8]
        try:
            cipher    = DES.new(key, DES.MODE_ECB)
            decrypted = cipher.decrypt(encrypted)
            score     = sum(1 for b in decrypted[:80] if 32 <= b < 127)
            best.append((score, author, email, key_str, decrypted))
        except Exception:
            pass

best.sort(reverse=True)
for score, author, email, key_str, decrypted in best[:5]:
    print(f"score={score}/80 | author={author!r} | email={email!r} | key={key_str}")
    print(f"  preview: {decrypted[:80]}")
    print()
```

Hasil yang benar menunjukkan `score=80/80` dan preview dimulai dengan `[{"internal_type":`.

---

## Langkah 8: Dekripsi dan Rekonstruksi Preset

```python
from Crypto.Cipher import DES
import base64, json

def java_hashcode(s):
    h = 0
    for c in s:
        h = (31 * h + ord(c)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return h

with open('internal_readonly_values.txt', 'r') as f:
    raw = f.read().strip()

data = raw.split(': "', 1)[1].rstrip('"')
data = data.replace('-', '+').replace('_', '/')
pad  = (4 - len(data) % 4) % 4
data += "=" * pad
encrypted = base64.b64decode(data)

seed   = "poiuyrqoispsx"
author = "dgamexo"
email  = ""

h       = java_hashcode(seed + author + email)
key_str = f"{h:08d}"
key     = key_str.encode('utf-8')[:8]

cipher    = DES.new(key, DES.MODE_ECB)
decrypted = cipher.decrypt(encrypted)

pad_len = decrypted[-1]
if pad_len < 16:
    decrypted = decrypted[:-pad_len]

layers = json.loads(decrypted)
with open('decrypted_layers.json', 'w') as f:
    json.dump(layers, f, ensure_ascii=False)

print(f"Berhasil mendekripsi {len(layers)} objek layer")
```

### Rekonstruksi Menggunakan Shell Preset Kosong

Buat preset kosong baru di KLWP, ekspor sebagai `blank.klwp`, lalu:

```bash
unzip blank.klwp -d blank_ex
```

```python
import json

with open('blank_ex/preset.json') as f:
    shell = json.load(f)

with open('preset_extracted/preset.json') as f:
    original = json.load(f)

with open('decrypted_layers.json') as f:
    layers = json.load(f)

shell['preset_info'] = original['preset_info']
shell['preset_info']['locked'] = False

shell['preset_root'] = original['preset_root']
shell['preset_root'].pop('internal_readonly', None)
shell['preset_root']['viewgroup_items'] = layers

with open('blank_ex/preset.json', 'w') as f:
    json.dump(shell, f, ensure_ascii=False)

print("Berhasil digabung. Jumlah layer:", len(layers))
```

---

## Langkah 9: Repack dan Import

```bash
cp -r preset_extracted/bitmaps blank_ex/
cp -r preset_extracted/fonts   blank_ex/
cp -r preset_extracted/icons   blank_ex/

cd blank_ex
zip -r ../preset_unlocked.klwp .

adb push preset_unlocked.klwp /sdcard/Kustom/wallpapers/preset_unlocked.klwp
```

Buka KLWP, import preset, dan verifikasi semua layer terlihat dan bisa diedit.

---

## Catatan Per Versi

String seed berubah antar versi KLWP. Setiap kali bekerja dengan APK yang berbeda, ekstrak seed lagi dari `liblocal-config-lib.so`.

### Seed yang Diketahui (v3.63, build Google Play)

| Fungsi | Seed |
|---|---|
| `getPresetUnlockSeed` | `poiuyrqoispsx` |
| `getKomponentUnlockSeed` | `askoeruqwoie` |
| `getServiceDESSeed` | `ouweirit72idn` |

### Mengekstrak Seed untuk Versi Lain

```bash
strings -o ./lib/x86_64/liblocal-config-lib.so | grep -E "[a-z0-9]{8,20}"

objdump -d ./lib/x86_64/liblocal-config-lib.so 2>/dev/null \
  | grep -A8 "getPresetUnlockSeed\|getKomponentUnlockSeed\|getServiceDESSeed"
```

---

## Troubleshooting

### Skor di bawah 30/80

Key salah. Penyebab umum:
- Author atau email berbeda pada saat penguncian
- Preset didistribusikan ulang dengan `preset_info` yang dimodifikasi
- Versi atau varian APK salah (AOSP vs Google Play)

### JSONDecodeError setelah dekripsi

Hapus padding PKCS7:

```python
pad_len = decrypted[-1]
if pad_len < 16:
    decrypted = decrypted[:-pad_len]
```

### Preset ter-load tapi layer kosong

Periksa apakah `viewgroup_items` sudah diinjeksikan:

```python
print(len(shell['preset_root'].get('viewgroup_items', [])))
```

Harus lebih dari 0.

### Error padding Base64

Konversi Base64 URL-safe sebelum decode:

```python
data = data.replace('-', '+').replace('_', '/')
pad  = (4 - len(data) % 4) % 4
data += "=" * pad
```

---

## Ringkasan

```
field release di preset.json
        |
        v
Download APK KLWP yang sesuai (build sama, varian Google Play)
        |
        v
apktool d --> smali + lib/
        |
        v
strings + objdump pada liblocal-config-lib.so --> string seed
        |
        v
java_hashcode(seed + author + email) --> format %08d --> key DES 8-byte
        |
        v
Decode Base64 URL-safe --> dekripsi DES ECB --> hapus padding PKCS7
        |
        v
JSON array layer --> inject ke shell preset kosong sebagai viewgroup_items
        |
        v
salin bitmaps/fonts/icons --> repack sebagai .klwp --> import dan verifikasi
```

Proses ini diteliti dan didokumentasikan melalui reverse engineering penuh KLWP v3.63, menelusuri jalur enkripsi dari `RootLayerModule.smali` melalui `SeedHelper.smali` ke native `liblocal-config-lib.so`, dan akhirnya ke `DESHelper.kt` (dikompilasi sebagai `z6/a.smali`).
