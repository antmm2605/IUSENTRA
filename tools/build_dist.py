#!/usr/bin/env python3
"""
HACS Local Signer — Build cross-platform da Linux/macOS/Windows.

Genera in tools/dist/:
  - SetupLocalSigner-<versione>.exe        Windows offline (IExpress stub + CAB MSZIP)
  - InstallaLocalSigner-<versione>.command macOS  online  (download dal server)
  - InstallaLocalSigner-<versione>.run     Linux  online  (download dal server)
  - LocalSigner-<versione>.txt             release note

Uso:
  python3 tools/build_dist.py
  python3 tools/build_dist.py --base-url https://mio-server.example.com

L'EXE Windows e' un IExpress self-extracting offline self-contained:
lo stub PE (iexpress_stub.bin) + un CAB MSZIP con tutti i file embedded.
Non richiede internet, non richiede Execution Policy, funziona con doppio clic.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
import textwrap
import zlib
from datetime import datetime, timezone
from pathlib import Path

# ── Percorsi ───────────────────────────────────────────────────────────────────
TOOLS_DIR      = Path(__file__).resolve().parent
REPO_DIR       = TOOLS_DIR.parent
DIST_DIR       = TOOLS_DIR / "dist"
LS_PY          = TOOLS_DIR / "local_signer.py"
REQS_TXT       = TOOLS_DIR / "requirements_local_signer.txt"
INSTALL_PS1    = TOOLS_DIR / "installa_local_signer_locale.ps1"
UFFICI_JSON    = REPO_DIR / "pct" / "data" / "uffici_ministero.json"
IEXPRESS_STUB  = TOOLS_DIR / "iexpress_stub.bin"

BASE_URL_DEFAULT  = "https://studio-legale-pct-production.up.railway.app"
DOWNLOAD_PAGE     = f"{BASE_URL_DEFAULT}/impostazioni?tab=firma"

CAB_BLOCK_SIZE = 32768  # dimensione massima blocco CFDATA (non compresso)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _version() -> str:
    src = LS_PY.read_text(encoding="utf-8")
    m = re.search(r'(?m)^VERSION\s*=\s*"([^"]+)"', src)
    if not m:
        raise ValueError("VERSION non trovata in local_signer.py")
    return m.group(1)


def _dos_datetime() -> tuple[int, int]:
    """Restituisce (date, time) in formato DOS per i CFFILE header."""
    now = datetime.now()
    dos_date = ((now.year - 1980) << 9) | (now.month << 5) | now.day
    dos_time = (now.hour << 11) | (now.minute << 5) | (now.second // 2)
    return dos_date, dos_time


def _mszip_block(data: bytes) -> bytes:
    """Comprime un blocco in formato MSZIP: b'CK' + deflate raw."""
    # zlib.compress produce: 2-byte header + deflate + 4-byte Adler32
    # Vogliamo solo il deflate (strip header e checksum)
    deflate = zlib.compress(data, 6)[2:-4]
    return b"CK" + deflate


def _build_cab(files: list[tuple[str, bytes]]) -> bytes:
    """
    Crea un CAB Microsoft (MSZIP, compress_type=1) con i file specificati.
    Formato: CFHEADER + CFFOLDER + CFFILE[] + CFDATA[]
    Checksum = 0 (come IExpress originale).

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

    # ── Offsets struttura ─────────────────────────────────────────────────────
    # CFHEADER = 36, CFFOLDER = 8, poi i CFFILE
    first_file_offset = 36 + 8            # = 44
    first_data_offset = 36 + 8 + len(cffiles_bin)

    # ── CFDATA blocks ─────────────────────────────────────────────────────────
    all_data = b"".join(content for _, content in files)
    cfdata_bin = b""
    num_blocks = 0
    offset = 0
    while offset < len(all_data) or (not all_data and num_blocks == 0):
        block = all_data[offset : offset + CAB_BLOCK_SIZE]
        compressed = _mszip_block(block)
        cfdata_bin += struct.pack(
            "<IHH",
            0,                    # checksum = 0
            len(compressed),      # compressed_size
            len(block),           # uncompressed_size
        ) + compressed
        num_blocks += 1
        offset += len(block)
        if not all_data:
            break

    # ── Dimensione totale CAB ─────────────────────────────────────────────────
    cab_size = 36 + 8 + len(cffiles_bin) + len(cfdata_bin)

    # ── CFHEADER (36 byte) ────────────────────────────────────────────────────
    header = struct.pack(
        "<4sIIIIIBBHHHHH",
        b"MSCF",            # signature
        0,                  # reserved1
        cab_size,           # cabinet_size
        0,                  # reserved2
        first_file_offset,  # first_file_offset (offset al primo CFFILE)
        0,                  # reserved3
        3,                  # minor_version
        1,                  # major_version
        1,                  # num_folders
        num_files,          # num_files
        0,                  # flags
        0,                  # set_id
        0,                  # cabinet_index
    )

    # ── CFFOLDER (8 byte) ─────────────────────────────────────────────────────
    folder = struct.pack(
        "<IHH",
        first_data_offset,  # first_data_offset (offset al primo CFDATA)
        num_blocks,         # num_data_blocks
        1,                  # compress_type = MSZIP
    )

    return header + folder + cffiles_bin + cfdata_bin


