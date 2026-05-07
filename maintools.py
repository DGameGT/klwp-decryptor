#!/usr/bin/env python3
"""
KLWP Preset Decryptor
Berdasarkan riset oleh DGameXO (dgxo / dgamexo)
"""

import os
import sys
import json
import base64
import zipfile
import shutil
import subprocess
import tempfile
import re
import platform

# ── Dependency check ──────────────────────────────────────────────────────────
missing = []
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.rule import Rule
    from rich.align import Align
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Confirm
except ImportError:
    missing.append("rich")

try:
    import questionary
    from questionary import Style as QStyle
except ImportError:
    missing.append("questionary")

try:
    from Crypto.Cipher import DES
except ImportError:
    missing.append("pycryptodome")

if missing:
    print(f"[ERROR] Library belum terinstall: {', '.join(missing)}")
    print(f"Jalankan: pip install {' '.join(missing)}")
    sys.exit(1)

# ── Setup ─────────────────────────────────────────────────────────────────────
console = Console()

style = QStyle([
    ("qmark",       "fg:#f5a623 bold"),
    ("question",    "bold"),
    ("answer",      "fg:#4fc3f7 bold"),
    ("pointer",     "fg:#00ff00 bold"),
    ("highlighted", "fg:#00ff00 bold"),
    ("selected",    "fg:#4fc3f7"),
    ("instruction", "fg:#6c6c6c"),
    ("text",        ""),
    ("disabled",    "fg:#858585 italic"),
])

DOWNLOAD_BASE = "https://kustom.rocks/download/klwp/{release}/google_release"
DOWNLOAD_DOCS = "https://docs.kustom.rocks/docs/downloads/download-klwp/"
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
BLANK_KLWP    = os.path.join(SCRIPT_DIR, "blank.klwp")

# ── UI Helpers ────────────────────────────────────────────────────────────────
def ok(msg):   console.print(f"[bold green]✓[/bold green] {msg}")
def err(msg):  console.print(f"[bold red]✗[/bold red] {msg}")
def info(msg): console.print(f"[dim cyan]ℹ[/dim cyan] {msg}")
def warn(msg): console.print(f"[bold yellow]⚠[/bold yellow] {msg}")
def br():      console.print()

def separator(title):
    br()
    console.print(Rule(f"[bold yellow]{title}[/bold yellow]", style="yellow"))
    br()

def show_banner():
    console.clear()
    ascii_art = """[bold cyan]
 ____   ____                        __  __  ___  
|  _ \ / ___| __ _ _ __ ___   ___   \ \/ / / _ \ 
| | | | |  _ / _` | '_ ` _ \ / _ \   \  / | | | |
| |_| | |_| | (_| | | | | | |  __/   /  \ | |_| |
|____/ \____|\__,_|_| |_| |_|\___|  /_/\_\ \___/ 
[/bold cyan]"""
    info_text = "[bold white]Author:[/bold white] [green]DGameGT/DGameXO[/green]  |  [bold white]Support:[/bold white] [green]othersupport@dgxo.my.id[/green]"

    panel_content = Align.center(ascii_art + "\n" + info_text)
    console.print(Panel(panel_content, border_style="cyan", padding=(1, 2), title="[bold yellow]KLWP Decryptor TUI[/bold yellow]"))
    br()

def pause():
    br()
    console.input("[blink dim white]Tekan Enter untuk kembali ke menu...[/blink dim white]")

