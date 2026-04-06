#!/usr/bin/env python3
"""
HACS Local Signer — Build cross-platform da Linux/macOS/Windows.

Genera in tools/dist/:
  - SetupLocalSigner-<versione>.exe        Windows offline (IExpress SFX, doppio clic)
  - InstallaLocalSigner-<versione>.command macOS  online  (download dal server)
  - InstallaLocalSigner-<versione>.run     Linux  online  (download dal server)
  - LocalSigner-<versione>.txt             release note

Uso:
  python3 tools/build_dist.py
  python3 tools/build_dist.py --base-url https://mio-server.example.com

Il EXE Windows e' un IExpress SFX auto-estrattore offline self-contained:
contiene tutti i file necessari nel CAB embedded. Non richiede internet.
Lo stub IExpress e' in tools/iexpress_stub.bin (estratto da build Windows originale).
"""

from __future__ import annotations

import argparse
import base64
import re
import struct
import sys
import textwrap
import zlib
from datetime import datetime, timezone
from pathlib import Path

# ── Percorsi ───────────────────────────────────────────────────────────────────
TOOLS_DIR    = Path(__file__).resolve().parent
REPO_DIR     = TOOLS_DIR.parent
DIST_DIR     = TOOLS_DIR / "dist"
LS_PY        = TOOLS_DIR / "local_signer.py"
REQS_TXT     = TOOLS_DIR / "requirements_local_signer.txt"
INSTALL_PS1  = TOOLS_DIR / "installa_local_signer_locale.ps1"
UFFICI_JSON  = REPO_DIR / "pct" / "data" / "uffici_ministero.json"
IEXPRESS_STUB = TOOLS_DIR / "iexpress_stub.bin"  # Stub IExpress (PE senza CAB)

BASE_URL_DEFAULT  = "https://studio-legale-pct-production.up.railway.app"
DOWNLOAD_PAGE     = f"{BASE_URL_DEFAULT}/impostazioni?tab=firma"

# ── Helpers ────────────────────────────────────────────────────────────────────

def _version() -> str:
    src = LS_PY.read_text(encoding="utf-8")
    m = re.search(r'(?m)^VERSION\s*=\s*"([^"]+)"', src)
    if not m:
        raise ValueError("VERSION non trovata in local_signer.py")
    return m.group(1)