# ── Generatori ─────────────────────────────────────────────────────────────────

def build_windows_exe(version: str) -> bytes:
    """
    Genera un installer Windows EXE offline self-contained.
    Formato: IExpress stub (iexpress_stub.bin) + CAB MSZIP con i file embedded.
    Lancia powershell.exe -ExecutionPolicy Bypass -File installa_local_signer_locale.ps1.
    Funziona con doppio clic, non richiede internet ne' permessi speciali.
    """
    stub = IEXPRESS_STUB.read_bytes()

    # PS1 con line endings CRLF per Windows
    ps1_crlf = INSTALL_PS1.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")

    # Release note embedded nel CAB
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    release_txt = (
        f"HACS Local Signer\r\n"
        f"Versione: {version}\r\n"
        f"Generato: {now}\r\n"
        f"Punto ufficiale download: {DOWNLOAD_PAGE}\r\n"
    ).encode("utf-8")

    files = [
        ("installa_local_signer_locale.ps1", ps1_crlf),
        ("local_signer.py",                  LS_PY.read_bytes()),
        ("requirements_local_signer.txt",    REQS_TXT.read_bytes()),
        ("uffici_ministero.json",            UFFICI_JSON.read_bytes()),
        ("local_signer_release.txt",         release_txt),
    ]

    cab = _build_cab(files)
    return stub + cab


def build_macos_command(version: str, base_url: str) -> str:
    allowed_origins = ",".join(sorted({
        base_url.rstrip("/"),
        BASE_URL_DEFAULT,
    }))
    return textwrap.dedent(f"""\
        #!/bin/bash
        # HACS Local Signer v{version} - Installer macOS
        # Punto ufficiale: {DOWNLOAD_PAGE}
        set -euo pipefail

        BASE_URL="{base_url}"
        ALLOWED_ORIGINS="{allowed_origins}"
        VERSION="{version}"
        DIR="$HOME/Library/Application Support/HACS/LocalSigner"
        DATA_DIR="$DIR/data"
        VENV="$DIR/.venv"
        PY="$VENV/bin/python3"
        PLIST="$HOME/Library/LaunchAgents/it.hacs.local-signer.plist"

        echo "HACS Local Signer v$VERSION - Installazione macOS"
        echo "Scarico da: $BASE_URL"

        mkdir -p "$DIR" "$DATA_DIR" "$(dirname "$PLIST")"

        if ! command -v python3 >/dev/null 2>&1; then
          echo "Python 3 non trovato. Scaricarlo da https://python.org"
          read -r -p "Premi Invio per uscire..." _; exit 1
        fi

        curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
        curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
        python3 -m venv "$VENV"
        "$PY" -m pip install --quiet --upgrade pip
        "$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography

        cat > "$PLIST" <<PLISTEOF
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
          <key>Label</key><string>it.hacs.local-signer</string>
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
        launchctl kickstart -k "gui/$(id -u)/it.hacs.local-signer"

        echo
        echo "Installazione completata. Local Signer v$VERSION pronto su http://127.0.0.1:27272"
        echo "Tornare su HACS e cliccare Riverifica."
        read -r -p "Premi Invio per chiudere..." _
    """)


