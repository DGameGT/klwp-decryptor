# KLWP Locked Preset Decryption: A Complete Technical Guide

> Documented by **DGameXO (dgxo / dgamexo)**
> This guide covers the full process from understanding the encryption scheme to recovering a locked preset.

---

## Table of Contents

1. [Overview](#overview)
2. [How KLWP Encryption Works](#how-klwp-encryption-works)
3. [What You Need](#what-you-need)
4. [Step 1: Identify the Preset Version](#step-1-identify-the-preset-version)
5. [Step 2: Download the Correct APK](#step-2-download-the-correct-apk)
6. [Step 3: Decode the APK with Apktool](#step-3-decode-the-apk-with-apktool)
7. [Step 4: Find the Encryption Seed in the Native Library](#step-4-find-the-encryption-seed-in-the-native-library)
8. [Step 5: Understand the Key Derivation](#step-5-understand-the-key-derivation)
9. [Step 6: Extract the Encrypted Data](#step-6-extract-the-encrypted-data)
10. [Step 7: Brute Force the Key](#step-7-brute-force-the-key)
11. [Step 8: Decrypt and Rebuild the Preset](#step-8-decrypt-and-rebuild-the-preset)
12. [Step 9: Repack and Import](#step-9-repack-and-import)
13. [Version-Specific Notes](#version-specific-notes)
14. [Troubleshooting](#troubleshooting)

---

## Overview

KLWP (Kustom Live Wallpaper) allows creators to lock their presets before exporting, which prevents other users from editing or viewing the internal layers. When a preset is locked, its layer data is encrypted and stored inside the `.klwp` file under the key `internal_readonly`.

This guide documents the full reverse engineering process used to recover the encryption scheme and successfully decrypt a locked preset.

### Encryption Flow

```
Creator locks preset in KLWP
        |
        v
Layer data (JSON array) --> DES/ECB encrypt --> Base64 URL-safe encode
        |
        v
Stored as "internal_readonly" value in preset.json inside .klwp file
```

### Decryption Flow

```
Read "internal_readonly" from preset.json
        |
        v
Base64 URL-safe decode --> DES/ECB decrypt (with derived key)
        |
        v
JSON array of all layers --> inject into preset_root.viewgroup_items
        |
        v
Repack as .klwp --> import into KLWP
```

---

## How KLWP Encryption Works

### Algorithm

KLWP uses **DES (Data Encryption Standard)** in **ECB (Electronic Codebook)** mode with **PKCS7 padding**.

The encrypted data is encoded using **Base64 URL-safe** encoding (Android flag `0xa` = `Base64.URL_SAFE`). This means the Base64 string uses `-` instead of `+` and `_` instead of `/`.

This was confirmed by finding `DESHelper.kt` compiled into the APK at:

```
smali_classes5/z6/a.smali
```

The relevant cipher initialization in smali:

```smali
const-string v0, "DES"
invoke-static {v0}, Ljavax/crypto/Cipher;->getInstance(Ljava/lang/String;)Ljavax/crypto/Cipher;
const/4 v3, 0x2   # DECRYPT_MODE
invoke-virtual {v0, v3, p0}, Ljavax/crypto/Cipher;->init(ILjava/security/Key;)V
```

### Key Derivation

The DES key is not hardcoded as a plain string. Instead, it is derived through the following process:

```
key = String.format("%08d", hashCode(seed + author + email))
```

Where:
- `seed` is a string returned by a native function `getPresetUnlockSeed()` from `liblocal-config-lib.so`
- `author` is the value of the `author` field in `preset_info` at the time the preset was locked
- `email` is the value of the `email` field in `preset_info` at the time the preset was locked
- `hashCode()` is Java's standard `String.hashCode()` implementation

The final key string is encoded as UTF-8 and only the **first 8 bytes** are used as the DES key.

### Java hashCode Implementation

Java's `String.hashCode()` is deterministic and can be replicated in Python:

```python
def java_hashcode(s):
    h = 0
    for c in s:
        h = (31 * h + ord(c)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return h
```

Note that the result can be negative. Java's `String.format("%08d", negative_number)` produces a string longer than 8 characters (e.g., `-236174758`), and only the first 8 bytes are used as the DES key.

### Where the Seed Comes From

The seed is returned by a native C function loaded from `liblocal-config-lib.so`. This library is loaded via:

```java
System.loadLibrary("local-config-lib")
```

The three native functions in `SeedHelper.kt` are:

| Function | Purpose |
|---|---|
| `getPresetUnlockSeed()` | Seed for KLWP preset lock |
| `getKomponentUnlockSeed()` | Seed for KLWP komponent lock |
| `getServiceDESSeed()` | Seed for service-level DES |

For KLWP v3.63 (build `363228708`), the seeds extracted from `lib/x86_64/liblocal-config-lib.so`:

| Function | Seed |
|---|---|
| `getPresetUnlockSeed` | `poiuyrqoispsx` |
| `getKomponentUnlockSeed` | `askoeruqwoie` |
| `getServiceDESSeed` | `ouweirit72idn` |

---

## What You Need

- A Linux or macOS environment (WSL works on Windows)
- `apktool` (version 2.x) installed or available at `~/bin/apktool`
- `objdump` and `strings` (usually pre-installed on Linux)
- `python3` with `pycryptodome`: `pip install pycryptodome`
- The locked `.klwp` file you want to decrypt
- A best guess of the **author name** and **email** used when the preset was locked
- The KLWP APK for the **same version** that was used to lock the preset

---

## Step 1: Identify the Preset Version

A `.klwp` file is a ZIP archive. Extract it directly with `unzip`:

```bash
unzip your_preset.klwp -d preset_extracted
cat preset_extracted/preset.json
```

Look for the `preset_info` block:

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

The `release` field is the Android `versionCode` of the KLWP build used to lock the preset.

### Decoding the Release Number

| release value | KLWP version |
|---|---|
| `363228708` | 3.63b228708 |
| `362224415` | 3.62b224415 |
| `361223012` | 3.61b223012 |
| `360220710` | 3.60b220710 |

Format: first 3 digits = major.minor version, remaining digits = build number.

Also note the `author` and `email` fields. These are the values set at the time of locking. If the file was redistributed with a modified `preset_info`, the values may differ from the originals.

---

## Step 2: Download the Correct APK

Download the KLWP APK matching the `release` version.

Official archive: `https://docs.kustom.rocks/docs/downloads/download-klwp/`

APKMirror: `https://www.apkmirror.com/apk/kustom-industries/klwp-live-wallpaper-maker/`

Download the **Google Play** variant, not AOSP or Huawei, as the native library may differ.

For v3.63: `https://kustom.rocks/download/klwp/363228708/google_release`

---

## Step 3: Decode the APK with Apktool

```bash
~/bin/apktool d klwp_google_release_363.apk -o klwp_363_decoded
cd klwp_363_decoded
```

This produces:
- `smali/` through `smali_classes5/` - decompiled bytecode
- `lib/` - native libraries
- `assets/` - bundled assets

---

## Step 4: Find the Encryption Seed in the Native Library

Locate the library:

```bash
find . -name "liblocal-config-lib.so"
```

Use the `x86_64` variant for analysis.

### Extract Candidate Strings

```bash
strings ./lib/x86_64/liblocal-config-lib.so | grep -E ".{8,20}" | head -30
```

In v3.63, look for:

```
poiuyrqoispsx
ouweirit72idn
askoeruqwoie
```

### Map Strings to Functions

Get file offsets:

```bash
strings -o ./lib/x86_64/liblocal-config-lib.so | grep -E "poiuyrqoispsx|ouweirit72idn|askoeruqwoie|getPresetUnlockSeed|getKomponentUnlockSeed|getServiceDESSeed"
```

Disassemble to find which offset each function loads:

```bash
objdump -d ./lib/x86_64/liblocal-config-lib.so 2>/dev/null | grep -A10 "getPresetUnlockSeed>"
```

The `lea` instruction comment shows the memory address loaded. Cross-reference with `strings -o` output.

For v3.63 x86_64:

| Offset | String | Function |
|---|---|---|
| `0x598` | `poiuyrqoispsx` | `getPresetUnlockSeed` |
| `0x5a6` | `ouweirit72idn` | `getServiceDESSeed` |
| `0x5b4` | `askoeruqwoie` | `getKomponentUnlockSeed` |

---

## Step 5: Understand the Key Derivation

Reconstructed from `smali_classes5/org/kustom/lib/render/RootLayerModule.smali`:

```java
String seed   = SeedHelper.getPresetUnlockSeed();
String author = presetInfo.getAuthor();
String email  = presetInfo.getEmail();

String combined = seed + (author != null ? author : "") + (email != null ? email : "");
int    hash     = combined.hashCode();
String key      = String.format("%08d", hash);
// Only first 8 bytes used as DES key
```

Python equivalent:

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
key_str  = f"{h:08d}"      # e.g. "-236174758"
key      = key_str.encode('utf-8')[:8]
```

---

## Step 6: Extract the Encrypted Data

```bash
grep -o 'internal_readonly[^,}]*' preset_extracted/preset.json > internal_readonly_values.txt
head -c 200 internal_readonly_values.txt
```

The value will look like URL-safe Base64 using `-` and `_` characters:

```
internal_readonly": "LajhAAincgvul-7Qluu6YHuXE9XTeqS97dkKe...
```

---

## Step 7: Brute Force the Key

A correct decryption produces readable JSON with a score of 80/80 printable characters in the first 80 bytes.

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

authors = ["your_username", "creator_name", ""]
emails  = ["your@email.com", "creator@email.com", ""]

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

A correct result shows `score=80/80` and preview begins with `[{"internal_type":`.

---

## Step 8: Decrypt and Rebuild the Preset

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

print(f"Decrypted {len(layers)} layer objects")
```

### Rebuild Using a Blank Preset Shell

Create a new blank preset in KLWP, export it as `blank.klwp`, then:

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

print("Merged. Layer count:", len(layers))
```

---

## Step 9: Repack and Import

```bash
cp -r preset_extracted/bitmaps blank_ex/
cp -r preset_extracted/fonts   blank_ex/
cp -r preset_extracted/icons   blank_ex/

cd blank_ex
zip -r ../preset_unlocked.klwp .

adb push preset_unlocked.klwp /sdcard/Kustom/wallpapers/preset_unlocked.klwp
```

Open KLWP, import the preset, and verify all layers are visible and editable.

---

## Version-Specific Notes

The seed string changes between KLWP versions. Each time you work with a different APK, extract the seed again from `liblocal-config-lib.so`.

### Known Seeds (v3.63, Google Play build)

| Function | Seed |
|---|---|
| `getPresetUnlockSeed` | `poiuyrqoispsx` |
| `getKomponentUnlockSeed` | `askoeruqwoie` |
| `getServiceDESSeed` | `ouweirit72idn` |

### Extracting Seeds for Other Versions

```bash
strings -o ./lib/x86_64/liblocal-config-lib.so | grep -E "[a-z0-9]{8,20}"

objdump -d ./lib/x86_64/liblocal-config-lib.so 2>/dev/null \
  | grep -A8 "getPresetUnlockSeed\|getKomponentUnlockSeed\|getServiceDESSeed"
```

---

## Troubleshooting

### Score below 30/80

Key is wrong. Common causes:
- Author or email was different at time of locking
- Preset was redistributed with modified `preset_info`
- Wrong APK version or variant (AOSP vs Google Play)

### JSONDecodeError after decryption

Strip PKCS7 padding:

```python
pad_len = decrypted[-1]
if pad_len < 16:
    decrypted = decrypted[:-pad_len]
```

### Preset loads but layers are empty

Check that `viewgroup_items` was injected:

```python
print(len(shell['preset_root'].get('viewgroup_items', [])))
```

Must be greater than 0.

### Base64 padding error

Convert URL-safe Base64 before decoding:

```python
data = data.replace('-', '+').replace('_', '/')
pad  = (4 - len(data) % 4) % 4
data += "=" * pad
```

---

## Summary

```
release field in preset.json
        |
        v
Download matching KLWP APK (same build, Google Play variant)
        |
        v
apktool d --> smali + lib/
        |
        v
strings + objdump on liblocal-config-lib.so --> seed string
        |
        v
java_hashcode(seed + author + email) --> format %08d --> 8-byte DES key
        |
        v
Base64 URL-safe decode --> DES ECB decrypt --> strip PKCS7 padding
        |
        v
JSON array of layers --> inject into blank preset shell as viewgroup_items
        |
        v
copy bitmaps/fonts/icons --> repack as .klwp --> import and verify
```

This process was researched and documented through full reverse engineering of KLWP v3.63, tracing the encryption path from `RootLayerModule.smali` through `SeedHelper.smali` to the native `liblocal-config-lib.so`, and finally to `DESHelper.kt` (compiled as `z6/a.smali`).
