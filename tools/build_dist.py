#!/usr/bin/env python3
"""
IUSENTRA Local Signer — Build cross-platform da Linux/macOS/Windows.

Genera in tools/dist/:
  - SetupLocalSigner-<versione>.exe        Windows piccolo con builder IExpress storico
  - IUSENTRA-LocalSigner-<versione>.dmg     macOS (generato nativamente su macOS)
  - InstallaLocalSigner-<versione>.command  macOS, ripiego online controllato
  - InstallaLocalSigner-<versione>.run     Linux  online  (download dal server)
  - LocalSigner-<versione>.txt             release note

Uso:
  python3 tools/build_dist.py
  python3 tools/build_dist.py --base-url https://mio-server.example.com

L'EXE Windows usa il builder IExpress nativo, la stessa famiglia tecnica dei
pacchetti piccoli gia' funzionanti. Lo script installato disinstalla la vecchia
versione locale e installa quella corrente.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

# ── Percorsi ───────────────────────────────────────────────────────────────────
TOOLS_DIR      = Path(__file__).resolve().parent
REPO_DIR       = TOOLS_DIR.parent
DIST_DIR       = TOOLS_DIR / "dist"
LS_PY          = TOOLS_DIR / "local_signer.py"
FOREGROUND_HELPER_PY = TOOLS_DIR / "local_signer_foreground_helper.py"
WINDOWS_HTTP_PS1 = TOOLS_DIR / "local_signer_windows_http.ps1"
AI_BRIDGE_PY   = TOOLS_DIR / "local_ai_host_bridge.py"
LEX_CONTEXT_PY = TOOLS_DIR / "lex_document_context.py"
REQS_TXT       = TOOLS_DIR / "requirements_local_signer.txt"
INSTALL_PS1    = TOOLS_DIR / "installa_local_signer_locale.ps1"
UFFICI_JSON    = REPO_DIR / "pct" / "data" / "uffici_ministero.json"
UFFICI_PST_PUBBLICI_JSON = REPO_DIR / "pct" / "data" / "uffici_pst_pubblici.json"
LOCAL_SIGNER_MOD_DIR = REPO_DIR / "local_signer_mod"
VISIBLE_SIGNATURE_PY = REPO_DIR / "visible_signature.py"
IEXPRESS_STUB  = TOOLS_DIR / "iexpress_stub.bin"
WINDOWS_NATIVE_BUILDER = TOOLS_DIR / "build_local_signer_windows_exe.ps1"
MACOS_DMG_BUILDER = TOOLS_DIR / "build_local_signer_macos_dmg.sh"

BASE_URL_DEFAULT  = "https://app.iusentra.it"
DOWNLOAD_PAGE     = f"{BASE_URL_DEFAULT}/impostazioni?tab=firma"

CAB_BLOCK_SIZE = 32768  # dimensione massima blocco CFDATA (non compresso)

# Dimensione area riservata IExpress nel CFHEADER (replica esatta formato originale)
IEXPRESS_RESERVED_SIZE = 6144


# ── Helpers ────────────────────────────────────────────────────────────────────

def _version() -> str:
    src = LS_PY.read_text(encoding="utf-8")
    m = re.search(r'(?m)^VERSION\s*=\s*"([^"]+)"', src)
    if not m:
        raise ValueError("VERSION non trovata in local_signer.py")
    return m.group(1)


def _local_signer_mod_files() -> list[Path]:
    if not LOCAL_SIGNER_MOD_DIR.exists():
        raise FileNotFoundError(f"Modulo Local Signer non trovato: {LOCAL_SIGNER_MOD_DIR}")
    files = sorted(LOCAL_SIGNER_MOD_DIR.glob("*.py"))
    required = {
        "__init__.py",
        "ai_cache.py",
        "ai_handlers.py",
        "pec_bridge.py",
        "security.py",
        "server_bootstrap.py",
        "support_agent.py",
    }
    found = {path.name for path in files}
    missing = sorted(required - found)
    if missing:
        raise FileNotFoundError(
            "Modulo Local Signer incompleto: "
            + ", ".join(f"local_signer_mod/{name}" for name in missing)
        )
    return files


def _local_signer_mod_cab_files() -> list[tuple[str, bytes]]:
    return [
        (f"local_signer_mod__{path.name}", path.read_bytes())
        for path in _local_signer_mod_files()
    ]


def _local_signer_mod_download_lines(target_expr: str) -> str:
    lines = []
    for path in _local_signer_mod_files():
        name = path.name
        lines.append(
            f'curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/{name}" '
            f'-o "{target_expr}/{name}"'
        )
    return "\n".join(lines)


def _dos_datetime() -> tuple[int, int]:
    """Restituisce (date, time) in formato DOS per i CFFILE header."""
    now = datetime.now()
    dos_date = ((now.year - 1980) << 9) | (now.month << 5) | now.day
    dos_time = (now.hour << 11) | (now.minute << 5) | (now.second // 2)
    return dos_date, dos_time


def _build_cab(files: list[tuple[str, bytes]]) -> bytes:
    """
    Crea un CAB Microsoft compatibile IExpress (TYPE_NONE, nessuna compressione).

    Replica la struttura esatta dei CAB generati da IExpress originale:
      - flags=0x0004 (reserved fields present)
      - cbCFHeader=6144, cbCFFolder=0, cbCFData=0
      - Area riservata: 6144 byte di zeri (come wextract.exe originale)
      - typeCompress=0x0000 (TYPE_NONE — massima compatibilità con wextract.exe)
      - Checksum=0 per tutti i CFDATA block

    Senza questa struttura (flags=0x0004 + area riservata) wextract.exe rifiuta
    il CAB con "Impossibile eseguire questa app nel tuo PC".

    files: lista di (filename_ascii, content_bytes)
    """
    num_files = len(files)
    dos_date, dos_time = _dos_datetime()

    # ── CFFILE headers ────────────────────────────────────────────────────────
    cffiles_bin = b""
    offset_in_folder = 0
    for fname, content in files:
        fname_b = fname.encode("ascii") + b"\x00"
        cffiles_bin += struct.pack(
            "<IIHHHH",
            len(content),       # file_size
            offset_in_folder,   # file_offset_in_folder
            0,                  # folder_index
            dos_date,           # date
            dos_time,           # time
            0x20,               # attribs = ARCHIVE
        ) + fname_b
        offset_in_folder += len(content)

    # ── Struttura IExpress-compatibile ───────────────────────────────────────
    # CFHEADER standard (36 byte)
    # + reserved size fields (4 byte): cbCFHeader=6144, cbCFFolder=0, cbCFData=0
    # + reserved cabinet data (6144 byte di zeri)
    # + CFFOLDER (8 byte)
    # + CFFILE[] records
    # + CFDATA[] blocks

    CF_HEADER_SIZE  = 36
    CF_RESERVESIZES = 4   # cbCFHeader(2) + cbCFFolder(1) + cbCFData(1)
    CF_RESERVED     = IEXPRESS_RESERVED_SIZE  # 6144 byte di zeri
    CF_FOLDER_SIZE  = 8

    first_file_offset = (CF_HEADER_SIZE + CF_RESERVESIZES + CF_RESERVED
                         + CF_FOLDER_SIZE)
    first_data_offset = first_file_offset + len(cffiles_bin)

    # ── CFDATA blocks (TYPE_NONE: dati raw senza compressione) ───────────────
    all_data = b"".join(content for _, content in files)
    cfdata_bin = b""
    num_blocks = 0
    offset = 0
    while offset < len(all_data) or (not all_data and num_blocks == 0):
        block = all_data[offset : offset + CAB_BLOCK_SIZE]
        cfdata_bin += struct.pack(
            "<IHH",
            0,           # checksum = 0
            len(block),  # cbData == cbUncomp per TYPE_NONE
            len(block),  # cbUncomp
        ) + block
        num_blocks += 1
        offset += len(block)
        if not all_data:
            break

    # ── Dimensione totale CAB ─────────────────────────────────────────────────
    cab_size = (CF_HEADER_SIZE + CF_RESERVESIZES + CF_RESERVED
                + CF_FOLDER_SIZE + len(cffiles_bin) + len(cfdata_bin))

    # ── CFHEADER (36 byte) ────────────────────────────────────────────────────
    header = struct.pack(
        "<4sIIIIIBBHHHHH",
        b"MSCF",            # signature
        0,                  # reserved1
        cab_size,           # cabinet_size
        0,                  # reserved2
        first_file_offset,  # offset al primo CFFILE dall'inizio del CAB
        0,                  # reserved3
        3,                  # minor_version
        1,                  # major_version
        1,                  # num_folders
        num_files,          # num_files
        0x0004,             # flags: _A_RESERVE_PRESENT (richiesto da wextract.exe)
        0,                  # set_id
        0,                  # cabinet_index
    )

    # ── Reserved size fields (4 byte) ────────────────────────────────────────
    reserve_sizes = struct.pack(
        "<HBB",
        IEXPRESS_RESERVED_SIZE,  # cbCFHeader = 6144
        0,                        # cbCFFolder = 0
        0,                        # cbCFData = 0
    )

    # ── CFFOLDER (8 byte) ─────────────────────────────────────────────────────
    folder = struct.pack(
        "<IHH",
        first_data_offset,  # coffCabStart (offset al primo CFDATA dall'inizio CAB)
        num_blocks,         # cCFData
        0x0000,             # typeCompress = TYPE_NONE (massima compatibilità)
    )

    return (header
            + reserve_sizes
            + bytes(IEXPRESS_RESERVED_SIZE)   # 6144 byte di zeri
            + folder
            + cffiles_bin
            + cfdata_bin)


# ── Generatori ─────────────────────────────────────────────────────────────────

def build_windows_exe(version: str, base_url: str = BASE_URL_DEFAULT) -> bytes:
    """
    Genera l'installer Windows piccolo con il builder IExpress storico.

    Il parametro base_url resta per compatibilita' con i chiamanti esistenti:
    il builder PowerShell storico usa la URL ufficiale di produzione.
    """
    _ = base_url
    return build_windows_exe_native(version)


def build_windows_exe_native(version: str) -> bytes:
    """
    Genera l'EXE Windows usando IExpress nativo.

    Questa e' la strada preferita su Windows perche' replica il formato
    degli installer che hanno funzionato correttamente fino alla 1.5.9.
    Il builder custom resta come fallback tecnico per ambienti senza
    IExpress o non-Windows.
    """
    if os.name != "nt":
        raise RuntimeError("Builder Windows nativo disponibile solo su Windows.")
    if not WINDOWS_NATIVE_BUILDER.exists():
        raise FileNotFoundError(f"Builder PowerShell non trovato: {WINDOWS_NATIVE_BUILDER}")

    subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(WINDOWS_NATIVE_BUILDER),
        ],
        cwd=str(REPO_DIR),
        check=True,
    )

    win_path = DIST_DIR / f"SetupLocalSigner-{version}.exe"
    if not win_path.exists():
        raise FileNotFoundError(f"Build IExpress completata senza generare {win_path}")
    return win_path.read_bytes()


def build_macos_command(version: str, base_url: str) -> str:
    allowed_origins = ",".join(sorted({
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        base_url.rstrip("/"),
        BASE_URL_DEFAULT,
        "https://studio-legale-pct-production.up.railway.app",
    }))
    return textwrap.dedent(f"""\
        #!/bin/bash
        # IUSENTRA Local Signer v{version} - Installer macOS
        # Punto ufficiale: {DOWNLOAD_PAGE}
        set -euo pipefail

        BASE_URL="{base_url}"
        ALLOWED_ORIGINS="{allowed_origins}"
        VERSION="{version}"
        DIR="$HOME/Library/Application Support/IUSENTRA/LocalSigner"
        DATA_DIR="$DIR/data"
        MOD_DIR="$DIR/local_signer_mod"
        VENV="$DIR/.venv"
        PY="$VENV/bin/python3"
        PLIST="$HOME/Library/LaunchAgents/it.iusentra.local-signer.plist"

        echo "IUSENTRA Local Signer v$VERSION - Installazione macOS"
        echo "Scarico da: $BASE_URL"

        mkdir -p "$DIR" "$DATA_DIR" "$MOD_DIR" "$(dirname "$PLIST")"

        if ! command -v python3 >/dev/null 2>&1; then
          echo "Python 3 non trovato. Scaricarlo da https://python.org"
          read -r -p "Premi Invio per uscire..." _; exit 1
        fi

curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-ai-bridge" -o "$DIR/local_ai_host_bridge.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/lex-document-context" -o "$DIR/lex_document_context.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/visible-signature" -o "$DIR/visible_signature.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici-pst-pubblici" -o "$DATA_DIR/uffici_pst_pubblici.json"
{_local_signer_mod_download_lines("$MOD_DIR")}
        python3 -m venv "$VENV"
        "$PY" -m pip install --quiet --upgrade pip
        "$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography pyhanko pyhanko-certvalidator zeep pdfplumber mammoth pypdf reportlab pillow

        cat > "$PLIST" <<PLISTEOF
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
          <key>Label</key><string>it.iusentra.local-signer</string>
          <key>ProgramArguments</key>
          <array><string>$PY</string><string>$DIR/local_signer.py</string></array>
          <key>EnvironmentVariables</key>
          <dict>
            <key>PCT_LOCAL_SIGNER_ALLOWED_ORIGINS</key><string>$ALLOWED_ORIGINS</string>
          </dict>
          <key>RunAtLoad</key><true/>
          <key>KeepAlive</key><true/>
          <key>WorkingDirectory</key><string>$DIR</string>
        </dict>
        </plist>
        PLISTEOF

        launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
        launchctl bootstrap "gui/$(id -u)" "$PLIST"
        launchctl kickstart -k "gui/$(id -u)/it.iusentra.local-signer"

        echo
        echo "Installazione completata. Local Signer v$VERSION pronto su http://127.0.0.1:27272"
        echo "Tornare su IUSENTRA e cliccare Riverifica."
        read -r -p "Premi Invio per chiudere..." _
    """)


def build_macos_dmg(version: str, command_path: Path) -> Path | None:
    """Crea il DMG Finder soltanto su macOS, dove hdiutil e' disponibile."""
    if sys.platform != "darwin":
        return None
    if not MACOS_DMG_BUILDER.exists():
        raise FileNotFoundError(f"Builder DMG macOS non trovato: {MACOS_DMG_BUILDER}")
    if not command_path.exists():
        raise FileNotFoundError(f"Installer macOS non trovato: {command_path}")

    dmg_path = DIST_DIR / f"IUSENTRA-LocalSigner-{version}.dmg"
    subprocess.run(
        ["/bin/bash", str(MACOS_DMG_BUILDER), version, str(command_path), str(dmg_path)],
        cwd=str(REPO_DIR),
        check=True,
    )
    if not dmg_path.exists() or dmg_path.stat().st_size == 0:
        raise RuntimeError(f"Build DMG completata senza generare {dmg_path}")
    return dmg_path