def _make_mszip_cab(files: list[tuple[str, bytes]]) -> bytes:
    """
    Genera un archivio CAB MSZIP con i file forniti.
    files: lista di (nome_file, contenuto_bytes)
    Restituisce i byte del CAB completo.
    """
    MAX_BLOCK = 32768

    # Concatena tutti i file in uno stream unico
    stream = b"".join(content for _, content in files)

    # Blocchi CFDATA (MSZIP = raw deflate con prefisso 'CK')
    blocks: list[tuple[bytes, int]] = []
    pos = 0
    while pos < len(stream):
        chunk = stream[pos : pos + MAX_BLOCK]
        raw_deflate = zlib.compress(chunk, 6)[2:-4]  # rimuovi header/trailer zlib
        blocks.append((b"CK" + raw_deflate, len(chunk)))
        pos += len(chunk)

    # Date/time DOS per i file
    d = datetime.now(timezone.utc)
    dos_date = ((d.year - 1980) << 9) | (d.month << 5) | d.day
    dos_time = (d.hour << 11) | (d.minute << 5) | (d.second // 2)

    # Costruisci entries CFFILE
    file_entries = b""
    offset_in_stream = 0
    for fname, content in files:
        fname_b = fname.encode("ascii") + b"\x00"
        file_entries += struct.pack(
            "<IIHHHH",
            len(content),       # cbFile
            offset_in_stream,   # uoffFolderStart
            0,                  # iFolder
            dos_date,
            dos_time,
            0x20,               # attributi: ARCHIVE
        ) + fname_b
        offset_in_stream += len(content)

    CFHEADER_SIZE = 36
    CFFOLDER_SIZE = 8
    first_file_offset  = CFHEADER_SIZE + CFFOLDER_SIZE
    first_data_offset  = first_file_offset + len(file_entries)
    data_size = sum(8 + len(b) for b, _ in blocks)   # 4(csum)+2(cbData)+2(cbUncomp)+data
    cabinet_size = first_data_offset + data_size

    header = struct.pack(
        "<4sIIIIIBBHHHHH",
        b"MSCF", 0, cabinet_size, 0,
        first_file_offset, 0,
        3, 1,                # versione 1.3
        1,                   # num_folders
        len(files),          # num_files
        0,                   # flags (nessun RESERVE_PRESENT)
        0, 0,                # setID, iCabinet
    )
    assert len(header) == CFHEADER_SIZE

    folder = struct.pack("<IHH", first_data_offset, len(blocks), 0x0001)  # MSZIP
    assert len(folder) == CFFOLDER_SIZE

    data_blocks = b"".join(
        struct.pack("<IHH", 0, len(mszip), uncomp) + mszip
        for mszip, uncomp in blocks
    )

    return header + folder + file_entries + data_blocks


# ── Generatori ─────────────────────────────────────────────────────────────────

def build_windows_exe(version: str) -> bytes:
    """
    Genera un installer Windows EXE offline self-contained (IExpress SFX).
    Struttura: stub IExpress (tools/iexpress_stub.bin) + CAB MSZIP con tutti i file.
    Doppio clic su Windows per installare — non richiede internet.
    """
    if not IEXPRESS_STUB.exists():
        raise FileNotFoundError(
            f"Stub IExpress non trovato: {IEXPRESS_STUB}\n"
            "Il file viene estratto automaticamente da un .exe esistente in tools/dist/.\n"
            "Esegui: python3 -c \""
            "from pathlib import Path; "
            "d=sorted(Path('tools/dist').glob('SetupLocalSigner-*.exe')); "
            "s=open(d[-1],'rb').read(); "
            "cab=s.index(b'MSCF'); "
            "open('tools/iexpress_stub.bin','wb').write(s[:cab])\""
        )

    stub = IEXPRESS_STUB.read_bytes()
    now  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    release_note = (
        f"HACS Local Signer\nVersione: {version}\nGenerato: {now}\n"
        f"Piattaforme: Windows (EXE offline), macOS (.command), Linux (.run)\n"
        f"Punto ufficiale download: {DOWNLOAD_PAGE}\n"
    )

    files_to_pack = [
        ("installa_local_signer_locale.ps1", INSTALL_PS1.read_bytes()),
        ("local_signer.py",                  LS_PY.read_bytes()),
        ("requirements_local_signer.txt",    REQS_TXT.read_bytes()),
        ("uffici_ministero.json",            UFFICI_JSON.read_bytes()),
        ("local_signer_release.txt",         release_note.encode("utf-8")),
    ]

    cab = _make_mszip_cab(files_to_pack)
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
        f"Piattaforme: Windows (PS1 offline), macOS (.command), Linux (.run)\n"
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
        help="Salta la generazione del pacchetto Windows (PS1 offline è grande ~800KB)",
    )
    args = parser.parse_args()

    for path in [LS_PY, REQS_TXT, INSTALL_PS1, UFFICI_JSON]:
        if not path.exists():
            print(f"ERRORE: file sorgente non trovato: {path}", file=sys.stderr)
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

    # Windows EXE (IExpress SFX offline)
    if not args.no_windows:
        win_path = DIST_DIR / f"SetupLocalSigner-{version}.exe"
        print(f"  Genero Windows EXE offline (IExpress SFX + CAB {LS_PY.stat().st_size//1024}KB + {UFFICI_JSON.stat().st_size//1024}KB)...")
        exe_data = build_windows_exe(version)
        win_path.write_bytes(exe_data)
        # Aggiorna alias legacy
        alias_path = DIST_DIR / "SetupLocalSigner.exe"
        alias_path.write_bytes(exe_data)
        print(f"  [OK] Windows : {win_path.name}  ({win_path.stat().st_size//1024}KB)")
        print(f"  [OK] Alias   : SetupLocalSigner.exe aggiornato")

    # Release note
    note_path = DIST_DIR / f"LocalSigner-{version}.txt"
    note_path.write_text(build_release_note(version), encoding="utf-8")
    print(f"  [OK] Note    : {note_path.name}")

    print()
    print(f"Build completata. {3 if not args.no_windows else 2} pacchetti generati in {DIST_DIR}")


if __name__ == "__main__":
    main()