def build_linux_run(version: str, base_url: str) -> str:
    allowed_origins = ",".join(sorted({
        base_url.rstrip("/"),
        BASE_URL_DEFAULT,
    }))
    return textwrap.dedent(f"""\
        #!/usr/bin/env bash
        # HACS Local Signer v{version} - Installer Linux
        # Punto ufficiale: {DOWNLOAD_PAGE}
        set -euo pipefail

        BASE_URL="{base_url}"
        ALLOWED_ORIGINS="{allowed_origins}"
        VERSION="{version}"
        DIR="${{XDG_DATA_HOME:-$HOME/.local/share}}/hacs/local-signer"
        DATA_DIR="$DIR/data"
        VENV="$DIR/.venv"
        PY="$VENV/bin/python"
        SERVICE_DIR="${{XDG_CONFIG_HOME:-$HOME/.config}}/systemd/user"
        SERVICE="$SERVICE_DIR/hacs-local-signer.service"

        echo "HACS Local Signer v$VERSION - Installazione Linux"
        echo "Scarico da: $BASE_URL"

        mkdir -p "$DIR" "$DATA_DIR" "$SERVICE_DIR"

        if ! command -v python3 >/dev/null 2>&1; then
          echo "Python 3 non trovato. Installarlo con il gestore pacchetti della distribuzione."
          read -r -p "Premi Invio per uscire..." _; exit 1
        fi

        curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
        curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
        python3 -m venv "$VENV"
        "$PY" -m pip install --quiet --upgrade pip
        "$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography

        cat > "$SERVICE" <<EOF
        [Unit]
        Description=HACS Local Signer
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
        systemctl --user enable --now hacs-local-signer.service

        echo
        echo "Installazione completata. Local Signer v$VERSION pronto su http://127.0.0.1:27272"
        echo "Tornare su HACS e cliccare Riverifica."
        read -r -p "Premi Invio per chiudere..." _
    """)


def build_release_note(version: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"HACS Local Signer\n"
        f"Versione: {version}\n"
        f"Generato: {now}\n"
        f"Piattaforme: Windows (EXE offline), macOS (.command), Linux (.run)\n"
        f"Punto ufficiale download: {DOWNLOAD_PAGE}\n"
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Build Local Signer dist packages")
    parser.add_argument(
        "--base-url",
        default=BASE_URL_DEFAULT,
        help=f"URL base del server HACS (default: {BASE_URL_DEFAULT})",
    )
    parser.add_argument(
        "--no-windows",
        action="store_true",
        help="Salta la generazione del pacchetto Windows (EXE offline)",
    )
    args = parser.parse_args()

    for path in [LS_PY, REQS_TXT, INSTALL_PS1, UFFICI_JSON]:
        if not path.exists():
            print(f"ERRORE: file sorgente non trovato: {path}", file=sys.stderr)
            sys.exit(1)

    if not args.no_windows and not IEXPRESS_STUB.exists():
        print(f"ERRORE: stub IExpress non trovato: {IEXPRESS_STUB}", file=sys.stderr)
        sys.exit(1)

    version = _version()
    base_url = args.base_url.rstrip("/")
    DIST_DIR.mkdir(exist_ok=True)

    print(f"Build HACS Local Signer v{version}")
    print(f"  Base URL: {base_url}")
    print(f"  Output:   {DIST_DIR}")
    print()

    # macOS
    mac_path = DIST_DIR / f"InstallaLocalSigner-{version}.command"
    mac_path.write_text(build_macos_command(version, base_url), encoding="utf-8")
    mac_path.chmod(0o755)
    print(f"  [OK] macOS   : {mac_path.name}")

    # Linux
    linux_path = DIST_DIR / f"InstallaLocalSigner-{version}.run"
    linux_path.write_text(build_linux_run(version, base_url), encoding="utf-8")
    linux_path.chmod(0o755)
    print(f"  [OK] Linux   : {linux_path.name}")

    # Windows EXE (IExpress stub + CAB MSZIP offline)
    if not args.no_windows:
        win_path = DIST_DIR / f"SetupLocalSigner-{version}.exe"
        total_kb = (LS_PY.stat().st_size + UFFICI_JSON.stat().st_size) // 1024
        print(f"  Genero Windows EXE offline (stub + CAB MSZIP, ~{total_kb}KB payload)...")
        exe_data = build_windows_exe(version)
        win_path.write_bytes(exe_data)
        # Aggiorna alias legacy
        alias_path = DIST_DIR / "SetupLocalSigner.exe"
        alias_path.write_bytes(exe_data)
        print(f"  [OK] Windows : {win_path.name}  ({win_path.stat().st_size // 1024}KB)")
        print(f"  [OK] Alias   : SetupLocalSigner.exe aggiornato")

    # Release note
    note_path = DIST_DIR / f"LocalSigner-{version}.txt"
    note_path.write_text(build_release_note(version), encoding="utf-8")
    print(f"  [OK] Note    : {note_path.name}")

    print()
    print(f"Build completata. {3 if not args.no_windows else 2} pacchetti generati in {DIST_DIR}")


if __name__ == "__main__":
    main()