def build_linux_run(version: str, base_url: str) -> str:
    allowed_origins = ",".join(sorted({
        "http://127.0.0.1:8080",
        "http://localhost:8080",
        base_url.rstrip("/"),
        BASE_URL_DEFAULT,
        "https://studio-legale-pct-production.up.railway.app",
    }))
    return textwrap.dedent(f"""\
        #!/usr/bin/env bash
        # IUSENTRA Local Signer v{version} - Installer Linux
        # Punto ufficiale: {DOWNLOAD_PAGE}
        set -euo pipefail

        BASE_URL="{base_url}"
        ALLOWED_ORIGINS="{allowed_origins}"
        VERSION="{version}"
        DIR="${{XDG_DATA_HOME:-$HOME/.local/share}}/iusentra/local-signer"
        DATA_DIR="$DIR/data"
        MOD_DIR="$DIR/local_signer_mod"
        VENV="$DIR/.venv"
        PY="$VENV/bin/python"
        SERVICE_DIR="${{XDG_CONFIG_HOME:-$HOME/.config}}/systemd/user"
        SERVICE="$SERVICE_DIR/iusentra-local-signer.service"

        echo "IUSENTRA Local Signer v$VERSION - Installazione Linux"
        echo "Scarico da: $BASE_URL"

        mkdir -p "$DIR" "$DATA_DIR" "$MOD_DIR" "$SERVICE_DIR"

        if ! command -v python3 >/dev/null 2>&1; then
          echo "Python 3 non trovato. Installarlo con il gestore pacchetti della distribuzione."
          read -r -p "Premi Invio per uscire..." _; exit 1
        fi

curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-ai-bridge" -o "$DIR/local_ai_host_bridge.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/lex-document-context" -o "$DIR/lex_document_context.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/visible-signature" -o "$DIR/visible_signature.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici-pst-pubblici" -o "$DATA_DIR/uffici_pst_pubblici.json"
{_local_signer_mod_download_lines("$MOD_DIR")}
        python3 -m venv "$VENV"
        "$PY" -m pip install --quiet --upgrade pip
        "$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography pyhanko pyhanko-certvalidator zeep pdfplumber mammoth pypdf reportlab pillow

        cat > "$SERVICE" <<EOF
        [Unit]
        Description=IUSENTRA Local Signer
        After=network.target

        [Service]
        Type=simple
        WorkingDirectory=$DIR
        Environment=PCT_LOCAL_SIGNER_ALLOWED_ORIGINS=$ALLOWED_ORIGINS
        ExecStart=$PY $DIR/local_signer.py
        Restart=on-failure

        [Install]
        WantedBy=default.target
        EOF

        systemctl --user daemon-reload
        systemctl --user enable --now iusentra-local-signer.service

        echo
        echo "Installazione completata. Local Signer v$VERSION pronto su http://127.0.0.1:27272"
        echo "Tornare su IUSENTRA e cliccare Riverifica."
        read -r -p "Premi Invio per chiudere..." _
    """)