# ── File Picker ───────────────────────────────────────────────────────────────
def _pick_zenity(title, filetypes):
    cmd = ["zenity", "--file-selection", f"--title={title}"]
    for name, pattern in filetypes:
        cmd += [f"--file-filter={name} | {pattern}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    path = r.stdout.strip()
    return path if path and os.path.exists(path) else None

def _pick_kdialog(title, filetypes):
    filters = " ".join(pat for _, pat in filetypes)
    cmd = ["kdialog", "--getopenfilename", os.path.expanduser("~"), filters, "--title", title]
    r = subprocess.run(cmd, capture_output=True, text=True)
    path = r.stdout.strip()
    return path if path and os.path.exists(path) else None

def _pick_yad(title, filetypes):
    cmd = ["yad", "--file-selection", f"--title={title}"]
    for name, pattern in filetypes:
        cmd += [f"--file-filter={name} | {pattern}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    path = r.stdout.strip()
    return path if path and os.path.exists(path) else None

def _pick_tkinter(title, filetypes):
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(title=title, filetypes=filetypes)
        root.destroy()
        return path if path and os.path.exists(path) else None
    except Exception:
        return None

def _pick_powershell(title, filetypes):
    exts = ";".join(pat.lstrip("*") for _, pat in filetypes)
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$d = New-Object System.Windows.Forms.OpenFileDialog;"
        f'$d.Title = "{title}";'
        f'$d.Filter = "Files|{exts}";'
        "if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $d.FileName }"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    path = r.stdout.strip()
    return path if path and os.path.exists(path) else None

def pick_file(title="Pilih File", filetypes=None):
    if filetypes is None:
        filetypes = [("All Files", "*")]
    info(f"Membuka file picker: [dim]{title}[/dim]")

    pickers = [_pick_powershell, _pick_tkinter] if platform.system() == "Windows" else [_pick_zenity, _pick_kdialog, _pick_yad, _pick_tkinter]
    for picker in pickers:
        try:
            path = picker(title, filetypes)
            if path:
                ok(f"Dipilih: [cyan]{path}[/cyan]")
                return path
        except:
            continue

    warn("File picker tidak tersedia, input path manual.")
    p = questionary.path(f"{title} (ketik path):", style=style).ask()
    if not p:
        return None
    p = p.strip()
    if not os.path.exists(p):
        err(f"File tidak ditemukan: {p}")
        return None
    return p

def pick_klwp(): return pick_file("Pilih file .klwp", [("KLWP Preset", "*.klwp"), ("All Files", "*")])
def pick_apk():  return pick_file("Pilih file APK KLWP", [("APK", "*.apk"), ("All Files", "*")])

# ── Preset reader & Crypto ────────────────────────────────────────────────────
def read_preset_json(klwp_path):
    try:
        with zipfile.ZipFile(klwp_path) as z:
            with z.open("preset.json") as f:
                return json.load(f)
    except Exception as e:
        err(f"Gagal baca preset.json: {e}")
        return None

def java_hashcode(s):
    h = 0
    for c in s:
        h = (31 * h + ord(c)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return h

def derive_key(seed, author, email):
    combined = seed + (author or "") + (email or "")
    h = java_hashcode(combined)
    return f"{h:08d}".encode("utf-8")[:8]

def decrypt_payload(b64, key):
    try:
        data = b64.replace("-", "+").replace("_", "/")
        data += "=" * ((4 - len(data) % 4) % 4)
        encrypted = base64.b64decode(data)
        cipher = DES.new(key, DES.MODE_ECB)
        dec = cipher.decrypt(encrypted)
        pad = dec[-1]
        if 0 < pad < 16:
            dec = dec[:-pad]
        return dec
    except Exception:
        return None

def score_bytes(data):
    if not data:
        return 0
    # Cek prefix JSON valid sebagai validasi tambahan
    try:
        preview = data[:80]
        printable = sum(1 for b in preview if 32 <= b < 127)
        # Bonus kalau dimulai dengan tanda JSON array/object
        if data[:2] in (b'[{', b'[ '):
            printable += 10
        return min(printable, 80)
    except Exception:
        return 0

# ── Seed Extraction ───────────────────────────────────────────────────────────
def extract_seed_from_so(so_path):
    seeds = {}
    try:
        # Step 1: Parse section headers buat mapping vaddr <-> file offset
        readelf = subprocess.run(
            ["readelf", "-S", "--wide", so_path],
            capture_output=True, text=True, timeout=30
        )
        sections = []
        for line in readelf.stdout.splitlines():
            m = re.search(
                r'\[\s*\d+\]\s+\S+\s+\S+\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)',
                line
            )
            if m:
                vaddr = int(m.group(1), 16)
                foff  = int(m.group(2), 16)
                size  = int(m.group(3), 16)
                if size > 0:
                    sections.append((vaddr, foff, size))

        def vaddr_to_foff(va):
            for base_va, base_off, size in sections:
                if base_va <= va < base_va + size:
                    return base_off + (va - base_va)
            return None

        # Step 2: Kumpulkan kandidat string dengan file offset-nya
        str_result = subprocess.run(
            ["strings", "-o", so_path],
            capture_output=True, text=True, timeout=30
        )
        offset_to_str = {}
        for line in str_result.stdout.strip().splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                off, s = int(parts[0]), parts[1]
                if 8 <= len(s) <= 20 and re.match(r'^[a-z0-9]+$', s):
                    offset_to_str[off] = s

        # Step 3: Disassemble dan map tiap fungsi ke string-nya
        dump = subprocess.run(
            ["objdump", "-d", so_path],
            capture_output=True, text=True, timeout=60
        )
        txt = dump.stdout

        fn_names = ["getPresetUnlockSeed", "getKomponentUnlockSeed", "getServiceDESSeed"]
        fn_map   = {fn: None for fn in fn_names}

        for fn in fn_names:
            # Cari fungsi — coba full JNI name dulu, fallback ke short name
            idx = txt.find(f"<Java_org_kustom_lib_crypto_SeedHelper_{fn}>")
            if idx == -1:
                idx = txt.find(f"<{fn}>")
            if idx == -1:
                continue

            block = txt[idx: idx + 600]

            # objdump tulis resolved address sebagai comment setelah #
            # contoh: lea -0x1e9(%rip),%rsi   # 598 <note_end+0x2c8>
            for m in re.finditer(r'#\s*([0-9a-f]+)', block):
                try:
                    va = int(m.group(1), 16)
                except ValueError:
                    continue

                # Coba match langsung (beberapa build kebetulan offset == vaddr)
                if va in offset_to_str:
                    fn_map[fn] = offset_to_str[va]
                    break

                # Konversi vaddr ke file offset lewat section map
                fo = vaddr_to_foff(va)
                if fo is not None:
                    if fo in offset_to_str:
                        fn_map[fn] = offset_to_str[fo]
                        break
                    # Fuzzy match kecil — toleransi alignment 4 byte
                    for off, s in offset_to_str.items():
                        if abs(off - fo) <= 4:
                            fn_map[fn] = s
                            break

                if fn_map[fn]:
                    break

        # Fallback heuristic kalau ada yang masih None
        unmapped = [fn for fn in fn_names if fn_map[fn] is None]
        if unmapped:
            warn(f"Fallback heuristic untuk: {unmapped}")
            used = set(fn_map.values()) - {None}
            # Urutkan by offset biar deterministik
            remaining = sorted(
                [(off, s) for off, s in offset_to_str.items() if s not in used],
                key=lambda x: x[0]
            )
            for fn, (_, s) in zip(unmapped, remaining):
                fn_map[fn] = s
                warn(f"  {fn} -> {s!r} (heuristic, mungkin tidak akurat)")

        seeds = {k: v for k, v in fn_map.items() if v}

    except Exception as e:
        err(f"Error extract seed: {e}")

    return seeds

def extract_seed_from_apk(apk_path):
    with tempfile.TemporaryDirectory() as tmp:
        try:
            with zipfile.ZipFile(apk_path) as z:
                candidates = [n for n in z.namelist() if "liblocal-config-lib" in n and n.endswith(".so")]
                if not candidates:
                    err("liblocal-config-lib.so tidak ditemukan di APK")
                    return {}
                # Prioritas: x86_64 > arm64 > yang lain
                target = next(
                    (c for c in candidates if "x86_64" in c),
                    next((c for c in candidates if "arm64" in c), candidates[0])
                )
                dest = os.path.join(tmp, "liblocal-config-lib.so")
                with z.open(target) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                info(f"Library: [dim]{target}[/dim]")
                return extract_seed_from_so(dest)
        except Exception as e:
            err(f"Gagal ekstrak .so dari APK: {e}")
            return {}

# ── Menu Actions ──────────────────────────────────────────────────────────────
def menu_check_release():
    separator("Cek Version Release")
    path = pick_klwp()
    if not path:
        return
    data = read_preset_json(path)
    if not data:
        return
    release = data.get("preset_info", {}).get("release", "tidak ditemukan")
    br()
    console.print(Panel(
        Align.center(f"[bold cyan]Release ID: {release}[/bold cyan]"),
        border_style="cyan", padding=(1, 4)
    ))

def menu_check_author():
    separator("Cek Author")
    path = pick_klwp()
    if not path:
        return
    data = read_preset_json(path)
    if not data:
        return
    ib = data.get("preset_info", {})
    br()
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="dim")
    t.add_column(style="bold white")
    t.add_row("Author", ib.get("author", "(kosong)"))
    t.add_row("Email",  ib.get("email",  "(kosong)"))
    console.print(Panel(t, title="[blue]Author Info[/blue]", border_style="blue", padding=(1, 4)))

def menu_check_locked():
    separator("Cek Locked Status")
    path = pick_klwp()
    if not path:
        return
    data = read_preset_json(path)
    if not data:
        return
    locked = data.get("preset_info", {}).get("locked", False)
    br()
    if locked:
        console.print(Panel(
            Align.center("[bold red]LOCKED[/bold red]\nPreset dikunci oleh pemilik"),
            border_style="red", padding=(1, 4)
        ))
    else:
        console.print(Panel(
            Align.center("[bold green]UNLOCKED[/bold green]\nPreset bebas diedit"),
            border_style="green", padding=(1, 4)
        ))

def menu_download_apk():
    separator("Download KLWP APK")
    choice = questionary.select(
        "Pilih metode:",
        choices=["Auto — download otomatis", "Manual — cari di browser"],
        style=style
    ).ask()
    if not choice:
        return

    if "Manual" in choice:
        br()
        info("Buka halaman berikut di browser:")
        console.print(f"  [underline cyan]{DOWNLOAD_DOCS}[/underline cyan]")
        return

    release_id = questionary.text("Masukkan Release ID:", style=style).ask()
    if not release_id or not release_id.strip().isdigit():
        err("Release ID harus berupa angka.")
        return

    url         = DOWNLOAD_BASE.format(release=release_id.strip())
    output_file = os.path.join(SCRIPT_DIR, f"klwp_{release_id.strip()}.apk")
    br()
    info(f"URL    : {url}")
    info(f"Output : {output_file}")
    br()

    if shutil.which("wget"):
        cmd = ["wget", "-O", output_file, url]
    elif shutil.which("curl"):
        cmd = ["curl", "-L", "-o", output_file, url]
    else:
        err("wget / curl tidak ditemukan.")
        return

    try:
        subprocess.run(cmd, check=True)
        br()
        if os.path.exists(output_file) and os.path.getsize(output_file) > 100_000:
            ok(f"APK berhasil didownload: [bold]{output_file}[/bold]")
        else:
            err("Download selesai tapi file tampak tidak valid.")
    except subprocess.CalledProcessError:
        err("Download gagal. Cek koneksi atau coba manual.")

def menu_teardown_apk():
    separator("Teardown APK — Cari Seed")
    apk_path = pick_apk()
    if not apk_path:
        return
    br()
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
        t = prog.add_task("Mengekstrak library & mencari seed...", total=None)
        seeds = extract_seed_from_apk(apk_path)
        prog.remove_task(t)
    br()
    if not seeds:
        err("Seed tidak ditemukan. Pastikan APK valid.")
        return

    tbl = Table(title="Seed Ditemukan", border_style="green")
    tbl.add_column("Fungsi", style="dim")
    tbl.add_column("Seed", style="bold cyan")
    labels = {
        "getPresetUnlockSeed":    "Preset Unlock",
        "getKomponentUnlockSeed": "Komponent Unlock",
        "getServiceDESSeed":      "Service DES",
    }
    for fn, val in seeds.items():
        tbl.add_row(labels.get(fn, fn), val)
    console.print(tbl)

def menu_unlock_preset():
    separator("Unlock Preset")

    if not os.path.exists(BLANK_KLWP):
        err("blank.klwp tidak ditemukan.")
        info("Cara mendapatkannya: buat preset kosong baru di KLWP, lalu export ke folder yang sama dengan script ini dengan nama blank.klwp")
        return

    klwp_path = pick_klwp()
    if not klwp_path:
        return
    preset_data = read_preset_json(klwp_path)
    if not preset_data:
        return

    ib = preset_data.get("preset_info", {})
    if not ib.get("locked"):
        info("Preset ini sudah tidak terkunci.")
        return

    payload = preset_data.get("preset_root", {}).get("internal_readonly")
    if not payload:
        err("Field 'internal_readonly' tidak ditemukan.")
        return

    br()
    apk_path = pick_apk()
    if not apk_path:
        return

    br()
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
        t = prog.add_task("Mengekstrak seed dari APK...", total=None)
        seeds = extract_seed_from_apk(apk_path)
        prog.remove_task(t)

    if not seeds:
        err("Gagal mendapatkan seed dari APK.")
        return

    all_seed_values = list(dict.fromkeys(v for v in seeds.values() if v))
    info(f"Seed ditemukan: [cyan]{', '.join(all_seed_values)}[/cyan]")
    br()

    preset_author = ib.get("author", "")
    preset_email  = ib.get("email",  "")
    info(f"Author preset: [cyan]{preset_author or '(kosong)'}[/cyan] | Email: [cyan]{preset_email or '(kosong)'}[/cyan]")
    br()

    mode = questionary.select(
        "Mode input author/email:",
        choices=["Gunakan dari preset (otomatis)", "Input manual", "Brute force"],
        style=style
    ).ask()
    if not mode:
        return

    if "otomatis" in mode:
        pairs = [(preset_author, preset_email)]
    elif "manual" in mode:
        author = questionary.text("Author:", default=preset_author, style=style).ask() or ""
        email  = questionary.text("Email:",  default=preset_email,  style=style).ask() or ""
        pairs  = [(author.strip(), email.strip())]
    else:
        a_raw   = questionary.text("Authors (pisah koma):", default=preset_author, style=style).ask() or ""
        e_raw   = questionary.text("Emails (pisah koma):",  default=preset_email,  style=style).ask() or ""
        authors = [x.strip() for x in a_raw.split(",") if x.strip()] or [""]
        emails  = [x.strip() for x in e_raw.split(",") if x.strip()] or [""]
        if "" not in authors: authors.append("")
        if "" not in emails:  emails.append("")
        pairs = [(a, e) for a in authors for e in emails]

    br()
    total_combos = len(all_seed_values) * len(pairs)
    info(f"Mencoba [yellow]{total_combos}[/yellow] kombinasi (seed x author/email)...")
    br()

    results = []
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
        t = prog.add_task("Mendekripsi layer...", total=None)
        for seed_val in all_seed_values:
            for author, email in pairs:
                key = derive_key(seed_val, author, email)
                dec = decrypt_payload(payload, key)
                if dec:
                    sc = score_bytes(dec)
                    results.append((sc, seed_val, author, email, dec))
        prog.remove_task(t)

    if not results:
        err("Semua kombinasi gagal.")
        return

    results.sort(reverse=True)
    best_score, best_seed, best_author, best_email, best_data = results[0]

    tbl = Table(title="Hasil Dekripsi (Top 5)", border_style="cyan")
    tbl.add_column("Rank",   style="dim", width=6)
    tbl.add_column("Score",  width=8)
    tbl.add_column("Seed",   style="dim cyan")
    tbl.add_column("Author")
    tbl.add_column("Email")
    for i, (sc, sv, au, em, _) in enumerate(results[:5]):
        color = "green" if sc >= 70 else "yellow" if sc >= 40 else "red"
        tbl.add_row(
            str(i + 1),
            f"[{color}]{sc}/80[/{color}]",
            sv,
            au or "(kosong)",
            em or "(kosong)"
        )
    console.print(tbl)
    br()

    if best_score < 40:
        err(f"Score {best_score}/80 — key kemungkinan salah.")
        if not Confirm.ask("Tetap lanjut?"):
            return

    try:
        layers = json.loads(best_data)
        ok(f"Dekripsi berhasil — [bold green]{len(layers)}[/bold green] layer dipulihkan")
    except Exception:
        err("Hasil bukan JSON valid.")
        return

    br()
    out_path = questionary.text(
        "Simpan output ke:",
        default=klwp_path.replace(".klwp", "_unlocked.klwp"),
        style=style
    ).ask()
    if not out_path:
        return

    out_path = out_path.strip()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
        t = prog.add_task("Merekonstruksi preset...", total=None)
        success = False
        try:
            with tempfile.TemporaryDirectory() as tmp:
                # Ekstrak blank shell
                with zipfile.ZipFile(BLANK_KLWP) as z:
                    z.extractall(tmp)

                # Tulis preset.json yang sudah di-merge
                blank_preset = os.path.join(tmp, "preset.json")
                with open(blank_preset, "r", encoding="utf-8") as f:
                    shell = json.load(f)

                shell["preset_info"] = preset_data.get("preset_info", {})
                shell["preset_info"]["locked"] = False
                shell["preset_root"] = preset_data.get("preset_root", {})
                shell["preset_root"].pop("internal_readonly", None)
                shell["preset_root"]["viewgroup_items"] = layers

                with open(blank_preset, "w", encoding="utf-8") as f:
                    json.dump(shell, f, ensure_ascii=False, indent=2)

                # Salin aset dari preset original
                with zipfile.ZipFile(klwp_path) as zsrc:
                    for name in zsrc.namelist():
                        if name.startswith(("bitmaps/", "fonts/", "icons/")):
                            dest = os.path.join(tmp, name)
                            os.makedirs(os.path.dirname(dest), exist_ok=True)
                            with zsrc.open(name) as sf, open(dest, "wb") as df:
                                shutil.copyfileobj(sf, df)

                # Repack
                with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
                    for root, dirs, files in os.walk(tmp):
                        for file in files:
                            fp = os.path.join(root, file)
                            zout.write(fp, os.path.relpath(fp, tmp))

                success = True
        except Exception as e:
            err(f"Gagal rebuild: {e}")
        prog.remove_task(t)

    br()
    if success:
        size_kb = os.path.getsize(out_path) / 1024
        ok(f"Tersimpan: [bold cyan]{out_path}[/bold cyan] ({size_kb:.1f} KB)")
        br()
        console.print(Panel(
            "1. Pindah ke [cyan]/sdcard/Kustom/wallpapers/[/cyan]\n"
            "2. Buka KLWP -> Import\n"
            "3. Selesai",
            title="Langkah Selanjutnya",
            border_style="green",
            padding=(1, 2)
        ))

# ── Main Menu ─────────────────────────────────────────────────────────────────
MENU_CHOICES = [
    "1. Cek version release",
    "2. Cek author",
    "3. Cek locked status",
    "4. Download KLWP APK",
    "5. Teardown APK — cari seed",
    "6. Unlock preset",
    "──────────────────",
    "0. Exit",
]

MENU_ACTIONS = {
    "1": menu_check_release,
    "2": menu_check_author,
    "3": menu_check_locked,
    "4": menu_download_apk,
    "5": menu_teardown_apk,
    "6": menu_unlock_preset,
}

def main():
    while True:
        show_banner()
        choice = questionary.select(
            "Pilih navigasi:",
            choices=MENU_CHOICES,
            style=style,
            pointer="►",
            use_indicator=True
        ).ask()

        if choice is None or choice.startswith("0"):
            console.print("\n[dim]Keluar dari program...[/dim]\n")
            break

        if choice.startswith("──"):
            continue

        action = MENU_ACTIONS.get(choice[0])
        if action:
            action()
            pause()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[dim]Dibatalkan.[/dim]")
        sys.exit(0)