def build_release_note(version: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"IUSENTRA Local Signer\n"
        f"Versione: {version}\n"
        f"Generato: {now}\n"
        f"Piattaforme: Windows (EXE IExpress), macOS (.dmg quando generato su Mac; .command di ripiego), Linux (.run)\n"
        f"Ponte PEC locale: test SMTP e invio dal PC dello studio\n"
        f"Ricerca diretta via signer di default: PDP, PAT, PTT/SIGIT\n"
        f"Raccolta file browser ufficiale: PDP, PAT, PTT/SIGIT dai download locali\n"
        f"Proxy PST allineato a Documentazione servizi web v1.69 / A1 WSDL Catalog v1.52\n"
        f"PST: pacchetto allineato al riuso sessione view/download per evitare prompt PIN ripetuti\n"
        f"Punto ufficiale download: {DOWNLOAD_PAGE}\n"
    )


def build_windows_ps1(version: str) -> str:
    header = (
        f"# IUSENTRA Local Signer Setup v{version}\n"
        f"# Pacchetto generato il {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"# Punto ufficiale download: {DOWNLOAD_PAGE}\n\n"
    )
    return header + INSTALL_PS1.read_text(encoding="utf-8")


def write_windows_support_files(dist_dir: Path) -> list[Path]:
    copied: list[Path] = []
    for source, target_name in (
        (LS_PY, "local_signer.py"),
        (FOREGROUND_HELPER_PY, "local_signer_foreground_helper.py"),
        (WINDOWS_HTTP_PS1, "local_signer_windows_http.ps1"),
        (AI_BRIDGE_PY, "local_ai_host_bridge.py"),
        (LEX_CONTEXT_PY, "lex_document_context.py"),
        (VISIBLE_SIGNATURE_PY, "visible_signature.py"),
        (REQS_TXT, "requirements_local_signer.txt"),
        (UFFICI_JSON, "uffici_ministero.json"),
        (UFFICI_PST_PUBBLICI_JSON, "uffici_pst_pubblici.json"),
    ):
        target = dist_dir / target_name
        shutil.copyfile(source, target)
        copied.append(target)
    module_dir = dist_dir / "local_signer_mod"
    module_dir.mkdir(exist_ok=True)
    module_sources = _local_signer_mod_files()
    expected = {source.name for source in module_sources}
    for stale in module_dir.glob("*.py"):
        if stale.name not in expected:
            stale.unlink()
    for source in module_sources:
        target = module_dir / source.name
        shutil.copyfile(source, target)
        copied.append(target)
    return copied


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Build Local Signer dist packages")
    parser.add_argument(
        "--base-url",
        default=BASE_URL_DEFAULT,
        help=f"URL base del server IUSENTRA (default: {BASE_URL_DEFAULT})",
    )
    parser.add_argument(
        "--no-windows",
        action="store_true",
        help="Salta la generazione del pacchetto Windows (EXE)",
    )
    parser.add_argument(
        "--native-windows",
        action="store_true",
        help=(
            "Forza il builder Windows IExpress nativo. E' gia' il default su Windows."
        ),
    )
    args = parser.parse_args()

    for path in [LS_PY, WINDOWS_HTTP_PS1, REQS_TXT, INSTALL_PS1, UFFICI_JSON, VISIBLE_SIGNATURE_PY, LOCAL_SIGNER_MOD_DIR]:
        if not path.exists():
            print(f"ERRORE: file sorgente non trovato: {path}", file=sys.stderr)
            sys.exit(1)

    version = _version()
    base_url = args.base_url.rstrip("/")
    DIST_DIR.mkdir(exist_ok=True)

    print(f"Build IUSENTRA Local Signer v{version}")
    print(f"  Base URL: {base_url}")
    print(f"  Output:   {DIST_DIR}")
    print()

    # macOS: il .command e' sempre mantenuto nel DMG come installatore leggibile
    # e serve da ripiego quando il rilascio viene prodotto fuori da macOS.
    mac_path = DIST_DIR / f"InstallaLocalSigner-{version}.command"
    mac_path.write_text(build_macos_command(version, base_url), encoding="utf-8")
    mac_path.chmod(0o755)
    print(f"  [OK] macOS   : {mac_path.name}")
    dmg_path = build_macos_dmg(version, mac_path)
    if dmg_path is not None:
        print(f"  [OK] macOS   : {dmg_path.name}  ({dmg_path.stat().st_size // 1024}KB)")

    # Linux
    linux_path = DIST_DIR / f"InstallaLocalSigner-{version}.run"
    linux_path.write_text(build_linux_run(version, base_url), encoding="utf-8")
    linux_path.chmod(0o755)
    print(f"  [OK] Linux   : {linux_path.name}")

    # Windows: EXE IExpress generabile SOLO da Windows. Su Linux/macOS e con
    # --no-windows scrive comunque i sorgenti in dist/ (il server li serve via
    # /polisWeb/local-signer/download/*: le installazioni esistenti si
    # auto-aggiornano da li') e lascia un marker che indica di rigenerare
    # l'EXE da Windows alla prossima build su quella piattaforma.
    can_build_windows_exe = (
        not args.no_windows
        and os.name == "nt"
        and WINDOWS_NATIVE_BUILDER.exists()
    )
    if can_build_windows_exe:
        win_path = DIST_DIR / f"SetupLocalSigner-{version}.exe"
        alias_path = DIST_DIR / "SetupLocalSigner.exe"
        ps1_path = DIST_DIR / f"InstallaLocalSigner-{version}.ps1"
        print("  Genero Windows EXE piccolo con IExpress storico...")
        exe_data = build_windows_exe(version, base_url)
        win_path.write_bytes(exe_data)
        alias_path.write_bytes(exe_data)
        pending_marker = DIST_DIR / f"SetupLocalSigner-{version}.exe.PENDING-WINDOWS-BUILD.txt"
        pending_marker.unlink(missing_ok=True)
        ps1_path.write_text(build_windows_ps1(version), encoding="utf-8")
        support_files = write_windows_support_files(DIST_DIR)
        print(f"  [OK] Windows : {win_path.name}  ({win_path.stat().st_size // 1024}KB)")
        print(f"  [OK] Alias   : SetupLocalSigner.exe aggiornato")
        print(f"  [OK] Support : {ps1_path.name}")
        print(f"  [OK] Files   : {', '.join(path.name for path in support_files)}")
    else:
        # Sorgenti in dist/ sempre allineati alla versione corrente (sono cio'
        # che il server distribuisce ai client via /update). Solo l'EXE
        # IExpress richiede Windows: quando manca, l'alias SetupLocalSigner.exe
        # (ultima build Windows committata) resta l'installer di prima
        # installazione e i client si aggiornano poi dai sorgenti via /update.
        support_files = write_windows_support_files(DIST_DIR)
        ps1_path = DIST_DIR / f"InstallaLocalSigner-{version}.ps1"
        ps1_path.write_text(build_windows_ps1(version), encoding="utf-8")
        if not args.no_windows:
            reason = (
                "ambiente non-Windows"
                if os.name != "nt"
                else f"builder mancante: {WINDOWS_NATIVE_BUILDER}"
            )
            print(
                f"  [!!] Windows : EXE versionato non generato ({reason}); "
                "alias SetupLocalSigner.exe usato come fallback di prima installazione."
            )
        print(f"  [OK] Support : {ps1_path.name}")
        print(f"  [OK] Files   : {', '.join(path.name for path in support_files)}")

    # Release note
    note_path = DIST_DIR / f"LocalSigner-{version}.txt"
    note_path.write_text(build_release_note(version), encoding="utf-8")
    print(f"  [OK] Note    : {note_path.name}")

    print()
    print(f"Build completata. {3 if not args.no_windows else 2} pacchetti generati in {DIST_DIR}")


if __name__ == "__main__":
    main()
